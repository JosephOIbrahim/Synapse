"""Artist-driven World Labs Atlas import. Network work and SPZ decoding never run on the Qt thread.

SYNAPSE reads Atlas and never drives it: it lists finished splat operations, downloads one, decodes its SPZ, and
imports it. Atlas tasks cost credits, so they are run with the ``worldlabs`` CLI or the World Labs app.
"""
from __future__ import annotations

import os
from pathlib import Path
import time
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
    button.setAccessibleName("World Labs — import an Atlas splat scene")
    button.setToolTip("Import a World Labs Atlas splat scene or a local .spz / .ply Gaussian splat")
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


def _operation_title(row):
    created = row.get("created")
    when = time.strftime("%Y-%m-%d %H:%M", time.localtime(created)) if isinstance(created, int) else "recent"
    return "Splats · %s · %s" % (str(row["id"])[:10], when)


class WorldLabsDialog(QtWidgets.QDialog):
    """Session-only credentials and one explicit import per artist click."""

    _received = QtCore.Signal(object)

    def __init__(self, parent=None, *, client_factory=None, importer=None, preparer=None,
                 cache_dir=None, task_factory=None, key_resolver=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setWindowTitle("SYNAPSE · World Labs")
        self.setModal(False)
        self._client_factory = client_factory
        self._importer = importer
        self._preparer = preparer
        self._key_resolver = key_resolver
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
        intro = c.label("Bring a World Labs Atlas splat scene into Houdini.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addSpacing(t.scaled(t.SPACE_SM, scale))

        key_label = c.label("Atlas API connection", role="label", scale=scale)
        layout.addWidget(key_label)
        self.key = QtWidgets.QLineEdit()
        self.key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.key.setPlaceholderText("Atlas API key · kept for this session")
        self.key.setAccessibleName("World Labs Atlas API key")
        self.key.setText(os.environ.get("WLT_API_KEY", ""))
        # A key saved by `worldlabs auth login` is used as is. It is never shown in the field.
        saved_source = None if self.key.text() else self._resolve_key("")[1]
        if saved_source:
            self.key.setPlaceholderText("Using your %s · paste a key to override" % saved_source)
        key_label.setBuddy(self.key)
        layout.addWidget(self.key)
        self.connect_button = c.Button("Connect to Atlas", variant="secondary")
        self.connect_button.clicked.connect(self._connect)
        layout.addWidget(self.connect_button)

        self.recent = QtWidgets.QComboBox()
        self.recent.setAccessibleName("Recent Atlas splat scenes")
        self.recent.addItem("Recent splat scenes", None)
        self.recent.activated.connect(self._pick_recent)
        self.recent.hide()
        layout.addWidget(self.recent)
        layout.addSpacing(t.scaled(t.SPACE_SM, scale))
        source_label = c.label("Atlas operation or local splat", role="label", scale=scale)
        layout.addWidget(source_label)
        self.source = QtWidgets.QLineEdit()
        self.source.setPlaceholderText("Atlas operation ID, a downloaded folder, or a local .spz / .ply path")
        self.source.setAccessibleName("Atlas operation ID, downloaded folder, or local Gaussian splat path")
        source_label.setBuddy(self.source)
        layout.addWidget(self.source)
        self.detail = QtWidgets.QComboBox()
        self.detail.setAccessibleName("Splat detail")
        for title, value in (("Most splats", "most"), ("Fewest splats · layout", "fewest")):
            self.detail.addItem(title, value)
        layout.addWidget(self.detail)
        self.status = c.label(("Using your %s. " % saved_source if saved_source else
                               "Local .spz and .ply splats work without an API key. ")
                              + "Connect to list your finished Atlas splat scenes.", role="body", scale=scale)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        self.status.setWordWrap(True)
        self.status.setAccessibleName("World Labs import status")
        layout.addWidget(self.status)
        layout.addStretch(1)
        row = QtWidgets.QHBoxLayout()
        self.close_button = c.Button("Close", variant="secondary")
        self.close_button.clicked.connect(self.close)
        self.import_button = c.Button("Import splats", variant="primary")
        self.import_button.clicked.connect(self._import)
        row.addWidget(self.close_button)
        row.addWidget(self.import_button)
        layout.addLayout(row)
        submenus.prepare(self, scale, kind="worldlabs")
        self.resize(round(540 * min(scale, 1.5)), round(510 * min(scale, 1.4)))

    def _client(self):
        factory = self._client_factory
        if factory is None:
            from synapse.worldlabs.client import AtlasClient
            factory = AtlasClient
        return factory(self.key.text().strip())

    def _resolve_key(self, typed):
        resolver = self._key_resolver
        if resolver is None:
            from synapse.worldlabs.client import resolve_key
            resolver = resolve_key
        return resolver(typed)

    def _has_key(self):
        return bool(self._resolve_key(self.key.text())[0])

    def _prepare_local(self, path):
        preparer = self._preparer
        if preparer is None:
            from synapse.worldlabs.importer import prepare_local_asset
            preparer = prepare_local_asset
        return preparer(path, self._cache_dir)

    def _set_busy(self, on):
        self._busy = on
        for control in (self.key, self.source, self.recent, self.detail,
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
        if not self._has_key():
            self.status.setText("Add your Atlas API key, or run `worldlabs auth login`, to connect. "
                                "Local files can still be imported.")
            return
        client = self._client()
        self.status.setText("Checking your Atlas connection…")
        self._start("connect", lambda: {"connection": client.check_connection()})

    def _pick_recent(self, index):
        identifier = self.recent.itemData(index)
        if identifier:
            self.source.setText(str(identifier))

    def _import(self):
        if self._busy:
            return
        source = self.source.text().strip().strip('"')
        if not source:
            self.status.setText("Paste an Atlas operation ID, or the path to a downloaded folder or local splat.")
            return
        local = Path(source).expanduser()
        if local.is_file() or local.is_dir():
            self.status.setText("Preparing the local splat…")
            self._start("import", lambda: self._prepare_local(local))
            return
        if local.is_absolute() or source.lower().endswith((".ply", ".spz")):
            self.status.setText("That local file could not be found. Check its full path.")
            return
        if not self._has_key():
            self.status.setText("An Atlas API key is needed to import this operation. Add one, run "
                                "`worldlabs auth login`, or use a local file.")
            return
        client = self._client()
        choice = self.detail.currentData()
        cache_dir = self._cache_dir
        self.status.setText("Reading the Atlas operation and downloading its splats…")
        self._start("import", lambda: client.prepare_import(source, cache_dir, choice))

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
            operations = value["connection"].get("operations") or []
            self.recent.clear()
            self.recent.addItem("Choose a splat scene…", None)
            for row in operations:
                self.recent.addItem(_operation_title(row), row["id"])
            self.recent.setVisible(bool(operations))
            if operations:
                self.status.setText("Connected · %d recent splat scene%s. Choose one or paste an operation ID."
                                    % (len(operations), "" if len(operations) == 1 else "s"))
            else:
                self.status.setText("Connected. No finished splat scenes yet: run posedImages2Splats with the "
                                    "worldlabs CLI or the World Labs app, then connect again.")
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
            notes = list(value.get("metadata", {}).get("notes") or []) + list(imported.get("warnings", []))
            self.status.setText(("Imported into %s. " % node + " ".join(str(item) for item in notes)).strip())

    def hideEvent(self, event):
        # Escape/reject(), close(), and hiding a parent all dismiss the view.
        # A finished download cannot change the scene after any of these.
        self._serial += 1
        self._set_busy(False)
        super().hideEvent(event)
