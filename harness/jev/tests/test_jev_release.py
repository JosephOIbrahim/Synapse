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
    # notes() must reach the shared verdict, directly or through final_verdict
    # (which adds the existence gate and delegates the judgement to classify_claim).
    assert ("final_verdict(" in body) or ("classify_claim(" in body), (
        "notes() does not call the shared verdict")
    assert "unsupported_min" not in body, "notes() still carries its own threshold logic"


# ---- H-CLAIM-PATH: existence outranks the model -------------------------
# The guard judged a claim against a diff stat and commit subjects, neither of which
# can see whether a named path is in the tree. A note claiming a module shipped
# scored 0.84 supported while the module was absent from master.

_MISSING = "python/synapse/host/retina_receipts.py"
_PRESENT = "harness/jev/jev_release.py"


def test_a_claim_naming_an_absent_path_is_unsupported_even_when_the_model_says_supported():
    claim = f"One new product module ships, dormant, at {_MISSING}."
    verdict, missing = jr.final_verdict(claim, "supported", 0.85,
                                        {"supported": 0.85}, POL,
                                        root=Path(__file__).resolve().parents[3])
    assert verdict == "UNSUPPORTED", verdict
    assert missing == [_MISSING], missing


def test_a_claim_naming_a_present_path_keeps_the_model_verdict():
    claim = f"The guard lives at {_PRESENT}."
    verdict, missing = jr.final_verdict(claim, "supported", 0.85,
                                        {"supported": 0.85}, POL,
                                        root=Path(__file__).resolve().parents[3])
    assert verdict == "SUPPORTED", verdict
    assert missing == []


def test_a_claim_naming_no_path_is_left_to_the_model():
    verdict, missing = jr.final_verdict("The scan is 12% of the work.", "supported", 0.80,
                                        {"supported": 0.80}, POL,
                                        root=Path(__file__).resolve().parents[3])
    assert verdict == "SUPPORTED"
    assert missing == []


def test_bare_filenames_are_not_treated_as_asserted_locations():
    """Naming `decide.py` asserts a thing, not a location; demanding it exist at the
    repo root would manufacture false defects in the opposite direction."""
    assert jr.claim_paths("see decide.py for the rule") == []
    assert jr.claim_paths("see harness/vision/qc_timing/decide.py") == ["harness/vision/qc_timing/decide.py"]
