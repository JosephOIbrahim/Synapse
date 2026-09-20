#!/usr/bin/env python3
"""BP8-CRUX mutation runner -- crucible-authored, never replays a builder's proved_it_bites.

Runs one mutation at a time against a scratch clone of a leg branch:
  1. baseline: the selector must be GREEN in the untouched tree (proves binding);
  2. for each mutation: assert the `old` text occurs exactly `count` times, write the
     mutated file, run the selector, restore the ORIGINAL BYTES, confirm `git diff`
     is empty for that file;
  3. baseline again at the end: must still be GREEN.
A mutation is REDDENED when every test it names FAILED/ERRORED; SURVIVED when the
selector stayed green (a guard hole); MIXED otherwise. Collateral failures are
recorded, never hidden. The runner edits only the scratch clone it is pointed at.

Usage:
  python mutate.py --leg watchdog --tree <scratch-clone> --out <log.json> [--hython <exe>]
  python mutate.py --leg timeouts --tree <scratch-clone> --out <log.json>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CHAT = "python/synapse/panel/chat_panel.py"
ROUTER = "python/synapse/routing/router.py"
HANDLERS = "python/synapse/server/handlers.py"
WD_TESTS = ["tests/test_response_watchdog.py"]
TO_TESTS = ["tests/test_bp8_timeouts.py"]

WATCHDOG = [
    {
        "id": "W-M1",
        "title": "delete the timer stop on the REPLY path only (mandated crucible mutation)",
        "file": CHAT,
        "old": (
            '    def _on_response(self, response):\n'
            '        """Handle server response from route_chat."""\n'
            '        self._clear_waiting_state()\n'
        ),
        "new": (
            '    def _on_response(self, response):\n'
            '        """Handle server response from route_chat."""\n'
            '        self._waiting_for_response = False\n'
            '        self._chat.hide_typing_indicator()\n'
        ),
        "expect_red": ["test_delivered_response_stops_watchdog_and_no_late_line",
                       "test_real_qtimer_fires_and_stop_prevents_it"],
        "expect_survivor": False,
    },
    {
        "id": "W-M2",
        "title": "the shared helper no longer hides the typing indicator",
        "file": CHAT,
        "old": (
            '        self._waiting_for_response = False\n'
            '        self._chat.hide_typing_indicator()\n'
            '\n'
            '    def _send_message(self):\n'
        ),
        "new": (
            '        self._waiting_for_response = False\n'
            '\n'
            '    def _send_message(self):\n'
        ),
        "expect_red": ["test_watchdog_hang_clears_state_and_shows_one_line",
                       "test_connection_error_clears_waiting_via_shared_helper",
                       "test_disconnect_status_clears_waiting_via_shared_helper"],
        "expect_survivor": False,
    },
    {
        "id": "W-M3",
        "title": "_on_connection_error no longer clears the waiting state",
        "file": CHAT,
        "old": (
            '        self._clear_waiting_state()\n'
            '        self._chat.append_system_message(error_msg)\n'
        ),
        "new": (
            '        self._chat.append_system_message(error_msg)\n'
        ),
        "expect_red": ["test_connection_error_clears_waiting_via_shared_helper"],
        "expect_survivor": False,
    },
    {
        "id": "W-M4",
        "title": "_on_status_changed(False) no longer clears the waiting state",
        "file": CHAT,
        "old": (
            '            self._clear_waiting_state()\n'
            '            _sc = _ERROR_COLOR\n'
        ),
        "new": (
            '            _sc = _ERROR_COLOR\n'
        ),
        "expect_red": ["test_disconnect_status_clears_waiting_via_shared_helper"],
        "expect_survivor": False,
    },
    {
        "id": "W-M5",
        "title": "the watchdog fire appends the line but never clears the waiting state",
        "file": CHAT,
        "old": (
            '        self._clear_waiting_state()\n'
            '        self._chat.append_system_message(NO_RESPONSE_LINE)\n'
        ),
        "new": (
            '        self._chat.append_system_message(NO_RESPONSE_LINE)\n'
        ),
        "expect_red": ["test_watchdog_hang_clears_state_and_shows_one_line",
                       "test_real_qtimer_fires_and_stop_prevents_it"],
        "expect_survivor": False,
    },
    {
        "id": "W-M6",
        "title": "GUARD-HOLE PROBE: delete the production `timeout.connect` line in createInterface",
        "file": CHAT,
        "old": '        self._response_watchdog.timeout.connect(self._on_response_timeout)\n',
        "new": '',
        "expect_red": [],
        "expect_survivor": True,
    },
    {
        "id": "W-M7",
        "title": "GUARD-HOLE PROBE: production timer made repeating (setSingleShot False)",
        "file": CHAT,
        "old": '        self._response_watchdog.setSingleShot(True)\n',
        "new": '        self._response_watchdog.setSingleShot(False)\n',
        "expect_red": [],
        "expect_survivor": True,
    },
    {
        "id": "W-M8",
        "title": "GUARD-HOLE PROBE: production interval set to 1 ms instead of WATCHDOG_TIMEOUT_MS",
        "file": CHAT,
        "old": '        self._response_watchdog.setInterval(WATCHDOG_TIMEOUT_MS)\n',
        "new": '        self._response_watchdog.setInterval(1)\n',
        "expect_red": [],
        "expect_survivor": True,
    },
    {
        "id": "W-M9",
        "title": "margin dropped: budget equals the 30 s slow-op budget exactly",
        "file": CHAT,
        "old": '_WATCHDOG_MARGIN_MS = 5000\n',
        "new": '_WATCHDOG_MARGIN_MS = 0\n',
        "expect_red": ["test_budget_is_slow_op_plus_margin_named_not_literal"],
        "expect_survivor": False,
    },
    {
        "id": "W-M10",
        "title": "the send path never arms the watchdog",
        "file": CHAT,
        "old": (
            '        if self._response_watchdog is not None:\n'
            '            self._response_watchdog.start()\n'
            '        ctx = self._gather_context_if_stale()\n'
        ),
        "new": (
            '        ctx = self._gather_context_if_stale()\n'
        ),
        "expect_red": ["test_watchdog_hang_clears_state_and_shows_one_line",
                       "test_delivered_response_stops_watchdog_and_no_late_line",
                       "test_failed_send_stops_watchdog_no_zombie_timer"],
        "expect_survivor": False,
    },
]

TIMEOUTS = [
    {
        "id": "T-M1",
        "title": "remove the wall-clock timeout from the tier-2 future (mandated crucible mutation)",
        "file": ROUTER,
        "old": '                response = _future.result(timeout=_t2)\n',
        "new": '                response = _future.result()\n',
        "expect_red": ["test_try_tier2_returns_within_timeout"],
        "expect_survivor": False,
    },
    {
        "id": "T-M2",
        "title": "remove the wall-clock timeout from the tier-3 future (mandated crucible mutation)",
        "file": ROUTER,
        "old": '                response = _future.result(timeout=_t3)\n',
        "new": '                response = _future.result()\n',
        "expect_red": ["test_tier3_sync_returns_within_timeout"],
        "expect_survivor": False,
    },
    {
        "id": "T-M3",
        "title": "delete the handler's `except Exception` arm (a raising route() propagates)",
        "file": HANDLERS,
        "old": (
            '        except Exception as exc:\n'
            '            _log.warning("route() failed: %s", exc)\n'
            '            return {\n'
            '                "response": f"The request could not be completed: {exc}",\n'
            '                "tier": "error",\n'
            '                "success": False,\n'
            '                "error": str(exc),\n'
            '            }\n'
        ),
        "new": '',
        "expect_red": ["test_handler_raising_route_replies_with_response_and_tier"],
        "expect_survivor": False,
    },
    {
        "id": "T-M4",
        "title": "remove the overall deadline from the handler's route() future",
        "file": HANDLERS,
        "old": '            result = _future.result(timeout=deadline)\n',
        "new": '            result = _future.result()\n',
        "expect_red": ["test_handler_timed_out_route_replies_with_response_and_tier"],
        "expect_survivor": False,
    },
    {
        "id": "T-M5",
        "title": "the timeout reply loses its `tier` key (ws_bridge.py:339 would drop it)",
        "file": HANDLERS,
        "old": (
            '                "response": "The request timed out before it could be answered. Please try again.",\n'
            '                "tier": "timeout",\n'
        ),
        "new": (
            '                "response": "The request timed out before it could be answered. Please try again.",\n'
        ),
        "expect_red": ["test_handler_timed_out_route_replies_with_response_and_tier"],
        "expect_survivor": False,
    },
    {
        "id": "T-M6",
        "title": "GUARD-HOLE PROBE: drop the transport-layer `timeout=_t2` kwarg that reaches the SDK",
        "file": ROUTER,
        "old": (
            '                    messages=[{"role": "user", "content": user_message}],\n'
            '                    timeout=_t2,\n'
            '                )\n'
        ),
        "new": (
            '                    messages=[{"role": "user", "content": user_message}],\n'
            '                )\n'
        ),
        "expect_red": [],
        "expect_survivor": True,
    },
    {
        "id": "T-M7",
        "title": "GUARD-HOLE PROBE: the tier-2 timeout branch no longer records the STANDARD failure metric",
        "file": ROUTER,
        "old": (
            '                latency_ms = (time.monotonic() - start) * 1000\n'
            '                self._record_metric(RoutingTier.STANDARD, latency_ms, False)\n'
            '                logger.warning("Tier 2 timed out after %.1fs", _t2)\n'
        ),
        "new": (
            '                latency_ms = (time.monotonic() - start) * 1000\n'
            '                logger.warning("Tier 2 timed out after %.1fs", _t2)\n'
        ),
        "expect_red": [],
        "expect_survivor": True,
    },
    {
        "id": "T-M8",
        "title": "the tier-2 timeout result carries an EMPTY answer (a silent turn)",
        "file": ROUTER,
        "old": '                    answer="The request timed out before the standard tier could respond.",\n',
        "new": '                    answer="",\n',
        "expect_red": ["test_try_tier2_returns_within_timeout"],
        "expect_survivor": False,
    },
]

LEGS = {"watchdog": (WATCHDOG, WD_TESTS), "timeouts": (TIMEOUTS, TO_TESTS)}

_SUMMARY_RE = re.compile(r"(\d+ passed|\d+ failed|\d+ error|\d+ skipped)")
_ROW_RE = re.compile(r"^(PASSED|FAILED|ERROR)\s+(\S+::\S+?)(?:\s+-\s+(.*))?$")


def run_pytest(tree: Path, selector: list[str], interpreter: str, env_extra: dict) -> dict:
    # -vv: pytest stops width-truncating the short-summary failure reason (right_reason evidence).
    cmd = [interpreter, "-m", "pytest", "-p", "no:cacheprovider", "-vv", "-rA", *selector]
    env = dict(os.environ)
    env.update(env_extra)
    t0 = time.monotonic()
    proc = subprocess.run(cmd, cwd=str(tree), capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace")
    out = proc.stdout + proc.stderr
    rows: dict[str, dict] = {}
    for line in out.splitlines():
        m = _ROW_RE.match(line.strip())
        if m:
            name = m.group(2).split("::")[-1]
            rows[name] = {"status": m.group(1), "reason": (m.group(3) or "")[:300]}
        elif line.strip().startswith("SKIPPED"):
            rows.setdefault("_skipped", {"status": "SKIPPED", "reason": line.strip()[:300]})
    summary = ""
    for line in out.splitlines():
        if _SUMMARY_RE.search(line) and ("passed" in line or "failed" in line or "error" in line):
            summary = line.strip().strip("=").strip()
    return {"cmd": " ".join(cmd), "returncode": proc.returncode, "rows": rows, "summary": summary,
            "elapsed_s": round(time.monotonic() - t0, 2), "tail": out[-1500:]}


def git_clean(tree: Path, rel: str) -> bool:
    return subprocess.run(["git", "diff", "--quiet", "--", rel], cwd=str(tree)).returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--leg", choices=list(LEGS), required=True)
    ap.add_argument("--tree", required=True, help="scratch clone of the leg branch")
    ap.add_argument("--out", required=True)
    ap.add_argument("--hython", default=None, help="run the selector under this hython instead of CPython")
    ap.add_argument("--only", default=None, help="comma-separated mutation ids")
    a = ap.parse_args()

    tree = Path(a.tree).resolve()
    mutations, selector = LEGS[a.leg]
    if a.only:
        keep = set(a.only.split(","))
        mutations = [m for m in mutations if m["id"] in keep]
    interpreter = a.hython or sys.executable
    env_extra = {"QT_QPA_PLATFORM": "offscreen"} if a.hython else {}
    label = "hython" if a.hython else "cpython"

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tree), capture_output=True,
                          text=True).stdout.strip()
    log = {"leg": a.leg, "tree": str(tree), "head": head, "interpreter": interpreter,
           "interpreter_label": label, "selector": selector,
           "started": time.strftime("%Y-%m-%dT%H:%M:%S"), "baseline_before": None,
           "mutations": [], "baseline_after": None}

    base = run_pytest(tree, selector, interpreter, env_extra)
    log["baseline_before"] = base
    print(f"[baseline/{label}] {base['summary']}  rc={base['returncode']}")
    if base["returncode"] != 0:
        print("baseline is not green -- refusing to mutate (binding or environment problem)")
        Path(a.out).write_text(json.dumps(log, indent=2), encoding="utf-8")
        return 2

    for m in mutations:
        rel = m["file"]
        path = tree / rel
        original = path.read_bytes()
        text = original.decode("utf-8")
        count = m.get("count", 1)
        found = text.count(m["old"])
        entry = {"id": m["id"], "title": m["title"], "file": rel, "expect_red": m["expect_red"],
                 "expect_survivor": m["expect_survivor"], "old_occurrences": found}
        if found != count:
            entry["result"] = "NOT_APPLIED"
            entry["evidence"] = f"expected {count} occurrence(s) of the old text, found {found}"
            log["mutations"].append(entry)
            print(f"[{m['id']}] NOT_APPLIED ({entry['evidence']})")
            continue
        path.write_bytes(text.replace(m["old"], m["new"]).encode("utf-8"))
        try:
            run = run_pytest(tree, selector, interpreter, env_extra)
        finally:
            path.write_bytes(original)
        entry["restored_clean"] = git_clean(tree, rel)
        entry["run"] = {"summary": run["summary"], "returncode": run["returncode"],
                        "elapsed_s": run["elapsed_s"], "rows": run["rows"],
                        "output_tail": run["tail"]}
        failed = {n for n, r in run["rows"].items() if r["status"] in ("FAILED", "ERROR")}
        expected = set(m["expect_red"])
        # A test that SKIPS under this interpreter cannot redden here; drop it from the expectation.
        present = {n for n in run["rows"] if n != "_skipped"}
        expected_here = {n for n in expected if n in present}
        if run["returncode"] == 0 and not failed:
            entry["result"] = "SURVIVED"
        elif expected_here and expected_here <= failed:
            entry["result"] = "REDDENED"
        elif failed:
            entry["result"] = "MIXED"
        else:
            entry["result"] = "SURVIVED"
        entry["reddened_tests"] = sorted(failed)
        entry["collateral"] = sorted(failed - expected)
        entry["expected_not_reddened"] = sorted(expected_here - failed)
        entry["expected_absent_under_interpreter"] = sorted(expected - present)
        entry["right_reason"] = {n: run["rows"][n]["reason"] for n in sorted(failed)}
        entry["verdict_vs_expectation"] = (
            "as expected" if (entry["result"] == "SURVIVED") == m["expect_survivor"]
            and (m["expect_survivor"] or entry["result"] == "REDDENED") else "UNEXPECTED")
        log["mutations"].append(entry)
        print(f"[{m['id']}] {entry['result']} ({entry['verdict_vs_expectation']}) "
              f"red={sorted(failed)} restored_clean={entry['restored_clean']} {run['summary']}")

    after = run_pytest(tree, selector, interpreter, env_extra)
    log["baseline_after"] = after
    log["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"[baseline-after/{label}] {after['summary']}  rc={after['returncode']}")
    Path(a.out).write_text(json.dumps(log, indent=2), encoding="utf-8")
    return 0 if after["returncode"] == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
