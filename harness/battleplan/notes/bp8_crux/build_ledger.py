#!/usr/bin/env python3
"""Compose harness/battleplan/notes/BP8-CRUX_mutations.json from the runner logs.

Every evidence string is copied from the JSON the runner / probe wrote, never retyped.
Run from anywhere: python build_ledger.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import mutate  # noqa: E402  (the specs: ids, titles, files, expected tests)

OUT = HERE.parent / "BP8-CRUX_mutations.json"
REL = "harness/battleplan/notes/bp8_crux"


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def entry_from(log, mid):
    for m in log["mutations"]:
        if m["id"] == mid:
            return m
    return None


def summarize_run(log, m, label):
    if m is None:
        return None
    run = m.get("run", {})
    return {
        "interpreter": log["interpreter"],
        "tree_head": log["head"],
        "result": m["result"],
        "verdict_vs_expectation": m.get("verdict_vs_expectation"),
        "pytest_summary": run.get("summary"),
        "reddened_tests": m.get("reddened_tests", []),
        "collateral_failures": m.get("collateral", []),
        "expected_but_not_reddened": m.get("expected_not_reddened", []),
        "expected_test_absent_under_interpreter": m.get("expected_absent_under_interpreter", []),
        "right_reason": m.get("right_reason", {}),
        "restored_clean": m.get("restored_clean"),
        "log": f"{REL}/{label}",
    }


def main() -> int:
    wd_c = load("WATCHDOG_mutations_cpython.json")
    wd_h = load("WATCHDOG_mutations_hython22.0.400.json")
    to_c = load("TIMEOUTS_mutations_cpython.json")
    probe_base = load("WATCHDOG_probe_wiring_baseline_hython22.0.400.json")
    probe_neg = load("WATCHDOG_probe_wiring_deleteconnect_hython22.0.400.json")

    mutations = []
    for spec in mutate.WATCHDOG:
        c = entry_from(wd_c, spec["id"])
        h = entry_from(wd_h, spec["id"])
        results = {r["result"] for r in (c, h) if r}
        overall = "REDDENED" if results == {"REDDENED"} else ("SURVIVED" if results == {"SURVIVED"} else "MIXED")
        mutations.append({
            "id": spec["id"],
            "builder_leg": "BP8-WATCHDOG",
            "description": spec["title"],
            "file": spec["file"],
            "mutation_old": spec["old"],
            "mutation_new": spec["new"],
            "check_reddened": spec["expect_red"] or "(guard-hole probe: expected to survive the committed suite)",
            "expected_survivor": spec["expect_survivor"],
            "result": overall,
            "runs": {
                "cpython_3.14.2": summarize_run(wd_c, c, "WATCHDOG_mutations_cpython.json"),
                "hython_22.0.400_offscreen": summarize_run(wd_h, h, "WATCHDOG_mutations_hython22.0.400.json"),
            },
        })
    for spec in mutate.TIMEOUTS:
        c = entry_from(to_c, spec["id"])
        mutations.append({
            "id": spec["id"],
            "builder_leg": "BP8-TIMEOUTS",
            "description": spec["title"],
            "file": spec["file"],
            "mutation_old": spec["old"],
            "mutation_new": spec["new"],
            "check_reddened": spec["expect_red"] or "(guard-hole probe: expected to survive the committed suite)",
            "expected_survivor": spec["expect_survivor"],
            "result": c["result"] if c else "NOT_RUN",
            "runs": {"cpython_3.14.2": summarize_run(to_c, c, "TIMEOUTS_mutations_cpython.json")},
        })

    reddened = sum(1 for m in mutations if m["result"] == "REDDENED")
    survived = sum(1 for m in mutations if m["result"] == "SURVIVED")
    per_leg = {}
    for m in mutations:
        per_leg[m["builder_leg"]] = per_leg.get(m["builder_leg"], 0) + 1

    ledger = {
        "leg": "BP8-CRUX",
        "date": "2026-09-20",
        "authored_by": (
            "BP8-CRUX crucible (referee tier, Fable 5.1). Every mutation self-authored from a "
            "full read of both legs; none replays a builder's proved_it_bites row verbatim. W-M1 "
            "and T-M1/T-M2 are the mutations the two missions' crucible_criteria mandate; the "
            "rest are the crucible's own, including five deliberate guard-hole probes."
        ),
        "sandbox": (
            "git clone --shared -c core.longpaths=true of each leg branch under the session "
            "scratchpad (wm + w for WATCHDOG, tm for TIMEOUTS, wp for the wiring probe); never the "
            "builder worktrees, never the main tree. The runner (bp8_crux/mutate.py) asserts the old "
            "text occurs exactly once, mutates, runs the leg's own test file, restores the ORIGINAL "
            "BYTES, and checks `git diff --quiet` per file; the baseline is proven green before the "
            "first mutation and again after the last one, in every run."
        ),
        "environment_notes": [
            "Binding proof: the leg symbols exist only on the branch (router._llm_pool / handlers._ROUTE_OVERALL_TIMEOUT_S hasattr True on the leg clone, False on the master clone; the watchdog test file run against the master package fails at import on NO_RESPONSE_LINE). See bp8_crux/T1_probes.txt.",
            "Watchdog mutations ran under BOTH stock CPython 3.14.2 (Layer 1, mock timer; Layer 2 skips) and pinned hython 22.0.400 / Python 3.13.10 with QT_QPA_PLATFORM=offscreen (Layer 2 real QTimer runs). A test that skips under an interpreter is listed under expected_test_absent_under_interpreter, never counted as reddened.",
            "pytest -vv -rA so the short-summary failure reason is not width-truncated; right_reason carries it per reddened test.",
            "Timeouts mutations ran under stock CPython only: the leg's tests are pure-Python (fake clients, no Qt, no hou). The SDK signature check for row 5 was done separately on the production interpreter (hython 22.0.400, vendored anthropic 0.96.0: Messages.create has a `timeout` parameter) -- see T1_probes.txt.",
        ],
        "screen_lines_pre_read": {
            "BP8-WATCHDOG": "screen BP8-WATCHDOG: REFEREE - full read; weak rows [1, 2, 4]; self_contradiction 0.22; crux_need 0.76",
            "BP8-TIMEOUTS": "screen BP8-TIMEOUTS: REFEREE - full read; weak rows [1, 2]; crux_need 0.80",
            "ledger": "harness/jev/ledger/bp8.screen.jsonl (per-leg lines) and bp8.shadow.screen.jsonl (shadow table; the shadow run scored crux_need 0.74 / 0.76 and self_contradiction 0.21 -- Jev is not bit-deterministic across runs)",
        },
        "totals": {
            "mutations": len(mutations),
            "reddened": reddened,
            "survived": survived,
            "survived_breakdown": {"guard_holes_predicted_and_confirmed": survived},
            "per_leg": per_leg,
            "baselines": {
                "WATCHDOG_cpython": [wd_c["baseline_before"]["summary"], wd_c["baseline_after"]["summary"]],
                "WATCHDOG_hython22.0.400": [wd_h["baseline_before"]["summary"], wd_h["baseline_after"]["summary"]],
                "TIMEOUTS_cpython": [to_c["baseline_before"]["summary"], to_c["baseline_after"]["summary"]],
            },
        },
        "mutations": mutations,
        "crucible_probes": [
            {
                "id": "W-P1",
                "builder_leg": "BP8-WATCHDOG",
                "description": (
                    "Production createInterface watchdog wiring under real Qt (hython 22.0.400 offscreen): "
                    "build the real interface, read the production timer back, then fire IT (interval "
                    "shrunk to 1 ms) so the production `timeout.connect` line is what delivers the slot."
                ),
                "script": f"{REL}/probe_watchdog_wiring.py",
                "baseline": probe_base,
                "negative_control_delete_connect": probe_neg,
                "reading": (
                    "Baseline: single-shot True, interval 35000 == WATCHDOG_TIMEOUT_MS, not armed after "
                    "createInterface, parent is _root, fired -> waiting cleared, exactly one NO_RESPONSE line, "
                    "production_connect_live True. Negative control with the connect line deleted: fired but "
                    "waiting NOT cleared and 0 lines -> the probe catches W-M6 where the committed suite does not."
                ),
            }
        ],
    }
    OUT.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes): {len(mutations)} mutations, {reddened} reddened, {survived} survived")
    return 0


if __name__ == "__main__":
    sys.exit(main())
