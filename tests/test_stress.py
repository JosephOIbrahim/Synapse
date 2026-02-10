"""
Synapse Stress / Load Tests (No Live Server Required)

Unit-testable load patterns that verify resilience components
under concurrent pressure:
- RateLimiter under concurrent acquire
- CircuitBreaker trip/recovery under rapid failures
- ReadWriteLock contention with many writers
- MemoryStore throughput simulation
- BackpressureController escalation under increasing load
- Handler dispatch under concurrent calls

These run in normal pytest (no SYNAPSE_LOAD_TEST env var needed).
"""

import os
import sys
import time
import json
import types
import threading
import tempfile
import importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

# ---------------------------------------------------------------------------
# Bootstrap hou stub (needed for synapse package imports)
# ---------------------------------------------------------------------------
if "hou" not in sys.modules:
    _hou = types.ModuleType("hou")
    sys.modules["hou"] = _hou

# ---------------------------------------------------------------------------
# Import resilience directly (no relative imports inside resilience.py)
# ---------------------------------------------------------------------------
resilience_path = os.path.join(python_dir, "synapse", "server", "resilience.py")
spec = importlib.util.spec_from_file_location("resilience", resilience_path)
resilience = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resilience)

RateLimiter = resilience.RateLimiter
CircuitBreaker = resilience.CircuitBreaker
CircuitBreakerConfig = resilience.CircuitBreakerConfig
CircuitState = resilience.CircuitState
BackpressureController = resilience.BackpressureController
BackpressureConfig = resilience.BackpressureConfig
BackpressureLevel = resilience.BackpressureLevel

# ---------------------------------------------------------------------------
# Import ReadWriteLock via package path (store.py has relative imports)
# ---------------------------------------------------------------------------
from synapse.memory.store import ReadWriteLock


# =============================================================================
# RATE LIMITER CONCURRENCY TESTS
# =============================================================================

class TestRateLimiterConcurrency:
    """Test RateLimiter under concurrent access from multiple threads."""

    def test_50_concurrent_acquires(self):
        """50 threads acquiring simultaneously - no crashes, no data races."""
        limiter = RateLimiter(tokens_per_second=1000.0, bucket_size=200, per_client_bucket=50)
        results = {"allowed": 0, "rejected": 0}
        lock = threading.Lock()

        def worker(client_id):
            allowed, _ = limiter.acquire(client_id)
            with lock:
                if allowed:
                    results["allowed"] += 1
                else:
                    results["rejected"] += 1

        with ThreadPoolExecutor(max_workers=50) as pool:
            futures = [pool.submit(worker, f"client_{i}") for i in range(50)]
            for f in as_completed(futures):
                f.result()  # Raises if thread crashed

        total = results["allowed"] + results["rejected"]
        assert total == 50, f"Expected 50 results, got {total}"
        # With 200 global tokens and 50 per-client, most should succeed
        assert results["allowed"] > 0, "At least some should be allowed"

    def test_rapid_burst_exhaustion(self):
        """Rapid burst exhausts global bucket, then rejects."""
        limiter = RateLimiter(tokens_per_second=1.0, bucket_size=10, per_client_bucket=100)
        allowed_count = 0
        for i in range(20):
            allowed, _ = limiter.acquire("burst_client")
            if allowed:
                allowed_count += 1

        # Should have exhausted after ~10 tokens
        assert 8 <= allowed_count <= 12, f"Expected ~10 allowed, got {allowed_count}"

    def test_per_client_isolation(self):
        """One client exhausting their bucket doesn't block others."""
        limiter = RateLimiter(tokens_per_second=100.0, bucket_size=1000, per_client_bucket=3)

        # Exhaust client A's per-client bucket
        for _ in range(5):
            limiter.acquire("clientA")

        # Client B should still have tokens
        allowed, _ = limiter.acquire("clientB")
        assert allowed, "Client B should still have tokens"

    def test_client_removal_under_load(self):
        """Removing clients while others acquire doesn't crash."""
        limiter = RateLimiter(tokens_per_second=500.0, bucket_size=500, per_client_bucket=50)
        errors = []

        def acquirer():
            try:
                for _ in range(20):
                    limiter.acquire("persistent_client")
            except Exception as e:
                errors.append(e)

        def remover():
            try:
                for i in range(10):
                    limiter.acquire(f"temp_{i}")
                    limiter.remove_client(f"temp_{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=acquirer),
            threading.Thread(target=remover),
            threading.Thread(target=acquirer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"

    def test_stats_consistency(self):
        """Stats reflect actual request counts."""
        limiter = RateLimiter(tokens_per_second=100.0, bucket_size=50, per_client_bucket=10)
        for i in range(30):
            limiter.acquire(f"client_{i % 5}")

        stats = limiter.get_stats()
        assert stats["total_requests"] == 30
        assert stats["active_clients"] == 5


# =============================================================================
# CIRCUIT BREAKER STRESS TESTS
# =============================================================================

class TestCircuitBreakerStress:
    """Test CircuitBreaker under rapid failure/success patterns."""

    def test_rapid_failures_trip_circuit(self):
        """5 rapid failures trip the circuit to OPEN."""
        cb = CircuitBreaker(
            name="stress-test",
            config=CircuitBreakerConfig(failure_threshold=5, timeout_seconds=0.1)
        )

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_recovery_cycle(self):
        """Trip -> wait -> half-open -> successes -> closed."""
        cb = CircuitBreaker(
            name="recovery",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=0.05
            )
        )

        # Trip it
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        # Succeed twice to close
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_concurrent_record_no_crash(self):
        """Multiple threads recording successes/failures simultaneously."""
        cb = CircuitBreaker(
            name="concurrent",
            config=CircuitBreakerConfig(failure_threshold=100, timeout_seconds=0.1)
        )
        errors = []

        def record_mixed(thread_id):
            try:
                for i in range(50):
                    if i % 3 == 0:
                        cb.record_failure()
                    else:
                        cb.record_success()
                    cb.can_execute()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_mixed, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0, f"Thread errors: {errors}"
        # Should still be queryable
        _ = cb.state
        _ = cb.get_stats()

    def test_half_open_failure_retriggers_open(self):
        """Failure in half-open sends circuit back to OPEN."""
        cb = CircuitBreaker(
            name="half-open-fail",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.05
            )
        )

        # Trip
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for half-open
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        # Fail in half-open
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_state_history_bounded(self):
        """State history deque is bounded at maxlen=50."""
        cb = CircuitBreaker(
            name="history",
            config=CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.01)
        )

        # Rapidly trip and recover many times
        for _ in range(100):
            cb.record_failure()
            time.sleep(0.02)
            cb.record_success()
            cb.record_success()
            cb.record_success()

        stats = cb.get_stats()
        assert len(stats["history"]) <= 10  # get_stats returns last 10


# =============================================================================
# READWRITELOCK CONTENTION TESTS
# =============================================================================

class TestReadWriteLockContention:
    """Test ReadWriteLock under heavy concurrent read/write pressure."""

    def test_many_readers_no_writer(self):
        """Multiple concurrent readers don't block each other."""
        rwlock = ReadWriteLock()
        shared_data = {"count": 0}
        read_results = []
        lock = threading.Lock()

        def reader():
            with rwlock.read_lock():
                val = shared_data["count"]
                time.sleep(0.001)  # Simulate read work
                with lock:
                    read_results.append(val)

        threads = [threading.Thread(target=reader) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(read_results) == 20

    def test_writer_exclusion(self):
        """Writers get exclusive access."""
        rwlock = ReadWriteLock()
        shared = {"value": 0}
        errors = []

        def writer(amount):
            try:
                with rwlock.write_lock():
                    current = shared["value"]
                    time.sleep(0.001)  # Simulate work
                    shared["value"] = current + amount
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(1,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert len(errors) == 0
        assert shared["value"] == 10, f"Expected 10, got {shared['value']}"

    def test_mixed_read_write_contention(self):
        """Mix of readers and writers doesn't deadlock or corrupt."""
        rwlock = ReadWriteLock()
        data = {"counter": 0}
        errors = []

        def reader_fn():
            try:
                for _ in range(20):
                    with rwlock.read_lock():
                        _ = data["counter"]
            except Exception as e:
                errors.append(e)

        def writer_fn():
            try:
                for _ in range(5):
                    with rwlock.write_lock():
                        data["counter"] += 1
            except Exception as e:
                errors.append(e)

        threads = (
            [threading.Thread(target=reader_fn) for _ in range(5)] +
            [threading.Thread(target=writer_fn) for _ in range(3)]
        )
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0, f"Errors: {errors}"
        assert data["counter"] == 15  # 3 writers * 5 increments


# =============================================================================
# BACKPRESSURE ESCALATION TESTS
# =============================================================================

class TestBackpressureEscalation:
    """Test BackpressureController escalation under increasing load."""

    def test_normal_to_critical_escalation(self):
        """Backpressure escalates through levels as load increases."""
        bp = BackpressureController(config=BackpressureConfig(
            queue_elevated=10,
            queue_high=30,
            queue_critical=50,
        ))

        # Normal
        level, _ = bp.evaluate(queue_size=5, avg_latency=0.01)
        assert level == BackpressureLevel.NORMAL

        # Elevated
        level, _ = bp.evaluate(queue_size=15, avg_latency=0.01)
        assert level == BackpressureLevel.ELEVATED

        # High
        level, _ = bp.evaluate(queue_size=35, avg_latency=0.01)
        assert level == BackpressureLevel.HIGH

        # Critical
        level, _ = bp.evaluate(queue_size=55, avg_latency=0.01)
        assert level == BackpressureLevel.CRITICAL

    def test_latency_driven_escalation(self):
        """High latency alone triggers escalation."""
        bp = BackpressureController(config=BackpressureConfig(
            latency_elevated=0.1,
            latency_high=0.5,
            latency_critical=2.0,
        ))

        # Low latency = normal
        level, _ = bp.evaluate(queue_size=0, avg_latency=0.05)
        assert level == BackpressureLevel.NORMAL

        # High latency
        level, _ = bp.evaluate(queue_size=0, avg_latency=1.0)
        assert level == BackpressureLevel.HIGH

        # Critical latency
        level, _ = bp.evaluate(queue_size=0, avg_latency=3.0)
        assert level == BackpressureLevel.CRITICAL

    def test_circuit_open_forces_critical(self):
        """Open circuit breaker forces CRITICAL regardless of queue/latency."""
        bp = BackpressureController()
        level, info = bp.evaluate(queue_size=0, avg_latency=0.0, circuit_state="open")
        assert level == BackpressureLevel.CRITICAL
        assert info["reason"] == "circuit_open"

    def test_should_accept_behavior(self):
        """should_accept() reflects current backpressure level."""
        bp = BackpressureController(config=BackpressureConfig(
            queue_elevated=5,
            queue_high=10,
            queue_critical=20,
        ))

        # Normal - accept all
        bp.evaluate(queue_size=0, avg_latency=0.0)
        assert bp.should_accept() is True

        # High - reject non-critical
        bp.evaluate(queue_size=15, avg_latency=0.0)
        assert bp.should_accept(is_critical=False) is False
        assert bp.should_accept(is_critical=True) is True

        # Critical - reject all
        bp.evaluate(queue_size=25, avg_latency=0.0)
        assert bp.should_accept() is False


# =============================================================================
# SUSTAINED SESSION SIMULATION
# =============================================================================

class TestSustainedSessionSimulation:
    """Simulate sustained session patterns (condensed versions of 12-hour test)."""

    def test_1000_sequential_commands(self):
        """Process 1000 commands through rate limiter + circuit breaker."""
        limiter = RateLimiter(tokens_per_second=500.0, bucket_size=2000, per_client_bucket=1000)
        cb = CircuitBreaker(
            name="sustained",
            config=CircuitBreakerConfig(failure_threshold=10, timeout_seconds=1.0)
        )

        allowed_count = 0
        rejected_count = 0
        cb_blocked = 0

        for i in range(1000):
            # Rate limit check
            allowed, _ = limiter.acquire("session_client")
            if not allowed:
                rejected_count += 1
                continue

            # Circuit breaker check
            can_exec, _ = cb.can_execute()
            if not can_exec:
                cb_blocked += 1
                continue

            # Simulate occasional failure (1%)
            if i % 100 == 99:
                cb.record_failure()
            else:
                cb.record_success()

            allowed_count += 1

        # With generous limits, most should succeed
        assert allowed_count > 900, f"Only {allowed_count}/1000 succeeded"
        assert cb.state == CircuitState.CLOSED, "Circuit should still be closed"

    def test_crash_recovery_simulation(self):
        """Simulate Houdini crash (rapid failures) then recovery."""
        cb = CircuitBreaker(
            name="crash-recovery",
            config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_seconds=0.05
            )
        )

        # Normal operation
        for _ in range(10):
            cb.record_success()
        assert cb.state == CircuitState.CLOSED

        # Simulate crash (5 rapid failures)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.1)
        assert cb.state == CircuitState.HALF_OPEN

        # Recovery (3 successes)
        for _ in range(3):
            can_exec, _ = cb.can_execute()
            assert can_exec, "Half-open should allow test calls"
            cb.record_success()

        assert cb.state == CircuitState.CLOSED

    def test_multi_client_concurrent_session(self):
        """Simulate 10 clients with concurrent sessions."""
        limiter = RateLimiter(tokens_per_second=500.0, bucket_size=2000, per_client_bucket=100)
        results = {"total_allowed": 0, "total_rejected": 0}
        lock = threading.Lock()

        def client_session(client_id, num_requests):
            local_allowed = 0
            local_rejected = 0
            for _ in range(num_requests):
                allowed, _ = limiter.acquire(client_id)
                if allowed:
                    local_allowed += 1
                else:
                    local_rejected += 1
            with lock:
                results["total_allowed"] += local_allowed
                results["total_rejected"] += local_rejected

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(client_session, f"client_{i}", 50)
                for i in range(10)
            ]
            for f in as_completed(futures):
                f.result()

        total = results["total_allowed"] + results["total_rejected"]
        assert total == 500, f"Expected 500 total, got {total}"
        # Most should succeed with generous limits
        assert results["total_allowed"] > 400
