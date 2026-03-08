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
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

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
from .resources import get_resources, get_resource_templates, resolve_resource
from .tools import dispatch_tool, get_tools

# Resilience layer — shared with WebSocket server
try:
    from ..server.resilience import (
        RateLimiter,
        CircuitBreaker,
        CircuitBreakerConfig,
    )
    _RESILIENCE_AVAILABLE = True
except ImportError:
    _RESILIENCE_AVAILABLE = False

# Main-thread stall detection
try:
    from ..server.main_thread import is_main_thread_stalled
    _STALL_DETECT_AVAILABLE = True
except ImportError:
    _STALL_DETECT_AVAILABLE = False
    def is_main_thread_stalled():
        return False

# Fast JSON (He2025: sort_keys)
try:
    import orjson
    def _dumps(obj) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
except ImportError:
    def _dumps(obj) -> bytes:
        return json.dumps(obj, sort_keys=True).encode("utf-8")


logger = logging.getLogger("synapse.mcp")

# SSE event types
SSE_RENDER_PROGRESS = "synapse/render_progress"
SSE_GATE_REQUEST = "synapse/gate_request"
SSE_TOOLS_CHANGED = "synapse/tools_changed"
SSE_MEMORY_EVOLVED = "synapse/memory_evolved"
SSE_HEALTH_UPDATE = "synapse/health_update"

# Read-only tools: bypass resilience/rate-limiting in future fast-path.
# Derived from registry annotations instead of hardcoded list.
from ._tool_registry import TOOL_JSON as _TOOL_JSON_REGISTRY

_READ_ONLY_TOOLS: frozenset = frozenset(
    name for name, defn in _TOOL_JSON_REGISTRY.items()
    if defn.get("annotations", {}).get("readOnlyHint", False)
)

# Synapse version — read from package metadata if available, else hardcoded
try:
    from synapse import __version__ as _SYNAPSE_VERSION
except Exception:
    try:
        from importlib.metadata import version as _pkg_version
        _SYNAPSE_VERSION = _pkg_version("synapse-houdini")
    except Exception:
        _SYNAPSE_VERSION = "5.8.0"


# =========================================================================
# SSE Event Bus (polling pattern for hwebserver)
# =========================================================================

class SSEEventBus:
    """Per-session event queue for SSE polling.

    hwebserver does not support chunked transfer encoding or long-polling,
    so clients GET /mcp with Accept: text/event-stream and receive any
    queued events as a batch. The client polls again after a short delay.
    """

    def __init__(self, max_queue_size: int = 100):
        self._queues: Dict[str, list] = {}  # session_id -> [events]
        self._lock = threading.Lock()
        self._max_size = max_queue_size
        self._event_counter = 0

    def emit(self, session_id: str, event_type: str, data: dict) -> None:
        """Queue an event for a session."""
        with self._lock:
            if session_id not in self._queues:
                self._queues[session_id] = []
            q = self._queues[session_id]
            self._event_counter += 1
            q.append({
                "id": str(self._event_counter),
                "event": event_type,
                "data": json.dumps(data, sort_keys=True),
            })
            # Cap queue size -- drop oldest
            if len(q) > self._max_size:
                q[:] = q[-self._max_size:]

    def drain(self, session_id: str, last_event_id: Optional[str] = None) -> list:
        """Drain all queued events for a session.

        If last_event_id is provided, only return events after that ID.
        Returns list of event dicts.
        """
        with self._lock:
            q = self._queues.get(session_id, [])
            if not q:
                return []

            if last_event_id:
                # Find events after the given ID
                idx = None
                for i, evt in enumerate(q):
                    if evt["id"] == last_event_id:
                        idx = i
                        break
                if idx is not None:
                    events = q[idx + 1:]
                    q[:] = []  # Clear the full queue
                    return events

            events = list(q)
            q.clear()
            return events

    def create_session_queue(self, session_id: str) -> None:
        """Create an event queue for a new session."""
        with self._lock:
            if session_id not in self._queues:
                self._queues[session_id] = []

    def destroy_session_queue(self, session_id: str) -> None:
        """Remove and discard the event queue for a session."""
        with self._lock:
            self._queues.pop(session_id, None)

    def broadcast(self, event_type: str, data: dict) -> None:
        """Emit an event to ALL active sessions."""
        with self._lock:
            session_ids = list(self._queues.keys())
        for sid in session_ids:
            self.emit(sid, event_type, data)


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
        self._events = SSEEventBus()

        # Resilience (shared logic with WebSocket server)
        self._enable_resilience = _RESILIENCE_AVAILABLE and (
            os.environ.get("SYNAPSE_RESILIENCE", "").strip() != "0"
        )
        if self._enable_resilience:
            self._rate_limiter = RateLimiter()
            self._circuit_breaker = CircuitBreaker(
                name="synapse-mcp",
                config=CircuitBreakerConfig(
                    failure_threshold=5,
                    timeout_seconds=30.0,
                ),
            )
        else:
            self._rate_limiter = None
            self._circuit_breaker = None

        # Latency tracking (EMA)
        self._avg_latency = 0.0
        self._latency_alpha = 0.2

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
            result = self._route_method(method, params, session_id=session_id)
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

    def _route_method(self, method: str, params: dict, session_id: Optional[str] = None) -> dict:
        """Route a JSON-RPC method to its handler."""
        if method == "tools/list":
            return self._handle_tools_list(params)
        elif method == "tools/call":
            return self._handle_tools_call(params, session_id=session_id)
        elif method == "resources/list":
            return self._handle_resources_list(params)
        elif method == "resources/read":
            return self._handle_resources_read(params)
        elif method == "resources/templates/list":
            return self._handle_resource_templates_list(params)
        elif method == "ping":
            return self._handle_ping()
        else:
            raise JsonRpcMethodNotFound(method)

    # -----------------------------------------------------------------
    # Method handlers
    # -----------------------------------------------------------------

    def _handle_initialize(self, params: dict) -> dict:
        """MCP initialize handshake.

        Creates a session, returns server capabilities, and pre-loads
        project context for the session (best-effort).
        """
        client_info = params.get("clientInfo", {})
        session_id = self._sessions.create_session(client_info)
        self._sessions.mark_initialized(session_id)
        self._events.create_session_queue(session_id)

        # Auto-load project context so agents start with full memory
        session = self._sessions.get_session(session_id)
        if session is not None:
            try:
                handler = self._get_handler()
                try:
                    import hdefereval
                    result = hdefereval.executeInMainThreadWithResult(
                        dispatch_tool, handler, "synapse_project_setup", {}
                    )
                except ImportError:
                    result = dispatch_tool(handler, "synapse_project_setup", {})
                if not result.get("isError"):
                    session.project_context = result
            except Exception:
                pass  # Best-effort — don't fail the handshake

        return {
            "_session_id": session_id,  # stripped before sending
            "capabilities": {
                "tools": {"listChanged": True},
                "resources": {"subscribe": False, "listChanged": False},
            },
            "instructions": (
                "SYNAPSE is a bridge between AI agents and SideFX Houdini. "
                "WORKFLOW: Always inspect before mutating. One mutation per tool call. "
                "Verify every mutation result. Use ensure_* guard functions for idempotency.\n\n"
                "SAFETY: All mutations go through atomic scripts, idempotent guards, "
                "and undo-group transactions. execute_python wraps in undo group.\n\n"
                "CRITICAL USD CONVENTION: Houdini 21 USD light parameters use encoded names: "
                "xn__inputsintensity_i0a (not 'intensity'), xn__inputscolor_vya (not 'color'), "
                "xn__inputsexposure_vya (not 'exposure'). Always inspect a node first "
                "to get exact parameter names.\n\n"
                "LIGHTING LAW: Intensity is ALWAYS 1.0. Brightness controlled by exposure (stops). "
                "Key:fill ratio 3:1 = 1.585 stops difference.\n\n"
                "TONE: You are a supportive senior VFX artist. Never blame. Always suggest next steps. "
                "Error messages should make artists want to keep going, not close the app.\n\n"
                "START EVERY SESSION: Call synapse_project_setup to load project/scene memory. "
                "This gives you full context about the artist's project and previous decisions."
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

    def _handle_tools_call(self, params: dict, session_id: Optional[str] = None) -> dict:
        """Dispatch a tool call with resilience checks.

        Tool calls go through hdefereval.executeInMainThreadWithResult()
        because hwebserver @urlHandler callbacks run on worker threads,
        but hou.* calls require the main thread.

        Resilience gates (rate limiter, circuit breaker, stall detection)
        match the WebSocket server's behavior so both transports have the
        same safety guarantees.

        If dispatch_tool returns isError=True, we raise a JsonRpcError so
        MCP clients receive a proper JSON-RPC error response instead of a
        success response with error content buried inside.
        """
        tool_name = params.get("name")
        if not tool_name:
            raise JsonRpcInvalidParams("Missing 'name' in tools/call params")

        arguments = params.get("arguments", {})
        handler = self._get_handler()

        # Read-only tools bypass resilience (cheap reads can't cause cascading failures)
        if tool_name in _READ_ONLY_TOOLS:
            try:
                import hdefereval
                result = hdefereval.executeInMainThreadWithResult(
                    dispatch_tool, handler, tool_name, arguments
                )
            except ImportError:
                result = dispatch_tool(handler, tool_name, arguments)
            if self._circuit_breaker and not (isinstance(result, dict) and result.get("isError")):
                self._circuit_breaker.record_success()
            return result

        # --- Resilience gates (match WebSocket server behavior) ---

        # 1. Main-thread stall detection
        if _STALL_DETECT_AVAILABLE and is_main_thread_stalled():
            if self._circuit_breaker:
                self._circuit_breaker.record_failure()
            raise JsonRpcError(
                INTERNAL_ERROR,
                "Houdini's main thread is unresponsive — commands will resume when it recovers",
            )

        # 2. Rate limiting (keyed by MCP session, not per-client like WS)
        if self._enable_resilience and self._rate_limiter:
            allowed, info = self._rate_limiter.acquire("mcp")
            if not allowed:
                raise JsonRpcError(
                    INTERNAL_ERROR,
                    "Synapse is handling a lot of requests right now — "
                    "try again in a moment ({})".format(info.get("reason", "")),
                )

        # 3. Circuit breaker
        if self._enable_resilience and self._circuit_breaker:
            can_exec, cb_info = self._circuit_breaker.can_execute()
            if not can_exec:
                raise JsonRpcError(
                    INTERNAL_ERROR,
                    "Synapse paused commands temporarily to recover from errors — "
                    "it'll resume shortly ({})".format(cb_info.get("reason", "")),
                )

        # Notify SSE subscribers about critical tool execution
        if session_id is not None and tool_name in (
            "houdini_execute_python", "houdini_execute_vex",
        ):
            self._events.emit(session_id, SSE_GATE_REQUEST, {
                "level": "critical",
                "operation": tool_name,
            })

        # --- Dispatch with latency tracking ---
        t0 = time.monotonic()

        try:
            import hdefereval
            result = hdefereval.executeInMainThreadWithResult(
                dispatch_tool, handler, tool_name, arguments
            )
        except ImportError:
            result = dispatch_tool(handler, tool_name, arguments)

        elapsed = time.monotonic() - t0
        self._avg_latency = (
            self._latency_alpha * elapsed
            + (1 - self._latency_alpha) * self._avg_latency
        )

        # Propagate tool errors to JSON-RPC layer so MCP clients detect failures
        if isinstance(result, dict) and result.get("isError"):
            error_text = "Unknown error"
            content = result.get("content", [])
            if content and isinstance(content[0], dict):
                error_text = content[0].get("text", error_text)
            # Only record infrastructure failures for circuit breaker
            # (not user errors like "node not found")
            if any(k in error_text.lower() for k in ("timeout", "main thread", "crashed", "unresponsive")):
                if self._circuit_breaker:
                    self._circuit_breaker.record_failure()
                self.broadcast_event(SSE_HEALTH_UPDATE, {
                    "component": "mcp",
                    "reason": error_text[:200],
                    "status": "degraded",
                })
            raise JsonRpcError(INTERNAL_ERROR, error_text)

        if self._circuit_breaker:
            self._circuit_breaker.record_success()

        # Emit completion event for SSE subscribers
        if session_id is not None:
            self._events.emit(session_id, "synapse/tool_complete", {
                "latency_ms": round(elapsed * 1000),
                "tool": tool_name,
            })

        # Render-related tools get a progress event
        if session_id is not None and tool_name in (
            "houdini_render", "synapse_safe_render",
            "synapse_autonomous_render", "synapse_render_progressively",
            "synapse_render_sequence", "tops_render_sequence",
        ):
            self._events.emit(session_id, SSE_RENDER_PROGRESS, {
                "latency_ms": round(elapsed * 1000),
                "status": "complete",
                "tool": tool_name,
            })

        return result

    def _handle_ping(self) -> dict:
        """MCP ping — empty result."""
        return {}

    def _handle_resources_list(self, params: dict) -> dict:
        """Return all available MCP resources."""
        return {"resources": get_resources()}

    def _handle_resource_templates_list(self, params: dict) -> dict:
        """Return all MCP resource templates."""
        return {"resourceTemplates": get_resource_templates()}

    def _handle_resources_read(self, params: dict) -> dict:
        """Read a resource by URI, dispatching to the appropriate handler."""
        uri = params.get("uri")
        if not uri:
            raise JsonRpcInvalidParams("Missing 'uri' in resources/read params")

        resolved = resolve_resource(uri)
        if resolved is None:
            raise JsonRpcInvalidParams(f"Unknown resource URI: {uri}")

        handler_name, payload = resolved
        handler = self._get_handler()

        # Build a SynapseCommand and dispatch through the handler
        from ..core.protocol import SynapseCommand
        command = SynapseCommand(
            type=handler_name,
            id=f"mcp-resource-{uri}",
            payload=payload,
        )

        try:
            import hdefereval
            response = hdefereval.executeInMainThreadWithResult(
                handler.handle, command
            )
        except ImportError:
            response = handler.handle(command)

        if response.success:
            import json as _json
            text = _json.dumps(response.data, sort_keys=True) if isinstance(response.data, dict) else str(response.data or "")
            return {
                "contents": [{
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": text,
                }]
            }
        else:
            raise JsonRpcInvalidParams(response.error or f"Failed to read resource: {uri}")

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
        self._events.destroy_session_queue(session_id)
        return self._sessions.destroy_session(session_id)

    # -----------------------------------------------------------------
    # SSE event emission
    # -----------------------------------------------------------------

    def emit_event(self, session_id: str, event_type: str, data: dict) -> None:
        """Queue a server-initiated event for a session."""
        self._events.emit(session_id, event_type, data)

    def broadcast_event(self, event_type: str, data: dict) -> None:
        """Queue an event for all active sessions."""
        self._events.broadcast(event_type, data)

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

        # Bearer token auth (opt-in: only when SYNAPSE_API_KEY or auth.key is configured)
        try:
            from ..server.auth import get_auth_key, authenticate
            auth_key = get_auth_key()
            if auth_key is not None:
                auth_header = request.headers().get("Authorization", "")
                token = ""
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()
                if not authenticate(token, auth_key):
                    return hwebserver.Response(
                        '{"error": "Unauthorized. Provide a valid Bearer token."}',
                        status=401,
                        content_type="application/json",
                    )
        except ImportError:
            pass  # auth module not available — skip

        # Origin validation (DNS rebinding protection)
        try:
            from ..server.auth import validate_origin
            origin = request.headers().get("Origin", "")
            deploy_mode = os.environ.get("SYNAPSE_DEPLOY_MODE", "local")
            if not validate_origin(origin, deploy_mode=deploy_mode):
                return hwebserver.Response(
                    '{"error": "Origin not allowed"}',
                    status=403,
                    content_type="application/json",
                )
        except ImportError:
            pass  # auth module not available

        if request.method() == "POST":
            body = request.body()
            if isinstance(body, str):
                body = body.encode("utf-8")

            session_id = request.headers().get("Mcp-Session-Id")
            response_body, headers = server.handle_request(body, session_id)

            if response_body is None:
                # Notification — 204 No Content
                return hwebserver.Response("", status=204, content_type="text/plain")

            data = response_body.decode("utf-8") if isinstance(response_body, bytes) else response_body
            resp = hwebserver.Response(
                data,
                status=200,
                content_type=headers.get("Content-Type", "application/json"),
            )
            for key, val in headers.items():
                if key != "Content-Type":
                    resp.setHeader(key, val)
            return resp

        elif request.method() == "DELETE":
            session_id = request.headers().get("Mcp-Session-Id")
            if session_id:
                server.destroy_session(session_id)
            return hwebserver.Response("", status=200, content_type="text/plain")

        elif request.method() == "GET":
            # SSE polling -- drain queued events for the session
            accept = request.headers().get("Accept", "")
            if "text/event-stream" not in accept:
                return hwebserver.Response(
                    '{"error": "GET /mcp requires Accept: text/event-stream"}',
                    status=406,
                    content_type="application/json",
                )

            session_id = request.headers().get("Mcp-Session-Id")
            if not session_id:
                return hwebserver.Response(
                    '{"error": "Missing Mcp-Session-Id header"}',
                    status=400,
                    content_type="application/json",
                )

            # Validate session exists
            session = server._sessions.get_session(session_id)
            if session is None:
                return hwebserver.Response(
                    '{"error": "Unknown session"}',
                    status=404,
                    content_type="application/json",
                )

            last_event_id = request.headers().get("Last-Event-ID")
            events = server._events.drain(session_id, last_event_id)

            if not events:
                # No events -- return empty SSE with retry hint
                body = ": no events\nretry: 2000\n\n"
            else:
                lines = []
                for evt in events:
                    lines.append("id: {}".format(evt["id"]))
                    lines.append("event: {}".format(evt["event"]))
                    lines.append("data: {}".format(evt["data"]))
                    lines.append("")  # blank line = end of event
                body = "\n".join(lines) + "\n"

            resp = hwebserver.Response(
                body,
                status=200,
                content_type="text/event-stream",
            )
            resp.setHeader("Cache-Control", "no-cache")
            resp.setHeader("Mcp-Session-Id", session_id)
            return resp

        else:
            return hwebserver.Response(
                '{"error": "Method not allowed. Use POST, GET, or DELETE."}',
                status=405,
                content_type="application/json",
            )

    logger.info("MCP endpoint registered at /mcp (hwebserver)")

except ImportError:
    # Not running inside Houdini — hwebserver not available.
    # MCPServer still works standalone for testing.
    pass
