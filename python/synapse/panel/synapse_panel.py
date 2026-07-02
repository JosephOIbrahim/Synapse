"""SYNAPSE panel — the redesigned, unified surface.

One panel, three zones (Converse / Act / Trust) framed by a Context ribbon and a
Connection footer, built on the vendored design system and *reusing the proven
runtime* (ClaudeWorker streaming + ToolExecutor + ChatDisplay + GateWidget)
rather than rewriting it. Closes the consent-gate gap the shipped legacy panel
had: GateWidget is wired in, so HumanGate proposals surface as actionable cards.

Entry point: ``createInterface()`` (Houdini Python Panel convention). The
``.pypanel`` at houdini/python_panels/ is a thin loader for this class.
"""

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
    from synapse.panel.face_review import FaceReview, detect_render_flags
except Exception:  # pragma: no cover
    FaceReview = None
    detect_render_flags = None

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsInput")
        self.setAcceptRichText(False)
        self.setPlaceholderText("Ask SYNAPSE…    ·    / for commands")
        # Default a comfortable multi-line height — but small enough that the
        # input + Send row are never pushed off the bottom at the min pane
        # height (the old 216px default was the crop culprit). The artist can
        # still drag it taller via the resize grip; it also auto-grows to fit.
        self._user_h = 96
        self._floor, self._max_h = 64, 600
        self.setFixedHeight(self._user_h)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        content = int(self.document().size().height()) + 18
        self.setFixedHeight(max(self._user_h, min(self._max_h, content)))

    def set_user_height(self, h):
        """Set the artist's preferred input height (driven by the resize grip)."""
        self._user_h = max(self._floor, min(self._max_h, int(h)))
        self._autosize()

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


class SynapsePanel(QtWidgets.QWidget):
    """The redesigned SYNAPSE panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumWidth(t.PANEL_MIN_WIDTH)
        # Load the bundled families BEFORE the stylesheet references them; a
        # missing family raises the build-mismatch flag (logged) and falls back.
        self._font_status = fontload.load_application_fonts()
        self._font_build_mismatch = self._font_status.get("build_mismatch", False)
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
        self.setStyleSheet(qss.stylesheet(self._chrome_scale))

        self._messages = []          # Anthropic-format conversation
        self._stream_buf = []        # accumulates streamed tokens
        self._worker = None
        self._last_tool = None       # C8: name of the in-flight tool, for an honest Stop
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
        except Exception:
            pass

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
        # Live context ribbon + connection (main-thread hou reads on a timer).
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
        # D3 — freeze-safety heartbeat. The panel runs on Houdini's main thread,
        # so this 1s beat IS the main-thread liveness signal: it arms the
        # process-wide Watchdog (freeze_chain), whose sustained-freeze escalation
        # opens the live breaker + triggers the emergency halt. The panel rebuild
        # had removed the only heartbeat source — this restores it.
        # M3-C: the panel is the beat source, so its forensic trail must be
        # durable even when no server was started. Idempotent; guarded so a
        # packaging gap can never break panel construction.
        try:
            from synapse.core.logfile import ensure_file_logging
            from synapse.server.telemetry_dump import start_periodic_flush
            ensure_file_logging()
            start_periodic_flush()
        except ImportError:
            pass
        self._freeze_timer = QTimer(self)
        self._freeze_timer.setInterval(1000)
        self._freeze_timer.timeout.connect(self._beat_freeze_chain)
        self._freeze_timer.start()
        self._beat_freeze_chain()

    # ---------------------------------------------------------------- UI
    def _section(self):
        """An opaque section container. Opaque surfaces are what stop Houdini's
        compositor from ghosting (the old global transparent rule was the bug)."""
        w = QtWidgets.QWidget()
        w.setObjectName("DsSection")
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        return w

    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Persistent rail (Mile 1) → context ribbon → switcher → the three faces.
        # Each face is a full content surface; the controller brings the right
        # one forward as the agent's state changes. The work is the hero.
        root.addWidget(self._build_rail())          # mark-as-status · state · Stop
        root.addWidget(c.divider())
        root.addWidget(self._build_model_bar())     # engine selection — apparent
        root.addWidget(c.divider())
        root.addWidget(self._build_context_ribbon())
        root.addWidget(self._build_mode_bar())      # Direct · Work · Review pills
        root.addWidget(self._build_faces(), 1)      # dominant — the stacked faces
        self._set_face("direct")                    # idle resting face

    def _build_rail(self):
        """The persistent rail (Pentagram pass, Mile 1).

        One strip replacing the old header AND footer: the mark-as-status +
        wordmark + state phrase on top; connection, an activity meter, and Stop
        beneath. Termination and live state never scroll away.
        """
        w = self._section()
        w.setObjectName("DsHeader")          # keep the subtle cool→warm gradient
        col = QtWidgets.QVBoxLayout(w)
        # Generous, confident header padding (Pentagram): a wider left margin and
        # real vertical air so the brand isn't crammed against the pane edge.
        col.setContentsMargins(t.SPACE_LG, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)
        col.setSpacing(t.SPACE_SM)

        # line 1 — identity + state. The mark fills with the agent's state.
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(t.SPACE_SM)
        self._mark = c.MarkDot("idle", diameter=16)
        word = c.label("SYNAPSE", role="display")
        # BRAND tracking lives on the QFont (Qt QSS has no letter-spacing); the
        # stylesheet carries colour only.
        word.setStyleSheet("color:%s;" % t.TEXT_BRIGHT)
        word.setFont(fontload.tracked_font("BRAND", t.SIZE_HERO, scale=self._chrome_scale))
        self._wordmark = word
        self._header_status = c.label("Standing by", role="caption", scale=self._chrome_scale)
        self._header_status.setStyleSheet("color:%s;" % t.TEXT_SECONDARY)
        # quiet ⌘K affordance — the palette is already bound (QShortcut); this
        # only makes it discoverable. Its text is set from the ACTUAL bound
        # QKeySequence after the shortcut is created (platform-correct, never
        # lies about the key). It rides line 1, never the meter row.
        self._palette_hint = c.label("", role="caption")
        self._palette_hint.setFont(fontload.tracked_font("LABEL_SM", t.SIZE_SMALL, scale=self._chrome_scale))
        self._palette_hint.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        overflow = c.Button("⋯", variant="ghost")
        overflow.setFixedWidth(32)
        overflow.clicked.connect(self._show_overflow)
        top.addWidget(self._mark)
        top.addSpacing(t.SPACE_XS)        # a beat between the mark and the wordmark
        top.addWidget(word)
        top.addSpacing(t.SPACE_SM)        # let the brand breathe before the stretch
        top.addStretch(1)
        top.addWidget(self._header_status)
        top.addWidget(self._palette_hint)
        top.addWidget(overflow)
        col.addLayout(top)

        # line 2 — connection · activity meter · Stop. The meter lifts to WARM
        # while the agent works, dim at rest (observability, always on).
        bot = QtWidgets.QHBoxLayout()
        bot.setSpacing(t.SPACE_SM)
        # author signature — DISPLAY ONLY — leads the telemetry cluster it
        # answers for (the model that produces results in this panel).
        self._author_lbl = c.label("", role="caption")
        self._author_lbl.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        self._author_lbl.setFont(fontload.tracked_font("DATA", t.SIZE_SMALL, scale=self._chrome_scale))
        self._author_lbl.setText(self._author_token())
        self._foot_dot = c.StatusDot("disconnected")
        self._foot_label = c.label("Not connected", role="caption", scale=self._chrome_scale)
        self._foot_label.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        # Force-connect the bridge server (the hwebserver serving /synapse for
        # external MCP clients + the /mcp endpoint the tool executor uses). The
        # panel's chat runs in-process, but tools + external tools need this up,
        # and it does NOT auto-start — this button is the one-click way to force
        # it without dropping into Houdini's Python Shell.
        self._connect_btn = c.Button("Connect", variant="ghost")
        self._connect_btn.setToolTip(
            "Start the Synapse bridge server (port 9999) so external / MCP tools "
            "can reach Houdini. Safe to click anytime — idempotent."
        )
        self._connect_btn.clicked.connect(self._on_connect)
        # Activate the H21 documentation corpus so Solaris assembly grounds in
        # real Houdini-21 docs (verified node types / parm names) instead of
        # phantom APIs. Mirrors the Connect button; idempotent.
        self._corpus_btn = c.Button("Corpus", variant="ghost")
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
        self._observe.setStyleSheet("background:%s; border-radius:2px;" % t.SIGNAL_TINT)
        self._stop_btn = c.Button("Stop", variant="danger")
        self._stop_btn.setMinimumWidth(64)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        self._stop_btn.setVisible(False)   # state-gated: shown only while working
        bot.addWidget(self._author_lbl)
        bot.addWidget(self._foot_dot)
        bot.addWidget(self._foot_label)
        bot.addWidget(self._connect_btn)
        bot.addWidget(self._corpus_btn)
        bot.addWidget(self._observe, 1)
        bot.addWidget(self._stop_btn)
        col.addLayout(bot)
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

    def _build_model_bar(self):
        """Model selection, made APPARENT (Image #6). A segmented Claude·Gemini
        control whose active engine reads as a filled SIGNAL pill, plus a
        prominent model-id chip — the switch used to be buried two levels deep
        in the ⋯ menu. Display/telemetry only; the pick takes effect on the NEXT
        message (same contract as the old menu switch)."""
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        lay.setSpacing(t.SPACE_SM)
        lbl = c.label("ENGINE", role="caption")
        lbl.setFont(fontload.tracked_font("LABEL_SM", t.SIZE_SMALL, scale=self._chrome_scale))
        self._engine_lbl = lbl
        lay.addWidget(lbl)
        self._engine_pills = {}
        try:
            from synapse.panel.providers.registry import PROVIDER_IDS, PROVIDER_LABELS
            ids, labels = PROVIDER_IDS, PROVIDER_LABELS
        except Exception:
            ids, labels = ("claude",), {"claude": "Claude"}
        for pid in ids:
            seg = QtWidgets.QPushButton(labels.get(pid, pid))
            seg.setObjectName("DsSeg")
            seg.setCursor(Qt.CursorShape.PointingHandCursor)
            seg.clicked.connect(lambda _=False, p=pid: self._set_provider(p))
            lay.addWidget(seg)
            self._engine_pills[pid] = seg
        lay.addStretch(1)
        # prominent model-id readout (e.g. 'sonnet-4.6') — the chip Image #6 asks
        # for; cost is intentionally omitted (the worker doesn't surface usage yet,
        # so a cost figure would be fabricated).
        # Clickable model picker — a SHORT model label + a ▾ affordance; opens a
        # menu of the active engine's models (Opus/Sonnet/Haiku/Fable for Claude).
        # Styled by the QSS #DsModelChip rule (caption-size, so the long NVIDIA
        # ids no longer dominate the panel).
        self._model_chip = QtWidgets.QPushButton(self._model_chip_text())
        self._model_chip.setObjectName("DsModelChip")
        self._model_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self._model_chip.setFlat(True)
        self._model_chip.setToolTip("Switch model")
        self._model_chip.clicked.connect(self._open_model_menu)
        lay.addWidget(self._model_chip)
        self._refresh_engine_selector()
        return w

    def _refresh_engine_selector(self):
        """Paint the active engine (filled pill) + the model chip from the live
        provider id. Idempotent; safe before the bar is built."""
        cur = getattr(self, "_provider_id", "claude")
        for pid, seg in getattr(self, "_engine_pills", {}).items():
            seg.setProperty("active", pid == cur)
            c.repolish(seg)
        chip = getattr(self, "_model_chip", None)
        if chip is not None:
            try:
                chip.setText(self._model_chip_text())
            except Exception:
                pass
        # keep the rail author signature in sync too — a MODEL switch (not just a
        # provider switch) must update it (its docstring promises this).
        lbl = getattr(self, "_author_lbl", None)
        if lbl is not None:
            try:
                lbl.setText(self._author_token())
            except Exception:
                pass

    def _build_context_ribbon(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        self._ctx_label = c.label("no scene context", role="label", scale=self._chrome_scale)
        lay.addWidget(self._ctx_label)
        lay.addStretch(1)
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
        # height and clipped the input/Send row at short pane sizes.
        self._chat.setMinimumHeight(80)
        self._converse_stack = QtWidgets.QStackedWidget()
        self._converse_stack.addWidget(self._chat)              # page 0: chat
        self._converse_stack.addWidget(self._build_hda_form())  # page 1: Build HDA
        self._converse_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        self._converse_stack.setMinimumHeight(80)
        return self._converse_stack

    # the two tabs, in switcher order (v9: Review folded into Work's done state)
    _FACE_INDEX = {"direct": 0, "work": 1}

    def _build_mode_bar(self):
        """The switcher: Direct · Work. Underline tabs (v9 call 1). A pill click
        is the *only* thing that moves the visible tab — agent state never does
        (the same-pane law)."""
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_XS)
        lay.setSpacing(t.SPACE_SM)
        self._face_pills = {}
        for face, text in (("direct", "Direct"), ("work", "Work")):
            pill = c.Pill(text)
            pill.setFont(fontload.tracked_font("LABEL", t.SIZE_UI + 2))  # tab tracking
            pill.clicked.connect(lambda _=False, f=face: self._set_face(f))
            lay.addWidget(pill)
            self._face_pills[face] = pill
        lay.addStretch(1)
        return w

    def _build_faces(self):
        """The two tabs in one stack. Direct is the artist's surface; Work is the
        working glance AND the payoff (its done sub-state folds in the old
        Review). The controller never auto-switches between them."""
        self._faces = QtWidgets.QStackedWidget()
        self._faces.addWidget(self._build_direct_face())   # 0 · idle / converse
        self._faces.addWidget(self._build_work_face())     # 1 · glance → done payoff
        self._faces.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding
        )
        # Low floor so the faces stack (Direct = chat + act + input) never forces
        # the panel taller than a short pane and clips the Send row. The chat's
        # stretch keeps it dominant at normal heights.
        self._faces.setMinimumHeight(160)
        return self._faces

    def _build_direct_face(self):
        """Direct — converse + quick actions + input. The artist's surface."""
        page = self._section()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._build_converse(), 1)   # chat | Build-HDA inner stack
        col.addWidget(self._build_act())
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
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self._work_stack = QtWidgets.QStackedWidget()

        # sub-state 0 · COOKING — FaceWork owns the glance
        if FaceWork is not None:
            self._work_face = FaceWork()
            cook = self._work_face
        else:  # graceful fallback — the surface stays present without FaceWork
            self._work_face = None
            cook = self._section()
            _l = QtWidgets.QVBoxLayout(cook)
            _l.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
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
        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        if GateWidget is not None:
            self._gate = GateWidget(parent=page)
            col.addWidget(self._gate)
        else:
            self._gate = None
        col.addStretch(1)
        return page

    def _set_work_substate(self, state):
        """Swap the Work face between 'cook' and 'done'. A content update WITHIN
        the Work tab — never a top-level tab switch (the same-pane law). The rail
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

    def _model_chip_text(self):
        """Short, readable chip label for the active model (e.g. 'Sonnet 4.6'),
        NOT the raw model id (which is long enough to dominate the panel)."""
        try:
            from synapse.panel.providers.registry import model_label
            pid = getattr(self, "_provider_id", "claude")
            lbl = model_label(pid, self._active_model())
        except Exception:
            lbl = self._author_token()
        return (lbl or "model") + "  ▾"

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

    def _model_menu_items(self):
        """``(model_id, label, active)`` rows for the active provider's picker —
        the exact data the model menu renders; exposed for the readability
        audit so the picker is gate-checkable offscreen."""
        try:
            from synapse.panel.providers import registry as reg
        except Exception:
            return []
        pid = getattr(self, "_provider_id", "claude")
        cur = self._active_model()
        rows = reg.models_for(pid)
        if pid == "ollama":
            # Live local tag list (menu-open is user-initiated; 1s localhost
            # timeout) — the registry row is only the static fallback.
            try:
                from synapse.panel.providers.ollama_provider import OllamaProvider
                live = OllamaProvider.available_models(timeout=1.0)
                if live:
                    rows = live
            except Exception:
                pass
        return [(mid, lbl, mid == cur) for mid, lbl in rows]

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

    def _author_token(self):
        """Best-effort display signature of the active engine's model, e.g.
        ``claude-sonnet-4-6`` → ``sonnet-4.6``; ``gemini-3.5-flash`` shown as-is.
        DISPLAY ONLY — it is never authored to USD."""
        m = self._active_model()
        if not m:
            return ""
        # Prefer the registry's curated short label — it handles Haiku's dated id
        # (claude-haiku-4-5-20251001 → 'Haiku 4.5', not 'haiku-4.5.20251001') and
        # the long slash-bearing NVIDIA ids cleanly. Fall back to the claude-
        # string surgery only for an unknown (non-registry) model id.
        try:
            from synapse.panel.providers.registry import model_label, models_for
            pid = getattr(self, "_provider_id", "claude")
            if m in {mid for mid, _ in models_for(pid)}:
                return model_label(pid, m)
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

    def _populate_review(self):
        """On 'done', fill the Work done sub-state with what we can: a taut
        verdict from the last reply, the SIGNED authorship line, and provenance
        from the routing_log (best-effort). All display-only."""
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
        rf.refresh_provenance()

    def _on_accept(self):
        try:
            self._chat.append_system_message("Accepted — keeping the result.")
        except Exception:
            pass

    def _on_revert(self):
        # Reversibility: route an undo through the proven agent/bridge path
        # rather than touching the substrate from the panel.
        try:
            self._chat.append_system_message("Reverting the last change…")
        except Exception:
            pass
        self._send("Undo the last change using houdini_undo, then confirm what was reverted.")

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
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_MD, t.SPACE_MD, t.SPACE_MD)
        lay.setSpacing(t.SPACE_SM)
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
        row.setSpacing(t.SPACE_SM)
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
        """Bring a tab forward. The *only* caller is a user pill click (and the
        explicit idle default); agent state never calls this — it drives the
        Work sub-state + the rail mark instead (the same-pane law). ``manual``
        is accepted for call-site compatibility and otherwise unused."""
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

    def _beat_freeze_chain(self):
        """1s main-thread liveness beat → process-wide freeze chain (D3).
        Best-effort: a missing/old server package must never break the panel."""
        try:
            from synapse.server.freeze_chain import beat
            beat()
        except Exception:
            pass

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
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        if tone:
            btn.setProperty("tone", tone)
        btn.clicked.connect(on_click)
        return btn

    def _build_act(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        lay.setSpacing(t.SPACE_MD)
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
        col.setContentsMargins(t.SPACE_MD, 0, t.SPACE_MD, t.SPACE_SM)
        col.setSpacing(t.SPACE_XS)
        self._input = _GrowingInput()
        # The prompt scales with the Aa content scale via a widget-level sheet
        # (overrides the root QSS font-size for this widget only); chrome stays put.
        self._input.setStyleSheet("QTextEdit#DsInput { font-size: %dpx; }"
                                  % t.scaled(t.SIZE_UI, self._font_scale))
        self._input.submitted.connect(self._on_submit)
        self._input.slash.connect(self._open_palette)   # "/" → command palette
        col.addWidget(_InputResizeGrip(self._input))   # drag handle at the top
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(t.SPACE_SM)
        attach = c.Button("\U0001F4CE", variant="ghost")  # paperclip
        attach.setFixedWidth(32)
        attach.setToolTip("Attach image / file as context")
        attach.clicked.connect(self._on_attach)
        self._send_btn = c.Button("Send", variant="primary")
        self._send_btn.setMinimumWidth(72)
        self._send_btn.clicked.connect(self._on_submit)
        row.addWidget(self._input, 1)
        row.addWidget(attach)
        row.addWidget(self._send_btn)
        col.addLayout(row)
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
                pass

    def _on_gate_raised(self, proposal):
        """A gate proposal arrived → surface it in Work's done sub-state and let
        the rail mark signal a ready result (skip noisy INFORM). Same-pane law:
        we never auto-switch the visible tab — the artist moves to Work when they
        choose; the mark is the call to attention."""
        if isinstance(proposal, dict):
            level = proposal.get("level", "")
        else:
            level = getattr(proposal, "level", "")
        if level and level != "inform":
            self._populate_review()
            self._set_work_substate("done")
            self._set_header("done", "Result ready")

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
        menu.addAction("Larger text", lambda: self._set_scale(1.15))
        menu.addAction("Default text", lambda: self._set_scale(self._chrome_scale))
        menu.exec(QtGui.QCursor.pos()) if hasattr(menu, "exec") else menu.exec_(QtGui.QCursor.pos())

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
        prompt input. The prompt uses a widget-level stylesheet — a widget's own
        sheet overrides the inherited root QSS font-size for that widget only, so
        the chrome around it stays put. Defensive: safe before either is built."""
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
                inp.setStyleSheet("QTextEdit#DsInput { font-size: %dpx; }"
                                  % t.scaled(t.SIZE_UI, sc))
            except Exception:
                pass

    def _cycle_font_scale(self):
        """The 'Aa' button — step through the font-scale presets live."""
        steps = list(t.FONT_SCALE_STEPS)
        cur = getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT)
        try:
            nxt = steps[(steps.index(cur) + 1) % len(steps)]
        except ValueError:
            # cur is the host-derived base (not on the ladder) — step to the next
            # size ABOVE it so the first Aa press never SHRINKS below the
            # host-matched body; wrap to the smallest if already at/above the top.
            above = [s for s in steps if s > cur + 1e-6]
            nxt = above[0] if above else steps[0]
        self._set_scale(nxt)

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

    def _build_system_prompt(self):
        """SYNAPSE's identity + the 'act via tools, don't narrate' steering.
        The redesigned panel dropped this — with an empty system prompt the
        model EXPLAINS build requests instead of executing them (the artist
        sees 'processing… text, no nodes'). Reads live scene context on the
        main thread (this runs from the send handler), all best-effort."""
        try:
            from synapse.panel.system_prompt import build_system_prompt
        except Exception:
            return ""
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
            return build_system_prompt(ctx)
        except Exception:
            return ""

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
        self._last_tool = None       # C8: fresh run — no stale in-flight tool name
        self._set_thinking(True)
        self._set_busy(True)
        tools = get_anthropic_tools() if get_anthropic_tools else None
        system = self._build_system_prompt()
        # Interactive panel = human-in-the-loop: the artist typed the request
        # and is watching it run, so the worker allowlist gate (autonomous-only)
        # is disabled here to preserve the existing artist-initiated path.
        self._worker = ClaudeWorker(self._messages, system_prompt=system,
                                    tools=tools, parent=self,
                                    enforce_worker_policy=False,
                                    provider=self._make_provider())
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_done.connect(self._on_done)
        self._worker.stream_error.connect(self._on_error)
        if self._tool_executor is not None:
            self._worker.tool_requested.connect(self._tool_executor.execute_tool)
        self._worker.tool_status.connect(self._on_tool_status)
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
            self._chat.stream_chunk(tok)
        except Exception:
            pass

    def _on_done(self):
        text = "".join(self._stream_buf).strip()
        signed = self._author_token()   # display-only authorship note on results
        if getattr(self, "_streaming_started", False):
            # finalize the live stream → fully formatted (links, code blocks)
            try:
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
        self._set_busy(False)

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
        verb = {"running": "running", "done": "ok", "error": "failed"}.get(phase, phase)
        self._set_header("working", "%s %s" % (name, verb))
        wf = getattr(self, "_work_face", None)
        if wf is not None:
            wf.set_tool_status(name, verb, _detail)   # feed the plan-with-progress
        # a render finishing → refresh the Review face's quality flags (BL-007/008)
        rf = getattr(self, "_review_face", None)
        if (rf is not None and detect_render_flags is not None
                and "render" in name.lower() and phase in ("done", "error")):
            try:
                rf.set_flags(detect_render_flags())
            except Exception:
                pass
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
        self._observe.setStyleSheet(
            "background:%s; border-radius:2px;" % (t.WARM if busy else t.SIGNAL_TINT)
        )
        # state→Work-sub-state edges (NO tab switch — the same-pane law). A new
        # work cycle shows the cook sub-state; finishing fills + shows the done
        # payoff. Because the tab never auto-switches, the RAIL MARK is the only
        # ready-result signal — so the falling edge lifts it to 'done'; the
        # artist moves to the Work tab when they choose.
        if busy and not self._was_busy:
            self._set_header("working", "Working on it")
            self._set_work_substate("cook")
        elif not busy and self._was_busy:
            self._populate_review()      # fill verdict + provenance for the payoff
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
        """Refresh the context ribbon + connection footer from live hou state."""
        try:
            import hou
        except Exception:
            self._ctx_label.setText("standalone — no Houdini")
            return
        try:
            frame = int(hou.frame())
            sel = hou.selectedNodes()
            if sel:
                parent = sel[0].parent()
                where = parent.path() if parent else sel[0].path()
                txt = "%s · %d selected · f%d" % (where, len(sel), frame)
            else:
                try:
                    hip = hou.hipFile.basename()
                except Exception:
                    hip = "untitled.hip"
                txt = "%s · f%d" % (hip, frame)
            self._ctx_label.setText(txt)
            if self._gate_stale_reason:
                # M3-A: a disarmed phantom-API gate must be LOUD, not a
                # one-line console warning the week API drift peaks.
                self._foot_dot.set_status("warning")
                self._foot_label.setText(
                    "Houdini · API gate stale — see docs/studio/UPGRADE.md"
                )
            else:
                self._foot_dot.set_status("connected")
                self._foot_label.setText("Houdini")
            if self._header_status.text() in ("Standing by", ""):
                self._set_header("idle", "Ready")
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
