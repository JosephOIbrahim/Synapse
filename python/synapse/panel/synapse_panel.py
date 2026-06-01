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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DsInput")
        self.setAcceptRichText(False)
        self.setPlaceholderText("Ask SYNAPSE…")
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._min_h, self._max_h = 72, 220
        self.setFixedHeight(self._min_h)
        self.textChanged.connect(self._autosize)

    def _autosize(self):
        h = int(self.document().size().height()) + 18
        self.setFixedHeight(max(self._min_h, min(self._max_h, h)))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(e)


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

        root.addWidget(self._build_header())
        root.addWidget(c.divider())
        root.addWidget(self._build_context_ribbon())
        root.addWidget(self._build_converse(), 1)   # dominant
        root.addWidget(self._build_trust())
        root.addWidget(self._build_act())
        root.addWidget(self._build_input())
        root.addWidget(c.divider())
        root.addWidget(self._build_footer())

    def _build_header(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_SM, t.SPACE_MD, t.SPACE_SM)
        lay.setSpacing(t.SPACE_SM)
        mark = c.label("◖ SYNAPSE", role="display")
        self._header_dot = c.StatusDot("idle")
        self._header_status = c.label("Standing by", role="caption")
        overflow = c.Button("⋯", variant="ghost")
        overflow.setFixedWidth(32)
        overflow.clicked.connect(self._show_overflow)
        lay.addWidget(mark)
        lay.addWidget(self._header_dot)
        lay.addWidget(self._header_status)
        lay.addStretch(1)
        lay.addWidget(overflow)
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
        try:
            self._chat.append_system_message(
                "Ready. What are we building?"
            )
        except Exception:
            pass
        return self._chat

    def _build_trust(self):
        self._trust = self._section()
        lay = QtWidgets.QVBoxLayout(self._trust)
        lay.setContentsMargins(t.SPACE_MD, 0, t.SPACE_MD, 0)
        lay.setSpacing(t.SPACE_XS)
        if GateWidget is not None:
            self._gate = GateWidget(parent=self._trust)
            lay.addWidget(self._gate)
        else:
            self._gate = None
        return self._trust

    def _build_act(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_XS, t.SPACE_MD, t.SPACE_XS)
        lay.setSpacing(t.SPACE_XS)
        for label_text, prompt in _QUICK_ACTIONS:
            pill = c.Pill(label_text)
            pill.clicked.connect(lambda _=False, p=prompt: self._send(p))
            lay.addWidget(pill)
        lay.addStretch(1)
        more = c.Pill("⌘K  more…")
        more.clicked.connect(self._open_palette)
        lay.addWidget(more)
        return w

    def _build_input(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_XS, t.SPACE_MD, t.SPACE_SM)
        lay.setSpacing(t.SPACE_SM)
        self._input = _GrowingInput()
        self._input.submitted.connect(self._on_submit)
        self._send_btn = c.Button("Send", variant="primary")
        self._send_btn.setFixedWidth(64)
        self._send_btn.clicked.connect(self._on_submit)
        lay.addWidget(self._input, 1)
        lay.addWidget(self._send_btn)
        return w

    def _build_footer(self):
        w = self._section()
        lay = QtWidgets.QHBoxLayout(w)
        lay.setContentsMargins(t.SPACE_MD, t.SPACE_XS, t.SPACE_MD, t.SPACE_XS)
        self._foot_dot = c.StatusDot("disconnected")
        self._foot_label = c.label("Not connected", role="caption")
        self._stop_btn = c.Button("Stop", variant="danger")
        self._stop_btn.setFixedWidth(64)
        self._stop_btn.clicked.connect(self._on_stop)
        self._stop_btn.setEnabled(False)
        lay.addWidget(self._foot_dot)
        lay.addWidget(self._foot_label)
        lay.addStretch(1)
        lay.addWidget(self._stop_btn)
        return w

    # ------------------------------------------------------------ behavior
    def _wire_gate(self):
        """GateWidget self-registers HumanGate callbacks; nothing else needed.

        Wiring it into the tree is what closes the consent gap — the legacy
        shipped panel never instantiated it.
        """
        return

    def _show_overflow(self):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Larger text", lambda: self._set_scale(1.15))
        menu.addAction("Default text", lambda: self._set_scale(1.0))
        menu.exec(QtGui.QCursor.pos()) if hasattr(menu, "exec") else menu.exec_(QtGui.QCursor.pos())

    def _set_scale(self, scale):
        self.setStyleSheet(qss.stylesheet(scale))
        if hasattr(self._chat, "font_scale"):
            try:
                self._chat.font_scale = scale
            except Exception:
                pass

    def _open_palette(self):
        try:
            from synapse.panel.tool_palette import ToolPalette
            pal = ToolPalette(self)
            pal.command_selected.connect(self._on_tool_picked)
            self._palette = pal  # keep a ref
            pal.show()
            pal.raise_()
        except Exception:
            # Palette unavailable — fall back to focusing input.
            self._input.setFocus()

    def _on_tool_picked(self, tool_name):
        """A palette pick routes through chat so it hits the gated bridge path."""
        self._send("Use the `%s` tool." % tool_name)

    def _on_submit(self):
        text = self._input.toPlainText().strip()
        if text:
            self._input.clear()
            self._send(text)

    def _send(self, text):
        try:
            self._chat.append_user_message(text)
        except Exception:
            pass
        self._messages.append({"role": "user", "content": text})
        self._start_worker()

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
        try:
            self._chat.show_typing_indicator()
        except Exception:
            pass
        self._set_busy(True)
        tools = get_anthropic_tools() if get_anthropic_tools else None
        self._worker = ClaudeWorker(self._messages, tools=tools, parent=self)
        self._worker.token_received.connect(self._on_token)
        self._worker.stream_done.connect(self._on_done)
        self._worker.stream_error.connect(self._on_error)
        if self._tool_executor is not None:
            self._worker.tool_requested.connect(self._tool_executor.execute_tool)
        self._worker.tool_status.connect(self._on_tool_status)
        self._worker.start()

    def _on_token(self, tok):
        self._stream_buf.append(tok)

    def _on_done(self):
        try:
            self._chat.hide_typing_indicator()
        except Exception:
            pass
        text = "".join(self._stream_buf).strip()
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
        try:
            self._chat.hide_typing_indicator()
            self._chat.append_system_message("We hit a snag: %s" % msg)
        except Exception:
            pass
        self._set_busy(False)

    def _on_tool_status(self, name, phase, _detail):
        verb = {"running": "running", "done": "ok", "error": "failed"}.get(phase, phase)
        self._set_header("working", "%s %s" % (name, verb))

    def _on_stop(self):
        if self._worker is not None:
            self._worker.abort()
        self._set_busy(False)

    def _set_busy(self, busy):
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setEnabled(busy)
        self._set_header("working" if busy else "idle",
                         "Working on it" if busy else "Standing by")

    def _set_header(self, status, phrase):
        self._header_dot.set_status(status)
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


def onCreateInterface():
    """Houdini Python Panel entry point — Houdini calls onCreateInterface()."""
    return SynapsePanel()


# Some code paths / older docs use createInterface — alias so either name works.
createInterface = onCreateInterface
