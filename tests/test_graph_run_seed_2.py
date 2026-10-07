"""F01: safe_render / render_progressively report failed settings writes.

forced_background must mean soho_foreground=0 was actually applied, and a
failed settings write in render_progressively must surface on every pass.
"""

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
elif not hasattr(sys.modules["hou"], "undos"):
    sys.modules["hou"].undos = MagicMock()

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")
if not hasattr(sys.modules["hdefereval"], "executeDeferred"):
    sys.modules["hdefereval"].executeDeferred = lambda fn: fn()

import pkgbootstrap  # noqa: E402  (tests/ is on sys.path under pytest)

_ROOT = Path(__file__).resolve().parent.parent / "python" / "synapse"
for _name, _path in [
    ("synapse", _ROOT),
    ("synapse.core", _ROOT / "core"),
    ("synapse.server", _ROOT / "server"),
    ("synapse.session", _ROOT / "session"),
]:
    pkgbootstrap.ensure_package(_name, _path)
for _name, _path in [
    ("synapse.core.protocol", _ROOT / "core" / "protocol.py"),
    ("synapse.core.aliases", _ROOT / "core" / "aliases.py"),
    ("synapse.server.handlers", _ROOT / "server" / "handlers.py"),
]:
    pkgbootstrap.load_module(_name, _path)

handlers_mod = sys.modules["synapse.server.handlers"]
if not hasattr(handlers_mod.hou, "undos"):
    handlers_mod.hou.undos = MagicMock()


def _handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    h._handle_get_stage_info = MagicMock(return_value={"cameras": ["/cameras/cam1"]})
    h._handle_render = MagicMock(return_value={"image_path": "/tmp/render.exr"})
    return h


def test_safe_render_failed_background_write_is_not_reported_forced():
    h = _handler()
    h._handle_render_settings = MagicMock(side_effect=ValueError("no such parm"))
    result = h._handle_safe_render({"rop_path": "/out/karma", "width": 1920, "height": 1080})
    assert result["forced_background"] is False
    assert "no such parm" in result["background_error"]


def test_safe_render_without_rop_is_not_reported_forced():
    h = _handler()
    result = h._handle_safe_render({"width": 1920, "height": 1080})
    assert result["forced_background"] is False
    assert "background_error" not in result


def test_safe_render_successful_write_is_reported_forced():
    h = _handler()
    h._handle_render_settings = MagicMock(return_value={})
    result = h._handle_safe_render({"rop_path": "/out/karma", "width": 1920, "height": 1080})
    assert result["forced_background"] is True
    assert "background_error" not in result


def test_render_progressively_surfaces_failed_settings_write():
    h = _handler()
    h._handle_render_settings = MagicMock(side_effect=PermissionError("locked"))
    h._handle_validate_frame = MagicMock(return_value={"valid": True})
    result = h._handle_render_progressively({"rop_path": "/out/karma"})
    assert result["passes"]
    for p in result["passes"]:
        assert "locked" in p["settings_error"]
