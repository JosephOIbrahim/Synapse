"""Tests for TOPS/PDG Phase 1 handlers.

Tests all 5 TOPS handlers:
  - tops_get_work_items
  - tops_get_dependency_graph
  - tops_get_cook_stats
  - tops_cook_node
  - tops_generate_items

Mock-based -- no Houdini or PDG required.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: hou + pdg stubs
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=1.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    # executeInMainThreadWithResult just calls the function directly in tests
    _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]
    if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
        _hdefereval.executeInMainThreadWithResult = lambda fn, *args, **kwargs: fn(*args, **kwargs)

# PDG stub with work item states
if "pdg" not in sys.modules:
    _pdg = types.ModuleType("pdg")

    class _WorkItemState:
        CookedSuccess = "CookedSuccess"
        CookedFail = "CookedFail"
        Cooking = "Cooking"
        Scheduled = "Scheduled"
        Uncooked = "Uncooked"
        CookedCancel = "CookedCancel"

    _pdg.workItemState = _WorkItemState
    sys.modules["pdg"] = _pdg
else:
    _pdg = sys.modules["pdg"]

# Bootstrap synapse package modules
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
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
aliases_mod = sys.modules["synapse.core.aliases"]

# Get the hou reference from handlers_tops.py — that's where the TOPS handlers
# live and where hou.node() is called. In the full test suite, earlier tests may
# have replaced sys.modules["hou"], but handlers_tops.hou still points to
# the original object. We patch THAT object.
_tops_mod = sys.modules.get("synapse.server.handlers_tops")
_handlers_hou = _tops_mod.hou if _tops_mod else handlers_mod.hou

# Ensure the hou stub has the attributes we need to patch (cross-test robustness:
# earlier test files may have replaced hou with a bare ModuleType)
if not hasattr(_handlers_hou, "node"):
    _handlers_hou.node = MagicMock()


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

class _MockState:
    """Mock for pdg.workItemState enum values."""
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    def __eq__(self, other):
        if isinstance(other, _MockState):
            return self._name == other._name
        return self._name == other

    def __hash__(self):
        return hash(self._name)

    def __str__(self):
        return self._name


class _MockAttrib:
    def __init__(self, name, vals):
        self._name = name
        self._vals = vals

    @property
    def name(self):
        return self._name

    def values(self):
        return self._vals


def _make_work_item(id=0, index=0, name="item_0", state="CookedSuccess",
                    cook_time=1.5, attrs=None):
    wi = MagicMock()
    wi.id = id
    wi.index = index
    wi.name = name
    wi.state = _MockState(state)
    wi.cookTime = cook_time
    wi.attribs = []
    if attrs:
        for k, v in sorted(attrs.items()):
            wi.attribs.append(_MockAttrib(k, v))
    return wi


def _make_pdg_node(work_items=None):
    pdg_node = MagicMock()
    pdg_node.workItems = work_items or []
    return pdg_node


class _MockCategory:
    def __init__(self, name):
        self._name = name
    def name(self):
        return self._name


class _MockNodeType:
    def __init__(self, name="null", category="Top"):
        self._name = name
        self._cat = _MockCategory(category)
    def name(self):
        return self._name
    def category(self):
        return self._cat


def _make_top_node(path="/obj/topnet1/node1", pdg_node=None, category="Top",
                   type_name="genericgenerator", children=None):
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name, category)
    node.getPDGNode.return_value = pdg_node
    node.children.return_value = children or []
    node.inputConnections.return_value = []
    node.cook = MagicMock()
    node.generateStaticItems = MagicMock()
    return node


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    return h


# ===========================================================================
# TestGetWorkItems
# ===========================================================================

class TestGetWorkItems:
    def test_returns_all_items(self, handler):
        items = [_make_work_item(id=i, index=i, name=f"item_{i}") for i in range(3)]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({"node": "/obj/topnet1/node1"})

        assert result["total_items"] == 3
        assert result["returned"] == 3
        assert result["filter"] == "all"
        assert len(result["items"]) == 3

    def test_state_filter_cooked(self, handler):
        items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedFail"),
            _make_work_item(id=2, state="CookedSuccess"),
        ]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "state_filter": "cooked",
            })

        assert result["returned"] == 2
        assert result["total_items"] == 3

    def test_state_filter_failed(self, handler):
        items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedFail"),
        ]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "state_filter": "failed",
            })

        assert result["returned"] == 1
        assert result["items"][0]["state"] == "CookedFail"

    def test_include_attributes(self, handler):
        items = [_make_work_item(id=0, attrs={"output": ["/tmp/out.exr"], "frame": [1]})]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "include_attributes": True,
            })

        assert "attributes" in result["items"][0]
        assert result["items"][0]["attributes"]["output"] == ["/tmp/out.exr"]

    def test_exclude_attributes(self, handler):
        items = [_make_work_item(id=0, attrs={"output": ["/tmp/out.exr"]})]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "include_attributes": False,
            })

        assert "attributes" not in result["items"][0]

    def test_limit(self, handler):
        items = [_make_work_item(id=i, index=i, name=f"item_{i}") for i in range(10)]
        pdg_node = _make_pdg_node(items)
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "limit": 3,
            })

        assert result["returned"] == 3
        assert result["total_items"] == 10

    def test_no_pdg_node_error(self, handler):
        top_node = _make_top_node(pdg_node=None)
        with patch.object(_handlers_hou, "node", return_value=top_node):
            with pytest.raises(ValueError, match="isn't a TOP node"):
                handler._handle_tops_get_work_items({"node": "/obj/topnet1/node1"})

    def test_node_not_found_error(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_get_work_items({"node": "/nonexistent"})

    def test_empty_node(self, handler):
        pdg_node = _make_pdg_node([])
        top_node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=top_node):
            result = handler._handle_tops_get_work_items({"node": "/obj/topnet1/node1"})

        assert result["total_items"] == 0
        assert result["returned"] == 0
        assert result["items"] == []


# ===========================================================================
# TestGetDependencyGraph
# ===========================================================================

class TestGetDependencyGraph:
    def test_simple_graph(self, handler):
        pdg1 = _make_pdg_node([_make_work_item(id=0, state="CookedSuccess")])
        pdg2 = _make_pdg_node([])
        child1 = _make_top_node("/obj/topnet1/gen1", pdg1, type_name="genericgenerator")
        child2 = _make_top_node("/obj/topnet1/rop1", pdg2, type_name="ropfetch")

        # child2 has an input from child1
        conn = MagicMock()
        conn.inputNode.return_value = child1
        conn.inputIndex.return_value = 0
        conn.outputIndex.return_value = 0
        child2.inputConnections.return_value = [conn]

        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child1, child2])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_dependency_graph({"topnet_path": "/obj/topnet1"})

        assert result["node_count"] == 2
        assert len(result["edges"]) == 1
        assert result["edges"][0]["from"] == "/obj/topnet1/gen1"
        assert result["edges"][0]["to"] == "/obj/topnet1/rop1"

    def test_empty_network(self, handler):
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet", children=[])
        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_dependency_graph({"topnet_path": "/obj/topnet1"})

        assert result["node_count"] == 0
        assert result["nodes"] == []
        assert result["edges"] == []

    def test_non_topnet_error(self, handler):
        geo = _make_top_node("/obj/geo1", None, "Object", "geo")
        with patch.object(_handlers_hou, "node", return_value=geo):
            with pytest.raises(ValueError, match="not a TOP network"):
                handler._handle_tops_get_dependency_graph({"topnet_path": "/obj/geo1"})

    def test_node_not_found_error(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_get_dependency_graph({"topnet_path": "/nonexistent"})

    def test_work_item_counts(self, handler):
        items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedSuccess"),
            _make_work_item(id=2, state="CookedFail"),
        ]
        pdg = _make_pdg_node(items)
        child = _make_top_node("/obj/topnet1/gen1", pdg)
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet", children=[child])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_dependency_graph({"topnet_path": "/obj/topnet1"})

        node_info = result["nodes"][0]
        assert node_info["total_items"] == 3
        assert node_info["work_items"]["CookedSuccess"] == 2
        assert node_info["work_items"]["CookedFail"] == 1

    def test_node_without_pdg(self, handler):
        child = _make_top_node("/obj/topnet1/null1", None)
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet", children=[child])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_dependency_graph({"topnet_path": "/obj/topnet1"})

        assert result["nodes"][0]["total_items"] == 0
        assert result["nodes"][0]["work_items"] == {}


# ===========================================================================
# TestGetCookStats
# ===========================================================================

class TestGetCookStats:
    def test_single_node(self, handler):
        items = [
            _make_work_item(id=0, state="CookedSuccess", cook_time=1.5),
            _make_work_item(id=1, state="CookedSuccess", cook_time=2.3),
        ]
        pdg = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen1", pdg, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_cook_stats({"node": "/obj/topnet1/gen1"})

        assert result["is_network"] is False
        assert result["total_items"] == 2
        assert result["total_cook_time"] == 3.8
        assert result["by_state"]["CookedSuccess"] == 2

    def test_network_aggregate(self, handler):
        items1 = [_make_work_item(id=0, state="CookedSuccess", cook_time=1.0)]
        items2 = [
            _make_work_item(id=1, state="CookedSuccess", cook_time=0.5),
            _make_work_item(id=2, state="CookedFail", cook_time=0.2),
        ]
        child1 = _make_top_node("/obj/topnet1/gen1", _make_pdg_node(items1))
        child2 = _make_top_node("/obj/topnet1/rop1", _make_pdg_node(items2))
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child1, child2])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_cook_stats({"node": "/obj/topnet1"})

        assert result["is_network"] is True
        assert result["total_items"] == 3
        assert result["by_state"]["CookedSuccess"] == 2
        assert result["by_state"]["CookedFail"] == 1
        assert result["total_cook_time"] == 1.7
        assert len(result["nodes"]) == 2

    def test_empty_node(self, handler):
        pdg = _make_pdg_node([])
        node = _make_top_node("/obj/topnet1/gen1", pdg, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_cook_stats({"node": "/obj/topnet1/gen1"})

        assert result["total_items"] == 0
        assert result["total_cook_time"] == 0.0
        assert result["by_state"] == {}

    def test_node_without_pdg(self, handler):
        node = _make_top_node("/obj/topnet1/null1", None, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_cook_stats({"node": "/obj/topnet1/null1"})

        assert result["total_items"] == 0
        assert result["total_cook_time"] == 0.0

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_get_cook_stats({"node": "/nonexistent"})

    def test_cook_time_rounding(self, handler):
        items = [
            _make_work_item(id=0, state="CookedSuccess", cook_time=0.1234),
            _make_work_item(id=1, state="CookedSuccess", cook_time=0.5678),
        ]
        pdg = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen1", pdg, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_cook_stats({"node": "/obj/topnet1/gen1"})

        assert result["total_cook_time"] == 0.6912


# ===========================================================================
# TestCookNode
# ===========================================================================

class TestCookNode:
    def test_blocking_cook(self, handler):
        pdg = _make_pdg_node([_make_work_item(id=0)])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_node({"node": "/obj/topnet1/node1"})

        assert result["status"] == "cooked"
        node.cook.assert_called_once_with(block=True)

    def test_nonblocking_cook(self, handler):
        pdg = _make_pdg_node([])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_node({
                "node": "/obj/topnet1/node1",
                "blocking": False,
            })

        assert result["status"] == "cooking"
        node.cook.assert_called_once_with(block=False)

    def test_generate_only(self, handler):
        pdg = _make_pdg_node([_make_work_item(id=0)])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_node({
                "node": "/obj/topnet1/node1",
                "generate_only": True,
            })

        assert result["status"] == "generated"
        node.generateStaticItems.assert_called_once()
        node.cook.assert_not_called()

    def test_no_pdg_node_error(self, handler):
        node = _make_top_node(pdg_node=None)
        with patch.object(_handlers_hou, "node", return_value=node):
            with pytest.raises(ValueError, match="isn't a TOP node"):
                handler._handle_tops_cook_node({"node": "/obj/topnet1/node1"})

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_cook_node({"node": "/nonexistent"})

    def test_result_shape(self, handler):
        pdg = _make_pdg_node([_make_work_item(id=0), _make_work_item(id=1)])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_node({"node": "/obj/topnet1/node1"})

        assert "node" in result
        assert "status" in result
        assert "work_items" in result
        assert result["work_items"] == 2

    def test_default_params(self, handler):
        """Default: blocking=True, generate_only=False, top_down=True."""
        pdg = _make_pdg_node([])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_node({"node": "/obj/topnet1/node1"})

        assert result["status"] == "cooked"
        node.cook.assert_called_once_with(block=True)

    def test_missing_node_param(self, handler):
        with pytest.raises(ValueError, match="Missing required"):
            handler._handle_tops_cook_node({})


# ===========================================================================
# TestGenerateItems
# ===========================================================================

class TestGenerateItems:
    def test_basic_generate(self, handler):
        pdg = _make_pdg_node([_make_work_item(id=0), _make_work_item(id=1)])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_generate_items({"node": "/obj/topnet1/node1"})

        assert result["status"] == "generated"
        assert result["item_count"] == 2
        node.generateStaticItems.assert_called_once()

    def test_no_pdg_node_error(self, handler):
        node = _make_top_node(pdg_node=None)
        with patch.object(_handlers_hou, "node", return_value=node):
            with pytest.raises(ValueError, match="isn't a TOP node"):
                handler._handle_tops_generate_items({"node": "/obj/topnet1/node1"})

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_generate_items({"node": "/nonexistent"})

    def test_result_shape(self, handler):
        pdg = _make_pdg_node([])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_generate_items({"node": "/obj/topnet1/node1"})

        assert "node" in result
        assert "status" in result
        assert "item_count" in result

    def test_empty_result(self, handler):
        pdg = _make_pdg_node([])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_generate_items({"node": "/obj/topnet1/node1"})

        assert result["item_count"] == 0


# ===========================================================================
# TestAliases
# ===========================================================================

# ===========================================================================
# TestConfigureScheduler (Phase 2)
# ===========================================================================

class TestConfigureScheduler:
    def test_basic_configure(self, handler):
        scheduler = MagicMock()
        scheduler.path.return_value = "/obj/topnet1/localscheduler"
        scheduler.type.return_value = _MockNodeType("localscheduler", "Top")
        scheduler.parm.return_value = MagicMock()

        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[scheduler])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_configure_scheduler({
                "topnet_path": "/obj/topnet1",
                "max_concurrent": 8,
            })

        assert result["status"] == "configured"
        assert result["topnet"] == "/obj/topnet1"
        assert result["max_concurrent"] == 8

    def test_no_scheduler_error(self, handler):
        child = _make_top_node("/obj/topnet1/gen1", None, "Top", "genericgenerator")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            with pytest.raises(ValueError, match="Couldn't find a scheduler"):
                handler._handle_tops_configure_scheduler({"topnet_path": "/obj/topnet1"})

    def test_not_topnet_error(self, handler):
        geo = _make_top_node("/obj/geo1", None, "Object", "geo")
        with patch.object(_handlers_hou, "node", return_value=geo):
            with pytest.raises(ValueError, match="not a TOP network"):
                handler._handle_tops_configure_scheduler({"topnet_path": "/obj/geo1"})


# ===========================================================================
# TestCancelCook (Phase 2)
# ===========================================================================

class TestCancelCook:
    def test_cancel_topnet(self, handler):
        ctx = MagicMock()
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet")
        topnet.getPDGGraphContext.return_value = ctx

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_cancel_cook({"node": "/obj/topnet1"})

        assert result["status"] == "cancelled"
        ctx.cancelCook.assert_called_once()

    def test_cancel_single_node(self, handler):
        pdg_node = _make_pdg_node([])
        node = _make_top_node("/obj/topnet1/gen1", pdg_node, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cancel_cook({"node": "/obj/topnet1/gen1"})

        assert result["status"] == "cancelled"
        pdg_node.dirty.assert_called_once_with(False)

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_cancel_cook({"node": "/nonexistent"})


# ===========================================================================
# TestDirtyNode (Phase 2)
# ===========================================================================

class TestDirtyNode:
    def test_dirty_single_node(self, handler):
        pdg_node = _make_pdg_node([])
        node = _make_top_node("/obj/topnet1/gen1", pdg_node, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_dirty_node({"node": "/obj/topnet1/gen1"})

        assert result["status"] == "dirtied"
        assert result["dirty_upstream"] is False
        pdg_node.dirty.assert_called_once_with(False)

    def test_dirty_with_upstream(self, handler):
        pdg_node = _make_pdg_node([])
        node = _make_top_node("/obj/topnet1/gen1", pdg_node, "Top")

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_dirty_node({
                "node": "/obj/topnet1/gen1",
                "dirty_upstream": True,
            })

        assert result["dirty_upstream"] is True
        pdg_node.dirty.assert_called_once_with(True)

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_dirty_node({"node": "/nonexistent"})


# ===========================================================================
# TestSetupWedge (Phase 3)
# ===========================================================================

class TestSetupWedge:
    def test_basic_wedge_setup(self, handler):
        wedge_node = MagicMock()
        wedge_node.path.return_value = "/obj/topnet1/wedge1"
        wedge_node.parm.return_value = MagicMock()
        wedge_node.moveToGoodPosition = MagicMock()

        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet")
        topnet.createNode = MagicMock(return_value=wedge_node)

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_setup_wedge({
                "topnet_path": "/obj/topnet1",
                "attributes": [
                    {"name": "roughness", "type": "float", "start": 0.0, "end": 1.0, "steps": 5},
                ],
            })

        assert result["wedge_node"] == "/obj/topnet1/wedge1"
        assert result["total_variations"] == 5
        assert len(result["attributes"]) == 1
        assert result["attributes"][0]["name"] == "roughness"

    def test_multiple_attributes(self, handler):
        wedge_node = MagicMock()
        wedge_node.path.return_value = "/obj/topnet1/wedge1"
        wedge_node.parm.return_value = MagicMock()
        wedge_node.moveToGoodPosition = MagicMock()

        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet")
        topnet.createNode = MagicMock(return_value=wedge_node)

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_setup_wedge({
                "topnet_path": "/obj/topnet1",
                "attributes": [
                    {"name": "roughness", "type": "float", "start": 0.0, "end": 1.0, "steps": 3},
                    {"name": "metalness", "type": "float", "start": 0.0, "end": 1.0, "steps": 4},
                ],
            })

        assert result["total_variations"] == 12  # 3 * 4
        # He2025: attributes sorted by name
        assert result["attributes"][0]["name"] == "metalness"
        assert result["attributes"][1]["name"] == "roughness"

    def test_empty_attributes_error(self, handler):
        with pytest.raises(ValueError, match="attributes"):
            handler._handle_tops_setup_wedge({
                "topnet_path": "/obj/topnet1",
                "attributes": [],
            })


# ===========================================================================
# TestBatchCook (Phase 3)
# ===========================================================================

class TestBatchCook:
    def test_batch_cook_success(self, handler):
        items = [_make_work_item(id=0, state="CookedSuccess")]
        pdg1 = _make_pdg_node(items)
        pdg2 = _make_pdg_node(items)
        node1 = _make_top_node("/obj/topnet1/gen1", pdg1)
        node2 = _make_top_node("/obj/topnet1/gen2", pdg2)

        def _mock_node(path):
            return {"/obj/topnet1/gen1": node1, "/obj/topnet1/gen2": node2}.get(path)

        with patch.object(_handlers_hou, "node", side_effect=_mock_node):
            result = handler._handle_tops_batch_cook({
                "node_paths": ["/obj/topnet1/gen1", "/obj/topnet1/gen2"],
            })

        assert len(result["nodes"]) == 2
        assert result["nodes"][0]["status"] == "cooked"
        assert result["nodes"][1]["status"] == "cooked"
        assert "total_cook_time" in result
        assert "summary" in result

    def test_batch_cook_stop_on_error(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_batch_cook({
                    "node_paths": ["/nonexistent"],
                    "stop_on_error": True,
                })

    def test_batch_cook_continue_on_error(self, handler):
        items = [_make_work_item(id=0, state="CookedSuccess")]
        pdg1 = _make_pdg_node(items)
        node1 = _make_top_node("/obj/topnet1/gen1", pdg1)

        def _mock_node(path):
            return {"/obj/topnet1/gen1": node1}.get(path)

        with patch.object(_handlers_hou, "node", side_effect=_mock_node):
            result = handler._handle_tops_batch_cook({
                "node_paths": ["/nonexistent", "/obj/topnet1/gen1"],
                "stop_on_error": False,
            })

        assert result["nodes"][0]["status"] == "error"
        assert result["nodes"][1]["status"] == "cooked"

    def test_empty_paths_error(self, handler):
        with pytest.raises(ValueError, match="node_paths"):
            handler._handle_tops_batch_cook({"node_paths": []})


# ===========================================================================
# TestQueryItems (Phase 3)
# ===========================================================================

class TestQueryItems:
    def test_eq_filter(self, handler):
        items = [
            _make_work_item(id=0, name="item_0", attrs={"output": ["/tmp/a.exr"]}),
            _make_work_item(id=1, name="item_1", attrs={"output": ["/tmp/b.exr"]}),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_query_items({
                "node": "/obj/topnet1/node1",
                "query_attribute": "output",
                "filter_op": "eq",
                "filter_value": "/tmp/a.exr",
            })

        assert result["matched_count"] == 1
        assert result["total_count"] == 2
        assert result["items"][0]["name"] == "item_0"

    def test_gt_filter(self, handler):
        items = [
            _make_work_item(id=0, name="item_0", attrs={"frame": [1]}),
            _make_work_item(id=1, name="item_1", attrs={"frame": [5]}),
            _make_work_item(id=2, name="item_2", attrs={"frame": [10]}),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_query_items({
                "node": "/obj/topnet1/node1",
                "query_attribute": "frame",
                "filter_op": "gt",
                "filter_value": 3,
            })

        assert result["matched_count"] == 2

    def test_invalid_operator(self, handler):
        with pytest.raises(ValueError, match="Unknown filter operator"):
            handler._handle_tops_query_items({
                "node": "/obj/topnet1/node1",
                "query_attribute": "frame",
                "filter_op": "bad",
                "filter_value": 1,
            })

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_query_items({
                    "node": "/nonexistent",
                    "query_attribute": "output",
                    "filter_value": "x",
                })


class TestAliases:
    def test_node_alias_resolves(self, handler):
        """'node_path' should resolve to 'node' via aliases."""
        pdg = _make_pdg_node([])
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_work_items({"node_path": "/obj/topnet1/node1"})

        assert result["node"] == "/obj/topnet1/node1"

    def test_topnet_alias_resolves(self, handler):
        """'topnet' should resolve to 'topnet_path' via aliases."""
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet", children=[])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_get_dependency_graph({"topnet": "/obj/topnet1"})

        assert result["topnet"] == "/obj/topnet1"

    def test_state_filter_alias(self, handler):
        """'filter_state' should resolve to 'state_filter'."""
        items = [_make_work_item(id=0, state="CookedSuccess")]
        pdg = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_get_work_items({
                "node": "/obj/topnet1/node1",
                "filter_state": "cooked",
            })

        assert result["returned"] == 1


# ===========================================================================
# TestCommandTypeEnums
# ===========================================================================

class TestCommandTypeEnums:
    def test_tops_enums_exist(self):
        """All 14 TOPS CommandType enum values should exist."""
        ct = protocol_mod.CommandType
        assert ct.TOPS_GET_WORK_ITEMS.value == "tops_get_work_items"
        assert ct.TOPS_GET_DEPENDENCY_GRAPH.value == "tops_get_dependency_graph"
        assert ct.TOPS_GET_COOK_STATS.value == "tops_get_cook_stats"
        assert ct.TOPS_COOK_NODE.value == "tops_cook_node"
        assert ct.TOPS_GENERATE_ITEMS.value == "tops_generate_items"
        assert ct.TOPS_CONFIGURE_SCHEDULER.value == "tops_configure_scheduler"
        assert ct.TOPS_CANCEL_COOK.value == "tops_cancel_cook"
        assert ct.TOPS_DIRTY_NODE.value == "tops_dirty_node"
        assert ct.TOPS_SETUP_WEDGE.value == "tops_setup_wedge"
        assert ct.TOPS_BATCH_COOK.value == "tops_batch_cook"
        assert ct.TOPS_QUERY_ITEMS.value == "tops_query_items"
        assert ct.TOPS_COOK_AND_VALIDATE.value == "tops_cook_and_validate"
        assert ct.TOPS_DIAGNOSE.value == "tops_diagnose"
        assert ct.TOPS_PIPELINE_STATUS.value == "tops_pipeline_status"


# ===========================================================================
# TestHandlerRegistration
# ===========================================================================

class TestHandlerRegistration:
    def test_all_tops_handlers_registered(self, handler):
        """All 14 TOPS handlers should be in the command registry."""
        reg = handler._registry
        for cmd in [
            "tops_get_work_items",
            "tops_get_dependency_graph",
            "tops_get_cook_stats",
            "tops_cook_node",
            "tops_generate_items",
            "tops_configure_scheduler",
            "tops_cancel_cook",
            "tops_dirty_node",
            "tops_setup_wedge",
            "tops_batch_cook",
            "tops_query_items",
            "tops_cook_and_validate",
            "tops_diagnose",
            "tops_pipeline_status",
        ]:
            assert reg.has(cmd), f"Handler not registered: {cmd}"

    def test_read_only_commands(self):
        """Read-only TOPS commands should be in the read-only set."""
        from synapse.server.handlers import _READ_ONLY_COMMANDS
        assert "tops_get_work_items" in _READ_ONLY_COMMANDS
        assert "tops_get_dependency_graph" in _READ_ONLY_COMMANDS
        assert "tops_get_cook_stats" in _READ_ONLY_COMMANDS
        assert "tops_query_items" in _READ_ONLY_COMMANDS
        assert "tops_diagnose" in _READ_ONLY_COMMANDS
        assert "tops_pipeline_status" in _READ_ONLY_COMMANDS
        # Mutating commands should NOT be read-only
        assert "tops_cook_node" not in _READ_ONLY_COMMANDS
        assert "tops_generate_items" not in _READ_ONLY_COMMANDS
        assert "tops_configure_scheduler" not in _READ_ONLY_COMMANDS
        assert "tops_cancel_cook" not in _READ_ONLY_COMMANDS
        assert "tops_dirty_node" not in _READ_ONLY_COMMANDS
        assert "tops_setup_wedge" not in _READ_ONLY_COMMANDS
        assert "tops_batch_cook" not in _READ_ONLY_COMMANDS
        assert "tops_cook_and_validate" not in _READ_ONLY_COMMANDS

    def test_audit_categories(self):
        """All TOPS commands should have PIPELINE audit category."""
        from synapse.server.handlers import _CMD_CATEGORY
        from synapse.core.audit import AuditCategory
        for cmd in [
            "tops_get_work_items",
            "tops_get_dependency_graph",
            "tops_get_cook_stats",
            "tops_cook_node",
            "tops_generate_items",
            "tops_configure_scheduler",
            "tops_cancel_cook",
            "tops_dirty_node",
            "tops_setup_wedge",
            "tops_batch_cook",
            "tops_query_items",
            "tops_cook_and_validate",
            "tops_diagnose",
            "tops_pipeline_status",
        ]:
            assert _CMD_CATEGORY[cmd] == AuditCategory.PIPELINE


# ===========================================================================
# TestMCPToolDefs
# ===========================================================================

class TestMCPToolDefs:
    def test_all_tops_tools_in_registry(self):
        """All 14 TOPS tools should appear in mcp/tools.py _TOOL_DEFS."""
        # Import the tools module
        tools_path = _base / "mcp" / "tools.py"
        if "synapse.mcp" not in sys.modules:
            pkg = types.ModuleType("synapse.mcp")
            pkg.__path__ = [str(_base / "mcp")]
            sys.modules["synapse.mcp"] = pkg
        if "synapse.mcp.tools" not in sys.modules:
            spec = importlib.util.spec_from_file_location("synapse.mcp.tools", tools_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["synapse.mcp.tools"] = mod
            spec.loader.exec_module(mod)

        tools_mod = sys.modules["synapse.mcp.tools"]
        tool_names = tools_mod.get_tool_names()

        for name in [
            "tops_get_work_items",
            "tops_get_dependency_graph",
            "tops_get_cook_stats",
            "tops_cook_node",
            "tops_generate_items",
            "tops_configure_scheduler",
            "tops_cancel_cook",
            "tops_dirty_node",
            "tops_setup_wedge",
            "tops_batch_cook",
            "tops_query_items",
            "tops_cook_and_validate",
            "tops_diagnose",
            "tops_pipeline_status",
        ]:
            assert name in tool_names, f"Tool not in MCP registry: {name}"

    def test_tops_tool_annotations(self):
        """Read-only TOPS tools should have readOnlyHint=True."""
        tools_mod = sys.modules["synapse.mcp.tools"]
        tools = {t["name"]: t for t in tools_mod.get_tools()}

        # Read-only tools
        for name in ["tops_get_work_items", "tops_get_dependency_graph",
                      "tops_get_cook_stats", "tops_query_items",
                      "tops_diagnose", "tops_pipeline_status"]:
            assert tools[name]["annotations"]["readOnlyHint"] is True
            assert tools[name]["annotations"]["destructiveHint"] is False

        # Mutating tools
        for name in ["tops_cook_node", "tops_generate_items",
                      "tops_configure_scheduler", "tops_cancel_cook", "tops_dirty_node",
                      "tops_setup_wedge", "tops_batch_cook",
                      "tops_cook_and_validate"]:
            assert tools[name]["annotations"]["readOnlyHint"] is False
            assert tools[name]["annotations"]["destructiveHint"] is True

    def test_tops_tools_have_input_schemas(self):
        """All TOPS tools should have non-empty inputSchema."""
        tools_mod = sys.modules["synapse.mcp.tools"]
        tools = {t["name"]: t for t in tools_mod.get_tools()}

        for name in [
            "tops_get_work_items",
            "tops_get_dependency_graph",
            "tops_get_cook_stats",
            "tops_cook_node",
            "tops_generate_items",
            "tops_configure_scheduler",
            "tops_cancel_cook",
            "tops_dirty_node",
            "tops_setup_wedge",
            "tops_batch_cook",
            "tops_query_items",
            "tops_cook_and_validate",
            "tops_diagnose",
            "tops_pipeline_status",
        ]:
            schema = tools[name]["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema

    def test_tops_dispatch_routes(self):
        """Dispatch should map to correct command types."""
        tools_mod = sys.modules["synapse.mcp.tools"]

        assert tools_mod.has_tool("tops_get_work_items")
        assert tools_mod.has_tool("tops_cook_node")
        assert tools_mod.has_tool("tops_generate_items")
        assert tools_mod.has_tool("tops_configure_scheduler")
        assert tools_mod.has_tool("tops_cancel_cook")
        assert tools_mod.has_tool("tops_dirty_node")
        assert tools_mod.has_tool("tops_setup_wedge")
        assert tools_mod.has_tool("tops_batch_cook")
        assert tools_mod.has_tool("tops_query_items")
        assert tools_mod.has_tool("tops_cook_and_validate")
        assert tools_mod.has_tool("tops_diagnose")
        assert tools_mod.has_tool("tops_pipeline_status")


# ===========================================================================
# TestCookAndValidate (Phase 4)
# ===========================================================================

class TestCookAndValidate:
    def test_success_no_retries(self, handler):
        """All items succeed on first attempt, no retries needed."""
        items = [
            _make_work_item(id=0, state="CookedSuccess", cook_time=1.0),
            _make_work_item(id=1, state="CookedSuccess", cook_time=2.0),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({"node": "/obj/topnet1/gen1"})

        assert result["status"] == "success"
        assert result["total_attempts"] == 1
        assert result["node"] == "/obj/topnet1/gen1"
        assert result["final_by_state"]["CookedSuccess"] == 2
        node.cook.assert_called_once_with(block=True)

    def test_failures_no_retry_configured(self, handler):
        """Items fail but max_retries=0 (default), so no retry happens."""
        items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedFail"),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({"node": "/obj/topnet1/gen1"})

        assert result["status"] == "failed"
        assert result["total_attempts"] == 1
        assert result["attempts"][0]["failed_items"] == 1
        node.cook.assert_called_once()

    def test_retry_succeeds(self, handler):
        """Items fail on first attempt, succeed after retry."""
        fail_items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedFail"),
        ]
        success_items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedSuccess"),
        ]
        pdg_node = _make_pdg_node(fail_items)
        node = _make_top_node(pdg_node=pdg_node)

        # After first cook + dirty, swap work items to success
        def _cook_side_effect(block=True):
            pdg_node.workItems = success_items

        node.cook.side_effect = [None, _cook_side_effect]
        # First cook: fail_items stay. Second cook: success_items appear.
        call_count = [0]
        def _cook(block=True):
            call_count[0] += 1
            if call_count[0] == 2:
                pdg_node.workItems = success_items
        node.cook.side_effect = _cook

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({
                "node": "/obj/topnet1/gen1",
                "max_retries": 1,
            })

        assert result["status"] == "success"
        assert result["total_attempts"] == 2
        assert result["attempts"][0]["status"] == "retry"
        assert result["attempts"][1]["status"] == "success"
        pdg_node.dirty.assert_called_once_with(False)

    def test_retry_exhausted(self, handler):
        """Retries exhausted, still failing."""
        items = [
            _make_work_item(id=0, state="CookedFail"),
            _make_work_item(id=1, state="CookedFail"),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({
                "node": "/obj/topnet1/gen1",
                "max_retries": 2,
            })

        assert result["status"] == "failed"
        assert result["total_attempts"] == 3  # 1 initial + 2 retries
        # First two attempts should be "retry", last should be "failed"
        assert result["attempts"][0]["status"] == "retry"
        assert result["attempts"][1]["status"] == "retry"
        assert result["attempts"][2]["status"] == "failed"

    def test_validate_disabled(self, handler):
        """With validate_states=False, failures don't trigger retries."""
        items = [_make_work_item(id=0, state="CookedFail")]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({
                "node": "/obj/topnet1/gen1",
                "max_retries": 3,
                "validate_states": False,
            })

        # Even though there are failures and retries configured,
        # validate_states=False means we don't check and don't retry
        assert result["total_attempts"] == 1
        # With validation disabled, status comes from failed_count check
        assert result["status"] == "failed"

    def test_kahan_sum_cook_times(self, handler):
        """total_cook_time should use kahan_sum for stability."""
        items = [_make_work_item(id=0, state="CookedSuccess")]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({"node": "/obj/topnet1/gen1"})

        # total_cook_time should be a number (kahan_sum result)
        assert isinstance(result["total_cook_time"], (int, float))
        assert result["total_cook_time"] >= 0

    def test_by_state_sorted(self, handler):
        """by_state dict keys should be sorted (He2025)."""
        items = [
            _make_work_item(id=0, state="CookedSuccess"),
            _make_work_item(id=1, state="CookedFail"),
            _make_work_item(id=2, state="Cooking"),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node(pdg_node=pdg_node)

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_cook_and_validate({"node": "/obj/topnet1/gen1"})

        keys = list(result["final_by_state"].keys())
        assert keys == sorted(keys)

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_cook_and_validate({"node": "/nonexistent"})


# ===========================================================================
# TestDiagnose (Phase 4)
# ===========================================================================

class TestDiagnose:
    def test_mixed_states(self, handler):
        """Diagnose a node with mixed success/failure states."""
        items = [
            _make_work_item(id=0, name="item_0", state="CookedSuccess", cook_time=1.0),
            _make_work_item(id=1, name="item_1", state="CookedFail", cook_time=0.5),
            _make_work_item(id=2, name="item_2", state="CookedSuccess", cook_time=2.0),
            _make_work_item(id=3, name="item_3", state="CookedFail", cook_time=0.1),
        ]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen1", pdg_node=pdg_node)
        node.parent.return_value = _make_top_node("/obj/topnet1", children=[])
        node.inputConnections.return_value = []

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen1"})

        assert result["total_items"] == 4
        assert result["failed_items"] == 2
        assert result["by_state"]["CookedSuccess"] == 2
        assert result["by_state"]["CookedFail"] == 2
        assert len(result["failed_details"]) == 2
        # He2025: failed_details sorted by id
        assert result["failed_details"][0]["id"] == 1
        assert result["failed_details"][1]["id"] == 3

    def test_uncooked_items(self, handler):
        """Node with uncooked items should suggest generating first."""
        items = []
        pdg_node = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen1", pdg_node=pdg_node)
        node.parent.return_value = _make_top_node("/obj/topnet1", children=[])
        node.inputConnections.return_value = []

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen1"})

        assert result["total_items"] == 0
        assert any("No work items" in s for s in result["suggestions"])

    def test_no_items(self, handler):
        """Empty PDG node should report 0 items with a suggestion."""
        pdg_node = _make_pdg_node([])
        node = _make_top_node("/obj/topnet1/gen1", pdg_node=pdg_node)
        node.parent.return_value = _make_top_node("/obj/topnet1", children=[])
        node.inputConnections.return_value = []

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen1"})

        assert result["total_items"] == 0
        assert result["failed_items"] == 0

    def test_upstream_failures(self, handler):
        """Upstream node with failures should generate a suggestion."""
        items = [_make_work_item(id=0, state="CookedFail")]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen2", pdg_node=pdg_node)
        node.parent.return_value = _make_top_node("/obj/topnet1", children=[])

        # Upstream node with failures
        upstream_items = [_make_work_item(id=0, state="CookedFail")]
        upstream_pdg = _make_pdg_node(upstream_items)
        upstream_node = _make_top_node("/obj/topnet1/gen1", pdg_node=upstream_pdg)

        conn = MagicMock()
        conn.inputNode.return_value = upstream_node
        node.inputConnections.return_value = [conn]

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen2"})

        assert len(result["upstream"]) == 1
        assert result["upstream"][0]["has_failures"] is True
        assert any("Upstream node" in s for s in result["suggestions"])

    def test_scheduler_info(self, handler):
        """Scheduler info should be included when include_scheduler=True."""
        items = [_make_work_item(id=0, state="CookedSuccess")]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen1", pdg_node=pdg_node)
        node.inputConnections.return_value = []

        scheduler = MagicMock()
        scheduler.path.return_value = "/obj/topnet1/localscheduler"
        scheduler.type.return_value = _MockNodeType("localscheduler", "Top")
        procs_parm = MagicMock()
        procs_parm.eval.return_value = 4
        scheduler.parm.return_value = procs_parm

        parent = _make_top_node("/obj/topnet1", children=[scheduler, node])
        node.parent.return_value = parent

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen1"})

        assert result["scheduler"] is not None
        assert result["scheduler"]["type"] == "localscheduler"
        assert result["scheduler"]["max_procs"] == 4

    def test_suggestions_sorted(self, handler):
        """Suggestions should be sorted (He2025)."""
        items = [_make_work_item(id=0, state="CookedFail")]
        pdg_node = _make_pdg_node(items)
        node = _make_top_node("/obj/topnet1/gen2", pdg_node=pdg_node)
        node.parent.return_value = _make_top_node("/obj/topnet1", children=[])

        upstream_items = [_make_work_item(id=0, state="CookedFail")]
        upstream_pdg = _make_pdg_node(upstream_items)
        upstream_node = _make_top_node("/obj/topnet1/gen1", pdg_node=upstream_pdg)
        conn = MagicMock()
        conn.inputNode.return_value = upstream_node
        node.inputConnections.return_value = [conn]

        with patch.object(_handlers_hou, "node", return_value=node):
            result = handler._handle_tops_diagnose({"node": "/obj/topnet1/gen2"})

        suggestions = result["suggestions"]
        assert suggestions == sorted(suggestions)

    def test_node_not_found(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            with pytest.raises(ValueError, match="Couldn't find"):
                handler._handle_tops_diagnose({"node": "/nonexistent"})


# ===========================================================================
# TestPipelineStatus (Phase 4)
# ===========================================================================

class TestPipelineStatus:
    def test_healthy_network(self, handler):
        """All nodes healthy -> overall_health='healthy'."""
        items1 = [_make_work_item(id=0, state="CookedSuccess", cook_time=1.0)]
        items2 = [_make_work_item(id=1, state="CookedSuccess", cook_time=2.0)]
        child1 = _make_top_node("/obj/topnet1/gen1", _make_pdg_node(items1),
                                type_name="genericgenerator")
        child2 = _make_top_node("/obj/topnet1/rop1", _make_pdg_node(items2),
                                type_name="ropfetch")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child1, child2])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({"topnet_path": "/obj/topnet1"})

        assert result["overall_health"] == "healthy"
        assert result["node_count"] == 2
        assert result["total_items"] == 2
        assert result["issues"] == []
        assert result["by_state"]["CookedSuccess"] == 2

    def test_network_with_errors(self, handler):
        """Nodes with failures -> overall_health='error', issues populated."""
        items_ok = [_make_work_item(id=0, state="CookedSuccess", cook_time=1.0)]
        items_fail = [
            _make_work_item(id=1, state="CookedSuccess", cook_time=0.5),
            _make_work_item(id=2, state="CookedFail", cook_time=0.2),
        ]
        child1 = _make_top_node("/obj/topnet1/gen1", _make_pdg_node(items_ok),
                                type_name="genericgenerator")
        child2 = _make_top_node("/obj/topnet1/process1", _make_pdg_node(items_fail),
                                type_name="ropfetch")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child1, child2])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({"topnet_path": "/obj/topnet1"})

        assert result["overall_health"] == "error"
        assert len(result["issues"]) == 1
        assert "/obj/topnet1/process1" in result["issues"][0]
        assert len(result["suggestions"]) > 0

    def test_empty_network(self, handler):
        """No work items anywhere -> overall_health='empty'."""
        child1 = _make_top_node("/obj/topnet1/gen1", _make_pdg_node([]),
                                type_name="genericgenerator")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child1])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({"topnet_path": "/obj/topnet1"})

        assert result["overall_health"] == "empty"
        assert result["total_items"] == 0
        assert any("No work items" in s for s in result["suggestions"])

    def test_include_items(self, handler):
        """include_items=True should include per-item details in nodes."""
        items = [
            _make_work_item(id=0, name="item_0", state="CookedSuccess", cook_time=1.0),
            _make_work_item(id=1, name="item_1", state="CookedSuccess", cook_time=2.0),
        ]
        child = _make_top_node("/obj/topnet1/gen1", _make_pdg_node(items),
                               type_name="genericgenerator")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({
                "topnet_path": "/obj/topnet1",
                "include_items": True,
            })

        assert "items" in result["nodes"][0]
        assert len(result["nodes"][0]["items"]) == 2

    def test_nodes_sorted_by_path(self, handler):
        """He2025: nodes list should be sorted by path."""
        child_b = _make_top_node("/obj/topnet1/z_last", _make_pdg_node([]),
                                 type_name="null")
        child_a = _make_top_node("/obj/topnet1/a_first", _make_pdg_node([]),
                                 type_name="null")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child_b, child_a])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({"topnet_path": "/obj/topnet1"})

        paths = [n["path"] for n in result["nodes"]]
        assert paths == sorted(paths)

    def test_skips_schedulers(self, handler):
        """Scheduler nodes should be excluded from the node list."""
        items = [_make_work_item(id=0, state="CookedSuccess")]
        child = _make_top_node("/obj/topnet1/gen1", _make_pdg_node(items),
                               type_name="genericgenerator")
        scheduler = _make_top_node("/obj/topnet1/localscheduler", None,
                                   type_name="localscheduler")
        topnet = _make_top_node("/obj/topnet1", None, "TopNet", "topnet",
                                children=[child, scheduler])

        with patch.object(_handlers_hou, "node", return_value=topnet):
            result = handler._handle_tops_pipeline_status({"topnet_path": "/obj/topnet1"})

        assert result["node_count"] == 1
        node_names = [n["name"] for n in result["nodes"]]
        assert "localscheduler" not in node_names

    def test_not_topnet_error(self, handler):
        """Non-TopNet node should raise ValueError."""
        geo = _make_top_node("/obj/geo1", None, "Object", "geo")
        with patch.object(_handlers_hou, "node", return_value=geo):
            with pytest.raises(ValueError, match="not a TOP network"):
                handler._handle_tops_pipeline_status({"topnet_path": "/obj/geo1"})
