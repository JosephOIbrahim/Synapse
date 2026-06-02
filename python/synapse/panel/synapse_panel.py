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

_VERSION = "7.0.0"

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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsInput")
        self.setAcceptRichText(False)
        self.setPlaceholderText("Ask SYNAPSE…")
        self._user_h = 216          # default ~3x the previous 72px
        self._floor, self._max_h = 80, 600
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
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
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
        self.setCursor(Qt.SizeVerCursor)
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
        p.setPen(Qt.NoPen)
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
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(t.PANEL_MIN_WIDTH)
        self.setStyleSheet(qss.stylesheet(t.FONT_SCALE_DEFAULT))

        self._messages = []          # Anthropic-format conversation
        self._stream_buf = []        # accumulates streamed tokens
        self._worker = None
        self._tool_executor = ToolExecutor(parent=self) if ToolExecutor else None
        self._pending_context = []  # paths dropped in; prepended to the next send
        self._font_scale = t.FONT_SCALE_DEFAULT

        # state→face controller (Pentagram pass, Mile 2)
        self._current_face = "direct"
        self._manual_face = None     # a pill pick; held until the next work edge
        self._pending_face = None    # an auto switch deferred by the focus guard
        self._was_busy = False

        self.setAcceptDrops(True)
        self._build_ui()
        self._wire_gate()
        self._palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._palette_shortcut.activated.connect(self._open_palette)
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

    # ---------------------------------------------------------------- UI
    def _section(self):
        """An opaque section container. Opaque surfaces are what stop Houdini's
        compositor from ghosting (the old global transparent rule was the bug)."""
        w = QtWidgets.QWidget()
        w.setObjectName("DsSection")
        w.setAttribute(Qt.WA_StyledBackground, True)
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
        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        col.setSpacing(t.SPACE_XS)

        # line 1 — identity + state. The mark fills with the agent's state.
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(t.SPACE_SM)
        self._mark = c.MarkDot("idle", diameter=16)
        word = c.label("SYNAPSE", role="display")
        word.setStyleSheet(
            "color:%s; font-size:16px; letter-spacing:2px;" % t.TEXT_BRIGHT
        )
        self._header_status = c.label("Standing by", role="caption")
        self._header_status.setStyleSheet("color:%s;" % t.TEXT_SECONDARY)
        overflow = c.Button("⋯", variant="ghost")
        overflow.setFixedWidth(32)
        overflow.clicked.connect(self._show_overflow)
        top.addWidget(self._mark)
        top.addWidget(word)
        top.addStretch(1)
        top.addWidget(self._header_status)
        top.addWidget(overflow)
        col.addLayout(top)

        # line 2 — connection · activity meter · Stop. The meter lifts to WARM
        # while the agent works, dim at rest (observability, always on).
        bot = QtWidgets.QHBoxLayout()
        bot.setSpacing(t.SPACE_SM)
        self._foot_dot = c.StatusDot("disconnected")
        self._foot_label = c.label("Not connected", role="caption")
        self._foot_label.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        self._observe = QtWidgets.QWidget()
        self._observe.setObjectName("DsRailMeter")
        self._observe.setAttribute(Qt.WA_StyledBackground, True)
        self._observe.setFixedHeight(3)
        self._observe.setStyleSheet("background:%s; border-radius:2px;" % t.SIGNAL_TINT)
        self._stop_btn = c.Button("Stop", variant="danger")
        self._stop_btn.setMinimumWidth(64)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        bot.addWidget(self._foot_dot)
        bot.addWidget(self._foot_label)
        bot.addWidget(self._observe, 1)
        bot.addWidget(self._stop_btn)
        col.addLayout(bot)
        return w

    def _build_context_ribbon(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_XS, t.SPACE_MD, t.SPACE_XS)
        self._ctx_label = c.label("no scene context", role="label")
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
        try:
            self._chat.append_system_message(
                "Ready. What are we building?"
            )
        except Exception:
            pass
        self._chat.setMinimumHeight(380)  # a tall, dominant chat window
        self._converse_stack = QtWidgets.QStackedWidget()
        self._converse_stack.addWidget(self._chat)              # page 0: chat
        self._converse_stack.addWidget(self._build_hda_form())  # page 1: Build HDA
        self._converse_stack.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self._converse_stack.setMinimumHeight(380)
        return self._converse_stack

    # the three faces, in switcher order
    _FACE_INDEX = {"direct": 0, "work": 1, "review": 2}

    def _build_mode_bar(self):
        """The switcher: Direct · Work · Review. Pills are a manual override of
        the state→face controller; the controller drives them otherwise."""
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, 0, t.SPACE_MD, 0)
        lay.setSpacing(t.SPACE_XS)
        self._face_pills = {}
        for face, text in (("direct", "Direct"), ("work", "Work"), ("review", "Review")):
            pill = c.Pill(text)
            pill.clicked.connect(lambda _=False, f=face: self._set_face(f, manual=True))
            lay.addWidget(pill)
            self._face_pills[face] = pill
        lay.addStretch(1)
        return w

    def _build_faces(self):
        """The three faces in one stack. Each is a full content surface; the
        controller decides which is forward. Interiors are recomposed in later
        miles (Direct=3, Work=4, Review=5) — here they hold the proven widgets."""
        self._faces = QtWidgets.QStackedWidget()
        self._faces.addWidget(self._build_direct_face())   # 0 · idle / converse
        self._faces.addWidget(self._build_work_face())     # 1 · working / glance
        self._faces.addWidget(self._build_review_face())   # 2 · done / the payoff
        self._faces.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self._faces.setMinimumHeight(380)
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
        """Work — the walk-away glance. FaceWork (Mile 4) owns the cook preview,
        plan-with-progress, live tool status, the thinking pulse, and the
        embedded observability infographic. The panel delegates its working
        signals to it (set_thinking / set_tool_status / set_health)."""
        if FaceWork is not None:
            self._work_face = FaceWork()
            return self._work_face
        # graceful fallback — the surface stays present even without FaceWork
        self._work_face = None
        page = self._section()
        lay = QtWidgets.QVBoxLayout(page)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        lay.addWidget(c.label("Work face unavailable in this build", role="caption"))
        lay.addStretch(1)
        return page

    def _build_review_face(self):
        """Review — the payoff. The render becomes the hero in Mile 5; for now
        this surface carries the consent gate (reversibility / provenance)."""
        page = self._section()
        col = QtWidgets.QVBoxLayout(page)
        col.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        col.setSpacing(t.SPACE_SM)
        if GateWidget is not None:
            self._gate = GateWidget(parent=page)
            col.addWidget(self._gate)
        else:
            self._gate = None
        hint = c.label("render · verdict · credit land here — mile 5", role="caption")
        hint.setStyleSheet("color:%s;" % t.TEXT_TERTIARY)
        col.addWidget(hint)
        col.addStretch(1)
        return page

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
        lay.addStretch(1)
        return page

    def _set_direct_view(self, view):
        """Toggle Direct's inner surface: the chat (0) or the Build-HDA form (1).
        Build HDA is no longer a top-level face — it lives inside Direct (⌘K too)."""
        if hasattr(self, "_converse_stack"):
            self._converse_stack.setCurrentIndex(1 if view == "hda" else 0)
        self._set_face("direct")   # the HDA form lives on the Direct surface

    # ------------------------------------------------------- face controller
    def _input_focused(self):
        inp = getattr(self, "_input", None)
        return inp is not None and inp.hasFocus()

    def _set_face(self, face, manual=False):
        """Bring a face forward. ``manual=True`` is a pill pick — it holds until
        the next work cycle begins, so the controller won't fight the artist."""
        if not hasattr(self, "_faces") or face not in self._FACE_INDEX:
            return
        if manual:
            self._manual_face = face
            self._pending_face = None
        self._faces.setCurrentIndex(self._FACE_INDEX[face])
        self._current_face = face
        for f, pill in getattr(self, "_face_pills", {}).items():
            pill.setProperty("active", f == face)
            c.repolish(pill)

    def _request_face(self, face):
        """The state controller wants ``face``. Honor two guards:
        never yank away from Direct while the artist is typing, and don't
        override a manual pill pick (a real gate clears the manual hold first)."""
        if face != "direct" and self._input_focused():
            self._pending_face = face     # defer; applied on input focus-out
            return
        if self._manual_face is not None and self._manual_face != face:
            self._pending_face = face
            return
        self._set_face(face)

    def _apply_pending_face(self):
        """Input lost focus → honor any auto switch the focus guard deferred."""
        if (self._pending_face and self._manual_face is None
                and not self._input_focused()):
            face, self._pending_face = self._pending_face, None
            self._set_face(face)

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

    def _verb(self, text, on_click, accent=False):
        """A type-set action — mono, letter-spaced, no pill chrome (Mile 3).
        Verbs read as type, not buttons; the work is the hero, not the controls.
        Inline-styled so it overrides the DsPill look without touching qss.py
        (the QSS design pass is Mile 7)."""
        btn = QtWidgets.QPushButton(text)
        btn.setObjectName("DsVerb")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFlat(True)
        rest = t.TEXT_ACCENT if accent else t.TEXT_SECONDARY
        btn.setStyleSheet(
            "QPushButton#DsVerb{background:transparent; border:none; padding:2px 0;"
            " color:%s; font-family:%s; font-size:11px; letter-spacing:1.4px;}"
            "QPushButton#DsVerb:hover{color:%s;}"
            % (rest, t.FONT_MONO, t.TEXT_ACCENT)
        )
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
        self._more_btn = self._verb(
            "⌘K", lambda _=False: self._open_palette(), accent=True)
        self._more_btn.setToolTip("Command palette — every tool, two axes")
        lay.addWidget(self._more_btn)
        return w

    def _build_input(self):
        w = self._section()
        col = QtWidgets.QVBoxLayout(w)
        col.setContentsMargins(t.SPACE_MD, 0, t.SPACE_MD, t.SPACE_SM)
        col.setSpacing(t.SPACE_XS)
        self._input = _GrowingInput()
        self._input.submitted.connect(self._on_submit)
        self._input.focus_lost.connect(self._apply_pending_face)
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
        """A gate proposal arrived → bring Review forward (skip noisy INFORM).
        A real gate supersedes a manual park, but still respects the focus guard."""
        if isinstance(proposal, dict):
            level = proposal.get("level", "")
        else:
            level = getattr(proposal, "level", "")
        if level and level != "inform":
            self._manual_face = None
            self._request_face("review")

    def _show_overflow(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Copy conversation", self._copy_conversation)
        menu.addSeparator()
        menu.addAction("Larger text", lambda: self._set_scale(1.15))
        menu.addAction("Default text", lambda: self._set_scale(1.0))
        menu.exec(QtGui.QCursor.pos()) if hasattr(menu, "exec") else menu.exec_(QtGui.QCursor.pos())

    def _set_scale(self, scale):
        self._font_scale = scale
        self.setStyleSheet(qss.stylesheet(scale))
        if hasattr(self._chat, "font_scale"):
            try:
                self._chat.font_scale = scale
            except Exception:
                pass

    def _cycle_font_scale(self):
        """The 'Aa' button — step through the font-scale presets live."""
        steps = list(t.FONT_SCALE_STEPS)
        cur = getattr(self, "_font_scale", t.FONT_SCALE_DEFAULT)
        try:
            nxt = steps[(steps.index(cur) + 1) % len(steps)]
        except ValueError:
            nxt = t.FONT_SCALE_DEFAULT
        self._set_scale(nxt)

    def _open_palette(self):
        try:
            from synapse.panel.tool_palette import ToolPalette
            pal = ToolPalette(self)
            pal.command_selected.connect(self._on_tool_picked)
            self._palette = pal  # keep a ref
            self._position_popup(pal, getattr(self, "_more_btn", None))
            pal.show()
            pal.raise_()
            pal.activateWindow()
        except Exception:
            # Palette unavailable — fall back to focusing input.
            self._input.setFocus()

    def _position_popup(self, popup, anchor):
        """Place a Qt.Popup the SideFX way: anchored to the widget that opened
        it, on that widget's screen, fully visible. The palette is tall and the
        'more' button sits low in the panel, so prefer opening UPWARD from the
        button — falling back to downward only when there's no room above."""
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
        # Submitting is the artist handing off — drop input focus so the
        # controller's working→Work switch isn't held back by the focus guard.
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
        self._set_thinking(True)
        self._set_busy(True)
        tools = get_anthropic_tools() if get_anthropic_tools else None
        system = self._build_system_prompt()
        self._worker = ClaudeWorker(self._messages, system_prompt=system,
                                    tools=tools, parent=self)
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
        if getattr(self, "_streaming_started", False):
            # finalize the live stream → fully formatted (links, code blocks)
            try:
                self._chat.end_stream(text if text else None)
            except Exception:
                pass
        else:
            # no text tokens (e.g. a tool-only turn) → just stop + append
            self._set_thinking(False)
            if text:
                try:
                    self._chat.append_synapse_message(text)
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
        verb = {"running": "running", "done": "ok", "error": "failed"}.get(phase, phase)
        self._set_header("working", "%s %s" % (name, verb))
        wf = getattr(self, "_work_face", None)
        if wf is not None:
            wf.set_tool_status(name, verb, _detail)   # feed the plan-with-progress
        if phase == "running":
            self._request_face("work")   # a live tool → the walk-away glance

    def _on_stop(self):
        if self._worker is not None:
            self._worker.abort()
        self._set_thinking(False)
        self._set_busy(False)

    def _set_busy(self, busy):
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._observe.setStyleSheet(
            "background:%s; border-radius:2px;" % (t.WARM if busy else t.SIGNAL_TINT)
        )
        self._set_header("working" if busy else "idle",
                         "Working on it" if busy else "Standing by")
        # state→face edges: a new work cycle clears any manual park and shows
        # Work; work finishing shows Review (the payoff). idle→Direct is the
        # resting default and is set explicitly when a fresh turn begins.
        if busy and not self._was_busy:
            self._manual_face = None
            self._request_face("work")
        elif not busy and self._was_busy:
            self._request_face("review")
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
            self._foot_dot.set_status("connected")
            self._foot_label.setText("Houdini")
            if self._header_status.text() in ("Standing by", ""):
                self._set_header("idle", "Ready")
        except Exception:
            pass

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
