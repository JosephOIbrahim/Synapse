"""The Spatial control's words and its default call (D6 / R-10, R-11).

No Qt and no ``hou``: this module is what the panel says after a click, and
the one call it makes. The result below is the trail tool's own, from the
recorded GUI test on the demo scene (2026-10-02), trimmed to the fields the
panel reads.
"""
from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Optional

from synapse.panel import spatial_action as sa

OUTCOME = ("demo_cam: an arc of radius 6.00 m through 20.0 deg, 2.09 m of travel at a stage "
           "height of 1.29 m, aimed at the arc's centre; the nearest splat centre comes to "
           "1.04 m, left of the lens, at frame 1. Drew the path as /guides/demo_cam_path "
           "(proxy purpose, 144 points); Karma's render settings leave it out.")
CREATED = {
    "status": "SUCCESS",
    "outcome": OUTCOME,
    "clearance": {"min_m": 1.04, "frame": 1.0, "side": "left", "status": "SUCCESS"},
    "trail": {"status": "created", "node": "/stage/demo_cam_path", "prim": "/guides/demo_cam_path",
              "points": 144, "purpose": "proxy", "karma_leaves_it_out": True},
    "undo": {"artist": "One Ctrl+Z reverses: spatial trail", "label": "SYNAPSE: spatial_trail"},
}


def test_the_answer_is_the_tools_sentence_then_the_way_back():
    text = sa.answer_text(CREATED)
    first, last = text.split("\n\n")
    assert first == OUTCOME                       # the tool's sentence, word for word
    assert last == "One Ctrl+Z reverses: spatial trail."
    # Nothing here is the panel's own claim about the scene.
    assert "Not measured" not in text


def test_what_the_clearance_left_out_is_said_without_the_tool_hint():
    result = dict(CREATED, clearance=dict(CREATED["clearance"], not_measured=[
        "1 mesh prim (pass against=mesh)", "point-instancer instances"]))
    text = sa.answer_text(result)
    assert "Not measured: 1 mesh prim; point-instancer instances." in text
    assert "against=" not in text                 # a hint for a model, not for an artist
    # Order: the measurement, what it left out, then the way back.
    assert text.index(OUTCOME) < text.index("Not measured") < text.index("One Ctrl+Z")


def test_an_unchanged_trail_has_no_way_back_line_and_earns_no_receipt():
    unchanged = {"outcome": "demo_cam: static. The path is already drawn as /guides/demo_cam_path.",
                 "trail": {"status": "unchanged"}}
    assert sa.answer_text(unchanged) == unchanged["outcome"]
    assert sa.changed_scene(unchanged) is False
    assert sa.changed_scene(CREATED) is True
    assert sa.changed_scene(dict(CREATED, trail={"status": "updated"})) is True
    assert sa.changed_scene({}) is False


def test_an_error_shows_the_tools_own_reason():
    reason = ("No trail drawn: no Camera LOP at or upstream of /stage/out authors /cameras/cam, "
              "so its move can't be read without moving the playhead")
    assert sa.error_text(reason) == "Spatial: " + reason
    # No result and no reason is still said, never an empty line.
    assert sa.error_text(None) == "Spatial: the tool returned no result"
    assert sa.error_text("  ") == "Spatial: the tool returned no result"


def test_the_copy_names_no_vendor_and_fits_the_control():
    for text in (sa.TOOLTIP, sa.SIGNED, sa.BUSY, sa.RUNNING, sa.HISTORY_ASK, sa.HISTORY_NOTE):
        assert "world labs" not in text.lower() and "worldlabs" not in text.lower()
    assert "No model call" in sa.TOOLTIP and "One undo step" in sa.TOOLTIP
    assert "no model request" in sa.SIGNED
    assert sa.TOOL == "synapse_spatial_trail"


@dataclass
class _Request:
    tool_use_id: str
    tool_name: str
    tool_input: dict
    result: Any = None
    error: Optional[str] = None
    done: threading.Event = field(default_factory=threading.Event)


def _fake_executor_module(outcome):
    seen = {}

    class _Executor:
        def execute_tool_off_main(self, request):
            seen["tool"], seen["input"] = request.tool_name, request.tool_input
            seen["thread"] = threading.get_ident()
            outcome(request)
            request.done.set()

    return SimpleNamespace(ToolExecutor=_Executor, ToolRequest=_Request), seen


def test_call_trail_runs_the_one_tool_with_no_arguments(monkeypatch):
    module, seen = _fake_executor_module(lambda request: setattr(request, "result", CREATED))
    monkeypatch.setitem(sys.modules, "synapse.panel.tool_executor", module)
    result, error = sa.call_trail()
    assert (result, error) == (CREATED, None)
    # One tool, and nothing a model could have steered: no code, no coordinates.
    assert seen["tool"] == "synapse_spatial_trail" and seen["input"] == {}


def test_call_trail_returns_the_tools_error_and_never_a_half_result(monkeypatch):
    module, _ = _fake_executor_module(lambda request: setattr(request, "error", "No trail drawn: x"))
    monkeypatch.setitem(sys.modules, "synapse.panel.tool_executor", module)
    assert sa.call_trail() == (None, "No trail drawn: x")
    module, _ = _fake_executor_module(lambda request: setattr(request, "result", "OK"))
    monkeypatch.setitem(sys.modules, "synapse.panel.tool_executor", module)
    assert sa.call_trail() == (None, None)        # not a dict: the panel says "no result"
