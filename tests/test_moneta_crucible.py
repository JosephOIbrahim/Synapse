"""Mile 7 — CRUCIBLE L4 adversarial pins for the Moneta backend.

These encode the findings of the Mile 7 adversarial fan-out. Two were real
defects and are FIXED here (protected-quota silent demotion; corrupt-snapshot
startup-killer); the rest pin documented behavior so any future drift fails
loud. Never weakened — fix-forward only.
"""

import json
import queue
import sys
import threading
import time
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import moneta_runtime as mr  # noqa: E402
from synapse.memory.embedding import HashEmbedder  # noqa: E402
from synapse.memory.models import (  # noqa: E402
    LinkType, Memory, MemoryQuery, MemoryTier, MemoryType,
)
from synapse.memory.store import MemoryStore  # noqa: E402

pytestmark = pytest.mark.skipif(
    not mr.moneta_available(),
    reason=f"Moneta not importable (set $MONETA_SRC). Last error: {mr.import_error()}",
)

DIM = 256


def _eph(**cfg):
    from synapse.memory.moneta_store import MonetaBackedStore
    return MonetaBackedStore(mr.make_ephemeral(embedding_dim=DIM, **cfg), HashEmbedder(dim=DIM))


def _backdate(store, seconds_ago=10_000):
    ecs = store._handle.ecs
    past = time.time() - seconds_ago
    for i in range(len(ecs._last_evaluated)):
        ecs._last_evaluated[i] = past


# --------------------------------------------------------------------------- #
# decay / consolidation (opt-in; protected set survives)
# --------------------------------------------------------------------------- #

def test_unprotected_memory_pruned_only_on_explicit_sleep_pass():
    s = _eph(half_life_seconds=60.0)
    s.add(Memory(content="routine note", memory_type=MemoryType.NOTE))
    s.add(Memory(content="an action", memory_type=MemoryType.ACTION))
    assert s.count() == 2
    # No pruning happens on normal add/read — only when consolidation is asked for.
    assert s.count() == 2
    _backdate(s)
    result = s.run_sleep_pass()  # explicit, opt-in
    assert result.pruned == 2
    assert s.count() == 0  # documented: decay expires unprotected memories


def test_decision_survives_many_sleep_passes():
    s = _eph(half_life_seconds=60.0)
    s.add(Memory(content="load-bearing decision", memory_type=MemoryType.DECISION))
    for _ in range(25):
        _backdate(s)
        s.run_sleep_pass()
    assert s.count() == 1
    assert s.get_by_type(MemoryType.DECISION)[0].content == "load-bearing decision"


def test_protected_quota_does_not_silently_demote(tmp_path):
    # FIX VERIFICATION: from_storage_dir raises quota_override high, so the 101st
    # protected memory is NOT silently demoted to prunable (CRUCIBLE finding 2).
    from synapse.memory.moneta_store import MonetaBackedStore
    s = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        for i in range(101):
            s.add(Memory(content=f"decision {i}", memory_type=MemoryType.DECISION))
        assert s._handle.ecs.count_protected() == 101  # all pinned, none demoted
        _backdate(s)
        s.run_sleep_pass()
        assert s.count() == 101  # none pruned
    finally:
        s.close()


def test_get_recent_order_stable_under_decay():
    s = _eph(half_life_seconds=60.0)
    for i in range(4):
        s.add(Memory(content=f"m{i}", memory_type=MemoryType.DECISION,
                     created_at=f"2026-01-0{i + 1}T00:00:00Z"))
    before = [m.id for m in s.get_recent(10)]
    _backdate(s)
    s.run_sleep_pass()
    after = [m.id for m in s.get_recent(10)]
    assert before == after  # decay sorts on created_at, never reorders


# --------------------------------------------------------------------------- #
# corrupt-snapshot recovery (FIX VERIFICATION)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("garbage", [
    "", "{not json", "[1,2,3]", '{"rows": "nope"}',
    '{"snapshot_version":1,"rows":[{"entity_id":"x"}]}',  # row missing required keys
])
def test_corrupt_snapshot_is_quarantined_not_fatal(tmp_path, garbage):
    from synapse.memory.moneta_store import MonetaBackedStore
    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    s1.add(Memory(content="will be stranded", memory_type=MemoryType.DECISION))
    s1.save()
    s1.close()

    snap = tmp_path / "proj" / ".moneta" / "snapshot.json"
    snap.write_text(garbage, encoding="utf-8")

    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")  # must not crash
    try:
        assert s2.count() == 0  # fresh start
        quarantined = list((tmp_path / "proj" / ".moneta").glob("snapshot.json.corrupt-*"))
        assert quarantined, "corrupt snapshot must be preserved, not abandoned"
    finally:
        s2.close()


def test_valid_snapshot_is_not_quarantined(tmp_path):
    from synapse.memory.moneta_store import MonetaBackedStore
    s1 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    s1.add(Memory(content="survives", memory_type=MemoryType.DECISION))
    s1.save()
    s1.close()
    s2 = MonetaBackedStore.from_storage_dir(tmp_path / "proj")
    try:
        assert s2.count() == 1  # clean reload, nothing quarantined
        assert not list((tmp_path / "proj" / ".moneta").glob("snapshot.json.corrupt-*"))
    finally:
        s2.close()


# --------------------------------------------------------------------------- #
# concurrency / single-writer (FC4 seam)
# --------------------------------------------------------------------------- #

def test_concurrent_add_is_lossless_under_gil():
    # Append-only deposits are atomic under the GIL; pin it so a regression
    # (or a free-threaded build) surfaces.
    s = _eph()
    n_threads, per = 8, 200

    def worker(t):
        for i in range(per):
            s.add(Memory(content=f"t{t}-i{i}", memory_type=MemoryType.NOTE))

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert s.count() == n_threads * per


def test_serialized_writer_is_lossless():
    # The shape SYNAPSE's async server must use: all mutations funneled to one
    # writer. Single-writer access is correct (the supported contract).
    s = _eph()
    q = queue.Queue()
    for i in range(500):
        q.put(Memory(content=f"m{i}", memory_type=MemoryType.NOTE))
    while not q.empty():
        s.add(q.get())
    assert s.count() == 500


# --------------------------------------------------------------------------- #
# payload integrity / edges
# --------------------------------------------------------------------------- #

def test_hostile_payload_round_trips_exactly():
    s = _eph()
    m = Memory(
        content='{"x":1}\n\t"q" café \U0001f9e0 \\ \r end',
        memory_type=MemoryType.DECISION,
        tags=['a"b', 'c\\d', 'café'],
        keywords=['k\\1'],
        frame_range=(1001, 1095),
        confidence=0.333333333333,
    )
    m.add_link("mem_target", LinkType.SUPERSEDES, reason="r")
    s.add(m)
    assert s.get(m.id).to_dict() == m.to_dict()  # every field, exact


def test_empty_content_is_enumerable_not_lost():
    s = _eph()
    m = Memory(content="", memory_type=MemoryType.NOTE)
    s.add(m)
    # Zero-vector embedding => invisible to a future vector query, but every
    # enumeration read must still surface it (no silent loss).
    assert s.get(m.id) is not None
    assert any(x.id == m.id for x in s.get_by_type(MemoryType.NOTE))
    assert any(r.memory.id == m.id for r in s.search(MemoryQuery()))


def test_duplicate_content_id_collision_is_documented():
    # Upstream models.py: Memory.id hashes content+type (created_at empty at id
    # time), so same content+type collides. Moneta appends both rows; get()
    # returns the first. Pinned so a future models.py fix is a deliberate change.
    s = _eph()
    a = Memory(content="dup", memory_type=MemoryType.NOTE)
    b = Memory(content="dup", memory_type=MemoryType.NOTE)
    assert a.id == b.id
    s.add(a)
    s.add(b)
    assert s.count() == 2
    assert len([m for m in s.all() if m.id == a.id]) == 2
    assert s.get(a.id) is not None


def test_get_by_tag_is_raw_case_sensitive():
    s = _eph()
    s.add(Memory(content="c", memory_type=MemoryType.NOTE, tags=["MixedCase"]))
    assert len(s.get_by_tag("MixedCase")) == 1
    assert len(s.get_by_tag("mixedcase")) == 0  # raw match, matching search() semantics


@pytest.mark.parametrize("q", [
    MemoryQuery(text="", limit=50),
    MemoryQuery(text="café", limit=50),
    MemoryQuery(text="hello", limit=10 ** 9),
    MemoryQuery(text="hello", limit=0),
    MemoryQuery(text="zzz-nothing-matches", limit=50),
    MemoryQuery(limit=50),
])
def test_search_edge_query_parity_with_jsonl(tmp_path, q):
    j = MemoryStore(tmp_path / ".synapse")
    s = _eph()
    corpus = [
        Memory(content="hello world", memory_type=MemoryType.NOTE, tags=["t1"]),
        Memory(content="café \U0001f9e0", memory_type=MemoryType.DECISION),
    ]
    for m in corpus:
        j.add(m)
        s.add(m)
    norm = lambda res: [(r.memory.id, round(r.score, 6)) for r in res]
    assert norm(s.search(q)) == norm(j.search(q))


# --------------------------------------------------------------------------- #
# isolation / flag hygiene
# --------------------------------------------------------------------------- #

def test_moneta_backend_never_fires_evolution(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory import evolution
    calls = []
    monkeypatch.setattr(evolution, "check_evolution", lambda *a, **k: calls.append(1) or {})
    from synapse.memory.store import SynapseMemory
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    try:
        for i in range(25):
            sm.add(content=f"m{i}", memory_type=MemoryType.NOTE)
        assert calls == []  # evolution.py is retired under the Moneta backend
    finally:
        sm.store.close()


@pytest.mark.parametrize("value,expect_moneta", [
    ("moneta", True), ("MONETA", True), (" moneta ", True),
    ("garbage", False), ("", False), ("JSONL", False),
])
def test_flag_hygiene(tmp_path, monkeypatch, value, expect_moneta):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", value)
    from synapse.memory.store import SynapseMemory
    from synapse.memory.moneta_store import MonetaBackedStore
    sm = SynapseMemory(project_path=str(tmp_path / f"proj_{abs(hash(value))}"))
    try:
        assert isinstance(sm.store, MonetaBackedStore) is expect_moneta
    finally:
        if hasattr(sm.store, "close"):
            sm.store.close()


def test_fallback_to_jsonl_when_moneta_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    from synapse.memory import moneta_runtime
    monkeypatch.setattr(moneta_runtime, "moneta_available", lambda: False)
    from synapse.memory.store import SynapseMemory
    sm = SynapseMemory(project_path=str(tmp_path / "proj"))
    assert isinstance(sm.store, MemoryStore)  # graceful, no crash
