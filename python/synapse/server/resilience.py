"""
Synapse Resilience Layer

Production-grade stability for the AI-Houdini bridge.
Prevents crashes, manages load, enables recovery.

Components:
- RateLimiter: Token bucket algorithm, per-client limits
- CircuitBreaker: Trip after failures, prevent cascade
- PortManager: Automatic failover to backup ports
- BackpressureController: Signal clients to slow down
- Watchdog: Monitor main thread, detect freezes
- HealthMonitor: Aggregate system health
"""

import time
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Callable, Any, Tuple
from enum import Enum
from collections import deque

# NOTE: round_float (Decimal-based) is intentionally NOT used here.
# He2025 determinism applies to user-facing outputs, not internal timing.
# Using Decimal for token-bucket math added ~2x overhead per command
# with zero determinism benefit. Plain round() is sufficient.


# =============================================================================
# RATE LIMITER - Token Bucket Algorithm
# =============================================================================

class RateLimiter:
    """
    Token bucket rate limiter with per-client tracking.

    Allows burst traffic up to bucket size, then enforces steady rate.
    Clients that exceed limits get backpressure signals.
    """

    def __init__(
        self,
        tokens_per_second: float = 50.0,
        bucket_size: int = 100,
        per_client_bucket: int = 20
    ):
        self.tokens_per_second = tokens_per_second
        self.bucket_size = bucket_size
        self.per_client_bucket = per_client_bucket

        # Global bucket
        self._tokens = float(bucket_size)
        self._last_refill = time.time()

        # Per-client buckets: client_id -> (tokens, last_refill)
        self._client_buckets: Dict[str, Tuple[float, float]] = {}

        self._lock = threading.Lock()

        # Stats
        self._total_requests = 0
        self._rejected_requests = 0

    def _refill_global(self):
        """Refill global token bucket based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(
            self.bucket_size,
            self._tokens + elapsed * self.tokens_per_second
        )
        self._last_refill = now

    def _refill_client(self, client_id: str) -> float:
        """Refill client bucket, return current tokens."""
        now = time.time()

        if client_id not in self._client_buckets:
            self._client_buckets[client_id] = (float(self.per_client_bucket), now)
            return float(self.per_client_bucket)

        tokens, last_refill = self._client_buckets[client_id]
        elapsed = now - last_refill
        new_tokens = min(
            self.per_client_bucket,
            tokens + elapsed * (self.tokens_per_second / 5)  # Slower per-client refill
        )
        self._client_buckets[client_id] = (new_tokens, now)
        return new_tokens

    def acquire(self, client_id: str = "global", tokens: int = 1) -> Tuple[bool, Dict]:
        """
        Try to acquire tokens for a request.

        Returns:
            (allowed: bool, info: dict with retry_after, remaining, etc.)
        """
        with self._lock:
            self._total_requests += 1
            self._refill_global()
            client_tokens = self._refill_client(client_id)

            # Check global limit
            if self._tokens < tokens:
                self._rejected_requests += 1
                wait_time = round((tokens - self._tokens) / self.tokens_per_second, 3)
                return False, {
                    "reason": "global_rate_limit",
                    "retry_after": wait_time,
                    "remaining_global": int(self._tokens),
                    "remaining_client": int(client_tokens)
                }

            # Check per-client limit
            if client_tokens < tokens:
                self._rejected_requests += 1
                wait_time = round((tokens - client_tokens) / (self.tokens_per_second / 5), 3)
                return False, {
                    "reason": "client_rate_limit",
                    "retry_after": wait_time,
                    "remaining_global": int(self._tokens),
                    "remaining_client": int(client_tokens)
                }

            # Consume tokens
            self._tokens -= tokens
            self._client_buckets[client_id] = (
                client_tokens - tokens,
                self._client_buckets[client_id][1]
            )

            return True, {
                "remaining_global": int(self._tokens),
                "remaining_client": int(client_tokens - tokens)
            }

    def remove_client(self, client_id: str):
        """Clean up when client disconnects."""
        with self._lock:
            self._client_buckets.pop(client_id, None)

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "rejected_requests": self._rejected_requests,
                "rejection_rate": (
                    self._rejected_requests / self._total_requests
                    if self._total_requests > 0 else 0
                ),
                "current_tokens": int(self._tokens),
                "active_clients": len(self._client_buckets)
            }


# =============================================================================
# CIRCUIT BREAKER - Prevent Cascade Failures
# =============================================================================

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Rejecting all requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    timeout_seconds: float = 30.0       # How long to stay open
    half_open_max_calls: int = 3        # Max calls in half-open state
    error_types: tuple = (Exception,)   # What counts as failure


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    States:
    - CLOSED: Normal operation, counting failures
    - OPEN: Rejecting all calls, waiting for timeout
    - HALF_OPEN: Testing if system recovered
    """

    def __init__(self, name: str = "synapse", config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0

        self._lock = threading.Lock()

        # Callbacks
        self._on_state_change: Optional[Callable] = None

        # History for debugging
        self._state_history: deque = deque(maxlen=50)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._check_state_transition()
            return self._state

    def _check_state_transition(self):
        """Check if we should transition states."""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.config.timeout_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state

        # Reset counters on transition
        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._success_count = 0

        # Record history
        self._state_history.append({
            "from": old_state.value,
            "to": new_state.value,
            "time": time.time(),
            "failures": self._failure_count
        })

        # Notify callback
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception:
                pass

        print(f"[CircuitBreaker:{self.name}] {old_state.value} -> {new_state.value}")

    def can_execute(self) -> Tuple[bool, Dict]:
        """
        Check if a call is allowed.

        Returns:
            (allowed: bool, info: dict with state, retry_after, etc.)
        """
        with self._lock:
            self._check_state_transition()

            if self._state == CircuitState.CLOSED:
                return True, {"state": "closed", "failures": self._failure_count}

            elif self._state == CircuitState.OPEN:
                if self._last_failure_time:
                    remaining = self.config.timeout_seconds - (time.time() - self._last_failure_time)
                    return False, {
                        "state": "open",
                        "retry_after": max(0, remaining),
                        "reason": "circuit_open"
                    }
                return False, {"state": "open", "reason": "circuit_open"}

            else:  # HALF_OPEN
                if self._half_open_calls >= self.config.half_open_max_calls:
                    # Reset to OPEN to retry recovery cycle
                    self._last_failure_time = time.time()
                    self._transition_to(CircuitState.OPEN)
                    return False, {
                        "state": "open",
                        "retry_after": self.config.timeout_seconds,
                        "reason": "half_open_exhausted_retrying"
                    }
                self._half_open_calls += 1
                return True, {"state": "half_open", "test_call": self._half_open_calls}

    def record_success(self):
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                # Decay failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    def record_failure(self, error: Exception = None):
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)

    def force_open(self):
        """Manually trip the circuit."""
        with self._lock:
            self._last_failure_time = time.time()
            self._transition_to(CircuitState.OPEN)

    def force_close(self):
        """Manually close the circuit."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)

    def on_state_change(self, callback: Callable):
        """Register callback for state changes."""
        self._on_state_change = callback

    def get_stats(self) -> Dict:
        with self._lock:
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "history": list(self._state_history)[-10:]
            }


# =============================================================================
# PORT MANAGER - Automatic Failover
# =============================================================================

@dataclass
class PortHealth:
    """Health status of a port."""
    port: int
    is_active: bool = False
    is_healthy: bool = True
    last_error: Optional[str] = None
    error_count: int = 0
    last_check: float = field(default_factory=time.time)
    connections: int = 0


class PortManager:
    """
    Manages multiple ports with automatic failover.

    If primary port fails or gets overwhelmed:
    1. Mark it unhealthy
    2. Start server on backup port
    3. Notify connected clients of new port
    4. Attempt recovery of primary
    """

    def __init__(
        self,
        primary_port: int = 9999,
        backup_ports: List[int] = None,
        health_check_interval: float = 5.0
    ):
        self.primary_port = primary_port
        self.backup_ports = backup_ports or [9998, 9997, 9996]
        self.health_check_interval = health_check_interval

        self._ports: Dict[int, PortHealth] = {}
        self._active_port: Optional[int] = None
        self._lock = threading.Lock()

        # Initialize port health
        all_ports = [primary_port] + self.backup_ports
        for port in all_ports:
            self._ports[port] = PortHealth(port=port)

        # Callbacks
        self._on_port_change: Optional[Callable] = None
        self._on_health_change: Optional[Callable] = None

    def get_active_port(self) -> int:
        """Get the currently active port."""
        with self._lock:
            if self._active_port and self._ports[self._active_port].is_healthy:
                return self._active_port
            return self._find_healthy_port()

    def _find_healthy_port(self) -> int:
        """Find a healthy port, preferring primary."""
        # Try primary first
        if self._ports[self.primary_port].is_healthy:
            return self.primary_port

        # Try backups in order
        for port in self.backup_ports:
            if self._ports[port].is_healthy:
                return port

        # All unhealthy - return primary anyway
        return self.primary_port

    def mark_active(self, port: int):
        """Mark a port as the active server port."""
        with self._lock:
            old_port = self._active_port
            self._active_port = port
            self._ports[port].is_active = True

            # Deactivate others
            for p, health in self._ports.items():
                if p != port:
                    health.is_active = False

            if old_port != port and self._on_port_change:
                try:
                    self._on_port_change(old_port, port)
                except Exception:
                    pass

    def mark_unhealthy(self, port: int, error: str = None):
        """Mark a port as unhealthy after error."""
        with self._lock:
            health = self._ports.get(port)
            if health:
                health.is_healthy = False
                health.last_error = error
                health.error_count += 1
                health.last_check = time.time()

                print(f"[PortManager] Port {port} marked unhealthy: {error}")

                if self._on_health_change:
                    try:
                        self._on_health_change(port, False, error)
                    except Exception:
                        pass

    def mark_healthy(self, port: int):
        """Mark a port as recovered."""
        with self._lock:
            health = self._ports.get(port)
            if health:
                health.is_healthy = True
                health.last_error = None
                health.last_check = time.time()

                print(f"[PortManager] Port {port} recovered")

    def should_failover(self) -> Tuple[bool, Optional[int]]:
        """Check if we should failover to a new port."""
        with self._lock:
            if not self._active_port:
                return True, self._find_healthy_port()

            active_health = self._ports[self._active_port]
            if not active_health.is_healthy:
                new_port = self._find_healthy_port()
                if new_port != self._active_port:
                    return True, new_port

            return False, None

    def update_connections(self, port: int, count: int):
        """Update connection count for load monitoring."""
        with self._lock:
            if port in self._ports:
                self._ports[port].connections = count

    def on_port_change(self, callback: Callable):
        """Register callback for port changes."""
        self._on_port_change = callback

    def on_health_change(self, callback: Callable):
        """Register callback for health changes."""
        self._on_health_change = callback

    def get_status(self) -> Dict:
        with self._lock:
            return {
                "active_port": self._active_port,
                "primary_port": self.primary_port,
                "ports": {
                    port: {
                        "is_active": h.is_active,
                        "is_healthy": h.is_healthy,
                        "error_count": h.error_count,
                        "connections": h.connections,
                        "last_error": h.last_error
                    }
                    for port, h in self._ports.items()
                }
            }


# =============================================================================
# WATCHDOG - Monitor Main Thread Health
# =============================================================================

class Watchdog:
    """
    Monitors main thread responsiveness.

    If main thread stops responding (Houdini freeze):
    1. Detect via heartbeat timeout
    2. Stop accepting new commands
    3. Attempt recovery or notify user
    """

    def __init__(
        self,
        heartbeat_interval: float = 1.0,
        freeze_threshold: float = 5.0,
        on_freeze: Callable = None,
        on_recover: Callable = None
    ):
        self.heartbeat_interval = heartbeat_interval
        self.freeze_threshold = freeze_threshold
        self._on_freeze = on_freeze
        self._on_recover = on_recover

        self._last_heartbeat = time.time()
        self._is_frozen = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Stats
        self._freeze_count = 0
        self._total_heartbeats = 0
        self._max_latency = 0.0
        self._latencies: deque = deque(maxlen=100)

    def start(self):
        """Arm the watchdog — actual monitoring begins on first heartbeat().

        This avoids false freeze detection when no heartbeat source
        (e.g. panel QTimer) is running yet.
        """
        if self._running:
            return
        self._running = True
        # Don't launch thread yet — _ensure_started() does that on first heartbeat

    def stop(self):
        """Stop the watchdog."""
        was_running = self._running
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if was_running:
            print("[Watchdog] Stopped")

    def _ensure_started(self):
        """Launch monitor thread on first heartbeat (lazy start)."""
        if self._thread is not None:
            return
        self._last_heartbeat = time.time()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="Synapse-Watchdog"
        )
        self._thread.start()
        print("[Watchdog] Started monitoring main thread")

    def heartbeat(self):
        """
        Call this from main thread to signal it's alive.
        Should be called by QTimer in Synapse panel.
        """
        if not self._running:
            return

        # Lazy start: first heartbeat spins up the monitor thread
        self._ensure_started()

        now = time.time()
        with self._lock:
            latency = now - self._last_heartbeat
            self._latencies.append(latency)
            self._max_latency = max(self._max_latency, latency)
            self._last_heartbeat = now
            self._total_heartbeats += 1

            # Recover from freeze
            if self._is_frozen:
                self._is_frozen = False
                print(f"[Watchdog] Main thread recovered (was frozen for {latency:.1f}s)")
                if self._on_recover:
                    try:
                        self._on_recover()
                    except Exception:
                        pass

    def _monitor_loop(self):
        """Background thread that checks for freezes."""
        while self._running:
            time.sleep(self.heartbeat_interval)

            with self._lock:
                elapsed = time.time() - self._last_heartbeat

                if elapsed > self.freeze_threshold and not self._is_frozen:
                    self._is_frozen = True
                    self._freeze_count += 1

                    print(f"[Watchdog] FREEZE DETECTED! No heartbeat for {elapsed:.1f}s")

                    if self._on_freeze:
                        try:
                            self._on_freeze(elapsed)
                        except Exception:
                            pass

    @property
    def is_frozen(self) -> bool:
        with self._lock:
            return self._is_frozen

    def get_stats(self) -> Dict:
        with self._lock:
            latencies = list(self._latencies)
            avg_latency = sum(latencies) / len(latencies) if latencies else 0

            return {
                "is_frozen": self._is_frozen,
                "freeze_count": self._freeze_count,
                "total_heartbeats": self._total_heartbeats,
                "max_latency": self._max_latency,
                "avg_latency": avg_latency,
                "last_heartbeat_ago": time.time() - self._last_heartbeat
            }


# =============================================================================
# BACKPRESSURE CONTROLLER
# =============================================================================

class BackpressureLevel(Enum):
    NORMAL = "normal"           # Accept all
    ELEVATED = "elevated"       # Accept, but warn
    HIGH = "high"              # Throttle non-critical
    CRITICAL = "critical"      # Only accept critical


@dataclass
class BackpressureConfig:
    """Thresholds for backpressure levels."""
    queue_elevated: int = 25    # Queue size for ELEVATED
    queue_high: int = 50        # Queue size for HIGH
    queue_critical: int = 80    # Queue size for CRITICAL
    latency_elevated: float = 0.1   # Seconds
    latency_high: float = 0.5
    latency_critical: float = 2.0


class BackpressureController:
    """
    Controls system load via backpressure signals.

    Monitors queue size, latency, and circuit state to determine
    how much load the system can handle.
    """

    def __init__(self, config: BackpressureConfig = None):
        self.config = config or BackpressureConfig()
        self._level = BackpressureLevel.NORMAL
        self._lock = threading.Lock()

    def evaluate(
        self,
        queue_size: int,
        avg_latency: float,
        circuit_state: str = "closed"
    ) -> Tuple[BackpressureLevel, Dict]:
        """Evaluate current system state and return backpressure level."""
        with self._lock:
            # Circuit breaker override
            if circuit_state == "open":
                self._level = BackpressureLevel.CRITICAL
                return self._level, {"reason": "circuit_open"}

            # Check queue thresholds
            if queue_size >= self.config.queue_critical:
                self._level = BackpressureLevel.CRITICAL
                return self._level, {"reason": "queue_critical", "queue_size": queue_size}

            if queue_size >= self.config.queue_high:
                self._level = BackpressureLevel.HIGH
                return self._level, {"reason": "queue_high", "queue_size": queue_size}

            # Check latency thresholds
            if avg_latency >= self.config.latency_critical:
                self._level = BackpressureLevel.CRITICAL
                return self._level, {"reason": "latency_critical", "latency": avg_latency}

            if avg_latency >= self.config.latency_high:
                self._level = BackpressureLevel.HIGH
                return self._level, {"reason": "latency_high", "latency": avg_latency}

            if queue_size >= self.config.queue_elevated or avg_latency >= self.config.latency_elevated:
                self._level = BackpressureLevel.ELEVATED
                return self._level, {"queue_size": queue_size, "latency": avg_latency}

            self._level = BackpressureLevel.NORMAL
            return self._level, {}

    @property
    def level(self) -> BackpressureLevel:
        with self._lock:
            return self._level

    def should_accept(self, is_critical: bool = False) -> bool:
        """Check if a command should be accepted given current backpressure."""
        with self._lock:
            if self._level == BackpressureLevel.NORMAL:
                return True
            if self._level == BackpressureLevel.ELEVATED:
                return True
            if self._level == BackpressureLevel.HIGH:
                return is_critical  # Only critical commands
            return False  # CRITICAL level - reject all


# =============================================================================
# HEALTH MONITOR - Aggregate System Health
# =============================================================================

@dataclass
class HealthStatus:
    """Overall system health status."""
    healthy: bool
    level: str  # "healthy", "degraded", "unhealthy", "critical"
    components: Dict[str, Dict]
    timestamp: float = field(default_factory=time.time)
    message: str = ""


class HealthMonitor:
    """
    Aggregates health from all resilience components.
    Provides single endpoint for health checks.
    """

    def __init__(
        self,
        rate_limiter: RateLimiter = None,
        circuit_breaker: CircuitBreaker = None,
        port_manager: PortManager = None,
        watchdog: Watchdog = None,
        backpressure: BackpressureController = None
    ):
        self.rate_limiter = rate_limiter
        self.circuit_breaker = circuit_breaker
        self.port_manager = port_manager
        self.watchdog = watchdog
        self.backpressure = backpressure

    def check(self) -> HealthStatus:
        """Run full health check."""
        components = {}
        issues = []

        # Rate limiter
        if self.rate_limiter:
            stats = self.rate_limiter.get_stats()
            components["rate_limiter"] = stats
            if stats["rejection_rate"] > 0.5:
                issues.append("High rate limit rejection")

        # Circuit breaker
        if self.circuit_breaker:
            stats = self.circuit_breaker.get_stats()
            components["circuit_breaker"] = stats
            if stats["state"] == "open":
                issues.append("Circuit breaker OPEN")
            elif stats["state"] == "half_open":
                issues.append("Circuit breaker recovering")

        # Port manager
        if self.port_manager:
            status = self.port_manager.get_status()
            components["port_manager"] = status
            unhealthy_ports = sum(
                1 for p in status["ports"].values()
                if not p["is_healthy"]
            )
            if unhealthy_ports > 0:
                issues.append(f"{unhealthy_ports} ports unhealthy")

        # Watchdog
        if self.watchdog:
            stats = self.watchdog.get_stats()
            components["watchdog"] = stats
            if stats["is_frozen"]:
                issues.append("Main thread FROZEN")

        # Backpressure
        if self.backpressure:
            level = self.backpressure.level
            components["backpressure"] = {"level": level.value}
            if level in (BackpressureLevel.HIGH, BackpressureLevel.CRITICAL):
                issues.append(f"Backpressure {level.value}")

        # Determine overall health
        if not issues:
            level = "healthy"
            healthy = True
            message = "All systems operational"
        elif any("FROZEN" in i or "OPEN" in i for i in issues):
            level = "critical"
            healthy = False
            message = "; ".join(issues)
        elif len(issues) > 2:
            level = "unhealthy"
            healthy = False
            message = "; ".join(issues)
        else:
            level = "degraded"
            healthy = True
            message = "; ".join(issues)

        return HealthStatus(
            healthy=healthy,
            level=level,
            components=components,
            message=message
        )

    def to_dict(self) -> Dict:
        """Get health as dictionary (for JSON response)."""
        status = self.check()
        return {
            "healthy": status.healthy,
            "level": status.level,
            "message": status.message,
            "components": status.components,
            "timestamp": status.timestamp
        }


# =============================================================================
# ERROR CLASSIFICATION
# =============================================================================

# Errors that should NOT trip the circuit breaker (user/validation errors)
USER_ERROR_TYPES = (
    ValueError,
    KeyError,
    AttributeError,
    TypeError,
    IndexError,
    NameError,
)

# Errors that SHOULD trip the circuit breaker (service failures)
SERVICE_ERROR_TYPES = (
    TimeoutError,
    ConnectionError,
    OSError,
    RuntimeError,
)


def is_service_error(error: Exception) -> bool:
    """Check if an error should trip the circuit breaker."""
    return isinstance(error, SERVICE_ERROR_TYPES)


def is_user_error(error: Exception) -> bool:
    """Check if an error is a user/validation error."""
    return isinstance(error, USER_ERROR_TYPES)
