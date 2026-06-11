"""M3-E (studio-operable, report §4.4 + §5 item 10c): bounded autonomy.

The autonomous render loop had no wall-clock bound, an unclamped
payload-controlled max_iterations (worst case = iterations × frames ×
(1 + retries) renders while every client abandons the run at 600 s), and
both kill switches were unreachable — driver.emergency_stop had zero
retention anywhere, and a naively-registered cancel would have BLOCKED
behind the C5 mutation lock the running render holds for its whole
sequence. Now: max_iterations clamps at MAX_ITERATIONS_HARD_CAP, every
run carries a wall-clock deadline defaulting to the canonical client
budget, reports say WHY they stopped (stop_reason), and
synapse_render_farm_cancel reaches both the farm singleton and the
live-driver registry on the read-only fast path.

Headless. Plant-or-enrich hou-fake convention (tests/test_m2_cook_verify.py
header); handler-module globals patched directly, never sys.modules residency.
"""

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

if "hou" not in sys.modules:
    sys.modules["hou"] = ModuleType("hou")
_h = sys.modules["hou"]
for _attr in ("undos", "node", "ui"):
    if not hasattr(_h, _attr):
        setattr(_h, _attr, MagicMock())
if not hasattr(_h, "text"):
    _h.text = MagicMock()
    _h.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
if not hasattr(_h, "frame"):
    _h.frame = MagicMock(return_value=1)
if "hdefereval" not in sys.modules:
    _hd = ModuleType("hdefereval")
    _hd.executeInMainThreadWithResult = lambda fn, *a, **k: fn(*a, **k)
    sys.modules["hdefereval"] = _hd

from synapse.autonomy import driver as driver_mod  # noqa: E402
from synapse.autonomy.driver import (  # noqa: E402
    AutonomousDriver,
    MAX_ITERATIONS_HARD_CAP,
    _register_live_driver,
    get_live_driver,
)
from synapse.autonomy.models import (  # noqa: E402
    GateLevel,
    RenderPlan,
    RenderReport,
    SequenceEvaluation,
)
from synapse.core.timeouts import timeout_for  # noqa: E402
from synapse.server import handlers as handlers_mod  # noqa: E402
from synapse.server.handlers import SynapseHandler  # noqa: E402
from synapse.mcp._tool_registry import TOOL_DEFS  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_registry():
    _register_live_driver(None)
    yield
    _register_live_driver(None)


def _driver(max_iterations=3, **kw):
    return AutonomousDriver(
        planner=None, validator=None, evaluator=None,
        handler_interface=None, max_iterations=max_iterations, **kw,
    )


# ---------------------------------------------------------------------------
# Clamp + wall-clock defaults
# ---------------------------------------------------------------------------


def test_max_iterations_clamped():
    assert _driver(max_iterations=10**9)._max_iterations == MAX_ITERATIONS_HARD_CAP == 10
    assert _driver(max_iterations=0)._max_iterations == 1
    assert _driver(max_iterations=3)._max_iterations == 3


def test_wall_clock_default_is_canonical_budget():
    assert _driver()._max_wall_clock == timeout_for("autonomous_render") == 600.0
    assert _driver(max_wall_clock_seconds=1200.0)._max_wall_clock == 1200.0


def test_report_stop_reason_default():
    assert RenderReport(plan=RenderPlan(intent="x")).stop_reason == ""


# ---------------------------------------------------------------------------
# Wall-clock + iteration-exhaustion honesty (real driver, faked stages)
# ---------------------------------------------------------------------------


def _wire_stages(d):
    """Minimal real-loop wiring: plan of 0 steps, no checks, failing eval."""
    plan = RenderPlan(intent="t", gate_level=GateLevel.INFORM)
    d._planner = SimpleNamespace(plan=lambda i: plan, replan=lambda p, e: p)

    async def _validate(p):
        return []

    d._validator = SimpleNamespace(validate=_validate)
    d._evaluator = SimpleNamespace(
        evaluate_sequence=lambda r: SequenceEvaluation(passed=False)
    )

    async def _call(tool, params):
        return {"success": True}

    d._handler = SimpleNamespace(call=_call)
    return d


def test_wall_clock_exceeded_stops_honestly(monkeypatch):
    d = _wire_stages(_driver(max_iterations=5))
    # Event-driven clock: the deadline is crossed DURING iteration 1's
    # evaluation, so exactly one iteration completes before the bound fires
    # (robust against how many monotonic() calls checkpointing makes).
    clock = {"t": 0.0}
    monkeypatch.setattr(driver_mod.time, "monotonic", lambda: clock["t"])

    def _eval(results):
        clock["t"] = 700.0  # past the 600s default deadline
        return SequenceEvaluation(passed=False)

    d._evaluator = SimpleNamespace(evaluate_sequence=_eval)
    report = asyncio.run(d.execute("t"))
    assert report.success is False
    assert report.stop_reason == "wall_clock_exceeded"
    assert report.iterations < 5
    assert any(dec.context == "wall_clock_exceeded" for dec in report.decisions)
    # Partial progress kept, not erased
    assert report.evaluation is not None


def test_exhausted_run_reports_max_iterations():
    d = _wire_stages(_driver(max_iterations=2))
    report = asyncio.run(d.execute("t"))
    assert report.success is False
    assert report.stop_reason == "max_iterations"
    assert report.iterations == 2


def test_passing_run_has_empty_stop_reason():
    d = _wire_stages(_driver(max_iterations=2))
    d._evaluator = SimpleNamespace(
        evaluate_sequence=lambda r: SequenceEvaluation(passed=True)
    )
    report = asyncio.run(d.execute("t"))
    assert report.success is True
    assert report.stop_reason == ""


# ---------------------------------------------------------------------------
# Live-driver registry lifecycle
# ---------------------------------------------------------------------------


def test_live_driver_registry_lifecycle():
    d = _wire_stages(_driver(max_iterations=1))
    seen = {}

    async def _call(tool, params):
        seen["live_during_run"] = get_live_driver()
        return {"success": True}

    d._handler = SimpleNamespace(call=_call)
    asyncio.run(d.execute("t"))
    assert seen.get("live_during_run") is None or seen["live_during_run"] is d
    assert get_live_driver() is None  # deregistered on exit

    # only_if guard: an old instance can't deregister a newer one
    new = _driver()
    old = _driver()
    _register_live_driver(new)
    _register_live_driver(None, only_if=old)
    assert get_live_driver() is new


def test_registry_cleared_on_exception():
    d = _driver(max_iterations=1)
    d._planner = SimpleNamespace(plan=MagicMock(side_effect=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        asyncio.run(d.execute("t"))
    assert get_live_driver() is None


# ---------------------------------------------------------------------------
# render_farm_cancel handler truth
# ---------------------------------------------------------------------------


def test_render_farm_cancel_handler_truth():
    h = SynapseHandler()
    farm = MagicMock()
    farm.is_running = True
    h._render_farm = farm
    fake_driver = _driver()
    _register_live_driver(fake_driver)

    fn = h._registry.get("render_farm_cancel")
    assert fn is not None, "render_farm_cancel not registered"
    result = fn({})

    farm.cancel.assert_called_once()
    assert fake_driver._cancelled is True
    assert result["farm_cancel_requested"] is True
    assert result["farm_was_running"] is True
    assert result["driver_cancel_requested"] is True
    # Truth contract: signal sent is the only claim — never "cancelled: True"
    assert "cancelled" not in result and "success" not in result

    # Honest no-op: nothing running
    _register_live_driver(None)
    h2 = SynapseHandler()
    result2 = h2._registry.get("render_farm_cancel")({})
    assert result2["farm_cancel_requested"] is False
    assert result2["driver_cancel_requested"] is False


def test_cancel_classification_and_registration():
    # The C5-bypass reachability property — removing this silently
    # re-deadlocks the kill switch behind the render it cancels.
    assert "render_farm_cancel" in handlers_mod._READ_ONLY_COMMANDS
    entry = [t for t in TOOL_DEFS if t[0] == "synapse_render_farm_cancel"]
    assert len(entry) == 1
    name, cmd, _builder, _desc, _schema, read_only, destructive, _idem = entry[0]
    assert cmd == "render_farm_cancel"
    # MCP-hint honesty: the tool HAS an effect (read_only False, destructive
    # True) — independent of the server-side dispatch classification above.
    assert read_only is False and destructive is True
