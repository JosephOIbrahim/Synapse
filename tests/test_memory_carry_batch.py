"""BP12 item 1, the save freeze, found at the v5.85.0 release (2026-09-28).

The first save of an untitled scene carries every unsaved record into the new
scene's store (memory_lifecycle._copy_records). Each record paid a strict scan,
a full engine snapshot and a full cortex_root.usda save on Moneta, and a full
memory.jsonl rewrite on JSONL, so the carry grew with the square of the record
count: 1,458 records froze Houdini for about 7 minutes. Measured before the fix
with HashEmbedder on Moneta: 400 records took 14.1 s, with 404 snapshots and
405 scans. The carry is now one checked batch, and its checkpoints stay
constant however many records travel.
"""
import pytest

from synapse.memory import store as module
from synapse.memory.models import Memory, MemoryType
from test_memory_lifecycle import payloads, remember, saved, seat  # noqa: F401  (seat is a fixture)

N = 30


def _count_calls(monkeypatch, cls, name, counts, key):
    real = getattr(cls, name)

    def counting(self, *args, **kwargs):
        counts[key] += 1
        return real(self, *args, **kwargs)

    monkeypatch.setattr(cls, name, counting)


def _memory(text):
    return Memory(content=text, memory_type=MemoryType.DECISION, hip_file="untitled.hip")


@pytest.mark.parametrize("seat", ["jsonl", "moneta"], indirect=True)
def test_first_save_checkpoints_stay_constant(seat, monkeypatch):
    owner = module.get_synapse_memory()
    records = [remember(owner, seat.hip.current, f"note {i}") for i in range(N)]
    counts = {"save": 0, "scan": 0, "cortex": 0}
    store_type = type(owner.store)
    _count_calls(monkeypatch, store_type, "save", counts, "save")
    if hasattr(store_type, "_iter_memories"):
        _count_calls(monkeypatch, store_type, "_iter_memories", counts, "scan")
    from synapse.memory import moneta_runtime
    _count_calls(monkeypatch, moneta_runtime.UsdCortexStore, "_save", counts, "cortex")

    hip = saved(seat.root / "show" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    seat.hip.fire("AfterSave", hip)

    rebound = module.get_synapse_memory()
    assert rebound.storage_dir == hip.parent / ".synapse"
    assert payloads(rebound) == {m.id: m.to_json() for m in records}
    # Before the fix each count was N plus a handful.
    assert counts["save"] < 10, counts
    assert counts["scan"] < 10, counts
    assert counts["cortex"] < 10, counts


@pytest.mark.parametrize("seat", ["moneta"], indirect=True)
def test_failed_carry_publishes_nothing_and_the_retry_completes(seat, monkeypatch):
    from synapse.host import memory_lifecycle as lifecycle
    from synapse.memory.embedding import HashEmbedder

    owner = module.get_synapse_memory()
    records = [remember(owner, seat.hip.current, f"note {i}") for i in range(N)]
    hip = saved(seat.root / "saved" / "a.hip")
    seat.values["JOB"] = str(hip.parent)
    real = HashEmbedder.embed
    calls = {"n": 0}

    def flaky(self, text):
        calls["n"] += 1
        if calls["n"] == N // 2:
            raise OSError("embedder lost halfway through the carry")
        return real(self, text)

    with monkeypatch.context() as patch:
        patch.setattr(HashEmbedder, "embed", flaky)
        seat.hip.fire("AfterSave", hip)
        assert module._global_synapse is owner  # nothing was published
    assert calls["n"] == N // 2  # the failure landed mid-batch

    repaired = lifecycle.ensure_current_memory()
    assert repaired.storage_dir == hip.parent / ".synapse"
    assert payloads(repaired) == {m.id: m.to_json() for m in records}
    assert len(repaired.store.all()) == N  # the retry deposited no duplicates


@pytest.mark.parametrize("seat", ["jsonl", "moneta"], indirect=True)
def test_batch_refuses_a_conflict_before_inserting_anything(seat):
    owner = module.get_synapse_memory()
    kept = remember(owner, seat.hip.current, "kept as written")
    changed = Memory.from_json(kept.to_json())
    changed.content = "a different payload under the same identity"
    fresh = _memory("would have been new")
    before = payloads(owner)
    with pytest.raises(ValueError):
        owner.store.add_durable_many_if_absent([fresh, changed])
    assert payloads(owner) == before

    twin = Memory.from_json(fresh.to_json())
    assert owner.store.add_durable_many_if_absent([fresh, twin, kept]) == 1
    assert payloads(owner) == {**before, fresh.id: fresh.to_json()}


def test_cortex_saves_once_per_deferred_batch(tmp_path, monkeypatch):
    from synapse.memory import moneta_runtime

    cortex = moneta_runtime.UsdCortexStore(str(tmp_path / ".moneta"))
    if not cortex.available:
        pytest.skip("pxr is unavailable, so the cortex is disabled")
    counts = {"cortex": 0}
    _count_calls(monkeypatch, moneta_runtime.UsdCortexStore, "_save", counts, "cortex")
    with cortex.deferred_save():
        for i in range(5):
            cortex.write("decision", f"id{i}", "{}")
    assert counts["cortex"] == 1
    cortex.write("decision", "id5", "{}")
    assert counts["cortex"] == 2  # outside the context every write still saves
    assert len(cortex.query(kind="decision")) == 6
