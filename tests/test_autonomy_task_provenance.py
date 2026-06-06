"""
Tests for the autonomy -> agent.usd task provenance wiring.

These pin the live producer that `_handle_autonomous_render` now feeds into the
already-live `suspend_all_tasks(agent_usd)` consumer (websocket.py:483 /
mcp/session.py:207). Before this wire, `/SYNAPSE/agent/tasks/` was ALWAYS empty
because nothing called `create_task`; the consumer therefore always found
nothing. The loop-closure test below proves a real producer -> consumer closure.

Reuses the FakeStage mock-pxr harness from tests/test_agent_state.py so it runs
without a real pxr.

Run: python -m pytest tests/test_autonomy_task_provenance.py -v
"""

import os
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

# Add package + tests dir to path (mirror test_agent_state.py).
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # for test_agent_state harness

from synapse.memory import agent_state


def _SH():
    """Lazily import ``SynapseHandler`` INSIDE a test, never at collection time.

    Importing ``synapse.server.handlers`` at module/collection time would make
    this module the FIRST importer of handlers — before any handler test installs
    its fake ``hou`` in ``sys.modules`` (the pattern at test_capture.py:11-26) —
    which leaves ``handlers.hou`` undefined for the whole session and breaks
    sibling handler tests (e.g. test_mcp_roundtrip.py:94 reads ``handlers.hou``).
    Deferring lets a handler test bind ``handlers.hou`` first. This module never
    needs real ``hou`` anyway (it stubs ``_resolve_agent_usd`` + mocks pxr)."""
    from synapse.server.handlers import SynapseHandler
    return SynapseHandler

# Reuse the proven FakeStage mock-pxr harness from the sibling test module.
from test_agent_state import (  # noqa: E402
    _fake_create_new,
    _fake_open,
    _fake_stages,
    FakeSdf,
    FakeVt,
)


# ═════════════════════════════════════════════════════════════════
# Minimal RenderReport-shaped fakes (match autonomy/models.py shapes)
# ═════════════════════════════════════════════════════════════════

# Mirror the LIVE autonomy/models.py CheckSeverity vocabulary exactly — a
# divergent set ("error"/"warning") would let the hard_fail counter read 0 in
# the test while the live path also reads 0, masking the bug. These are the real
# values the live RenderReport carries.
class _Sev(Enum):
    HARD_FAIL = "hard_fail"   # blocking — what before_state's hard_fail counts
    SOFT_WARN = "soft_warn"
    INFO = "info"


@dataclass
class FakeCheck:
    name: str
    passed: bool = True
    severity: _Sev = _Sev.INFO


@dataclass
class FakePlan:
    validation_checks: List[FakeCheck] = field(default_factory=list)


@dataclass
class FakeEvaluation:
    overall_score: float = 0.0
    passed: bool = False


@dataclass
class FakeReport:
    """Stand-in for autonomy.models.RenderReport (live-relevant fields only)."""
    success: bool = False
    plan: FakePlan = field(default_factory=FakePlan)
    evaluation: Optional[FakeEvaluation] = None
    verification: Optional[object] = None  # always None on the live path


def _success_report():
    return FakeReport(
        success=True,
        plan=FakePlan(validation_checks=[
            FakeCheck("camera_exists", passed=True, severity=_Sev.HARD_FAIL),
            FakeCheck("output_writable", passed=True, severity=_Sev.SOFT_WARN),
        ]),
        evaluation=FakeEvaluation(overall_score=0.91, passed=True),
    )


def _failed_report():
    return FakeReport(
        success=False,
        plan=FakePlan(validation_checks=[
            # A FAILED hard_fail check — before_state must count this as hard_fail=1.
            FakeCheck("camera_exists", passed=False, severity=_Sev.HARD_FAIL),
            FakeCheck("output_writable", passed=True, severity=_Sev.SOFT_WARN),
        ]),
        evaluation=FakeEvaluation(overall_score=0.40, passed=False),
    )


# ═════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_pxr(tmp_path):
    """Patch agent_state to use the fake pxr objects from test_agent_state."""
    _fake_stages.clear()

    fake_usd = MagicMock()
    fake_usd.Stage.CreateNew = _fake_create_new
    fake_usd.Stage.Open = _fake_open

    with patch.object(agent_state, "PXR_AVAILABLE", True), \
         patch.object(agent_state, "Usd", fake_usd), \
         patch.object(agent_state, "Sdf", FakeSdf), \
         patch.object(agent_state, "Vt", FakeVt):
        yield

    _fake_stages.clear()


@pytest.fixture
def agent_usd_path(tmp_path):
    return os.path.join(str(tmp_path), "agent.usd")


def _stage_for(path):
    return _fake_stages[os.path.normpath(path)]


def _task_prim(path, task_id):
    # Tasks are stored under the sanitized prim name (hyphens -> underscores).
    safe = agent_state._safe_prim_name(task_id)
    return _stage_for(path).GetPrimAtPath(f"/SYNAPSE/agent/tasks/{safe}")


# ═════════════════════════════════════════════════════════════════
# THE LOOP-CLOSURE TEST (proof it is NOT theater)
# ═════════════════════════════════════════════════════════════════

class TestLoopClosure:
    def test_producer_feeds_live_suspend_consumer(self, agent_usd_path, mock_pxr):
        """create_task + helper produce a task that the ALREADY-LIVE
        suspend_all_tasks consumer now finds -- it found nothing before.
        """
        agent_state.initialize_agent_usd(agent_usd_path)
        task_id = "autorender-deadbeef"

        # --- Baseline: the live consumer finds NOTHING (the dormant state) ---
        agent_state.suspend_all_tasks(agent_usd_path)
        tasks_prim = _stage_for(agent_usd_path).GetPrimAtPath("/SYNAPSE/agent/tasks")
        assert tasks_prim.GetChildren() == [], "tasks/ must start empty (dormant producer)"

        # --- PRODUCER on dispatch: create the pending task ---
        agent_state.create_task(agent_usd_path, task_id, "render frames 1-48")

        # --- Helper closes the lifecycle after the (fake) render returns ---
        _SH()._record_autonomy_task(agent_usd_path, task_id, _success_report())

        # Task prim now EXISTS with status completed.
        task = _task_prim(agent_usd_path, task_id)
        assert task.IsValid()
        assert task.GetAttribute("synapse:status").Get() == "completed"

        # Verification prim exists with checks + result.
        vlog = _stage_for(agent_usd_path).GetPrimAtPath("/SYNAPSE/agent/verification_log")
        vchildren = vlog.GetChildren()
        assert len(vchildren) == 1
        ventry = vchildren[0]
        assert ventry.GetAttribute("synapse:taskId").Get() == task_id
        assert ventry.GetAttribute("synapse:result").Get() == "pass"
        assert "camera_exists:pass" in ventry.GetAttribute("synapse:checks").Get()
        assert ventry.GetAttribute("synapse:afterState").Get() == "score=0.91 passed=True"
        assert ventry.GetAttribute("synapse:beforeState").Get() == "checks=2 hard_fail=0"

        # --- CONSUMER closure: the SAME already-live consumer the disconnect
        # path calls. A *new* pending task (mid-flight on a fresh dispatch)
        # is now visible to it. Before the wire this returned nothing. ---
        agent_state.create_task(agent_usd_path, "autorender-inflight", "render turntable")
        agent_state.suspend_all_tasks(agent_usd_path)

        inflight = _task_prim(agent_usd_path, "autorender-inflight")
        assert inflight.GetAttribute("synapse:status").Get() == "suspended", (
            "suspend_all_tasks now FINDS a pending autorender task -- "
            "the producer->consumer loop is closed"
        )


# ═════════════════════════════════════════════════════════════════
# Failed-render path
# ═════════════════════════════════════════════════════════════════

class TestFailedRenderPath:
    def test_failed_report_marks_task_failed(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        task_id = "autorender-cafef00d"
        agent_state.create_task(agent_usd_path, task_id, "render frames 1-48")

        _SH()._record_autonomy_task(agent_usd_path, task_id, _failed_report())

        task = _task_prim(agent_usd_path, task_id)
        assert task.GetAttribute("synapse:status").Get() == "failed"

        vlog = _stage_for(agent_usd_path).GetPrimAtPath("/SYNAPSE/agent/verification_log")
        ventry = vlog.GetChildren()[0]
        assert ventry.GetAttribute("synapse:result").Get() == "fail"
        # The HARD_FAIL-severity check failed -> hard_fail=1 (real live vocabulary).
        assert ventry.GetAttribute("synapse:beforeState").Get() == "checks=2 hard_fail=1"
        assert "camera_exists:fail" in ventry.GetAttribute("synapse:checks").Get()

    def test_no_evaluation_uses_sentinel(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        task_id = "autorender-noeval"
        agent_state.create_task(agent_usd_path, task_id, "render")
        report = FakeReport(success=True, plan=FakePlan(validation_checks=[]), evaluation=None)

        _SH()._record_autonomy_task(agent_usd_path, task_id, report)

        vlog = _stage_for(agent_usd_path).GetPrimAtPath("/SYNAPSE/agent/verification_log")
        ventry = vlog.GetChildren()[0]
        assert ventry.GetAttribute("synapse:afterState").Get() == "no_evaluation"


# ═════════════════════════════════════════════════════════════════
# BEST-EFFORT: a writer failure must never propagate
# ═════════════════════════════════════════════════════════════════

class TestBestEffort:
    def test_helper_swallows_update_status_failure(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        task_id = "autorender-boom1"
        agent_state.create_task(agent_usd_path, task_id, "render")

        def _boom(*a, **k):
            raise RuntimeError("disk on fire")

        # Patch the names as imported inside the helper's local import.
        with patch.object(agent_state, "update_task_status", _boom):
            # Must NOT raise.
            _SH()._record_autonomy_task(agent_usd_path, task_id, _success_report())

        # write_verification still ran despite update_task_status blowing up.
        vlog = _stage_for(agent_usd_path).GetPrimAtPath("/SYNAPSE/agent/verification_log")
        assert len(vlog.GetChildren()) == 1

    def test_helper_swallows_write_verification_failure(self, agent_usd_path, mock_pxr):
        agent_state.initialize_agent_usd(agent_usd_path)
        task_id = "autorender-boom2"
        agent_state.create_task(agent_usd_path, task_id, "render")

        def _boom(*a, **k):
            raise RuntimeError("verification kaboom")

        with patch.object(agent_state, "write_verification", _boom):
            # Must NOT raise.
            _SH()._record_autonomy_task(agent_usd_path, task_id, _success_report())

        # update_task_status still applied despite write_verification failing.
        task = _task_prim(agent_usd_path, task_id)
        assert task.GetAttribute("synapse:status").Get() == "completed"

    def test_full_handler_returns_report_when_writer_throws(self, mock_pxr, tmp_path):
        """End-to-end: _handle_autonomous_render returns the render result
        unchanged even when a provenance WRITER raises.

        Drives the real handler with a stubbed autonomy stack (no Houdini), then
        sabotages write_verification to raise. Because the helper is the
        best-effort boundary, the exception is swallowed and the serialized
        report is returned intact.
        """
        agent_usd = os.path.join(str(tmp_path), "agent.usd")
        agent_state.initialize_agent_usd(agent_usd)
        report = _success_report()

        handler = _SH().__new__(_SH())  # no heavy __init__
        handler._registry = MagicMock()  # adapter holds it; fake driver never calls it
        import synapse.server.handlers as H

        class _FakeDriver:
            def __init__(self, **kw):
                pass

            async def execute(self, intent):
                return report

        fake_autonomy = type(sys)("synapse.autonomy")
        fake_autonomy.AutonomousDriver = _FakeDriver
        fake_autonomy.RenderPlanner = lambda *a, **k: object()
        fake_autonomy.PreFlightValidator = lambda *a, **k: object()
        fake_autonomy.RenderEvaluator = lambda *a, **k: object()

        def _boom(*a, **k):
            raise RuntimeError("writer exploded mid-render")

        with patch.dict(sys.modules, {"synapse.autonomy": fake_autonomy}), \
             patch.object(H.SynapseHandler, "_resolve_agent_usd", staticmethod(lambda: agent_usd)), \
             patch.object(agent_state, "write_verification", _boom), \
             patch.object(agent_state, "create_task", _boom):
            out = handler._handle_autonomous_render({"intent": "render frames 1-48"})

        # Render result survives a writer explosion on BOTH dispatch + completion.
        assert isinstance(out, dict)
        assert out["success"] is True


# ═════════════════════════════════════════════════════════════════
# Handler-level genuine activation (create_task fires THROUGH the handler)
# ═════════════════════════════════════════════════════════════════

class TestHandlerLevelActivation:
    def test_handler_authors_task_through_live_wiring(self, mock_pxr, tmp_path):
        """Drive the REAL _handle_autonomous_render happy-path with create_task
        NOT patched, and assert a task prim is authored THROUGH the handler's
        wiring (status 'completed') — pins handler-level activation, not just the
        helper called in isolation. Proves the registered-live handler reaches
        create_task on its real dispatch path."""
        agent_usd = os.path.join(str(tmp_path), "agent.usd")
        agent_state.initialize_agent_usd(agent_usd)
        report = _success_report()

        handler = _SH().__new__(_SH())  # no heavy __init__
        handler._registry = MagicMock()
        import synapse.server.handlers as H

        class _FakeDriver:
            def __init__(self, **kw):
                pass

            async def execute(self, intent):
                return report

        fake_autonomy = type(sys)("synapse.autonomy")
        fake_autonomy.AutonomousDriver = _FakeDriver
        fake_autonomy.RenderPlanner = lambda *a, **k: object()
        fake_autonomy.PreFlightValidator = lambda *a, **k: object()
        fake_autonomy.RenderEvaluator = lambda *a, **k: object()

        # Baseline: tasks group is empty before the handler runs.
        tasks_grp = _stage_for(agent_usd).GetPrimAtPath("/SYNAPSE/agent/tasks")
        assert len(tasks_grp.GetChildren()) == 0

        with patch.dict(sys.modules, {"synapse.autonomy": fake_autonomy}), \
             patch.object(H.SynapseHandler, "_resolve_agent_usd", staticmethod(lambda: agent_usd)):
            out = handler._handle_autonomous_render({"intent": "render frames 1-48"})

        assert out["success"] is True
        # A task prim was authored THROUGH the handler (create_task fired live).
        tasks = _stage_for(agent_usd).GetPrimAtPath("/SYNAPSE/agent/tasks").GetChildren()
        assert len(tasks) == 1, "handler did not author a task through the live wiring"
        assert tasks[0].GetAttribute("synapse:status").Get() == "completed"
        assert tasks[0].GetAttribute("synapse:description").Get() == "render frames 1-48"


# ═════════════════════════════════════════════════════════════════
# no-pxr / no-hou graceful no-op
# ═════════════════════════════════════════════════════════════════

class TestGracefulNoOp:
    def test_helper_noop_without_pxr(self, agent_usd_path):
        """With pxr unavailable the writers no-op; helper must not raise."""
        with patch.object(agent_state, "PXR_AVAILABLE", False):
            # No file, no stage -- pure no-op path.
            _SH()._record_autonomy_task(agent_usd_path, "autorender-x", _success_report())

    def test_resolve_agent_usd_returns_none_without_hou(self):
        """Without Houdini, agent.usd resolution returns None (never raises)."""
        import synapse.server.handlers as H
        with patch.object(H, "HOU_AVAILABLE", False):
            assert H.SynapseHandler._resolve_agent_usd() is None
