"""HDA creation mode views for the Synapse chat panel.

Three-state flow:
    DescribeView  -- artist describes the HDA they want
    BuildingView  -- progress indicator while HDA is built
    ResultView    -- outcome display with actions
"""

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    from PySide6.QtCore import Signal
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    from PySide2.QtCore import Signal

from synapse.panel import tokens as t


# ── DescribeView ────────────────────────────────────────────────────────

class DescribeView(QtWidgets.QWidget):
    """First state: artist describes the HDA they want."""

    generate_requested = Signal(str, str, dict)
    # Emits: (prompt_text, context_type, options_dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DescribeView")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Section label
        label = QtWidgets.QLabel("DESCRIBE YOUR HDA")
        label.setObjectName("SectionLabel")
        label.setStyleSheet(
            "color: {sig}; font-size: 10px; "
            "font-family: monospace; letter-spacing: 2px;".format(
                sig=t.SIGNAL
            )
        )
        layout.addWidget(label)

        # Prompt input
        self.prompt_input = QtWidgets.QTextEdit()
        self.prompt_input.setObjectName("HdaPromptInput")
        self.prompt_input.setPlaceholderText(
            "Describe the HDA you want to create...\n\n"
            "Examples:\n"
            "  'A scatter tool that distributes points on a surface "
            "with density control'\n"
            "  'A 3-point light rig with key, fill, and rim lights'\n"
            "  'A Karma render setup with draft/preview/production "
            "quality tiers'"
        )
        self.prompt_input.setMinimumHeight(120)
        self.prompt_input.setMaximumHeight(200)
        layout.addWidget(self.prompt_input)

        # Options row
        options_row = QtWidgets.QHBoxLayout()
        options_row.setSpacing(8)

        # Context selector
        ctx_label = QtWidgets.QLabel("Context:")
        ctx_label.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 11px;".format(
                c=t.SLATE
            )
        )
        self.context_combo = QtWidgets.QComboBox()
        self.context_combo.setObjectName("HdaContextSelector")
        self.context_combo.addItems(["SOP", "LOP", "DOP", "COP", "TOP"])
        self.context_combo.setCurrentText("SOP")

        options_row.addWidget(ctx_label)
        options_row.addWidget(self.context_combo)
        options_row.addStretch()

        # Checkboxes
        self.chk_help = QtWidgets.QCheckBox("Include help text")
        self.chk_help.setChecked(True)
        self.chk_help.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 11px;".format(
                c=t.SILVER
            )
        )

        self.chk_toolbar = QtWidgets.QCheckBox("Add to toolbar")
        self.chk_toolbar.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 11px;".format(
                c=t.SILVER
            )
        )

        options_row.addWidget(self.chk_help)
        options_row.addWidget(self.chk_toolbar)
        layout.addLayout(options_row)

        # Generate button
        self.generate_btn = QtWidgets.QPushButton("GENERATE HDA")
        self.generate_btn.setObjectName("HdaGenerateBtn")
        self.generate_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.generate_btn.clicked.connect(self._on_generate)
        layout.addWidget(self.generate_btn)

        layout.addStretch()

    def _on_generate(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return
        context = self.context_combo.currentText()
        options = {
            "include_help": self.chk_help.isChecked(),
            "add_to_toolbar": self.chk_toolbar.isChecked(),
        }
        self.generate_requested.emit(prompt, context, options)

    def reset(self):
        """Clear for next HDA creation."""
        self.prompt_input.clear()
        self.context_combo.setCurrentText("SOP")
        self.chk_help.setChecked(True)
        self.chk_toolbar.setChecked(False)


# ── BuildingView ────────────────────────────────────────────────────────

class BuildingView(QtWidgets.QWidget):
    """Second state: shows progress while HDA is being built."""

    cancel_requested = Signal()

    STAGES = [
        ("parsing_prompt", "Parsing prompt..."),
        ("selecting_recipe", "Selecting recipe..."),
        ("creating_subnet", "Creating subnet..."),
        ("building_nodes", "Building internal nodes..."),
        ("wiring_connections", "Wiring connections..."),
        ("promoting_parameters", "Promoting parameters..."),
        ("validating", "Validating HDA..."),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("BuildingView")
        self._current_stage = 0
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        layout.addStretch()

        # Stage indicator
        self.stage_label = QtWidgets.QLabel("Preparing...")
        self.stage_label.setObjectName("StageLabel")
        self.stage_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stage_label.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 14px; "
            "font-weight: 700;".format(c=t.BONE)
        )
        layout.addWidget(self.stage_label)

        # Progress bar
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setObjectName("HdaProgressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(6)
        layout.addWidget(self.progress_bar)

        # Stage dots row
        self.dots_layout = QtWidgets.QHBoxLayout()
        self.dots_layout.setSpacing(4)
        self.dots_layout.addStretch()
        self.dot_labels = []
        for _i, (_name, _display) in enumerate(self.STAGES):
            dot = QtWidgets.QLabel("\u25CF")  # filled circle
            dot.setStyleSheet(
                "color: {c}; font-size: 8px;".format(c=t.HDA_STAGE_INACTIVE)
            )
            dot.setAlignment(QtCore.Qt.AlignCenter)
            self.dot_labels.append(dot)
            self.dots_layout.addWidget(dot)
        self.dots_layout.addStretch()
        layout.addLayout(self.dots_layout)

        # Detail text
        self.detail_label = QtWidgets.QLabel("")
        self.detail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.detail_label.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 10px;".format(
                c=t.SLATE
            )
        )
        layout.addWidget(self.detail_label)

        layout.addStretch()

        # Cancel button
        self.cancel_btn = QtWidgets.QPushButton("Cancel")
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.cancel_btn.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_btn, alignment=QtCore.Qt.AlignCenter)

    def update_stage(self, stage_name, progress_pct, detail=""):
        """Update to a new stage. Called via signal from controller."""
        self.progress_bar.setValue(int(progress_pct))

        # Find stage index
        for i, (name, display) in enumerate(self.STAGES):
            if name == stage_name:
                self._current_stage = i
                self.stage_label.setText(display)
                break

        # Update dots
        for i, dot in enumerate(self.dot_labels):
            if i < self._current_stage:
                dot.setStyleSheet(
                    "color: {c}; font-size: 8px;".format(
                        c=t.HDA_STAGE_COMPLETE
                    )
                )
            elif i == self._current_stage:
                dot.setStyleSheet(
                    "color: {c}; font-size: 10px;".format(
                        c=t.HDA_STAGE_ACTIVE
                    )
                )
            else:
                dot.setStyleSheet(
                    "color: {c}; font-size: 8px;".format(
                        c=t.HDA_STAGE_INACTIVE
                    )
                )

        if detail:
            self.detail_label.setText(detail)

    def reset(self):
        """Reset to initial state."""
        self._current_stage = 0
        self.progress_bar.setValue(0)
        self.stage_label.setText("Preparing...")
        self.detail_label.setText("")
        for dot in self.dot_labels:
            dot.setStyleSheet(
                "color: {c}; font-size: 8px;".format(c=t.HDA_STAGE_INACTIVE)
            )


# ── ResultView ──────────────────────────────────────────────────────────

class ResultView(QtWidgets.QWidget):
    """Third state: shows the created HDA with actions."""

    action_requested = Signal(str)  # "inspect", "edit", "save", "new"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ResultView")
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Success/failure header
        self.status_label = QtWidgets.QLabel("HDA Created")
        self.status_label.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 14px; "
            "font-weight: 700;".format(c=t.GROW)
        )
        layout.addWidget(self.status_label)

        # Node path (copyable)
        self.path_label = QtWidgets.QLabel("")
        self.path_label.setObjectName("NodePathLabel")
        self.path_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse
        )
        self.path_label.setCursor(QtCore.Qt.IBeamCursor)
        layout.addWidget(self.path_label)

        # Parameter table
        self.param_table = QtWidgets.QTableWidget()
        self.param_table.setObjectName("ParamTable")
        self.param_table.setColumnCount(4)
        self.param_table.setHorizontalHeaderLabels(
            ["Parameter", "Type", "Default", "Range"]
        )
        self.param_table.horizontalHeader().setStretchLastSection(True)
        self.param_table.verticalHeader().setVisible(False)
        self.param_table.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers
        )
        self.param_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.param_table.setMinimumHeight(120)
        layout.addWidget(self.param_table)

        # Validation summary
        self.validation_label = QtWidgets.QLabel("")
        self.validation_label.setStyleSheet(
            "color: {c}; font-family: monospace; font-size: 10px;".format(
                c=t.SLATE
            )
        )
        self.validation_label.setWordWrap(True)
        layout.addWidget(self.validation_label)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.setSpacing(8)

        for action, label in [
            ("inspect", "Inspect in Network"),
            ("edit", "Edit Parameters"),
            ("save", "Save as HDA File"),
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("HdaActionBtn")
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, a=action: self.action_requested.emit(a)
            )
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)

        # Create Another button
        new_btn = QtWidgets.QPushButton("Create Another HDA")
        new_btn.setObjectName("HdaGenerateBtn")
        new_btn.setCursor(QtCore.Qt.PointingHandCursor)
        new_btn.clicked.connect(
            lambda: self.action_requested.emit("new")
        )
        layout.addWidget(new_btn)

    def populate(self, result_data):
        """Fill the view with HDA creation results."""
        success = result_data.get("success", False)

        if success:
            self.status_label.setText("HDA Created Successfully")
            self.status_label.setStyleSheet(
                "color: {c}; font-family: monospace; font-size: 14px; "
                "font-weight: 700;".format(c=t.GROW)
            )
            self.path_label.setText(result_data.get("node_path", ""))
            self.path_label.setStyleSheet(
                "color: {fg}; font-family: monospace; font-size: 12px; "
                "padding: 8px 12px; background: {bg}; "
                "border-radius: 4px;".format(
                    fg=t.GROW, bg=t.HDA_RESULT_SUCCESS_BG,
                )
            )

            # Populate parameter table
            params = result_data.get("parameters", [])
            self.param_table.setRowCount(len(params))
            for row, p in enumerate(params):
                self.param_table.setItem(
                    row, 0,
                    QtWidgets.QTableWidgetItem(p.get("name", ""))
                )
                self.param_table.setItem(
                    row, 1,
                    QtWidgets.QTableWidgetItem(p.get("type", ""))
                )
                self.param_table.setItem(
                    row, 2,
                    QtWidgets.QTableWidgetItem(str(p.get("default", "")))
                )
                rng = p.get("range", [])
                range_str = (
                    "{} - {}".format(rng[0], rng[1]) if len(rng) >= 2 else ""
                )
                self.param_table.setItem(
                    row, 3, QtWidgets.QTableWidgetItem(range_str)
                )

            # Validation summary
            val = result_data.get("validation", {})
            parts = []
            if val.get("cook_success"):
                parts.append("Cook test passed")
            if val.get("connections_valid"):
                parts.append(
                    "{} nodes connected".format(
                        val.get("internal_nodes", "?")
                    )
                )
            if val.get("warnings"):
                parts.append(
                    "{} warnings".format(len(val["warnings"]))
                )
            self.validation_label.setText("  |  ".join(parts))

        else:
            self.status_label.setText("HDA Creation Failed")
            self.status_label.setStyleSheet(
                "color: {c}; font-family: monospace; font-size: 14px; "
                "font-weight: 700;".format(c=t.ERROR_COLOR)
            )
            self.path_label.setText(result_data.get("error", "Unknown error"))
            self.path_label.setStyleSheet(
                "color: {fg}; font-family: monospace; font-size: 11px; "
                "padding: 8px 12px; background: {bg}; "
                "border-radius: 4px;".format(
                    fg=t.ERROR_COLOR, bg=t.HDA_RESULT_ERROR_BG,
                )
            )
            self.param_table.setRowCount(0)

            rollback = (
                "Scene rolled back."
                if result_data.get("rollback")
                else ""
            )
            self.validation_label.setText(
                "{} {}".format(
                    result_data.get("detail", ""), rollback
                ).strip()
            )

    def reset(self):
        """Clear for next result."""
        self.param_table.setRowCount(0)
        self.path_label.setText("")
        self.validation_label.setText("")
