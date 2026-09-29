"""BP12 item 9, found at the v5.85.0 release (2026-09-28).

MemoryStore.clear() called save() while holding the store's writer lock. save()
takes the same lock, and ReadWriteLock is not reentrant, so every clear() on a
JSONL store blocked forever. The panel's Clear All Memories button calls it on
Houdini's main thread.
"""
import threading

from synapse.memory.models import Memory, MemoryType
from synapse.memory.store import MemoryStore


def _note(text):
    return Memory(content=text, memory_type=MemoryType.DECISION, hip_file="untitled.hip")


def test_clear_returns_and_leaves_an_empty_store_on_disk(tmp_path):
    store = MemoryStore(tmp_path / ".synapse", background_load=False)
    for i in range(3):
        store.add(_note(f"note {i}"))
    store.save()
    store.add(_note("still in the append buffer"))

    finished = threading.Event()

    def run():
        store.clear()
        finished.set()

    threading.Thread(target=run, daemon=True).start()
    assert finished.wait(10), "clear() did not return: it blocked on the store's own writer lock"
    assert store.all() == []
    store.flush()  # nothing buffered may resurrect a cleared record

    reopened = MemoryStore(tmp_path / ".synapse", background_load=False)
    assert reopened.all() == []
