"""BP8-TIMEOUTS — router tier timeouts are enforced, and route() is bounded in the handler.

Covers the two defects the BP7 verdict traced:
  * RoutingConfig.tier2_timeout / tier3_timeout were DEFINED but never applied to
    the guarded_create LLM calls (router.py) -- a hung tier blocked forever.
  * handlers._handle_route_chat called route() with no try/except and no timeout
    (T2). BP9-RETIRE-FIX: that handler is deleted with the legacy chat surface,
    so the T2 tests went with it; only the router-side T1 tests remain.

Run without Houdini or an API key:
    python -m pytest tests/test_bp8_timeouts.py -v

Mutation map (each test reddens under exactly this change to the product code):
  * test_try_tier2_returns_within_timeout
        router.py _try_tier2: `_future.result(timeout=_t2)` -> `_future.result()`
        (drop the timeout arg) -> the tier blocks ~3s and elapsed > t2+1 fails.
  * test_tier3_sync_returns_within_timeout
        router.py _tier3_sync: `_future.result(timeout=_t3)` -> `_future.result()`
        -> the deep tier blocks ~3s and elapsed > t3+1 fails.
  * test_try_tier2_success_passthrough
        router.py _try_tier2: make the future ignore its result (e.g. return None
        instead of `_future.result(...)`) -> the parsed answer is lost.
"""

import os
import sys
import time
import threading

import pytest

import pkgbootstrap  # noqa: F401  (test-path bootstrap, mirrors test_routing.py)

package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_dir = os.path.join(package_root, "python")
sys.path.insert(0, python_dir)

from synapse.routing import router as router_mod
from synapse.routing.router import (
    TieredRouter,
    RoutingConfig,
    RoutingResult,
    RoutingTier,
)


# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class _StubResponse:
    """Shaped like an Anthropic SDK reply: `.content[0].text` + `.usage`."""

    class _Block:
        text = '{"action": "answer", "answer": "hi there", "confidence": 0.7}'

    content = [_Block()]
    usage = None


def _make_slow_guarded_create(stop_event, total_s):
    """A guarded_create stand-in that ignores its own timeout= kwarg and sleeps.

    It sleeps in small slices and honours ``stop_event`` so the worker abandoned
    on a wall-clock timeout exits promptly once the test has measured -- teardown
    stays fast despite the long nominal sleep. This is exactly the client the
    verdict describes: one that "sleeps past the tier timeout".
    """

    def _slow(client, *, lane, **kwargs):
        deadline = time.monotonic() + total_s
        while time.monotonic() < deadline:
            if stop_event.wait(0.02):
                break
        return _StubResponse()

    return _slow


def _router_with_timeouts(t2=1.0, t3=1.0):
    cfg = RoutingConfig(
        llm_api_key="test-key",
        enable_tier2=True,
        enable_tier3=True,
        tier2_timeout=t2,
        tier3_timeout=t3,
        tier3_async=False,
    )
    router = TieredRouter(config=cfg)
    # Bypass real client construction; guarded_create is monkeypatched per test,
    # so the client object is never actually dereferenced.
    router._llm_client = object()
    return router



# ---------------------------------------------------------------------------
# T1 -- tier timeouts are enforced in the router
# ---------------------------------------------------------------------------

def test_try_tier2_returns_within_timeout(monkeypatch):
    """Acceptance #1: fake client sleeping 3x tier2_timeout -> _try_tier2 returns
    in under tier2_timeout + 1 s, with a well-formed failure result."""
    stop = threading.Event()
    router = _router_with_timeouts(t2=1.0)
    monkeypatch.setattr(
        router_mod, "guarded_create", _make_slow_guarded_create(stop, total_s=3.0)
    )
    try:
        started = time.monotonic()
        result = router._try_tier2("hello", {}, "ctxhash", time.monotonic())
        elapsed = time.monotonic() - started
    finally:
        stop.set()

    assert elapsed < router._config.tier2_timeout + 1.0, f"took {elapsed:.2f}s"
    assert result is not None
    assert result.success is False
    assert result.tier is RoutingTier.STANDARD
    assert result.answer  # non-empty -> becomes the handler `response`
    assert result.metadata.get("timeout") is True


def test_tier3_sync_returns_within_timeout(monkeypatch):
    """Acceptance #2: same for the deep tier against tier3_timeout."""
    stop = threading.Event()
    router = _router_with_timeouts(t3=1.0)
    monkeypatch.setattr(
        router_mod, "guarded_create", _make_slow_guarded_create(stop, total_s=3.0)
    )
    try:
        started = time.monotonic()
        result = router._tier3_sync("plan this", {}, "ctxhash", time.monotonic())
        elapsed = time.monotonic() - started
    finally:
        stop.set()

    assert elapsed < router._config.tier3_timeout + 1.0, f"took {elapsed:.2f}s"
    assert result is not None
    assert result.success is False
    assert result.tier is RoutingTier.DEEP
    assert result.answer
    assert result.metadata.get("timeout") is True


def test_try_tier2_success_passthrough(monkeypatch):
    """Guardrail: wrapping the call in a future must still return the real reply
    on the non-timeout path (a mutation that drops the future's result reddens)."""
    stop = threading.Event()  # never set; fast create returns immediately anyway
    router = _router_with_timeouts(t2=5.0)

    def _fast(client, *, lane, **kwargs):
        return _StubResponse()

    monkeypatch.setattr(router_mod, "guarded_create", _fast)
    monkeypatch.setattr(router_mod, "sdk_receipt", lambda client: None)

    result = router._try_tier2("hello", {}, "ctxhash", time.monotonic())
    stop.set()

    assert result is not None
    assert result.success is True
    assert result.tier is RoutingTier.STANDARD
    assert result.answer == "hi there"
