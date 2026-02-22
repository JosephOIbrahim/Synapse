"""
Synapse Resilience Layer Tests

Comprehensive tests for production stability components:
- RateLimiter: Token bucket algorithm
- CircuitBreaker: State machine for failure isolation
- PortManager: Automatic port failover
- Watchdog: Main thread freeze detection
- BackpressureController: Load management
- HealthMonitor: Aggregate system health

Run without Houdini to verify core logic.
"""

import sys
import os
import time
import threading
from unittest.mock import Mock, patch

# Add package to path - import resilience directly to avoid hou dependency
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
resilience_dir = os.path.join(python_dir, "synapse", "server")
sys.path.insert(0, python_dir)
sys.path.insert(0, resilience_dir)

# Import directly from resilience.py to avoid synapse/__init__.py which imports hou
import importlib.util
spec = importlib.util.spec_from_file_location("resilience", os.path.join(resilience_dir, "resilience.py"))
resilience = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resilience)

RateLimiter = resilience.RateLimiter
CircuitBreaker = resilience.CircuitBreaker
CircuitBreakerConfig = resilience.CircuitBreakerConfig
CircuitState = resilience.CircuitState
PortManager = resilience.PortManager
PortHealth = resilience.PortHealth
Watchdog = resilience.Watchdog
BackpressureController = resilience.BackpressureController
BackpressureConfig = resilience.BackpressureConfig
BackpressureLevel = resilience.BackpressureLevel
HealthMonitor = resilience.HealthMonitor


# =============================================================================
# RATE LIMITER TESTS
# =============================================================================

def test_rate_limiter_basic_acquire():
    """Test basic token acquisition."""
    print("\n=== Testing RateLimiter: Basic Acquire ===")

    limiter = RateLimiter(tokens_per_second=10.0, bucket_size=100, per_client_bucket=20)

    # Should succeed - plenty of tokens
    allowed, info = limiter.acquire("client1")
    assert allowed, "First acquire should succeed"
    assert "remaining_global" in info, "Should return remaining tokens"
    print(f"  [PASS] Basic acquire: remaining_global={info['remaining_global']}")



def test_rate_limiter_exhaustion():
    """Test behavior when tokens exhausted."""
    print("\n=== Testing RateLimiter: Token Exhaustion ===")

    # Small bucket for quick exhaustion
    limiter = RateLimiter(tokens_per_second=1.0, bucket_size=5, per_client_bucket=3)

    # Exhaust global bucket
    for i in range(5):
        allowed, _ = limiter.acquire(f"client{i}")
        assert allowed, f"Acquire {i} should succeed"

    # Next should fail (global exhausted)
    allowed, info = limiter.acquire("clientX")
    assert not allowed, "Should be rejected when exhausted"
    assert info["reason"] == "global_rate_limit", f"Wrong reason: {info['reason']}"
    assert "retry_after" in info, "Should include retry_after"
    print(f"  [PASS] Global exhaustion: retry_after={info['retry_after']:.3f}s")



def test_rate_limiter_per_client():
    """Test per-client rate limiting."""
    print("\n=== Testing RateLimiter: Per-Client Limits ===")

    limiter = RateLimiter(tokens_per_second=100.0, bucket_size=100, per_client_bucket=3)

    # Exhaust one client's bucket
    client_id = "greedy_client"
    for i in range(3):
        allowed, _ = limiter.acquire(client_id)
        assert allowed, f"Acquire {i} should succeed"

    # Same client should be rejected
    allowed, info = limiter.acquire(client_id)
    assert not allowed, "Greedy client should be rejected"
    assert info["reason"] == "client_rate_limit", f"Wrong reason: {info['reason']}"
    print(f"  [PASS] Per-client limit enforced")

    # Different client should still work
    allowed, info = limiter.acquire("polite_client")
    assert allowed, "Different client should succeed"
    print(f"  [PASS] Other clients unaffected")



def test_rate_limiter_refill():
    """Test token refill over time."""
    print("\n=== Testing RateLimiter: Token Refill ===")

    # Fast refill for testing
    limiter = RateLimiter(tokens_per_second=100.0, bucket_size=10, per_client_bucket=5)

    # Exhaust bucket
    for i in range(10):
        limiter.acquire(f"client{i}")

    # Should be near empty
    allowed, _ = limiter.acquire("test")
    # Might pass due to refill during loop, but let's check stats

    # Wait for refill
    time.sleep(0.15)  # 15 tokens at 100/sec

    # Should have tokens again
    allowed, info = limiter.acquire("test2")
    assert allowed, "Should succeed after refill"
    print(f"  [PASS] Tokens refilled: remaining={info['remaining_global']}")



def test_rate_limiter_stats():
    """Test stats tracking."""
    print("\n=== Testing RateLimiter: Stats ===")

    limiter = RateLimiter(tokens_per_second=1.0, bucket_size=2, per_client_bucket=2)

    # Make some requests
    limiter.acquire("a")
    limiter.acquire("b")
    limiter.acquire("c")  # Should be rejected

    stats = limiter.get_stats()
    assert stats["total_requests"] == 3, f"Wrong total: {stats['total_requests']}"
    assert stats["rejected_requests"] >= 1, "Should have rejections"
    print(f"  [PASS] Stats: total={stats['total_requests']}, rejected={stats['rejected_requests']}")



def test_rate_limiter_client_cleanup():
    """Test client removal."""
    print("\n=== Testing RateLimiter: Client Cleanup ===")

    limiter = RateLimiter(tokens_per_second=10.0, bucket_size=100, per_client_bucket=10)

    # Add some clients
    limiter.acquire("client1")
    limiter.acquire("client2")

    stats_before = limiter.get_stats()
    assert stats_before["active_clients"] == 2, f"Wrong client count: {stats_before['active_clients']}"

    # Remove one
    limiter.remove_client("client1")

    stats_after = limiter.get_stats()
    assert stats_after["active_clients"] == 1, f"Client not removed: {stats_after['active_clients']}"
    print(f"  [PASS] Client cleanup: {stats_before['active_clients']} -> {stats_after['active_clients']}")



# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================

def test_circuit_breaker_initial_state():
    """Test circuit starts closed."""
    print("\n=== Testing CircuitBreaker: Initial State ===")

    cb = CircuitBreaker(name="test")
    assert cb.state == CircuitState.CLOSED, f"Should start CLOSED, got {cb.state}"
    print(f"  [PASS] Initial state: {cb.state.value}")



def test_circuit_breaker_opens_on_failures():
    """Test circuit opens after threshold failures."""
    print("\n=== Testing CircuitBreaker: Opens on Failures ===")

    config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=1.0)
    cb = CircuitBreaker(name="test", config=config)

    # Record failures
    for i in range(3):
        cb.record_failure(Exception(f"error {i}"))

    assert cb.state == CircuitState.OPEN, f"Should be OPEN after {config.failure_threshold} failures"
    print(f"  [PASS] Circuit opened after {config.failure_threshold} failures")

    # Verify calls rejected
    can_exec, info = cb.can_execute()
    assert not can_exec, "Should reject calls when OPEN"
    assert info["state"] == "open", f"Wrong state in info: {info['state']}"
    print(f"  [PASS] Calls rejected when open: retry_after={info.get('retry_after', 'N/A')}")



def test_circuit_breaker_timeout_to_half_open():
    """Test circuit transitions to HALF_OPEN after timeout."""
    print("\n=== Testing CircuitBreaker: Timeout to HALF_OPEN ===")

    config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
    cb = CircuitBreaker(name="test", config=config)

    # Open the circuit
    cb.record_failure(Exception("error"))
    assert cb.state == CircuitState.OPEN, "Should be OPEN"

    # Wait for timeout
    time.sleep(0.15)

    # Check state (triggers transition check)
    assert cb.state == CircuitState.HALF_OPEN, f"Should be HALF_OPEN after timeout, got {cb.state}"
    print(f"  [PASS] Transitioned to HALF_OPEN after {config.timeout_seconds}s")



def test_circuit_breaker_half_open_recovery():
    """Test circuit closes from HALF_OPEN on successes."""
    print("\n=== Testing CircuitBreaker: HALF_OPEN Recovery ===")

    config = CircuitBreakerConfig(
        failure_threshold=1,
        timeout_seconds=0.1,
        success_threshold=2
    )
    cb = CircuitBreaker(name="test", config=config)

    # Open and wait for half-open
    cb.record_failure(Exception("error"))
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN, "Should be HALF_OPEN"

    # Record successes
    cb.record_success()
    cb.record_success()

    assert cb.state == CircuitState.CLOSED, f"Should be CLOSED after successes, got {cb.state}"
    print(f"  [PASS] Circuit closed after {config.success_threshold} successes")



def test_circuit_breaker_half_open_failure():
    """Test circuit reopens on failure in HALF_OPEN."""
    print("\n=== Testing CircuitBreaker: HALF_OPEN Failure ===")

    config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
    cb = CircuitBreaker(name="test", config=config)

    # Open and wait for half-open
    cb.record_failure(Exception("error"))
    time.sleep(0.15)
    assert cb.state == CircuitState.HALF_OPEN, "Should be HALF_OPEN"

    # Fail again
    cb.record_failure(Exception("another error"))

    assert cb.state == CircuitState.OPEN, f"Should reopen on HALF_OPEN failure, got {cb.state}"
    print(f"  [PASS] Circuit reopened on HALF_OPEN failure")



def test_circuit_breaker_force_operations():
    """Test force_open and force_close."""
    print("\n=== Testing CircuitBreaker: Force Operations ===")

    cb = CircuitBreaker(name="test")

    # Force open
    cb.force_open()
    assert cb.state == CircuitState.OPEN, "force_open should open circuit"
    print(f"  [PASS] force_open: state={cb.state.value}")

    # Force close
    cb.force_close()
    assert cb.state == CircuitState.CLOSED, "force_close should close circuit"
    print(f"  [PASS] force_close: state={cb.state.value}")



def test_circuit_breaker_reset():
    """Test reset() fully clears failure state and closes circuit."""
    print("\n=== Testing CircuitBreaker: Reset ===")

    cb = CircuitBreaker(name="test")

    # Trigger open state
    for _ in range(5):
        cb.record_failure(Exception("error"))
    assert cb.state == CircuitState.OPEN

    # Reset should close and clear failures
    cb.reset()
    assert cb.state == CircuitState.CLOSED, "reset should close circuit"

    stats = cb.get_stats()
    assert stats["failure_count"] == 0, "reset should clear failure count"
    print(f"  [PASS] reset: state={cb.state.value}, failures={stats['failure_count']}")

    # Should be fully operational after reset
    allowed, info = cb.can_execute()
    assert allowed, "should allow execution after reset"
    print(f"  [PASS] Operational after reset")


def test_circuit_breaker_half_open_call_limit():
    """Test HALF_OPEN limits concurrent test calls."""
    print("\n=== Testing CircuitBreaker: HALF_OPEN Call Limit ===")

    config = CircuitBreakerConfig(
        failure_threshold=1,
        timeout_seconds=0.1,
        half_open_max_calls=2
    )
    cb = CircuitBreaker(name="test", config=config)

    # Open and wait for half-open
    cb.record_failure(Exception("error"))
    time.sleep(0.15)

    # Should allow limited calls
    can1, _ = cb.can_execute()
    can2, _ = cb.can_execute()
    can3, info = cb.can_execute()

    assert can1 and can2, "First two calls should be allowed"
    assert not can3, "Third call should be rejected"
    assert info["reason"] == "half_open_exhausted_retrying", f"Wrong reason: {info.get('reason')}"
    print(f"  [PASS] HALF_OPEN limited to {config.half_open_max_calls} calls")



def test_circuit_breaker_state_callback():
    """Test state change callback."""
    print("\n=== Testing CircuitBreaker: State Callback ===")

    transitions = []

    def on_change(old_state, new_state):
        transitions.append((old_state.value, new_state.value))

    config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
    cb = CircuitBreaker(name="test", config=config)
    cb.on_state_change(on_change)

    # Trigger transitions
    cb.record_failure(Exception("error"))  # CLOSED -> OPEN
    time.sleep(0.15)
    _ = cb.state  # OPEN -> HALF_OPEN
    cb.record_success()
    cb.record_success()
    cb.record_success()  # HALF_OPEN -> CLOSED

    assert len(transitions) >= 2, f"Expected transitions, got {transitions}"
    print(f"  [PASS] Transitions recorded: {transitions}")



# =============================================================================
# PORT MANAGER TESTS
# =============================================================================

def test_port_manager_initial_state():
    """Test port manager initialization."""
    print("\n=== Testing PortManager: Initial State ===")

    pm = PortManager(primary_port=9999, backup_ports=[9998, 9997])

    status = pm.get_status()
    assert status["primary_port"] == 9999, "Wrong primary port"
    assert 9999 in status["ports"], "Primary not in ports"
    assert 9998 in status["ports"], "Backup 1 not in ports"
    assert 9997 in status["ports"], "Backup 2 not in ports"
    print(f"  [PASS] Initialized with primary={status['primary_port']}, backups={pm.backup_ports}")



def test_port_manager_mark_active():
    """Test marking port as active."""
    print("\n=== Testing PortManager: Mark Active ===")

    pm = PortManager(primary_port=9999, backup_ports=[9998])

    pm.mark_active(9999)
    status = pm.get_status()

    assert status["active_port"] == 9999, "Active port not set"
    assert status["ports"][9999]["is_active"], "Port not marked active"
    print(f"  [PASS] Marked active: {status['active_port']}")



def test_port_manager_health_tracking():
    """Test health marking."""
    print("\n=== Testing PortManager: Health Tracking ===")

    pm = PortManager(primary_port=9999, backup_ports=[9998])

    # Mark unhealthy
    pm.mark_unhealthy(9999, "Address in use")
    status = pm.get_status()

    assert not status["ports"][9999]["is_healthy"], "Should be unhealthy"
    assert status["ports"][9999]["last_error"] == "Address in use", "Error not recorded"
    assert status["ports"][9999]["error_count"] == 1, "Error count wrong"
    print(f"  [PASS] Marked unhealthy: error='{status['ports'][9999]['last_error']}'")

    # Mark healthy
    pm.mark_healthy(9999)
    status = pm.get_status()

    assert status["ports"][9999]["is_healthy"], "Should be healthy"
    assert status["ports"][9999]["last_error"] is None, "Error should be cleared"
    print(f"  [PASS] Marked healthy")



def test_port_manager_failover_detection():
    """Test failover detection."""
    print("\n=== Testing PortManager: Failover Detection ===")

    pm = PortManager(primary_port=9999, backup_ports=[9998, 9997])
    pm.mark_active(9999)

    # Initially no failover needed
    should_failover, new_port = pm.should_failover()
    assert not should_failover, "Should not failover when healthy"

    # Mark primary unhealthy
    pm.mark_unhealthy(9999, "Connection refused")

    should_failover, new_port = pm.should_failover()
    assert should_failover, "Should failover when active is unhealthy"
    assert new_port == 9998, f"Should failover to first backup, got {new_port}"
    print(f"  [PASS] Failover detected: {9999} -> {new_port}")



def test_port_manager_get_active_prefers_primary():
    """Test that get_active_port prefers primary when healthy."""
    print("\n=== Testing PortManager: Primary Preference ===")

    pm = PortManager(primary_port=9999, backup_ports=[9998])

    # All healthy - should return primary
    port = pm.get_active_port()
    assert port == 9999, f"Should prefer primary, got {port}"
    print(f"  [PASS] Returns primary when healthy: {port}")

    # Primary unhealthy - should return backup
    pm.mark_unhealthy(9999, "error")
    port = pm.get_active_port()
    assert port == 9998, f"Should return backup, got {port}"
    print(f"  [PASS] Returns backup when primary unhealthy: {port}")



# =============================================================================
# WATCHDOG TESTS
# =============================================================================

def test_watchdog_heartbeat():
    """Test heartbeat tracking."""
    print("\n=== Testing Watchdog: Heartbeat ===")

    watchdog = Watchdog(heartbeat_interval=0.1, freeze_threshold=0.5)
    watchdog.start()  # arm watchdog (lazy — thread starts on first heartbeat)

    # Send heartbeat
    watchdog.heartbeat()
    stats = watchdog.get_stats()

    assert stats["total_heartbeats"] == 1, f"Wrong count: {stats['total_heartbeats']}"
    assert not stats["is_frozen"], "Should not be frozen"
    print(f"  [PASS] Heartbeat recorded: count={stats['total_heartbeats']}")

    watchdog.stop()


def test_watchdog_freeze_detection():
    """Test freeze detection."""
    print("\n=== Testing Watchdog: Freeze Detection ===")

    freeze_called = [False]
    freeze_duration = [0]

    def on_freeze(duration):
        freeze_called[0] = True
        freeze_duration[0] = duration

    watchdog = Watchdog(
        heartbeat_interval=0.05,
        freeze_threshold=0.1,
        on_freeze=on_freeze
    )

    # Start monitoring
    watchdog.start()
    watchdog.heartbeat()

    # Wait for freeze detection (no heartbeats)
    time.sleep(0.25)

    assert watchdog.is_frozen, "Should detect freeze"
    assert freeze_called[0], "Should call on_freeze callback"
    print(f"  [PASS] Freeze detected after {freeze_duration[0]:.2f}s")

    watchdog.stop()


def test_watchdog_recovery():
    """Test recovery from freeze."""
    print("\n=== Testing Watchdog: Recovery ===")

    recovered = [False]

    def on_freeze(duration):
        pass

    def on_recover():
        recovered[0] = True

    watchdog = Watchdog(
        heartbeat_interval=0.05,
        freeze_threshold=0.1,
        on_freeze=on_freeze,
        on_recover=on_recover
    )

    watchdog.start()
    watchdog.heartbeat()

    # Let it freeze
    time.sleep(0.2)
    assert watchdog.is_frozen, "Should be frozen"

    # Recover
    watchdog.heartbeat()
    assert not watchdog.is_frozen, "Should recover"
    assert recovered[0], "Should call on_recover"
    print(f"  [PASS] Recovery detected")

    watchdog.stop()


def test_watchdog_stats():
    """Test stats collection."""
    print("\n=== Testing Watchdog: Stats ===")

    watchdog = Watchdog(heartbeat_interval=0.1, freeze_threshold=1.0)
    watchdog.start()  # arm watchdog

    # Send some heartbeats with delays
    watchdog.heartbeat()
    time.sleep(0.05)
    watchdog.heartbeat()
    time.sleep(0.03)
    watchdog.heartbeat()

    stats = watchdog.get_stats()
    assert stats["total_heartbeats"] == 3, f"Wrong count: {stats['total_heartbeats']}"
    assert "avg_latency" in stats, "Should track avg latency"
    assert "max_latency" in stats, "Should track max latency"
    print(f"  [PASS] Stats: count={stats['total_heartbeats']}, avg={stats['avg_latency']:.4f}s")

    watchdog.stop()


# =============================================================================
# BACKPRESSURE CONTROLLER TESTS
# =============================================================================

def test_backpressure_normal_at_low_load():
    """Test NORMAL level at low load."""
    print("\n=== Testing BackpressureController: Normal Level ===")

    bp = BackpressureController()

    level, info = bp.evaluate(queue_size=5, avg_latency=0.01)

    assert level == BackpressureLevel.NORMAL, f"Should be NORMAL, got {level}"
    assert bp.should_accept(is_critical=False), "Should accept non-critical"
    print(f"  [PASS] NORMAL at low load")



def test_backpressure_elevated_at_medium_load():
    """Test ELEVATED level at medium load."""
    print("\n=== Testing BackpressureController: Elevated Level ===")

    config = BackpressureConfig(queue_elevated=10, queue_high=50)
    bp = BackpressureController(config=config)

    level, info = bp.evaluate(queue_size=15, avg_latency=0.01)

    assert level == BackpressureLevel.ELEVATED, f"Should be ELEVATED, got {level}"
    assert bp.should_accept(is_critical=False), "Should still accept at ELEVATED"
    print(f"  [PASS] ELEVATED at queue={info.get('queue_size', 15)}")



def test_backpressure_high_at_heavy_load():
    """Test HIGH level at heavy load."""
    print("\n=== Testing BackpressureController: High Level ===")

    config = BackpressureConfig(queue_high=20, queue_critical=80)
    bp = BackpressureController(config=config)

    level, info = bp.evaluate(queue_size=30, avg_latency=0.01)

    assert level == BackpressureLevel.HIGH, f"Should be HIGH, got {level}"
    assert not bp.should_accept(is_critical=False), "Should reject non-critical at HIGH"
    assert bp.should_accept(is_critical=True), "Should accept critical at HIGH"
    print(f"  [PASS] HIGH at queue={info.get('queue_size', 30)}")



def test_backpressure_critical_at_extreme_load():
    """Test CRITICAL level at extreme load."""
    print("\n=== Testing BackpressureController: Critical Level ===")

    config = BackpressureConfig(queue_critical=50)
    bp = BackpressureController(config=config)

    level, info = bp.evaluate(queue_size=60, avg_latency=0.01)

    assert level == BackpressureLevel.CRITICAL, f"Should be CRITICAL, got {level}"
    assert not bp.should_accept(is_critical=False), "Should reject non-critical"
    assert not bp.should_accept(is_critical=True), "Should reject even critical at CRITICAL"
    print(f"  [PASS] CRITICAL at queue={info.get('queue_size', 60)}")



def test_backpressure_circuit_override():
    """Test circuit state overrides queue-based level."""
    print("\n=== Testing BackpressureController: Circuit Override ===")

    bp = BackpressureController()

    # Even with low queue, circuit open = CRITICAL
    level, info = bp.evaluate(queue_size=1, avg_latency=0.001, circuit_state="open")

    assert level == BackpressureLevel.CRITICAL, f"Should be CRITICAL when circuit open, got {level}"
    assert info["reason"] == "circuit_open", f"Wrong reason: {info.get('reason')}"
    print(f"  [PASS] Circuit open overrides to CRITICAL")



def test_backpressure_latency_thresholds():
    """Test latency-based level transitions."""
    print("\n=== Testing BackpressureController: Latency Thresholds ===")

    config = BackpressureConfig(
        latency_elevated=0.1,
        latency_high=0.5,
        latency_critical=2.0
    )
    bp = BackpressureController(config=config)

    # High latency should trigger
    level, info = bp.evaluate(queue_size=1, avg_latency=0.6)
    assert level == BackpressureLevel.HIGH, f"Should be HIGH at high latency, got {level}"
    print(f"  [PASS] HIGH at latency={info.get('latency', 0.6)}s")

    # Critical latency
    level, info = bp.evaluate(queue_size=1, avg_latency=3.0)
    assert level == BackpressureLevel.CRITICAL, f"Should be CRITICAL at critical latency, got {level}"
    print(f"  [PASS] CRITICAL at latency={info.get('latency', 3.0)}s")



# =============================================================================
# HEALTH MONITOR TESTS
# =============================================================================

def test_health_monitor_all_healthy():
    """Test health status when all components healthy."""
    print("\n=== Testing HealthMonitor: All Healthy ===")

    # Create healthy components
    rate_limiter = RateLimiter(tokens_per_second=100, bucket_size=100, per_client_bucket=20)
    circuit_breaker = CircuitBreaker(name="test")
    port_manager = PortManager(primary_port=9999)
    port_manager.mark_active(9999)
    port_manager.mark_healthy(9999)
    watchdog = Watchdog(heartbeat_interval=1.0, freeze_threshold=5.0)
    backpressure = BackpressureController()

    monitor = HealthMonitor(
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker,
        port_manager=port_manager,
        watchdog=watchdog,
        backpressure=backpressure
    )

    health = monitor.to_dict()

    assert health["healthy"], "Should be healthy"
    assert health["level"] == "healthy", f"Wrong level: {health['level']}"
    assert "components" in health, "Should include components"
    print(f"  [PASS] All healthy: level={health['level']}, message='{health['message']}'")



def test_health_monitor_degraded():
    """Test health status when partially degraded."""
    print("\n=== Testing HealthMonitor: Degraded ===")

    # Create with one unhealthy port
    port_manager = PortManager(primary_port=9999, backup_ports=[9998])
    port_manager.mark_unhealthy(9999, "test error")

    monitor = HealthMonitor(port_manager=port_manager)

    health = monitor.to_dict()

    # Should be degraded but still "healthy" overall
    assert health["level"] in ("degraded", "unhealthy"), f"Should be degraded, got {health['level']}"
    assert "unhealthy" in health["message"].lower() or "ports" in health["message"].lower(), \
        f"Message should mention issue: {health['message']}"
    print(f"  [PASS] Degraded: level={health['level']}, message='{health['message']}'")



def test_health_monitor_critical():
    """Test health status when critical."""
    print("\n=== Testing HealthMonitor: Critical ===")

    # Create with open circuit
    circuit_breaker = CircuitBreaker(name="test")
    circuit_breaker.force_open()

    monitor = HealthMonitor(circuit_breaker=circuit_breaker)

    health = monitor.to_dict()

    assert not health["healthy"], "Should not be healthy"
    assert health["level"] == "critical", f"Should be critical, got {health['level']}"
    assert "circuit" in health["message"].lower() or "open" in health["message"].lower(), \
        f"Message should mention circuit: {health['message']}"
    print(f"  [PASS] Critical: level={health['level']}, message='{health['message']}'")



def test_health_monitor_component_stats():
    """Test that component stats are included."""
    print("\n=== Testing HealthMonitor: Component Stats ===")

    rate_limiter = RateLimiter(tokens_per_second=10, bucket_size=10, per_client_bucket=5)
    rate_limiter.acquire("test")

    circuit_breaker = CircuitBreaker(name="test")

    monitor = HealthMonitor(
        rate_limiter=rate_limiter,
        circuit_breaker=circuit_breaker
    )

    health = monitor.to_dict()

    assert "rate_limiter" in health["components"], "Should include rate_limiter"
    assert "circuit_breaker" in health["components"], "Should include circuit_breaker"
    assert health["components"]["rate_limiter"]["total_requests"] == 1, "Should track requests"
    print(f"  [PASS] Component stats included")



# =============================================================================
# TEST RUNNER
# =============================================================================

def run_all_tests():
    """Run all resilience layer tests."""
    print("=" * 70)
    print("SYNAPSE RESILIENCE LAYER TEST SUITE")
    print("=" * 70)

    tests = [
        # Rate Limiter
        ("RateLimiter: Basic Acquire", test_rate_limiter_basic_acquire),
        ("RateLimiter: Token Exhaustion", test_rate_limiter_exhaustion),
        ("RateLimiter: Per-Client Limits", test_rate_limiter_per_client),
        ("RateLimiter: Token Refill", test_rate_limiter_refill),
        ("RateLimiter: Stats", test_rate_limiter_stats),
        ("RateLimiter: Client Cleanup", test_rate_limiter_client_cleanup),

        # Circuit Breaker
        ("CircuitBreaker: Initial State", test_circuit_breaker_initial_state),
        ("CircuitBreaker: Opens on Failures", test_circuit_breaker_opens_on_failures),
        ("CircuitBreaker: Timeout to HALF_OPEN", test_circuit_breaker_timeout_to_half_open),
        ("CircuitBreaker: HALF_OPEN Recovery", test_circuit_breaker_half_open_recovery),
        ("CircuitBreaker: HALF_OPEN Failure", test_circuit_breaker_half_open_failure),
        ("CircuitBreaker: Force Operations", test_circuit_breaker_force_operations),
        ("CircuitBreaker: HALF_OPEN Call Limit", test_circuit_breaker_half_open_call_limit),
        ("CircuitBreaker: State Callback", test_circuit_breaker_state_callback),

        # Port Manager
        ("PortManager: Initial State", test_port_manager_initial_state),
        ("PortManager: Mark Active", test_port_manager_mark_active),
        ("PortManager: Health Tracking", test_port_manager_health_tracking),
        ("PortManager: Failover Detection", test_port_manager_failover_detection),
        ("PortManager: Primary Preference", test_port_manager_get_active_prefers_primary),

        # Watchdog
        ("Watchdog: Heartbeat", test_watchdog_heartbeat),
        ("Watchdog: Freeze Detection", test_watchdog_freeze_detection),
        ("Watchdog: Recovery", test_watchdog_recovery),
        ("Watchdog: Stats", test_watchdog_stats),

        # Backpressure
        ("Backpressure: Normal Level", test_backpressure_normal_at_low_load),
        ("Backpressure: Elevated Level", test_backpressure_elevated_at_medium_load),
        ("Backpressure: High Level", test_backpressure_high_at_heavy_load),
        ("Backpressure: Critical Level", test_backpressure_critical_at_extreme_load),
        ("Backpressure: Circuit Override", test_backpressure_circuit_override),
        ("Backpressure: Latency Thresholds", test_backpressure_latency_thresholds),

        # Health Monitor
        ("HealthMonitor: All Healthy", test_health_monitor_all_healthy),
        ("HealthMonitor: Degraded", test_health_monitor_degraded),
        ("HealthMonitor: Critical", test_health_monitor_critical),
        ("HealthMonitor: Component Stats", test_health_monitor_component_stats),
    ]

    results = []
    for name, test_fn in tests:
        try:
            test_fn()
            results.append((name, True, None))
        except Exception as e:
            import traceback
            results.append((name, False, str(e)))
            traceback.print_exc()

    print("\n" + "=" * 70)
    print("TEST RESULTS")
    print("=" * 70)

    passed = 0
    failed = 0
    for name, success, error in results:
        status = "PASS" if success else "FAIL"
        print(f"  [{status}] {name}")
        if error:
            print(f"         Error: {error}")
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\nTotal: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
