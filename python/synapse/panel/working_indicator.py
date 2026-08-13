"""Working / stalled indicator — the panel's honest in-flight liveness cue.

WHY THIS EXISTS
---------------
When the artist sends a prompt, a long tool call can leave the panel quiet for
seconds. With nothing on screen that says "the tool is still working", that
silence reads as "Houdini hung" — the worst possible misread, because the artist
force-quits a session that was actually fine. This indicator closes the gap with
three honest states and nothing else:

  * IDLE     — no call in flight. Renders NOTHING (an idle panel makes no claim).
  * BUSY     — a call is in flight and the main thread is answering. Reads as
               "tool working" in the design system's WORKING note.
  * STALLED  — a call is in flight AND the marshal layer reports the main thread
               is not answering (``stall_state()["stalled"]``). Reads as "the
               tool is stalled", in the WARNING note — never the ERROR note,
               because a stall is "worth a look", not "Houdini crashed".

STATE IS REAL, NEVER A CLOCK
----------------------------
The three states are a PURE FUNCTION of two real inputs — the panel's own busy
bool (edge-detected in ``synapse_panel._set_busy`` on the real worker lifecycle,
never a timer) and ``synapse.server.main_thread.stall_state()`` (the accumulated
``run_on_main`` timeout counter, incremented by real timeouts and reset by real
main-thread progress). There is NO ``QTimer`` in this module and no elapsed-time
threshold computed here: a near-frozen panel is told apart from a working one by
EVIDENCE the marshal layer already holds, not by a stopwatch this widget runs.
The inline budget (``marshal_guard.DEFAULT_INLINE_BUDGET_S`` /
``inline_budget_s()``) is the threshold that DEFINES an overrun inside the
marshal layer; it is surfaced here as the stalled explanation — read, never
counted against a local clock. That is the whole of acceptance #1.

HONEST LIMIT
------------
An INLINE main-thread stall (a fast-path-2 payload running ON the main thread)
freezes the Qt event loop itself; nothing in Python — this widget included — can
repaint during it (see ``marshal_guard`` module docstring). The live stalled
signal this widget CAN show is the OFF-MAIN worker-path stall, where the event
loop stays alive and ``stall_state()`` flips while the panel can still refresh.
The widget does not pretend to render during an unbreakable inline freeze.

There is a second, subtler limit on the OFF-MAIN case, named here rather than
hidden: if the mount drives ``refresh()`` from a MAIN-THREAD poll tick, the
starvation that produces the worker-path timeouts can also starve the poll, and
any successful ``run_on_main`` that lets the loop repaint RESETS the stall
counter (``main_thread._record_success``) — so the aliveness that permits a
repaint tends to clear the very stall the repaint would show. The honest way to
surface a live stall is therefore EVENT-DRIVEN: the mount should push
``refresh(stall=…, budget_s=…)`` from the marshal timeout path (``refresh`` and
``set_busy`` accept an injected snapshot for exactly that reason), not rely
solely on a main-thread poll to notice.

THREADING / COLOUR
------------------
Zero main-thread I/O, zero ``hou``. A refresh reads only O(1) in-process module
state (``stall_state()`` takes a lock and copies a dict; ``inline_budget_s()``
reads an env var). Colour comes entirely from
``designsystem.tokens.STATUS`` — this module declares none (H4 single colour
authority). Mirrors ``health_strip.py``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from synapse.panel.designsystem import tokens as t

# ── Qt guard (PySide6 primary, PySide2 fallback, None standalone) ─────────
# The pure-data core below imports with none of these, so every state / render
# rule is testable under stock CPython with no PySide (mirrors health_strip.py).
# NOTE: QtCore is deliberately NOT imported — this widget owns no timer, and not
# importing it keeps that guarantee greppable.
_QT_AVAILABLE = False
try:
    from PySide6 import QtWidgets  # noqa: F401
    _QT_AVAILABLE = True
except ImportError:
    try:
        from PySide2 import QtWidgets  # noqa: F401
        _QT_AVAILABLE = True
    except ImportError:
        QtWidgets = None


# ======================================================================
# 1. State vocabulary + the pure state machine
# ======================================================================

STATE_IDLE = "idle"
STATE_BUSY = "busy"
STATE_STALLED = "stalled"

# Each VISIBLE state → (key into the design system's one STATUS grammar, label).
# No colour is declared here; the key indexes ``tokens.STATUS`` (H4). IDLE has
# no row on purpose: it renders nothing.
#   working → FIRE  ("tool working")
#   warning → WARN  ("tool stalled" — amber, deliberately NOT ERROR/red: a stall
#                    is worth a look, not a crash, and must never read as
#                    "Houdini hung")
_STATE_STATUS = {
    STATE_BUSY:    ("working", "Working…"),
    STATE_STALLED: ("warning", "Tool stalled — still waiting"),
}


def compute_state(busy: bool, stall: Optional[Dict[str, Any]]) -> str:
    """Map (real busy bool, ``stall_state()`` dict) → visual state.

    Total, deterministic, side-effect-free: no clock, no timer, no ``hou``, no
    I/O. This is the ENTIRE state machine, kept as a pure function so acceptance
    #1 — "state transitions driven by the real busy bool and stall_state(), no
    timer-derived state" — is provable by calling it.

    ``busy`` False always wins: an idle panel makes no claim, even if the stall
    counter is still dirty from a prior turn (it is reset by the next real
    main-thread success, not by this widget).
    """
    if not busy:
        return STATE_IDLE
    stalled = bool(stall.get("stalled")) if isinstance(stall, dict) else False
    return STATE_STALLED if stalled else STATE_BUSY


def state_color(state: str) -> Optional[str]:
    """Design-system hex for a state, via the STATUS grammar. ``None`` for IDLE
    (nothing to paint). Declares no colour — indexes the one authority."""
    row = _STATE_STATUS.get(state)
    if row is None:
        return None
    return t.STATUS.get(row[0], t.STATUS["idle"])[0]


def state_label(state: str, budget_s: Optional[float] = None) -> str:
    """Operator-facing label for a state. IDLE → "" (renders nothing).

    When STALLED and an inline budget is known, the label cites it so the
    overrun reads as a measured threshold rather than a vague hang. The budget
    is the marshal layer's definition of "too long to wait inline"; it is
    surfaced, not re-measured here.
    """
    row = _STATE_STATUS.get(state)
    if row is None:
        return ""
    if state == STATE_STALLED and budget_s is not None:
        try:
            return "Tool stalled — no reply within its %.0fs window" % float(budget_s)
        except (TypeError, ValueError):
            pass
    return row[1]


def render_spec(state: str, budget_s: Optional[float] = None) -> Dict[str, Any]:
    """Pure render contract for a state — ``{visible, label, color}``.

    IDLE renders NOTHING (``visible`` False, empty label, no colour). BUSY and
    STALLED differ in BOTH label and colour, so they are distinguishable without
    relying on colour alone (colour is never the only channel). This is the data
    the Qt widget binds to, and the surface acceptance #2 tests directly.
    """
    if state not in _STATE_STATUS:
        return {"visible": False, "label": "", "color": None}
    return {
        "visible": True,
        "label": state_label(state, budget_s),
        "color": state_color(state),
    }


# ======================================================================
# 2. Real-state readers  (in-process only — no hou, no I/O)
# ======================================================================

def read_stall_state() -> Dict[str, Any]:
    """The marshal layer's live stall snapshot, defensively.

    ``main_thread.stall_state()`` takes a lock and copies a dict — no ``hou``,
    no disk, no socket. A missing/ío-broken server module degrades to
    "not stalled" (the honest default: absence of stall evidence is not a
    stall) rather than raising into the panel tick.
    """
    try:
        from synapse.server.main_thread import stall_state
        return stall_state()
    except Exception:
        return {"stalled": False, "consecutive_timeouts": 0, "last_timeout_ts": None}


def read_inline_budget() -> Optional[float]:
    """The marshal layer's inline budget (seconds), defensively. Env-overridable
    read of an in-memory constant — no ``hou``, no I/O. ``None`` if unavailable
    (the label simply omits the threshold)."""
    try:
        from synapse.server.marshal_guard import inline_budget_s
        return inline_budget_s()
    except Exception:
        return None


# ======================================================================
# 3. Qt widget — a thin binding of the pure contract above
# ======================================================================
# Only defined when a Qt binding is present. Headless CI exercises the pure
# functions above; the widget's LIVE visibility is the gui_required predicate,
# verified at a real GUI, recorded UNKNOWN when unmeasured.

if _QT_AVAILABLE:

    class WorkingIndicator(QtWidgets.QWidget):
        """Slim busy/stalled strip. Hidden when idle.

        Fed by the panel, event-driven, with NO timer of its own:
          * ``set_busy(bool)`` — called from ``synapse_panel._set_busy`` on the
            real busy edge (instant busy/idle).
          * ``refresh()``      — called from an EXISTING panel tick (e.g. the
            health/context timer), which flips busy↔stalled from live
            ``stall_state()`` while a call is in flight.

        The widget constructs no ``QTimer`` — the panel's existing ticks drive
        it, so it can never derive state from a clock of its own.
        """

        def __init__(self, parent=None):
            super().__init__(parent)
            self._busy = False
            self._state = STATE_IDLE
            self._budget_s = None

            row = QtWidgets.QHBoxLayout(self)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(getattr(t, "SPACE_XS", 4))
            self._dot = QtWidgets.QLabel("●", self)   # ● status dot
            self._dot.setObjectName("workingIndicatorDot")
            self._text = QtWidgets.QLabel("", self)
            self._text.setObjectName("workingIndicatorText")
            row.addWidget(self._dot)
            row.addWidget(self._text)
            row.addStretch(1)
            self._apply(STATE_IDLE)

        # -- fed by the panel (event-driven, no timer) --------------------
        def set_busy(self, busy) -> None:
            """Called from the panel's real ``_set_busy`` edge."""
            self._busy = bool(busy)
            self.refresh()

        def refresh(self, stall=None, budget_s=None) -> None:
            """Recompute the visible state from real inputs.

            Called from an existing panel tick and from ``set_busy``. Reads
            ``stall_state()``/``inline_budget_s()`` lazily when the caller does
            not pass a snapshot, so a test can inject one and the panel can hand
            the one it already read this tick. No ``hou``, no I/O.
            """
            if stall is None:
                stall = read_stall_state()
            if budget_s is None:
                budget_s = read_inline_budget()
            self._budget_s = budget_s
            self._apply(compute_state(self._busy, stall))

        def state(self) -> str:
            """Current visual state — for tests and the panel."""
            return self._state

        # -- render (binds the pure render_spec) --------------------------
        def _apply(self, state: str) -> None:
            self._state = state
            spec = render_spec(state, self._budget_s)
            if not spec["visible"]:
                self._text.setText("")
                self.setVisible(False)
                return
            color = spec["color"]
            sheet = ("color: %s;" % color) if color else ""
            self._dot.setStyleSheet(sheet)
            self._text.setStyleSheet(sheet)
            self._text.setText(spec["label"])
            self.setVisible(True)


__all__ = [
    "STATE_IDLE", "STATE_BUSY", "STATE_STALLED",
    "compute_state", "state_color", "state_label", "render_spec",
    "read_stall_state", "read_inline_budget",
    "WorkingIndicator", "_QT_AVAILABLE",
]
