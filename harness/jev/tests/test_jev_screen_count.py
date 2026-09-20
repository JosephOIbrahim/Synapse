# test_jev_screen_count.py - the code-side count check in JEV-SCREEN (docs-driven, 2026-09-20).
# Jev 1.13 "does not count reliably" (docs.typesafe.ai/model-jaggedness/jev-1.13), so the count
# comparison that screen rule 2 used to delegate to Jev is now plain code. Every test bites.
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_screen as js  # noqa: E402

REPO = JEV_DIR.parents[1]


def _m(note, preds=("table row count equals the total",)):
    return {"id": "BP9-X", "note": note, "acceptance": [{"predicate": p, "evidence": "check"} for p in preds]}


def _r(*evidence):
    return {"acceptance": [{"verdict": "pass", "evidence": e} for e in evidence]}


def test_rulings_shape_is_caught_by_code():
    """Regression for BP4-RULINGS (CRUX: BROKEN). Mutation: drop the disjoint check -> the 21-vs-22
    miss that Jev scored 0.25 goes back to being invisible."""
    m = _m("Self-cap: 12 turns. Compile the 22 items from seven receipts; read 40-line windows.")
    cm = js.count_mismatch_rows(m, _r("CTO_RULINGS.md: 21 rows extracted", "bus claim 'table compiled: 21 rows'"))
    assert [c["i"] for c in cm] == [0, 1] and cm[0]["expected"] == ["22"] and cm[0]["reported"] == ["21"]


def test_turn_caps_and_line_windows_are_not_counts():
    """Mutation: widen the noun list to any word -> '12 turns' becomes an expected count and every
    receipt reporting '5 tests' is flagged against it."""
    m = _m("Self-cap: 12 turns (progress every 3). Read 40-line windows.")
    assert js.count_mismatch_rows(m, _r("6 tests pass")) == []          # no expected count at all
    m = _m("Compile the 22 items.")
    assert js.count_mismatch_rows(m, _r("done in 9 turns, 22 rows")) == []  # matching count present


def test_matching_or_absent_numbers_never_flag():
    """Mutation: flag whenever expected != reported as sets -> a receipt naming 22 rows AND 7 files
    would be flagged for the 7."""
    m = _m("Compile the 22 items from 7 receipts.")
    assert js.count_mismatch_rows(m, _r("22 rows from 7 receipts", "no numbers here")) == []


def test_real_bp8_green_receipts_do_not_trip_it():
    """The two BP8 receipts CRUX is reading now: both green. Mutation: a false positive here would
    have inserted a repair leg on a sound build."""
    for leg in ("BP8-WATCHDOG", "BP8-TIMEOUTS"):
        m = json.loads((REPO / "harness" / "battleplan" / "missions" / f"{leg}.json").read_text(encoding="utf-8"))
        wt = REPO / ".claude" / "worktrees" / leg.lower()
        rp = wt / "harness" / "notes" / "receipts" / f"{leg}.json"
        if not rp.exists():
            continue
        assert js.count_mismatch_rows(m, json.loads(rp.read_text(encoding="utf-8-sig"))) == [], leg


def test_real_bp4_rulings_receipt_is_flagged():
    """Same check against the actual BROKEN receipt at commit a62267f9 (never merged). Skipped if git
    cannot show it. Mutation: any weakening of the noun/number regex that loses '21 rows'."""
    m = json.loads((REPO / "harness" / "battleplan" / "missions" / "BP4-RULINGS.json").read_text(encoding="utf-8"))
    p = subprocess.run(["git", "-C", str(REPO), "show", "a62267f9:harness/notes/receipts/BP4-RULINGS.json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        import pytest
        pytest.skip("a62267f9 not reachable")
    cm = js.count_mismatch_rows(m, json.loads(p.stdout))
    assert cm and all(c["reported"] == ["21"] for c in cm) and "22" in cm[0]["expected"]
