"""bubble: the overlay's fields for one node, pure and on system Python."""
from __future__ import annotations

import pytest

from synapse.identify import bubble as B
from synapse.identify import compose as C


def _facts(**over):
    base = {
        "path": "/obj/geo1/polybevel1", "type_label": "PolyBevel",
        "type_name": "polybevel::3.0", "category": "Sop",
        "summary": "Bevels points and edges.", "summary_source": "library",
        "params": [], "lop_writes": None, "errors": [], "warnings": [],
        "bypassed": False, "beta": False,
    }
    base.update(over)
    return base


def test_title_tag_and_summary_come_from_the_facts():
    model = B.bubble_model(_facts())
    assert model["title"] == "PolyBevel"
    assert model["tag"] == "SOP"
    assert model["summary"] == "Bevels points and edges."
    assert model["writes"] is None and model["changes"] is None and model["state"] is None


def test_unknown_type_has_no_summary_instead_of_a_guess():
    model = B.bubble_model(_facts(summary=None, summary_source="unknown"))
    assert model["summary"] is None


def test_a_summary_with_an_unknown_source_is_not_shown():
    model = B.bubble_model(_facts(summary_source="unknown"))
    assert model["summary"] is None


def test_long_summary_is_kept_whole_for_wrapping_not_cut_at_the_comment_width():
    long = "Word " * 30 + "end."
    model = B.bubble_model(_facts(summary=long.strip()))
    assert len(model["summary"]) > C.WIDTH
    assert not model["summary"].endswith("...")


def test_pathological_summary_is_bounded():
    model = B.bubble_model(_facts(summary="x" * 5000))
    assert len(model["summary"]) == B.TEXT_MAX
    assert model["summary"].endswith("...")


def test_lop_writes_names_the_first_prim_and_the_rest_as_a_count():
    model = B.bubble_model(_facts(category="Lop", lop_writes={"first": "/ball", "count": 3}))
    assert model["tag"] == "LOP"
    assert model["writes"] == {"path": "/ball", "more": 2}
    assert model["changes"] is None


def test_changes_use_compose_formatting():
    params = [{"name": "offset", "label": "Offset", "kind": "float", "value": 0.0714,
               "multi": False, "is_expression": False, "hidden": False}]
    facts = _facts(params=params)
    assert B.bubble_model(facts)["changes"] == C.here_line(facts, B.TEXT_MAX) == "Offset 0.0714"


def test_state_line_reports_trouble():
    model = B.bubble_model(_facts(errors=["Invalid source"], bypassed=True))
    assert model["state"] == "error: Invalid source, bypassed"


@pytest.mark.parametrize("category, tag", [
    ("Sop", "SOP"), ("Lop", "LOP"), ("Object", "OBJ"), ("Driver", "ROP"),
    ("Cop", "COP"), ("Vop", "VOP"), ("Sometype", "SOME"), ("", ""), (None, ""),
])
def test_category_tag(category, tag):
    assert B.category_tag(category) == tag


def test_bubble_model_rejects_a_non_dict():
    with pytest.raises(TypeError):
        B.bubble_model(["not", "facts"])


def test_legacy_what_lines_cover_both_forms_an_older_identify_wrote():
    facts = _facts()
    lines = B.legacy_what_lines(facts)
    assert C.what_line(facts) in lines
    assert "PolyBevel - not in library" in lines
    assert len(lines) == 2


def test_legacy_what_lines_for_an_unknown_type_is_the_not_in_library_form_only():
    lines = B.legacy_what_lines(_facts(summary=None, summary_source="unknown"))
    assert lines == frozenset({"PolyBevel - not in library"})
