"""WP3 (M1 "stop the fictions") -- compose handlers self-marshal + self-undo-wrap.

Before WP3, handlers_solaris_compose ran resolve_stage / build / bind directly
on the WS handler thread and its docstrings claimed the bridge owned
undo/integrity/consent -- a fiction on the live /synapse path (handlers are
dispatched directly; the bridge only wraps the panel/MCP path). Now each
mutating handler marshals its closure through run_on_main(timeout=_SLOW_TIMEOUT)
and owns its undo group with the build_graph rollback idiom (hou.undos.group +
performUndo on exception); assess_render_ready marshals read-only (no undo
group, default timeout); build_karma_xpu_shot reports its non-undoable
department-layer disk writes; and the panel bridge adapter marks the shotsetup
tool touches_disk so R4 elevates the gate to APPROVE.
"""

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Established handler-test convention: fakes before importing handlers.
_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)
_mock_hou.undos = MagicMock()
_hde = ModuleType("hdefereval")
_hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
sys.modules.setdefault("hou", _mock_hou)
sys.modules.setdefault("hdefereval", _hde)

from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.server import handlers_solaris_compose as hsc  # noqa: E402
from synapse.server import main_thread as mt  # noqa: E402


class _RecordingUndos:
    """hou.undos fake: group() is a recording contextmanager, performUndo a stub."""

    def __init__(self, events):
        self._events = events
        self.undo_count = 0

    def group(self, label):
        events = self._events

        class _Ctx:
            def __enter__(self):
                events.append(("group_enter", label))
                return self

            def __exit__(self, exc_type, exc, tb):
                events.append(("group_exit", label))
                return False

        return _Ctx()

    def performUndo(self):
        self.undo_count += 1
        self._events.append(("performUndo",))


def _wire(monkeypatch, events, node=None):
    """Install fake hou + run_on_main spy. Returns (in_main, calls, undos)."""
    in_main = {"active": False}
    calls = []
    undos = _RecordingUndos(events)

    def _node(path):
        events.append(("hou.node", path, in_main["active"]))
        return node

    def spy_run_on_main(fn, timeout=None):
        calls.append({"timeout": timeout})
        in_main["active"] = True
        try:
            return fn()
        finally:
            in_main["active"] = False

    monkeypatch.setattr(hsc, "hou", SimpleNamespace(undos=undos, node=_node))
    monkeypatch.setattr(hsc, "HOU_AVAILABLE", True)
    # Patch the LIVE sys.modules entry, not this file's collection-time `mt`:
    # test_main_thread.py swaps in a private main_thread instance at collection,
    # and the handlers' call-time `from .main_thread import run_on_main`
    # resolves against whatever is resident NOW.
    import importlib

    mt_live = importlib.import_module("synapse.server.main_thread")
    monkeypatch.setattr(mt_live, "run_on_main", spy_run_on_main)
    return in_main, calls, undos


def test_shotsetup_marshals_and_undo_wraps(monkeypatch):
    events = []
    in_main, calls, undos = _wire(monkeypatch, events)
    sentinel = {"status": "created", "sentinel": "wp3"}

    def fake_resolve(path):
        events.append(("resolve_stage", path, in_main["active"]))
        return "STAGE"

    def fake_build(stage, **kwargs):
        events.append(("build", stage, in_main["active"]))
        return sentinel

    monkeypatch.setattr(hsc, "_sc", SimpleNamespace(resolve_stage=fake_resolve))
    monkeypatch.setattr(
        hsc, "_tools", SimpleNamespace(build_karma_xpu_shot=fake_build)
    )

    h = SynapseHandler()
    result = h._handle_solaris_shotsetup_karma_xpu({"shot": "wp3"})

    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["timeout"] == mt._SLOW_TIMEOUT
    # resolve_stage and the build both ran inside the main-thread closure
    assert ("resolve_stage", "/stage", True) in events
    build_idx = events.index(("build", "STAGE", True))
    enter_idx = events.index(("group_enter", "SYNAPSE: solaris_shotsetup_karma_xpu"))
    exit_idx = events.index(("group_exit", "SYNAPSE: solaris_shotsetup_karma_xpu"))
    assert enter_idx < build_idx < exit_idx
    assert undos.undo_count == 0


def test_shotsetup_rolls_back_on_exception(monkeypatch):
    events = []
    in_main, calls, undos = _wire(monkeypatch, events)

    def boom(stage, **kwargs):
        raise RuntimeError("cook failed")

    monkeypatch.setattr(hsc, "_sc", SimpleNamespace(resolve_stage=lambda p: "STAGE"))
    monkeypatch.setattr(hsc, "_tools", SimpleNamespace(build_karma_xpu_shot=boom))

    h = SynapseHandler()
    with pytest.raises(RuntimeError, match="cook failed"):
        h._handle_solaris_shotsetup_karma_xpu({})

    assert undos.undo_count == 1  # performUndo rollback recorded
    assert ("performUndo",) in events


def test_matlib_bind_marshals(monkeypatch):
    events = []
    node_sentinel = object()
    in_main, calls, undos = _wire(monkeypatch, events, node=node_sentinel)
    sentinel = {"status": "bound", "sentinel": "wp3"}
    seen = {}

    def fake_resolve(path):
        events.append(("resolve_stage", path, in_main["active"]))
        return "STAGE"

    def fake_bind(stage, material, targets, input_node=None, strength=None):
        events.append(("bind", in_main["active"]))
        seen["input_node"] = input_node
        return sentinel

    monkeypatch.setattr(hsc, "_sc", SimpleNamespace(resolve_stage=fake_resolve))
    monkeypatch.setattr(hsc, "_tools", SimpleNamespace(bind_material=fake_bind))

    h = SynapseHandler()
    result = h._handle_matlib_bind({
        "material": "/materials/red",
        "targets": "//Mesh",
        "input_node": "/stage/dept_stack",
    })

    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["timeout"] == mt._SLOW_TIMEOUT
    # hou.node + resolve_stage resolved INSIDE the main-thread closure
    assert ("hou.node", "/stage/dept_stack", True) in events
    assert ("resolve_stage", "/stage", True) in events
    assert seen["input_node"] is node_sentinel
    bind_idx = events.index(("bind", True))
    enter_idx = events.index(("group_enter", "SYNAPSE: matlib_bind"))
    exit_idx = events.index(("group_exit", "SYNAPSE: matlib_bind"))
    assert enter_idx < bind_idx < exit_idx


def test_assess_marshals_no_undo(monkeypatch):
    events = []
    in_main, calls, undos = _wire(monkeypatch, events)
    sentinel = {"ready": True}

    def fake_assess(stage, engine_hint=None):
        events.append(("assess", in_main["active"]))
        return sentinel

    monkeypatch.setattr(hsc, "_sc", SimpleNamespace(resolve_stage=lambda p: "STAGE"))
    monkeypatch.setattr(
        hsc, "_tools", SimpleNamespace(assess_render_ready=fake_assess)
    )

    h = SynapseHandler()
    result = h._handle_assess_render_ready({"engine": "xpu"})

    assert result is sentinel
    assert len(calls) == 1
    assert calls[0]["timeout"] is None  # default timeout, not _SLOW_TIMEOUT
    assert ("assess", True) in events
    # Read-only: no undo group ever entered
    assert not any(e[0] == "group_enter" for e in events)
    assert undos.undo_count == 0


def test_disk_writes_reported(tmp_path, monkeypatch):
    from synapse.server import solaris_compose_tools as sct

    class _FakeSdfLayer:
        @staticmethod
        def CreateNew(fp):
            Path(fp).write_text("#usda 1.0\n")
            return SimpleNamespace(Save=lambda: None)

    fake_pxr = ModuleType("pxr")
    fake_pxr.Sdf = SimpleNamespace(Layer=_FakeSdfLayer)
    monkeypatch.setitem(sys.modules, "pxr", fake_pxr)

    fake_sc = MagicMock()
    fake_sc.composition_errors.return_value = []
    monkeypatch.setattr(sct, "sc", fake_sc)
    monkeypatch.setattr(sct, "HOU_AVAILABLE", True)
    monkeypatch.setattr(
        sct, "hou", SimpleNamespace(expandString=lambda s: str(tmp_path))
    )

    stage_node = MagicMock()
    first = sct.build_karma_xpu_shot(stage_node, shot="wp3", layer_dir=str(tmp_path))
    expected = [
        str(tmp_path) + "/" + d + ".usd"
        for d in ("layout", "animation", "lighting", "fx", "render")
    ]
    assert first["disk_writes"] == expected
    assert first["disk_writes_undoable"] is False
    assert all(Path(fp).exists() for fp in expected)

    # Second call: files already exist -- nothing new written to disk.
    second = sct.build_karma_xpu_shot(stage_node, shot="wp3", layer_dir=str(tmp_path))
    assert second["disk_writes"] == []
    assert second["disk_writes_undoable"] is False


def test_bridge_adapter_marks_touches_disk(monkeypatch):
    from synapse.panel import bridge_adapter as ba

    class _RecorderBridge:
        def __init__(self):
            self.ops = []

        def execute(self, op):
            self.ops.append(op)
            return SimpleNamespace(
                success=True,
                result=SimpleNamespace(data=None),
                integrity=None,
                error=None,
            )

    recorder = _RecorderBridge()
    monkeypatch.setattr(ba, "get_bridge", lambda: recorder)

    command = SimpleNamespace(id="wp3", payload={"shot": "wp3"})
    ba.execute_through_bridge(
        "synapse_solaris_shotsetup_karma_xpu", MagicMock(), command
    )

    assert len(recorder.ops) == 1
    assert recorder.ops[0].kwargs["touches_disk"] is True
