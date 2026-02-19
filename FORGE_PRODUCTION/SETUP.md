# FORGE-PRODUCTION Setup

## Quick Start

### 1. Copy files into your SYNAPSE repo

```powershell
# From wherever you downloaded this:
Copy-Item -Path "docs\forge" -Destination "C:\Users\User\SYNAPSE\docs\forge" -Recurse
Copy-Item -Path ".claude\tasks" -Destination "C:\Users\User\SYNAPSE\.claude\tasks" -Recurse
Copy-Item -Path ".claude\agent.md" -Destination "C:\Users\User\SYNAPSE\.claude\agent.md" -Force
```

### 2. Verify file placement

```
C:\Users\User\SYNAPSE\
├── .claude\
│   ├── agent.md                          ← Updated for FORGE-PRODUCTION
│   └── tasks\
│       ├── phase1_alpha_rag.md           ← RAG scan + ingestion + recipes
│       ├── phase1_delta_tests.md         ← Recipe test scaffolding
│       ├── phase2_bravo_tops.md          ← TOPS handlers (monitor, sequence, warm)
│       ├── phase2_charlie_autonomy.md    ← Autonomy package (planner/validator/evaluator/driver)
│       ├── phase2_delta_tests.md         ← Autonomy test suites
│       ├── phase3_integration.md         ← Integration + Solaris ordering
│       └── phase4_echo_cameras.md        ← Camera digital twins
├── docs\
│   └── forge\
│       └── FORGE_PRODUCTION.md           ← Master plan
└── ... (existing repo)
```

### 3. Add to CLAUDE.md

Add this block to your existing `CLAUDE.md` (near the top, after the project identity section):

```markdown
## Active Sprint: FORGE-PRODUCTION

**Plan:** `docs/forge/FORGE_PRODUCTION.md` — read this first.
**Agent directives:** `.claude/agent.md` — loaded for all Task sub-agents.
**Task prompts:** `.claude/tasks/` — dispatch files for each team.

### Phase Detection (run on session start)
```bash
grep -c "render_turntable_production" synapse/routing/recipes.py 2>/dev/null
ls synapse/autonomy/__init__.py 2>/dev/null
grep -c "solaris_validate_ordering" synapse/handlers_solaris.py 2>/dev/null
ls rag/skills/houdini21-reference/camera_sensor_database.md 2>/dev/null
```

Phase 1 active if no production recipes.
Phase 2 active if recipes exist but no autonomy/.
Phase 3 active if autonomy/ exists but no ordering validator.
Phase 4 active if ordering exists but no camera database.
All exist = FORGE-PRODUCTION complete.

**RAG Source:** `G:\HOUDINI21_RAG_SYSTEM` — Houdini 21 reference knowledge.
```

---

## How to Dispatch Agent Teams

### Option A: Full task file (recommended)

Open Claude Code in your SYNAPSE directory. Use the Task tool and paste the contents of the relevant `.claude/tasks/` file.

**Phase 1 (parallel):**
```
# Terminal 1: ALPHA — RAG + Recipes
Task: [paste contents of .claude/tasks/phase1_alpha_rag.md]

# Terminal 2: DELTA — Test scaffolding  
Task: [paste contents of .claude/tasks/phase1_delta_tests.md]
```

**Phase 2 (parallel):**
```
# Terminal 1: BRAVO — TOPS handlers
Task: [paste contents of .claude/tasks/phase2_bravo_tops.md]

# Terminal 2: CHARLIE — Autonomy package
Task: [paste contents of .claude/tasks/phase2_charlie_autonomy.md]

# Terminal 3: DELTA — Autonomy tests
Task: [paste contents of .claude/tasks/phase2_delta_tests.md]
```

**Phase 3 (sequential):**
```
# Single terminal, run steps in order
Task: [paste contents of .claude/tasks/phase3_integration.md]
```

**Phase 4 (parallel):**
```
# Terminal 1: ECHO — Camera database + recipes
Task: [paste contents of .claude/tasks/phase4_echo_cameras.md]

# Terminal 2: DELTA — Camera tests (after ECHO delivers spec)
```

### Option B: Quick dispatch (shorter prompt)

If you want a shorter dispatch, use:

```
Read docs/forge/FORGE_PRODUCTION.md and .claude/tasks/phase1_alpha_rag.md.
Execute TEAM ALPHA Phase 1 deliverables. Report before ingesting any RAG files.
```

### Option C: Orchestrator mode

Run the main Claude Code thread as orchestrator:

```
Read docs/forge/FORGE_PRODUCTION.md.
Run phase detection to determine active phase.
Dispatch the appropriate teams via Task tool.
Run gate checks after all teams complete.
```

---

## Gate Checks

Run these between phases to verify completion:

### After Phase 1
```bash
# Recipes exist?
grep -c "render_turntable_production\|character_cloth_setup\|destruction_sequence\|multi_shot_composition\|copernicus_render_comp" synapse/routing/recipes.py

# Tests pass?
python -m pytest tests/test_forge_recipes.py -v

# Full suite still passes?
python -m pytest tests/ -x --timeout=60
```

### After Phase 2
```bash
# Autonomy package exists?
ls synapse/autonomy/__init__.py synapse/autonomy/planner.py synapse/autonomy/validator.py synapse/autonomy/evaluator.py synapse/autonomy/driver.py

# TOPS handlers registered?
grep -c "tops_monitor_stream\|tops_render_sequence" synapse/mcp/tools.py

# Tests pass?
python -m pytest tests/test_autonomy_*.py -v

# Full suite?
python -m pytest tests/ -x --timeout=60
```

### After Phase 3
```bash
# Ordering validator exists?
grep -c "solaris_validate_ordering" synapse/handlers_solaris.py

# Integration tests pass?
python -m pytest tests/test_integration_pipeline.py tests/test_solaris_ordering.py -v

# Full suite?
python -m pytest tests/ -x --timeout=60
```

### After Phase 4
```bash
# Camera database exists?
ls rag/skills/houdini21-reference/camera_sensor_database.md

# Camera recipe exists?
grep -c "camera_match_real\|camera_match_turntable" synapse/routing/recipes.py

# Tests pass?
python -m pytest tests/test_camera_twins.py -v

# FULL suite — final check
python -m pytest tests/ --timeout=60
echo "Target: 1,800+ tests"
```

---

## Troubleshooting

**Agent modified files it doesn't own:**
Roll back with git, re-dispatch with emphasis on file ownership rules.

**Tests failing after Phase N:**
Don't proceed to Phase N+1. Fix first. Run `git diff` to see what changed.

**RAG scan found unexpected format:**
Report structure to Joe before ingesting. Never blind-copy.

**Phase detection gives wrong result:**
Run the bash checks manually. The gates are filesystem-based — if files exist, the phase is done.

**Agent asks questions you can't answer:**
Check existing codebase patterns first. If truly ambiguous, pause and ask Joe in Desktop.
