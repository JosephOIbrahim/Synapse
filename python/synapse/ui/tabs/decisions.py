"""
Synapse Decisions Tab

View and add decisions with reasoning.
"""

import logging
from typing import Optional, List

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from ...memory.store import SynapseMemory
from ...memory.models import Memory

logger = logging.getLogger("synapse.ui.decisions")


class DecisionItem(QtWidgets.QFrame):
    """A single decision entry widget."""

    def __init__(self, memory: Memory, parent=None):
        super().__init__(parent)
        self.memory = memory
        self._setup_ui()

    def _setup_ui(self):
        self.setFrameStyle(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header with date
        header = QtWidgets.QHBoxLayout()
        date_str = self.memory.created_at.split("T")[0] if self.memory.created_at else "Unknown"
        date_label = QtWidgets.QLabel(date_str)
        date_label.setStyleSheet("color: palette(light); font-size: 11px;")
        header.addWidget(date_label)
        header.addStretch()

        # Tags
        if self.memory.tags:
            tags_str = " ".join([f"#{t}" for t in self.memory.tags[:3]])
            tags_label = QtWidgets.QLabel(tags_str)
            tags_label.setStyleSheet("color: palette(light); font-size: 11px;")
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
            reason_label.setStyleSheet("color: palette(light); font-size: 12px;")
            layout.addWidget(reason_label)


class DecisionsTab(QtWidgets.QWidget):
    """Tab for viewing and adding decisions."""

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
        title = QtWidgets.QLabel("Decision Log")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        header.addWidget(refresh_btn)

        layout.addLayout(header)

        # Add decision form — wider internal spacing
        add_group = QtWidgets.QGroupBox("Record New Decision")
        add_layout = QtWidgets.QVBoxLayout(add_group)
        add_layout.setSpacing(10)
        add_layout.setContentsMargins(10, 14, 10, 10)

        self.decision_input = QtWidgets.QLineEdit()
        self.decision_input.setPlaceholderText("What did you decide?")
        add_layout.addWidget(self.decision_input)

        self.reasoning_input = QtWidgets.QTextEdit()
        self.reasoning_input.setPlaceholderText("Why? What was the reasoning?")
        self.reasoning_input.setMaximumHeight(80)
        add_layout.addWidget(self.reasoning_input)

        # Alternatives + Tags on one row
        extras_row = QtWidgets.QHBoxLayout()
        extras_row.setSpacing(8)

        self.alternatives_input = QtWidgets.QLineEdit()
        self.alternatives_input.setPlaceholderText("Alternatives (comma-sep)")
        extras_row.addWidget(self.alternatives_input)

        self.tags_input = QtWidgets.QLineEdit()
        self.tags_input.setPlaceholderText("Tags (comma-sep)")
        self.tags_input.setFixedWidth(140)
        extras_row.addWidget(self.tags_input)

        self.add_btn = QtWidgets.QPushButton("Record")
        self.add_btn.clicked.connect(self._add_decision)
        extras_row.addWidget(self.add_btn)

        add_layout.addLayout(extras_row)
        layout.addWidget(add_group)

        # Decisions list
        self.decisions_scroll = QtWidgets.QScrollArea()
        self.decisions_scroll.setWidgetResizable(True)
        self.decisions_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.decisions_container = QtWidgets.QWidget()
        self.decisions_layout = QtWidgets.QVBoxLayout(self.decisions_container)
        self.decisions_layout.setSpacing(12)
        self.decisions_layout.setContentsMargins(0, 4, 0, 4)
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
            logger.error("Failed to load decisions: %s", e)

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
            logger.error("Failed to add decision: %s", e)
