"""MemoryStore.save() drains the append buffer, so a flush cannot duplicate lines.

Found by the Windows CI job on 2026-09-28 (run 36492617056): add() buffers a line
for the background flusher, save() rewrites the whole file from memory, and the
next flush appended the buffered lines again. tests/test_backfill.py saw its
seeded source grow from 7 lines to 14 while the backfill ran. These tests drive
the flush directly, so they do not depend on the flusher's 2 s timing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from synapse.memory.models import Memory, MemoryType  # noqa: E402
from synapse.memory.store import MemoryStore  # noqa: E402


def _store(tmp_path):
    store = MemoryStore(tmp_path / ".synapse")
    store._wait_loaded()
    return store


def test_flush_after_save_does_not_duplicate_buffered_adds(tmp_path):
    store = _store(tmp_path)
    try:
        for i in range(7):
            store.add(Memory(content=f"note {i}", memory_type=MemoryType.NOTE))
        store.save()
        before = store.memory_file.read_bytes()
        store._flush_writes()  # what the background flusher does on its next tick
        assert store.memory_file.read_bytes() == before
        assert len(before.splitlines()) == 7
    finally:
        store._flusher_running = False


def test_adds_after_a_save_still_reach_disk(tmp_path):
    store = _store(tmp_path)
    try:
        store.add(Memory(content="first", memory_type=MemoryType.NOTE))
        store.save()
        store.add(Memory(content="second", memory_type=MemoryType.NOTE))
        store._flush_writes()
        assert len(store.memory_file.read_bytes().splitlines()) == 2
    finally:
        store._flusher_running = False
