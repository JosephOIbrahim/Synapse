"""C11 (CTO Remediation Mile 3.5) — render blocking IO moved off the main thread.

Before C11, _render_on_main ran the up-to-15s output-file poll (time.sleep loop)
and the iconvert subprocess INSIDE the executeInMainThreadWithResult closure —
freezing Houdini's UI and the whole run_on_main pipeline for the flush window on
every render. Now the closure ends right after node.render() (+ $HFS resolve);
poll + iconvert run on the WS handler thread, and the flipbook fallback is a
second, conditional main-thread hop.

The pin: drive _handle_render with an instrumented fake hdefereval and assert
NO time.sleep happens while a main-thread closure is executing.
"""

import contextlib
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

# Established handler-test convention: fakes before importing handlers.
_mock_hou = ModuleType("hou")
_mock_hou.ui = MagicMock()
_mock_hou.text = MagicMock()
_mock_hou.frame = MagicMock(return_value=1)
_hde = ModuleType("hdefereval")
_hde.executeInMainThreadWithResult = staticmethod(lambda fn, *a, **k: fn(*a, **k))
sys.modules.setdefault("hou", _mock_hou)
sys.modules.setdefault("hdefereval", _hde)

from synapse.server.handlers import SynapseHandler  # noqa: E402


def test_no_sleep_inside_main_thread_closure(tmp_path, monkeypatch):
    from synapse.server import handlers_render as hr

    # Fake hou: a ROP whose render() "writes" the output file immediately.
    out_file = tmp_path / "render_0001.exr"

    class _Parm:
        def __init__(self, v=""):
            self._v = v
        def eval(self):
            return self._v
        def set(self, v):
            self._v = v

    picture = _Parm(str(tmp_path / "render_$F4.exr"))

    class _Rop:
        def type(self):
            return SimpleNamespace(name=lambda: "karma")
        def parm(self, name):
            return picture if name == "picture" else None
        def render(self, frame_range=None, verbose=False):
            out_file.write_bytes(b"EXR")
        def path(self):
            return "/out/karma1"

    fake_hou = SimpleNamespace(
        node=lambda p: _Rop(),
        frame=lambda: 1,
        text=SimpleNamespace(expandString=lambda s: str(tmp_path)),
        ui=MagicMock(),
        paneTabType=SimpleNamespace(SceneViewer="SceneViewer"),
        setFrame=lambda f: None,
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )

    # Instrumented fake hdefereval: flags while a main-thread closure runs.
    in_main = {"active": False}
    fake_hde = ModuleType("hdefereval")

    def _exec(fn, *a, **k):
        in_main["active"] = True
        try:
            return fn(*a, **k)
        finally:
            in_main["active"] = False
    fake_hde.executeInMainThreadWithResult = _exec

    # time.sleep spy in the RENDER module: fail loud if called on "main thread".
    sleeps = {"on_main": 0, "off_main": 0}
    real_sleep = time.sleep

    def spy_sleep(s):
        if in_main["active"]:
            sleeps["on_main"] += 1
        else:
            sleeps["off_main"] += 1
        real_sleep(0)  # don't actually wait in the test

    g = SynapseHandler._handle_render.__globals__   # handlers_render namespace
    monkeypatch.setitem(g, "hou", fake_hou)
    monkeypatch.setitem(g, "HOU_AVAILABLE", True)
    monkeypatch.setitem(sys.modules, "hdefereval", fake_hde)
    monkeypatch.setattr(hr.time, "sleep", spy_sleep)

    h = SynapseHandler()
    result = h._handle_render({"node": "/out/karma1", "frame": 1})

    assert result["image_path"]                       # render path resolved
    assert sleeps["on_main"] == 0, "blocking poll ran inside the main-thread closure"
