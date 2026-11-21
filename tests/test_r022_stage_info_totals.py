"""R-022 (OBSERVER-6): get_stage_info aggregates are whole-stage facts.

Predicate: on a 5,000-prim stage with a light at prim 4,900,
``houdini_stage_info`` returns it in ``lights`` (or ``lights_truncated`` with
the count), and no field claimed as a total is the inspected prefix length.

Before this repair the handler stopped traversing the stage as soon as the
returned ``prims`` list reached ``limit`` (default 500). Every aggregate --
cameras, lights, ``renderable_prims``, unassigned materials, unresolved
references -- therefore described only the first ``limit`` prims, and
``prim_count`` claimed to be a total while being the prefix length. A
5,000-prim stage with its only light at prim 4,900 reported no lights at all.

These headless tests fake ``hou`` and ``pxr`` (the vendored SDK is inactive on
CPython 3.14) and run the handler's main-thread callback inline, matching the
test_r008_usd_readback.py idiom.
"""

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from synapse.server import handlers_usd as husd
from synapse.server.handlers import SynapseHandler


# ---------------------------------------------------------------------------
# Fake USD surface
# ---------------------------------------------------------------------------

_SCHEMA_CAMERA = SimpleNamespace(_r022_name="Camera")
_SCHEMA_GPRIM = SimpleNamespace(_r022_name="Gprim")
_SCHEMA_LIGHT_API = SimpleNamespace(_r022_name="LightAPI")


class _FakePath:
    def __init__(self, path):
        self._path = path

    def __str__(self):
        return self._path


class _FakePrim:
    """Minimal USD prim: path, type name, schema membership, material bound."""

    def __init__(self, path, type_name, gprim=False, light=False,
                 camera=False, bound=True):
        self._path = path
        self._type = type_name
        self._gprim = gprim
        self._light = light
        self._camera = camera
        self._bound = bound

    def GetPath(self):
        return _FakePath(self._path)

    def GetTypeName(self):
        return self._type

    def IsA(self, schema):
        name = getattr(schema, "_r022_name", "")
        if name == "Camera":
            return self._camera
        if name == "Gprim":
            return self._gprim
        if name == "LightAPI":
            return self._light
        return False

    def HasAuthoredReferences(self):
        return False


class _FakeBindingAPI:
    def __init__(self, prim):
        self._prim = prim

    def ComputeBoundMaterial(self):
        return (object(), None) if self._prim._bound else (None, None)


class _FakeStage:
    def __init__(self, prims):
        self._prims = prims

    def Traverse(self):
        return iter(self._prims)


class _FakeNode:
    def __init__(self, stage, path="/stage/lop1"):
        self._stage = stage
        self._path = path

    def stage(self):
        return self._stage

    def path(self):
        return self._path


def _fake_pxr_modules():
    geom = SimpleNamespace(Camera=_SCHEMA_CAMERA, Gprim=_SCHEMA_GPRIM)
    lux = SimpleNamespace(LightAPI=_SCHEMA_LIGHT_API)
    shade = SimpleNamespace(MaterialBindingAPI=_FakeBindingAPI)
    pxr = ModuleType("pxr")
    pxr.UsdGeom = geom
    pxr.UsdLux = lux
    pxr.UsdShade = shade
    return {
        "pxr": pxr,
        "pxr.UsdGeom": geom,
        "pxr.UsdLux": lux,
        "pxr.UsdShade": shade,
    }


@pytest.fixture()
def wired(monkeypatch):
    """Install fake hou/pxr and an inline run_on_main; return a handler factory."""
    nodes = {}

    def install(stage):
        node = _FakeNode(stage)
        nodes["node"] = node
        fake_hou = SimpleNamespace(
            node=lambda path: node,
            selectedNodes=lambda: [],
        )
        monkeypatch.setattr(husd, "hou", fake_hou)
        monkeypatch.setattr(husd, "HOU_AVAILABLE", True)
        mt = importlib.import_module("synapse.server.main_thread")
        monkeypatch.setattr(mt, "run_on_main", lambda fn, timeout=None, **kw: fn())
        for name, mod in _fake_pxr_modules().items():
            monkeypatch.setitem(sys.modules, name, mod)
        return SynapseHandler()

    return install


# ---------------------------------------------------------------------------
# Predicate
# ---------------------------------------------------------------------------

def test_light_at_prim_4900_is_found_beyond_the_inspected_prefix(wired):
    """5,000-prim stage, only light at index 4,900, limit 10: light is reported."""
    prims = [_FakePrim("/world", "Xform")]
    for i in range(1, 5000):
        prims.append(_FakePrim("/world/mesh_%d" % i, "Mesh", gprim=True))
    prims[4900] = _FakePrim("/lights/key", "DistantLight", light=True)

    handler = wired(_FakeStage(prims))
    result = handler._handle_get_stage_info({"node": "/stage/lop1", "limit": 10})

    # The returned prim list is the inspected prefix, honestly named.
    assert result["inspected_prim_count"] == 10
    assert len(result["prims"]) == 10
    assert result["truncated"] is True

    # Totals are whole-stage counts, not the prefix length.
    assert result["prim_total"] == 5000
    assert result["prim_count"] == 5000
    assert result["prim_count"] != result["inspected_prim_count"]
    assert result["renderable_prims"] == 4998  # the Xform and the light are not Gprims

    # The light at prim 4,900 is found despite the 10-prim returned list.
    assert result["lights"] == ["/lights/key"]
    assert result["lights_total"] == 1
    assert result["lights_omitted"] == 0
    assert result["lights_truncated"] is False

    # The applied bound is exposed so a caller knows the list was bounded.
    assert result["limit"] == 10


# ---------------------------------------------------------------------------
# Per-list omitted counts
# ---------------------------------------------------------------------------

def test_bounded_lists_report_total_omitted_and_truncated(wired):
    """30 lights with limit 5: 5 returned, 25 counted as omitted."""
    prims = [
        _FakePrim("/lights/light_%02d" % i, "SphereLight", light=True)
        for i in range(30)
    ]

    handler = wired(_FakeStage(prims))
    result = handler._handle_get_stage_info({"node": "/stage/lop1", "limit": 5})

    assert len(result["lights"]) == 5
    assert result["lights_total"] == 30
    assert result["lights_omitted"] == 25
    assert result["lights_truncated"] is True

    assert result["prim_total"] == 30
    assert result["inspected_prim_count"] == 5
    assert result["truncated"] is True


def test_small_stage_totals_are_honest_and_untruncated(wired):
    """Under the cap, totals equal the returned lengths and nothing is omitted."""
    prims = [
        _FakePrim("/world", "Xform"),
        _FakePrim("/world/mesh", "Mesh", gprim=True),
        _FakePrim("/world/unbound", "Mesh", gprim=True, bound=False),
        _FakePrim("/cameras/cam", "Camera", camera=True),
        _FakePrim("/lights/key", "DomeLight", light=True),
    ]

    handler = wired(_FakeStage(prims))
    result = handler._handle_get_stage_info({"node": "/stage/lop1"})

    assert result["prim_total"] == 5
    assert result["prim_count"] == 5
    assert result["inspected_prim_count"] == 5
    assert result["truncated"] is False
    assert result["limit"] == 500  # exposed default

    assert result["cameras"] == ["/cameras/cam"]
    assert result["cameras_total"] == 1
    assert result["cameras_omitted"] == 0
    assert result["cameras_truncated"] is False

    assert result["lights"] == ["/lights/key"]
    assert result["lights_total"] == 1
    assert result["lights_omitted"] == 0

    assert result["renderable_prims"] == 2
    assert result["unassigned_material_prims"] == ["/world/unbound"]
    assert result["unassigned_material_prims_total"] == 1
    assert result["unassigned_material_prims_omitted"] == 0
    assert result["unassigned_material_prims_truncated"] is False

    assert result["unresolved_references"] == []
    assert result["unresolved_references_total"] == 0
    assert result["unresolved_references_omitted"] == 0


# ---------------------------------------------------------------------------
# Registry half: the bound is exposed and forwarded over MCP
# ---------------------------------------------------------------------------

def test_tool_registry_exposes_and_forwards_limit():
    from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON

    cmd, builder = TOOL_DISPATCH["houdini_stage_info"]
    assert cmd == "get_stage_info"
    assert builder({"node": "/stage/lop1", "limit": 10}) == {
        "node": "/stage/lop1",
        "limit": 10,
    }

    schema = TOOL_JSON["houdini_stage_info"]["inputSchema"]
    assert "limit" in schema["properties"]
    assert schema["properties"]["limit"]["type"] == "integer"
