"""H3b — pins for the panel's cook-cancel / emergency-halt controls.

The load-bearing piece here is ``extract_node_path``. The panel's cancel
control can only work if it knows WHICH node to cancel, and the only place the
panel ever sees one is the tool-status ``detail`` string — which
``claude_worker`` produces as ``json.dumps(tool_input)[:120]``, i.e. TRUNCATED.

A reader that only tried ``json.loads`` would return None on precisely the long
payloads a real cook produces. The control would look wired, the menu entry
would render, and it would silently never find a target. That is the R60 defect
exactly, so the reader is calibrated with truncated fixtures and paired
negative cases, and each pin has a mutant it must reject (R34).

``_on_stop`` is NOT tested here because it is NOT changed by this leg (brief:
"Do not replace it"). Its behaviour is pinned where it already was.
"""

import json
import os
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _root)
sys.path.insert(0, os.path.join(_root, "python"))

from synapse.panel.direct_tool import extract_node_path, is_cookish_tool


# ---------------------------------------------------------------------------
# Fixtures shaped exactly like claude_worker.py's producer:
#     detail = json.dumps(tool_input)[:120]
# ---------------------------------------------------------------------------

def _as_panel_detail(payload: dict) -> str:
    """Reproduce the panel's own truncation, so fixtures cannot drift from it."""
    return json.dumps(payload)[:120]


WHOLE = _as_panel_detail({"node": "/tasks/topnet1"})

# A realistic cook payload long enough that 120 chars CUTS IT OFF mid-object.
LONG_PAYLOAD = {
    "node": "/tasks/topnet1/wedge_shotA",
    "scheduler": "localscheduler",
    "block": False,
    "generate_only": False,
    "note": "cook every wedge for shot A at full resolution",
}
TRUNCATED = _as_panel_detail(LONG_PAYLOAD)


def test_fixture_really_is_truncated():
    """Guard the guard: if this fixture ever stops being truncated, the
    truncation pins below would pass for the wrong reason."""
    assert len(TRUNCATED) == 120
    try:
        json.loads(TRUNCATED)
        raise AssertionError("fixture parsed as JSON -- it is not truncated")
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# R60 — reader calibration.
# ---------------------------------------------------------------------------

def test_reader_recovers_node_from_whole_json():
    assert extract_node_path(WHOLE) == "/tasks/topnet1"


def test_reader_recovers_node_from_TRUNCATED_json():
    """The case the panel actually produces. This is the pin that matters."""
    assert extract_node_path(TRUNCATED) == "/tasks/topnet1/wedge_shotA"


def test_reader_returns_None_when_there_is_genuinely_no_node():
    """The negative control. Without it, a reader that returned a constant
    path would pass every positive pin above."""
    assert extract_node_path(_as_panel_detail({"intent": "render shot A"})) is None
    assert extract_node_path("") is None
    assert extract_node_path(None) is None


def test_reader_ignores_relative_names_and_takes_only_absolute_paths():
    assert extract_node_path(_as_panel_detail({"node": "topnet1"})) is None


# A TRUNCATED fragment carrying no node at all. This is a distinct code path
# from the valid-JSON no-node case above: it falls all the way through both
# fallbacks to the final return. The mutation harness (harness/notes/
# h3b_mutate.py, M6) proved the earlier control did NOT reach that line, so a
# reader that invented a default target passed every pin. Found by the
# instrument, not by review.
NO_NODE_TRUNCATED = _as_panel_detail(
    {"intent": "render the hero shot at full quality with every wedge "
               "enabled and the farm scheduler attached", "quality": "final"})


def test_no_node_truncated_fixture_really_is_truncated():
    assert len(NO_NODE_TRUNCATED) == 120
    try:
        json.loads(NO_NODE_TRUNCATED)
        raise AssertionError("fixture parsed -- it is not truncated")
    except ValueError:
        pass


def test_reader_returns_None_for_a_TRUNCATED_payload_with_no_node():
    """The path M6 exposed. A cancel control that invents a target is worse
    than one that admits it has none."""
    assert extract_node_path(NO_NODE_TRUNCATED) is None


def test_reader_refuses_a_file_path_as_a_node_target():
    """Truncation can hide the node key while leaving an output path visible.
    Cancelling a cook on /mnt/shots/a.exr is a WRONG target, not a missing
    one -- the fallback must decline it."""
    assert extract_node_path('{"output": "/mnt/shots/a.exr", "quality": "fin') is None
    # ...but a real node path with no dot in its last segment is still found
    assert extract_node_path('{"unknown_key": "/tasks/topnet1", "q": "fi') == "/tasks/topnet1"


def test_reader_accepts_the_alias_keys_handlers_actually_use():
    for key in ("node", "node_path", "parent_path", "path"):
        assert extract_node_path(_as_panel_detail({key: "/tasks/t1"})) == "/tasks/t1"


# ---------------------------------------------------------------------------
# R34 — mutation proofs for the reader.
# ---------------------------------------------------------------------------

def _mutant_json_only(detail):
    """MUTANT: the obvious implementation -- json.loads and nothing else.

    This is what the reader would have been without the truncation fallback.
    """
    if not detail:
        return None
    try:
        parsed = json.loads(detail)
    except (ValueError, TypeError):
        return None
    return parsed.get("node") if isinstance(parsed, dict) else None


def test_MUTATION_CATCHES_truncation_blindness():
    """Proves the truncated-JSON pin discriminates: the naive reader returns
    None on the exact payload a real cook produces, which would have shipped a
    cancel control that never found a target."""
    assert extract_node_path(TRUNCATED) == "/tasks/topnet1/wedge_shotA"
    assert _mutant_json_only(TRUNCATED) is None


def _mutant_any_path_first(detail):
    """MUTANT: grabs the first absolute-looking path, ignoring key preference."""
    import re
    m = re.search(r'"(/[^"]+)"', detail or "")
    return m.group(1) if m else None


def test_MUTATION_CATCHES_key_preference():
    """A payload whose FIRST path is an output file, not the node. The real
    reader must prefer the node key; the mutant grabs the file and would
    cancel using a filesystem path."""
    detail = _as_panel_detail({"output": "/mnt/shots/a.exr", "node": "/tasks/t1"})
    assert extract_node_path(detail) == "/tasks/t1"
    assert _mutant_any_path_first(detail) == "/mnt/shots/a.exr"


def _mutant_never_none(detail):
    """MUTANT: falls back to a default network instead of admitting it does
    not know. This is the 'cancel the wrong thing' failure."""
    return extract_node_path(detail) or "/tasks/topnet1"


def test_MUTATION_CATCHES_guessing_a_target():
    no_node = _as_panel_detail({"intent": "render shot A"})
    assert extract_node_path(no_node) is None
    assert _mutant_never_none(no_node) == "/tasks/topnet1"


# ---------------------------------------------------------------------------
# Which tools the cancel control offers itself for.
# ---------------------------------------------------------------------------

def test_cookish_tools_are_recognised_with_and_without_the_prefix():
    assert is_cookish_tool("tops_cook_node")
    assert is_cookish_tool("synapse_tops_batch_cook")


def test_non_cook_tools_are_not_offered_a_cook_cancel():
    for name in ("houdini_create_node", "synapse_recall", "render", None, ""):
        assert not is_cookish_tool(name)


# ---------------------------------------------------------------------------
# Structural pins on the panel wiring itself: the controls must exist, must be
# DISTINCT from Stop, and must not have replaced it (brief: "_on_stop
# unchanged", R29 "not a rename of Stop").
# ---------------------------------------------------------------------------

_PANEL = os.path.join(_root, "python", "synapse", "panel", "synapse_panel.py")


def _panel_source():
    with open(_PANEL, "r", encoding="utf-8") as fh:
        return fh.read()


def test_stop_button_is_still_state_gated_to_working():
    """R29 §1: a Stop shown when nothing is running is the same lie as a
    consent gate that does not gate. This leg must not have loosened it."""
    src = _panel_source()
    assert "self._stop_btn.setVisible(busy)" in src


def test_on_stop_still_only_aborts_the_loop_and_never_claims_idle():
    """The brief forbids replacing _on_stop. Pin its two load-bearing lines."""
    src = _panel_source()
    assert "self._worker.abort()" in src
    assert "Stopping — waiting on" in src


def test_cancel_cook_and_emergency_halt_are_separate_handlers():
    """Three verbs, three consequences -- never collapsed into one button."""
    src = _panel_source()
    for handler in ("def _on_stop(", "def _on_cancel_cook(",
                    "def _on_emergency_halt("):
        assert handler in src, handler
    # and the halt must NOT be wired to the Stop button
    assert "self._stop_btn.clicked.connect(self._on_stop)" in src
    assert "self._stop_btn.clicked.connect(self._on_emergency_halt)" not in src


def test_cancel_cook_refuses_rather_than_guessing_a_node():
    """The panel must not invent a target when it has none."""
    src = _panel_source()
    start = src.index("def _on_cancel_cook(")
    body = src[start:start + 900]
    assert "if not node:" in body
    assert "I don't know which node to cancel" in body
