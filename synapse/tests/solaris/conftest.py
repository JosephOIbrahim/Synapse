"""
Shared test fixtures for RELAY-SOLARIS tool tests.

Provides mock Houdini objects and path-based imports for tool modules
that live outside the installable python/synapse/ package tree.
"""

import pytest
import sys
import os
import importlib.util
from unittest.mock import MagicMock
from pathlib import Path

# ---------------------------------------------------------------------------
# Path-based import helper — tools live in synapse/mcp/tools/solaris/
# which is NOT inside the python/synapse/ package tree.
# ---------------------------------------------------------------------------

_TOOLS_DIR = Path(__file__).resolve().parents[2] / "mcp" / "tools" / "solaris"


def _import_tool(module_name: str):
    """Import a tool module by filename from synapse/mcp/tools/solaris/."""
    spec = importlib.util.spec_from_file_location(
        f"solaris_tools.{module_name}",
        _TOOLS_DIR / f"{module_name}.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Pre-import all tool modules and register them in sys.modules
# so test files can use normal `from ... import ...` syntax.
for _name in [
    "component_builder", "import_megascans", "scene_template",
    "create_variants", "set_purpose",
]:
    _key = f"synapse.mcp.tools.solaris.{_name}"
    if _key not in sys.modules:
        try:
            sys.modules[_key] = _import_tool(_name)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Mock Houdini fixtures
# ---------------------------------------------------------------------------

class MockParm:
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


class MockNodeType:
    def __init__(self, name, category_name="Lop"):
        self._name = name
        self._category_name = category_name
    def name(self):
        return self._name
    def category(self):
        m = MagicMock()
        m.name.return_value = self._category_name
        return m


class MockNode:
    def __init__(self, path, type_name="null", parent=None):
        self._path = path
        self._type = MockNodeType(type_name)
        self._parent = parent
        self._children = {}
        self._parms = {}
        self._inputs = []
        self._outputs = []
        self._user_data = {}
        self._name = path.rsplit("/", 1)[-1] if "/" in path else path

    def path(self):
        return self._path
    def name(self):
        return self._name
    def setName(self, name, unique_name=False):
        self._name = name
    def type(self):
        return self._type
    def parent(self):
        return self._parent
    def children(self):
        return list(self._children.values())
    def node(self, relative_path):
        return self._children.get(relative_path)
    def createNode(self, type_name, name=None):
        node_name = name or type_name
        child_path = f"{self._path}/{node_name}"
        child = MockNode(child_path, type_name, parent=self)
        child._parms = _default_parms(type_name)
        self._children[node_name] = child
        return child
    def parm(self, name):
        return self._parms.get(name)
    def parms(self):
        return list(self._parms.values())
    def setInput(self, index, node):
        while len(self._inputs) <= index:
            self._inputs.append(None)
        self._inputs[index] = node
        if node and hasattr(node, '_outputs'):
            node._outputs.append(self)
    def inputs(self):
        return [i for i in self._inputs if i is not None]
    def outputs(self):
        return self._outputs
    def setUserData(self, key, value):
        self._user_data[key] = value
    def userData(self, key):
        return self._user_data.get(key)
    def layoutChildren(self):
        pass
    def moveToGoodPosition(self):
        pass
    def isNetwork(self):
        return len(self._children) > 0
    def destroy(self):
        if self._parent and self._name in self._parent._children:
            del self._parent._children[self._name]


def _default_parms(type_name):
    common = {
        "primitive": {"primpath": MockParm("primpath"), "primtype": MockParm("primtype"), "primkind": MockParm("primkind")},
        "sopimport": {"soppath": MockParm("soppath"), "primpath": MockParm("primpath")},
        "camera": {"primpath": MockParm("primpath")},
        "materiallibrary": {"primpath": MockParm("primpath")},
        "karmaphysicalsky": {"primpath": MockParm("primpath")},
        "karmarendersettings": {"engine": MockParm("engine"), "resx": MockParm("resx"), "resy": MockParm("resy"), "camera": MockParm("camera")},
        "usdrender_rop": {"outputimage": MockParm("outputimage")},
        "componentgeometry": {"soppath": MockParm("soppath"), "purpose": MockParm("purpose")},
        "componentmaterial": {},
        "componentoutput": {"name": MockParm("name"), "filepath": MockParm("filepath")},
        "componentgeometryvariants": {},
        "explorevariants": {},
        "subnet": {},
        "reference": {"filepath1": MockParm("filepath1"), "primpath": MockParm("primpath"), "destpath": MockParm("destpath")},
        "usdimport": {"filepath": MockParm("filepath"), "unpacktopolygons": MockParm("unpacktopolygons")},
        "xform": {"scale": MockParm("scale"), "rx": MockParm("rx"), "ry": MockParm("ry"), "rz": MockParm("rz")},
        "matchsize": {"justifyy": MockParm("justifyy")},
        "polyreduce": {"percentage": MockParm("percentage")},
        "output": {},
    }
    return common.get(type_name, {})


class MockUndoGroup:
    def __init__(self, name=""):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *a):
        pass


@pytest.fixture
def mock_stage():
    return MockNode("/stage", "lopnet")


@pytest.fixture
def mock_hou(mock_stage):
    m = MagicMock()
    m.node.side_effect = lambda path: mock_stage if path == "/stage" else None
    m.undos.group.side_effect = lambda name="": MockUndoGroup(name)
    m.lopNodeTypeCategory.return_value = MagicMock()
    m.nodeType.return_value = None
    m.copyNodesTo = lambda nodes, parent: [
        parent.createNode(n.type().name(), f"{n.name()}_copy") for n in nodes
    ]
    return m
