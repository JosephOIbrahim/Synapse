"""Artist-driven Marble import. Network work never runs on the Qt thread."""
from __future__ import annotations

import os
from pathlib import Path
import weakref

from .designsystem import components as c, submenus, tokens as t

QtCore, QtWidgets = c.QtCore, c.QtWidgets
_CALLS = set()


class _Call(QtCore.QThread):
    delivered = QtCore.Signal(object)

    def __init__(self, action):
        super().__init__(None)
        self.action = action

    def run(self):
        try:
            result = {"value": self.action()}
        except Exception as exc:
            # Backend errors are deliberately public messages, with credentials
            # and signed asset URLs excluded. No traceback reaches the panel.
            result = {"error": str(exc)}
        self.action = None
        self.delivered.emit(result)


def _deliver(reference, serial, kind, result):
    dialog = reference()
    if dialog is not None:
        try:
            dialog._received.emit((serial, kind, result))
        except RuntimeError:
            pass


def create_worldlabs_button(panel):
    existing = getattr(panel, "_worldlabs_btn", None)
    if existing is not None:
        return existing
    button = c.Button("World Labs", variant="ghost")
    button.setAccessibleName("World Labs — import a Marble world")
    button.setToolTip("Import a Marble world or a local Gaussian splat export")
    button.clicked.connect(lambda: open_worldlabs(panel))
    panel._worldlabs_btn = button
    return button


def open_worldlabs(panel):
    dialog = getattr(panel, "_worldlabs_dialog", None)
    if dialog is None:
        dialog = WorldLabsDialog(panel)
        panel._worldlabs_dialog = dialog
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


class WorldLabsDialog(QtWidgets.QDialog):
    """Session-only credentials and one explicit import per artist click."""

    _received = QtCore.Signal(object)

    def __init__(self, parent=None, *, client_factory=None, importer=None,
                 cache_dir=None, task_factory=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setWindowTitle("SYNAPSE · World Labs")
        self.setModal(False)
        self._client_factory = client_factory
        self._importer = importer
        self._task_factory = task_factory or _Call
        self._cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".synapse" / "worldlabs"
        self._serial = 0
        self._busy = False
        self._received.connect(self._receive)
        scale = getattr(parent, "_chrome_scale", t.FONT_SCALE_DEFAULT)
        c.apply_stylesheet(self, scale)
        layout = QtWidgets.QVBoxLayout(self)
        heading = c.label("World Labs", role="title", scale=scale)
        layout.addWidget(heading)
        intro = c.label("Bring a Marble world into your scene.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addSpacing(t.scaled(t.SPACE_SM, scale))

        key_label = c.label("World API connection", role="label", scale=scale)
        layout.addWidget(key_label)
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key.setPlaceholderText("World Labs API key · kept for this session")
        self.key.setAccessibleName("World Labs API key")
        self.key.setText(os.environ.get("WLT_API_KEY", ""))
        key_label.setBuddy(self.key)
        layout.addWidget(self.key)
        self.connect_button = c.Button("Connect World Labs", variant="secondary")
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)

        self.recent = QtWidgets.QComboBox()
        self.recent.setAccessibleName("Recent World API worlds")
        self.recent.addItem("Recent API worlds", None)
        self.recent.activated.connect(self._pick_recent)
        self.recent.hide()
        layout.addWidget(self.recent)
        layout.addSpacing(t.scaled(t.SPACE_SM, scale))
        source_label = c.label("World or local export", role="label", scale=scale)
        layout.addWidget(source_label)
        self.source = QtWidgets.QLineEdit()
        self.source.setPlaceholderText("Marble URL, world ID, or local .ply path")
        self.source.setAccessibleName("Marble world URL, ID, or local Gaussian splat path")
        source_label.setBuddy(self.source)
        layout.addWidget(self.source)
        self.resolution = QtWidgets.QComboBox()
        self.resolution.setAccessibleName("Splat resolution")
        for title, value in (("Layout · 100k", "100k"), ("Balanced · 500k", "500k"),
                             ("Full resolution", "full_res")):
            self.resolution.addItem(title, value)
        self.resolution.setCurrentIndex(1)
        layout.addWidget(self.resolution)
        self.status = c.label("Gaussian-splat PLY exports work without an API key. Connect to browse your API worlds.",
                              role="body", scale=scale)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("World Labs import status")
        layout.addWidget(self.status)
        layout.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        self.close_button = c.Button("Close", variant="secondary")
        self.close_button.clicked.connect(self.close)
        self.import_button = c.Button("Import world", variant="primary")
        self.import_button.clicked.connect(self._import)
        row.addWidget(self.close_button)
        row.addWidget(self.import_button)
        layout.addLayout(row)
        submenus.prepare(self, scale, kind="worldlabs")
        self.resize(round(540 * min(scale, 1.5)), round(510 * min(scale, 1.4)))

    def _client(self):
        factory = self._client_factory
        if factory is None:
            from synapse.worldlabs.client import WorldLabsClient
            factory = WorldLabsClient
        return factory(self.key.text().strip())

    def _set_busy(self, on):
        self._busy = on
        for control in (self.key, self.source, self.recent, self.resolution,
                        self.connect_button, self.import_button):
            control.setEnabled(not on)

    def _start(self, kind, action):
        if self._busy:
            return
        self._serial += 1
        serial = self._serial
        worker = self._task_factory(action)
        _CALLS.add(worker)
        reference = weakref.ref(self)
        worker.delivered.connect(lambda result: _deliver(reference, serial, kind, result))

        def release():
            _CALLS.discard(worker)
            worker.deleteLater()

        worker.finished.connect(release)
        self._set_busy(True)
        worker.start()

    def _connect(self):
        if not self.key.text().strip():
            self.status.setText("Add your World Labs API key to connect. Local files can still be imported.")
            return
        client = self._client()
        self.status.setText("Checking your World API connection…")

        def connect():
            facts = client.check_connection()
            worlds = client.list_worlds()
            return {"connection": facts, "worlds": worlds}

        self._start("connect", connect)

    def _pick_recent(self, index):
        identifier = self.recent.itemData(index)
        if identifier:
            self.source.setText(str(identifier))

    def _import(self):
        if self._busy:
            return
        source = self.source.text().strip().strip('"')
        if not source:
            self.status.setText("Paste a Marble world URL or ID, or the path to a local splat export.")
            return
        local = Path(source).expanduser()
        if local.is_file():
            self.status.setText("Preparing the local splat…")
            self._start("import", lambda: {"path": str(local), "metadata": {}})
            return
        if local.is_absolute() or source.lower().endswith((".ply", ".spz")):
            self.status.setText("That local file could not be found. Check its full path.")
            return
        if not self.key.text().strip():
            self.status.setText("Connect with your World Labs API key to import this world, or use a local export.")
            return
        client = self._client()
        resolution = self.resolution.currentData()
        cache_dir = self._cache_dir
        self.status.setText("Resolving the world and downloading its splat…")
        self._start("import", lambda: client.prepare_import(source, resolution, cache_dir))

    def _receive(self, envelope):
        serial, kind, result = envelope
        if serial != self._serial or not self.isVisible():
            return
        self._set_busy(False)
        if "error" in result:
            # Also protect against an unexpected third-party exception echoing
            # the key. Backend tests cover URLs/headers in ordinary failures.
            error = str(result["error"])
            secret = self.key.text().strip()
            self.status.setText(error.replace(secret, "[redacted]") if secret else error)
            return
        value = result["value"]
        if kind == "connect":
            self.recent.clear()
            self.recent.addItem("Choose an API world…", None)
            for world in value["worlds"]:
                self.recent.addItem(world.get("title") or world["id"], world["id"])
            self.recent.setVisible(bool(value["worlds"]))
            balance = value["connection"].get("remaining_credits")
            summary = "Connected" if balance is None else "Connected · %s API credits" % balance
            self.status.setText(summary + ". Choose an API world or paste its URL. For Marble app worlds, a local export is also available.")
            return
        try:
            importer = self._importer
            if importer is None:
                from synapse.server.main_thread import run_on_main
                from synapse.worldlabs.importer import import_local_asset
                importer = lambda path, metadata: run_on_main(
                    lambda: import_local_asset(path, metadata), timeout=30,
                    label="worldlabs-import")
            imported = importer(value["path"], value.get("metadata", {}))
        except Exception as exc:
            self.status.setText(str(exc))
        else:
            node = imported.get("node_path", imported.get("path", "the scene"))
            warnings = " ".join(str(item) for item in imported.get("warnings", []))
            self.status.setText(("Imported into %s. " % node + warnings).strip())

    def hideEvent(self, event):
        # Escape/reject(), close(), and hiding a parent all dismiss the view.
        # A finished download cannot change the scene after any of these.
        self._serial += 1
        self._set_busy(False)
        super().hideEvent(event)
