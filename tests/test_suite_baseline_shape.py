"""Pins the R31 two-leg tuple target for harness/verify/suite_baseline.json.

W5-BASE prepared the promotion (remove the top-level passed/failed/skipped
scalars that trip parse_tuple_baseline's FLAT rejection, checks.py:2283), but
harness/verify/suite_baseline.json is DENY-LISTED from agent edit in every
launch profile (agent-settings.json / relay-settings.json; promotion is a human
act by design -- see parse_tuple_baseline's own error message and checks.py:2248).

So this test does two things, both landing-safe:
  1. validates the BANKED PROPOSAL is a well-formed R31 tuple (green NOW), so the
     ready-to-apply content is proven before a human touches the live file;
  2. asserts the LIVE baseline once a human applies it -- and SKIPS (never reddens)
     while the live file is still the pre-existing FLAT shape.

Loaded by path like test_r_track.py / test_s_track.py -- harness/verify is not a
package, so checks.py is exec'd under its own alias to reuse the REAL
parse_tuple_baseline (the same gate check_suite_baseline runs), never a copy.
"""
import importlib.util
import json
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parents[1]
_CHECKS = _REPO / "harness" / "verify" / "checks.py"
_LIVE = _REPO / "harness" / "verify" / "suite_baseline.json"
_PROPOSAL = _REPO / "harness" / "notes" / "receipts" / "W5-BASE_PROPOSED_suite_baseline.json"

_spec = importlib.util.spec_from_file_location("harness_checks_suite_baseline", _CHECKS)
checks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(checks)

_LEGS = ("gate", "shipping")


def _assert_valid_r31_tuple(raw, src):
    legs = checks.parse_tuple_baseline(raw)  # REAL parser; raises on FLAT / missing leg / bad field
    assert set(legs) == set(_LEGS), f"{src}: legs {set(legs)} != {set(_LEGS)}"
    for name in _LEGS:
        entry = legs[name]
        assert entry["interpreter"].strip(), f"{src}: {name} leg does not name its interpreter"
        assert entry["producer"].strip(), f"{src}: {name} leg does not name its producer (Law 2)"
        for field in ("passed", "failed", "skipped"):
            assert isinstance(entry[field], int), f"{src}: {name}.{field} is not an int"
    gate = legs["gate"]
    assert gate["failed"] == 0, f"{src}: gate leg is not green (failed != 0)"
    assert gate["passed"] > 0, f"{src}: gate leg has no passing tests -- not a real green run"
    return legs


def test_banked_proposal_is_valid_r31_tuple():
    """The prepared content W5-BASE hands to the human must already be a valid tuple."""
    if not _PROPOSAL.is_file():
        pytest.skip("proposal consumed -- promotion has been applied to the live baseline")
    _assert_valid_r31_tuple(_PROPOSAL.read_text(encoding="utf-8"), "PROPOSAL")


def test_live_baseline_is_tuple_or_pending_human_promotion():
    """Once a human applies the promotion, the live baseline must parse as an R31 tuple.
    Skips (never reddens) while it is still the pre-existing FLAT shape."""
    d = json.loads(_LIVE.read_text(encoding="utf-8"))
    if "passed" in d or "failed" in d:
        pytest.skip("live harness/verify/suite_baseline.json still carries top-level scalars "
                    "(FLAT) -- awaiting human promotion; it is deny-listed from agent edit and "
                    "W5-BASE banked the ready content at "
                    "harness/notes/receipts/W5-BASE_PROPOSED_suite_baseline.json")
    _assert_valid_r31_tuple(_LIVE.read_text(encoding="utf-8"), "LIVE")


def test_flat_shape_still_rejected_by_parser():
    """Guard the guard: a flat scalar baseline must still raise, so a regression to the
    flat form cannot silently pass parse_tuple_baseline."""
    with pytest.raises(checks.BaselineShapeError):
        checks.parse_tuple_baseline(json.dumps({"passed": 1, "failed": 0, "skipped": 0}))


def test_missing_leg_rejected_by_parser():
    """A tuple missing the shipping leg must raise -- both legs are mandatory."""
    with pytest.raises(checks.BaselineShapeError):
        checks.parse_tuple_baseline(json.dumps({
            "gate": {"passed": 1, "failed": 0, "skipped": 0,
                     "interpreter": "x", "producer": "y"}}))
