"""
Synapse Search Tab

Memory search interface.
"""

from typing import Optional

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from ...memory.store import SynapseMemory


class SearchTab(QtWidgets.QWidget):
    """Tab for searching memories."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        title = QtWidgets.QLabel("Search Memories")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        layout.addWidget(title)

        # Search input
        search_layout = QtWidgets.QHBoxLayout()

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Search memories...")
        self.search_input.returnPressed.connect(self._search)
        search_layout.addWidget(self.search_input)

        self.type_filter = QtWidgets.QComboBox()
        self.type_filter.addItem("All Types", "")
        self.type_filter.addItem("Decisions", "decision")
        self.type_filter.addItem("Context", "context")
        self.type_filter.addItem("Actions", "action")
        self.type_filter.addItem("Notes", "note")
        self.type_filter.addItem("Errors", "error")
        search_layout.addWidget(self.type_filter)

        search_btn = QtWidgets.QPushButton("Search")
        search_btn.clicked.connect(self._search)
        search_layout.addWidget(search_btn)

        layout.addLayout(search_layout)

        # Results count
        self.results_label = QtWidgets.QLabel("")
        self.results_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        layout.addWidget(self.results_label)

        # Results list
        self.results_list = QtWidgets.QListWidget()
        self.results_list.itemDoubleClicked.connect(self._show_details)
        layout.addWidget(self.results_list)

        # Details panel
        self.details_group = QtWidgets.QGroupBox("Memory Details")
        details_layout = QtWidgets.QVBoxLayout(self.details_group)

        self.details_text = QtWidgets.QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        details_layout.addWidget(self.details_text)

        self.details_group.setVisible(False)
        layout.addWidget(self.details_group)

    def set_synapse(self, synapse: SynapseMemory):
        """Set the Synapse instance."""
        self._synapse = synapse

    def _search(self):
        """Perform search."""
        self.results_list.clear()
        self.details_group.setVisible(False)

        if not self._synapse:
            return

        query = self.search_input.text().strip()
        type_filter = self.type_filter.currentData()

        try:
            results = self._synapse.search(query, limit=50)

            # Filter by type if specified
            if type_filter:
                results = [r for r in results if r.memory.memory_type.value == type_filter]

            self.results_label.setText(f"Found {len(results)} results")

            for result in results:
                memory = result.memory
                item = QtWidgets.QListWidgetItem()
                item.setText(f"[{memory.memory_type.value}] {memory.summary}")
                item.setData(QtCore.Qt.UserRole, memory)
                self.results_list.addItem(item)

        except Exception as e:
            self.results_label.setText(f"Search error: {e}")

    def _show_details(self, item):
        """Show details for selected memory."""
        memory = item.data(QtCore.Qt.UserRole)
        if not memory:
            return

        details = f"""ID: {memory.id}
Type: {memory.memory_type.value}
Created: {memory.created_at}
Tags: {', '.join(memory.tags) if memory.tags else 'none'}
Keywords: {', '.join(memory.keywords) if memory.keywords else 'none'}

--- Content ---
{memory.content}
"""
        self.details_text.setPlainText(details)
        self.details_group.setVisible(True)
