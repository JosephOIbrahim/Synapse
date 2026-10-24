"""Tests for the catalogue-types probe.

`harness/probes/catalog_types_check.py` is the standing evidence behind the
World Labs audit's central claim: that the node-type catalogue in
rag/catalog/h22.0.400/ matches the live build, and that the "three mis-
described types" claim was wrong. The audit cites the probe and its receipt,
so the probe has to fail when it cannot answer - and it has to answer the
question it was asked.

Every test below names the condition under which the probe changes its
answer, and a test that cannot fail is deleted rather than kept green.

Run:  python -m pytest harness/probes/tests -q
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0]))

import catalog_types_check as P  # noqa: E402


# --------------------------------------------------------------- the target list

def _loader(catalogue):
    """A loader that answers from a plain dict, so the test needs no catalogue
    on disk and no Houdini seat."""
    def load(category, key):
        return catalogue.get((category, key))
    return load


def test_a_target_the_catalogue_does_not_name_is_a_finding():
    """The hole this probe had.

    A target that is not in the catalogue at all was SKIPPED: the probe
    printed "not in the catalogue at all", wrote a row saying
    `in_catalogue: False`, and moved on with no finding and no count. The
    run then printed "AGREEMENT ... The catalogue is FAITHFUL to the live
    build." The subject of the probe was absent, so nothing had established
    anything about it - and the probe reported success.

    An abstention printed as a pass is the worst kind of green: it means
    nothing, and it means it while looking like evidence.
    """
    out = P.resolution_pass([("Sop", "gltf")], _loader({}), {"Sop": {"gltf": {}}})
    assert out["problems"], "a target the catalogue does not name must be a finding"
    assert "does not name this type" in out["problems"][0]
    assert out["rows"][0]["in_catalogue"] is False
    # and it is still counted: a target that was not compared has not been cleared
    assert out["checked"] == 1


def test_a_target_the_catalogue_names_produces_no_finding():
    """The control. The fix must not make every target a finding."""
    out = P.resolution_pass([("Sop", "gltf")],
                            _loader({("Sop", "gltf"): {"parms": []}}),
                            {"Sop": {"gltf": {}}})
    assert out["problems"] == []
    assert out["rows"][0]["in_catalogue"] is True
    assert out["rows"][0]["live_type_exists"] is True
    assert out["checked"] == 1


def test_one_absent_target_does_not_clear_the_others():
    """A run with five good targets and one missing is not a clean run."""
    catalogue = {("Sop", "gltf"): {"parms": []}, ("Lop", "distantlight"): {"parms": []}}
    out = P.resolution_pass([("Sop", "gltf"), ("Sop", "gltf::2.0"),
                              ("Lop", "distantlight")],
                             _loader(catalogue),
                             {"Sop": {"gltf": {}, "gltf::2.0": {}},
                              "Lop": {"distantlight": {}}})
    assert len(out["problems"]) == 1
    assert "gltf::2.0" in out["problems"][0]
    assert out["checked"] == 3


def test_a_catalogue_entry_with_no_live_type_is_not_called_a_catalogue_defect():
    """The other half of the question, left alone on purpose.

    An unversioned catalogue key often resolves to a versioned live type -
    createNode("gltf") hands back a gltf::2.0 node. The probe answers that
    downstream (Q3 records what createNode() actually returned, Q4 shows
    which parm names are absent on the node you get) and reports it as a
    CONSUMER TRAP. Calling it a catalogue defect here would mislabel it, and
    the shipped receipt would flip to DISAGREEMENT on a correct catalogue.
    """
    out = P.resolution_pass([("Sop", "gltf")],
                             _loader({("Sop", "gltf"): {"parms": []}}),
                             {"Sop": {"gltf::2.0": {}}})
    assert out["problems"] == []
    assert out["rows"][0]["in_catalogue"] is True
    assert out["rows"][0]["live_type_exists"] is False


def test_the_checked_count_is_compared_questions_not_catalogue_entries():
    """The receipt's `checked` is a count of ANSWERED COMPARISONS.

    The old summary printed it as "checked 18 catalogue entries" when there
    are six targets and three comparable questions. A number labelled with
    the wrong unit is a number nobody can check.
    """
    targets = [("Sop", "gltf"), ("Sop", "gltf::2.0"), ("Lop", "distantlight"),
               ("Lop", "distantlight::2.0"), ("Driver", "usdrender"), ("Top", "usdrender")]
    catalogue = {(c, k): {"parms": []} for c, k in targets}
    live = {}
    for c, k in targets:
        live.setdefault(c, {})[k] = {}
    out = P.resolution_pass(targets, _loader(catalogue), live)
    assert out["checked"] == len(targets)
    assert out["problems"] == []
