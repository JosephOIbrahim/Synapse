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


# ------------------------------------------- the ratchet's interpreter identity
#
# check_suite_baseline ran the suite under whatever sys.executable launched it and
# compared the counts against a gate leg recorded on a DIFFERENT interpreter, with
# no identity term anywhere: ok = failed_now <= failed_base and passed_now >= passed_base.
# On 2026-11-12 this machine's PATH resolved to 3.12.10 while the gate leg records
# "system python 3.14.2 (C:/Python314/python.exe)", so every sprint's ratchet verdict
# was a comparison across two interpreters wearing the baseline's label.
#
# These pin the refusal. They inject the RUNNING identity so the assertions do not
# depend on which interpreter happens to execute this file.

_GATE = "system python 3.14.2 (C:/Python314/python.exe) - vendor tree INACTIVE"


def test_ratchet_refuses_a_run_on_a_different_interpreter():
    """The synthetic pair: gate 3.14.2, run 3.12.10. Must refuse, naming both."""
    problems = checks._identity_mismatch(_GATE, running={
        "version": (3, 12, 10),
        "executable": r"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe",
        "implementation": "cpython",
    })
    assert problems, "a 3.14.2 baseline must not be ratcheted from a 3.12.10 run"
    joined = " ".join(problems)
    assert "3.14.2" in joined, joined
    assert "3.12.10" in joined, joined


def test_ratchet_proceeds_on_the_interpreted_it_was_measured_on():
    """Positive control: same version, same executable, same implementation."""
    problems = checks._identity_mismatch(_GATE, running={
        "version": (3, 14, 2),
        "executable": "C:/Python314/python.exe",
        "implementation": "cpython",
    })
    assert problems == [], f"a matching identity must not be refused: {problems}"


def test_same_version_different_executable_still_refuses():
    """Two builds of 3.14.2 are still two interpreters."""
    problems = checks._identity_mismatch(_GATE, running={
        "version": (3, 14, 2),
        "executable": r"C:\Python314-other\python.exe",
        "implementation": "cpython",
    })
    assert problems, "same version but a different executable must refuse"
    assert any("executable" in p for p in problems), problems


def test_unparseable_gate_identity_fails_closed():
    """No parseable version means the guard cannot tell which fruit it holds."""
    problems = checks._identity_mismatch("system python - unknown build", running={
        "version": (3, 14, 2),
        "executable": "C:/Python314/python.exe",
        "implementation": "cpython",
    })
    assert problems, "an unparseable gate identity must refuse rather than pass"
    assert any("no parseable version" in p for p in problems), problems


def test_the_live_baseline_gate_identity_parses_to_a_version_and_a_path():
    """The shipped baseline must stay parseable, or the guard refuses everything."""
    legs = checks.parse_tuple_baseline(_LIVE.read_text(encoding="utf-8"))
    ident = checks._gate_identity(legs["gate"]["interpreter"])
    assert ident["version"] is not None, legs["gate"]["interpreter"]
    assert ident["executable"] is not None, legs["gate"]["interpreter"]


def test_the_running_identity_is_read_from_this_process():
    ident = checks._running_identity()
    import sys as _sys
    assert ident["version"] == tuple(_sys.version_info[:3])
    assert ident["executable"] == _sys.executable
    assert ident["implementation"] == _sys.implementation.name
