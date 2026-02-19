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

# -- Design tokens -------------------------------------------------------
_VOID = "#252525"
_GRAPHITE = "#222222"
_CARBON = "#333333"
_NEAR_BLACK = "#3C3C3C"
_TEXT = "#E0E0E0"
_TEXT_DIM = "#999999"
_SIGNAL = "#00D4FF"
_UI_PX = 24
_BODY_PX = 26
_SMALL_PX = 22

# Hover color for buttons
_HOVER = "#484848"

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

    def createInterface(self):
        """Build the panel layout and return the root QWidget.

        Returns
        -------
        QtWidgets.QWidget
            The root widget for the Houdini panel.
        """
        self._root = QtWidgets.QWidget()
        self._root.setStyleSheet(
            "QWidget {{ background: {bg}; }}".format(bg=_VOID)
        )

        main_layout = QtWidgets.QVBoxLayout(self._root)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # -- Chat display (expanding) ------------------------------------
        self._chat = ChatDisplay(self._root)
        self._chat.node_clicked.connect(self._on_node_clicked)
        main_layout.addWidget(self._chat, stretch=1)

        # -- Context bar -------------------------------------------------
        self._context_bar = ContextBar(self._root)
        main_layout.addWidget(self._context_bar)

        # -- Quick actions -----------------------------------------------
        actions_widget = self._build_quick_actions()
        main_layout.addWidget(actions_widget)

        # -- Input area --------------------------------------------------
        input_widget = self._build_input_area()
        main_layout.addWidget(input_widget)

        # -- WebSocket bridge --------------------------------------------
        self._bridge = SynapseWSBridge(self._root)
        self._bridge.response_received.connect(self._on_response)
        self._bridge.status_changed.connect(self._on_status_changed)
        self._bridge.context_updated.connect(self._on_context_updated)

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
                "  font-size: {sz}px;"
                "}}"
                "QPushButton:hover {{"
                "  background: {hover};"
                "}}"
                "QPushButton:pressed {{"
                "  background: {pressed};"
                "}}".format(
                    bg=_CARBON,
                    fg=_TEXT,
                    border=_NEAR_BLACK,
                    sz=_SMALL_PX,
                    hover=_HOVER,
                    pressed=_SIGNAL,
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
            "  font-size: {sz}px;"
            "  font-weight: bold;"
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
                hover="#33DDFF",
                pressed="#00AADD",
            )
        )
        self._send_btn.clicked.connect(self._send_message)
        layout.addWidget(self._send_btn)

        return widget

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
        """Handle connection status change."""
        self._context_bar.set_connected(connected)
        if connected:
            self._chat.append_system_message("Connected to SYNAPSE server.")
        else:
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
