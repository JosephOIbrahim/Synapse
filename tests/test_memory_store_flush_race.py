"""BP12 item 21: the flusher's append cannot land on a file save() has replaced.

_flush_writes() takes the buffered lines, then appends them to memory.jsonl. If save() replaced the
file in that gap, the append landed on the new file: a duplicate line after an ordinary save, or a
cleared record coming back after clear(). The tests pause the flusher inside its append, run save()
or clear() on another thread, and then let the append finish.
"""
import builtins
import threading

from synapse.memory.models import Memory, MemoryType
from synapse.memory.store import MemoryStore


def _note(text):
    return Memory(content=text, memory_type=MemoryType.DECISION, hip_file="untitled.hip")


def _quiet_store(root):
    store = MemoryStore(root, background_load=False)
    store._flusher_running = False       # the test drives every flush itself
    store._flush_event.set()
    store._flusher.join(5)
    assert not store._flusher.is_alive(), "the background flusher is still running"
    return store


class _PausedAppend:
    """Make the first 'a'-mode open of memory_file wait, so the flusher stalls mid-append."""

    def __init__(self, monkeypatch, path):
        self.entered = threading.Event()
        self.release = threading.Event()
        real = builtins.open

        def fake(file, mode="r", *a, **kw):
            if mode == "a" and str(file) == str(path) and not self.entered.is_set():
                self.entered.set()
                self.release.wait(10)
            return real(file, mode, *a, **kw)

        monkeypatch.setattr(builtins, "open", fake)


def _run(fn):
    th = threading.Thread(target=fn, daemon=True)
    th.start()
    return th


def test_save_during_an_append_does_not_duplicate_the_line(tmp_path, monkeypatch):
    store = _quiet_store(tmp_path / ".synapse")
    store.add(_note("only once"))
    pause = _PausedAppend(monkeypatch, store.memory_file)

    flusher = _run(store._flush_writes)
    assert pause.entered.wait(10), "the flusher never reached its append"
    saver = _run(store.save)
    saver.join(0.5)
    assert saver.is_alive(), "save() did not wait for the in-flight append"
    pause.release.set()
    flusher.join(10)
    saver.join(10)
    assert not flusher.is_alive() and not saver.is_alive()

    lines = [l for l in store.memory_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 1, f"the record was written {len(lines)} times"
    assert len(MemoryStore(tmp_path / ".synapse", background_load=False).all()) == 1


def test_clear_during_an_append_leaves_the_store_empty(tmp_path, monkeypatch):
    store = _quiet_store(tmp_path / ".synapse")
    store.add(_note("to be cleared"))
    pause = _PausedAppend(monkeypatch, store.memory_file)

    flusher = _run(store._flush_writes)
    assert pause.entered.wait(10), "the flusher never reached its append"
    clearer = _run(store.clear)
    clearer.join(0.5)
    assert clearer.is_alive(), "clear() did not wait for the in-flight append"
    pause.release.set()
    flusher.join(10)
    clearer.join(10)
    assert not flusher.is_alive() and not clearer.is_alive()

    assert store.all() == []
    assert MemoryStore(tmp_path / ".synapse", background_load=False).all() == [], \
        "a cleared record came back from an append that was already in flight"


def test_a_plain_add_flush_save_cycle_still_round_trips(tmp_path):
    store = _quiet_store(tmp_path / ".synapse")
    for i in range(3):
        store.add(_note(f"n{i}"))
    store.flush()
    store.save()
    store.add(_note("after"))
    store.flush()
    assert len(MemoryStore(tmp_path / ".synapse", background_load=False).all()) == 4
