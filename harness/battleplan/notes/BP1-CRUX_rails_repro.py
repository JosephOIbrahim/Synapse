#!/usr/bin/env python3
"""BP1-CRUX independent reproduction of the RAILS tiny-cap halt.

The crucible does not reuse the builder's proofB ledger. It drives the SAME
engine (harness/rails.py, imported from the leg checkout) with its own run
names and writes its OWN ledger artifact, then asserts the hard stop and that
no ledger field is an estimate (every token field is a measured int or the
literal 'UNKNOWN').

Run:  python BP1-CRUX_rails_repro.py <rails_worktree> <out_runs_dir> <date>
"""
import json
import sys
import time
from pathlib import Path

RAILS_WT = Path(sys.argv[1]).resolve()
OUT_RUNS = Path(sys.argv[2]).resolve()
DATE = sys.argv[3]

sys.path.insert(0, str(RAILS_WT / "harness"))
import rails  # noqa: E402
from rails import Rails, BudgetExceeded, resolve_model, UNKNOWN  # noqa: E402

LEGS = [
    {"id": "CRUX-TRIVIAL-1", "tier": "mechanical"},
    {"id": "CRUX-TRIVIAL-2", "tier": "reasoning"},
    {"id": "CRUX-TRIVIAL-3", "tier": "mechanical"},
]


def prepare(leg):
    t0 = time.perf_counter_ns()
    model = resolve_model(leg["tier"])          # real rails_exec.json lookup
    wall_ms = round((time.perf_counter_ns() - t0) / 1e6, 3)
    return model, wall_ms


def no_estimate(ledger):
    """Every token field is a measured int OR the literal 'UNKNOWN' — never a
    float proxy, never a bare 0 substituted for unobtainable."""
    bad = []
    def check(where, v):
        if not (v == UNKNOWN or isinstance(v, int)):
            bad.append((where, v))
    check("totals.tokens_in", ledger["totals"]["tokens_in"])
    check("totals.tokens_out", ledger["totals"]["tokens_out"])
    for lg in ledger["legs"]:
        check(f"{lg['leg']}.tokens_in", lg["tokens_in"])
        check(f"{lg['leg']}.tokens_out", lg["tokens_out"])
    return bad


def main():
    result = {"reproduced_by": "BP1-CRUX", "engine": str(RAILS_WT / "harness" / "rails.py")}

    # control: under-cap run completes
    ra = Rails(run="bp1-crux-rails-control", cap=f"{len(LEGS)+1}turns", date=DATE, runs_dir=OUT_RUNS)
    for leg in LEGS:
        model, wall_ms = prepare(leg)
        ra.charge(leg["id"], model, wall_ms=wall_ms)
    la = ra.close()
    result["control"] = {"status": la["status"], "path": str(ra.ledger_path()),
                         "no_estimate_violations": no_estimate(la)}

    # tiny-cap run halts on the 2nd charge (cap=1turn, 3 legs)
    rb = Rails(run="bp1-crux-rails-tinycap", cap="1turns", date=DATE, runs_dir=OUT_RUNS)
    halted = False
    lb = None
    refused = None
    for leg in LEGS:
        model, wall_ms = prepare(leg)
        try:
            rb.charge(leg["id"], model, wall_ms=wall_ms)
        except BudgetExceeded as e:
            halted, lb, refused = True, e.ledger, leg["id"]
            break
    result["tinycap"] = {
        "halted": halted,
        "refused_leg": refused,
        "status": (lb or {}).get("status"),
        "reason": (lb or {}).get("reason"),
        "enforced_unit": (lb or {}).get("enforced_unit"),
        "remaining_turns": (lb or {}).get("remaining", {}).get("turns"),
        "path": str(rb.ledger_path()),
        "no_estimate_violations": no_estimate(lb) if lb else "N/A",
    }

    # CLI exit-7 path (the exact seam orchestrate.ps1 calls): open then over-cap charge
    import subprocess
    run = "bp1-crux-rails-cli"
    subprocess.run([sys.executable, str(RAILS_WT / "harness" / "rails.py"), "open",
                    "--run", run, "--cap", "1turns", "--date", DATE,
                    "--runs-dir", str(OUT_RUNS)], capture_output=True, text=True)
    c1 = subprocess.run([sys.executable, str(RAILS_WT / "harness" / "rails.py"), "charge",
                         "--run", run, "--leg", "CLI-1", "--tier", "mechanical",
                         "--date", DATE, "--runs-dir", str(OUT_RUNS)], capture_output=True, text=True)
    c2 = subprocess.run([sys.executable, str(RAILS_WT / "harness" / "rails.py"), "charge",
                         "--run", run, "--leg", "CLI-2", "--tier", "reasoning",
                         "--date", DATE, "--runs-dir", str(OUT_RUNS)], capture_output=True, text=True)
    result["cli"] = {"charge1_exit": c1.returncode, "charge2_exit": c2.returncode,
                     "expected": "charge1=0 (admitted), charge2=7 (blocked:budget)"}

    result["verdict"] = {
        "hard_stop_reproduced": halted and (lb or {}).get("status") == "blocked"
                                 and (lb or {}).get("reason") == "budget",
        "cli_exit7_on_overcap": c1.returncode == 0 and c2.returncode == 7,
        "no_estimate_anywhere": not (result["control"]["no_estimate_violations"]
                                     or (result["tinycap"]["no_estimate_violations"] or [])),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
