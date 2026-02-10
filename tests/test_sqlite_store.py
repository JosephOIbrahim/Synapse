"""
SQLite Memory Store Tests

Tests that SQLiteMemoryStore is a drop-in replacement for MemoryStore.
Covers: CRUD, search (text + tag + keyword + type), links, FTS5,
concurrent access, factory selection, He2025 ordering.
"""

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import patch

# Bootstrap package imports
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# Need hou stub for store.py import chain
if "hou" not in sys.modules:
    import types as _types
    sys.modules["hou"] = _types.ModuleType("hou")

from synapse.memory.models import (
    Memory,
    MemoryType,
    MemoryTier,
    MemoryLink,
    LinkType,
    MemoryQuery,
    MemorySearchResult,
)
from synapse.memory.sqlite_store import SQLiteMemoryStore, create_memory_store


# =============================================================================
# HELPERS
# =============================================================================

def _make_store(tmp_path: Path) -> SQLiteMemoryStore:
    """Create a SQLiteMemoryStore in a temp directory (sync init)."""
    return SQLiteMemoryStore(tmp_path, background_load=False)


def _make_memory(
    content: str = "test content",
    memory_type: MemoryType = MemoryType.NOTE,
    tags: list = None,
    keywords: list = None,
    source: str = "user",
) -> Memory:
    return Memory(
        content=content,
        memory_type=memory_type,
        tags=tags or [],
        keywords=keywords or [],
        source=source,
    )


# =============================================================================
# BASIC CRUD
# =============================================================================

class TestSQLiteCRUD:
    """Core create/read/update/delete operations."""

    def test_add_and_get(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("hello world")
        mid = store.add(mem)
        assert mid == mem.id

        got = store.get(mid)
        assert got is not None
        assert got.content == "hello world"
        assert got.id == mid

    def test_get_nonexistent(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.get("nonexistent") is None

    def test_update(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("original")
        store.add(mem)

        mem.content = "updated"
        store.update(mem)

        got = store.get(mem.id)
        assert got.content == "updated"

    def test_update_nonexistent_is_noop(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("ghost")
        mem.id = "nonexistent_id"
        store.update(mem)  # Should not raise
        assert store.get("nonexistent_id") is None

    def test_delete(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("doomed")
        store.add(mem)
        assert store.delete(mem.id) is True
        assert store.get(mem.id) is None

    def test_delete_nonexistent(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.delete("nope") is False

    def test_count(self, tmp_path):
        store = _make_store(tmp_path)
        assert store.count() == 0
        store.add(_make_memory("one"))
        store.add(_make_memory("two"))
        assert store.count() == 2

    def test_all(self, tmp_path):
        store = _make_store(tmp_path)
        store.add(_make_memory("alpha"))
        store.add(_make_memory("beta"))
        all_mems = store.all()
        assert len(all_mems) == 2
        contents = {m.content for m in all_mems}
        assert "alpha" in contents
        assert "beta" in contents

    def test_clear(self, tmp_path):
        store = _make_store(tmp_path)
        store.add(_make_memory("temp"))
        store.clear()
        assert store.count() == 0
        assert store.all() == []


# =============================================================================
# MEMORY FIELDS
# =============================================================================

class TestSQLiteFields:
    """Verify all Memory fields survive round-trip through SQLite."""

    def test_full_roundtrip(self, tmp_path):
        store = _make_store(tmp_path)
        mem = Memory(
            content="Full field test",
            memory_type=MemoryType.DECISION,
            tier=MemoryTier.SHOW,
            summary="A decision was made",
            keywords=["lighting", "exposure"],
            tags=["key-light", "review"],
            hip_file="SH010_fx_v003.hip",
            hip_version=3,
            frame=42,
            frame_range=(1, 100),
            node_paths=["/obj/geo1", "/stage/lights"],
            source="ai",
            agent_id="agent-001",
            confidence=0.95,
            is_consolidated=False,
            consolidated_into=None,
        )
        store.add(mem)

        got = store.get(mem.id)
        assert got.content == "Full field test"
        assert got.memory_type == MemoryType.DECISION
        assert got.tier == MemoryTier.SHOW
        assert got.summary == "A decision was made"
        assert got.keywords == ["exposure", "lighting"]  # sorted in storage
        assert set(got.tags) == {"key-light", "review"}
        assert got.hip_file == "SH010_fx_v003.hip"
        assert got.hip_version == 3
        assert got.frame == 42
        assert got.frame_range == (1, 100)
        assert got.node_paths == ["/obj/geo1", "/stage/lights"]
        assert got.source == "ai"
        assert got.agent_id == "agent-001"
        assert got.confidence == 0.95
        assert got.is_consolidated is False

    def test_embedding_roundtrip(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("with embedding")
        mem.embedding = [0.1, 0.2, 0.3, 0.4]
        store.add(mem)

        got = store.get(mem.id)
        assert got.embedding == [0.1, 0.2, 0.3, 0.4]

    def test_none_optional_fields(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("minimal")
        store.add(mem)

        got = store.get(mem.id)
        assert got.frame is None
        assert got.frame_range is None
        assert got.embedding is None
        assert got.consolidated_into is None


# =============================================================================
# LINKS
# =============================================================================

class TestSQLiteLinks:
    """Link persistence and retrieval."""

    def test_add_with_links(self, tmp_path):
        store = _make_store(tmp_path)
        target = _make_memory("target")
        store.add(target)

        source = _make_memory("source")
        source.add_link(target.id, LinkType.SUPPORTS, "backs up the target")
        store.add(source)

        got = store.get(source.id)
        assert len(got.links) == 1
        assert got.links[0].target_id == target.id
        assert got.links[0].link_type == LinkType.SUPPORTS
        assert got.links[0].reason == "backs up the target"

    def test_get_linked(self, tmp_path):
        store = _make_store(tmp_path)
        t1 = _make_memory("linked-target-1")
        t2 = _make_memory("linked-target-2")
        store.add(t1)
        store.add(t2)

        source = _make_memory("the source")
        source.add_link(t1.id, LinkType.RELATED)
        source.add_link(t2.id, LinkType.DEPENDS_ON)
        store.add(source)

        linked = store.get_linked(source.id)
        linked_ids = {m.id for m in linked}
        assert t1.id in linked_ids
        assert t2.id in linked_ids


# =============================================================================
# SEARCH
# =============================================================================

class TestSQLiteSearch:
    """Search with text, tags, keywords, types, and filters."""

    def _seed(self, store):
        """Seed store with test data."""
        store.add(Memory(
            content="Key light exposure adjusted to 5.0 stops",
            memory_type=MemoryType.ACTION,
            tags=["lighting", "key-light"],
            keywords=["exposure", "stops"],
            source="ai",
        ))
        store.add(Memory(
            content="Decided to use Karma XPU for all renders",
            memory_type=MemoryType.DECISION,
            tags=["rendering", "karma"],
            keywords=["karma", "xpu", "render"],
            source="user",
        ))
        store.add(Memory(
            content="Pyro source scatter count set to 50000",
            memory_type=MemoryType.ACTION,
            tags=["fx", "pyro"],
            keywords=["pyro", "scatter"],
            source="auto",
        ))

    def test_search_by_text(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(text="Karma XPU"))
        assert len(results) >= 1
        assert any("Karma XPU" in r.memory.content for r in results)

    def test_search_by_tag(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(tags=["lighting"]))
        assert len(results) == 1
        assert results[0].memory.tags == ["key-light", "lighting"]

    def test_search_by_keyword(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(keywords=["pyro"]))
        assert len(results) == 1
        assert "pyro" in results[0].memory.keywords

    def test_search_by_type(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(memory_types=[MemoryType.DECISION]))
        assert len(results) == 1
        assert results[0].memory.memory_type == MemoryType.DECISION

    def test_search_by_source(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(source="auto"))
        assert len(results) == 1
        assert results[0].memory.source == "auto"

    def test_search_no_criteria_returns_all(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery())
        assert len(results) == 3

    def test_search_limit(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(limit=1))
        assert len(results) == 1

    def test_search_combined_filters(self, tmp_path):
        store = _make_store(tmp_path)
        self._seed(store)

        results = store.search(MemoryQuery(
            memory_types=[MemoryType.ACTION],
            tags=["fx"],
        ))
        assert len(results) == 1
        assert "pyro" in results[0].memory.content.lower()

    def test_search_consolidated_excluded_by_default(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("old note")
        mem.is_consolidated = True
        store.add(mem)

        results = store.search(MemoryQuery())
        assert len(results) == 0

    def test_search_consolidated_included(self, tmp_path):
        store = _make_store(tmp_path)
        mem = _make_memory("old note")
        mem.is_consolidated = True
        store.add(mem)

        results = store.search(MemoryQuery(include_consolidated=True))
        assert len(results) == 1


# =============================================================================
# INDEXED LOOKUPS
# =============================================================================

class TestSQLiteIndexedLookups:
    """get_by_type, get_by_tag, get_recent."""

    def test_get_by_type(self, tmp_path):
        store = _make_store(tmp_path)
        store.add(_make_memory("note1", memory_type=MemoryType.NOTE))
        store.add(_make_memory("dec1", memory_type=MemoryType.DECISION))
        store.add(_make_memory("note2", memory_type=MemoryType.NOTE))

        notes = store.get_by_type(MemoryType.NOTE)
        assert len(notes) == 2
        assert all(m.memory_type == MemoryType.NOTE for m in notes)

    def test_get_by_tag(self, tmp_path):
        store = _make_store(tmp_path)
        store.add(_make_memory("a", tags=["lighting"]))
        store.add(_make_memory("b", tags=["fx"]))
        store.add(_make_memory("c", tags=["lighting", "fx"]))

        lighting = store.get_by_tag("lighting")
        assert len(lighting) == 2

    def test_get_recent(self, tmp_path):
        store = _make_store(tmp_path)
        # Add with distinct timestamps
        for i in range(5):
            m = _make_memory(f"mem-{i}")
            m.created_at = f"2026-02-10T00:00:0{i}Z"
            store.add(m)

        recent = store.get_recent(3)
        assert len(recent) == 3
        # Most recent first
        assert recent[0].created_at > recent[1].created_at
        assert recent[1].created_at > recent[2].created_at


# =============================================================================
# HE2025 DETERMINISM
# =============================================================================

class TestSQLiteDeterminism:
    """He2025 compliance: deterministic ordering, sort_keys in JSON."""

    def test_search_order_deterministic(self, tmp_path):
        """Same query always returns same order."""
        store = _make_store(tmp_path)
        for i in range(10):
            store.add(_make_memory(f"item-{i:03d}"))

        r1 = store.search(MemoryQuery())
        r2 = store.search(MemoryQuery())
        assert [r.memory.id for r in r1] == [r.memory.id for r in r2]

    def test_all_order_deterministic(self, tmp_path):
        """all() returns consistent ordering."""
        store = _make_store(tmp_path)
        for c in ["charlie", "alpha", "bravo"]:
            store.add(_make_memory(c))

        ids1 = [m.id for m in store.all()]
        ids2 = [m.id for m in store.all()]
        assert ids1 == ids2

    def test_json_sort_keys(self, tmp_path):
        """Verify stored JSON uses sort_keys."""
        store = _make_store(tmp_path)
        mem = _make_memory("test", tags=["zebra", "alpha"], keywords=["beta", "alpha"])
        store.add(mem)

        got = store.get(mem.id)
        # Keywords and tags are sorted in storage
        assert got.keywords == ["alpha", "beta"]
        assert got.tags == ["alpha", "zebra"]


# =============================================================================
# CONCURRENCY
# =============================================================================

class TestSQLiteConcurrency:
    """Thread safety under concurrent access."""

    def test_concurrent_writes(self, tmp_path):
        """50 threads writing simultaneously."""
        store = _make_store(tmp_path)
        errors = []

        def writer(idx):
            try:
                store.add(_make_memory(f"concurrent-{idx}"))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert store.count() == 50

    def test_concurrent_read_write(self, tmp_path):
        """Readers and writers interleaved."""
        store = _make_store(tmp_path)
        # Pre-seed
        for i in range(20):
            store.add(_make_memory(f"seed-{i}"))

        errors = []
        read_counts = []

        def reader():
            try:
                count = store.count()
                read_counts.append(count)
            except Exception as e:
                errors.append(e)

        def writer(idx):
            try:
                store.add(_make_memory(f"new-{idx}"))
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=reader))
            threads.append(threading.Thread(target=writer, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        assert store.count() == 40  # 20 seed + 20 new


# =============================================================================
# FACTORY
# =============================================================================

class TestFactory:
    """create_memory_store() factory selection."""

    def test_default_is_jsonl(self, tmp_path):
        with patch.dict(os.environ, {"SYNAPSE_MEMORY_BACKEND": "jsonl"}):
            store = create_memory_store(tmp_path, background_load=False)
            from synapse.memory.store import MemoryStore
            assert isinstance(store, MemoryStore)

    def test_sqlite_selection(self, tmp_path):
        with patch.dict(os.environ, {"SYNAPSE_MEMORY_BACKEND": "sqlite"}):
            store = create_memory_store(tmp_path, background_load=False)
            assert isinstance(store, SQLiteMemoryStore)

    def test_no_env_defaults_to_jsonl(self, tmp_path):
        with patch.dict(os.environ, {}, clear=False):
            env = dict(os.environ)
            env.pop("SYNAPSE_MEMORY_BACKEND", None)
            with patch.dict(os.environ, env, clear=True):
                store = create_memory_store(tmp_path, background_load=False)
                from synapse.memory.store import MemoryStore
                assert isinstance(store, MemoryStore)


# =============================================================================
# PERSISTENCE
# =============================================================================

class TestSQLitePersistence:
    """Data survives store recreation (reopening the DB file)."""

    def test_persistence_across_instances(self, tmp_path):
        store1 = _make_store(tmp_path)
        store1.add(_make_memory("persist me"))
        del store1

        store2 = _make_store(tmp_path)
        assert store2.count() == 1
        mems = store2.all()
        assert mems[0].content == "persist me"

    def test_links_persist(self, tmp_path):
        store1 = _make_store(tmp_path)
        target = _make_memory("target")
        store1.add(target)
        source = _make_memory("source")
        source.add_link(target.id, LinkType.SUPPORTS, "evidence")
        store1.add(source)
        del store1

        store2 = _make_store(tmp_path)
        got = store2.get(source.id)
        assert len(got.links) == 1
        assert got.links[0].target_id == target.id

    def test_tags_persist(self, tmp_path):
        store1 = _make_store(tmp_path)
        store1.add(_make_memory("tagged", tags=["lighting", "karma"]))
        del store1

        store2 = _make_store(tmp_path)
        results = store2.get_by_tag("lighting")
        assert len(results) == 1


# =============================================================================
# FLUSH AND SAVE ARE NO-OPS
# =============================================================================

class TestSQLiteNoOps:
    """flush() and save() don't raise."""

    def test_flush_noop(self, tmp_path):
        store = _make_store(tmp_path)
        store.flush()  # Should not raise

    def test_save_noop(self, tmp_path):
        store = _make_store(tmp_path)
        store.save()  # Should not raise
