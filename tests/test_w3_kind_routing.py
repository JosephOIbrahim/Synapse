"""W3-KIND — recall routes on TYPE, not a free-text scan.

Pins the routing half of the mission:
  * (predicate 1) a kind-filtered query returns ONLY that kind, across all
    five spec kinds, at the store, SynapseMemory, and MCP-handler levels;
  * (predicate 2) the filtered path is STRUCTURALLY shown to touch only that
    kind's typed prims, not the whole store — proven with a _memories proxy
    that counts per-id access vs full-store iteration;
  * (crucible negative control) an unknown kind returns empty + a loud
    invalid_kinds report, and provably NEVER falls through to a full scan.

Scope note: proven against the jsonl MemoryStore (the default backend, which
already resolves kind via its by_type index). The Moneta backend's per-kind
non-scan is the typed-cortex substrate owned by W3-STORE (moneta_store.py,
open claim) — W3-KIND routes through the store.get_by_type API both backends
expose, and does not edit moneta_store.py.
"""

import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import kind_schema as ks  # noqa: E402
from synapse.memory.models import Memory, MemoryType, MemoryQuery  # noqa: E402
from synapse.memory.store import MemoryStore, SynapseMemory  # noqa: E402
from synapse.session.tracker import SynapseBridge  # noqa: E402


# --------------------------------------------------------------------------
# Fixtures & helpers
# --------------------------------------------------------------------------

# Every MemoryType so isolation is tested against a genuinely mixed store, not
# only the five spec kinds.
_ALL_KINDS = list(MemoryType)


class CountingDict(dict):
    """A dict that counts full-store iteration vs targeted per-id access.

    ``values()`` / ``__iter__`` are the full-store signals (a scan); each
    ``__getitem__`` is one targeted typed-prim access. Swapped in for a
    MemoryStore's ``_memories`` to make the non-scan claim measurable rather
    than asserted.
    """

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.getitem_calls = 0
        self.values_calls = 0
        self.iter_calls = 0

    def reset(self):
        self.getitem_calls = self.values_calls = self.iter_calls = 0

    def __getitem__(self, key):
        self.getitem_calls += 1
        return super().__getitem__(key)

    def values(self):
        self.values_calls += 1
        return super().values()

    def __iter__(self):
        self.iter_calls += 1
        return super().__iter__()


def _mixed_store(per_kind=3, note_noise=25):
    """A store holding `per_kind` of every kind + extra NOTE noise."""
    store = MemoryStore(tempfile.mkdtemp())
    for k in _ALL_KINDS:
        for i in range(per_kind):
            store.add(Memory(content=f"{k.value} memory {i}", memory_type=k,
                             summary=f"{k.value}-{i}"))
    for i in range(note_noise):
        store.add(Memory(content=f"noise note {i}", memory_type=MemoryType.NOTE))
    # Force the (trivial, empty-dir) background load so _memories is stable
    # before any proxy swap.
    store.get_by_type(MemoryType.NOTE)
    return store


def _synapse_over(store):
    """A headless SynapseMemory wrapping an explicit store (no Houdini)."""
    mem = object.__new__(SynapseMemory)
    mem.store = store
    mem._on_memory_added = []
    return mem


# --------------------------------------------------------------------------
# Predicate 1 — a kind-filtered query returns ONLY that kind (all five)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kind", list(ks.SPEC_KINDS))
def test_store_get_by_type_returns_only_that_kind(kind):
    store = _mixed_store()
    got = store.get_by_type(kind)
    assert got, "expected at least one memory of this kind"
    assert all(m.memory_type == kind for m in got)


@pytest.mark.parametrize("kind", list(ks.SPEC_KINDS))
def test_synapse_search_kind_filter_returns_only_that_kind(kind):
    mem = _synapse_over(_mixed_store())
    results = mem.search("memory", memory_types=[kind])
    assert results
    assert all(r.memory.memory_type == kind for r in results)


@pytest.mark.parametrize("kind", list(ks.SPEC_KINDS))
def test_synapse_recall_kind_filter_returns_only_that_kind(kind):
    mem = _synapse_over(_mixed_store())
    recalled = mem.recall("memory", kinds=[kind], limit=100)
    assert recalled
    assert all(m.memory_type == kind for m in recalled)


@pytest.mark.parametrize("kind", list(ks.SPEC_KINDS))
def test_handler_search_kind_filter_returns_only_that_kind(kind):
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(_mixed_store())
    out = bridge.handle_memory_search({"query": "memory", "types": [kind.value]})
    assert out["results"]
    assert all(r["type"] == kind.value for r in out["results"])


def test_kind_filter_excludes_other_kinds_even_when_text_matches():
    # A NOTE and a DECISION both contain "rim"; a decision-filtered query must
    # not leak the note.
    store = MemoryStore(tempfile.mkdtemp())
    store.add(Memory(content="rim light note", memory_type=MemoryType.NOTE))
    store.add(Memory(content="rim light warmer", memory_type=MemoryType.DECISION,
                     reasoning="client wanted warmth"))
    mem = _synapse_over(store)
    results = mem.search("rim", memory_types=[MemoryType.DECISION])
    assert [r.memory.memory_type for r in results] == [MemoryType.DECISION]


# --------------------------------------------------------------------------
# Predicate 2 — the filtered path touches only matching typed prims
# --------------------------------------------------------------------------

def test_get_by_type_touches_only_matching_prims_not_whole_store():
    store = _mixed_store(per_kind=3, note_noise=25)
    proxy = CountingDict(store._memories)
    store._memories = proxy
    proxy.reset()

    got = store.get_by_type(MemoryType.DECISION)

    assert len(got) == 3
    # Touched exactly the 3 decision prims, and NEVER iterated the whole store.
    assert proxy.getitem_calls == 3
    assert proxy.values_calls == 0
    assert proxy.iter_calls == 0


def test_search_kind_filter_touches_only_matching_prims():
    store = _mixed_store(per_kind=3, note_noise=25)
    proxy = CountingDict(store._memories)
    store._memories = proxy
    proxy.reset()

    results = store.search(MemoryQuery(memory_types=[MemoryType.TASK]))

    assert all(r.memory.memory_type == MemoryType.TASK for r in results)
    # Candidate resolution reads only the task ids from the index.
    assert proxy.getitem_calls == 3
    assert proxy.values_calls == 0


def test_control_unfiltered_search_DOES_scan_the_whole_store():
    # Proves the counter actually detects a scan — an unfiltered query is
    # allowed to (and does) iterate the whole store, so the zero-scan asserts
    # above are meaningful, not vacuous.
    store = _mixed_store()
    proxy = CountingDict(store._memories)
    store._memories = proxy
    proxy.reset()

    store.search(MemoryQuery())  # no text, no kind -> full scan

    assert proxy.values_calls >= 1


# --------------------------------------------------------------------------
# Negative control — unknown kind: empty + loud, never a silent full scan
# --------------------------------------------------------------------------

def test_handler_search_unknown_kind_is_empty_and_loud():
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(_mixed_store())
    out = bridge.handle_memory_search({"query": "memory", "types": ["banana"]})
    assert out["count"] == 0
    assert out["results"] == []
    assert out.get("invalid_kinds") == ["banana"]
    assert "error" in out


def test_handler_recall_unknown_kind_is_empty_and_loud():
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(_mixed_store())
    out = bridge.handle_memory_recall({"query": "memory", "types": ["banana"]})
    assert out["count"] == 0
    assert out["matches"] == []
    assert out.get("invalid_kinds") == ["banana"]
    assert out["found"] is False


def test_handler_search_unknown_kind_does_NOT_fall_through_to_full_scan():
    # The crux of the negative control: a bad kind must not be silently dropped
    # and then answered with the whole store. We prove it structurally — the
    # store is never scanned on the invalid-kind path.
    store = _mixed_store()
    proxy = CountingDict(store._memories)
    store._memories = proxy
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(store)
    proxy.reset()

    out = bridge.handle_memory_search({"query": "memory", "types": ["banana"]})

    assert out["count"] == 0
    assert proxy.values_calls == 0
    assert proxy.getitem_calls == 0


def test_partial_invalid_kinds_filter_by_valid_and_report_invalid():
    # "decision" is valid, "banana" is not: filter by decision, report banana.
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(_mixed_store())
    out = bridge.handle_memory_search(
        {"query": "memory", "types": ["decision", "banana"]}
    )
    assert out["results"]
    assert all(r["type"] == "decision" for r in out["results"])
    assert out.get("invalid_kinds") == ["banana"]


def test_valid_but_absent_kind_returns_empty_without_scan():
    # A valid kind with zero stored memories: empty, and no full scan.
    store = MemoryStore(tempfile.mkdtemp())
    store.add(Memory(content="only a note", memory_type=MemoryType.NOTE))
    store.get_by_type(MemoryType.NOTE)  # force load
    proxy = CountingDict(store._memories)
    store._memories = proxy
    proxy.reset()

    got = store.get_by_type(MemoryType.SUMMARY)  # none exist

    assert got == []
    assert proxy.values_calls == 0
    assert proxy.getitem_calls == 0


# --------------------------------------------------------------------------
# Back-compat — recall with no kind still defaults to decisions
# --------------------------------------------------------------------------

def test_recall_default_still_returns_decisions_only():
    mem = _synapse_over(_mixed_store())
    recalled = mem.recall("memory", limit=100)  # no kinds -> decisions
    assert recalled
    assert all(m.memory_type == MemoryType.DECISION for m in recalled)


def test_handler_recall_default_is_decisions_prose_only():
    # Recall stays PROSE-ONLY (SEAM-C tripwire in test_prst_network_persistence):
    # a match is exactly {id, summary, content, date}, no structural keys. The
    # kind-filter routing is unaffected -- only the response shape is pinned.
    store = MemoryStore(tempfile.mkdtemp())
    store.add(Memory(content="**Decision:** rim light warmer\n**Reasoning:** client wanted warmth",
                     memory_type=MemoryType.DECISION, summary="rim warmer"))
    bridge = SynapseBridge()
    bridge._synapse = _synapse_over(store)
    out = bridge.handle_memory_recall({"query": "rim"})
    assert out["found"] is True
    assert set(out["matches"][0]) == {"id", "summary", "content", "date"}
    for key in ("type", "fields", "nodes", "wires", "parms", "graph", "network"):
        assert key not in out["matches"][0]


def test_handler_search_carries_typed_fields_of_the_prim():
    # The STRUCTURED typed-field view lives on synapse_search (not recall).
    store = MemoryStore(tempfile.mkdtemp())
    mem = _synapse_over(store)
    mem.decision("rim light warmer", "client wanted warmth",
                 alternatives=["cooler", "neutral"])
    bridge = SynapseBridge()
    bridge._synapse = mem
    out = bridge.handle_memory_search({"query": "rim", "types": ["decision"]})
    assert out["results"]
    r0 = out["results"][0]
    assert r0["type"] == "decision"
    assert r0["fields"] == {
        "reasoning": "client wanted warmth",
        "alternatives": ["cooler", "neutral"],
    }
