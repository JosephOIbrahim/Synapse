"""
Synapse hwebserver Adapter

Native C++ WebSocket server using Houdini's built-in hwebserver module.
Eliminates: Python websockets dependency, daemon threads, haio.py conflicts,
watchdog false positives, and thread pool dispatching.

Usage (inside Houdini):
    from synapse.server.hwebserver_adapter import start_hwebserver, stop_hwebserver
    start_hwebserver(port=9999)

Architecture:
    Claude Desktop  <-[stdio/JSON-RPC]->  mcp_server.py  <-[WebSocket]->  hwebserver (C++)
                                                                            |
                                                                         SynapseWS.receive()
                                                                            |
                                                                         SynapseHandler.handle()
                                                                            |
                                                                         hou module
"""

import json
import logging
import threading
from typing import Dict, Optional

# Fast JSON — orjson if available, stdlib fallback
try:
    import orjson
    def _dumps(obj):
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode()
except ImportError:
    _dumps = json.dumps

logger = logging.getLogger("synapse.hwebserver")

try:
    import hwebserver
    HWEBSERVER_AVAILABLE = True
except ImportError:
    HWEBSERVER_AVAILABLE = False

try:
    import hou
except ImportError:
    pass

from ..core.protocol import (
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
)
from .handlers import SynapseHandler
from .resilience import RateLimiter, BackpressureController
from ..session.tracker import get_bridge


# =============================================================================
# HWEBSERVER WEBSOCKET HANDLER
# =============================================================================

# Module-level state (hwebserver decorators require module-level class defs)
_handler: Optional[SynapseHandler] = None
_rate_limiter: Optional[RateLimiter] = None
_backpressure: Optional[BackpressureController] = None
_client_counter = 0
_client_lock = threading.Lock()
_client_sessions: Dict[int, str] = {}  # counter -> session_id
_running = False
_port = 0


def _get_handler() -> SynapseHandler:
    global _handler
    if _handler is None:
        _handler = SynapseHandler()
    return _handler


def _next_client_id() -> str:
    global _client_counter
    with _client_lock:
        _client_counter += 1
        return f"client_{PROTOCOL_VERSION}_{_client_counter:05d}"


if HWEBSERVER_AVAILABLE:
    @hwebserver.webSocket("/synapse")
    class SynapseWS(hwebserver.WebSocket):
        """
        Native Houdini WebSocket handler for Synapse protocol.

        Handles the same SynapseCommand/SynapseResponse JSON wire format
        as the Python websockets server, but runs inside Houdini's C++
        multi-threaded server — no daemon threads, no asyncio, no haio.py.
        """

        async def connect(self, req):
            """Accept WebSocket upgrade — lightweight, no context loading."""
            self._client_id = _next_client_id()
            self._session_id = None
            self._ws_id = _client_counter
            await self.accept()
            logger.info("Client connected: %s", self._client_id)

        async def receive(self, text_data=None, bytes_data=None):
            """Handle incoming SynapseCommand message."""
            if text_data is None:
                return

            try:
                command = SynapseCommand.from_json(text_data)

                # Heartbeat fast path (orjson bypass — skip protocol overhead)
                if command.type == "heartbeat":
                    await self.send(_dumps({
                        "id": command.id,
                        "success": True,
                        "data": {"pong": True},
                        "sequence": command.sequence,
                        "protocol_version": PROTOCOL_VERSION,
                    }), is_binary=False)
                    return

                # Ping/health bypass rate limiting
                if command.type in ("ping", "get_health"):
                    handler = _get_handler()
                    response = handler.handle(command)
                    await self.send(response.to_json(), is_binary=False)
                    return

                # Rate limiting (if enabled)
                if _rate_limiter:
                    allowed, info = _rate_limiter.acquire(self._client_id)
                    if not allowed:
                        await self.send(SynapseResponse(
                            id=command.id,
                            success=False,
                            error=f"Rate limited: {info.get('reason')}",
                            data={"retry_after": info.get("retry_after", 1.0)},
                            sequence=command.sequence
                        ).to_json(), is_binary=False)
                        return

                # Lazy session creation
                if self._session_id is None:
                    bridge = get_bridge()
                    self._session_id = bridge.start_session(self._client_id)
                    _get_handler().set_session_id(self._session_id)
                    _client_sessions[self._ws_id] = self._session_id

                # Dispatch to handler
                handler = _get_handler()
                response = handler.handle(command)
                await self.send(response.to_json(), is_binary=False)

            except json.JSONDecodeError as e:
                await self.send(SynapseResponse(
                    id="unknown",
                    success=False,
                    error=f"Invalid JSON: {e}"
                ).to_json(), is_binary=False)
            except Exception as e:
                await self.send(SynapseResponse(
                    id="unknown",
                    success=False,
                    error=str(e)
                ).to_json(), is_binary=False)

        async def disconnect(self, code):
            """Clean up session on disconnect."""
            if self._session_id:
                try:
                    bridge = get_bridge()
                    summary = bridge.end_session(self._session_id)
                    if summary:
                        logger.info("Session summary:\n%s", summary)
                except Exception:
                    pass

            _client_sessions.pop(getattr(self, '_ws_id', None), None)

            if _rate_limiter:
                _rate_limiter.remove_client(self._client_id)

            logger.info("Client disconnected: %s", self._client_id)


# =============================================================================
# PUBLIC API
# =============================================================================

def start_hwebserver(port: int = 9999, enable_rate_limiter: bool = True):
    """
    Start the Synapse hwebserver.

    Call this once from Houdini's Python Shell or a startup script.
    In graphical mode, runs non-blocking alongside the UI.

    Args:
        port: Port to listen on (default: 9999)
        enable_rate_limiter: Enable request rate limiting
    """
    if not HWEBSERVER_AVAILABLE:
        raise ImportError("hwebserver not available — must run inside Houdini")

    global _rate_limiter, _backpressure, _running, _handler, _port

    if _running:
        logger.info("Already running")
        return

    # Initialize handler
    _handler = SynapseHandler()

    # Optional rate limiter (no circuit breaker — hwebserver IS Houdini)
    if enable_rate_limiter:
        _rate_limiter = RateLimiter()
        _backpressure = BackpressureController()

    # Start native server — non-blocking in GUI, blocking in hython
    hwebserver.run(
        port=port,
        debug=False,
        in_background=True,
        max_num_threads=4,
    )

    _running = True
    _port = port
    logger.info("Running on ws://localhost:%s/synapse", port)
    logger.info("Native C++ server -- no watchdog, no circuit breaker")


def stop_hwebserver():
    """Stop the Synapse hwebserver."""
    global _running, _handler, _rate_limiter, _backpressure

    if not _running:
        return

    try:
        hwebserver.requestShutdown()
    except Exception:
        pass

    _running = False
    _handler = None
    _rate_limiter = None
    _backpressure = None
    _client_sessions.clear()
    logger.info("Stopped")


def is_running() -> bool:
    """Check if hwebserver is running."""
    return _running


def get_health() -> Dict:
    """Get health status for the hwebserver backend."""
    return {
        "backend": "hwebserver",
        "running": _running,
        "port": _port,
        "clients": len(_client_sessions),
        "rate_limiter": _rate_limiter is not None,
    }
