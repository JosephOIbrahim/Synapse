"""Tests for the Solaris compose tools (solaris_compose_tools.py).

These tools are hou-orchestration -- the meaningful gate is the LIVE [REAL]
verification on H21.0.671 (recorded per-mile in the commit history). This is a
thin CI net: import + the department-order invariant + the no-hou guard.

A minimal hou stub is installed in sys.modules so the package import chain
doesn't ImportError under CI (no Houdini). Monkeypatch rebinds auto-restore.
"""

import sys
import types

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = types.ModuleType("hou")

from synapse.server import solaris_compose_tools as t  # noqa: E402
from synapse.server import solaris_compose as sc  # noqa: E402


def test_department_order_render_strongest_first():
    # Conceptual strongest-first; the sublayer LOP is filled weakest-first
    # (verified: sublayer LOP composes filepathN as strongest).
    assert t.DEPARTMENT_LAYERS_STRONGEST_FIRST == [
        "render", "fx", "lighting", "animation", "layout",
    ]


def test_build_requires_hou(monkeypatch):
    monkeypatch.setattr(t, "HOU_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        t.build_karma_xpu_shot(object(), shot="x")


def test_set_helper_skips_locked(monkeypatch):
    from unittest.mock import MagicMock
    monkeypatch.setattr(t, "HOU_AVAILABLE", True, raising=False)
    node = MagicMock()
    locked = MagicMock()
    locked.isLocked.return_value = True
    node.parm.return_value = locked
    assert t._set(node, "resolution2", 1920) is False  # locked -> skipped
    locked.set.assert_not_called()


def test_set_helper_missing_parm():
    from unittest.mock import MagicMock
    node = MagicMock()
    node.parm.return_value = None
    assert t._set(node, "no_such_parm", 1) is False


# -- Mile 3: matlib_bind target expansion + guards --------------------------

class _FakePrim:
    def __init__(self, path, type_name="Mesh"):
        self._path = path
        self._type = type_name

    def GetPath(self):
        return self._path

    def GetTypeName(self):
        return self._type

    def IsValid(self):
        return True


class _FakeStage:
    def __init__(self, prims):
        self._prims = {p._path: p for p in prims}

    def Traverse(self):
        return list(self._prims.values())

    def GetPrimAtPath(self, p):
        return self._prims.get(p)


def test_expand_targets_exact():
    st = _FakeStage([_FakePrim("/geo/a"), _FakePrim("/geo/b")])
    assert t._expand_targets(st, "/geo/a") == ["/geo/a"]


def test_expand_targets_missing_exact_returns_empty():
    st = _FakeStage([_FakePrim("/geo/a")])
    assert t._expand_targets(st, "/nope") == []


def test_expand_targets_glob():
    st = _FakeStage([_FakePrim("/geo/a"), _FakePrim("/geo/b"), _FakePrim("/other/c")])
    assert sorted(t._expand_targets(st, "/geo/*")) == ["/geo/a", "/geo/b"]


def test_expand_targets_type_expression():
    st = _FakeStage([_FakePrim("/geo/a", "Mesh"), _FakePrim("/lights/l", "SphereLight")])
    assert t._expand_targets(st, "//Mesh") == ["/geo/a"]


def test_bind_material_requires_hou(monkeypatch):
    monkeypatch.setattr(t, "HOU_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        t.bind_material(object(), "/materials/m", "/geo/x")


def test_ensure_mtlx_material_requires_hou(monkeypatch):
    monkeypatch.setattr(t, "HOU_AVAILABLE", False, raising=False)
    with pytest.raises(sc.ComposeError):
        t.ensure_mtlx_material(object(), "m")


# -- Mile 4: assess_render_ready clause logic (real in-memory USD; skips w/o pxr) --

def _build_render_stage(tmp_path, *, with_rs=True, camera=True, bind_mesh=True,
                        product=True, product_dir=None, aov=True, engine="xpu",
                        osl=False, volume=False):
    pytest.importorskip("pxr")
    from pxr import Usd, UsdShade, UsdRender, Sdf
    s = Usd.Stage.CreateInMemory()
    s.DefinePrim("/cam", "Camera")
    mesh = s.DefinePrim("/geo/m", "Mesh")
    mat = UsdShade.Material.Define(s, "/mats/red")
    if bind_mesh:
        UsdShade.MaterialBindingAPI.Apply(mesh).Bind(mat)
    if osl:
        UsdShade.Shader.Define(s, "/mats/red/osl_surf").CreateIdAttr("osl_oslsurface")
    if volume:
        s.DefinePrim("/vol", "Volume")
    if with_rs:
        rs = s.DefinePrim("/Render/rs", "RenderSettings")
        if camera:
            UsdRender.Settings(rs).CreateCameraRel().SetTargets(["/cam"])
        if engine:
            rs.CreateAttribute("karma:engine", Sdf.ValueTypeNames.Token).Set(engine)
        if product:
            rp = s.DefinePrim("/Render/Products/beauty", "RenderProduct")
            pdir = product_dir if product_dir is not None else str(tmp_path)
            UsdRender.Product(rp).CreateProductNameAttr(pdir + "/out.exr")
        if aov:
            s.DefinePrim("/Render/rs/beauty", "RenderVar")
    return s


def test_render_ready_good(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path))
    assert rep["ready"] is True, rep
    assert all(v in ("pass", "n/a") for v in rep["clauses"].values()), rep["clauses"]


def test_render_ready_missing_rendersettings(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, with_rs=False))
    assert rep["ready"] is False
    assert rep["clauses"]["rendersettings"] == "fail"
    assert rep["clauses"]["camera"] == "fail"


def test_render_ready_unresolved_camera(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, camera=False))
    assert rep["clauses"]["camera"] == "fail"


def test_render_ready_unbound_mesh(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, bind_mesh=False))
    assert rep["clauses"]["materials_bound"] == "fail"
    assert "/geo/m" in rep["details"]["materials_bound"]["unbound"]


def test_render_ready_bad_product_dir(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, product_dir="/no/such/synapse/dir"))
    assert rep["clauses"]["output_path"] == "fail"


def test_render_ready_no_aovs(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, aov=False))
    assert rep["clauses"]["aovs"] == "fail"


def test_render_ready_xpu_osl_incompatible(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, engine="xpu", osl=True))
    assert rep["clauses"]["xpu_compatible"] == "fail"


def test_render_ready_cpu_skips_xpu_check(tmp_path):
    rep = t._assess_stage(_build_render_stage(tmp_path, engine="cpu", osl=True))
    assert rep["clauses"]["xpu_compatible"] == "n/a"
