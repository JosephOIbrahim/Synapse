"""Main Synapse Chat Panel for Houdini.

Registered as a pythonpanel interface. Houdini calls ``createInterface()``
when the panel tab is opened. Provides an AI chat interface connected to
the SYNAPSE server via WebSocket.

Layout::

    +-------------------------------------+
    | Chat History (QTextEdit, read-only)  |  <- expanding
    |                                      |
    | [SYNAPSE] Ready. What shall we       |
    | work on?                             |
    |                                      |
    | [You] Scatter rocks on terrain       |
    |                                      |
    | [SYNAPSE] Done -- created scatter    |
    | network at /obj/geo1/rock_scatter    |
    +--------------------------------------+
    | /obj/geo1  * Connected   3 nodes     |  <- context bar
    +--------------------------------------+
    | [Explain] [Make HDA] [Fix Error]     |  <- quick actions
    | [Optimize] [VEX Help]                |
    +--------------------------------------+
    | Type a message...          | Send |  |  <- input area
    +--------------------------------------+
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot, QTimer
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot, QTimer

from synapse.panel.chat_display import ChatDisplay
from synapse.panel.context_bar import ContextBar
from synapse.panel.ws_bridge import SynapseWSBridge
from synapse.panel.quick_actions import QUICK_ACTIONS
from synapse.panel.hda_views import DescribeView, BuildingView, ResultView
from synapse.panel.styles import get_hda_stylesheet, animate_stack_transition
from synapse.panel import tokens as t

# -- Design tokens (from canonical design system) -------------------------
_VOID = t.VOID
_GRAPHITE = t.GRAPHITE
_CARBON = t.CARBON
_NEAR_BLACK = t.NEAR_BLACK
_TEXT = t.TEXT
_TEXT_DIM = t.TEXT_DIM
_SIGNAL = t.SIGNAL
_GROW = t.GROW
_ERROR_COLOR = t.ERROR
_UI_PX = t.SIZE_UI
_BODY_PX = t.SIZE_BODY
_SMALL_PX = t.SIZE_SMALL
_LABEL_PX = t.SIZE_LABEL
_HOVER = t.HOVER
_FONT_MONO = t.FONT_MONO
_FONT_SANS = t.FONT_SANS

# How often to refresh context (ms)
_CONTEXT_POLL_MS = 2000


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

    def createInterface(self):
        """Build the panel layout and return the root QWidget.

        Returns
        -------
        QtWidgets.QWidget
            The root widget for the Houdini panel.
        """
        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(
            "QWidget {{ background: {bg}; "
            "font-family: '{sans}', 'Segoe UI', sans-serif; "
            "color: {fg}; }}".format(bg=_VOID, sans=_FONT_SANS, fg=_TEXT)
        )

        main_layout = QtWidgets.QVBoxLayout(self._root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- Mode toggle toolbar ----------------------------------------
        toolbar = self._build_mode_toolbar()
        main_layout.addWidget(toolbar)

        # -- Mode stack: Chat vs HDA ------------------------------------
        self._mode_stack = QtWidgets.QStackedWidget(self._root)
        self._mode_stack.setObjectName("ModeStack")

        # Index 0: Chat mode (existing layout wrapped in a widget)
        self._chat_widget = QtWidgets.QWidget()
        chat_layout = QtWidgets.QVBoxLayout(self._chat_widget)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(0)

        self._chat = ChatDisplay(self._chat_widget)
        self._chat.node_clicked.connect(self._on_node_clicked)
        chat_layout.addWidget(self._chat, stretch=1)

        self._context_bar = ContextBar(self._chat_widget)
        chat_layout.addWidget(self._context_bar)

        actions_widget = self._build_quick_actions()
        chat_layout.addWidget(actions_widget)

        input_widget = self._build_input_area()
        chat_layout.addWidget(input_widget)

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

        # -- HDA controller (wired in Phase 3, lazy import) -------------
        self._wire_hda_controller()

        # -- Context polling timer ---------------------------------------
        self._context_timer = QTimer(self._root)
        self._context_timer.timeout.connect(self._poll_context)
        self._context_timer.setInterval(_CONTEXT_POLL_MS)

        # -- Welcome message ---------------------------------------------
        self._chat.append_synapse_message(
            "Ready. What shall we work on?"
        )

        return self._root

    def onActivateInterface(self):
        """Panel becomes visible -- connect WS if not connected."""
        if self._bridge is not None and not self._bridge.isRunning():
            self._bridge.start()

        if self._context_timer is not None:
            self._context_timer.start()

    def onDeactivateInterface(self):
        """Panel hidden -- keep WS alive but pause UI updates."""
        if self._context_timer is not None:
            self._context_timer.stop()

    def onDestroyInterface(self):
        """Panel closing -- clean up bridge thread."""
        if self._context_timer is not None:
            self._context_timer.stop()

        if self._bridge is not None:
            self._bridge.stop()

    # -- UI builders -----------------------------------------------------

    def _build_quick_actions(self):
        """Build the quick action buttons row."""
        widget = QtWidgets.QWidget(self._root)
        widget.setStyleSheet(
            "background: {bg};".format(bg=_GRAPHITE)
        )

        # Use a flow layout via QHBoxLayout with wrapping
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        for action in QUICK_ACTIONS:
            btn = QtWidgets.QPushButton(action["label"], widget)
            btn.setToolTip(action.get("tooltip", ""))
            btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            btn.setStyleSheet(
                "QPushButton {{"
                "  background: {bg};"
                "  color: {fg};"
                "  border: 1px solid {border};"
                "  border-radius: 4px;"
                "  padding: 4px 12px;"
                "  font-family: '{mono}', 'Consolas', monospace;"
                "  font-size: {sz}px;"
                "}}"
                "QPushButton:hover {{"
                "  background: {hover};"
                "  border-color: {accent};"
                "  color: {white};"
                "}}"
                "QPushButton:pressed {{"
                "  background: rgba(0, 212, 255, 0.15);"
                "  border-color: {accent};"
                "  color: {accent};"
                "}}".format(
                    bg=_CARBON,
                    fg=_TEXT,
                    border=_NEAR_BLACK,
                    sz=_SMALL_PX,
                    hover=_HOVER,
                    accent=_SIGNAL,
                    white="#F0F0F0",
                    mono=_FONT_MONO,
                )
            )
            # Capture action in closure
            btn.clicked.connect(
                lambda checked=False, a=action: self._on_quick_action(a)
            )
            layout.addWidget(btn)

        layout.addStretch()
        return widget

    def _build_input_area(self):
        """Build the message input field and send button."""
        widget = QtWidgets.QWidget(self._root)
        widget.setStyleSheet(
            "background: {bg};".format(bg=_GRAPHITE)
        )

        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(8)

        # Text input
        self._input = QtWidgets.QLineEdit(widget)
        self._input.setPlaceholderText("Type a message...")
        self._input.setStyleSheet(
            "QLineEdit {{"
            "  background: {bg};"
            "  color: {fg};"
            "  border: 1px solid {border};"
            "  border-radius: 6px;"
            "  padding: 8px 12px;"
            "  font-family: '{sans}', 'Segoe UI', sans-serif;"
            "  font-size: {sz}px;"
            "}}"
            "QLineEdit:focus {{"
            "  border: 1px solid {accent};"
            "}}".format(
                bg=_VOID,
                fg=_TEXT,
                border=_NEAR_BLACK,
                sz=_UI_PX,
                accent=_SIGNAL,
                sans=_FONT_SANS,
            )
        )
        self._input.returnPressed.connect(self._send_message)
        layout.addWidget(self._input, stretch=1)

        # Send button
        self._send_btn = QtWidgets.QPushButton("Send", widget)
        self._send_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._send_btn.setStyleSheet(
            "QPushButton {{"
            "  background: {accent};"
            "  color: {bg};"
            "  border: none;"
            "  border-radius: 6px;"
            "  padding: 8px 20px;"
            "  font-family: '{mono}', 'Consolas', monospace;"
            "  font-size: {sz}px;"
            "  font-weight: 700;"
            "  letter-spacing: 1px;"
            "}}"
            "QPushButton:hover {{"
            "  background: {hover};"
            "}}"
            "QPushButton:pressed {{"
            "  background: {pressed};"
            "}}".format(
                accent=_SIGNAL,
                bg=_VOID,
                sz=_UI_PX,
                hover=t.SIGNAL_HOVER,
                pressed=t.SIGNAL_PRESS,
                mono=_FONT_MONO,
            )
        )
        self._send_btn.clicked.connect(self._send_message)
        layout.addWidget(self._send_btn)

        return widget

    # -- Connection bar --------------------------------------------------

    def _build_connection_bar(self):
        """Build the bottom connection status and controls.

        Styled to match the SYNAPSE design system connection_frame pattern:
        mono font, SIGNAL cyan accents, canonical GROW/ERROR status colors.
        """
        import os

        _port = int(os.environ.get("SYNAPSE_PORT", "9999"))
        _path = os.environ.get("SYNAPSE_PATH", "/synapse")
        self._ws_url = "ws://localhost:{}{}".format(_port, _path)

        frame = QtWidgets.QWidget(self._root)
        frame.setObjectName("connection_frame")
        frame.setStyleSheet(
            "QWidget#connection_frame {{"
            "  background: {bg};"
            "  border-top: 1px solid {border};"
            "}}".format(bg=_CARBON, border=_GRAPHITE)
        )
        layout = QtWidgets.QHBoxLayout(frame)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Status dot
        self._conn_dot = QtWidgets.QLabel("\u25CF")
        self._conn_dot.setObjectName("status_dot")
        self._conn_dot.setStyleSheet(
            "color: {c}; font-size: 18px; border: none;".format(c=_ERROR_COLOR)
        )
        layout.addWidget(self._conn_dot)

        # Status label
        self._conn_label = QtWidgets.QLabel("Disconnected")
        self._conn_label.setObjectName("status_label")
        self._conn_label.setStyleSheet(
            "color: {c}; font-family: '{mono}', 'Consolas', monospace;"
            " font-size: {sz}px; letter-spacing: 1px;"
            " border: none;".format(
                c=_ERROR_COLOR, mono=_FONT_MONO, sz=_SMALL_PX,
            )
        )
        layout.addWidget(self._conn_label)

        layout.addStretch()

        # Connect/Disconnect button (matches design system connect_button)
        self._conn_btn = QtWidgets.QPushButton("Connect")
        self._conn_btn.setObjectName("connect_button")
        self._conn_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self._conn_btn.setStyleSheet(
            "QPushButton#connect_button {{"
            "  background: transparent;"
            "  color: {accent};"
            "  border: 1px solid {accent};"
            "  border-radius: 3px;"
            "  font-family: '{mono}', 'Consolas', monospace;"
            "  font-size: {sz}px;"
            "  padding: 4px 12px;"
            "  min-width: 100px;"
            "}}"
            "QPushButton#connect_button:hover {{"
            "  background: rgba(0, 212, 255, 0.1);"
            "}}"
            "QPushButton#connect_button:pressed {{"
            "  background: rgba(0, 212, 255, 0.2);"
            "}}".format(
                accent=_SIGNAL, mono=_FONT_MONO, sz=_SMALL_PX,
            )
        )
        self._conn_btn.clicked.connect(self._on_connect_toggle)
        layout.addWidget(self._conn_btn)

        # WS URL button (matches design system ws_path_button)
        ws_btn = QtWidgets.QPushButton(self._ws_url)
        ws_btn.setObjectName("ws_path_button")
        ws_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        ws_btn.setStyleSheet(
            "QPushButton#ws_path_button {{"
            "  background: transparent;"
            "  color: {slate};"
            "  border: 1px solid {border};"
            "  border-radius: 3px;"
            "  font-family: '{mono}', 'Consolas', monospace;"
            "  font-size: {sz}px;"
            "  padding: 4px 8px;"
            "}}"
            "QPushButton#ws_path_button:hover {{"
            "  color: {accent};"
            "  border-color: {accent};"
            "  background: rgba(0, 212, 255, 0.1);"
            "}}"
            "QPushButton#ws_path_button:pressed {{"
            "  background: rgba(0, 212, 255, 0.2);"
            "}}".format(
                slate=t.SLATE, border=_GRAPHITE, mono=_FONT_MONO,
                sz=_LABEL_PX, accent=_SIGNAL,
            )
        )
        ws_btn.setToolTip("Copy WebSocket URL to clipboard")
        ws_btn.clicked.connect(self._on_copy_ws_url)
        layout.addWidget(ws_btn)

        frame.setFixedHeight(44)
        return frame

    def _on_connect_toggle(self):
        """Start or stop the WebSocket bridge."""
        if self._bridge is not None and self._bridge.isRunning():
            self._bridge.stop()
        else:
            if self._bridge is not None:
                self._bridge.start()

    def _on_copy_ws_url(self):
        """Copy WebSocket URL to clipboard."""
        import subprocess, platform
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
        toolbar.setStyleSheet(
            "background: {bg}; border-bottom: 1px solid {border};".format(
                bg=_GRAPHITE, border=_CARBON
            )
        )
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
            self._hda_stack.setCurrentIndex(0)  # Reset to Describe
            self.describe_view.reset()
            self._mode_chat_btn.setObjectName("ModeToggleInactive")
            self._mode_hda_btn.setObjectName("ModeToggleActive")

        # Refresh styling after objectName change
        for btn in (self._mode_chat_btn, self._mode_hda_btn):
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _wire_hda_controller(self):
        """Connect HDA views to the controller and bridge signals."""
        from synapse.panel.hda_controller import HdaController

        self._hda_controller = HdaController(self._bridge)

        # Describe -> Controller
        self.describe_view.generate_requested.connect(
            self._hda_controller.execute
        )

        # Controller -> Building
        self._hda_controller.progress.connect(
            self.building_view.update_stage
        )

        # Auto-switch to Building view when generation starts
        self.describe_view.generate_requested.connect(
            lambda *_: animate_stack_transition(self._hda_stack, 1)
        )

        # Controller -> Result
        self._hda_controller.result.connect(self._on_hda_result)

        # Result actions
        self.result_view.action_requested.connect(self._on_hda_action)

        # Cancel -> back to Describe
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
            # Navigate to the created HDA in the network editor
            path = self.result_view.path_label.text()
            if path:
                self._on_node_clicked(path)
        elif action == "save":
            # Could trigger file dialog in future
            pass

    # -- Actions ---------------------------------------------------------

    def _send_message(self):
        """Read input field, send via WS bridge, clear input."""
        text = self._input.text().strip()
        if not text:
            return

        self._input.clear()
        self._chat.append_user_message(text)

        # Gather context on main thread
        context = None
        try:
            if self._bridge is not None:
                context = self._bridge.gather_context()
        except Exception:
            pass

        if self._bridge is not None:
            self._bridge.send_command("execute_python", {
                "content": text,
                "context": context,
            })
        else:
            self._chat.append_system_message(
                "Not connected to SYNAPSE server."
            )

    @Slot(dict)
    def _on_response(self, response):
        """Handle server response -- format and append to chat."""
        status = response.get("status", "")
        if status == "error":
            self._chat.append_synapse_message(response)
        else:
            self._chat.append_synapse_message(response)

    @Slot(bool)
    def _on_status_changed(self, connected):
        """Handle connection status change -- update context bar and connection bar."""
        self._context_bar.set_connected(connected)

        # Update connection bar widgets
        if connected:
            _sc = _GROW
            self._conn_dot.setStyleSheet(
                "color: {c}; font-size: 18px; border: none;".format(c=_sc)
            )
            self._conn_label.setText("Connected")
            self._conn_label.setStyleSheet(
                "color: {c}; font-family: '{mono}', 'Consolas', monospace;"
                " font-size: {sz}px; letter-spacing: 1px;"
                " border: none;".format(c=_sc, mono=_FONT_MONO, sz=_SMALL_PX)
            )
            self._conn_btn.setText("Disconnect")
            self._chat.append_system_message("Connected to SYNAPSE server.")
        else:
            _sc = _ERROR_COLOR
            self._conn_dot.setStyleSheet(
                "color: {c}; font-size: 18px; border: none;".format(c=_sc)
            )
            self._conn_label.setText("Disconnected")
            self._conn_label.setStyleSheet(
                "color: {c}; font-family: '{mono}', 'Consolas', monospace;"
                " font-size: {sz}px; letter-spacing: 1px;"
                " border: none;".format(c=_sc, mono=_FONT_MONO, sz=_SMALL_PX)
            )
            self._conn_btn.setText("Connect")
            self._chat.append_system_message(
                "Disconnected from SYNAPSE server. Reconnecting..."
            )

    @Slot(dict)
    def _on_context_updated(self, context):
        """Update context bar with fresh scene state."""
        self._context_bar.set_network_path(
            context.get("current_network", "")
        )
        self._context_bar.set_selection_count(
            len(context.get("selected_nodes", []))
        )
        self._context_bar.set_frame(context.get("frame", 1.0))

    def _on_quick_action(self, action):
        """Handle quick action button press."""
        prompt = action.get("prompt", "")
        requires_sel = action.get("requires_selection", False)

        # Check selection requirement
        if requires_sel:
            context = None
            try:
                if self._bridge is not None:
                    context = self._bridge.gather_context()
            except Exception:
                pass

            if context and not context.get("selected_nodes"):
                self._chat.append_system_message(
                    "Please select one or more nodes first."
                )
                return
        else:
            context = None
            try:
                if self._bridge is not None:
                    context = self._bridge.gather_context()
            except Exception:
                pass

        # Display as user message
        label = action.get("label", "Action")
        self._chat.append_user_message("[{label}] {prompt}".format(
            label=label, prompt=prompt
        ))

        # Send to server
        if self._bridge is not None:
            self._bridge.send_command("execute_python", {
                "content": prompt,
                "context": context,
            })

    def _on_node_clicked(self, node_path):
        """Navigate to a clicked node path in the network editor."""
        try:
            import hou

            node = hou.node(node_path)
            if node is not None:
                # Select the node
                node.setSelected(True, clear_all_selected=True)
                # Navigate network editor to it
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

    def _poll_context(self):
        """Periodically refresh scene context for the context bar."""
        if self._bridge is not None and self._bridge.connected:
            try:
                self._bridge.gather_context()
            except Exception:
                pass
