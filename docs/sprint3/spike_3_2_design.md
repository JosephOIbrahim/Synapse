# Spike 3.2 — SceneLoadBridge (Auto-Warm on Scene Load) Design

> **Authority:** ARCHITECT (design only). FORGE writes implementation;
> CRUCIBLE writes hostile tests. This document is the contract between
> them.
>
> **Status:** Pre-implementation. No code mutated. Mile 4 audit at
> ``docs/sprint3/spike_3_2_scene_load_audit.md`` is the empirical
> surface this design binds against. Spike 3.1's TopsEventBridge
> (``python/synapse/host/tops_bridge.py``) is the prior-art it composes
> with.
>
> **Sprint position:** Spike 3.2 closes Phase B of Sprint 3 — the
> scene-load auto-warm scaffold sitting on top of Spike 3.1's per-topnet
> PDG event bridge. Spike 3.3 (first TOPS event surface) and 3.4
> (hostile Crucible) build downstream and require Joe-at-GUI live
> Houdini cooks.

---

## 1. Diagnosis

### 1.1 What "auto-warm on scene load" means architecturally

Spike 3.1 shipped ``TopsEventBridge.warm(top_node)`` and
``TopsEventBridge.warm_all()`` — the daemon (or any caller) can
manually subscribe to PDG events on a TOP network. That's necessary,
but not sufficient, for the wrangler-in-the-room metaphor: every time
the artist hits **File → Open**, every TOP network in the new scene
is a fresh ``hou.LopNode``-style instance with a fresh
``pdg.GraphContext``. Stale subscriptions held against the prior
scene's contexts are dead handles. Without an auto-warm wire the
agent goes mute on scene reload — the wrangler walks out of the room.

Spike 3.2 closes that gap. It is the bridge between **Houdini's scene
lifecycle** (``hou.hipFile`` events) and **the PDG perception channel**
(``TopsEventBridge.warm_all()``). On every ``AfterLoad``:

1. Cool every subscription the embedded ``TopsEventBridge`` is holding
   (the prior scene's topnets are gone — those handles are dead).
2. Walk the new scene's network with ``hou.node('/').allSubChildren()``
   filtered by ``hou.topNodeTypeCategory()`` (Spike 3.1 § 2.6 already
   verified this surface).
3. ``tops_bridge.warm(topnet)`` per topnet found.

The wrangler stays in the room across as many scene loads as the artist
runs — fresh ears, fresh ``GraphContext`` references, every time.

### 1.2 The gap between Spike 3.1's scaffold and what Phase B needs

Spike 3.1's ``TopsEventBridge.warm_all()`` is a one-shot discovery: it
walks the current scene, warms each topnet, returns the list of
``Subscription`` tokens. It does **not** subscribe to ``hou.hipFile``
events. It does **not** re-fire on scene change. It does **not** cool
stale subscriptions when the underlying scene rotates out from under
them.

Phase B needs the auto-fire wiring layered on top. Composition, not
inheritance — see § 2.6 for the relationship choice.

### 1.3 Mile 4 audit — load-bearing findings (cited verbatim)

The audit at ``docs/sprint3/spike_3_2_scene_load_audit.md`` is the
empirical contract. Three findings drive the design:

| Finding | Audit § | Design consequence |
|---|---|---|
| All four hipFile events fire on ``MainThread`` (``is_main_thread=True``) | § 3, § 3.1 | **NO ``hdefereval`` in the handler.** Direct call. § 2.5 below. |
| Event sequence on File→Open: BeforeLoad → BeforeClear → AfterClear → AfterLoad | § 3, § 3.2 | **Trigger filter MUST be ``AfterLoad`` specifically.** ``AfterClear`` fires mid-load against transient empty-scene state — would warm zero topnets. § 2.4. |
| ``hou.hipFile.addEventCallback`` returns ``None``; double-add ≠ deduped (FIFO) | § 1.2, § 4.1 | **Cleanup is callback-identity, not handle-based.** Bridge stores the bound function reference. § 2.7. **Idempotency is the bridge's responsibility** via ``_subscribed: bool`` guard. § 3. |

Audit conclusion (§ 6, verbatim): *"None — surfaces matched watchlist
exactly."* All six surfaces this design touches resolved cleanly.

### 1.4 Cognitive vs host placement

Same boundary lint applies as Spike 3.1: the bridge imports ``hou``,
so it lives under ``synapse.host.*``. Cognitive layer (``synapse.
cognitive.*``) talks to it via the ``TopsEventBridge`` callback
contract — no ``hou`` reference crosses the boundary.

Path: ``python/synapse/host/scene_load_bridge.py``. Mirrors Spike
3.1's ``tops_bridge.py`` placement.

---

## 2. SceneLoadBridge interface

### 2.1 Naming choice — justification

**Picked:** ``SceneLoadBridge``. Three candidates considered:

| Name | Pro | Con | Verdict |
|---|---|---|---|
| ``SceneLoadBridge`` | Matches audit doc, spike name, and the Mile 4 audit's own subject ("scene-load API audit"). Verb-noun symmetric with ``TopsEventBridge``. Names the **event source** it bridges (hipFile events) | Slightly long | **Picked.** Symmetric with prior art; name traces to audit. |
| ``AutoWarmBridge`` | Names the **action** (auto-warm) | Action-named classes drift when scope expands. If Spike 3.5 adds AfterMerge handling or AfterSave handling, "auto-warm" no longer describes the surface; the bridge becomes about scene-lifecycle reactions in general. Naming for the action that's-true-today is fragile. | Rejected. |
| ``HipFileBridge`` | Names the API surface | Too low-level. Doesn't say what it does, only what it imports. ``TopsEventBridge`` doesn't call itself ``PDGEventHandlerBridge`` for the same reason. | Rejected. |

### 2.2 Public class signature

```python
# python/synapse/host/scene_load_bridge.py

from typing import Any, Callable, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from synapse.host.tops_bridge import TopsEventBridge


class SceneLoadBridge:
    """Auto-warm wire from hou.hipFile.AfterLoad → TopsEventBridge.

    Sits between Houdini's scene lifecycle (hipFile events) and the PDG
    perception channel (TopsEventBridge). On every AfterLoad: cools
    stale subscriptions, walks the new scene, warms each TOP network.

    Composition (NOT inheritance) — bridge takes a TopsEventBridge
    instance via constructor injection. See § 2.6 for the relationship
    rationale.

    Threading contract (per Mile 4 audit § 3.1)
    -------------------------------------------
    hou.hipFile event callbacks fire on MainThread
    (is_main_thread=True, all four event types empirically). Therefore
    the AfterLoad handler may call hou.* directly — NO hdefereval
    marshaling required. This is the OPPOSITE shape from PDG events
    (which may fire on cook/scheduler threads, per Spike 3.1 § 2.8).

    Cleanup contract (per Mile 4 audit § 1.2 + § 4.1)
    -------------------------------------------------
    hou.hipFile.addEventCallback returns None — the bridge stores the
    bound method reference and passes it to removeEventCallback at
    teardown. Double-add is NOT deduped by the API (audit § 4.1
    confirms FIFO-style duplicate registration). The bridge's
    _subscribed bool flag is the idempotency guard at the call site.
    """

    def __init__(
        self,
        tops_bridge: "TopsEventBridge",
    ) -> None:
        """Construct with an injected TopsEventBridge.

        Args:
            tops_bridge: The TopsEventBridge whose subscriptions this
                bridge will auto-warm and auto-cool on each scene
                load. Bridge takes ownership of its subscription
                lifecycle once subscribe() is called — see § 2.6.
        """
        ...

    # ── Subscription lifecycle ──────────────────────────────────────

    def subscribe(self) -> None:
        """Register the AfterLoad callback with hou.hipFile.

        Idempotent — second call is a no-op (audit § 4.1 mandates an
        explicit guard since the API does NOT deduplicate).

        Does NOT call warm_all() on the injected TopsEventBridge.
        Initial warming for the currently-loaded scene is the caller's
        responsibility — the daemon decides timing. This keeps
        SceneLoadBridge a single-purpose component (react to
        scene-load events) and makes warm timing explicit at the call
        site.

        Raises:
            SceneLoadBridgeError: hou unavailable (headless mode).
        """
        ...

    def unsubscribe(self) -> None:
        """Remove the AfterLoad callback and cool the embedded bridge.

        Idempotent. Removes the hipFile callback (by identity, per
        audit § 1.2) and calls tops_bridge.cool_all() to unwind every
        active PDG subscription.
        """
        ...

    # ── Introspection ───────────────────────────────────────────────

    def is_subscribed(self) -> bool:
        """True iff the AfterLoad callback is currently registered."""
        ...

    def reload_count(self) -> int:
        """How many AfterLoad events the bridge has handled.

        Test fixture and observability hook. Increments once per
        AfterLoad event delivered to the handler (filtered events do
        not count).
        """
        ...
```

### 2.3 Errors

```python
class SceneLoadBridgeError(RuntimeError):
    """Raised when the bridge cannot perform an operation.

    Reasons: hou module unavailable; hou.hipFile namespace missing
    (degraded Houdini install).
    """
```

### 2.4 Trigger filter — AfterLoad SPECIFICALLY

**Decision:** filter on ``hou.hipFileEventType.AfterLoad`` only.
Drop everything else at the handler boundary.

**Rationale (audit § 3.2 verbatim):**

> A fresh File → Open emits **BeforeLoad → BeforeClear → AfterClear →
> AfterLoad** in sequence. Auto-warm must trigger on ``AfterLoad``
> specifically (not ``AfterClear``) to avoid warming against the
> transient empty-scene state mid-load: between ``AfterClear`` and
> ``AfterLoad`` the stage holds no nodes, so any TOP-network walk
> would return zero topnets and warm nothing useful.

**Implementation pattern** (matches Spike 3.1's ``_make_event_handler``
filter shape):

```python
def _on_hip_event(self, event_type: Any) -> None:
    """hou.hipFile callback — filtered to AfterLoad only."""
    if event_type != hou.hipFileEventType.AfterLoad:
        return
    self._on_after_load()
```

Identity-compare against the live enum member (``hou.hipFileEventType
.AfterLoad``) rather than the integer value: per the Mile 4 audit § 2.1
the enum members are real ``EnumValue`` instances with stable identity
across calls; equality on the enum is the documented contract. Matches
how Spike 3.1's handler reads ``event.type`` from PDG events.

### 2.5 Threading model — direct call, no hdefereval

**Decision:** the AfterLoad handler calls ``hou.*`` and
``tops_bridge.*`` synchronously, on whatever thread fired the event.

**Property the threading rule enforces:** all ``hou.*`` calls
originate on Houdini's main thread (the H21 single-threaded HOM
contract).

**Why the pattern is satisfied without ``hdefereval``** (per
orchestrator hygiene rule #7 — *property requirements over pattern
paraphrase*):

- ``hdefereval.executeInMainThread*`` exists to **marshal off-thread
  work onto the main thread**. It is the right tool when the
  originating callback fires on a worker/cook/scheduler thread (Spike
  3.1's PDG handler is the canonical SYNAPSE example;
  ``shared/bridge.py:649`` uses it for the PDG cook trigger).
- Mile 4 audit § 3 captured **all four** hipFile events firing on
  ``MainThread`` (``is_main_thread=True``, ``thread_id`` consistent
  across BeforeLoad / BeforeClear / AfterClear / AfterLoad).
- Therefore: the property "all ``hou.*`` calls on main thread" holds
  by construction inside an AfterLoad handler. No marshaling needed.
  Adding ``hdefereval.executeInMainThread`` would be cargo-cult —
  it would dispatch a main-thread call from the main thread, which
  is either a no-op (if the executor short-circuits same-thread
  dispatch) or a deadlock (if it queues and waits).

**Hard halt-and-surface trigger:** Section 0 of the Phase B
constitution names *"ANY suggestion to add hdefereval to the
scene-load handler"* as a halt trigger. This design honors that:
the handler is a direct call. No deferred dispatch. No
``executeInMainThread*``. No ``executeDeferred``.

### 2.6 Composition with TopsEventBridge — relationship choice

**Picked:** **composition with constructor injection.**
``SceneLoadBridge(tops_bridge=...)``.

**Three candidates considered:**

| Relationship | Rationale | Verdict |
|---|---|---|
| **Composition (injection)** | SceneLoadBridge wraps a TopsEventBridge instance. Each class keeps its single responsibility: TopsEventBridge handles per-topnet PDG subscriptions; SceneLoadBridge handles scene-lifecycle wiring. Hostile testing is trivial — pass a mock TopsEventBridge to assert ``warm_all`` and ``cool_all`` calls. Dependency direction matches Spike 3.1's natural extension point: ``TopsEventBridge.warm_all()`` is the public API SceneLoadBridge consumes. | **Picked.** |
| Inheritance (``SceneLoadBridge(TopsEventBridge)``) | Reuse the existing class via subclassing | **Rejected.** Inheritance implies "is-a" — SceneLoadBridge is not a TopsEventBridge, it's a *coordinator* of one. PDG event subscription and hipFile event subscription are different concerns: different event source, different threading model, different cleanup contract, different lifetime. Mixing them collapses two single-responsibility classes into one with double the surface. |
| Separate (no formal relationship — daemon coordinates both) | Daemon holds both; SceneLoadBridge handler calls into daemon to trigger warm | **Rejected.** Pushes coordination logic into the daemon, which already has too much. Makes the AfterLoad → warm relationship implicit (a hop through daemon state) rather than explicit (a method call on the injected dependency). Spike 3.4's hostile suite would have to assert daemon state instead of bridge calls. |

**Ownership contract on subscribe():**
Once ``SceneLoadBridge.subscribe()`` is called, **the SceneLoadBridge
takes total ownership of the injected TopsEventBridge's subscription
lifecycle.** On every AfterLoad it calls ``tops_bridge.cool_all()``
followed by ``tops_bridge.warm_all()``. Callers MUST NOT independently
warm or cool the embedded bridge after ``subscribe()`` — those
subscriptions would be wiped on the next AfterLoad regardless.

This is a deliberate choice: the alternative (track only "subs we
made") leaves stale-subscription cleanup as a runtime hazard
(externally-warmed subs hold dead ``GraphContext`` references after
a scene reload). The total-ownership rule is documented in the
docstring; daemon integration in Spike 3.3 honors it.

### 2.7 Cleanup contract — callback-identity, not handle-based

**Per Mile 4 audit § 1.2 (verbatim):**

> ``hou.hipFile.addEventCallback`` returns ``None`` (NoneType). The
> auto-warm scaffold MUST store the bound callback function reference
> itself (not a returned handle) and pass that same function reference
> to ``hou.hipFile.removeEventCallback`` at teardown.

**Implementation:**

```python
def __init__(self, tops_bridge: "TopsEventBridge") -> None:
    self._tops_bridge = tops_bridge
    self._subscribed: bool = False
    # Store the bound method reference for identity-based removal.
    # Per audit § 4.1, addEventCallback does NOT dedupe — the
    # _subscribed flag is the idempotency guard.
    self._callback_fn: Callable[[Any], None] = self._on_hip_event
    self._reload_count: int = 0

def subscribe(self) -> None:
    if self._subscribed:
        return  # Idempotent — audit § 4.1 mandates this guard
    if not _HOU_AVAILABLE:
        raise SceneLoadBridgeError(
            "hou module not available — SceneLoadBridge.subscribe() "
            "requires Houdini's hou module"
        )
    hou.hipFile.addEventCallback(self._callback_fn)
    self._subscribed = True

def unsubscribe(self) -> None:
    if not self._subscribed:
        return  # Idempotent
    if _HOU_AVAILABLE:
        try:
            hou.hipFile.removeEventCallback(self._callback_fn)
        except Exception as exc:
            logger.info(
                "SceneLoadBridge unsubscribe swallowed teardown error: %r",
                exc,
            )
    self._subscribed = False
    # Cool the embedded bridge — total-ownership contract per § 2.6
    try:
        self._tops_bridge.cool_all()
    except Exception as exc:
        logger.info(
            "SceneLoadBridge unsubscribe swallowed cool_all error: %r",
            exc,
        )
```

**Why bind once at construction (not lazily in subscribe):** Python
re-binding a method off the same instance produces a new bound-method
object each time. Storing the bound reference once at ``__init__``
guarantees the same identity is passed to ``addEventCallback`` and
``removeEventCallback`` even across pathological call orders. This
matches Spike 3.1's ``Subscription._handler`` strong-reference
discipline (3.1 § 7.2 risk #6).

### 2.8 AfterLoad handler — full spec

```python
def _on_after_load(self) -> None:
    """Cool stale subscriptions, walk new scene, warm each topnet.

    Runs on Houdini's main thread (Mile 4 audit § 3.1). Total
    ownership of tops_bridge's subscription lifecycle (§ 2.6).
    """
    self._reload_count += 1
    # Step 1: cool stale subs from the prior scene. The graph contexts
    # we held references to are now dead — those topnets were cleared
    # in the BeforeClear → AfterClear phase (audit § 3.2). cool_all()
    # is idempotent and per-subscription-fault-tolerant (3.1 § 2.7).
    try:
        self._tops_bridge.cool_all()
    except Exception as exc:
        logger.info(
            "SceneLoadBridge AfterLoad cool_all swallowed: %r", exc
        )
    # Step 2: walk + warm. tops_bridge.warm_all() already does
    # discovery via hou.node('/').allSubChildren() filtered by
    # hou.topNodeTypeCategory() and skips topnets that fail
    # individually (3.1 § 2.x — _build_event_handler partial-failure
    # rollback). One-line delegation.
    try:
        self._tops_bridge.warm_all()
    except Exception as exc:
        # Don't re-raise — protects Houdini's hipFile callback
        # invocation chain from agent-side bugs. Same defensive shape
        # as Spike 3.1's perception_callback exception swallowing.
        logger.info(
            "SceneLoadBridge AfterLoad warm_all swallowed: %r", exc
        )
```

**Why no separate ``_walk_topnets`` method:** ``TopsEventBridge.
warm_all()`` already does it (Spike 3.1 ``tops_bridge.py:324–362``).
Re-implementing the walk would be duplication. The AfterLoad handler
delegates.

### 2.9 Re-export from ``synapse.host``

Mirror Spike 3.1's pattern in ``python/synapse/host/__init__.py``:

```python
from synapse.host.scene_load_bridge import (
    SceneLoadBridge,
    SceneLoadBridgeError,
)

__all__ = [
    # ...existing entries...
    # SceneLoadBridge (Spike 3.2 — auto-warm on scene load)
    "SceneLoadBridge",
    "SceneLoadBridgeError",
]
```

---

## 3. Idempotency contract

| Property | Mechanism | Hostile test that pins it |
|---|---|---|
| Multiple ``subscribe()`` calls do not stack registrations | ``self._subscribed: bool`` early-return guard | § 5 case 3 |
| Multiple AfterLoad events do not duplicate per-topnet handlers | Each handler call begins with ``tops_bridge.cool_all()`` before re-warming. Spike 3.1's ``cool_all()`` is itself idempotent | § 5 case 3 |
| ``unsubscribe()`` after ``subscribe()`` zero-leaks | ``removeEventCallback`` by identity (audit § 1.2) + ``cool_all()`` on embedded bridge | § 5 case 8 |
| ``unsubscribe()`` without prior ``subscribe()`` is safe | Same ``_subscribed`` guard inverted | § 5 case 8 |
| Re-loading the same scene re-warms cleanly | cool_all → warm_all per AfterLoad. Same scene = same topnet paths = same warm pattern, different ``GraphContext`` instances | § 5 case 3 |
| Cool-all on shutdown removes every subscription added across N scene loads | ``unsubscribe()`` calls ``tops_bridge.cool_all()``; cool_all unwinds every ``Subscription`` regardless of which AfterLoad created it | § 5 case 8 |

**Audit-mandated guard:** § 4.1 states *"second_add_same_fn ok AND
second_remove ok → API treats double-add as two distinct registrations
(FIFO-style removal). Spike 3.2 must guard against double-subscription
with an explicit bool flag or single-registration discipline."* The
``_subscribed: bool`` field is the chosen guard.

---

## 4. Files to touch

| Action | Path | Notes |
|---|---|---|
| **create** | ``python/synapse/host/scene_load_bridge.py`` | ``SceneLoadBridge``, ``SceneLoadBridgeError`` — full module. Defensive ``hou`` import (mirrors ``tops_bridge.py:60–65``). |
| **modify** | ``python/synapse/host/__init__.py`` | re-export ``SceneLoadBridge``, ``SceneLoadBridgeError`` (per § 2.9). |
| **create** (FORGE) | ``tests/test_scene_load_bridge.py`` | Basic suite — construction, subscribe/unsubscribe round-trip, AfterLoad fires warm path (mocked), AfterClear filtered out, hou-unavailable raises. ~5–7 tests. |
| **extend** (CRUCIBLE) | ``tests/test_scene_load_bridge.py`` | Hostile suite § 5 — 10 cases. Below the ``# CRUCIBLE`` divider, mirroring Spike 3.1's split. |

**Out of scope (do NOT touch):**

- ``python/synapse/host/tops_bridge.py`` — Spike 3.1 stays as-is. Read it,
  compose with it, do not modify it.
- ``shared/bridge.py`` — R8 stays as-is. Reading the pattern is fine.
- ``python/synapse/cognitive/**`` — bridge stays in host layer; cognitive
  boundary preserved.
- ``python/synapse/host/daemon.py`` — daemon-side wiring of the new
  bridge is Spike 3.3 territory (live integration), not Spike 3.2.
- ``python/synapse/server/**`` — Strangler Fig WebSocket path stays
  operational.

---

## 5. Test plan for CRUCIBLE

Hostile cases mandatory. Each test name pins the failure mode it
probes. All tests run in standalone mode (no live Houdini) — ``hou``
and ``pdg`` are mocked. Reuse the FakePDG / FakeTopNode / FakeGraphContext
shapes from ``tests/test_tops_bridge.py`` where useful. Add a
FakeHipFile namespace to capture ``addEventCallback`` /
``removeEventCallback`` and fire events synchronously.

| # | Test name | Probes |
|---|---|---|
| 1 | ``test_after_load_event_warms_all_topnets`` | ``AfterLoad`` fires → ``tops_bridge.cool_all()`` then ``tops_bridge.warm_all()`` called once each. Order matters. Use a real ``TopsEventBridge`` with the FakePDG fixture, scene with N=3 topnets; assert 3 ``Subscription`` objects in ``tops_bridge.active_subscriptions()`` after the event fires. |
| 2 | ``test_after_clear_event_does_not_warm`` | ``AfterClear`` fires → ``warm_all`` NOT called. Filter holds (audit § 3.2 — must NOT warm against transient empty state). Assert ``tops_bridge.active_subscriptions() == ()`` after firing AfterClear with a 3-topnet scene. |
| 3 | ``test_multiple_after_load_no_duplicate_subscriptions`` | Fire ``AfterLoad`` 3 times in sequence on a 2-topnet scene. After all three: exactly 2 active ``Subscription`` objects, NOT 6. ``cool_all`` between warmings is the mechanism that pins this. |
| 4 | ``test_scene_loads_with_zero_topnets_no_error`` | Scene walk returns no topnets. ``AfterLoad`` fires, handler runs cleanly, no exception, ``tops_bridge.active_subscriptions() == ()``. ``reload_count() == 1``. |
| 5 | ``test_one_topnet_warm_failure_does_not_block_others`` | Scene has 3 topnets; topnet #2's ``getPDGGraphContext()`` returns ``None`` (warm raises ``TopsBridgeError`` per Spike 3.1 § 2.6). Topnets 1 and 3 still get warmed. ``len(tops_bridge.active_subscriptions()) == 2``. |
| 6 | ``test_unsubscribe_during_after_load_handling_does_not_crash`` | While ``_on_after_load`` is mid-flight, an ``unsubscribe()`` call fires from another thread (simulated via ``threading.Event`` synchronization). Bridge does not double-cool, does not crash, ``unsubscribe`` completes idempotently. |
| 7 | ``test_subscribe_unsubscribe_no_callback_leak`` | After ``subscribe() → unsubscribe()``, the FakeHipFile's registered-callback list is empty AND ``tops_bridge.active_subscriptions() == ()``. ``is_subscribed() == False``. Re-subscribe works cleanly. |
| 8 | ``test_unsubscribe_idempotent_and_subscribe_idempotent`` | ``unsubscribe()`` without prior ``subscribe()`` — no crash, no error. ``subscribe()`` twice — second call is a no-op, FakeHipFile registered-callback list has length 1 not 2 (audit § 4.1 mandates this guard since the API does NOT dedupe). |
| 9 | ``test_multiple_scene_load_bridge_instances_same_hou`` | Two ``SceneLoadBridge`` instances with two different injected ``TopsEventBridge``s, both subscribed against the same FakeHipFile. ``AfterLoad`` fires once → BOTH bridges run their handlers, both ``TopsEventBridge``s get their ``warm_all()`` invoked. Independence holds (matches Spike 3.1 § 5 case 3 hostile property for TopsEventBridge). |
| 10 | ``test_callback_raising_mid_event_swallowed`` | Inject a ``TopsEventBridge`` whose ``warm_all()`` raises ``RuntimeError("synthetic")``. ``AfterLoad`` fires → exception is swallowed, bridge state stays consistent, ``reload_count() == 1`` (event WAS handled, even though warming failed). Houdini's hipFile callback invocation chain is never broken by agent-side bugs. |

**Required assertions:**

- Specific failure modes named in test docstrings
- ``assert isinstance(...)`` for type checks, not ``assert ... is not None``
- Specific equality / count assertions, not "didn't crash"
- For idempotency tests: assert specific counts, not absence-of-crash
- Use a real ``TopsEventBridge`` (with FakePDG fixture from
  ``test_tops_bridge.py``) where the test asserts on subscription
  state; use a mock TopsEventBridge where the test asserts on call
  shape (``warm_all`` called once, ``cool_all`` called first)

---

## 6. Gate criteria

Restated **verbatim** from
``docs/sprint3/CONTINUATION_INSIDE_OUT_TOPS.md`` § "Spike 3.2 gate":

> - Bridge ``warm_on_scene_load()`` runs inside live Houdini 21.0.671
> - TOP networks discovered correctly across at least 2 test scenes
> - ``hou.hipFile`` event callback fires on scene reload
> - Manual verification log captured in ``docs/sprint3/spike_3_2_warm_verification.md``

**Phase B constitution gate (Section 4)** adds the structural checks:

- docs/sprint3/spike_3_2_design.md exists with all 8 required sections ← *this artifact*
- Every API reference traces to a RESOLVED audit entry ← § 7.4 below
- SceneLoadBridge implementation matches design § 2 signatures exactly
- NO hdefereval in scene-load handler (cite line numbers in
  implementation — must be a direct call path)
- Trigger filter is hou.hipFileEventType.AfterLoad (cite line)
- Basic + hostile test suites green
- Test count strictly increased from sprint baseline (2850 → ≥2860)
- Cleanup contract is callback-identity (cite line numbers)
- Idempotency: multiple AfterLoad events do not duplicate subscriptions
  (cite hostile test that pins this — § 5 case 3)
- All commits atomic, shippable individually
- Working tree clean
- Composition with TopsEventBridge documented in design § 2.6

**Note on the four CONTINUATION gate bullets:** the third (live H21
callback firing) is what Joe-at-GUI verifies in Spike 3.3's live
cook session; Spike 3.2's design phase delivers the scaffold + the
hostile test that synthetically fires AfterLoad to prove the wiring.
Live verification is Spike 3.3's gate, not Spike 3.2's. CONTINUATION's
fourth bullet (manual verification log) similarly lands during the
live session — Phase B closes when scaffold + hostile suite land.

---

## 7. Risk register

### 7.1 Invariants threatened — and how the design preserves them

| Invariant | Status under this design | Evidence |
|---|---|---|
| All ``hou.*`` calls on main thread | **Preserved.** AfterLoad handler fires on MainThread per audit § 3 (all four event types). Direct call path. | § 2.5 + audit § 3 |
| All tool calls route through Dispatcher | **Preserved.** SceneLoadBridge does not dispatch tool calls — it dispatches PDG subscription lifecycle through the injected TopsEventBridge | § 2.6 — composition with TopsEventBridge, no Dispatcher reference |
| ``AgentToolError`` envelope shape preserved | **Preserved.** Bridge produces no error envelopes; raises ``SceneLoadBridgeError`` for unrecoverable construction faults (matches Spike 3.1's ``TopsBridgeError`` shape) | § 2.3 |
| Test count strictly increases | **Will hold.** § 6 floor is +5 (basic) + 10 (hostile) = +15 minimum vs the 2850 baseline | § 5 + § 6 |
| No new dependencies | **Preserved.** Bridge uses only ``threading``, ``logging``, ``typing``, and the (defensively-imported) ``hou`` module already in scope | § 2 import list |
| Strangler Fig WebSocket survives | **Preserved.** ``mcp_server.py`` not touched | § 4 out-of-scope |
| Hard API verification before any new ``hou.*`` | **Preserved.** Every API reference traces to either Spike 3.0 PDG audit or Spike 3.2 scene-load audit RESOLVED list | § 7.4 below |
| No ``import hou`` under ``synapse/cognitive/**`` | **Preserved.** Bridge lives in ``synapse.host.*``. Cognitive layer talks to it via constructor injection of TopsEventBridge | § 1.4 placement decision |
| Cleanup is callback-identity, not handle-based | **Preserved.** Bridge stores the bound method reference at ``__init__`` and uses it for both add and remove | § 2.7 |

### 7.2 What could go wrong

1. **``hou.hipFile.addEventCallback`` returns ``None`` (Spike 3.0
   § 3.1 + audit § 1.2 finding).** Sketch must store the callback
   function reference, NOT a returned handle. Mitigation: bind the
   method reference once at ``__init__`` (``self._callback_fn =
   self._on_hip_event``) and use it for both add and remove.
   Hostile test § 5 case 7 pins this.

2. **Walk-cost on large scenes.** ``hou.node('/').allSubChildren()``
   on a scene with many thousand nodes can be slow (linear in node
   count, called inside a hipFile event handler that blocks Houdini
   UI). Spike 3.1 already used this pattern in ``warm_all()`` without
   complaint, so the cost is bounded by Spike 3.1's own performance
   envelope. Mitigation: SceneLoadBridge delegates to
   ``warm_all()`` rather than re-implementing the walk — any future
   optimization to the walk lands in one place. If Spike 3.4 hostile
   suite finds the cost unacceptable on artist-scale scenes, the
   optimization is a Spike 3.4 follow-up, not a Spike 3.2 design
   blocker. **Accepted risk.**

3. **Race: AfterLoad fires while a previous warm is still in
   progress.** Two AfterLoad events in rapid succession (rare —
   would require user double-clicking File→Open, or a script
   firing two loads back-to-back). Both handlers run on
   MainThread (audit § 3.1) and Houdini's main-thread queue is
   serial — the second handler runs after the first completes.
   Python's GIL plus single-threaded HOM means the race is
   structurally impossible. **No mitigation needed.** Hostile test
   § 5 case 6 covers the related (and possible) race: ``unsubscribe``
   from another thread mid-handler, mitigated by ``cool_all`` /
   ``unsubscribe`` idempotency.

4. **Subscription leak across Python interpreter session.** Same
   accepted limitation as Spike 3.1 § 7.2 #5 — bridge users SHOULD
   call ``unsubscribe()`` before daemon shutdown. Spike 3.3 will
   wire this into ``SynapseDaemon.stop()`` alongside Spike 3.1's
   ``tops_bridge.cool_all()`` integration. **Documented; not a
   Spike 3.2 design blocker.**

5. **AfterLoad callback receives the *enum value*, not the integer.**
   Audit § 2.1 captured the members as ``EnumValue`` instances. The
   handler compares with ``event_type != hou.hipFileEventType.AfterLoad``
   — direct enum-member identity. Per Spike 3.1's PDG handler this
   is the supported comparison. **No risk.**

6. **Composition vs the daemon's existing wiring.** If the daemon
   already calls ``tops_bridge.warm_all()`` independently (e.g. at
   daemon boot, before SceneLoadBridge.subscribe() lands in Spike
   3.3), those subscriptions get cooled on the next AfterLoad — by
   design (§ 2.6 total-ownership contract). **Documented;
   coordinated at the daemon-integration phase, not at the bridge
   level.**

### 7.3 Open questions — none

All design-time decisions resolved at § 2.4–§ 2.8. Pinned trigger
filter (§ 2.4), pinned threading model (§ 2.5), pinned composition
relationship (§ 2.6), pinned cleanup contract (§ 2.7), pinned handler
behavior (§ 2.8). FORGE: if you encounter an ambiguity not covered by
§ 2 or § 4, halt and surface per Section 0 standing orders.

### 7.4 API verification trace — every ``hou.*`` reference vs audit

| Reference in design | Audit | Audit § | Audit status |
|---|---|---|---|
| ``hou`` (module) | Spike 3.0 § ALL_PROBED | RESOLVED |
| ``hou.hipFile`` (module) | Spike 3.2 audit § 5.1 | RESOLVED |
| ``hou.hipFile.addEventCallback(callback)`` | Spike 3.2 audit § 1.1 | RESOLVED (returns ``None``) |
| ``hou.hipFile.removeEventCallback(callback)`` | Spike 3.2 audit § 5.3 | RESOLVED |
| ``hou.hipFileEventType`` (type) | Spike 3.2 audit § 2.1 | RESOLVED |
| ``hou.hipFileEventType.AfterLoad`` | Spike 3.2 audit § 2.1 | RESOLVED |
| ``hou.hipFileEventType.AfterClear`` | Spike 3.2 audit § 2.1 | RESOLVED (referenced for filter-test only — bridge does NOT subscribe to this; hostile test fires it to prove the filter holds) |
| ``hou.node('/')`` (root accessor) | Spike 3.0 audit (already in codebase via Spike 3.1 ``tops_bridge.py:348``) | RESOLVED via Spike 3.1 prior art |
| ``hou.topNodeTypeCategory()`` | Spike 3.0 audit § 2.6 / § 2.8 | RESOLVED |
| ``allSubChildren()`` (on ``hou.Node``) | Spike 3.0 (referenced) + Spike 3.1 prior art at ``tops_bridge.py:348`` | RESOLVED via prior art |

**No assumed-not-audited references in this design.** Every ``hou.*``
path used by SceneLoadBridge appears in either the Spike 3.0 PDG
audit RESOLVED list or the Spike 3.2 scene-load audit RESOLVED list.

**Composition target:** ``TopsEventBridge`` (Spike 3.1) — full
interface contract at ``docs/sprint3/spike_3_1_design.md`` § 2,
implementation at ``python/synapse/host/tops_bridge.py:203–672``.
Methods consumed by SceneLoadBridge:

- ``TopsEventBridge.warm_all()`` (``tops_bridge.py:324–362``)
- ``TopsEventBridge.cool_all()`` (``tops_bridge.py:394–410``)
- ``TopsEventBridge.active_subscriptions()`` (``tops_bridge.py:414–417``,
  used in hostile assertions only)

---

## 8. Open questions for FORGE dispatch

**None.** All design-time decisions resolved at § 2.4–§ 2.8.

If FORGE encounters an ambiguity not covered by § 2 or § 4, halt and
surface per Section 0 standing orders (no improvising). FORGE is on a
contract; deviation requires orchestrator dispatch back to ARCHITECT.

Specifically NOT open for FORGE to decide:

- Whether to add ``hdefereval`` to the AfterLoad handler. **Decided:
  no.** Adding it is a Section 0 halt-and-surface trigger.
- Whether to subscribe to ``AfterClear`` or other hipFile events.
  **Decided: no.** Filter is ``AfterLoad`` only.
- Whether to inherit from TopsEventBridge. **Decided: no.**
  Composition with constructor injection.
- Whether ``subscribe()`` should also call ``warm_all()``. **Decided:
  no.** Initial warm is the daemon's call (Spike 3.3 wiring).
- Whether the bridge should walk topnets itself. **Decided: no.**
  Delegate to ``tops_bridge.warm_all()``.

---

*End of design. FORGE proceeds. CRUCIBLE follows.*
