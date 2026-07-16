"""Tests for Copernicus (COPs) handlers.

Tests all 21 COP handlers across 4 phases:
  - Foundation: create_network, create_copnet, create_node, connect, set_opencl, read_layer_info
  - Pipeline: to_materialx, composite_aovs, analyze_render, slap_comp
  - Procedural: create_solver, procedural_texture, growth_propagation,
                reaction_diffusion, pixel_sort, stylize
  - Advanced: wetmap, bake_textures, temporal_analysis, stamp_scatter, batch_cook

Mock-based -- no Houdini required.
"""

import importlib.util
import logging
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, call, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: hou stub
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=1.0)
    _hou.setFrame = MagicMock()
    _hou.fps = MagicMock(return_value=24.0)
    _hou.hipFile = MagicMock()
    _hou.hipFile.name = MagicMock(return_value="/tmp/test.hip")
    _hou.playbar = MagicMock()
    _hou.playbar.frameRange = MagicMock(return_value=(1, 100))
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    # executeDeferred: call fn immediately (run_on_main uses this + threading.Event)
    _hdefereval.executeDeferred = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]
    if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
        _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    if not hasattr(_hdefereval, "executeDeferred"):
        _hdefereval.executeDeferred = lambda fn, *args, **kwargs: fn(*args, **kwargs)

# Bootstrap synapse package modules
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
    ("synapse.routing", _base / "routing"),
    ("synapse.memory", _base / "memory"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _base / "core" / "protocol.py"),
    ("synapse.core.aliases", _base / "core" / "aliases.py"),
    ("synapse.core.errors", _base / "core" / "errors.py"),
    ("synapse.server.handlers", _base / "server" / "handlers.py"),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]
protocol_mod = sys.modules["synapse.core.protocol"]

# Get the hou reference from handlers_cops.py
import synapse.server.handlers_cops as _hc  # noqa: E402  (bootstrapped above)
_cops_mod = sys.modules.get("synapse.server.handlers_cops")
_handlers_hou = _cops_mod.hou if _cops_mod else handlers_mod.hou

if not hasattr(_handlers_hou, "node"):
    _handlers_hou.node = MagicMock()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class _MockCategory:
    def __init__(self, name="Cop2"):
        self._name = name
    def name(self):
        return self._name


class _MockNodeType:
    def __init__(self, name="blur", category="Cop2"):
        self._name = name
        self._cat = _MockCategory(category)
    def name(self):
        return self._name
    def category(self):
        return self._cat
    def maxNumInputs(self):
        return 4


def _make_cop_node(path="/obj/cop2net1/blur1", type_name="blur",
                   parms=None, errors=None, warnings=None):
    """Create a mock COP node."""
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name)
    node.moveToGoodPosition = MagicMock()
    node.setDisplayFlag = MagicMock()
    node.setInput = MagicMock()
    node.cook = MagicMock()
    node.errors.return_value = errors or []
    node.warnings.return_value = warnings or []
    node.children.return_value = []

    # Resolution methods
    node.xRes.return_value = 1024
    node.yRes.return_value = 1024
    node.planes.return_value = ["C", "A"]

    # Real H22 signature: hou.Cop2Node.depth(plane) REQUIRES a plane-name arg on
    # 22.0.368 -- a bare depth() TypeErrors. The mock enforces that so the handler
    # can no longer green-light a dead bare depth() call (W.1b sev-3).
    def _depth(*args):
        if not args:
            raise TypeError(
                "depth() missing 1 required positional argument: 'plane' "
                "(hou.Cop2Node.depth needs a plane name on 22.0.368)"
            )
        return "float32"
    node.depth.side_effect = _depth

    # Parm mock
    _parms = parms or {}
    def _parm(name):
        if name in _parms:
            p = MagicMock()
            p.eval.return_value = _parms[name]
            p.name.return_value = name
            return p
        return None
    node.parm = _parm
    node.parmTuple = MagicMock(return_value=None)

    return node


def _make_copernicus_node(path="/img/copnet1/ramp1", type_name="ramp",
                          wire_names=("ramp",), resolution=(1024, 1024),
                          storage="imageLayerStorageType.Float32", channels=3,
                          parms=None, errors=None, warnings=None):
    """Create a mock H22 Copernicus COP node (category ``Cop``).

    H22 REMOVED planes()/xRes()/yRes()/depth() from hou.CopNode (NWS-03) --
    the attrs are deleted so any leftover legacy-surface call raises
    AttributeError instead of silently returning mock data. Reads go through
    the verified replacement surface: cable() -> CopCable -> ImageLayer.
    """
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name, category="Cop")
    node.cook = MagicMock()
    node.errors.return_value = errors or []
    node.warnings.return_value = warnings or []

    del node.planes
    del node.xRes
    del node.yRes
    del node.depth

    layer = MagicMock()
    layer.bufferResolution.return_value = tuple(resolution) if resolution else None
    layer.channelCount.return_value = channels
    layer.storageType.return_value = storage

    cable = MagicMock()
    cable.wireNames.return_value = list(wire_names)
    cable.wireCount.return_value = len(wire_names)
    cable.layerByIndex.return_value = layer
    node.cable.return_value = cable

    _parms = parms or {}
    def _parm(name):
        if name in _parms:
            p = MagicMock()
            p.eval.return_value = _parms[name]
            p.name.return_value = name
            return p
        return None
    node.parm = _parm
    node.parmTuple = MagicMock(return_value=None)

    return node


def _make_network_node(path="/obj/cop2net1", children=None):
    """Create a mock COP2 network node."""
    net = MagicMock()
    net.path.return_value = path
    net.name.return_value = path.rsplit("/", 1)[-1]
    net.type.return_value = _MockNodeType("cop2net", "Object")
    net.moveToGoodPosition = MagicMock()
    net.children.return_value = children or []

    # createNode returns a mock child
    def _create_node(node_type, name=None):
        child_name = name or node_type
        child = _make_cop_node(f"{path}/{child_name}", node_type)
        return child
    net.createNode = MagicMock(side_effect=_create_node)

    return net


def _make_drifted_copernicus_node(path="/img/copnet1/drift1", type_name="ramp"):
    """A Copernicus node whose H22 replacement surface has DRIFTED further.

    ``cable().wireNames()`` has vanished (raises AttributeError) -- the exact
    silent-degrade class W.1 fixed for ``planes()``. wireCount/layer still resolve,
    so resolution is still readable: this proves the plane read degrades LOUD (drift
    entry + warn) while the rest of the read survives.
    """
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name, category="Cop")
    node.cook = MagicMock()
    node.errors.return_value = []
    node.warnings.return_value = []

    del node.planes
    del node.xRes
    del node.yRes
    del node.depth

    layer = MagicMock()
    layer.bufferResolution.return_value = (1024, 1024)
    layer.channelCount.return_value = 3
    layer.storageType.return_value = "imageLayerStorageType.Float32"

    cable = MagicMock()
    del cable.wireNames  # DRIFT: the H22 plane-name reader vanished on this build
    cable.wireCount.return_value = 1
    cable.layerByIndex.return_value = layer
    node.cable.return_value = cable

    node.parm = lambda name: None
    node.parmTuple = MagicMock(return_value=None)
    return node


# The six Copernicus replacement-surface symbols _copernicus_image_info reads, each
# mapped (by owner) into the cable() -> CopCable -> ImageLayer chain. Deleting any ONE
# makes exactly that deref raise AttributeError while every upstream read still
# resolves -> exactly one drift entry. cable/wireCount/bufferResolution/storageType
# were the four sites that (pre-repair) were passed to _read_or_drift as BOUND METHODS,
# so their AttributeError fired at argument evaluation -- outside the guard -- and
# crashed the whole command instead of drifting. Wrapping all six in lambdas fixed it;
# _make_symbol_drifted_copernicus_node + the per-symbol test below now pin every site.
_COP_DRIFT_SYMBOLS = (
    "hou.CopNode.cable",
    "hou.CopCable.wireNames",
    "hou.CopCable.wireCount",
    "hou.CopCable.layerByIndex",
    "hou.ImageLayer.bufferResolution",
    "hou.ImageLayer.storageType",
)


def _make_symbol_drifted_copernicus_node(drift_symbol, path="/img/copnet1/symdrift"):
    """A Copernicus node healthy on every replacement-surface symbol EXCEPT one.

    ``drift_symbol`` (a ``_COP_DRIFT_SYMBOLS`` entry) is deleted from wherever it lives
    in the cable() -> CopCable -> ImageLayer chain, so that single deref raises
    AttributeError and everything upstream of it still resolves.
    """
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType("ramp", category="Cop")
    node.cook = MagicMock()
    node.errors.return_value = []
    node.warnings.return_value = []

    del node.planes
    del node.xRes
    del node.yRes
    del node.depth

    layer = MagicMock()
    layer.bufferResolution.return_value = (1024, 1024)
    layer.channelCount.return_value = 3
    layer.storageType.return_value = "imageLayerStorageType.Float32"

    cable = MagicMock()
    cable.wireNames.return_value = ["ramp"]
    cable.wireCount.return_value = 1
    cable.layerByIndex.return_value = layer
    node.cable.return_value = cable

    node.parm = lambda name: None
    node.parmTuple = MagicMock(return_value=None)

    # Delete exactly the drifted method from its owner so that deref raises.
    _owner = {
        "hou.CopNode.cable": node,
        "hou.CopCable.wireNames": cable,
        "hou.CopCable.wireCount": cable,
        "hou.CopCable.layerByIndex": cable,
        "hou.ImageLayer.bufferResolution": layer,
        "hou.ImageLayer.storageType": layer,
    }[drift_symbol]
    delattr(_owner, drift_symbol.rsplit(".", 1)[-1])
    return node


# Sentinel classes standing in for hou.Cop2Node / hou.CopNode. The test hou stub is
# a bare ModuleType with no such classes, so _uses_legacy_cop2_surface's isinstance
# branches are normally skipped -- planting these exercises them (W.1b task 3).
class _Cop2NodeSentinel:
    pass


class _CopNodeSentinel:
    pass


def _make_parent_node(path="/obj"):
    """Create a mock parent node that can create cop2net children."""
    parent = MagicMock()
    parent.path.return_value = path

    def _create_node(node_type, name=None):
        child_name = name or node_type
        if node_type == "cop2net":
            return _make_network_node(f"{path}/{child_name}")
        return _make_cop_node(f"{path}/{child_name}", node_type)
    parent.createNode = MagicMock(side_effect=_create_node)

    return parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    """Create a SynapseHandler instance."""
    return handlers_mod.SynapseHandler()


# ---------------------------------------------------------------------------
# Phase 1: Foundation Tests
# ---------------------------------------------------------------------------

class TestCopsCreateNetwork:
    def test_create_network_basic(self, handler):
        parent = _make_parent_node("/obj")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_network",
                id="test-1",
                payload={"parent": "/obj", "name": "my_cops"},
            ))
        assert result.success
        assert "network_path" in result.data

    def test_create_network_default_name(self, handler):
        parent = _make_parent_node("/obj")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_network",
                id="test-2",
                payload={},
            ))
        assert result.success

    def test_create_network_with_initial_nodes(self, handler):
        parent = _make_parent_node("/obj")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_network",
                id="test-3",
                payload={"parent": "/obj", "initial_nodes": ["blur", "composite"]},
            ))
        assert result.success
        assert "initial_nodes" in result.data

    def test_create_network_bad_parent(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_network",
                id="test-4",
                payload={"parent": "/nonexistent"},
            ))
        assert not result.success
        assert "Couldn't find" in result.error


class TestCopsCreateNode:
    def test_create_node_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_node",
                id="test-5",
                payload={"parent": "/obj/cop2net1", "type": "blur"},
            ))
        assert result.success
        assert result.data["type"] == "blur"

    def test_create_node_with_name(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_node",
                id="test-6",
                payload={"parent": "/obj/cop2net1", "type": "blur", "name": "my_blur"},
            ))
        assert result.success

    def test_create_node_missing_type(self, handler):
        result = handler.handle(handlers_mod.SynapseCommand(
            type="cops_create_node",
            id="test-7",
            payload={"parent": "/obj/cop2net1"},
        ))
        assert not result.success

    def test_create_node_bad_parent(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_node",
                id="test-8",
                payload={"parent": "/nonexistent", "type": "blur"},
            ))
        assert not result.success


class TestCopsConnect:
    def test_connect_basic(self, handler):
        src = _make_cop_node("/obj/cop2net1/blur1", "blur")
        tgt = _make_cop_node("/obj/cop2net1/composite1", "composite")

        def _node_router(path):
            if path == "/obj/cop2net1/blur1":
                return src
            if path == "/obj/cop2net1/composite1":
                return tgt
            return None

        with patch.object(_handlers_hou, "node", side_effect=_node_router):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_connect",
                id="test-9",
                payload={
                    "source": "/obj/cop2net1/blur1",
                    "target": "/obj/cop2net1/composite1",
                },
            ))
        assert result.success
        assert result.data["connected"] is True

    def test_connect_bad_source(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_connect",
                id="test-10",
                payload={"source": "/bad", "target": "/obj/cop2net1/blur1"},
            ))
        assert not result.success


class TestCopsSetOpencl:
    def test_set_opencl_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/opencl1", "opencl",
                              parms={"kernelcode": ""})
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_set_opencl",
                id="test-11",
                payload={
                    "node": "/obj/cop2net1/opencl1",
                    "kernel_code": "float val = @P.x;",
                },
            ))
        assert result.success
        assert result.data["kernel_set"] is True

    def test_set_opencl_bad_node(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_set_opencl",
                id="test-12",
                payload={"node": "/nonexistent", "kernel_code": "x"},
            ))
        assert not result.success

    def test_set_opencl_no_parm(self, handler):
        node = _make_cop_node("/obj/cop2net1/bad1", "null", parms={})
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_set_opencl",
                id="test-13",
                payload={"node": "/obj/cop2net1/bad1", "kernel_code": "x"},
            ))
        assert not result.success


class TestCopsReadLayerInfo:
    def test_read_layer_info_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_read_layer_info",
                id="test-14",
                payload={"node": "/obj/cop2net1/file1"},
            ))
        assert result.success
        assert result.data["resolution"] == [1024, 1024]
        assert "planes" in result.data

    def test_read_layer_info_bad_node(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_read_layer_info",
                id="test-15",
                payload={"node": "/nonexistent"},
            ))
        assert not result.success

    def test_read_layer_info_legacy_cop2_path_preserved(self, handler):
        """Legacy Cop2 nodes (category Cop2) still read via planes()/xRes()/depth()."""
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_read_layer_info",
                id="test-15b",
                payload={"node": "/obj/cop2net1/file1"},
            ))
        assert result.success
        assert result.data["planes"] == ["C", "A"]
        assert result.data["resolution"] == [1024, 1024]
        assert result.data["data_type"] == "float32"

    def test_read_layer_info_copernicus_surface(self, handler):
        """H22 Copernicus nodes read via cable()/ImageLayer -- planes truthfully
        populated from wire names instead of silently degrading to []."""
        node = _make_copernicus_node("/img/copnet1/ramp1", "ramp",
                                     wire_names=("ramp",))
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_read_layer_info",
                id="test-15c",
                payload={"node": "/img/copnet1/ramp1"},
            ))
        assert result.success
        assert result.data["planes"] == ["ramp"]
        assert result.data["resolution"] == [1024, 1024]
        assert result.data["data_type"] == "imageLayerStorageType.Float32"

    def test_read_layer_info_copernicus_envelope_matches_legacy(self, handler):
        """Response envelope shape is identical across both surfaces (same keys)."""
        legacy = _make_cop_node("/obj/cop2net1/file1", "file")
        modern = _make_copernicus_node("/img/copnet1/ramp1", "ramp")
        results = {}
        for name, node in [("legacy", legacy), ("modern", modern)]:
            with patch.object(_handlers_hou, "node", return_value=node):
                results[name] = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_read_layer_info",
                    id=f"test-15d-{name}",
                    payload={"node": node.path()},
                ))
        assert results["legacy"].success and results["modern"].success
        assert set(results["legacy"].data.keys()) == set(results["modern"].data.keys())

    def test_read_layer_info_copernicus_empty_cable(self, handler):
        """Un-cooked/unloaded Copernicus node: zero wires -> honest empty planes,
        resolution falls back to resx/resy parms."""
        node = _make_copernicus_node("/img/copnet1/file1", "file",
                                     wire_names=(),
                                     parms={"resx": 512, "resy": 512})
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_read_layer_info",
                id="test-15e",
                payload={"node": "/img/copnet1/file1"},
            ))
        assert result.success
        assert result.data["planes"] == []
        assert result.data["resolution"] == [512, 512]


# ---------------------------------------------------------------------------
# Phase 2: Pipeline Integration Tests
# ---------------------------------------------------------------------------

class TestCopsToMaterialx:
    def test_to_materialx_basic(self, handler):
        cop = _make_cop_node("/obj/cop2net1/tex1", "vopcop2gen")
        mat = _make_cop_node("/stage/matlib/shader1", "mtlxstandard_surface",
                             parms={"base_color_texture": ""})

        def _node_router(path):
            if "tex1" in path:
                return cop
            if "shader1" in path:
                return mat
            return None

        with patch.object(_handlers_hou, "node", side_effect=_node_router):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_to_materialx",
                id="test-16",
                payload={
                    "cop_path": "/obj/cop2net1/tex1",
                    "material_node": "/stage/matlib/shader1",
                },
            ))
        assert result.success
        assert "op:" in result.data["op_path"]


class TestCopsCompositeAovs:
    def test_composite_aovs_basic(self, handler):
        parent = _make_parent_node("/obj")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_composite_aovs",
                id="test-17",
                payload={"exr_path": "/tmp/render.exr"},
            ))
        assert result.success
        assert "network_path" in result.data
        assert len(result.data["layers"]) == 3  # default: beauty, diffuse, specular


class TestCopsAnalyzeRender:
    def test_analyze_render_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-18",
                payload={"node": "/obj/cop2net1/file1"},
            ))
        assert result.success
        assert result.data["overall_quality"] == "pass"
        assert result.data["resolution"] == [1024, 1024]

    def test_analyze_render_with_errors(self, handler):
        node = _make_cop_node("/obj/cop2net1/bad1", "file",
                              errors=["Missing texture"])
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-19",
                payload={"node": "/obj/cop2net1/bad1"},
            ))
        assert result.success
        assert result.data["overall_quality"] == "fail"

    def test_analyze_render_legacy_planes_preserved(self, handler):
        """Legacy Cop2 nodes still report planes via planes()."""
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-19b",
                payload={"node": "/obj/cop2net1/file1"},
            ))
        assert result.success
        assert result.data["planes"] == ["C", "A"]
        assert result.data["pixel_count"] == 1024 * 1024

    def test_analyze_render_copernicus_surface(self, handler):
        """H22 Copernicus nodes: resolution/planes read via cable()/ImageLayer --
        report truthfully populated instead of resolution:None + planes:[]."""
        node = _make_copernicus_node("/img/copnet1/ramp1", "ramp",
                                     wire_names=("ramp",))
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-19c",
                payload={"node": "/img/copnet1/ramp1"},
            ))
        assert result.success
        assert result.data["overall_quality"] == "pass"
        assert result.data["resolution"] == [1024, 1024]
        assert result.data["pixel_count"] == 1024 * 1024
        assert result.data["planes"] == ["ramp"]

    def test_analyze_render_copernicus_empty_cable(self, handler):
        """Zero wires on a Copernicus node -> resolution None (preserved envelope),
        honest empty planes, no pixel_count key."""
        node = _make_copernicus_node("/img/copnet1/file1", "file", wire_names=())
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-19d",
                payload={"node": "/img/copnet1/file1"},
            ))
        assert result.success
        assert result.data["resolution"] is None
        assert result.data["planes"] == []
        assert "pixel_count" not in result.data


# Golden envelope key freezes (W.1b task 3): the exact key set each handler returns
# on a healthy node. Pins the response contract so a future silent addition/removal
# on EITHER the legacy or the Copernicus read path fails loud in CI.
_READ_LAYER_INFO_GOLDEN_KEYS = {
    "node", "type", "resolution", "data_type", "planes",
    "cook_status", "errors", "warnings",
}
_ANALYZE_RENDER_GOLDEN_KEYS = {
    "node", "checks_run", "issues", "overall_quality",
    "resolution", "pixel_count", "planes",
}


class TestCopsSurfaceGoldensAndDrift:
    """W.1b follow-ups: golden envelope keys, loud Copernicus API drift, and the
    isinstance branches of ``_uses_legacy_cop2_surface`` (normally skipped because
    the test hou stub has no Cop2Node/CopNode classes)."""

    def test_read_layer_info_golden_envelope_keys(self, handler):
        legacy = _make_cop_node("/obj/cop2net1/file1", "file")
        modern = _make_copernicus_node("/img/copnet1/ramp1", "ramp")
        for node in (legacy, modern):
            with patch.object(_handlers_hou, "node", return_value=node):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_read_layer_info",
                    id="test-w1b-rli-golden",
                    payload={"node": node.path()},
                ))
            assert result.success
            assert set(result.data.keys()) == _READ_LAYER_INFO_GOLDEN_KEYS

    def test_analyze_render_golden_envelope_keys(self, handler):
        legacy = _make_cop_node("/obj/cop2net1/file1", "file")
        modern = _make_copernicus_node("/img/copnet1/ramp1", "ramp")
        for node in (legacy, modern):
            with patch.object(_handlers_hou, "node", return_value=node):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_analyze_render",
                    id="test-w1b-ar-golden",
                    payload={"node": node.path()},
                ))
            assert result.success
            assert set(result.data.keys()) == _ANALYZE_RENDER_GOLDEN_KEYS

    def test_analyze_render_copernicus_drift_is_loud(self, handler):
        """A vanished replacement-surface symbol surfaces an api_drift issue and
        flips overall_quality -- it can no longer masquerade as a clean pass."""
        _hc._WARNED_COP_DRIFT.clear()
        node = _make_drifted_copernicus_node("/img/copnet1/drift_ar")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_analyze_render",
                id="test-w1b-ar-drift",
                payload={"node": node.path()},
            ))
        assert result.success
        drift = [i for i in result.data["issues"] if i.get("check") == "api_drift"]
        assert len(drift) == 1
        assert "wireNames" in drift[0]["symbol"]
        assert drift[0]["severity"] == "warning"
        assert result.data["overall_quality"] == "warning"
        # Plane read degraded honestly; unaffected reads still succeed.
        assert result.data["planes"] == []
        assert result.data["resolution"] == [1024, 1024]

    def test_read_layer_info_drift_surfaces_log_and_api_drift_key(self, handler, caplog):
        """read_layer_info has no issues[] channel, so drift surfaces TWO ways: the
        warn-once log AND an additive ``api_drift`` key. The key is present ONLY on
        drift, so the healthy-node golden envelope stays frozen -- but a persistently
        drifted node is never indistinguishable from an un-cooked one (the warn-once
        log alone goes silent after call #1)."""
        _hc._WARNED_COP_DRIFT.clear()
        node = _make_drifted_copernicus_node("/img/copnet1/drift_rli")
        with patch.object(_handlers_hou, "node", return_value=node):
            with caplog.at_level(logging.WARNING, logger="synapse.server.handlers_cops"):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_read_layer_info",
                    id="test-w1b-rli-drift",
                    payload={"node": node.path()},
                ))
        assert result.success
        assert "API drift" in caplog.text
        assert "wireNames" in caplog.text
        assert result.data["planes"] == []
        # Additive: golden keys PLUS the api_drift key on a drifted node.
        assert set(result.data.keys()) == _READ_LAYER_INFO_GOLDEN_KEYS | {"api_drift"}
        drift = result.data["api_drift"]
        assert [d["symbol"] for d in drift] == ["hou.CopCable.wireNames"]
        assert drift[0]["check"] == "api_drift"

    def test_cop_drift_entry_every_call_warn_once_per_symbol(self, caplog):
        """For EACH of the six replacement-surface symbols, a vanished method yields
        exactly one api_drift entry on EVERY call (callers always see it) and is
        warned exactly once per process. This genuinely exercises all six sites --
        cable/wireCount/bufferResolution/storageType used to raise an *uncaught*
        AttributeError at argument evaluation (bound methods) and crash the read;
        deleting any one now must degrade loud, never crash."""
        for symbol in _COP_DRIFT_SYMBOLS:
            _hc._WARNED_COP_DRIFT.clear()
            with caplog.at_level(logging.WARNING, logger="synapse.server.handlers_cops"):
                caplog.clear()
                # Call twice: drift entry emitted every call, warning logged once.
                _i1, drift1 = _hc._copernicus_image_info(
                    _make_symbol_drifted_copernicus_node(symbol, "/img/copnet1/d1"))
                _i2, drift2 = _hc._copernicus_image_info(
                    _make_symbol_drifted_copernicus_node(symbol, "/img/copnet1/d2"))

            assert [d["symbol"] for d in drift1] == [symbol], (
                f"{symbol}: expected exactly one drift entry, got {[d['symbol'] for d in drift1]}")
            assert [d["symbol"] for d in drift2] == [symbol], (
                f"{symbol}: drift entry must fire on EVERY call, got {[d['symbol'] for d in drift2]}")
            assert symbol in _hc._WARNED_COP_DRIFT
            warns = [r for r in caplog.records
                     if r.levelno == logging.WARNING and symbol in r.getMessage()]
            assert len(warns) == 1, f"{symbol}: expected one warn across two calls, got {len(warns)}"

    def test_uses_legacy_cop2_surface_isinstance_branches(self):
        with patch.object(_hc.hou, "Cop2Node", _Cop2NodeSentinel, create=True), \
             patch.object(_hc.hou, "CopNode", _CopNodeSentinel, create=True):
            # First isinstance branch: a Cop2Node instance -> legacy surface (True).
            assert _hc._uses_legacy_cop2_surface(_Cop2NodeSentinel()) is True
            # Second isinstance branch: a CopNode instance -> Copernicus surface (False).
            assert _hc._uses_legacy_cop2_surface(_CopNodeSentinel()) is False


class TestCopsSlapComp:
    def test_slap_comp_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/comp1", "composite")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_slap_comp",
                id="test-20",
                payload={"cop_path": "/obj/cop2net1/comp1"},
            ))
        assert result.success
        assert result.data["configured"] is True


# ---------------------------------------------------------------------------
# Phase 3: Procedural & Motion Design Tests
# ---------------------------------------------------------------------------

class TestCopsCreateSolver:
    def test_create_solver_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_solver",
                id="test-21",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert "block_begin" in result.data
        assert "block_end" in result.data

    def test_create_solver_custom_iterations(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_solver",
                id="test-22",
                payload={"parent": "/obj/cop2net1", "iterations": 50},
            ))
        assert result.success
        assert result.data["iterations"] == 50


class TestCopsProceduralTexture:
    def test_procedural_texture_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_procedural_texture",
                id="test-23",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["noise_type"] == "perlin"

    def test_procedural_texture_worley(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_procedural_texture",
                id="test-24",
                payload={"parent": "/obj/cop2net1", "noise_type": "worley"},
            ))
        assert result.success
        assert result.data["noise_type"] == "worley"


class TestCopsGrowthPropagation:
    def test_growth_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_growth_propagation",
                id="test-25",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert "block_begin" in result.data
        assert result.data["growth_rate"] == 0.5

    def test_growth_custom_params(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_growth_propagation",
                id="test-26",
                payload={
                    "parent": "/obj/cop2net1",
                    "iterations": 50,
                    "growth_rate": 0.8,
                },
            ))
        assert result.success
        assert result.data["iterations"] == 50
        assert result.data["growth_rate"] == 0.8


class TestCopsReactionDiffusion:
    def test_rd_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_reaction_diffusion",
                id="test-27",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["feed_rate"] == 0.055
        assert result.data["kill_rate"] == 0.062

    def test_rd_custom_rates(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_reaction_diffusion",
                id="test-28",
                payload={
                    "parent": "/obj/cop2net1",
                    "feed_rate": 0.04,
                    "kill_rate": 0.06,
                },
            ))
        assert result.success
        assert result.data["feed_rate"] == 0.04

    def test_reaction_diffusion_reports_scaffolded(self, handler):
        """Honest scaffold: placeholder kernel only, no cook -- the result
        must say so and no created node may have been cooked."""
        net = _make_network_node("/obj/cop2net1")
        created = []

        def _create_and_track(node_type, name=None):
            child = _make_cop_node(f"/obj/cop2net1/{name or node_type}", node_type)
            created.append(child)
            return child

        net.createNode = MagicMock(side_effect=_create_and_track)
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_reaction_diffusion",
                id="test-47",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["scaffolded"] is True
        assert result.data["cooked"] is False
        for n in created:
            n.cook.assert_not_called()


class TestCopsPixelSort:
    def test_pixel_sort_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_pixel_sort",
                id="test-29",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["sort_by"] == "luminance"
        assert result.data["direction"] == "vertical"

    def test_pixel_sort_custom(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_pixel_sort",
                id="test-30",
                payload={
                    "parent": "/obj/cop2net1",
                    "sort_by": "hue",
                    "direction": "horizontal",
                },
            ))
        assert result.success
        assert result.data["sort_by"] == "hue"

    def test_pixel_sort_reports_scaffolded(self, handler):
        """Honest scaffold: placeholder kernel only, no cook -- the result
        must say so and no created node may have been cooked."""
        net = _make_network_node("/obj/cop2net1")
        created = []

        def _create_and_track(node_type, name=None):
            child = _make_cop_node(f"/obj/cop2net1/{name or node_type}", node_type)
            created.append(child)
            return child

        net.createNode = MagicMock(side_effect=_create_and_track)
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_pixel_sort",
                id="test-48",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["scaffolded"] is True
        assert result.data["cooked"] is False
        for n in created:
            n.cook.assert_not_called()


class TestCopsStylize:
    def test_stylize_toon(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="test-31",
                payload={"parent": "/obj/cop2net1", "style_type": "toon"},
            ))
        assert result.success
        assert result.data["style_type"] == "toon"

    def test_stylize_edge_detect(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="test-32",
                payload={"parent": "/obj/cop2net1", "style_type": "edge_detect"},
            ))
        assert result.success
        assert result.data["style_type"] == "edge_detect"

    def test_stylize_posterize(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="test-33",
                payload={"parent": "/obj/cop2net1", "style_type": "posterize", "levels": 4},
            ))
        assert result.success
        assert result.data["levels"] == 4

    def test_stylize_risograph(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="test-34",
                payload={"parent": "/obj/cop2net1", "style_type": "risograph"},
            ))
        assert result.success
        assert result.data["style_type"] == "risograph"


# ---------------------------------------------------------------------------
# Phase 4: Advanced Tests
# ---------------------------------------------------------------------------

class TestCopsWetmap:
    def test_wetmap_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_wetmap",
                id="test-35",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert "block_begin" in result.data
        assert result.data["decay"] == 0.95

    def test_wetmap_custom_decay(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_wetmap",
                id="test-36",
                payload={"parent": "/obj/cop2net1", "decay": 0.8, "blur": 4.0},
            ))
        assert result.success
        assert result.data["decay"] == 0.8
        assert result.data["blur"] == 4.0


# ---------------------------------------------------------------------------
# W.4-H22-solverblocks (SB-3): solver-block binding + alias no-op re-authoring
#
# Ground truth (live bridge + hython parm probes, 22.0.368 -- docs/reviews/
# h22-live-reconfirm-2026-07-16.md §2.1 + h22-cop-audit-verification.md
# tools #11/#13/#14/#16/#17):
#   * block_end LOST method/blocktype/blockpath; blockpath MOVED to
#     block_begin; binding is NOT implicit (unbound pair -> hou.OperationFailed
#     on cook). Surviving block_end surface = sim/iteration driver
#     (simulate/iterations/startframe/cacheenabled/...).
#   * 'limit' resolves to 'clamp' whose surface is upperlimit/doupperlimit
#     (+lower pair) -- max/high are ABSENT.
#   * quantize lost levels/steps on BOTH surfaces; live replacements:
#     Cop method='segments'+segments (int), Cop2 step (float, 1/levels).
#
# Two mock flavors below:
#   * RESTRICTED -- parm() resolves ONLY live-probed names (positive pins:
#     the emitted writes land on the real H22 surface);
#   * PERMISSIVE -- every parm name resolves and records (negative pins:
#     even a fake surface that resurrects a removed parm must not be written).
# ---------------------------------------------------------------------------

# Live-probed per-type parm surfaces (hython 22.0.368, W.4 SB-3 probe).
_H22_COP_SURFACE = {
    "block_begin": {"blockpath", "cablerenamebylabel", "ports"},
    "block_end": {
        "cablerenamebylabel", "cachedframes", "cacheenabled", "checkpointframes",
        "continuouscook", "continuouscook_tick", "continuouscook_toggle",
        "docompile", "firstpassvar", "iterations", "iterationvar", "ports",
        "resimulate", "simulate", "slapcomp", "slapcompaddaovs",
        "slapcompcameraspace", "startframe", "timescale", "totalitervar",
    },
    "clamp": {
        "computerange", "dolowerlimit", "doupperlimit", "lowerlimit", "mask",
        "method", "scopergba", "softclipdir", "softcliprange", "upperlimit",
    },
    "dilateerode": {"radius"},
    "blur": {"size"},
    "bright": {"bright"},
    "opencl": {"kernelcode", "kernelname"},
    "quantize": {
        "clampabove", "clampbelow", "computerange", "mask", "maxval", "method",
        "minval", "offset", "round", "roundoffset", "segments", "signature",
        "width",
    },
    "vopcop2gen": set(),  # audit tool #12: every probed parm alt ABSENT
}

# The block_end parms REMOVED on 22.0.368 (plus the never-existed block_begin
# guess) that the pre-fix builders wrote -- must never be written again.
_REMOVED_BLOCK_END_PARMS = ("blockpath", "block_begin", "method", "blocktype")


def _make_recording_cop_node(path, type_name, allowed=None):
    """Mock Cop node whose parm() returns a RECORDING parm mock per name.

    ``allowed=None`` -> permissive (every name resolves); a set -> only those
    names resolve (the live-probed surface), everything else is None exactly
    like the real runtime. Writes are inspected via ``node.recorded_parms``.
    """
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name, category="Cop")
    node.errors.return_value = []
    node.warnings.return_value = []
    recorded = {}

    def _parm(name):
        if allowed is not None and name not in allowed:
            return None
        if name not in recorded:
            p = MagicMock()
            p.name.return_value = name
            recorded[name] = p
        return recorded[name]

    node.parm = _parm
    node.parmTuple = MagicMock(return_value=None)
    node.recorded_parms = recorded
    return node


def _make_recording_network(path="/img/copnet1", restricted=True):
    """Mock copnet whose children record parm writes; ``net.created`` maps
    child name -> node. ``restricted=True`` limits every child to its
    live-probed H22 parm surface."""
    net = MagicMock()
    net.path.return_value = path
    net.name.return_value = path.rsplit("/", 1)[-1]
    net.children.return_value = []
    created = {}

    def _create(node_type, name=None):
        child_name = name or node_type
        allowed = _H22_COP_SURFACE.get(node_type) if restricted else None
        child = _make_recording_cop_node(
            f"{path}/{child_name}", node_type, allowed=allowed)
        created[child_name] = child
        return child

    net.createNode = MagicMock(side_effect=_create)
    net.created = created
    return net


def _assert_never_set(node, parm_name):
    parm = node.recorded_parms.get(parm_name)
    assert parm is None or not parm.set.called, (
        f"{node.name()}: parm '{parm_name}' was WRITTEN -- removed on "
        "22.0.368, the write is a silent no-op on the live build"
    )


class TestW4SolverBlockBinding:
    """The four solver builders bind explicitly on block_begin.blockpath."""

    def test_create_solver_binds_on_live_surface(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_solver",
                id="w4-1",
                payload={"parent": "/img/copnet1", "iterations": 12},
            ))
        assert result.success
        begin = net.created["solver_begin"]
        end = net.created["solver_end"]
        begin.recorded_parms["blockpath"].set.assert_called_once_with("../solver_end")
        end.recorded_parms["iterations"].set.assert_called_once_with(12)
        # default method 'singlepass' -> simulate toggle OFF
        end.recorded_parms["simulate"].set.assert_called_once_with(0)
        assert result.data["bound"] is True
        assert result.data["simulate"] is False

    def test_create_solver_simulate_method(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_solver",
                id="w4-2",
                payload={"parent": "/img/copnet1", "method": "simulate"},
            ))
        assert result.success
        end = net.created["solver_end"]
        end.recorded_parms["simulate"].set.assert_called_once_with(1)
        assert result.data["simulate"] is True

    def test_growth_binds_and_authors_clamp_threshold(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_growth_propagation",
                id="w4-3",
                payload={"parent": "/img/copnet1", "threshold": 0.7},
            ))
        assert result.success
        # canonical H22 spelling emitted -- never the 'limit' alias
        emitted_types = [c.args[0] for c in net.createNode.call_args_list]
        assert "clamp" in emitted_types
        assert "limit" not in emitted_types
        thresh = net.created["growth_threshold"]
        thresh.recorded_parms["doupperlimit"].set.assert_called_once_with(1)
        thresh.recorded_parms["upperlimit"].set.assert_called_once_with(0.7)
        _assert_never_set(thresh, "max")
        _assert_never_set(thresh, "high")
        # surviving fallbacks land on the live names
        net.created["growth_dilate"].recorded_parms["radius"].set.assert_called_once_with(0.5)
        net.created["growth_blur"].recorded_parms["size"].set.assert_called_once_with(1.0)
        net.created["growth_begin"].recorded_parms["blockpath"].set.assert_called_once_with("../growth_end")
        assert result.data["bound"] is True

    def test_reaction_diffusion_binds(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_reaction_diffusion",
                id="w4-4",
                payload={"parent": "/img/copnet1"},
            ))
        assert result.success
        begin = net.created["reaction_diffusion_begin"]
        end = net.created["reaction_diffusion_end"]
        begin.recorded_parms["blockpath"].set.assert_called_once_with(
            "../reaction_diffusion_end")
        end.recorded_parms["iterations"].set.assert_called_once_with(100)
        assert result.data["bound"] is True

    def test_wetmap_simulate_toggle_and_binding(self, handler):
        """Tool #17: temporal decay = the simulate toggle + explicit binding."""
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_wetmap",
                id="w4-5",
                payload={"parent": "/img/copnet1"},
            ))
        assert result.success
        end = net.created["wetmap_end"]
        end.recorded_parms["simulate"].set.assert_called_once_with(1)
        net.created["wetmap_begin"].recorded_parms["blockpath"].set.assert_called_once_with(
            "../wetmap_end")
        net.created["wetmap_decay"].recorded_parms["bright"].set.assert_called_once_with(0.95)
        assert result.data["bound"] is True

    @pytest.mark.parametrize("command,begin_name,end_name", [
        ("cops_create_solver", "solver_begin", "solver_end"),
        ("cops_growth_propagation", "growth_begin", "growth_end"),
        ("cops_reaction_diffusion", "reaction_diffusion_begin", "reaction_diffusion_end"),
        ("cops_wetmap", "wetmap_begin", "wetmap_end"),
    ])
    def test_no_builder_writes_removed_block_end_parms(
            self, handler, command, begin_name, end_name):
        """PERMISSIVE surface: even when a fake parm surface resurrects the
        removed block_end parms, no builder may write them."""
        net = _make_recording_network(restricted=False)
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type=command,
                id=f"w4-neg-{command}",
                payload={"parent": "/img/copnet1"},
            ))
        assert result.success
        end = net.created[end_name]
        for removed in _REMOVED_BLOCK_END_PARMS:
            _assert_never_set(end, removed)
        begin = net.created[begin_name]
        begin.recorded_parms["blockpath"].set.assert_called_once_with(
            f"../{end_name}")
        assert result.data["bound"] is True

    def test_unbound_pair_reported_honestly(self, handler):
        """A surface with no block_begin.blockpath (drift/stub) must surface
        bound=False in the envelope -- never a silent skip."""
        net = _make_recording_network()
        # strip blockpath from the begin surface for this test
        orig_create = net.createNode.side_effect

        def _create_no_blockpath(node_type, name=None):
            child = orig_create(node_type, name)
            if node_type == "block_begin":
                child.parm = lambda _n: None
                child.recorded_parms = {}
            return child

        net.createNode.side_effect = _create_no_blockpath
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_create_solver",
                id="w4-6",
                payload={"parent": "/img/copnet1"},
            ))
        assert result.success
        assert result.data["bound"] is False


class TestW4StylizeQuantizeSurface:
    """Tool #16: quantize levels re-authored to the live H22 parm surfaces."""

    def test_toon_authors_segments_on_cop_surface(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-7",
                payload={"parent": "/img/copnet1", "style_type": "toon", "levels": 4},
            ))
        assert result.success
        node = net.created["stylize"]
        node.recorded_parms["method"].set.assert_called_once_with("segments")
        node.recorded_parms["segments"].set.assert_called_once_with(4)
        assert result.data["levels_applied"] is True

    def test_toon_falls_back_to_cop2_step(self, handler):
        """Legacy Cop2 quantize surface: step = 1/levels (Pixel Step float)."""
        net = _make_recording_network(restricted=False)

        def _create_cop2_quantize(node_type, name=None):
            child = _make_recording_cop_node(
                f"/obj/cop2net1/{name or node_type}", node_type,
                allowed={"quantize", "step", "offset"})
            net.created[name or node_type] = child
            return child

        net.createNode.side_effect = _create_cop2_quantize
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-8",
                payload={"parent": "/obj/cop2net1", "style_type": "posterize", "levels": 4},
            ))
        assert result.success
        node = net.created["stylize"]
        node.recorded_parms["step"].set.assert_called_once_with(pytest.approx(0.25))
        assert result.data["levels_applied"] is True

    def test_toon_degrades_loud_when_no_surface(self, handler):
        """Neither segments nor step -> levels_applied False, never silent."""
        net = _make_recording_network(restricted=False)

        def _create_bare(node_type, name=None):
            child = _make_recording_cop_node(
                f"/img/copnet1/{name or node_type}", node_type, allowed=set())
            net.created[name or node_type] = child
            return child

        net.createNode.side_effect = _create_bare
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-9",
                payload={"parent": "/img/copnet1", "style_type": "toon"},
            ))
        assert result.success
        assert result.data["levels_applied"] is False

    def test_levels_never_written_via_removed_names(self, handler):
        """PERMISSIVE surface: levels/steps must not be written even when a
        fake surface resurrects them."""
        net = _make_recording_network(restricted=False)
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-10",
                payload={"parent": "/img/copnet1", "style_type": "toon", "levels": 5},
            ))
        assert result.success
        node = net.created["stylize"]
        _assert_never_set(node, "levels")
        _assert_never_set(node, "steps")
        node.recorded_parms["segments"].set.assert_called_once_with(5)

    def test_risograph_authors_segments(self, handler):
        net = _make_recording_network()
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-11",
                payload={"parent": "/img/copnet1", "style_type": "risograph", "levels": 3},
            ))
        assert result.success
        quant = net.created["stylize_quant"]
        quant.recorded_parms["segments"].set.assert_called_once_with(3)
        assert result.data["levels_applied"] is True

    def test_edge_detect_levels_not_relevant(self, handler):
        net = _make_recording_network(restricted=False)
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stylize",
                id="w4-12",
                payload={"parent": "/img/copnet1", "style_type": "edge_detect"},
            ))
        assert result.success
        assert result.data["levels_applied"] is None


class TestCopsBakeTextures:
    def test_bake_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_bake_textures",
                id="test-37",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["map_types"] == ["normal"]

    def test_bake_multiple_maps(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_bake_textures",
                id="test-38",
                payload={
                    "parent": "/obj/cop2net1",
                    "map_types": ["normal", "ao", "curvature"],
                },
            ))
        assert result.success
        assert len(result.data["bake_nodes"]) == 3

    def test_bake_textures_reports_scaffolded(self, handler):
        """Honest scaffold: the result must say nothing was baked, and
        high_res/low_res must be echoed back as unused inputs."""
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_bake_textures",
                id="test-46",
                payload={
                    "parent": "/obj/cop2net1",
                    "high_res": "/obj/high_geo",
                    "low_res": "/obj/low_geo",
                },
            ))
        assert result.success
        assert result.data["scaffolded"] is True
        assert result.data["baked"] is False
        assert result.data["unused_inputs"] == {
            "high_res": "/obj/high_geo",
            "low_res": "/obj/low_geo",
        }


class TestCopsTemporalAnalysis:
    def test_temporal_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            with patch.object(_handlers_hou, "frame", return_value=50.0, create=True):
                with patch.object(_handlers_hou, "setFrame", create=True):
                    result = handler.handle(handlers_mod.SynapseCommand(
                        type="cops_temporal_analysis",
                        id="test-39",
                        payload={"node": "/obj/cop2net1/file1"},
                    ))
        assert result.success
        assert "analysis" in result.data

    def test_temporal_custom_range(self, handler):
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            with patch.object(_handlers_hou, "setFrame", create=True):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_temporal_analysis",
                    id="test-40",
                    payload={
                        "node": "/obj/cop2net1/file1",
                        "frame_range": [1, 10],
                    },
                ))
        assert result.success
        assert result.data["frame_range"] == [1, 10]

    def test_temporal_analysis_restores_playhead(self, handler):
        """The handler moves the playhead to cook each frame -- it must
        restore the artist's original frame afterwards."""
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        with patch.object(_handlers_hou, "node", return_value=node):
            with patch.object(_handlers_hou, "frame", return_value=50.0, create=True):
                with patch.object(_handlers_hou, "setFrame", create=True) as set_frame:
                    result = handler.handle(handlers_mod.SynapseCommand(
                        type="cops_temporal_analysis",
                        id="test-49",
                        payload={
                            "node": "/obj/cop2net1/file1",
                            "frame_range": [10, 12],
                        },
                    ))
        assert result.success
        assert set_frame.call_args_list == [
            call(10), call(11), call(12), call(50.0),
        ]

    def test_temporal_analysis_restores_playhead_on_cook_error(self, handler):
        """Even when every cook raises, the playhead restore still runs."""
        node = _make_cop_node("/obj/cop2net1/file1", "file")
        node.cook.side_effect = Exception("cook failed")
        with patch.object(_handlers_hou, "node", return_value=node):
            with patch.object(_handlers_hou, "frame", return_value=50.0, create=True):
                with patch.object(_handlers_hou, "setFrame", create=True) as set_frame:
                    result = handler.handle(handlers_mod.SynapseCommand(
                        type="cops_temporal_analysis",
                        id="test-50",
                        payload={
                            "node": "/obj/cop2net1/file1",
                            "frame_range": [10, 12],
                        },
                    ))
        assert result.success
        assert set_frame.call_args_list[-1] == call(50.0)


class TestCopsStampScatter:
    def test_stamp_scatter_basic(self, handler):
        net = _make_network_node("/obj/cop2net1")
        with patch.object(_handlers_hou, "node", return_value=net):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_stamp_scatter",
                id="test-41",
                payload={"parent": "/obj/cop2net1"},
            ))
        assert result.success
        assert result.data["count"] == 50
        assert result.data["seed"] == 42


class TestCopsBatchCook:
    def test_batch_cook_basic(self, handler):
        node = _make_cop_node("/obj/cop2net1/blur1", "blur")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_batch_cook",
                id="test-42",
                payload={"nodes": ["/obj/cop2net1/blur1"]},
            ))
        assert result.success
        assert result.data["cooked"] == 1

    def test_batch_cook_missing_node(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_batch_cook",
                id="test-43",
                payload={"nodes": ["/nonexistent"]},
            ))
        assert result.success  # Batch itself succeeds
        assert result.data["failed"] == 1

    def test_batch_cook_empty_list(self, handler):
        result = handler.handle(handlers_mod.SynapseCommand(
            type="cops_batch_cook",
            id="test-44",
            payload={"nodes": []},
        ))
        assert not result.success

    def test_batch_cook_multiple(self, handler):
        node = _make_cop_node("/obj/cop2net1/blur1", "blur")
        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler.handle(handlers_mod.SynapseCommand(
                type="cops_batch_cook",
                id="test-45",
                payload={"nodes": ["/obj/cop2net1/blur1", "/obj/cop2net1/blur2"]},
            ))
        assert result.success
        assert result.data["total"] == 2


# ---------------------------------------------------------------------------
# Transactional Builder Tests
# ---------------------------------------------------------------------------

class TestCopsTransactionalBuilders:
    def test_builder_rolls_back_on_partial_failure(self, handler):
        """create_solver: block_begin succeeds, block_end raises -- the
        stranded block_begin must be rolled back via performUndo (once)."""
        net = _make_network_node("/obj/cop2net1")
        block_begin = _make_cop_node("/obj/cop2net1/solver_begin", "block_begin")
        net.createNode = MagicMock(side_effect=[block_begin, RuntimeError("boom")])
        fresh_undos = MagicMock()
        with patch.object(_handlers_hou, "node", return_value=net):
            with patch.object(_handlers_hou, "undos", fresh_undos):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_create_solver",
                    id="test-51",
                    payload={"parent": "/obj/cop2net1"},
                ))
        assert not result.success
        assert fresh_undos.performUndo.call_count == 1

    def test_builder_no_rollback_when_nothing_created(self, handler):
        """create_solver: the FIRST createNode raises -- nothing was
        created, so performUndo must NOT fire (pins the created_any guard)."""
        net = _make_network_node("/obj/cop2net1")
        net.createNode = MagicMock(side_effect=RuntimeError("boom"))
        fresh_undos = MagicMock()
        with patch.object(_handlers_hou, "node", return_value=net):
            with patch.object(_handlers_hou, "undos", fresh_undos):
                result = handler.handle(handlers_mod.SynapseCommand(
                    type="cops_create_solver",
                    id="test-52",
                    payload={"parent": "/obj/cop2net1"},
                ))
        assert not result.success
        fresh_undos.performUndo.assert_not_called()


# ---------------------------------------------------------------------------
# Registration Tests
# ---------------------------------------------------------------------------

class TestCopsRegistration:
    def test_all_cops_commands_registered(self, handler):
        """Verify all 21 COPs handlers are registered."""
        cops_commands = [
            "cops_create_network", "cops_create_copnet", "cops_create_node",
            "cops_connect",
            "cops_set_opencl", "cops_read_layer_info",
            "cops_to_materialx", "cops_composite_aovs",
            "cops_analyze_render", "cops_slap_comp",
            "cops_create_solver", "cops_procedural_texture",
            "cops_growth_propagation", "cops_reaction_diffusion",
            "cops_pixel_sort", "cops_stylize",
            "cops_wetmap", "cops_bake_textures",
            "cops_temporal_analysis", "cops_stamp_scatter",
            "cops_batch_cook",
        ]
        registered = handler._registry.registered_types
        for cmd in cops_commands:
            assert cmd in registered, f"'{cmd}' not registered"

    def test_cops_count(self, handler):
        """Verify exactly 21 COPs commands are registered."""
        cops_cmds = [c for c in handler._registry.registered_types
                     if c.startswith("cops_")]
        assert len(cops_cmds) == 21

    def test_protocol_command_types(self):
        """Verify CommandType enum has all COPs entries."""
        ct = protocol_mod.CommandType
        cops_types = [m for m in ct.__members__ if m.startswith("COPS_")]
        assert len(cops_types) == 21

    def test_read_only_commands(self):
        """Verify read-only COPs commands are in _READ_ONLY_COMMANDS."""
        ro = handlers_mod._READ_ONLY_COMMANDS
        assert "cops_read_layer_info" in ro
        assert "cops_analyze_render" in ro
        # Mutations should NOT be in read-only
        assert "cops_create_network" not in ro
        assert "cops_create_node" not in ro

    def test_temporal_analysis_is_not_read_only(self):
        """cops_temporal_analysis moves the playhead to cook each frame --
        it mutates session state and must NOT be classified read-only."""
        assert "cops_temporal_analysis" not in handlers_mod._READ_ONLY_COMMANDS


# ---------------------------------------------------------------------------
# Recipe Tests
# ---------------------------------------------------------------------------

class TestCopsRecipes:
    def test_copernicus_recipes_registered(self):
        """Verify all Copernicus recipes exist."""
        from synapse.routing.recipes import RecipeRegistry
        registry = RecipeRegistry()
        recipe_names = [r.name for r in registry.recipes]

        expected = [
            "copernicus_render_comp",
            "copernicus_procedural_texture",
            "copernicus_pixel_sort",
            "copernicus_reaction_diffusion",
            "copernicus_growth",
            "copernicus_stylize",
            "copernicus_wetmap",
            "copernicus_bake_textures",
            "copernicus_stamp_scatter",
            "copernicus_batch_process",
        ]
        for name in expected:
            assert name in recipe_names, f"Recipe '{name}' not registered"

    def test_copernicus_recipe_count(self):
        """Verify we have at least 10 Copernicus recipes."""
        from synapse.routing.recipes import RecipeRegistry
        registry = RecipeRegistry()
        cops_recipes = [r for r in registry.recipes
                        if r.name.startswith("copernicus_")]
        assert len(cops_recipes) >= 10


# ---------------------------------------------------------------------------
# MCP Tool Definition Tests
# ---------------------------------------------------------------------------

class TestCopsMcpTools:
    def test_mcp_tool_defs_exist(self):
        """Verify all 21 COPs tools are in mcp/tools.py _TOOL_DEFS."""
        # Import the mcp tools module
        mcp_tools_path = _base / "mcp" / "tools.py"
        if "synapse.mcp" not in sys.modules:
            pkg = types.ModuleType("synapse.mcp")
            pkg.__path__ = [str(_base / "mcp")]
            sys.modules["synapse.mcp"] = pkg

        if "synapse.mcp.tools" not in sys.modules:
            spec = importlib.util.spec_from_file_location(
                "synapse.mcp.tools", mcp_tools_path
            )
            mod = importlib.util.module_from_spec(spec)
            sys.modules["synapse.mcp.tools"] = mod
            spec.loader.exec_module(mod)

        mcp_tools_mod = sys.modules["synapse.mcp.tools"]
        tool_names = [t[0] for t in mcp_tools_mod.TOOL_DEFS]

        cops_tools = [n for n in tool_names if n.startswith("cops_")]
        assert len(cops_tools) == 21

    def test_mcp_tool_group_module(self):
        """Verify mcp_tools_cops.py has correct tool count."""
        # Direct import from project root
        mcp_tools_cops_path = Path(__file__).resolve().parent.parent / "mcp_tools_cops.py"
        spec = importlib.util.spec_from_file_location("mcp_tools_cops_test", mcp_tools_cops_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert len(mod.TOOL_NAMES) == 21
        assert len(mod.DISPATCH_KEYS) == 21
        assert "GROUP_KNOWLEDGE" in dir(mod)
