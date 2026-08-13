"""Acceptance tests for the panel working/stalled indicator (W2-S3).

The indicator's substance is a pure state machine fed by REAL state — the
panel's busy bool and ``main_thread.stall_state()`` — so every predicate below
is provable under stock CPython with no PySide and no Houdini. The Qt widget is
a thin binding of that contract; its live on-screen visibility is the
``gui_required`` predicate, verified at a real GUI (recorded UNKNOWN when
unmeasured), not here.

Predicate map (mission W2-S3 acceptance):
  #1 real-state, no timer   → TestNoTimerRealState
  #2 busy/stalled distinct, idle nothing → TestDistinguishableRender
  #3 zero main-thread I/O, zero hou       → TestZeroHouZeroIO
  crucible: no new colour/token authority → TestNoNewColourAuthority
"""

import builtins
import re
import sys
from pathlib import Path

import pytest

# Warm the server import cache BEFORE any open()-tripwire test runs, so the
# import machinery's own file reads can never be mistaken for indicator I/O.
import synapse.server.main_thread  # noqa: E402,F401
import synapse.server.marshal_guard  # noqa: E402,F401

from synapse.panel import working_indicator as wi  # noqa: E402
from synapse.panel.designsystem import tokens as dt  # noqa: E402


# ======================================================================
# Acceptance #1 — real-state transitions, no timer-derived state
# ======================================================================

class TestNoTimerRealState:
    def test_state_from_real_busy_bool_and_stall_state(self):
        # idle: nothing in flight
        assert wi.compute_state(False, {"stalled": False}) == wi.STATE_IDLE
        # busy: in flight, main thread answering
        assert wi.compute_state(True, {"stalled": False}) == wi.STATE_BUSY
        # stalled: in flight, marshal layer reports no answer
        assert wi.compute_state(True, {"stalled": True}) == wi.STATE_STALLED

    def test_not_busy_overrides_stall(self):
        # An idle panel makes no claim even if the stall counter is still dirty.
        assert wi.compute_state(False, {"stalled": True}) == wi.STATE_IDLE

    def test_state_is_time_independent(self):
        # Pure function: identical inputs → identical output, no clock involved.
        a = wi.compute_state(True, {"stalled": False})
        b = wi.compute_state(True, {"stalled": False})
        assert a == b == wi.STATE_BUSY

    def test_malformed_stall_snapshot_degrades_to_busy_not_crash(self):
        # A non-dict / missing key is treated as "no stall evidence" — busy, not
        # a raise into the panel tick.
        assert wi.compute_state(True, None) == wi.STATE_BUSY
        assert wi.compute_state(True, {}) == wi.STATE_BUSY

    def test_module_declares_no_timer(self):
        src = Path(wi.__file__).read_text(encoding="utf-8")
        # The widget owns no clock. Asserted on CODE constructs (not prose — the
        # docstring names QTimer to say there is none): a timer cannot be built
        # without CONSTRUCTING one (``QTimer(``) and cannot be referenced without
        # importing ``QtCore``, which vends it. Neither appears.
        assert "QTimer(" not in src
        assert "import QtCore" not in src
        # Also no inherited-timer backdoor: a QWidget can drive a clock via
        # startTimer()/timerEvent()/QBasicTimer without ever naming QTimer.
        assert "startTimer(" not in src
        assert "timerEvent" not in src
        assert "QBasicTimer" not in src

    def test_readers_bind_to_the_real_primitives(self):
        # Proves the feeds are the real primitives named in the brief, not stubs.
        snap = wi.read_stall_state()
        assert isinstance(snap, dict) and "stalled" in snap
        budget = wi.read_inline_budget()
        # DEFAULT_INLINE_BUDGET_S = 5.0 (marshal_guard), env-overridable.
        from synapse.server.marshal_guard import inline_budget_s
        assert budget == inline_budget_s()


# ======================================================================
# Acceptance #2 — busy and stalled render distinguishably; idle nothing
# ======================================================================

class TestDistinguishableRender:
    def test_idle_renders_nothing(self):
        spec = wi.render_spec(wi.STATE_IDLE)
        assert spec == {"visible": False, "label": "", "color": None}

    def test_busy_and_stalled_render_distinguishably(self):
        busy = wi.render_spec(wi.STATE_BUSY)
        stalled = wi.render_spec(wi.STATE_STALLED, budget_s=5.0)
        assert busy["visible"] and stalled["visible"]
        # Distinguishable on BOTH channels, never colour alone.
        assert busy["label"] != stalled["label"]
        assert busy["color"] != stalled["color"]

    def test_stalled_is_warning_not_error(self):
        # A stall is "worth a look", never "Houdini crashed": it uses the WARNING
        # note, and must NOT borrow the ERROR note.
        stalled_color = wi.state_color(wi.STATE_STALLED)
        assert stalled_color == dt.STATUS["warning"][0]
        assert stalled_color != dt.STATUS["error"][0]

    def test_busy_uses_the_working_note(self):
        assert wi.state_color(wi.STATE_BUSY) == dt.STATUS["working"][0]

    def test_stalled_label_cites_the_inline_budget(self):
        # The inline budget feeds the stalled explanation (a measured threshold,
        # not a vague hang).
        label = wi.state_label(wi.STATE_STALLED, budget_s=5.0)
        assert "5" in label and label != wi.state_label(wi.STATE_BUSY)

    def test_widget_visibility_transitions(self):
        pytest.importorskip("PySide6")
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        ind = wi.WorkingIndicator()
        # idle → nothing
        ind.set_busy(False)
        assert ind.state() == wi.STATE_IDLE and not ind.isVisible()
        # busy → visible working (inject a clear stall snapshot)
        ind.set_busy(True)
        ind.refresh(stall={"stalled": False}, budget_s=5.0)
        assert ind.state() == wi.STATE_BUSY and ind.isVisible()
        busy_text = ind._text.text()
        # stalled → visible warning, distinct text
        ind.refresh(stall={"stalled": True}, budget_s=5.0)
        assert ind.state() == wi.STATE_STALLED and ind.isVisible()
        assert ind._text.text() != busy_text
        # back to idle → hidden again
        ind.set_busy(False)
        assert ind.state() == wi.STATE_IDLE and not ind.isVisible()

    def test_widget_constructs_no_qtimer(self):
        pytest.importorskip("PySide6")
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6 import QtWidgets, QtCore
        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        ind = wi.WorkingIndicator()
        assert ind.findChild(QtCore.QTimer) is None


# ======================================================================
# Acceptance #3 — zero main-thread I/O, zero hou
# ======================================================================

class _HouTripwire:
    """Any attribute touch on ``hou`` is recorded — the module must never do so."""

    def __init__(self):
        self.accessed = []

    def __getattr__(self, name):
        self.accessed.append(name)
        raise AttributeError("indicator touched hou.%s — forbidden" % name)


class TestZeroHouZeroIO:
    def _exercise(self):
        # Every real-state path the widget runs on a refresh, minus Qt.
        wi.read_stall_state()
        wi.read_inline_budget()
        for st in (wi.STATE_IDLE, wi.STATE_BUSY, wi.STATE_STALLED):
            wi.render_spec(wi.compute_state(True, {"stalled": st == wi.STATE_STALLED}),
                           budget_s=wi.read_inline_budget())

    def test_refresh_makes_no_hou_call(self):
        # Restore THE ORIGINAL object (the conftest fake hou is resident here);
        # express absence as ``= None``, never a pop — the repo's fake-residency
        # guard fails a session that leaves a foreign hou or pops the key.
        original = sys.modules.get("hou", None)
        trip = _HouTripwire()
        sys.modules["hou"] = trip
        try:
            self._exercise()
        finally:
            sys.modules["hou"] = original if original is not None else None
        assert trip.accessed == []

    def test_refresh_does_no_file_io(self):
        # main_thread + marshal_guard are already imported (warmed at module top),
        # so the only open() that could fire here would be indicator I/O.
        real_open = builtins.open
        calls = []

        def _tripwire_open(*a, **k):
            calls.append(a[0] if a else None)
            raise AssertionError("indicator performed file I/O: open(%r)" % (a[:1],))

        builtins.open = _tripwire_open
        try:
            self._exercise()
        finally:
            builtins.open = real_open
        assert calls == []


# ======================================================================
# Crucible criterion — no new colour/token authority (H4 respected)
# ======================================================================

class TestNoNewColourAuthority:
    def test_declares_no_colour_literal(self):
        src = Path(wi.__file__).read_text(encoding="utf-8")
        # No raw hex colour anywhere — every colour is indexed from the one
        # authority (designsystem.tokens.STATUS), exactly like health_strip.py.
        assert re.search(r"#[0-9A-Fa-f]{6}\b", src) is None

    def test_colours_come_from_the_status_authority(self):
        # The two visible states map onto existing STATUS keys, not new tokens.
        assert wi.state_color(wi.STATE_BUSY) in {v[0] for v in dt.STATUS.values()}
        assert wi.state_color(wi.STATE_STALLED) in {v[0] for v in dt.STATUS.values()}
