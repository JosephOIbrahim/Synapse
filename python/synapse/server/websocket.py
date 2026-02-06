"""
Synapse WebSocket Server

WebSocket server for AI-Houdini communication.
Provides real-time bidirectional communication with resilience features.
"""

import asyncio
import threading
import json
import time
from typing import Dict, Any, Optional, Set, Callable

try:
    import websockets
    from websockets.server import serve
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    websockets = None

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
)
from ..core.queue import DeterministicCommandQueue, ResponseDeliveryQueue
from .handlers import SynapseHandler
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

        self.host = host
        self.port = port
        self._actual_port = port

        # Server state
        self._server = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        # Connected clients
        self._clients: Set = set()
        self._client_sessions: Dict[Any, str] = {}  # websocket -> session_id
        self._client_ids: Dict[Any, str] = {}  # websocket -> client_id

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
            print("[SynapseServer] Already running")
            return

        self._running = True

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

        print(f"[SynapseServer] Starting on {self.host}:{self.port}")

    def stop(self):
        """Stop the WebSocket server."""
        if not self._running:
            return

        self._running = False

        # Stop watchdog
        if self._watchdog:
            self._watchdog.stop()

        # Close all client connections
        if self._loop and self._clients:
            for client in list(self._clients):
                try:
                    asyncio.run_coroutine_threadsafe(
                        client.close(),
                        self._loop
                    )
                except:
                    pass

        # Stop the server
        if self._server:
            self._server.close()

        # Stop the event loop
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)

        print("[SynapseServer] Stopped")

    def _run_server(self):
        """Run the server event loop."""
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            # Try to bind to port with retries
            for attempt in range(MAX_PORT_RETRIES):
                try:
                    port_to_try = self.port if attempt == 0 else self.port + attempt
                    self._server = self._loop.run_until_complete(
                        serve(
                            self._handle_client,
                            self.host,
                            port_to_try
                        )
                    )
                    self._actual_port = port_to_try

                    if self._port_manager:
                        self._port_manager.mark_active(port_to_try)

                    print(f"[SynapseServer] Running on ws://{self.host}:{port_to_try}")
                    break

                except OSError as e:
                    if "Address already in use" in str(e) or e.errno == 10048:  # Windows WSAEADDRINUSE
                        print(f"[SynapseServer] Port {port_to_try} in use, trying next...")
                        if self._port_manager:
                            self._port_manager.mark_unhealthy(port_to_try, str(e))
                        time.sleep(PORT_RETRY_DELAY)
                    else:
                        raise

            if self._server is None:
                raise RuntimeError(f"Failed to bind to any port after {MAX_PORT_RETRIES} attempts")

            # Run until stopped
            self._loop.run_forever()

        except Exception as e:
            print(f"[SynapseServer] Error: {e}")
        finally:
            if self._loop:
                self._loop.close()

    async def _handle_client(self, websocket):
        """Handle a client connection."""
        # Generate client ID
        client_id = f"client_{int(time.time())}_{id(websocket)}"
        self._clients.add(websocket)
        self._client_ids[websocket] = client_id

        # Start session
        bridge = get_bridge()
        session_id = bridge.start_session(client_id)
        self._client_sessions[websocket] = session_id
        self._handler.set_session_id(session_id)

        print(f"[SynapseServer] Client connected: {client_id}")

        # Notify callback
        if self._on_client_connect:
            try:
                self._on_client_connect(client_id)
            except:
                pass

        # Send initial context
        try:
            context = bridge.get_connection_context()
            await websocket.send(json.dumps({
                "type": "connection_context",
                "protocol_version": PROTOCOL_VERSION,
                "context": context
            }))
        except Exception as e:
            print(f"[SynapseServer] Failed to send context: {e}")

        try:
            async for message in websocket:
                await self._handle_message(websocket, message, client_id)
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"[SynapseServer] Error handling client: {e}")
        finally:
            # End session
            session_id = self._client_sessions.pop(websocket, None)
            if session_id:
                summary = bridge.end_session(session_id)
                if summary:
                    print(f"[SynapseServer] Session summary:\n{summary}")

            # Cleanup
            self._clients.discard(websocket)
            self._client_ids.pop(websocket, None)

            if self._rate_limiter:
                self._rate_limiter.remove_client(client_id)

            print(f"[SynapseServer] Client disconnected: {client_id}")

            # Notify callback
            if self._on_client_disconnect:
                try:
                    self._on_client_disconnect(client_id)
                except:
                    pass

    async def _handle_message(self, websocket, message: str, client_id: str):
        """Handle an incoming message."""
        try:
            # Parse command
            command = SynapseCommand.from_json(message)

            # Handle heartbeat without rate limiting
            if command.type == "heartbeat":
                await websocket.send(SynapseResponse(
                    id=command.id,
                    success=True,
                    data={"pong": True},
                    sequence=command.sequence
                ).to_json())
                return

            # Check resilience (if enabled)
            if self._enable_resilience:
                # Rate limiting
                allowed, info = self._rate_limiter.acquire(client_id)
                if not allowed:
                    await websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Rate limited: {info.get('reason')}",
                        data={"retry_after": info.get("retry_after", 1.0)},
                        sequence=command.sequence
                    ).to_json())
                    return

                # Circuit breaker
                can_exec, cb_info = self._circuit_breaker.can_execute()
                if not can_exec:
                    await websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Circuit breaker open: {cb_info.get('reason')}",
                        data={"retry_after": cb_info.get("retry_after", 30.0)},
                        sequence=command.sequence
                    ).to_json())
                    return

                # Backpressure
                if not self._backpressure.should_accept():
                    await websocket.send(SynapseResponse(
                        id=command.id,
                        success=False,
                        error=f"Backpressure: {self._backpressure.level.value}",
                        sequence=command.sequence
                    ).to_json())
                    return

            # Process command
            response = self._handler.handle(command)

            # Record success/failure for circuit breaker
            if self._circuit_breaker:
                if response.success:
                    self._circuit_breaker.record_success()
                elif response.error and is_service_error(Exception(response.error)):
                    self._circuit_breaker.record_failure()

            # Send response
            await websocket.send(response.to_json())

        except json.JSONDecodeError as e:
            await websocket.send(SynapseResponse(
                id="unknown",
                success=False,
                error=f"Invalid JSON: {e}"
            ).to_json())
        except Exception as e:
            await websocket.send(SynapseResponse(
                id="unknown",
                success=False,
                error=str(e)
            ).to_json())

    def _on_freeze(self, duration: float):
        """Called when main thread freeze is detected."""
        print(f"[SynapseServer] Main thread frozen for {duration:.1f}s")
        if self._circuit_breaker:
            self._circuit_breaker.force_open()

    def _on_recover(self):
        """Called when main thread recovers from freeze."""
        print("[SynapseServer] Main thread recovered")

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
                avg_latency=0.0,  # TODO: track actual latency
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
