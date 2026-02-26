"""
Synapse Panel

Main unified panel combining server controls and memory management.

Tabs:
1. Connection - Server status and controls
2. Context - Project context editing
3. Decisions - Decision log
4. Activity - Memory feed
5. Search - Memory search
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("synapse.ui")

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False
    hou = None

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from ..memory.store import SynapseMemory, get_synapse_memory, reset_synapse_memory
from ..memory.models import MemoryType
from ..session.tracker import get_bridge
from .tabs.connection import ConnectionTab
from .tabs.context import ContextTab
from .tabs.decisions import DecisionsTab
from .tabs.activity import ActivityTab
from .tabs.search import SearchTab

from synapse import __version__


class SynapsePanel(QtWidgets.QWidget):
    """
    Main Synapse panel with tabs for connection, context, decisions, activity, and search.

    Combines server and memory functionality into a unified interface.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._last_hip = ""
        self._setup_ui()
        self._init_synapse()

        # Auto-refresh timer
        self._refresh_timer = QtCore.QTimer()
        self._refresh_timer.timeout.connect(self._on_timer)
        self._refresh_timer.start(5000)  # 5 seconds — minimal main-thread impact

    def _setup_ui(self):
        self.setWindowTitle("Synapse - AI Bridge")
        self.setMinimumSize(380, 500)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)

        title = QtWidgets.QLabel("SYNAPSE")
        title.setStyleSheet("font-size: 54px; font-weight: bold; letter-spacing: 4px;")
        header_layout.addWidget(title)

        self.status_indicator = QtWidgets.QLabel("No Project")
        self.status_indicator.setStyleSheet(
            "font-weight: bold; color: palette(mid); font-size: 11px;"
        )
        header_layout.addWidget(self.status_indicator)

        header_layout.addStretch()

        version_label = QtWidgets.QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: palette(light); font-size: 10px;")
        header_layout.addWidget(version_label)

        layout.addLayout(header_layout)

        # Project info — compact row, no group box
        info_layout = QtWidgets.QHBoxLayout()
        info_layout.setSpacing(12)

        self.project_label = QtWidgets.QLabel("untitled")
        self.project_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        info_layout.addWidget(self.project_label)

        self.memory_count_label = QtWidgets.QLabel("0 memories")
        self.memory_count_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        info_layout.addWidget(self.memory_count_label)

        info_layout.addStretch()

        open_folder_btn = QtWidgets.QPushButton("Open")
        open_folder_btn.setFixedWidth(50)
        open_folder_btn.clicked.connect(self._open_folder)
        info_layout.addWidget(open_folder_btn)

        layout.addLayout(info_layout)

        # Storage path on its own row — prevents truncation
        self.storage_label = QtWidgets.QLabel("$HIP/.synapse/")
        self.storage_label.setStyleSheet(
            "font-family: monospace; font-size: 10px; color: palette(mid);"
        )
        self.storage_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.storage_label)

        # Separator
        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep)

        # Tabs — short labels for breathing room
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { padding: 6px 14px; }")

        self.connection_tab = ConnectionTab()
        self.tabs.addTab(self.connection_tab, "Server")

        self.context_tab = ContextTab()
        self.tabs.addTab(self.context_tab, "Context")

        self.decisions_tab = DecisionsTab()
        self.tabs.addTab(self.decisions_tab, "Log")

        self.activity_tab = ActivityTab()
        self.tabs.addTab(self.activity_tab, "Feed")

        self.search_tab = SearchTab()
        self.tabs.addTab(self.search_tab, "Search")

        layout.addWidget(self.tabs)

        # Metrics status bar
        metrics_frame = QtWidgets.QFrame()
        metrics_frame.setFrameStyle(QtWidgets.QFrame.StyledPanel)
        metrics_layout = QtWidgets.QVBoxLayout(metrics_frame)
        metrics_layout.setContentsMargins(8, 6, 8, 6)
        metrics_layout.setSpacing(2)

        self.metrics_line1 = QtWidgets.QLabel("")
        self.metrics_line1.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10px; color: palette(light);"
        )
        metrics_layout.addWidget(self.metrics_line1)

        self.metrics_line2 = QtWidgets.QLabel("")
        self.metrics_line2.setStyleSheet(
            "font-family: Consolas, monospace; font-size: 10px; color: palette(light);"
        )
        metrics_layout.addWidget(self.metrics_line2)

        layout.addWidget(metrics_frame)

        # Footer controls
        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 4, 0, 0)

        self.reload_btn = QtWidgets.QPushButton("Reload")
        self.reload_btn.clicked.connect(self._reload_project)
        controls.addWidget(self.reload_btn)

        controls.addStretch()

        self.clear_btn = QtWidgets.QPushButton("Clear All")
        self.clear_btn.clicked.connect(self._clear_memories)
        controls.addWidget(self.clear_btn)

        layout.addLayout(controls)

    def _init_synapse(self):
        """Initialize Synapse for current project."""
        try:
            self._synapse = get_synapse_memory()
            self._update_ui()
        except Exception as e:
            logger.error("Panel init failed: %s", e)
            self._synapse = None
            self._update_ui()

    def _update_ui(self):
        """Update all tabs with current Synapse instance."""
        if self._synapse:
            project_path = self._synapse.project_path
            hip_name = Path(project_path).stem if project_path else "untitled"
            memory_count = self._synapse.store.count()

            self.status_indicator.setText("Active")
            self.status_indicator.setStyleSheet(
                "font-weight: bold; color: #4CAF50; font-size: 11px;"
            )

            self.project_label.setText(hip_name)
            self.storage_label.setText(str(self._synapse.storage_dir))
            self.memory_count_label.setText(f"{memory_count} memories")
            # Store raw hou.hipFile.path() — same source as timer comparison
            self._last_hip = hou.hipFile.path() if HOU_AVAILABLE else str(project_path)

            self.clear_btn.setEnabled(memory_count > 0)
        else:
            self.status_indicator.setText("No Project")
            self.status_indicator.setStyleSheet(
                "font-weight: bold; color: palette(mid); font-size: 11px;"
            )
            self.project_label.setText("untitled")
            self.storage_label.setText("$HIP/.synapse/")
            self.memory_count_label.setText("0 memories")
            self.clear_btn.setEnabled(False)

        # Update tabs
        self.context_tab.set_synapse(self._synapse)
        self.decisions_tab.set_synapse(self._synapse)
        self.search_tab.set_synapse(self._synapse)
        self.activity_tab.set_synapse(self._synapse)

    def _update_metrics(self):
        """Update the compact metrics status bar."""
        try:
            # Line 1: Session stats + server health
            parts1 = []
            bridge = get_bridge()
            server = self.connection_tab._server

            # Active session info
            if bridge and bridge._sessions:
                # Sum across all active sessions
                total_cmds = sum(s.commands_executed for s in bridge._sessions.values())
                total_nodes = sum(len(s.nodes_created) for s in bridge._sessions.values())
                total_errs = sum(len(s.errors_encountered) for s in bridge._sessions.values())
                # Duration from oldest session
                oldest = min(bridge._sessions.values(), key=lambda s: s.started_at)
                dur = oldest.duration_seconds()
                mins = int(dur // 60)
                parts1.append(f"Session: {mins}m")
                parts1.append(f"Cmds: {total_cmds}")
                if total_nodes:
                    parts1.append(f"Nodes: {total_nodes}")
                if total_errs:
                    parts1.append(f"Errs: {total_errs}")

            # Server info
            if server and getattr(server, 'is_running', False):
                parts1.append(f"Clients: {server.client_count}")
                health = server.get_health()
                cb_state = health.get("circuit_breaker", {})
                if isinstance(cb_state, dict):
                    state = cb_state.get("state", "?")
                else:
                    state = str(cb_state) if cb_state else "?"
                parts1.append(f"CB: {state}")
            elif not parts1:
                parts1.append("No active session")

            self.metrics_line1.setText(" │ ".join(parts1))

            # Line 2: Memory breakdown by type
            parts2 = []
            if self._synapse:
                store = self._synapse.store
                for mtype, label in [
                    (MemoryType.DECISION, "Dec"),
                    (MemoryType.NOTE, "Note"),
                    (MemoryType.ACTION, "Act"),
                    (MemoryType.CONTEXT, "Ctx"),
                    (MemoryType.ERROR, "Err"),
                ]:
                    count = len(store.get_by_type(mtype))
                    if count:
                        parts2.append(f"{label}: {count}")

                if parts2:
                    self.metrics_line2.setText(" │ ".join(parts2))
                else:
                    self.metrics_line2.setText("No memories yet")
            else:
                self.metrics_line2.setText("")

        except Exception:
            # Metrics are non-critical — never break the panel
            pass

    def _on_timer(self):
        """Timer callback for heartbeat and project change detection."""
        # Feed watchdog via connection tab
        self.connection_tab.heartbeat()

        # Update metrics on every tick (lightweight reads)
        self._update_metrics()

        # Check for project change (compare raw hou.hipFile.path() to itself — no normalization)
        if HOU_AVAILABLE:
            try:
                current_hip = hou.hipFile.path()
                if current_hip != self._last_hip:
                    self._last_hip = current_hip  # Update immediately to prevent re-trigger
                    logger.info("Project changed: %s", Path(current_hip).name)
                    self._reload_project()
            except:
                pass

    def _reload_project(self):
        """Reload Synapse for current project."""
        reset_synapse_memory()
        self._init_synapse()

    def _clear_memories(self):
        """Clear all memories after confirmation."""
        if not self._synapse:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Clear All Memories",
            "This will delete all memories for this project.\n\nAre you sure?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            try:
                self._synapse.store.clear()
                self._update_ui()
            except Exception as e:
                logger.error("Failed to clear memories: %s", e)

    def _open_folder(self):
        """Open the .synapse folder in file explorer."""
        if not self._synapse:
            return

        folder = str(self._synapse.storage_dir)
        if os.path.exists(folder):
            if os.name == 'nt':  # Windows
                os.startfile(folder)
            elif os.name == 'posix':
                import subprocess
                subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', folder])

    def closeEvent(self, event):
        """Handle panel close."""
        self._refresh_timer.stop()
        super().closeEvent(event)


# Backwards compatibility
NexusPanel = SynapsePanel


# =============================================================================
# ENTRY POINT
# =============================================================================

def create_panel():
    """Create and show Synapse panel."""
    panel = SynapsePanel()
    if HOU_AVAILABLE and hou:
        panel.setParent(hou.qt.mainWindow(), QtCore.Qt.Window)
    panel.show()
    return panel


if __name__ == "__main__":
    create_panel()
