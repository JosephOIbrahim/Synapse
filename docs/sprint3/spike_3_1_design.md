# Spike 3.1 — TopsEventBridge Scaffold (Design)

> **Authority:** ARCHITECT (design only). FORGE writes implementation;
> CRUCIBLE writes hostile tests. This document is the contract between
> them.
>
> **Status:** Pre-implementation. No code mutated. Spike 3.0 PDG audit
> at `docs/sprint3/spike_3_0_pdg_api_audit.md` is the empirical surface
> this design binds against.
>
> **Sprint position:** Spike 3.1 is the perception-channel scaffold —
> an in-process PDG event bridge. Spike 3.2 (auto-warm on scene load),
> 3.3 (first event surface), 3.4 (hostile Crucible) build on this.

---

## 1. Diagnosis

### 1.1 What "inside-out TOPS event surfacing" means

Pre-Sprint-3, every PDG event paid a WebSocket round-trip: cook event
fires inside Houdini → handler in Houdini's Python → serialize to JSON
→ WebSocket frame → external agent process → deserialize → react. State
synchronization between Houdini's PDG cook engine and the agent's mental
model required constant marshaling.

Post-Sprint-3 (inside-out): the agent runs IN Houdini's Python interpreter.
Daemon already has `hou` in scope. PDG callbacks fire in the same process
the agent runs in. The transport hop disappears — events become a
**typed in-process queue** between PDG (event producer) and the agent's
perception layer (event consumer). No serialization. No marshaling. No
round-trip latency.

The wrangler metaphor: the wrangler isn't on the phone with the artist.
The wrangler is in the room, listening to the same cook events the
scheduler emits, reacting in the same heartbeat.

### 1.2 The gap between current `bridge.py` PDG handling and Sprint 3 needs

`shared/bridge.py:560–680` (R8: PDG Async Cook Bridge) implements
**single-cook event subscription**: when the orchestrator triggers a PDG
cook, R8 attaches a `pdg.PyEventHandler` to that one cook's
`GraphContext`, listens for `CookComplete` / `CookError`, and detaches
when the cook finishes. Useful for single-cook orchestration. Not what
Sprint 3 needs.

Spike 3.1 needs **continuous, multi-network event surfacing** across the
artist's whole scene:

- All TOP networks the artist creates, not just one.
- Across the entire session lifetime, not just one cook.
- Multiple event scopes (cook lifecycle, node progress, work-item state),
  not just `CookComplete` / `CookError`.
- Richer typed payload: frame, output paths, durations, node identities.
- Idempotent cleanup that survives partial failures and avoids leaks
  across sessions.

R8 is the **proof of pattern** — it confirms the empirical surface
(`pdg.PyEventHandler`, `graph_context.addEventHandler(handler, type)`,
`graph_context.removeEventHandler(handler)`, `top_node.getPDGGraphContext()`).
Spike 3.1 generalizes the pattern to a long-lived bridge with many
subscriptions.

### 1.3 Cognitive vs host placement

The bridge imports `hou` and `pdg`. The cognitive boundary lint
(`tests/test_cognitive_boundary.py`) forbids `import hou` under
`synapse.cognitive.*`. So the bridge lives in `synapse.host.*`,
alongside `daemon`, `turn_handle`, `transport`, `main_thread_executor`,
`auth`, `dialog_suppression`. Cognitive layer talks to it through a
pure-Python callback contract — no `hou` reference crosses the boundary.

The continuation artifact's sketched path (`python/synapse/agent/perception/...`)
was speculative; `agent/` is not a package in this codebase. The
correct host is `python/synapse/host/tops_bridge.py`.

---

## 2. TopsEventBridge interface

### 2.1 Public class signature

```python
# python/synapse/host/tops_bridge.py

class TopsEventBridge:
    """In-process PDG event bridge for SYNAPSE inside-out perception.

    Subscribes to PDG events at three audit-verified scopes
    (GraphContext / Node / WorkItem) and delivers typed events to a
    pure-Python callback. Bridge instances are independent — multiple
    can subscribe to the same graph without interfering.

    Audit surface (Spike 3.0): standalone ``pdg`` module. ``hou.pdg.*``
    paths do not resolve in Houdini 21.0.671.

    Threading contract: PDG event callbacks may fire on a non-main thread
    (cook thread, scheduler thread, etc.). The bridge's internal
    handler is thread-safe (no ``hou.*`` calls inside the handler). The
    user-supplied ``perception_callback`` is invoked on whatever thread
    the PDG event fires on. The cognitive layer must use a thread-safe
    delivery primitive (``queue.Queue``, ``threading.Event``).
    """

    def __init__(
        self,
        perception_callback: Callable[[TopsEvent], None],
        *,
        dispatcher: Optional["Dispatcher"] = None,
        max_dropped_log: int = 1024,
    ) -> None:
        ...

    # ── Subscription lifecycle ──────────────────────────────────────

    def warm(self, top_node: "hou.Node") -> "Subscription":
        """Subscribe to one TOP network's events.

        Acquires the live ``pdg.GraphContext`` via
        ``top_node.getPDGGraphContext()`` (R8 pattern, ``bridge.py:616``).
        Class-instantiation of ``pdg.GraphContext()`` is for fresh
        graphs only — never use it to attach to the artist's existing
        scene.

        Returns a ``Subscription`` token the caller stores for later
        ``cool(subscription)`` cleanup.

        Raises ``TopsBridgeError`` if the TOP node has no graph context
        (uninstantiated network) or if PDG is unavailable.
        """
        ...

    def warm_all(self) -> List["Subscription"]:
        """Discover every TOP network in the scene and warm each.

        Uses ``hou.node('/').allSubChildren()`` filtered by
        ``hou.topNodeTypeCategory()`` (audit RESOLVED) to enumerate.
        Returns the list of subscriptions in discovery order.

        Spike 3.2 will integrate this with ``hou.hipFile.addEventCallback``
        for re-warm on scene load. Spike 3.1 does not yet auto-fire on
        scene change.
        """
        ...

    def cool(self, subscription: "Subscription") -> None:
        """Unsubscribe one TOP network. Idempotent on already-cooled
        subscriptions. No-op if the underlying graph context has been
        destroyed (e.g. network deleted while we held the subscription)."""
        ...

    def cool_all(self) -> None:
        """Unsubscribe every active subscription. Idempotent."""
        ...

    # ── Introspection ───────────────────────────────────────────────

    def active_subscriptions(self) -> Tuple["Subscription", ...]:
        """Snapshot of currently-active subscriptions. Read-only."""
        ...

    def dropped_event_count(self) -> int:
        """Count of events the bridge dropped (e.g. callback raised,
        callback returned a sentinel asking to skip). Spike 3.4 hostile
        suite verifies this counter increments under fault."""
        ...
```

### 2.2 `Subscription` value object

```python
@dataclass(frozen=True, slots=True)
class Subscription:
    """Token returned from ``warm(...)``. Caller stores for cool().

    Per Spike 3.0 finding: cleanup is by handler-identity, not by an
    opaque returned handle. The bridge stores the bound
    ``pdg.PyEventHandler`` instance and the ``pdg.GraphContext`` it was
    registered against.
    """
    top_node_path: str        # canonical hou path, e.g. "/tasks/topnet1"
    scope: str                # "graph" | "node" | "workitem"
    event_types: Tuple[int, ...]  # pdg.EventType.* int values registered
    # Bridge-private fields (consumers read top_node_path / scope only):
    _handler: Any             # pdg.PyEventHandler instance
    _graph_context: Any       # pdg.GraphContext instance the handler was attached to
    _alive: List[bool]        # 1-element mutable bool — flips False on cool()
```

### 2.3 `TopsEvent` typed payload

```python
@dataclass(frozen=True, slots=True)
class TopsEvent:
    """Typed event surfaced to the perception callback.

    Constructed by the bridge from raw ``pdg.Event`` objects without
    any ``hou.*`` calls — the bridge handler runs on a non-main thread
    in some configurations (scheduler thread). Only ``pdg.*`` attribute
    reads are made from the handler.
    """
    event_type: str           # human-readable, e.g. "tops.workitem.result"
    pdg_event_type_int: int   # raw pdg.EventType enum value (audit-verified)
    top_node_path: str        # which TOP network this event belongs to
    timestamp: float          # time.monotonic() when event was received

    # Optional fields populated per event_type. Absent → None.
    work_item_id: Optional[int] = None
    work_item_frame: Optional[float] = None
    work_item_state: Optional[str] = None
    work_item_outputs: Tuple[str, ...] = ()
    work_item_cook_duration_seconds: Optional[float] = None  # see §3
    node_path: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializable form for downstream JSON / WebSocket / log."""
        ...
```

### 2.4 Subscription scopes — pick one per event class

Audit RESOLVED three event-handler-bearing surfaces:

| Surface | `addEventHandler` confirmed | Use for |
|---|---|---|
| `pdg.GraphContext` (Spike 3.0 §2.6) | yes (R8 uses it) | **Cook lifecycle** (graph-wide) |
| `pdg.Scheduler` (§2.3) | yes (audit dir() shows it) | _reserved_ — not used in 3.1 |
| `pdg.Node` (referenced in pdg dir()) | yes | **Per-node progress** |
| `pdg.WorkItem` (§2.4) | yes | **Per-item state** (rare — opt-in) |

**Picks for Spike 3.1:**

- **Graph scope** (subscribe via `graph_context.addEventHandler(handler, type)`):
  - `pdg.EventType.CookStart` — cook began on this graph
  - `pdg.EventType.CookComplete` — graph cook finished (R8-verified)
  - `pdg.EventType.CookError` — graph cook errored (R8-verified)
  - `pdg.EventType.CookWarning`
  - `pdg.EventType.WorkItemAdd` — new item materialized
  - `pdg.EventType.WorkItemStateChange` — item moved between cooked/cancelled/failed states
  - `pdg.EventType.WorkItemResult` — item produced output(s) (alias of `WorkItemOutputFiles` per audit)

  *Justification:* one handler per graph captures everything per-graph
  without N × Node or N × WorkItem registration. Matches R8's pattern.
  Cleanup is single-call per graph.

- **Node scope** (reserved — `pdg.Node.addEventHandler(handler, type)`):
  - `pdg.EventType.NodeCooked` — single node finished cooking
  - `pdg.EventType.NodeProgressUpdate` — coarse percent
  - `pdg.EventType.NodeFirstCook` — node's first cook in this session

  *Spike 3.1 ships node-scope APIs but does NOT auto-subscribe.* Per-node
  subscription is opt-in via `bridge.watch_node(node)` (parked for 3.3 if
  the agent ends up needing per-node granularity beyond what graph-level
  events provide). For 3.1, only the graph-scope subscription fires.

- **WorkItem scope** (reserved — `work_item.addEventHandler(handler, type)`):
  - Reserved for explicit "watch this specific work item" requests.
  - Not used in 3.1 — too fine-grained to register at scale (could be
    thousands of work items per cook).

**Decision pinned:** Spike 3.1 ships only **graph-scope** subscription.
Node and WorkItem scopes are present in the API surface but the
implementation defers their wiring to later spikes. Reduces Spike 3.1
surface to one event-handler installation per `warm(...)`.

### 2.5 Event filter — what surfaces to Claude vs what stays internal

The audit captured 50+ `pdg.EventType` members. Surfacing every event
to the agent would drown reasoning in noise (`WorkItemSet*` chatter,
attribute updates, dirty events, UI events). Spike 3.1 surfaces a
**fixed allowlist** of 7 cook + work-item events. Everything else is
silently dropped at the bridge boundary.

**Surfaced (allowlist — 7 types):**

| `pdg.EventType` | Int | Surfaced as | Scope |
|---|---|---|---|
| `CookStart` | 38 | `tops.cook.start` | graph |
| `CookComplete` | 14 | `tops.cook.complete` | graph |
| `CookError` | 12 | `tops.cook.error` | graph |
| `CookWarning` | 13 | `tops.cook.warning` | graph |
| `WorkItemAdd` | 1 | `tops.workitem.add` | graph |
| `WorkItemStateChange` | 5 | `tops.workitem.state_change` | graph |
| `WorkItemResult` | 35 | `tops.workitem.result` | graph |

(`WorkItemResult` and `WorkItemOutputFiles` are dual aliases for int 35
per audit — register once, use the canonical name `WorkItemResult`.)

**Internal-only (silently dropped at bridge boundary):**

- `DirtyAll`, `DirtyStart`, `DirtyStop` (graph-level dirty churn —
  upstream of cook events that the agent already consumes)
- All `WorkItemSet*` (attribute setter chatter — the surfaced
  `WorkItemStateChange` summarizes)
- `UISelect` (UI-only, no semantic content)
- `Service*` (irrelevant to artist-facing reasoning)
- `Node*` events except those the future node-scope opt-in adds

**Surfaced/internal split is hard-coded in Spike 3.1.** Spike 3.4+ may
expose a per-bridge configurable filter; Spike 3.1 ships a single
`_SURFACED_EVENT_TYPES: FrozenSet[int]` constant.

### 2.6 Live `GraphContext` acquisition

**Pattern (R8-verified, `bridge.py:616`):**

```python
graph_context = top_node.getPDGGraphContext()
if not graph_context:
    raise TopsBridgeError(
        f"TOP node {top_node.path()} has no graph context "
        "(network not yet instantiated, or node is not a topnet)"
    )
```

**Anti-pattern (audit-rejected):**

```python
# WRONG: this constructs a NEW empty graph, not the live one
graph_context = pdg.GraphContext()
```

Class-instantiation of `pdg.GraphContext()` is for callers who want to
construct a fresh graph from scratch (e.g. headless PDG tooling). The
artist's existing scene's contexts are owned by their respective TOP
nodes and acquired via the instance accessor. **Documented as a hard
distinction in Spike 3.1 docstrings + risk register §7.**

### 2.7 Cleanup contract — callback-identity, not handle-based

**Per Spike 3.0 finding** (audit §2.8 callback-by-identity note for
`hou.hipFile.addEventCallback`):

- `pdg.GraphContext.removeEventHandler(handler)` takes the **same
  handler object** that was passed to `addEventHandler`. It is not a
  handle, token, or opaque cookie. It's the `pdg.PyEventHandler`
  instance itself.
- Therefore: the `Subscription` value object (§2.2) holds the
  `_handler` reference. Cleanup is `subscription._graph_context.removeEventHandler(subscription._handler)`.
- **Bridge guarantee:** `cool(subscription)` is idempotent. Multiple
  calls on the same subscription are no-ops. The `_alive: List[bool]`
  field flips to `[False]` on first call; subsequent calls observe and
  return.
- **Bridge guarantee:** `cool_all()` is safe even after partial
  failure — each subscription is wrapped in its own `try/except`; one
  failed teardown doesn't block the others.
- **Crucible verifies** (§5): event firing during shutdown, callback
  raising mid-event, bridge subscribed when topnet deleted mid-cook.

### 2.8 Threading model

**Defensive assumption:** PDG event callbacks may fire on:
- Houdini's main thread (R8 doc claims this for typical scheduler)
- A scheduler worker thread (farm scheduler, deadline scheduler, etc.)
- A cook coordinator thread (large work-item dispatch)

The audit could not pin which thread events fire on without a runtime
example. **Sprint 3.1 designs against the broadest assumption: events
may fire on any thread.**

**Therefore the bridge handler MUST NOT call `hou.*` directly.** PDG
event objects expose `pdg.*` properties (workitem.frame, workitem.id,
workitem.state, workitem.cookDuration, workitem.node — though the last
returns a `pdg.Node`, which has `path()` per the standard hou-style
accessor). Reading `pdg.*` properties from any thread is safe (pybind11
read-only access).

**Cross-thread delivery (bridge → cognitive layer):** the user-supplied
`perception_callback` is invoked on whatever thread the event fires on.
The cognitive layer is responsible for thread-safe delivery to the
daemon's perception queue — typically:

```python
# In cognitive layer (NOT in tops_bridge.py — example only)
import queue
perception_queue = queue.Queue(maxsize=1024)

def perception_callback(event: TopsEvent) -> None:
    try:
        perception_queue.put_nowait(event.to_dict())
    except queue.Full:
        # Backpressure — drop event, log
        ...
```

`queue.Queue.put_nowait` is thread-safe.

**`hou.*` calls inside the bridge:** only allowed in `warm_all()` (which
runs once at user request, on the calling thread — typically main
thread) for `hou.node('/').allSubChildren()`. Nowhere inside the event
handler.

**`top_node.getPDGGraphContext()` invocation:** called inside `warm(...)`
on the caller's thread. Per `bridge.py:616` precedent this is treated
as main-thread-safe at call time. If the caller invokes from a
non-main thread, R8's pattern is to use `hdefereval.executeInMainThread`
to dispatch — but for `warm()` we document the caller's responsibility
to invoke from the main thread (consistent with how the bridge is
expected to be used by the daemon during scene-load setup).

### 2.9 PyEventHandler construction pattern

Mirror R8's exact pattern at `bridge.py:636`:

```python
def _make_event_handler(
    self,
    subscription_alive: List[bool],
    top_node_path: str,
) -> "pdg.PyEventHandler":
    def on_pdg_event(event):
        # Idempotency guard — drops events arriving after cool()
        if not subscription_alive[0]:
            return
        # Filter
        event_type_int = int(event.type)
        if event_type_int not in _SURFACED_EVENT_TYPES:
            return
        # Construct typed event (no hou.*; pdg.* only)
        try:
            tops_event = self._build_tops_event(event, top_node_path)
        except Exception:
            self._dropped += 1
            return
        # Deliver
        try:
            self._perception_callback(tops_event)
        except Exception:
            self._dropped += 1
            # Don't re-raise — protects PDG cook from agent-side bugs

    return pdg.PyEventHandler(on_pdg_event)
```

Each `addEventHandler` call **registers the same handler against ONE
event type**. R8 does this:

```python
graph_context.addEventHandler(handler, _pdg.EventType.CookComplete)
graph_context.addEventHandler(handler, _pdg.EventType.CookError)
```

Spike 3.1 follows: register the same handler against all 7 surfaced
event types. The handler internally re-filters on `event.type` for
defense-in-depth (in case PDG fires an unsubscribed type — should not
happen but cheap to guard).

---

## 3. cookDuration handling

**Assumed unit:** seconds (per common SideFX convention; matches
`pdg.WorkItem.cookDuration` property naming, not `cookDurationMs`).

**Risk:** unit not in introspectable docstring (audit §3.1 watchlist).

**Resolution at design time:** assume seconds; populate `TopsEvent.work_item_cook_duration_seconds`
directly from `event.workItem.cookDuration`. **Single validation step at
first integration test:** Spike 3.3's first end-to-end test prints

```
print(f"[spike-3.3-verify] cookDuration={duration} seconds (expected ~1.0)")
```

…during a controlled 1-second cook. Operator confirms unit. If wrong,
single-line fix in `_build_tops_event` (`* 1000`) before Spike 3.4
ships. Not a Spike 3.1 design blocker.

---

## 4. Files to touch

| Action | Path | Notes |
|---|---|---|
| **create** | `python/synapse/host/tops_bridge.py` | `TopsEventBridge`, `Subscription`, `TopsEvent`, `TopsBridgeError` — full module |
| **modify** | `python/synapse/host/__init__.py` | re-export `TopsEventBridge`, `Subscription`, `TopsEvent`, `TopsBridgeError` |
| **create** (FORGE) | `tests/test_tops_bridge.py` | basic suite — construction, warm/cool round-trip, mocked event dispatch, one happy path per surfaced event type |
| **extend** (CRUCIBLE) | `tests/test_tops_bridge.py` | hostile suite §5 — 8 cases minimum |

**Out of scope (do NOT touch):**

- `python/synapse/cognitive/**` — bridge stays in host layer; cognitive boundary preserved
- `python/synapse/host/daemon.py` — daemon-side wiring is Spike 3.2 (auto-warm on scene load) territory
- `python/synapse/host/main_thread_executor.py` — bridge does not extend it
- `shared/bridge.py` — R8 stays as-is; reading the pattern is fine, modifying it is not in scope
- `python/synapse/server/**` — Strangler Fig WebSocket path stays operational
- `python/synapse/_vendor/**` — vendored anthropic boundary preserved

---

## 5. Test plan for CRUCIBLE

Hostile cases mandatory. Each test name pins the failure mode it probes.
All tests run in standalone mode (no live Houdini) — `pdg` and `hou` are
mocked. The `live` pytest marker is reserved for Spike 3.3 integration.

| # | Test name | Probes |
|---|---|---|
| 1 | `test_subscribe_unsubscribe_no_handler_leak` | `warm()` then `cool()` removes handler from graph context. Tracked by counting handler refs on the mock graph context — must drop to zero |
| 2 | `test_cook_error_during_subscription_does_not_crash_bridge` | While the bridge is subscribed, mock graph fires `CookError`. Bridge converts to `tops.cook.error` typed event with `error_message` populated. Bridge state stays consistent |
| 3 | `test_multiple_bridges_same_graph_context_independent` | Two `TopsEventBridge` instances both `warm()` the same TOP node. Each gets its own handler. `cool()` on bridge A leaves bridge B's subscription intact |
| 4 | `test_event_firing_during_shutdown_does_not_double_dispatch` | Bridge fires an event AT THE SAME MOMENT `cool()` is called. The `_alive` flag dropping mid-event must prevent double-dispatch. Use `threading.Event` synchronization in the test |
| 5 | `test_perception_callback_raising_does_not_break_bridge` | User callback raises `RuntimeError`. Bridge increments `dropped_event_count()`, swallows the exception, continues processing subsequent events. PDG's cook is never disrupted by agent-side bugs |
| 6 | `test_warm_on_topnet_without_graph_context_raises_typed_error` | Mock TOP node returns `None` from `getPDGGraphContext()`. Bridge raises `TopsBridgeError` with a clear message — does NOT silently fail |
| 7 | `test_topnet_deleted_mid_subscription_cool_no_crash` | Active subscription's underlying graph context becomes invalid (mock raises on `removeEventHandler`). `cool()` swallows + logs, does NOT crash the bridge or block other subscriptions |
| 8 | `test_multiple_event_types_same_cook_no_loss_no_reorder` | Single mock cook fires `CookStart`, `WorkItemAdd × 5`, `WorkItemResult × 5`, `CookComplete` in sequence. All 12 events delivered to callback in original order. No drops, no reordering, no dedup |

**Required assertions:**

- Specific failure modes named in test docstrings
- `assert isinstance(event, TopsEvent)` not `assert event is not None`
- `assert event.event_type == "tops.cook.complete"` not `assert "complete" in str(event)`
- Numeric/identity assertions on counters (`assert bridge.dropped_event_count() == 1`)
- For idempotency tests: assert specific count behaviors, not just absence-of-crash

---

## 6. Gate criteria

Restated **verbatim** from `docs/sprint3/CONTINUATION_INSIDE_OUT_TOPS.md`
§ "Spike 3.1 gate":

> - TopsEventBridge module imports headless without `hou`
> - ≥10 unit tests for queue mechanics, backpressure, callback registration shape
> - mypy clean on the new module
> - Test count strictly increases

**Concrete numeric targets** (orchestrator-derived from the bullets):

- Sprint baseline: **2752 passed**, 5 failed (5 pre-existing flakes), 47 skipped
- Spike 3.1 floor: **≥2762 passed** (≥10 net-new), 5 failed (unchanged — only pre-existing flakes), skipped count unchanged
- Hostile suite contributes the bulk; basic suite is gravy

---

## 7. Risk register

### 7.1 Invariants threatened — and how the design preserves them

| Invariant | Status under this design | Evidence |
|---|---|---|
| All tool calls route through Dispatcher | **Preserved.** Bridge is downstream of perception; it doesn't dispatch tool calls. The dispatcher reference in the constructor is for log-dropped-event integration only | §2.1 constructor — `dispatcher: Optional["Dispatcher"]` |
| `AgentToolError` envelope shape preserved | **Preserved.** Bridge does not produce `AgentToolError` envelopes; it produces typed `TopsEvent` payloads. Untouched | n/a |
| Test count strictly increases | **Will hold.** §6 floor is +10 minimum | §5 test plan + §6 floor |
| No new dependencies | **Preserved.** Bridge uses only `threading`, `dataclasses`, `typing`, and the (defensively-imported) `hou` + `pdg` modules already in scope | §2 import list |
| Strangler Fig WebSocket survives | **Preserved.** `mcp_server.py` not touched | §4 out-of-scope |
| Hard API verification before any new `hou.*` / `pdg.*` | **Preserved.** Every API reference in §2 traces to Spike 3.0 audit RESOLVED list | §7.4 trace table below |
| No `import hou` under `synapse/cognitive/**` | **Preserved.** Bridge lives in `synapse.host.*`. Cognitive layer talks to it via callback contract | §1.3 placement decision |

### 7.2 What could go wrong

1. **`pdg.Node.path()` vs `.name`.** Sketch reads `event.workItem.node.path()`. Audit confirmed `pdg.WorkItem.node` returns a `pdg.Node`. The audit did NOT introspect `pdg.Node` directly — `path()` accessor is **assumed** based on hou-style convention. If `pdg.Node.path()` doesn't exist, `_build_tops_event` raises and the event is dropped (Spike 3.4's hostile suite catches this). Mitigation: defensive `getattr(node, "path", lambda: getattr(node, "name", "<unknown>"))()` in `_build_tops_event`. Spike 3.3 integration verifies.

2. **`cookDuration` unit.** Assumed seconds. Single integration print at Spike 3.3 verifies. Wrong-unit fix is a one-line change to multiply by 1000.

3. **Cook-thread vs main-thread event firing.** Designed defensively (no `hou.*` in handler). If events ALWAYS fire on main thread (R8's claim), the design is over-engineered but still correct. If events sometimes fire on non-main threads (likely under farm scheduler), the design holds. Net: defensive design wins both cases.

4. **Cleanup race.** Event firing while `cool()` is being called. The `_alive: List[bool]` flag is the gate — once flipped to `[False]`, subsequent event handler invocations early-return. Test §5 case 4 pins this. Note: the flag is checked under no lock — Python's GIL provides atomic read of a list-element-access, so a torn read is impossible.

5. **Subscription leak across Python interpreter session.** PDG `GraphContext` instances are owned by Houdini's C++ side. On Python shutdown, the bridge's `__del__` is not guaranteed to run. Documented as an accepted limitation: bridge users SHOULD call `cool_all()` before daemon shutdown. Spike 3.2's daemon integration will wire this into `SynapseDaemon.stop()`.

6. **`pdg.PyEventHandler` GC during subscription.** If the handler instance is garbage-collected while still registered against the graph context, future events may segfault (pybind11 weak ref to dead Python object). The `Subscription._handler` field holds a strong reference. Test §5 case 1 pins this by checking handler-ref count drops to zero only after `cool()`.

### 7.3 Open questions — none

The orchestrator's Phase A scope resolves all design-time decisions
(scope picks, filter list, threading assumption, cleanup contract).
Open questions for FORGE: none. If FORGE encounters an ambiguity, halt
and surface per Section 0 standing orders.

### 7.4 API verification trace — every `pdg.*` / `hou.*` reference vs audit

| Reference in design | Audit section | Audit status |
|---|---|---|
| `pdg` (module) | §2.2 | RESOLVED |
| `pdg.GraphContext` | §2.6 | RESOLVED |
| `pdg.GraphContext.addEventHandler(handler, type)` | §2.6 dir() | RESOLVED (instancemethod) |
| `pdg.GraphContext.removeEventHandler(handler)` | §2.6 dir() | RESOLVED (instancemethod) |
| `pdg.PyEventHandler(callback)` | §2.5 | RESOLVED |
| `pdg.WorkItem` | §2.4 | RESOLVED |
| `pdg.WorkItem.cookDuration` | §2.4 dir() | RESOLVED (property) |
| `pdg.WorkItem.frame` | §2.4 dir() | RESOLVED (property) |
| `pdg.WorkItem.id` | §2.4 dir() | RESOLVED (property) |
| `pdg.WorkItem.state` | §2.4 dir() | RESOLVED (property) |
| `pdg.WorkItem.expectedResultData` | §2.4 dir() | RESOLVED (property) |
| `pdg.WorkItem.node` | §2.4 dir() | RESOLVED (property) |
| `pdg.EventType.CookStart` | §2.5 | RESOLVED (enum, int=38) |
| `pdg.EventType.CookComplete` | §2.5 | RESOLVED (enum, int=14) |
| `pdg.EventType.CookError` | §2.5 | RESOLVED (enum, int=12) |
| `pdg.EventType.CookWarning` | §2.5 | RESOLVED (enum, int=13) |
| `pdg.EventType.WorkItemAdd` | §2.5 | RESOLVED (enum, int=1) |
| `pdg.EventType.WorkItemStateChange` | §2.5 | RESOLVED (enum, int=5) |
| `pdg.EventType.WorkItemResult` | §2.5 | RESOLVED (enum, int=35; alias `WorkItemOutputFiles`) |
| `top_node.getPDGGraphContext()` | bridge.py:616 (R8 prior art) | RESOLVED via R8 precedent |
| `hou.node('/')` | hou root accessor (already used in codebase) | RESOLVED |
| `hou.topNodeTypeCategory()` | §2.6 / §2.8 | RESOLVED (function) |
| `pdg.Node.path()` | NOT AUDITED — assumed | **Risk §7.2 #1 — mitigated by defensive getattr** |
| `event.type` | bridge.py:628 R8 prior art | RESOLVED (used in R8) |
| `event.message` | bridge.py:633 R8 prior art | RESOLVED (used in R8 for CookError) |
| `event.workItem` | bridge sketch + R8 (implicit per PyEventHandler payload) | RESOLVED via convention; verified at runtime in Spike 3.3 |

**One reference assumed-not-audited (`pdg.Node.path()`).** Mitigated by
defensive `getattr` fallback in `_build_tops_event`. Spike 3.3 will pin
empirically.

---

## 8. Open questions for FORGE dispatch

**None.** All design-time decisions resolved at §2.4–§2.8. Pinned filter
allowlist (§2.5), pinned cleanup pattern (§2.7), pinned threading model
(§2.8), pinned graph-scope-only subscription for 3.1 (§2.4 decision).

If FORGE encounters an ambiguity not covered by §2 or §4, halt and
surface per Section 0 standing orders (no improvising). FORGE is on a
contract; deviation requires orchestrator dispatch back to ARCHITECT.

---

*End of design. FORGE proceeds. CRUCIBLE follows.*
