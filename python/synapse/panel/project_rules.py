"""Explicit local project permissions. Opening this dialog sends nothing."""
import os
from pathlib import Path

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from synapse import model_access as access
from synapse.panel.designsystem import components as c, qss


class ProjectRulesDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, spec=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setProperty("panel_popup", "model_rules")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        scale = getattr(parent, "_chrome_scale", 1.0)
        qss.prepare_model_rules_dialog(self, scale)
        self.setWindowTitle("Project rules")
        self.resize(620, 690)
        self._spec = spec
        outer = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("DsRulesScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        page = QtWidgets.QWidget()
        page.setObjectName("DsRulesPage")
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        layout = QtWidgets.QVBoxLayout(page)
        intro = c.label("USD memory and saved recipes stay on this computer. These rules control which models SYNAPSE can send project content to.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.location = QtWidgets.QPlainTextEdit()
        self.location.setObjectName("DsRulesPath")
        self.location.setReadOnly(True)
        self.location.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.location.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.location.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.location.setMinimumHeight(int(76 * scale))
        self.location.setMaximumHeight(int(100 * scale))
        layout.addWidget(self.location)
        folder_row = QtWidgets.QHBoxLayout()
        self.folder = QtWidgets.QLineEdit()
        self.folder.setObjectName("DsField")
        self.folder.setPlaceholderText("Project folder on this computer")
        self.select_folder = c.Button("Use folder", variant="secondary")
        self.use_installation = c.Button("Use installation rules", variant="ghost")
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(self.select_folder)
        layout.addLayout(folder_row)
        layout.addWidget(self.use_installation)
        self.mode = QtWidgets.QComboBox()
        self.mode.setObjectName("DsConnectionSelect")
        self.mode.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mode.setMinimumContentsLength(15)
        self.mode.addItem("Ask before sharing with another service", "ask")
        self.mode.addItem("Local only — checked local weights", "local_only")
        layout.addWidget(self.mode)
        note = c.label("Background permissions allow repeated requests without a task prompt. Each permission names one model and service. Uncheck to revoke it.", role="body", scale=scale)
        note.setWordWrap(True)
        layout.addWidget(note)
        self.permissions = QtWidgets.QListWidget()
        self.permissions.setMinimumHeight(115)
        self.permissions.setMaximumHeight(200)
        layout.addWidget(self.permissions, 1)
        sharing = c.label("Allowed background requests may send prompts, conversation, scene context, recalled memory, tool results and images to the checked models.", role="caption", scale=scale)
        sharing.setWordWrap(True)
        layout.addWidget(sharing)
        self.disclosure = QtWidgets.QCheckBox("I allow these background permissions")
        layout.addWidget(self.disclosure)
        boundary = c.label("Other applications and external MCP clients control their own model connections. Local only is a SYNAPSE request rule, not a workstation firewall.", role="caption", scale=scale)
        boundary.setWordWrap(True)
        layout.addWidget(boundary)
        self.status = c.label("", role="body", scale=scale)
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        buttons = QtWidgets.QHBoxLayout()
        cancel = c.Button("Cancel", variant="ghost")
        save = c.Button("Save rules", variant="primary")
        save.clicked.connect(self._save)
        cancel.clicked.connect(self.reject)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        outer.addLayout(buttons)
        self.select_folder.clicked.connect(self._select_folder)
        self.use_installation.clicked.connect(lambda: self._select(None))
        locked = bool(os.environ.get("SYNAPSE_MODEL_POLICY", "").strip())
        for widget in (self.folder, self.select_folder, self.use_installation):
            widget.setEnabled(not locked)
        self._load()

    def _load(self):
        try:
            self._policy = access.load_policy()
        except access.ModelAccessDenied as exc:
            self._policy = None
            self.status.setText(str(exc))
            return
        policy = self._policy
        self.location.setPlainText("Rules file: " + str(policy.path))
        self.mode.setCurrentIndex(self.mode.findData(policy.mode))
        self.permissions.clear()
        rows = list(policy.approved_models)
        if self._spec is not None and self._spec not in rows:
            rows.append(self._spec)
        for spec in rows:
            item = QtWidgets.QListWidgetItem(spec.identity + "\n" + spec.endpoint)
            item.setData(QtCore.Qt.UserRole, spec)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if spec in policy.approved_models else QtCore.Qt.Unchecked)
            self.permissions.addItem(item)
        self.disclosure.setChecked(False)
        self.status.setText(policy.error or "Changes apply to the next request, including work already queued.")

    def _select_folder(self):
        folder = Path(self.folder.text().strip())
        if not folder.is_absolute() or not folder.is_dir():
            self.status.setText("Enter an existing absolute project folder path.")
            return
        self._select(folder / ".synapse/model_access.json")

    def _select(self, path):
        try:
            access.select_project_policy(path)
            self._load()
        except access.ModelAccessDenied as exc:
            self.status.setText(str(exc))

    def _save(self):
        if self._policy is None:
            return
        approved = tuple(self.permissions.item(i).data(QtCore.Qt.UserRole)
                         for i in range(self.permissions.count())
                         if self.permissions.item(i).checkState() == QtCore.Qt.Checked)
        additions = set(approved) - set(self._policy.approved_models)
        if additions and not self.disclosure.isChecked():
            self.status.setText("Review and check the sharing permission before allowing background work.")
            return
        try:
            # A different window may have selected another project meanwhile.
            if access.policy_path() != self._policy.path:
                raise access.ModelAccessDenied("The selected project changed. Reopen Project rules before saving.")
            access.save_policy(self.mode.currentData(), approved, path=self._policy.path,
                               expected_revision=self._policy.revision)
        except (access.ModelAccessDenied, ValueError) as exc:
            self.status.setText(str(exc))
            return
        self.accept()
