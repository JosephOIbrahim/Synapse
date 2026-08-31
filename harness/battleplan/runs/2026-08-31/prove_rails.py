# prove_rails.py - the BP1-RAILS proof (Target 5), reproducible.
#
# Produces two ledger artifacts in this directory by driving the REAL rails.py
# engine over control_manifest.json:
#   ledger_bp1-rails-proofA.json  - a capped run that COMPLETES under cap
#   ledger_bp1-rails-proofB.json  - a run with a deliberately tiny cap that HALTS
#                                   with status "blocked", reason "budget"
#
# The legs are dry (a real leg would spend real tokens), so tokens_in/tokens_out
# are the literal UNKNOWN and enforcement falls to the turns floor - the exact
# fallback the mission requires. wall_ms is MEASURED (real monotonic elapsed of
# preparing each dispatch, seam lookup included), never an estimate.
#
# Re-run:  python harness/battleplan/runs/2026-08-31/prove_rails.py
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / "harness"))

import rails  # noqa: E402
from rails import Rails, BudgetExceeded, resolve_model  # noqa: E402

DATE = "2026-08-31"
RUNS_DIR = ROOT / "harness" / "battleplan" / "runs"
LEGS = json.loads((HERE / "control_manifest.json").read_text(encoding="utf-8"))["legs"]


def prepare(leg):
    """The trivial 'dispatch' work whose wall we measure: resolve the leg's tier
    to a model string through the execution seam. Real work, small, measured.
    perf_counter_ns gives true sub-millisecond resolution, so wall_ms is a real
    measured number (e.g. 0.03), never a floored-to-zero placeholder."""
    t0 = time.perf_counter_ns()
    model = resolve_model(leg["tier"])          # a real rails_exec.json lookup
    wall_ms = round((time.perf_counter_ns() - t0) / 1e6, 3)
    return model, wall_ms


def proof_a():
    # cap one turn ABOVE the leg count -> completes under cap
    r = Rails(run="bp1-rails-proofA", cap=f"{len(LEGS) + 1}turns",
              date=DATE, runs_dir=RUNS_DIR)
    for leg in LEGS:
        model, wall_ms = prepare(leg)
        # tokens are UNKNOWN by omission: nothing launched, nothing measured
        r.charge(leg["id"], model, wall_ms=wall_ms)
    ledger = r.close()
    print(f"PROOF A  status={ledger['status']}  turns={ledger['totals']['turns']}/"
          f"{ledger['cap']['turns']}  enforced={ledger['enforced_unit']}  "
          f"-> {r.ledger_path().relative_to(ROOT)}")
    assert ledger["status"] == "complete", ledger
    assert r.ledger_path().exists()
    return ledger


def proof_b():
    # cap BELOW the spend (1 turn, 3 legs) -> halts on the 2nd charge
    r = Rails(run="bp1-rails-proofB", cap="1turns", date=DATE, runs_dir=RUNS_DIR)
    halted = False
    for leg in LEGS:
        model, wall_ms = prepare(leg)
        try:
            r.charge(leg["id"], model, wall_ms=wall_ms)
        except BudgetExceeded as e:
            halted = True
            ledger = e.ledger
            print(f"PROOF B  status={ledger['status']}  reason={ledger['reason']}  "
                  f"refused={leg['id']}  -> {r.ledger_path().relative_to(ROOT)}")
            break
    assert halted, "tiny-cap run did NOT halt - hard stop failed"
    assert ledger["status"] == "blocked" and ledger["reason"] == "budget", ledger
    assert r.ledger_path().exists()
    return ledger


if __name__ == "__main__":
    a = proof_a()
    b = proof_b()
    print("\nBOTH ARTIFACTS WRITTEN under harness/battleplan/runs/%s/:" % DATE)
    print("  ledger_bp1-rails-proofA.json  status=%s" % a["status"])
    print("  ledger_bp1-rails-proofB.json  status=%s reason=%s" % (b["status"], b["reason"]))
