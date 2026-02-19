# agent.md — SYNAPSE Agent Task Directives

> **Location:** `C:\Users\User\SYNAPSE\.claude\agent.md`
> **Active Sprint:** FORGE-PRODUCTION (SOLARIS + AUTONOMY)
> **Plan:** `docs/forge/FORGE_PRODUCTION.md`

---

## Agent Identity

You are an implementation agent working on SYNAPSE, an AI-Houdini bridge.
You operate under the safety constraints defined in `CLAUDE.md`. All mutations
go through existing safety middleware — you never bypass it.

---

## Active Sprint: FORGE-PRODUCTION

### Phase Detection (run first)

```bash
# Phase 1: Check if production recipes exist
grep -c "render_turntable_production\|character_cloth_setup\|destruction_sequence\|multi_shot_composition\|copernicus_render_comp" synapse/routing/recipes.py 2>/dev/null

# Phase 2: Check if autonomy package exists
ls synapse/autonomy/__init__.py synapse/autonomy/planner.py synapse/autonomy/validator.py synapse/autonomy/evaluator.py synapse/autonomy/driver.py 2>/dev/null

# Phase 3: Check if ordering validation exists
grep -c "solaris_validate_ordering" synapse/handlers_solaris.py 2>/dev/null

# Phase 4: Check if camera database exists
ls rag/skills/houdini21-reference/camera_sensor_database.md 2>/dev/null
```

- **0 recipes found** → Phase 1 active
- **Recipes exist, no autonomy/** → Phase 2 active
- **Autonomy exists, no ordering** → Phase 3 active
- **Ordering exists, no cameras** → Phase 4 active
- **All exist** → FORGE-PRODUCTION complete, normal dev mode

### Read the Plan

Before any work: `cat docs/forge/FORGE_PRODUCTION.md`

This tells you:
- Which phase is active
- Which team you're on
- What files you own (exclusive write)
- What files you can read but NOT modify
- Gate criteria for phase completion

---

## Task Decomposition Rules

### General

1. **One handler per task.** Each agent sub-task implements exactly one handler
   or one test file. Don't bundle.

2. **Handler + Registration + Test = complete.** A task is not done until:
   - Handler exists in the appropriate `handlers_*.py`
   - Tool is registered in `mcp/tools.py` with `inputSchema` and `annotations`
   - Tool is registered in `mcp_server.py` (stdio bridge)
   - Test exists and passes

3. **Read before write.** Before implementing anything:
   - Read existing code in the target file
   - Read the RAG knowledge for the domain
   - Read existing test patterns
   - Match conventions exactly

4. **Respect file ownership.** Check `docs/forge/FORGE_PRODUCTION.md` for which
   team owns which files. If you need to modify a file you don't own, generate
   a patch and report it — don't write directly.

5. **Safety middleware is non-negotiable:**
   - All scene mutations through undo groups
   - Idempotent guards (check-before-mutate)
   - Atomic operations (one mutation per call)
   - Transaction wrappers (rollback on error)

6. **RAG ingestion rules:**
   - Never copy files verbatim from `G:\HOUDINI21_RAG_SYSTEM`
   - Extract knowledge, restructure into SYNAPSE format
   - SHA-256 manifest for every new file
   - Collision-safe prefix: `_gen_` for generated, no prefix for curated
   - Cross-reference existing RAG before creating new files

---

## Autonomy Package Conventions

When working on `synapse/autonomy/`:

### Data Structures (dataclass-based, not dicts)

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class GateLevel(Enum):
    INFORM = "inform"      # Log, don't ask
    REVIEW = "review"      # Show plan, wait for approval
    CONFIRM = "confirm"    # Require explicit approval per step

@dataclass
class RenderStep:
    handler: str           # MCP tool name
    params: dict           # Handler parameters
    description: str       # Human-readable description
    gate: GateLevel = GateLevel.INFORM

@dataclass
class RenderPlan:
    steps: List[RenderStep]
    validation_checks: List[str]
    estimated_frames: int
    gate_level: GateLevel = GateLevel.REVIEW
    # ... etc
```

### Decision Logging

Every non-trivial decision gets logged:

```python
def log_decision(self, context: str, decision: str, reasoning: str):
    """Log to scene memory for artist review."""
    # Use existing memory system
```

### Integration Points

- Planner → uses `routing/recipes.py` for recipe lookup
- Validator → calls handlers via existing MCP interface
- Evaluator → receives frame paths from TOPS work item results
- Driver → orchestrates all three + calls TOPS handlers

---

## Test Conventions

```python
# File naming: test_{module}_{component}.py
# Test naming: test_{what}_{condition}_{expected}

# Mock hou module (existing pattern)
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_hou():
    """Standard hou module mock."""
    hou = MagicMock()
    # ... existing patterns from tests/
    return hou

# Mock TOPS handlers
@pytest.fixture
def mock_tops():
    """Mock TOPS handler responses."""
    return {
        "tops_render_sequence": {"job_id": "test_001", "status": "cooking"},
        "tops_pipeline_status": {"completed": 24, "total": 48, "percent": 50.0},
    }
```

---

## Emergency Protocols

- **Tests failing after changes:** Roll back, report to orchestrator
- **File ownership conflict:** Stop, generate patch, report
- **Unclear requirement:** Ask — don't guess
- **RAG data quality concern:** Flag it, don't ingest
- **Safety middleware bypass temptation:** Never. Ever.
