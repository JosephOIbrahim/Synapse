"""Context bar widget showing selection, connection state, and frame info.

Displays a horizontal status bar at the bottom of the chat panel with:
- Current network path (from active network editor)
- Connection status LED (green = connected, red = disconnected)
- Selected node count
- Current frame number
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal, Slot
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal, Slot

# -- Design tokens -------------------------------------------------------
_GRAPHITE = "#222222"
_CARBON = "#333333"
_TEXT = "#E0E0E0"
_TEXT_DIM = "#999999"
_SIGNAL = "#00D4FF"
_SUCCESS = "#6BCB77"
_ERROR = "#FF6B6B"
_UI_PX = 24
_SMALL_PX = 22


class ContextBar(QtWidgets.QWidget):
    """Horizontal status bar for the Synapse chat panel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected = False
        self._network_path = ""
        self._selection_count = 0
        self._frame = 1.0
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(12)

        self.setStyleSheet(
            "background: {bg}; border-top: 1px solid {border};".format(
                bg=_GRAPHITE, border=_CARBON
            )
        )

        # Network path label
        self._path_label = QtWidgets.QLabel("")
        self._path_label.setStyleSheet(
            "color: {c}; font-size: {s}px; font-family: 'JetBrains Mono', "
            "'Consolas', monospace; border: none;".format(c=_SIGNAL, s=_SMALL_PX)
        )
        layout.addWidget(self._path_label)

        layout.addStretch()

        # Selection count
        self._sel_label = QtWidgets.QLabel("")
        self._sel_label.setStyleSheet(
            "color: {c}; font-size: {s}px; border: none;".format(
                c=_TEXT_DIM, s=_SMALL_PX
            )
        )
        layout.addWidget(self._sel_label)

        # Frame label
        self._frame_label = QtWidgets.QLabel("F1")
        self._frame_label.setStyleSheet(
            "color: {c}; font-size: {s}px; border: none;".format(
                c=_TEXT_DIM, s=_SMALL_PX
            )
        )
        layout.addWidget(self._frame_label)

        # Connection LED
        self._led = QtWidgets.QLabel()
        self._led.setFixedSize(12, 12)
        self._update_led()
        layout.addWidget(self._led)

        # Connection text
        self._conn_label = QtWidgets.QLabel("Disconnected")
        self._conn_label.setStyleSheet(
            "color: {c}; font-size: {s}px; border: none;".format(
                c=_TEXT_DIM, s=_SMALL_PX
            )
        )
        layout.addWidget(self._conn_label)

        self.setFixedHeight(36)

    def _update_led(self):
        color = _SUCCESS if self._connected else _ERROR
        self._led.setStyleSheet(
            "background: {c}; border-radius: 6px; border: none;".format(c=color)
        )

    @Slot(bool)
    def set_connected(self, connected):
        """Update connection status display."""
        self._connected = connected
        self._update_led()
        self._conn_label.setText("Connected" if connected else "Disconnected")
        color = _TEXT_DIM if connected else _ERROR
        self._conn_label.setStyleSheet(
            "color: {c}; font-size: {s}px; border: none;".format(
                c=color, s=_SMALL_PX
            )
        )

    def set_network_path(self, path):
        """Update displayed network path."""
        self._network_path = path
        self._path_label.setText(path if path else "")

    def set_selection_count(self, count):
        """Update selected node count."""
        self._selection_count = count
        if count > 0:
            self._sel_label.setText(
                "{n} node{s}".format(n=count, s="s" if count != 1 else "")
            )
        else:
            self._sel_label.setText("")

    def set_frame(self, frame):
        """Update current frame display."""
        self._frame = frame
        if float(frame) == int(frame):
            self._frame_label.setText("F{f}".format(f=int(frame)))
        else:
            self._frame_label.setText("F{f:.1f}".format(f=frame))
