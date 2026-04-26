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

    def test_warm_without_pdg_raises_typed_error(self):
        # No fake_pdg fixture — _PDG_AVAILABLE is False at module load
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
    def test_warm_all_returns_empty_when_hou_unavailable(self, fake_pdg):
        # _HOU_AVAILABLE is False at module load
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
