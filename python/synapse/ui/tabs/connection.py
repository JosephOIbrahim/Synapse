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
    import hou
    _HOU = True
except ImportError:
    _HOU = False

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

    # How often the full UI refresh runs (every N heartbeats)
    _UI_REFRESH_INTERVAL = 2  # 10s at 5s timer interval

    def __init__(self, parent=None):
        super().__init__(parent)
        self._server: Optional['SynapseServer'] = None
        self._tick = 0  # heartbeat counter
        # Cached UI state for dirty-flag diffing (avoids redundant setStyleSheet)
        self._ui_state = {
            "status": None,
            "clients": None,
            "url": None,
            "health_level": None,
            "healthy": None,
            "running": None,
        }
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(16)

        # --- Status + Controls (merged) ---
        server_group = QtWidgets.QGroupBox("WebSocket Server")
        server_layout = QtWidgets.QVBoxLayout(server_group)
        server_layout.setSpacing(12)

        # Status row
        status_row = QtWidgets.QHBoxLayout()
        status_row.setSpacing(16)

        self.status_indicator = QtWidgets.QLabel("Stopped")
        self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
        status_row.addWidget(self.status_indicator)

        self.clients_label = QtWidgets.QLabel("0 clients")
        self.clients_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        status_row.addWidget(self.clients_label)

        self.protocol_label = QtWidgets.QLabel("v4.0.0")
        self.protocol_label.setStyleSheet("color: palette(mid); font-size: 10px;")
        status_row.addWidget(self.protocol_label)

        status_row.addStretch()
        server_layout.addLayout(status_row)

        # Port + buttons row
        controls_row = QtWidgets.QHBoxLayout()
        controls_row.setSpacing(8)

        controls_row.addWidget(QtWidgets.QLabel("Port:"))
        self.port_input = QtWidgets.QSpinBox()
        self.port_input.setRange(1024, 65535)
        self.port_input.setValue(9999)
        self.port_input.setFixedWidth(80)
        controls_row.addWidget(self.port_input)

        self.port_label = QtWidgets.QLabel("9999")
        self.port_label.setVisible(False)

        controls_row.addSpacing(12)

        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.clicked.connect(self._start_server)
        controls_row.addWidget(self.start_btn)

        self.stop_btn = QtWidgets.QPushButton("Stop")
        self.stop_btn.clicked.connect(self._stop_server)
        self.stop_btn.setEnabled(False)
        controls_row.addWidget(self.stop_btn)

        controls_row.addStretch()
        server_layout.addLayout(controls_row)

        # URL row
        url_row = QtWidgets.QHBoxLayout()
        url_row.setSpacing(8)

        self.url_label = QtWidgets.QLabel("ws://localhost:9999")
        self.url_label.setStyleSheet("font-family: monospace; font-size: 11px;")
        self.url_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        url_row.addWidget(self.url_label)

        copy_btn = QtWidgets.QPushButton("Copy URL")
        copy_btn.setMinimumWidth(64)
        copy_btn.clicked.connect(self._copy_url)
        url_row.addWidget(copy_btn)

        server_layout.addLayout(url_row)
        layout.addWidget(server_group)

        # --- Health (compact) ---
        health_group = QtWidgets.QGroupBox("Health")
        health_layout = QtWidgets.QHBoxLayout(health_group)
        health_layout.setSpacing(20)

        self.health_indicator = QtWidgets.QLabel("Unknown")
        health_layout.addWidget(QtWidgets.QLabel("Level:"))
        health_layout.addWidget(self.health_indicator)

        self.rate_limit_label = QtWidgets.QLabel("-")
        health_layout.addWidget(QtWidgets.QLabel("Rate:"))
        health_layout.addWidget(self.rate_limit_label)

        self.circuit_label = QtWidgets.QLabel("-")
        health_layout.addWidget(QtWidgets.QLabel("Circuit:"))
        health_layout.addWidget(self.circuit_label)

        health_layout.addStretch()
        layout.addWidget(health_group)

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

        # Check for existing running server on hou.session first
        if self._server is None and _HOU:
            try:
                if hasattr(hou.session, '_synapse_server'):
                    srv = hou.session._synapse_server
                    if srv and getattr(srv, 'is_running', False):
                        self._server = srv
                        self._update_status()
                        self.server_started.emit()
                        return
            except:
                pass

        if self._server is None:
            from ...server.websocket import SynapseServer
            port = self.port_input.value()
            self._server = SynapseServer(port=port)

        if not self._server.is_running:
            self._server.start()
            # Store on hou.session so it survives panel reloads
            if _HOU:
                try:
                    hou.session._synapse_server = self._server
                except:
                    pass
            self._update_status()
            self.server_started.emit()

    def _stop_server(self):
        """Stop the WebSocket server."""
        if self._server and self._server.is_running:
            self._server.stop()
            self._update_status()
            self.server_stopped.emit()

    def _update_status(self):
        """Update status display — uses dirty-flag diffing to skip redundant updates."""
        if self._server and self._server.is_running:
            running = True
            clients = f"{self._server.client_count} clients"
            url = f"ws://localhost:{self._server.actual_port}"

            # Health check only on full refresh ticks (expensive)
            health = self._server.get_health()
            health_level = health.get("level", "unknown")
            healthy = health.get("healthy", False)
        else:
            running = False
            clients = "0 clients"
            url = self._ui_state.get("url")  # keep last known
            health_level = "-"
            healthy = None

        # Diff against cached state — only touch widgets that changed
        prev = self._ui_state

        if prev["running"] != running:
            if running:
                self.status_indicator.setText("Running")
                self.status_indicator.setStyleSheet("font-weight: bold; color: #4CAF50;")
                self.start_btn.setEnabled(False)
                self.stop_btn.setEnabled(True)
                self.port_input.setEnabled(False)
            else:
                self.status_indicator.setText("Stopped")
                self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
                self.start_btn.setEnabled(SERVER_AVAILABLE)
                self.stop_btn.setEnabled(False)
                self.port_input.setEnabled(True)
            prev["running"] = running

        if prev["clients"] != clients:
            self.clients_label.setText(clients)
            prev["clients"] = clients

        if running and prev["url"] != url:
            self.url_label.setText(url)
            prev["url"] = url

        if prev["health_level"] != health_level:
            self.health_indicator.setText(health_level)
            prev["health_level"] = health_level

        if prev["healthy"] != healthy:
            if healthy is True:
                self.health_indicator.setStyleSheet("color: #4CAF50;")
            elif healthy is False:
                self.health_indicator.setStyleSheet("color: #F44336;")
            else:
                self.health_indicator.setStyleSheet("")
            prev["healthy"] = healthy

    def _copy_url(self):
        """Copy connection URL to clipboard."""
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.url_label.text())

    def heartbeat(self):
        """Called by timer — fast path feeds watchdog, slow path updates UI."""
        # Auto-discover server from hou.session (once, not every tick)
        if self._server is None and _HOU:
            try:
                if hasattr(hou.session, '_synapse_server'):
                    srv = hou.session._synapse_server
                    if srv and srv.is_running:
                        self._server = srv
            except:
                pass

        if self._server:
            # Fast path: watchdog heartbeat only (lightweight — lock + timestamp)
            self._server.heartbeat()

            # Slow path: full UI refresh every N ticks
            self._tick += 1
            if self._tick >= self._UI_REFRESH_INTERVAL:
                self._tick = 0
                self._update_status()
