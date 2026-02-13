"""
MCP Endpoint Handler

Handles MCP JSON-RPC 2.0 requests over Streamable HTTP transport.
Integrates with Houdini's hwebserver via @hwebserver.urlHandler("/mcp").

This module runs INSIDE Houdini. The dispatch path is:

    HTTP POST /mcp  ->  handle_mcp_request()  ->  method router
        initialize       ->  _handle_initialize()
        tools/list       ->  _handle_tools_list()
        tools/call       ->  _handle_tools_call()  ->  tools.dispatch_tool()
        ping             ->  _handle_ping()
        notifications/*  ->  (acknowledged, no response)

MCP Protocol Version: 2025-06-18
"""

import json
import logging
import time
from typing import Any, Optional, Tuple

from .protocol import (
    MCP_PROTOCOL_VERSION,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    SESSION_INVALID,
    JsonRpcError,
    JsonRpcInvalidParams,
    JsonRpcMethodNotFound,
    error_from_exception,
    is_notification,
    jsonrpc_error,
    jsonrpc_result,
    parse_request,
)
from .session import MCPSessionManager
from .tools import dispatch_tool, get_tools

# Fast JSON (He2025: sort_keys)
try:
    import orjson
    def _dumps(obj) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
except ImportError:
    def _dumps(obj) -> bytes:
        return json.dumps(obj, sort_keys=True).encode("utf-8")


logger = logging.getLogger("synapse.mcp")

# Synapse version — read from package metadata if available, else hardcoded
try:
    from importlib.metadata import version as _pkg_version
    _SYNAPSE_VERSION = _pkg_version("synapse")
except Exception:
    _SYNAPSE_VERSION = "5.3.0"


# =========================================================================
# MCP Server
# =========================================================================

class MCPServer:
    """MCP protocol server handling JSON-RPC requests.

    Manages sessions, routes methods, and dispatches tool calls
    through the existing SynapseHandler infrastructure.
    """

    def __init__(self, handler=None):
        """Initialize the MCP server.

        Args:
            handler: Optional SynapseHandler instance. If None, one will
                     be created lazily on first tool call.
        """
        self._handler = handler
        self._sessions = MCPSessionManager()

    def _get_handler(self):
        if self._handler is None:
            from ..server.handlers import SynapseHandler
            self._handler = SynapseHandler()
        return self._handler

    # -----------------------------------------------------------------
    # Request handling
    # -----------------------------------------------------------------

    def handle_request(
        self,
        body: bytes,
        session_id: Optional[str] = None,
    ) -> Tuple[Optional[bytes], dict]:
        """Handle an MCP HTTP POST request.

        Args:
            body: Raw request body (JSON-RPC 2.0).
            session_id: Mcp-Session-Id header value (None for initialize).

        Returns:
            Tuple of (response_body, headers_dict).
            response_body is None for notifications (no response expected).
            headers_dict always includes Content-Type and may include
            Mcp-Session-Id.
        """
        headers = {"Content-Type": "application/json"}

        # Parse JSON-RPC
        try:
            msg = parse_request(body)
        except JsonRpcError as e:
            return error_from_exception(None, e), headers

        msg_id = msg.get("id")
        method = msg["method"]
        params = msg.get("params", {})

        # Notifications have no id — process silently
        if is_notification(msg):
            self._handle_notification(method, params, session_id)
            return None, headers

        # Session validation (initialize creates session, everything else needs one)
        if method == "initialize":
            result = self._handle_initialize(params)
            new_session_id = result.pop("_session_id")
            headers["Mcp-Session-Id"] = new_session_id
            return jsonrpc_result(msg_id, result), headers

        # All other methods require a valid session
        if session_id is None:
            return jsonrpc_error(
                msg_id, SESSION_INVALID,
                "Missing Mcp-Session-Id header. Send initialize first.",
            ), headers

        session = self._sessions.get_session(session_id)
        if session is None:
            return jsonrpc_error(
                msg_id, SESSION_INVALID,
                f"Unknown session: {session_id}",
            ), headers

        headers["Mcp-Session-Id"] = session_id

        # Route to method handler
        try:
            result = self._route_method(method, params)
            return jsonrpc_result(msg_id, result), headers
        except JsonRpcError as e:
            return error_from_exception(msg_id, e), headers
        except Exception as e:
            logger.exception("Unhandled error in %s", method)
            return jsonrpc_error(
                msg_id, INTERNAL_ERROR,
                f"Internal error: {e}",
            ), headers

    # -----------------------------------------------------------------
    # Method routing
    # -----------------------------------------------------------------

    def _route_method(self, method: str, params: dict) -> dict:
        """Route a JSON-RPC method to its handler."""
        if method == "tools/list":
            return self._handle_tools_list(params)
        elif method == "tools/call":
            return self._handle_tools_call(params)
        elif method == "ping":
            return self._handle_ping()
        else:
            raise JsonRpcMethodNotFound(method)

    # -----------------------------------------------------------------
    # Method handlers
    # -----------------------------------------------------------------

    def _handle_initialize(self, params: dict) -> dict:
        """MCP initialize handshake.

        Creates a session and returns server capabilities.
        """
        client_info = params.get("clientInfo", {})
        session_id = self._sessions.create_session(client_info)
        self._sessions.mark_initialized(session_id)

        return {
            "_session_id": session_id,  # stripped before sending
            "capabilities": {
                "tools": {"listChanged": True},
            },
            "instructions": (
                "SYNAPSE is a bridge between AI agents and SideFX Houdini. "
                "All mutations go through safety middleware enforcing atomic "
                "scripts, idempotent guards, and undo-group transactions. "
                "Tools that modify the scene are destructive unless noted otherwise."
            ),
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "serverInfo": {
                "name": "synapse",
                "version": _SYNAPSE_VERSION,
            },
        }

    def _handle_tools_list(self, params: dict) -> dict:
        """Return all available MCP tools."""
        return {"tools": get_tools()}

    def _handle_tools_call(self, params: dict) -> dict:
        """Dispatch a tool call to SynapseHandler."""
        tool_name = params.get("name")
        if not tool_name:
            raise JsonRpcInvalidParams("Missing 'name' in tools/call params")

        arguments = params.get("arguments", {})
        handler = self._get_handler()
        return dispatch_tool(handler, tool_name, arguments)

    def _handle_ping(self) -> dict:
        """MCP ping — empty result."""
        return {}

    # -----------------------------------------------------------------
    # Notifications
    # -----------------------------------------------------------------

    def _handle_notification(
        self, method: str, params: dict, session_id: Optional[str]
    ) -> None:
        """Handle a notification (no response expected)."""
        if method == "notifications/initialized":
            if session_id:
                self._sessions.mark_initialized(session_id)
        elif method == "notifications/cancelled":
            # Acknowledged — cancellation not yet implemented
            pass
        # Unknown notifications are silently ignored per MCP spec

    # -----------------------------------------------------------------
    # Session management
    # -----------------------------------------------------------------

    def destroy_session(self, session_id: str) -> bool:
        """Destroy a session (e.g. on HTTP DELETE /mcp)."""
        return self._sessions.destroy_session(session_id)

    @property
    def active_sessions(self) -> int:
        """Number of active MCP sessions."""
        return self._sessions.active_count


# =========================================================================
# Module-level singleton (for hwebserver integration)
# =========================================================================

_mcp_server: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Get or create the module-level MCPServer singleton."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = MCPServer()
    return _mcp_server


# =========================================================================
# hwebserver integration (conditional — only when running inside Houdini)
# =========================================================================

try:
    import hwebserver

    @hwebserver.urlHandler("/mcp")
    def _mcp_url_handler(request):
        """HTTP POST /mcp handler for MCP Streamable HTTP transport."""
        server = get_mcp_server()

        if request.method() == "POST":
            body = request.body()
            if isinstance(body, str):
                body = body.encode("utf-8")

            session_id = request.headers().get("Mcp-Session-Id")
            response_body, headers = server.handle_request(body, session_id)

            if response_body is None:
                # Notification — 204 No Content
                return hwebserver.Response(
                    204, "", "text/plain",
                )

            resp = hwebserver.Response(
                200,
                response_body.decode("utf-8") if isinstance(response_body, bytes) else response_body,
                headers.get("Content-Type", "application/json"),
            )
            for key, val in headers.items():
                if key != "Content-Type":
                    resp.setHeader(key, val)
            return resp

        elif request.method() == "DELETE":
            session_id = request.headers().get("Mcp-Session-Id")
            if session_id:
                server.destroy_session(session_id)
            return hwebserver.Response(200, "", "text/plain")

        else:
            # GET for SSE — Phase 2
            return hwebserver.Response(
                405,
                '{"error": "Method not allowed. Use POST for MCP requests."}',
                "application/json",
            )

    logger.info("MCP endpoint registered at /mcp (hwebserver)")

except ImportError:
    # Not running inside Houdini — hwebserver not available.
    # MCPServer still works standalone for testing.
    pass
