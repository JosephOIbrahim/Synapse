"""The release verdict has exactly one implementation, and four outcomes.

A scratch runner once re-implemented this rule and applied the model's argmax
instead of the shipped policy. Four claims at 0.33-0.56 "unsupported" probability
were reported as defects: the model had said `unsupported`, and the runner treated
that label as the verdict. The policy says otherwise, and these pin it.
"""
import importlib.util
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
GUARD = HERE.parent / "jev_release.py"

pytest.importorskip("jev_client", reason="the release guard needs the Jev client on the path")
_spec = importlib.util.spec_from_file_location("jev_release_under_test", GUARD)
jr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(jr)

POL = {"supported_min": 0.75, "unsupported_min": 0.6}


def test_a_low_probability_unsupported_label_is_a_partial():
    """The exact defect: the argmax said unsupported, the probability did not."""
    assert jr.classify_claim("unsupported", 0.35,
                             {"unsupported": 0.35, "partial": 0.4, "supported": 0.25}, POL) == "PARTIAL"


def test_a_supported_label_below_the_confidence_gate_is_a_partial():
    assert jr.classify_claim("supported", 0.51,
                             {"supported": 0.51, "partial": 0.4}, POL) == "PARTIAL"


def test_a_high_unsupported_probability_is_unsupported_whatever_the_label():
    for label in ("unsupported", "partial", "supported"):
        assert jr.classify_claim(label, 0.9, {"unsupported": 0.65}, POL) == "UNSUPPORTED"


def test_a_supported_label_above_the_gate_is_supported():
    assert jr.classify_claim("supported", 0.80, {"supported": 0.80}, POL) == "SUPPORTED"


def test_the_thresholds_come_from_the_policy_not_from_constants():
    """A tightened gate must change the verdict, or code is not reading the policy."""
    strict = {"supported_min": 0.95, "unsupported_min": 0.6}
    assert jr.classify_claim("supported", 0.80, {"supported": 0.80}, strict) == "PARTIAL"
    loose = {"supported_min": 0.10, "unsupported_min": 0.6}
    assert jr.classify_claim("supported", 0.20, {"supported": 0.20}, loose) == "SUPPORTED"


def test_notes_has_no_second_copy_of_the_rule():
    """The point of the extraction: one implementation, reached by the caller."""
    import inspect
    body = inspect.getsource(jr.notes)
    assert "classify_claim(" in body, "notes() does not call the shared verdict"
    assert "unsupported_min" not in body, "notes() still carries its own threshold logic"
