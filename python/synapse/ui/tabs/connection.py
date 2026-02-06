"""
Synapse Connection Tab

Server status and controls for the WebSocket server.
"""

from typing import Optional

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

try:
    from ...server.websocket import SynapseServer
    SERVER_AVAILABLE = True
except ImportError:
    SERVER_AVAILABLE = False
    SynapseServer = None


class ConnectionTab(QtWidgets.QWidget):
    """Tab for server connection status and controls."""

    server_started = QtCore.Signal()
    server_stopped = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server: Optional['SynapseServer'] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Server Status")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        # Status group
        status_group = QtWidgets.QGroupBox("Connection")
        status_layout = QtWidgets.QFormLayout(status_group)

        self.status_indicator = QtWidgets.QLabel("Stopped")
        self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
        status_layout.addRow("Status:", self.status_indicator)

        self.port_label = QtWidgets.QLabel("9999")
        status_layout.addRow("Port:", self.port_label)

        self.clients_label = QtWidgets.QLabel("0")
        status_layout.addRow("Clients:", self.clients_label)

        self.protocol_label = QtWidgets.QLabel("4.0.0")
        status_layout.addRow("Protocol:", self.protocol_label)

        layout.addWidget(status_group)

        # Server controls
        controls_group = QtWidgets.QGroupBox("Controls")
        controls_layout = QtWidgets.QVBoxLayout(controls_group)

        # Port input
        port_row = QtWidgets.QHBoxLayout()
        port_row.addWidget(QtWidgets.QLabel("Port:"))
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(9999)
        port_row.addWidget(self.port_input)
        port_row.addStretch()
        controls_layout.addLayout(port_row)

        # Start/Stop buttons
        btn_row = QtWidgets.QHBoxLayout()

        self.start_btn = QtWidgets.QPushButton("Start Server")
        self.start_btn.clicked.connect(self._start_server)
        btn_row.addWidget(self.start_btn)

        self.stop_btn = QtWidgets.QPushButton("Stop Server")
        self.stop_btn.clicked.connect(self._stop_server)
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        controls_layout.addLayout(btn_row)

        layout.addWidget(controls_group)

        # Health status
        health_group = QtWidgets.QGroupBox("Health")
        health_layout = QtWidgets.QFormLayout(health_group)

        self.health_indicator = QtWidgets.QLabel("Unknown")
        health_layout.addRow("Level:", self.health_indicator)

        self.rate_limit_label = QtWidgets.QLabel("-")
        health_layout.addRow("Rate Limit:", self.rate_limit_label)

        self.circuit_label = QtWidgets.QLabel("-")
        health_layout.addRow("Circuit:", self.circuit_label)

        layout.addWidget(health_group)

        # Connection URL
        url_group = QtWidgets.QGroupBox("Connect")
        url_layout = QtWidgets.QVBoxLayout(url_group)

        self.url_label = QtWidgets.QLabel("ws://localhost:9999")
        self.url_label.setStyleSheet("font-family: monospace;")
        self.url_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        url_layout.addWidget(self.url_label)

        copy_btn = QtWidgets.QPushButton("Copy URL")
        copy_btn.clicked.connect(self._copy_url)
        url_layout.addWidget(copy_btn)

        layout.addWidget(url_group)

        layout.addStretch()

        # Check if server module available
        if not SERVER_AVAILABLE:
            self.start_btn.setEnabled(False)
            self.status_indicator.setText("Unavailable")
            self.status_indicator.setStyleSheet("font-weight: bold; color: #F44336;")

    def set_server(self, server: 'SynapseServer'):
        """Set the server instance to control."""
        self._server = server
        self._update_status()

    def _start_server(self):
        """Start the WebSocket server."""
        if not SERVER_AVAILABLE:
            return

        if self._server is None:
            from ...server.websocket import SynapseServer
            port = self.port_input.value()
            self._server = SynapseServer(port=port)

        if not self._server.is_running:
            self._server.start()
            self._update_status()
            self.server_started.emit()

    def _stop_server(self):
        """Stop the WebSocket server."""
        if self._server and self._server.is_running:
            self._server.stop()
            self._update_status()
            self.server_stopped.emit()

    def _update_status(self):
        """Update status display."""
        if self._server and self._server.is_running:
            self.status_indicator.setText("Running")
            self.status_indicator.setStyleSheet("font-weight: bold; color: #4CAF50;")
            self.port_label.setText(str(self._server.actual_port))
            self.clients_label.setText(str(self._server.client_count))
            self.url_label.setText(f"ws://localhost:{self._server.actual_port}")
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.port_input.setEnabled(False)

            # Health
            health = self._server.get_health()
            self.health_indicator.setText(health.get("level", "unknown"))
            if health.get("healthy"):
                self.health_indicator.setStyleSheet("color: #4CAF50;")
            else:
                self.health_indicator.setStyleSheet("color: #F44336;")
        else:
            self.status_indicator.setText("Stopped")
            self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
            self.clients_label.setText("0")
            self.start_btn.setEnabled(SERVER_AVAILABLE)
            self.stop_btn.setEnabled(False)
            self.port_input.setEnabled(True)
            self.health_indicator.setText("-")
            self.health_indicator.setStyleSheet("")

    def _copy_url(self):
        """Copy connection URL to clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.url_label.text())

    def heartbeat(self):
        """Called by timer to update status and feed watchdog."""
        if self._server:
            self._server.heartbeat()
            self._update_status()
