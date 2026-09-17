"""B6 — a sick store must be VISIBLE on every health surface.

THE INCIDENT THESE PIN
----------------------
2026-09-15 15:09 -> 2026-09-17 15:53: a ``MemoryStore`` sat DEGRADED and refused
EVERY write for ~2 days. One duplicated-id line did it (``_load`` raises
"conflicting duplicate memory identity" on the second differing canonical;
store.py:396-401 then degrades the whole store). Every health surface in the
repo reported ok for the entire outage, and ``synapse_memory_status`` returned a
dict shape IDENTICAL to a healthy store's.

Each test below fails against the pre-B6 code. That is the point: a guard that
cannot fail is worse than none, because it reads as covered.

NO DISK, NO ``hou``, NO REAL STORE. Every fixture is a stub — these tests must
never be able to touch the live store they exist to protect.
"""

from __future__ import annotations

import types

import pytest

from synapse.panel import health_strip as hs
from synapse.server import write_plane as wp


# ---------------------------------------------------------------------------
# Stubs. Named to match the real classes where the code matches BY NAME.
# ---------------------------------------------------------------------------

class _ContractStore:
    """A store carrying Lane B3's pinned health contract."""

    def __init__(self, degraded=False, reason="", writable=None,
                 records=0, rejected=0):
        self._degraded = degraded
        self._reason = reason
        self._writable = (not degraded) if writable is None else writable
        self._records = records
        self._rejected = rejected

    @property
    def is_degraded(self):
        return self._degraded

    @property
    def degraded_reason(self):
        return self._reason

    def health(self):
        return {"degraded": self._degraded, "reason": self._reason,
                "writable": self._writable, "records": self._records,
                "rejected_writes": self._rejected}

    def count(self):
        return self._records


class _LegacyStore:
    """A store object predating the contract — no health(), no properties.

    The defensive case: "we could not determine health" must never collapse
    into "healthy".
    """

    def count(self):
        return 1117  # the count measured live DURING the outage


class MemoryStore(_ContractStore):
    """Name-matched to the real jsonl class, which ``store_health`` matches on."""


class MonetaBackedStore:
    """The facade shape from the incident: healthy-looking, dead safety net."""

    def __init__(self, jsonl_net):
        self._jsonl_net = jsonl_net
        self._handle = types.SimpleNamespace(durability=object())

    def count(self):
        return 1117


# ---------------------------------------------------------------------------
# 1. read_store_write_health — the shared reader
# ---------------------------------------------------------------------------

def test_sick_store_reads_degraded_and_says_so_in_operator_words():
    got = wp.read_store_write_health(
        _ContractStore(degraded=True,
                       reason="conflicting duplicate memory identity",
                       rejected=42))
    assert got["status"] == "degraded"
    assert got["accepting_writes"] is False
    assert "not accepting writes" in got["reason"]
    assert got["rejected_writes"] == 42
    assert "42 write(s) have been refused" in got["reason"]


def test_store_without_the_contract_is_unknown_never_ok():
    got = wp.read_store_write_health(_LegacyStore())
    assert got["status"] == "unknown"
    assert got["accepting_writes"] is None
    assert got["status"] != "ok"


def test_healthy_store_reads_ok():
    got = wp.read_store_write_health(_ContractStore(records=10))
    assert got["status"] == "ok"
    assert got["accepting_writes"] is True


def test_health_that_raises_is_unknown_not_ok():
    class _Raises:
        def health(self):
            raise RuntimeError("boom")

    got = wp.read_store_write_health(_Raises())
    assert got["status"] == "unknown"
    assert "raised" in got["reason"]


def test_malformed_health_dict_is_unknown_not_ok():
    class _Malformed:
        def health(self):
            return {"degraded": "no", "writable": "yes"}  # strings, not bools

    assert wp.read_store_write_health(_Malformed())["status"] == "unknown"


def test_fail_closed_negative_rejected_count_is_never_rendered_as_a_number():
    """``MemoryStore.health()`` fail-closes with ``rejected_writes: -1`` when its
    own probe cannot complete. That sentinel must not surface as "-1 write(s)
    have been refused" — a fabricated number in the one sentence an artist acts
    on. The store is still reported sick, via degraded/writable."""
    got = wp.read_store_write_health(
        _ContractStore(degraded=True, reason="health probe did not complete",
                       rejected=-1))
    assert got["status"] == "degraded"
    assert "-1" not in got["reason"]
    assert got["rejected_writes"] is None       # uncounted, not "minus one"


def test_dead_jsonl_safety_net_behind_a_healthy_moneta_facade_is_degraded():
    """THE incident shape. Moneta is the primary and looks fine; the JSONL
    mirror it dual-writes to is refusing every write. Asking only the facade
    reports this as healthy — which is what happened."""
    facade = MonetaBackedStore(
        jsonl_net=_ContractStore(degraded=True, reason="degraded load"))
    got = wp.read_store_write_health(facade)
    assert got["status"] == "degraded"
    assert "MonetaBackedStore._jsonl_net" in got["sources"]


# ---------------------------------------------------------------------------
# 2. write_plane.store_health — the authoritative check must DOMINATE
# ---------------------------------------------------------------------------

def test_store_health_degrades_when_the_store_refuses_writes(monkeypatch):
    """All three pre-B6 checks pass; only the store's own verdict dissents.

    Serving class matches the requested backend, ``count()`` returns a normal
    number, and it is not Moneta so the durability check is skipped. Pre-B6 this
    returned ok. That was the outage.
    """
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)
    sick = MemoryStore(degraded=True, reason="conflicting duplicate memory identity",
                       records=1117)
    monkeypatch.setattr(wp, "_live_store", lambda: sick)

    info = wp.store_health()
    assert info["evaluated"] is True
    assert info["count"] == 1117          # the count still looks fine
    assert info["serving_class"] == "MemoryStore"
    assert info["status"] == "degraded"   # ...and the verdict does not
    assert info["accepting_writes"] is False


def test_store_health_is_unknown_for_a_store_that_cannot_answer(monkeypatch):
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)
    monkeypatch.setattr(wp, "_live_store", lambda: _LegacyStore())

    info = wp.store_health()
    assert info["status"] == "unknown"
    assert info["status"] != "ok"


# ---------------------------------------------------------------------------
# 3. health_strip — the panel dot
# ---------------------------------------------------------------------------

def test_memory_cell_goes_red_when_writes_are_refused():
    cell = hs.cell_memory({"fallback": None, "backend": "MonetaBackedStore",
                           "moneta_live": True,
                           "write_health": {"sick": True,
                                            "reason": "degraded load"}})
    assert cell.verdict == hs.Verdict.RED
    assert cell.verdict != hs.Verdict.OK
    assert "not accepting writes" in cell.reason


def test_memory_cell_is_unknown_when_write_health_could_not_be_read():
    """A live backend whose write state nothing could report is UNKNOWN. The
    identity positive must not be able to short-circuit to green past it."""
    cell = hs.cell_memory({"fallback": None, "backend": "MonetaBackedStore",
                           "moneta_live": True, "write_health": None})
    assert cell.verdict == hs.Verdict.UNKNOWN
    assert cell.color != hs.t.GROW
    assert cell.value == "MonetaBackedStore"   # still says WHAT is serving


@pytest.mark.parametrize("bogus", ["ok", 1, [], True])
def test_memory_cell_is_unknown_for_an_uninterpretable_write_health(bogus):
    """A write_health of the wrong shape must not fall through to the green
    returns below it — that would rebuild the collapse this lane removes."""
    cell = hs.cell_memory({"fallback": None, "backend": "MonetaBackedStore",
                           "moneta_live": True, "write_health": bogus})
    assert cell.verdict == hs.Verdict.UNKNOWN
    assert cell.color != hs.t.GROW


def test_memory_cell_stays_ok_when_the_store_confirms_it_is_writing():
    cell = hs.cell_memory({"fallback": None, "backend": "MonetaBackedStore",
                           "moneta_live": True,
                           "write_health": {"sick": False, "reason": ""}})
    assert cell.verdict == hs.Verdict.OK


@pytest.mark.parametrize("store,expect_sick", [
    (_ContractStore(degraded=True, reason="degraded load"), True),
    (_ContractStore(), False),
])
def test_gather_reads_write_health_off_the_live_singleton(monkeypatch, store,
                                                          expect_sick):
    from synapse.memory import store as store_mod
    monkeypatch.setattr(store_mod, "_global_synapse",
                        types.SimpleNamespace(store=store), raising=False)
    monkeypatch.setattr(store_mod, "backend_fallback", lambda: None)

    fact = hs._gather_memory()
    assert fact["write_health"] == {"sick": expect_sick,
                                    "reason": "degraded load" if expect_sick else ""}


# ---------------------------------------------------------------------------
# 4. Against the REAL MemoryStore (tmp_path only — never the live store)
# ---------------------------------------------------------------------------

def test_real_degraded_memorystore_is_seen_by_every_surface(tmp_path):
    """End-to-end on the real class, reproducing the incident's trigger: two
    JSONL lines sharing an id with different content."""
    from synapse.memory.store import MemoryStore

    storage = tmp_path / "store"
    storage.mkdir()
    (storage / "memory.jsonl").write_text(
        '{"id":"a","created_at":"2026-09-15T15:09:00","content":"one",'
        '"memory_type":"decision"}\n'
        '{"id":"a","created_at":"2026-09-15T15:09:00","content":"TWO",'
        '"memory_type":"decision"}\n',
        encoding="utf-8")
    store = MemoryStore(storage, background_load=False)

    assert store.is_degraded is True          # B3's contract, live
    reading = wp.read_store_write_health(store)
    assert reading["status"] == "degraded"
    assert reading["accepting_writes"] is False

    cell = hs.cell_memory({"fallback": None, "backend": "MemoryStore",
                           "moneta_live": False,
                           "write_health": {"sick": True,
                                            "reason": store.degraded_reason}})
    assert cell.verdict == hs.Verdict.RED


def test_gather_reports_none_for_a_store_with_no_contract(monkeypatch):
    from synapse.memory import store as store_mod
    monkeypatch.setattr(store_mod, "_global_synapse",
                        types.SimpleNamespace(store=_LegacyStore()), raising=False)
    monkeypatch.setattr(store_mod, "backend_fallback", lambda: None)

    fact = hs._gather_memory()
    assert fact["write_health"] is None
    assert hs.cell_memory(fact).verdict == hs.Verdict.UNKNOWN
