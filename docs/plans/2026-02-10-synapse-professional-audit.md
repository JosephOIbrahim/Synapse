# Synapse v5.0.0 Professional VFX Audit

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Brutally honest evaluation of Synapse from the perspective of a senior VFX generalist who has shipped commercials and features at MPC, Framestore, ILM, and DNEG -- someone who opens Houdini 21 before coffee and doesn't close it until wrap.

**Architecture:** Score each axis 1-10 with evidence from the actual codebase. Identify the precise gaps between current state and a 9. Then produce an actionable roadmap.

**Methodology:** Every claim below is grounded in specific files, line counts, and code paths verified on 2026-02-10. No inflation.

---

## The Evaluator's Perspective

I'm writing this as someone who:
- Has used Houdini professionally for 10+ years across commercials, episodic, and features
- Works in Solaris/LOPs daily for lighting and layout
- Writes VEX in attribwrangles 20+ times a day
- Manages hundreds of Karma XPU renders per week
- Relies on Vellum for cloth/hair, KineFX for rigging, Crowds for background action
- Uses PDG/TOPs for wedging, dependency graphs, and farm submission
- Lives inside a studio pipeline (ShotGrid, Deadline, ACES, review tools)
- Has strong opinions about what "production-ready" means after surviving 80-hour crunch weeks

---

## Axis 1: Frontier AI Worthiness

### Score: 7.5 / 10

### What earns points

**The architecture is genuinely novel and sophisticated.** There is no other open-source tool that bridges Claude to Houdini via a 6-tier routing cascade with He2025 determinism compliance. This is original research-grade work, not a wrapper.

Evidence:
- **6-tier routing cascade** (`routing/router.py`, 833 lines): Cache(O(1)) -> Recipe(O(1)) -> Tier0/regex -> Tier1/RAG -> Tier2/Haiku -> Tier3/Agent. Each tier is cheapest-first with speculative T0+T1 parallelism via ThreadPoolExecutor(2).
- **Tier pinning** with He2025 batch invariance: Same input + context maps to same tier. LRU cache (1,000 pins), stale pin eviction by epoch ID (monotonic int, not wall-clock).
- **Epoch-based adaptive routing** (`routing/adaptation.py`, 183 lines): Fixed-size epochs (100 commands), Kahan-summed success rates, sorted aggregation. The adaptation learns from outcomes without violating determinism. This is a genuine contribution.
- **37 MCP tools** with concurrent dispatch (`mcp_server.py`, 1,313 lines): `_pending` dict + `_recv_loop` coroutine -- true parallel tool calls, no blocking lock. This is how you'd design it at scale.
- **Determinism primitives** (`core/determinism.py`, 367 lines): `round_float()`, `kahan_sum()`, `deterministic_uuid()`, `@deterministic` decorator. Content-based IDs, not random UUIDs.
- **Tamper-evident audit chain** (`core/audit.py`, 402 lines): SHA-256 hash chain, daily JSONL, optional Fernet encryption. 9 audit levels, 12 categories. Now wired into handler dispatch.

**What's genuinely frontier:**
- The idea that an AI assistant should have a *routing cascade* that selects the cheapest-sufficient computation path is ahead of how most AI tools work today
- Tier pinning + epoch adaptation is a novel approach to the "consistency vs. learning" tension in LLM tool systems
- The He2025 determinism compliance (verified 9/9) means reproducible behavior -- rare in AI tooling
- Project memory with semantic search means the AI accumulates context across sessions -- no other Houdini tool does this

### What costs points

**No multi-agent orchestration for complex VFX tasks.** The Agent SDK exists (`~/.synapse/agent/`) but it's a single-agent loop. A frontier system would decompose "light this shot for broadcast" into parallel sub-tasks: set up key/fill/rim, check exposure ratios, render preview, adjust based on visual feedback, iterate.

**No visual feedback loop in the routing cascade.** The system can capture viewports and render frames, but there's no automated "render -> analyze -> adjust -> re-render" cycle. A senior artist would expect the AI to look at its own render and say "the fill is too hot, let me back it off."

**Knowledge base is thin relative to the ambition.** 1,108 lines across 17 RAG topics is a cheat sheet, not a knowledge base. Houdini's official documentation runs to tens of thousands of pages. The RAG lookup returns surface-level answers that a junior TD would outgrow in their first month.

**No tool-use planning.** The system dispatches tools one at a time based on the current message. A frontier system would plan multi-step operations: "To set up this pyro shot, I need to: create source geo -> scatter -> wrangle emission attributes -> add pyrosolver -> set voxel size -> cache -> import to LOPs -> assign volume material -> render preview." The recipe system partially addresses this, but recipes are static templates, not dynamic plans.

### Gap to 9

1. Multi-step tool planning with visual feedback loops
2. Knowledge base 10x deeper (10,000+ lines, not 1,100)
3. Multi-agent decomposition for complex workflows
4. Self-evaluation: render, analyze composition/exposure, iterate

---

## Axis 2: VFX Utility

### Score: 5 / 10

This is the harshest score and it will sting. But honesty serves the project.

### What earns points

**The core operations genuinely work.** Creating nodes, setting parameters, connecting networks, reading USD attributes, rendering frames, capturing viewports -- these cover the atomic operations of Houdini work. The parameter alias system (`core/aliases.py`) with USD name translation means the AI can understand "set the intensity" without knowing the encoded parm name `xn__inputsintensity_i0a`.

**Introspection is solid** (`server/introspection.py`, 417 lines): Modified parameter detection (comparing current vs. default), geometry summary with attribute sampling, recursive input graph traversal up to N levels, warning/error collection. This is genuinely useful for understanding an unfamiliar scene.

**Material workflow is complete:** create_material, assign_material, read_material. MaterialX standard surface with base_color, roughness, metalness. This covers 80% of look-dev starting points.

**Viewport capture + Karma render** with image return to the AI. This is the visual feedback that makes the tool actually useful rather than blind.

### What costs points

**Missing entire production domains.** A senior generalist at a top studio uses these daily:

| Domain | Status in Synapse | Importance |
|--------|-------------------|------------|
| Vellum cloth/hair/grain | Not present | Critical for character FX |
| KineFX rigging/retargeting | Not present | Critical for animation |
| Crowd simulation | Not present | Essential for features/episodic |
| Advanced FLIP/ocean | 49-line cheat sheet | Essential for water FX |
| Terrain (heightfields, erosion) | Not present | Essential for environment |
| Wire/strand dynamics | Not present | Used weekly |
| Muscle simulation | Not present | Used for creature work |
| UV unwrapping/layout | Not present | Used daily |
| SOP Solver / feedback loops | Not present | Core Houdini pattern |
| CHOP networks | Not present | Used for procedural animation |

**The RAG knowledge is surface-level.** Let me be specific:

- `lighting.md` (44 lines): Lists light types, mentions three-point setup with `intensity=3-5`. **This violates the project's own Lighting Law** ("Intensity is ALWAYS 1.0 or below, brightness controlled by EXPOSURE"). A senior lighter would catch this immediately and lose trust in the system.
- `pyro_fx.md` (45 lines): Covers the basic chain (scatter -> wrangle -> volumerasterize -> pyrosolver) but nothing about: combustion model tuning, sourcing from animated geometry, microsolvers, upresing, caching strategy for multi-shot pyro, or Karma volume rendering settings.
- `rbd_simulation.md` (62 lines): Basic fracture -> assemble -> solve. No coverage of: impact data, constraint networks at scale, partial destruction, SOP-level RBD vs. Bullet vs. Vellum grains for debris, speed optimization for thousands of pieces, proxy collision geometry.
- `vex_functions.md` (85 lines): A function reference list. No workflow patterns like: "how to build a custom deformer", "how to transfer attributes between mismatched topology", "how to build a noise-based displacement setup", "how to write a point relaxation solver".

**Average RAG file depth: 65 lines.** That's a quick-reference card, not production knowledge. For comparison, SideFX's documentation for just the Pyro Solver is hundreds of pages.

**Recipes don't match real workflows.** The 11 recipes include three-point lighting, scatter-copy, dome light, camera rig, pyro source, material setup, karma render, sopimport, and edit transform. These are "first hour of a Houdini class" setups, not production patterns. A senior artist would want:
- "Set up a character cloth sim with collision" (Vellum + constraints + collision geo + cache)
- "Build a destruction sequence" (fracture + constraints + glue network + trigger animation + cache + debris + dust pyro)
- "Create a render-ready turntable" (camera + lighting + backdrop + render settings + AOVs + frame range)
- "Set up ocean with whitewater" (ocean spectrum + FLIP + whitewater solver + mesh + shader)

**No pipeline integration.** At MPC/DNEG/ILM, you don't render on your workstation. You submit to Deadline or Tractor. You publish assets to ShotGrid. You version files through a pipeline. Synapse has no awareness of:
- Render farm submission
- Asset management (publish/version/checkout)
- Shot management (ShotGrid/Ftrack)
- File versioning conventions
- ACES color management
- Review tools (RV, SyncSketch)

### Gap to 9

1. RAG knowledge 10x deeper, with workflow-oriented content (not just reference lists)
2. Fix the lighting.md Lighting Law violation
3. Cover missing domains: Vellum, KineFX, Crowds, terrain, ocean, CHOP, UV
4. Recipes for real production workflows (not just beginner setups)
5. Studio pipeline awareness (even if not integrated -- understanding file conventions, naming schemes, version control)

---

## Axis 3: Professional Development Quality

### Score: 7 / 10

### What earns points

**Exceptional project structure and documentation.** `CLAUDE.md` is one of the best project documentation files I've seen -- it covers architecture, testing patterns, gotchas, conventions, and domain knowledge in a format that makes a new developer productive immediately. The plan documents in `docs/plans/` show deliberate architectural thinking.

**Comprehensive testing.** 637 core tests + 49 agent SDK + 44 design system = 730 tests. The test patterns are sophisticated: `importlib.util.spec_from_file_location` for Houdini-free testing, proper `hou` stub management in conftest, correct patching patterns documented. `test_routing.py` alone has ~323 tests including a routing benchmark with 40+ utterances.

**Clean architecture.** 7 packages with clear separation:
- `core/` (protocol, aliases, determinism, audit, gates, crypto, queue) = foundation
- `memory/` (store, models, context, markdown) = persistence
- `routing/` (router, parser, knowledge, recipes, cache, adaptation) = intelligence
- `server/` (websocket, handlers, resilience, introspection, guards) = execution
- `session/` (tracker, summary) = state management
- `agent/` (executor, protocol, learning) = autonomy
- `ui/` (panel, tabs) = display

**Design system is Pentagram-quality.** The `.synapse/design/` package with tokens, icon generation from construction rules (21 SVGs), and Qt stylesheet generation is professional-grade visual design.

**Zero dependencies in core.** The base package runs on stdlib alone. Optional deps via extras (`websockets`, `mcp`, `anthropic`, `cryptography`). This is the right choice for embedding inside Houdini's Python.

### What costs points

**Single-developer project.** There are no code reviews, no CI beyond basic pytest, no integration tests against actual Houdini sessions. The `conftest.py` hou stub is clever but means every handler is tested against a mock, never against real Houdini.

**No type checking enforced.** No `mypy` in CI, no `pyright` configuration. Type hints are present but not validated. In a production codebase at a studio, this would be caught in code review.

**No API documentation generated.** The code has docstrings, but there's no generated API docs (Sphinx, MkDocs). A developer wanting to extend Synapse has to read source.

**Backwards compatibility burden.** `NexusServer`, `NexusHandler`, `EngramMemory`, `HyphaeAuditLog` -- legacy names preserved for migration. This is good practice, but the sheer number of aliases in `__init__.py` (30+ backwards-compat names) suggests rapid renaming that would frustrate external users.

### Gap to 9

1. Integration tests against real Houdini (even if manual/optional)
2. Type checking in CI (mypy --strict or pyright)
3. Generated API documentation
4. Contribution guide and external developer onboarding

---

## Axis 4: Production Readiness

### Score: 6.5 / 10

### What earns points

**Structured logging is now complete.** 0 print() statements remain. All output goes through `logging` module with proper logger hierarchy (`synapse.server`, `synapse.memory`, `synapse.resilience`, etc.). This is table stakes for production, and it's now done.

**Resilience layer is genuine** (`server/resilience.py`, 887 lines):
- Token bucket rate limiter (500 TPS, 2000 burst, per-client tracking)
- Circuit breaker with configurable failure thresholds, half-open probing, error classification (user errors don't trip it)
- Port manager with automatic failover
- Watchdog for main thread freeze detection
- Backpressure controller with 4 levels (NORMAL -> ELEVATED -> HIGH -> CRITICAL)
- Health monitor aggregating all components

**Audit trail with hash chain integrity.** Every mutating command is logged with SHA-256 chain linking. Daily JSONL files. Optional Fernet encryption. This satisfies security audit requirements.

**Graceful shutdown.** Signal handlers (SIGTERM, SIGINT) when running standalone. atexit cleanup for MCP WebSocket. Existing `_signal_all_pending(exc)` handles in-flight futures.

**Thread safety.** ReadWriteLock (writer-priority) in MemoryStore. threading.Lock for tier-pin cache. threading.Event for background store loading. ThreadPoolExecutor(2) for fire-and-forget logging.

**Error handling with coaching tone.** Errors say "Couldn't find node at /obj/missing" with parameter suggestions, not stack traces. This matters when the artist sees error output.

### What costs points

**Never tested under real load.** The resilience layer exists but has never been exercised with:
- 50+ concurrent tool calls
- 12-hour sustained sessions
- Network interruptions mid-render
- Houdini crash and recovery
- Multiple clients connected simultaneously

**Memory store is file-based JSONL.** For a single artist, fine. For a studio with 200 artists sharing project memory? JSONL with file locks will not scale. No database backend option.

**No telemetry or crash reporting.** If something goes wrong in production, there's no way to diagnose it after the fact beyond reading log files. No structured error reporting, no performance metrics dashboard (the Prometheus exporter exists but there's no collection or visualization).

**No horizontal scaling.** Single WebSocket server, single Houdini instance. Studios run Houdini on render farms with hundreds of nodes. Synapse can't distribute work.

**No automated health recovery.** The circuit breaker can trip, but there's no automated recovery beyond the half-open probe. If Houdini crashes, Synapse doesn't restart it. If the WebSocket drops, the MCP server retries but with limited intelligence.

**Resilience was just enabled by default.** The `enable_resilience=True` change was made in this v5.0 release. It hasn't been battle-tested in any real session yet. The env var override (`SYNAPSE_RESILIENCE=0`) suggests the developers themselves may need to disable it.

**No security model.** Anyone on localhost can connect to port 9999 and execute arbitrary Python in Houdini. No authentication, no authorization, no TLS. For a personal tool this is fine. For a studio with shared workstations, this is a security incident.

### Gap to 9

1. Load testing (sustained sessions, concurrent clients, Houdini crash recovery)
2. Security: authentication, authorization, TLS option
3. Database-backed memory for multi-artist workflows
4. Telemetry and crash reporting
5. Automated health recovery and Houdini session management

---

## Summary Scorecard

| Axis | Score | One-Line Verdict |
|------|-------|-----------------|
| **Frontier AI** | **7.5** | Genuinely novel architecture, but no visual feedback loop or multi-step planning |
| **VFX Utility** | **5.0** | Core ops work, but missing entire production domains and knowledge is surface-level |
| **Professional Dev** | **7.0** | Excellent docs/testing/architecture, but single-developer and no type checking |
| **Production Ready** | **6.5** | Right patterns in place, but untested under real load and no security model |

**Weighted Average: 6.5 / 10**

---

## What a Senior Artist Would Actually Say

> "Look, the architecture is impressive -- I haven't seen anything else that bridges Claude to Houdini with this level of thought. The routing cascade, the determinism stuff, the audit trail -- that's serious engineering. And the coaching tone in errors is a nice touch.
>
> But when I sit down to actually USE this on a shot? I can create nodes and set parms, sure. But I can't ask it to set up a Vellum cloth sim. I can't ask it to help me with KineFX retargeting. The pyro knowledge is a cheat sheet I could write on a Post-It. And the lighting guide says to set intensity to 3-5, which is wrong by the project's own rules.
>
> For me to actually reach for this during crunch, I need to trust it. And trust comes from depth, not breadth. I'd rather have 5 tools that deeply understand lighting, pyro, and materials than 37 tools that know a little about everything.
>
> The bones are great. The flesh needs work."

---

## Actionable Roadmap: From 6.5 to 9

### Phase A: Fix What's Wrong (VFX Utility 5 -> 6.5)
1. Fix lighting.md Lighting Law violation (intensity -> exposure)
2. Deepen existing RAG files to 200+ lines each with workflow patterns
3. Add missing critical domains: Vellum, KineFX, terrain (even surface-level)

### Phase B: Deepen What Works (VFX Utility 6.5 -> 8, Frontier 7.5 -> 8.5)
4. Build "render -> analyze -> adjust" visual feedback loop
5. Create 10 production-grade recipes (cloth setup, destruction, turntable, ocean, etc.)
6. Expand RAG to 5,000+ lines with workflow-oriented patterns
7. Add multi-step tool planning to the routing cascade

### Phase C: Harden for Production (Production 6.5 -> 8.5)
8. Load test: 12-hour session, 50 concurrent calls, Houdini crash/recovery
9. Add authentication (even basic API key)
10. Integration test suite against real Houdini

### Phase D: Studio-Ready (All axes -> 9)
11. Pipeline integration awareness (ShotGrid concepts, file versioning conventions)
12. Multi-artist memory (database-backed store)
13. Type checking in CI
14. Generated API documentation

**Estimated effort:** Phase A = 1 week. Phase B = 3 weeks. Phase C = 2 weeks. Phase D = 4 weeks.

---

*Assessment by: Claude (channeling a 10-year senior VFX generalist, NYC/London commercial and feature pipeline experience)*
*Date: 2026-02-10*
*Synapse version audited: 5.0.0 (637 tests, 37 MCP tools, 17 RAG files / 1,108 lines)*
