# CONTINUATION — Inside-Out × TOPS

> Continuation from 4/21 capsule (Michael Gold meeting day, post-Sprint 3 Day 1).
>
> **Last known commit at handoff:** `cce7b34` (Spike 2.3 revert — deadlock unmasked)
> **Last known tag:** `v5.5.0` at `4faaa3a`
> **Codebase has been dark for ~5 days.** Audit before execution.
>
> **Three threads converge here:**
> 1. **Spike 2.4** — the daemon ↔ main-thread deadlock, three options scoped, none executed.
> 2. **TOPS × inside-out synthesis** — Always-Warm collapses when the agent runs in-process.
> 3. **Umbrella vs. split** — context-aware Dispatcher resolves the tool-surface bloat question without splitting the package.

---

## Capsule

```
+== CONTINUATION CAPSULE: 4/25 =====================================+
| WHERE WE ARE:        Sprint 3 Day 1 shipped 4/20.                 |
|                      v5.5.0 tagged at 4faaa3a.                    |
|                      Michael Gold meeting was 4/21.               |
|                      Five days dark on the codebase since.        |
|                                                                    |
| MILE MARKER:         End of Sprint 3 planning + Day 1 execution.  |
|                      Beginning of Sprint 3 Day 2 / continuation.  |
|                                                                    |
| OPEN FROM SPRINT 3:  Spike 2.4 — daemon ↔ main-thread deadlock.   |
|                      Three options scoped at 4/21 capsule.        |
|                      Must close before Spike 3 opens.             |
|                                                                    |
| EXPLORATION OPEN:    TOPS Always-Warm × inside-out synthesis.     |
|                      Context-aware Dispatcher (parked, surfaced). |
|                                                                    |
| NEXT ACTION:         Run repo audit (below) → execute Spike 2.4   |
|                      → open Spike 3.0 (TopsEventBridge scaffold). |
|                                                                    |
| ENERGY REQUIRED:     Implementation (Spike 2.4, ~2h) →            |
|                      Architecture exploration (Spike 3, ~1 day).  |
|                                                                    |
| BLOCKERS:            None known. Repo audit may surface drift.    |
+====================================================================+
```

---

## Phase 0 — Repo audit (do this first)

The capsule is 5 days cold. Confirm reality before the plan touches code.

```bash
cd C:\Users\User\SYNAPSE
git status
git log --oneline -20
git tag --list 'v5.*' | sort
python -m pytest tests/ -q 2>&1 | tail -5
```

**Expected state (verify each):**

| Check | Expected |
|---|---|
| `HEAD` | `cce7b34` or later (no uncommitted state) |
| Tag `v5.5.0` | exists at `4faaa3a` |
| Test count | ~2700 passing, 5 pre-existing failures |
| Working tree | clean |

**If any check fails, stop and report.** The continuation plan assumes the capsule's recorded state. Drift means the plan needs reconciliation before execution.

**One known public-vs-local gap:** GitHub releases page shows v5.3.0 as latest published release. Capsule says v5.5.0 was tagged 4/20. Likely v5.5.0 was tagged locally and pushed but no GitHub release object was created. Confirm with:

```bash
git ls-remote --tags origin | grep v5.5.0
```

Not blocking — just worth knowing whether the public surface needs a release object before Spike 3 commits land.

---

## Spike 2.4 — Deadlock fix (BLOCKING)

**The problem (per 4/21 capsule):** Main-thread / daemon-thread deadlock identified during live verification. Spike 2.3 attempted a fix (auto-wire transport) which unmasked rather than resolved the underlying issue — reverted at `cce7b34`.

**The three options scoped at 4/21:**

### Option A — Non-blocking submit_turn

Agent loop submits tool calls to Dispatcher fire-and-forget. Result returns through `asyncio.Future` or threading queue. The agent's `await` on the future is what blocks — not a synchronous wait inside the daemon thread.

**Pros:**
- Smallest blast radius. No thread topology change.
- Matches Anthropic SDK's async-first call pattern naturally.
- Doesn't foreclose Option B or C if needed later.

**Cons:**
- Requires audit of every tool handler for re-entrancy assumptions.
- Future-based result delivery adds a small layer of indirection.

### Option B — Qt-pumping wait

Daemon thread's synchronous wait pumps Qt events while waiting. Keeps main thread responsive even during long tool calls.

**Pros:**
- Preserves synchronous tool semantics throughout the codebase.
- Lowest churn to existing tool implementations.

**Cons:**
- Qt event pumping from a non-main thread is fragile.
- Higher complexity, harder to test.
- Couples the daemon to Qt assumptions.

### Option C — Agent-loop off-daemon

Agent's main loop runs on a thread separate from the daemon's transport thread. Daemon handles transport only; agent reasoning happens elsewhere.

**Pros:**
- Cleanest architectural separation.
- Most defensible long-term shape.

**Cons:**
- Largest change. Touches daemon boot, lifecycle, shutdown, error propagation.
- Test surface expands significantly.
- Highest risk of regression.

### Recommendation

**Option A.** Smallest change that closes the deadlock cleanly. Does not foreclose B or C if a future need surfaces. The async/Future pattern is already how the Anthropic SDK wants tool calls structured — adopting it earns you the alignment for free.

Decision is yours. Whichever option ships, the gate is the same.

### Spike 2.4 Gate

- [ ] Hostile Crucible turn passes (the one that didn't run end-of-day 4/20)
- [ ] Baseline turn re-runs without timeout
- [ ] Test suite green at ≥2700 passing
- [ ] No new regressions
- [ ] `hou.secure` audit revisited — env-var fallback path documented (carried from Sprint 3 parked bug)

**No work on Spike 3 until 2.4's gate is green.** Inside-out without a working agent loop is theoretical.

---

## The synthesis: TOPS × inside-out

This is the architectural exploration. It's what makes the work after Spike 2.4 worth doing now rather than later.

### What TOPS Always-Warm was designed for (outside-in world)

P0 scope as captured pre-refactor (from 2/15 and 2/19 sessions):

- **Event-driven work item callbacks** — push, not poll
- **Auto-warm on scene load** — no artist action required
- **Persistent cook status stream** — living state, not batch-and-pray
- **Job priority queue** — artist can re-prioritize mid-cook
- **The render wrangler metaphor** — always at desk, doesn't bother artist with infra, flags problems early

In the outside-in model, every TOPS event paid a WebSocket round-trip:

```
pdg.WorkItem.cookComplete  →  handler in Houdini
                               →  serialize event
                               →  WebSocket
                               →  external agent
                               →  deserialize
                               →  agent reacts
                               →  (maybe call back through WebSocket)
```

State synchronization between Houdini's PDG state and the agent's mental model required constant marshaling. Push-based felt push-y, but every push paid a tax.

### What it becomes inside-out

Agent runs IN Houdini's Python interpreter. Daemon already has `hou` in scope. PDG callbacks fire in the same process the agent runs in.

```
pdg.WorkItem.cookComplete  →  in-process Python callback
                               →  publishes to agent's event queue
                               →  agent reacts on next loop iteration
```

No serialization. No marshaling. No transport hop. The TOPS event stream becomes the agent's **primary perception channel** — the way the agent sees the world cooking.

The wrangler metaphor sharpens: the wrangler isn't on the phone with the artist. The wrangler is in the room, listening to the same cook events the scheduler emits, reacting in the same heartbeat.

### Concrete shape — TopsEventBridge (early sketch, not committed)

```python
# python/synapse/agent/perception/tops_bridge.py

from __future__ import annotations
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.agent.dispatcher import Dispatcher

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False


class TopsEventBridge:
    """Hooks PDG callbacks into the agent's perception channel.

    Runs in-process inside Houdini's Python interpreter. Emits typed events
    onto the agent's perception queue without crossing any transport boundary.

    Invariants:
      - All tool calls back into TOPS still route through Dispatcher.
      - Events are typed (matches Spike 1's AgentToolError envelope shape).
      - Perception queue is bounded; backpressure surfaces as dropped-event
        log entry, never as deadlock.
    """

    def __init__(
        self,
        perception_queue: asyncio.Queue,
        dispatcher: "Dispatcher",
        max_queue_size: int = 1024,
    ) -> None:
        self._queue = perception_queue
        self._dispatcher = dispatcher
        self._max_size = max_queue_size
        self._registered_topnets: dict[str, object] = {}
        self._scene_callback_fn = None

    def warm_on_scene_load(self) -> None:
        """Auto-discover TOP networks and register callbacks."""
        if not HOU_AVAILABLE:
            return
        # Scan existing scene
        for node in hou.node("/").allSubChildren():
            if node.type().category() == hou.topNodeTypeCategory():
                self._register_topnet(node)
        # Subscribe to future scene events.
        # addEventCallback returns None — removal is by callback identity,
        # so store the bound function reference for later removeEventCallback.
        self._scene_callback_fn = self._on_hip_event
        hou.hipFile.addEventCallback(self._scene_callback_fn)

    def _on_hip_event(self, event_type) -> None:
        """Re-warm on scene change."""
        if event_type == hou.hipFileEventType.AfterLoad:
            self.warm_on_scene_load()

    def _register_topnet(self, topnet) -> None:
        """Register PDG event callbacks for a TOP network.

        Per Spike 3.0 audit (docs/sprint3/spike_3_0_pdg_api_audit.md):
          - Use standalone ``pdg`` module (``import pdg as _pdg``)
          - Live GraphContext via ``topnet.getPDGGraphContext()`` —
            pdg.GraphContext is the class, but live contexts are
            acquired via the TOP node instance method, not class-instantiated.
          - Subscribe with ``pdg.PyEventHandler`` + ``graph_context.addEventHandler(...)``
          - Filter on ``pdg.EventType.CookComplete`` / ``CookError`` / ``WorkItemResult``
        """
        ...

    def _on_workitem_complete(self, event) -> None:
        """Push completion event into agent perception."""
        try:
            self._queue.put_nowait({
                "type": "tops.workitem.complete",
                "node_path": event.workItem.node.path(),
                "frame": event.workItem.attribValue("frame"),
                "outputs": [
                    f.path for f in event.workItem.expectedResultData
                ],
                "duration_ms": event.workItem.cookDuration * 1000,
            })
        except asyncio.QueueFull:
            # Backpressure — drop event, log it. Never block.
            self._dispatcher.log_dropped_event(
                "tops.workitem.complete",
                event.workItem.node.path(),
            )

    def shutdown(self) -> None:
        """Clean teardown of all callbacks."""
        if self._scene_callback_fn and HOU_AVAILABLE:
            hou.hipFile.removeEventCallback(self._scene_callback_fn)
        # Unregister all per-topnet callbacks
        ...
```

**Key invariants:**

- Bridge lives in-process. No transport hop.
- Events are typed dicts (parallels Spike 1's `AgentToolError` envelope shape).
- Perception queue is bounded — backpressure surfaces as dropped-event log entry, never as deadlock.
- All tool calls into TOPS still go through Dispatcher (preserves the cognitive/host boundary established at Spike 1.0).
- `hou` API access guarded by import check — bridge is testable headless via mock injection.

### Hard API verification gate (carried from established constraints)

Houdini 21.0.671 has known divergences from prior versions. Memory: `componentbuilder` doesn't exist natively, `hou.secure` absent, light nodes use `xn__` parameter prefix encoding. PDG API lives at standalone `pdg` (not `hou.pdg`, which doesn't resolve in 21.0.671 — confirmed by Spike 3.0 audit) and Gemini/external reasoning frequently assumes APIs that don't exist.

**Before any Spike 3.0 code lands:**

```python
# Run inside graphical Houdini 21.0.671 Python Shell
import hou
import pdg
print(dir(pdg))
print(dir(pdg.Scheduler))
# Identify event subscription API surface concretely
# Identify workItem callback registration concretely
# Identify cook lifecycle event types concretely
```

Capture the introspection output as a parked note in `docs/sprint3/spike_3_0_pdg_api_audit.md` before writing the bridge. **Non-negotiable.**

---

## Umbrella vs. split — resolved

The strategic question opened earlier today: should SYNAPSE split per Houdini context (SOPs / LOPs / TOPs / COPs / DOPs / Karma) or stay umbrella?

**Resolution in the inside-out world:** Umbrella stays. Tool surface becomes context-aware at the Dispatcher layer.

The Dispatcher already mediates every tool call (post Spike 1). Extending it to gate tool visibility based on active Houdini context is a daemon-side concern, not a packaging concern.

```
NEVER SPLIT (the moat)
├── Core         protocol, queue, determinism, audit, gates
├── Memory       cross-context decisions, provenance, audit chain
├── Daemon       in-process agent loop, Dispatcher, TopsEventBridge
└── Server       optional WebSocket for remote clients

MODULAR AT DISPATCHER (the surface)
├── always-on        system, scene, memory, introspection (~12 tools)
├── ctx:solaris      USD, references, variants — hot when /stage focused
├── ctx:tops         PDG, work items, schedulers — hot when /tasks focused
├── ctx:karma        render settings, MaterialX, lights — hot near rop_usdrender
├── ctx:fx           DOPs, simulation — hot when /obj contains DOP networks
├── ctx:cops         Copernicus — hot when /img focused
└── ctx:sops         geometry, attributes — hot when active pane is SOP
```

**Detection signal:** active pane network type + `$HIP` heuristics + explicit pin override.

**Don't implement context gating in Spike 3.** Surface as Spike 4 candidate. Spike 3 focuses on TOPS Always-Warm specifically because TOPS is the highest-value context to bring online first — it's the execution engine for autonomy.

The pattern Spike 3 establishes (in-process bridge → typed perception events → Dispatcher-mediated tool calls) generalizes directly to the other contexts at Spike 4. Get it right once with TOPS.

---

## Sprint shape — proposed sequence

```
Spike 2.4    Deadlock fix                      [BLOCKING]
             ↓ gate green
Spike 3.0    PDG API audit (dir() introspection inside Houdini)
             ↓
Spike 3.1    TopsEventBridge scaffold + headless tests
             ↓
Spike 3.2    Auto-warm on scene load
             ↓
Spike 3.3    First TOPS event surface (workitem.complete → agent perception)
             ↓
Spike 3.4    Hostile TOPS Crucible (event flood, malformed events, cancellation)
             ↓ gate green
Spike 4.0    [parked, surfaced] Context-aware Dispatcher tool gating
```

### Gates per spike

**Spike 3.1 gate:**
- TopsEventBridge module imports headless without `hou`
- ≥10 unit tests for queue mechanics, backpressure, callback registration shape
- mypy clean on the new module
- Test count strictly increases

**Spike 3.2 gate:**
- Bridge `warm_on_scene_load()` runs inside live Houdini 21.0.671
- TOP networks discovered correctly across at least 2 test scenes
- `hou.hipFile` event callback fires on scene reload
- Manual verification log captured in `docs/sprint3/spike_3_2_warm_verification.md`

**Spike 3.3 gate:**
- A real PDG cook fires at least one `workitem.complete` event onto the perception queue
- Agent loop pulls the event from the queue and acknowledges it (no reasoning required at this gate — just wire continuity)
- End-to-end timing under 50ms from `cookComplete` to agent perception (in-process should be sub-ms; budget is for safety margin)

**Spike 3.4 gate (hostile Crucible):**
- Event flood test: 10K events emitted in 1s, queue saturates, dropped-event log records overflow, agent never deadlocks
- Malformed event test: event with missing fields surfaces as typed parse error, not exception
- Cancellation test: bridge shutdown mid-cook unregisters cleanly with no orphaned callbacks

---

## Hard invariants (carried from Sprint 3)

These do not change. Every commit honors them or doesn't ship.

1. All tool calls into Houdini route through Dispatcher (cognitive/host boundary established at Spike 1.0)
2. `AgentToolError` envelope shape preserved for all error paths
3. Test count strictly increases or holds — never decreases
4. No new dependencies added — vendored `anthropic` stays the dep boundary
5. Strangler Fig — old WebSocket path stays operational throughout
6. Hard API verification before any Houdini call: `dir()` introspection in live Houdini 21.0.671 first, blueprint code second
7. `execute_python` transport constraint — multi-line Python with dict literals fails over WebSocket; sequential single-line calls is the working pattern (relevant if any Spike 3 work touches the legacy WebSocket path)

---

## Parked items (do not open this sprint)

- Full Solaris context bundle in Dispatcher (Spike 4)
- COP / DOP / SOP context bundles (Spike 4)
- Multi-Houdini-session daemon coordination
- Cognitive Bridge integration
- Sequence-rendering UX layer (artist-facing "render 1-48" sugar)
- Frame validation feedback loop (separate concern from event surface)
- v5.6.0 release planning
- BL-007 (EXR not written) and BL-008 (Karma asset references invisible) — known bugs, not in this sprint's scope

---

## Non-goals

- Demo for Michael Gold (already happened 4/21 — that arc is closed regardless of follow-up)
- New MCP tools (TOPS coverage is sufficient at the tool layer; this sprint is about the **event channel**, not the tool surface)
- Performance optimization (correctness first, perf measurable after Spike 3.4)
- Public release object for v5.5.0 (separate housekeeping task, doesn't gate code work)

---

## What this sprint proves

**Spike 2.4 closing** — inside-out architecture is production-stable, not just functionally proven.

**Spike 3 closing** — the agent has a real perception channel. Not just tool-calling capability (Spike 1) and reasoning capability (Spike 2), but **eyes**. The render wrangler is in the room, listening.

**That ordering matters:** Spike 1 gave the agent hands. Spike 2 gave the agent a brain. Spike 3 gives the agent eyes. Spike 4 (parked) sharpens the agent's attention. The portfolio thesis pitched to Michael Gold — agent in-process, peer in MCP graph — gets its first real demonstration at Spike 3.3.

---

## Demo-shape statement (for Joe's reference, not for Claude Code)

The shape of a Spike 3.3 demo, when it lands:

> Open a Houdini scene with a TOP network. Daemon auto-warms — no shelf button, no menu action. Trigger a cook of 5 frames. Watch the agent's terminal log five `tops.workitem.complete` events arrive in real-time, each with frame number and output path. Agent says one sentence: *"Five frames cooked. Average duration 1.2s. Two outputs at /render/v001."*
>
> No WebSocket in the loop. No marshaling. No bridge. The agent saw what Houdini saw.

That's the moment "inside-out" stops being a thesis and becomes an experience.

---

## Final session reminders

- This is a continuation, not a sprint kickoff. Don't redo planning that's already done.
- Spike 2.4 first. No exceptions. No exploration before the deadlock closes.
- Hard API verification before any Houdini call. `dir()` in live Houdini 21.0.671. No Gemini-assumed APIs.
- Marathon markers in commits — `Spike 3.1` style, matches established pattern.
- If anything drifts from this plan during execution, **stop and surface** rather than improvising.

---

*Generated 4/25 from synthesis of: 4/21 capsule, Sprint 3 4/20 execution arc, TOPS Always-Warm scope (2/15 + 2/19 sessions), today's umbrella-vs-split exploration.*
