"""Q2 mutation test for checks.py::parse_tuple_baseline.

Law 1: a check that cannot fail is a decoration. This proves the reader FAILS on
the old flat shape and PASSES on the R31 tuple. Exit 0 = both behaved correctly;
exit 1 = the reader silently accepted something it must reject.

    python harness/notes/receipts/q2_mutation_test_baseline_reader.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness" / "verify"))

from checks import BaselineShapeError, parse_tuple_baseline  # noqa: E402

OLD_FLAT = json.dumps({"_comment": "legacy", "passed": 4275, "failed": 0, "skipped": 87})
NEW_TUPLE = json.dumps({
    "gate": {"interpreter": "python 3.14.2", "passed": 4874, "failed": 0, "skipped": 128,
             "commit": "671079f", "producer": "python -m pytest tests/ -q"},
    "shipping": {"interpreter": "hython 3.13.10", "passed": 0, "failed": 0, "skipped": 1,
                 "commit": "671079f", "producer": "hython -m pytest tests/ -q"},
})
MUTANTS = {
    "flat_shape": OLD_FLAT,
    "bare_integer": "4275",
    "missing_shipping_leg": json.dumps({"gate": json.loads(NEW_TUPLE)["gate"]}),
    "leg_missing_producer": json.dumps({
        "gate": {"interpreter": "x", "passed": 1, "failed": 0, "skipped": 0},
        "shipping": json.loads(NEW_TUPLE)["shipping"]}),
    "non_integer_count": json.dumps({
        "gate": {"interpreter": "x", "producer": "p", "passed": "many", "failed": 0, "skipped": 0},
        "shipping": json.loads(NEW_TUPLE)["shipping"]}),
}


def main():
    bad = []
    for name, raw in MUTANTS.items():
        try:
            parse_tuple_baseline(raw)
        except BaselineShapeError as e:
            print(f"REJECTED {name}: {e}")
        else:
            bad.append(name)
            print(f"ACCEPTED-BUT-SHOULD-NOT {name}")
    try:
        legs = parse_tuple_baseline(NEW_TUPLE)
        print(f"ACCEPTED tuple: gate={legs['gate']['passed']}p "
              f"shipping={legs['shipping']['passed']}p")
    except BaselineShapeError as e:
        bad.append("valid_tuple_rejected")
        print(f"REJECTED-BUT-SHOULD-NOT valid tuple: {e}")
    if bad:
        print(f"MUTATION TEST FAILED: {bad}")
        return 1
    print("MUTATION TEST PASSED: all mutants rejected, valid tuple accepted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
