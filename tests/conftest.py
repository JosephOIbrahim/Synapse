"""Shared test fixtures for SYNAPSE test suite.

Provides optional fixtures for common Houdini mocking patterns.
Existing tests that do their own mocking are unaffected -- these
fixtures only activate when explicitly requested by name.
"""

import importlib.util
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
# .pyd binaries, NOT the running build; update these when re-vendoring.
# As of the H22 drop (2026-07-15) BOTH cp311 (H20.5/21.0/21.5) and cp313
# (H22) binaries ship side by side at the same package versions. VENDOR_PY /
# VENDOR_ABI_TAG keep the cp311 primary for existing single-ABI assertions;
# VENDOR_PYS / VENDOR_ABI_TAGS are the full vendored set (keep in lockstep
# with python/synapse/__init__.py's _VENDOR_PYS and the actual _vendor .pyds).
VENDOR_PY = (3, 11)
VENDOR_ABI_TAG = "cp311-win_amd64"
VENDOR_PYS = frozenset({(3, 11), (3, 13)})
VENDOR_ABI_TAGS = ("cp311-win_amd64", "cp313-win_amd64")


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

# The resident at conftest-import time, captured BY OBJECT. Under hython this is
# real Houdini; standalone it is the canonical fake planted just above. Both
# guards below compare against this exact object — identity, never a sentinel.
_HOU_AT_IMPORT = sys.modules.get("hou")

# Test in flight, for attribution. A one-element list so the guard (defined
# before the hooks) reads the live value rather than a stale binding.
_CURRENT_NODEID = ["<collection>"]


# ---------------------------------------------------------------------------
# HOU_REIMPORT_GUARD — `hou.py` must never execute twice in one process
# ---------------------------------------------------------------------------
# VERIFIED-RUNTIME (22.0.368, 2026-07-26): evicting `hou` from sys.modules and
# letting anything `import hou` again is process-corrupting, and it corrupts in
# a way that every obvious check reports as healthy.
#
#   1. `hou.py` re-executes and re-runs `_hou.Parm_swigregister(Parm)` — the C
#      extension's type registry now points at a NEW `Parm` class object.
#   2. `hou.py:123810 __finishImport()` then RAISES (`type object
#      'PerfMonProfile' has no attribute 'save'` — the deprecation wrappers are
#      not re-appliable), so the new class is left HALF-BUILT: 166 attributes
#      against the original's 186, and no `Parm.set`.
#   3. importlib discards the failed module, leaving `sys.modules['hou']`
#      ABSENT. The test then restores the original object — correctly, by
#      object — and only from that moment do `sys.modules['hou']` and
#      `hou.Parm` look perfect again, with `hou.Parm.set` True. (The restore is
#      what manufactures the innocent-looking state; without it the resident is
#      simply gone. VERIFIED-RUNTIME.)
#   4. But `node.parm("x")` now returns an instance of the ZOMBIE class, and
#      `node.parm("x").set(v)` raises
#      `AttributeError: 'Parm' object has no attribute 'set'`.
#
# That is the fake-hou residency defect's second form, and it is why the
# positive control (`hou.Parm.set` -> True) and the failure coexisted: the
# module is innocent, the C-level type registry is the casualty.
#
# Restore-by-OBJECT does not repair it. Nothing does, in-process. The damage is
# done at the moment of the re-import, so the re-import is what must not happen.
#
# TWO ROUTES REACH THIS FINDER, and only one of them involves an eviction:
#
#   (a) `hou` ABSENT from sys.modules, then `import hou`. The original module
#       object survives untouched in whoever still holds a reference; the
#       casualty is the C type registry.
#   (b) `importlib.reload(hou)` with `hou` PRESENT. reload consults meta_path
#       directly, so this finder sees it — and it is the STRICTLY NASTIER route,
#       because reload re-executes into the SAME module namespace: `hou.Parm`
#       itself becomes the zombie (VERIFIED-RUNTIME 2026-07-26: after a raised
#       reload, `hou.Parm is <original>` -> False, `dir()` 166 vs 186, no
#       `.set`). Nothing in the tree reloads `hou` today; the guard covers it by
#       construction and `test_reimport_guard_covers_importlib_reload` pins it,
#       so the coverage is by design rather than by luck.
#
# It hands back the original module object instead of re-executing `hou.py`, and
# RECORDS the offence so the session-finish gate can fail the run naming the
# test that caused it (Law 3: the rescue is never silent).
# `sys.modules["hou"] = None` does NOT reach this finder — CPython raises
# ImportError on a None entry without consulting meta_path (VERIFIED-RUNTIME) —
# so tests that need a deterministic ABSENT `hou` keep working, and that is the
# idiom to use instead of a pop.
class _HouReimportGuard:
    """Return the original `hou` module rather than let `hou.py` run twice."""

    def __init__(self, real_hou):
        self._real = real_hou
        self.interceptions = []  # list[dict]: offender file:line + module name

    def find_spec(self, fullname, path=None, target=None):
        if fullname != "hou":
            return None
        frame = sys._getframe(1)
        # Walk out of importlib's own frames to the code that asked for `hou`.
        while frame is not None and "importlib" in (frame.f_code.co_filename or ""):
            frame = frame.f_back
        self.interceptions.append(
            {
                "offender": f"{frame.f_code.co_filename}:{frame.f_lineno}" if frame else "<unknown>",
                "function": frame.f_code.co_name if frame else "<unknown>",
                # The importer is usually product code doing a lazy `import hou`
                # — the innocent party. The guilty one is whoever left `hou`
                # ABSENT, and that is the test in flight. Naming it is the
                # difference between a report and an actionable report.
                "during": _CURRENT_NODEID[0],
            }
        )
        return importlib.util.spec_from_loader(fullname, _ReturnExistingLoader(self._real))


class _ReturnExistingLoader:
    """Loader that yields an already-initialised module object, unexecuted."""

    def __init__(self, module):
        self._module = module

    def create_module(self, spec):
        return self._module

    def exec_module(self, module):  # already executed, exactly once, at startup
        return None


# Only real, file-backed Houdini needs protecting: the canonical fake is a
# plain ModuleType with no C extension behind it, and re-importing it is a
# no-op rather than a hazard.
HOU_REIMPORT_GUARD = None
if (
    _HOU_AT_IMPORT is not None
    and getattr(_HOU_AT_IMPORT, "__file__", None)
    and not getattr(_HOU_AT_IMPORT, "__synapse_canonical__", False)
):
    HOU_REIMPORT_GUARD = _HouReimportGuard(_HOU_AT_IMPORT)
    sys.meta_path.insert(0, HOU_REIMPORT_GUARD)


# The ONE file permitted to evict `hou` and re-import it: the pin that proves
# the guard works has to trip the guard to prove anything. Every other offender
# fails the run. Kept as an explicit, readable allowlist of one rather than a
# silent exemption.
SANCTIONED_REIMPORTERS = ("tests/test_hou_reimport_guard.py",)


def unsanctioned_hou_reimports(interceptions):
    """Offences from anywhere but the sanctioned exerciser.

    Matched on ``during`` — the test that left `hou` absent — NOT on
    ``offender``. The offender is whichever module happened to execute the lazy
    `import hou` inside the window, and it is usually innocent product code:
    the same eviction was attributed to
    ``python/synapse/panel/designsystem/theme_source.py:45`` in one run and to
    ``python/synapse/memory/store.py:29`` in another. Exempting on the offender
    would therefore exempt a rotating cast of production files while never
    being able to name the test actually responsible.

    Pure function of its argument so the pin can feed it synthetic data and
    prove the gate can fail without corrupting a real process.
    """
    out = []
    for rec in interceptions:
        during = (rec.get("during") or "").replace("\\", "/")
        if any(ok in during for ok in SANCTIONED_REIMPORTERS):
            continue
        out.append(rec)
    return out


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


@pytest.fixture(autouse=True)
def _reset_backend_fallback_telemetry():
    """C-0: the backend-fallback flag in synapse.memory.store is process-global
    by design (the doctor reads it to report a selected-but-not-serving
    backend). In a test session that global would leak one test's simulated
    fallback into a later test's doctor verdict — e.g. the broken-moneta
    ``_make_store`` tests run before the doctor cell tests in the same file.
    Clear it after every test. No-op when the module was never imported."""
    yield
    store_mod = sys.modules.get("synapse.memory.store")
    if store_mod is not None:
        store_mod._BACKEND_FALLBACK = None


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

# Port-wave passthrough transport (ws_passthrough) — zero-`hou`, so importing it
# here is residency-safe. Moved here from test_port_wave_scene1.py's autouse
# fixture (W.8) so EVERY wave test file inherits the reset and can't leak the
# module-level transport or the loop-bound Dispatcher singleton into the next.
try:
    from synapse.cognitive.tools import ws_passthrough as _ws_passthrough
    _WS_PASSTHROUGH_AVAILABLE = True
except ImportError:
    _WS_PASSTHROUGH_AVAILABLE = False

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


if _WS_PASSTHROUGH_AVAILABLE:
    def _reset_ws_passthrough_state():
        """Clear the port-wave transport + the loop-bound Dispatcher singleton.

        Resetting the singleton only when mcp_server is already imported avoids
        forcing that heavy import onto the whole suite: a test that never
        touches the port path never imports mcp_server, so there is no singleton
        to clear; wave test files import it at collection time, so by the time
        this runs the singleton is resettable.
        """
        _ws_passthrough.reset_transport()
        _mcp = sys.modules.get("mcp_server")
        if _mcp is not None:
            _mcp._ported_dispatcher = None

    @pytest.fixture(autouse=True)
    def _ws_passthrough_cleanup_transport():
        """Reset port-wave passthrough state before/after every test.

        ws_passthrough.configure_transport() mutates module-level state and the
        port-wave Dispatcher singleton (mcp_server._ported_dispatcher) captures
        the event loop it was built on. Every wave test runs in a fresh
        asyncio.run loop, so without this reset a stale transport or a
        dead-loop-bound singleton would leak across wave test files — the
        stale-loop leakage this fixture (moved here from test_port_wave_scene1.py
        per W.8) prevents for ALL wave test files.

        No-op for tests that don't touch the port path: reset_transport() is
        idempotent and the singleton reset is skipped when unimported.
        """
        _reset_ws_passthrough_state()
        yield
        _reset_ws_passthrough_state()


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
# ARMED IN BOTH MODES. It previously returned early whenever this conftest had
# not planted — i.e. under hython, the one interpreter where a resident fake is
# a real defect rather than a tidiness question. That is Law 1 inside the guard
# that exists to enforce Law 1: a check that could not fail exactly where the
# failure lives. The guard now compares the resident against `_HOU_AT_IMPORT`
# BY OBJECT, so real Houdini is a first-class protected resident.
# ===========================================================================
def pytest_collection_finish(session):
    if _HOU_AT_IMPORT is None:
        return
    resident = sys.modules.get("hou")
    if resident is _HOU_AT_IMPORT:
        return
    real_hou = not _CANONICAL_HOU_INSTALLED
    raise pytest.UsageError(
        "FAKE_HOU_RESIDENCY_GUARD: sys.modules['hou'] was replaced during "
        "collection and not restored. Exactly one module may own the resident "
        "(this conftest under standalone; real Houdini under hython); every "
        "other module must DEFER to it (`if \"hou\" not in sys.modules`) or "
        "swap and RESTORE THE ORIGINAL OBJECT around its own import — a "
        "sentinel-guarded restore is not a restore, because real `hou` carries "
        "no sentinel.\n"
        f"  expected resident: {_HOU_AT_IMPORT!r}\n"
        f"  actual resident:   {resident!r}\n"
        f"  interpreter:       {'real Houdini (hython)' if real_hou else 'standalone'}\n"
        "See the fake-hou residency trap note at the top of tests/conftest.py."
    )


# ===========================================================================
# HOU_REIMPORT_GUARD enforcement — order-independent, run-level.
# ---------------------------------------------------------------------------
# The guard RESCUES (hands back the original module) so one bad idiom cannot
# corrupt the process for every test after it. Rescuing silently would be Law 3
# exactly — a success status over a thing that went wrong — so the rescue is
# recorded and this hook turns it into a red run naming the offender's
# file:line. Its own negative control lives in tests/test_hou_reimport_guard.py.
# ===========================================================================
def pytest_runtest_logstart(nodeid, location):
    _CURRENT_NODEID[0] = nodeid


def pytest_runtest_logfinish(nodeid, location):
    # Reset, so an offence raised during teardown, a later collection, or at
    # session finish is not attributed to the last test that merely STARTED.
    # A confident wrong file:line is worse than an honest unknown.
    _CURRENT_NODEID[0] = f"<after {nodeid}>"


def pytest_sessionfinish(session, exitstatus):
    # (1) RUN-PHASE residency. pytest_collection_finish above is collection
    # scoped — it cannot see a swap that happens while tests are running, and
    # rt_full_before.json's transitions 3 and 4 were both run-phase. The only
    # other identity assertion is a test, which runs at its own alphabetical
    # slot and therefore cannot observe anything after it. This one is
    # order-independent, which is what the guard's header claims it is.
    if _HOU_AT_IMPORT is not None and sys.modules.get("hou") is not _HOU_AT_IMPORT:
        raise pytest.UsageError(
            "FAKE_HOU_RESIDENCY_GUARD (run phase): sys.modules['hou'] was "
            "replaced during the RUN and never restored. Collection finished "
            "clean, so the offender is a test body or fixture teardown, not an "
            "import.\n"
            f"  expected resident: {_HOU_AT_IMPORT!r}\n"
            f"  actual resident:   {sys.modules.get('hou')!r}\n"
            f"  last test boundary: {_CURRENT_NODEID[0]}\n"
            "Swap and restore THE ORIGINAL OBJECT; express absence as "
            '`sys.modules["hou"] = None`, never a pop.'
        )

    # (2) Re-import offences.
    if HOU_REIMPORT_GUARD is None:
        return
    offences = unsanctioned_hou_reimports(HOU_REIMPORT_GUARD.interceptions)
    if not offences:
        return
    listed = "\n".join(
        f"    during {o.get('during', '?')}\n"
        f"      imported by {o['offender']}  in {o['function']}()"
        for o in offences
    )
    # NOTE ON THE EXIT CODE: raising here ends the run at pytest's
    # EXIT_USAGEERROR (4), not 1. An earlier draft also set
    # `session.exitstatus = 1`; the raise overrides it, so the assignment was
    # dead code that would have misled anyone writing CI logic keyed on
    # `exit == 1`. Gate on non-zero, or on 4 specifically.
    raise pytest.UsageError(
        "HOU_REIMPORT_GUARD: `hou` was evicted from sys.modules and re-imported "
        f"by {len(offences)} site(s). Under hython that re-executes hou.py, "
        "re-registers the SWIG type map to a half-built `Parm` class, and makes "
        "every later `node.parm(...).set(...)` raise AttributeError. The guard "
        "intercepted it so this run stayed sound, but the idiom must go: express "
        'absence as `sys.modules["hou"] = None` (deterministic ImportError, no '
        "re-execution) and restore the prior resident BY OBJECT.\n"
        f"{listed}"
    )


@pytest.fixture(autouse=True)
def _contain_leaked_freeze_chain():
    """Suite-wide net for the R310a zombie class (attack-F followup 2).

    The file-local guard in tests/test_freeze_chain.py protects one file; the
    crucible falsified the lane's 'only place that builds the singleton'
    claim, so the net has to cover every test. Teardown-side and nearly free:
    a sys.modules dict lookup unless the freeze-chain module was actually
    imported.

    CONTAINS rather than fails: a leaked process-wide chain is shut down HERE,
    deterministically, so its ~30s escalation timer can never fire into a
    later, unrelated test (the exact mechanism behind the m3_logs_doctor
    flake). The leak is surfaced as a WARNING naming the offending test --
    visible in -W and the warnings summary -- rather than an error, so
    enumerating current offenders is observation, not a suite-red event.
    Flipping this to a hard fail once offenders are enumerated is the
    recorded followup.
    """
    yield
    import sys as _sys
    fc = _sys.modules.get("synapse.server.freeze_chain")
    if fc is None:
        return
    chain = getattr(fc, "_chain", None)
    if chain is None or getattr(chain, "_stopped", False):
        return
    try:
        fc.shutdown_freeze_chain()
    except Exception:
        pass
    import warnings as _warnings
    _warnings.warn(
        "process-wide FreezeChain left ARMED by this test and shut down by "
        "the conftest net (R310a zombie class) -- add shutdown_freeze_chain() "
        "to the test's teardown",
        RuntimeWarning, stacklevel=2)


# ===========================================================================
# needs_houdini -- the ONE marker for "cannot run without a Houdini runtime"
# ---------------------------------------------------------------------------
# CI0. Stock GitHub runners have neither `hou` (Houdini's Python module, which
# exists only inside a Houdini/hython interpreter) nor `pxr` (OpenUSD). Some
# test modules cannot be collected or run without one of them. This marker
# names that set once, so .github/workflows/ci.yml can say
# `-m "not needs_houdini"` instead of encoding the list in YAML.
#
# THE HONESTY INVARIANT -- why this marker cannot hide a failure:
#
#   A module is marked ONLY when it already refuses to run without its runtime
#   on its own: a module-level `pytest.importorskip("hou"|"pxr")`, an unguarded
#   module-level import, or a module-level `pytestmark` skipif keyed on the
#   runtime. The marker is therefore REDUNDANT with a gate the module already
#   carries -- everything `-m "not needs_houdini"` removes would have skipped
#   anyway. It cannot deselect a test that would otherwise have run and passed.
#   tests/test_needs_houdini_marker.py pins that invariant and goes red if a
#   module is ever marked without its own gate.
#
# Detection is deliberately CONSERVATIVE and AST-based, not grep-based:
#   * a guarded `try: import hou / except ImportError:` is NESTED, not module
#     level, so it does not mark -- those modules run fine here
#   * `import hou` inside a function, or inside a string of code shipped over
#     the wire (tests/test_e2e_tops.py does exactly that), does not mark
#   * a module gated on something OTHER than the runtime -- e.g.
#     tests/test_usd_relationship_live.py gates on $SYNAPSE_H22_LIVE -- does not
#     mark, because "needs a Houdini runtime" would be the wrong reason to show
#     a reader
# Under-marking costs nothing (the module's own gate still skips it, visibly);
# over-marking would hide tests. The bias is set accordingly.
#
# For `hou` specifically: this conftest plants a canonical FAKE `hou` in
# sys.modules, so `import hou` succeeds even on stock Python. The real gate in
# those modules is a `pytestmark` skipif checking for a REAL hou -- that is what
# rule 3 detects. The bare import is not the gate.
# ===========================================================================

_RUNTIME_MODULES = ("hou", "pxr")

# nodeid -> runtime module name, filled during collection and read by the
# terminal-summary reporter so a `-m` deselection is never silent (Law 3).
_NEEDS_HOUDINI: dict = {}
_NEEDS_HOUDINI_DESELECTED: list = []
_MODULE_REQUIREMENT_CACHE: dict = {}


def module_runtime_requirement(source: str):
    """Return "hou"/"pxr" if this test module cannot run without that runtime.

    Module level ONLY -- see the conservatism note above. Public (no leading
    underscore) because tests/test_needs_houdini_marker.py drives it with
    synthetic positive AND negative controls; a detector nothing can disagree
    with is a decoration, not a check (Law 1).
    """
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in tree.body:
        # 1. Unguarded module-level import of the runtime.
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _RUNTIME_MODULES:
                    return root
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            root = node.module.split(".")[0]
            if root in _RUNTIME_MODULES:
                return root

        # 2. Module-level pytest.importorskip("hou"|"pxr") -- the module skips
        #    itself at collection time when the runtime is absent.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute)
                    and call.func.attr == "importorskip"
                    and call.args
                    and isinstance(call.args[0], ast.Constant)
                    and call.args[0].value in _RUNTIME_MODULES):
                return call.args[0].value

        # 3. Module-level `pytestmark = pytest.mark.skipif(<runtime gate>)`.
        if isinstance(node, ast.Assign):
            targets = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if "pytestmark" in targets:
                segment = ast.get_source_segment(source, node.value) or ""
                if "skipif" in segment or "importorskip" in segment:
                    lowered = segment.lower()
                    for runtime in _RUNTIME_MODULES:
                        if runtime in lowered:
                            return runtime
    return None


def _requirement_for_path(path):
    key = str(path)
    if key not in _MODULE_REQUIREMENT_CACHE:
        try:
            with open(key, encoding="utf-8", errors="replace") as handle:
                source = handle.read()
        except OSError:
            _MODULE_REQUIREMENT_CACHE[key] = None
        else:
            _MODULE_REQUIREMENT_CACHE[key] = module_runtime_requirement(source)
    return _MODULE_REQUIREMENT_CACHE[key]


def needs_houdini_reason(runtime: str) -> str:
    """The skip/deselect reason. Names the missing dependency, always."""
    where = {
        "hou": "`hou` (Houdini's Python module -- exists only inside "
               "Houdini/hython, never on a stock interpreter)",
        "pxr": "`pxr` (OpenUSD -- not installed on stock CI runners)",
    }[runtime]
    return f"needs a Houdini runtime: this module requires {where}"


# tryfirst: these marks must exist BEFORE pytest's own `-m` filtering runs in
# its pytest_collection_modifyitems, or the filter has nothing to match on.
@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(session, config, items):
    for item in items:
        path = getattr(item, "path", None) or getattr(item, "fspath", None)
        if path is None:
            continue
        runtime = _requirement_for_path(path)
        if runtime is None:
            continue
        _NEEDS_HOUDINI[item.nodeid] = runtime
        item.add_marker(
            pytest.mark.needs_houdini(runtime, reason=needs_houdini_reason(runtime))
        )


def pytest_deselected(items):
    for item in items:
        runtime = _NEEDS_HOUDINI.get(getattr(item, "nodeid", None))
        if runtime is not None:
            _NEEDS_HOUDINI_DESELECTED.append((item.nodeid, runtime))


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Report the deselected needs_houdini set.

    `-rs` prints skips and their reasons; nothing prints DESELECTIONS, so a
    `-m "not needs_houdini"` run would otherwise drop tests out of the summary
    with no trace at all. That silent hole is exactly what this leg exists to
    close, so the set is printed here with the runtime each module needs.
    """
    if not _NEEDS_HOUDINI_DESELECTED:
        return
    by_module: dict = {}
    for nodeid, runtime in _NEEDS_HOUDINI_DESELECTED:
        module = nodeid.split("::", 1)[0]
        entry = by_module.setdefault(module, [runtime, 0])
        entry[1] += 1
    total = len(_NEEDS_HOUDINI_DESELECTED)
    terminalreporter.write_sep(
        "=", "needs_houdini deselected (NOT silently dropped)", yellow=True)
    for module in sorted(by_module):
        runtime, count = by_module[module]
        terminalreporter.line(
            f"NEEDS_HOUDINI  {module}  [{count} test(s)]"
            f"  -- {needs_houdini_reason(runtime)}")
    terminalreporter.line(
        f"{total} test(s) in {len(by_module)} module(s) deselected by "
        f"-m 'not needs_houdini'. Run the full suite under hython "
        f"(pytest tests/, no -m filter) to execute them.")
