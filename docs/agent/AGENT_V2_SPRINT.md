# SYNAPSE -- Agent SDK v2 Sprint Instructions

> **Sprint Goal:** Evolve the autonomous VFX co-pilot from a linear tool-use loop into
> a planning-capable, self-healing agent with TOPS integration, checkpoint/resume, and
> viewport-driven verification. The agent should handle multi-step VFX tasks autonomously
> while recovering gracefully from failures.
>
> **Prerequisite:** TOPS/PDG Sprint must be complete (TOPS tools registered in MCP).
> The agent needs TOPS tools to orchestrate PDG workflows autonomously.

---

## 0. PRE-FLIGHT -- Read Before Coding

1. **Read the v1 agent code:**
   - `~/.synapse/agent/synapse_agent.py` -- Main agentic loop (Opus 4.6, MAX_TURNS=30)
   - `~/.synapse/agent/synapse_tools.py` -- 8 tools + 4 memory tools, `execute_tool()` dispatch
   - `~/.synapse/agent/synapse_hooks.py` -- Pre/post execution hooks (advisory, not blocking)
   - `~/.synapse/agent/synapse_ws.py` -- WebSocket client wrapper

2. **Understand v1 limitations:**
   - Linear loop: message -> tool call -> result -> message (no planning)
   - No checkpointing: context lost if agent crashes mid-task
   - No self-healing: failures stop the loop, no retry/recovery strategy
   - Missing tools: no TOPS, no viewport capture, no batch commands
   - No multi-goal decomposition: single prompt drives entire session

3. **Verify TOPS is available** before starting:
   ```bash
   grep -c "tops_" C:/Users/User/SYNAPSE/mcp_server.py
   # Must return 14+ (all TOPS tools registered)
   ```

---

## 1. ARCHITECTURE

### v2 Agent Architecture

```
User Goal ("Light and render the cave scene at sunset")
    |
synapse_planner.py (NEW)
    |  Decomposes into sub-goals with dependencies
    |  [inspect scene] -> [set up lighting] -> [assign materials] -> [test render] -> [final render]
    |
synapse_agent.py (ENHANCED)
    |  Executes sub-goals sequentially
    |  Checkpoint after each sub-goal
    |  Self-heal on failure (retry, alternative approach, rollback)
    |
synapse_tools.py (EXPANDED)
    |  8 existing + 6 new TOPS tools + viewport capture + batch
    |
synapse_checkpoint.py (NEW)
    |  Save/restore agent state to disk
    |  Resume interrupted tasks from last checkpoint
    |
synapse_hooks.py (ENHANCED)
    |  Viewport verification after mutations
    |  TOPS cook validation after pipeline runs
    |
Synapse WebSocket -> Houdini
```

### Key Principle

The v2 agent builds ON TOP of v1 -- no rewrites. The linear tool-use loop remains the
execution engine. Planning and self-healing are layers that decompose and retry at the
sub-goal level, not at the individual tool-call level.

---

## 2. NEW MODULES

### 2.1 `synapse_planner.py` -- Multi-Goal Decomposition

Decomposes a user goal into an ordered list of sub-goals with dependencies.

```python
@dataclass
class SubGoal:
    id: str                          # deterministic_uuid from description
    description: str                 # Natural language ("Set up key light")
    tools_hint: list[str]            # Suggested tools ["synapse_execute", "synapse_inspect_node"]
    depends_on: list[str]            # Sub-goal IDs that must complete first
    verification: str                # How to check success ("Verify key light exists at /lights/key")
    max_retries: int = 2             # Self-healing retry limit
    status: str = "pending"          # pending | running | completed | failed

@dataclass
class Plan:
    goal: str                        # Original user goal
    sub_goals: list[SubGoal]         # Ordered list
    created_at: float                # time.monotonic()
```

**Planning uses Claude itself** -- send the goal + scene context to the model and ask it to
decompose into sub-goals. This is a single LLM call at the start, not a separate agent.

### 2.2 `synapse_checkpoint.py` -- State Persistence

Saves agent state to `~/.synapse/agent/checkpoints/` after each completed sub-goal.

```python
@dataclass
class Checkpoint:
    plan: Plan                       # Current plan with sub-goal statuses
    messages: list[dict]             # Conversation history (truncated to last 20)
    completed_goals: list[str]       # Sub-goal IDs completed
    scene_snapshot: dict             # Scene info at checkpoint time
    timestamp: float                 # time.monotonic()

def save_checkpoint(checkpoint: Checkpoint, path: Path) -> None: ...
def load_checkpoint(path: Path) -> Checkpoint | None: ...
def resume_from_checkpoint(path: Path) -> tuple[Plan, list[dict]]: ...
```

**Checkpoint files are JSONL** -- one JSON object per line, append-only. The latest
checkpoint is the last line. Deterministic naming: `{goal_hash}_{subgoal_id}.jsonl`.

### 2.3 New Tools in `synapse_tools.py`

| Tool | Type | Description |
|------|------|-------------|
| `synapse_tops_cook` | TOPS | Cook a TOP node with optional retry |
| `synapse_tops_status` | TOPS | Get pipeline health for a topnet |
| `synapse_tops_diagnose` | TOPS | Diagnose failures in a TOP node |
| `synapse_tops_wedge` | TOPS | Set up and cook a parameter wedge |
| `synapse_tops_work_items` | TOPS | Query work items with state filter |
| `synapse_tops_cook_stats` | TOPS | Get cook timing and stats |
| `synapse_capture_viewport` | Render | Capture viewport screenshot for visual verification |
| `synapse_batch` | Control | Execute multiple commands atomically |

All new tools follow the existing pattern: tool schema in `TOOL_DEFINITIONS`, dispatch
in `execute_tool()`, WebSocket call to Synapse server.

---

## 3. SELF-HEALING PATTERNS

### 3.1 Retry with Backoff

When a sub-goal fails:
1. Log the failure reason
2. If retries remain: checkpoint, adjust approach (e.g., different parameter values), retry
3. If retries exhausted: mark sub-goal as failed, report to user with diagnostics

### 3.2 Viewport Verification

After visual mutations (lighting, materials, geometry):
1. Capture viewport screenshot via `synapse_capture_viewport`
2. Include in next message to Claude for visual assessment
3. Agent decides if result matches intent or needs adjustment

### 3.3 TOPS Pipeline Recovery

After TOPS cook failures:
1. Call `synapse_tops_diagnose` to identify root cause
2. If work items failed: dirty and retry (up to max_retries)
3. If scheduler issue: report configuration suggestion
4. If upstream failure: trace back to source and attempt fix

---

## 4. PHASES

| Phase | Scope | Gate Files |
|-------|-------|------------|
| **Phase 1 -- Tools** | Add TOPS + viewport + batch tools to agent | `synapse_tools.py` updated with 8 new tools |
| **Phase 2 -- Planner** | Multi-goal decomposition, sub-goal execution | `synapse_planner.py` exists, tests pass |
| **Phase 3 -- Checkpoint** | Save/restore, resume interrupted tasks | `synapse_checkpoint.py` exists, tests pass |
| **Phase 4 -- Self-Heal** | Retry logic, viewport verification, TOPS recovery | Integration tests pass |

### Phase 1 Rules
- Add tool schemas to `TOOL_DEFINITIONS` list
- Add dispatch cases to `execute_tool()`
- Each new tool maps to an existing Synapse server command
- Write unit tests for each tool dispatch

### Phase 2 Rules
- Planner is a single LLM call, not a separate agent loop
- Sub-goals are plain text descriptions, not code
- Dependencies form a DAG -- validate no cycles
- Plan is deterministic for the same goal + scene context (He2025)

### Phase 3 Rules
- Checkpoints are append-only JSONL
- Checkpoint after every completed sub-goal
- Resume loads latest checkpoint and continues from there
- Old checkpoints auto-prune after 7 days

### Phase 4 Rules
- Self-healing is per sub-goal, not per tool call
- Maximum 2 retries per sub-goal by default
- Viewport verification is optional (controlled by sub-goal `verification` field)
- All retry/recovery decisions logged to memory

---

## 5. FILESYSTEM GATES

Sprint C is complete when ALL of these exist:

```
~/.synapse/agent/synapse_planner.py      -- Multi-goal planner
~/.synapse/agent/synapse_checkpoint.py   -- Checkpoint/resume
~/.synapse/agent/tests/test_planner.py   -- Planner tests (must pass)
```

**Verification:**
```bash
ls ~/.synapse/agent/synapse_planner.py ~/.synapse/agent/synapse_checkpoint.py \
   ~/.synapse/agent/tests/test_planner.py 2>/dev/null | wc -l
# Must return 3
python -m pytest ~/.synapse/agent/tests/test_planner.py -v
# Must pass
```

---

## 6. He2025 COMPLIANCE

| Pattern | Applied In |
|---------|-----------|
| `deterministic_uuid()` | Sub-goal IDs (content-based, not random) |
| `time.monotonic()` | Plan timestamps, checkpoint timestamps |
| `sorted()` | Sub-goal dependency resolution order |
| `dict(sorted())` | Scene snapshot serialization |
| `encoding="utf-8"` | All file I/O (checkpoints, logs) |

---

*Cross-reference: TOPS_SPRINT.md for TOPS tool definitions, CLAUDE.md for He2025 patterns.*
