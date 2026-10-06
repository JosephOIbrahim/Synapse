"""HOM-13: rollback after an undo group must not take back the artist's last action.

No Houdini. The decision is extracted into two helpers shared by execute_python
(handlers.py) and configure_render_passes (handlers_render.py); the helpers are
driven with a stand-in hou.undos, and the source is pinned so both sites use them.
"""
import inspect
import types

from synapse.server import handlers, handlers_render


class _Undos:
    def __init__(self):
        self.labels = ["artist: move node"]
        self.performed = 0

    def undoLabels(self):
        return tuple(self.labels)

    def performUndo(self):
        self.performed += 1
        self.labels.pop()


def _run(body_adds_entry):
    undos = _Undos()
    hou = types.SimpleNamespace(undos=undos)
    before = handlers_render._undo_labels_snapshot(hou)
    if body_adds_entry:
        undos.labels.append("SYNAPSE: group")
    handlers_render._rollback_if_group_left_entry(hou, before)
    return undos


def test_body_raises_before_any_entry_does_not_undo():
    undos = _run(body_adds_entry=False)
    assert undos.performed == 0
    assert undos.labels == ["artist: move node"]


def test_body_adds_entry_then_raises_undoes_once():
    undos = _run(body_adds_entry=True)
    assert undos.performed == 1
    assert undos.labels == ["artist: move node"]


def test_unreadable_stack_does_not_undo():
    class Broken:
        def undoLabels(self):
            raise RuntimeError("no undo stack")

        def performUndo(self):
            raise AssertionError("must not be called")

    hou = types.SimpleNamespace(undos=Broken())
    before = handlers_render._undo_labels_snapshot(hou)
    assert before is None
    assert handlers_render._rollback_if_group_left_entry(hou, before) is False


def test_both_sites_use_the_guard():
    assert handlers._rollback_if_group_left_entry is handlers_render._rollback_if_group_left_entry
    exec_src = inspect.getsource(handlers)
    render_src = inspect.getsource(handlers_render.RenderHandlerMixin)
    assert "_rollback_if_group_left_entry(hou, _labels_before)" in exec_src
    assert "_rollback_if_group_left_entry(hou, labels_before)" in render_src
