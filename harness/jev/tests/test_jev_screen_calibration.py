# test_jev_screen_calibration.py - JEV-SCREEN's policy, calibrated on CRUX's verdicts (BP12 item 8).
# The first policy cleared no leg in four waves, so the screen never saved a CRUX read. The cases
# are the recorded Jev answers for 20 CRUX-judged legs (calibrate_screen.py --write); replaying
# them pins the calibration: no BROKEN leg clears, and the sound legs that clear stay cleared.
from __future__ import annotations

import json
import sys
from pathlib import Path

JEV_DIR = Path(__file__).resolve().parents[1]
if str(JEV_DIR) not in sys.path:
    sys.path.insert(0, str(JEV_DIR))

import jev_client as jc  # noqa: E402
import jev_screen as js  # noqa: E402

CASES = json.loads((JEV_DIR / "tests" / "fixtures" / "screen_calibration_cases.json")
                   .read_text(encoding="utf-8"))["cases"]
POLICY = jc.load_questions()["guards"]["screen"]["policy"]


def _replay(case):
    if case["code_flags"]:
        return "FLAG"
    return js.decide(case["n_rows"], case["answers"], POLICY)["verdict"]


def test_the_answer_key_holds_both_kinds_of_leg():
    kinds = {c["crux"] for c in CASES}
    assert len(CASES) >= 20 and "BROKEN" in kinds and kinds - {"BROKEN"}


def test_no_broken_leg_is_cleared():
    assert [c["leg"] for c in CASES if c["crux"] == "BROKEN" and _replay(c) == "CLEAR"] == []


def test_the_calibrated_screen_saves_reads_the_first_policy_never_did():
    sound = [c for c in CASES if c["crux"] != "BROKEN"]
    cleared = [c["leg"] for c in sound if _replay(c) == "CLEAR"]
    assert len(cleared) >= 6, cleared
    assert all(c["recorded_verdict"] != "CLEAR" for c in CASES)


def _answers(rows, sc=0.1, cn=0.4):
    return {"choices": {f"acc_{i}": {"choice": choice, "confidence": 0.9, "probabilities": p}
                        for i, (choice, p) in enumerate(rows)},
            "nouls": {"self_contradiction": {"noul": sc}}, "scores": {"crux_need": {"score": cn}}}


SUP = ("supports", {"supports": 0.9, "partial": 0.1, "does_not_support": 0.0, "claims_unknown": 0.0})
UNK = ("claims_unknown", {"supports": 0.0, "partial": 0.0, "does_not_support": 0.0, "claims_unknown": 1.0})
PART = ("partial", {"supports": 0.3, "partial": 0.7, "does_not_support": 0.0, "claims_unknown": 0.0})
THIN = ("supports", {"supports": 0.45, "partial": 0.4, "does_not_support": 0.15, "claims_unknown": 0.0})
DNS = ("does_not_support", {"supports": 0.1, "partial": 0.2, "does_not_support": 0.7, "claims_unknown": 0.0})


def test_a_row_the_receipt_marks_unknown_does_not_block_clear():
    d = js.decide(3, _answers([SUP, UNK, SUP]), POLICY)
    assert d["verdict"] == "CLEAR" and d["unknown"] == [1]
    assert "rows [1] claim UNKNOWN" in js.brief_line("BP99-LEG", d, 3)


def test_partial_and_thinly_supported_rows_are_the_weak_rows():
    d = js.decide(4, _answers([SUP, PART, THIN, UNK]), POLICY)
    assert d["verdict"] == "REFEREE" and d["rows"] == [1, 2] and d["unknown"] == [3]


def test_does_not_support_still_flags_first():
    d = js.decide(2, _answers([DNS, UNK]), POLICY)
    assert d["verdict"] == "FLAG" and d["rows"] == [0]


def test_self_contradiction_or_crux_need_over_the_line_blocks_clear():
    over_sc = POLICY["clear_max_self_contradiction"] + 0.01
    over_cn = POLICY["clear_max_crux_need"] + 0.01
    assert js.decide(1, _answers([SUP], sc=over_sc), POLICY)["verdict"] == "REFEREE"
    assert js.decide(1, _answers([SUP], cn=over_cn), POLICY)["verdict"] == "REFEREE"


def test_record_crux_adds_each_screened_legs_reading(tmp_path, monkeypatch):
    notes, ledger_dir = tmp_path / "notes", tmp_path / "ledger"
    notes.mkdir()
    ledger_dir.mkdir()
    (notes / "BP99-CRUX_verdicts.md").write_text(
        "## BP99-ONE - **SOUND-WITH-NITS**\n## BP99-TWO - **BROKEN**\n", encoding="utf-8")
    (ledger_dir / "bp99.screen.jsonl").write_text(
        "".join(json.dumps({"leg": leg, "result": "decision"}) + "\n"
                for leg in ("BP99-ONE", "BP99-TWO", "BP99-ONE", "BP99-THREE")), encoding="utf-8")
    monkeypatch.setattr(js, "NOTES", notes)
    monkeypatch.setattr(jc, "LEDGER_DIR", ledger_dir)
    assert js.record_crux("bp99") == 2
    rows = [json.loads(line) for line in
            (ledger_dir / "bp99.screen.jsonl").read_text(encoding="utf-8").splitlines()]
    readings = {r["leg"]: r["crux"] for r in rows if r.get("result") == "crux_reading"}
    assert readings == {"BP99-ONE": "SOUND-WITH-NITS", "BP99-TWO": "BROKEN"}


def test_a_receipt_that_contradicts_itself_like_bp4_rulings_never_clears():
    """BP4-RULINGS (CRUX: BROKEN) contradicted itself at 0.69. Its crux need also blocks CLEAR,
    so take that out: self-contradiction alone must still keep it from clearing."""
    rulings = next(c for c in CASES if c["leg"] == "BP4-RULINGS")
    answers = json.loads(json.dumps(rulings["answers"]))
    answers["scores"]["crux_need"]["score"] = 0.0
    assert js.decide(rulings["n_rows"], answers, POLICY)["verdict"] == "REFEREE"
