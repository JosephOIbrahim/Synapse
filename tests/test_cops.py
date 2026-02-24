"""Tests for Copernicus (COPs) handlers.

Tests all 20 COP handlers across 4 phases:
  - Foundation: create_network, create_node, connect, set_opencl, read_layer_info
  - Pipeline: to_materialx, composite_aovs, analyze_render, slap_comp
  - Procedural: create_solver, procedural_texture, growth_propagation,
                reaction_diffusion, pixel_sort, stylize
  - Advanced: wetmap, bake_textures, temporal_analysis, stamp_scatter, batch_cook

Mock-based -- no Houdini required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

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
    node.depth.return_value = "float32"
    node.planes.return_value = ["C", "A"]

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
# Registration Tests
# ---------------------------------------------------------------------------

class TestCopsRegistration:
    def test_all_cops_commands_registered(self, handler):
        """Verify all 20 COPs handlers are registered."""
        cops_commands = [
            "cops_create_network", "cops_create_node", "cops_connect",
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
        """Verify exactly 20 COPs commands are registered."""
        cops_cmds = [c for c in handler._registry.registered_types
                     if c.startswith("cops_")]
        assert len(cops_cmds) == 20

    def test_protocol_command_types(self):
        """Verify CommandType enum has all COPs entries."""
        ct = protocol_mod.CommandType
        cops_types = [m for m in ct.__members__ if m.startswith("COPS_")]
        assert len(cops_types) == 20

    def test_read_only_commands(self):
        """Verify read-only COPs commands are in _READ_ONLY_COMMANDS."""
        ro = handlers_mod._READ_ONLY_COMMANDS
        assert "cops_read_layer_info" in ro
        assert "cops_analyze_render" in ro
        assert "cops_temporal_analysis" in ro
        # Mutations should NOT be in read-only
        assert "cops_create_network" not in ro
        assert "cops_create_node" not in ro


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
        """Verify all 20 COPs tools are in mcp/tools.py _TOOL_DEFS."""
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
        assert len(cops_tools) == 20

    def test_mcp_tool_group_module(self):
        """Verify mcp_tools_cops.py has correct tool count."""
        # Direct import from project root
        mcp_tools_cops_path = Path(__file__).resolve().parent.parent / "mcp_tools_cops.py"
        spec = importlib.util.spec_from_file_location("mcp_tools_cops_test", mcp_tools_cops_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert len(mod.TOOL_NAMES) == 20
        assert len(mod.DISPATCH_KEYS) == 20
        assert "GROUP_KNOWLEDGE" in dir(mod)
