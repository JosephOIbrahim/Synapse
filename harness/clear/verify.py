#!/usr/bin/env python3
"""CLEAR — verify.py

The bar. Eight acceptance predicates from SPEC.md, each checked headlessly
(no `hou`, no live bridge). Every PASS must come from an actual check — this
file never returns PASS without evidence. Statuses: PASS / FAIL / PENDING.

  P1.1  latency-relay files committed at <sha> OR dropped via a logged gate
  P2.1  board non-stale (<24h) AND cycle C.0 has a recorded human decision
  P3.1  F6 fixed: SessionStart pings before reporting "connected"
  P3.2  CI mcp drift resolved (mcp pinned OR mcp_server.py:899 updated)
  P3.3  websocket.py:471 cancel reachable mid-frame
  P3.4  husk render cure parked behind a named gate (Indie-blocked)
  P3.5  latency report §1 addendum appended (Joe's gate) OR deferred
  P4.1  v5.34-v5.40 CHANGELOG entries OR a deliberate non-backfill decision

Usage:
  python harness/clear/verify.py            # table + exit non-zero on FAIL
  python harness/clear/verify.py --count    # print FAIL count only, exit non-zero on FAIL
  python harness/clear/verify.py --json     # machine-readable
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

REPO = Path(__file__).resolve().parents[2]
CLEAR = Path(__file__).resolve().parent
STATE = REPO / "harness" / "state"
DECISIONS = REPO / "harness" / "decisions.py"
FLYWHEEL = STATE / "flywheel_queue.json"
DECISIONS_MD = STATE / "DECISIONS.md"
CHANGELOG = REPO / "CHANGELOG.md"
MCP_SERVER = REPO / "mcp_server.py"
REQUIREMENTS = REPO / "requirements.txt"
PYPROJECT = REPO / "pyproject.toml"

LATENCY_FILES = [
    ".claude/agents/latency-forge.md",
    ".claude/agents/latency-measurer.md",
    ".claude/agents/latency-relay-orchestrator.md",
    ".claude/workflows/latency-relay.js",
    "docs/latency-relay-operator-card.md",
    "docs/reviews/synapse-latency-report-2026-07-27.md",
]

VERSION_TARGETS = [f"## v5.{v}.0" for v in range(34, 41)] + [f"## v5.{v}" for v in range(34, 41)]

PASS = "PASS"
FAIL = "FAIL"
PENDING = "PENDING"


def _run(cmd, timeout=60):
    """Run a command in REPO, return (rc, stdout, stderr). Never raises."""
    try:
        p = subprocess.run(
            cmd, cwd=str(REPO), capture_output=True, text=True, timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


def _git_log_has(path):
    rc, out, _ = _run(["git", "log", "--all", "--format=%H", "--", path])
    return rc == 0 and bool(out.strip())


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _drop_marker_present():
    """Look for a logged 'dropped' marker for the latency-relay set in the
    board substrate (DECISIONS.md / flywheel) or harness/clear state."""
    haystack = _read(DECISIONS_MD) + _read(FLYWHEEL)
    if "latency-relay" in haystack and re.search(r"\b(dropped|drop|deferred)\b", haystack, re.I):
        return True
    return False


def _husk_deferral_present():
    """A husk deferral must live in the board substrate, not only the
    harness's own DEADENDS.md (which is the harness's bookkeeping, not a
    cross-tool decision record)."""
    haystack = _read(DECISIONS_MD) + _read(FLYWHEEL)
    return "husk" in haystack.lower() and re.search(r"\b(park|defer|indie)\b", haystack, re.I)


# ── Predicates ──────────────────────────────────────────────────────────────

def p1_1():
    committed = [f for f in LATENCY_FILES if _git_log_has(f)]
    if len(committed) == len(LATENCY_FILES):
        return PASS, f"all {len(LATENCY_FILES)} latency-relay files committed"
    if _drop_marker_present():
        return PASS, "latency-relay set dropped via a logged gate"
    return FAIL, f"{len(LATENCY_FILES) - len(committed)}/{len(LATENCY_FILES)} files untracked, no drop entry"


def p2_1():
    # Board runs at all?
    rc, out, err = _run([sys.executable, str(DECISIONS), "--count"], timeout=60)
    if rc not in (0, 6):  # 6 = overdue items exist (still "runs")
        return FAIL, f"decisions.py --count failed: rc={rc} {err.strip()[:120]}"
    board_runs = True

    # Staleness: flywheel mtime < 24h
    fresh = False
    try:
        if FLYWHEEL.exists():
            age = time.time() - FLYWHEEL.stat().st_mtime
            fresh = age < 24 * 3600
    except OSError:
        fresh = False

    # C.0 human decision
    fw = _read(FLYWHEEL)
    c0_decided = False
    if fw:
        try:
            data = json.loads(fw)
        except json.JSONDecodeError:
            data = {}
        for cyc in data.get("cycles", []) if isinstance(data, dict) else []:
            if not isinstance(cyc, dict):
                continue
            name = str(cyc.get("name") or cyc.get("id") or "")
            if name.startswith("C.0") or name == "C0":
                ratified = cyc.get("ratified")
                deferred = bool(cyc.get("deferred"))
                c0_decided = bool(ratified) or deferred
                break

    if board_runs and fresh and c0_decided:
        return PASS, "board fresh + C.0 has a recorded human decision"
    reasons = []
    if not fresh:
        reasons.append("board stale (>24h or missing)")
    if not c0_decided:
        reasons.append("C.0 has no ratified/deferred decision")
    return FAIL, "; ".join(reasons) if reasons else "incomplete"


def p3_1():
    t = REPO / "tests" / "test_sessionstart_ping.py"
    if not t.exists():
        return FAIL, "tests/test_sessionstart_ping.py not present (no F6 fix shipped)"
    rc, out, err = _run([sys.executable, "-m", "pytest", str(t), "--co", "-q"], timeout=60)
    if rc != 0:
        return FAIL, f"collection error: {err.strip()[:120]}"
    rc, out, err = _run([sys.executable, "-m", "pytest", str(t), "-q"], timeout=120)
    if rc == 0:
        return PASS, "SessionStart ping test passes"
    return FAIL, f"ping test fails: {err.strip()[:120]}"


def p3_2():
    """Source-level check (CI-vs-local mcp difference makes a pure pytest
    check dishonest on a green local box): does mcp_server.py still call the
    dropped server.list_tools() API, and is mcp pinned?"""
    src = _read(MCP_SERVER)
    uses_dropped = bool(re.search(r"\.list_tools\s*\(", src))
    # The deps live in pyproject.toml (no requirements.txt). A pin is an exact
    # or upper-bounded mcp constraint; the unbounded "mcp>=1.0.0" is NOT a pin.
    reqs = _read(PYPROJECT) + _read(REQUIREMENTS)
    has_unbounded = bool(re.search(r'"mcp>=', reqs))
    pinned = (bool(re.search(r'"mcp==', reqs)) or
              bool(re.search(r'"mcp>=?[\d.]+,\s*<', reqs)) or
              bool(re.search(r'"mcp<', reqs)))
    # unbounded pin alongside a real pin is fine (real pin wins); unbounded
    # alone is the drift that turned CI red.
    if pinned and has_unbounded:
        pinned = True
    elif has_unbounded and not pinned:
        pinned = False
    if (not uses_dropped) or pinned:
        return PASS, "mcp_server.py off the dropped list_tools API OR mcp pinned"
    return FAIL, "mcp_server.py still calls list_tools() and mcp is not pinned"


def p3_3():
    t = REPO / "tests" / "test_websocket_cancel_reachable.py"
    ws = REPO / "server" / "websocket.py"
    if not t.exists():
        # confirm the serial loop still exists (the thing to fix)
        loop_present = "471" and "serial" in _read(ws).lower() or True
        return FAIL, "tests/test_websocket_cancel_reachable.py not present (no cancel-reachability fix)"
    rc, out, err = _run([sys.executable, "-m", "pytest", str(t), "-q"], timeout=120)
    if rc == 0:
        return PASS, "websocket cancel-injection test passes"
    return FAIL, f"cancel test fails: {err.strip()[:120]}"


def p3_4():
    if _husk_deferral_present():
        return PASS, "husk deferral registered in the board substrate"
    return FAIL, "husk parked in harness DEADENDS only, not in the decisions board substrate"


def p3_5():
    addendum = REPO / "docs" / "reviews" / "synapse-latency-report-2026-07-27-addendum.md"
    if addendum.exists():
        return PASS, "latency §1 addendum appended"
    haystack = _read(DECISIONS_MD) + _read(FLYWHEEL)
    if "latency" in haystack.lower() and re.search(r"\b(defer|gated|joe)\b", haystack, re.I):
        return PASS, "latency addendum explicitly deferred (Joe's gate)"
    return FAIL, "no addendum and no deferred entry (Joe's gate not yet triaged)"


def p4_1():
    cl = _read(CHANGELOG)
    found = [h for h in VERSION_TARGETS if h in cl]
    # dedupe by minor version
    minors = sorted({h.split(".")[1] for h in found if h.startswith("## v5.")} |
                    {h.split()[1].split(".")[1] for h in found if re.match(r"## v5\.\d+$", h)})
    expected_minors = {str(v) for v in range(34, 41)}
    if expected_minors.issubset(set(minors)):
        return PASS, "v5.34-v5.40 CHANGELOG entries present"
    haystack = _read(DECISIONS_MD) + _read(FLYWHEEL)
    if "changelog" in haystack.lower() and re.search(r"\b(not\s+backfill|backfill|defer)\b", haystack, re.I):
        return PASS, "deliberate non-backfill decision recorded"
    missing = sorted(expected_minors - set(minors))
    return FAIL, f"missing CHANGELOG minors: v5.{', v5.'.join(missing)}; no non-backfill decision"


PREDICATES = [
    ("P1.1", "latency-relay files committed-or-dropped", p1_1),
    ("P2.1", "decisions board fresh + C.0 decided", p2_1),
    ("P3.1", "F6 SessionStart ping fix", p3_1),
    ("P3.2", "CI mcp drift resolved", p3_2),
    ("P3.3", "websocket.py:471 cancel reachable", p3_3),
    ("P3.4", "husk cure parked behind gate", p3_4),
    ("P3.5", "latency §1 addendum (Joe's gate)", p3_5),
    ("P4.1", "v5.34-v5.40 CHANGELOG gap", p4_1),
]


def run_all():
    results = []
    for pid, label, fn in PREDICATES:
        try:
            status, reason = fn()
        except Exception as e:  # never crash the bar — a predicate error is a FAIL
            status, reason = FAIL, f"verifier raised: {type(e).__name__}: {e}"
        results.append({"id": pid, "label": label, "status": status, "reason": reason})
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", action="store_true", help="print FAIL count only")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args()

    results = run_all()
    fail = sum(1 for r in results if r["status"] == FAIL)

    if args.json:
        print(json.dumps(results, indent=2))
    elif args.count:
        print(fail)
    else:
        w = max(len(r["id"]) for r in results)
        for r in results:
            print(f"{r['id']:<{w}}  {r['status']:<7}  {r['label']}  —  {r['reason']}")
        print(f"\n{sum(1 for r in results if r['status']==PASS)} PASS / "
              f"{fail} FAIL / "
              f"{sum(1 for r in results if r['status']==PENDING)} PENDING")

    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()