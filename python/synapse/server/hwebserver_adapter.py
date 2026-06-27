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
import os
import threading
from typing import Dict, Optional

# Fast JSON — orjson if available, stdlib fallback
try:
    import orjson
    def _dumps(obj):
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode()
except ImportError:
    def _dumps(obj):
        return json.dumps(obj, sort_keys=True)

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
from .auth import get_auth_key, authenticate, validate_origin, AUTH_COMMAND_TYPE, AUTH_REQUIRED_TYPE
from .handlers import SynapseHandler
from .resilience import RateLimiter, BackpressureController
from ..session.tracker import get_bridge
from .bridge_endpoint import publish_endpoint, clear_endpoint


# =============================================================================
# HWEBSERVER WEBSOCKET HANDLER
# =============================================================================

# Module-level state (hwebserver decorators require module-level class defs)
_handler: Optional[SynapseHandler] = None
_rate_limiter: Optional[RateLimiter] = None
_backpressure: Optional[BackpressureController] = None
_metrics_aggregator = None  # live MetricsAggregator (Sprint E) — None until start
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
            # Origin validation (DNS rebinding protection)
            origin = ""
            try:
                origin = req.headers().get("Origin", "")
            except (AttributeError, TypeError):
                pass
            deploy_mode = os.environ.get("SYNAPSE_DEPLOY_MODE", "local")
            if not validate_origin(origin, deploy_mode=deploy_mode):
                logger.warning("Rejected WebSocket from origin: %s", origin)
                await self.close(4003, "Origin not allowed")
                return

            self._client_id = _next_client_id()
            self._session_id = None
            self._ws_id = _client_counter
            self._authenticated = False
            await self.accept()

            # Send auth_required if key is configured
            auth_key = get_auth_key()
            if auth_key is not None:
                await self.send(json.dumps({
                    "type": AUTH_REQUIRED_TYPE,
                    "message": "Authentication required",
                    "protocol_version": PROTOCOL_VERSION,
                }, sort_keys=True), is_binary=False)
                self._auth_key = auth_key
            else:
                self._authenticated = True
                self._auth_key = None

            logger.info("Client connected: %s", self._client_id)

        async def receive(self, text_data=None, bytes_data=None):
            """Handle incoming SynapseCommand message."""
            if text_data is None:
                return

            # Auth handshake (first message when key is configured)
            if not self._authenticated and self._auth_key:
                try:
                    msg = json.loads(text_data)
                    token = msg.get("payload", {}).get("key", "")
                    if msg.get("type") == AUTH_COMMAND_TYPE and authenticate(token, self._auth_key):
                        self._authenticated = True
                        await self.send(json.dumps({
                            "type": "auth_success",
                            "success": True,
                            "protocol_version": PROTOCOL_VERSION,
                        }, sort_keys=True), is_binary=False)
                        logger.info("Client authenticated: %s", self._client_id)
                        return
                    else:
                        await self.send(json.dumps({
                            "type": "auth_failed",
                            "success": False,
                            "error": "Invalid API key",
                            "protocol_version": PROTOCOL_VERSION,
                        }, sort_keys=True), is_binary=False)
                        logger.warning("Auth failed for client %s", self._client_id)
                        await self.close()
                        return
                except json.JSONDecodeError:
                    await self.close()
                    return

            # Heartbeat fast path (raw-substring — skip SynapseCommand.from_json).
            # Heartbeats are the highest-frequency message (3045/sample); short-
            # circuit on the literal substring BEFORE the full protocol parse.
            # Mirrors websocket.py:_handle_message. Behavior identical to the
            # post-parse heartbeat branch below — just an earlier exit.
            if '"heartbeat"' in text_data[:80]:
                try:
                    raw = json.loads(text_data)
                    if raw.get("type") == "heartbeat":
                        await self.send(_dumps({
                            "id": raw.get("id", ""),
                            "success": True,
                            "data": {"pong": True},
                            "sequence": raw.get("sequence", 0),
                            "protocol_version": PROTOCOL_VERSION,
                        }), is_binary=False)
                        return
                except (json.JSONDecodeError, KeyError):
                    pass  # Fall through to normal parsing

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

            _client_sessions.pop(getattr(self, '_ws_id', None), None)  # type: ignore[arg-type]

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
    # M3-C: durable log + telemetry flush. Idempotent; never raises.
    from ..core.logfile import ensure_file_logging
    from .telemetry_dump import start_periodic_flush
    ensure_file_logging()
    start_periodic_flush()

    if not HWEBSERVER_AVAILABLE:
        raise ImportError("hwebserver not available — must run inside Houdini")

    global _rate_limiter, _backpressure, _running, _handler, _port
    global _metrics_aggregator

    if _running:
        logger.info("Already running")
        return

    # Initialize handler
    _handler = SynapseHandler()

    # Optional rate limiter (no circuit breaker — hwebserver IS Houdini)
    if enable_rate_limiter:
        _rate_limiter = RateLimiter()
        _backpressure = BackpressureController()

    # Live metrics aggregator (Sprint E). The legacy websocket.py builds + feeds
    # one; this dominant hwebserver path never did, so telemetry always stamped
    # live_metrics_latest_absent. Mirror websocket.py: construct, wire it to the
    # handler via the same set_metrics_aggregator hook, and START its collection
    # loop so .latest() returns real snapshots (it is FED, not empty). Best-effort
    # — a metrics failure must never block the transport from starting.
    try:
        from .live_metrics import MetricsAggregator
        _metrics_aggregator = MetricsAggregator()
        _handler.set_metrics_aggregator(_metrics_aggregator)
        _metrics_aggregator.start()
    except Exception:
        logger.debug("Metrics aggregator init failed (best-effort)", exc_info=True)
        _metrics_aggregator = None

    # Start native server — non-blocking in GUI, blocking in hython.
    # FINDING 3: the metrics daemon is already .start()ed above, but _running is
    # only set True AFTER run() returns. If run() raises, _running stays False,
    # so a retry slips past the `if _running: return` guard and constructs a
    # SECOND aggregator — orphaning the first. Tear the started aggregator down
    # before re-raising so the failure path leaves no leaked daemon thread.
    try:
        hwebserver.run(
            port=port,
            debug=False,
            in_background=True,
            max_num_threads=4,
        )
    except Exception:
        if _metrics_aggregator is not None:
            try:
                _metrics_aggregator.stop()
            except Exception:
                logger.debug(
                    "Metrics aggregator cleanup failed after hwebserver startup failure",
                    exc_info=True,
                )
            _metrics_aggregator = None
        # Clear the rest of the half-started state too, else stop_hwebserver()
        # (which returns early while _running is False) can never reclaim it and
        # a retry inherits stale handler/limiter/backpressure objects.
        _handler = None
        _rate_limiter = None
        _backpressure = None
        raise

    _running = True
    _port = port

    # Publish the real bound port to the discoverable sidecar so clients can
    # find us. hwebserver binds the requested port (no failover), so _port is
    # the real port once run() returns without raising. Best-effort.
    try:
        publish_endpoint(
            "localhost", _port, pid=os.getpid(), protocol=PROTOCOL_VERSION,
        )
    except Exception:
        pass

    logger.info("Running on ws://localhost:%s/synapse", port)
    logger.info("Native C++ server -- no watchdog, no circuit breaker")


def stop_hwebserver():
    """Stop the Synapse hwebserver."""
    global _running, _handler, _rate_limiter, _backpressure, _metrics_aggregator

    if not _running:
        return

    # Stop the live metrics collector (best-effort — never block shutdown).
    if _metrics_aggregator is not None:
        try:
            _metrics_aggregator.stop()
        except Exception:
            pass
        _metrics_aggregator = None

    try:
        hwebserver.requestShutdown()
    except Exception:
        pass

    # Remove our discoverable endpoint sidecar (only if it's ours).
    try:
        clear_endpoint(os.getpid())
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
