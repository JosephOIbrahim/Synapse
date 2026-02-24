"""Tests for resilience fixes -- aliases, session expiry, persist graceful failure."""
import importlib
import importlib.util
import json
import os
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import patch, MagicMock

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

# Add package to path for normal imports
_python_dir = str(Path(__file__).resolve().parent.parent / "python")
if _python_dir not in sys.path:
    sys.path.insert(0, _python_dir)

if "hou" not in sys.modules:
    sys.modules["hou"] = types.ModuleType("hou")


class TestAddAlias:
    """C5: add_alias() updates reverse map and is thread-safe."""

    def test_reverse_map_updated(self):
        spec = importlib.util.spec_from_file_location(
            "synapse.core.aliases", _base / "core" / "aliases.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        mod.add_alias("test_canonical_c5", "test_alias_c5")
        assert mod._REVERSE_ALIASES.get("test_alias_c5") == "test_canonical_c5"
        # Cleanup
        mod.PARAM_ALIASES.pop("test_canonical_c5", None)
        mod._REVERSE_ALIASES.pop("test_alias_c5", None)

    def test_thread_safety(self):
        spec = importlib.util.spec_from_file_location(
            "synapse.core.aliases", _base / "core" / "aliases.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        errors = []
        def adder(i):
            try:
                mod.add_alias(f"ts_canon_{i}", f"ts_alias_{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=adder, args=(i,)) for i in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        # Verify all aliases landed
        for i in range(50):
            assert mod._REVERSE_ALIASES.get(f"ts_alias_{i}") == f"ts_canon_{i}"
        # Cleanup
        for i in range(50):
            mod.PARAM_ALIASES.pop(f"ts_canon_{i}", None)
            mod._REVERSE_ALIASES.pop(f"ts_alias_{i}", None)


class TestSessionExpiry:
    """C9: Session lifecycle management."""

    def _load_session_module(self):
        spec = importlib.util.spec_from_file_location(
            "synapse.mcp.session", _base / "mcp" / "session.py"
        )
        if "synapse.mcp" not in sys.modules:
            pkg = types.ModuleType("synapse.mcp")
            pkg.__path__ = [str(_base / "mcp")]
            sys.modules["synapse.mcp"] = pkg
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_expired_sessions_swept(self):
        mod = self._load_session_module()

        mgr = mod.MCPSessionManager()
        sid = mgr.create_session({"name": "old_client"})
        # Age the session beyond TTL
        with mgr._lock:
            mgr._sessions[sid].created_at = time.time() - 7200
        mgr.create_session({"name": "new_client"})
        assert mgr.get_session(sid) is None

    def test_max_sessions_enforced(self):
        mod = self._load_session_module()

        mgr = mod.MCPSessionManager()
        for i in range(105):
            mgr.create_session({"name": f"c{i}"})
        # After 105 creates, sweep should keep <= _MAX_SESSIONS + 1 (the new one)
        assert mgr.active_count <= 101


class TestPersistResilience:
    """C12: Disk write failures don't crash handlers."""

    def test_audit_persist_failure_does_not_crash(self):
        from synapse.core.audit import AuditLog, AuditEntry, AuditLevel, AuditCategory
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        try:
            audit = AuditLog(log_dir=Path(tmp_dir) / "audit_c12")
            entry = AuditEntry(
                timestamp_utc="2026-02-24T00:00:00Z",
                level=AuditLevel.INFO,
                category=AuditCategory.SYSTEM,
                operation="test_op",
                message="test message",
            )
            # Patch open to fail
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                # This should NOT raise
                try:
                    audit._persist_entry(entry)
                except Exception:
                    raise AssertionError("_persist_entry should not propagate exceptions")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_gate_persist_failure_does_not_crash(self):
        from synapse.core.gates import HumanGate, GateProposal, GateLevel
        from synapse.core.audit import AuditCategory
        import tempfile

        tmp_dir = tempfile.mkdtemp()
        try:
            gate = HumanGate(storage_dir=Path(tmp_dir) / "gate_c12")
            proposal = GateProposal(
                proposal_id="test-001",
                gate_id="gate-001",
                sequence_id="seq-001",
                operation="test_op",
                description="test",
                category=AuditCategory.SYSTEM,
                level=GateLevel.INFORM,
            )
            with patch("builtins.open", side_effect=PermissionError("Access denied")):
                try:
                    gate._persist_proposal(proposal)
                except Exception:
                    raise AssertionError("_persist_proposal should not propagate exceptions")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
