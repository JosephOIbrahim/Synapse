"""TopsEventBridge — in-process PDG event bridge for inside-out perception.

Sprint 3 Spike 3.1 ships the agent's first **perception channel**.
Pre-Sprint-3, every PDG event paid a WebSocket round-trip; post-Sprint-3
the agent runs IN Houdini's Python interpreter and PDG callbacks fire
in the same process the agent reasons in. This module is the typed
in-process queue between PDG (event producer) and the cognitive layer
(event consumer).

Why this lives in ``synapse.host.*``
------------------------------------
The bridge imports ``hou`` (for TOP-network discovery) and ``pdg``
(for event registration). The cognitive boundary lint forbids
``import hou`` under ``synapse.cognitive.*``. Cognitive layer code
talks to the bridge via a pure-Python callback contract — no ``hou``
or ``pdg`` reference crosses the boundary.

Empirical surface
-----------------
Every API reference traces to Spike 3.0's audit:
``docs/sprint3/spike_3_0_pdg_api_audit.md`` (RESOLVED list). One
reference (``pdg.Node.path()``) is not directly audited and uses a
defensive ``getattr`` fallback in ``_build_tops_event``.

Threading model
---------------
PDG event callbacks may fire on a non-main thread (cook thread,
scheduler worker). The bridge's internal handler reads ``pdg.*``
properties only — no ``hou.*`` calls — and is safe to invoke from any
thread. The user-supplied ``perception_callback`` is invoked on
whatever thread the PDG event fires on. Cross-thread delivery to the
daemon's perception queue is the cognitive layer's responsibility
(typically via ``queue.Queue.put_nowait``).

See ``docs/sprint3/spike_3_1_design.md`` for the full design contract.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:  # pragma: no cover
    from synapse.cognitive.dispatcher import Dispatcher

# ── Defensive imports: bridge must import headless without hou or pdg ──

_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None

_PDG_AVAILABLE = False
try:
    import pdg
    _PDG_AVAILABLE = True
except ImportError:
    pdg = None


logger = logging.getLogger(__name__)


# ── Spike 3.0 audit-verified pdg.EventType integer values ─────────────
#
# Hard-coded so the module imports headless. Audit § 2.5 enum members.
# Verified against pdg.EventType at runtime when pdg is available.

_EVT_COOK_START = 38
_EVT_COOK_COMPLETE = 14
_EVT_COOK_ERROR = 12
_EVT_COOK_WARNING = 13
_EVT_WORKITEM_ADD = 1
_EVT_WORKITEM_STATE_CHANGE = 5
_EVT_WORKITEM_RESULT = 35

# Surfaced allowlist (design § 2.5). Anything outside this set is
# silently dropped at the bridge boundary.
_SURFACED_EVENT_TYPES: FrozenSet[int] = frozenset(
    {
        _EVT_COOK_START,
        _EVT_COOK_COMPLETE,
        _EVT_COOK_ERROR,
        _EVT_COOK_WARNING,
        _EVT_WORKITEM_ADD,
        _EVT_WORKITEM_STATE_CHANGE,
        _EVT_WORKITEM_RESULT,
    }
)

# Human-readable event names (design § 2.5 mapping).
_EVENT_NAME_BY_INT: Dict[int, str] = {
    _EVT_COOK_START: "tops.cook.start",
    _EVT_COOK_COMPLETE: "tops.cook.complete",
    _EVT_COOK_ERROR: "tops.cook.error",
    _EVT_COOK_WARNING: "tops.cook.warning",
    _EVT_WORKITEM_ADD: "tops.workitem.add",
    _EVT_WORKITEM_STATE_CHANGE: "tops.workitem.state_change",
    _EVT_WORKITEM_RESULT: "tops.workitem.result",
}


# ── Errors ──────────────────────────────────────────────────────────


class TopsBridgeError(RuntimeError):
    """Raised when the bridge cannot perform an operation.

    Reasons include: PDG module unavailable; TOP node has no live
    graph context; ``hou`` not importable when ``warm_all()`` is called.
    """


# ── Value objects ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class TopsEvent:
    """Typed event surfaced to the perception callback.

    Constructed by the bridge from raw ``pdg.Event`` objects. Reads only
    ``pdg.*`` properties — no ``hou.*`` calls — so safe to construct
    on any thread.

    Optional fields are populated per ``event_type``. Absent → ``None``
    or empty tuple.
    """

    event_type: str
    pdg_event_type_int: int
    top_node_path: str
    timestamp: float

    work_item_id: Optional[int] = None
    work_item_frame: Optional[float] = None
    work_item_state: Optional[str] = None
    work_item_outputs: Tuple[str, ...] = ()
    work_item_cook_duration_seconds: Optional[float] = None
    node_path: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializable form for downstream JSON / WebSocket / log."""
        return {
            "event_type": self.event_type,
            "pdg_event_type_int": self.pdg_event_type_int,
            "top_node_path": self.top_node_path,
            "timestamp": self.timestamp,
            "work_item_id": self.work_item_id,
            "work_item_frame": self.work_item_frame,
            "work_item_state": self.work_item_state,
            "work_item_outputs": list(self.work_item_outputs),
            "work_item_cook_duration_seconds": (
                self.work_item_cook_duration_seconds
            ),
            "node_path": self.node_path,
            "error_message": self.error_message,
        }


@dataclass(frozen=True, slots=True)
class Subscription:
    """Token returned from ``warm(...)``. Caller stores for ``cool()``.

    Per Spike 3.0 finding: cleanup is by handler-identity, not by an
    opaque returned handle. The bridge stores the bound
    ``pdg.PyEventHandler`` instance and the ``pdg.GraphContext`` it was
    registered against so that ``cool()`` can call
    ``graph_context.removeEventHandler(handler)``.

    The ``_alive`` field is a single-element list whose only element is
    flipped from ``True`` to ``False`` by ``cool()``. Python's GIL makes
    list-element-access atomic, so the event handler can read it
    without a lock for an idempotency guard.
    """

    top_node_path: str
    scope: str  # "graph" | "node" | "workitem"
    event_types: Tuple[int, ...]
    # Bridge-private fields (consumers read public fields only):
    _handler: Any = field(repr=False)
    _graph_context: Any = field(repr=False)
    _alive: List[bool] = field(repr=False)


# ── The bridge ──────────────────────────────────────────────────────


class TopsEventBridge:
    """In-process PDG event bridge for SYNAPSE inside-out perception.

    Subscribes to PDG events at the audit-verified GraphContext scope
    and delivers typed events to a pure-Python callback. Bridge
    instances are independent — multiple can subscribe to the same
    graph context without interfering.

    See ``docs/sprint3/spike_3_1_design.md`` § 2 for the full interface
    contract and § 7.4 for the API verification trace against Spike 3.0
    audit findings.
    """

    def __init__(
        self,
        perception_callback: Callable[[TopsEvent], None],
        *,
        dispatcher: Optional["Dispatcher"] = None,
        max_dropped_log: int = 1024,
    ) -> None:
        if perception_callback is None:
            raise TypeError(
                "TopsEventBridge requires a perception_callback callable"
            )
        self._perception_callback = perception_callback
        self._dispatcher = dispatcher
        self._max_dropped_log = max(1, max_dropped_log)
        self._subscriptions: List[Subscription] = []
        self._dropped: int = 0
        self._lock = threading.Lock()

    # ── Subscription lifecycle ─────────────────────────────────────

    def warm(self, top_node: Any) -> Subscription:
        """Subscribe to one TOP network's events.

        Acquires the live ``pdg.GraphContext`` via
        ``top_node.getPDGGraphContext()`` (R8 pattern, ``bridge.py:616``)
        and registers a ``pdg.PyEventHandler`` against the surfaced
        event types.

        Args:
            top_node: The TOP network's ``hou.Node``. Must expose
                ``path()`` and ``getPDGGraphContext()``.

        Returns:
            A ``Subscription`` token the caller stores for later
            ``cool(subscription)`` cleanup.

        Raises:
            TopsBridgeError: PDG module unavailable; TOP node has no
                live graph context; or registration failed.
        """
        if not _PDG_AVAILABLE:
            raise TopsBridgeError(
                "pdg module not available — TopsEventBridge.warm() "
                "requires Houdini's standalone pdg module"
            )
        if top_node is None:
            raise TopsBridgeError("warm() requires a TOP node, got None")

        try:
            top_node_path = top_node.path()
        except Exception as exc:  # pragma: no cover - defensive
            raise TopsBridgeError(
                f"Could not read TOP node path: {exc!r}"
            ) from exc

        # R8 pattern: live graph contexts come from the TOP node
        # instance — never class-instantiated. See bridge.py:616.
        graph_context = top_node.getPDGGraphContext()
        if graph_context is None:
            raise TopsBridgeError(
                f"TOP node {top_node_path} has no live graph context "
                "(network not yet instantiated, or not a topnet). "
                "Class-instantiation of pdg.GraphContext() is for "
                "fresh graphs only — never use it to attach to the "
                "artist's existing scene."
            )

        alive: List[bool] = [True]
        handler = self._make_event_handler(alive, top_node_path)

        # Register the same handler against each surfaced event type.
        # Per audit § 2.6, addEventHandler is the 2-arg form
        # (handler, EventType). R8 prior art at bridge.py:637-638.
        registered: List[int] = []
        try:
            for event_type_int in sorted(_SURFACED_EVENT_TYPES):
                event_type_enum = self._resolve_event_type_enum(event_type_int)
                graph_context.addEventHandler(handler, event_type_enum)
                registered.append(event_type_int)
        except Exception as exc:
            # Partial failure: roll back what we did register, then raise.
            for event_type_int in registered:
                try:
                    graph_context.removeEventHandler(handler)
                except Exception:
                    pass
            raise TopsBridgeError(
                f"Failed to register event handler on {top_node_path}: "
                f"{exc!r}"
            ) from exc

        subscription = Subscription(
            top_node_path=top_node_path,
            scope="graph",
            event_types=tuple(registered),
            _handler=handler,
            _graph_context=graph_context,
            _alive=alive,
        )
        with self._lock:
            self._subscriptions.append(subscription)
        logger.info(
            "TopsEventBridge warmed %s (%d event types)",
            top_node_path,
            len(registered),
        )
        return subscription

    def warm_all(self) -> List[Subscription]:
        """Discover every TOP network in the scene and warm each.

        Uses ``hou.node('/').allSubChildren()`` filtered by
        ``hou.topNodeTypeCategory()`` to enumerate. Skips topnets whose
        ``getPDGGraphContext()`` returns ``None`` (uninstantiated).

        Spike 3.2 will integrate this with ``hou.hipFile.addEventCallback``
        for re-warm on scene load. Spike 3.1 does not auto-fire on
        scene change.

        Returns:
            List of subscriptions in discovery order. Empty list when
            ``hou`` is unavailable (headless).
        """
        if not _HOU_AVAILABLE:
            return []
        if not _PDG_AVAILABLE:
            raise TopsBridgeError(
                "pdg module not available — cannot warm_all without pdg"
            )

        topnet_category = hou.topNodeTypeCategory()
        results: List[Subscription] = []
        for node in hou.node("/").allSubChildren():
            try:
                if node.type().category() != topnet_category:
                    continue
            except Exception:
                continue
            try:
                results.append(self.warm(node))
            except TopsBridgeError as exc:
                logger.info(
                    "TopsEventBridge skipped %s: %s",
                    getattr(node, "path", lambda: "<unknown>")(),
                    exc,
                )
        return results

    def cool(self, subscription: Subscription) -> None:
        """Unsubscribe one TOP network. Idempotent.

        No-op if the underlying graph context has been destroyed (e.g.
        network deleted while the subscription was held). Always flips
        ``subscription._alive[0]`` to ``False`` first so that any
        in-flight events early-return from the handler.
        """
        if subscription is None:
            return
        # Flip alive flag BEFORE removing the handler so any in-flight
        # event invocations see the closed state.
        subscription._alive[0] = False
        try:
            subscription._graph_context.removeEventHandler(
                subscription._handler
            )
        except Exception as exc:
            logger.info(
                "TopsEventBridge cool() swallowed teardown error on %s: %r",
                subscription.top_node_path,
                exc,
            )
        with self._lock:
            try:
                self._subscriptions.remove(subscription)
            except ValueError:
                # Already removed (idempotent cool, or never registered).
                pass

    def cool_all(self) -> None:
        """Unsubscribe every active subscription. Idempotent.

        Each subscription's teardown is wrapped in its own try/except
        so a single failed teardown doesn't block the others.
        """
        with self._lock:
            snapshot = list(self._subscriptions)
        for subscription in snapshot:
            try:
                self.cool(subscription)
            except Exception as exc:  # pragma: no cover - defensive
                logger.info(
                    "TopsEventBridge cool_all() error on %s: %r",
                    subscription.top_node_path,
                    exc,
                )

    # ── Introspection ──────────────────────────────────────────────

    def active_subscriptions(self) -> Tuple[Subscription, ...]:
        """Snapshot of currently-active subscriptions. Read-only."""
        with self._lock:
            return tuple(self._subscriptions)

    def dropped_event_count(self) -> int:
        """Count of events dropped at the bridge boundary.

        Drops happen when:
          - The user-supplied perception_callback raises an exception
            (bridge swallows so PDG cooks aren't disrupted)
          - The event payload could not be constructed (e.g. pdg
            attribute access raised)
        """
        with self._lock:
            return self._dropped

    # ── Internal — event handler factory ──────────────────────────

    def _make_event_handler(
        self,
        subscription_alive: List[bool],
        top_node_path: str,
    ) -> Any:
        """Build a ``pdg.PyEventHandler`` for one subscription.

        The closure captures ``subscription_alive`` and ``top_node_path``
        so the handler can early-return on cooled subscriptions and
        attribute the event to the right TOP network. R8 pattern at
        ``bridge.py:636``.
        """

        def on_pdg_event(event: Any) -> None:
            # Idempotency guard — drops events arriving after cool().
            if not subscription_alive[0]:
                return
            # Defense-in-depth filter (graph context shouldn't fire
            # unsubscribed types, but cheap to guard).
            try:
                event_type_int = int(event.type)
            except Exception:
                self._increment_dropped()
                return
            if event_type_int not in _SURFACED_EVENT_TYPES:
                return
            # Construct typed event (no hou.*; pdg.* only).
            try:
                tops_event = self._build_tops_event(
                    event, event_type_int, top_node_path
                )
            except Exception as exc:
                logger.debug(
                    "TopsEventBridge dropped event on %s: build raised %r",
                    top_node_path,
                    exc,
                )
                self._increment_dropped()
                return
            # Deliver to user callback. Swallow exceptions so PDG cook
            # is never disrupted by agent-side bugs.
            try:
                self._perception_callback(tops_event)
            except Exception as exc:
                logger.debug(
                    "TopsEventBridge dropped event on %s: callback raised %r",
                    top_node_path,
                    exc,
                )
                self._increment_dropped()

        return pdg.PyEventHandler(on_pdg_event)

    def _build_tops_event(
        self,
        event: Any,
        event_type_int: int,
        top_node_path: str,
    ) -> TopsEvent:
        """Construct a ``TopsEvent`` from a raw ``pdg.Event`` object.

        Reads ``pdg.*`` properties only — no ``hou.*`` calls — so safe
        to invoke from any thread.
        """
        event_name = _EVENT_NAME_BY_INT.get(
            event_type_int, f"tops.unknown.{event_type_int}"
        )
        timestamp = time.monotonic()
        # Cook-level events (no work-item payload): only error_message
        # is potentially populated.
        if event_type_int in {
            _EVT_COOK_START,
            _EVT_COOK_COMPLETE,
            _EVT_COOK_ERROR,
            _EVT_COOK_WARNING,
        }:
            error_message: Optional[str] = None
            if event_type_int in {_EVT_COOK_ERROR, _EVT_COOK_WARNING}:
                error_message = self._safe_str_attr(event, "message")
            return TopsEvent(
                event_type=event_name,
                pdg_event_type_int=event_type_int,
                top_node_path=top_node_path,
                timestamp=timestamp,
                error_message=error_message,
            )
        # Work-item events: drill into event.workItem for the typed
        # payload fields.
        work_item = getattr(event, "workItem", None)
        if work_item is None:
            return TopsEvent(
                event_type=event_name,
                pdg_event_type_int=event_type_int,
                top_node_path=top_node_path,
                timestamp=timestamp,
            )
        return TopsEvent(
            event_type=event_name,
            pdg_event_type_int=event_type_int,
            top_node_path=top_node_path,
            timestamp=timestamp,
            work_item_id=self._safe_int_attr(work_item, "id"),
            work_item_frame=self._safe_float_attr(work_item, "frame"),
            work_item_state=self._safe_str_attr(work_item, "state"),
            work_item_outputs=self._read_outputs(work_item),
            work_item_cook_duration_seconds=self._safe_float_attr(
                work_item, "cookDuration"
            ),
            node_path=self._read_node_path(work_item),
        )

    def _read_outputs(self, work_item: Any) -> Tuple[str, ...]:
        """Read ``expectedResultData`` outputs as a tuple of paths.

        Each element is expected to expose ``.path``. Defensive against
        missing attribute (single-element fallback to ``str()``).
        """
        try:
            results = work_item.expectedResultData
        except Exception:
            return ()
        outputs: List[str] = []
        try:
            for entry in results:
                path = getattr(entry, "path", None)
                if path is None:
                    path = str(entry)
                outputs.append(str(path))
        except TypeError:
            return ()
        return tuple(outputs)

    def _read_node_path(self, work_item: Any) -> Optional[str]:
        """Read ``work_item.node.path()`` defensively.

        Per Spike 3.0 audit, ``pdg.Node.path()`` was not directly
        introspected. Fallback chain: ``.path()`` → ``.name`` → None.
        Spike 3.3 integration confirms which accessor is canonical.
        """
        try:
            node = work_item.node
        except Exception:
            return None
        if node is None:
            return None
        path_attr = getattr(node, "path", None)
        if callable(path_attr):
            try:
                return str(path_attr())
            except Exception:
                pass
        name_attr = getattr(node, "name", None)
        if name_attr is not None:
            try:
                return str(name_attr() if callable(name_attr) else name_attr)
            except Exception:
                pass
        return None

    @staticmethod
    def _safe_int_attr(obj: Any, name: str) -> Optional[int]:
        try:
            value = getattr(obj, name, None)
            return int(value) if value is not None else None
        except Exception:
            return None

    @staticmethod
    def _safe_float_attr(obj: Any, name: str) -> Optional[float]:
        try:
            value = getattr(obj, name, None)
            return float(value) if value is not None else None
        except Exception:
            return None

    @staticmethod
    def _safe_str_attr(obj: Any, name: str) -> Optional[str]:
        try:
            value = getattr(obj, name, None)
            return str(value) if value is not None else None
        except Exception:
            return None

    def _increment_dropped(self) -> None:
        with self._lock:
            self._dropped += 1
            if self._dropped > self._max_dropped_log and self._dispatcher:
                # Cap noise: only log every Nth drop after the threshold.
                if self._dropped % self._max_dropped_log == 0:
                    log_dropped_event = getattr(
                        self._dispatcher, "log_dropped_event", None
                    )
                    if callable(log_dropped_event):
                        try:
                            log_dropped_event(
                                "tops.dropped",
                                f"count={self._dropped}",
                            )
                        except Exception:
                            pass

    @staticmethod
    def _resolve_event_type_enum(event_type_int: int) -> Any:
        """Map an audit-verified int back to its ``pdg.EventType`` enum.

        ``pdg.GraphContext.addEventHandler`` takes the enum value, not
        the int. We hold the int (audit-stable) and resolve to the enum
        at registration time.
        """
        if not _PDG_AVAILABLE:
            raise TopsBridgeError(
                "pdg module not available — cannot resolve EventType"
            )
        # pdg.EventType is iterable over its members; a plain int compare
        # picks out the matching enum value.
        event_type_cls = pdg.EventType
        for member in event_type_cls.__members__.values() if hasattr(
            event_type_cls, "__members__"
        ) else []:
            try:
                if int(member) == event_type_int:
                    return member
            except Exception:
                continue
        # Fallback: pybind11 enums often accept int construction.
        try:
            return event_type_cls(event_type_int)
        except Exception as exc:
            raise TopsBridgeError(
                f"Could not resolve pdg.EventType for int {event_type_int}: "
                f"{exc!r}"
            ) from exc


__all__ = [
    "TopsBridgeError",
    "TopsEvent",
    "Subscription",
    "TopsEventBridge",
]
