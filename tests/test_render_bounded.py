"""Tests for RenderHandlerMixin._handle_render_bounded — the bounded/guarded
tool-level render entry (Indie fix), and the render_session registry.

Mock-based, no Houdini. Patches handlers_render MODULE GLOBALS via monkeypatch
(never sys.modules — the fake-residency trap). The bounded path requires the
caller NOT to be the main thread (pytest runs on MainThread, where the wrapper
correctly takes the panel-inline branch), so bounded tests dispatch the call
from a worker thread — the same topology as the live WS handler thread.
"""

import threading
import time
import types
from unittest.mock import MagicMock

import pytest

from synapse.server import handlers_render as hr
from synapse.server import main_thread as mt
from synapse.server import render_session as rs


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class _Handler(hr.RenderHandlerMixin):
    pass


def _fake_rop(engine_val=None):
    """MagicMock ROP: type name 'karma'; parm() returns None except an
    optional 'renderer' parm evaluating to engine_val."""
    rop = MagicMock()
    rop.type.return_value.name.return_value = "karma"

    def _parm(name):
        if engine_val is not None and name == "renderer":
            p = MagicMock()
            p.eval.return_value = engine_val
            return p
        return None

    rop.parm.side_effect = _parm
    return rop


@pytest.fixture
def handler(monkeypatch):
    rs.reset()
    stub_hou = types.SimpleNamespace()
    rop = _fake_rop()
    stub_hou.node = lambda p: rop if p == "/stage/karma1" else None
    monkeypatch.setattr(hr, "hou", stub_hou, raising=False)
    monkeypatch.setattr(hr, "HOU_AVAILABLE", True)
    # Hermeticity (the fake-residency trap): the wrapper's guard probe calls
    # run_on_main, whose worker path does `import hdefereval` — importable in
    # a full-suite run ONLY because other test files plant a sys.modules fake
    # at collection time. Patch the module global instead so these tests pass
    # in isolation; run_on_main itself is pinned by test_main_thread.py.
    monkeypatch.setattr(
        mt, "run_on_main",
        lambda fn, timeout=None, **kw: fn(),
    )
    h = _Handler()
    h._test_rop = rop
    h._test_hou = stub_hou
    yield h
    rs.reset()


def _call_off_main(fn, timeout=10.0):
    """Run fn() on a worker thread (the live WS topology) and return its
    result; re-raises any exception with its original type."""
    box = {}

    def _run():
        try:
            box["r"] = fn()
        except BaseException as exc:  # noqa: BLE001
            box["e"] = exc

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    assert not t.is_alive(), "worker call did not return in time"
    if "e" in box:
        raise box["e"]
    return box["r"]


def _wait_state(token, state, deadline_s=5.0):
    """Event-anchored wait: poll the registry until the session reaches
    state (bounded), never a bare sleep assertion."""
    t0 = time.monotonic()
    while time.monotonic() - t0 < deadline_s:
        sess = rs.get_session(token)
        if sess is not None and sess["state"] == state:
            return sess
        time.sleep(0.02)
    raise AssertionError("session %s never reached %r" % (token, state))


# ---------------------------------------------------------------------------
# render_session registry
# ---------------------------------------------------------------------------

class TestRenderSessionRegistry:
    def setup_method(self):
        rs.reset()

    def teardown_method(self):
        rs.reset()

    def test_lifecycle_done(self):
        tok = rs.start_session({"rop": "/stage/karma1"})
        assert rs.get_session(tok)["state"] == "running"
        assert rs.active_session()[0] == tok
        rs.complete_session(tok, {"image_path": "x.jpg"})
        sess = rs.get_session(tok)
        assert sess["state"] == "done"
        assert sess["result"]["image_path"] == "x.jpg"
        assert rs.active_session() is None

    def test_lifecycle_error_records_message_and_type(self):
        tok = rs.start_session({})
        rs.fail_session(tok, ValueError("boom"))
        sess = rs.get_session(tok)
        assert sess["state"] == "error"
        assert sess["error"] == "boom"
        # F6: only str + type NAME are retained — never the exception object
        # (it would pin its traceback in the registry until eviction).
        assert sess["error_type"] == "ValueError"
        assert "error_exc" not in sess

    def test_status_payload_shapes(self):
        tok = rs.start_session({"engine": "karma_cpu"})
        running = rs.as_status_payload(rs.get_session(tok))
        assert running["status"] == "render_in_progress"
        assert running["render_token"] == tok
        rs.complete_session(tok, {"image_path": "x.jpg"})
        done = rs.as_status_payload(rs.get_session(tok))
        assert done["status"] == "done"
        assert done["result"]["image_path"] == "x.jpg"

    def test_eviction_keeps_running_and_caps_finished(self):
        running_tok = rs.start_session({"keep": True})
        for i in range(rs._MAX_SESSIONS + 8):
            t = rs.start_session({"i": i})
            rs.complete_session(t, {})
        assert rs.get_session(running_tok) is not None
        assert len(rs.summary()) <= rs._MAX_SESSIONS


# ---------------------------------------------------------------------------
# _handle_render_bounded
# ---------------------------------------------------------------------------

class TestBoundedRender:
    def test_fast_render_returns_result_unchanged(self, handler):
        payload_result = {"image_path": "x.jpg", "rop": "/stage/karma1"}
        handler._handle_render = lambda p: dict(payload_result)
        result = _call_off_main(
            lambda: handler._handle_render_bounded({"node": "/stage/karma1"}))
        assert result == payload_result
        assert "render_token" not in result
        assert "foreground_guard" not in result

    def test_slow_render_returns_token_then_poll_completes(self, handler):
        release = threading.Event()

        def slow_render(payload):
            release.wait(5)
            return {"image_path": "slow.jpg"}

        handler._handle_render = slow_render
        result = _call_off_main(lambda: handler._handle_render_bounded(
            {"node": "/stage/karma1", "wait_budget_s": 0.05}))
        assert result["status"] == "render_in_progress"
        token = result["render_token"]

        release.set()
        _wait_state(token, "done")
        polled = handler._handle_render_bounded({"poll": token})
        assert polled["status"] == "done"
        assert polled["result"]["image_path"] == "slow.jpg"

    def test_zero_budget_returns_immediately(self, handler):
        release = threading.Event()
        handler._handle_render = lambda p: (release.wait(5), {"image_path": "z"})[1]
        result = _call_off_main(lambda: handler._handle_render_bounded(
            {"node": "/stage/karma1", "wait_budget_s": 0}))
        assert result["status"] == "render_in_progress"
        release.set()
        _wait_state(result["render_token"], "done")

    def test_single_flight_returns_active_token(self, handler):
        release = threading.Event()
        handler._handle_render = lambda p: (release.wait(5), {"image_path": "a"})[1]
        first = _call_off_main(lambda: handler._handle_render_bounded(
            {"node": "/stage/karma1", "wait_budget_s": 0.05}))
        token = first["render_token"]

        second = _call_off_main(lambda: handler._handle_render_bounded(
            {"node": "/stage/karma1"}))
        assert second["status"] == "render_in_progress"
        assert second["render_token"] == token
        release.set()
        _wait_state(token, "done")

    def test_error_within_budget_reraises_original_type(self, handler):
        def failing_render(payload):
            raise ValueError("no camera")

        handler._handle_render = failing_render
        with pytest.raises(ValueError, match="no camera"):
            _call_off_main(lambda: handler._handle_render_bounded(
                {"node": "/stage/karma1"}))

    def test_poll_unknown_token_raises(self, handler):
        with pytest.raises(ValueError, match="render session"):
            handler._handle_render_bounded({"poll": "deadbeef0000"})

    def test_main_thread_caller_renders_inline(self, handler):
        handler._handle_render = lambda p: {"image_path": "inline.jpg"}
        result = handler._handle_render_bounded({"node": "/stage/karma1"})
        assert result == {"image_path": "inline.jpg"}
        assert rs.summary() == []  # no session on the inline path

    def test_xpu_cold_cache_refused(self, handler, monkeypatch, tmp_path):
        from synapse.server import foreground_guard as fg
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))  # empty = cold
        xpu_rop = _fake_rop(engine_val="xpu")
        handler._test_hou.node = (
            lambda p: xpu_rop if p == "/stage/karma1" else None)
        handler._handle_render = lambda p: {"image_path": "never"}
        with pytest.raises(RuntimeError, match="Foreground render refused"):
            _call_off_main(lambda: handler._handle_render_bounded(
                {"node": "/stage/karma1"}))

    def test_xpu_cold_force_runs_with_advisory(self, handler, monkeypatch, tmp_path):
        from synapse.server import foreground_guard as fg
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))
        xpu_rop = _fake_rop(engine_val="xpu")
        handler._test_hou.node = (
            lambda p: xpu_rop if p == "/stage/karma1" else None)
        handler._handle_render = lambda p: {"image_path": "forced.jpg"}
        result = _call_off_main(lambda: handler._handle_render_bounded(
            {"node": "/stage/karma1", "force_foreground": True}))
        assert result["image_path"] == "forced.jpg"
        assert result["foreground_guard"]["level"] == "forced"

    def test_delegate_id_rop_refines_engine_from_settings_lop(
            self, handler, monkeypatch, tmp_path):
        """F1: a usdrender ROP whose renderer parm evals to a Hydra delegate
        id (BRAY_HdKarma → engine 'karma_bray_hdkarma') must still refine the
        real engine from the settings LOP — here xpu + cold cache → refused."""
        from synapse.server import foreground_guard as fg
        monkeypatch.setenv(fg.OPTIX_CACHE_ENV, str(tmp_path))  # empty = cold

        krs = MagicMock()
        krs.type.return_value.name.return_value = "karmarendersettings"

        def _krs_parm(name):
            if name == "engine":
                p = MagicMock()
                p.eval.return_value = "xpu"
                return p
            return None

        krs.parm.side_effect = _krs_parm

        rop = MagicMock()
        rop.type.return_value.name.return_value = "usdrender_rop"

        def _rop_parm(name):
            if name == "renderer":
                p = MagicMock()
                p.eval.return_value = "BRAY_HdKarma"
                return p
            if name == "loppath":
                p = MagicMock()
                p.eval.return_value = "/stage/krs"
                return p
            return None

        rop.parm.side_effect = _rop_parm
        handler._test_hou.node = (
            lambda p: {"/stage/karma1": rop, "/stage/krs": krs}.get(p))
        handler._handle_render = lambda p: {"image_path": "never"}
        with pytest.raises(RuntimeError, match="Foreground render refused"):
            _call_off_main(lambda: handler._handle_render_bounded(
                {"node": "/stage/karma1"}))

    def test_farm_status_surfaces_sessions_only_when_present(self, handler):
        assert handler._handle_render_farm_status({}) == {
            "running": False, "cancelled": False, "scene_tags": []}
        tok = rs.start_session({"rop": "/stage/karma1"})
        status = handler._handle_render_farm_status({})
        assert status["render_sessions"][0]["token"] == tok
        rs.complete_session(tok, {})
