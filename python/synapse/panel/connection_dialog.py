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
                 session_keys=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        qss.prepare_connection_dialog(self, getattr(parent, "_chrome_scale", 1.0))
        self.setWindowTitle("Connect a model")
        self.setMinimumWidth(380)
        self._picks = dict(models or {})
        self._custom = dict(custom or {})
        self._keys = dict(session_keys or {})
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="synapse-connection")
        self._future = None
        self._checked = None
        self.selection = None
        layout = QtWidgets.QVBoxLayout(self)
        intro = c.label("Choose where SYNAPSE sends this panel’s requests.", role="body")
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
        form.addRow(c.label("Service", role="label"), self.engine)
        self.model = QtWidgets.QComboBox()
        self.model.setObjectName("DsConnectionSelect")
        self.model.setEditable(True)
        self.model.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.model.setMinimumContentsLength(15)
        form.addRow(c.label("Model", role="label"), self.model)
        self.address = QtWidgets.QLineEdit(self._custom.get("base_url", ""))
        self.address.setPlaceholderText("https://your-service/v1")
        self.address_label = c.label("Service address", role="label")
        form.addRow(self.address_label, self.address)
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key.setPlaceholderText("Paste a key, or use an already configured key")
        form.addRow(c.label("API key", role="label"), self.key)
        for edit in (self.address, self.key, self.model.lineEdit()):
            edit.setObjectName("DsField")
        layout.addLayout(form)
        self.destination = c.label("", role="body")
        self.destination.setWordWrap(True)
        self.destination.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.destination)
        self.status = c.label("Check the connection to discover available models.", role="body")
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        note = c.label(
            "Entered keys stay in this panel session. Closing the panel clears them; "
            "a task already running may finish first. Existing environment keys still work.\n\n"
            "The check sends credentials and asks for model metadata only. It sends no scene or prompt.", role="caption")
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
        layout.addLayout(buttons)
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
        self.selection = (bound.spec, bound.facts, bound.provider.resolve_key(),
                          self.address.text().strip())
        self.accept()

    def done(self, result):
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
