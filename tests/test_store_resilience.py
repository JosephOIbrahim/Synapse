"""Tests for MemoryStore resilience -- buffer restore, index integrity, flush ordering."""
import importlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import types
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

# Project paths
_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

# Stub hou module
if "hou" not in sys.modules:
    sys.modules["hou"] = types.ModuleType("hou")


class TestFlushResilience:
    """C3: Buffer restored on write failure."""

    def test_buffer_restored_on_write_failure(self, tmp_path):
        """If disk write fails, buffer lines are restored for retry."""
        # Import store module
        spec = importlib.util.spec_from_file_location(
            "synapse.memory.store", _base / "memory" / "store.py"
        )
        store_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store_mod)

        store = store_mod.MemoryStore(storage_dir=str(tmp_path))
        store._write_buffer = ['{"id": "1", "test": true}\n', '{"id": "2", "test": true}\n']

        # Patch open to raise on append
        original_open = open
        def failing_open(path, mode='r', **kwargs):
            if 'a' in mode:
                raise OSError("Disk full")
            return original_open(path, mode, **kwargs)

        with patch("builtins.open", side_effect=failing_open):
            store._flush_writes()

        # Buffer should be restored
        assert len(store._write_buffer) == 2

    def test_buffer_cleared_on_write_success(self, tmp_path):
        """Normal flush clears the buffer."""
        spec = importlib.util.spec_from_file_location(
            "synapse.memory.store", _base / "memory" / "store.py"
        )
        store_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store_mod)

        store = store_mod.MemoryStore(storage_dir=str(tmp_path))
        # Create the memory file first
        (tmp_path / "memory.jsonl").touch()
        store._write_buffer = ['{"id": "1"}\n']
        store._flush_writes()
        assert len(store._write_buffer) == 0


class TestIndexIntegrity:
    """C4: Stale index.json doesn't overwrite live index."""

    def test_stale_index_does_not_overwrite_live(self, tmp_path):
        """After loading JSONL, stale index.json doesn't replace live index."""
        spec = importlib.util.spec_from_file_location(
            "synapse.memory.store", _base / "memory" / "store.py"
        )
        store_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store_mod)

        # Write 3 memories to JSONL
        mem_file = tmp_path / "memory.jsonl"
        for i in range(3):
            entry = {
                "id": f"mem-{i}",
                "memory_type": "note",
                "content": f"test {i}",
                "summary": f"test {i}",
                "tags": [f"tag{i}"],
                "keywords": [],
                "source": "user",
                "tier": "shot",
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "hip_file": "",
                "hip_version": 0,
                "frame": None,
                "node_paths": [],
                "links": [],
                "access_count": 0,
                "is_consolidated": False,
                "metadata": {},
            }
            with open(mem_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, sort_keys=True) + '\n')

        # Write stale index.json with only 1 entry
        index_file = tmp_path / "index.json"
        stale_index = {
            "by_type": {"note": ["mem-0"]},
            "by_tag": {"tag0": ["mem-0"]},
            "by_keyword": {},
            "links": {},
            "created": "2025-01-01T00:00:00Z",
            "updated": "",
            "version": 1,
        }
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(stale_index, f)

        # Load store (background_load=False so _load runs synchronously in constructor)
        store = store_mod.MemoryStore(storage_dir=str(tmp_path), background_load=False)

        # All 3 memories should be indexed (live index, not stale)
        assert len(store._memories) == 3
        note_set = store._index.get("by_type", {}).get("note", set())
        assert len(note_set) == 3


class TestFlushEventOrdering:
    """C7: Flush event signal not lost."""

    def test_clear_before_wait_pattern(self):
        """Verify the flush loop uses clear-before-wait pattern."""
        spec = importlib.util.spec_from_file_location(
            "synapse.memory.store", _base / "memory" / "store.py"
        )
        store_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(store_mod)

        import inspect
        source = inspect.getsource(store_mod.MemoryStore._flush_loop)
        # clear() should come before wait() in the source
        clear_pos = source.index("clear()")
        wait_pos = source.index("wait(")
        assert clear_pos < wait_pos, "clear() must come before wait() to prevent signal loss"
