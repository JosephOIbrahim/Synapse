"""Tests for ``synapse.host.scene_load_bridge`` (Sprint 3 Spike 3.2).

Layout mirrors Spike 3.1's ``test_tops_bridge.py``:

  - Top half (this section): FORGE-owned basic suite — construction,
    subscribe/unsubscribe round-trip, AfterLoad fires warm path,
    AfterClear filtered out, hou-unavailable raises.
  - Below the ``# CRUCIBLE`` divider: hostile suite — adversarial
    scenarios per design § 5 (added by CRUCIBLE in the second pass).

Empirical surface this binds against: Mile 4 audit at
``docs/sprint3/spike_3_2_scene_load_audit.md`` (RESOLVED list).
Composition target: TopsEventBridge from
``python/synapse/host/tops_bridge.py``.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock

import pytest

from synapse.host.scene_load_bridge import (
    SceneLoadBridge,
    SceneLoadBridgeError,
)
from synapse.host.tops_bridge import (
    Subscription,
    TopsBridgeError,
    TopsEvent,
    TopsEventBridge,
)


# ── Fakes for headless hou / pdg mocking ────────────────────────────


class FakeHipFileEnum:
    """Fake ``hou.hipFileEventType.*`` enum member.

    Matches Mile 4 audit § 2.1: members are ``EnumValue`` instances
    compared by identity (handler does ``event_type != AfterLoad``).
    Uses Python identity equality — distinct instances are not equal.
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"<FakeHipFileEventType.{self.name}>"


class FakeHipFileEventTypeCls:
    """Fake ``hou.hipFileEventType`` class with the four event members."""

    def __init__(self) -> None:
        self.BeforeLoad = FakeHipFileEnum("BeforeLoad")
        self.BeforeClear = FakeHipFileEnum("BeforeClear")
        self.AfterClear = FakeHipFileEnum("AfterClear")
        self.AfterLoad = FakeHipFileEnum("AfterLoad")
        self.BeforeMerge = FakeHipFileEnum("BeforeMerge")
        self.AfterMerge = FakeHipFileEnum("AfterMerge")
        self.BeforeSave = FakeHipFileEnum("BeforeSave")
        self.AfterSave = FakeHipFileEnum("AfterSave")


class FakeHipFile:
    """Fake ``hou.hipFile`` namespace.

    Captures registered callbacks so tests can fire events
    synchronously and assert add/remove behavior. The audit-captured
    ``addEventCallback`` returns ``None``; ``removeEventCallback``
    matches by callback-identity.
    """

    def __init__(self) -> None:
        self.callbacks: List[Callable[[Any], None]] = []
        self.add_calls: int = 0
        self.remove_calls: int = 0

    def addEventCallback(self, callback: Callable[[Any], None]) -> None:
        self.add_calls += 1
        self.callbacks.append(callback)
        # Audit § 1.2: returns None.

    def removeEventCallback(self, callback: Callable[[Any], None]) -> None:
        self.remove_calls += 1
        # Audit § 4.1: identity-based. FIFO removes first matching.
        for idx, registered in enumerate(self.callbacks):
            if registered is callback:
                del self.callbacks[idx]
                return
        raise ValueError("callback not registered")

    def fire(self, event_type: Any) -> None:
        """Synthesize a hipFile event — fires every registered callback.

        Iterate a snapshot so callbacks that mutate the list (e.g.
        unsubscribe-mid-handler hostile cases) don't trip iteration.
        """
        for callback in list(self.callbacks):
            callback(event_type)


# ── Fake hou.Node walk surface ──────────────────────────────────────


class FakeNodeTypeCategory:
    """Fake ``hou.NodeTypeCategory`` instance.

    Identity-comparable so ``node.type().category() != topnet_category``
    discriminates topnets from other nodes (matches the
    ``TopsEventBridge.warm_all`` filter at ``tops_bridge.py:350``).
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name


class FakeNodeType:
    """Fake ``hou.NodeType``."""

    __slots__ = ("_category",)

    def __init__(self, category: FakeNodeTypeCategory) -> None:
        self._category = category

    def category(self) -> FakeNodeTypeCategory:
        return self._category


class FakeGraphContext:
    """Fake ``pdg.GraphContext`` capturing handler registrations.

    Same shape as the FakePDG fixture in ``test_tops_bridge.py`` —
    counts addEventHandler / removeEventHandler calls so tests can
    assert per-topnet warm/cool behavior.
    """

    def __init__(self) -> None:
        self.handlers: List[Any] = []
        self.remove_calls: int = 0

    def addEventHandler(self, handler: Any, event_type: Any) -> None:
        self.handlers.append((handler, event_type))

    def removeEventHandler(self, handler: Any) -> None:
        self.remove_calls += 1
        self.handlers = [
            (h, et) for h, et in self.handlers if h is not handler
        ]


class FakeTopNode:
    """Fake ``hou.Node`` shape for a TOP network.

    ``type().category()`` returns the topnet category (so
    ``warm_all``'s filter accepts it). ``getPDGGraphContext()`` returns
    a fresh ``FakeGraphContext`` — or ``None`` if the test wants to
    simulate an uninstantiated network.
    """

    def __init__(
        self,
        path: str,
        category: FakeNodeTypeCategory,
        graph_context: Optional[FakeGraphContext] = None,
        no_graph: bool = False,
    ) -> None:
        self._path = path
        self._type = FakeNodeType(category)
        self.graph_context = graph_context or FakeGraphContext()
        self._no_graph = no_graph

    def path(self) -> str:
        return self._path

    def type(self) -> FakeNodeType:
        return self._type

    def getPDGGraphContext(self) -> Optional[FakeGraphContext]:
        if self._no_graph:
            return None
        return self.graph_context


class FakeNonTopNode:
    """Fake ``hou.Node`` whose category is NOT the topnet category.

    Used to verify the ``warm_all`` walk filters out non-topnets.
    """

    def __init__(self, path: str, non_topnet_category: FakeNodeTypeCategory) -> None:
        self._path = path
        self._type = FakeNodeType(non_topnet_category)

    def path(self) -> str:
        return self._path

    def type(self) -> FakeNodeType:
        return self._type


class FakeRootNode:
    """Fake ``hou.node('/')``. Returns the test-provided node list."""

    def __init__(self, children: List[Any]) -> None:
        self._children = children

    def allSubChildren(self) -> List[Any]:
        return list(self._children)


class FakeHou:
    """Fake ``hou`` module — namespace for hipFile + node walk + topnet category.

    Constructed per-test with a FakeHipFile, a list of nodes for the
    walk, and a topnet category instance. Tests fire hipFile events via
    ``self.hipFile.fire(...)``.
    """

    def __init__(
        self,
        hip_file: FakeHipFile,
        topnet_category: FakeNodeTypeCategory,
        children: Optional[List[Any]] = None,
    ) -> None:
        self.hipFile = hip_file
        self.hipFileEventType = FakeHipFileEventTypeCls()
        self._topnet_category = topnet_category
        self._root = FakeRootNode(children or [])

    def node(self, path: str) -> FakeRootNode:
        if path == "/":
            return self._root
        raise ValueError(f"FakeHou.node only knows '/', got {path!r}")

    def topNodeTypeCategory(self) -> FakeNodeTypeCategory:
        return self._topnet_category


# ── Fake pdg shapes (mirrors test_tops_bridge.py) ───────────────────


class FakePDGEnum:
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


_FAKE_PDG_EVENT_TYPE_MEMBERS = {
    "CookStart": FakePDGEnum("CookStart", 38),
    "CookComplete": FakePDGEnum("CookComplete", 14),
    "CookError": FakePDGEnum("CookError", 12),
    "CookWarning": FakePDGEnum("CookWarning", 13),
    "WorkItemAdd": FakePDGEnum("WorkItemAdd", 1),
    "WorkItemStateChange": FakePDGEnum("WorkItemStateChange", 5),
    "WorkItemResult": FakePDGEnum("WorkItemResult", 35),
}


class FakePDGEventTypeCls:
    __members__ = _FAKE_PDG_EVENT_TYPE_MEMBERS

    def __init__(self) -> None:
        for name, member in _FAKE_PDG_EVENT_TYPE_MEMBERS.items():
            setattr(self, name, member)

    def __call__(self, value: int) -> FakePDGEnum:
        for member in _FAKE_PDG_EVENT_TYPE_MEMBERS.values():
            if int(member) == value:
                return member
        raise ValueError(f"No FakeEventType with value {value}")


class FakePyEventHandler:
    __slots__ = ("callback",)

    def __init__(self, callback: Any) -> None:
        self.callback = callback


class FakePDG:
    EventType = FakePDGEventTypeCls()
    PyEventHandler = FakePyEventHandler


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def topnet_category() -> FakeNodeTypeCategory:
    return FakeNodeTypeCategory("topnet")


@pytest.fixture
def fake_hip_file() -> FakeHipFile:
    return FakeHipFile()


@pytest.fixture
def fake_pdg(monkeypatch) -> FakePDG:
    """Patch ``synapse.host.tops_bridge`` with a fake ``pdg`` module."""
    fake = FakePDG()
    monkeypatch.setattr("synapse.host.tops_bridge.pdg", fake)
    monkeypatch.setattr("synapse.host.tops_bridge._PDG_AVAILABLE", True)
    return fake


def _install_fake_hou(
    monkeypatch,
    hip_file: FakeHipFile,
    topnet_category: FakeNodeTypeCategory,
    children: Optional[List[Any]] = None,
) -> FakeHou:
    """Install a FakeHou into both modules that need it (scene_load_bridge
    AND tops_bridge.warm_all walk path)."""
    fake_hou = FakeHou(hip_file, topnet_category, children=children)
    monkeypatch.setattr(
        "synapse.host.scene_load_bridge.hou", fake_hou, raising=False
    )
    monkeypatch.setattr(
        "synapse.host.scene_load_bridge._HOU_AVAILABLE", True, raising=False
    )
    monkeypatch.setattr(
        "synapse.host.tops_bridge.hou", fake_hou, raising=False
    )
    monkeypatch.setattr(
        "synapse.host.tops_bridge._HOU_AVAILABLE", True, raising=False
    )
    return fake_hou


# ── Construction + headless-import gate ─────────────────────────────


class TestConstruction:
    """Bridge construction + the headless-import gate criterion."""

    def test_module_imports_headless_without_hou(self):
        """Gate criterion: module imports headless without ``hou``."""
        from synapse.host.scene_load_bridge import (
            SceneLoadBridge as _SceneLoadBridge,
            SceneLoadBridgeError as _SceneLoadBridgeError,
        )
        assert _SceneLoadBridge is SceneLoadBridge
        assert _SceneLoadBridgeError is SceneLoadBridgeError

    def test_construct_with_tops_bridge_succeeds(self):
        tops = TopsEventBridge(perception_callback=lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        assert bridge.is_subscribed() is False
        assert bridge.reload_count() == 0

    def test_construct_without_tops_bridge_raises_typeerror(self):
        with pytest.raises(TypeError, match="TopsEventBridge"):
            SceneLoadBridge(tops_bridge=None)

    def test_re_exported_from_synapse_host(self):
        """Confirm public surface visible from ``synapse.host`` package."""
        from synapse import host
        assert host.SceneLoadBridge is SceneLoadBridge
        assert host.SceneLoadBridgeError is SceneLoadBridgeError


# ── subscribe / unsubscribe round trip ─────────────────────────────


class TestSubscribeUnsubscribe:
    """Happy-path subscription lifecycle."""

    def test_subscribe_registers_callback_with_hou_hipfile(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()
        assert bridge.is_subscribed() is True
        assert fake_hip_file.add_calls == 1
        assert len(fake_hip_file.callbacks) == 1

    def test_unsubscribe_removes_callback_by_identity(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()
        registered = fake_hip_file.callbacks[0]
        bridge.unsubscribe()
        assert bridge.is_subscribed() is False
        assert fake_hip_file.remove_calls == 1
        assert len(fake_hip_file.callbacks) == 0
        # Identity check — bridge passed the same bound-method
        # reference to addEventCallback and removeEventCallback.
        assert registered is bridge._callback_fn

    def test_subscribe_without_hou_raises_typed_error(self, monkeypatch):
        """Per design § 2.2 — subscribe raises when hou unavailable."""
        monkeypatch.setattr(
            "synapse.host.scene_load_bridge._HOU_AVAILABLE", False
        )
        monkeypatch.setattr(
            "synapse.host.scene_load_bridge.hou", None
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        with pytest.raises(SceneLoadBridgeError, match="hou module not available"):
            bridge.subscribe()


# ── Filter behavior — AfterLoad fires, others do not ───────────────


class TestEventFilter:
    """Trigger filter: AfterLoad fires the warm path; everything else does not."""

    def test_after_load_fires_warm(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode("/tasks/topnet_a", topnet_category),
            FakeTopNode("/tasks/topnet_b", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        assert bridge.reload_count() == 1
        assert len(tops.active_subscriptions()) == 2

    def test_after_clear_does_not_fire_warm(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        """Audit § 3.2: filter must NOT trigger on AfterClear."""
        topnets = [FakeTopNode("/tasks/topnet_a", topnet_category)]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterClear)

        assert bridge.reload_count() == 0
        assert tops.active_subscriptions() == ()

    def test_before_load_and_before_clear_filtered(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [FakeTopNode("/tasks/topnet_a", topnet_category)]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.BeforeLoad)
        fake_hip_file.fire(fake_hou.hipFileEventType.BeforeClear)

        assert bridge.reload_count() == 0
        assert tops.active_subscriptions() == ()


# ── Walk filter — non-topnets are skipped ───────────────────────────


class TestWalkFilter:
    """The walk filters out non-topnets via topNodeTypeCategory()."""

    def test_non_topnet_nodes_are_skipped(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        other_category = FakeNodeTypeCategory("sop")
        children = [
            FakeTopNode("/tasks/topnet_a", topnet_category),
            FakeNonTopNode("/obj/geo1", other_category),
            FakeTopNode("/tasks/topnet_b", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=children
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        paths = {sub.top_node_path for sub in tops.active_subscriptions()}
        assert paths == {"/tasks/topnet_a", "/tasks/topnet_b"}


# ────────────────────────────────────────────────────────────────────
#                          # CRUCIBLE
# ────────────────────────────────────────────────────────────────────
#
# Hostile suite per design § 5. Adversarial posture: the
# implementation is the system under test. Each test pins a specific
# failure mode the bridge must defend against.


# ── Hostile case 1 ─────────────────────────────────────────────────


class TestHostile_AfterLoadWarmsAllTopnets:
    """Case 1 — AfterLoad fires → cool_all THEN warm_all called once each.

    Order matters per design § 2.8: cool stale subs first (their graph
    contexts are dead post-clear), then warm fresh ones. With a real
    TopsEventBridge under FakePDG, assert N=3 active subscriptions
    after a single AfterLoad.
    """

    def test_after_load_warms_all_topnets_in_order(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode("/tasks/topnet_a", topnet_category),
            FakeTopNode("/tasks/topnet_b", topnet_category),
            FakeTopNode("/tasks/topnet_c", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )

        # Use a spy that wraps a real TopsEventBridge to record call
        # order without losing the real warm/cool behavior.
        real_tops = TopsEventBridge(lambda e: None)
        call_order: List[str] = []

        original_cool_all = real_tops.cool_all
        original_warm_all = real_tops.warm_all

        def spy_cool_all() -> None:
            call_order.append("cool_all")
            original_cool_all()

        def spy_warm_all() -> List[Subscription]:
            call_order.append("warm_all")
            return original_warm_all()

        # Bind onto the instance — only this test's bridge is touched.
        real_tops.cool_all = spy_cool_all  # type: ignore[method-assign]
        real_tops.warm_all = spy_warm_all  # type: ignore[method-assign]

        bridge = SceneLoadBridge(tops_bridge=real_tops)
        bridge.subscribe()
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        # Order: cool_all THEN warm_all — design § 2.8.
        assert call_order == ["cool_all", "warm_all"]
        # All three topnets warmed.
        paths = {
            sub.top_node_path for sub in real_tops.active_subscriptions()
        }
        assert paths == {
            "/tasks/topnet_a",
            "/tasks/topnet_b",
            "/tasks/topnet_c",
        }
        assert bridge.reload_count() == 1


# ── Hostile case 2 ─────────────────────────────────────────────────


class TestHostile_AfterClearDoesNotWarm:
    """Case 2 — AfterClear must NOT trigger warming.

    Audit § 3.2 — between AfterClear and AfterLoad the scene holds zero
    nodes. Warming on AfterClear would walk the empty stage and do
    nothing useful AND would increment reload_count incorrectly.
    """

    def test_after_clear_does_not_warm_with_three_topnets_present(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode(f"/tasks/topnet_{i}", topnet_category) for i in range(3)
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterClear)

        assert tops.active_subscriptions() == ()
        assert bridge.reload_count() == 0


# ── Hostile case 3 ─────────────────────────────────────────────────


class TestHostile_MultipleAfterLoadNoDuplicates:
    """Case 3 — N consecutive AfterLoad events do NOT stack subs.

    Audit § 4.1 confirmed the underlying API does NOT dedupe. The
    bridge is responsible: cool_all between warmings is the mechanism.
    """

    def test_three_after_loads_yields_two_subs_not_six(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode("/tasks/topnet_a", topnet_category),
            FakeTopNode("/tasks/topnet_b", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        assert bridge.reload_count() == 3
        assert len(tops.active_subscriptions()) == 2  # Not 6!
        # Each topnet's graph context should have exactly one handler
        # (the latest), with the prior subscriptions cooled cleanly.
        for topnet in topnets:
            # 7 surfaced event types per topnet, one handler instance
            # registered against each.
            assert len(topnet.graph_context.handlers) == 7


# ── Hostile case 4 ─────────────────────────────────────────────────


class TestHostile_ZeroTopnetsNoError:
    """Case 4 — empty scene → handler runs cleanly, no exception."""

    def test_after_load_with_no_topnets_succeeds(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=[]
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        assert bridge.reload_count() == 1
        assert tops.active_subscriptions() == ()


# ── Hostile case 5 ─────────────────────────────────────────────────


class TestHostile_OneTopnetWarmFailureDoesNotBlockOthers:
    """Case 5 — topnet without graph context skipped; siblings still warm.

    Per Spike 3.1 § 2.6 a topnet with ``getPDGGraphContext() is None``
    causes ``warm`` to raise ``TopsBridgeError``. ``warm_all``
    swallows per-topnet failures (Spike 3.1 ``tops_bridge.py:354–361``).
    SceneLoadBridge inherits this resilience by delegation.
    """

    def test_failing_topnet_does_not_block_siblings(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        good_a = FakeTopNode("/tasks/good_a", topnet_category)
        bad = FakeTopNode("/tasks/bad", topnet_category, no_graph=True)
        good_b = FakeTopNode("/tasks/good_b", topnet_category)
        fake_hou = _install_fake_hou(
            monkeypatch,
            fake_hip_file,
            topnet_category,
            children=[good_a, bad, good_b],
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        paths = {
            sub.top_node_path for sub in tops.active_subscriptions()
        }
        assert paths == {"/tasks/good_a", "/tasks/good_b"}
        # The bad topnet did not poison reload_count or block the
        # handler from completing.
        assert bridge.reload_count() == 1


# ── Hostile case 6 ─────────────────────────────────────────────────


class TestHostile_UnsubscribeDuringAfterLoadHandlingDoesNotCrash:
    """Case 6 — unsubscribe fired mid-AfterLoad must not crash.

    Synthesizes the race with a TopsEventBridge subclass whose warm_all
    triggers ``bridge.unsubscribe()`` partway through. The bridge must
    swallow the cool_all-during-cool race without crashing.
    """

    def test_unsubscribe_fires_during_warm_all(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode("/tasks/a", topnet_category),
            FakeTopNode("/tasks/b", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )

        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)
        bridge.subscribe()

        # Wire warm_all to call unsubscribe partway through.
        original_warm = tops.warm

        warmed: List[str] = []

        def warm_then_unsubscribe(top_node: Any) -> Subscription:
            sub = original_warm(top_node)
            warmed.append(top_node.path())
            if len(warmed) == 1:
                # Right after first warm — fire unsubscribe.
                bridge.unsubscribe()
            return sub

        tops.warm = warm_then_unsubscribe  # type: ignore[method-assign]

        # Should NOT crash even though unsubscribe runs while warm_all
        # is still iterating.
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        # Unsubscribe ran. After the handler returns, the bridge is
        # cleanly off and the subscriptions wiped.
        assert bridge.is_subscribed() is False
        assert tops.active_subscriptions() == ()


# ── Hostile case 7 ─────────────────────────────────────────────────


class TestHostile_SubscribeUnsubscribeNoCallbackLeak:
    """Case 7 — full lifecycle leaves no callback leak; re-subscribe works."""

    def test_full_round_trip_no_leak_then_resubscribe(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [FakeTopNode("/tasks/a", topnet_category)]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)

        bridge.subscribe()
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)
        assert len(tops.active_subscriptions()) == 1

        bridge.unsubscribe()
        # No callback leaked at the hipFile layer.
        assert fake_hip_file.callbacks == []
        # No subscription leaked at the PDG layer.
        assert tops.active_subscriptions() == ()
        # Public introspection reflects the state.
        assert bridge.is_subscribed() is False

        # Re-subscription works cleanly.
        bridge.subscribe()
        assert bridge.is_subscribed() is True
        assert len(fake_hip_file.callbacks) == 1
        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)
        assert len(tops.active_subscriptions()) == 1


# ── Hostile case 8 ─────────────────────────────────────────────────


class TestHostile_IdempotencyGuards:
    """Case 8 — subscribe twice does not double-register; unsubscribe-without-subscribe is safe.

    Audit § 4.1: API does NOT dedupe. The bridge's _subscribed guard
    is the single registration discipline.
    """

    def test_subscribe_twice_does_not_double_register(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)

        bridge.subscribe()
        bridge.subscribe()  # Second call — must be no-op
        bridge.subscribe()  # Third call — also no-op

        assert fake_hip_file.add_calls == 1
        assert len(fake_hip_file.callbacks) == 1

    def test_unsubscribe_without_prior_subscribe_is_noop(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)

        # No prior subscribe — must not crash, must not call into hou.
        bridge.unsubscribe()
        bridge.unsubscribe()

        assert fake_hip_file.remove_calls == 0
        assert bridge.is_subscribed() is False

    def test_unsubscribe_idempotent_after_subscribe(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)
        tops = TopsEventBridge(lambda e: None)
        bridge = SceneLoadBridge(tops_bridge=tops)

        bridge.subscribe()
        bridge.unsubscribe()
        bridge.unsubscribe()  # Second call — must not crash
        bridge.unsubscribe()  # Third call — also safe

        assert fake_hip_file.remove_calls == 1
        assert bridge.is_subscribed() is False


# ── Hostile case 9 ─────────────────────────────────────────────────


class TestHostile_MultipleSceneLoadBridgesSameHou:
    """Case 9 — two SceneLoadBridges on the same hou session are independent.

    Each owns its own injected TopsEventBridge. AfterLoad fires both
    handlers; both bridges warm independently.
    """

    def test_two_bridges_independent_after_one_event(
        self, monkeypatch, fake_hip_file, fake_pdg, topnet_category
    ):
        topnets = [
            FakeTopNode("/tasks/a", topnet_category),
            FakeTopNode("/tasks/b", topnet_category),
        ]
        fake_hou = _install_fake_hou(
            monkeypatch, fake_hip_file, topnet_category, children=topnets
        )

        tops_a = TopsEventBridge(lambda e: None)
        tops_b = TopsEventBridge(lambda e: None)
        bridge_a = SceneLoadBridge(tops_bridge=tops_a)
        bridge_b = SceneLoadBridge(tops_bridge=tops_b)

        bridge_a.subscribe()
        bridge_b.subscribe()

        # Two distinct callbacks registered on the FakeHipFile.
        assert len(fake_hip_file.callbacks) == 2
        # The two callback identities differ — one bound method per
        # bridge instance.
        assert fake_hip_file.callbacks[0] is not fake_hip_file.callbacks[1]

        fake_hip_file.fire(fake_hou.hipFileEventType.AfterLoad)

        assert bridge_a.reload_count() == 1
        assert bridge_b.reload_count() == 1
        assert len(tops_a.active_subscriptions()) == 2
        assert len(tops_b.active_subscriptions()) == 2

        # Tearing down bridge_a leaves bridge_b's wiring intact.
        bridge_a.unsubscribe()
        assert len(fake_hip_file.callbacks) == 1
        assert tops_a.active_subscriptions() == ()
        assert len(tops_b.active_subscriptions()) == 2


# ── Hostile case 10 ────────────────────────────────────────────────


class TestHostile_CallbackRaisingMidEventSwallowed:
    """Case 10 — exceptions inside warm_all are swallowed.

    The bridge MUST NOT propagate exceptions from the embedded
    TopsEventBridge back into Houdini's hipFile callback invocation
    chain — agent-side bugs cannot disrupt Houdini's scene load.
    reload_count still increments (the event WAS handled, even if
    warming failed).
    """

    def test_warm_all_raising_does_not_propagate(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)

        bad_tops = MagicMock()
        bad_tops.cool_all = MagicMock()
        bad_tops.warm_all = MagicMock(side_effect=RuntimeError("synthetic"))

        bridge = SceneLoadBridge(tops_bridge=bad_tops)
        bridge.subscribe()

        # Must NOT raise — exception is swallowed inside the handler.
        fake_hou_module = bridge._callback_fn.__self__  # noqa: SLF001 — test access
        # Fire the event via the public hipFile.fire shape.
        # Looking up the live AfterLoad value off the same fake hou
        # the bridge sees:
        from synapse.host import scene_load_bridge as _slb_mod
        after_load = _slb_mod.hou.hipFileEventType.AfterLoad
        fake_hip_file.fire(after_load)

        # Counter advanced — event was handled.
        assert bridge.reload_count() == 1
        # cool_all called BEFORE warm_all per design § 2.8.
        bad_tops.cool_all.assert_called_once()
        bad_tops.warm_all.assert_called_once()
        # Bridge state stayed consistent — no flag corruption.
        assert bridge.is_subscribed() is True

    def test_cool_all_raising_does_not_block_warm_all(
        self, monkeypatch, fake_hip_file, topnet_category
    ):
        """Even if cool_all blows up, warm_all still runs.

        Per design § 2.8: each step is independently try/except'd.
        """
        _install_fake_hou(monkeypatch, fake_hip_file, topnet_category)

        flaky_tops = MagicMock()
        flaky_tops.cool_all = MagicMock(side_effect=RuntimeError("cool boom"))
        flaky_tops.warm_all = MagicMock(return_value=[])

        bridge = SceneLoadBridge(tops_bridge=flaky_tops)
        bridge.subscribe()

        from synapse.host import scene_load_bridge as _slb_mod
        after_load = _slb_mod.hou.hipFileEventType.AfterLoad
        fake_hip_file.fire(after_load)

        # warm_all still ran despite cool_all raising.
        flaky_tops.cool_all.assert_called_once()
        flaky_tops.warm_all.assert_called_once()
        assert bridge.reload_count() == 1
