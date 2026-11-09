"""SLEEP-PASS COUNTER: Doctor says how many sleep passes ran in this process.

``_check_moneta_consolidation`` reported ``sleep_pass_called: "not_tracked"``
because no counter for ``run_sleep_pass`` existed. ``run_sleep_pass`` is the
one destructive memory op (it permanently prunes), and it is reached from two
places: the APPROVE-gated ``synapse_sleep_pass`` handler and the opt-in
every-100th-add trigger. Whether it has ever run is the first question an
operator asks after a memory went missing.

The counter is process-lifetime (module state in ``moneta_store``), so it
survives ``reset_synapse_memory()`` rebuilding the store. ``run_sleep_pass``
maintains it: the count, the time of the last pass, and a summary of the last
result, including a pass that raised (rows can already be gone by then).

Fakes only, the ``test_prune_audit_on_failure.py`` shape. Nothing imports
``moneta``: the handle is a double whose ``durability`` is None.
"""
from __future__ import annotations

import importlib
import uuid
from types import SimpleNamespace

import pytest

from synapse.memory import moneta_store
from synapse.memory.models import Memory, MemoryType
from synapse.memory.moneta_store import MonetaBackedStore
from synapse.server import doctor

_STAMP = "2026-11-09T00:00:00Z"


class PanicException(BaseException):
    """Stand-in for ``pyo3_runtime.PanicException`` (a BaseException)."""


PanicException.__module__ = "pyo3_runtime"


class _FakeRow:
    def __init__(self, entity_id, payload):
        self.entity_id = entity_id
        self.payload = payload


class _FakeECS:
    def __init__(self, rows):
        self._rows = {row.entity_id: row for row in rows}

    @property
    def n(self):
        return len(self._rows)

    def iter_rows(self):
        return list(self._rows.values())

    def remove(self, entity_id):
        del self._rows[entity_id]

    def count_protected(self):
        return 0


class _FakeHandle:
    """Prunes the doomed rows first, then may raise (Moneta's run_pass order)."""

    durability = None

    def __init__(self, rows, doomed=(), *, raise_after_prune=None):
        self.ecs = _FakeECS(rows)
        self._doomed = list(doomed)
        self._raise = raise_after_prune

    def run_sleep_pass(self):
        for eid in self._doomed:
            self.ecs.remove(eid)
        if self._raise is not None:
            raise self._raise
        return SimpleNamespace(staged=1, attention_updated=2)


def _store(n_rows=3, n_doomed=1, **kwargs):
    rows, doomed = [], []
    for i in range(n_rows):
        eid = uuid.uuid4()
        mem = Memory(id=f"mem_{i}", created_at=_STAMP, content=f"note {i}",
                     memory_type=MemoryType.NOTE)
        rows.append(_FakeRow(eid, mem.to_json()))
        if i < n_doomed:
            doomed.append(eid)
    return MonetaBackedStore(_FakeHandle(rows, doomed, **kwargs), embedder=None)


@pytest.fixture
def live_store(monkeypatch):
    """Point the doctor's consolidation check at an isolated fake store."""
    holder = {}
    store_mod = importlib.import_module("synapse.memory.store")
    monkeypatch.setattr(store_mod, "get_synapse_memory",
                        lambda: SimpleNamespace(store=holder["store"]))
    return holder


# ---------------------------------------------------------------------------
# RED: the doctor reports a count after a pass ran
# ---------------------------------------------------------------------------

def test_consolidation_reports_a_sleep_pass_count_after_run_sleep_pass(live_store):
    """Fails on the unmodified tree: the check said ``"not_tracked"``."""
    store = _store()
    live_store["store"] = store

    before = doctor._check_moneta_consolidation()
    assert before["status"] == "ok", before
    passes_before = before["result"].get("sleep_passes")
    assert isinstance(passes_before, dict), (
        "no sleep-pass counter is reported: sleep_pass_called="
        f"{before['result'].get('sleep_pass_called')!r}")

    audit = store.run_sleep_pass()
    assert audit.pruned == 1

    after = doctor._check_moneta_consolidation()
    passes = after["result"]["sleep_passes"]
    assert passes["count"] == passes_before["count"] + 1
    assert passes["completed"] == passes_before["completed"] + 1
    assert after["result"]["sleep_pass_called"] is True
    last = passes["last_result"]
    assert last["outcome"] == "completed"
    assert (last["pruned"], last["count_before"], last["count_after"]) == (1, 3, 2)
    assert passes["last_at"]
    assert f"{passes['count']} sleep pass" in after["detail"]


# ---------------------------------------------------------------------------
# The counter itself
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_counter():
    moneta_store._reset_sleep_pass_stats_for_tests()
    yield
    moneta_store._reset_sleep_pass_stats_for_tests()


def test_a_fresh_process_reports_zero_and_no_last_pass(fresh_counter, live_store):
    live_store["store"] = _store()

    check = doctor._check_moneta_consolidation()

    passes = check["result"]["sleep_passes"]
    assert passes["count"] == 0 and passes["last_at"] is None
    assert passes["last_result"] is None
    assert check["result"]["sleep_pass_called"] is False
    assert "no sleep pass has run in this process" in check["detail"]


def test_a_completed_pass_is_counted_with_its_summary(fresh_counter):
    _store(n_rows=4, n_doomed=2).run_sleep_pass()

    stats = moneta_store.sleep_pass_stats()

    assert (stats["count"], stats["completed"], stats["failed"]) == (1, 1, 0)
    assert stats["last_result"] == {
        "outcome": "completed", "pruned": 2, "staged": 1,
        "attention_updated": 2, "count_before": 4, "count_after": 2,
        "error": None}
    assert stats["last_at"].endswith("Z") and stats["last_monotonic"] > 0


def test_a_pass_that_raises_is_counted_as_failed_and_reraised(fresh_counter):
    store = _store(n_rows=3, n_doomed=1, raise_after_prune=ValueError("snapshot failed"))

    with pytest.raises(ValueError, match="snapshot failed"):
        store.run_sleep_pass()

    stats = moneta_store.sleep_pass_stats()
    assert (stats["count"], stats["completed"], stats["failed"]) == (1, 0, 1)
    last = stats["last_result"]
    assert last["outcome"] == "failed"
    assert last["error"] == "ValueError: snapshot failed"
    # The failed pass had already pruned: the counter says so.
    assert (last["pruned"], last["count_before"], last["count_after"]) == (1, 3, 2)


def test_a_native_panic_is_counted_as_failed_and_reraised(fresh_counter):
    store = _store(raise_after_prune=PanicException("rust panicked"))

    with pytest.raises(PanicException):
        store.run_sleep_pass()

    stats = moneta_store.sleep_pass_stats()
    assert stats["failed"] == 1
    assert stats["last_result"]["error"] == "PanicException: rust panicked"


def test_an_operator_interrupt_is_not_counted(fresh_counter):
    store = _store(raise_after_prune=KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        store.run_sleep_pass()

    assert moneta_store.sleep_pass_stats()["count"] == 0


def test_the_counter_is_process_lifetime_across_stores(fresh_counter):
    """A rebuilt store (reset_synapse_memory) must not zero the count."""
    _store().run_sleep_pass()
    _store().run_sleep_pass()

    assert moneta_store.sleep_pass_stats()["count"] == 2


def test_stats_are_a_copy(fresh_counter):
    _store().run_sleep_pass()
    stats = moneta_store.sleep_pass_stats()
    stats["count"] = 999
    stats["last_result"]["pruned"] = 999

    again = moneta_store.sleep_pass_stats()
    assert again["count"] == 1 and again["last_result"]["pruned"] == 1
