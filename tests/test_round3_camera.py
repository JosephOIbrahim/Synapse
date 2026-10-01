"""Round 3 camera polish (10/1 12:22 take): R1 REVERT, R2 label spacing,
R3 narration spacing, R4 prompt rules.

The fake undo stack is pinned to hou.undos on 22.0.400 (probed): undoLabels()
returns a tuple, next-to-undo FIRST; performUndo() pops that entry onto the
redo stack; areEnabled() -> bool. create_autospec on the spec class means a
call with an invented argument fails here.
"""
import ast
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

from synapse.panel import turn_revert  # noqa: E402
from synapse.server import handlers_solaris_graph as graph_mod  # noqa: E402


class _UndosSpec:
    def undoLabels(self): ...
    def performUndo(self): ...
    def areEnabled(self): ...


def _undos(labels, enabled=True):
    """A fake hou.undos over ``labels`` (next-to-undo first)."""
    stack = list(labels)
    undos = mock.create_autospec(_UndosSpec, instance=True)
    undos.undoLabels.side_effect = lambda: tuple(stack)
    undos.performUndo.side_effect = lambda: stack.pop(0)
    undos.areEnabled.return_value = enabled
    undos.stack = stack
    return undos


BEFORE = ("Artist: create light", "Load scene")
BUILD = "SYNAPSE: synapse_solaris_build_graph: {\"parent\": \"/stage\"}"
AFTER = (BUILD,) + BEFORE


# ── R1: the safety property ─────────────────────────────────────────────


class TestTurnRevert:
    def test_undoes_exactly_the_turns_synapse_entries(self):
        undos = _undos(AFTER)
        ok, message = turn_revert.revert_turn(undos, BEFORE, AFTER)
        assert ok and "Reverted 1 SYNAPSE change" in message
        assert tuple(undos.stack) == BEFORE
        assert undos.performUndo.call_count == 1

    def test_several_entries_from_one_turn(self):
        after = ("SYNAPSE: synapse_set_parm: {}", BUILD) + BEFORE
        undos = _undos(after)
        ok, _ = turn_revert.revert_turn(undos, BEFORE, after)
        assert ok and tuple(undos.stack) == BEFORE and undos.performUndo.call_count == 2

    @pytest.mark.parametrize("above", [
        "hou.NetworkMovableItem.setPosition",   # an artist's manual edit
        "Change Selection",                     # one click in the network editor
        "Clear Selection",
        "SYNAPSE: synapse_set_parm: {}",        # a LATER turn's change
    ])
    def test_anything_above_the_turn_refuses_and_changes_nothing(self, above):
        undos = _undos((above,) + AFTER)
        ok, message = turn_revert.revert_turn(undos, BEFORE, AFTER)
        assert ok is False
        assert above in message and "Nothing was changed" in message
        undos.performUndo.assert_not_called()

    def test_artist_already_undid_part_of_it_refuses(self):
        undos = _undos(BEFORE)
        ok, message = turn_revert.revert_turn(undos, BEFORE, AFTER)
        assert not ok and "Nothing was changed" in message
        undos.performUndo.assert_not_called()

    def test_a_foreign_entry_inside_the_turn_refuses(self):
        after = (BUILD, "Change Selection") + BEFORE
        undos = _undos(after)
        ok, message = turn_revert.revert_turn(undos, BEFORE, after)
        assert not ok and "Change Selection" in message
        undos.performUndo.assert_not_called()

    @pytest.mark.parametrize("before, after", [(None, AFTER), (BEFORE, None), (BEFORE, BEFORE)])
    def test_missing_or_empty_turn_record_refuses(self, before, after):
        undos = _undos(AFTER)
        ok, _ = turn_revert.revert_turn(undos, before, after)
        assert not ok
        undos.performUndo.assert_not_called()

    def test_disabled_or_absent_undo_refuses(self):
        undos = _undos(AFTER, enabled=False)
        assert turn_revert.revert_turn(undos, BEFORE, AFTER)[0] is False
        undos.performUndo.assert_not_called()
        assert turn_revert.revert_turn(None, BEFORE, AFTER)[0] is False

    def test_synapse_label_prefixes(self):
        for label in (BUILD, "SYNAPSE insert saved network", "synapse_set_parm"):
            assert turn_revert.is_synapse_label(label)
        for label in ("Change Selection", "hou.Node.setInput", "Synapse-ish", ""):
            assert not turn_revert.is_synapse_label(label)


def _panel_method(name):
    source = Path(_ROOT) / "python/synapse/panel/synapse_panel.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SynapsePanel")
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = {"logger": mock.Mock()}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[name]


class TestPanelRevert:
    def _panel(self):
        return SimpleNamespace(_worker=None, _chat=mock.Mock(), _set_face=mock.Mock(),
                               _send=mock.Mock(return_value=True), _hide_turn_receipt=mock.Mock(),
                               _turn_undo_before=BEFORE, _turn_undo_after=AFTER)

    def test_receipt_revert_undoes_directly_without_a_model_turn(self, monkeypatch):
        undos = _undos(AFTER)
        monkeypatch.setattr(turn_revert, "hou_undos", lambda: undos)
        panel = self._panel()
        assert _panel_method("_on_revert")(panel) is True
        panel._send.assert_not_called()
        assert tuple(undos.stack) == BEFORE
        panel._hide_turn_receipt.assert_called_once()
        panel._set_face.assert_called_once_with("direct")
        assert panel._turn_undo_after is None          # one turn, one revert
        assert "Reverted" in panel._chat.append_system_message.call_args[0][0]

    def test_refusal_says_so_and_keeps_the_receipt(self, monkeypatch):
        undos = _undos(("Change Selection",) + AFTER)
        monkeypatch.setattr(turn_revert, "hou_undos", lambda: undos)
        panel = self._panel()
        assert _panel_method("_on_revert")(panel) is False
        undos.performUndo.assert_not_called()
        panel._hide_turn_receipt.assert_not_called()
        panel._set_face.assert_not_called()
        assert "REVERT refused" in panel._chat.append_system_message.call_args[0][0]

    def test_second_click_refuses(self, monkeypatch):
        undos = _undos(AFTER)
        monkeypatch.setattr(turn_revert, "hou_undos", lambda: undos)
        panel = self._panel()
        revert = _panel_method("_on_revert")
        assert revert(panel) is True
        assert revert(panel) is False
        assert undos.performUndo.call_count == 1

    def test_turn_start_and_end_take_snapshots(self):
        src = (Path(_ROOT) / "python/synapse/panel/synapse_panel.py").read_text(encoding="utf-8")
        send = src[src.index("    def _send(self, text):"):]
        done = src[src.index("    def _on_done(self):"):]
        assert "self._turn_undo_before = turn_revert.snapshot(turn_revert.hou_undos())" in send
        assert "self._turn_undo_after = turn_revert.snapshot(turn_revert.hou_undos())" in done


# ── R1 corollary: framing never pushes a selection undo entry ───────────


def test_framing_selects_inside_an_undo_disabler(monkeypatch):
    from test_solaris_graph_oncamera import _fake_hou, _editor, _chain, _parent
    entered = []

    class _Disabler:
        def __enter__(self):
            entered.append("in")

        def __exit__(self, *exc):
            entered.append("out")

    editor = _editor("/stage")
    fake = _fake_hou(tabs=[editor])
    fake.undos = SimpleNamespace(disabler=_Disabler)
    monkeypatch.setattr(graph_mod, "hou", fake, raising=False)
    look, key, rim, dome = _chain()
    key.setSelected.side_effect = lambda *a, **k: entered.append("select")
    assert graph_mod._frame_new_nodes(_parent(), [key, rim], rim) is True
    assert entered == ["in", "select", "out"]


# ── R2: label-aware spacing ─────────────────────────────────────────────


class TestLabelSpacing:
    LOOK_COMMENT = ("The look: fade_10 (Joe, 10/1). Each splat's opacity x min(1, 10 / "
                    "elongation). Bypass for the as-is look.")

    def test_label_lines_rule(self):
        assert graph_mod._label_lines(self.LOOK_COMMENT, True, False) == 3   # drew 3 on camera
        assert graph_mod._label_lines(self.LOOK_COMMENT, False, False) == 0  # comment hidden
        assert graph_mod._label_lines("SYNAPSE: build_graph", True, True) == 2  # comment + prim path
        assert graph_mod._label_lines("", True, True) == 1
        assert graph_mod._label_lines("a\nb", True, False) == 2

    def test_inline_gaps_grow_by_label_lines(self):
        look, dome = (-1.69, 2.41), (-1.69, 1.52)
        local = {"key": (0.0, 0.0), "rim": (0.0, -1.2)}
        down = {"/stage/demo_dome": dome, "/stage/demo_cam": (-1.69, 0.62)}
        positions, shifts = graph_mod._inline_splice_layout(
            look, dome, local, down, anchor_lines=3, node_lines={"key": 2, "rim": 2})
        pitch, line = 2.41 - 1.52, graph_mod._LABEL_LINE
        assert look[1] - positions["key"][1] == pytest.approx(pitch + 3 * line)
        assert positions["key"][1] - positions["rim"][1] == pytest.approx(pitch + 2 * line)
        new_dome = dome[1] + shifts[0][2]
        assert positions["rim"][1] - new_dome == pytest.approx(pitch + 2 * line)
        assert all(s[2] == pytest.approx(shifts[0][2]) for s in shifts)   # chain keeps its spacing

    def test_no_labels_keeps_round2_layout(self):
        look, dome = (-1.69, 2.41), (-1.69, 1.52)
        positions, _ = graph_mod._inline_splice_layout(look, dome, {"k": (0.0, 0.0)}, {})
        assert positions["k"][1] == pytest.approx(1.52)


# ── R3: narration chunks from separate model turns are separated ─────────

from test_worker_tool_policy import claude_worker_module  # noqa: E402,F401


class _Provider:
    id = "fake"
    model_identity = "fake-model-1"

    def __init__(self, script):
        self._script = list(script)
        self.last_usage = None

    def resolve_key(self):
        return "key"

    def key_error_message(self):
        return "no key"

    def stream(self, emit_token=None, **_kw):
        stop, blocks, texts = self._script.pop(0)
        for text in texts:
            emit_token(text)
        return stop, blocks


def _emitted(cw, script, monkeypatch):
    monkeypatch.setattr(cw, "try_mcp_tool_call", lambda name, inp: {"ok": True})
    w = cw.ClaudeWorker([{"role": "user", "content": "hi"}], tools=[], provider=_Provider(script))
    for sig in ("tool_status", "activity_changed", "token_received", "stream_done", "stream_error"):
        setattr(w, sig, mock.MagicMock())
    w._conversation_loop("key")
    return [c.args[0] for c in w.token_received.emit.call_args_list]


def test_turns_of_narration_get_a_paragraph_break(claude_worker_module, monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(tmp_path / "turns.jsonl"))
    tool = [{"type": "tool_use", "id": "t1", "name": "synapse_ping", "input": {}}]
    out = _emitted(claude_worker_module, [
        ("tool_use", tool, ["Checking the ", "stage"]),
        ("tool_use", [dict(tool[0], id="t2")], []),          # a silent turn adds nothing
        ("end_turn", [], ["instead, I ", "put it together."]),
    ], monkeypatch)
    assert "".join(out) == "Checking the stage\n\ninstead, I put it together."


def test_single_turn_text_is_untouched(claude_worker_module, monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_USAGE_LEDGER", str(tmp_path / "turns.jsonl"))
    out = _emitted(claude_worker_module, [("end_turn", [], ["Good, ", "done."])], monkeypatch)
    assert out == ["Good, ", "done."]


# ── R4: prompt rules ────────────────────────────────────────────────────


def test_prompt_rules_r4():
    from synapse.panel import system_prompt
    g = system_prompt._TOOL_GUIDANCE
    assert "**Inspect once, then build:**" in g
    assert "do \\\nnot re-query" not in g and "not re-query what the receipt already proves" in g
    assert "**Asked to show, but you cannot see:**" in g
    assert "Do not search for a render path or a ROP unless the artist" in g
    assert "**State what you set, not how it looks:**" in g
    assert "exposure 0.5, 3200 K, rotated -22/-30" in g
    assert "not done or not verified" in g   # round-2 disclosure rule intact
