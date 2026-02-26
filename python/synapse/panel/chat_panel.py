"""Main Synapse Chat Panel for Houdini.

Registered as a pythonpanel interface. Houdini calls ``createInterface()``
when the panel tab is opened. Provides an AI chat interface connected to
the SYNAPSE server via WebSocket.

Layout::

    +-------------------------------------+
    | [Chat] [Create HDA]                |  <- mode toolbar
    +-------------------------------------+
    | Chat History (QTextBrowser)         |  <- expanding
    |                                     |
    | SYNAPSE                             |
    | Ready. What shall we work on?       |
    |                           2:34 PM   |
    |                                     |
    |                    You              |
    |    Scatter rocks on terrain         |
    |                           2:35 PM   |
    +-------------------------------------+
    | v [Explain] [Make HDA] [Fix Error]  |  <- collapsible quick action pills
    +-------------------------------------+
    | * /obj/geo1  3 nodes  F24           |  <- context chips (inline)
    | Type a message...         [Aa] Send |  <- growing multi-line input
    +-------------------------------------+
    | * Connected  ws://...    [Connect]  |  <- connection bar
    +-------------------------------------+
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot, QTimer
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot, QTimer

from synapse.panel.chat_display import ChatDisplay
from synapse.panel.context_bar import ContextChips
from synapse.panel.ws_bridge import SynapseWSBridge
from synapse.panel.quick_actions import (
    QUICK_ACTIONS, CONTEXT_MENU_EXTRAS, QuickActionPills,
)
from synapse.panel.hda_views import DescribeView, BuildingView, ResultView
from synapse.panel.gate_widget import GateWidget
from synapse.panel.styles import (
    get_hda_stylesheet,
    animate_stack_transition,
    get_growing_input_stylesheet,
    get_send_button_stylesheet,
    get_connect_button_stylesheet,
    get_ws_url_button_stylesheet,
    get_status_dot_stylesheet,
    get_status_label_stylesheet,
    get_root_widget_stylesheet,
    get_section_container_stylesheet,
    get_connection_frame_stylesheet,
    get_mode_toolbar_stylesheet,
    get_font_size_button_stylesheet,
    get_halt_button_stylesheet,
)
from synapse.panel import tokens as t

# -- Design tokens (from canonical design system) -------------------------
_SIGNAL = t.SIGNAL
_GROW = t.GROW
_ERROR_COLOR = t.ERROR

# Max age before context is re-gathered on send (ms)
_CONTEXT_MAX_AGE_MS = 5000


def _get_server_class():
    """Lazily import SynapseServer to avoid import-time issues."""
    try:
        from synapse.server.websocket import SynapseServer
        return SynapseServer
    except ImportError:
        return None


def _find_running_server():
    """Find an existing SynapseServer instance via gc (handles zombie servers)."""
    import gc
    for obj in gc.get_objects():
        if type(obj).__name__ == "SynapseServer" and getattr(obj, "_running", False):
            return obj
    return None


class _InputEventFilter(QtCore.QObject):
    """Event filter for Enter-to-send, Shift+Enter-for-newline, and Up-arrow recall."""

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self._panel = panel

    def eventFilter(self, obj, event):
        if obj is not self._panel._input:
            return False
        if event.type() != QtCore.QEvent.KeyPress:
            return False

        key = event.key()
        mods = event.modifiers()

        # Enter/Return sends message (without Shift)
        if key in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            if mods & QtCore.Qt.ShiftModifier:
                # Shift+Enter: insert newline (default QTextEdit behavior)
                return False
            # Plain Enter: send
            self._panel._send_message()
            return True

        # Up arrow recalls last message when input is empty
        if key == QtCore.Qt.Key_Up:
            text = self._panel._input.toPlainText()
            if not text and self._panel._last_sent_message:
                self._panel._input.setPlainText(self._panel._last_sent_message)
                # Move cursor to end
                cursor = self._panel._input.textCursor()
                cursor.movePosition(QtGui.QTextCursor.End)
                self._panel._input.setTextCursor(cursor)
                return True

        return False


class SynapseChatPanel:
    """Houdini Python Panel for AI-assisted workflow.

    Registered as a pythonpanel interface. Houdini calls
    ``createInterface()`` when the panel tab is opened.
    """

    def __init__(self):
        self._root = None
        self._bridge = None
        self._context_timer = None
        self._hda_controller = None
        self._last_context = None
        self._last_context_time = None
        self._project_initialized = False
        self._last_sent_message = ""
        self._waiting_for_response = False
        self._font_scale = t.FONT_SCALE_DEFAULT
        self._font_scale_index = t.FONT_SCALE_STEPS.index(t.FONT_SCALE_DEFAULT)

    def createInterface(self):
        """Build the panel layout and return the root QWidget.

        Returns
        -------
        QtWidgets.QWidget
            The root widget for the Houdini panel.
        """
        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(get_root_widget_stylesheet())

        main_layout = QtWidgets.QVBoxLayout(self._root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- Mode toggle toolbar ----------------------------------------
        toolbar = self._build_mode_toolbar()
        main_layout.addWidget(toolbar)

        # -- Mode stack: Chat vs HDA ------------------------------------
        self._mode_stack = QtWidgets.QStackedWidget(self._root)
        self._mode_stack.setObjectName("ModeStack")

        # Index 0: Chat mode
        self._chat_widget = QtWidgets.QWidget()
        chat_layout = QtWidgets.QVBoxLayout(self._chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        # 1. Chat display (expanding)
        self._chat = ChatDisplay(self._chat_widget)
        self._chat.node_clicked.connect(self._on_node_clicked)
        chat_layout.addWidget(self._chat, stretch=1)

        # 2. Quick actions (collapsible pills)
        self._quick_actions = QuickActionPills(self._chat_widget)
        self._quick_actions.action_triggered.connect(self._on_quick_action)
        chat_layout.addWidget(self._quick_actions)

        # 2.5. Gate proposals + integrity (collapsible)
        self._gate_widget = GateWidget(self._chat_widget)
        chat_layout.addWidget(self._gate_widget)

        # 3. Context chips + input area (merged)
        input_container = self._build_input_area()
        chat_layout.addWidget(input_container)

        self._mode_stack.addWidget(self._chat_widget)  # index 0

        # Index 1: HDA mode
        self._hda_container = QtWidgets.QWidget()
        self._hda_container.setObjectName("HdaModeWidget")
        hda_layout = QtWidgets.QVBoxLayout(self._hda_container)
        hda_layout.setContentsMargins(0, 0, 0, 0)
        hda_layout.setSpacing(0)

        self._hda_stack = QtWidgets.QStackedWidget()
        self.describe_view = DescribeView()
        self.building_view = BuildingView()
        self.result_view = ResultView()
        self._hda_stack.addWidget(self.describe_view)   # index 0
        self._hda_stack.addWidget(self.building_view)    # index 1
        self._hda_stack.addWidget(self.result_view)      # index 2

        hda_layout.addWidget(self._hda_stack)
        self._hda_container.setStyleSheet(get_hda_stylesheet())
        self._mode_stack.addWidget(self._hda_container)  # index 1

        main_layout.addWidget(self._mode_stack, stretch=1)

        # -- Connection bar ------------------------------------------------
        conn_bar = self._build_connection_bar()
        main_layout.addWidget(conn_bar)

        # -- WebSocket bridge --------------------------------------------
        self._bridge = SynapseWSBridge(self._root)
        self._bridge.response_received.connect(self._on_response)
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.context_updated.connect(self._on_context_updated)
        self._bridge.connection_error.connect(self._on_connection_error)
        self._bridge.gate_proposal.connect(self._gate_widget.handle_ws_proposal)
        self._bridge.session_report.connect(self._gate_widget.handle_ws_report)

        # -- HDA controller (wired in Phase 3, lazy import) -------------
        self._wire_hda_controller()

        # -- Context background refresh
        self._context_timer = QTimer(self._root)
        self._context_timer.timeout.connect(self._poll_context)
        self._context_timer.setInterval(10000)

        # -- Integrity polling (gate widget)
        self._integrity_timer = QTimer(self._root)
        self._integrity_timer.timeout.connect(self._poll_integrity)
        self._integrity_timer.setInterval(5000)

        # -- Keyboard shortcuts -------------------------------------------
        self._install_shortcuts()

        # -- Right-click context menu on chat display --------------------
        self._chat.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._chat.customContextMenuRequested.connect(self._show_context_menu)

        # -- Welcome message ---------------------------------------------
        self._chat.append_synapse_message(
            "Ready. What shall we work on?"
        )

        return self._root

    def onActivateInterface(self):
        """Panel becomes visible -- ensure server is running, then connect."""
        self._ensure_server()

        if self._bridge is not None and not self._bridge.isRunning():
            self._bridge.start()

        if self._context_timer is not None:
            self._context_timer.start()

        if self._integrity_timer is not None:
            self._integrity_timer.start()

    def onDeactivateInterface(self):
        """Panel hidden -- keep WS alive but pause UI updates."""
        if self._context_timer is not None:
            self._context_timer.stop()

        if self._integrity_timer is not None:
            self._integrity_timer.stop()

    def onDestroyInterface(self):
        """Panel closing -- clean up bridge thread."""
        if self._context_timer is not None:
            self._context_timer.stop()

        if self._integrity_timer is not None:
            self._integrity_timer.stop()

        if self._bridge is not None:
            self._bridge.stop()

    # -- Server auto-start -----------------------------------------------

    def _ensure_server(self):
        """Make sure a SynapseServer is running before the bridge connects."""
        import os

        try:
            import hou
        except ImportError:
            return

        server = getattr(hou.session, "_synapse_server", None)
        if server is not None and getattr(server, "_running", False):
            return

        server = _find_running_server()
        if server is not None:
            hou.session._synapse_server = server
            return

        SynapseServer = _get_server_class()
        if SynapseServer is None:
            self._chat.append_system_message(
                "Couldn't import SynapseServer -- is the synapse package installed?"
            )
            return

        port = int(os.environ.get("SYNAPSE_PORT", "9999"))
        try:
            server = SynapseServer(host="localhost", port=port)
            server.start()
        except Exception as exc:
            self._chat.append_system_message(
                "Couldn't start the server automatically: {}".format(exc)
            )
            return

        hou.session._synapse_server = server
        actual_port = getattr(server, "_actual_port", port)
        self._chat.append_system_message(
            "Started SYNAPSE server on port {}.".format(actual_port)
        )

    # -- Project memory auto-init ----------------------------------------

    def _ensure_project_initialized(self):
        """Auto-call project_setup on first interaction."""
        if self._project_initialized:
            return
        if self._bridge is not None and self._bridge.connected:
            try:
                self._bridge.send_command("project_setup", {})
                self._project_initialized = True
            except Exception:
                pass

    # -- Keyboard shortcuts -----------------------------------------------

    def _install_shortcuts(self):
        """Install keyboard shortcuts on the root widget."""
        _QShortcut = getattr(QtGui, "QShortcut", None) or QtWidgets.QShortcut

        clear_sc = _QShortcut(
            QtGui.QKeySequence("Ctrl+L"), self._root
        )
        clear_sc.activated.connect(self._shortcut_clear_chat)

        focus_sc = _QShortcut(
            QtGui.QKeySequence("Ctrl+K"), self._root
        )
        focus_sc.activated.connect(self._shortcut_focus_input)

        esc_sc = _QShortcut(
            QtGui.QKeySequence("Escape"), self._root
        )
        esc_sc.activated.connect(self._shortcut_escape)

        # Event filter for Enter/Shift+Enter/Up on QTextEdit input
        self._event_filter = _InputEventFilter(self, parent=self._input)
        self._input.installEventFilter(self._event_filter)

    def _shortcut_clear_chat(self):
        """Ctrl+L -- clear all chat history."""
        if self._chat is not None:
            self._chat.clear()

    def _shortcut_focus_input(self):
        """Ctrl+K -- focus the message input field."""
        if self._input is not None:
            self._input.setFocus()

    def _shortcut_escape(self):
        """Escape -- clear input text."""
        if self._input is not None:
            self._input.clear()

    # -- UI builders -----------------------------------------------------

    def _build_input_area(self):
        """Build the merged context chips + growing input + send button + font control."""
        container = QtWidgets.QWidget(self._root)
        container.setStyleSheet(get_section_container_stylesheet())

        outer_layout = QtWidgets.QVBoxLayout(container)
        outer_layout.setContentsMargins(8, 6, 8, 8)
        outer_layout.setSpacing(4)

        # Context chips row (above input)
        self._context_chips = ContextChips(container)
        outer_layout.addWidget(self._context_chips)

        # Input row: QTextEdit + font button + send button
        input_row = QtWidgets.QHBoxLayout()
        input_row.setSpacing(8)

        # Growing text input (replaces QLineEdit)
        self._input = QtWidgets.QTextEdit(container)
        self._input.setPlaceholderText("Type a message...")
        self._input.setStyleSheet(get_growing_input_stylesheet())
        self._input.setMinimumHeight(t.CHAT_INPUT_MIN_H)
        self._input.setMaximumHeight(t.CHAT_INPUT_MAX_H)
        self._input.setAcceptRichText(False)
        self._input.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self._input.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._input.textChanged.connect(self._adjust_input_height)
        input_row.addWidget(self._input, stretch=1)

        # Right-side controls (vertical stack: font icon on top, send below)
        controls_layout = QtWidgets.QVBoxLayout()
        controls_layout.setSpacing(4)

        # Font size control "Aa" button
        self._font_btn = QtWidgets.QPushButton("Aa", container)
        self._font_btn.setFixedSize(28, 22)
        self._font_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._font_btn.setToolTip(
            "Font size: {:.0f}%".format(self._font_scale * 100)
        )
        self._font_btn.setStyleSheet(get_font_size_button_stylesheet())
        self._font_btn.clicked.connect(self._cycle_font_size)
        controls_layout.addWidget(self._font_btn, alignment=QtCore.Qt.AlignRight)

        # Send button
        self._send_btn = QtWidgets.QPushButton("Send", container)
        self._send_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._send_btn.setStyleSheet(get_send_button_stylesheet())
        self._send_btn.clicked.connect(self._send_message)
        controls_layout.addWidget(self._send_btn)

        input_row.addLayout(controls_layout)
        outer_layout.addLayout(input_row)

        return container

    def _adjust_input_height(self):
        """Auto-grow the QTextEdit based on content, up to max height."""
        doc = self._input.document()
        # Add padding/margins to the document height
        doc_height = int(doc.size().height()) + 12
        new_h = max(t.CHAT_INPUT_MIN_H, min(doc_height, t.CHAT_INPUT_MAX_H))
        self._input.setFixedHeight(new_h)

    def _cycle_font_size(self):
        """Cycle through font scale steps: 0.75x -> 1.0x -> 1.25x -> 1.5x."""
        steps = t.FONT_SCALE_STEPS
        self._font_scale_index = (self._font_scale_index + 1) % len(steps)
        self._font_scale = steps[self._font_scale_index]

        # Update chat display
        self._chat.font_scale = self._font_scale

        # Update tooltip
        self._font_btn.setToolTip(
            "Font size: {:.0f}%".format(self._font_scale * 100)
        )

    # -- Right-click context menu ----------------------------------------

    def _show_context_menu(self, pos):
        """Build and show context menu on right-click in chat display."""
        menu = QtWidgets.QMenu(self._chat)
        menu.setStyleSheet(
            "QMenu {{ background: {bg}; color: {fg}; border: 1px solid {border}; }}"
            "QMenu::item:selected {{ background: {hover}; }}".format(
                bg=t.CARBON, fg=t.BONE, border=t.GRAPHITE, hover=t.HOVER,
            )
        )

        # Quick actions
        for action in QUICK_ACTIONS:
            act = menu.addAction(action["label"])
            act.setToolTip(action.get("tooltip", ""))
            act.triggered.connect(
                lambda checked=False, a=action: self._on_quick_action(a)
            )

        menu.addSeparator()

        # Extra context menu actions
        for extra in CONTEXT_MENU_EXTRAS:
            act = menu.addAction(extra["label"])
            action_key = extra.get("action", "")
            act.triggered.connect(
                lambda checked=False, key=action_key: self._on_context_menu_action(key)
            )

        menu.exec_(self._chat.mapToGlobal(pos))

    def _on_context_menu_action(self, action_key):
        """Handle context menu extra actions."""
        if action_key == "clear_chat":
            self._chat.clear()
        elif action_key == "copy_last":
            self._copy_last_response()
        elif action_key == "toggle_actions":
            expanded = self._quick_actions._expanded
            self._quick_actions.set_expanded(not expanded)

    def _copy_last_response(self):
        """Copy the last SYNAPSE response text to clipboard."""
        import subprocess
        import platform

        # Extract plain text from the chat display
        text = self._chat.toPlainText()
        # Find the last SYNAPSE block
        lines = text.split("\n")
        last_synapse_lines = []
        in_synapse = False
        for line in reversed(lines):
            stripped = line.strip()
            if stripped == "SYNAPSE":
                in_synapse = True
                break
            if in_synapse or stripped:
                last_synapse_lines.insert(0, line)

        response_text = "\n".join(last_synapse_lines).strip()
        if not response_text:
            return

        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["clip"], input=response_text.encode("utf-8"),
                    creationflags=0x08000000, timeout=5,
                )
                return
            except Exception:
                pass
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.clipboard().setText(response_text)
        except Exception:
            pass

    # -- Connection bar --------------------------------------------------

    def _build_connection_bar(self):
        """Build the bottom connection status and controls."""
        import os

        _port = int(os.environ.get("SYNAPSE_PORT", "9999"))
        _path = os.environ.get("SYNAPSE_PATH", "/synapse")
        self._ws_url = "ws://localhost:{}{}".format(_port, _path)

        frame = QtWidgets.QWidget(self._root)
        frame.setObjectName("connection_frame")
        frame.setStyleSheet(get_connection_frame_stylesheet())
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Status dot
        self._conn_dot = QtWidgets.QLabel("\u25CF")
        self._conn_dot.setObjectName("status_dot")
        self._conn_dot.setStyleSheet(get_status_dot_stylesheet(_ERROR_COLOR))
        layout.addWidget(self._conn_dot)

        # Status label
        self._conn_label = QtWidgets.QLabel("Disconnected")
        self._conn_label.setObjectName("status_label")
        self._conn_label.setStyleSheet(get_status_label_stylesheet(_ERROR_COLOR))
        layout.addWidget(self._conn_label)

        # Emergency halt button
        self._halt_btn = QtWidgets.QPushButton("HALT")
        self._halt_btn.setStyleSheet(get_halt_button_stylesheet())
        self._halt_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._halt_btn.setToolTip("Emergency halt -- cancel all agent operations")
        self._halt_btn.clicked.connect(self._on_emergency_halt)
        layout.addWidget(self._halt_btn)

        layout.addStretch()

        # Connect/Disconnect button
        self._conn_btn = QtWidgets.QPushButton("Connect")
        self._conn_btn.setObjectName("connect_button")
        self._conn_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._conn_btn.setStyleSheet(get_connect_button_stylesheet())
        self._conn_btn.clicked.connect(self._on_connect_toggle)
        layout.addWidget(self._conn_btn)

        # WS URL button
        ws_btn = QtWidgets.QPushButton(self._ws_url)
        ws_btn.setObjectName("ws_path_button")
        ws_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        ws_btn.setStyleSheet(get_ws_url_button_stylesheet())
        ws_btn.setToolTip("Copy WebSocket URL to clipboard")
        ws_btn.clicked.connect(self._on_copy_ws_url)
        layout.addWidget(ws_btn)

        frame.setFixedHeight(44)
        return frame

    def _on_connect_toggle(self):
        """Start or stop the WebSocket bridge with immediate visual feedback."""
        if self._bridge is not None and self._bridge.isRunning():
            self._bridge.stop()
            self._conn_btn.setText("Connect")
            self._conn_btn.setEnabled(True)
        else:
            self._ensure_server()
            if self._bridge is not None:
                self._conn_dot.setStyleSheet(get_status_dot_stylesheet(_SIGNAL))
                self._conn_label.setText("Connecting...")
                self._conn_label.setStyleSheet(
                    get_status_label_stylesheet(_SIGNAL)
                )
                self._conn_btn.setText("Cancel")
                self._conn_btn.setEnabled(True)
                self._chat.append_system_message(
                    "Connecting to {url}...".format(url=self._ws_url)
                )
                self._bridge.start()

    def _on_copy_ws_url(self):
        """Copy WebSocket URL to clipboard."""
        import subprocess
        import platform

        url = getattr(self, "_ws_url", "ws://localhost:9999/synapse")
        if platform.system() == "Windows":
            try:
                subprocess.run(
                    ["clip"], input=url.encode("utf-8"),
                    creationflags=0x08000000, timeout=5,
                )
                self._chat.append_system_message(
                    "Copied: {}".format(url)
                )
                return
            except Exception:
                pass
        try:
            app = QtWidgets.QApplication.instance()
            if app:
                app.clipboard().setText(url)
                self._chat.append_system_message(
                    "Copied: {}".format(url)
                )
        except Exception:
            pass

    # -- Mode toggle -----------------------------------------------------

    def _build_mode_toolbar(self):
        """Build the Chat / Create HDA mode toggle toolbar."""
        toolbar = QtWidgets.QWidget(self._root)
        toolbar.setStyleSheet(get_mode_toolbar_stylesheet())
        layout = QtWidgets.QHBoxLayout(toolbar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        self._mode_chat_btn = QtWidgets.QPushButton("Chat")
        self._mode_chat_btn.setObjectName("ModeToggleActive")
        self._mode_chat_btn.setCursor(
            QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        )
        self._mode_chat_btn.clicked.connect(
            lambda: self._set_mode("chat")
        )
        layout.addWidget(self._mode_chat_btn)

        self._mode_hda_btn = QtWidgets.QPushButton("Create HDA")
        self._mode_hda_btn.setObjectName("ModeToggleInactive")
        self._mode_hda_btn.setCursor(
            QtGui.QCursor(QtCore.Qt.PointingHandCursor)
        )
        self._mode_hda_btn.clicked.connect(
            lambda: self._set_mode("hda")
        )
        layout.addWidget(self._mode_hda_btn)

        layout.addStretch()

        toolbar.setFixedHeight(36)
        return toolbar

    def _set_mode(self, mode):
        """Switch between chat and HDA creation modes."""
        if mode == "chat":
            animate_stack_transition(self._mode_stack, 0)
            self._mode_chat_btn.setObjectName("ModeToggleActive")
            self._mode_hda_btn.setObjectName("ModeToggleInactive")
        elif mode == "hda":
            animate_stack_transition(self._mode_stack, 1)
            self._hda_stack.setCurrentIndex(0)
            self.describe_view.reset()
            self._mode_chat_btn.setObjectName("ModeToggleInactive")
            self._mode_hda_btn.setObjectName("ModeToggleActive")

        for btn in (self._mode_chat_btn, self._mode_hda_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _wire_hda_controller(self):
        """Connect HDA views to the controller and bridge signals."""
        from synapse.panel.hda_controller import HdaController

        self._hda_controller = HdaController(
            self._bridge,
            context_source=lambda: self._last_context,
        )

        self.describe_view.generate_requested.connect(
            self._hda_controller.execute
        )
        self._hda_controller.progress.connect(
            self.building_view.update_stage
        )
        self.describe_view.generate_requested.connect(
            lambda *_: animate_stack_transition(self._hda_stack, 1)
        )
        self._hda_controller.result.connect(self._on_hda_result)
        self.result_view.action_requested.connect(self._on_hda_action)
        self.building_view.cancel_requested.connect(
            self._hda_controller.cancel
        )
        self.building_view.cancel_requested.connect(
            lambda: animate_stack_transition(self._hda_stack, 0)
        )

    @Slot(dict)
    def _on_hda_result(self, data):
        """Handle HDA creation result -- switch to result view."""
        self.result_view.populate(data)
        animate_stack_transition(self._hda_stack, 2)

    def _on_hda_action(self, action):
        """Handle result view action buttons."""
        if action == "new":
            self.describe_view.reset()
            self.building_view.reset()
            animate_stack_transition(self._hda_stack, 0)
        elif action == "inspect":
            path = self.result_view.path_label.text()
            if path:
                self._on_node_clicked(path)
        elif action == "save":
            pass

    # -- Actions ---------------------------------------------------------

    def _gather_context_if_stale(self, max_age_ms=_CONTEXT_MAX_AGE_MS):
        """Gather context only if cached data is stale."""
        import time
        now = time.time() * 1000
        if self._last_context_time and (now - self._last_context_time) < max_age_ms:
            return self._last_context
        try:
            from synapse.panel.ws_bridge import _gather_context_on_main_thread
            ctx = _gather_context_on_main_thread()
            if ctx:
                self._last_context = ctx
                self._last_context_time = time.time() * 1000
        except Exception:
            pass
        return self._last_context

    def _send_message(self):
        """Read input field, send via WS bridge, clear input."""
        text = self._input.toPlainText().strip()
        if not text:
            return

        self._last_sent_message = text
        self._input.clear()
        self._chat.append_user_message(text)

        if self._bridge is not None:
            self._ensure_project_initialized()
            self._waiting_for_response = True
            self._chat.show_typing_indicator()
            ctx = self._gather_context_if_stale()
            self._bridge.send_command("route_chat", {
                "message": text,
                "context": ctx,
            })
        else:
            self._chat.append_system_message(
                "Not connected to SYNAPSE server."
            )

    @Slot(dict)
    def _on_response(self, response):
        """Handle server response from route_chat."""
        self._waiting_for_response = False
        self._chat.hide_typing_indicator()

        status = response.get("status", "")

        if status == "error":
            self._chat.append_synapse_message(response)
            return

        text = response.get("response", "")
        tier = response.get("tier", "")
        commands = response.get("commands", [])

        if text:
            self._chat.append_synapse_message({"message": text, "tier": tier})

        if commands:
            for cmd in commands:
                self._chat.append_system_message(
                    "\u2192 {} {}".format(
                        cmd.get("type", ""),
                        cmd.get("description", cmd.get("id", "")),
                    )
                )

    @Slot(bool)
    def _on_status_changed(self, connected):
        """Handle connection status change."""
        self._context_chips.set_connected(connected)
        self._conn_btn.setEnabled(True)

        if connected:
            _sc = _GROW
            self._conn_dot.setStyleSheet(get_status_dot_stylesheet(_sc))
            self._conn_label.setText("Connected")
            self._conn_label.setStyleSheet(get_status_label_stylesheet(_sc))
            self._conn_btn.setText("Disconnect")
            self._chat.append_system_message("Connected to SYNAPSE server.")
        else:
            _sc = _ERROR_COLOR
            self._conn_dot.setStyleSheet(get_status_dot_stylesheet(_sc))
            self._conn_label.setText("Disconnected")
            self._conn_label.setStyleSheet(get_status_label_stylesheet(_sc))
            self._conn_btn.setText("Connect")

    @Slot(str)
    def _on_connection_error(self, error_msg):
        """Surface connection errors in the chat."""
        self._chat.append_system_message(error_msg)

    @Slot(dict)
    def _on_context_updated(self, context):
        """Update context chips and cache for send-time use."""
        import time
        self._last_context = context
        self._last_context_time = time.time() * 1000
        self._context_chips.set_network_path(
            context.get("current_network", "")
        )
        self._context_chips.set_selection_count(
            len(context.get("selected_nodes", []))
        )
        self._context_chips.set_frame(context.get("frame", 1.0))

        project_name = context.get("project_name", "")
        evolution_stage = context.get("evolution_stage", "")
        self._context_chips.set_project_context(project_name, evolution_stage)

    def _on_quick_action(self, action):
        """Handle quick action pill press."""
        prompt = action.get("prompt", "")
        requires_sel = action.get("requires_selection", False)

        ctx = self._gather_context_if_stale()

        if requires_sel:
            if not ctx or not ctx.get("selected_nodes"):
                self._chat.append_system_message(
                    "Please select one or more nodes first."
                )
                return

        label = action.get("label", "Action")
        self._chat.append_user_message("[{label}] {prompt}".format(
            label=label, prompt=prompt
        ))

        if self._bridge is not None:
            self._bridge.send_command("route_chat", {
                "message": prompt,
                "context": ctx,
            })

    def _on_node_clicked(self, node_path):
        """Navigate to a clicked node path in the network editor."""
        try:
            import hou

            node = hou.node(node_path)
            if node is not None:
                node.setSelected(True, clear_all_selected=True)
                editors = [
                    p
                    for p in hou.ui.paneTabs()
                    if p.type() == hou.paneTabType.NetworkEditor
                ]
                if editors:
                    editors[0].setCurrentNode(node)
                    editors[0].homeToSelection()
        except Exception:
            pass

    def _on_emergency_halt(self):
        """Emergency halt -- cancel all agent operations."""
        self._chat.append_system_message("Emergency halt triggered.")
        if self._bridge is not None and self._bridge.connected:
            self._bridge.send_command(
                "emergency_halt", {"reason": "Artist triggered panel halt"}
            )

    def _poll_integrity(self):
        """Poll bridge for integrity report and update gate widget."""
        if self._bridge is not None and self._bridge.connected:
            self._bridge.send_command("get_session_report", {})

    def _poll_context(self):
        """Periodically refresh scene context for the context chips."""
        if self._bridge is not None and self._bridge.connected:
            try:
                import time as _time
                from synapse.panel.ws_bridge import _gather_context_on_main_thread
                ctx = _gather_context_on_main_thread()
                if ctx:
                    self._last_context = ctx
                    self._last_context_time = _time.time() * 1000
                    self._bridge.context_updated.emit(ctx)
            except Exception:
                pass
