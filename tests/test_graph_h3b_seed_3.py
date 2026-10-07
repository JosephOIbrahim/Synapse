"""F05: a shader parm that does not exist must be reported.

create_material's _apply_shader_parm used to drop every value behind
``if p:`` when the caller-chosen shader_type lacked the mtlxstandard_surface
parm names. Hou-free.
"""
import contextlib
from types import SimpleNamespace

from synapse.server import handlers_material as hm
from synapse.server import main_thread


class _Shader:
    def parm(self, name):
        return None

    def path(self):
        return "/stage/mat/mat_shader"


class _Matlib:
    def setInput(self, *a):
        pass

    def moveToGoodPosition(self):
        pass

    def parm(self, name):
        return None

    def cook(self, force=False):
        pass

    def createNode(self, type_name, name):
        return _Shader()

    def path(self):
        return "/stage/mat"


class _Parent:
    def createNode(self, type_name, name):
        return _Matlib()


class _Node:
    def parent(self):
        return _Parent()


class _Handler(hm.MaterialHandlerMixin):
    def _resolve_lop_node(self, path):
        return _Node()


def test_missing_shader_parm_is_reported(monkeypatch):
    fake_hou = SimpleNamespace(
        undos=SimpleNamespace(group=lambda label: contextlib.nullcontext()),
    )
    monkeypatch.setattr(hm, "hou", fake_hou, raising=False)
    monkeypatch.setattr(hm, "HOU_AVAILABLE", True)
    monkeypatch.setattr(main_thread, "run_on_main", lambda fn, **kw: fn())
    monkeypatch.setattr(hm, "_query_material_usd_path", lambda m, n: "/materials/mat")
    monkeypatch.setattr(hm, "_wire_display", lambda m, n, s: {})

    result = _Handler()._handle_create_material({
        "name": "mat",
        "metalness": 0.5,
        "shader_type": "somethingelse",
    })

    assert result["parms_missed"] == ["metalness"]
