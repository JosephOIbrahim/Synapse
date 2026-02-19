# ALL TEAMS — Phase 3: Integration + Solaris Ordering

> **This phase is COORDINATED, not parallel.**
> Run tasks sequentially: BRAVO → CHARLIE → DELTA → end-to-end test.

## Prerequisites

Phase 2 gate must pass:
```bash
# Verify Phase 2 is complete
python -m pytest tests/test_autonomy_planner.py tests/test_autonomy_validator.py tests/test_autonomy_evaluator.py tests/test_autonomy_driver.py -v
ls synapse/autonomy/__init__.py synapse/autonomy/planner.py synapse/autonomy/validator.py synapse/autonomy/evaluator.py synapse/autonomy/driver.py
grep -c "tops_monitor_stream\|tops_render_sequence" synapse/mcp/tools.py
```

---

## Step 1: BRAVO — Solaris Ordering Validator

Add to `synapse/handlers_solaris.py`:

### Handler: `solaris_validate_ordering`

```python
async def handle_solaris_validate_ordering(params: dict) -> dict:
    """Walk LOP network from render ROP backwards, detect ambiguous merge points.

    Ambiguous merge = a LOP node with multiple inputs where evaluation order
    is not explicitly set and affects the output (e.g., merge LOPs, sublayer
    stacks where order determines opinion strength).

    Returns:
        {
            "issues": [
                {
                    "node": "/stage/merge1",
                    "type": "ambiguous_merge",
                    "input_count": 3,
                    "current_order": ["/stage/lighting", "/stage/materials", "/stage/geo"],
                    "suggested_fix": "Verify merge order matches intended layer strength"
                }
            ],
            "clean": bool  # True if no issues found
        }
    """
```

### Implementation approach

1. Start from the render ROP node (Karma LOP or usdrender ROP)
2. Walk backwards through input connections
3. At each node, check:
   - Is it a merge/sublayer node with 2+ inputs?
   - Are the inputs order-dependent? (merge LOP: yes. switch LOP: no.)
   - Is the order explicitly set or just default creation order?
4. For order-dependent multi-input nodes, flag as potential issue
5. Suggest: review order, or use explicit sublayer ordering

### Registration

```python
{
    "name": "solaris_validate_ordering",
    "description": "Detect ambiguous Solaris/LOP network ordering that could cause non-deterministic render output.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "render_node": {"type": "string", "description": "Path to render ROP or Karma LOP. If omitted, finds the first render node."}
        }
    },
    "annotations": {"readOnlyHint": True}
}
```

---

## Step 2: CHARLIE — Wire Validator

Update `synapse/autonomy/validator.py`:

Replace the `_check_solaris_ordering` stub with a real implementation that calls `solaris_validate_ordering`:

```python
async def _check_solaris_ordering(self, plan: RenderPlan) -> PreFlightCheck:
    """Detect ambiguous LOP merge ordering via solaris_validate_ordering handler."""
    result = await self.handler_interface.call("solaris_validate_ordering", {
        "render_node": plan.steps[0].params.get("render_node", "")
    })

    if result.get("clean", True):
        return PreFlightCheck(
            name="solaris_ordering",
            description="Solaris network ordering check",
            severity=CheckSeverity.INFO,
            passed=True,
            message="No ordering ambiguities detected."
        )
    else:
        issues = result.get("issues", [])
        issue_desc = "; ".join(f"{i['node']}: {i['type']}" for i in issues)
        return PreFlightCheck(
            name="solaris_ordering",
            description="Solaris network ordering check",
            severity=CheckSeverity.SOFT_WARN,
            passed=False,
            message=f"Ordering ambiguities detected: {issue_desc}. Review merge order before rendering."
        )
```

---

## Step 3: DELTA — Integration Tests

### `tests/test_integration_pipeline.py`

```python
"""Full pipeline integration tests for FORGE-PRODUCTION."""

# test_full_pipeline_mock — end-to-end with all mocks: intent → report
# test_pipeline_with_ordering_warning — ambiguous merge detected, reported in validation
# test_pipeline_with_hard_failure — missing camera, pipeline stops
# test_pipeline_feedback_loop — bad frames → replan → re-render → passes
# test_pipeline_decision_log_complete — every step has a logged decision
# test_pipeline_checkpoint_resume — interrupt mid-render → resume from checkpoint
# test_pipeline_max_iterations — 3 bad evaluations → stops, reports all attempts
```

### `tests/test_solaris_ordering.py`

```python
"""Tests for Solaris ordering validation."""

# test_clean_network — linear LOP chain → no issues
# test_ambiguous_merge — merge LOP with 3 unsorted inputs → flagged
# test_explicit_order — merge with explicit ordering → not flagged
# test_no_render_node — no render ROP found → graceful error
# test_complex_network — branching + merging → all merge points checked
```

---

## Step 4: End-to-End Test (with live Houdini)

This requires Joe to run manually with Houdini open:

### Test Script: `tests/manual_e2e_forge.py`

```python
"""Manual end-to-end test for FORGE-PRODUCTION pipeline.

Run with Houdini open and SYNAPSE connected:
    python tests/manual_e2e_forge.py

Tests:
1. Simple render: "render frame 1" → single frame output
2. Sequence render: "render frames 1-24" → 24 frames + evaluation report
3. Broken scene: remove camera → validator catches it
4. Feedback loop: low samples → evaluator flags → driver replans
"""
```

**This is a manual test file — not part of pytest suite.**
Mark clearly in docstring. Include step-by-step instructions for Joe.

---

## Gate

```
[ ] solaris_validate_ordering handler implemented and registered
[ ] validator.py uses real ordering check (not stub)
[ ] Integration tests pass (~12 new tests)
[ ] Ordering tests pass (~5 new tests)
[ ] Full pipeline mock test passes end-to-end
[ ] All existing tests pass (target: 1,700+)
[ ] manual_e2e_forge.py ready for Joe to run with live Houdini
```
