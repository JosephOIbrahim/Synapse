"""The Scatter Instances recipe keeps its direction mask (measured in hython 2026-10-03)."""
from synapse.routing.solaris_recipes import RECIPES


def _scatter_parms():
    nodes = RECIPES["scatter_instances"]["payload"]["nodes"]
    return next(n["parms"] for n in nodes if n.get("type") == "scatterinstances")


def test_direction_mask_is_on_and_tight():
    parms = _scatter_parms()
    assert parms["enabledirection"] == 1
    # 45 left 73 of 763 instances off the lane; 20 left 12 of 758.
    assert 0 < parms["maxangle"] <= 20


def test_camera_mask_stays_on():
    parms = _scatter_parms()
    assert parms["enablecameramask"] == 1 and parms["enablecamera"] == 1


def test_notes_name_the_far_plane_parms():
    notes = " ".join(RECIPES["scatter_instances"]["notes"])
    assert "enablecameramaskfar" in notes and "cameramaskfar" in notes
