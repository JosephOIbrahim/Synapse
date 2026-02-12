"""
Synapse WebSocket Server

WebSocket server for AI-Houdini communication.
Provides real-time bidirectional communication with resilience features.
"""

import logging
import os
import signal
import threading
import json
import time
from typing import Dict, Any, Optional, Set, Callable

try:
    import websockets
    from websockets.sync.server import serve as sync_serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None
    sync_serve = None

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.protocol import (
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
    HEARTBEAT_INTERVAL,
    COMMAND_TIMEOUT,
    MAX_PORT_RETRIES,
    PORT_RETRY_DELAY,
    _to_json_str,
)
from ..core.queue import DeterministicCommandQueue, ResponseDeliveryQueue
from .auth import get_auth_key, authenticate, AUTH_COMMAND_TYPE, AUTH_REQUIRED_TYPE
from .handlers import SynapseHandler, _READ_ONLY_COMMANDS
from .resilience import (
    RateLimiter,
    CircuitBreaker,
    CircuitBreakerConfig,
    PortManager,
    Watchdog,
    BackpressureController,
    HealthMonitor,
    is_service_error,
)
from ..session.tracker import get_bridge

logger = logging.getLogger("synapse.server")


class SynapseServer:
    """
    WebSocket server for AI-Houdini communication.

    Features:
    - Real-time bidirectional communication
    - Rate limiting and backpressure
    - Circuit breaker for crash prevention
    - Automatic port failover
    - Session tracking with memory integration
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9999,
        enable_resilience: bool = True
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets package required. Install with: pip install websockets")

        # SYNAPSE_RESILIENCE=0 disables resilience (for CI / testing)
        import os
        if os.environ.get("SYNAPSE_RESILIENCE", "").strip() == "0":
            enable_resilience = False

        self.host = host
        self.port = port
        self._actual_port = port

        # Server state
        self._server = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # Connected clients (guarded by _clients_lock — mutated from thread pool)
        self._clients: Set = set()
        self._client_sessions: Dict[Any, str] = {}  # websocket -> session_id
        self._client_ids: Dict[Any, str] = {}  # websocket -> client_id
        self._clients_lock = threading.Lock()
        self._client_counter = 0  # monotonic counter for deterministic IDs

        # Command processing
        self._command_queue = DeterministicCommandQueue()
        self._response_queue = ResponseDeliveryQueue()
        self._handler = SynapseHandler()

        # Resilience layer
        self._enable_resilience = enable_resilience
        if enable_resilience:
            self._rate_limiter = RateLimiter()
            self._circuit_breaker = CircuitBreaker(
                name="synapse",
                config=CircuitBreakerConfig(failure_threshold=5, timeout_seconds=30.0)
            )
            self._port_manager = PortManager(primary_port=port)
            self._watchdog = Watchdog(
                on_freeze=self._on_freeze,
                on_recover=self._on_recover
            )
            self._backpressure = BackpressureController()
            self._health_monitor = HealthMonitor(
                rate_limiter=self._rate_limiter,
                circuit_breaker=self._circuit_breaker,
                port_manager=self._port_manager,
                watchdog=self._watchdog,
                backpressure=self._backpressure
            )
        else:
            self._rate_limiter = None
            self._circuit_breaker = None
            self._port_manager = None
            self._watchdog = None
            self._backpressure = None
            self._health_monitor = None

        # Latency tracking (exponential moving average)
        self._avg_latency = 0.0
        self._latency_alpha = 0.2  # EMA smoothing factor

        # Callbacks
        self._on_client_connect: Optional[Callable] = None
        self._on_client_disconnect: Optional[Callable] = None

    @property
    def actual_port(self) -> int:
        """Get the actual port the server is running on."""
        return self._actual_port

    @property
    def client_count(self) -> int:
        """Get number of connected clients."""
        return len(self._clients)

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    def start(self):
        """Start the WebSocket server in a background thread."""
        if self._running:
            logger.info("Already running")
            return

        self._running = True

        # Register signal handlers for graceful shutdown (standalone only)
        if not HOU_AVAILABLE:
            signal.signal(signal.SIGTERM, lambda s, f: self.stop())
            signal.signal(signal.SIGINT, lambda s, f: self.stop())

        # Start watchdog
        if self._watchdog:
            self._watchdog.start()

        # Start server in background thread
        self._thread = threading.Thread(
            target=self._run_server,
            daemon=True,
            name="Synapse-Server"
        )
        self._thread.start()

        logger.info("Starting on %s:%s", self.host, self.port)

    def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return

        self._running = False

        # Stop watchdog
        if self._watchdog:
            self._watchdog.stop()

        # Stop the sync server (this closes the listening socket)
        if self._server:
            try:
                self._server.shutdown()
            except Exception as e:
                logger.error("Shutdown error: %s", e)

        logger.info("Stopped")

    def _run_server(self):
        """Run the sync WebSocket server (no asyncio — avoids Houdini's haio.py)."""
        try:
            # Try to bind to port with retries
            for attempt in range(MAX_PORT_RETRIES):
                try:
                    port_to_try = self.port if attempt == 0 else self.port + attempt
                    self._server = sync_serve(
                        self._handle_client,
                        self.host,
                        port_to_try,
                        ping_interval=None,
                        ping_timeout=None,
                    )
                    self._actual_port = port_to_try

                    if self._port_manager:
                        self._port_manager.mark_active(port_to_try)

                    logger.info("Running on ws://%s:%s", self.host, port_to_try)
                    break

                except OSError as e:
                    if "Address already in use" in str(e) or e.errno == 10048:
                        logger.warning("Port %s in use, trying next...", port_to_try)
                        if self._port_manager:
                            self._port_manager.mark_unhealthy(port_to_try, str(e))
                        time.sleep(PORT_RETRY_DELAY)
                    else:
                        raise

            if self._server is None:
                raise RuntimeError(f"Failed to bind to any port after {MAX_PORT_RETRIES} attempts")

            # serve_forever blocks until shutdown() is called
            self._server.serve_forever()

        except Exception as e:
            import traceback
            err_detail = traceback.format_exc()
            logger.error("Server error: %s", e)
            logger.debug("%s", err_detail)
        finally:
            self._running = False

    def _handle_client(self, websocket):
        """Handle a client connection (sync — runs in server thread pool)."""
        # Deterministic client ID (monotonic counter, not time/memory address)
        with self._clients_lock:
            self._client_counter += 1
            client_id = f"client_{PROTOCOL_VERSION}_{self._client_counter:05d}"
            self._clients.add(websocket)
            self._client_ids[websocket] = client_id

        session_id = None

        try:
            logger.info("Client connected: %s", client_id)

            # Notify callback
            if self._on_client_connect:
                try:
                    self._on_client_connect(client_id)
                except Exception as e:
                    logger.error("Connect callback error: %s", e)

            # Authentication handshake (if key is configured)
            auth_key = get_auth_key()
            if auth_key is not None:
                # Tell client auth is required
                websocket.send(_to_json_str({
                    "type": AUTH_REQUIRED_TYPE,
                    "message": "Authentication required",
                    "protocol_version": PROTOCOL_VERSION,
                }))

                # Wait for auth message
                try:
                    auth_msg = json.loads(next(iter([websocket.recv()])))
                    token = auth_msg.get("payload", {}).get("key", "")
                    if auth_msg.get("type") != AUTH_COMMAND_TYPE or not authenticate(token, auth_key):
                        websocket.send(_to_json_str({
                            "type": "auth_failed",
                            "success": False,
                            "error": "Invalid API key",
                            "protocol_version": PROTOCOL_VERSION,
                        }))
                        logger.warning("Auth failed for client %s", client_id)
                        return
                except (json.JSONDecodeError, StopIteration):
                    websocket.send(_to_json_str({
                        "type": "auth_failed",
                        "success": False,
                        "error": "Expected authenticate command",
                        "protocol_version": PROTOCOL_VERSION,
                    }))
                    return

                websocket.send(_to_json_str({
                    "type": "auth_success",
                    "success": True,
                    "protocol_version": PROTOCOL_VERSION,
                }))
                logger.info("Client authenticated: %s", client_id)

            for message in websocket:
                # Lazy session: create on first real command, not on connect
                if session_id is None:
                    with self._clients_lock:
                        # Double-check under lock to prevent race
                        if websocket not in self._client_sessions:
                            bridge = get_bridge()
                            session_id = bridge.start_session(client_id)
                            self._client_sessions[websocket] = session_id
                        else:
                            session_id = self._client_sessions[websocket]
                    self._handler.set_session_id(session_id)

                self._handle_message(websocket, message, client_id)

        except websockets.exceptions.ConnectionClosedOK:
            pass
        except websockets.exceptions.ConnectionClosedError:
            pass
        except Exception as e:
            logger.error("Error handling client: %s", e)
        finally:
            # Cleanup under lock (guaranteed even if bridge.start_session fails)
            with self._clients_lock:
                session_id = self._client_sessions.pop(websocket, None)
                self._clients.discard(websocket)
                self._client_ids.pop(websocket, None)

            # End session
            if session_id:
                try:
                    bridge = get_bridge()
                    summary = bridge.end_session(session_id)
                    if summary:
                        logger.info("Session summary:\n%s", summary)
                except Exception as e:
                    logger.error("End session error: %s", e)

            # Living Memory: suspend agent tasks and write session end
            if session_id:
                try:
                    from ..memory.scene_memory import write_session_end, ensure_scene_structure
                    from ..memory.agent_state import suspend_all_tasks, log_session
                    if HOU_AVAILABLE:
                        hip_path = hou.hipFile.path()
                        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
                        paths = ensure_scene_structure(hip_path, job_path)

                        # Suspend any pending/executing tasks
                        agent_usd = paths.get("agent_usd", "")
                        if agent_usd and os.path.exists(agent_usd):
                            suspend_all_tasks(agent_usd)
                            log_session(agent_usd, {
                                "end_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                                "summary_text": f"Session ended (client: {client_id})",
                            })

                        # Write session end to memory.md
                        write_session_end(paths["scene_dir"], {
                            "stopped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        })
                except Exception as e:
                    logger.warning("Living Memory disconnect hook error: %s", e)

            if self._rate_limiter:
                self._rate_limiter.remove_client(client_id)

            logger.info("Client disconnected: %s", client_id)

            # Notify callback
            if self._on_client_disconnect:
                try:
                    self._on_client_disconnect(client_id)
                except Exception as e:
                    logger.error("Disconnect callback error: %s", e)

    def _handle_message(self, websocket, message: str, client_id: str):
        """Handle an incoming message (sync)."""
        try:
            # Parse command
            command = SynapseCommand.from_json(message)

            # Handle heartbeat and ping without resilience checks
            if command.type == "heartbeat":
                websocket.send(SynapseResponse(
                    id=command.id,
                    success=True,
                    data={"pong": True},
                    sequence=command.sequence
                ).to_json())
                return

            if command.type in ("ping", "get_health"):
                response = self._handler.handle(command)
                websocket.send(response.to_json())
                return

            # Read-only commands bypass resilience — they're cheap reads
            # that can't cause cascading failures
            if self._enable_resilience and command.type in _READ_ONLY_COMMANDS:
                response = self._handler.handle(command)
                if self._circuit_breaker and response.success:
                    self._circuit_breaker.record_success()
                websocket.send(response.to_json())
                return

            # Check resilience (if enabled)
            if self._enable_resilience:
                # Rate limiting
                allowed, info = self._rate_limiter.acquire(client_id)
                if not allowed:
                    websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Synapse is handling a lot of requests right now \u2014 try again in a moment ({info.get('reason')})",
                        data={"retry_after": info.get("retry_after", 1.0)},
                        sequence=command.sequence
                    ).to_json())
                    return

                # Circuit breaker
                can_exec, cb_info = self._circuit_breaker.can_execute()
                if not can_exec:
                    websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Synapse paused commands temporarily to recover from errors \u2014 it'll resume shortly ({cb_info.get('reason')})",
                        data={"retry_after": cb_info.get("retry_after", 30.0)},
                        sequence=command.sequence
                    ).to_json())
                    return

                # Backpressure
                if not self._backpressure.should_accept():
                    websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Synapse is under heavy load right now (level: {self._backpressure.level.value}) \u2014 try again shortly",
                        data={"retry_after": 2.0},
                        sequence=command.sequence
                    ).to_json())
                    return

            # Process command with latency tracking
            t0 = time.monotonic()
            response = self._handler.handle(command)
            elapsed = time.monotonic() - t0
            self._avg_latency = (
                self._latency_alpha * elapsed
                + (1 - self._latency_alpha) * self._avg_latency
            )

            # Record success for circuit breaker — failures are only
            # recorded in the except block for actual service errors
            # (not user errors like "Node not found")
            if self._circuit_breaker and response.success:
                self._circuit_breaker.record_success()

            # Send response
            websocket.send(response.to_json())

        except json.JSONDecodeError as e:
            websocket.send(SynapseResponse(
                id="unknown",
                success=False,
                error=f"Couldn't parse the incoming message as JSON \u2014 check the message format ({e})"
            ).to_json())
        except Exception as e:
            # Notify circuit breaker on handler exceptions (service errors)
            if self._circuit_breaker and is_service_error(e):
                self._circuit_breaker.record_failure()
            websocket.send(SynapseResponse(
                id="unknown",
                success=False,
                error=str(e)
            ).to_json())

    def _on_freeze(self, duration: float):
        """Called when main thread freeze is detected (informational only)."""
        logger.warning("Main thread frozen for %.1fs (logged, not blocking)", duration)

    def _on_recover(self):
        """Called when main thread recovers from freeze."""
        logger.info("Main thread recovered")
        # Reset the circuit breaker so commands flow again
        if self._circuit_breaker:
            self._circuit_breaker.reset()

    def heartbeat(self):
        """
        Call from main thread to signal responsiveness.
        Should be called by QTimer in the panel.
        """
        if self._watchdog:
            self._watchdog.heartbeat()

        # Update backpressure
        if self._backpressure and self._circuit_breaker:
            self._backpressure.evaluate(
                queue_size=self._command_queue.size(),
                avg_latency=self._avg_latency,
                circuit_state=self._circuit_breaker.state.value
            )

    def get_health(self) -> Dict:
        """Get system health status."""
        if self._health_monitor:
            return self._health_monitor.to_dict()
        return {
            "healthy": self._running,
            "level": "healthy" if self._running else "unhealthy",
            "message": "Running" if self._running else "Stopped"
        }

    def on_client_connect(self, callback: Callable):
        """Register callback for client connections."""
        self._on_client_connect = callback

    def on_client_disconnect(self, callback: Callable):
        """Register callback for client disconnections."""
        self._on_client_disconnect = callback


# Backwards compatibility
NexusServer = SynapseServer
