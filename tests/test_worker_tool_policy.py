"""Tests for the autonomous-worker tool ALLOWLIST gate (CTO deferred-item #1).

Two layers, both pure-Python (no live QThread, no hou):

  1. Policy/advertise layer -- ``worker_policy.is_tool_allowed_for_worker`` and
     ``tool_bridge.get_anthropic_tools_for_worker``. These import cleanly
     headlessly; no Qt required.

  2. Dispatch-side enforcement -- the load-bearing check inside
     ``ClaudeWorker._execute_tool_block``. ``claude_worker`` imports PySide at
     module load and subclasses QThread, so the dispatch test installs minimal
     PySide stubs via a fixture that RESTORES ``sys.modules`` on teardown (no
     leak into sibling panel tests). We never start a real thread -- we call the
     method directly on an instance.
"""

import importlib
import os
import sys
import types
from unittest.mock import MagicMock

import pytest

# Ensure THIS worktree's synapse.panel submodules win. An editable install
# elsewhere may have bound ``synapse`` to a sibling checkout that lacks the new
# worker_policy module (and the new get_anthropic_tools_for_worker in
# tool_bridge). The editable finder resolves ``synapse`` ahead of plain
# sys.path dirs, so we can't win by ordering alone. Instead we make the
# existing ``synapse.panel`` package ALSO search this worktree's panel dir
# (prepended) and drop the panel submodules under test so they reload from the
# worktree copy. ``synapse`` top and other subtrees are left untouched -- sibling
# tests (e.g. test_mcp_roundtrip) build those by hand and must not be disturbed.
_PYTHON_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"
)
if sys.path and sys.path[0] != _PYTHON_DIR:
    sys.path.insert(0, _PYTHON_DIR)

_WORKTREE_PANEL_DIR = os.path.join(_PYTHON_DIR, "synapse", "panel")

if "synapse.panel.worker_policy" not in sys.modules:
    # Import the panel package (the editable finder resolves ``synapse`` ahead
    # of plain sys.path dirs, so we can't win by ordering alone) and extend its
    # __path__ to ALSO search this worktree's panel dir. The new submodules then
    # resolve from the worktree copy. ``synapse`` top and other subtrees are not
    # otherwise mutated.
    import synapse.panel as _panel_pkg  # noqa: E402

    _ppath = getattr(_panel_pkg, "__path__", None)
    if _ppath is not None and _WORKTREE_PANEL_DIR not in list(_ppath):
        _ppath.insert(0, _WORKTREE_PANEL_DIR)
    # Drop the specific panel submodules this test depends on so they reload
    # from the worktree copy (carrying the new code under test).
    for _name in (
        "synapse.panel.tool_bridge",
        "synapse.panel.claude_worker",
        "synapse.panel.worker_policy",
    ):
        sys.modules.pop(_name, None)

from synapse.panel.worker_policy import (  # noqa: E402
    _ENV_VAR,
    denial_tool_result,
    is_tool_allowed_for_worker,
)
from synapse.panel.tool_bridge import (  # noqa: E402
    get_anthropic_tools,
    get_anthropic_tools_for_worker,
)


# ---------------------------------------------------------------------------
# Env isolation: every test runs with a clean, default ('standard') mode unless
# it explicitly sets the var. Restores whatever was there before.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _clean_worker_mode_env():
    prev = os.environ.get(_ENV_VAR)
    os.environ.pop(_ENV_VAR, None)
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop(_ENV_VAR, None)
        else:
            os.environ[_ENV_VAR] = prev


# ===========================================================================
# Policy layer: is_tool_allowed_for_worker (standard / default mode)
# ===========================================================================

def test_execute_python_denied_under_standard():
    allowed, reason = is_tool_allowed_for_worker("houdini_execute_python")
    assert allowed is False
    assert reason  # non-empty explanation


def test_execute_vex_denied_under_standard():
    allowed, _ = is_tool_allowed_for_worker("houdini_execute_vex")
    assert allowed is False


@pytest.mark.parametrize("tool", ["synapse_ping", "houdini_get_parm"])
def test_read_only_tools_allowed(tool):
    allowed, _ = is_tool_allowed_for_worker(tool)
    assert allowed is True


def test_inform_mutation_allowed():
    # houdini_create_node: read_only=False, derived gate 'inform' -> allowed.
    allowed, _ = is_tool_allowed_for_worker("houdini_create_node")
    assert allowed is True


@pytest.mark.parametrize("tool", ["houdini_delete_node", "houdini_render"])
def test_review_and_approve_tools_denied(tool):
    # delete_node -> 'review', houdini_render -> 'approve'. Both denied.
    allowed, _ = is_tool_allowed_for_worker(tool)
    assert allowed is False


@pytest.mark.parametrize("tool", ["synapse_solaris_build_graph", "synapse_solaris_assemble_chain"])
def test_solaris_builders_allowed_for_worker(tool):
    # L4 (signed off 2026-06-25): 'review'-gated by derivation (build_from_manifest)
    # but explicitly allowlisted -- composites of inform-level, undo-wrapped
    # primitives, so the autonomous worker can collapse a multi-node build into
    # one declarative call instead of a 25-turn imperative loop.
    allowed, _ = is_tool_allowed_for_worker(tool)
    assert allowed is True


def test_destructive_tools_still_denied_after_builder_allowlist():
    # The builder allowlist must NOT leak to genuinely gated ops.
    for tool in ("houdini_delete_node", "houdini_render", "houdini_execute_python"):
        assert is_tool_allowed_for_worker(tool)[0] is False


def test_unknown_tool_denied_fail_closed():
    allowed, reason = is_tool_allowed_for_worker("totally_made_up_tool_xyz")
    assert allowed is False
    assert "unknown" in reason.lower() or "fail-closed" in reason.lower()


def test_group_tools_allowed():
    allowed, _ = is_tool_allowed_for_worker("synapse_group_scene")
    assert allowed is True


def test_unclassified_mutation_denied_fail_closed():
    # synapse_write_report: read_only=False, not in _TOOL_TO_OPERATION ->
    # no derivable gate -> fail closed.
    allowed, reason = is_tool_allowed_for_worker("synapse_write_report")
    assert allowed is False


# ===========================================================================
# Advertise layer: get_anthropic_tools_for_worker
# ===========================================================================

def test_worker_toolset_strictly_smaller():
    full = get_anthropic_tools()
    worker = get_anthropic_tools_for_worker()
    assert len(worker) < len(full)
    full_names = {t["name"] for t in full}
    worker_names = {t["name"] for t in worker}
    assert worker_names.issubset(full_names)


def test_worker_toolset_excludes_code_execution():
    worker_names = {t["name"] for t in get_anthropic_tools_for_worker()}
    assert "houdini_execute_python" not in worker_names
    assert "houdini_execute_vex" not in worker_names


def test_worker_toolset_includes_a_read_only_tool():
    worker_names = {t["name"] for t in get_anthropic_tools_for_worker()}
    assert "synapse_ping" in worker_names


# ===========================================================================
# Conformance: every advertised (full) tool resolves with no KeyError.
# ===========================================================================

def test_every_full_tool_resolves_without_error():
    for tool in get_anthropic_tools():
        allowed, reason = is_tool_allowed_for_worker(tool["name"])
        assert isinstance(allowed, bool)
        assert isinstance(reason, str) and reason


# ===========================================================================
# Env overrides
# ===========================================================================

def test_unrestricted_allows_execute_python():
    os.environ[_ENV_VAR] = "unrestricted"
    allowed, _ = is_tool_allowed_for_worker("houdini_execute_python")
    assert allowed is True


def test_strict_denies_inform_mutation():
    os.environ[_ENV_VAR] = "strict"
    # create_node is an 'inform' mutation -> allowed under standard, denied
    # under strict (read-only only).
    allowed, _ = is_tool_allowed_for_worker("houdini_create_node")
    assert allowed is False


def test_strict_still_allows_read_only():
    os.environ[_ENV_VAR] = "strict"
    allowed, _ = is_tool_allowed_for_worker("synapse_ping")
    assert allowed is True


def test_unknown_env_value_falls_back_to_standard():
    os.environ[_ENV_VAR] = "bogus_mode"
    # Standard behavior: execute_python denied, create_node allowed.
    assert is_tool_allowed_for_worker("houdini_execute_python")[0] is False
    assert is_tool_allowed_for_worker("houdini_create_node")[0] is True


# ===========================================================================
# Dispatch-side enforcement (the load-bearing check).
# Requires importing ClaudeWorker -> PySide. Stub PySide with a sys.modules-
# restoring fixture so no stub leaks into sibling panel tests.
# ===========================================================================

@pytest.fixture
def claude_worker_module():
    """Import claude_worker headlessly, restoring sys.modules afterward.

    If real PySide is present we use it. Otherwise we install minimal stubs
    (QThread as a plain object base, Signal as a no-op factory) ONLY for the
    duration of this test, then restore every key we touched.
    """
    # Panel modules that subclass Qt and must re-import against the (possibly
    # stubbed) QtCore. Saved + restored so no stub leaks into sibling tests.
    touched = [
        "PySide6", "PySide6.QtCore",
        "PySide2", "PySide2.QtCore",
        "synapse.panel.claude_worker",
        "synapse.panel.tool_executor",
    ]
    saved = {k: sys.modules.get(k) for k in touched}

    def _is_genuine_qt(modname):
        """True only if ``modname`` exposes a REAL ``QThread`` *class*.

        Trusting a bare ``import ... ; real_qt=True`` is the documented trap: a
        sibling panel test (test_chat_panel) installs a MagicMock ``PySide6``
        into ``sys.modules`` and never restores it. That mock imports fine, but
        its ``QThread`` is a MagicMock *instance*, not a class — subclassing it
        makes ``_execute_tool_block`` return a MagicMock and the dispatch
        assertions silently rot (order-fragile: green alone, red after
        test_chat_panel). Requiring ``isinstance(QThread, type)`` rejects the
        mock so we fall through to our own functional stub instead.
        """
        try:
            mod = importlib.import_module(modname)
        except Exception:
            return False
        return isinstance(getattr(mod, "QThread", None), type)

    real_qt = _is_genuine_qt("PySide6.QtCore") or _is_genuine_qt("PySide2.QtCore")

    if not real_qt:
        # Minimal but sufficient PySide6.QtCore stub. QThread/QObject must be
        # real, usable base classes (claude_worker subclasses QThread,
        # tool_executor subclasses QObject). Other attributes (Slot, QTimer...)
        # auto-vivify via __getattr__ so unrelated imports don't explode.
        class _StubBase:
            def __init__(self, *a, **kw):
                pass

        class _QtCoreStub(types.ModuleType):
            QThread = _StubBase
            QObject = _StubBase

            @staticmethod
            def Signal(*a, **kw):
                return MagicMock()

            @staticmethod
            def Slot(*a, **kw):
                return lambda fn: fn

            def __getattr__(self, name):  # pragma: no cover - defensive
                return MagicMock()

        qtcore = _QtCoreStub("PySide6.QtCore")
        pyside = types.ModuleType("PySide6")
        pyside.QtCore = qtcore
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore

    # Force a fresh import so the (possibly stubbed) QThread is the base class.
    if not real_qt:
        sys.modules.pop("synapse.panel.tool_executor", None)
    sys.modules.pop("synapse.panel.claude_worker", None)
    import synapse.panel.claude_worker as cw

    try:
        yield cw
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def _make_worker(cw_module, **kwargs):
    """Build a ClaudeWorker without running its QThread (no .start())."""
    worker = cw_module.ClaudeWorker(messages=[], **kwargs)
    # Neutralize the Qt signal so .emit() is a no-op regardless of stub/real.
    worker.tool_status = MagicMock()
    return worker


def _denied_block():
    return {"id": "tu_1", "name": "houdini_execute_python", "input": {"code": "x=1"}}


def test_dispatch_denies_and_does_not_dispatch(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    sentinel = MagicMock(name="try_mcp_tool_call")
    monkeypatch.setattr(cw, "try_mcp_tool_call", sentinel)

    worker = _make_worker(cw, enforce_worker_policy=True)
    result = worker._execute_tool_block(_denied_block())

    assert result["is_error"] is True
    assert result["tool_use_id"] == "tu_1"
    sentinel.assert_not_called()  # never reached dispatch


def test_dispatch_passes_through_when_policy_disabled(claude_worker_module, monkeypatch):
    cw = claude_worker_module
    # When disabled, the denied tool reaches dispatch. Return a sentinel dict so
    # the method completes without the Qt signal/main-thread fallback path.
    called = {"n": 0}

    def _fake_mcp(name, inp):
        called["n"] += 1
        return {"ok": True}

    monkeypatch.setattr(cw, "try_mcp_tool_call", _fake_mcp)

    worker = _make_worker(cw, enforce_worker_policy=False)
    result = worker._execute_tool_block(_denied_block())

    assert called["n"] == 1  # dispatch WAS reached
    assert result["is_error"] is False


# ---------------------------------------------------------------------------
# denial_tool_result shape
# ---------------------------------------------------------------------------

def test_denial_tool_result_shape():
    block = denial_tool_result("tu_9", "houdini_render", "gate 'approve' ...")
    assert block["type"] == "tool_result"
    assert block["tool_use_id"] == "tu_9"
    assert block["is_error"] is True
    assert "houdini_render" in block["content"]
