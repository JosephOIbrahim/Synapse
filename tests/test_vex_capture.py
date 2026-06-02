"""Pins session-VEX capture (Mile 6 of the VEX-corpus goal).

A successful wrangle should become recall-able session memory: non-trivial only,
keyworded by its @attributes + functions, deduped by content hash, tagged for
recall. Standalone -- no hou, no Moneta required (a tiny in-memory fake store).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "python"))

from synapse.memory import vex_capture as vc  # noqa: E402
from synapse.memory.models import MemoryType, MemoryTier  # noqa: E402


class _FakeStore:
    """Minimal store: add() records, search() matches on MemoryQuery.tags."""

    def __init__(self):
        self.memories = []

    def add(self, memory):
        self.memories.append(memory)
        return memory.id

    def search(self, query):
        tags = set(getattr(query, "tags", []) or [])
        if not tags:
            return []
        return [m for m in self.memories if tags & set(m.tags)]


# --- triviality gate -------------------------------------------------------

def test_should_capture_rejects_trivial():
    assert not vc.should_capture("")
    assert not vc.should_capture("// just a comment")
    assert not vc.should_capture("@P;")  # too short
    assert not vc.should_capture("   \n  ")


def test_should_capture_accepts_real_wrangle():
    assert vc.should_capture("@Cd = chramp('ramp', @P.y);")
    assert vc.should_capture("f@mass = fit01(rand(@ptnum), 0.5, 2.0);")


# --- keyword extraction ----------------------------------------------------

def test_extract_keywords_picks_attrs_and_funcs():
    kws = vc.extract_keywords("v@up = normalize(@N); @Cd = set(@P.x, 0, 0);")
    assert "@up" in kws and "@N" in kws and "@Cd" in kws and "@P" in kws
    assert "normalize" in kws
    assert "set" not in kws  # stop-word func filtered


# --- memory shape ----------------------------------------------------------

def test_make_vex_memory_shape():
    mem = vc.make_vex_memory("@Cd = @P;\nf@d = length(@P);", {"run_over": "points", "node": "/obj/geo1/aw"})
    assert mem.memory_type == MemoryType.REFERENCE
    assert mem.tier == MemoryTier.SEQUENCE
    assert "vex" in mem.tags and "session" in mem.tags
    assert any(t.startswith("vexhash:") for t in mem.tags)
    assert mem.keywords  # non-empty trigger surface
    assert "```vex" in mem.content


# --- capture + dedup -------------------------------------------------------

def test_capture_writes_once_and_dedups():
    store = _FakeStore()
    code = "@Cd = chramp('ramp', @P.y); f@mass = rand(@ptnum);"
    mid = vc.capture_vex_pattern(store, code, {"run_over": "points"})
    assert mid is not None
    assert len(store.memories) == 1
    # Same snippet again -> deduped, no new entry.
    assert vc.capture_vex_pattern(store, code, {"run_over": "points"}) is None
    assert len(store.memories) == 1


def test_capture_skips_trivial():
    store = _FakeStore()
    assert vc.capture_vex_pattern(store, "// nope", {}) is None
    assert store.memories == []


def test_capture_survives_search_failure():
    """If the store's dedup search raises, capture still writes (best-effort)."""
    class _Flaky(_FakeStore):
        def search(self, query):
            raise RuntimeError("index down")

    store = _Flaky()
    mid = vc.capture_vex_pattern(store, "@Cd = @P; f@d = length(@N);", {})
    assert mid is not None and len(store.memories) == 1
