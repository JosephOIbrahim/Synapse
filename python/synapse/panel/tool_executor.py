"""
Main-Thread Tool Executor -- Qt signal/slot bridge for Houdini panel.

The Claude API worker runs on a QThread and cannot call hou.* directly.
This module provides a ToolRequest + ToolExecutor pair that bridges the gap:

  1. Worker creates a ToolRequest (with a threading.Event)
  2. Worker emits a Qt signal carrying the request
  3. Qt's AutoConnection delivers the signal to ToolExecutor on the main thread
  4. ToolExecutor dispatches through SynapseHandler (which calls hou.*)
  5. ToolExecutor sets request.result/error and fires request.done
  6. Worker's request.done.wait() unblocks

All hou.* calls happen on the main thread. The worker never touches hou.

An optional MCP dispatch path is available via :func:`try_mcp_tool_call`.
Worker threads can call this *before* emitting the Qt signal to route
through the local hwebserver MCP endpoint, gaining resilience (circuit
breaker, rate limiter), journal logging, and session tracking for free.
The MCP path must NOT be called from the main thread (deadlock risk with
hdefereval).
"""

from __future__ import annotations

import http.client
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from .tool_bridge import get_tool_dispatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ToolRequest -- data object shared between worker thread and main thread
# ---------------------------------------------------------------------------

@dataclass
class ToolRequest:
    """Request object passed from worker thread to main-thread executor.

    The worker creates this, emits it via signal, then calls
    ``done.wait(timeout=30.0)`` to block until the executor finishes.

    Attributes:
        tool_use_id: The ``id`` from the Anthropic API tool_use content block.
        tool_name:   MCP tool name (e.g. ``"create_node"``).
        tool_input:  Tool arguments dict from the API.
        result:      Set by executor on success (response.data).
        error:       Set by executor on failure (error message string).
        done:        Threading event -- set by executor when processing is complete.
    """
    tool_use_id: str
    tool_name: str
    tool_input: dict
    result: Any = field(default=None, repr=False)
    error: Optional[str] = None
    done: threading.Event = field(default_factory=threading.Event, repr=False)


# ---------------------------------------------------------------------------
# MCP local client (lightweight -- stdlib only)
# ---------------------------------------------------------------------------

class _MCPLocalClient:
    """Lightweight JSON-RPC client for the local hwebserver MCP endpoint.

    Uses http.client (stdlib) so there are zero external dependencies.
    Manages a single MCP session with auto-initialize on first use.

    NOT safe to use from the main thread -- the MCP endpoint dispatches
    tool calls back to the main thread via hdefereval, so calling from
    the main thread would deadlock.
    """

    def __init__(self):
        self._session_id: Optional[str] = None
        self._port: Optional[int] = None
        self._lock = threading.Lock()

    def _detect_port(self) -> Optional[int]:
        """Detect hwebserver port from Houdini."""
        try:
            import hou
            return hou.webServer.port()
        except Exception:
            return None

    @property
    def available(self) -> bool:
        """Check if MCP endpoint is likely reachable."""
        if self._port is None:
            self._port = self._detect_port()
        return self._port is not None

    def _post(self, body: dict, headers: Optional[dict] = None) -> dict:
        """POST JSON-RPC to localhost MCP endpoint. Returns parsed response."""
        if self._port is None:
            raise ConnectionError("hwebserver port unknown")

        all_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if headers:
            all_headers.update(headers)

        payload = json.dumps(body, sort_keys=True).encode("utf-8")

        conn = http.client.HTTPConnection("localhost", self._port, timeout=35)
        try:
            conn.request("POST", "/mcp", body=payload, headers=all_headers)
            resp = conn.getresponse()
            data = resp.read().decode("utf-8")

            # Capture session ID from response headers
            session_hdr = resp.getheader("Mcp-Session-Id")
            if session_hdr:
                self._session_id = session_hdr

            return json.loads(data)
        finally:
            conn.close()

    def _ensure_session(self) -> str:
        """Initialize an MCP session if we don't have one."""
        with self._lock:
            if self._session_id is not None:
                return self._session_id

            result = self._post({
                "jsonrpc": "2.0",
                "id": "panel-init-{}".format(int(time.time() * 1000)),
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "synapse-panel",
                        "version": "1.0.0",
                    },
                    "protocolVersion": "2025-06-18",
                },
            })

            if "error" in result:
                raise ConnectionError(
                    "MCP initialize failed: {}".format(result["error"])
                )

            if self._session_id is None:
                raise ConnectionError("No Mcp-Session-Id in response")

            return self._session_id

    def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a tool via MCP. Returns the result dict.

        Raises ConnectionError if MCP is unreachable.
        Raises RuntimeError if the tool call returns a JSON-RPC error.
        """
        session_id = self._ensure_session()

        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": "panel-{}-{}".format(tool_name, int(time.time() * 1000)),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            },
            headers={"Mcp-Session-Id": session_id},
        )

        if "error" in result:
            error_msg = result["error"].get("message", "Unknown MCP error")
            # Session may have expired -- clear it so next call re-initializes
            if result["error"].get("code") == -32003:  # SESSION_INVALID
                with self._lock:
                    self._session_id = None
            raise RuntimeError(error_msg)

        return result.get("result", {})

    def reset(self) -> None:
        """Reset the client (e.g., on session expiry)."""
        with self._lock:
            self._session_id = None
            self._port = None


# Module-level MCP client singleton
_mcp_client = _MCPLocalClient()


# ---------------------------------------------------------------------------
# ToolExecutor -- QObject living on the main thread
# ---------------------------------------------------------------------------

class ToolExecutor(QtCore.QObject):
    """Executes Synapse tool calls on Houdini's main thread.

    Created by the panel (which itself lives on the main thread).
    The worker thread connects its signal to :meth:`execute_tool`; Qt's
    ``AutoConnection`` ensures the slot runs on the main thread.

    Usage::

        executor = ToolExecutor()       # in panel setup (main thread)
        worker.tool_signal.connect(executor.execute_tool)

        # In worker thread:
        req = ToolRequest(tool_use_id="tu_abc", tool_name="create_node",
                          tool_input={"type": "geo", "path": "/obj"})
        worker.tool_signal.emit(req)
        req.done.wait(timeout=30.0)
        if req.error:
            ...  # handle error
        else:
            ...  # use req.result
    """

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._handler = None  # Lazy-loaded SynapseHandler

    # ------------------------------------------------------------------
    # Lazy handler initialisation
    # ------------------------------------------------------------------

    def _get_handler(self):
        """Lazy-load SynapseHandler to avoid importing hou at module level.

        Returns the cached handler instance, or None if the import fails
        (e.g. running outside Houdini).
        """
        if self._handler is not None:
            return self._handler

        try:
            from synapse.server.handlers import SynapseHandler
            self._handler = SynapseHandler()
            logger.debug("SynapseHandler initialised for ToolExecutor")
        except Exception:
            logger.exception("Failed to import/create SynapseHandler")
            # Leave self._handler as None so we retry next call
        return self._handler

    # ------------------------------------------------------------------
    # Main-thread slot
    # ------------------------------------------------------------------

    @QtCore.Slot(object)
    def execute_tool(self, request: ToolRequest) -> None:
        """Execute a tool request on the main thread.

        Connected to the worker's signal via Qt AutoConnection, which
        guarantees this runs on the thread that owns the ToolExecutor
        (the main thread).

        Args:
            request: The ToolRequest to process. On return, either
                ``request.result`` or ``request.error`` will be set,
                and ``request.done`` will be signalled.
        """
        try:
            # 1. Resolve tool name to (command_type, payload_builder)
            dispatch = get_tool_dispatch(request.tool_name)
            if dispatch is None:
                request.error = f"Unknown tool: {request.tool_name}"
                logger.warning("No dispatch for tool %r", request.tool_name)
                return

            cmd_type, payload_builder = dispatch

            # 2. Build payload from tool input
            payload = payload_builder(request.tool_input)

            # 3. Create SynapseCommand
            from synapse.core.protocol import SynapseCommand
            command = SynapseCommand(
                type=cmd_type,
                id=f"panel-{request.tool_name}-{int(time.time() * 1000)}",
                payload=payload,
            )

            # 4. Get handler (lazy init)
            handler = self._get_handler()
            if handler is None:
                request.error = (
                    "SynapseHandler unavailable -- "
                    "hou module may not be loaded yet"
                )
                return

            # 5. Dispatch (through bridge if available, direct otherwise)
            try:
                from synapse.panel.bridge_adapter import (
                    execute_through_bridge, is_read_only,
                )
                if not is_read_only(request.tool_name):
                    response = execute_through_bridge(
                        request.tool_name, handler, command,
                    )
                else:
                    response = handler.handle(command)
            except ImportError:
                response = handler.handle(command)

            # 6. Transfer result
            if response.success:
                request.result = response.data
            else:
                request.error = response.error or "Tool execution failed"

        except Exception as exc:
            logger.exception(
                "Unhandled exception executing tool %r", request.tool_name
            )
            request.error = f"Exception: {exc}"

        finally:
            # ALWAYS signal done -- the worker thread is blocking on this
            request.done.set()


# ---------------------------------------------------------------------------
# MCP dispatch helper (for worker threads)
# ---------------------------------------------------------------------------

def try_mcp_tool_call(
    tool_name: str, arguments: dict
) -> Optional[dict]:
    """Try dispatching a tool call through the local MCP endpoint.

    Safe to call from any thread (worker threads, background threads).
    NOT safe to call from the main thread (will deadlock with hdefereval).

    Returns:
        Result dict on success, None if MCP is unavailable.

    Raises:
        RuntimeError: If MCP returned a JSON-RPC error (tool-level failure).
    """
    if not _mcp_client.available:
        return None
    try:
        return _mcp_client.call_tool(tool_name, arguments)
    except (ConnectionError, OSError):
        return None
