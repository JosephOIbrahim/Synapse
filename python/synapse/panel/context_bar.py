"""Inline context chips for the Synapse chat input area.

Replaces the old fixed-height ContextBar with compact pill-shaped chips
that sit above the text input. Each chip shows contextual info:
- Network path (e.g. /obj/geo1)
- Selection count (e.g. 3 nodes)
- Current frame (e.g. F24)
- Connection LED (green/red dot)
- Project name + evolution stage (if available)
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot

from synapse.panel import tokens as _t


class ContextChips(QtWidgets.QWidget):
    """Inline context pills for the input area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._network_path = ""
        self._selection_count = 0
        self._frame = 1.0
        self._project_name = ""
        self._evolution_stage = ""
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Connection LED chip (just a dot)
        self._led = QtWidgets.QLabel()
        self._led.setFixedSize(10, 10)
        self._update_led()
        layout.addWidget(self._led)

        # Network path chip
        self._path_chip = self._make_chip("")
        self._path_chip.setStyleSheet(self._chip_style(accent=True))
        layout.addWidget(self._path_chip)

        # Selection chip
        self._sel_chip = self._make_chip("")
        layout.addWidget(self._sel_chip)

        # Frame chip
        self._frame_chip = self._make_chip("F1")
        layout.addWidget(self._frame_chip)

        # Project chip (evolution stage)
        self._project_chip = self._make_chip("")
        layout.addWidget(self._project_chip)

        layout.addStretch()

        # Start with chips hidden until data arrives
        self._path_chip.setVisible(False)
        self._sel_chip.setVisible(False)
        self._frame_chip.setVisible(False)
        self._project_chip.setVisible(False)

        self.setFixedHeight(24)

    def _make_chip(self, text):
        """Create a pill-shaped QLabel chip."""
        label = QtWidgets.QLabel(text, self)
        label.setStyleSheet(self._chip_style())
        label.setAlignment(QtCore.Qt.AlignCenter)
        return label

    def _chip_style(self, accent=False):
        """Return stylesheet for a context chip."""
        fg = _t.SIGNAL if accent else _t.TEXT_DIM
        return (
            "background: {bg}; border: 1px solid {border}; "
            "border-radius: 10px; padding: 2px 8px; "
            "font-size: {sz}px; color: {fg}; "
            "font-family: '{mono}', 'Consolas', monospace;"
        ).format(
            bg=_t.GRAPHITE, border=_t.CARBON, sz=_t.SIZE_LABEL,
            fg=fg, mono=_t.FONT_MONO,
        )

    def _update_led(self):
        color = _t.GROW if self._connected else _t.ERROR
        self._led.setStyleSheet(
            "background: {c}; border-radius: 5px; border: none;".format(c=color)
        )

    @Slot(bool)
    def set_connected(self, connected):
        """Update connection status display."""
        self._connected = connected
        self._update_led()

    def set_network_path(self, path):
        """Update displayed network path."""
        self._network_path = path
        if path:
            self._path_chip.setText(path)
            self._path_chip.setVisible(True)
        else:
            self._path_chip.setVisible(False)

    def set_selection_count(self, count):
        """Update selected node count."""
        self._selection_count = count
        if count > 0:
            self._sel_chip.setText(
                "{n} node{s}".format(n=count, s="s" if count != 1 else "")
            )
            self._sel_chip.setVisible(True)
        else:
            self._sel_chip.setVisible(False)

    def set_frame(self, frame):
        """Update current frame display."""
        self._frame = frame
        if float(frame) == int(frame):
            self._frame_chip.setText("F{f}".format(f=int(frame)))
        else:
            self._frame_chip.setText("F{f:.1f}".format(f=frame))
        self._frame_chip.setVisible(True)

    def set_project_context(self, project_name, evolution_stage=""):
        """Update project name and evolution stage chip."""
        self._project_name = project_name
        self._evolution_stage = evolution_stage
        if project_name:
            text = project_name
            if evolution_stage:
                text = "{} | {}".format(project_name, evolution_stage)
            self._project_chip.setText(text)
            self._project_chip.setVisible(True)
        else:
            self._project_chip.setVisible(False)


# Backwards compatibility alias
ContextBar = ContextChips
