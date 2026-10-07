"""F01: COP scaffold handlers report dropped parm writes and unresolved inputs.

bake_textures (resx/resy), stamp_scatter (seed/copies/count + stamp_source)
and pixel_sort (input_node) guarded each write or wire with ``is not None``
and returned success with nothing saying it missed. They now return
``parms_missed`` / ``inputs_missed``.
"""

import contextlib
import sys
import types
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
if "hdefereval" not in sys.modules:
    _hd = types.ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    _hd.executeDeferred = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

import synapse.server.handlers_cops as cops_mod  # noqa: E402
import synapse.server.main_thread as main_thread_mod  # noqa: E402


def _bare_node(path):
    node = MagicMock()
    node.path.return_value = path
    node.parm.return_value = None
    node.type.return_value.name.return_value = "vopcop2gen"
    return node


@pytest.fixture
def world(monkeypatch):
    parent = MagicMock()
    parent.path.return_value = "/img/c"
    created = []

    def _create(_parent, _type, name=None):
        node = _bare_node(f"/img/c/{name}")
        created.append(node)
        return node

    parent.createNode.side_effect = lambda t, n=None: _create(parent, t, n)
    fake_hou = types.SimpleNamespace(
        node=lambda p: parent if p == "/img/c" else None,
        undos=types.SimpleNamespace(
            group=lambda *_a, **_k: contextlib.nullcontext(),
            performUndo=lambda: None,
        ),
    )
    monkeypatch.setattr(cops_mod, "hou", fake_hou, raising=False)
    monkeypatch.setattr(cops_mod, "HOU_AVAILABLE", True)
    monkeypatch.setattr(cops_mod, "_create_cop_node", _create)
    monkeypatch.setattr(cops_mod, "gated_set", lambda *_a, **_k: {})
    monkeypatch.setattr(main_thread_mod, "run_on_main", lambda fn, **_k: fn())
    return cops_mod.CopsHandlerMixin(), created


def test_bake_textures_reports_missing_resolution_parms(world):
    mixin, _ = world
    result = mixin._handle_cops_bake_textures(
        {"parent": "/img/c", "map_types": ["normal"], "resolution": [512, 512]}
    )
    assert result["parms_missed"] == ["vopcop2gen.resx", "vopcop2gen.resy"]


def test_stamp_scatter_reports_missing_parms_and_input(world):
    mixin, created = world
    result = mixin._handle_cops_stamp_scatter(
        {"parent": "/img/c", "stamp_source": "/img/c/missing"}
    )
    assert result["parms_missed"] == ["vopcop2gen.seed", "vopcop2gen.copies|count"]
    assert result["inputs_missed"] == ["/img/c/missing"]
    created[0].setInput.assert_not_called()


def test_pixel_sort_reports_missing_input(world):
    mixin, created = world
    result = mixin._handle_cops_pixel_sort(
        {"parent": "/img/c", "input_node": "/img/missing"}
    )
    assert result["inputs_missed"] == ["/img/missing"]
    created[0].setInput.assert_not_called()
