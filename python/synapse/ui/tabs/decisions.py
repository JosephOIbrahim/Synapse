"""
Synapse Decisions Tab

View and add decisions with reasoning.
"""

from typing import Optional, List

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from ...memory.store import SynapseMemory
from ...memory.models import Memory


class DecisionItem(QtWidgets.QFrame):
    """A single decision entry widget."""

    def __init__(self, memory: Memory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Header with date
        header = QtWidgets.QHBoxLayout()
        date_str = self.memory.created_at.split("T")[0] if self.memory.created_at else "Unknown"
        date_label = QtWidgets.QLabel(date_str)
        date_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        header.addWidget(date_label)
        header.addStretch()

        # Tags
        if self.memory.tags:
            tags_str = " ".join([f"#{t}" for t in self.memory.tags[:3]])
            tags_label = QtWidgets.QLabel(tags_str)
            tags_label.setStyleSheet("color: palette(mid); font-size: 10px;")
            header.addWidget(tags_label)

        layout.addLayout(header)

        # Decision summary
        summary = QtWidgets.QLabel(self.memory.summary)
        summary.setWordWrap(True)
        summary.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(summary)

        # Reasoning (if available in content)
        content_lines = self.memory.content.split("\n")
        reasoning = ""
        for line in content_lines:
            if line.startswith("**Reasoning:**"):
                reasoning = line.replace("**Reasoning:**", "").strip()
                break

        if reasoning:
            reason_label = QtWidgets.QLabel(reasoning)
            reason_label.setWordWrap(True)
            reason_label.setStyleSheet("color: palette(mid); font-size: 11px;")
            layout.addWidget(reason_label)


class DecisionsTab(QtWidgets.QWidget):
    """Tab for viewing and adding decisions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Decision Log")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Add decision form
        add_group = QtWidgets.QGroupBox("Record New Decision")
        add_layout = QtWidgets.QVBoxLayout(add_group)

        self.decision_input = QtWidgets.QLineEdit()
        self.decision_input.setPlaceholderText("What did you decide?")
        add_layout.addWidget(self.decision_input)

        self.reasoning_input = QtWidgets.QTextEdit()
        self.reasoning_input.setPlaceholderText("Why? What was the reasoning?")
        self.reasoning_input.setMaximumHeight(80)
        add_layout.addWidget(self.reasoning_input)

        self.alternatives_input = QtWidgets.QLineEdit()
        self.alternatives_input.setPlaceholderText("Alternatives considered (comma-separated)")
        add_layout.addWidget(self.alternatives_input)

        self.tags_input = QtWidgets.QLineEdit()
        self.tags_input.setPlaceholderText("Tags (comma-separated)")
        add_layout.addWidget(self.tags_input)

        add_btn_layout = QtWidgets.QHBoxLayout()
        add_btn_layout.addStretch()
        self.add_btn = QtWidgets.QPushButton("Record Decision")
        self.add_btn.clicked.connect(self._add_decision)
        add_btn_layout.addWidget(self.add_btn)
        add_layout.addLayout(add_btn_layout)

        layout.addWidget(add_group)

        # Decisions list
        self.decisions_scroll = QtWidgets.QScrollArea()
        self.decisions_scroll.setWidgetResizable(True)
        self.decisions_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.decisions_container = QtWidgets.QWidget()
        self.decisions_layout = QtWidgets.QVBoxLayout(self.decisions_container)
        self.decisions_layout.setSpacing(10)
        self.decisions_layout.addStretch()

        self.decisions_scroll.setWidget(self.decisions_container)
        layout.addWidget(self.decisions_scroll)

    def set_synapse(self, synapse: SynapseMemory):
        """Set the Synapse instance and load decisions."""
        self._synapse = synapse
        self._refresh()

    def _refresh(self):
        """Refresh the decisions list."""
        # Clear existing
        while self.decisions_layout.count() > 1:
            item = self.decisions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._synapse:
            return

        try:
            decisions = self._synapse.get_decisions()
            for decision in reversed(decisions):  # Newest first
                item = DecisionItem(decision)
                self.decisions_layout.insertWidget(self.decisions_layout.count() - 1, item)
        except Exception as e:
            print(f"[Synapse] Failed to load decisions: {e}")

    def _add_decision(self):
        """Add a new decision."""
        if not self._synapse:
            return

        decision_text = self.decision_input.text().strip()
        if not decision_text:
            return

        reasoning = self.reasoning_input.toPlainText().strip()
        alternatives = [a.strip() for a in self.alternatives_input.text().split(",") if a.strip()]
        tags = [t.strip() for t in self.tags_input.text().split(",") if t.strip()]

        try:
            self._synapse.decision(
                decision=decision_text,
                reasoning=reasoning,
                alternatives=alternatives,
                tags=tags
            )

            # Clear form
            self.decision_input.clear()
            self.reasoning_input.clear()
            self.alternatives_input.clear()
            self.tags_input.clear()

            # Refresh list
            self._refresh()
        except Exception as e:
            print(f"[Synapse] Failed to add decision: {e}")
