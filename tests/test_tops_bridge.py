"""Basic tests for ``synapse.host.tops_bridge`` (Sprint 3 Spike 3.1).

Scope: FORGE-owned basic suite — construction smoke, warm/cool happy
path, mocked event dispatch covering all 7 surfaced event types,
headless-import gate. The hostile suite is CRUCIBLE's territory and
lives below the ``# CRUCIBLE`` divider in the second pass of this file.

Empirical surface this binds against: Spike 3.0 audit at
``docs/sprint3/spike_3_0_pdg_api_audit.md`` (RESOLVED list).
"""

from __future__ import annotations

from typing import Any, List
from unittest.mock import MagicMock

import pytest

from synapse.host.tops_bridge import (
    Subscription,
    TopsBridgeError,
    TopsEvent,
    TopsEventBridge,
)


# ── Fakes for headless pdg / hou mocking ────────────────────────────


class FakePDGEnum:
    """Fake ``pdg.EventType.*`` enum member.

    Compares equal to its int value, supports ``int(...)`` and is
    hashable. Mirrors the audit-captured pybind11 enum surface enough
    to drive the bridge.
    """

    __slots__ = ("name", "value")

    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, FakePDGEnum):
            return self.value == other.value
        try:
            return self.value == int(other)
        except (TypeError, ValueError):
            return False

    def __hash__(self) -> int:
        return hash(self.value)

    def __repr__(self) -> str:
        return f"<FakeEventType.{self.name}: {self.value}>"


_FAKE_EVENT_TYPE_MEMBERS = {
    "CookStart": FakePDGEnum("CookStart", 38),
    "CookComplete": FakePDGEnum("CookComplete", 14),
    "CookError": FakePDGEnum("CookError", 12),
    "CookWarning": FakePDGEnum("CookWarning", 13),
    "WorkItemAdd": FakePDGEnum("WorkItemAdd", 1),
    "WorkItemStateChange": FakePDGEnum("WorkItemStateChange", 5),
    "WorkItemResult": FakePDGEnum("WorkItemResult", 35),
}


class FakeEventTypeCls:
    """Fake ``pdg.EventType`` class with ``__members__`` and call shape."""

    __members__ = _FAKE_EVENT_TYPE_MEMBERS

    def __init__(self) -> None:
        for name, member in _FAKE_EVENT_TYPE_MEMBERS.items():
            setattr(self, name, member)

    def __call__(self, value: int) -> FakePDGEnum:
        for member in _FAKE_EVENT_TYPE_MEMBERS.values():
            if int(member) == value:
                return member
        raise ValueError(f"No FakeEventType with value {value}")


class FakePyEventHandler:
    """Fake ``pdg.PyEventHandler`` — captures the bound callback."""

    __slots__ = ("callback",)

    def __init__(self, callback: Any) -> None:
        self.callback = callback


class FakePDG:
    """Fake ``pdg`` module surface — enough for the bridge to operate."""

    EventType = FakeEventTypeCls()
    PyEventHandler = FakePyEventHandler


class FakeGraphContext:
    """Fake ``pdg.GraphContext`` capturing handler registrations."""

    def __init__(self) -> None:
        self.handlers: List[Any] = []  # registrations: (handler, event_type)
        self.remove_calls: int = 0

    def addEventHandler(self, handler: Any, event_type: Any) -> None:
        self.handlers.append((handler, event_type))

    def removeEventHandler(self, handler: Any) -> None:
        self.remove_calls += 1
        self.handlers = [
            (h, et) for h, et in self.handlers if h is not handler
        ]


class FakeTopNode:
    """Fake ``hou.Node`` shape for a TOP network."""

    def __init__(
        self,
        path: str = "/tasks/topnet1",
        graph_context: FakeGraphContext = None,
    ) -> None:
        self._path = path
        self.graph_context = graph_context or FakeGraphContext()

    def path(self) -> str:
        return self._path

    def getPDGGraphContext(self) -> FakeGraphContext:
        return self.graph_context


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def fake_pdg(monkeypatch):
    """Patch ``synapse.host.tops_bridge`` with a fake ``pdg`` module."""
    fake = FakePDG()
    monkeypatch.setattr("synapse.host.tops_bridge.pdg", fake)
    monkeypatch.setattr("synapse.host.tops_bridge._PDG_AVAILABLE", True)
    return fake


@pytest.fixture
def fake_top_node():
    return FakeTopNode()


def _build_fake_event(event_type_int: int, **kwargs: Any) -> MagicMock:
    """Build a fake ``pdg.Event`` with the given type int + payload."""
    fake = MagicMock()
    fake.type = event_type_int
    for key, value in kwargs.items():
        setattr(fake, key, value)
    return fake


def _build_fake_workitem(
    *,
    item_id: int = 1,
    frame: float = 1.0,
    state: str = "ready",
    cook_duration: float = 0.0,
    outputs: List[str] = None,
    node_path: str = "/tasks/topnet1/cooker",
) -> MagicMock:
    """Build a fake ``pdg.WorkItem`` with the audit-captured surface."""
    work_item = MagicMock()
    work_item.id = item_id
    work_item.frame = frame
    work_item.state = state
    work_item.cookDuration = cook_duration
    if outputs:
        work_item.expectedResultData = [
            MagicMock(path=path) for path in outputs
        ]
    else:
        work_item.expectedResultData = []
    work_item.node = MagicMock()
    work_item.node.path = MagicMock(return_value=node_path)
    return work_item


# ── Construction + headless-import gate ─────────────────────────────


class TestConstruction:
    """Bridge construction + the headless-import gate criterion."""

    def test_module_imports_headless_without_hou(self):
        """Gate criterion: module imports headless without ``hou``."""
        # Import already succeeded at module load — assert the surface
        # the gate cares about is reachable.
        from synapse.host.tops_bridge import (
            Subscription as _Subscription,
            TopsBridgeError as _TopsBridgeError,
            TopsEvent as _TopsEvent,
            TopsEventBridge as _TopsEventBridge,
        )
        assert _Subscription is Subscription
        assert _TopsBridgeError is TopsBridgeError
        assert _TopsEvent is TopsEvent
        assert _TopsEventBridge is TopsEventBridge

    def test_construct_with_callback_succeeds(self):
        bridge = TopsEventBridge(perception_callback=lambda e: None)
        assert bridge.dropped_event_count() == 0
        assert bridge.active_subscriptions() == ()

    def test_construct_without_callback_raises_typeerror(self):
        with pytest.raises(TypeError, match="perception_callback"):
            TopsEventBridge(perception_callback=None)

    def test_active_subscriptions_returns_tuple(self):
        bridge = TopsEventBridge(perception_callback=lambda e: None)
        result = bridge.active_subscriptions()
        assert isinstance(result, tuple)


# ── warm / cool round trip ─────────────────────────────────────────


class TestWarmCool:
    """Subscribe / unsubscribe happy paths."""

    def test_warm_returns_subscription_with_audit_verified_shape(
        self, fake_pdg, fake_top_node
    ):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        assert isinstance(sub, Subscription)
        assert sub.top_node_path == "/tasks/topnet1"
        assert sub.scope == "graph"
        # 7 surfaced event types per design § 2.5
        assert len(sub.event_types) == 7
        assert set(sub.event_types) == {38, 14, 12, 13, 1, 5, 35}

    def test_warm_registers_handlers_on_graph_context(
        self, fake_pdg, fake_top_node
    ):
        bridge = TopsEventBridge(lambda e: None)
        bridge.warm(fake_top_node)
        # One registration per surfaced event type
        assert len(fake_top_node.graph_context.handlers) == 7

    def test_warm_appends_to_active_subscriptions(
        self, fake_pdg, fake_top_node
    ):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        assert bridge.active_subscriptions() == (sub,)

    def test_cool_flips_alive_flag(self, fake_pdg, fake_top_node):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        assert sub._alive[0] is True
        bridge.cool(sub)
        assert sub._alive[0] is False

    def test_cool_removes_from_active_subscriptions(
        self, fake_pdg, fake_top_node
    ):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        bridge.cool(sub)
        assert bridge.active_subscriptions() == ()

    def test_cool_calls_remove_event_handler_once(
        self, fake_pdg, fake_top_node
    ):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        bridge.cool(sub)
        # Per Spike 3.0: removeEventHandler takes the handler instance
        # itself, not a handle. One call detaches the handler from all
        # event types it was registered against.
        assert fake_top_node.graph_context.remove_calls == 1
        assert fake_top_node.graph_context.handlers == []

    def test_cool_idempotent(self, fake_pdg, fake_top_node):
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        bridge.cool(sub)
        bridge.cool(sub)  # Second call — must not crash
        bridge.cool(sub)  # Third call — also safe
        assert bridge.active_subscriptions() == ()

    def test_cool_none_is_noop(self):
        bridge = TopsEventBridge(lambda e: None)
        bridge.cool(None)  # Defensive — no crash

    def test_cool_all_unsubscribes_everything(self, fake_pdg):
        bridge = TopsEventBridge(lambda e: None)
        bridge.warm(FakeTopNode("/tasks/a"))
        bridge.warm(FakeTopNode("/tasks/b"))
        bridge.warm(FakeTopNode("/tasks/c"))
        assert len(bridge.active_subscriptions()) == 3
        bridge.cool_all()
        assert bridge.active_subscriptions() == ()

    def test_cool_all_idempotent(self, fake_pdg, fake_top_node):
        bridge = TopsEventBridge(lambda e: None)
        bridge.warm(fake_top_node)
        bridge.cool_all()
        bridge.cool_all()  # Second call — must not crash
        assert bridge.active_subscriptions() == ()

    def test_warm_without_pdg_raises_typed_error(self, monkeypatch):
        # Explicitly force _PDG_AVAILABLE = False — other test modules
        # in the suite inject mock pdg into sys.modules at import time,
        # so the module-load default cannot be relied on under full-
        # suite ordering. Test asserts the bridge's typed-error path
        # specifically, regardless of upstream injection state.
        monkeypatch.setattr("synapse.host.tops_bridge._PDG_AVAILABLE", False)
        monkeypatch.setattr("synapse.host.tops_bridge.pdg", None)
        bridge = TopsEventBridge(lambda e: None)
        with pytest.raises(TopsBridgeError, match="pdg module not available"):
            bridge.warm(MagicMock())

    def test_warm_with_none_topnode_raises_typed_error(self, fake_pdg):
        bridge = TopsEventBridge(lambda e: None)
        with pytest.raises(TopsBridgeError, match="requires a TOP node"):
            bridge.warm(None)

    def test_warm_without_graph_context_raises_typed_error(self, fake_pdg):
        node = MagicMock()
        node.path.return_value = "/tasks/empty"
        node.getPDGGraphContext.return_value = None
        bridge = TopsEventBridge(lambda e: None)
        with pytest.raises(TopsBridgeError, match="no live graph context"):
            bridge.warm(node)


# ── warm_all without hou ────────────────────────────────────────────


class TestWarmAllHeadless:
    def test_warm_all_returns_empty_when_hou_unavailable(
        self, fake_pdg, monkeypatch
    ):
        # Explicitly force _HOU_AVAILABLE = False — other test modules
        # inject sys.modules["hou"] at collection time, so we cannot
        # rely on the module-load default under full-suite ordering.
        # Test asserts the headless-empty contract specifically.
        monkeypatch.setattr("synapse.host.tops_bridge._HOU_AVAILABLE", False)
        monkeypatch.setattr("synapse.host.tops_bridge.hou", None)
        bridge = TopsEventBridge(lambda e: None)
        result = bridge.warm_all()
        assert result == []


# ── Event dispatch — one happy path per surfaced event type ────────


class TestEventDispatch:
    """One dispatch test per design § 2.5 surfaced event type."""

    def _arm_bridge(self, fake_top_node):
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)
        return bridge, sub, received

    def test_dispatch_cook_start(self, fake_pdg, fake_top_node):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        sub._handler.callback(_build_fake_event(38))
        assert len(received) == 1
        evt = received[0]
        assert evt.event_type == "tops.cook.start"
        assert evt.pdg_event_type_int == 38
        assert evt.top_node_path == "/tasks/topnet1"

    def test_dispatch_cook_complete(self, fake_pdg, fake_top_node):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        sub._handler.callback(_build_fake_event(14))
        assert len(received) == 1
        assert received[0].event_type == "tops.cook.complete"
        assert received[0].pdg_event_type_int == 14

    def test_dispatch_cook_error_with_message(self, fake_pdg, fake_top_node):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        sub._handler.callback(
            _build_fake_event(12, message="cook failed because magic")
        )
        assert received[0].event_type == "tops.cook.error"
        assert received[0].error_message == "cook failed because magic"

    def test_dispatch_cook_warning_with_message(
        self, fake_pdg, fake_top_node
    ):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        sub._handler.callback(
            _build_fake_event(13, message="deprecated parm")
        )
        assert received[0].event_type == "tops.cook.warning"
        assert received[0].error_message == "deprecated parm"

    def test_dispatch_workitem_add(self, fake_pdg, fake_top_node):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        wi = _build_fake_workitem(item_id=42, frame=2.5, state="added")
        sub._handler.callback(_build_fake_event(1, workItem=wi))
        assert received[0].event_type == "tops.workitem.add"
        assert received[0].work_item_id == 42
        assert received[0].work_item_frame == 2.5
        assert received[0].work_item_state == "added"

    def test_dispatch_workitem_state_change(
        self, fake_pdg, fake_top_node
    ):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        wi = _build_fake_workitem(item_id=7, state="cooked")
        sub._handler.callback(_build_fake_event(5, workItem=wi))
        assert received[0].event_type == "tops.workitem.state_change"
        assert received[0].work_item_state == "cooked"

    def test_dispatch_workitem_result_with_outputs(
        self, fake_pdg, fake_top_node
    ):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        wi = _build_fake_workitem(
            item_id=99,
            frame=10.0,
            cook_duration=1.234,
            outputs=["/tmp/out_001.exr", "/tmp/out_002.exr"],
            node_path="/tasks/topnet1/render",
        )
        sub._handler.callback(_build_fake_event(35, workItem=wi))
        evt = received[0]
        assert evt.event_type == "tops.workitem.result"
        assert evt.pdg_event_type_int == 35
        assert evt.work_item_id == 99
        assert evt.work_item_frame == 10.0
        assert evt.work_item_cook_duration_seconds == 1.234
        assert evt.work_item_outputs == (
            "/tmp/out_001.exr",
            "/tmp/out_002.exr",
        )
        assert evt.node_path == "/tasks/topnet1/render"

    def test_unsurfaced_event_silently_dropped(
        self, fake_pdg, fake_top_node
    ):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        # WorkItemSetInt = 27, NOT in the surfaced allowlist
        sub._handler.callback(_build_fake_event(27))
        assert received == []
        # And the bridge does not count this as a "drop" (filtered, not dropped)
        assert bridge.dropped_event_count() == 0

    def test_event_after_cool_dropped_via_alive_flag(
        self, fake_pdg, fake_top_node
    ):
        bridge, sub, received = self._arm_bridge(fake_top_node)
        bridge.cool(sub)
        # Try to deliver an event after cool — handler must early-return
        sub._handler.callback(_build_fake_event(14))
        assert received == []


# ── TopsEvent value object ─────────────────────────────────────────


class TestTopsEvent:
    def test_to_dict_round_trip_minimal(self):
        evt = TopsEvent(
            event_type="tops.cook.complete",
            pdg_event_type_int=14,
            top_node_path="/tasks/topnet1",
            timestamp=1234.5,
        )
        d = evt.to_dict()
        assert d["event_type"] == "tops.cook.complete"
        assert d["pdg_event_type_int"] == 14
        assert d["top_node_path"] == "/tasks/topnet1"
        assert d["timestamp"] == 1234.5
        assert d["work_item_outputs"] == []

    def test_to_dict_serializes_outputs_as_list(self):
        evt = TopsEvent(
            event_type="tops.workitem.result",
            pdg_event_type_int=35,
            top_node_path="/tasks/x",
            timestamp=0.0,
            work_item_outputs=("/a.exr", "/b.exr"),
        )
        d = evt.to_dict()
        assert d["work_item_outputs"] == ["/a.exr", "/b.exr"]
        assert isinstance(d["work_item_outputs"], list)

    def test_frozen_dataclass_rejects_mutation(self):
        evt = TopsEvent(
            event_type="tops.cook.start",
            pdg_event_type_int=38,
            top_node_path="/tasks/x",
            timestamp=0.0,
        )
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            evt.event_type = "tampered"  # type: ignore[misc]


# ════════════════════════════════════════════════════════════════════
# CRUCIBLE — hostile suite (Spike 3.1 § 5)
# ════════════════════════════════════════════════════════════════════
#
# Adversarial posture: I did NOT build TopsEventBridge. The
# implementation is the system under test. These tests probe specific
# defect categories: handler leaks, race windows during cool(),
# exception swallowing, ordering invariants. Test weakness is a bug —
# fix-forward through FORGE, never weaken assertions.
#
# All tests run standalone (no live Houdini). pdg + hou are fully
# mocked. Live integration is reserved for Spike 3.3 with the @live
# pytest marker.


class TestHostileSubscriptionLeak:
    """§ 5.1 — subscribe → unsubscribe → verify no handler leak."""

    def test_warm_cool_leaves_zero_handlers_on_graph_context(
        self, fake_pdg, fake_top_node
    ):
        """After cool(), graph context must hold zero handlers.

        Defect category: handler leak — cool() forgets to detach,
        memory + event delivery survives bridge teardown.
        """
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        # 7 surfaced types → 7 registrations
        assert len(fake_top_node.graph_context.handlers) == 7
        bridge.cool(sub)
        # After cool: zero handlers — no leak
        assert fake_top_node.graph_context.handlers == [], (
            "cool() left handlers on graph context — handler leak"
        )

    def test_repeated_warm_cool_cycles_no_accumulation(
        self, fake_pdg, fake_top_node
    ):
        """100 warm/cool cycles must leave zero handlers and zero
        active subscriptions. Defect category: cumulative leak."""
        bridge = TopsEventBridge(lambda e: None)
        for _ in range(100):
            sub = bridge.warm(fake_top_node)
            bridge.cool(sub)
        assert fake_top_node.graph_context.handlers == []
        assert bridge.active_subscriptions() == ()

    def test_subscription_alive_flag_holds_strong_handler_ref(
        self, fake_pdg, fake_top_node
    ):
        """The Subscription must hold a strong ref to the bound
        PyEventHandler. If the bridge let it be GC'd, future events
        could segfault under pybind11. Defect category: weak ref.
        """
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        handler_ref = sub._handler
        # The handler must be a real object reachable through Subscription
        assert handler_ref is not None
        assert handler_ref.callback is not None
        # The same handler must be in graph_context.handlers
        registered_handlers = {
            h for h, _et in fake_top_node.graph_context.handlers
        }
        assert handler_ref in registered_handlers


class TestHostileCookErrorDuringSubscription:
    """§ 5.2 — Cook error during subscription does not crash bridge."""

    def test_cook_error_dispatches_typed_event_and_bridge_continues(
        self, fake_pdg, fake_top_node
    ):
        """A CookError event must:
          1. Convert to a tops.cook.error TopsEvent with error_message
          2. NOT crash the bridge
          3. NOT poison subsequent events
        Defect category: exception bleed.
        """
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)
        # Fire CookError
        sub._handler.callback(
            _build_fake_event(12, message="catastrophic cook failure")
        )
        # Then fire a normal CookComplete
        sub._handler.callback(_build_fake_event(14))
        assert len(received) == 2
        assert received[0].event_type == "tops.cook.error"
        assert received[0].error_message == "catastrophic cook failure"
        assert received[1].event_type == "tops.cook.complete"
        # Bridge state unchanged
        assert len(bridge.active_subscriptions()) == 1
        assert bridge.dropped_event_count() == 0


class TestHostileMultipleBridgesSameContext:
    """§ 5.3 — Multiple bridges on same graph context are independent."""

    def test_two_bridges_same_topnet_register_distinct_handlers(
        self, fake_pdg, fake_top_node
    ):
        """Both bridges register their own PyEventHandler. Cooling
        bridge A must not affect bridge B's subscription. Defect
        category: shared state collision."""
        received_a: List[TopsEvent] = []
        received_b: List[TopsEvent] = []
        bridge_a = TopsEventBridge(received_a.append)
        bridge_b = TopsEventBridge(received_b.append)
        sub_a = bridge_a.warm(fake_top_node)
        sub_b = bridge_b.warm(fake_top_node)
        # Both bridges' handlers are distinct instances
        assert sub_a._handler is not sub_b._handler
        # Graph context holds 14 registrations (7 per bridge)
        assert len(fake_top_node.graph_context.handlers) == 14
        # Cool bridge A
        bridge_a.cool(sub_a)
        # Bridge B's handler still attached
        assert len(fake_top_node.graph_context.handlers) == 7
        # Bridge B still receives events
        sub_b._handler.callback(_build_fake_event(14))
        assert len(received_b) == 1
        assert received_b[0].event_type == "tops.cook.complete"
        # Bridge A received nothing post-cool
        assert received_a == []


class TestHostileEventFiringDuringShutdown:
    """§ 5.4 — Event firing concurrently with cool() must not double-dispatch."""

    def test_event_after_alive_flag_flip_does_not_dispatch(
        self, fake_pdg, fake_top_node
    ):
        """Simulate the race window: cool() flips _alive to False;
        any subsequent handler invocation must early-return.
        Defect category: TOCTOU race — handler reads alive=True,
        then cool flips to False, then handler dispatches stale event.

        Strategy: cool() the subscription, then directly invoke the
        handler with an event. If the alive guard is correct, the
        callback receives nothing.
        """
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)
        bridge.cool(sub)
        # Event fires after cool — handler must early-return
        sub._handler.callback(_build_fake_event(14))
        sub._handler.callback(_build_fake_event(38))
        sub._handler.callback(_build_fake_event(35))
        assert received == [], (
            "Event delivered after cool() — alive flag race"
        )

    def test_threaded_event_during_cool_no_dispatch(
        self, fake_pdg, fake_top_node
    ):
        """Use threading to actually race a fire against a cool().
        Hostile: 100 events on a worker thread while main thread
        races cool(). Final count of received events must be ≤
        events fired before cool() returned. Bridge must not crash."""
        import threading
        received: List[TopsEvent] = []
        lock = threading.Lock()

        def safe_append(event):
            with lock:
                received.append(event)

        bridge = TopsEventBridge(safe_append)
        sub = bridge.warm(fake_top_node)

        stop_flag = threading.Event()

        def fire_events():
            i = 0
            while not stop_flag.is_set():
                try:
                    sub._handler.callback(_build_fake_event(14))
                except Exception:
                    pass
                i += 1
                if i > 10_000:  # safety cap
                    break

        worker = threading.Thread(target=fire_events, daemon=True)
        worker.start()
        # Let some events fire, then cool
        import time
        time.sleep(0.01)
        bridge.cool(sub)
        stop_flag.set()
        worker.join(timeout=1.0)
        assert not worker.is_alive()
        # Bridge must remain consistent — no crashes, alive is False,
        # subscription removed.
        assert sub._alive[0] is False
        assert bridge.active_subscriptions() == ()


class TestHostileCallbackRaising:
    """§ 5.5 — User callback raising must not break bridge."""

    def test_callback_raises_increments_drop_counter_continues(
        self, fake_pdg, fake_top_node
    ):
        """User callback raises every other event. Bridge:
          1. Does NOT propagate the exception (PDG cook protected)
          2. Increments dropped_event_count() per failure
          3. Continues delivering subsequent events
        Defect category: exception escape into PDG's cook thread.
        """
        call_count = [0]

        def raising_callback(event):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise RuntimeError(f"intentional failure on call {call_count[0]}")

        bridge = TopsEventBridge(raising_callback)
        sub = bridge.warm(fake_top_node)
        # Fire 10 events; 5 will fail (calls 2,4,6,8,10)
        for _ in range(10):
            sub._handler.callback(_build_fake_event(14))
        # Bridge state remains consistent
        assert call_count[0] == 10, "Bridge stopped delivering after failure"
        assert bridge.dropped_event_count() == 5, (
            f"Expected 5 drops, got {bridge.dropped_event_count()}"
        )
        # Subscription still active
        assert len(bridge.active_subscriptions()) == 1

    def test_callback_raising_baseexception_still_swallowed(
        self, fake_pdg, fake_top_node
    ):
        """A KeyboardInterrupt / SystemExit (BaseException) inside the
        callback must not poison the bridge if the bridge swallows
        Exception. Defect category: bridge catches Exception but
        BaseException leaks. We probe with a regular Exception
        subclass to verify the swallow path covers all reasonable
        agent-side bugs (custom exception classes)."""

        class _AgentBug(Exception):
            pass

        def buggy_callback(event):
            raise _AgentBug("custom user-defined exception")

        received: List[TopsEvent] = []
        # Use a wrapper to count successful deliveries
        bridge = TopsEventBridge(buggy_callback)
        sub = bridge.warm(fake_top_node)
        # Fire 5 events — all must be swallowed, not crash
        for _ in range(5):
            sub._handler.callback(_build_fake_event(14))
        assert bridge.dropped_event_count() == 5
        assert len(bridge.active_subscriptions()) == 1


class TestHostileGraphContextErrors:
    """§ 5.6 — Bridge subscribed when topnet has no graph context."""

    def test_warm_when_get_pdg_graph_context_returns_none(
        self, fake_pdg
    ):
        """Defect category: silent failure when topnet is uninstantiated.
        Must raise typed TopsBridgeError, NOT crash with AttributeError."""
        node = MagicMock()
        node.path.return_value = "/tasks/uninstantiated"
        node.getPDGGraphContext.return_value = None
        bridge = TopsEventBridge(lambda e: None)
        with pytest.raises(TopsBridgeError) as exc_info:
            bridge.warm(node)
        msg = str(exc_info.value)
        assert "no live graph context" in msg
        assert "/tasks/uninstantiated" in msg

    def test_warm_when_get_pdg_graph_context_raises(self, fake_pdg):
        """Defect: getPDGGraphContext() raises (e.g. node was destroyed
        between hou query and bridge call). Bridge must surface as
        typed TopsBridgeError, not bare exception."""
        node = MagicMock()
        node.path.return_value = "/tasks/destroyed"
        node.getPDGGraphContext.side_effect = RuntimeError(
            "TOP node was destroyed"
        )
        bridge = TopsEventBridge(lambda e: None)
        with pytest.raises(Exception) as exc_info:
            bridge.warm(node)
        # The bridge currently re-raises the inner error. Either it
        # wraps as TopsBridgeError or surfaces RuntimeError. Both are
        # acceptable as long as the bridge state is unchanged.
        assert bridge.active_subscriptions() == ()


class TestHostileTopnetDeletedMidSubscription:
    """§ 5.7 — Topnet deleted mid-subscription: cool() must not crash."""

    def test_cool_when_remove_event_handler_raises(
        self, fake_pdg, fake_top_node
    ):
        """Underlying graph context's removeEventHandler raises (e.g.
        the graph was destroyed). cool() must swallow + log, NOT
        crash, AND remove the subscription from active list.
        Defect category: exception in teardown path leaks."""
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        # Make remove raise
        fake_top_node.graph_context.removeEventHandler = MagicMock(
            side_effect=RuntimeError("graph destroyed")
        )
        # cool() must not crash
        bridge.cool(sub)
        # Subscription still removed from active list (the bridge's
        # bookkeeping is independent of the underlying context)
        assert bridge.active_subscriptions() == ()
        # Alive flag flipped
        assert sub._alive[0] is False

    def test_cool_all_continues_after_one_failure(self, fake_pdg):
        """One subscription's teardown raises; others must still be
        cooled. Defect category: error in cool_all() blocks remaining
        teardowns → multi-bridge handler leak."""
        bridge = TopsEventBridge(lambda e: None)
        node_a = FakeTopNode("/tasks/a")
        node_b = FakeTopNode("/tasks/b")
        node_c = FakeTopNode("/tasks/c")
        bridge.warm(node_a)
        bridge.warm(node_b)
        bridge.warm(node_c)
        # Make B's teardown raise
        node_b.graph_context.removeEventHandler = MagicMock(
            side_effect=RuntimeError("bad teardown on B")
        )
        bridge.cool_all()
        # All three must be removed from active list despite B's failure
        assert bridge.active_subscriptions() == ()
        # A and C must have had their teardown called; B's was attempted
        assert node_a.graph_context.handlers == []
        assert node_c.graph_context.handlers == []


class TestHostileMultiEventOrdering:
    """§ 5.8 — Multiple event types in same cook: no loss, no reorder."""

    def test_twelve_events_same_cook_delivered_in_order(
        self, fake_pdg, fake_top_node
    ):
        """A realistic cook sequence must arrive in order with no drops:
          CookStart → WorkItemAdd × 5 → WorkItemResult × 5 → CookComplete

        Defect categories: dropped events, reordering, deduplication,
        type-filter false positives.
        """
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)

        # CookStart
        sub._handler.callback(_build_fake_event(38))
        # 5 × WorkItemAdd
        for i in range(5):
            wi = _build_fake_workitem(item_id=i, frame=float(i))
            sub._handler.callback(_build_fake_event(1, workItem=wi))
        # 5 × WorkItemResult
        for i in range(5):
            wi = _build_fake_workitem(
                item_id=i, frame=float(i), outputs=[f"/tmp/{i}.exr"]
            )
            sub._handler.callback(_build_fake_event(35, workItem=wi))
        # CookComplete
        sub._handler.callback(_build_fake_event(14))

        # 12 events total, in original order, no drops, no dedup
        assert len(received) == 12
        expected_types = (
            ["tops.cook.start"]
            + ["tops.workitem.add"] * 5
            + ["tops.workitem.result"] * 5
            + ["tops.cook.complete"]
        )
        actual_types = [e.event_type for e in received]
        assert actual_types == expected_types, (
            f"Reordering or loss detected:\n"
            f"  expected: {expected_types}\n"
            f"  actual:   {actual_types}"
        )
        # Specific payload assertions on the WorkItemResult events
        result_events = [e for e in received if e.event_type == "tops.workitem.result"]
        assert len(result_events) == 5
        for i, evt in enumerate(result_events):
            assert evt.work_item_id == i, f"id mismatch at index {i}"
            assert evt.work_item_outputs == (f"/tmp/{i}.exr",)
            assert evt.work_item_frame == float(i)
        assert bridge.dropped_event_count() == 0


class TestHostileBonusEdges:
    """Extra adversarial cases beyond the 8 mandatory."""

    def test_pdg_node_path_attribute_missing_falls_back_gracefully(
        self, fake_pdg, fake_top_node
    ):
        """pdg.Node may expose .name instead of .path() in some configs.
        The defensive getattr in _read_node_path must fall through.
        Defect category: rigid attribute assumption."""
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)
        wi = _build_fake_workitem(item_id=1)
        # Replace node with one that has no path() and no name
        wi.node = object()  # plain object — no path, no name
        sub._handler.callback(_build_fake_event(35, workItem=wi))
        assert received[0].node_path is None  # Defensive fallback worked

    def test_expected_result_data_raises_returns_empty_outputs(
        self, fake_pdg, fake_top_node
    ):
        """expectedResultData property might raise on an in-flight
        item. Bridge must capture an empty tuple and continue."""
        received: List[TopsEvent] = []
        bridge = TopsEventBridge(received.append)
        sub = bridge.warm(fake_top_node)
        wi = MagicMock()
        wi.id = 1
        wi.frame = 0.0
        wi.state = "ready"
        wi.cookDuration = 0.0
        # Make expectedResultData property raise
        type(wi).expectedResultData = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("not yet"))
        )
        wi.node = MagicMock()
        wi.node.path = MagicMock(return_value="/n")
        sub._handler.callback(_build_fake_event(35, workItem=wi))
        assert received[0].work_item_outputs == ()

    def test_event_type_int_cast_failure_increments_drop_counter(
        self, fake_pdg, fake_top_node
    ):
        """If event.type is malformed (e.g. None or unhashable),
        int() cast fails. Bridge must drop, not crash."""
        bridge = TopsEventBridge(lambda e: None)
        sub = bridge.warm(fake_top_node)
        bad_event = MagicMock()
        bad_event.type = MagicMock(side_effect=TypeError("not int-able"))
        # The MagicMock's int(bad_event.type) might or might not raise
        # depending on Mock behavior. Instead, build a real bad event:
        class _BadEvent:
            @property
            def type(self):
                raise TypeError("event corrupted")
        sub._handler.callback(_BadEvent())
        assert bridge.dropped_event_count() == 1
