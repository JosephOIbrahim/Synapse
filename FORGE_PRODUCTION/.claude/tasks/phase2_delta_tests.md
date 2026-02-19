# TEAM DELTA — Phase 2: Autonomy Pipeline Tests

> **File ownership:** `tests/` (all test files)
> **Do NOT modify:** any non-test files

## Context

Read these first:
- `CLAUDE.md` (project conventions)
- `docs/forge/FORGE_PRODUCTION.md` (your deliverables)
- `synapse/autonomy/` (the modules you're testing — read CHARLIE's task for specs)
- Existing test patterns: `tests/test_tops.py`, `tests/test_e2e_tops.py`

## Test Files to Create

### 1. `tests/test_autonomy_models.py`
```python
"""Tests for autonomy data models."""
# Test dataclass creation, defaults, serialization
# test_render_plan_creation
# test_gate_level_ordering
# test_step_status_transitions
# test_render_report_aggregation
```

### 2. `tests/test_autonomy_planner.py` (~10 tests)
```python
# test_simple_render_plan — "render frame 1" → valid single-frame plan
# test_sequence_render_plan — "render 1-48" → plan with frame range, correct step count
# test_turntable_plan — "render turntable" → plan using turntable production recipe
# test_rerender_plan — evaluation with 3 bad frames → plan targeting only those frames
# test_invalid_intent — empty/garbage input → graceful error, not crash
# test_plan_gate_levels — first render = REVIEW, re-render = INFORM
# test_plan_step_ordering — handlers appear in correct dependency order
# test_plan_with_scene_context — scene context influences plan (e.g., existing camera used)
# test_plan_estimated_frames — frame count matches intent
# test_replan_increases_samples — noise evaluation → replan with higher samples
```

### 3. `tests/test_autonomy_validator.py` (~12 tests)
```python
# test_valid_scene_passes — all checks pass for well-formed scene
# test_missing_camera_hard_fails — no camera → HARD_FAIL, render blocked
# test_missing_renderable_prims_hard_fails — empty stage → HARD_FAIL
# test_missing_materials_soft_warns — unassigned prims → SOFT_WARN, render proceeds
# test_low_samples_soft_warns — samples < threshold → SOFT_WARN
# test_invalid_frame_range_hard_fails — start > end → HARD_FAIL
# test_negative_frame_range_hard_fails — negative frames → HARD_FAIL
# test_output_path_missing_warns — nonexistent dir → SOFT_WARN
# test_solaris_ordering_stub — ordering check returns INFO (stub for Phase 3)
# test_missing_assets_warns — unresolved USD refs → SOFT_WARN
# test_multiple_hard_fails — multiple failures all reported
# test_all_checks_run — no short-circuit, all checks execute even after first fail
```

### 4. `tests/test_autonomy_evaluator.py` (~15 tests)
```python
# --- Per-frame ---
# test_clean_frame_passes — normal render output → score 1.0
# test_black_frame_detection — all-black image → flagged
# test_nan_detection — NaN pixels → flagged
# test_inf_detection — Inf pixels → flagged
# test_firefly_detection — statistical outlier pixels → flagged
# test_overexposure_clipping — >5% pure white → flagged
# test_underexposure_clipping — >5% pure black → flagged
# test_multiple_issues — frame with 2+ issues → all reported, score reduced correctly

# --- Sequence ---
# test_stable_sequence_passes — consistent frames → temporal coherence passes
# test_flickering_detection — alternating bright/dark → flagged
# test_motion_discontinuity — large frame-to-frame jump → flagged
# test_missing_frame_detection — gap in sequence (1,2,3,5,6) → frame 4 flagged
# test_sequence_score_calculation — verify scoring formula
# test_empty_sequence — 0 frames → graceful handling
# test_single_frame_sequence — 1 frame → no temporal checks, frame eval only
```

### 5. `tests/test_autonomy_driver.py` (~12 tests)
```python
# test_full_loop_success — plan → validate → execute → evaluate → report (all pass)
# test_validation_hard_fail_stops — bad scene → stops before render, report explains why
# test_validation_soft_warn_continues — warning → render proceeds
# test_evaluation_triggers_replan — bad frames → re-render triggered
# test_max_iterations_respected — 3 failures → stops, doesn't loop forever
# test_max_iterations_configurable — custom limit honored
# test_checkpoint_save — checkpoint created after each step
# test_checkpoint_resume — load checkpoint, continue from saved state
# test_gate_review_waits — REVIEW gate → approval mock called
# test_gate_inform_proceeds — INFORM gate → no approval needed
# test_decision_logging — every step generates a Decision with reasoning
# test_emergency_stop — cancel triggers tops_cancel handler
```

## Mock Strategy

```python
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import numpy as np

@pytest.fixture
def mock_handler_interface():
    """Mock the MCP handler call interface."""
    interface = AsyncMock()
    interface.call.return_value = {"status": "ok"}
    return interface

@pytest.fixture
def mock_tops_results():
    """Synthetic TOPS work item results."""
    return {
        "job_id": "test_001",
        "status": "complete",
        "work_items": [
            {"frame": i, "output_path": f"/tmp/test/frame.{i:04d}.exr", "status": "complete"}
            for i in range(1, 49)
        ]
    }

@pytest.fixture
def mock_clean_frame():
    """Generate a synthetic 'clean' rendered frame (numpy array)."""
    return np.random.uniform(0.1, 0.9, (100, 100, 3)).astype(np.float32)

@pytest.fixture
def mock_black_frame():
    """Generate a synthetic black frame."""
    return np.zeros((100, 100, 3), dtype=np.float32)

@pytest.fixture
def mock_firefly_frame():
    """Generate frame with statistical outlier pixels."""
    frame = np.random.uniform(0.1, 0.5, (100, 100, 3)).astype(np.float32)
    frame[50, 50] = [100.0, 100.0, 100.0]  # Firefly
    return frame

@pytest.fixture
def mock_memory_system():
    """Mock scene memory for decision logging."""
    memory = MagicMock()
    memory.log_decision = MagicMock()
    return memory

@pytest.fixture
def mock_routing():
    """Mock routing cascade + recipe registry."""
    routing = MagicMock()
    routing.route.return_value = {
        "recipe": "render_turntable_production",
        "handlers": ["create_camera", "create_light", "render_settings", "tops_render_sequence"]
    }
    return routing
```

## Important

- ALL tests must pass without a live Houdini connection
- Mock ALL external dependencies (hou, pdg, WebSocket, file system)
- Use `numpy` for synthetic frame generation (it's in SYNAPSE deps)
- If `numpy` is not available, use simple Python lists as fallback
- Follow naming: `test_{module}_{what}_{condition}_{expected}`
- Each test function tests ONE behavior
- Mark integration tests with `@pytest.mark.integration`

## Done Criteria

- [ ] 5 test files created
- [ ] ~55 tests total
- [ ] All tests pass with mocked dependencies
- [ ] No live Houdini required
- [ ] Existing tests still pass (run full suite)
- [ ] Report: test count, coverage areas, untestable paths
