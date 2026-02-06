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

import os
import sys
from pathlib import Path
from typing import Optional

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
from .tabs.connection import ConnectionTab
from .tabs.context import ContextTab
from .tabs.decisions import DecisionsTab
from .tabs.activity import ActivityTab
from .tabs.search import SearchTab

__title__ = "Synapse"
__version__ = "4.0.0"
__author__ = "Joe Ibrahim"
__license__ = "MIT"
__product__ = "Synapse - AI-Houdini Bridge"


class SynapsePanel(QtWidgets.QWidget):
    """
    Main Synapse panel with tabs for connection, context, decisions, activity, and search.

    Combines server and memory functionality into a unified interface.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._setup_ui()
        self._init_synapse()

        # Auto-refresh timer
        self._refresh_timer = QtCore.QTimer()
        self._refresh_timer.timeout.connect(self._on_timer)
        self._refresh_timer.start(1000)  # 1 second for heartbeat

        self._last_hip = ""

    def _setup_ui(self):
        self.setWindowTitle("Synapse - AI Bridge")
        self.setMinimumSize(350, 400)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header section
        header_layout = QtWidgets.QHBoxLayout()

        title = QtWidgets.QLabel("SYNAPSE")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        header_layout.addWidget(title)

        subtitle = QtWidgets.QLabel("AI-Houdini Bridge")
        subtitle.setStyleSheet("color: palette(mid); font-size: 11px;")
        header_layout.addWidget(subtitle)

        header_layout.addStretch()

        version_label = QtWidgets.QLabel(f"v{__version__}")
        version_label.setStyleSheet("color: palette(mid); font-size: 10px;")
        header_layout.addWidget(version_label)

        layout.addLayout(header_layout)

        # Project status group
        status_group = QtWidgets.QGroupBox("Memory Status")
        status_layout = QtWidgets.QFormLayout(status_group)

        self.status_indicator = QtWidgets.QLabel("No Project")
        self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
        status_layout.addRow("Status:", self.status_indicator)

        self.project_label = QtWidgets.QLabel("untitled")
        status_layout.addRow("Project:", self.project_label)

        self.memory_count_label = QtWidgets.QLabel("0")
        status_layout.addRow("Memories:", self.memory_count_label)

        layout.addWidget(status_group)

        # Storage path group
        storage_group = QtWidgets.QGroupBox("Storage Location")
        storage_layout = QtWidgets.QVBoxLayout(storage_group)

        self.storage_label = QtWidgets.QLabel("$HIP/.synapse/")
        self.storage_label.setStyleSheet("font-family: monospace;")
        self.storage_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        storage_layout.addWidget(self.storage_label)

        open_folder_btn = QtWidgets.QPushButton("Open Folder")
        open_folder_btn.clicked.connect(self._open_folder)
        storage_layout.addWidget(open_folder_btn)

        layout.addWidget(storage_group)

        # Tabs - Communication first, then memory
        self.tabs = QtWidgets.QTabWidget()

        self.connection_tab = ConnectionTab()
        self.tabs.addTab(self.connection_tab, "Connection")

        self.context_tab = ContextTab()
        self.tabs.addTab(self.context_tab, "Context")

        self.decisions_tab = DecisionsTab()
        self.tabs.addTab(self.decisions_tab, "Decisions")

        self.activity_tab = ActivityTab()
        self.tabs.addTab(self.activity_tab, "Activity")

        self.search_tab = SearchTab()
        self.tabs.addTab(self.search_tab, "Search")

        layout.addWidget(self.tabs)

        # Footer controls
        controls = QtWidgets.QHBoxLayout()

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
            print(f"[Synapse Panel] Init failed: {e}")
            self._synapse = None
            self._update_ui()

    def _update_ui(self):
        """Update all tabs with current Synapse instance."""
        if self._synapse:
            project_path = self._synapse.project_path
            hip_name = Path(project_path).stem if project_path else "untitled"
            memory_count = self._synapse.store.count()

            self.status_indicator.setText("Active")
            self.status_indicator.setStyleSheet("font-weight: bold; color: #4CAF50;")

            self.project_label.setText(hip_name)
            self.storage_label.setText(str(self._synapse.storage_dir))
            self.memory_count_label.setText(str(memory_count))
            self._last_hip = str(project_path) if project_path else ""

            self.clear_btn.setEnabled(memory_count > 0)
        else:
            self.status_indicator.setText("No Project")
            self.status_indicator.setStyleSheet("font-weight: bold; color: palette(mid);")
            self.project_label.setText("untitled")
            self.storage_label.setText("$HIP/.synapse/")
            self.memory_count_label.setText("0")
            self.clear_btn.setEnabled(False)

        # Update tabs
        self.context_tab.set_synapse(self._synapse)
        self.decisions_tab.set_synapse(self._synapse)
        self.search_tab.set_synapse(self._synapse)
        self.activity_tab.set_synapse(self._synapse)

    def _on_timer(self):
        """Timer callback for heartbeat and project change detection."""
        # Feed watchdog via connection tab
        self.connection_tab.heartbeat()

        # Check for project change
        if HOU_AVAILABLE:
            try:
                current_hip = hou.hipFile.name()
                if current_hip != self._last_hip:
                    print(f"[Synapse] Project changed: {current_hip}")
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
                print(f"[Synapse] Failed to clear memories: {e}")

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
