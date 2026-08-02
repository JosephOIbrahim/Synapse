"""h7 inline guard + honest thread attribution — FREEZE_FORENSICS_20260731.

Pins the three defects the 2026-07-31 forensics left as an unimplemented
remediation ticket (§5 items 1, 2 and 3).

Background, because the shape is counter-intuitive. The v5.40.1 "chat no longer
grips the UI" fix bounded the *caller's wait* and never the *running payload*.
Freezes therefore continued after it: 8 of them on 2026-07-31, up to 44.4s, one
escalating to SUSTAINED FREEZE. The reason a payload cannot simply be timed out
is stated verbatim at handlers_render.py:109-113 — "nothing in Python can
interrupt the main thread from the main thread". A guard that REFUSES before
entry is the only mechanism available, which is why this mirrors the render
foreground_guard rather than adding another timeout.

  §5.1 PRIMARY  — a heavy payload must not start inline on the main thread
  §5.2 SECONDARY— off-main wall-time must never be recorded as main-thread time
  §5.3 HAZARD   — the armed-but-inert class-3 wire must stay emitter-free
"""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Qt stub — mirrors the canonical sibling stub (test_panel_preflight.py /
# test_timeouts_c7.py) EXACTLY, and only plants when nothing else has.
#
# ⚠ THE FILENAME IS LOAD-BEARING. This module is named to sort immediately
# AFTER test_panel_preflight.py ('.' < '_'), so in a full-suite run that file
# has already planted the stub and imported tool_executor, and this one
# inherits both. An earlier name (the first draft was
# test_freeze_h7_inline_guard.py) made this module the alphabetically-first
# panel test, which pulled `from synapse.panel import tool_executor` forward in
# collection — the class then bound QObject from whatever stub existed at that
# earlier moment, and six previously-green tests in test_panel_preflight.py
# started failing with `_last_preflight` returning a MagicMock attribute
# instead of None. They pass on master; the rename, not a code change, fixed
# them. Do not rename this file without re-running the FULL suite.
# ---------------------------------------------------------------------------
if "PySide6" not in sys.modules:
    class _QObject:
        def __init__(self, *a, **k):
            pass

    class _QThread:
        def __init__(self, *a, **k):
            pass

    _qtcore = types.ModuleType("PySide6.QtCore")
    _qtcore.QObject = _QObject
    _qtcore.QThread = _QThread
    _qtcore.Slot = lambda *a, **k: (lambda f: f)
    _qtcore.Signal = lambda *a, **k: MagicMock()
    _pyside6 = types.ModuleType("PySide6")
    _pyside6.QtCore = _qtcore
    sys.modules["PySide6"] = _pyside6
    sys.modules["PySide6.QtCore"] = _qtcore

from synapse.panel import bridge_adapter as ba
from synapse.panel import tool_executor as te

REPO = Path(__file__).resolve().parents[1]

HEAVY = {"code": "y = 1\n" * 1000}
LIGHT = {"code": "hou.node('/obj')"}


class _Resp:
    def __init__(self, data):
        self.success = True
        self.data = data
        self.error = None


class _Handler:
    def __init__(self, data):
        self._data = data
        self.calls = []

    def handle(self, command):
        self.calls.append(command)
        return _Resp(self._data)


def _wire(monkeypatch, handler):
    ex = te.ToolExecutor()
    monkeypatch.setattr(te, "get_tool_dispatch",
                        lambda name: ("execute_python", lambda inp: dict(inp)))
    monkeypatch.setattr(ba, "is_read_only", lambda name: True)  # skip the bridge
    monkeypatch.setattr(ex, "_get_handler", lambda: handler)
    return ex


def _really_off_main(ex, req, timeout=10.0):
    """Run on a genuine non-main thread.

    Calling execute_tool_off_main from the test's own thread is still
    main-thread execution — the guard reads real thread identity, not the
    entrypoint. That distinction is the whole point of §5.2.
    """
    th = threading.Thread(target=ex.execute_tool_off_main, args=(req,), daemon=True)
    th.start()
    th.join(timeout=timeout)
    assert not th.is_alive(), "off-main dispatch did not finish"


# ── §5.1 PRIMARY — the inline guard ────────────────────────────────────────

def test_heavy_tool_is_refused_inline_on_the_main_thread(monkeypatch):
    """FAILS IF: a payload the pre-flight calls heavy is allowed to start on
    Houdini's main thread. That is the 46.7-second freeze."""
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    req = te.ToolRequest("tu_heavy_main", "houdini_execute_python", HEAVY)

    ex.execute_tool(req)  # the Qt slot path == main thread

    assert req.error is not None, "heavy inline dispatch was NOT refused"
    assert "main thread" in req.error
    assert handler.calls == [], "the payload ran anyway — the guard is cosmetic"
    assert req.done.is_set(), "a refused request must still be completed"


def test_light_tool_still_runs_inline(monkeypatch):
    """FAILS IF: the guard over-fires and refuses ordinary work."""
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    req = te.ToolRequest("tu_light_main", "houdini_execute_python", LIGHT)

    ex.execute_tool(req)

    assert req.error is None
    assert len(handler.calls) == 1


def test_heavy_tool_runs_when_genuinely_off_main(monkeypatch):
    """FAILS IF: the guard blocks the production path. The worker dispatches
    off-main (claude_worker.py:348-374); heavy work must still get through."""
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    req = te.ToolRequest("tu_heavy_off", "houdini_execute_python", HEAVY)

    _really_off_main(ex, req)

    assert req.error is None, "the guard leaked onto the off-main path"
    assert len(handler.calls) == 1


def test_escape_hatch_allows_a_deliberate_inline_freeze(monkeypatch):
    """A caller that has accepted the freeze can still opt in explicitly."""
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    ex._allow_heavy_inline = True
    req = te.ToolRequest("tu_forced", "houdini_execute_python", HEAVY)

    ex.execute_tool(req)

    assert req.error is None
    assert len(handler.calls) == 1


def test_guard_does_not_leak_between_requests(monkeypatch):
    """FAILS IF: a heavy request's verdict refuses the NEXT, light request."""
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)

    heavy = te.ToolRequest("tu_a", "houdini_execute_python", HEAVY)
    ex.execute_tool(heavy)
    assert heavy.error is not None

    light = te.ToolRequest("tu_b", "houdini_execute_python", LIGHT)
    ex.execute_tool(light)
    assert light.error is None, "stale heavy verdict leaked into the next request"


# ── §5.2 SECONDARY — honest thread attribution ─────────────────────────────

def test_off_main_time_is_not_recorded_as_main_thread_time(monkeypatch):
    """FAILS IF: daemon-thread wall-time lands in the main-thread counters.

    This is the follow-on defect the forensics said "corrupted forensics this
    run and will corrupt the next one" — an off-main dispatch stalls no Qt
    loop, so counting it as main-thread hold time aims the next investigation
    at the wrong mechanism.
    """
    te.reset_panel_inline_stats()
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    req = te.ToolRequest("tu_attr", "houdini_execute_python", LIGHT)

    _really_off_main(ex, req)

    stats = te.panel_inline_stats()
    assert stats["count"] == 0, "off-main dispatch counted as main-thread time"
    assert stats["offmain_count"] == 1, "off-main dispatch was not recorded at all"
    assert stats["offmain_slowest_tool"] == "houdini_execute_python"


def test_main_thread_dispatch_is_recorded_as_main_thread_time(monkeypatch):
    """The paired positive control — without it the test above passes vacuously
    if the counter simply stopped recording anything."""
    te.reset_panel_inline_stats()
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)
    req = te.ToolRequest("tu_attr2", "houdini_execute_python", LIGHT)

    ex.execute_tool(req)

    stats = te.panel_inline_stats()
    assert stats["count"] == 1
    assert stats["offmain_count"] == 0


def test_slow_log_discriminates_the_two_paths(monkeypatch, caplog):
    """FAILS IF: both paths log the same 'Qt loop stalled' sentence."""
    monkeypatch.setattr(te, "PANEL_INLINE_SLOW_MS", 0.0)
    handler = _Handler({"ok": 1})
    ex = _wire(monkeypatch, handler)

    with caplog.at_level("WARNING"):
        _really_off_main(ex, te.ToolRequest("tu_s1", "houdini_execute_python", LIGHT))

    msgs = [r.getMessage() for r in caplog.records]
    assert any("Qt loop NOT stalled" in m for m in msgs), (
        "off-main dispatch must not claim the Qt loop stalled")
    assert not any("Qt loop stalled this long" in m for m in msgs)


# ── §5.3 HAZARD — the armed-but-inert class-3 wire ─────────────────────────

def test_no_production_emitter_of_tool_requested():
    """FAILS IF: anything in production emits ``tool_requested``.

    synapse_panel.py:1938 connects worker.tool_requested -> execute_tool, the
    synchronous main-thread slot. The wire is live and has zero emitters, which
    is the only reason class 3 stays closed. ONE ``.emit`` re-arms a freeze
    class that already has a verified fix, and nothing else in CI would notice.
    """
    offenders = []
    for path in (REPO / "python").rglob("*.py"):
        if "_vendor" in path.parts or "test" in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if "tool_requested" in line and ".emit" in line:
                offenders.append(f"{path.relative_to(REPO).as_posix()}:{n}: {line.strip()}")

    assert not offenders, (
        "tool_requested is emitted in production — this re-arms freeze class 3 "
        "(chat-time Qt fallback, closed at d15d9b2). Dispatch off-main instead:\n"
        + "\n".join(offenders)
    )
