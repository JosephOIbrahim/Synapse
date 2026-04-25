# SPRINT 3 — SYNAPSE Inside-Out Refactor — EXECUTE

> Continuation from Sprint 2 Week 1 commit `5e6fc0c`
> 
> Planning arc closed across three Gemini Deep Think rounds.
> All architectural forks resolved. Execution begins with Spike 0.

---

## Capsule

```
+== PROJECT CAPSULE: SYNAPSE 2.0 — Sprint 3 =========+
| WHERE WE ARE:        Sprint 3 execution start       |
| MILE MARKER:         Spike 0 of 4 (planning done)   |
| WHAT I WAS THINKING: Transport refactor from        |
|                      outside-in (WebSocket bridge)  |
|                      to inside-out (in-process      |
|                      Agent SDK in Houdini).         |
|                      First proof of physics is      |
|                      SDK import in hython.          |
| NEXT ACTION:         Run `hython spikes/spike_0.py` |
|                      while `rg -l websocket tests/` |
|                      runs in parallel terminal.     |
| BLOCKERS:            None until Spike 0 returns.    |
| ENERGY REQUIRED:     Implementation (activation 3). |
|                      First empirical signal after   |
|                      ~8 miles of planning.          |
| IDEAS PARKED:        Phase 4 native migration,      |
|                      sidecar index, peer discovery, |
|                      archive rotation, cost caps.   |
+=====================================================+
```

---

## The thesis

**SYNAPSE today:** agent in external process → WebSocket → Houdini (outside-in).

**SYNAPSE after this sprint:** Agent SDK embedded inside Houdini's Python interpreter. Tool calls become in-process Python calls. WebSocket survives as optional remote-access layer for external clients only (inside-out).

**Portfolio implication:** same refactor pattern applies to Moneta (Nuke), Octavius, and Cognitive Bridge later. Architectural decisions here lock in portfolio-wide patterns.

---

## Architectural Decisions (LOCKED — do not re-litigate)

### Transport
- Agent SDK runs in-process inside Houdini (`hython` / `houdini.exe`)
- Tools become pure Python functions behind a `Dispatcher` interface (Strangler Fig pattern)
- WebSocket becomes a thin JSON-RPC adapter calling the Dispatcher
- Both transports live simultaneously during migration — `master` stays shippable

### Threading
- Agent loop: background daemon thread
- Tool dispatch: `hdefereval.executeInMainThreadWithResult()` marshals to Houdini main thread
- Standard DCC pattern (Maya `executeDeferred`, Unreal `AsyncTask(GameThread)`, Blender equivalent)

### USD Cognitive Substrate
- **Schema:** typed conventions + dataclass validators (zero-dep — NOT Pydantic)
- **Topology:** stage-per-session + stable Agent Assets
  - Session stages reference Agent Asset stages by path
  - Pixar Shot/Asset analog
- **Rollouts:** sibling prims under `/Candidates` scope
  - NOT VariantSets (Pcp cache mutex kills parallel evaluation)
- **FORGE:** native Specializes arcs on the agent's Asset prim
- **Atomic writes:** `Stage.Export(tmp_path)` → `os.replace(tmp, session_path)`
- **customData on `/Session` root Scope:**
  - `cog:dcc_host` (string, e.g. `"houdini_21.0.631"`)
  - `cog:session_status` (enum: `active` | `completed` | `crashed`)
  - `cog:tools_used` (string array)
  - `cog:tokens_used` (int64)
  - `cog:started_at` (ISO8601 string)
  - `cog:agent_version` (semver string)

### Code boundary
- `synapse.cognitive.*` — pure Python. USD stage, schema, dispatcher. **Zero `hou` imports.**
  - Must compose across DCCs later (Moneta, Octavius)
- `synapse.host.*` — Houdini UI, `hou` imports, Qt threads, daemon bootstrap
- Lint hook enforces: any file under `synapse/cognitive/**` fails CI on `import hou`

### Authentication
- `hou.secure.setPassword('synapse_anthropic', key)` — binds to Windows Credential Manager
- Zero deps, OS-level secret management
- Agent retrieves via `hou.secure.password('synapse_anthropic')`

---

## Hard Invariants

Constitutional for this architecture. Violation breaks the portfolio thesis.

### Invariant 1 — Test Mode Bypass

The Dispatcher MUST expose `is_testing=True` that runs synchronously on the calling thread, bypassing `executeInMainThreadWithResult`.

**Rationale:** Headless `hython` does not pump a Qt event loop. Tests using `executeInMainThreadWithResult` hang forever waiting for an event loop that isn't running.

**Enforcement:** Built into Dispatcher at Spike 1. All 2606+ tests pass through it.

### Invariant 2 — Time vs Identity

**Time is append-only. LIVRPS is identity.**

- Turns are immutable sibling prims under `/Session/Turns/`
- LIVRPS composition (Inherits, Variants, References, Payloads, Specializes) applies to **identity** — personas, RAG, multi-agent coordination, FORGE specialization
- LIVRPS **never** overrides history
- Never use composition arcs to "correct" past turns
- The agent's mistakes must remain visible in its own history

**Rationale:** Using USD overrides to hide a bad turn lobotomizes the agent's ability to learn from mistakes. The mistake disappears from the composed stage, and the agent silently repeats it.

### Invariant 3 — JSON-serializable API boundary (transition only)

Until WebSocket is fully deprecated, the Dispatcher API accepts and returns JSON-serializable values only: URIs (strings), dicts, numbers, booleans, lists.

Native `hou.Node` objects across the Dispatcher boundary break the WS adapter's JSON-RPC marshaller with `TypeError`.

**Lift point:** Phase 4, post-sprint. Migrating to native objects is ~5 days of work across ~100 tools.

---

## Spike Sequence

```
Spike 0    SDK Import Gate                       10 min
Spike 1.0  Test Mode Bypass                      30 min – 2 hrs
Spike 1    Dispatcher Extraction                 4–6 hrs
Spike 2    The Crucible (Hostile Co-Tenant)      1–2 hrs
Spike 3    USD Blackboard Physics                4–6 hrs

TOTAL      ~16 hours of focused work
```

Each spike has a binary pass/fail gate. **Do not start the next spike on a red previous spike.**

---

## Spike 0 — SDK Import Gate

**Goal:** Prove Agent SDK imports in `hython` and completes a round-trip to Anthropic without asyncio/httpx friction.

**Script:** `spikes/spike_0.py` (separate artifact)

**Commands:**

```bash
# Terminal 1 — Houdini
cd C:\Users\User\SYNAPSE

# API key — pick one:
# Option A (fastest for Spike 0):
set ANTHROPIC_API_KEY=sk-ant-...

# Option B (validates hou.secure early — preferred if running anyway):
# From any Houdini Python shell:
#   hou.secure.setPassword('synapse_anthropic', 'sk-ant-...')

"C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" spikes\spike_0.py
```

```bash
# Terminal 2 — Parallel (runs in 5 seconds)
cd C:\Users\User\SYNAPSE
rg -l websocket tests/
```

**Pass:** `HYTHON_ALIVE` printed, exit code 0.

**Known failure modes:**

1. **Hang or `NotImplementedError`** → ProactorEventLoop collision with httpx/anyio on Python 3.11 Windows. Uncomment `WindowsSelectorEventLoopPolicy` line in script, re-run. If selector policy fixes it, this fix moves into daemon bootstrap permanently.
2. **`ImportError` on anthropic** → dependency not installed in `hython`'s Python. Install via `hython -m pip install anthropic`.
3. **Anything else** → capture full stack trace. Staged Gemini prompt available for unexpected failures.

**On pass → Spike 1.0 unblocked.**

---

## Spike 1.0 — Test Mode Bypass

**Goal:** Dispatcher runs synchronously in tests without Qt event loop.

**Depends on:** Spike 0 pass.

**Branch resolution** via `rg -l websocket tests/` output:

### Branch A — Mocks only (30 min)

If tests patch transport via `unittest.mock` / `pytest-mock`:

- Inject `Dispatcher(is_testing=True)` into `tests/conftest.py` base fixture
- Bypasses `executeInMainThreadWithResult` queue entirely
- No test rewrites

### Branch B — Live integration (~2 hrs)

If tests spin up actual `pytest-asyncio` client on `ws://localhost:9999`:

- **Do NOT rewrite 2606 tests**
- Write `TestTransportAdapter` fixture exposing the `send()` / `recv()` signatures tests expect
- Adapter synchronously hands JSON payloads to Dispatcher under the hood
- Tests see the same interface; Dispatcher sees the bypass

**Pass:** All 2606+ tests green with Dispatcher in path (via test-mode bypass).

---

## Spike 1 — Dispatcher Extraction

**Goal:** Pure `Dispatcher` interface. One tool ported end-to-end. WS adapter routes through it. All 2606+ tests green.

**Scope — strict order:**

1. **Create `synapse.cognitive.dispatcher`** — pure Python, zero `hou` imports
   - `Dispatcher.execute(tool_name: str, kwargs: dict) -> dict | AgentToolError`
   - `is_testing` flag from Spike 1.0 baked in
   - **Exception boundary:** all unhandled exceptions caught, wrapped as structured `AgentToolError`, returned (not raised). Fail-visible, not fail-fast — the LLM needs to see failures to rewrite its approach.

2. **Port ONE tool end-to-end** — suggest `synapse_inspect_stage`
   - Sprint 2 Week 1 deliverable, read-only, safe
   - Extract tool body to `synapse.cognitive.tools.inspect_stage` as pure function
   - Dispatcher calls it directly
   - JSON-serializable boundary already compatible (URIs in, dict out)

3. **Modify WS adapter** (`mcp_server.py`)
   - Handler for `synapse_inspect_stage` now calls `Dispatcher.execute('synapse_inspect_stage', kwargs)`
   - JSON-RPC marshalling unchanged from caller's perspective
   - All other tools continue through existing path until ported later

4. **Add lint hook**
   - CI check that any file under `synapse/cognitive/**` fails on `import hou`
   - Can be `grep`-based or AST-based — `grep` is fine for Sprint 3

5. **Code split**
   - Move cognitive-layer code to `synapse.cognitive.*`
   - Move Houdini-specific code to `synapse.host.*`
   - Dispatcher lives in `cognitive`; host-specific thread marshaling lives in `host`

**Verification gates (ALL must be green to commit):**

- [ ] All 2606+ tests green (including Spike 1.0 bypass)
- [ ] Lint hook active, CI failing on `import hou` in `cognitive/`
- [ ] `synapse_inspect_stage` works identically through WS adapter
- [ ] Dispatcher returns `AgentToolError` for tool exceptions instead of raising
- [ ] No new regressions against Sprint 2 Week 1 baseline

**Commit message pattern:** `feat(dispatcher): Sprint 3 Spike 1 — Dispatcher extraction + inspect_stage port`

---

## Spike 2 — The Crucible (Hostile Co-Tenant)

**Goal:** Prove the embedded agent survives concurrent scene mutation by an artist.

**Architecture required before Crucible test:**

1. **`synapse.host.daemon`** — Agent SDK in background daemon thread
2. **Boot gate:** `if hou.isUIAvailable():` — prevents Render Farm Fork Bomb where PDG/TOPs spawns N `hython` subprocesses each booting an agent
3. **`threading.Event('cancel_requested')`** — checked before every API yield and every tool dispatch. Physical Stop button.
4. **Timeout wrapper** on `hdefereval.executeInMainThreadWithResult()` — deadlock prevention
5. **Modal dialog suppression layer** — tools never call `hou.ui.displayMessage()`. If a tool would, route to structured error instead.
6. **`hou.secure.password('synapse_anthropic')`** for API key retrieval at daemon boot

### Crucible test protocol

1. Load test scene with ~20 prims at known paths
2. Agent begins multi-turn generation referencing a specific `hou.Node` by path
3. While agent is yielding to network I/O (seconds 2–30 of turn):
   - Delete the node the agent is reasoning about
   - Scrub the timeline to force geometry cooks
   - Hit ESC
4. Observe agent behavior when network call returns

### Pass rubric

- **Baseline pass:** no segfault, Houdini stays alive
- **Full pass:** agent catches `hou.ObjectWasDeleted`, routes error into LLM context as recoverable, LLM rewrites approach next turn
- **Partial pass:** catches exception but can't articulate what happened to the LLM → needs a Spike 2.5 iteration on error structuring
- **FAIL:** silent retry on stale pointer, or segfault

### Pre-mitigation (bake into Spike 2 architecture)

- **Undo-stack desync:** before dispatch, context builder queries DCC to validate referenced objects actually exist. USD log is *intent*, not ground truth.
- **Modal dialog deadlock:** timeout on `executeInMainThreadWithResult` (suggest 30s hard ceiling), suppression layer for `hou.ui.displayMessage`.

---

## Spike 3 — USD Blackboard Physics

**Goal:** Prove USD stage-per-session topology meets latency budgets and composes correctly.

**All architectural decisions pre-locked. Do not re-choose.**

### Architecture

1. **`synapse.cognitive.stage`** — Stage-per-session manager
2. Anonymous `pxr.Usd.Stage` instantiated at agent init
3. Agent Asset stage at `C:\Users\User\SYNAPSE\assets\agents\synapse_base.usda`
   - Stable, versioned, read-only during active sessions
4. Session stage references Agent Asset by path
5. **Turn prims as siblings** under `/Session/Turns/`:
   - `/Session/Turns/Turn_001`, `/Session/Turns/Turn_002`, ...
   - Append-only, immutable, deterministic paths
6. **`/Session/Candidates`** scope for parallel rollouts (sibling prims, NOT VariantSets)
7. **customData on `/Session` root Scope** (schema locked above)
8. **Atomic write:**
   ```python
   tmp = session_path.with_suffix('.tmp.usda')
   stage.Export(str(tmp))
   os.replace(tmp, session_path)  # atomic on Windows
   ```
9. **Dataclass validators** wrap USD attribute access:
   - `@dataclass` with `__post_init__` validation
   - Zero-dep substitute for Pydantic
   - Cognitive-layer contract is Python-typed; USD layer is dynamic attributes
10. **Undo-stack validation:** before dispatch, confirm referenced `hou.Node` paths exist in DCC. Fail-visible if missing.

### Measurement targets

```
Stage.Export() of session at 100 turns:    < 100 ms
Agent Asset resolution via reference:      <  20 ms
Sibling prim write during tool call:       <  10 ms
```

### Pass criteria

- All three latency budgets met on representative state (100 turns, ~3 tool calls per turn)
- Full round-trip: create session stage → 10 turns → export → reload → verify content parity
- customData fields populate correctly on session open, update, close

---

## Phase 4 — Post-Sprint (Scoped, Not Scheduled)

After Spikes 0–3 green, the JSON-serializable Dispatcher boundary becomes a technical limitation to lift.

**Scope:**

1. Extend Dispatcher to support native object types (`hou.Node`, `Sdf.Path`)
2. Migrate ~100 tools to accept/return native types where meaningful
3. Deprecate WebSocket transport OR keep as optional remote-only layer
4. Budget: ~5 days focused work

**Anti-pattern to avoid:** letting the JSON-serializable scaffold ossify into permanent tech debt. Inside-out architecture's payoff is native object passing. The scaffold is transition-only.

---

## Parked / Deferred

Not blocking this sprint. Schema co-design happens at Spike 3 via customData; database/tooling deferred.

### Sidecar index (cross-session RAG)
- USD can't do vector `SELECT WHERE` queries
- Schema already co-designed in root customData
- Retroactive one-time crawler builds SQLite/Chroma index when cross-session retrieval matters
- **Spike 5+ territory**

### Peer discovery
- `~/.cognitive_twin/peers/synapse_pid{N}.json` — filesystem as registry
- On agent boot: write file with PID, port, session USD path
- Cognitive Bridge watches directory asynchronously
- **PID liveness check** (zero-dep, Windows-safe):
  ```python
  import ctypes
  
  def _process_alive(pid: int) -> bool:
      """Check if PID corresponds to a live process. Zero deps, Windows-safe."""
      PROCESS_QUERY_INFORMATION = 0x0400
      handle = ctypes.windll.kernel32.OpenProcess(
          PROCESS_QUERY_INFORMATION, False, pid
      )
      if not handle:
          return False
      ctypes.windll.kernel32.CloseHandle(handle)
      return True
  ```
- Ghost peers from crashes ruin multi-agent graphs without this check
- **Spike 4+ territory**

### Other deferrals
- **Schema migration path** — customData fields additive only. Old schemas read-compatible forever. Name explicitly; don't retrofit silently.
- **Session archive rotation** — at N sessions, prune or roll up. Not urgent pre-Beta.
- **Multi-user workstations** — `~/synapse/` per-user rather than shared machine-wide. Explicit scoping in Spike 3 customData (`cog:user_id`).
- **Hard cost caps** — log `tokens_used` to root metadata. Budget enforcement deferred to Beta.
- **FORGE write coordination** — live sessions treat Agent Asset as read-only. Local ledger during session. Flush to Asset on process shutdown. Prevents OS file-lock contention between simultaneous Houdini instances.
- **Anonymous sublayers (3C) for speculative tool calls** — known technique. Drop-the-layer-to-rollback for hallucinated/malformed tool calls. Spike 4+ territory.

---

## Handoff notes for Claude Code

1. **Always outline the plan before executing**, even if obvious. "Here's what I'm going to do: [plan]. Sound right?" before each spike.
2. **Ship-over-perfect.** Don't polish past the spike gate. The spike is binary pass/fail.
3. **Marathon markers** on every multi-step execution: `Mile X of ~Y`.
4. **All 2606+ tests MUST stay green** throughout. Regression = stop and fix.
5. **Commit only at spike gate passes.** No partial commits across spikes.
6. **If a spike surfaces something outside the locked decisions above, SURFACE IT**, don't work around it. Three Gemini Deep Think rounds locked those decisions; violating them silently means the next rounds were wasted.
7. **Trust existing SYNAPSE safety layers:** atomic scripts, idempotent guards, undo-group transactions. They survive the refactor unchanged.
8. **Staged Gemini prompts exist** for unexpected failures at Spike 0 (asyncio/httpx), Spike 2 (unknown Crucible hazards), and Spike 3 (USD schema forks). Do not start these unless a spike actually surfaces the matching failure.

### Spike 0 failure → do not proceed to Spike 1

If Spike 0 fails in an unexpected way (not ProactorEventLoop, not missing dep):

- Capture full stack trace
- Capture Python version (`hython --version` equivalent: `import sys; sys.version`)
- Capture `hython`'s `sys.path` (helps diagnose dep isolation)
- Report back — staged prompt goes to Gemini at that point

---

**End of execution plan. Proceed to Spike 0.**
