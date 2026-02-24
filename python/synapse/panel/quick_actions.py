"""Quick action definitions and collapsible pill widget for the Synapse chat panel.

Provides three modes of access:
1. Pill chips (compact row above input, collapsible)
2. Collapsible toolbar (chevron toggle)
3. Right-click context menu entries (data only -- menu built in chat_panel.py)

The data dicts (QUICK_ACTIONS, CONTEXT_MENU_EXTRAS) are always importable.
The QuickActionPills widget requires PySide6/PySide2 at runtime (Houdini).
"""

QUICK_ACTIONS = [
    {
        "label": "Explain",
        "icon": "BUTTONS_help",
        "prompt": (
            "Explain the selected node network. What does each node do "
            "and how does data flow through them?"
        ),
        "requires_selection": True,
        "tooltip": "Explain selected network",
    },
    {
        "label": "Make HDA",
        "icon": "COMMON_subnet",
        "prompt": (
            "Package the selected subnet into an HDA with a clean "
            "interface and help card."
        ),
        "requires_selection": True,
        "tooltip": "Convert selection to HDA",
    },
    {
        "label": "Fix Error",
        "icon": "STATUS_warning",
        "prompt": (
            "The selected node has a cook error. Diagnose the issue "
            "and suggest a fix."
        ),
        "requires_selection": True,
        "tooltip": "Diagnose cook errors",
    },
    {
        "label": "Optimize",
        "icon": "BUTTONS_resimulate",
        "prompt": (
            "Analyze this network for performance issues and suggest "
            "optimizations."
        ),
        "requires_selection": True,
        "tooltip": "Performance analysis",
    },
    {
        "label": "VEX Help",
        "icon": "SOP_attribwrangle",
        "prompt": (
            "Help me write VEX code for the selected wrangle node. "
            "What should the code do?"
        ),
        "requires_selection": True,
        "tooltip": "VEX coding assistance",
    },
]

# Additional actions for the right-click context menu (appended to QUICK_ACTIONS)
CONTEXT_MENU_EXTRAS = [
    {
        "label": "Clear Chat",
        "prompt": None,
        "action": "clear_chat",
        "requires_selection": False,
        "tooltip": "Clear all chat history",
    },
    {
        "label": "Copy Last Response",
        "prompt": None,
        "action": "copy_last",
        "requires_selection": False,
        "tooltip": "Copy the last SYNAPSE response to clipboard",
    },
    {
        "label": "Toggle Quick Actions",
        "prompt": None,
        "action": "toggle_actions",
        "requires_selection": False,
        "tooltip": "Show/hide the quick action pills",
    },
]


# -- Widget (requires Qt) ------------------------------------------------

try:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        from PySide6.QtCore import Signal
    except ImportError:
        from PySide2 import QtWidgets, QtCore, QtGui
        from PySide2.QtCore import Signal

    from synapse.panel import tokens as _t

    class QuickActionPills(QtWidgets.QWidget):
        """Collapsible row of pill-shaped quick action chips.

        Emits ``action_triggered(dict)`` when a pill is clicked.
        """

        action_triggered = Signal(dict)

        def __init__(self, parent=None):
            super().__init__(parent)
            self._expanded = True
            self._pills = []
            self._build_ui()

        def _build_ui(self):
            self._outer_layout = QtWidgets.QHBoxLayout(self)
            self._outer_layout.setContentsMargins(8, 4, 8, 4)
            self._outer_layout.setSpacing(0)

            # Chevron toggle
            self._chevron = QtWidgets.QPushButton(self)
            self._chevron.setFixedSize(20, 20)
            self._chevron.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            self._chevron.setToolTip("Toggle quick actions")
            self._chevron.clicked.connect(self._toggle)
            self._update_chevron()
            self._chevron.setStyleSheet(
                "QPushButton {{ background: transparent; border: none; "
                "color: {fg}; font-size: 14px; }}"
                "QPushButton:hover {{ color: {hover}; }}".format(
                    fg=_t.TEXT_DIM, hover=_t.SIGNAL,
                )
            )
            self._outer_layout.addWidget(self._chevron)

            # Pills container
            self._pills_container = QtWidgets.QWidget(self)
            self._pills_layout = QtWidgets.QHBoxLayout(self._pills_container)
            self._pills_layout.setContentsMargins(4, 0, 0, 0)
            self._pills_layout.setSpacing(6)

            for action in QUICK_ACTIONS:
                pill = QtWidgets.QPushButton(action["label"], self._pills_container)
                pill.setToolTip(action.get("tooltip", ""))
                pill.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
                pill.setStyleSheet(self._pill_stylesheet())
                pill.clicked.connect(
                    lambda checked=False, a=action: self.action_triggered.emit(a)
                )
                self._pills_layout.addWidget(pill)
                self._pills.append(pill)

            self._pills_layout.addStretch()
            self._outer_layout.addWidget(self._pills_container, stretch=1)

        def _pill_stylesheet(self):
            """Stylesheet for a quick action pill chip."""
            return (
                "QPushButton {{"
                "  background: {bg};"
                "  color: {fg};"
                "  border: 1px solid {border};"
                "  border-radius: 14px;"
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
                    bg=_t.CARBON, fg=_t.BONE, border=_t.GRAPHITE,
                    sz=_t.SIZE_LABEL, hover=_t.HOVER,
                    accent=_t.SIGNAL, white=_t.WHITE, mono=_t.FONT_MONO,
                )
            )

        def _update_chevron(self):
            """Update chevron arrow direction."""
            arrow = "\u25B8" if not self._expanded else "\u25BE"
            self._chevron.setText(arrow)

        def _toggle(self):
            """Toggle pill visibility."""
            self._expanded = not self._expanded
            self._pills_container.setVisible(self._expanded)
            self._update_chevron()

        def set_expanded(self, expanded):
            """Programmatically expand/collapse."""
            self._expanded = expanded
            self._pills_container.setVisible(expanded)
            self._update_chevron()

except ImportError:
    # No Qt available -- provide a stub so imports don't break
    class QuickActionPills:
        """Stub -- requires PySide6/PySide2 at runtime."""
        def __init__(self, *args, **kwargs):
            raise ImportError("QuickActionPills requires PySide6 or PySide2")
