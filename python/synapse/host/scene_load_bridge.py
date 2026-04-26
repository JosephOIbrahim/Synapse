"""SceneLoadBridge — auto-warm wire from hou.hipFile.AfterLoad to
TopsEventBridge.

Sprint 3 Spike 3.2 ships the scene-load reaction layer for the
inside-out perception channel. Spike 3.1's TopsEventBridge handles
per-topnet PDG subscriptions; this module handles the scene-lifecycle
event that triggers re-discovery and re-warming when the artist opens
a new scene.

Composition, not inheritance. SceneLoadBridge takes a TopsEventBridge
instance via constructor injection and orchestrates its
``warm_all`` / ``cool_all`` lifecycle in response to
``hou.hipFile.AfterLoad`` events. See
``docs/sprint3/spike_3_2_design.md`` § 2.6 for the relationship
rationale.

Threading model
---------------
hou.hipFile event callbacks fire on Houdini's main thread (Mile 4
audit § 3.1: all four event types empirically captured with
``is_main_thread=True``). The handler calls ``hou.*`` and the
embedded TopsEventBridge directly — NO ``hdefereval`` marshaling. This
is the OPPOSITE shape from PDG events, which may fire on cook /
scheduler threads (Spike 3.1 § 2.8).

Cleanup contract
----------------
``hou.hipFile.addEventCallback`` returns ``None`` (Mile 4 audit § 1.2).
The bridge stores the bound method reference at ``__init__`` and
passes that same reference to ``hou.hipFile.removeEventCallback`` at
teardown. Removal is by callback identity, not by handle. Idempotency
at the call site is guarded by ``_subscribed: bool`` because the
underlying API does NOT deduplicate (audit § 4.1: FIFO-style
double-registration on repeated add).

See ``docs/sprint3/spike_3_2_design.md`` for the full design contract.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from synapse.host.tops_bridge import TopsEventBridge

# ── Defensive imports: bridge must import headless without hou ──

_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None


logger = logging.getLogger(__name__)


# ── Errors ──────────────────────────────────────────────────────────


class SceneLoadBridgeError(RuntimeError):
    """Raised when the bridge cannot perform an operation.

    Reasons: ``hou`` module unavailable; ``hou.hipFile`` namespace
    missing (degraded Houdini install).
    """


# ── The bridge ──────────────────────────────────────────────────────


class SceneLoadBridge:
    """Auto-warm wire from hou.hipFile.AfterLoad → TopsEventBridge.

    Sits between Houdini's scene lifecycle (hipFile events) and the PDG
    perception channel (TopsEventBridge). On every AfterLoad: cools
    stale subscriptions, walks the new scene, warms each TOP network.

    Composition, not inheritance — bridge takes a TopsEventBridge
    instance via constructor injection. Once ``subscribe()`` is called
    SceneLoadBridge takes total ownership of the embedded bridge's
    subscription lifecycle: callers MUST NOT independently warm or
    cool the embedded bridge after subscribe().

    Threading: AfterLoad fires on Houdini's main thread (Mile 4 audit
    § 3.1). The handler calls ``hou.*`` directly — no ``hdefereval``.

    Cleanup: callback-identity (audit § 1.2 — addEventCallback returns
    None). Idempotency: ``_subscribed: bool`` guards against double
    subscription because the API does NOT deduplicate (audit § 4.1).

    See ``docs/sprint3/spike_3_2_design.md`` § 2 for the full
    interface contract.
    """

    def __init__(
        self,
        tops_bridge: "TopsEventBridge",
    ) -> None:
        """Construct with an injected TopsEventBridge.

        Args:
            tops_bridge: The TopsEventBridge whose subscriptions this
                bridge will auto-warm and auto-cool on each scene
                load. Total ownership transfers to SceneLoadBridge
                once ``subscribe()`` is called.
        """
        if tops_bridge is None:
            raise TypeError(
                "SceneLoadBridge requires a TopsEventBridge instance"
            )
        self._tops_bridge = tops_bridge
        self._subscribed: bool = False
        # Bind once at construction so the same identity is passed to
        # both addEventCallback and removeEventCallback even across
        # pathological call orders (per design § 2.7).
        self._callback_fn: Callable[[Any], None] = self._on_hip_event
        self._reload_count: int = 0

    # ── Subscription lifecycle ─────────────────────────────────────

    def subscribe(self) -> None:
        """Register the AfterLoad callback with hou.hipFile.

        Idempotent — second call is a no-op (audit § 4.1 mandates an
        explicit guard since the API does NOT deduplicate).

        Does NOT call ``warm_all()`` on the injected TopsEventBridge.
        Initial warming for the currently-loaded scene is the caller's
        responsibility — the daemon decides timing.

        Raises:
            SceneLoadBridgeError: hou unavailable (headless mode).
        """
        if self._subscribed:
            return
        if not _HOU_AVAILABLE:
            raise SceneLoadBridgeError(
                "hou module not available — SceneLoadBridge.subscribe() "
                "requires Houdini's hou module"
            )
        hou.hipFile.addEventCallback(self._callback_fn)
        self._subscribed = True
        logger.info("SceneLoadBridge subscribed to hou.hipFile events")

    def unsubscribe(self) -> None:
        """Remove the AfterLoad callback and cool the embedded bridge.

        Idempotent. Removes the hipFile callback (by identity, per
        audit § 1.2) and calls ``tops_bridge.cool_all()`` to unwind
        every active PDG subscription.
        """
        if not self._subscribed:
            return
        if _HOU_AVAILABLE:
            try:
                hou.hipFile.removeEventCallback(self._callback_fn)
            except Exception as exc:
                logger.info(
                    "SceneLoadBridge unsubscribe swallowed teardown "
                    "error: %r",
                    exc,
                )
        self._subscribed = False
        # Cool the embedded bridge — total-ownership contract (§ 2.6).
        try:
            self._tops_bridge.cool_all()
        except Exception as exc:
            logger.info(
                "SceneLoadBridge unsubscribe swallowed cool_all "
                "error: %r",
                exc,
            )

    # ── Introspection ──────────────────────────────────────────────

    def is_subscribed(self) -> bool:
        """True iff the AfterLoad callback is currently registered."""
        return self._subscribed

    def reload_count(self) -> int:
        """How many AfterLoad events the bridge has handled.

        Increments once per AfterLoad event delivered to the handler;
        filtered events (BeforeLoad / BeforeClear / AfterClear etc.)
        do not count.
        """
        return self._reload_count

    # ── Internal — event handler ──────────────────────────────────

    def _on_hip_event(self, event_type: Any) -> None:
        """hou.hipFile callback — filtered to AfterLoad only.

        Per Mile 4 audit § 3.2: a fresh File→Open emits
        BeforeLoad → BeforeClear → AfterClear → AfterLoad. Only
        AfterLoad means the scene is fully loaded; warming on
        AfterClear would hit transient empty-scene state.
        """
        if not _HOU_AVAILABLE:
            return
        if event_type != hou.hipFileEventType.AfterLoad:
            return
        self._on_after_load()

    def _on_after_load(self) -> None:
        """Cool stale subscriptions, walk new scene, warm each topnet.

        Runs on Houdini's main thread (Mile 4 audit § 3.1). Total
        ownership of tops_bridge's subscription lifecycle (§ 2.6).
        """
        self._reload_count += 1
        # Step 1: cool stale subs from the prior scene. Their graph
        # contexts were destroyed in BeforeClear → AfterClear (audit
        # § 3.2). cool_all is idempotent and per-subscription
        # fault-tolerant (Spike 3.1 § 2.7).
        try:
            self._tops_bridge.cool_all()
        except Exception as exc:
            logger.info(
                "SceneLoadBridge AfterLoad cool_all swallowed: %r", exc
            )
        # Step 2: walk + warm. Delegate to TopsEventBridge.warm_all,
        # which already does discovery via
        # hou.node('/').allSubChildren() filtered by
        # hou.topNodeTypeCategory() and skips topnets that fail
        # individually.
        try:
            self._tops_bridge.warm_all()
        except Exception as exc:
            # Don't re-raise — protects Houdini's hipFile callback
            # invocation chain from agent-side bugs.
            logger.info(
                "SceneLoadBridge AfterLoad warm_all swallowed: %r", exc
            )
        # Reconciliation: if unsubscribe() fired mid-handler (e.g. a
        # warm callback or daemon shutdown invoked it while warm_all
        # was iterating), subscriptions added after the unsubscribe
        # are stale. Total-ownership contract (§ 2.6) requires the
        # embedded bridge be fully cooled when the SceneLoadBridge is
        # not subscribed.
        if not self._subscribed:
            try:
                self._tops_bridge.cool_all()
            except Exception as exc:
                logger.info(
                    "SceneLoadBridge AfterLoad reconcile cool_all "
                    "swallowed: %r",
                    exc,
                )


__all__ = [
    "SceneLoadBridge",
    "SceneLoadBridgeError",
]
