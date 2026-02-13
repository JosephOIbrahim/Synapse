"""Tests for the MCP protocol layer (Phase 1 MVP).

Tests: JSON-RPC parsing, session management, tool dispatch,
error handling, He2025 determinism.

No Houdini required — MCPServer is tested with a mocked handler.
"""

import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Bootstrap: load MCP modules without Houdini
# ---------------------------------------------------------------------------

_base = Path(__file__).resolve().parent.parent / "python" / "synapse"

# Ensure package stubs exist
for mod_name, mod_path in [
    ("synapse", _base),
    ("synapse.core", _base / "core"),
    ("synapse.server", _base / "server"),
    ("synapse.session", _base / "session"),
    ("synapse.mcp", _base / "mcp"),
]:
    if mod_name not in sys.modules:
        pkg = types.ModuleType(mod_name)
        pkg.__path__ = [str(mod_path)]
        sys.modules[mod_name] = pkg

# Load core modules the MCP layer depends on
_core_modules = {
    "synapse.core.protocol": _base / "core" / "protocol.py",
    "synapse.core.aliases": _base / "core" / "aliases.py",
}

for mod_name, fpath in _core_modules.items():
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

# Load MCP modules
_mcp_modules = {
    "synapse.mcp.protocol": _base / "mcp" / "protocol.py",
    "synapse.mcp.session": _base / "mcp" / "session.py",
    "synapse.mcp.tools": _base / "mcp" / "tools.py",
    "synapse.mcp.server": _base / "mcp" / "server.py",
}

for mod_name, fpath in _mcp_modules.items():
    if mod_name not in sys.modules:
        spec = importlib.util.spec_from_file_location(mod_name, fpath)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)

protocol_mod = sys.modules["synapse.mcp.protocol"]
session_mod = sys.modules["synapse.mcp.session"]
tools_mod = sys.modules["synapse.mcp.tools"]
server_mod = sys.modules["synapse.mcp.server"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jsonrpc(method, params=None, msg_id=1):
    """Build a JSON-RPC 2.0 request as bytes."""
    msg = {"jsonrpc": "2.0", "method": method, "id": msg_id}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg, sort_keys=True).encode("utf-8")


def _notification(method, params=None):
    """Build a JSON-RPC 2.0 notification (no id)."""
    msg = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    return json.dumps(msg, sort_keys=True).encode("utf-8")


def _parse_response(body):
    """Parse response bytes to dict."""
    return json.loads(body)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_handler():
    """Create a mock SynapseHandler."""
    handler = MagicMock()
    response = MagicMock()
    response.success = True
    response.data = {"status": "ok"}
    response.error = None
    handler.handle.return_value = response
    return handler


@pytest.fixture
def server(mock_handler):
    """Create an MCPServer with a mocked handler."""
    return server_mod.MCPServer(handler=mock_handler)


# ===========================================================================
# Tests: JSON-RPC Protocol (protocol.py)
# ===========================================================================

class TestJsonRpcParsing:
    def test_valid_request(self):
        body = _jsonrpc("tools/list")
        msg = protocol_mod.parse_request(body)
        assert msg["method"] == "tools/list"
        assert msg["jsonrpc"] == "2.0"
        assert msg["id"] == 1

    def test_invalid_json_raises_parse_error(self):
        with pytest.raises(protocol_mod.JsonRpcParseError):
            protocol_mod.parse_request(b"not json")

    def test_missing_jsonrpc_version(self):
        body = json.dumps({"method": "test", "id": 1}).encode()
        with pytest.raises(protocol_mod.JsonRpcInvalidRequest):
            protocol_mod.parse_request(body)

    def test_wrong_jsonrpc_version(self):
        body = json.dumps({"jsonrpc": "1.0", "method": "test", "id": 1}).encode()
        with pytest.raises(protocol_mod.JsonRpcInvalidRequest):
            protocol_mod.parse_request(body)

    def test_missing_method(self):
        body = json.dumps({"jsonrpc": "2.0", "id": 1}).encode()
        with pytest.raises(protocol_mod.JsonRpcInvalidRequest):
            protocol_mod.parse_request(body)

    def test_non_object_request(self):
        body = json.dumps([1, 2, 3]).encode()
        with pytest.raises(protocol_mod.JsonRpcInvalidRequest):
            protocol_mod.parse_request(body)

    def test_notification_detection(self):
        assert protocol_mod.is_notification({"method": "test"}) is True
        assert protocol_mod.is_notification({"method": "test", "id": 1}) is False

    def test_result_response_format(self):
        body = protocol_mod.jsonrpc_result(42, {"answer": True})
        resp = json.loads(body)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 42
        assert resp["result"]["answer"] is True

    def test_error_response_format(self):
        body = protocol_mod.jsonrpc_error(1, -32600, "Bad request")
        resp = json.loads(body)
        assert resp["error"]["code"] == -32600
        assert resp["error"]["message"] == "Bad request"

    def test_error_response_with_data(self):
        body = protocol_mod.jsonrpc_error(1, -32603, "Oops", {"detail": "x"})
        resp = json.loads(body)
        assert resp["error"]["data"]["detail"] == "x"

    def test_error_from_exception(self):
        exc = protocol_mod.JsonRpcInvalidParams("bad arg")
        body = protocol_mod.error_from_exception(5, exc)
        resp = json.loads(body)
        assert resp["id"] == 5
        assert resp["error"]["code"] == protocol_mod.INVALID_PARAMS


# ===========================================================================
# Tests: Session Management (session.py)
# ===========================================================================

class TestSessionManager:
    def test_create_session(self):
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session({"name": "test-client"})
        assert sid.startswith("mcp-session-")
        assert mgr.active_count == 1

    def test_get_session(self):
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session()
        session = mgr.get_session(sid)
        assert session is not None
        assert session.session_id == sid

    def test_get_nonexistent_session(self):
        mgr = session_mod.MCPSessionManager()
        assert mgr.get_session("does-not-exist") is None

    def test_mark_initialized(self):
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session()
        assert mgr.mark_initialized(sid) is True
        assert mgr.get_session(sid).initialized is True

    def test_mark_initialized_missing(self):
        mgr = session_mod.MCPSessionManager()
        assert mgr.mark_initialized("nope") is False

    def test_destroy_session(self):
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session()
        assert mgr.destroy_session(sid) is True
        assert mgr.get_session(sid) is None
        assert mgr.active_count == 0

    def test_destroy_nonexistent(self):
        mgr = session_mod.MCPSessionManager()
        assert mgr.destroy_session("nope") is False

    def test_sequential_ids(self):
        """He2025: IDs must be sequential, not random."""
        mgr = session_mod.MCPSessionManager()
        id1 = mgr.create_session()
        id2 = mgr.create_session()
        # Extract numeric suffix
        n1 = int(id1.split("-")[-1])
        n2 = int(id2.split("-")[-1])
        assert n2 == n1 + 1

    def test_session_to_dict(self):
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session({"name": "claude"})
        session = mgr.get_session(sid)
        d = session.to_dict()
        assert d["session_id"] == sid
        assert d["client_info"]["name"] == "claude"
        assert d["protocol_version"] == "2025-06-18"


# ===========================================================================
# Tests: Tool Registry (tools.py)
# ===========================================================================

class TestToolRegistry:
    def test_get_tools_returns_list(self):
        tools = tools_mod.get_tools()
        assert isinstance(tools, list)
        assert len(tools) >= 40  # 44 tools registered

    def test_tools_sorted_by_name(self):
        """He2025: tool list must be sorted."""
        tools = tools_mod.get_tools()
        names = [t["name"] for t in tools]
        assert names == sorted(names)

    def test_tool_has_required_fields(self):
        tools = tools_mod.get_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "annotations" in tool

    def test_has_tool(self):
        assert tools_mod.has_tool("synapse_ping") is True
        assert tools_mod.has_tool("houdini_create_node") is True
        assert tools_mod.has_tool("nonexistent_tool") is False

    def test_get_tool_names(self):
        names = tools_mod.get_tool_names()
        assert "synapse_ping" in names
        assert "houdini_render" in names
        assert names == sorted(names)

    def test_dispatch_unknown_tool(self):
        handler = MagicMock()
        result = tools_mod.dispatch_tool(handler, "fake_tool", {})
        assert result["isError"] is True
        assert "Unknown tool" in result["content"][0]["text"]

    def test_dispatch_success(self):
        handler = MagicMock()
        response = MagicMock()
        response.success = True
        response.data = {"pong": True}
        handler.handle.return_value = response

        result = tools_mod.dispatch_tool(handler, "synapse_ping", {})
        assert "isError" not in result or result.get("isError") is not True
        assert result["content"][0]["type"] == "text"

    def test_dispatch_error(self):
        handler = MagicMock()
        response = MagicMock()
        response.success = False
        response.error = "Something went wrong"
        response.data = None
        handler.handle.return_value = response

        result = tools_mod.dispatch_tool(handler, "synapse_ping", {})
        assert result["isError"] is True
        assert "Something went wrong" in result["content"][0]["text"]

    def test_validate_frame_registered(self):
        assert tools_mod.has_tool("synapse_validate_frame") is True

    def test_annotations_structure(self):
        tools = tools_mod.get_tools()
        for tool in tools:
            ann = tool["annotations"]
            assert "readOnlyHint" in ann
            assert "destructiveHint" in ann
            assert "idempotentHint" in ann
            assert ann["openWorldHint"] is False


# ===========================================================================
# Tests: MCP Server (server.py)
# ===========================================================================

class TestInitialize:
    def test_initialize_returns_capabilities(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, headers = server.handle_request(body)

        assert resp_body is not None
        resp = _parse_response(resp_body)
        assert "result" in resp
        result = resp["result"]
        assert result["protocolVersion"] == "2025-06-18"
        assert "tools" in result["capabilities"]
        assert result["serverInfo"]["name"] == "synapse"

    def test_initialize_returns_session_id(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        _, headers = server.handle_request(body)
        assert "Mcp-Session-Id" in headers
        assert headers["Mcp-Session-Id"].startswith("mcp-session-")

    def test_initialize_creates_session(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        _, headers = server.handle_request(body)
        assert server.active_sessions == 1


class TestToolsList:
    def test_tools_list_requires_session(self, server):
        body = _jsonrpc("tools/list")
        resp_body, _ = server.handle_request(body, session_id=None)
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.SESSION_INVALID

    def test_tools_list_with_valid_session(self, server):
        # Initialize first
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        # List tools
        list_body = _jsonrpc("tools/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(list_body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "result" in resp
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) >= 40

    def test_tools_list_invalid_session(self, server):
        body = _jsonrpc("tools/list")
        resp_body, _ = server.handle_request(body, session_id="bad-session")
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.SESSION_INVALID


class TestToolsCall:
    def test_tools_call_dispatches(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        # Call ping
        call_body = _jsonrpc("tools/call", {
            "name": "synapse_ping",
            "arguments": {},
        }, msg_id=2)
        resp_body, _ = server.handle_request(call_body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "result" in resp

    def test_tools_call_missing_name(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        # Call without name
        call_body = _jsonrpc("tools/call", {"arguments": {}}, msg_id=2)
        resp_body, _ = server.handle_request(call_body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.INVALID_PARAMS


class TestPing:
    def test_ping_returns_empty(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        # Ping
        ping_body = _jsonrpc("ping", {}, msg_id=2)
        resp_body, _ = server.handle_request(ping_body, session_id=sid)
        resp = _parse_response(resp_body)
        assert resp["result"] == {}


class TestNotifications:
    def test_notification_returns_none(self, server):
        # Initialize first
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _notification("notifications/initialized")
        resp_body, _ = server.handle_request(body, session_id=sid)
        assert resp_body is None

    def test_unknown_notification_ignored(self, server):
        body = _notification("notifications/unknown")
        resp_body, _ = server.handle_request(body)
        assert resp_body is None


class TestMethodNotFound:
    def test_unknown_method(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("resources/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.METHOD_NOT_FOUND


class TestErrorHandling:
    def test_invalid_json(self, server):
        resp_body, _ = server.handle_request(b"not json")
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.PARSE_ERROR

    def test_missing_jsonrpc_field(self, server):
        body = json.dumps({"method": "test", "id": 1}).encode()
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        assert "error" in resp
        assert resp["error"]["code"] == protocol_mod.INVALID_REQUEST


class TestSessionLifecycle:
    def test_full_lifecycle(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]
        assert server.active_sessions == 1

        # Destroy
        server.destroy_session(sid)
        assert server.active_sessions == 0

        # Tools call should fail with destroyed session
        call_body = _jsonrpc("tools/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(call_body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "error" in resp


class TestHe2025Determinism:
    def test_response_keys_sorted(self, server):
        """He2025: all JSON responses must have sorted keys."""
        body = _jsonrpc("initialize", {}, msg_id=1)
        resp_body, _ = server.handle_request(body)
        # Parse as raw string and verify key order
        raw = resp_body.decode("utf-8") if isinstance(resp_body, bytes) else resp_body
        resp = json.loads(raw)
        # Top-level keys should be sorted
        keys = list(resp.keys())
        assert keys == sorted(keys)

    def test_tools_list_sorted(self, server):
        """He2025: tool list must be sorted by name."""
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        list_body = _jsonrpc("tools/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(list_body, session_id=sid)
        resp = _parse_response(resp_body)
        names = [t["name"] for t in resp["result"]["tools"]]
        assert names == sorted(names)


class TestModuleSingleton:
    def test_get_mcp_server_returns_same_instance(self):
        # Reset singleton
        server_mod._mcp_server = None
        s1 = server_mod.get_mcp_server()
        s2 = server_mod.get_mcp_server()
        assert s1 is s2
        # Cleanup
        server_mod._mcp_server = None
