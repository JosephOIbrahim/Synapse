"""FORGE C4 — Tests for the modern Copernicus 'copnet' handler.

Covers the single new Foundation handler `_handle_cops_create_copnet` added
to CopsHandlerMixin. This handler builds an H21 Copernicus 'copnet' network
container (distinct from the legacy 'cop2net' used by the 20 existing tools).

Structural only — NO behavioral/cook assertions. The live Synapse bridge is
down, so whether the copnet cooks through Karma XPU is DEFERRED. These tests
assert that the handler requests a 'copnet' node type and returns a node path.

Mock-based -- no Houdini required. Bootstrap mirrors tests/test_cops.py.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: hou stub (mirrors tests/test_cops.py lines 25-54)
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
    _hdefereval.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    # executeDeferred: call fn immediately (run_on_main uses this + threading.Event)
    _hdefereval.executeDeferred = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]
    if not hasattr(_hdefereval, "executeInMainThreadWithResult"):
        _hdefereval.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    if not hasattr(_hdefereval, "executeDeferred"):
        _hdefereval.executeDeferred = lambda fn, *a, **k: fn(*a, **k)

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

# Get the hou reference from handlers_cops.py (where the handler actually
# resolves nodes -- patch THIS one, not the test-local _hou).
_cops_mod = sys.modules.get("synapse.server.handlers_cops")
_handlers_hou = _cops_mod.hou if _cops_mod else handlers_mod.hou

if not hasattr(_handlers_hou, "node"):
    _handlers_hou.node = MagicMock()


# ---------------------------------------------------------------------------
# Mock helpers (single-purpose, copnet-focused)
# ---------------------------------------------------------------------------

class _MockCategory:
    def __init__(self, name="Cop"):
        self._name = name

    def name(self):
        return self._name


class _MockNodeType:
    def __init__(self, name="copnet", category="Cop"):
        self._name = name
        self._cat = _MockCategory(category)

    def name(self):
        return self._name

    def category(self):
        return self._cat


def _make_node(path, type_name):
    """Create a generic mock node with .path() and .type().name()."""
    node = MagicMock()
    node.path.return_value = path
    node.name.return_value = path.rsplit("/", 1)[-1]
    node.type.return_value = _MockNodeType(type_name)
    node.moveToGoodPosition = MagicMock()
    node.children.return_value = []
    return node


def _make_copnet(path="/obj/copnet1"):
    """Create a mock 'copnet' network whose createNode yields child COP nodes."""
    net = _make_node(path, "copnet")

    def _create_child(node_type, name=None):
        child_name = name or node_type
        return _make_node(f"{path}/{child_name}", node_type)

    net.createNode = MagicMock(side_effect=_create_child)
    return net


def _make_parent_node(path="/obj", net_path="/obj/copnet1"):
    """Create a mock parent. createNode('copnet', ...) returns a copnet mock."""
    parent = MagicMock()
    parent.path.return_value = path

    def _create_node(node_type, name=None):
        if node_type == "copnet":
            return _make_copnet(net_path)
        child_name = name or node_type
        return _make_node(f"{path}/{child_name}", node_type)

    parent.createNode = MagicMock(side_effect=_create_node)
    return parent


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def handler():
    """SynapseHandler instance.

    INTEGRATOR registers 'cops_create_copnet' in handlers.py during the merge
    phase. During this parallel build phase the registration may not yet be
    wired, so we self-register the method onto the instance registry if absent.
    This keeps the test green standalone and stays correct once wired.
    """
    h = handlers_mod.SynapseHandler()
    if h._registry.get("cops_create_copnet") is None:
        h._registry.register("cops_create_copnet", h._handle_cops_create_copnet)
    return h


def _cmd(payload, cmd_id="forge-copnet"):
    return handlers_mod.SynapseCommand(
        type="cops_create_copnet", id=cmd_id, payload=payload
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCopsCreateCopnet:
    def test_create_copnet_requests_copnet_node_type(self, handler):
        """KEY ASSERTION: the handler asks the parent for a 'copnet' node."""
        parent = _make_parent_node("/obj", "/obj/copnet1")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(_cmd({"parent": "/obj", "name": "copnet1"}))
        assert result.success, result.error
        # First positional arg of the network creation must be 'copnet'.
        first_call = parent.createNode.call_args_list[0]
        assert first_call.args[0] == "copnet"
        parent.createNode.assert_any_call("copnet", "copnet1")

    def test_create_copnet_returns_node_path(self, handler):
        parent = _make_parent_node("/obj", "/obj/copnet1")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(_cmd({"parent": "/obj", "name": "copnet1"}))
        assert result.success, result.error
        assert "network_path" in result.data
        assert result.data["network_path"] == "/obj/copnet1"
        assert result.data["type"] == "copnet"

    def test_create_copnet_default_parent_and_name(self, handler):
        """Empty payload -> default parent '/obj', default name 'copnet'."""
        parent = _make_parent_node("/obj", "/obj/copnet")
        with patch.object(_handlers_hou, "node", return_value=parent) as p:
            result = handler.handle(_cmd({}))
        assert result.success, result.error
        # parent resolved from default '/obj'
        p.assert_called_with("/obj")
        first_call = parent.createNode.call_args_list[0]
        assert first_call.args[0] == "copnet"   # node type
        assert first_call.args[1] == "copnet"   # default name

    def test_create_copnet_bad_parent(self, handler):
        with patch.object(_handlers_hou, "node", return_value=None):
            result = handler.handle(_cmd({"parent": "/nonexistent"}))
        assert not result.success
        assert "Couldn't find" in result.error

    def test_create_copnet_with_starter(self, handler):
        """Optional starter creates one child inside the new copnet."""
        net = _make_copnet("/obj/copnet1")
        parent = MagicMock()
        parent.path.return_value = "/obj"
        parent.createNode = MagicMock(return_value=net)
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(_cmd({"starter": "null"}))
        assert result.success, result.error
        # The network (not the parent) created the starter child.
        net.createNode.assert_any_call("null")
        assert isinstance(result.data["starter_node"], str)
        assert result.data["starter_node"] == "/obj/copnet1/null"

    def test_create_copnet_no_starter_is_none(self, handler):
        parent = _make_parent_node("/obj", "/obj/copnet1")
        with patch.object(_handlers_hou, "node", return_value=parent):
            result = handler.handle(_cmd({"parent": "/obj"}))
        assert result.success, result.error
        assert result.data["starter_node"] is None
