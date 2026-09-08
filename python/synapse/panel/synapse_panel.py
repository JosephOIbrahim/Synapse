"""SYNAPSE panel — the redesigned, unified surface.

One panel, three zones (Converse / Act / Trust) framed by a Context ribbon and a
Connection footer, built on the vendored design system and *reusing the proven
runtime* (ClaudeWorker streaming + ToolExecutor + ChatDisplay + GateWidget)
rather than rewriting it. Closes the consent-gate gap the shipped legacy panel
had: GateWidget is wired in, so HumanGate proposals surface as actionable cards.

Entry point: ``createInterface()`` (Houdini Python Panel convention). The
``.pypanel`` at houdini/python_panels/ is a thin loader for this class.
"""

import logging
from functools import partial

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QShortcut, QKeySequence
except ImportError:  # pragma: no cover - Houdini ships PySide6
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Qt, QTimer, Signal
    from PySide2.QtWidgets import QShortcut
    from PySide2.QtGui import QKeySequence

from synapse.panel.designsystem import tokens as t
from synapse.panel.designsystem import qss
from synapse.panel.designsystem import components as c
from synapse.panel.designsystem import motion
from synapse.panel.designsystem import fontload
from synapse.panel.gate_stamp import phantom_gate_status

# L5-2: layout manifests + compositor — the region sequence is data-driven.
# Pure-stdlib modules, but guarded like the rest of the runtime imports so the
# panel always instantiates; _build_ui falls back to the v5.42.0 wiring.
try:
    from synapse.panel.manifests import ManifestError, get_manifest, DEFAULT_PROFILE
    from synapse.panel.compositor import compose
except Exception:  # pragma: no cover
    ManifestError = get_manifest = compose = None
    DEFAULT_PROFILE = "expert"

# This module had no logger. Its guarded runtime paths therefore had nowhere to
# leave a trail even if they wanted one — which is how `_wire_gate` ended up
# swallowing a consent-relay wiring failure in silence.
logger = logging.getLogger(__name__)

# A running thread must outlive a destroyed Houdini panel. These references
# disappear at thread completion; the thread has no QWidget parent.
_ACTIVE_PANEL_WORKERS = set()


def _session_permission_views():
    """UI observers survive ordinary panel reloads without owning permission."""
    import os
    import sys
    import types
    import weakref
    name = "_synapse_panel_session_permission_views_v1"
    state = sys.modules.get(name)
    if (not isinstance(state, types.ModuleType)
            or getattr(state, "owner_pid", None) != os.getpid()
            or not isinstance(getattr(state, "views", None), weakref.WeakSet)):
        state = types.ModuleType(name)
        state.owner_pid = os.getpid()
        state.views = weakref.WeakSet()
        sys.modules[name] = state
    return state.views


_SESSION_PERMISSION_VIEWS = _session_permission_views()


def _refresh_session_permission_views():
    """Keep open panels in sync without retaining a destroyed Qt widget."""
    for panel in tuple(_SESSION_PERMISSION_VIEWS):
        try:
            panel._refresh_session_permission()
        except Exception:
            # A stale or unavailable view cannot interrupt approval/revocation.
            _SESSION_PERMISSION_VIEWS.discard(panel)


def _revoke_model_connections(connections, *_):
    for connection in tuple(connections):
        connection.revoke()


def _release_panel_worker(worker):
    _ACTIVE_PANEL_WORKERS.discard(worker)
    worker.deleteLater()

# Proven runtime + widgets — composed, not rewritten. All optional so the panel
# always instantiates (graceful degradation is a runtime contract).
try:
    from synapse.panel.chat_display import ChatDisplay
except Exception:  # pragma: no cover
    ChatDisplay = None
try:
    from synapse.panel.gate_widget import GateWidget
except Exception:  # pragma: no cover
    GateWidget = None
try:
    from synapse.panel.claude_worker import ClaudeWorker
except Exception:  # pragma: no cover
    ClaudeWorker = None
try:
    from synapse.panel.tool_executor import ToolExecutor
except Exception:  # pragma: no cover
    ToolExecutor = None
try:
    from synapse.panel.tool_bridge import get_anthropic_tools
except Exception:  # pragma: no cover
    get_anthropic_tools = None
# FRZ attribution: times the main-thread result-path slots. Measurement only — it
# imposes no bound and changes no control flow. Degrades to a zero-cost no-op
# context manager so an import failure can never break the panel's result path.
try:
    from synapse.panel.result_telemetry import timed_phase as _timed_phase
except Exception:  # pragma: no cover
    from contextlib import nullcontext as _nullctx

    def _timed_phase(*_a, **_k):
        return _nullctx()
try:
    # H3b — off-UI-thread single-tool dispatch for the cancel/halt controls.
    from synapse.panel.direct_tool import (
        DirectToolCall, extract_node_path, is_cookish_tool,
    )
except Exception:  # pragma: no cover
    DirectToolCall = None
    extract_node_path = None
    is_cookish_tool = None
try:
    from synapse.panel.health_infographic import HealthInfographic
    from synapse.panel import agent_health
except Exception:  # pragma: no cover
    HealthInfographic = None
    agent_health = None
try:
    from synapse.panel.face_work import FaceWork
except Exception:  # pragma: no cover
    FaceWork = None
try:
    from synapse.panel.face_review import FaceReview
except Exception:  # pragma: no cover
    FaceReview = None

_VERSION = "9.1.0"  # v9 re-layout: 2 tabs (Review folded into Work), bundled type; 9.1: honest Stop + freeze-chain heartbeat (v5.12.0)

# Context-aware quick actions (prompt macros). Network-agnostic defaults; the
# context ribbon refines them per network type at runtime.
# The state sentence's vocabulary (bc-wave BC-2). Every string the rail's one
# sentence can show: the STATUS phrases (tokens.py) plus the two turn phrases.
# _build_rail floors the sentence at the widest of these in its own font, so
# it never elides - the wordmark's rule, no px literal.
_DONE_PHRASE = "Result ready"
_STOPPING_PHRASE = "Stopping\u2026"


def _state_phrases():
    return [row[2] for row in t.STATUS.values()] + [_DONE_PHRASE, _STOPPING_PHRASE]


def _houdini_build_label():
    """'Houdini 22.0.400' from the running host, else plain 'Houdini' - the
    corpus copy names the build it grounds in, never a hard-coded major."""
    try:
        import hou
        ver = hou.applicationVersionString()
        return "Houdini %s" % ver if ver else "Houdini"
    except Exception:
        return "Houdini"


_QUICK_ACTIONS = [
    ("Explain", "Explain what the selected nodes do and how they connect."),
    ("Fix", "Diagnose any problems with the current scene and propose fixes."),
    ("Optimize", "Suggest performance optimizations for the current network."),
]


class _ShortcutLayout(QtWidgets.QLayout):
    """Keep local links at their natural width, centered on every wrapped row."""

    def __init__(self, horizontal_gap, vertical_gap):
        super().__init__()
        self._items = []
        self._horizontal_gap = horizontal_gap
        self._vertical_gap = vertical_gap
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)
        self.invalidate()

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.invalidate()
            return item
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._arrange(QtCore.QRect(0, 0, width, 0), place=False)

    def minimumSize(self):
        size = QtCore.QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def sizeHint(self):
        sizes = [item.sizeHint() for item in self._items]
        return QtCore.QSize(
            sum(size.width() for size in sizes) + self._horizontal_gap * max(0, len(sizes) - 1),
            max((size.height() for size in sizes), default=0))

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._arrange(rect, place=True)

    def _arrange(self, rect, place):
        rows, row, row_width = [], [], 0
        for item in self._items:
            size = item.sizeHint()
            gap = self._horizontal_gap if row else 0
            if row and row_width + gap + size.width() > rect.width():
                rows.append((row, row_width))
                row, row_width, gap = [], 0, 0
            row.append((item, size))
            row_width += gap + size.width()
        if row:
            rows.append((row, row_width))
        heights = [max(size.height() for _, size in row) for row, _ in rows]
        height = sum(heights) + self._vertical_gap * max(0, len(rows) - 1)
        if place:
            y = rect.y() + max(0, (rect.height() - height) // 2)
            for (row, width), row_height in zip(rows, heights):
                x = rect.x() + max(0, (rect.width() - width) // 2)
                for item, size in row:
                    item.setGeometry(QtCore.QRect(
                        QtCore.QPoint(x, y + (row_height - size.height()) // 2), size))
                    x += size.width() + self._horizontal_gap
                y += row_height + self._vertical_gap
        return height


class _GrowingInput(QtWidgets.QTextEdit):
    """Auto-growing chat input. Enter sends; Shift+Enter newlines."""

    submitted = Signal()
    focus_lost = Signal()      # lets the face controller honor a deferred switch
    slash = Signal()           # "/" on an empty prompt → open the command palette
    height_committed = Signal(int)   # grip drag released → persist (L5-22)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsInput")
        self.setAcceptRichText(False)
        # The composer's one '/' telling (BC-4; G3 pins it here). bc-wave
        # repair (CRUX 2026-09-05): it has to read WHOLE at 340 - the text
        # width the viewport paints a placeholder in is ~182px, and the old
        # 'Ask SYNAPSE…    ·    / for commands' advanced 245 and wrapped
        # behind the send margin as 'Ask SYNAPSE…  ·  / for'. Pinned by
        # tests/panel/test_bc_wave.py::test_composer_telling_reads_whole_at_340.
        self.setPlaceholderText("Ask SYNAPSE… · / commands")
        # L5-22: no constant first-run height (the v9 132 landed the divider
        # above centre in every tall pane — Joe re-dragged it each session).
        # The height settles exactly once, via settle_height: the artist's
        # persisted drag, or centred from the pane's real size at show.
        # __init__ holds the floor because the pane's height is unknowable
        # here. Grip-drag + auto-grow behaviour unchanged.
        self._floor, self._max_h = 64, 600
        self._user_h = self._floor
        self._height_settled = False     # flips on settle_height / drag
        self._cap = None            # pane-imposed ceiling (CTO B4); never persisted
        self._send_widget = None    # the embedded Send (attach_send)
        self.setFixedHeight(self._user_h)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        content = int(self.document().size().height()) + 18
        h = max(self._user_h, min(self._max_h, content))
        if self._cap is not None:
            h = max(self._floor, min(h, self._cap))
        self.setFixedHeight(h)

    def cap_height(self, cap):
        """Pane-imposed ceiling (CTO B4 ruling 2026-09-05). The artist's
        ``_user_h`` is untouched and un-persisted - L6 still holds, the
        divider is never re-centred - but a composer taller than the pane
        it sits in clipped Send below the dock edge (G3 'input not clipped',
        red since 1ce31c99). ``None`` lifts the cap when the pane grows."""
        # Live-found 2026-09-05 (Joe's Houdini, chrome scale 2.25): a cap of
        # 114px left a 21px viewport under a 27px font and clipped the
        # placeholder. The cap's floor is one readable line above the Send
        # margin, whatever the scale - never the bare logical floor.
        if cap is not None:
            line_floor = (self.viewportMargins().bottom()
                          + self.fontMetrics().height() + 12)
            cap = max(self._floor, line_floor, int(cap))
        if cap != self._cap:
            self._cap = cap
            self._autosize()

    def settle_height(self, h):
        """One-shot first-run height (persisted restore or centred — the
        panel decides which, this widget just clamps). No-op once settled:
        after first run the divider moves only under the artist's hand,
        never on the panel's own (L6)."""
        if self._height_settled:
            return
        self._height_settled = True
        self._user_h = max(self._floor, min(self._max_h, int(h)))
        self._autosize()

    def set_user_height(self, h):
        """Set the artist's preferred input height (driven by the resize grip)."""
        self._height_settled = True      # the artist decided — never re-centre
        self._user_h = max(self._floor, min(self._max_h, int(h)))
        self._autosize()

    # -- embedded Send (v9 comp: bottom-right INSIDE the field) -------------
    def attach_send(self, btn):
        """Parent the Send button to the field itself (NOT the viewport, so it
        never scrolls) and reserve a bottom viewport margin so text never
        flows under it."""
        self._send_widget = btn
        btn.setParent(self)
        try:
            self.setViewportMargins(0, 0, 0, btn.sizeHint().height() + 12)
        except Exception:
            pass
        btn.show()
        self._place_send()

    def _place_send(self):
        btn = self._send_widget
        if btn is None:
            return
        bs = btn.sizeHint()
        btn.resize(bs)
        btn.move(self.width() - bs.width() - 10, self.height() - bs.height() - 10)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._place_send()

    def keyPressEvent(self, e):
        # "/" on an empty prompt opens the command palette (⌘K folded into the
        # input — no separate bar button). Ctrl+K still works as the shortcut.
        if e.text() == "/" and not self.toPlainText():
            self.slash.emit()
            return
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (e.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.focus_lost.emit()


class _InputResizeGrip(QtWidgets.QWidget):
    """A thin drag handle above the input — drag up/down to set its height."""

    def __init__(self, target, parent=None):
        super().__init__(parent)
        self._target = target
        self.setObjectName("DsGrip")
        self.setFixedHeight(10)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self._drag_y = None
        self._start_h = 0

    def _gy(self, event):
        try:
            return event.globalPosition().y()   # PySide6
        except Exception:
            return event.globalY()               # PySide2

    def mousePressEvent(self, event):
        self._drag_y = self._gy(event)
        self._start_h = self._target._user_h

    def mouseMoveEvent(self, event):
        if self._drag_y is not None:
            delta = self._drag_y - self._gy(event)   # drag up → taller
            self._target.set_user_height(self._start_h + delta)

    def mouseReleaseEvent(self, _event):
        if self._drag_y is not None and self._target._user_h != self._start_h:
            # L5-22: persist the artist's answer on release only — one
            # settings write per drag, never one per mouse-move.
            self._target.height_committed.emit(self._target._user_h)
        self._drag_y = None

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QtGui.QColor(t.BORDER_STRONG))
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        for dx in (-12, 0, 12):
            p.drawEllipse(QtCore.QRectF(cx + dx - 1.5, cy - 1.5, 3, 3))
        p.end()


def _image_icon(px=18, color=None):
    """A small photo/image glyph (frame · sun · mountain) for the attach button.

    A *drawn* icon, not an emoji: the bundled Space Mono has no pictographs, so
    a paperclip/📷 codepoint renders as a tofu box (unreadable). This matches the
    panel's QPainter drawing idiom and reads as 'add an image' at 18px."""
    color = color or t.TEXT_SECONDARY
    dpr = 2                                        # supersample → crisp when small
    pm = QtGui.QPixmap(px * dpr, px * dpr)
    pm.setDevicePixelRatio(dpr)
    pm.fill(QtGui.QColor(0, 0, 0, 0))              # transparent
    p = QtGui.QPainter(pm)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    col = QtGui.QColor(color)
    m = 1.6
    frame = QtCore.QRectF(m, m, px - 2 * m, px - 2 * m)
    pen = QtGui.QPen(col, 1.4)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(QtGui.QColor(0, 0, 0, 0))
    p.drawRoundedRect(frame, 2.4, 2.4)             # picture frame
    clip = QtGui.QPainterPath()                    # keep sun + mountain inside it
    clip.addRoundedRect(frame, 2.4, 2.4)
    p.setClipPath(clip)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(col)
    sr = px * 0.11                                 # sun
    p.drawEllipse(QtCore.QPointF(frame.left() + frame.width() * 0.33,
                                 frame.top() + frame.height() * 0.30), sr, sr)
    base = frame.bottom()                          # mountain rising from the base
    p.drawPolygon(QtGui.QPolygonF([
        QtCore.QPointF(frame.left(), base),
        QtCore.QPointF(frame.left() + frame.width() * 0.40, frame.center().y()),
        QtCore.QPointF(frame.left() + frame.width() * 0.60, frame.top() + frame.height() * 0.66),
        QtCore.QPointF(frame.right(), base),
    ]))
    p.end()
    return QtGui.QIcon(pm)


def _tools_icon(px=18):
    """Draw a clean lightning bolt without a symbol-font dependency."""
    icon = QtGui.QIcon()
    for mode, color in ((QtGui.QIcon.Normal, t.TEXT_PRIMARY),
                        (QtGui.QIcon.Active, t.TEXT_ACCENT),
                        (QtGui.QIcon.Disabled, t.TEXT_DISABLED)):
        pm = QtGui.QPixmap(px * 2, px * 2)
        pm.setDevicePixelRatio(2)
        pm.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QtGui.QColor(color))
        points = [QtCore.QPointF(px * x, px * y) for x, y in (
            (0.60, 0.05), (0.18, 0.56), (0.45, 0.56),
            (0.33, 0.95), (0.83, 0.39), (0.57, 0.39),
        )]
        painter.drawPolygon(QtGui.QPolygonF(points))
        painter.end()
        icon.addPixmap(pm, mode)
    return icon


class SynapsePanel(QtWidgets.QWidget):
    """The redesigned SYNAPSE panel."""

    # W2-S5: off-main context marshal-back. gather_context_off_main invokes its
    # on_ready callback on a daemon thread; emitting this signal there hands the
    # dict to _apply_context on the Qt/main thread (queued, AutoConnection), so
    # no hou read and no Qt widget touch ever happens off its owning thread.
    _context_ready = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(t.PANEL_MIN_WIDTH)
        # Load the bundled families BEFORE the stylesheet references them; a
        # missing family raises the build-mismatch flag (logged) and falls back.
        self._font_status = fontload.load_application_fonts()
        self._font_build_mismatch = self._font_status.get("build_mismatch", False)
        # R99 ORDERING: the injector must run BEFORE anything reads the gate.
        # scout selects h{major}_symbol_table.json from EXPECTED_HOUDINI_VERSION,
        # and the injector that sets it lives in SynapseDaemon.start(). The panel
        # constructs first, so without this the gate below reads the H21 table
        # against a running 22.0.368 and reports STALE - which is exactly what
        # the panel footer showed after the fix landed. The fix was correct and
        # wired too late; the panel's own status light diagnosed it.
        # Idempotent by design: it will not overwrite a value already set.
        try:
            from synapse.host.version_injector import inject_houdini_version
            inject_houdini_version()
        except Exception:
            pass  # no host / no scout -> gate reports unknowable, never blocks boot

        # M3-A: one-time check -- the symbol table cannot change mid-session
        self._gate_stale_reason = phantom_gate_status()
        # Track Houdini's default text size: derive the base scale from the live
        # host UI font so SYNAPSE body is AT LEAST the host body on any display/DPI
        # (>= host, never smaller — a 1.25x readability floor). Headless → token default.
        # CHROME vs CONTENT (first principles): chrome — the header, labels,
        # pills, buttons, palette — is recognised, not read, so it is FROZEN at
        # the host UI size and never moves when the artist changes reading size.
        # Content — the dialogue + the prompt — is read and written, so it (and
        # only it) is what the Aa button scales. Both start at the host UI size.
        self._chrome_scale = self._host_font_scale()
        self._font_scale = self._chrome_scale      # content scale (Aa-driven)
        self.setStyleSheet(qss.stylesheet(self._chrome_scale))  # rhythm-exempt: installs the sole designsystem sheet at the root; no local style

        # Session survival (R.2): restore this scene's prior conversation from
        # the process- and reopen-durable store so a reopen continues the SAME
        # session instead of a blank one (the g5 "no chat history" fail).
        # Best-effort; a missing/corrupt store degrades to an empty conversation.
        try:
            from synapse.server import session_store as _session_store
            self._messages, _sess_scope = _session_store.load_conversation_scoped()
            # W7-SESSCOPE: work from an earlier Houdini boot is parked, never
            # destroyed - a fresh boot starts clean, /restore-session undoes.
            self._parked_previous = (_sess_scope == "previous_parked")
            if self._parked_previous:
                QTimer.singleShot(0, self._announce_parked)
        except Exception:
            self._messages = []          # Anthropic-format conversation
            self._parked_previous = False
        self._stream_buf = []        # accumulates streamed tokens
        # P2: what the agent actually DID this turn, in order. The result
        # surface has always been able to render credit/flags/paths; before
        # this it had no producer, so five of its eight setters had ZERO
        # product callers (P1 census, 2026-07-27) and it rendered a result it
        # never populated. This is the missing half.
        self._turn_tools = []        # [(name, verb, detail), ...] per turn
        self._worker = None
        self._session_keys = {}       # panel lifetime only; never settings/history
        self.destroyed.connect(self._session_keys.clear)
        self._connection_facts = {}
        self._task_connection = None
        self._permission_connections = []
        # The container outlives the QObject without a callback into deleted Qt.
        self.destroyed.connect(partial(_revoke_model_connections, self._permission_connections))
        self._last_tool = None       # C8: name of the in-flight tool, for an honest Stop
        # H3b: the NODE the in-flight tool is working on. The tool-status detail
        # already carried it and was discarded during "running"; a cook-cancel
        # needs a target, and this is the only place the panel ever sees one.
        self._last_tool_node = None
        self._direct_call = None     # live DirectToolCall, kept off the GC
        self._tool_executor = ToolExecutor(parent=self) if ToolExecutor else None
        self._pending_context = []  # paths dropped in; prepended to the next send
        # (_font_scale was set above from the host font)

        # tab controller (v9 re-layout) — two tabs, NO auto-switch (the
        # same-pane law). Tabs move only on a user pill click; agent state
        # drives the Work face's internal cook/done sub-state and the rail
        # mark, never the visible tab.
        self._current_face = "direct"
        self._work_substate = "cook"
        self._was_busy = False
        self._provider_id = "claude"   # active chat engine (provider switch)
        self._boot_note = None         # surfaced in chat once the UI exists
        # Per-provider picked model (the model switcher) — each engine remembers
        # its own selection; defaults come from the registry.
        try:
            from synapse.panel.providers import registry as _reg
            self._model_by_provider = dict(_reg.PROVIDER_DEFAULT_MODEL)
        except Exception:
            _reg = None
            self._model_by_provider = {}
        # Persisted picks (<repo>/.synapse/panel_settings.json) — a corrupt or
        # missing file yields defaults, never blocks boot. A stale engine id is
        # SURFACED (never a silent Claude switch).
        try:
            from synapse.panel import settings as _pset
            st = _pset.load_settings()
            pid = st.get("provider_id") or "claude"
            known = set(_reg.PROVIDER_IDS) if _reg is not None else {"claude"}
            if pid in known:
                self._provider_id = pid
            elif pid != "claude":
                self._provider_id = pid
                self._boot_note = (
                    "Saved engine %r is unavailable. Choose Connect models." % pid)
            self._model_by_provider = _pset.merged_model_picks(
                st, self._model_by_provider)
            # L5-4: restore the saved profile tab — _build_ui composes this
            # profile's manifest; the mode bar marks its pill active.
            self._profile_state = _pset.SwitcherState()
            self._layout_profile = self._profile_state.profile
        except Exception:
            pass

        # L5-4: build-once cache for the region builders. A live recompose
        # (profile tab switch) re-sequences these same widgets rather than
        # rebuilding them, so chat history and an in-flight turn survive.
        self._region_cache = {}
        self._recompose_hidden = set()
        self.setAcceptDrops(True)
        self._build_ui()
        if self._boot_note:
            try:
                self._chat.append_system_message(self._boot_note)
            except Exception:
                pass
        self._wire_gate()
        self._notification_controller = None
        self._notifications_dialog = None
        try:
            from synapse.panel.notifications import NotificationController
            self._notification_controller = NotificationController(self)
            self._notification_controller.changed.connect(self._refresh_events)
            self._refresh_events(self._notification_controller.journal.snapshot())
        except Exception:
            logger.warning("Local Events could not be started", exc_info=True)
            self._events_btn.setEnabled(False)
            self._events_btn.setToolTip("Local Events could not be started in this host.")
        self._palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._palette_shortcut.activated.connect(self._open_palette)
        # platform-correct ⌘K / Ctrl+K rail hint, derived from the ACTUAL bound
        # key sequence so it can never lie about the binding.
        try:
            self._palette_hint.setText(
                self._palette_shortcut.key().toString(QKeySequence.NativeText) or "Ctrl+K")
        except Exception:
            pass
        # Live context ribbon + connection. W2-S5: the three hou reads run OFF
        # the Qt/main thread via gather_context_off_main; _context_ready marshals
        # the result back to _apply_context here. Cadence (2s) is unchanged.
        self._context_ready.connect(self._apply_context)
        self._ctx_timer = QTimer(self)
        self._ctx_timer.setInterval(2000)
        self._ctx_timer.timeout.connect(self._update_context)
        self._ctx_timer.start()
        self._update_context()
        # Recursive-observability surface (RSI Line O): a slower poll that
        # records + persists the advisor's recommendations and runs the
        # meta-recursion analyzer, then paints the infographic.
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(4000)
        self._health_timer.timeout.connect(self._update_health)
        self._health_timer.start()
        self._update_health()
        # Selection-change callback (V0-guarded) → instant context updates; the
        # 2s timer above remains the proven fallback.
        self._register_selection_cb()
        # Freeze-safety forensic trail: keep the telemetry flush running so a
        # sustained-freeze dump is durable even when no server was started.
        # Idempotent; guarded so a packaging gap can never break construction.
        try:
            from synapse.core.logfile import ensure_file_logging
            from synapse.server.telemetry_dump import start_periodic_flush
            ensure_file_logging()
            start_periodic_flush()
        except ImportError:
            pass
        # R.2 — the 1s main-thread freeze beat is now owned by a PROCESS-
        # LIFETIME source (server/runtime_beat.py), NOT this widget. Its
        # parentless QTimer survives panel close, so closing the panel no longer
        # kills the runtime heartbeat and the Watchdog never false-freezes a
        # healthy runtime the artist merely closed (the g5 lifecycle fail).
        # ensure_beat_started is idempotent: reopen re-marks attachment without
        # arming a second timer. Best-effort — a packaging gap must never break
        # panel construction.
        try:
            from synapse.server.runtime_beat import ensure_beat_started
            ensure_beat_started()
        except Exception:
            pass

    # ---------------------------------------------------------------- UI
    def _section(self):
        """An opaque section container. Opaque surfaces are what stop Houdini's
        compositor from ghosting (the old global transparent rule was the bug)."""
        w = QtWidgets.QWidget()
        w.setObjectName("DsSection")
        w.setProperty("rhythm_role", "group")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return w

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        # band: the regions are chrome bands that own their own hairlines
        # (the #DsHeader rule), so the root stack pays no gap and no inset
        # (RULING-3; the B4 composer cap holds).
        self.setProperty("rhythm_role", "band")

        # Persistent rail (Mile 1) → context ribbon → switcher → the two faces.
        # v9: the ENGINE pill bar left the chrome — the rail author token is the
        # engine+model click target now (its menu machinery is reused). The
        # rail's bottom rule is the #DsHeader HAIR border (no divider widget).
        #
        # L5-2: the sequence is manifest-driven — the profile manifest names
        # the regions in order and the compositor maps each onto the same
        # _build_* calls below. "expert" is the v5.42.0 wiring exactly; an
        # invalid manifest falls back to that wiring hard-coded (the panel
        # always builds).
        #
        # J4 (Joe's five, 2026-09-05): the profile switch left the UI. The
        # persisted pick stays on disk for the day the profiles return with a
        # real difference; the composed panel is expert. __init__'s
        # SwitcherState read stands as is - this line overrides it, and
        # nothing an artist can reach composes any other manifest.
        profile = DEFAULT_PROFILE
        self._layout_profile = DEFAULT_PROFILE
        built = False
        if compose is not None:
            try:
                compose(self, root, get_manifest(profile))
                built = True
                self._regate_stop()
            except ManifestError:
                logger.exception(
                    "layout manifest %r invalid — using the v5.42.0 wiring",
                    profile,
                )
        if not built:
            root.addWidget(self._build_rail())          # identity + state
            root.addWidget(self._build_context_ribbon())   # context + CHAT / TOKEN
            root.addWidget(self._build_faces(), 1)      # dominant — the stacked faces
        self._set_face("direct")                    # rest on the CHAT surface

    # ------------------------------------------------- profile switcher (L5-4)
    # J4 (Joe's five, 2026-09-05): the profile choice has no artist-reachable
    # surface - no tab strip (BC-5 folded it), no overflow submenu (J4 retired
    # it). _select_profile / _mark_profile_pill / _recompose stay as machinery
    # (tests/test_rope_switcher_wires_profile.py drives them) so the profiles
    # can return the day they carry a real difference.
    def _select_profile(self, profile):
        """Select a profile: persist through settings, then recompose LIVE.

        ``SwitcherState`` (Qt-free, tested headless) owns selection → settings
        write → restore; this method owns the Qt half. A failed save still
        switches the session — and says so in chat, never silently. No
        artist-reachable control calls this since J4.
        """
        if profile == getattr(self, "_layout_profile", DEFAULT_PROFILE):
            return
        state = getattr(self, "_profile_state", None)
        if state is not None:
            state.select(profile)
            if not state.persist_ok:
                try:
                    self._chat.append_system_message(
                        "Profile switched to %s for this session — the pick "
                        "could not be saved." % profile)
                except Exception:
                    pass
        self._layout_profile = profile
        self._mark_profile_pill(profile)
        self._recompose(profile)

    def _mark_profile_pill(self, profile):
        """Check the selected profile control, if any. The composed panel
        builds none since J4 (``_profile_pills`` is never set, so this is a
        no-op); the name and the getattr default are kept for the switcher
        test, whose stub defines its own ``_profile_pills``."""
        for pid, act in getattr(self, "_profile_pills", {}).items():
            try:
                act.setChecked(pid == profile)
            except Exception:
                pass

    def _recompose(self, profile):
        """Re-run the compositor for ``profile`` on the LIVE panel.

        Recompose, never reconstruct: the root layout is stripped WITHOUT
        deleting anything — the region widgets stay children of the panel
        (same parent, so no reparent, no hide, no state loss) and the region
        builders are build-once (``_region_cache``), so ``compose()``
        re-sequences the SAME widgets. Chat history, an in-flight worker
        turn, and every face's state ride across untouched. A region the new
        manifest drops is hidden, never destroyed; any compose failure
        restores the previous sequence.
        """
        if compose is None or get_manifest is None:
            return      # import-guard wiring — nothing manifest-driven here
        root = self.layout()
        if root is None:
            return
        try:
            manifest = get_manifest(profile)
        except Exception:
            logger.exception(
                "layout manifest %r unavailable — keeping the current layout",
                profile)
            return
        # Widgets a prior recompose hid get their pre-hide state back FIRST,
        # so the compositor's own visibility attrs win for managed regions
        # (they apply after this show).
        for wdg in getattr(self, "_recompose_hidden", ()):
            try:
                wdg.show()
            except RuntimeError:  # pragma: no cover - C++ side already gone
                pass
        prev = []               # (item, widget, stretch) — the restore point
        while root.count():
            stretch = root.stretch(0)
            item = root.takeAt(0)
            prev.append((item, item.widget(), stretch))
        try:
            compose(self, root, manifest)
        except Exception:
            logger.exception(
                "recompose to %r failed — restoring the previous layout",
                profile)
            while root.count():     # drop whatever the partial pass added
                root.takeAt(0)
            for item, _wdg, _stretch in prev:
                root.addItem(item)
            for i, (_item, _wdg, stretch) in enumerate(prev):
                root.setStretch(i, stretch)
            for wdg in getattr(self, "_recompose_hidden", ()):
                try:
                    wdg.hide()
                except RuntimeError:  # pragma: no cover
                    pass
            return
        # QTextDocument spans are outside the QWidget role walker. Reapply
        # their group gaps after the same cached-widget recomposition.
        chat = getattr(self, "_chat", None)
        if chat is not None and hasattr(chat, "_apply_turn_rhythm"):
            chat._apply_turn_rhythm()
        # Stop is state-gated to working only; the compositor just applied the
        # manifest's visible=True to it. Re-assert the runtime gate inline
        # (the same rule as _regate_stop; written with getattr because this
        # method is also executed against duck-typed panels by the rope and
        # rhythm tests).
        busy = bool(getattr(self, "_was_busy", False))
        stop = getattr(self, "_stop_btn", None)
        if stop is not None:
            stop.setVisible(busy)
        connect = getattr(self, "_connect_btn", None)   # bc-wave BC-2: one slot
        if connect is not None:
            connect.setVisible(not busy)
        managed = {root.itemAt(i).widget() for i in range(root.count())}
        hidden = set()
        for _item, wdg, _stretch in prev:
            if wdg is not None and wdg not in managed:
                wdg.hide()  # dropped by the new manifest — hidden, not deleted
                hidden.add(wdg)
        self._recompose_hidden = hidden

    def _regate_stop(self):
        """Re-assert the Stop state gate after a compose.

        Stop is state-gated to working only (``_set_busy``). The manifests list
        it as PRESENT in the rail and the compositor applies ``visible=True`` to
        every listed widget, which un-hid the disabled Stop at rest after every
        compose - pinned red by tests/test_panel_faces.py::
        test_stop_gated_to_working_state, and the 64px that pushed the header
        row past the docking bound (landing r3, RULING-2B). Presence in a
        profile and runtime state are two different things.
        """
        busy = bool(getattr(self, "_was_busy", False))
        stop = getattr(self, "_stop_btn", None)
        if stop is not None:
            stop.setVisible(busy)
        # bc-wave BC-2: Connect and Stop share one slot on the state row -
        # Connect at rest, Stop while working - so the compositor's
        # visible=True on both must be re-gated together.
        connect = getattr(self, "_connect_btn", None)
        if connect is not None:
            connect.setVisible(not busy)

    def _build_rail(self):
        """The persistent rail (bc-wave BC-2): one truth, two identities.

        Row 1 is IDENTITY - the mark + wordmark (who is speaking) left, the
        model token (who is thinking) right. Joe's Addendum 2, 2026-09-05:
        the active provider/model is the one fact the artist must never
        lose, so the token never elides and never folds into the overflow.
        Row 2 is STATE - one sentence of what the panel is doing (the STATUS
        phrases, given the wordmark's never-elide floor) left; Connect / Stop
        and the overflow right. Nothing else is on the rail.

        Why two rows: at PANEL_PREF_WIDTH the interior is 280 (340 - 2 x
        GUTTER). A never-eliding sentence (~83-90) and a never-eliding
        17-character model id (~112) beside the mark, the wordmark, Connect
        and the overflow need ~330+ on one row; both rows here fit inside 280
        in every density, so nothing on the rail gives way and no child
        carries an Ignored policy any more (F2).

        The chrome that used to ride here - token meter, palette hint,
        connection dot / label, Corpus, Help, the health strip - is read
        through the overflow (_build_overflow_menu). Its data owners are
        still constructed for their writers (_refresh_usage via token_readout,
        the shortcut hint,
        _refresh_corpus_state) and for G3's chrome-floor walk, but they sit
        in no layout and are hidden.
        """
        cached = self._region_cache.get("_build_rail")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        w = self._section()
        w.setObjectName("DsHeader")          # flat PANEL + 1px HAIR bottom rule
        col = QtWidgets.QVBoxLayout(w)

        # -- row 1 - identity: [mark][SYNAPSE] ... [model token] -------------
        # A `stack` owner (gap 4/6/3, RULING-4a) inside the `shell` rail.
        ident = self._section()
        ident.setProperty("rhythm_role", "stack")
        top = QtWidgets.QHBoxLayout(ident)
        # Boot truth is one string: not connected (headless / bridge down).
        # MarkDot accepts 'disconnected' as a resting state (components._RESTING).
        self._mark = c.MarkDot("disconnected", diameter=16)
        # brand word - 14px/TEXT_BRIGHT (comp .word); tracking lives on the
        # QFont (Qt QSS has no letter-spacing), colour in the sheet.
        #
        # The v9 rule was weight 400: "hierarchy comes from the ~4px BRAND
        # tracking and the position, NEVER from weight." Checked against the
        # reference it cites (pentagram.com/work/cohere, read 2026-07-27) and
        # the reference does not support "never":
        #
        #     "Cohere Text has three weights (BOLD, reg, light) plus italics."
        #
        # Bold is one of three shipped weights, and the wordmark itself is
        # "carefully crafted using the Cohere typeface" - a designed lockup, not
        # tracked-out body text. So weight was never off the table; the rule was
        # an interpretation that hardened into a prohibition.
        #
        # Joe's call, 2026-07-27: the mark read thin and needed to sit as a
        # SOLID element at the same size. Weight alone would not do it - at 14px
        # bold with 4px tracking reads HEAVY AND SPARSE, individually bold
        # letters visually apart. Solidity is weight PLUS density:
        #   weight   400 -> 700  (a weight the reference ships)
        #   tracking BRAND 0.286em -> WORDMARK 0.16em  (~2.2px at 14px)
        #   colour   TEXT_PRIMARY -> TEXT_BRIGHT
        # Size held at 14px until Joe's addendum (2026-09-05, the review
        # canvas): "1pt larger and 5px farther to the right of the orange
        # circle" - 15px, and t.WORDMARK_GAP beyond the row's stack gap.
        # Position still carries hierarchy; weight now carries presence.
        word = c.label("SYNAPSE", role="body")
        word.setProperty("role", "title")
        word.setFont(fontload.tracked_font("WORDMARK", 15, scale=self._chrome_scale,
                                           weight=600))
        # The brand never elides (landing r3 repair): a hard minimum is the
        # one floor Qt's engine cannot cross. Chrome is FROZEN on Aa, so the
        # hint is set once here. The same rule now guards the model token
        # and the state sentence below - the three things on the rail that
        # must be read whole.
        word.setMinimumWidth(word.sizeHint().width())
        self._wordmark = word
        # model token - THE engine+model click target (v9): a flat button whose
        # text is _author_token(); click opens the engine menu. Discoverability =
        # pointing-hand + hover underline + tooltip (comp shows no arrow).
        # Addendum 2: Space Mono at DATA tracking (the data voice), at the
        # type floor, never elided (_refresh_engine_selector re-floors it on
        # every model switch), top right in every profile and density.
        self._author_lbl = QtWidgets.QPushButton()
        self._author_lbl.setObjectName("DsAuthor")
        self._author_lbl.setFlat(True)
        self._author_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._author_lbl.setToolTip("Engine & model - click to switch")
        self._author_lbl.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        self._author_lbl.clicked.connect(self._open_author_menu)
        self._refresh_engine_selector()      # text + never-elide floor
        top.addWidget(self._mark)
        top.addSpacing(t.WORDMARK_GAP)       # the lockup: mark ·stack gap + 5· SYNAPSE
        top.addWidget(word)
        top.addStretch(1)
        top.addWidget(self._author_lbl)
        col.addWidget(ident)

        # -- row 2 - state + action: [sentence] ... [Connect | Stop][overflow] --
        row = self._section()
        row.setProperty("rhythm_role", "stack")
        bot = QtWidgets.QHBoxLayout(row)
        # The ONE state sentence (F2). Its text is always a STATUS phrase, or
        # the two turn phrases (_DONE_PHRASE / _STOPPING_PHRASE); its floor is
        # the widest of them measured in its own font - the wordmark's rule
        # applied to the sentence, no px literal. Never Ignored, never elided.
        self._header_status = c.label(t.STATUS["disconnected"][2], role="caption",
                                      scale=self._chrome_scale)
        self._header_status.setProperty("role", "label")
        self._header_status.setSizePolicy(QtWidgets.QSizePolicy.Preferred,
                                          QtWidgets.QSizePolicy.Preferred)
        fm = self._header_status.fontMetrics()
        self._header_status.setMinimumWidth(
            max(fm.horizontalAdvance(phrase) for phrase in _state_phrases()))
        overflow = c.Button(variant="ghost")
        tools_icon_px = max(18, t.scaled(18, self._chrome_scale))
        overflow.setIcon(_tools_icon(tools_icon_px))
        overflow.setIconSize(QtCore.QSize(tools_icon_px, tools_icon_px))
        overflow.setAccessibleName("Tools and settings")
        overflow.setToolTip(
            "Tools and settings — commands, saved suggestions, engine, health and help")
        overflow.clicked.connect(self._show_overflow)
        self._stop_btn = c.Button("Stop", variant="danger")
        # L5-20: the mark (MarkDot.set_halt_handler) and this button are two
        # surfaces of ONE Stop -- #DsStop paints it in the mark's warm note,
        # not the danger outline, so the pair reads as a single control.
        self._stop_btn.setObjectName("DsStop")
        self._stop_btn.setMinimumWidth(t.SPACE_48)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setVisible(False)   # state-gated: shown only while working
        # Force-connect the bridge server (the hwebserver serving /synapse for
        # external MCP clients + the /mcp endpoint the tool executor uses). The
        # panel's chat runs in-process, but tools + external tools need this up,
        # and it does NOT auto-start - this button is the one-click way to force
        # it without dropping into Houdini's Python Shell. Connect and Stop
        # share one slot: Connect at rest, Stop while working (_set_busy).
        self._connect_btn = c.Button("Connect", variant="primary")
        self._connect_btn.setToolTip(
            "Start the Synapse bridge server (port 9999) so external / MCP tools "
            "can reach Houdini. Safe to click anytime - idempotent."
        )
        self._connect_btn.clicked.connect(self._on_connect)
        self._doctor_btn = c.Button("Doctor", variant="ghost")
        self._doctor_btn.setProperty("tone", "doctor")
        self._doctor_btn.setAccessibleName("Check SYNAPSE")
        self._doctor_btn.setToolTip("Run synapse_doctor locally · no model request or scene changes")
        self._doctor_btn.clicked.connect(self._open_doctor)
        bot.addWidget(self._header_status)
        bot.addStretch(1)
        bot.addWidget(self._connect_btn)
        bot.addWidget(self._stop_btn)     # termination never scrolls away
        bot.addSpacing(t.scaled(t.SPACE_12, self._chrome_scale))
        bot.addWidget(self._doctor_btn)
        bot.addWidget(overflow)
        col.addWidget(row)

        # -- hidden owners: constructed, written to, read by the overflow;
        #    in NO layout, never shown. ----------------------------------
        # token meter - TOKENS ONLY, never $ (metering-deferred D4). It stays
        # EMPTY until a provider reports real usage (J2: every registered
        # provider now does, through usage_sink) - never estimated;
        # token_readout.refresh_surfaces is the one display rule.
        self._meter_lbl = c.label("", role="caption", parent=w)
        self._meter_lbl.setObjectName("DsMeter")
        self._meter_lbl.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        self._session_tokens = 0
        # palette affordance - the palette is already bound (QShortcut); its
        # text is set from the ACTUAL bound QKeySequence after the shortcut is
        # created (platform-correct, never lies about the key) and the
        # overflow's 'Palette' action reads it.
        self._palette_hint = c.label("", role="caption", parent=w)
        self._palette_hint.setObjectName("DsKHint")
        self._palette_hint.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        # connection dot / label - the connection truth now reads through the
        # state sentence (_render_state); these mirror it for the overflow.
        self._foot_dot = c.StatusDot("disconnected", parent=w)
        self._foot_label = c.label(t.STATUS["disconnected"][2], role="caption",
                                   scale=self._chrome_scale, parent=w)
        self._foot_label.setProperty("role", "caption")
        # Houdini-help convention: the doc is a control, not a path to go
        # find. Reached as the overflow's 'Help'.
        self._help_btn = c.Button("?", variant="ghost", parent=w)
        self._help_btn.setAccessibleName("Open documentation")
        self._help_btn.setToolTip("Open docs/studio/UPGRADE.md")
        self._help_btn.clicked.connect(self._on_help)
        # Activate the documentation corpus so Solaris assembly grounds in the
        # running build's real docs (verified node types / parm names) instead
        # of phantom APIs. Reached as the overflow's 'Ground the corpus'.
        self._corpus_btn = c.Button("Corpus", variant="primary", parent=w)
        self._corpus_btn.setToolTip(
            "Connect the %s documentation corpus so Solaris assembly grounds "
            "in real docs (not phantom parms). Safe to click anytime - "
            "idempotent." % _houdini_build_label()
        )
        self._corpus_btn.clicked.connect(self._on_corpus)
        for owner in (self._meter_lbl, self._palette_hint, self._foot_dot,
                      self._foot_label, self._help_btn, self._corpus_btn):
            owner.setVisible(False)

        # shell: the rail is an edge container - GUTTER inset, SPACE_SM air.
        w.setProperty("rhythm_role", "shell")
        # J5 (Joe, 2026-09-05): the rail meets the pane's top edge, so it takes
        # the shell role's top-edge air (rhythm._EDGE_TOP: SPACE_MD, scaled
        # by density) - the value lives in the role table, not here.
        w.setProperty("rhythm_edge", "top")
        # One type applier per widget (RULING-4c): the header controls are
        # verbs and take the LABEL tracked font (mono) - the same applier as
        # _verb and the CHAT / TOKEN pills - so the chrome siblings match
        # byte-for-byte; no rhythm_role="label" on top of it.
        for control in (self._doctor_btn, self._connect_btn, self._corpus_btn, self._help_btn, overflow):
            control.setObjectName("DsVerb")
            control.setFont(fontload.tracked_font(
                "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        # Match the host's chrome scale so the bolt and its click target
        # stay readable alongside Houdini's enlarged text.
        overflow.setFixedWidth(max(t.SPACE_32, t.scaled(t.SPACE_32, self._chrome_scale)))
        self._overflow_btn = overflow
        self._regate_stop()
        self._region_cache["_build_rail"] = w
        return w

    def _on_connect(self):
        """Force-start the Synapse bridge server — the hwebserver that serves the
        /synapse WS for external MCP clients and the /mcp endpoint the panel's
        tool executor talks to. Idempotent (a no-op if already running), runs the
        native server in the background (non-blocking), and reports the outcome in
        the chat. Degrades gracefully outside Houdini (no hwebserver)."""
        try:
            from synapse.server.hwebserver_adapter import start_hwebserver, get_health
        except Exception as exc:
            self._announce_bridge("Bridge unavailable — it needs to run inside "
                                  "Houdini (%s)." % exc)
            return
        try:
            start_hwebserver(port=9999)
            health = get_health()
            if health.get("running"):
                self._announce_bridge("Bridge running on :%s — external / MCP tools "
                                      "can now reach Houdini." % health.get("port", 9999))
            else:
                self._announce_bridge("Bridge did not report running — check the "
                                      "Houdini console for details.")
        except Exception as exc:
            self._announce_bridge("Couldn't start the bridge: %s" % exc)
        self._refresh_bridge_state()

    def _announce_bridge(self, msg):
        """Surface a bridge status line in the chat; never raise."""
        try:
            self._chat.append_system_message(msg)
        except Exception:
            pass

    def _refresh_bridge_state(self):
        """Reflect the live bridge state on the Connect button — once the server
        is up the button reads 'Bridge ✓' (still clickable to re-confirm). Best
        effort: any failure leaves the default 'Connect'."""
        running = False
        try:
            from synapse.server.hwebserver_adapter import is_running
            running = bool(is_running())
        except Exception:
            running = False
        btn = getattr(self, "_connect_btn", None)
        if btn is not None:
            btn.setText("Bridge ✓" if running else "Connect")
            btn.setToolTip(
                "Synapse bridge is running on :9999. Click to re-confirm."
                if running else
                "Start the Synapse bridge server (port 9999) so external / MCP "
                "tools can reach Houdini. Safe to click anytime — idempotent."
            )

    def _on_corpus(self):
        """Activate the H21 documentation corpus so Solaris assembly grounds in
        real docs (verified node types / parm names), not phantom APIs. Builds
        the canonical repo rag/ corpus if absent and points scout at it (the same
        sequence the MCP server runs at init). Idempotent; reports in chat;
        degrades gracefully headless."""
        try:
            from synapse.cognitive.tools import scout_ingest
        except Exception as exc:
            self._announce_bridge("Corpus unavailable — %s." % exc)
            return
        try:
            info = scout_ingest.activate()
            hits = []
            try:
                from synapse.cognitive.tools.scout import synapse_scout
                hits = synapse_scout("karmarendersettings xpu engine", k=3).get("hits", [])
            except Exception:
                pass   # the probe is a confidence check, not a gate
            n = info.get("entries", -1)
            cnt = "%d entries" % n if isinstance(n, int) and n >= 0 else "cached"
            if hits:
                self._announce_bridge(
                    "Corpus active (%s, probe hit %d docs incl. %s) — Solaris "
                    "builds will ground in real %s docs."
                    % (cnt, len(hits), hits[0].get("source", "?"),
                       _houdini_build_label()))
            else:
                self._announce_bridge(
                    "Corpus loaded (%s) but a known probe returned no hits — the "
                    "rag/ tree may be incomplete." % cnt)
        except Exception as exc:
            self._announce_bridge("Couldn't load the corpus: %s" % exc)
        self._refresh_corpus_state()

    def _refresh_corpus_state(self):
        """Reflect live corpus state on the Corpus button — 'Corpus ✓' once the
        store's entries.jsonl is built. Best effort."""
        loaded = False
        try:
            from synapse.cognitive.tools import scout as _scout
            root = _scout.RAG_ROOT                  # a pathlib.Path
            if root is not None:
                fp = root / "corpus" / "entries.jsonl"
                loaded = fp.is_file() and fp.stat().st_size > 0
        except Exception:
            loaded = False
        btn = getattr(self, "_corpus_btn", None)
        if btn is not None:
            btn.setText("Corpus ✓" if loaded else "Corpus")

    def _refresh_engine_selector(self):
        """Repaint the engine/model selection readout — v9: the rail author
        token IS the selector (the ENGINE pill bar left the chrome; this keeps
        its name for the 4 call sites). A MODEL switch (not just a provider
        switch) must update it. Idempotent; safe before the rail is built.

        joe-five J1: this is also where the engine's KEYED truth is decided —
        the provider builds and its own ``resolve_key()`` returns a value
        (ollama's ``'not-needed'`` counts; an unconfigured Custom engine is
        ``None``). Env / .env reads only, never a network probe. Runs at rail
        build and on every provider / model switch, then re-renders the
        token's liveness colour (``_render_token_state``)."""
        lbl = getattr(self, "_author_lbl", None)
        if lbl is not None:
            try:
                lbl.setText(self._author_token())
                # Addendum 2: the token never elides. Re-floor on every model
                # switch (the text changed; chrome type is frozen on Aa).
                lbl.setMinimumWidth(lbl.sizeHint().width())
            except Exception:
                pass
        try:
            connection = self._prepare_connection()
            self._engine_keyed = bool(connection.provider.resolve_key())
            task = getattr(self, "_task_connection", None)
            shown = task or connection
            self._refresh_session_permission(shown)
            detail = shown.facts.description
            if task:
                detail = "Current task\n" + detail + "\n\nNext task: " + connection.spec.identity
            self._model_connection_detail = detail
            if lbl is not None:
                lbl.setToolTip(detail)
            status = getattr(self, "_connection_status", None)
            if status is not None:
                status.setText(shown.facts.location + " · Connect models")
                status.setToolTip(detail)
            face = getattr(self, "_token_face", None)
            if face is not None and hasattr(face, "set_connection"):
                face.set_connection(getattr(self, "_last_task_facts", None) or shown.facts)
            connection.release()
        except Exception:
            self._engine_keyed = False
            permission_button = getattr(self, "_session_permission_btn", None)
            if permission_button is not None:
                permission_button.hide()
            task = getattr(self, "_task_connection", None)
            if task is not None:
                self._model_connection_detail = "Current task\n" + task.facts.description + "\nNext selection is unavailable."
            else:
                self._model_connection_detail = "Selected: %s/%s\nLocation unverified. Open Connect models to check it." % (
                    getattr(self, "_provider_id", "unknown"), self._active_model())
            status = getattr(self, "_connection_status", None)
            if status is not None:
                status.setText((task.facts.location if task else "Unverified") + " · Connect models")
                status.setToolTip(self._model_connection_detail)
        self._render_token_state()      # getattr-guarded: no-op before the rail

    def _build_context_ribbon(self):
        cached = self._region_cache.get("_build_context_ribbon")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        w = self._section()
        w.setProperty("rhythm_role", "shell")   # edge container: GUTTER inset
        lay = QtWidgets.QHBoxLayout(w)
        # The shell role owns the ribbon's spacing. The context label is UI
        # label text (TYPE_ROLES['label'], sans, BP4) - not a section eyebrow,
        # so it carries no rhythm_role="label" (RULING-4c/4d).
        # BC-4: boot text is '' - absence, not 'no scene context'. The rail
        # sentence is the one idle telling; _apply_context fills this when a
        # context arrives (F14).
        self._ctx_label = c.label("", role="label", scale=self._chrome_scale)
        self._ctx_label.setObjectName("DsContextLabel")
        self._ctx_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(self._ctx_label, 1)
        # bc-wave BC-5: the ribbon is [context label, stretch][CHAT][TOKEN] -
        # the two face pills ride the ribbon's right edge at the shell gap;
        # the profile row they shared (DsTabRow) is gone, and J4 retired the
        # profile choice from the UI altogether. v9.1 (Option A): there is one
        # surface, CHAT, and consent/review auto-surfaces when actionable;
        # clicking CHAT is the manual way back. The internal face keys stay
        # "direct"/"work" - the invariants key on those, not the label.
        self._face_pills = {}
        pill = c.Pill("CHAT")
        pill.setFont(fontload.tracked_font(
            "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        pill.clicked.connect(lambda _=False: self._set_face("direct"))
        self._face_pills["direct"] = pill      # the idle default marks it active
        lay.addWidget(pill)
        # TOKEN - the economist read-out (R167). v9.1 removed DIRECT / WORK
        # because actionable state should AUTO-SURFACE rather than wait for
        # a click; token economics is DIAGNOSTIC, and a thing you go looking
        # for is what a tab is for.
        tok = c.Pill("TOKEN")
        tok.setFont(fontload.tracked_font(
            "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        tok.clicked.connect(lambda _=False: self._show_token_face())
        self._face_pills["token"] = tok
        lay.addWidget(tok)
        self._region_cache["_build_context_ribbon"] = w
        return w

    def _build_converse(self):
        if ChatDisplay is not None:
            self._chat = ChatDisplay()
        else:  # graceful fallback
            self._chat = QtWidgets.QTextBrowser()
        if hasattr(self._chat, "node_clicked"):
            self._chat.node_clicked.connect(self._on_node_clicked)
        # Apply the host-matched scale BEFORE the greeting renders, so even the
        # first line is at Houdini's body size.
        try:
            self._chat.font_scale = self._font_scale
        except Exception:
            pass
        try:
            self._chat.append_system_message(
                "Ready. What are we building?"
            )
        except Exception:
            pass
        # The chat is the dominant surface via stretch (it expands to fill), so
        # its MINIMUM is kept low — a high min here was what summed past the pane
        # height and clipped the input/Send row at short pane sizes. v9: lower
        # still (the 132px comp composer + khint reclaim the floor's budget).
        self._chat.setMinimumHeight(24)
        self._converse_stack = QtWidgets.QStackedWidget()
        self._converse_stack.addWidget(self._chat)              # page 0: chat
        self._converse_stack.addWidget(self._build_hda_form())  # page 1: Build HDA
        # Vertical IGNORED: the stack lives off its stretch factor, not its
        # pages' size hints — otherwise the chat/HDA-form hints manufacture a
        # layout deficit that compresses the 132px composer even in tall panes.
        self._converse_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Ignored
        )
        self._converse_stack.setMinimumHeight(24)
        return self._converse_stack

    # the two tabs, in switcher order (v9: Review folded into Work's done state)
    _FACE_INDEX = {"direct": 0, "work": 1, "token": 2}

    def _show_token_face(self):
        """Bring TOKEN forward and refresh it from the probe layer.

        Refreshed on OPEN rather than on a timer: V3 was explicit that a probe
        must never be the thing that trips the rate limit it reports on, and a
        face nobody is looking at has no reason to poll."""
        try:
            face = getattr(self, "_token_face", None)
            if face is not None and hasattr(face, "refresh_from_probe"):
                face.refresh_from_probe()
        except Exception:
            pass
        self._set_face("token")

    def _build_token_face(self):
        """The TOKEN face — the economist read-out (R167).

        v9.1 removed the DIRECT · WORK tab row because actionable state should
        AUTO-SURFACE rather than wait for a click. That rationale does not reach
        this face: WORK surfaces itself because it is actionable, and token
        economics is DIAGNOSTIC — the thing an artist goes looking for. Which is
        exactly what a tab is for.

        Nothing critical lives only here. Rate-limited, stale probe and model
        swap belong on the rail; this face only explains them.

        Never raises: if the face cannot be built the stack gets a placeholder
        and every other surface is unaffected.
        """
        try:
            from synapse.panel.face_token import FaceToken
            self._token_face = FaceToken(scale=self._chrome_scale)
            return self._token_face
        except Exception:
            self._token_face = None
            return self._section()

    def _build_faces(self):
        """The two faces in one stack. Direct (CHAT) is the artist's surface; Work
        is the working glance AND the payoff (its done sub-state folds in the old
        Review). Only an actionable consent gate auto-surfaces Work (v9.1 · Option
        A); quiet agent state never does."""
        cached = self._region_cache.get("_build_faces")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        self._faces = QtWidgets.QStackedWidget()
        self._faces.addWidget(self._build_direct_face())   # 0 · idle / converse
        self._faces.addWidget(self._build_work_face())     # 1 · glance → done payoff
        self._faces.addWidget(self._build_token_face())    # 2 · the economist read-out
        self._faces.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        # Low floor so the faces stack (Direct = chat + act + input) never forces
        # the panel taller than a short pane and clips the Send row. The chat's
        # stretch keeps it dominant at normal heights.
        self._faces.setMinimumHeight(160)
        self._region_cache["_build_faces"] = self._faces
        return self._faces

    def _build_direct_face(self):
        """Direct — converse + input. The artist's surface (direction B,
        bc-wave: composer-first). The face is a shell (GUTTER inset via the
        role, never an imperative margin) whose own gap is the beat between
        the transcript and the composer. The verb rail and the hairline that
        divided it from the composer left with it (F1 / F16): EXPLAIN / FIX /
        OPTIMIZE are slash-palette rows and BUILD HDA is an overflow action."""
        page = self._section()
        page.setProperty("rhythm_role", "shell")
        col = QtWidgets.QVBoxLayout(page)
        col.addWidget(self._build_converse(), 1)   # chat | Build-HDA inner stack
        # bc-wave BC-6a: the consent slot - a `card` collection (16/24/12,
        # whitespace between cards) between the transcript and the composer.
        # It holds the turn receipt ('{n} CHANGES' + '<- REVERT' after a quiet
        # turn that changed the scene, F11) and, once the gate lends its
        # cards here (set_card_host, BC-6b), the consent cards themselves.
        # Hidden while empty (_sync_consent_slot).
        self._consent_slot = self._section()
        self._consent_slot.setProperty("rhythm_role", "card")
        slot = QtWidgets.QVBoxLayout(self._consent_slot)
        self._turn_receipt = self._build_turn_receipt()
        slot.addWidget(self._turn_receipt)
        self._consent_slot.hide()
        col.addWidget(self._consent_slot)
        from synapse.panel.recall_card import RecallCard
        self._recall_card = RecallCard()
        self._recall_card.hide()
        col.addWidget(self._recall_card)
        from synapse.panel.lookdev_suggestion import LookdevSuggestionCard
        previous = getattr(self, "_lookdev_suggestion", None)
        if previous is not None:
            previous.shutdown()
        self._lookdev_suggestion = LookdevSuggestionCard()
        self._lookdev_suggestion.draft_ready.connect(self._prepare_lookdev_prompt)
        col.addWidget(self._lookdev_suggestion)
        col.addWidget(self._build_input())
        return page

    def _build_turn_receipt(self):
        """The quiet turn's receipt: a `stack` row - '{n} CHANGES' as a `tag`
        + '<- REVERT' (the panel's own verb) -> _on_revert. Shown by _on_done
        when the turn's evidence holds a successful mutator, hidden at the top
        of the next _send. One signal, one destination (F11)."""
        w = self._section()
        w.setProperty("rhythm_role", "stack")
        row = QtWidgets.QHBoxLayout(w)
        self._receipt_badge = c.Badge("")
        self._receipt_badge.setProperty("rhythm_role", "tag")
        self._receipt_badge.setFont(fontload.apply_family(self._receipt_badge.font(), mono=True))
        row.addWidget(self._receipt_badge)
        row.addStretch(1)
        self._receipt_revert = self._verb("\u2190 REVERT", lambda _=False: self._on_revert())
        row.addWidget(self._receipt_revert)
        w.hide()
        return w

    def _sync_consent_slot(self):
        """Show the consent slot iff something in it is live: the turn receipt
        or an undecided consent card (a decided card is hidden - the ledger
        already announced it in the chat; an unrecorded one stays, RULING 18)."""
        slot = getattr(self, "_consent_slot", None)
        if slot is None:
            return
        lay = slot.layout()
        live = False
        for i in range(lay.count()):
            w = lay.itemAt(i).widget()
            if w is None:
                continue
            if hasattr(w, "_proposal_id") and not w.isEnabled():
                w.hide()
            if not w.isHidden():
                live = True
        slot.setVisible(live)

    def _show_turn_receipt(self, count):
        badge = getattr(self, "_receipt_badge", None)
        if badge is not None:
            badge.setText("%d CHANGE%s" % (count, "" if count == 1 else "S"))
            c.repolish(badge)
        receipt = getattr(self, "_turn_receipt", None)
        if receipt is not None:
            receipt.show()
        self._sync_consent_slot()

    def _hide_turn_receipt(self):
        receipt = getattr(self, "_turn_receipt", None)
        if receipt is not None:
            receipt.hide()
        self._sync_consent_slot()

    def _build_work_face(self):
        """Work — the walk-away glance AND the payoff, on one surface (v9 fold).

        A sub-``QStackedWidget`` holds two sub-states: ``cook`` (FaceWork — cook
        preview, plan-with-progress, live tool status, the thinking pulse, the
        embedded observability infographic) and ``done`` (FaceReview — verdict,
        credit, quality flags, the graduated gate, accept/revert/commit). The
        panel delegates its working signals to FaceWork (set_thinking /
        set_tool_status / set_health). Cook→done is a content update *within this
        tab*, never a tab switch; the rail mark carries working→done. Review is
        no longer a top-level tab — it folded here."""
        page = self._section()
        col = QtWidgets.QVBoxLayout(page)
        self._work_stack = QtWidgets.QStackedWidget()

        # sub-state 0 · COOKING — FaceWork owns the glance
        if FaceWork is not None:
            self._work_face = FaceWork()
            cook = self._work_face
        else:  # graceful fallback — the surface stays present without FaceWork
            self._work_face = None
            cook = self._section()
            _l = QtWidgets.QVBoxLayout(cook)
            _l.addWidget(c.label("Work face unavailable in this build", role="caption"))
            _l.addStretch(1)
        self._work_stack.addWidget(cook)

        # sub-state 1 · DONE — FaceReview folds in as the synthesis / payoff
        self._work_stack.addWidget(self._build_done_substate())

        self._work_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        col.addWidget(self._work_stack, 1)
        self._work_stack.setCurrentIndex(0)   # cook is the resting Work sub-state
        return page

    def _build_done_substate(self):
        """The Work face's *done* sub-state — the payoff (v9 fold of old Review).
        FaceReview owns the render-hero, verdict, credit/provenance, quality
        flags (incl. BL-007/008), the graduated gate, and accept/revert/commit.
        ``self._gate`` aliases the embedded gate so the consent wiring
        (_wire_gate / _on_gate_raised) is unchanged."""
        if FaceReview is not None:
            self._review_face = FaceReview()
            self._gate = self._review_face.gate
            self._review_face.accepted.connect(self._on_accept)
            self._review_face.reverted.connect(self._on_revert)
            self._review_face.committed.connect(self._on_commit)
            self._review_face.open_render_requested.connect(self._on_open_render)
            return self._review_face
        # graceful fallback — keep the consent gate present without FaceReview
        self._review_face = None
        page = self._section()
        col = QtWidgets.QVBoxLayout(page)
        if GateWidget is not None:
            self._gate = GateWidget(parent=page)
            col.addWidget(self._gate)
        else:
            self._gate = None
        col.addStretch(1)
        return page

    def _set_work_substate(self, state):
        """Swap the Work face between 'cook' and 'done'. A content update WITHIN
        the Work face — never a surface switch (the same-pane law). The rail
        mark, not a tab change, is what signals a ready result."""
        stack = getattr(self, "_work_stack", None)
        if stack is None:
            return
        stack.setCurrentIndex(1 if state == "done" else 0)
        self._work_substate = state

    def _host_font_scale(self):
        """Base font-scale = the host UI font size, EXACTLY. The panel starts at
        Houdini's own default text size on any display/DPI (a larger host font
        starts the content larger, a smaller one smaller) — "default Houdini UI
        font size to start". No readability floor: the Aa control lifts it from
        there, but startup never reads larger than the host. ``QFontInfo``
        resolves the actual pixel size whether set in points or pixels; headless
        (no QApplication) falls back to the token default."""
        try:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                host_px = QtGui.QFontInfo(app.font()).pixelSize()
                if host_px and host_px > 0:
                    return host_px / float(t.SIZE_BODY)
        except Exception:
            pass
        return t.FONT_SCALE_DEFAULT

    def _active_model(self):
        """Model id of the active engine — the picked model for this provider,
        else the registry default (no network)."""
        pid = getattr(self, "_provider_id", "claude")
        picked = getattr(self, "_model_by_provider", {}).get(pid)
        if picked:
            return picked
        try:
            from synapse.panel.providers import registry as reg
            return reg.default_model(pid)
        except Exception:
            try:
                from synapse.panel.claude_worker import _MODEL
                return _MODEL
            except Exception:
                return ""

    def _provider_model_rows(self, pid):
        """``(model_id, label)`` rows for a provider — the registry rows, with
        the Ollama live-tag special case hoisted here (menu-open is user-
        initiated; 1s localhost timeout; the registry row is only the static
        fallback). Shared by the model picker AND the author engine menu.

        Guarantee (v9 hardening): when ``pid`` is the ACTIVE provider, the
        active model is always among the rows — a persisted pick can go stale
        (registry rotation) or be live-only (an Ollama tag while the daemon is
        down), and the selection must stay OBSERVABLE: the artist sees exactly
        what will run, checked, never a silently blank menu. The stale row is
        appended after the registry rows (label falls back to the raw id)."""
        try:
            from synapse.panel.providers import registry as reg
        except Exception:
            return []
        rows = list(reg.models_for(pid))
        if pid == "ollama":
            # Menu opening must not block Houdini on a network request. Setup
            # discovers models off-thread; keep checked models visible here.
            for spec in getattr(self, "_connection_facts", {}):
                if spec.provider == pid and spec.model not in {mid for mid, _ in rows}:
                    rows.append((spec.model, spec.model))
        if pid == getattr(self, "_provider_id", "claude"):
            cur = self._active_model()
            if cur and cur not in {mid for mid, _ in rows}:
                rows.append((cur, reg.model_label(pid, cur)))
        return rows

    def _model_menu_items(self):
        """``(model_id, label, active)`` rows for the active provider's picker —
        the exact data the model menu renders; exposed for the readability
        audit so the picker is gate-checkable offscreen."""
        pid = getattr(self, "_provider_id", "claude")
        cur = self._active_model()
        return [(mid, lbl, mid == cur)
                for mid, lbl in self._provider_model_rows(pid)]

    def _author_menu_items(self):
        """``(pid, provider_label, [(mid, label, active)])`` — the exact data
        the author-token engine menu renders, exposed so engine selection stays
        gate-checkable offscreen (the ``_model_menu_items`` pattern). Exactly
        ONE ``(pid, mid)`` is active across the whole tree."""
        try:
            from synapse.panel.providers.registry import PROVIDER_IDS, PROVIDER_LABELS
        except Exception:
            return []
        cur_pid = getattr(self, "_provider_id", "claude")
        cur_mid = self._active_model()
        return [
            (pid, PROVIDER_LABELS.get(pid, pid),
             [(mid, lbl, pid == cur_pid and mid == cur_mid)
              for mid, lbl in self._provider_model_rows(pid)])
            for pid in PROVIDER_IDS
        ]

    def _fill_author_submenu(self, sub, pid):
        """(Re)build one provider submenu from live rows. The Ollama submenu
        re-fills on aboutToShow so the local tag list stays current; Custom
        appends Configure… (and opens even while unconfigured)."""
        sub.clear()
        cur_pid = getattr(self, "_provider_id", "claude")
        cur_mid = self._active_model()
        for mid, lbl in self._provider_model_rows(pid):
            act = sub.addAction(lbl)
            act.setCheckable(True)
            act.setChecked(pid == cur_pid and mid == cur_mid)
            act.triggered.connect(
                lambda _=False, p=pid, m=mid: self._pick_engine_model(p, m))
        if pid == "custom":
            if not sub.isEmpty():
                sub.addSeparator()
            sub.addAction("Configure…", self._configure_custom)

    def _open_author_menu(self):
        """The rail author token's engine+model menu (v9) — one submenu per
        provider, rows from the registry; REUSES the proven _set_provider /
        _set_model / _persist_picks machinery (only the anchor moved from the
        retired pill bar). Exactly one row is checked: the active pair."""
        try:
            from synapse.panel.providers.registry import PROVIDER_IDS, PROVIDER_LABELS
        except Exception:
            return
        menu = QtWidgets.QMenu(self)
        menu.addAction("Connect models…", self._open_connections)
        menu.addSeparator()
        for pid in PROVIDER_IDS:
            sub = menu.addMenu(PROVIDER_LABELS.get(pid, pid))
            self._fill_author_submenu(sub, pid)
            if pid == "ollama":
                sub.aboutToShow.connect(
                    lambda s=sub, p=pid: self._fill_author_submenu(s, p))
        btn = getattr(self, "_author_lbl", None)
        anchor = btn if btn is not None else self
        pos = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))
        menu.exec(pos) if hasattr(menu, "exec") else menu.exec_(pos)

    def _pick_engine_model(self, pid, mid):
        """A row pick from the author menu: switch the engine if needed, then
        the model — both existing persisted paths (effective on the NEXT
        message; two chat announcements are acceptable)."""
        if pid != getattr(self, "_provider_id", "claude"):
            self._set_provider(pid)
        self._set_model(mid)

    def _open_model_menu(self):
        """Drop the model picker for the active engine — switching Anthropic
        models (Opus/Sonnet/Haiku/Fable) is now apparent, not hidden. The
        Custom engine's menu carries a Configure… action (and opens even
        while unconfigured, when it has no model row yet)."""
        items = self._model_menu_items()
        pid = getattr(self, "_provider_id", "claude")
        if not items and pid != "custom":
            return
        menu = QtWidgets.QMenu(self)
        for mid, lbl, active in items:
            act = menu.addAction("%s   %s" % (lbl, mid))
            act.setCheckable(True)
            act.setChecked(active)
            act.triggered.connect(lambda _=False, m=mid: self._set_model(m))
        if pid == "custom":
            if items:
                menu.addSeparator()
            menu.addAction("Configure…", self._configure_custom)
        chip = getattr(self, "_model_chip", None)
        anchor = chip if chip is not None else self
        pos = anchor.mapToGlobal(QtCore.QPoint(0, anchor.height()))
        menu.exec(pos) if hasattr(menu, "exec") else menu.exec_(pos)

    def _set_model(self, model_id):
        """Pick a model for the active engine. Takes effect on the NEXT message;
        the chip + author token update now. Display/telemetry only."""
        pid = getattr(self, "_provider_id", "claude")
        self._model_by_provider[pid] = model_id
        self._refresh_engine_selector()
        self._persist_picks()
        try:
            from synapse.panel.providers.registry import model_label
            self._chat.append_system_message(
                "Next task will use %s." % model_label(pid, model_id))
        except Exception:
            pass

    def _persist_picks(self):
        """Persist the engine + per-provider model picks (custom config rides
        along untouched). Best-effort — never breaks a switch."""
        try:
            from synapse.panel import settings as _pset
            st = _pset.load_settings()
            st["provider_id"] = getattr(self, "_provider_id", "claude")
            st["model_by_provider"] = dict(
                getattr(self, "_model_by_provider", {}) or {})
            _pset.save_settings(st)
        except Exception:
            pass

    def _persist_composer_height(self, h):
        """The artist dragged the composer divider — keep THEIR height for
        the next launch (L5-22). Read-modify-write so sibling keys survive;
        best-effort — a failed save never interrupts the session."""
        try:
            from synapse.panel import settings as _pset
            st = _pset.load_settings()
            st["composer_height"] = int(h)
            _pset.save_settings(st)
        except Exception:
            pass

    def _settle_composer_height(self):
        """L5-22 first run: the divider opens equidistant between prompt and
        chat — half the space the two share, measured at show/resize where
        the pane's height is real (never __init__). A persisted artist drag
        wins instead. Either way the height settles exactly ONCE per panel:
        after that the divider moves only under the artist's hand (L6 — the
        panel remembers their answer, never re-imposes its own). Identical
        in curious / expert / ml — this is seat comfort, not a profile."""
        inp = getattr(self, "_input", None)
        if inp is None or inp._height_settled:
            return
        lay = self.layout()
        if lay is not None:
            lay.activate()          # geometry must be real before we measure
        chat = getattr(self, "_converse_stack", None)
        chat_h = chat.height() if chat is not None else 0
        if chat_h <= 0:
            return                  # not laid out yet — the next event retries
        shared = chat_h + inp.height()
        try:
            from synapse.panel import settings as _pset
            target = _pset.composer_start_height(
                _pset.load_settings().get("composer_height"),
                shared, inp._floor, inp._max_h)
        except Exception:
            target = max(inp._floor, min(inp._max_h, shared // 2))
        inp.settle_height(target)

    def _fit_composer_to_pane(self):
        """CTO B4: after settle, the composer must fit the pane it is in.
        Measures Send's bottom edge in panel coords (the exact G3 probe);
        overflow caps the composer, headroom relaxes the cap. The artist's
        height is preserved for the next tall dock (L6)."""
        inp = getattr(self, "_input", None)
        if inp is None or not inp._height_settled:
            return
        lay = self.layout()
        # Live-found 2026-09-05: the old "relax by the room below the
        # composer" branch could never recover the artist's height, because
        # the transcript stretch absorbs every pixel the pane gains - a cap
        # taken while the pane was transiently small (reload, first show)
        # stuck for the session. Idempotent form: start from the artist's
        # height, lay out, cap only by the measured overflow.
        def _relayout():
            # Nested layouts (faces stack -> direct face -> composer) settle
            # through posted LayoutRequest events; activate() alone measures
            # stale geometry. Flush them so the measurement is the truth.
            if lay is not None:
                lay.activate()
            try:
                QtWidgets.QApplication.sendPostedEvents(
                    None, QtCore.QEvent.Type.LayoutRequest)
            except Exception:
                pass
            if lay is not None:
                lay.activate()
        before = inp._cap
        if inp._cap is not None:
            inp.cap_height(None)
        _relayout()
        bottom = inp.mapTo(self, QtCore.QPoint(0, inp.height())).y()
        room = self.height() - bottom
        if room < 0:
            inp.cap_height(inp.height() + room)
        # Nested layouts converge over event-loop turns, not in one call: a
        # pass that moved the cap schedules one more, until the cap is stable
        # (bounded - never a loop that outlives the resize).
        if inp._cap != before and getattr(self, "_fit_rounds", 0) < 8:
            self._fit_rounds = getattr(self, "_fit_rounds", 0) + 1
            QTimer.singleShot(0, self._fit_composer_to_pane)
        else:
            self._fit_rounds = 0

    def showEvent(self, e):
        super().showEvent(e)
        self._settle_composer_height()
        self._fit_composer_to_pane()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._settle_composer_height()
        self._fit_composer_to_pane()

    def _author_token(self):
        """The model token: ``<provider>/<model short id>`` - who is thinking.
        Joe's ruling 2026-09-05 (RULING_DIRECTION_BC.md Addendum 2 + 3.2):
        ``ollama/deepseek-v4-flash``, ``claude/fable-5.1``, ``gemini/3.5-flash``.
        Complete requested identity and location evidence live in the tooltip;
        provider name alone is not evidence of locality or cost.
        Lowercase mono data; the curated display label lives in the picker.
        DISPLAY ONLY - it is never authored to USD."""
        task = getattr(self, "_task_connection", None)
        m = task.spec.model if task else self._active_model()
        if not m:
            return ""
        pid = (task.spec.provider if task else getattr(self, "_provider_id", "claude") or "claude").strip().lower()
        ident = str(m).strip()
        ident = ident.split("/")[-1]            # nvidia/nemotron-... -> nemotron-...
        ident = ident.split(":")[0]             # glm-5.2:cloud -> glm-5.2
        if ident.lower().startswith("claude-"):
            ident = ident[len("claude-"):]      # claude-fable-5-1 -> fable-5.1
            parts = ident.split("-")
            if len(parts) >= 3 and parts[-1].isdigit() and parts[-2].isdigit():
                ident = "-".join(parts[:-2]) + "-" + parts[-2] + "." + parts[-1]
        ident = ident.lower()
        return f"{pid}/{ident}"

    def _set_provider(self, provider_id):
        """Switch the active chat engine. Takes effect on the NEXT message; the
        rail author token updates immediately. Display/telemetry only — never
        touches USD/customData."""
        self._provider_id = provider_id
        # _refresh_engine_selector repaints the pills + chip AND the rail author.
        self._refresh_engine_selector()
        self._persist_picks()
        try:
            from synapse.panel.providers.registry import PROVIDER_LABELS
            self._chat.append_system_message(
                "Switched engine to %s." % PROVIDER_LABELS.get(provider_id, provider_id))
        except Exception:
            pass
        # An unconfigured Custom pick opens the Configure dialog straight away
        # — there is nothing to chat with until a base URL + model exist.
        if provider_id == "custom" and not self._custom_configured():
            self._configure_custom()

    def _custom_configured(self):
        """True when the Custom engine has both a base URL and a model id
        persisted (the provider's own unconfigured test, panel-side)."""
        try:
            from synapse.panel import settings as _pset
            cfg = _pset.load_settings().get("custom") or {}
            return bool(cfg.get("base_url") and cfg.get("model"))
        except Exception:
            return False

    def _configure_custom(self):
        """Use the guided setup for custom endpoints as well."""
        self._open_connections()

    def _make_provider(self):
        """Panel requests fail closed; legacy registry fallback cannot send them."""
        from synapse.panel.providers.registry import build_provider, PROVIDER_IDS
        pid = getattr(self, "_provider_id", "claude")
        if pid not in PROVIDER_IDS:
            raise ValueError("This engine is unavailable. Choose Connect models.")
        prov = build_provider(pid, model=self._active_model())
        if prov is None or prov.id != pid:
            raise ValueError("This engine could not be loaded. Choose Connect models.")
        return prov

    def _prepare_connection(self):
        from synapse.panel import connections as cn
        provider = self._make_provider()
        configured_key = provider.resolve_key()
        spec = cn.provider_spec(provider)
        secret = getattr(self, "_session_keys", {}).get((spec.provider, spec.endpoint), configured_key)
        return cn.bind_provider(provider, key=secret,
                                facts=getattr(self, "_connection_facts", {}).get(spec))

    def _open_connections(self):
        from synapse.panel.connection_dialog import ConnectionDialog
        from synapse.panel import settings as pset
        settings = pset.load_settings()
        dialog = ConnectionDialog(self, provider_id=self._provider_id,
                                  models=self._model_by_provider,
                                  custom=settings.get("custom"),
                                  session_keys=getattr(self, "_session_keys", {}))
        accepted = dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        if not accepted or not dialog.selection:
            dialog.deleteLater()
            return
        spec, facts, key, address = dialog.selection
        dialog.selection = None
        settings = pset.load_settings()  # Rules/preferences may have changed in the dialog.
        if spec.provider == "custom":
            cfg = dict(settings.get("custom") or {})
            if address != cfg.get("base_url"):
                # A legacy environment credential belongs to its saved service.
                # Never restore the previous service's key after reopening.
                cfg.pop("key_env", None)
            cfg.update(base_url=address, model=spec.model)
            settings["custom"] = cfg
            pset.save_settings(settings)
        self._session_keys[(spec.provider, spec.endpoint)] = key
        self._connection_facts[spec] = facts
        self._provider_id = spec.provider
        self._model_by_provider[spec.provider] = spec.model
        self._persist_picks()
        self._refresh_engine_selector()
        self._chat.append_system_message("Ready for the next task: %s · %s. Generation has not been tested." %
                                         (spec.identity, facts.location))
        controller = getattr(self, "_notification_controller", None)
        if controller is not None:
            controller.journal.note("connection", "Model checked", "%s · %s. Endpoint metadata was checked; generation has not been tested." % (spec.identity, facts.location),
                                    source="model", dedupe_key="model-check")
            controller.refresh()
        dialog.deleteLater()

    def _allow_connection(self, connection):
        from synapse import model_access as access
        provider = connection.provider
        scope = getattr(provider, "_model_scope", None) or access.capture_scope()
        provider._model_scope = scope
        provider._connection_facts = connection.facts
        key = provider.resolve_key()
        try:
            permission = access.require_access(connection.spec, key=key, facts=connection.facts, scope=scope)
        except access.ModelAccessDenied:
            policy = access.load_policy()
            if policy.error or policy.mode == "local_only" or not scope.active:
                raise
            permission = None
        if permission:
            provider._model_grant = access.issue_task_grant(connection.spec, key=key,
                facts=connection.facts, approved=True, scope=scope)
            return True
        session_grant = access.session_task_grant(connection.spec, key=key,
            facts=connection.facts, scope=scope)
        if session_grant is not None:
            provider._model_grant = session_grant
            return True
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Allow this model connection?")
        box.setTextFormat(Qt.PlainText)
        box.setText(connection.facts.description)
        box.setInformativeText(
            "Your prompts, conversation, scene context, recalled memory, tool results and images supplied by "
            "tools can be sent to this service, including while tools run.\n\n"
            "Saved memory stays on this computer. Recalled contents may be sent.\n\n"
            "Allow one task, or allow follow-up panel tasks with this exact connection and selected project "
            "rules until Houdini exits. Session permission stays in memory. Revoke it below the prompt or in More.\n\n"
            "Changing project rules requires fresh permission. Background requests need separate Project rules. "
            "External MCP clients manage their own model connections.")
        allow = box.addButton("Allow this task", QtWidgets.QMessageBox.AcceptRole)
        session = box.addButton("Allow for this session", QtWidgets.QMessageBox.AcceptRole)
        cancel = box.addButton("Keep editing", QtWidgets.QMessageBox.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec() if hasattr(box, "exec") else box.exec_()
        clicked = box.clickedButton()
        box.deleteLater()
        if clicked is not allow and clicked is not session:
            scope.active = False
            return False
        if clicked is session:
            provider._model_grant = access.issue_session_grant(connection.spec, key=key,
                facts=connection.facts, approved=True, scope=scope)
            _refresh_session_permission_views()
        else:
            provider._model_grant = access.issue_task_grant(connection.spec, key=key,
                facts=connection.facts, approved=True, scope=scope)
        return True

    def _refresh_session_permission(self, connection=None):
        """Display permission for the shown recipient; never approve from a read."""
        button = getattr(self, "_session_permission_btn", None)
        if button is None:
            return
        temporary = None
        try:
            from synapse import model_access as access
            if connection is None:
                connection = getattr(self, "_task_connection", None)
            if connection is None:
                temporary = connection = self._prepare_connection()
            # A running task can retain an older class generation after another
            # panel opens. Normalize only this display identity, never its grant.
            shown_spec = access.ConnectionSpec(connection.spec.provider,
                connection.spec.model, connection.spec.endpoint)
            allowed = access.has_session_approval(shown_spec,
                key=connection.provider.resolve_key())
            button.setVisible(allowed)
            if allowed:
                button.setToolTip(
                    connection.facts.description + "\n\nAllowed for this Houdini session under the selected project rules. "
                    "Click to revoke all session model permissions in every open SYNAPSE panel. "
                    "Requests already sent may finish. Saved Project rules are separate.")
        except Exception:
            button.hide()
        finally:
            if temporary is not None:
                temporary.release()

    def _revoke_session_approvals(self):
        from synapse import model_access as access
        access.revoke_session_approvals()
        _refresh_session_permission_views()
        self._chat.append_system_message(
            "Session model permissions revoked for all SYNAPSE panels. "
            "The next request needs permission unless saved Project rules allow it. "
            "Requests already sent may finish.")

    def _route_connection(self, connection, text):
        from synapse.panel.model_routing import choose_route
        from synapse.panel import settings as pset, connections as cn
        from synapse.panel.providers.registry import build_provider
        settings = pset.load_settings()
        decision = choose_route(connection.facts, tuple(self._connection_facts.values()),
            mode=settings.get("routing_mode", "chosen_model"),
            need=settings.get("task_need", "conversation"),
            tools=get_anthropic_tools(),
            messages=self._messages + [{"role": "user", "content": text}])
        if not decision.ok:
            raise ValueError(decision.reason)
        if decision.facts.spec != connection.spec:
            target = decision.facts
            provider = build_provider(target.spec.provider, model=target.spec.model)
            if cn.provider_spec(provider) != target.spec:
                raise ValueError("The local service changed. Check the model again before using it.")
            key = self._session_keys.get((target.spec.provider, target.spec.endpoint), provider.resolve_key())
            replacement = cn.bind_provider(provider, key=key, facts=target)
            if replacement.spec != target.spec:
                replacement.release()
                raise ValueError("The local service changed while connecting. Check the model again before using it.")
            connection.release()
            connection = replacement
        connection.provider._automatic_requirements = decision.requirements if decision.automatic else None
        connection.provider._route_reason = decision.reason
        return connection

    _MUTATORS = ("create", "set_", "assign", "build", "wire", "connect",
                 "render", "author", "delete", "apply", "configure")

    def _turn_evidence(self):
        """(credit, flags, paths) from what the turn actually did.

        P2. The result surface could always RENDER these; nothing produced them.
        The P1 census measured it: set_credit / set_flags / set_paths /
        set_render / show_result had ZERO product callers, so the panel drew a
        result it never populated — and `set_credit`'s one caller passed a
        ROUTED row, which its DECISION filter drops. A credit it could never
        earn.

        Law 3: this reports what HAPPENED. A failed tool becomes a `fail` flag,
        not a missing row, and an empty turn returns empty rather than inventing
        a decision.
        """
        tools = list(getattr(self, "_turn_tools", []) or [])
        if not tools:
            return [], [], []

        credit, flags, paths = [], [], []
        seen = set()
        for name, verb, detail in tools:
            status = "ok" if verb == "ok" else "fail"
            flags.append((status, name if not detail else "%s — %s" % (name, str(detail)[:70])))

            # DECISION rows: only for tools that CHANGED something, and only
            # when they succeeded. A mutation that failed is a flag, not a credit.
            low = name.lower()
            if status == "ok" and any(k in low for k in self._MUTATORS):
                credit.append(("DECISION", name, str(detail or "")[:90]))

            # Node paths the turn touched, in order, de-duplicated.
            for tok in str(detail or "").split():
                if tok.startswith("/") and len(tok) > 1 and tok not in seen:
                    seen.add(tok)
                    paths.append(tok)

        return credit, flags, paths[:12]

    def _populate_review(self):
        """On 'done', fill the Work done sub-state with what we can: a taut
        verdict from the last reply, the SIGNED authorship line, and provenance
        from the routing_log (best-effort). All display-only.

        P2: also credits what the turn DID — the five setters that had no
        product caller until now.
        """
        from synapse.panel.recall_card import latest_recall_result
        result = latest_recall_result(getattr(self, "_messages", ()))
        if result is not None:
            self._display_recall_result(result)
        rf = getattr(self, "_review_face", None)
        if rf is None:
            return
        text = "".join(getattr(self, "_stream_buf", []) or []).strip()
        if text:
            verdict = text.split("\n", 1)[0].strip()
            if len(verdict) > 140:
                verdict = verdict[:137] + "…"
            rf.set_verdict(verdict)
        rf.set_signed(self._author_token())

        # P2 — the missing half. Best-effort and never fatal: a panel that
        # cannot draw its credit must still show the verdict.
        try:
            credit, flags, paths = self._turn_evidence()
            if credit:
                rf.set_credit(credit)
            if flags:
                rf.set_flags(flags)
            if paths:
                rf.set_paths(paths)
        except Exception:
            pass

        rf.refresh_provenance()

    def _on_render_receipt(self, event):
        """The RETINA T0 receipt, computed off the Qt thread by the worker
        (``render_receipt`` signal → here on the main thread). ``event`` is the
        perception-event envelope, or ``None`` for a render with no perception
        wired. Surface it in the Review face — this is the real render receipt
        that replaces the retired hardwired BL-007 flag."""
        rf = getattr(self, "_review_face", None)
        if rf is None:
            return
        try:
            rf.set_receipt(event)
        except Exception:
            pass

    def _on_integrity(self, summary):
        """The session IntegrityBlock roll-up (fidelity/verified/violations),
        emitted by the worker after each tracked result. Paint it in the Work
        face's telemetry cluster — the "what changed" window that closes the
        core guarantee's visibility gap (audit A.2.2). Best-effort; the empty
        state is honest SLATE, never a fabricated green."""
        wf = getattr(self, "_work_face", None)
        if wf is None:
            return
        try:
            wf.set_integrity(summary)
        except Exception:
            pass

    def _on_accept(self):
        try:
            self._chat.append_system_message("Accepted — keeping the result.")
        except Exception:
            pass
        self._set_face("direct")            # v9.1 · hand back to the conversation

    def _on_revert(self):
        # Reversibility: route an undo through the proven agent/bridge path
        # rather than touching the substrate from the panel.
        # Addendum 3.6: REVERT is state-gated like Stop - not while streaming.
        w = getattr(self, "_worker", None)
        if w is not None and hasattr(w, "isRunning") and w.isRunning():
            try:
                self._chat.append_system_message(
                    "Still working - Stop the current turn before reverting.")
            except Exception:
                pass
            return
        if self._send("Undo the last change using houdini_undo, then confirm what was reverted."):
            try:
                self._chat.append_system_message("Revert requested. Waiting for the task result…")
            except Exception:
                pass
            self._set_face("direct")        # return only after an accepted task

    def _on_commit(self):
        # Commit is a consent moment — it routes through the gate; the panel
        # never writes /stage itself (the substrate stays Gold's zone).
        try:
            self._chat.append_system_message(
                "Commit to /stage requested — routing through the consent gate.")
        except Exception:
            pass
        # The gate lives in Work's done sub-state; the artist is already there
        # (they clicked Commit). Keep it forward — never spawn or switch tabs.
        self._set_work_substate("done")

    def _on_open_render(self):
        # D1 (panel finishing harness) — render-view surface is an OPEN ITEM.
        # Surfacing Houdini's existing Render View needs the hou.ui pane chain
        # (hou.ui.curDesktop().paneTabOfType(hou.paneTabType.IPRViewer)
        # .setIsCurrentTab()). hou.ui is absent from the headless H21.0.671
        # symbol table (unconfirmable) and the live bridge was unavailable, so
        # per phantom-API discipline this stays a clean, feature-detected no-op
        # rather than guess the hou.ui chain. Same-pane law holds trivially: it
        # never switches a face and never spawns a pane.
        try:
            import hou  # noqa: F401 — headless → ImportError → silent no-op
        except Exception:
            return
        # Confirmed-API render-view surface intentionally NOT written (D1 halt).
        return

    def _build_hda_form(self):
        """Native-designsystem describe→build flow (the build runs through the
        agent's houdini_hda_package tool, so it reuses the proven runtime)."""
        page = self._section()
        lay = QtWidgets.QVBoxLayout(page)
        lay.addWidget(c.label("Describe the HDA you want", role="title"))
        self._hda_prompt = QtWidgets.QTextEdit()
        self._hda_prompt.setObjectName("DsInput")
        self._hda_prompt.setAcceptRichText(False)
        self._hda_prompt.setPlaceholderText(
            "e.g. a scatter tool with density control · a 3-point light rig · "
            "a Karma draft/preview/production setup"
        )
        self._hda_prompt.setMinimumHeight(110)
        lay.addWidget(self._hda_prompt)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(c.label("Context", role="caption"))
        self._hda_ctx = QtWidgets.QComboBox()
        self._hda_ctx.addItems(["SOP", "LOP", "DOP", "COP", "TOP"])
        row.addWidget(self._hda_ctx)
        self._hda_help = QtWidgets.QCheckBox("Include help text")
        self._hda_help.setObjectName("DsHdaOption")   # the SWEEP_B option rule (target floor)
        self._hda_help.setChecked(True)
        row.addWidget(self._hda_help)
        row.addStretch(1)
        lay.addLayout(row)
        gen = c.Button("Generate HDA", variant="primary")
        gen.clicked.connect(self._on_build_hda)
        lay.addWidget(gen)
        # Back to the conversation — Build HDA is an inner view of Direct, and
        # without an explicit way out it reads as a dead-end (artist feedback).
        back = c.Button("Main menu", variant="secondary")
        back.setToolTip("Back to the conversation")
        back.clicked.connect(lambda: self._set_direct_view("chat"))
        lay.addWidget(back)
        lay.addStretch(1)
        return page

    def _set_direct_view(self, view):
        """Toggle Direct's inner surface: the chat (0) or the Build-HDA form (1).
        Build HDA is no longer a top-level face — it lives inside Direct (⌘K too)."""
        if hasattr(self, "_converse_stack"):
            self._converse_stack.setCurrentIndex(1 if view == "hda" else 0)
        self._set_face("direct")   # the HDA form lives on the Direct surface

    # ------------------------------------------------------- tab controller
    def _set_face(self, face, manual=True):
        """Bring a face forward. Callers: a user click on the CHAT label, the idle
        default, and the consent AUTO-SURFACE (a raised gate → Work, then
        accept/revert → back; v9.1). Quiet agent state (busy / tool status) never
        calls this — it drives the Work sub-state + rail mark. ``manual`` is
        accepted for call-site compatibility and otherwise unused."""
        if not hasattr(self, "_faces") or face not in self._FACE_INDEX:
            return
        self._faces.setCurrentIndex(self._FACE_INDEX[face])
        self._current_face = face
        for f, pill in getattr(self, "_face_pills", {}).items():
            pill.setProperty("active", f == face)
            c.repolish(pill)

    def _on_build_hda(self):
        prompt = self._hda_prompt.toPlainText().strip()
        if not prompt:
            return
        ctx = self._hda_ctx.currentText()
        helptxt = " Include help text." if self._hda_help.isChecked() else ""
        if self._send(
            "Build a %s HDA: %s. Use the houdini_hda_package tool, then show me "
            "the node path and the promoted parameters.%s" % (ctx, prompt, helptxt)
        ):
            self._hda_prompt.clear()
            self._set_direct_view("chat")

    def _set_thinking(self, on):
        """Delegate the thinking pulse to the Work face (Mile 4)."""
        wf = getattr(self, "_work_face", None)
        if wf is not None:
            wf.set_thinking(on)

    def _update_health(self):
        """Timer-driven: poll the bridge, persist recommendations + run the
        meta-recursion analyzer, paint the infographic. Best-effort — a missing
        bridge or shared/ just yields the 'awaiting telemetry' empty state."""
        wf = getattr(self, "_work_face", None)
        if wf is None or agent_health is None:
            return
        try:
            data = agent_health.poll_agent_health()
        except Exception:
            data = None
        wf.set_health(data)

    def _verb(self, text, on_click, tone=None):
        """A type-set action — mono, no pill chrome (Mile 3). Styled by the
        canonical QPushButton#DsVerb QSS rule (Mile 7 finalized it); ``tone`` ∈
        {None, 'ok', 'hot', 'accent'} selects the semantic color via property."""
        btn = QtWidgets.QPushButton(text)
        btn.setObjectName("DsVerb")
        # One type applier per widget (RULING-4c): no rhythm_role="label" here.
        # L5-17: verbs carry the tab pills' tracking (same LABEL role, mono)
        # so they read as chrome siblings of CHAT/TOKEN, not body text.
        btn.setFont(fontload.tracked_font(
            "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        if tone:
            btn.setProperty("tone", tone)
        btn.clicked.connect(on_click)
        return btn

    def _build_input(self):
        w = self._section()
        # bc-wave BC-4: the composer is a flush `stack` - grip / input row /
        # legend at 4/6/3 - one beat on the grid, no hand-added spacer.
        w.setProperty("rhythm_role", "stack")
        col = QtWidgets.QVBoxLayout(w)
        self._input = _GrowingInput()
        self._input.setAccessibleName("Message to SYNAPSE")
        # Aa scales document text; the inherited root sheet owns the chrome.
        self._set_prompt_font(self._input, self._font_scale)
        self._input.submitted.connect(self._on_submit)
        self._input.slash.connect(self._open_palette)   # "/" → command palette
        # L5-22: a released grip-drag is the artist's answer — remember it
        self._input.height_committed.connect(self._persist_composer_height)
        col.addWidget(_InputResizeGrip(self._input))   # drag handle at the top
        row = QtWidgets.QHBoxLayout()
        # Image attachment uses the existing drawn glyph.
        attach = c.Button("", variant="ghost")
        attach.setIcon(_image_icon())
        attach.setIconSize(QtCore.QSize(36, 36))
        attach.setFixedWidth(52)
        attach.setToolTip("Attach image / file as context")
        attach.setAccessibleName("Attach image or file")
        attach.clicked.connect(self._on_attach)
        # v9 comp: SEND rides bottom-right INSIDE the composer (the attr name
        # `_send_btn` is load-bearing — the clip audit finds it by name).
        self._send_btn = QtWidgets.QPushButton("SEND")
        self._send_btn.setObjectName("DsSend")
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.setFont(fontload.tracked_font(
            "SEND", t.SIZE_SMALL, scale=self._chrome_scale, weight=500))
        self._send_btn.clicked.connect(self._on_submit)
        self._input.attach_send(self._send_btn)
        row.addWidget(self._input, 1)
        row.addWidget(attach)
        col.addLayout(row)
        # khint — the composer's quiet key legend (comp .khint). BC-4: it tells
        # the two keys and nothing else - '/' is told once, in the placeholder
        # (the telling G3 pins) - at the chrome floor (SIZE_SMALL, DATA mono,
        # TEXT_SECONDARY via the label colour role), one signal per fact.
        self._khint = c.label("Enter sends · Shift+Enter adds a line", role="label")
        self._khint.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        self._khint.setWordWrap(True)
        col.addWidget(self._khint)
        self._commands_btn = c.Button("Commands", variant="ghost")
        self._commands_btn.setToolTip("Browse commands · / on empty input · Ctrl+K")
        self._commands_btn.clicked.connect(self._open_palette)
        self._recipes_btn = c.Button("Recipes", variant="ghost")
        self._recipes_btn.setToolTip("Save, tag and reuse local Solaris networks")
        self._recipes_btn.clicked.connect(self._open_saved_recipes)
        self._events_btn = c.Button("Events", variant="ghost")
        self._events_btn.setToolTip("Local work and connection updates")
        self._events_btn.clicked.connect(self._open_notifications)
        col.addLayout(self._build_shortcut_footer())
        self._connection_status = c.Button("Connect models", variant="ghost")
        self._connection_status.clicked.connect(self._open_connections)
        col.addWidget(self._connection_status)
        self._session_permission_btn = c.Button("Session · Revoke", variant="ghost")
        self._session_permission_btn.setProperty("synapse_session_permission", True)
        self._session_permission_btn.clicked.connect(self._revoke_session_approvals)
        self._session_permission_btn.hide()
        col.addWidget(self._session_permission_btn)
        _SESSION_PERMISSION_VIEWS.add(self)
        # Expire display evidence without probing or sending any network traffic.
        self._location_timer = QTimer(self)
        self._location_timer.setInterval(30000)
        self._location_timer.timeout.connect(self._refresh_engine_selector)
        self._location_timer.start()
        QTimer.singleShot(0, self._refresh_engine_selector)
        return w

    def _build_shortcut_footer(self):
        """Center the three local links with the same light type as Ready."""
        footer = _ShortcutLayout(
            t.scaled(t.SPACE_LG, self._chrome_scale),
            t.scaled(t.SPACE_XS, self._chrome_scale))
        for button in (self._commands_btn, self._recipes_btn, self._events_btn):
            button.setObjectName("DsFooterLink")
            c.apply_font_role(button, "caption", scale=self._chrome_scale)
            button.setSizePolicy(QtWidgets.QSizePolicy.Maximum, QtWidgets.QSizePolicy.Preferred)
            footer.addWidget(button)
        return footer

    def _open_doctor(self):
        from synapse.panel.doctor_dialog import DoctorDialog
        dialog = getattr(self, "_doctor_dialog", None)
        if dialog is None:
            dialog = DoctorDialog(self)
            self._doctor_dialog = dialog
        already_visible = dialog.isVisible()
        dialog.show()
        dialog.raise_()
        if not already_visible:
            dialog.run_check()

    def _on_attach(self):
        """Image-attach button — adds picked files to the next request's context
        (same path as a file drag-drop)."""
        try:
            paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self, "Attach images / files", "",
                "Images (*.png *.jpg *.jpeg *.exr *.tif *.tiff);;All files (*)"
            )
        except Exception:
            paths = []
        added = []
        for p in paths or []:
            if p and p not in self._pending_context:
                self._pending_context.append(p)
                added.append(p)
        if added:
            try:
                self._chat.append_system_message("Attached: %s" % ", ".join(added))
            except Exception:
                pass
            self._input.setFocus()

    # ------------------------------------------------------------ behavior
    def _wire_gate(self):
        """GateWidget self-registers HumanGate callbacks; wiring it into the
        tree is what closes the consent gap (the legacy shipped panel never
        instantiated it). Mile 2 also taps its proposal relay so a raised gate
        brings the Review face forward — reversibility surfaces when it matters.
        """
        gate = getattr(self, "_gate", None)
        if gate is not None:
            try:
                # bc-wave BC-6b (direction C): consent cards land in the CHAT
                # consent slot - where the talking happens - and the slot
                # re-syncs on every card landing / decision. The Work-face
                # GateWidget keeps its fold header + integrity row.
                slot = getattr(self, "_consent_slot", None)
                if slot is not None:
                    gate.set_card_host(slot.layout(), self._sync_consent_slot)
            except Exception:
                logger.warning("consent slot host failed to wire", exc_info=True)
            try:
                # bc-wave BC-6a: REVIEW's '<- REVERT' on a card asks for the undo.
                gate.revert_requested.connect(lambda _pid=None: self._on_revert())
            except Exception:
                logger.warning("gate revert relay failed to wire", exc_info=True)
            try:
                gate._proposal_received.connect(self._on_gate_raised)
            except Exception:
                # Guarded, but never silent. If this relay fails to wire, a
                # raised consent gate stops bringing the Review face forward --
                # the artist is asked to approve something they are not shown.
                # The panel still starts (that is why the guard exists), but the
                # failure leaves a trail instead of vanishing (Law 3).
                #
                # WARNING, not debug, and the level is load-bearing: the panel's
                # own bootstrap calls ensure_file_logging(), which sets the
                # `synapse` logger to INFO. A debug record on this path is
                # therefore DISCARDED in every live session -- it would satisfy
                # a test that lowers the level and inform nobody in the field.
                # A degraded consent surface is not debug information anyway.
                logger.warning("gate proposal relay failed to wire", exc_info=True)

    def _on_gate_raised(self, proposal):
        """An actionable gate proposal arrived → consent surfaces INLINE on the
        CHAT face (bc-wave BC-6b, direction C, Joe's ruling item 2): the card
        is already in the consent slot (GateWidget.set_card_host), so the view
        never moves - the artist decides where they were talking. Noisy INFORM
        is skipped. Work's done payoff is still readied (verdict + provenance)
        for the artist who goes looking; the rail sentence follows STATUS,
        never a gate. Quiet state (busy / tool status / a plain answer) never
        moved the view before and still does not.

        v9.1 (Option A) used to switch to the Work face here; G3 invariant #2
        (audit_panel.py) and tests/test_panel_faces.py::
        test_gate_raised_auto_surfaces_work pin that MECHANISM. The INTENT -
        consent must be seen; quiet state never moves the view - is met by
        the inline card; the one-line intent edit to the audit is a human
        edit (RULING_DIRECTION_BC.md escalation), so this commit is held
        behind it."""
        if isinstance(proposal, dict):
            level = proposal.get("level", "")
        else:
            level = getattr(proposal, "level", "")
        if level and level != "inform":
            self._populate_review()
            self._set_work_substate("done")
            self._sync_consent_slot()

    def _show_overflow(self):
        menu = self._build_overflow_menu()
        menu.exec(QtGui.QCursor.pos()) if hasattr(menu, "exec") else menu.exec_(QtGui.QCursor.pos())

    def _build_overflow_menu(self):
        """The overflow QMenu, built without exec so a test can read it.

        bc-wave (direction B): the chrome that left the composed panel at rest
        lives here - Build HDA (was a verb on the retired rail), the text-size
        pair (the 'Aa' verb duplicated them, F10), the halt controls (H3b).
        J4 (Joe's five): no Profile submenu - the profile switch left the UI;
        'Larger text / Default text' are the Aa font scale, not density."""
        menu = QtWidgets.QMenu(self)
        menu.addAction("Copy conversation", self._copy_conversation)
        menu.addAction("Revoke session model permissions", self._revoke_session_approvals)
        # Build HDA: the form is unchanged; only the way in moved (BC-1).
        menu.addAction("Build HDA…", lambda: self._set_direct_view("hda"))
        menu.addAction("Saved lookdev suggestion…", self._open_lookdev_suggestion)
        # BC-2: the rail's chrome reads here. Palette names the ACTUAL bound
        # key (the hidden owner's text is set from the QShortcut, never a
        # guess); Ground the corpus is checked once the store is built.
        key = getattr(self, "_palette_hint", None)
        key_txt = key.text() if key is not None else ""
        menu.addAction("Palette   %s" % key_txt if key_txt else "Palette",
                       self._open_palette)
        try:
            self._refresh_corpus_state()
        except Exception:
            pass
        corpus_act = menu.addAction("Ground the corpus", self._on_corpus)
        corpus_act.setCheckable(True)
        corpus_btn = getattr(self, "_corpus_btn", None)
        corpus_act.setChecked(bool(corpus_btn is not None
                                   and corpus_btn.text().endswith("\u2713")))
        corpus_act.setToolTip(corpus_btn.toolTip() if corpus_btn is not None else "")
        menu.addSeparator()
        # — engine switch (multi-provider). Display/telemetry only; the worker
        # for the NEXT message is built with the selected provider. —
        try:
            from synapse.panel.providers.registry import PROVIDER_IDS, PROVIDER_LABELS
            cur = getattr(self, "_provider_id", "claude")
            eng = menu.addMenu("Engine")
            for pid in PROVIDER_IDS:
                act = eng.addAction(PROVIDER_LABELS.get(pid, pid))
                act.setCheckable(True)
                act.setChecked(pid == cur)
                act.triggered.connect(lambda _=False, p=pid: self._set_provider(p))
        except Exception:
            pass
        # Health: the four strip cells (connection · memory · project · job)
        # as disabled facts, built from the same producer the strip used
        # (health_strip.build_cells over the last context facts + O(1)
        # in-process reads). Never the doctor, never a main-thread hold.
        try:
            from synapse.panel import health_strip as _hs
            conn, proj = getattr(self, "_health_facts", (_hs.UNMEASURED, _hs.UNMEASURED))
            health = menu.addMenu("Health")
            for cell in _hs.build_cells(_hs.gather_snapshot(connection=conn, project=proj)):
                fact = health.addAction("%s   %s" % (cell.label, cell.value))
                fact.setEnabled(False)
                if cell.reason:
                    fact.setToolTip(cell.reason)
        except Exception:
            pass
        menu.addSeparator()
        menu.addAction("Larger text", self._cycle_font_scale)
        menu.addAction("Default text", lambda: self._set_scale(self._chrome_scale))
        menu.addAction("Help", self._on_help)

        # ── H3b · interruption controls (R29 §2: the halt belongs in the
        # overflow, NOT in the rail competing with Stop). Stop aborts the agent
        # LOOP; these reach the WORK Houdini is already doing. Three different
        # verbs, three different consequences — never collapsed into one button.
        if DirectToolCall is not None:
            menu.addSeparator()
            node = getattr(self, "_last_tool_node", None)

            # Cancel cook — state-gated exactly like Stop. An always-enabled
            # cancel with nothing to cancel is the same lie as a consent gate
            # that does not gate (R18).
            cook_act = menu.addAction(
                "Cancel cook  —  %s" % node if node else "Cancel cook")
            cook_act.setEnabled(bool(node) and bool(self._was_busy))
            cook_act.triggered.connect(self._on_cancel_cook)
            if not node:
                cook_act.setToolTip(
                    "No cooking node in flight. SYNAPSE only offers this when "
                    "it knows which node to cancel.")

            halt_act = menu.addAction("Emergency halt…")
            halt_act.triggered.connect(self._on_emergency_halt)
            halt_act.setToolTip(
                "Cancel PDG cooks under /obj and capture a session report. "
                "Does NOT stop background renders — those are reported back "
                "so you can stop them explicitly.")
        return menu

    # ── H3b · cook cancel + emergency halt ──────────────────────────────
    # These are DISTINCT from _on_stop, which is unchanged and stays as
    # written: it aborts the agent loop cooperatively and refuses to claim
    # idle. Stop ends the conversation's work; these two reach into Houdini.

    def _run_direct_tool(self, tool_name, arguments, busy_text, done_key=None):
        """Fire one named tool off the UI thread and report what happened.

        Never claims success from the click. The header says what was
        requested; the result message says what the server actually did.
        """
        if DirectToolCall is None:
            self._chat.append_system_message(
                "That control isn't available — the direct-tool transport "
                "didn't load.")
            return
        if self._direct_call is not None and self._direct_call.isRunning():
            self._set_header("working", "Still %s…" % busy_text)
            return
        self._set_header("working", "%s…" % busy_text)
        call = DirectToolCall(tool_name, arguments, parent=self)
        call.finished_ok.connect(
            lambda res: self._on_direct_tool_done(tool_name, res, done_key))
        call.failed.connect(lambda msg: self._on_direct_tool_failed(tool_name, msg))
        self._direct_call = call
        call.start()

    def _display_recall_result(self, result):
        card = getattr(self, "_recall_card", None)
        if card is not None:
            card.set_result(result)
            card.show()

    def _on_direct_tool_done(self, tool_name, result, done_key=None):
        if tool_name == "synapse_recall":
            self._display_recall_result(result)
        # Law 3 — report the server's own status verbatim rather than assuming
        # the click did anything. `noop`, `unmappable` and `ambiguous` are all
        # honest outcomes and none of them is a success.
        status = None
        note = None
        if isinstance(result, dict):
            status = result.get("status")
            note = result.get("note")
        parts = ["%s → %s" % (tool_name, status or "done")]
        if note:
            parts.append(note)
        try:
            self._chat.append_system_message("  ".join(parts))
        except Exception:
            pass
        self._set_header("done", status or "Done")

    def _on_direct_tool_failed(self, tool_name, msg):
        try:
            self._chat.append_system_message(
                "%s didn't go through: %s" % (tool_name, msg))
        except Exception:
            pass
        self._set_header("done", "Not cancelled")

    def _on_cancel_cook(self):
        node = getattr(self, "_last_tool_node", None)
        if not node:
            # Refuse rather than guess a target. Cancelling the wrong network
            # is worse than not cancelling.
            try:
                self._chat.append_system_message(
                    "I don't know which node to cancel — no cooking node is "
                    "in flight right now.")
            except Exception:
                pass
            return
        # NOTE the unprefixed name: tops_* tools register WITHOUT the
        # "synapse_" prefix (mcp/_tool_registry.py). Guessing the prefix here
        # would have produced a control that looked wired and 404'd at runtime.
        self._run_direct_tool(
            "tops_cancel_cook", {"node": node},
            "Cancelling the cook on %s" % node)

    def _on_emergency_halt(self):
        self._run_direct_tool(
            "synapse_emergency_halt",
            {"reason": "Artist triggered emergency halt from the panel"},
            "Emergency halt")

    def _set_scale(self, scale):
        """The Aa control scales CONTENT only — the dialogue and the prompt.
        Chrome (header, labels, pills, buttons, palette) was built once at the
        host UI size and is deliberately NOT rebuilt here, so the panel never
        jumps or reflows when the artist changes reading size."""
        self._font_scale = scale
        self._apply_content_scale()

    def _apply_content_scale(self):
        """Push the content font-scale to the two surfaces the artist reads and
        writes: the chat document default (dialogue + streamed tokens) and the
        prompt input. Document fonts keep content scaling independent of the
        root chrome stylesheet. Defensive: safe before either is built."""
        sc = self._font_scale
        chat = getattr(self, "_chat", None)
        if chat is not None and hasattr(chat, "font_scale"):
            try:
                chat.font_scale = sc
            except Exception:
                pass
        inp = getattr(self, "_input", None)
        if inp is not None:
            try:
                self._set_prompt_font(inp, sc)
            except Exception:
                pass

    @staticmethod
    def _set_prompt_font(inp, scale):
        font = QtGui.QFont(inp.font())
        font.setPixelSize(max(t.FONT_FLOOR_PX, t.scaled(t.SIZE_UI, scale)))
        inp.document().setDefaultFont(font)
        selection = inp.textCursor()
        content = QtGui.QTextCursor(inp.document())
        content.select(QtGui.QTextCursor.Document)
        fmt = QtGui.QTextCharFormat()
        fmt.setFont(font)
        content.mergeCharFormat(fmt)
        inp.setTextCursor(selection)
        inp.setCurrentFont(font)

    def _cycle_font_scale(self):
        """Step through the font-scale presets live. The overflow's 'Larger
        text' is its one surface (bc-wave BC-1: the 'Aa' verb was a duplicate
        signal and left with the verb rail; tests/panel/test_font_scale.py
        pins the stepping rule, so the method stays)."""
        self._set_scale(t.next_font_scale(getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT), getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT)))

    def _open_palette(self):
        try:
            from synapse.panel.tool_palette import ToolPalette
            pal = getattr(self, "_palette", None)
            if pal is None:
                pal = ToolPalette(self, scale=getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT))
                pal.command_selected.connect(self._on_tool_picked)
                pal.cancelled.connect(self._input.setFocus)
                self._palette = pal
            elif not pal.isVisible():
                pal.reset_search()
            # anchor to the input (the ⌘K button is gone — "/" in the input and
            # Ctrl+K are the triggers now)
            self._position_popup(pal, getattr(self, "_input", None))
            pal.show()
            pal.raise_()
            pal.activateWindow()
        except Exception:
            # Palette unavailable — fall back to focusing input.
            self._input.setFocus()

    def _position_popup(self, popup, anchor):
        """Place a Qt.Popup the SideFX way: anchored to the widget that opened
        it, on that widget's screen, fully visible. The palette is tall and the
        input row sits low in the panel, so prefer opening UPWARD from the anchor
        — falling back to downward only when there's no room above."""
        popup.adjustSize()
        sz = popup.size()
        if sz.width() < popup.minimumWidth() or sz.height() < popup.minimumHeight():
            sz = popup.minimumSize()
        # bc-wave repair (CRUX 2026-09-05, 'palette rows cut mid-word'):
        # adjustSize() shrinks the palette to its sizeHint (~256, the
        # QAbstractScrollArea default) - narrower than the dock that opened
        # it, so rows lost 80px for nothing. The popup takes the panel's
        # width (prepare_sweep_b_popup still caps it at the opener on show).
        if sz.width() < self.width():
            sz = QtCore.QSize(self.width(), sz.height())
            popup.resize(sz)
        ref = anchor if anchor is not None else self
        try:
            screen = ref.screen()
        except Exception:
            screen = None
        if screen is None:
            screen = QtWidgets.QApplication.primaryScreen()
        avail = screen.availableGeometry()
        # never let the popup exceed the screen, or the on-screen clamp below
        # would invert (top > bottom) and push a too-tall popup partly off the
        # display. The minimum size is already screen-clamped at construction;
        # this caps the adjustSize() result too.
        if sz.width() > avail.width() or sz.height() > avail.height():
            sz = QtCore.QSize(min(sz.width(), avail.width()),
                              min(sz.height(), avail.height()))
            popup.resize(sz)
        if anchor is not None:
            tl = anchor.mapToGlobal(QtCore.QPoint(0, 0))
            x = tl.x()
            y = tl.y() - sz.height() - 6            # open above the button
            if y < avail.top():
                y = tl.y() + anchor.height() + 6    # no room above → below
            # a dock-wide popup anchored at the input's x would spill past
            # the dock's right edge by the gutter: keep it inside the panel.
            right = self.mapToGlobal(QtCore.QPoint(self.width(), 0)).x()
            x = max(self.mapToGlobal(QtCore.QPoint(0, 0)).x(), min(x, right - sz.width()))
        else:
            cur = QtGui.QCursor.pos()
            x, y = cur.x(), cur.y()
        # clamp fully on-screen — SideFX popups never spill off the display
        x = max(avail.left(), min(x, avail.right() - sz.width()))
        y = max(avail.top(), min(y, avail.bottom() - sz.height()))
        popup.move(int(x), int(y))

    def _on_tool_picked(self, prompt):
        """Dispatch the selected command or prompt through the existing handler."""
        self._send(prompt)

    def _open_lookdev_suggestion(self):
        card = getattr(self, "_lookdev_suggestion", None)
        if card is not None:
            self._set_face("direct")
            self._converse_stack.setCurrentIndex(0)
            card.request()

    def _prepare_lookdev_prompt(self, draft):
        """Prepare text only. Sending remains the artist's separate action."""
        if not isinstance(draft, str) or not draft:
            return
        existing = self._input.toPlainText().rstrip()
        self._input.setPlainText(existing + "\n\n" + draft if existing else draft)
        self._input.setFocus()

    def _refresh_events(self, snapshot):
        button = getattr(self, "_events_btn", None)
        controller = getattr(self, "_notification_controller", None)
        if button is None or controller is None:
            return
        policy = controller.journal.get_policy()
        unread = sum(1 for entry in snapshot["entries"] if entry["unread"])
        button.setText("Events · quiet" if policy["quiet"] else
                       ("Events (%d)" % unread if unread else "Events"))
        button.setToolTip("%d unread local updates. History is kept in this Houdini process." % unread)

    def _open_notifications(self):
        controller = getattr(self, "_notification_controller", None)
        if controller is None:
            self._chat.append_system_message("Local Events is unavailable in this host.")
            return
        dialog = getattr(self, "_notifications_dialog", None)
        if dialog is None:
            from synapse.panel.notifications import NotificationsDialog
            dialog = NotificationsDialog(controller, self, open_connections=self._open_connections)
            self._notifications_dialog = dialog
        dialog.refresh()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _open_saved_recipes(self):
        from synapse.host.saved_networks import SavedNetworkService
        from synapse.host.recipe_watch import RecipeWatch
        from synapse.panel.saved_recipes import SavedRecipesDialog
        watch = getattr(self, "_recipe_watch", None)
        if watch is None:
            self._recipe_service = SavedNetworkService()
            import weakref
            reference = weakref.ref(self)
            def notify(result):
                def deliver():
                    panel = reference()
                    if panel is not None:
                        try:
                            panel._chat.append_system_message(result["message"])
                        except RuntimeError:
                            pass  # QObject may have been destroyed after queuing
                QTimer.singleShot(0, deliver)
            watch = RecipeWatch(self._recipe_service, notify)
            self._recipe_watch = watch
            self.destroyed.connect(lambda *_args, owner=watch: owner.close(notify=False))
        dialog = getattr(self, "_saved_recipes_dialog", None)
        if dialog is None:
            dialog = SavedRecipesDialog(self, self._recipe_service, watch,
                                        busy=lambda: bool(_ACTIVE_PANEL_WORKERS))
            self._saved_recipes_dialog = dialog
        else:
            dialog.refresh()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def _on_submit(self):
        text = self._input.toPlainText().strip()
        if text:
            if self._send(text):
                self._input.clear()

    def _send(self, text):
        if (text or "").strip().lower() == "/events":
            self._open_notifications()
            return True
        if (text or "").strip().lower() == "/saved-recipes":
            self._open_saved_recipes()
            return True
        if (text or "").strip().lower() == "/lookdev-suggestion":
            self._open_lookdev_suggestion()
            return True
        if _ACTIVE_PANEL_WORKERS:
            self._chat.append_system_message(
                "A SYNAPSE panel task is still running on this workstation. Wait for it to finish before starting another.")
            return False
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.isRunning():
            self._chat.append_system_message("Still working on the last task. Stop it first, or wait.")
            return False
        # W7-SESSCOPE: /restore-session brings back the conversation parked by
        # a fresh-boot scoped load. Panel-local, never reaches the model.
        if (text or "").strip().lower() in ("/restore-session", "/restore_session"):
            self._restore_previous_session()
            return True
        if ClaudeWorker is None:
            self._chat.append_system_message("The chat worker is unavailable in this build.")
            return False
        try:
            from synapse.model_access import capture_scope
            accepted_scope = capture_scope()
            connection = self._prepare_connection()
            connection = self._route_connection(connection, text)
            connection.provider._model_scope = accepted_scope
        except (ValueError, RuntimeError) as exc:
            if "connection" in locals():
                connection.release()
            self._chat.append_system_message(str(exc))
            return False
        except Exception:
            if "connection" in locals():
                connection.release()
            self._chat.append_system_message("Could not prepare this model. Open Connect models to check the selection.")
            return False
        if not connection.provider.resolve_key():
            connection.release()
            self._chat.append_system_message("Connect a model before sending. Use Connect models below the prompt.")
            return False
        try:
            allowed = self._allow_connection(connection)
        except RuntimeError as exc:
            connection.release()
            self._chat.append_system_message(str(exc))
            return False
        if not allowed:
            connection.release()
            return False
        self._task_connection = connection
        self._permission_connections[:] = [connection]
        self._last_task_facts = connection.facts
        self._chat.append_system_message(getattr(connection.provider, "_route_reason", connection.facts.description))
        # Submitting is the artist handing off — drop input focus. The last
        # turn's receipt goes with it (bc-wave BC-6a): a new turn, a new record.
        self._hide_turn_receipt()
        if getattr(self, "_input", None) is not None:
            self._input.clearFocus()
        display = text
        pending = list(self._pending_context)
        if self._pending_context:
            text = "[Context: %s]\n%s" % (", ".join(self._pending_context), text)
            self._pending_context = []
        try:
            self._chat.append_user_message(display)
        except Exception:
            pass
        self._messages.append({"role": "user", "content": text})
        try:
            self._start_worker()
        except Exception:
            connection.release()
            self._pending_context = pending
            self._on_error("The task could not start. Your draft is still available.")
            self._messages.pop()
            return False
        self._refresh_engine_selector()
        return True

    def _announce_parked(self):
        """W7-SESSCOPE: tell the artist their previous-boot work is parked, not
        gone. Fires once via singleShot after the UI exists. Best-effort."""
        try:
            self._chat.append_system_message(
                "Previous session from your last Houdini boot was parked - "
                "type /restore-session to bring it back.")
        except Exception:
            pass

    def _restore_previous_session(self):
        """W7-SESSCOPE: swap the parked previous-boot conversation back in as
        the live context. Display continues from here (full re-render of old
        turns is docketed); the model sees the complete restored history."""
        try:
            from synapse.server import session_store as _session_store
            restored = _session_store.restore_previous_conversation()
        except Exception:
            restored = []
        try:
            if restored:
                self._messages = restored
                self._parked_previous = False
                self._chat.append_system_message(
                    "Restored %d messages from the previous session - context "
                    "is live; new replies continue from that history." % len(restored))
            else:
                self._chat.append_system_message("No parked previous session to restore.")
        except Exception:
            pass

    def _build_system_prompt(self):
        """SYNAPSE's identity + the 'act via tools, don't narrate' steering.
        The redesigned panel dropped this — with an empty system prompt the
        model EXPLAINS build requests instead of executing them (the artist
        sees 'processing… text, no nodes'). Reads live scene context on the
        main thread (this runs from the send handler), all best-effort."""
        overlay = getattr(self, "_system_prompt_overlay", "") or ""
        try:
            from synapse.panel.system_prompt import build_system_prompt
        except Exception:
            return overlay
        ctx = {}
        try:
            import hou
            net = "/obj"
            try:
                pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
                if pane is not None and pane.pwd() is not None:
                    net = pane.pwd().path()
            except Exception:
                pass
            ctx = {
                "network": net,
                "selection": [n.path() for n in hou.selectedNodes()],
                "frame": int(hou.frame()),
                "hip": hou.hipFile.basename(),
            }
        except Exception:
            ctx = {}
        try:
            base = build_system_prompt(ctx)
        except Exception:
            return overlay
        # L5-2: the active profile's overlay rides on top of the built prompt —
        # tone/pacing only, never capability (L5/L6).
        return (base + "\n\n" + overlay) if overlay else base

    def _start_worker(self):
        connection = getattr(self, "_task_connection", None)
        if connection is None:
            raise RuntimeError("A panel task needs an approved connection.")
        # Addendum 3.6 (2026-09-05): never a second worker into the same
        # transcript. While one streams, a new turn (send, revert) waits.
        w = getattr(self, "_worker", None)
        if w is not None and hasattr(w, "isRunning") and w.isRunning():
            logger.warning("panel: _start_worker refused - a turn is still streaming")
            try:
                self._chat.append_system_message(
                    "Still working on the last turn - Stop it first, or wait.")
            except Exception:
                pass
            return False
        if ClaudeWorker is None:
            try:
                self._chat.append_system_message(
                    "We hit a snag — the chat worker isn't available in this build."
                )
            except Exception:
                pass
            return
        self._stream_buf = []
        self._streaming_started = False
        self._turn_tools = []        # P2: fresh turn — the result surface's producer
        self._last_tool = None       # C8: fresh run — no stale in-flight tool name
        self._set_thinking(True)
        self._set_busy(True)
        # FRZ probe 1 (SEND). All of this runs on the main thread the instant the
        # artist presses send: get_anthropic_tools(), _build_system_prompt() (which
        # does unmarshalled hou.* reads), _make_provider(), and ClaudeWorker.__init__
        # — whose `copy.deepcopy(messages)` (claude_worker.py:99) deep-copies every
        # prior tool_result payload of the session on THIS thread. Cost therefore
        # grows with conversation length, which is the scaling law payload_chars is
        # here to expose.
        # SIZE PROXY, deliberately cheap: payload_chars carries the conversation's
        # MESSAGE COUNT here, not a character count. Summing len(str(m)) over the
        # history would cost O(conversation) on the very thread being measured —
        # an instrument that costs as much as the thing it measures corrupts its
        # own reading. Turn count is O(1) and is the axis deepcopy cost scales on.
        with _timed_phase("send") as _frz_send:
            _frz_send.set_sizes(payload_chars=len(self._messages or ()))
            tools = get_anthropic_tools() if get_anthropic_tools else None
            system = self._build_system_prompt()
            # Interactive panel — the artist is in the loop for creative intent,
            # but the WORKER (an LLM) may not self-authorize gated ops.
            # Joe DECIDE 2026-08-18 (ENG-INJ-GATE-OFF): consent posture = ON.
            # The worker-policy allowlist (denies review/approve/critical gates:
            # execute_python/execute_vex, delete_node, renders, exports, prunes,
            # PDG cooks — fails closed on unknown tools) now binds this path too.
            # Gated ops happen in the native Houdini UI or via a bridge /mcp
            # consent-gated call, not through the panel worker.
            self._worker = ClaudeWorker(self._messages, system_prompt=system,
                                        tools=tools, parent=None,
                                        enforce_worker_policy=True,
                                        provider=connection.provider)
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_done.connect(self._on_done)
        self._worker.stream_error.connect(self._on_error)
        if self._tool_executor is not None:
            self._worker.tool_requested.connect(self._tool_executor.execute_tool)
        self._worker.tool_status.connect(self._on_tool_status)
        self._worker.render_receipt.connect(self._on_render_receipt)
        self._worker.integrity_updated.connect(self._on_integrity)
        self._worker.activity_changed.connect(self._on_activity)
        # Capture THIS binding, never a later selection. Release only when the
        # worker thread has actually finished (including close/headless finish).
        # Qt does not keep this plain Python bound-method receiver alive. The
        # panel can drop it in stream_done before the queued finished callback.
        from functools import partial
        self._worker.finished.connect(partial(type(connection).release, connection))
        self._worker.finished.connect(self._on_worker_thread_finished, Qt.QueuedConnection)
        self._worker.finished.connect(partial(_release_panel_worker, self._worker))
        _ACTIVE_PANEL_WORKERS.add(self._worker)
        self._worker.start()

    def _on_activity(self, text):
        face = getattr(self, "_work_face", None)
        if face is not None:
            face.set_activity(text)

    def _on_worker_finished(self, worker, connection):
        # Aborting intentionally omits stream_done in the existing worker.
        # The thread's terminal event is still authoritative for UI cleanup.
        if (worker is not getattr(self, "_worker", None)
                or getattr(self, "_task_connection", None) is not connection):
            return
        if getattr(worker, "_abort", False):
            self._on_done()
            self._chat.append_system_message("Stopped this task. An operation already sent to Houdini may still be finishing.")
        else:
            self._on_error("The task ended without a completion receipt.")

    def _on_worker_thread_finished(self):
        worker = self.sender()
        connection = getattr(self, "_task_connection", None)
        if connection is not None and worker is getattr(self, "_worker", None):
            self._on_worker_finished(worker, connection)

    def _on_token(self, tok):
        if not getattr(self, "_streaming_started", False):
            # first token: the toy hands off to live streaming text
            self._streaming_started = True
            self._set_thinking(False)
            try:
                self._chat.begin_stream()
            except Exception:
                pass
        self._stream_buf.append(tok)
        try:
            # FRZ probe 2 (STREAM). Fires once per SSE delta, so this is recorded as
            # an AGGREGATE — the module accumulates count/sum/max and only logs a
            # line when a single delta crosses the slow threshold. A per-call log at
            # token cadence would itself become the freeze.
            with _timed_phase("stream", payload_chars=len(tok or "")):
                self._chat.stream_chunk(tok)
        except Exception:
            pass

    def _on_done(self):
        sender = getattr(self, "sender", lambda: None)()
        if (sender is not None and ClaudeWorker is not None and isinstance(sender, ClaudeWorker)
                and sender is not getattr(self, "_worker", None)):
            return
        text = "".join(self._stream_buf).strip()
        connection = getattr(self, "_task_connection", None)
        if connection is not None:
            connection.revoke()
        signed = connection.spec.identity if connection else self._author_token()
        if getattr(self, "_streaming_started", False):
            # finalize the live stream → fully formatted (links, code blocks)
            try:
                # FRZ probe 3 (FINALIZE) — the fattest single main-thread event on
                # the result path: removeSelectedText over the whole streamed span,
                # then the four-regex formatter, then a full insertHtml re-layout.
                # NOTE: this phase strictly CONTAINS the "append" phase recorded
                # inside ChatDisplay.append_synapse_message; the two are nested, not
                # disjoint, and must not be summed.
                with _timed_phase("finalize", payload_chars=len(text or "")):
                    self._chat.end_stream(text if text else None, signed=signed)
            except Exception:
                pass
        else:
            # no text tokens (e.g. a tool-only turn) → just stop + append
            self._set_thinking(False)
            if text:
                try:
                    self._chat.append_synapse_message(text, signed=signed)
                except Exception:
                    pass
        if self._worker is not None:
            try:
                messages = self._worker.get_terminal_messages()
                if messages is not None:
                    self._messages = messages
            except Exception:
                pass
        # Session survival (R.2): persist the completed transcript so a reopen —
        # even one after the panel was closed while this turn finished headless —
        # restores the full conversation. Best-effort; disk-keyed by HIP.
        try:
            from synapse.server import session_store as _session_store
            _session_store.save_conversation(self._messages)
        except Exception:
            pass
        self._set_busy(False)
        # bc-wave BC-6a (F11): a quiet turn that CHANGED the scene leaves an
        # artist-clickable REVERT on the CHAT surface - the turn receipt,
        # counted from the same evidence the Work face credits.
        # Best-effort like every seam in this method: a completion must never
        # fail on the receipt (duck-typed completions carry no slot).
        try:
            credit = self._turn_evidence()[0]
            if credit:
                self._show_turn_receipt(len(credit))
            else:
                self._hide_turn_receipt()
        except Exception:
            pass
        # BP2-PANELTRUTH T2 / W5-PANEL item 3: the completed task's real token
        # receipt (usage_sink) now lands on the TOKEN face + the rail meter/pill
        # — event-driven from completion here, NEVER a QTimer (V3: a probe must
        # not trip the rate limit it reports on). Best-effort; never breaks the
        # completion path.
        self._refresh_token_surfaces()
        self._task_connection = None
        self._worker = None
        self._refresh_engine_selector()

    def _refresh_token_surfaces(self):
        """Push the last task's per-task token receipt (usage_sink) onto the
        TOKEN face and the rail meter + pill on TASK COMPLETION.

        Called from _on_done only — event-driven, never a timer (V3; the TOKEN
        face is likewise refreshed on OPEN, see _show_token_face). UNKNOWN stays
        UNKNOWN: an unmeasured task leaves the meter empty and the pill at its
        base label, never a fabricated figure and never a fuel-gauge bar (R162 /
        V3-F4). All best-effort so a completed turn never breaks on the read-out.
        The display rule is pure (token_readout); this method only supplies the
        live surfaces."""
        try:
            from synapse.panel import token_readout
        except Exception:
            return
        face = getattr(self, "_token_face", None)
        meter = getattr(self, "_meter_lbl", None)
        pills = getattr(self, "_face_pills", None)
        pill = pills.get("token") if isinstance(pills, dict) else None
        token_readout.refresh_surfaces(face=face, meter=meter, pill=pill)

    def _on_error(self, msg):
        sender = getattr(self, "sender", lambda: None)()
        if (sender is not None and ClaudeWorker is not None and isinstance(sender, ClaudeWorker)
                and sender is not getattr(self, "_worker", None)):
            return
        connection = getattr(self, "_task_connection", None)
        if connection is not None:
            connection.revoke()
        # The worker publishes this snapshot before any terminal signal. Never
        # read its live list while an error/finished event is still in flight.
        worker = getattr(self, "_worker", None)
        if worker is not None:
            try:
                messages = worker.get_terminal_messages()
                if messages is not None:
                    self._messages = messages
                    from synapse.server import session_store as _session_store
                    _session_store.save_conversation(self._messages)
            except Exception:
                pass
        self._set_thinking(False)
        if getattr(self, "_streaming_started", False):
            try:
                connection = getattr(self, "_task_connection", None)
                self._chat.end_stream("".join(self._stream_buf).strip() or None,
                                      signed=connection.spec.identity if connection else None)
            except Exception:
                pass
        try:
            self._chat.append_system_message("We hit a snag: %s" % msg)
        except Exception:
            pass
        self._set_busy(False)
        self._refresh_token_surfaces()
        self._task_connection = None
        self._worker = None
        self._refresh_engine_selector()

    def _on_tool_status(self, name, phase, _detail):
        if phase == "running":
            self._last_tool = name          # C8: remember what's in flight for Stop
            # H3b: also remember WHERE. _detail is json.dumps(tool_input)[:120]
            # — often truncated, so the reader handles fragments (direct_tool).
            if extract_node_path is not None:
                try:
                    self._last_tool_node = extract_node_path(_detail)
                except Exception:
                    self._last_tool_node = None
        verb = {"running": "running", "done": "ok", "error": "failed"}.get(phase, phase)
        # P2: accumulate what the turn actually DID. Every terminal tool result
        # is recorded once, in order, so _populate_review has something real to
        # credit. Before this the result surface had no producer at all and five
        # of its eight setters were unreachable from product code.
        if phase in ("done", "error"):
            try:
                self._turn_tools.append((name, verb, _detail))
            except Exception:
                pass
        # bc-wave BC-2: tool names no longer write the rail sentence - the
        # Work face's plan already carries them; the rail says one truth.
        wf = getattr(self, "_work_face", None)
        if wf is not None:
            wf.set_tool_status(name, verb, _detail)   # feed the plan-with-progress
        # A render's TRUTH is no longer guessed here: the RETINA T0 receipt flows
        # from the worker via render_receipt → _on_render_receipt. The old argless
        # quality-flag path is gone — it hardwired a BL-007 FAIL (empty output
        # path) beside a good render.
        # No auto-switch (same-pane law): a live tool feeds the Work face's plan
        # + the rail mark; the artist switches to Work to watch when they choose.

    def _on_stop(self):
        _revoke_model_connections(getattr(self, "_permission_connections", ()))
        # Honest Stop: abort the loop, but DO NOT claim idle — Houdini may still be
        # finishing the in-flight tool (abort is cooperative; it takes effect at the
        # next tool/iteration boundary). Stay busy and say "Stopping…"; the worker
        # emits stream_done / stream_error when it actually stops, which resets to
        # idle via _on_done / _on_error. (Cancelling the in-flight tool itself —
        # tops_cancel_cook / render cancel — must run off the UI thread against a live
        # bridge; deferred to the bridge-live pass, see Ledger.)
        if self._worker is not None:
            self._worker.abort()
        self._stop_btn.setEnabled(False)    # the press registered — avoid a confusing re-press
        # bc-wave BC-2: the sentence says 'Stopping…' (inside its floor); the
        # in-flight tool it waits on is named in the sentence's tooltip and
        # on the Work face's plan, never as rail text that would elide.
        self._stopping = True
        self._header_status.setToolTip(
            "Waiting on %s" % (self._last_tool or "the current tool"))
        self._set_header("working", _STOPPING_PHRASE)

    def _set_busy(self, busy):
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._stop_btn.setVisible(busy)   # Stop is state-gated to working only
        self._connect_btn.setVisible(not busy)   # Connect | Stop share one slot
        # state→Work-sub-state edges. Quiet state never moves the visible face
        # (v9.1 · only an ACTIONABLE consent gate auto-surfaces — see
        # _on_gate_raised). A new work cycle shows the cook sub-state; finishing
        # fills the done payoff and lifts the RAIL MARK to 'done' as the quiet
        # ready-result signal (a plain answer never changes the view).
        if busy and not self._was_busy:
            self._stopping = False
            self._turn_state = "working"
            self._set_work_substate("cook")
        elif not busy and self._was_busy:
            # FRZ probe 4 (REVIEW). Last main-thread work of the turn and the only
            # one that destroys and rebuilds widgets (face_review._clear → takeAt +
            # setParent(None) + deleteLater per row), so it is the natural suspect
            # for a tail stall that reads as "and then it recovers".
            with _timed_phase("review"):
                self._populate_review()  # fill verdict + provenance for the payoff
            self._set_work_substate("done")
            self._stopping = False
            self._turn_state = "done"
        elif busy:
            self._turn_state = "working"
        else:
            self._turn_state = "idle"
        self._was_busy = busy
        self._render_state()

    def _render_state(self):
        """The rail's one sentence, from the panel's state (bc-wave BC-2).

        Precedence: a turn in flight (working / stopping) > a finished turn
        (done: 'Result ready') > the connection truth at rest (disconnected
        'Not connected' / warning 'Worth a look' / connected 'Ready'). The
        idle phrase is never shown on its own - at rest the truth IS the
        connection, so boot reads exactly STATUS['disconnected'] and nothing
        else says 'nothing yet' (F14). Every phrase is inside the sentence's
        floor, so it never elides.

        joe-five J1: one status decision, then the two readouts that share
        it — the mark + sentence (``_set_header``) and the model token's
        liveness colour (``_render_token_state``). Every context tick lands
        here, so the token can never hold a stale green."""
        if getattr(self, "_was_busy", False):
            status = "working"
            phrase = _STOPPING_PHRASE if getattr(self, "_stopping", False) else None
        elif getattr(self, "_turn_state", "idle") == "done":
            status, phrase = "done", _DONE_PHRASE
        else:
            status = getattr(self, "_conn_state", "disconnected")
            if status not in t.STATUS:
                status = "disconnected"
            phrase = None
        self._set_header(status, phrase)
        self._render_token_state()

    def _render_token_state(self):
        """The model token is a status light (Joe's word, RULING_JOE_FIVE.md
        J1, 2026-09-05; supersedes RULING_DIRECTION_BC.md Addendum 3.3).

        The token says WHICH engine is thinking; that is state, and state has
        colour in this panel. Its colour is the engine's liveness, decided
        from the panel's OWN state — the same signal the mark and Connect
        read (``_apply_context`` → ``_render_state``, ``_set_busy`` →
        ``_render_state``) — so it is never a stale green:

          working  a turn is streaming            → WARM (the mark's busy note)
          live     Houdini connected (or 'warning': reachable, gate stale)
                   AND the engine is keyed         → CONIFEROUS
          off      not connected, or no key for the engine → TEXT_DISABLED

        'Keyed' is ``_engine_keyed`` from ``_refresh_engine_selector`` (the
        provider's own ``resolve_key()``; env / .env only, never a network
        probe — this is not a daemon liveness check). The state is written as
        the dynamic property ``liveness`` (qss.py paints it); unpolish/polish
        only when the value moves, so an idle context tick costs nothing. The
        tooltip carries the reason when off. Display only — never authored
        to USD. Safe before the rail exists (no-op)."""
        lbl = getattr(self, "_author_lbl", None)
        if lbl is None:
            return
        conn = getattr(self, "_conn_state", "disconnected")
        reachable = conn in ("connected", "warning")
        if getattr(self, "_was_busy", False):
            state, reason = "working", None
        elif reachable and getattr(self, "_engine_keyed", False):
            state, reason = "live", None
        elif not reachable:
            state, reason = "off", "Not connected"
        else:
            pid = (getattr(self, "_provider_id", "claude") or "claude").strip().lower()
            state, reason = "off", "No key for %s" % pid
        tip = "Engine & model - click to switch"
        detail = getattr(self, "_model_connection_detail", "")
        if detail:
            tip += "\n\n" + detail
        lbl.setToolTip(tip if reason is None else "%s\n%s" % (tip, reason))
        if lbl.property("liveness") != state:
            lbl.setProperty("liveness", state)
            try:
                st = lbl.style()
                st.unpolish(lbl)
                st.polish(lbl)
            except Exception:
                pass

    def _set_header(self, status, phrase=None):
        """Low-level writer: the mark takes ``status``; the sentence takes
        ``phrase`` (default: the STATUS phrase for ``status``)."""
        if phrase is None:
            phrase = t.STATUS.get(status, ("", "", ""))[2]
        self._mark.set_state(status)
        self._header_status.setText(phrase)
        if status != "working":
            self._header_status.setToolTip("")

    def _update_context(self):
        """Refresh the context ribbon + connection footer — OFF the Qt/main thread.

        W2-S5: the three live reads (``hou.frame()`` / ``hou.selectedNodes()`` /
        ``hou.hipFile.basename()``) used to run INLINE here on the Qt/main thread,
        unmarshalled — the W1-MTFIX crash-path class. They now run via
        ``ws_bridge.gather_context_off_main`` (a daemon thread → ``run_on_main``
        DEFERRED path, bounded + interleaved with UI events), and the result is
        marshalled back to the Qt thread through the ``_context_ready`` queued
        signal, where ``_apply_context`` renders the ribbon + health strip.

        ``import hou`` below is the availability guard ONLY — it makes no data
        read; the standalone message is unchanged. Content, cadence (2s), and
        consumers are identical to before; only the thread the reads run on
        changed. On a busy main thread the gather sheds and the last-rendered
        ribbon is kept (advisory), mirroring the poll/send freeze-hardening.
        """
        try:
            from synapse.panel import health_strip as _hs
            _unmeasured = _hs.UNMEASURED
        except Exception:
            _unmeasured = None
        try:
            import hou  # noqa: F401 — availability guard only (see docstring);
            # the three data reads run off-main in gather_context_off_main below.
        except Exception:
            self._ctx_label.setText("standalone — no Houdini")
            self._update_health_strip(_unmeasured, _unmeasured)  # no hou → cells stay UNKNOWN
            return
        try:
            from synapse.panel.ws_bridge import gather_context_off_main
        except Exception:
            return  # ws_bridge unavailable → keep the last-rendered ribbon
        gather_context_off_main(self._context_ready.emit)

    def _apply_context(self, ctx):
        """Render the ribbon + health strip from an off-main context gather.

        Runs on the Qt/main thread (queued ``_context_ready`` delivery), so this
        is the ONLY place the tick touches Qt widgets. ``ctx`` is the dict from
        ``ws_bridge._gather_context_on_main_thread`` — keys ``selected_nodes``
        (node paths), ``current_network``, ``scene_file`` (full path), ``frame``
        (float). The ribbon/strip content is byte-identical to the former inline
        computation: ``scene_file`` basename == ``hipFile.basename()`` and the
        first selection's parent path == ``sel[0].parent().path()`` were both
        confirmed on live H22.0.400 (W2-S5 probe).
        """
        try:
            from synapse.panel import health_strip as _hs
            _unmeasured = _hs.UNMEASURED
        except Exception:
            _unmeasured = None
        conn = _unmeasured
        proj = _unmeasured
        try:
            frame = int(ctx.get("frame") or 0)
            sel = ctx.get("selected_nodes") or []
            scene_file = ctx.get("scene_file") or ""
            _hip = scene_file.rsplit("/", 1)[-1] if scene_file else None
            # project / show name — the hip basename, or None when the scene is
            # untitled (a MEASURED quiet state, not the same as "not measured").
            proj = None if (not _hip or _hip == "untitled.hip") else _hip
            if sel:
                # parent path of the first selection == sel[0].parent().path()
                # (string-derived from the node path; W2-S5 live-verified).
                where = sel[0].rsplit("/", 1)[0] or "/"
                txt = "%s · %d selected · f%d" % (where, len(sel), frame)
            else:
                txt = "%s · f%d" % (_hip or "untitled.hip", frame)
            self._ctx_label.setText(txt)
            if self._gate_stale_reason:
                # M3-A: a disarmed phantom-API gate must be LOUD, not a
                # one-line console warning the week API drift peaks. The
                # sentence says 'Worth a look'; the reason rides its tooltip.
                self._conn_state = "warning"
                self._foot_dot.set_status("warning")
                self._foot_label.setText("Houdini · API gate stale")
                conn = "warning"
            else:
                self._conn_state = "connected"
                self._foot_dot.set_status("connected")
                self._foot_label.setText("Houdini")
                conn = "ok"
            # bc-wave BC-2: the connection truth reads through the ONE state
            # sentence (precedence in _render_state), not a second label.
            self._render_state()
            if conn == "warning" and not self._was_busy:
                self._header_status.setToolTip(
                    "API gate stale: %s" % self._gate_stale_reason)
        except Exception:
            pass
        self._update_health_strip(conn, proj)

    def _update_health_strip(self, connection, project):
        """Refresh the persistent health strip from cheap in-process facts.

        ``connection`` / ``project`` are what ``_update_context`` just derived;
        memory-backend and active-job are read O(1) inside ``gather_snapshot``.
        This never calls the doctor or ``get_health`` — the strip must not become
        a main-thread hold. Best-effort: any failure leaves the last-rendered
        cells untouched (never a fabricated green)."""
        # bc-wave BC-2: the strip left the rail; the facts it was fed are kept
        # here and the overflow's 'Health' submenu builds its four cells from
        # them at open time (same producer, same honesty, no rail pixels).
        self._health_facts = (connection, project)

    def _on_help(self):
        """Context-sensitive help, the way Houdini's own F1 behaves.

        Opens the artist help document (docs/help/index.html) — written for
        someone who knows Houdini and does not know Synapse. The engineering
        docs under docs/ are a different audience and are not what Help is for.
        """
        self._open_doc("docs/help/index.html")

    def _open_doc(self, rel):
        """Open a repo doc in the browser — the Houdini-help convention: a doc
        is a control, never a path the artist has to go find.

        Order is deliberate. hou.ui.showHelp is tried first so a registered
        help path renders in Houdini's own browser and the artist never leaves
        the host; QDesktopServices is the honest fallback (the doc is a real
        file on disk and every desktop can open it). Never raises: a failed
        help click must not disturb a working session.
        """
        import os
        root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))
        path = os.path.join(root, rel.replace("/", os.sep))
        try:
            import hou
            if hasattr(hou.ui, "showHelp"):
                hou.ui.showHelp(path)
                return
        except Exception:
            pass
        try:
            from qtpy import QtGui, QtCore as _QtCore
            QtGui.QDesktopServices.openUrl(_QtCore.QUrl.fromLocalFile(path))
        except Exception:
            try:
                import webbrowser
                webbrowser.open("file:///" + path.replace(os.sep, "/"))
            except Exception:
                pass

    def _register_selection_cb(self):
        """Update the context line on selection change. hou.ui is graphical-only
        and its callback API can't be probed headlessly, so we feature-detect at
        the call site (V0 at the call site) and fall back to the 2s timer (which
        uses the V1-confirmed hou.selectedNodes / hou.frame). No phantom call is
        ever made; the callback simply self-detects when running live."""
        self._sel_cb = None
        try:
            import hou
            ui = getattr(hou, "ui", None)
            if ui is not None and hasattr(ui, "addSelectionCallback"):
                self._sel_cb = lambda *_a, **_k: self._on_selection_changed()
                ui.addSelectionCallback(self._sel_cb)
        except Exception:
            self._sel_cb = None

    def _on_selection_changed(self):
        """Selection changed → refresh the context line. Guarded so a callback
        firing into a torn-down panel can never crash."""
        try:
            self._update_context()
        except Exception:
            pass

    def closeEvent(self, event):
        suggestion = getattr(self, "_lookdev_suggestion", None)
        if suggestion is not None:
            suggestion.shutdown()
        controller = getattr(self, "_notification_controller", None)
        if controller is not None:
            controller.close()
        _revoke_model_connections(getattr(self, "_permission_connections", ()))
        watch = getattr(self, "_recipe_watch", None)
        if watch is not None:
            watch.close()
            self._recipe_watch = None
            self._saved_recipes_dialog = None
        self._session_keys.clear()
        timer = getattr(self, "_location_timer", None)
        if timer is not None:
            timer.stop()
        # Remove the global selection callback so it never fires into a deleted
        # panel (dangling-ref safety).
        cb = getattr(self, "_sel_cb", None)
        if cb is not None:
            try:
                import hou
                hou.ui.removeSelectionCallback(cb)
            except Exception:
                pass
            self._sel_cb = None

        # R.2: the freeze beat is owned by a PROCESS-LIFETIME source
        # (server/runtime_beat.py), not this widget — so panel close is a
        # DELIBERATE DETACH, not a chain shutdown. Leaving the beat running is
        # what keeps the Watchdog seeing a live main thread (no false freeze on
        # the healthy runtime the artist just closed) AND keeps freeze
        # protection armed for any operation still finishing headless. The old
        # path shut the whole chain down here — that traded the R310a zombie for
        # zero protection after close. detach_panel never shuts the chain down;
        # it freshens the beat and records the detach.
        try:
            from synapse.server.runtime_beat import detach_panel
            detach_panel()
        except Exception:
            pass
        # Session survival (R.2): persist the current conversation so a reopen
        # restores it. Best-effort; disk-keyed by HIP.
        try:
            from synapse.server import session_store as _session_store
            _session_store.save_conversation(self._messages)
        except Exception:
            pass
        super().closeEvent(event)

    # ------------------------------------------------------------ drag & drop
    def dragEnterEvent(self, event):
        try:
            from synapse.panel import dnd
            if dnd.mime_is_acceptable(event.mimeData()):
                event.acceptProposedAction()
        except Exception:
            pass

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dropEvent(self, event):
        """Node-in / SOP-USD-in / files-in → add to the next request's context."""
        try:
            from synapse.panel import dnd
            mime = event.mimeData()
            added = []
            for p in dnd.extract_node_paths(mime) + dnd.extract_files(mime):
                if p and p not in self._pending_context:
                    self._pending_context.append(p)
                    added.append(p)
            if added:
                try:
                    self._chat.append_system_message(
                        "Added to context: %s — ask away." % ", ".join(added)
                    )
                except Exception:
                    pass
                self._input.setFocus()
            event.acceptProposedAction()
        except Exception:
            pass

    def _on_node_clicked(self, node_path):
        """Results-out / locate: a node link selects + frames the node in the
        Network Editor (which is native C++ and can't be a Qt drop target)."""
        try:
            from synapse.panel import dnd
            dnd.place_in_network(node_path)
        except Exception:
            pass

    def _copy_conversation(self):
        """Text-copy-out: copy the transcript as markdown for reports / LLMs."""
        try:
            from synapse.panel import dnd
            QtWidgets.QApplication.clipboard().setText(
                dnd.transcript_to_markdown(self._messages)
            )
            self._chat.append_system_message("Conversation copied as markdown.")
        except Exception:
            pass


def onCreateInterface():
    """Houdini Python Panel entry point — Houdini calls onCreateInterface()."""
    return SynapsePanel()


# Some code paths / older docs use createInterface — alias so either name works.
createInterface = onCreateInterface
