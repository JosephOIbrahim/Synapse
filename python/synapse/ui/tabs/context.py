"""
Synapse Context Tab

Edit project context stored in context.md.
"""

from typing import Optional

try:
    from PySide6 import QtWidgets, QtCore
except ImportError:
    from PySide2 import QtWidgets, QtCore

from ...memory.store import SynapseMemory
from ...memory.markdown import MarkdownSync, load_context, ShotContext


class ContextTab(QtWidgets.QWidget):
    """Tab for editing context.md sections."""

    context_changed = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._synapse: Optional[SynapseMemory] = None
        self._markdown_sync: Optional[MarkdownSync] = None
        self._modified = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        # Header
        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Shot Context")
        title.setStyleSheet("font-size: 13px; font-weight: bold;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.status_label = QtWidgets.QLabel("No project loaded")
        self.status_label.setStyleSheet("color: palette(mid); font-size: 11px;")
        header_layout.addWidget(self.status_label)
        layout.addLayout(header_layout)

        # Scroll area for sections
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        scroll_content = QtWidgets.QWidget()
        scroll_layout = QtWidgets.QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(20)
        scroll_layout.setContentsMargins(0, 4, 0, 4)

        # Context sections
        self.sections = {}
        section_configs = [
            ("overview", "Overview", "Describe what this shot is about..."),
            ("goals", "Goals", "What are we trying to achieve?"),
            ("constraints", "Constraints", "Technical or creative constraints..."),
            ("assets", "Assets", "Key assets used in this shot..."),
            ("client_notes", "Client Notes", "Feedback and direction from client/supervisor..."),
        ]

        for key, label, placeholder in section_configs:
            group = QtWidgets.QGroupBox(label)
            group_layout = QtWidgets.QVBoxLayout(group)

            text_edit = QtWidgets.QTextEdit()
            text_edit.setPlaceholderText(placeholder)
            text_edit.setMinimumHeight(80)
            text_edit.setMaximumHeight(150)
            text_edit.textChanged.connect(self._on_text_changed)
            group_layout.addWidget(text_edit)

            self.sections[key] = text_edit
            scroll_layout.addWidget(group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        # Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        self.revert_btn = QtWidgets.QPushButton("Revert")
        self.revert_btn.clicked.connect(self._revert)
        self.revert_btn.setEnabled(False)
        btn_layout.addWidget(self.revert_btn)

        self.save_btn = QtWidgets.QPushButton("Save Context")
        self.save_btn.clicked.connect(self._save)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)

        layout.addLayout(btn_layout)

    def set_synapse(self, synapse: SynapseMemory):
        """Set the Synapse instance and load context."""
        self._synapse = synapse
        if synapse:
            self._markdown_sync = MarkdownSync(synapse.storage_dir)
            self._load_context()
            self.status_label.setText("Loaded")
            self.status_label.setStyleSheet("color: #4CAF50;")
        else:
            self.status_label.setText("No project")
            self.status_label.setStyleSheet("color: palette(mid);")

    def _load_context(self):
        """Load context from markdown file."""
        if not self._synapse:
            return

        try:
            context = load_context(self._synapse.storage_dir)
            self.sections["overview"].setPlainText(context.overview or "")
            self.sections["goals"].setPlainText(context.goals or "")
            self.sections["constraints"].setPlainText(context.constraints or "")

            # Handle assets as newline-separated list
            if context.assets:
                self.sections["assets"].setPlainText("\n".join(context.assets))
            else:
                self.sections["assets"].setPlainText("")

            # Handle client notes as newline-separated list
            if context.client_notes:
                self.sections["client_notes"].setPlainText("\n".join(context.client_notes))
            else:
                self.sections["client_notes"].setPlainText("")

            self._modified = False
            self._update_buttons()
        except Exception as e:
            print(f"[Synapse] Failed to load context: {e}")

    def _on_text_changed(self):
        """Mark as modified when text changes."""
        self._modified = True
        self._update_buttons()

    def _update_buttons(self):
        """Update button states based on modification status."""
        self.save_btn.setEnabled(self._modified and self._synapse is not None)
        self.revert_btn.setEnabled(self._modified)

    def _save(self):
        """Save context to markdown file."""
        if not self._synapse:
            return

        try:
            from ...memory.markdown import save_context

            # Parse assets and client_notes as lists
            assets_text = self.sections["assets"].toPlainText()
            assets = [a.strip() for a in assets_text.split("\n") if a.strip()]

            notes_text = self.sections["client_notes"].toPlainText()
            client_notes = [n.strip() for n in notes_text.split("\n") if n.strip()]

            context = ShotContext(
                overview=self.sections["overview"].toPlainText(),
                goals=self.sections["goals"].toPlainText(),
                constraints=self.sections["constraints"].toPlainText(),
                assets=assets,
                client_notes=client_notes,
            )
            save_context(context, self._synapse.storage_dir)
            self._modified = False
            self._update_buttons()
            self.status_label.setText("Saved")
            self.status_label.setStyleSheet("color: #4CAF50;")
            self.context_changed.emit()
        except Exception as e:
            self.status_label.setText(f"Failed: {e}")
            self.status_label.setStyleSheet("color: #F44336;")

    def _revert(self):
        """Revert to last saved state."""
        self._load_context()
