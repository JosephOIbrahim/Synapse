"""B3: observing costs nothing.

* The tracker's three housekeeping rows are opt-in (the flip itself is pinned
  in tests/test_harden_h1_h4.py, next to the switch's own tests).
* The freeze watchdog stands down when Houdini begins to quit, and a late beat
  during teardown cannot rebuild it.

Not covered here, because it needs a real USD runtime: releasing the store's
USD layer on close (the "layer already exists" fallback on a rebind).

Pure Python: no hou.
"""
from __future__ import annotations

import types

import pytest

from synapse.server import freeze_chain as fc


@pytest.fixture(autouse=True)
def _clean_chain():
    fc.shutdown_freeze_chain()
    fc._quitting_until = 0.0
    yield
    fc.shutdown_freeze_chain()
    fc._quitting_until = 0.0


def test_housekeeping_rows_are_off_unless_asked_for(monkeypatch):
    from synapse.session.tracker import _auto_memory_enabled

    monkeypatch.delenv("SYNAPSE_AUTO_MEMORY", raising=False)
    assert _auto_memory_enabled() is False
    monkeypatch.setenv("SYNAPSE_AUTO_MEMORY", "1")
    assert _auto_memory_enabled() is True


def test_quitting_stops_a_running_chain():
    fc.beat()
    assert fc._chain is not None
    assert fc.note_host_quitting() is True
    assert fc._chain is None


def test_quitting_with_no_chain_is_harmless():
    assert fc.note_host_quitting() is False


def test_a_beat_during_the_quit_does_not_rebuild_the_chain():
    fc.beat()
    fc.note_host_quitting()
    fc.beat()
    fc.beat()
    assert fc._chain is None


def test_a_cancelled_quit_gets_the_watchdog_back_after_the_grace(monkeypatch):
    clock = {"now": 1000.0}
    monkeypatch.setattr(fc.time, "monotonic", lambda: clock["now"])
    fc.note_host_quitting(grace_s=120.0)
    clock["now"] += 119.0
    fc.beat()
    assert fc._chain is None
    clock["now"] += 2.0
    fc.beat()
    assert fc._chain is not None


def _fake_events():
    return types.SimpleNamespace(
        BeforeLoad="BeforeLoad", AfterLoad="AfterLoad", AfterSave="AfterSave",
        AfterClear="AfterClear", BeforeQuit="BeforeQuit")


def test_the_lifecycle_callback_stands_the_chain_down_on_before_quit(monkeypatch):
    from synapse.host import memory_lifecycle
    from synapse.memory import store as module

    monkeypatch.setattr(module, "hou", types.SimpleNamespace(hipFileEventType=_fake_events()),
                        raising=False)
    called = []
    monkeypatch.setattr(memory_lifecycle, "ensure_current_memory",
                        lambda **kw: called.append(kw))
    fc.beat()
    memory_lifecycle._handle_event("BeforeQuit")
    assert fc._chain is None
    assert called == []  # a quit is not a memory rebind


def test_a_build_without_before_quit_is_ignored(monkeypatch):
    from synapse.host import memory_lifecycle
    from synapse.memory import store as module

    events = _fake_events()
    del events.BeforeQuit
    monkeypatch.setattr(module, "hou", types.SimpleNamespace(hipFileEventType=events),
                        raising=False)
    monkeypatch.setattr(memory_lifecycle, "ensure_current_memory", lambda **kw: None)
    fc.beat()
    memory_lifecycle._handle_event(None)
    assert fc._chain is not None
