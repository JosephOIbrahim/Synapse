"""Guided connection setup; metadata requests never run on the Qt thread."""
from concurrent.futures import ThreadPoolExecutor

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtWidgets

from synapse.panel import connections as cn
from synapse.panel.providers import registry
from synapse.panel.designsystem import components as c, qss, tokens as t


class ConnectionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, provider_id="ollama", models=None, custom=None,
                 session_keys=None, discovery=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        scale = getattr(parent, "_chrome_scale", 1.0)
        self._chrome_scale = scale
        qss.prepare_connection_dialog(self, scale)
        self.setWindowTitle("Connect a model")
        self.setMinimumWidth(380)
        self._picks = dict(models or {})
        self._custom = dict(custom or {})
        self._keys = dict(session_keys or {})
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synapse-connection")
        self._future = None
        self._checked = None
        self.selection = None
        from synapse.panel.model_discovery import OllamaDiscovery
        self._owns_discovery = discovery is None
        self._discovery = discovery if discovery is not None else OllamaDiscovery(self)
        self._discovery.changed.connect(self._discovery_changed)
        outer = QtWidgets.QVBoxLayout(self)
        self._content_scroll = QtWidgets.QScrollArea(self)
        self._content_scroll.setObjectName("DsConnectionScroll")
        self._content_scroll.viewport().setObjectName("DsConnectionViewport")
        self._content_scroll.setWidgetResizable(True)
        self._content_scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._content_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        content = QtWidgets.QWidget()
        content.setObjectName("DsConnectionPage")
        content.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QtWidgets.QVBoxLayout(content)
        self._content_scroll.setWidget(content)
        outer.addWidget(self._content_scroll, 1)
        intro = c.label("Choose a model and where your work is allowed to go.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QtWidgets.QFormLayout()
        self.engine = QtWidgets.QComboBox()
        self.engine.setObjectName("DsConnectionSelect")
        labels = {"claude": "Anthropic · cloud", "gemini": "Google Gemini · cloud",
                  "ollama": "Ollama · installed models and cloud relays",
                  "nemotron": "NVIDIA or a compatible server", "custom": "Another model service"}
        for pid in registry.PROVIDER_IDS:
            self.engine.addItem(labels.get(pid, pid), pid)
        form.addRow(c.label("Service", role="label", scale=scale), self.engine)
        self.model = QtWidgets.QComboBox()
        self.model.setObjectName("DsConnectionSelect")
        self.model.setEditable(True)
        self.model.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model.setMinimumContentsLength(15)
        form.addRow(c.label("Model", role="label", scale=scale), self.model)
        self.address = QtWidgets.QLineEdit(self._custom.get("base_url", ""))
        self.address.setPlaceholderText("https://your-service/v1")
        self.address_label = c.label("Service address", role="label", scale=scale)
        form.addRow(self.address_label, self.address)
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key.setPlaceholderText("Paste a key, or use an already configured key")
        form.addRow(c.label("API key", role="label", scale=scale), self.key)
        for edit in (self.address, self.key, self.model.lineEdit()):
            edit.setObjectName("DsField")
        layout.addLayout(form)
        from synapse.panel.settings import load_settings
        saved = load_settings()
        routing_form = QtWidgets.QFormLayout()
        self.routing = QtWidgets.QComboBox()
        self.routing.setObjectName("DsConnectionSelect")
        self.routing.addItem("Use my chosen model", "chosen_model")
        self.routing.addItem("Prefer a checked local model", "prefer_checked_local")
        self.routing.setCurrentIndex(max(0, self.routing.findData(saved.get("routing_mode"))))
        routing_form.addRow(c.label("For each new task", role="label", scale=scale), self.routing)
        self.need = QtWidgets.QComboBox()
        self.need.setObjectName("DsConnectionSelect")
        self.need.addItem("Conversation", "conversation")
        self.need.addItem("Build and edit networks", "tools")
        self.need.addItem("Work with images", "vision")
        self.need.setCurrentIndex(max(0, self.need.findData(saved.get("task_need"))))
        routing_form.addRow(c.label("Task needs", role="label", scale=scale), self.need)
        layout.addLayout(routing_form)
        rules = c.Button("Project rules…", variant="secondary")
        rules.clicked.connect(self._project_rules)
        layout.addWidget(rules)
        jev_group = QtWidgets.QGroupBox("JEV routing measurement")
        jev_group.setObjectName("DsJevRouting")
        jev_layout = QtWidgets.QVBoxLayout(jev_group)
        self.jev_routing = QtWidgets.QComboBox()
        self.jev_routing.setObjectName("DsConnectionSelect")
        self.jev_routing.addItem("Off", "off")
        self.jev_routing.addItem("Measure routing", "shadow")
        self.jev_routing.setCurrentIndex(max(0, self.jev_routing.findData(saved.get("jev_routing_mode", "off"))))
        jev_layout.addWidget(self.jev_routing)
        jev_note = c.label(
            "Measure suggested routes while your chosen model works. This does not change its answer or tools. "
            "A separate TypeSafe permission covers your latest text request (up to 4,096 characters); "
            "history and attachments are excluded. Requests resembling code or credentials are skipped. "
            "Uses your configured TYPESAFE_API_KEY.", role="caption", scale=scale)
        jev_note.setWordWrap(True)
        jev_layout.addWidget(jev_note)
        jev_buttons = QtWidgets.QHBoxLayout()
        self.jev_permissions = c.Button("JEV permissions…", variant="secondary")
        self.jev_save = c.Button("Save routing preference", variant="ghost")
        self.jev_permissions.clicked.connect(self._jev_project_rules)
        self.jev_save.clicked.connect(self._save_jev)
        jev_buttons.addWidget(self.jev_permissions)
        jev_buttons.addWidget(self.jev_save)
        jev_layout.addLayout(jev_buttons)
        self.jev_status = c.label("", role="caption", scale=scale)
        self.jev_status.setWordWrap(True)
        self.jev_status.setTextFormat(QtCore.Qt.PlainText)
        jev_layout.addWidget(self.jev_status)
        layout.addWidget(jev_group)
        self._refresh_jev_status()
        self.destination = c.label("", role="body", scale=scale)
        self.destination.setWordWrap(True)
        self.destination.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.destination)
        self.status = c.label("Check the connection to discover available models.", role="body", scale=scale)
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        note = c.label(
            "Entered keys stay in this panel session. Closing the panel clears them; "
            "an in-flight response may finish, but closing stops further model requests. Existing environment keys still work.\n\n"
            "The check sends credentials and asks for model metadata only. It sends no scene or prompt.", role="caption", scale=scale)
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QtWidgets.QHBoxLayout()
        self.check = c.Button("Check connection", variant="secondary")
        self.use = c.Button("Use this model", variant="primary")
        self.use.setEnabled(False)
        cancel = c.Button("Cancel", variant="ghost")
        buttons.addWidget(self.check)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(self.use)
        outer.addLayout(buttons)  # Always accessible while the content scrolls.
        self.check.clicked.connect(self._check)
        self.use.clicked.connect(self._use)
        cancel.clicked.connect(self.reject)
        self.engine.currentIndexChanged.connect(self._engine_changed)
        for signal in (self.model.currentTextChanged, self.address.textChanged, self.key.textChanged):
            signal.connect(self._invalidate)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll)
        index = self.engine.findData(provider_id)
        self.engine.setCurrentIndex(index if index >= 0 else 0)
        self._engine_changed()
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(max(380, self.sizeHint().width()), max(380, available.width() - 32)),
                        min(self.sizeHint().height(), max(200, available.height() - 32)))

    def _engine_changed(self, *_):
        pid = self.engine.currentData()
        self.model.blockSignals(True)
        self.model.clear()
        for mid, _label in registry.models_for(pid):
            self.model.addItem(mid)
        picked = self._picks.get(pid) or self._custom.get("model") if pid == "custom" else self._picks.get(pid)
        self.model.setCurrentText(picked or registry.default_model(pid) or "")
        self.model.blockSignals(False)
        self.address.setVisible(pid == "custom")
        self.address_label.setVisible(pid == "custom")
        self.key.clear()
        self.key.setPlaceholderText("Optional for local Ollama" if pid == "ollama" else "Paste a key, or use an already configured key")
        self._invalidate()
        if pid == "ollama":
            self._discovery_changed()
            self._discovery.refresh()

    def _discovery_changed(self):
        if self.engine.currentData() != "ollama":
            return
        names = self._discovery.names()
        if names is not None:
            current = self.model.currentText()
            self.model.blockSignals(True)
            self.model.clear()
            self.model.addItems(list(names))
            self.model.setCurrentText(current)
            self.model.blockSignals(False)
        if self._future is None and self._checked is None:
            self.status.setText(self._discovery.message() or
                                "Models found. Check your selection before using it.")

    def _inputs(self):
        return (self.engine.currentData(), self.model.currentText().strip(),
                self.address.text().strip(), self.key.text().strip())

    def _candidate(self):
        pid, model, address, entered = self._inputs()
        if pid == "custom":
            from synapse.panel.providers.custom_provider import CustomProvider
            # Validate before constructing a provider; credentials cannot enter settings.
            cn.validate_endpoint(address)
            provider = CustomProvider(base_url=address, model=model,
                                      key_env=self._custom.get("key_env", "")
                                      if address == self._custom.get("base_url") else "")
        else:
            if pid not in registry.PROVIDER_IDS:
                raise ValueError("Choose an available service.")
            provider = registry.build_provider(pid, model=model)
        spec = cn.provider_spec(provider)
        key = entered or self._keys.get((pid, spec.endpoint)) or provider.resolve_key()
        return cn.bind_provider(provider, key=key)

    def _invalidate(self, *_):
        if self._checked is not None:
            self._checked.release()
        self._checked = None
        self.use.setEnabled(False)
        try:
            bound = self._candidate()
            self.destination.setText("Service: " + bound.spec.endpoint)
            bound.release()
        except Exception:
            self.destination.setText("Enter the service address and model to continue.")
        if self._future is None:
            self.status.setText("Check this selection before using it.")

    def _check(self):
        if self._future is not None:
            return
        try:
            bound = self._candidate()
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        except Exception:
            self.status.setText("Could not configure this service. Check the address and model.")
            return
        if not bound.provider.resolve_key():
            self.status.setText("Paste an API key to check this service.")
            bound.release()
            return
        self._request_inputs = self._inputs()
        self._candidate_bound = bound
        self.use.setEnabled(False)
        self.check.setEnabled(False)
        self.status.setText("Checking the service and available models…")
        self._future = self._executor.submit(cn.check_connection, bound.spec, bound.provider.resolve_key())
        self._timer.start()

    def _poll(self):
        if self._future is None or not self._future.done():
            return
        result = self._future.result()
        self._future = None
        self._timer.stop()
        self.check.setEnabled(True)
        bound = self._candidate_bound
        self._candidate_bound = None
        if self._inputs() != self._request_inputs:
            bound.release()
            self.status.setText("Selection changed. Check this selection before using it.")
            return
        current = self.model.currentText()
        self.model.blockSignals(True)
        for model in result.models:
            if self.model.findText(model) < 0:
                self.model.addItem(model)
        self.model.setCurrentText(current)
        self.model.blockSignals(False)
        if bound.spec.provider == "ollama" and (result.models or result.ok):
            self._discovery.remember(bound.spec.endpoint, result.models)
        self.status.setText(result.message)
        self.destination.setText(result.facts.description if result.facts else "Service: " + bound.spec.endpoint)
        if result.ok:
            bound.facts = result.facts
            self._checked = bound
            self.use.setEnabled(True)
        else:
            bound.release()

    def _use(self):
        if self._checked is None or self._inputs() != self._request_inputs:
            return
        bound = self._checked
        from synapse.panel.settings import load_settings, save_settings
        settings = load_settings()
        settings.update(routing_mode=self.routing.currentData(), task_need=self.need.currentData(),
                        jev_routing_mode=self.jev_routing.currentData())
        if not save_settings(settings):
            self.status.setText("The model preferences could not be saved. Try again.")
            return
        self.selection = (bound.spec, bound.facts, bound.provider.resolve_key(),
                          self.address.text().strip())
        self.accept()

    def _project_rules(self):
        from synapse.panel.project_rules import ProjectRulesDialog
        bound = None
        try:
            bound = self._candidate()
            spec = bound.spec
        except Exception:
            spec = None
        finally:
            if bound is not None:
                bound.release()
        dialog = ProjectRulesDialog(self, spec=spec)
        dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        dialog.deleteLater()

    def _save_jev(self):
        from synapse.panel.settings import load_settings, save_settings
        settings = load_settings()
        settings["jev_routing_mode"] = self.jev_routing.currentData()
        if not save_settings(settings):
            self.jev_status.setText("The routing preference could not be saved. Try again.")
            return
        self._refresh_jev_status()

    def _refresh_jev_status(self):
        from synapse import model_access as access
        from synapse.jev import adapter
        from synapse.panel.settings import load_settings
        if load_settings().get("jev_routing_mode") != "shadow":
            self.jev_status.setText("Off. No artist request is sent to JEV.")
            return
        if not adapter.enabled(opt_in=True):
            self.jev_status.setText("Unavailable: disabled by SYNAPSE_JEV. Your chosen model is unchanged.")
            return
        key = adapter.resolve_key()
        if not key:
            self.jev_status.setText("Unavailable: configure TYPESAFE_API_KEY. Your chosen model is unchanged.")
            return
        try:
            access.require_access(adapter.connection_spec(), key=key)
        except access.ModelAccessDenied as exc:
            self.jev_status.setText("Unavailable: " + str(exc))
            return
        self.jev_status.setText("Ready to measure future tasks. Endpoint: " + adapter.ENDPOINT)

    def _jev_project_rules(self):
        from synapse.jev.adapter import connection_spec
        from synapse.panel.project_rules import ProjectRulesDialog
        dialog = ProjectRulesDialog(self, spec=connection_spec())
        dialog.exec() if hasattr(dialog, "exec") else dialog.exec_()
        dialog.deleteLater()
        self._refresh_jev_status()

    def done(self, result):
        try:
            self._discovery.changed.disconnect(self._discovery_changed)
        except RuntimeError:
            pass
        if self._owns_discovery:
            self._discovery.close()
        self._timer.stop()
        for bound in (self._checked, getattr(self, "_candidate_bound", None)):
            if bound is not None:
                bound.release()
        self._checked = None
        self._candidate_bound = None
        self._keys.clear()
        self.key.clear()
        self._request_inputs = None
        self._executor.shutdown(wait=False, cancel_futures=True)
        super().done(result)
