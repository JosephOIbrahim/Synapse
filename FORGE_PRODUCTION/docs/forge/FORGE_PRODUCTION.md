# FORGE-PRODUCTION: SOLARIS + AUTONOMY

> **Status:** ACTIVE
> **Priority #1:** Production-grade SOLARIS + autonomous render loop via TOPS/PDG
> **Priority #2:** Camera digital twins (real camera bodies → USD parameters)
> **Agent model:** Claude Sonnet 4.6 via Claude Code Task tool
> **RAG source:** `G:\HOUDINI21_RAG_SYSTEM`

---

## Phases

| Phase | Name | Teams | Gate |
|-------|------|-------|------|
| 1 | RAG Foundation + Solaris Production Recipes | ALPHA, DELTA | All recipes pass routing tests |
| 2 | TOPS Autonomy Engine | BRAVO, CHARLIE, DELTA | Autonomy pipeline unit tests pass |
| 3 | Integration + Solaris Ordering | ALL (coordinated) | End-to-end flow with live Houdini |
| 4 | Camera Digital Twins | ECHO, ALPHA, DELTA | 8+ cameras mapped, recipes work |

**Hard rule:** No phase starts until the previous phase's gate passes.

---

## Team File Ownership

| Team | Exclusive Write | Read Only |
|------|----------------|-----------|
| ALPHA | `rag/skills/houdini21-reference/`, `routing/recipes.py`, `routing/parser.py` | handlers, agent, tests |
| BRAVO | `synapse/handlers_solaris.py`, `synapse/handlers_tops.py`, `synapse/mcp/tools.py`, `synapse/mcp/mcp_server.py` | rag, routing, agent |
| CHARLIE | `synapse/agent/`, `synapse/render_farm.py`, `synapse/autonomy/` (new dir) | handlers, rag, routing |
| DELTA | `tests/` | everything (read-only) |
| ECHO | camera-specific RAG + handlers + recipes | non-camera files |

**If a team needs to touch another team's files:** generate a patch, orchestrator applies it after the owning team's task completes.

---

## Phase 1: RAG Foundation + Solaris Production Recipes

### ALPHA: RAG Ingestion
Dispatch: `.claude/tasks/phase1_alpha_rag.md`

1. Scan `G:\HOUDINI21_RAG_SYSTEM` — catalog structure, topics, coverage
2. Cross-reference against existing `rag/skills/houdini21-reference/`
3. Identify gaps (priority: Solaris production, TOPS advanced, Copernicus, temporal coherence)
4. Ingest — extract + restructure into SYNAPSE RAG format. SHA-256 manifests. Collision-safe `_gen_` prefix.

### ALPHA: Production Recipes
Dispatch: `.claude/tasks/phase1_alpha_recipes.md`

Create 5 production-grade recipes in `routing/recipes.py`:
1. `render_turntable_production` — full turntable with camera orbit, 3-point lighting, ground, shadow catcher, Karma XPU prod settings, AOVs
2. `character_cloth_setup` — character USD ref, MaterialX materials, cloth sim cache, subdivision + displacement
3. `destruction_sequence` — RBD cache → Solaris, instancing debris, volumetric refs, multi-pass render (beauty, depth, motion vec, crypto)
4. `multi_shot_composition` — shot-based USD layers, per-shot overrides on shared base, shot cameras, shot lighting, render layers
5. `copernicus_render_comp` — render pass comp via Copernicus GPU nodes, beauty + utility → final comp, color grade

### DELTA: Test Scaffolding (parallel)
Dispatch: `.claude/tasks/phase1_delta_tests.md`

Tests for all new recipes — routing integration, parameter validation, handler sequence verification.

### Gate
```
[ ] RAG scan report reviewed (no blind copies)
[ ] New RAG files follow existing format + SHA-256 manifests
[ ] All 5 production recipes exist in recipes.py
[ ] routing/parser.py updated with patterns for new recipes
[ ] All recipe tests pass
[ ] Existing tests still pass (full suite)
```

---

## Phase 2: TOPS Autonomy Engine

### BRAVO: TOPS Enhancement
Dispatch: `.claude/tasks/phase2_bravo_tops.md`

1. `tops_monitor_stream` — event-driven cook monitoring via WebSocket push (not polling)
2. `tops_render_sequence` — single-call "render 1-48" interface: validate → create TOPS network → generate work items → cook → return job_id
3. TOPS warm standby — auto-create local scheduler on connect, always ready

### CHARLIE: Autonomy Layer
Dispatch: `.claude/tasks/phase2_charlie_autonomy.md`

New package `synapse/autonomy/` with 4 modules:
1. `planner.py` — decomposes artist intent into RenderPlan (steps, validation checks, gate levels)
2. `validator.py` — pre-flight checks (Solaris ordering, missing assets, render settings, camera, materials, frame range)
3. `evaluator.py` — post-render evaluation (black frame, NaN, fireflies, clipping, temporal coherence, flickering, missing frames)
4. `driver.py` — main loop: Plan → Validate → Execute → Evaluate → Report. Gate integration, checkpoint/resume, max iterations, decision logging.

### DELTA: Integration Tests (parallel)
Dispatch: `.claude/tasks/phase2_delta_tests.md`

Full test suites for planner, validator, evaluator, driver. Mock hou/pdg/WebSocket. ~30+ tests.

### Gate
```
[ ] tops_monitor_stream registered and tested
[ ] tops_render_sequence registered and tested
[ ] TOPS warm standby activates on connect
[ ] synapse/autonomy/ package with all 4 modules
[ ] All autonomy tests pass
[ ] Existing tests still pass
```

---

## Phase 3: Integration + Solaris Ordering

### Coordinated (not parallel)
Dispatch: `.claude/tasks/phase3_integration.md`

1. BRAVO: `solaris_validate_ordering` handler — detect ambiguous LOP merge points
2. CHARLIE: Wire validator.py to use ordering detection
3. DELTA: Integration tests for full pipeline
4. ALL: End-to-end test with live Houdini

### Gate
```
[ ] Full pipeline: intent → plan → validate → TOPS cook → evaluate → report
[ ] Solaris ordering detection works
[ ] Feedback loop completes at least 1 iteration
[ ] Decision log captures full reasoning chain
[ ] All tests pass (target: 1,700+)
```

---

## Phase 4: Camera Digital Twins

### ECHO: Camera Database + Recipes
Dispatch: `.claude/tasks/phase4_echo_cameras.md`

1. `camera_sensor_database.md` — 8+ real cameras with USD parameter mappings
2. `camera_match_real` recipe — camera body name → configured USD camera
3. `camera_match_turntable` — combine with production turntable recipe

### Gate
```
[ ] 8+ cameras in database with verified sensor dimensions
[ ] camera_match_real recipe routes correctly
[ ] camera_match_turntable chains correctly
[ ] USD parameter encoding verified (xn__ prefix)
[ ] All camera tests pass
```

---

## Success Criteria

**Overall:** Artist describes intent → walks away → returns to rendered frames with quality report and agent reasoning for every decision.

**Test target:** 1,800+ (from current 1,611)
**New MCP tools:** ~6
**New package:** `synapse/autonomy/` (4 modules)
**Estimated sessions:** 5

---

*FORGE-PRODUCTION v1.0 | February 2026*
