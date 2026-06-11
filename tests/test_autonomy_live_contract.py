"""Live-contract test: REAL planner -> REAL registry -> REAL driver/evaluator.

M1 'stop the fictions'. The autonomy plan used to schedule a validate_frame
step with a frame-only payload (the live handler requires image_path -- a
guaranteed 'Missing required parameter' death), and _collect_results
fabricated frame entries from step params when the render result was
unparseable (the false-pass generator). This file drives the real seam
headless and pins the repaired contract end to end:

  1. every planned step resolves in the LIVE registry,
  2. every planned step's EXACT params survive registry.invoke without
     dying on a missing parameter,
  3. render_sequence's published BatchReport shape (frame_results /
     image_path) is exactly what the REAL _collect_results consumes,
  4. nothing actually rendered headless -> the evaluator reports an HONEST
     failure, and the registered autonomous_render tool returns
     success=False with no contract-violation step errors.

Bootstrap mirrors tests/test_forge_render.py:36-99 verbatim (stub
hou/hdefereval into sys.modules BEFORE importing handlers, then
SynapseHandler() -> REAL registry). Only non-contract boundaries are
stubbed: batch notifications (toast/report writers) and the memory store.

Mock-based -- no Houdini required.
"""

import asyncio
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: load handlers without Houdini (verbatim from tests/test_render.py)
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.text = MagicMock()
    _hou.text.expandString = MagicMock(return_value="/tmp/houdini_temp")
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]
    if not hasattr(_hou, "undos"):
        _hou.undos = MagicMock()

if "hdefereval" not in sys.modules:
    _hdefereval = types.ModuleType("hdefereval")
    sys.modules["hdefereval"] = _hdefereval
else:
    _hdefereval = sys.modules["hdefereval"]

if not hasattr(_hdefereval, "executeDeferred"):
    _hdefereval.executeDeferred = lambda fn: fn()

_handlers_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "handlers.py"
_proto_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "protocol.py"
_aliases_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "aliases.py"

for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

for mod_name, fpath in [
    ("synapse.core.protocol", _proto_path),
    ("synapse.core.aliases", _aliases_path),
    ("synapse.server.handlers", _handlers_path),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]

_handlers_hou = handlers_mod.hou
if not hasattr(_handlers_hou, "undos"):
    _handlers_hou.undos = MagicMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def handler(monkeypatch, tmp_path):
    # Keep FloorGate provenance records out of the repo tree.
    monkeypatch.setenv("SYNAPSE_PROVENANCE_DIR", str(tmp_path / "provenance"))

    # Stub ONLY non-contract boundaries: notifications + memory store.
    import synapse.server.render_farm as render_farm_mod
    notified = []
    monkeypatch.setattr(
        render_farm_mod, "notify_batch_complete",
        lambda report, report_dir: notified.append((report, report_dir)) or {},
    )

    import synapse.memory.store as store_mod

    def _no_memory():
        raise RuntimeError("memory store disabled for live-contract test")

    monkeypatch.setattr(store_mod, "get_synapse_memory", _no_memory)

    h = handlers_mod.SynapseHandler()
    h._bridge = MagicMock()
    yield h

    farm = getattr(h, "_render_farm", None)
    if farm is not None:
        farm.shutdown()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _NullHandlerInterface:
    """_collect_results never touches the handler interface -- enforce it."""

    async def call(self, tool_name, params):
        raise AssertionError(
            "handler_interface must not be called by _collect_results"
        )


# ---------------------------------------------------------------------------
# Tests: the live plan -> registry -> driver -> evaluator contract
# ---------------------------------------------------------------------------

class TestAutonomyLiveContract:

    def test_plan_registry_collect_evaluate_contract(self, handler):
        from synapse.autonomy import (
            AutonomousDriver,
            PreFlightValidator,
            RenderEvaluator,
            RenderPlanner,
        )

        # ---- (1) every planned step resolves in the LIVE registry ----
        plan = RenderPlanner().plan("render frames 1-2")
        assert plan.steps, "planner produced an empty plan"
        for step in plan.steps:
            assert handler._registry.has(step.handler), (
                f"planner emitted a step with no registered handler: {step.handler!r}"
            )

        # ---- (2) the validate_frame fiction is dead ----
        for step in plan.steps:
            if step.handler == "validate_frame":
                assert "image_path" in step.params, (
                    "validate_frame planned with a frame-only payload -- "
                    "the live handler contract requires image_path"
                )

        # Each step's EXACT params must survive the real handler's parameter
        # resolution -- the old plan died here with 'Missing required parameter'.
        step_results = {}
        for step in plan.steps:
            try:
                step_results[step.handler] = handler._registry.invoke(
                    step.handler, dict(step.params)
                )
            except Exception as exc:
                assert "Missing required parameter" not in str(exc), (
                    f"step {step.handler!r} params {step.params} violate the "
                    f"handler contract: {exc}"
                )
                raise

        # ---- (3) published BatchReport shape feeds the REAL _collect_results ----
        render_result = step_results["render_sequence"]
        frame_results = render_result.get("frame_results")
        assert isinstance(frame_results, list)
        assert len(frame_results) == 2

        render_step = next(s for s in plan.steps if s.handler == "render_sequence")
        render_step.result = render_result

        driver = AutonomousDriver(
            planner=RenderPlanner(),
            validator=PreFlightValidator(_NullHandlerInterface()),
            evaluator=RenderEvaluator(),
            handler_interface=_NullHandlerInterface(),
        )
        results = asyncio.run(driver._collect_results(plan))
        assert results, "collect_results dropped the published frame_results"
        assert [r["frame"] for r in results] == [1, 2]
        for collected, fr in zip(results, frame_results):
            assert collected["output_path"] == fr["image_path"]

        # ---- (4) honest failure: nothing was actually rendered headless ----
        evaluation = RenderEvaluator().evaluate_sequence(results)
        assert evaluation.passed is False

    def test_autonomous_render_tool_reports_honest_failure(self, handler):
        """Outer pin: the registered tool, driven through the live registry,
        must come back success=False headless with no step ever dying on a
        missing parameter."""
        out = handler._registry.invoke(
            "autonomous_render",
            {"intent": "render frames 1-2", "max_iterations": 1},
        )
        assert isinstance(out, dict)
        assert out["success"] is False
        for step in out["plan"]["steps"]:
            assert "Missing required parameter" not in (step.get("error") or "")
