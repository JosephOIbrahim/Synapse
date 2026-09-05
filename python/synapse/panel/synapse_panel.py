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
_QUICK_ACTIONS = [
    ("Explain", "Explain what the selected nodes do and how they connect."),
    ("Fix", "Diagnose any problems with the current scene and propose fixes."),
    ("Optimize", "Suggest performance optimizations for the current network."),
]


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
        self.setPlaceholderText("Ask SYNAPSE…    ·    / for commands")
        # L5-22: no constant first-run height (the v9 132 landed the divider
        # above centre in every tall pane — Joe re-dragged it each session).
        # The height settles exactly once, via settle_height: the artist's
        # persisted drag, or centred from the pane's real size at show.
        # __init__ holds the floor because the pane's height is unknowable
        # here. Grip-drag + auto-grow behaviour unchanged.
        self._floor, self._max_h = 64, 600
        self._user_h = self._floor
        self._height_settled = False     # flips on settle_height / drag
        self._send_widget = None    # the embedded Send (attach_send)
        self.setFixedHeight(self._user_h)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        content = int(self.document().size().height()) + 18
        self.setFixedHeight(max(self._user_h, min(self._max_h, content)))

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
                self._boot_note = (
                    "Saved engine %r is unavailable — using Claude." % pid)
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
        self.setProperty("rhythm_role", "group")

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
        profile = getattr(self, "_layout_profile", DEFAULT_PROFILE)
        built = False
        if compose is not None:
            try:
                compose(self, root, get_manifest(profile))
                built = True
            except ManifestError:
                logger.exception(
                    "layout manifest %r invalid — using the v5.42.0 wiring",
                    profile,
                )
        if not built:
            root.addWidget(self._build_rail())          # mark · brand · author · Stop
            root.addWidget(self._build_context_ribbon())
            root.addWidget(self._build_mode_bar())      # the CHAT surface label (v9.1)
            root.addWidget(self._build_faces(), 1)      # dominant — the stacked faces
        self._set_face("direct")                    # rest on the CHAT surface

    # ------------------------------------------------- profile switcher (L5-4)
    def _select_profile(self, profile):
        """A profile-tab click: persist through settings, then recompose LIVE.

        ``SwitcherState`` (Qt-free, tested headless) owns selection → settings
        write → restore; this method owns the Qt half. A failed save still
        switches the session — and says so in chat, never silently.
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
        """Active-mark the selected profile pill (the _set_face idiom)."""
        for pid, pill in getattr(self, "_profile_pills", {}).items():
            pill.setProperty("active", pid == profile)
            c.repolish(pill)

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
        managed = {root.itemAt(i).widget() for i in range(root.count())}
        hidden = set()
        for _item, wdg, _stretch in prev:
            if wdg is not None and wdg not in managed:
                wdg.hide()  # dropped by the new manifest — hidden, not deleted
                hidden.add(wdg)
        self._recompose_hidden = hidden

    def _build_rail(self):
        """The persistent rail (Pentagram pass, Mile 1).

        One row of existing identity/actions, with the persistent health strip
        beneath it. Termination and live state never scroll away.
        """
        cached = self._region_cache.get("_build_rail")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        w = self._section()
        w.setObjectName("DsHeader")          # flat PANEL + 1px HAIR bottom rule
        col = QtWidgets.QVBoxLayout(w)
        # The owning widget's role supplies margins and inherited row gaps.
        # [mark]·12·[SYNAPSE] ··· [state] [author▾] [meter] [⌘K] [⋯] [Stop*]
        top = QtWidgets.QHBoxLayout()
        self._mark = c.MarkDot("idle", diameter=16)
        # brand word — 14px/TEXT_BRIGHT (comp .word); tracking lives on the
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
        # "carefully crafted using the Cohere typeface" — a designed lockup, not
        # tracked-out body text. So weight was never off the table; the rule was
        # an interpretation that hardened into a prohibition.
        #
        # Joe's call, 2026-07-27: the mark read thin and needed to sit as a
        # SOLID element at the same size. Weight alone would not do it — at 14px
        # bold with 4px tracking reads HEAVY AND SPARSE, individually bold
        # letters visually apart. Solidity is weight PLUS density:
        #   weight   400 -> 700  (a weight the reference ships)
        #   tracking BRAND 0.286em -> WORDMARK 0.16em  (~2.2px at 14px)
        #   colour   TEXT_PRIMARY -> TEXT_BRIGHT
        # Size holds at 14px. Position still carries hierarchy; weight now
        # carries presence.
        word = c.label("SYNAPSE", role="body")
        word.setProperty("role", "title")
        word.setFont(fontload.tracked_font("WORDMARK", 14, scale=self._chrome_scale,
                                           weight=600))
        self._wordmark = word
        self._header_status = c.label("Standing by", role="caption", scale=self._chrome_scale)
        self._header_status.setProperty("role", "label")
        # author token — THE engine+model click target (v9): a flat button whose
        # text is _author_token(); click opens the engine menu. Discoverability =
        # pointing-hand + hover underline + tooltip (comp shows no ▾).
        self._author_lbl = QtWidgets.QPushButton()
        self._author_lbl.setObjectName("DsAuthor")
        self._author_lbl.setFlat(True)
        self._author_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._author_lbl.setToolTip("Engine & model — click to switch")
        self._author_lbl.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        self._author_lbl.setText(self._author_token())
        self._author_lbl.clicked.connect(self._open_author_menu)
        # token meter — TOKENS ONLY, never $ (metering-deferred D4). Providers
        # don't surface usage yet, so it stays EMPTY until real usage arrives —
        # never estimated. _format_tokens is the one display rule.
        self._meter_lbl = c.label("", role="caption")
        self._meter_lbl.setObjectName("DsMeter")
        self._meter_lbl.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        self._session_tokens = 0
        # quiet ⌘K affordance — the palette is already bound (QShortcut); this
        # only makes it discoverable, restyled as a bordered chip (comp .cmdk;
        # 11px = the L2 chrome floor). Its text is set from the ACTUAL bound
        # QKeySequence after the shortcut is created (platform-correct, never
        # lies about the key).
        self._palette_hint = c.label("", role="caption")
        self._palette_hint.setObjectName("DsKHint")
        self._palette_hint.setFont(fontload.tracked_font(
            "DATA", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        overflow = c.Button("⋯", variant="ghost")
        overflow.setFixedWidth(32)
        overflow.clicked.connect(self._show_overflow)
        self._stop_btn = c.Button("Stop", variant="danger")
        # L5-20: the mark (MarkDot.set_halt_handler) and this button are two
        # surfaces of ONE Stop -- #DsStop paints it in the mark's warm note,
        # not the danger outline, so the pair reads as a single control.
        self._stop_btn.setObjectName("DsStop")
        self._stop_btn.setMinimumWidth(64)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setVisible(False)   # state-gated: shown only while working
        top.addWidget(self._mark)
        top.addWidget(word)
        top.addStretch(1)
        top.addWidget(self._header_status)
        top.addWidget(self._meter_lbl)
        top.addWidget(self._palette_hint)
        top.addWidget(overflow)
        top.addWidget(self._stop_btn)     # termination never scrolls away

        # Existing connection/corpus controls join the same header row.
        bot = top  # one header row; the persistent health strip remains below
        self._foot_dot = c.StatusDot("disconnected")
        self._foot_label = c.label("Not connected", role="caption", scale=self._chrome_scale)
        self._foot_label.setProperty("role", "caption")
        # Force-connect the bridge server (the hwebserver serving /synapse for
        # external MCP clients + the /mcp endpoint the tool executor uses). The
        # panel's chat runs in-process, but tools + external tools need this up,
        # and it does NOT auto-start — this button is the one-click way to force
        # it without dropping into Houdini's Python Shell.
        # Houdini-help convention: the doc is a control, not a path to go
        # find. Ghost so it reads as chrome; opens in the OS browser.
        self._help_btn = c.Button("?", variant="ghost")
        self._help_btn.setAccessibleName("Open documentation")
        self._help_btn.setToolTip("Open docs/studio/UPGRADE.md")
        self._help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._help_btn.clicked.connect(self._on_help)
        self._connect_btn = c.Button("Connect", variant="primary")
        self._connect_btn.setToolTip(
            "Start the Synapse bridge server (port 9999) so external / MCP tools "
            "can reach Houdini. Safe to click anytime — idempotent."
        )
        self._connect_btn.clicked.connect(self._on_connect)
        # Activate the H21 documentation corpus so Solaris assembly grounds in
        # real Houdini-21 docs (verified node types / parm names) instead of
        # phantom APIs. Mirrors the Connect button; idempotent.
        self._corpus_btn = c.Button("Corpus", variant="primary")
        self._corpus_btn.setToolTip(
            "Connect the Houdini-21 documentation corpus so Solaris assembly "
            "grounds in real H21 docs (not phantom parms). Safe to click anytime "
            "— idempotent."
        )
        self._corpus_btn.clicked.connect(self._on_corpus)
        self._observe = QtWidgets.QWidget()
        self._observe.setObjectName("DsRailMeter")
        self._observe.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._observe.setFixedHeight(3)
        # Idle/busy styling lives in qss.py (#DsRailMeter, the [busy] property).
        self._observe.setProperty("busy", False)
        c.repolish(self._observe)
        bot.addWidget(self._foot_dot)
        bot.addWidget(self._foot_label)
        # Order is task order: connect, then ground the corpus, then read up.
        bot.addWidget(self._connect_btn)
        bot.addWidget(self._corpus_btn)
        bot.addWidget(self._help_btn)
        # The rail meter is retired from the header: the mark already fills
        # and rotates, the status reads "Working on it", and Stop is present
        # — a full-width warm rule was a fourth signal for one state (Joe).
        # The widget stays constructed so _set_busy and the compositor keep
        # their referent; it is simply never shown.
        self._observe.setVisible(False)
        bot.addStretch(1)
        # Model picker rides the action row, right edge -- same line as
        # Connect/Corpus/Help, opposite side (Joe): actions left, choice right.
        bot.addWidget(self._author_lbl)
        w.setProperty("rhythm_role", "parm_row")
        for control in (self._connect_btn, self._corpus_btn, self._help_btn, overflow):
            control.setObjectName("DsVerb")
            control.setProperty("rhythm_role", "label")
        overflow.setFixedWidth(t.SPACE_LG)
        for label in (self._header_status, self._foot_label, self._meter_lbl,
                      self._palette_hint, self._author_lbl):
            label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        col.addLayout(bot)

        # line 3 — persistent health strip (P0.3 / readiness §4.1): connection ·
        # memory backend · project · active job. Every cell is FACT-sourced or
        # renders UNKNOWN — the doctor is honest and this makes the panel honest
        # too. Initial cells are all-UNKNOWN (nothing measured yet); the 2 s
        # _update_context tick fills them from cheap in-process reads. It adds NO
        # main-thread I/O and never calls the doctor (the 648 ms hold), so it
        # cannot become the next paint stall.
        try:
            from synapse.panel import health_strip as _hs
            self._health_strip = _hs.build_health_strip_widget(
                _hs.build_cells(_hs.StripSnapshot()), parent=w)
            col.addWidget(self._health_strip)
        except Exception:
            self._health_strip = None

        self._region_cache["_build_rail"] = w
        return w

    def _format_tokens(self, n):
        """Token-count display rule for the rail meter — tokens only, no $:
        812 · 18.0k · 1.2M. Pure formatting; the meter never estimates."""
        n = int(n)
        if n < 1000:
            return "%d" % n
        if n < 1_000_000:
            return "%.1fk" % (n / 1000.0)
        return "%.1fM" % (n / 1_000_000.0)

    def _note_usage(self, total_tokens):
        """Accumulate real provider-reported usage into the session meter.
        No provider surfaces usage yet (the seam is a future providers/ slice);
        until it lands the meter stays empty — never estimated."""
        try:
            self._session_tokens += int(total_tokens)
        except Exception:
            return
        lbl = getattr(self, "_meter_lbl", None)
        if lbl is not None:
            lbl.setText(self._format_tokens(self._session_tokens))

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
                    "builds will ground in real H21 docs."
                    % (cnt, len(hits), hits[0].get("source", "?")))
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
        switch) must update it. Idempotent; safe before the rail is built."""
        lbl = getattr(self, "_author_lbl", None)
        if lbl is not None:
            try:
                lbl.setText(self._author_token())
            except Exception:
                pass

    def _build_context_ribbon(self):
        cached = self._region_cache.get("_build_context_ribbon")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        # The section role owns the ribbon's spacing.
        self._ctx_label = c.label("no scene context", role="label", scale=self._chrome_scale)
        self._ctx_label.setObjectName("DsContextLabel")
        self._ctx_label.setProperty("rhythm_role", "label")
        self._ctx_label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        lay.addWidget(self._ctx_label, 1)
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

    def _build_mode_bar(self):
        """The home surface's label. v9.1 (Option A): the DIRECT · WORK tabs are
        gone — there is one surface, **CHAT**, and consent/review AUTO-SURFACES
        when it's actionable (a raised gate brings the Work face forward, then
        accept/revert hands back). Clicking CHAT is the manual way back to the
        conversation. `#DsTabRow` still carries the 1px BORDER rule; the internal
        face keys stay "direct"/"work" — the invariants key on those, not the label."""
        cached = self._region_cache.get("_build_mode_bar")
        if cached is not None:                     # L5-4: recompose reuse
            return cached
        w = self._section()
        w.setObjectName("DsTabRow")
        lay = QtWidgets.QHBoxLayout(w)
        navigation = self._build_context_ribbon().layout()
        self._face_pills = {}
        pill = c.Pill("CHAT")
        pill.setFont(fontload.tracked_font(
            "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        pill.clicked.connect(lambda _=False: self._set_face("direct"))
        self._face_pills["direct"] = pill      # the idle default marks it active
        navigation.addWidget(pill)

        # TOKEN — the economist read-out (R167).
        #
        # v9.1 removed DIRECT · WORK because actionable state should AUTO-SURFACE
        # rather than wait for a click. That reasoning does not reach this one:
        # Work surfaces ITSELF because it is actionable; token economics is
        # DIAGNOSTIC, and a thing you go looking for is what a tab is for.
        tok = c.Pill("TOKEN")
        tok.setFont(fontload.tracked_font(
            "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
        tok.clicked.connect(lambda _=False: self._show_token_face())
        self._face_pills["token"] = tok
        navigation.addWidget(tok)

        # L5-4: the profile tab strip — CURIOUS · EXPERT · ML select the layout
        # manifest (L5-2). A click writes through settings (SwitcherState) and
        # recomposes LIVE; boot restores the saved tab. Right-aligned: profile
        # is chrome, the faces are the surface.
        try:
            from synapse.panel.settings import PROFILES as _profiles
        except Exception:  # pragma: no cover - settings ships with the panel
            _profiles = ("curious", "expert", "ml")
        self._profile_pills = {}
        for pid in _profiles:
            p = c.Pill(pid.upper())
            p.setProperty("rhythm_role", "row")
            p.setFont(fontload.tracked_font(
                "LABEL", t.SIZE_SMALL, scale=self._chrome_scale, mono=True))
            p.clicked.connect(lambda _=False, pid=pid: self._select_profile(pid))
            self._profile_pills[pid] = p
            lay.addWidget(p)
        self._mark_profile_pill(getattr(self, "_layout_profile", DEFAULT_PROFILE))
        self._region_cache["_build_mode_bar"] = w
        return w

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
        """Direct — converse + quick actions + input. The artist's surface.
        The face carries the comp's GUTTER/24 content padding; inner rows are
        flush (their old horizontal margins would double it)."""
        page = self._section()
        col = QtWidgets.QVBoxLayout(page)
        col.addWidget(self._build_converse(), 1)   # chat | Build-HDA inner stack
        from synapse.panel.recall_card import RecallCard
        self._recall_card = RecallCard()
        self._recall_card.hide()
        col.addWidget(self._recall_card)
        col.addWidget(self._build_act())
        col.addWidget(c.divider())
        col.addWidget(self._build_input())
        return page

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
            try:
                from synapse.panel.providers.ollama_provider import OllamaProvider
                live = OllamaProvider.available_models(timeout=1.0)
                if live:
                    rows = list(live)
            except Exception:
                pass
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
                "Model set to %s." % model_label(pid, model_id))
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

    def showEvent(self, e):
        super().showEvent(e)
        self._settle_composer_height()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._settle_composer_height()

    def _author_token(self):
        """Best-effort display signature of the active engine's model, e.g.
        ``claude-sonnet-4-6`` → ``sonnet-4.6``; ``gemini-3.5-flash`` shown as-is.
        DISPLAY ONLY — it is never authored to USD."""
        m = self._active_model()
        if not m:
            return ""
        # Prefer the registry's curated short label — it handles Haiku's dated id
        # (claude-haiku-4-5-20251001 → 'Haiku 4.5'), the long slash-bearing NVIDIA
        # ids, AND an unknown Ollama live tag (glm-5.2:cloud → 'GLM 5.2', never the
        # raw ':tag'). model_label returns the id verbatim only for an unknown
        # non-Ollama id → then fall back to the claude- string surgery below.
        try:
            from synapse.panel.providers.registry import model_label
            pid = getattr(self, "_provider_id", "claude")
            lbl = model_label(pid, m)
            if lbl and lbl != m:
                return lbl
        except Exception:
            pass
        if m.startswith("claude-"):
            m = m[len("claude-"):]
            for fam in ("opus", "sonnet", "haiku"):
                if m.startswith(fam):
                    rest = m[len(fam):].lstrip("-").replace("-", ".")
                    return ("%s-%s" % (fam, rest)) if rest else fam
            return m
        return m

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
        """The 3-field Custom-engine dialog (Base URL / Model id / Key env).
        Accept → persisted to panel_settings.json + chip refresh; takes effect
        on the NEXT message (the _set_model contract)."""
        try:
            from synapse.panel import settings as _pset
            st = _pset.load_settings()
        except Exception:
            return
        cfg = st.get("custom") or {}
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Configure Custom engine")
        form = QtWidgets.QFormLayout(dlg)
        fields = {}
        for key, label, placeholder in (
            ("base_url", "Base URL", "http://localhost:8000  or  https://host/v1"),
            ("model", "Model id", "e.g. qwen3-vl:30b"),
            ("key_env", "Key env (optional)", "e.g. MY_ENDPOINT_API_KEY"),
        ):
            edit = QtWidgets.QLineEdit(cfg.get(key, ""))
            edit.setObjectName("DsField")   # designsystem QLineEdit styling
            edit.setPlaceholderText(placeholder)
            form.addRow(label, edit)
            fields[key] = edit
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if not (dlg.exec() if hasattr(dlg, "exec") else dlg.exec_()):
            return
        st["custom"] = {k: e.text().strip() for k, e in fields.items()}
        # Keep the per-provider pick in lockstep with the new config — a
        # reconfigured model id must never lose to a stale persisted pick.
        self._model_by_provider["custom"] = st["custom"]["model"]
        st["provider_id"] = getattr(self, "_provider_id", "claude")
        st["model_by_provider"] = dict(self._model_by_provider or {})
        _pset.save_settings(st)
        self._refresh_engine_selector()

    def _make_provider(self):
        """Build the StreamProvider for the active engine. ``None`` ⇒ the worker
        falls back to its own Claude default (graceful degradation). An unknown
        engine id (stale persisted pick) hits the registry's Claude floor — and
        is SURFACED in chat, never silently swapped."""
        try:
            from synapse.panel.providers.registry import build_provider
            pid = getattr(self, "_provider_id", "claude")
            model = getattr(self, "_model_by_provider", {}).get(pid)
            prov = build_provider(pid, model=model)
            if prov.id != pid:
                try:
                    self._chat.append_system_message(
                        "Engine %r unavailable — using Claude." % pid)
                except Exception:
                    pass
            return prov
        except Exception:
            return None

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
        try:
            self._chat.append_system_message("Reverting the last change…")
        except Exception:
            pass
        self._send("Undo the last change using houdini_undo, then confirm what was reverted.")
        self._set_face("direct")            # v9.1 · hand back to the conversation

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
        self._hda_prompt.clear()
        self._set_direct_view("chat")
        self._send(
            "Build a %s HDA: %s. Use the houdini_hda_package tool, then show me "
            "the node path and the promoted parameters.%s" % (ctx, prompt, helptxt)
        )

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
        btn.setProperty("rhythm_role", "label")
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

    def _build_act(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        # The group role owns inter-verb gaps; DsVerb remains the text action.
        for label_text, prompt in _QUICK_ACTIONS:
            lay.addWidget(self._verb(
                label_text.upper(), lambda _=False, p=prompt: self._send(p)))
        # Build HDA: demoted from a top-level face into a Direct verb (+ ⌘K).
        lay.addWidget(self._verb(
            "BUILD HDA", lambda _=False: self._set_direct_view("hda")))
        lay.addStretch(1)
        self._font_btn = self._verb(
            "Aa", lambda _=False: self._cycle_font_scale())
        self._font_btn.setToolTip("Font size — click to cycle")
        lay.addWidget(self._font_btn)
        # ⌘K is folded into the input ("/" opens it; Ctrl+K still works) — no
        # separate, unintuitive glyph button in the bar.
        return w

    def _build_input(self):
        w = self._section()
        col = QtWidgets.QVBoxLayout(w)
        self._input = _GrowingInput()
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
        # khint — the composer's quiet key legend (comp .khint)
        self._khint = c.label("↵ send · ⇧↵ newline · / commands", role="caption")
        self._khint.setFont(fontload.tracked_font(
            "DATA", t.SIZE_MICRO, scale=self._chrome_scale, mono=True))
        col.addSpacing(t.SPACE_SM)          # +XS layout spacing ⇒ the comp's 12
        col.addWidget(self._khint)
        return w

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
        """An actionable gate proposal arrived → AUTO-SURFACE Work's done sub-state
        (v9.1 · Option A: consent comes to the artist). Noisy INFORM is skipped.
        This is the one revision to the same-pane law: consent surfaces itself;
        quiet state (busy / tool status / a plain answer) still never moves the
        view. Accept/revert hand back to chat; commit stays forward."""
        if isinstance(proposal, dict):
            level = proposal.get("level", "")
        else:
            level = getattr(proposal, "level", "")
        if level and level != "inform":
            self._populate_review()
            self._set_work_substate("done")
            self._set_header("done", "Result ready")
            self._set_face("work")          # consent auto-surfaces (Option A)

    def _show_overflow(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Copy conversation", self._copy_conversation)
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
            menu.addSeparator()
        except Exception:
            pass
        menu.addAction("Larger text", lambda: self._set_scale(t.next_font_scale(getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT), getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT))))
        menu.addAction("Default text", lambda: self._set_scale(self._chrome_scale))

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

        menu.exec(QtGui.QCursor.pos()) if hasattr(menu, "exec") else menu.exec_(QtGui.QCursor.pos())

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
        """The 'Aa' button — step through the font-scale presets live."""
        self._set_scale(t.next_font_scale(getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT), getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT)))

    def _open_palette(self):
        try:
            from synapse.panel.tool_palette import ToolPalette
            pal = ToolPalette(self, scale=getattr(self, "_chrome_scale", t.FONT_SCALE_DEFAULT))
            pal.command_selected.connect(self._on_tool_picked)
            self._palette = pal  # keep a ref
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
        else:
            cur = QtGui.QCursor.pos()
            x, y = cur.x(), cur.y()
        # clamp fully on-screen — SideFX popups never spill off the display
        x = max(avail.left(), min(x, avail.right() - sz.width()))
        y = max(avail.top(), min(y, avail.bottom() - sz.height()))
        popup.move(int(x), int(y))

    def _on_tool_picked(self, prompt):
        """A palette pick is a ready-to-send prompt; route it through chat (and
        thus the gated bridge path)."""
        self._send(prompt)

    def _on_submit(self):
        text = self._input.toPlainText().strip()
        if text:
            self._input.clear()
            self._send(text)

    def _send(self, text):
        # W7-SESSCOPE: /restore-session brings back the conversation parked by
        # a fresh-boot scoped load. Panel-local, never reaches the model.
        if (text or "").strip().lower() in ("/restore-session", "/restore_session"):
            self._restore_previous_session()
            return
        # Submitting is the artist handing off — drop input focus.
        if getattr(self, "_input", None) is not None:
            self._input.clearFocus()
        display = text
        if self._pending_context:
            text = "[Context: %s]\n%s" % (", ".join(self._pending_context), text)
            self._pending_context = []
        try:
            self._chat.append_user_message(display)
        except Exception:
            pass
        self._messages.append({"role": "user", "content": text})
        self._start_worker()

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
                                        tools=tools, parent=self,
                                        enforce_worker_policy=True,
                                        provider=self._make_provider())
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_done.connect(self._on_done)
        self._worker.stream_error.connect(self._on_error)
        if self._tool_executor is not None:
            self._worker.tool_requested.connect(self._tool_executor.execute_tool)
        self._worker.tool_status.connect(self._on_tool_status)
        self._worker.render_receipt.connect(self._on_render_receipt)
        self._worker.integrity_updated.connect(self._on_integrity)
        self._worker.start()

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
        text = "".join(self._stream_buf).strip()
        signed = self._author_token()   # display-only authorship note on results
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
                self._messages = self._worker.get_messages()
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
        # BP2-PANELTRUTH T2 / W5-PANEL item 3: the completed task's real token
        # receipt (usage_sink) now lands on the TOKEN face + the rail meter/pill
        # — event-driven from completion here, NEVER a QTimer (V3: a probe must
        # not trip the rate limit it reports on). Best-effort; never breaks the
        # completion path.
        self._refresh_token_surfaces()

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
        self._set_thinking(False)
        if getattr(self, "_streaming_started", False):
            try:
                self._chat.end_stream("".join(self._stream_buf).strip() or None)
            except Exception:
                pass
        try:
            self._chat.append_system_message("We hit a snag: %s" % msg)
        except Exception:
            pass
        self._set_busy(False)

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
        self._set_header("working", "%s %s" % (name, verb))
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
        self._set_header("working", "Stopping — waiting on %s…" % (self._last_tool or "the current tool"))

    def _set_busy(self, busy):
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._stop_btn.setVisible(busy)   # Stop is state-gated to working only
        self._observe.setProperty("busy", busy)
        c.repolish(self._observe)
        # state→Work-sub-state edges. Quiet state never moves the visible face
        # (v9.1 · only an ACTIONABLE consent gate auto-surfaces — see
        # _on_gate_raised). A new work cycle shows the cook sub-state; finishing
        # fills the done payoff and lifts the RAIL MARK to 'done' as the quiet
        # ready-result signal (a plain answer never changes the view).
        if busy and not self._was_busy:
            self._set_header("working", "Working on it")
            self._set_work_substate("cook")
        elif not busy and self._was_busy:
            # FRZ probe 4 (REVIEW). Last main-thread work of the turn and the only
            # one that destroys and rebuilds widgets (face_review._clear → takeAt +
            # setParent(None) + deleteLater per row), so it is the natural suspect
            # for a tail stall that reads as "and then it recovers".
            with _timed_phase("review"):
                self._populate_review()  # fill verdict + provenance for the payoff
            self._set_work_substate("done")
            self._set_header("done", "Result ready")
        elif busy:
            self._set_header("working", "Working on it")
        else:
            self._set_header("idle", "Standing by")
        self._was_busy = busy

    def _set_header(self, status, phrase):
        self._mark.set_state(status)
        self._header_status.setText(phrase)

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
                # one-line console warning the week API drift peaks.
                self._foot_dot.set_status("warning")
                self._foot_label.setText(
                    "Houdini · API gate stale"
                )
                conn = "warning"
            else:
                self._foot_dot.set_status("connected")
                self._foot_label.setText("Houdini")
                conn = "ok"
            if self._header_status.text() in ("Standing by", ""):
                self._set_header("idle", "Ready")
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
        strip = getattr(self, "_health_strip", None)
        if strip is None:
            return
        try:
            from synapse.panel import health_strip as _hs
            snap = _hs.gather_snapshot(connection=connection, project=project)
            _hs.update_health_strip_widget(strip, _hs.build_cells(snap))
        except Exception:
            pass

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
