"""Artist-facing saved networks. Direct local actions; no model requests."""
from collections import Counter

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets

from synapse.panel.designsystem import components as c, qss, tokens as t


def describe(record):
    snapshot = record["snapshot"]
    counts = Counter(item["kind"] for item in snapshot.get("dependencies", []))
    lines = [f"{record['name']} · version {record['version']}",
             "Tags: " + (", ".join(record["tags"]) or "none yet"), record["notes"],
             f"{len(snapshot['nodes'])} nodes · Houdini {snapshot['houdini']}",
             "From: " + snapshot["source_scene"], "", "Dependencies"]
    if counts:
        lines.append(" · ".join(f"{count} {kind}" for kind, count in sorted(counts.items())))
    for item in snapshot.get("dependencies", []):
        location = item.get("node", item.get("destination", ""))
        if item.get("parm"):
            location += "." + item["parm"]
        if item.get("type"):
            location += " · " + item["type"]
        lines.append(f"{item['kind']} · {item['status']} · {location}\n{item['value']}")
    lines.extend(["", "Authored expressions are preserved. Their external dependencies may be unresolved.",
                  "Insertion creates a new subnet. File assets are not embedded; external input wires are not reconnected.",
                  "Saved network; rendering and portability have not been qualified."])
    return "\n".join(lines)


class SavedRecipesDialog(QtWidgets.QDialog):
    def __init__(self, parent, service, watch, *, busy=None):
        super().__init__(parent)
        self.service, self.watch = service, watch
        self.busy = busy or (lambda: False)
        self.selected = None
        self.setObjectName("DsRoot")
        self.setProperty("panel_popup", "recipes")
        self.setWindowTitle("Saved recipes")
        scale = getattr(parent, "_chrome_scale", 1.0)
        qss.prepare_saved_recipes_dialog(self, scale)
        font = QtGui.QFont(self.font())
        font.setPixelSize(t.scaled(t.SIZE_BODY, scale))
        self.setFont(font)
        self.resize(round(640 * min(scale, 1.4)), round(650 * min(scale, 1.25)))
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
        intro = c.label("Keep useful networks on this workstation.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        location = c.label("Local library · " + str(service.library.root), role="caption", scale=scale)
        location.setWordWrap(True)
        location.setTextFormat(QtCore.Qt.PlainText)
        location.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(location)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setMinimumSize(0, 0)
        layout.addWidget(self.tabs, 1)

        library_page = QtWidgets.QWidget()
        library_page.setObjectName("DsRecipePage")
        library_layout = QtWidgets.QVBoxLayout(library_page)
        self.search = QtWidgets.QLineEdit()
        self.search.setObjectName("DsField")
        self.search.setPlaceholderText("Search names, tags and notes")
        library_layout.addWidget(self.search)
        self.versions = QtWidgets.QCheckBox("Show all versions")
        library_layout.addWidget(self.versions)
        self.items = QtWidgets.QListWidget()
        self.items.setMinimumHeight(80)
        library_layout.addWidget(self.items, 2)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        library_layout.addWidget(self.details, 2)
        self.reviewed = QtWidgets.QCheckBox("Dependencies reviewed")
        self.reviewed.setToolTip("I have reviewed the listed dependencies and unresolved references.")
        library_layout.addWidget(self.reviewed)
        self.insert = c.Button("Insert a copy", variant="primary")
        self.insert.setEnabled(False)
        library_layout.addWidget(self.insert)
        self.tabs.addTab(self._scroll_page(library_page), "Library")

        capture_page = QtWidgets.QWidget()
        capture_page.setObjectName("DsRecipePage")
        capture_layout = QtWidgets.QVBoxLayout(capture_page)
        explanation = c.label("Select sibling Solaris nodes in Houdini, then name what is worth keeping.", role="body", scale=scale)
        explanation.setWordWrap(True)
        capture_layout.addWidget(explanation)
        form = QtWidgets.QFormLayout()
        form.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        self.name = QtWidgets.QLineEdit()
        self.tags = QtWidgets.QLineEdit()
        self.notes = QtWidgets.QPlainTextEdit()
        self.notes.setMaximumHeight(round(100 * scale))
        self.name.setPlaceholderText("Soft studio lighting")
        self.tags.setPlaceholderText("lookdev, studio, soft light")
        for field in (self.name, self.tags, self.notes):
            field.setObjectName("DsField")
        for label, field in (("Name", self.name), ("Tags", self.tags), ("Notes", self.notes)):
            form.addRow(c.label(label, role="label", scale=scale), field)
        capture_layout.addLayout(form)
        self.update = QtWidgets.QCheckBox("Save as a new version")
        self.update.setToolTip("Save a new version of the recipe selected in Library.")
        capture_layout.addWidget(self.update)
        self.save = c.Button("Save selection", variant="primary")
        capture_layout.addWidget(self.save)
        self.keep = c.Button("Keep at the next scene change", variant="secondary")
        capture_layout.addWidget(self.keep)
        self.stop_watch = c.Button("Stop keeping this selection", variant="ghost")
        capture_layout.addWidget(self.stop_watch)
        note = c.label("Keep arms this selection once. SYNAPSE saves locally before the next scene change or panel close, then stops watching. It cannot recover from a forced quit.", role="caption", scale=scale)
        note.setWordWrap(True)
        capture_layout.addWidget(note)
        capture_layout.addStretch()
        self.tabs.addTab(self._scroll_page(capture_page), "Save selection")
        self.status = c.label("", role="body", scale=scale)
        self.status.setWordWrap(True)
        self.status.setTextFormat(QtCore.Qt.PlainText)
        layout.addWidget(self.status)
        close = c.Button("Close", variant="ghost")
        close.clicked.connect(self.close)
        layout.addWidget(close)

        self.search.textChanged.connect(self.refresh)
        self.versions.toggled.connect(self.refresh)
        self.items.currentItemChanged.connect(self._select)
        self.reviewed.toggled.connect(self._update_insert)
        self.insert.clicked.connect(self._insert)
        self.save.clicked.connect(self._save)
        self.keep.clicked.connect(self._keep)
        self.stop_watch.clicked.connect(self._stop)
        self.update.toggled.connect(lambda checked: self.save.setText("Save new version" if checked else "Save selection"))
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(1000)
        self._refresh_timer.timeout.connect(lambda: self.stop_watch.setEnabled(self.watch.armed))
        self._refresh_timer.start()
        self.refresh()
        try:
            previous = service.last_notice()
            if previous:
                message = previous.get("message") if isinstance(previous, dict) else None
                self.status.setText("Previous result · " + message if isinstance(message, str) and message.strip() else "The last capture record is unreadable. Your library can still be inspected.")
        except Exception as exc:
            self.status.setText(f"The last capture record is unavailable: {exc}")

    def _scroll_page(self, page):
        scroll = QtWidgets.QScrollArea()
        scroll.setObjectName("DsRecipeScroll")
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        return scroll

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry().adjusted(16, 32, -16, -32)
            self.resize(min(self.width(), available.width()), min(self.height(), available.height()))
            self.move(max(available.left(), min(self.x(), available.right() - self.width())),
                      max(available.top(), min(self.y(), available.bottom() - self.height())))

    def refresh(self, *_):
        self.items.clear()
        self.selected = None
        self.details.clear()
        self.reviewed.setChecked(False)
        self.insert.setEnabled(False)
        try:
            entries, problems = self.service.search(self.search.text(), all_versions=self.versions.isChecked())
            for record in entries:
                title = f"{record['name']} · v{record['version']}"
                if record["tags"]:
                    title += "\n" + ", ".join(record["tags"])
                item = QtWidgets.QListWidgetItem(title)
                item.setData(QtCore.Qt.UserRole, (record["recipe_id"], record["version"]))
                self.items.addItem(item)
            if problems:
                self.status.setText(f"{len(problems)} saved version(s) could not be verified. " + problems[0])
            elif not entries:
                self.status.setText("No matching recipes. Use Save selection to keep a useful network.")
            else:
                self.status.setText(f"{len(entries)} local saved version(s). Choose one to inspect.")
        except Exception as exc:
            self.status.setText(str(exc))
        self.stop_watch.setEnabled(self.watch.armed)

    def _select(self, item, *_):
        self.selected = None
        self.reviewed.setChecked(False)
        if item is not None:
            try:
                self.selected = self.service.inspect(*item.data(QtCore.Qt.UserRole))
                self.details.setPlainText(describe(self.selected))
            except Exception as exc:
                self.details.setPlainText(str(exc))
        self._update_insert()

    def _update_insert(self, *_):
        self.insert.setEnabled(self.selected is not None and self.reviewed.isChecked())

    def _metadata(self):
        if self.busy():
            raise ValueError("Wait for the current SYNAPSE task to finish before saving or inserting a network.")
        recipe_id = None
        if self.update.isChecked():
            if self.selected is None:
                raise ValueError("Choose a recipe in Library before saving a new version.")
            recipe_id = self.selected["recipe_id"]
        return self.name.text(), self.tags.text().split(","), self.notes.toPlainText(), recipe_id

    def _save(self):
        try:
            name, tags, notes, identifier = self._metadata()
            saved = self.service.save_selection(name, tags, notes, recipe_id=identifier)
            result = {"status": "saved", "message": f"Saved {saved['name']} · version {saved['version']} locally."}
            try:
                self.service.record_notice(result)
            except Exception as exc:
                result["message"] += f" The last-result record could not be updated: {exc}"
            self.refresh()
            self.status.setText(result["message"])
        except Exception as exc:
            self.status.setText(str(exc))

    def _keep(self):
        try:
            name, tags, notes, identifier = self._metadata()
            self.watch.arm(name, tags, notes, recipe_id=identifier)
            self.status.setText(self.watch.last_result["message"])
            self.stop_watch.setEnabled(True)
        except Exception as exc:
            self.status.setText(str(exc))

    def _stop(self):
        self.watch.disarm()
        self.status.setText(self.watch.last_result["message"])
        self.stop_watch.setEnabled(False)

    def _insert(self):
        if self.selected is None or not self.reviewed.isChecked():
            return
        try:
            if self.busy():
                raise ValueError("Wait for the current SYNAPSE task to finish before inserting a network.")
            result = self.service.restore(self.selected["recipe_id"], self.selected["version"], dependencies_reviewed=True)
            self.status.setText(result["message"] + " " + result["path"])
        except Exception as exc:
            self.status.setText(str(exc))
