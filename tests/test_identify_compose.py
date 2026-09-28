"""compose(): pure facts -> bubble lines. Runs on system Python, no hou."""
from __future__ import annotations

from synapse.identify import compose as C


def _facts(**over):
    base = {
        "type_label": "PolyBevel", "type_name": "polybevel::3.0", "category": "Sop",
        "summary": "Bevels or chamfers the edges and corners of polygons.",
        "summary_source": "library", "params": [], "lop_writes": None,
        "errors": [], "warnings": [], "bypassed": False, "beta": False,
    }
    base.update(over)
    return base


def _param(name, label, value, kind="float", **over):
    p = {"name": name, "label": label, "kind": kind, "value": value,
         "multi": False, "is_expression": False, "hidden": False}
    p.update(over)
    return p


# ── What line ──────────────────────────────────────────────────────────────

def test_what_line_uses_library_summary():
    lines = C.compose(_facts())
    assert lines[0] == "Bevels or chamfers the edges and corners of polygons."


def test_unknown_type_says_not_in_library():
    lines = C.compose(_facts(summary=None, summary_source="unknown"))
    assert lines[0] == "PolyBevel - not in library"


def test_unknown_falls_back_to_type_name_when_no_label():
    lines = C.compose(_facts(summary=None, summary_source="unknown",
                             type_label=None))
    assert lines[0] == "polybevel::3.0 - not in library"


# ── Here line: the M0 PolyBevel acceptance ───────────────────────────────────

def test_m0_polybevel_one_here_entry_no_ramp_internal():
    """offset 0.07 plus five changed ramp internals -> one Here entry, by label."""
    params = [
        _param("offset", "Offset", 0.07),
        _param("profileramp1value", "Profile Ramp 1 Value", 0.5),
        _param("profileramp1interp", "Profile Ramp 1 Interp", 2),
        _param("profileramp2pos", "Profile Ramp 2 Pos", 0.3),
        _param("profileramp2value", "Profile Ramp 2 Value", 0.9),
        _param("profileramp2interp", "Profile Ramp 2 Interp", 1),
    ]
    lines = C.compose(_facts(params=params))
    here = lines[1]
    # exactly one entry (no comma joining a second), shown by its label
    assert "," not in here
    assert here == "Offset 0.07"
    # no ramp internal name or label leaked through
    assert "ramp" not in here.lower()
    assert "Profile" not in here


def test_here_drops_structural_and_hidden_parms():
    params = [
        _param("folder1", "Folder", 0, kind="folder"),
        _param("sepparm", "Sep", 0, kind="separator"),
        _param("labelparm", "Label", 0, kind="label"),
        _param("hiddenone", "Hidden", 5, hidden=True),
        _param("radius", "Radius", 1.5),
    ]
    lines = C.compose(_facts(params=params))
    assert lines[1] == "Radius 1.5"


def test_here_shows_at_most_two_params():
    params = [_param("a", "Alpha", 1.0), _param("b", "Beta", 2.0),
              _param("c", "Gamma", 3.0)]
    here = C.compose(_facts(params=params))[1]
    assert here == "Alpha 1, Beta 2"
    assert "Gamma" not in here


# ── Value formatting ─────────────────────────────────────────────────────────

def test_three_significant_digits():
    here = C.compose(_facts(params=[_param("x", "X", 1234.5678)]))[1]
    assert here == "X 1.23e+03"


def test_expression_marker():
    here = C.compose(_facts(params=[_param("x", "X", 0.0, is_expression=True)]))[1]
    assert here == "X (expr)"


def test_multi_component_is_ellipsis():
    here = C.compose(_facts(params=[_param("t", "Translate", None, multi=True)]))[1]
    assert here == "Translate ..."


def test_toggle_on_off():
    here = C.compose(_facts(params=[_param("en", "Enable", 1, kind="toggle")]))[1]
    assert here == "Enable on"


def test_long_string_value_truncated():
    here = C.compose(_facts(params=[_param("s", "Str", "x" * 60, kind="string")]))[1]
    assert here.endswith("...")
    assert len(here) <= C.WIDTH


# ── State line ────────────────────────────────────────────────────────────────

def test_state_absent_when_clean():
    lines = C.compose(_facts())
    # What + Here only (has a summary + no state); no third line
    assert all(not l.startswith("error") and not l.startswith("warning")
               for l in lines)


def test_state_error_takes_priority_over_warning():
    lines = C.compose(_facts(errors=["cannot cook input"], warnings=["slow"]))
    assert lines[-1].startswith("error: cannot cook input")


def test_state_bypassed_and_beta():
    lines = C.compose(_facts(bypassed=True, beta=True))
    assert lines[-1] == "bypassed, beta"


# ── LOP writes ────────────────────────────────────────────────────────────────

def test_lop_writes_line():
    facts = _facts(lop_writes={"first": "/stage/geo", "count": 3})
    here = C.compose(facts)[1]
    assert here == "writes /stage/geo (+2)"


def test_lop_writes_single_prim_no_suffix():
    facts = _facts(lop_writes={"first": "/stage/geo", "count": 1})
    assert C.compose(facts)[1] == "writes /stage/geo"


# ── Shape guarantees ──────────────────────────────────────────────────────────

def test_at_most_three_lines_and_width():
    params = [_param("offset", "Offset", 0.07)]
    lines = C.compose(_facts(params=params, errors=["boom"]))
    assert len(lines) <= 3
    assert all(len(l) <= C.WIDTH for l in lines)


def test_long_what_line_truncated_with_ellipsis():
    lines = C.compose(_facts(summary="x" * 100))
    assert lines[0].endswith("...")
    assert len(lines[0]) == C.WIDTH
