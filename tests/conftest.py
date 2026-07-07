"""Shared test fixtures for SYNAPSE test suite.

Provides optional fixtures for common Houdini mocking patterns.
Existing tests that do their own mocking are unaffected -- these
fixtures only activate when explicitly requested by name.
"""

import os
import pytest
import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Single-source build constants (runway §1.3 — the dual-build H21/H22 axis)
# ---------------------------------------------------------------------------
# Tests that pin against the RUNNING build parametrize on HOUDINI_BUILD.
# Tests that pin a COMMITTED artifact (e.g. the introspected H21 symbol
# table's stamp, the cp311 vendor .pyd) keep their own literals / the
# VENDOR_* constants so they track the artifact, not the env.

HOUDINI_BUILD = os.environ.get("SYNAPSE_TEST_HOUDINI_BUILD", "21.0.671")
HOUDINI_BUILD_TUPLE = tuple(int(p) for p in HOUDINI_BUILD.split("."))

# Vendored-dependency ABI (python/synapse/_vendor) — tracks the committed
# .pyd binary, NOT the running build; update these when re-vendoring.
VENDOR_PY = (3, 11)
VENDOR_ABI_TAG = "cp311-win_amd64"


# ---------------------------------------------------------------------------
# Canonical fake `hou` — the ONE authoritative sys.modules['hou'] planter
# ---------------------------------------------------------------------------
# Historically 56 test modules each planted their own sys.modules['hou'] fake
# at import time. 41 did so CONDITIONALLY (`if "hou" not in sys.modules`) and
# deferred to whoever planted first; 7 planted UNCONDITIONALLY and clobbered
# the resident mid-collection. Because pytest imports every test module during
# collection, the surviving resident — and thus which fake each handler module
# bound its `hou` global to — depended on collection ORDER. That is the fake-hou
# residency trap (docs/HARDENING_RUN_2026-06-10.md): green locally, red in CI,
# false-green evals when a diverging fake wins the race.
#
# conftest.py is imported before any test module is collected, so planting one
# canonical fake here makes it the authoritative resident. Conditional planters
# see it present and defer; the (converted) unconditional planters swap it in
# only to bind their module-under-test, then RESTORE this canonical object. The
# pytest_collection_finish guard at the bottom of this file fails the run if the
# canonical resident was replaced by a rogue unconditional planter.
#
# Under real Houdini (hython) `hou` is already resident, so we never plant and
# the guard is a no-op — real hou owns the module.

def _build_canonical_hou():
    """A permissive, superset fake `hou` shared by the whole standalone suite."""
    hou = types.ModuleType("hou")
    hou.__synapse_canonical__ = True  # sentinel the residency guard checks

    # Real types: isinstance() / `except` targets must be genuine classes.
    hou.OperationFailed = type("OperationFailed", (Exception,), {})
    hou.LoadWarning = type("LoadWarning", (Exception,), {})
    hou.NodeError = type("NodeError", (Exception,), {})
    for _t in ("Node", "LopNode", "SopNode", "ObjNode", "RopNode", "CopNode",
               "LopNetwork", "NodeType", "Parm", "ParmTuple", "Geometry"):
        setattr(hou, _t, type(_t, (), {}))

    class _Keyframe:
        def __init__(self, *a, **k):
            self._frame, self._value, self._expr = 0, 0.0, None
        def setFrame(self, f): self._frame = f
        def setValue(self, v): self._value = v
        def setExpression(self, *a, **k): self._expr = a[0] if a else None
        def frame(self): return self._frame
        def value(self): return self._value
    hou.Keyframe = _Keyframe

    # Parm templates (constructed by HDA-building code).
    for _pt in ("FolderParmTemplate", "StringParmTemplate", "FloatParmTemplate",
                "IntParmTemplate", "ToggleParmTemplate", "MenuParmTemplate",
                "FolderSetParmTemplate", "ParmTemplateGroup", "RampParmTemplate"):
        setattr(hou, _pt, MagicMock(name=_pt))

    # Numeric / string scalars that code reads and compares.
    hou.frame = MagicMock(return_value=1.0)
    hou.fps = MagicMock(return_value=24.0)
    hou.hscriptExpression = MagicMock(return_value="untitled")
    hou.applicationVersion = MagicMock(return_value=(21, 0, 671))
    hou.applicationVersionString = MagicMock(return_value="21.0.671")

    # Scene access.
    hou.node = MagicMock(return_value=None)
    hou.nodeType = MagicMock(return_value=None)
    hou.selectedNodes = MagicMock(return_value=[])
    hou.pwd = MagicMock(return_value=None)
    hou.undos = MagicMock()  # undos.group(...) is an auto context manager
    hou.hipFile = MagicMock()
    hou.hipFile.path = MagicMock(return_value="/tmp/untitled.hip")
    hou.hipFile.name = MagicMock(return_value="untitled.hip")
    hou.text = MagicMock()
    hou.text.expandString = MagicMock(side_effect=lambda s, *a, **k: s)
    hou.hda = MagicMock()
    hou.playbar = MagicMock()
    hou.playbar.frameRange = MagicMock(return_value=(1, 240))
    hou.playbar.playbackRange = MagicMock(return_value=(1, 240))

    # UI surface (headless-safe stubs).
    hou.ui = MagicMock()
    hou.ui.paneTabs = MagicMock(return_value=[])
    hou.paneTabType = MagicMock()
    hou.paneTabType.SceneViewer = "SceneViewer"
    hou.paneTabType.NetworkEditor = "NetworkEditor"
    hou.paneTabType.PythonPanel = "PythonPanel"

    # Enums referenced by name.
    hou.exprLanguage = types.SimpleNamespace(Hscript="hscript", Python="python")
    hou.scriptLanguage = types.SimpleNamespace(Hscript="hscript", Python="python")
    hou.severityType = types.SimpleNamespace(
        Message="message", ImportantMessage="importantmessage",
        Warning="warning", Error="error", Fatal="fatal")
    return hou


_CANONICAL_HOU_INSTALLED = False
if "hou" not in sys.modules:
    sys.modules["hou"] = _build_canonical_hou()
    _CANONICAL_HOU_INSTALLED = True


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


# ===========================================================================
# Inspector subsystem fixtures (added Sprint 2 Week 1, 2026-04-18)
# ---------------------------------------------------------------------------
# These fixtures support tests/test_inspect_mock.py and
# tests/test_inspect_live.py.
#
# Safety notes for the existing SYNAPSE test suite:
#   - The _cleanup_transport fixture below is autouse — it calls
#     reset_transport() before/after every test in the session.
#     It has no effect on tests that do not use the Inspector's
#     transport registration (i.e. every existing test), because
#     reset_transport() is a no-op when no transport is configured.
#   - All other Inspector fixtures are opt-in by name.
#
# If the synapse.inspector module is unavailable (e.g. during a
# partial install or pre-merge state), the import fails gracefully
# and the Inspector fixtures simply don't register. Existing tests
# continue to collect and run as normal.
# ===========================================================================

import json as _inspector_json
from pathlib import Path as _InspectorPath

try:
    from synapse.inspector import reset_transport as _inspector_reset_transport
    _INSPECTOR_AVAILABLE = True
except ImportError:
    _INSPECTOR_AVAILABLE = False

# Fixture file paths — resolved relative to this conftest.py
_INSPECTOR_FIXTURES_DIR = _InspectorPath(__file__).parent / "fixtures"
_INSPECTOR_GOLDEN_JSON_PATH = (
    _INSPECTOR_FIXTURES_DIR / "inspector_week1_flat.golden.json"
)
_INSPECTOR_GOLDEN_HIP_PATH = (
    _INSPECTOR_FIXTURES_DIR / "inspector_week1_flat.hip"
)


if _INSPECTOR_AVAILABLE:
    @pytest.fixture(autouse=True)
    def _inspector_cleanup_transport():
        """Reset Inspector global transport state before/after every test.

        The Inspector's configure_transport() mutates module-level state.
        Without cleanup, a test that calls configure_transport() would
        leak its transport to subsequent tests.

        This fixture is a no-op for tests that don't touch the Inspector
        transport registration (i.e. every existing SYNAPSE test).
        """
        _inspector_reset_transport()
        yield
        _inspector_reset_transport()


@pytest.fixture
def golden_json_str() -> str:
    """Raw JSON content of the Inspector golden fixture file.

    Used by tests/test_inspect_mock.py.
    """
    assert _INSPECTOR_GOLDEN_JSON_PATH.exists(), (
        f"Inspector golden fixture missing: {_INSPECTOR_GOLDEN_JSON_PATH}. "
        "Did you delete it accidentally?"
    )
    return _INSPECTOR_GOLDEN_JSON_PATH.read_text(encoding="utf-8")


@pytest.fixture
def golden_payload(golden_json_str: str) -> dict:
    """Parsed Inspector golden payload dict."""
    return _inspector_json.loads(golden_json_str)


@pytest.fixture
def mock_transport(golden_json_str: str):
    """Mock Inspector transport that always returns the golden JSON.

    Usage:
        def test_something(mock_transport):
            ast = synapse_inspect_stage(execute_python_fn=mock_transport)
            assert len(ast) == 8
    """

    def _transport(code: str, *, timeout=None) -> str:
        return golden_json_str

    return _transport


@pytest.fixture
def mock_transport_legacy(golden_json_str: str):
    """Mock Inspector transport WITHOUT the timeout kwarg (legacy signature).

    Used to verify the Inspector's graceful fallback when the configured
    transport predates timeout support.
    """

    def _transport(code: str) -> str:
        return golden_json_str

    return _transport


def make_mock_transport(response: str):
    """Helper for Inspector tests that need custom response content.

    Not a fixture — use directly:

        transport = make_mock_transport('{"synapse_error": "stage_not_found"}')
        with pytest.raises(StageNotFoundError):
            synapse_inspect_stage(execute_python_fn=transport)
    """

    def _transport(code: str, *, timeout=None) -> str:
        return response

    return _transport


# ===========================================================================
# Cognitive-layer Dispatcher fixture (added Sprint 3 Spike 1.0, 2026-04-20)
# ---------------------------------------------------------------------------
# Session-scoped, opt-in by name (NO autouse). Existing 2606 tests do not
# request this fixture and are unaffected by its presence — pytest only
# instantiates a fixture the first time a test asks for it by parameter name.
# ===========================================================================


@pytest.fixture(scope="session")
def dispatcher():
    """Session-scoped Dispatcher in test-mode bypass.

    Invariant 1 (SPRINT3): the Dispatcher MUST expose ``is_testing=True``
    that runs synchronously on the calling thread, bypassing
    ``hdefereval.executeInMainThreadWithResult``. Headless ``hython`` and
    stock pytest CI both lack a Qt event loop to pump, so anything that
    depends on it hangs forever.

    Tests opt in by requesting the fixture by name::

        def test_something(dispatcher):
            dispatcher.register('tool', lambda: {'ok': True})
            result = dispatcher.execute('tool', {})
            assert result == {'ok': True}
    """
    from synapse.cognitive.dispatcher import Dispatcher
    return Dispatcher(is_testing=True)


# ===========================================================================
# FAKE_HOU_RESIDENCY_GUARD — exactly one module may plant sys.modules['hou'].
# ---------------------------------------------------------------------------
# The canonical fake above is the single authoritative planter. Every test
# module must DEFER to it (`if "hou" not in sys.modules`) or temporarily swap
# it in only to bind its module-under-test and then RESTORE it. This hook runs
# once, after collection has imported every test module, and fails the run if
# the canonical resident was replaced by a rogue unconditional planter — the
# collection-order-dependent residency that the guard exists to prevent.
#
# No-op under real Houdini (hython): we never planted, so there is nothing to
# guard — real hou legitimately owns sys.modules['hou'].
# ===========================================================================
def pytest_collection_finish(session):
    if not _CANONICAL_HOU_INSTALLED:
        return
    resident = sys.modules.get("hou")
    if resident is None:
        return
    if not getattr(resident, "__synapse_canonical__", False):
        raise pytest.UsageError(
            "FAKE_HOU_RESIDENCY_GUARD: sys.modules['hou'] was replaced by a "
            "non-canonical planter during collection. Exactly one module (this "
            "conftest) may plant hou; every other module must DEFER to it "
            "(`if \"hou\" not in sys.modules`) or swap-and-RESTORE around its "
            f"own import. Offending resident: {resident!r}. See the fake-hou "
            "residency trap note at the top of tests/conftest.py."
        )
