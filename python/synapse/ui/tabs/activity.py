"""
Synapse Activity Tab

Real-time memory activity feed.
"""

from typing import Optional

try:
    from PySide6 import QtWidgets, QtCore, QtGui
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui

from ...memory.store import SynapseMemory
from ...memory.models import MemoryType


class ActivityTab(QtWidgets.QWidget):
    """Tab showing recent memory activity."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Header
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Recent Activity")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        header.addWidget(self.stats_label)

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Activity log
        self.activity_list = QtWidgets.QListWidget()
        self.activity_list.setStyleSheet(
            "font-family: monospace; font-size: 11px;"
            "QListWidget::item { padding: 4px 2px; }"
        )
        self.activity_list.setSpacing(2)
        layout.addWidget(self.activity_list)

    def set_synapse(self, synapse: SynapseMemory):
        """Set the Synapse instance and load activity."""
        self._synapse = synapse
        self._refresh()

    def _refresh(self):
        """Refresh activity list."""
        self.activity_list.clear()

        if not self._synapse:
            self.stats_label.setText("No project loaded")
            return

        try:
            recent = self._synapse.get_recent(30)
            total = self._synapse.store.count()

            self.stats_label.setText(f"Total memories: {total}")

            type_icons = {
                MemoryType.CONTEXT: "[CTX]",
                MemoryType.DECISION: "[DEC]",
                MemoryType.TASK: "[TSK]",
                MemoryType.ACTION: "[ACT]",
                MemoryType.NOTE: "[NOTE]",
                MemoryType.REFERENCE: "[REF]",
                MemoryType.FEEDBACK: "[FB]",
                MemoryType.ERROR: "[ERR]",
                MemoryType.SUMMARY: "[SUM]",
            }

            for memory in recent:
                icon = type_icons.get(memory.memory_type, "[?]")
                time_str = memory.created_at.split("T")[1][:5] if "T" in memory.created_at else ""
                text = f"{time_str} {icon} {memory.summary}"

                item = QtWidgets.QListWidgetItem(text)
                item.setData(QtCore.Qt.UserRole, memory)

                # Color by type
                if memory.memory_type == MemoryType.ERROR:
                    item.setForeground(QtGui.QColor("#F44336"))
                elif memory.memory_type == MemoryType.DECISION:
                    item.setForeground(QtGui.QColor("#4CAF50"))

                self.activity_list.addItem(item)

        except Exception as e:
            self.stats_label.setText(f"Error: {e}")
