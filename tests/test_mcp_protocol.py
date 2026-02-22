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
    "synapse.mcp.resources": _base / "mcp" / "resources.py",
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

        body = _jsonrpc("prompts/list", {}, msg_id=2)
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


# ===========================================================================
# Tests: Resources (resources.py)
# ===========================================================================

class TestResourcesList:
    def test_resources_list_returns_resources(self, server):
        # Initialize
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        # List resources
        body = _jsonrpc("resources/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "result" in resp
        resources = resp["result"]["resources"]
        assert len(resources) >= 3  # at least 3 static resources

    def test_resources_sorted_by_uri(self, server):
        """He2025: resources must be sorted by URI."""
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("resources/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        uris = [r["uri"] for r in resp["result"]["resources"]]
        assert uris == sorted(uris)

    def test_initialize_includes_resources_capability(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        assert "resources" in resp["result"]["capabilities"]


class TestResourceTemplatesList:
    def test_resource_templates_returns_templates(self, server):
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("resources/templates/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        assert "result" in resp
        templates = resp["result"]["resourceTemplates"]
        assert len(templates) >= 9  # 9 resource templates (7 + 2 Phase 4)

    def test_tops_status_template_exists(self, server):
        """Phase 4: tops status resource template should be listed."""
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("resources/templates/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        templates = resp["result"]["resourceTemplates"]
        uris = [t["uriTemplate"] for t in templates]
        assert "houdini://tops/{topnet_path}/status" in uris
        assert "houdini://tops/{node_path}/diagnosis" in uris


# ===========================================================================
# Tests: Auth Integration
# ===========================================================================

class TestAuthIntegration:
    def test_auth_module_exists(self):
        """The auth module should be importable."""
        auth_path = _base / "server" / "auth.py"
        assert auth_path.exists()

    def test_no_key_passes(self, server):
        """With no auth key, requests should pass through."""
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, headers = server.handle_request(body)
        resp = _parse_response(resp_body)
        assert "result" in resp

    def test_authenticate_function(self):
        """authenticate() with no key should return True."""
        if "synapse.server.auth" not in sys.modules:
            auth_path = _base / "server" / "auth.py"
            spec = importlib.util.spec_from_file_location("synapse.server.auth", auth_path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["synapse.server.auth"] = mod
            spec.loader.exec_module(mod)
        auth_mod = sys.modules["synapse.server.auth"]
        # Reset cache for clean test
        auth_mod.reset_auth_cache()
        # No key configured -> always passes
        assert auth_mod.authenticate("any-token") is True

    def test_authenticate_rejects_bad_token(self):
        """authenticate() with explicit key should reject wrong token."""
        auth_mod = sys.modules["synapse.server.auth"]
        assert auth_mod.authenticate("wrong", "correct-key") is False
        assert auth_mod.authenticate("correct-key", "correct-key") is True


class TestPhase4MCPTools:
    """Phase 4: Verify cook_and_validate, diagnose, pipeline_status in MCP."""

    def test_phase4_tools_in_tools_list(self, server):
        """All 3 Phase 4 tools should appear in tools/list."""
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("tools/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        tool_names = [t["name"] for t in resp["result"]["tools"]]

        assert "tops_cook_and_validate" in tool_names
        assert "tops_diagnose" in tool_names
        assert "tops_pipeline_status" in tool_names

    def test_phase4_tool_annotations(self):
        """Phase 4 annotations: cook_and_validate destructive, diagnose/status read-only."""
        tools = {t["name"]: t for t in tools_mod.get_tools()}

        # cook_and_validate is destructive
        cv = tools["tops_cook_and_validate"]
        assert cv["annotations"]["readOnlyHint"] is False
        assert cv["annotations"]["destructiveHint"] is True

        # diagnose is read-only
        diag = tools["tops_diagnose"]
        assert diag["annotations"]["readOnlyHint"] is True
        assert diag["annotations"]["destructiveHint"] is False

        # pipeline_status is read-only
        ps = tools["tops_pipeline_status"]
        assert ps["annotations"]["readOnlyHint"] is True
        assert ps["annotations"]["destructiveHint"] is False


class TestNetworkExplainMCPTool:
    """Verify network_explain tool registration in MCP layer."""

    def test_network_explain_in_tools_list(self):
        """network_explain should appear in the tool registry."""
        assert tools_mod.has_tool("houdini_network_explain")

    def test_network_explain_tool_definition(self):
        """Tool definition should have correct annotations."""
        tools = {t["name"]: t for t in tools_mod.get_tools()}
        ne = tools["houdini_network_explain"]

        assert ne["annotations"]["readOnlyHint"] is True
        assert ne["annotations"]["destructiveHint"] is False
        assert ne["annotations"]["idempotentHint"] is True

        # Required param
        assert "root_path" in ne["inputSchema"]["properties"]
        assert "root_path" in ne["inputSchema"]["required"]

    def test_network_explain_dispatch(self):
        """Dispatch should map root_path to node in payload."""
        handler = MagicMock()
        response = MagicMock()
        response.success = True
        response.data = {"status": "ok", "node_count": 0}
        handler.handle.return_value = response

        result = tools_mod.dispatch_tool(
            handler, "houdini_network_explain",
            {"root_path": "/obj/geo1"},
        )
        assert "isError" not in result or result.get("isError") is not True

        # Verify the command sent to handler has "node" not "root_path"
        call_args = handler.handle.call_args[0][0]
        assert call_args.payload.get("node") == "/obj/geo1"


class TestModuleSingleton:
    def test_get_mcp_server_returns_same_instance(self):
        # Reset singleton
        server_mod._mcp_server = None
        s1 = server_mod.get_mcp_server()
        s2 = server_mod.get_mcp_server()
        assert s1 is s2
        # Cleanup
        server_mod._mcp_server = None


# ===========================================================================
# Tests: P1 Intelligence — Enriched Instructions
# ===========================================================================

class TestP1EnrichedInstructions:
    """P1: Verify MCP initialize instructions include workflow protocol."""

    def test_instructions_include_workflow(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        instructions = resp["result"]["instructions"]
        assert "inspect before mutating" in instructions

    def test_instructions_include_one_mutation(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        instructions = resp["result"]["instructions"]
        assert "One mutation per tool call" in instructions

    def test_instructions_include_usd_convention(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        instructions = resp["result"]["instructions"]
        assert "xn__inputsintensity_i0a" in instructions

    def test_instructions_include_lighting_law(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        instructions = resp["result"]["instructions"]
        assert "Intensity is ALWAYS 1.0" in instructions

    def test_instructions_include_session_start(self, server):
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, _ = server.handle_request(body)
        resp = _parse_response(resp_body)
        instructions = resp["result"]["instructions"]
        assert "synapse_project_setup" in instructions


# ===========================================================================
# Tests: P1 Intelligence — Enriched Tool Descriptions
# ===========================================================================

class TestP1EnrichedDescriptions:
    """P1: Verify critical tool descriptions are enriched."""

    def test_project_setup_description_first_in_session(self):
        tools = {t["name"]: t for t in tools_mod.get_tools()}
        desc = tools["synapse_project_setup"]["description"]
        assert "FIRST" in desc

    def test_execute_python_description_one_mutation(self):
        tools = {t["name"]: t for t in tools_mod.get_tools()}
        desc = tools["houdini_execute_python"]["description"]
        assert "ONE mutation" in desc

    def test_set_parm_description_encoded_names(self):
        tools = {t["name"]: t for t in tools_mod.get_tools()}
        desc = tools["houdini_set_parm"]["description"]
        assert "xn__inputsintensity_i0a" in desc


# ===========================================================================
# Tests: P1 Intelligence — Auto-Init Project Context
# ===========================================================================

class TestP1AutoInitProjectContext:
    """P1: Verify project context auto-loads on session start."""

    def test_session_has_project_context_attribute(self):
        """MCPSession should have a project_context slot."""
        mgr = session_mod.MCPSessionManager()
        sid = mgr.create_session({"name": "test"})
        session = mgr.get_session(sid)
        assert hasattr(session, "project_context")
        assert session.project_context is None

    def test_auto_init_calls_project_setup(self):
        """Initialize should attempt to call project_setup."""
        handler = MagicMock()
        response = MagicMock()
        response.success = True
        response.data = {"stage": "charmander", "scene_memory": {}}
        handler.handle.return_value = response

        srv = server_mod.MCPServer(handler=handler)
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, headers = srv.handle_request(body)

        # Verify handler.handle was called (for project_setup auto-init)
        assert handler.handle.called
        # Verify the command was project_setup
        call_args = handler.handle.call_args_list[0][0][0]
        assert call_args.type == "project_setup"

    def test_auto_init_caches_context_on_session(self):
        """Project context should be cached on the MCPSession."""
        handler = MagicMock()
        response = MagicMock()
        response.success = True
        response.data = {"stage": "charmander", "scene_memory": {"entries": []}}
        handler.handle.return_value = response

        srv = server_mod.MCPServer(handler=handler)
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        _, headers = srv.handle_request(body)

        sid = headers["Mcp-Session-Id"]
        session = srv._sessions.get_session(sid)
        assert session.project_context is not None

    def test_auto_init_failure_doesnt_break_init(self):
        """If project_setup fails, initialize should still succeed."""
        handler = MagicMock()
        handler.handle.side_effect = Exception("Houdini not ready")

        srv = server_mod.MCPServer(handler=handler)
        body = _jsonrpc("initialize", {"clientInfo": {"name": "test"}})
        resp_body, headers = srv.handle_request(body)

        resp = _parse_response(resp_body)
        assert "result" in resp
        assert "Mcp-Session-Id" in headers


# ===========================================================================
# Tests: P1 Intelligence — Project Context Resource
# ===========================================================================

class TestP1ProjectContextResource:
    """P1: Verify synapse://project/context resource is registered."""

    def test_project_context_resource_exists(self, server):
        """synapse://project/context should appear in resources/list."""
        init_body = _jsonrpc("initialize", {}, msg_id=1)
        _, headers = server.handle_request(init_body)
        sid = headers["Mcp-Session-Id"]

        body = _jsonrpc("resources/list", {}, msg_id=2)
        resp_body, _ = server.handle_request(body, session_id=sid)
        resp = _parse_response(resp_body)
        uris = [r["uri"] for r in resp["result"]["resources"]]
        assert "synapse://project/context" in uris

    def test_project_context_resource_has_description(self):
        """Resource should have a meaningful description."""
        from synapse.mcp.resources import get_resources
        resources = get_resources()
        ctx_resource = [r for r in resources if r["uri"] == "synapse://project/context"]
        assert len(ctx_resource) == 1
        assert "project memory" in ctx_resource[0]["description"].lower()


# ===========================================================================
# Tests: P1 Intelligence — Tool Group Modules
# ===========================================================================

class TestP1ToolGroupModules:
    """P1: Verify tool group modules are importable and consistent."""

    def test_scene_group_importable(self):
        """mcp_tools_scene should be importable."""
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            mod = importlib.import_module("mcp_tools_scene")
            assert hasattr(mod, "GROUP_KNOWLEDGE")
            assert hasattr(mod, "TOOL_NAMES")
            assert hasattr(mod, "DISPATCH_KEYS")
            assert len(mod.TOOL_NAMES) > 0
        finally:
            sys.path.pop(0)

    def test_render_group_importable(self):
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            mod = importlib.import_module("mcp_tools_render")
            assert "LIGHTING LAW" in mod.GROUP_KNOWLEDGE or "Intensity" in mod.GROUP_KNOWLEDGE
            assert "houdini_render" in mod.TOOL_NAMES
        finally:
            sys.path.pop(0)

    def test_usd_group_importable(self):
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            mod = importlib.import_module("mcp_tools_usd")
            assert "xn__inputs" in mod.GROUP_KNOWLEDGE
            assert "houdini_stage_info" in mod.TOOL_NAMES
        finally:
            sys.path.pop(0)

    def test_tops_group_importable(self):
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            mod = importlib.import_module("mcp_tools_tops")
            assert "tops_cook_node" in mod.TOOL_NAMES
        finally:
            sys.path.pop(0)

    def test_memory_group_importable(self):
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            mod = importlib.import_module("mcp_tools_memory")
            assert "synapse_project_setup" in mod.TOOL_NAMES
            assert "FIRST" in mod.GROUP_KNOWLEDGE or "project_setup" in mod.GROUP_KNOWLEDGE
        finally:
            sys.path.pop(0)

    def test_all_tools_covered_by_groups(self):
        """Every tool in the registry should belong to exactly one group."""
        import importlib
        _repo = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_repo))
        try:
            all_group_tools = set()
            for mod_name in ["mcp_tools_scene", "mcp_tools_render", "mcp_tools_usd",
                             "mcp_tools_tops", "mcp_tools_memory"]:
                mod = importlib.import_module(mod_name)
                for name in mod.TOOL_NAMES:
                    assert name not in all_group_tools, f"Duplicate: {name}"
                    all_group_tools.add(name)

            # Every tool in the registry should be in a group
            registry_tools = set(tools_mod.get_tool_names())
            missing = registry_tools - all_group_tools
            assert not missing, f"Tools not in any group: {missing}"
        finally:
            sys.path.pop(0)
