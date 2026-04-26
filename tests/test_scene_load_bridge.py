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
# Hostile suite lives below this divider. Owned by CRUCIBLE in the
# second pass — see docs/sprint3/spike_3_2_design.md § 5.
