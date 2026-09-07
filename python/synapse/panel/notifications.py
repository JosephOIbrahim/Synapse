"""Local Events UI. Reads process facts; it never runs a model or a job."""
from __future__ import annotations

from datetime import datetime

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

from synapse import job_events
from . import settings
from .designsystem import components as c, qss, rhythm, tokens as t

ATTENTION = frozenset(("failed", "cancelled", "unknown"))
STATE_LABELS = {"running": "Running", "completed": "Finished", "failed": "Failed",
                "cancelled": "Cancelled", "preview": "Preview only", "unknown": "Needs attention",
                "info": "Update"}


def _close_watches(owners):
    """QObject destruction holds this box, never a callback into deleted Qt."""
    for owner in owners[:]:
        try:
            owner.close()
        except Exception:
            pass
    owners.clear()


def _detail(entry):
    lines = [entry.get("title", ""), STATE_LABELS.get(entry.get("state"), "Unknown"),
             entry.get("detail", "")]
    for key, label in (("node", "Node"), ("scene", "Scene")):
        if entry.get(key):
            lines.append(label + ": " + str(entry[key]))
    if entry.get("source"):
        names = {"model": "Model connection check", "bridge": "Local Houdini connection",
                 "render_session": "SYNAPSE render", "render_inline": "SYNAPSE render",
                 "render_batch_report": "Render batch report", "render_frame_report": "Render frame report",
                 "desktop": "Desktop notifications"}
        lines.append("Observed by: " + names.get(entry["source"], "Houdini work watcher"))
    return "\n".join(line for line in lines if line)


def _paired_layout():
    """Keep related controls together, wrapping at the host's actual font size."""
    layout = QtWidgets.QFormLayout()
    layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
    layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
    return layout


class NotificationController(QtCore.QObject):
    changed = QtCore.Signal(dict)

    def __init__(self, parent):
        super().__init__(parent)
        self.journal = job_events.get_journal()
        self.journal.initialize_policy(settings.load_settings().get("notifications", {}))
        snapshot = self.journal.snapshot()
        self._cursor = snapshot["sequence"]
        self._revision = -1
        self._policy = None
        self._bridge_running = None
        self._closed = False
        self._watch_owners = []
        parent.destroyed.connect(lambda *_args, owners=self._watch_owners: _close_watches(owners))
        self.destroyed.connect(lambda *_args, owners=self._watch_owners: _close_watches(owners))
        self._tray = None
        self.desktop_available = bool(QtWidgets.QSystemTrayIcon.isSystemTrayAvailable()
                                      and QtWidgets.QSystemTrayIcon.supportsMessages())
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(750)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self):
        if self._closed:
            return
        # This is the server's own cheap flag, not a network or HOM probe.
        try:
            from synapse.server.hwebserver_adapter import is_running
            running = bool(is_running())
        except Exception:
            running = None
        if running is not None:
            if self._bridge_running is not None and running != self._bridge_running:
                self.journal.note("connection", "Local bridge ready" if running else "Local bridge stopped",
                                  "External tools can reach this Houdini bridge." if running else
                                  "External tools cannot reach this bridge. Use Connect to start it again.",
                                  state="info" if running else "failed", source="bridge",
                                  dedupe_key="local-bridge")
            self._bridge_running = running
        snapshot = self.journal.snapshot()
        alerts = self.journal.claim_alerts(self._cursor)
        self._cursor = snapshot["sequence"]
        if alerts and self.desktop_available:
            try:
                self._show_desktop(alerts)
            except Exception:
                self.desktop_available = False
                self.journal.note("system", "Desktop alerts unavailable",
                                  "The operating system could not accept an alert. Work updates remain in Events.",
                                  state="unknown", source="desktop", dedupe_key="desktop-unavailable")
        policy = self.journal.get_policy()
        if snapshot["revision"] != self._revision or policy != self._policy:
            self._revision, self._policy = snapshot["revision"], policy
            self.changed.emit(snapshot)

    def _show_desktop(self, entries):
        # No paths, scene/model names or error messages enter OS history.
        if self._tray is None:
            self._tray = QtWidgets.QSystemTrayIcon(self)
            app = QtWidgets.QApplication.instance()
            self._tray.setIcon(app.style().standardIcon(QtWidgets.QStyle.SP_MessageBoxInformation))
            self._tray.setToolTip("SYNAPSE events")
            self._tray.show()
        attention = any(item["state"] in ATTENTION for item in entries)
        title = "SYNAPSE needs attention" if attention else "SYNAPSE work update"
        self._tray.showMessage(title, "Open Events in SYNAPSE to see the details.",
                               QtWidgets.QSystemTrayIcon.Warning if attention else
                               QtWidgets.QSystemTrayIcon.Information, 5000)

    def change_policy(self, updates):
        policy = self.journal.get_policy()
        policy.update(updates)
        saved = settings.load_settings()
        saved["notifications"] = policy
        if not settings.save_settings(saved):
            return False
        self.journal.set_policy(policy)
        self.refresh()
        return True

    def watch_selected(self):
        if not self._watch_owners:
            from synapse.host.job_watch import WatchSession
            self._watch_owners.append(WatchSession(self.journal))
        return self._watch_owners[0].watch_selected()

    def stop_watching(self):
        _close_watches(self._watch_owners)
        self.refresh()

    def focus_node(self, identity):
        for owner in self._watch_owners:
            if owner.focus(identity):
                return True
        return False

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._timer.stop()
        _close_watches(self._watch_owners)
        if self._tray is not None:
            self._tray.hide()


class NotificationsDialog(QtWidgets.QDialog):
    def __init__(self, controller, parent=None, *, open_connections=None):
        super().__init__(parent)
        self.controller = controller
        self._open_connections = open_connections
        self._entries = {}
        self.setWindowTitle("SYNAPSE · Events")
        self.setObjectName("DsRoot")
        self.setProperty("panel_popup", "notifications")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setModal(False)
        scale = getattr(parent, "_chrome_scale", 1.0)
        qss.prepare_events_dialog(self, scale)
        self.resize(round(560 * min(scale, 1.7)), round(640 * min(scale, 1.5)))
        self.setMinimumSize(360, 400)
        outer = QtWidgets.QVBoxLayout(self)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setObjectName("DsEventsScroll")
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        page = QtWidgets.QWidget()
        page.setObjectName("DsEventsPage")
        page.setProperty("rhythm_role", "stack")
        page.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        scroll.viewport().setObjectName("DsEventsViewport")
        scroll.setWidget(page)
        outer.addWidget(scroll, 1)
        layout = QtWidgets.QVBoxLayout(page)
        intro = c.label("Work updates, kept in this Houdini session.", role="body", scale=scale)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        coverage = c.label("SYNAPSE renders and batch reports appear here. Watch a supported render or cache output, or a TOP network, for other work.", role="caption", scale=scale)
        coverage.setWordWrap(True)
        layout.addWidget(coverage)
        toggles = _paired_layout()
        self.quiet = QtWidgets.QCheckBox("Quiet")
        self.quiet.setToolTip("Keep recording events without new alerts.")
        self.desktop = QtWidgets.QCheckBox("Desktop alerts")
        self.desktop.setEnabled(controller.desktop_available)
        self.desktop.setToolTip("Only a generic message is sent to your operating system. It may remain in OS notification history.")
        toggles.addRow(self.quiet, self.desktop)
        layout.addLayout(toggles)
        if not controller.desktop_available:
            note = c.label("Desktop alerts are unavailable on this system. Events still work here.", role="caption", scale=scale)
            note.setWordWrap(True)
            layout.addWidget(note)
        options = _paired_layout()
        self.completions = QtWidgets.QCheckBox("Completion alerts")
        self.connections = QtWidgets.QCheckBox("Connection alerts")
        options.addRow(self.completions, self.connections)
        layout.addLayout(options)
        self.filter = QtWidgets.QComboBox()
        self.filter.setObjectName("DsConnectionSelect")
        self.filter.addItem("All events", "all")
        self.filter.addItem("Needs attention", "attention")
        layout.addWidget(self.filter)
        self.list = QtWidgets.QListWidget()
        self.list.setWordWrap(True)
        self.list.setTextElideMode(QtCore.Qt.ElideRight)
        self.list.setMinimumHeight(round(125 * scale))
        self.list.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list.setAccessibleName("Work and connection events")
        layout.addWidget(self.list, 3)
        self.detail = QtWidgets.QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.detail.setAccessibleName("Selected event details")
        self.detail.setMaximumHeight(round(150 * scale))
        layout.addWidget(self.detail, 1)
        action_row = _paired_layout()
        self.inspect = c.Button("Inspect node", variant="secondary")
        self.model_setup = c.Button("Model setup", variant="secondary")
        self.copy = c.Button("Copy details", variant="ghost")
        action_row.addRow(self.inspect, self.model_setup)
        action_row.addRow(self.copy)
        layout.addLayout(action_row)
        watch_row = _paired_layout()
        self.watch = c.Button("Watch selected", variant="secondary")
        self.stop_watch = c.Button("Stop watching", variant="ghost")
        watch_row.addRow(self.watch, self.stop_watch)
        layout.addLayout(watch_row)
        self.status = c.label("", role="caption", scale=scale)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        footer = _paired_layout()
        self.mark = c.Button("Mark all read", variant="ghost")
        self.clear = c.Button("Clear finished", variant="ghost")
        self.dismiss = c.Button("Close", variant="secondary")
        footer.addRow(self.mark, self.clear)
        footer.addRow(self.dismiss)
        outer.addLayout(footer)
        for widget, key in ((self.quiet, "quiet"), (self.desktop, "desktop"),
                            (self.completions, "completions"), (self.connections, "connections")):
            widget.toggled.connect(lambda checked, key=key: self._policy_changed(key, checked))
        self.filter.currentIndexChanged.connect(lambda *_: self.refresh())
        self.list.currentItemChanged.connect(lambda *_: self._selection())
        self.watch.clicked.connect(self._watch)
        self.stop_watch.clicked.connect(self._stop_watch)
        self.inspect.clicked.connect(self._inspect)
        self.model_setup.clicked.connect(self._models)
        self.copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.detail.toPlainText()))
        self.mark.clicked.connect(self._mark)
        self.clear.clicked.connect(self._clear)
        self.dismiss.clicked.connect(self.close)
        controller.changed.connect(self.refresh)
        self.ensurePolished()
        rhythm.apply(page)
        self.refresh()
        screen = self.screen()
        if screen is not None:
            available = screen.availableGeometry()
            self.resize(min(self.width(), available.width()), min(self.height(), available.height()))

    def refresh(self, snapshot=None):
        snapshot = snapshot or self.controller.journal.snapshot()
        selected = self.list.currentItem()
        selected_id = selected.data(QtCore.Qt.UserRole) if selected else None
        scroll = self.list.verticalScrollBar().value()
        self._entries = {entry["id"]: entry for entry in snapshot["entries"]}
        self.list.blockSignals(True)
        self.list.clear()
        for entry in reversed(snapshot["entries"]):
            if self.filter.currentData() == "attention" and entry["state"] not in ATTENTION:
                continue
            stamp = datetime.fromtimestamp(entry["updated_at"]).strftime("%H:%M")
            row = QtWidgets.QListWidgetItem(("New · " if entry["unread"] else "") +
                    STATE_LABELS.get(entry["state"], "Unknown") + " · " + entry["title"] +
                    "\n" + stamp + (" · " + entry["node"] if entry.get("node") else ""))
            row.setData(QtCore.Qt.UserRole, entry["id"])
            row.setToolTip(entry["detail"])
            self.list.addItem(row)
            if entry["id"] == selected_id:
                self.list.setCurrentItem(row)
        self.list.blockSignals(False)
        if not self.list.currentItem() and self.list.count():
            self.list.setCurrentRow(0)
        self.list.verticalScrollBar().setValue(scroll)
        for widget, key in ((self.quiet, "quiet"), (self.desktop, "desktop"),
                            (self.completions, "completions"), (self.connections, "connections")):
            widget.blockSignals(True)
            widget.setChecked(self.controller.journal.get_policy()[key])
            widget.blockSignals(False)
        self._selection()
        self.desktop.setEnabled(self.controller.desktop_available)
        self.clear.setEnabled(any(e["state"] != "running" for e in self._entries.values()))
        self.mark.setEnabled(any(e["unread"] for e in self._entries.values()))
        if snapshot["dropped"]:
            self.status.setText("Some earlier events could not be retained (%s). This is a limited session history." % snapshot["dropped"])
        elif not self._entries:
            self.status.setText("No events yet. Ordinary background progress stays quiet.")
        elif self.status.text() == "No events yet. Ordinary background progress stays quiet.":
            self.status.clear()

    def _selected(self):
        row = self.list.currentItem()
        return self._entries.get(row.data(QtCore.Qt.UserRole), {}) if row else {}

    def _selection(self):
        entry = self._selected()
        self.detail.setPlainText(_detail(entry))
        self.inspect.setEnabled(bool(entry.get("identity")))
        self.model_setup.setEnabled(entry.get("source") == "model" and callable(self._open_connections))
        self.copy.setEnabled(bool(entry))

    def _policy_changed(self, key, checked):
        saved = self.controller.change_policy({key: checked})
        self.refresh()
        if not saved:
            self.status.setText("Preferences could not be saved. Your previous alert settings are still active.")

    def _watch(self):
        try:
            result = self.controller.watch_selected()
            parts = ["Watching %s · %s" % (item.get("kind", "work"), item["path"])
                     for item in result.get("watched", [])]
            parts += [item.get("path", "Selection") + ": " + item["reason"] for item in result.get("unavailable", [])]
            message = "\n".join(parts) or "Select a supported render/cache output or TOP network first."
        except Exception:
            message = "This selection could not be watched. Select a supported render/cache output or TOP network."
        self.controller.refresh()
        self.status.setText(message)

    def _stop_watch(self):
        self.controller.stop_watching()
        self.status.setText("Stopped watching selected work. Running jobs continue.")

    def _inspect(self):
        if not self.controller.focus_node(self._selected().get("identity")):
            self.status.setText("That node is no longer available in the watched scene. Its recorded details are kept above.")

    def _models(self):
        if callable(self._open_connections):
            self._open_connections()

    def _mark(self):
        self.controller.journal.mark_read()
        self.controller.refresh()

    def _clear(self):
        self.controller.journal.clear_finished()
        self.controller.refresh()
