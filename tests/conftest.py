"""Shared test fixtures for SYNAPSE test suite.

Provides optional fixtures for common Houdini mocking patterns.
Existing tests that do their own mocking are unaffected -- these
fixtures only activate when explicitly requested by name.
"""

import pytest
import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Mock Houdini parameter
# ---------------------------------------------------------------------------

class _MockParm:
    """Lightweight mock for hou.Parm with get/set semantics."""

    def __init__(self, name, value=None):
        self._name = name
        self._value = value

    def name(self):
        return self._name

    def set(self, value):
        self._value = value

    def eval(self):
        return self._value

    def evalAsString(self):
        return str(self._value) if self._value is not None else ""


# ---------------------------------------------------------------------------
# Mock Houdini node
# ---------------------------------------------------------------------------

class _MockNode:
    """Mock for hou.Node with children, parms, connections."""

    def __init__(self, path, type_name="null", parent=None):
        self._path = path
        self._type_name = type_name
        self._parent = parent
        self._children = {}
        self._parms = {}
        self._inputs = []
        self._outputs = []
        self._name = path.rsplit("/", 1)[-1] if "/" in path else path
        self._cook_count = 0
        self._session_id = id(self) & 0xFFFFFF
        self._user_data = {}

    # Identity
    def path(self):
        return self._path

    def name(self):
        return self._name

    def type(self):
        mock_type = MagicMock()
        mock_type.name.return_value = self._type_name
        return mock_type

    def parent(self):
        return self._parent

    # H21 scene hash primitives
    def sessionId(self):
        return self._session_id

    def cookCount(self):
        return self._cook_count

    def geometry(self):
        return None  # Override in tests that need geo

    # Tree
    def children(self):
        return list(self._children.values())

    def createNode(self, type_name, name=None):
        node_name = name or type_name
        child_path = f"{self._path}/{node_name}"
        child = _MockNode(child_path, type_name, parent=self)
        self._children[node_name] = child
        return child

    def node(self, relative_path):
        return self._children.get(relative_path)

    # Connections
    def setInput(self, index, node):
        while len(self._inputs) <= index:
            self._inputs.append(None)
        self._inputs[index] = node
        if node and hasattr(node, "_outputs"):
            node._outputs.append(self)

    def inputs(self):
        return [i for i in self._inputs if i is not None]

    def outputs(self):
        return self._outputs

    def dependents(self):
        return self._outputs

    # Parameters
    def parm(self, name):
        return self._parms.get(name)

    def parms(self):
        return list(self._parms.values())

    # User data
    def setUserData(self, key, value):
        self._user_data[key] = value

    def userData(self, key):
        return self._user_data.get(key)

    # Layout stubs
    def layoutChildren(self):
        pass

    def moveToGoodPosition(self):
        pass

    def destroy(self):
        if self._parent and self._name in self._parent._children:
            del self._parent._children[self._name]

    def allSubChildren(self):
        result = []
        for child in self._children.values():
            result.append(child)
            if hasattr(child, "allSubChildren"):
                result.extend(child.allSubChildren())
        return result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_node():
    """Provide a configurable mock Houdini node.

    Returns a factory: call it with (path, type_name) to get a node.
    """
    def _factory(path="/obj/geo1", type_name="null"):
        return _MockNode(path, type_name)
    return _factory


@pytest.fixture
def mock_hou():
    """Provide a mock hou module with common API surface.

    The mock is NOT injected into sys.modules -- tests that need
    module-level injection should do that themselves.
    """
    m = MagicMock()
    root = _MockNode("/obj", "obj")
    m.node.side_effect = lambda path: root if path == "/obj" else None
    m.undos.group.side_effect = lambda name="": _MockUndoCtx()
    m.undos.performUndo = MagicMock()
    m.hipFile.path.return_value = "/tmp/test.hip"
    m.frame.return_value = 1.0
    m.fps.return_value = 24.0
    m.selectedNodes.return_value = []
    m.LopNode = type("LopNode", (), {})  # Sentinel for isinstance checks
    m._root_node = root  # Expose for test setup
    return m


class _MockUndoCtx:
    """Context manager that mimics hou.undos.group()."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@pytest.fixture
def mock_undo_group():
    """Mock hou.undos.group() context manager."""
    return _MockUndoCtx
