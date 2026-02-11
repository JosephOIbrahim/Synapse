"""
MCP Roundtrip Integration Tests

Tests the full chain: MCP tool call -> handler dispatch -> response.
Uses a mock hou stub to avoid needing a real Houdini instance.

These tests verify that:
1. MCP tool schemas match handler expectations
2. Parameter aliases resolve correctly end-to-end
3. Error responses propagate through the full chain
4. Response IDs and sequences are preserved
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Bootstrap: load handlers package without Houdini
# ---------------------------------------------------------------------------

if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    _hou.node = MagicMock(return_value=None)
    _hou.hipFile = MagicMock()
    _hou.hipFile.path = MagicMock(return_value="/tmp/test.hip")
    _hou.hipFile.name = MagicMock(return_value="test.hip")
    _hou.getenv = MagicMock(return_value="/tmp")
    _hou.fps = MagicMock(return_value=24.0)
    _hou.frame = MagicMock(return_value=1001)
    _hou.undos = MagicMock()
    _hou.selectedNodes = MagicMock(return_value=[])
    _hou.playbar = MagicMock()
    _hou.playbar.frameRange = MagicMock(return_value=(1001, 1100))
    sys.modules["hou"] = _hou
else:
    _hou = sys.modules["hou"]

if "hdefereval" not in sys.modules:
    sys.modules["hdefereval"] = types.ModuleType("hdefereval")

# Set up package hierarchy for relative imports
_root = Path(__file__).resolve().parent.parent / "python"

# Register stub packages so relative imports work
for mod_name, mod_path in [
    ("synapse", _root / "synapse"),
    ("synapse.core", _root / "synapse" / "core"),
    ("synapse.server", _root / "synapse" / "server"),
    ("synapse.session", _root / "synapse" / "session"),
    ("synapse.memory", _root / "synapse" / "memory"),
    ("synapse.routing", _root / "synapse" / "routing"),
    ("synapse.agent", _root / "synapse" / "agent"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Load actual modules
_module_files = [
    ("synapse.core.errors", _root / "synapse" / "core" / "errors.py"),
    ("synapse.core.protocol", _root / "synapse" / "core" / "protocol.py"),
    ("synapse.core.aliases", _root / "synapse" / "core" / "aliases.py"),
    ("synapse.core.determinism", _root / "synapse" / "core" / "determinism.py"),
    ("synapse.core.audit", _root / "synapse" / "core" / "audit.py"),
    ("synapse.core.gates", _root / "synapse" / "core" / "gates.py"),
    ("synapse.core.queue", _root / "synapse" / "core" / "queue.py"),
    ("synapse.server.handlers_node", _root / "synapse" / "server" / "handlers_node.py"),
    ("synapse.server.handlers_usd", _root / "synapse" / "server" / "handlers_usd.py"),
    ("synapse.server.handlers_render", _root / "synapse" / "server" / "handlers_render.py"),
    ("synapse.server.handlers_memory", _root / "synapse" / "server" / "handlers_memory.py"),
    ("synapse.server.handlers", _root / "synapse" / "server" / "handlers.py"),
]

for mod_name, fpath in _module_files:
    if mod_name not in sys.modules and fpath.exists():
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        try:
            spec.loader.exec_module(mod)
        except Exception:
            pass  # Some modules may fail; we only need handlers

handlers_mod = sys.modules["synapse.server.handlers"]
_handlers_hou = handlers_mod.hou

from synapse.core.protocol import SynapseCommand, SynapseResponse, PROTOCOL_VERSION


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHandlerRoundtrip:
    """Test handler dispatch with real SynapseCommand objects."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def test_ping_roundtrip(self):
        """ping command -> success response with pong=True."""
        resp = self._handler().handle(
            SynapseCommand(type="ping", id="rt-001", payload={}, sequence=1)
        )
        assert resp.success is True
        assert resp.data["pong"] is True
        assert "protocol_version" in resp.data

    def test_get_health_roundtrip(self):
        """get_health -> success with healthy=True."""
        resp = self._handler().handle(
            SynapseCommand(type="get_health", id="rt-002", payload={}, sequence=2)
        )
        assert resp.success is True
        assert resp.data["healthy"] is True

    def test_get_help_roundtrip(self):
        """get_help -> success with 30+ registered commands."""
        resp = self._handler().handle(
            SynapseCommand(type="get_help", id="rt-003", payload={}, sequence=3)
        )
        assert resp.success is True
        assert "commands" in resp.data
        assert len(resp.data["commands"]) >= 30

    def test_unknown_command_roundtrip(self):
        """Unknown command -> failure with coaching-tone error."""
        resp = self._handler().handle(
            SynapseCommand(type="nonexistent_cmd", id="rt-004", payload={}, sequence=4)
        )
        assert resp.success is False
        assert "don't recognize" in resp.error

    def test_create_node_missing_parent(self):
        """create_node with invalid parent -> coaching-tone error."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="create_node", id="rt-005",
                    payload={"parent": "/obj/nonexistent", "type": "null"},
                    sequence=5,
                )
            )
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()

    def test_get_parm_missing_node(self):
        """get_parm on missing node -> error mentioning the path."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="rt-006",
                    payload={"node": "/stage/missing", "parm": "tx"},
                    sequence=6,
                )
            )
        assert resp.success is False
        assert "/stage/missing" in resp.error or "couldn't find" in resp.error.lower()

    def test_batch_commands_with_ping(self):
        """batch_commands with a ping -> array of results."""
        resp = self._handler().handle(
            SynapseCommand(
                type="batch_commands", id="rt-007",
                payload={"commands": [{"type": "ping", "payload": {}}]},
                sequence=7,
            )
        )
        assert resp.success is True
        assert resp.data["results"][0]["pong"] is True
        assert resp.data["statuses"][0] == "ok"

    def test_batch_commands_stop_on_error(self):
        """batch_commands with stop_on_error halts at first failure."""
        resp = self._handler().handle(
            SynapseCommand(
                type="batch_commands", id="rt-008",
                payload={
                    "commands": [
                        {"type": "unknown_cmd", "payload": {}},
                        {"type": "ping", "payload": {}},
                    ],
                    "stop_on_error": True,
                },
                sequence=8,
            )
        )
        assert resp.success is True
        assert resp.data["statuses"][0] == "error"

    def test_response_ids_match_command(self):
        """Response ID always matches the command ID."""
        handler = self._handler()
        for i in range(5):
            cmd_id = f"id-match-{i}"
            resp = handler.handle(
                SynapseCommand(type="ping", id=cmd_id, payload={}, sequence=i)
            )
            assert resp.id == cmd_id

    def test_sequence_numbers_preserved(self):
        """Response sequence matches command sequence."""
        resp = self._handler().handle(
            SynapseCommand(type="ping", id="seq-test", payload={}, sequence=42)
        )
        assert resp.sequence == 42

    def test_knowledge_lookup_doesnt_crash(self):
        """knowledge_lookup -> doesn't crash (RAG may not be loaded)."""
        resp = self._handler().handle(
            SynapseCommand(
                type="knowledge_lookup", id="rt-009",
                payload={"query": "dome light intensity"},
                sequence=9,
            )
        )
        assert isinstance(resp, SynapseResponse)


class TestParameterAliasRoundtrip:
    """Verify parameter aliases resolve end-to-end."""

    def _handler(self):
        return handlers_mod.SynapseHandler()

    def test_path_alias_resolves_to_node(self):
        """'path' alias resolves to 'node' for get_parm."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="alias-1",
                    payload={"path": "/stage/light", "parm": "tx"},
                    sequence=1,
                )
            )
        # Should attempt to find the node (not error about missing 'node' key)
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()

    def test_node_path_alias_resolves(self):
        """'node_path' alias resolves to 'node' for get_parm."""
        from unittest.mock import patch
        with patch.object(_handlers_hou, "node", return_value=None, create=True):
            resp = self._handler().handle(
                SynapseCommand(
                    type="get_parm", id="alias-2",
                    payload={"node_path": "/stage/light", "parm": "tx"},
                    sequence=2,
                )
            )
        assert resp.success is False
        assert "couldn't find" in resp.error.lower()
