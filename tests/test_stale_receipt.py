"""The turn receipt goes once Houdini's undo history no longer holds the turn.

STALERECEIPT (the recorded GUI check, 2026-10-02). After a Spatial click the
panel showed "1 CHANGE" and REVERT. The artist undid the path with Edit > Undo,
and the receipt stayed. A click on REVERT then refused, changed nothing and
said why, which is safe, and the panel was still offering to revert a change
that was no longer in the scene.

The panel already reads the scene every two seconds, off the Qt thread
(``ws_bridge.gather_context_off_main``). That read now carries the undo
history's labels, and the receipt goes when they no longer hold the turn as it
left the stack. Nothing is undone and nothing is said: the receipt was a record
of a step, and the step is gone.

What it does not do, and the record says so: the receipt goes within one tick,
not at once; a redo after the undo does not bring it back; and an unreadable
history is not evidence, so the receipt stays.

No Qt and no Houdini: the predicate is pure, the gather is read against a fake
``hou.undos``, and the panel methods are compiled out of the panel's source the
way ``test_round3_camera`` does it.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from qt_stub_window import qt_stub_window  # noqa: E402

from synapse.panel import turn_revert  # noqa: E402

with qt_stub_window():                         # ws_bridge imports QtCore at module level
    from synapse.panel import ws_bridge  # noqa: E402

BEFORE = ("Artist: create light", "Load scene")
TRAIL = "SYNAPSE: Draw camera path"
AFTER = (TRAIL,) + BEFORE


# --------------------------------------------------------------------------- #
#  The predicate                                                              #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("now, gone, why", [
    (AFTER, False, "nothing happened since the turn"),
    (("Change Selection",) + AFTER, False, "a click in the network editor sits on top of the turn"),
    (("Parameter Change", "Change Selection") + AFTER, False, "the artist kept working on top of it"),
    (BEFORE, True, "the artist undid the turn's step"),
    (BEFORE[1:], True, "the artist undid the turn's step and one before it"),
    (("Parameter Change",) + BEFORE, True, "the artist undid it and then did something else"),
    ((TRAIL,) + BEFORE[:1], True, "the history under the turn was trimmed; REVERT refuses this too"),
    ((), True, "the history was cleared"),
])
def test_a_turn_is_gone_when_the_stack_no_longer_holds_it_as_it_left_it(now, gone, why):
    assert turn_revert.turn_gone(BEFORE, AFTER, now) is gone, why


def test_a_redo_puts_the_turn_back_on_the_stack():
    assert turn_revert.turn_gone(BEFORE, AFTER, BEFORE) is True
    assert turn_revert.turn_gone(BEFORE, AFTER, AFTER) is False


def test_one_step_of_a_longer_turn_undone_is_gone():
    after = ("SYNAPSE: synapse_set_parm: {}", TRAIL) + BEFORE
    assert turn_revert.turn_gone(BEFORE, after, after) is False
    assert turn_revert.turn_gone(BEFORE, after, after[1:]) is True


def test_a_turn_that_left_no_step_cannot_go_stale():
    """A credited tool that writes nothing undoable leaves the stack as it was.
    The artist undoing something older says nothing about that turn."""
    assert turn_revert.turn_gone(BEFORE, BEFORE, BEFORE[1:]) is False
    assert turn_revert.turn_gone(BEFORE, BEFORE, ()) is False


@pytest.mark.parametrize("before, after, now", [
    (None, AFTER, BEFORE), (BEFORE, None, BEFORE), (BEFORE, AFTER, None),
    (BEFORE[1:] + ("x",), AFTER, BEFORE),       # the turn's own record is not a clean extension
])
def test_an_unreadable_history_is_not_evidence(before, after, now):
    assert turn_revert.turn_gone(before, after, now) is False


def test_revert_refuses_in_the_words_it_had():
    """REVERT's comparison and the receipt's are one function now. The two
    refusals an artist can meet read as they did."""
    undos = SimpleNamespace(areEnabled=lambda: True, undoLabels=lambda: ("Change Selection",) + AFTER,
                            performUndo=mock.Mock())
    ok, message = turn_revert.revert_turn(undos, BEFORE, AFTER)
    assert ok is False and message == (
        "REVERT refused: \"Change Selection\" happened after that turn, and REVERT never "
        "undoes your own changes. Nothing was changed. Ctrl+Z still works.")
    undos.undoLabels = lambda: BEFORE
    ok, message = turn_revert.revert_turn(undos, BEFORE, AFTER)
    assert ok is False and message == (
        "REVERT refused: the undo history changed after that turn. Nothing was changed. "
        "Ctrl+Z still works.")
    undos.performUndo.assert_not_called()


# --------------------------------------------------------------------------- #
#  The two-second read carries the labels                                     #
# --------------------------------------------------------------------------- #
def _undos(labels, enabled=True):
    return SimpleNamespace(areEnabled=lambda: enabled, undoLabels=lambda: tuple(labels))


def test_the_context_read_carries_the_undo_labels(monkeypatch):
    monkeypatch.setattr(turn_revert, "hou_undos", lambda: _undos(AFTER))
    assert ws_bridge._gather_context_on_main_thread()["undo_labels"] == AFTER
    # Disabled or absent undo is unreadable, never an empty history.
    monkeypatch.setattr(turn_revert, "hou_undos", lambda: _undos(AFTER, enabled=False))
    assert ws_bridge._gather_context_on_main_thread()["undo_labels"] is None
    monkeypatch.setattr(turn_revert, "hou_undos", lambda: None)
    assert ws_bridge._gather_context_on_main_thread()["undo_labels"] is None
    assert ws_bridge._empty_context()["undo_labels"] is None


def test_the_labels_are_read_even_when_the_scene_read_bails(monkeypatch):
    """The scene reads share one guarded block, and a host without one of them
    leaves that block early. The labels have a block of their own."""
    import types
    bare = types.ModuleType("hou")                  # no selectedNodes, no ui, no hipFile
    monkeypatch.setitem(sys.modules, "hou", bare)
    monkeypatch.setattr(turn_revert, "hou_undos", lambda: _undos(AFTER))
    ctx = ws_bridge._gather_context_on_main_thread()
    assert ctx["selected_nodes"] == [] and ctx["undo_labels"] == AFTER


def test_a_failing_undo_read_never_costs_the_ribbon_its_scene_read(monkeypatch):
    def boom():
        raise RuntimeError("undo history unavailable")
    monkeypatch.setattr(turn_revert, "hou_undos", boom)
    ctx = ws_bridge._gather_context_on_main_thread()
    assert ctx["undo_labels"] is None
    assert set(ctx) == {"selected_nodes", "current_network", "scene_file", "frame", "undo_labels"}


def test_the_undo_history_never_rides_a_chat_message():
    """The labels are for the panel's own receipt. ``send_chat`` takes the same
    dict as scene context, and they are left out of what it sends."""
    sent = []
    bridge = SimpleNamespace(_ws=SimpleNamespace(send=sent.append), _lock=mock.MagicMock(),
                             _queue=[], _connected=True)
    context = {"selected_nodes": ["/obj/geo1"], "current_network": "/obj", "scene_file": "a.hip",
               "frame": 1.0, "undo_labels": AFTER}
    ws_bridge.SynapseWSBridge.send_chat(bridge, "hello", context=context)
    assert len(sent) == 1
    payload = json.loads(sent[0])
    assert payload["context"] == {"selected_nodes": ["/obj/geo1"], "current_network": "/obj",
                                  "scene_file": "a.hip", "frame": 1.0}
    assert "undo_labels" in context                 # the caller's dict is not edited


# --------------------------------------------------------------------------- #
#  The panel                                                                  #
# --------------------------------------------------------------------------- #
_PANEL_SOURCE = Path(_ROOT) / "python/synapse/panel/synapse_panel.py"


def _panel_method(name):
    tree = ast.parse(_PANEL_SOURCE.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"logger": mock.Mock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(_PANEL_SOURCE), "exec"), namespace)
    return namespace[name]


def _panel(before=BEFORE, after=AFTER, hidden=False):
    return SimpleNamespace(_turn_receipt=SimpleNamespace(isHidden=lambda: hidden),
                           _hide_turn_receipt=mock.Mock(),
                           _turn_undo_before=before, _turn_undo_after=after)


def _ctx(labels):
    return {"selected_nodes": [], "current_network": "", "scene_file": "a.hip", "frame": 1.0,
            "undo_labels": labels}


def test_the_receipt_goes_after_the_artists_own_undo():
    retire = _panel_method("_retire_stale_receipt")
    panel = _panel()
    assert retire(panel, _ctx(BEFORE)) is True
    panel._hide_turn_receipt.assert_called_once_with()
    # The record of the turn stays: REVERT's own refusal is still the net under
    # a click that lands before the receipt has gone.
    assert panel._turn_undo_before == BEFORE and panel._turn_undo_after == AFTER


def test_the_receipt_stays_while_the_turn_is_still_on_the_stack():
    retire = _panel_method("_retire_stale_receipt")
    for labels in (AFTER, ("Change Selection",) + AFTER, list(AFTER)):
        panel = _panel()
        assert retire(panel, _ctx(labels)) is False
        panel._hide_turn_receipt.assert_not_called()


@pytest.mark.parametrize("panel, ctx, why", [
    (_panel(hidden=True), _ctx(BEFORE), "no receipt is showing"),
    (_panel(), _ctx(None), "the history could not be read"),
    (_panel(), {"selected_nodes": [], "current_network": "", "scene_file": "a.hip", "frame": 1.0},
     "an older caller's context has no labels"),
    (_panel(after=None), _ctx(BEFORE), "the turn's end was never recorded, or REVERT already ran"),
    (_panel(before=None), _ctx(BEFORE), "the turn's start was never recorded"),
    (_panel(), None, "no context at all"),
    (SimpleNamespace(_hide_turn_receipt=mock.Mock()), _ctx(BEFORE), "a panel with no receipt built"),
])
def test_what_is_not_evidence_hides_nothing(panel, ctx, why):
    assert _panel_method("_retire_stale_receipt")(panel, ctx) is False, why
    panel._hide_turn_receipt.assert_not_called()


def test_a_spoken_turn_and_a_click_are_retired_the_same_way():
    """``_on_done`` and ``_spatial_done`` both leave the same two snapshots, so
    one check covers the receipt after a turn the model ran and after a click."""
    source = _PANEL_SOURCE.read_text(encoding="utf-8")
    for method in ("    def _on_done(self):", "    def _spatial_done(self, result, error):"):
        body = source[source.index(method):]
        assert "self._turn_undo_after = turn_revert.snapshot(turn_revert.hou_undos())" in body[:6000]
    build = ("SYNAPSE: synapse_solaris_build_graph: {'parent': '/stage'}",) + BEFORE
    panel = _panel(after=build)
    assert _panel_method("_retire_stale_receipt")(panel, _ctx(BEFORE)) is True


def test_the_tick_checks_the_receipt_and_a_failure_there_never_costs_the_ribbon():
    """``_apply_context`` is the tick's one place on the Qt thread. The receipt
    check sits in a guarded block of its own, after the ribbon is drawn."""
    tree = ast.parse(_PANEL_SOURCE.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    apply_context = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                         and n.name == "_apply_context")
    guarded = [n for n in apply_context.body if isinstance(n, ast.Try)
               and "_retire_stale_receipt" in ast.unparse(n.body)]
    assert len(guarded) == 1, "the receipt check must sit in its own try"
    assert len(guarded[0].body) == 1                 # nothing else shares that block
    ribbon = next(n for n in apply_context.body if isinstance(n, ast.Try)
                  and "_ctx_label" in ast.unparse(n.body))
    assert apply_context.body.index(ribbon) < apply_context.body.index(guarded[0])
