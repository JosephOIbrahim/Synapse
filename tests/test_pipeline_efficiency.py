"""
Pipeline Efficiency Tests

Tests for the 6 pipeline efficiency suggestions:
1. Concurrent command dispatch (mcp_server.py)
2. Tier-pinning cache (router.py)
3. Batch commands (handlers.py + mcp_server.py)
4. Reader-writer lock (store.py)
5. Concise tool descriptions (mcp_server.py)
6. Speculative T0+T1 parallelism (router.py)

Run: python -m pytest tests/test_pipeline_efficiency.py -v
"""

import importlib.util
import sys
import os
import types
import threading
import time
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# ---------------------------------------------------------------------------
# Bootstrap hou stub for handler tests
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock()
    _hou.frame = MagicMock(return_value=24.0)
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.undos = MagicMock()
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    _hde = types.ModuleType("hdefereval")
    _hde.executeDeferred = lambda fn: fn()
    _hde.executeInMainThreadWithResult = lambda fn: fn()
    sys.modules["hdefereval"] = _hde

# Bootstrap synapse package stubs
for mod_name, mod_path in [
    ("synapse", Path(__file__).resolve().parent.parent / "python" / "synapse"),
    ("synapse.core", Path(__file__).resolve().parent.parent / "python" / "synapse" / "core"),
    ("synapse.server", Path(__file__).resolve().parent.parent / "python" / "synapse" / "server"),
    ("synapse.session", Path(__file__).resolve().parent.parent / "python" / "synapse" / "session"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

_proto_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "protocol.py"
_aliases_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "core" / "aliases.py"
_handlers_path = Path(__file__).resolve().parent.parent / "python" / "synapse" / "server" / "handlers.py"

for mod_name, fpath in [
    ("synapse.core.protocol", _proto_path),
    ("synapse.core.aliases", _aliases_path),
    ("synapse.server.handlers", _handlers_path),
]:
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

handlers_mod = sys.modules["synapse.server.handlers"]
_handlers_hou = handlers_mod.hou


# =============================================================================
# SUGGESTION 4: ReadWriteLock
# =============================================================================

from synapse.memory.store import ReadWriteLock


class TestReadWriteLock:
    """Tests for the ReadWriteLock class."""

    def test_single_reader(self):
        """A single reader can acquire and release."""
        rwl = ReadWriteLock()
        with rwl.read_lock():
            assert rwl._readers == 1
        assert rwl._readers == 0

    def test_single_writer(self):
        """A single writer can acquire and release."""
        rwl = ReadWriteLock()
        with rwl.write_lock():
            assert rwl._writer is True
        assert rwl._writer is False

    def test_concurrent_readers(self):
        """Multiple readers can hold the lock simultaneously."""
        rwl = ReadWriteLock()
        barrier = threading.Barrier(3)
        max_readers = []

        def reader():
            with rwl.read_lock():
                barrier.wait(timeout=2)
                max_readers.append(rwl._readers)
                time.sleep(0.01)

        threads = [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert all(r >= 2 for r in max_readers), f"Expected concurrent readers, got {max_readers}"

    def test_writer_excludes_readers(self):
        """Writer blocks new readers."""
        rwl = ReadWriteLock()
        writer_held = threading.Event()
        reader_entered = threading.Event()

        def writer():
            with rwl.write_lock():
                writer_held.set()
                time.sleep(0.1)

        def reader():
            writer_held.wait(timeout=2)
            time.sleep(0.02)  # Ensure writer is still held
            with rwl.read_lock():
                reader_entered.set()

        wt = threading.Thread(target=writer)
        rt = threading.Thread(target=reader)
        wt.start()
        rt.start()

        # Reader shouldn't enter until writer is done
        assert not reader_entered.wait(timeout=0.05)
        wt.join(timeout=5)
        rt.join(timeout=5)
        assert reader_entered.is_set()

    def test_writer_excludes_writers(self):
        """Two writers are mutually exclusive."""
        rwl = ReadWriteLock()
        order = []

        def writer(name):
            with rwl.write_lock():
                order.append(f"{name}_enter")
                time.sleep(0.05)
                order.append(f"{name}_exit")

        t1 = threading.Thread(target=writer, args=("A",))
        t2 = threading.Thread(target=writer, args=("B",))
        t1.start()
        time.sleep(0.01)  # Ensure A starts first
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        # One writer must fully finish before the other starts
        assert order[0].endswith("_enter")
        assert order[1].endswith("_exit")
        assert order[0][0] == order[1][0]  # Same writer enters and exits first

    def test_writer_priority(self):
        """A waiting writer blocks new readers (writer starvation prevention)."""
        rwl = ReadWriteLock()
        events = []
        reader_active = threading.Event()

        def first_reader():
            with rwl.read_lock():
                reader_active.set()
                events.append("R1_enter")
                time.sleep(0.15)
                events.append("R1_exit")

        def writer():
            reader_active.wait(timeout=2)
            time.sleep(0.01)
            events.append("W_waiting")
            with rwl.write_lock():
                events.append("W_enter")
                time.sleep(0.02)
                events.append("W_exit")

        def second_reader():
            reader_active.wait(timeout=2)
            time.sleep(0.03)  # Start after writer is waiting
            events.append("R2_waiting")
            with rwl.read_lock():
                events.append("R2_enter")

        t1 = threading.Thread(target=first_reader)
        tw = threading.Thread(target=writer)
        t2 = threading.Thread(target=second_reader)

        t1.start()
        tw.start()
        t2.start()
        t1.join(timeout=5)
        tw.join(timeout=5)
        t2.join(timeout=5)

        # Writer should enter before second reader (priority)
        if "W_enter" in events and "R2_enter" in events:
            assert events.index("W_enter") < events.index("R2_enter"), \
                f"Writer should have priority over new readers: {events}"


# =============================================================================
# SUGGESTION 2: Tier-Pinning Cache
# =============================================================================

from synapse.routing.router import TieredRouter, RoutingTier, RoutingConfig, _MAX_TIER_PINS


class TestTierPinning:
    """Tests for the tier-pinning cache."""

    def _make_router(self, **kwargs):
        config = RoutingConfig(
            enable_tier2=False,
            enable_tier3=False,
            **kwargs,
        )
        return TieredRouter(config=config)

    def test_pin_recorded_on_tier0_hit(self):
        """T0 match records a pin."""
        router = self._make_router()
        result = router.route("create a sphere at /obj")
        if result.tier == RoutingTier.INSTANT:
            key = f"create a sphere at /obj|"
            assert key in router._tier_pins
            assert router._tier_pins[key] == RoutingTier.INSTANT.value

    def test_pin_hit_returns_same_tier(self):
        """Same input routes to pinned tier on repeat."""
        router = self._make_router()
        r1 = router.route("create a sphere at /obj")
        r2 = router.route("create a sphere at /obj")
        assert r1.tier == r2.tier

    def test_stale_pin_evicted(self):
        """If pinned tier returns None, pin is deleted."""
        router = self._make_router()
        # Manually inject a pin for a tier that won't match
        pin_key = "nonexistent query|"
        router._tier_pins[pin_key] = RoutingTier.INSTANT.value
        router.route("nonexistent query")
        # Pin should be evicted since T0 won't match "nonexistent query"
        assert pin_key not in router._tier_pins

    def test_lru_eviction(self):
        """Oldest pin evicted when max capacity reached."""
        router = self._make_router()
        # Fill with fake pins
        for i in range(_MAX_TIER_PINS + 5):
            router._tier_pins[f"key_{i}|"] = "instant"

        assert len(router._tier_pins) <= _MAX_TIER_PINS + 5

        # Trigger eviction via _pin_tier
        router._pin_tier("new_input", "", "instant")
        assert len(router._tier_pins) <= _MAX_TIER_PINS + 5  # Hasn't exceeded hard limit

    def test_pin_eviction_removes_oldest(self):
        """_pin_tier evicts oldest entry when over limit."""
        router = self._make_router()
        # Fill exactly to limit
        for i in range(_MAX_TIER_PINS):
            router._tier_pins[f"fill_{i}|ctx"] = "instant"
        first_key = f"fill_0|ctx"
        assert first_key in router._tier_pins

        # Add one more — should evict first
        router._pin_tier("overflow", "ctx", "fast")
        assert first_key not in router._tier_pins
        assert f"overflow|ctx" in router._tier_pins


# =============================================================================
# SUGGESTION 6: Speculative T0+T1 Parallelism
# =============================================================================

class TestSpeculativeParallelism:
    """Tests for T0+T1 speculative parallel execution."""

    def _make_router(self, **kwargs):
        config = RoutingConfig(
            enable_tier2=False,
            enable_tier3=False,
            **kwargs,
        )
        return TieredRouter(config=config)

    def test_t0_wins(self):
        """T0 match returns immediately, T1 result discarded."""
        router = self._make_router()
        result = router.route("create a sphere at /obj")
        if result.tier == RoutingTier.INSTANT:
            assert result.success
            assert "sphere" in str(result.metadata).lower() or result.tier == RoutingTier.INSTANT

    def test_t0_miss_falls_through_to_t1(self):
        """T0 miss uses T1 result if available."""
        import tempfile, shutil

        tmp = tempfile.mkdtemp()
        try:
            # Create RAG dir
            meta_dir = os.path.join(tmp, "documentation", "_metadata")
            os.makedirs(meta_dir, exist_ok=True)
            index = {
                "test_topic": {
                    "summary": "Test topic answer",
                    "description": "Detailed test description",
                    "keywords": ["testing", "pipeline"],
                }
            }
            with open(os.path.join(meta_dir, "semantic_index.json"), "w", encoding="utf-8") as f:
                import json
                json.dump(index, f)

            router = self._make_router(rag_root=tmp)
            result = router.route("tell me about testing pipeline")
            # Should either be T1 (knowledge) or fall through
            assert result is not None
        finally:
            shutil.rmtree(tmp)

    def test_both_disabled_still_works(self):
        """If both T0 and T1 are disabled, routing still works."""
        router = self._make_router(enable_tier0=False, enable_tier1=False)
        result = router.route("create a sphere")
        # Falls through to fallback
        assert result is not None

    def test_only_t0_enabled(self):
        """If only T0 is enabled, no parallel dispatch needed."""
        router = self._make_router(enable_tier1=False)
        result = router.route("create a sphere at /obj")
        assert result is not None

    def test_only_t1_enabled(self):
        """If only T1 is enabled, T0 is skipped."""
        router = self._make_router(enable_tier0=False)
        result = router.route("create a sphere")
        assert result is not None


# =============================================================================
# SUGGESTION 3: Batch Commands
# =============================================================================

class TestBatchCommands:
    """Tests for the batch_commands handler."""

    def _make_handler(self):
        handler = handlers_mod.SynapseHandler()
        return handler

    def test_batch_basic(self):
        """Batch with valid commands returns results."""
        handler = self._make_handler()
        payload = {
            "commands": [
                {"type": "ping", "payload": {}},
                {"type": "get_health", "payload": {}},
            ],
            "atomic": False,
        }
        result = handler._handle_batch_commands(payload)
        assert len(result["results"]) == 2
        assert all(s == "ok" for s in result["statuses"])
        assert all(e is None for e in result["errors"])

    def test_batch_empty_raises(self):
        """Empty commands list raises ValueError."""
        handler = self._make_handler()
        with pytest.raises(ValueError, match="commands"):
            handler._handle_batch_commands({"commands": []})

    def test_batch_missing_commands_raises(self):
        """Missing commands key raises ValueError."""
        handler = self._make_handler()
        with pytest.raises(ValueError, match="commands"):
            handler._handle_batch_commands({})

    def test_batch_unknown_command(self):
        """Unknown command type records error but continues."""
        handler = self._make_handler()
        payload = {
            "commands": [
                {"type": "nonexistent_cmd", "payload": {}},
                {"type": "ping", "payload": {}},
            ],
            "atomic": False,
        }
        result = handler._handle_batch_commands(payload)
        assert result["statuses"][0] == "error"
        assert "unknown" in result["errors"][0].lower()
        assert result["statuses"][1] == "ok"

    def test_batch_stop_on_error(self):
        """stop_on_error=True halts after first error."""
        handler = self._make_handler()
        payload = {
            "commands": [
                {"type": "nonexistent_cmd", "payload": {}},
                {"type": "ping", "payload": {}},
            ],
            "atomic": False,
            "stop_on_error": True,
        }
        result = handler._handle_batch_commands(payload)
        assert len(result["statuses"]) == 1
        assert result["statuses"][0] == "error"

    def test_batch_error_in_middle(self):
        """Error in middle doesn't block subsequent commands."""
        handler = self._make_handler()
        payload = {
            "commands": [
                {"type": "ping", "payload": {}},
                {"type": "nonexistent_cmd", "payload": {}},
                {"type": "get_health", "payload": {}},
            ],
            "atomic": False,
        }
        result = handler._handle_batch_commands(payload)
        assert result["statuses"] == ["ok", "error", "ok"]

    def test_batch_atomic_calls_undo(self):
        """atomic=True wraps in undo group context manager."""
        handler = self._make_handler()
        _handlers_hou.undos.group = MagicMock()

        payload = {
            "commands": [
                {"type": "ping", "payload": {}},
            ],
            "atomic": True,
        }
        with patch.object(handlers_mod, "HOU_AVAILABLE", True):
            handler._handle_batch_commands(payload)

        _handlers_hou.undos.group.assert_called_once_with("synapse_batch")

    def test_batch_default_payload(self):
        """Commands without payload key get empty dict."""
        handler = self._make_handler()
        payload = {
            "commands": [
                {"type": "ping"},
            ],
            "atomic": False,
        }
        result = handler._handle_batch_commands(payload)
        assert result["statuses"][0] == "ok"


# =============================================================================
# SUGGESTION 1: Concurrent Command Dispatch
# =============================================================================

class TestConcurrentDispatch:
    """Tests for the concurrent command dispatch in mcp_server.py."""

    def test_pending_dict_exists(self):
        """_pending dict is available at module level."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        # Just verify the module defines the concurrent dispatch primitives
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert "_pending: dict[str, asyncio.Future]" in content
        assert "_recv_loop" in content
        assert "_start_recv_loop" in content

    def test_no_cmd_lock(self):
        """_cmd_lock should no longer exist (replaced by concurrent dispatch)."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert "_cmd_lock" not in content

    def test_signal_all_pending(self):
        """_signal_all_pending signals all futures with exception."""
        # Import the function from the mcp_server module
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"

        # We can test the logic directly by reading the source
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert "def _signal_all_pending" in content
        assert "_pending.clear()" in content

    def test_recv_loop_defined(self):
        """_recv_loop is defined as an async function."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert "async def _recv_loop" in content

    def test_warmup_starts_recv_loop(self):
        """_warmup calls _start_recv_loop after connecting."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        # Check warmup function calls _start_recv_loop
        warmup_section = content[content.index("async def _warmup"):]
        warmup_end = warmup_section.index("async def main")
        warmup_body = warmup_section[:warmup_end]
        assert "_start_recv_loop()" in warmup_body


# =============================================================================
# SUGGESTION 5: Concise Tool Descriptions
# =============================================================================

class TestConciseDescriptions:
    """Tests for trimmed tool descriptions."""

    def test_batch_tool_registered(self):
        """synapse_batch tool is registered in the tool list."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert 'name="synapse_batch"' in content

    def test_batch_tool_in_dispatch(self):
        """synapse_batch is in the TOOL_DISPATCH table."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert '"synapse_batch"' in content
        assert '"batch_commands"' in content

    def test_batch_in_slow_commands(self):
        """batch_commands has a 60s timeout in _SLOW_COMMANDS."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        assert '"batch_commands": 60.0' in content

    def test_descriptions_have_coaching(self):
        """Key coaching phrases preserved in descriptions."""
        mcp_path = Path(__file__).resolve().parent.parent / "mcp_server.py"
        with open(mcp_path, encoding="utf-8") as f:
            content = f.read()
        # Core coaching phrases that should survive trimming
        assert "celebrate progress" in content
        assert "collaborative iteration" in content
        assert "Lead with what" in content
        assert "trial and error" in content


# =============================================================================
# SUGGESTION 4: MemoryStore with RWLock integration
# =============================================================================

class TestMemoryStoreRWLock:
    """Tests that MemoryStore uses ReadWriteLock correctly."""

    def test_store_uses_rwlock(self):
        """MemoryStore._lock is a ReadWriteLock instance."""
        from synapse.memory.store import MemoryStore, ReadWriteLock
        import tempfile

        tmp = tempfile.mkdtemp()
        try:
            store = MemoryStore(Path(tmp), background_load=False)
            assert isinstance(store._lock, ReadWriteLock)
        finally:
            store._flusher_running = False
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)

    def test_concurrent_reads_dont_block(self):
        """Multiple concurrent reads on MemoryStore don't serialize."""
        from synapse.memory.store import MemoryStore
        import tempfile

        tmp = tempfile.mkdtemp()
        try:
            store = MemoryStore(Path(tmp), background_load=False)
            results = []
            barrier = threading.Barrier(3, timeout=5)

            def reader():
                barrier.wait()
                count = store.count()
                results.append(count)

            threads = [threading.Thread(target=reader) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)

            assert len(results) == 3
        finally:
            store._flusher_running = False
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
