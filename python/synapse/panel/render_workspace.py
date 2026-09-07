"""Modeless artist Render workspace. The farm service owns all execution.

transport_factory(tool_name, arguments) may inject a worker with succeeded,
failed, finished signals and start(). Workers have no dialog parent and remain
retained until finished, including after the artist closes or deletes the view.
"""
from __future__ import annotations

from copy import deepcopy
import json
import ntpath
import os
import weakref

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover
    from PySide2 import QtCore, QtGui, QtWidgets

from .designsystem import components as c, qss, rhythm, tokens as t
from .render_presenter import (
    ACTIVE_STATES, POLL_STATES, FarmResponseError, RenderWorkspaceModel,
    decode_response, expected_frames, inspection_frame_text, job_presentation,
    perform_farm_call, prepared_summary, verified_output_paths,
)


_ACTIVE_FARM_CALLS = set()


class _RenderButton(c.Button):
    """Keep full action labels readable in a narrow window at large host fonts."""

    def __init__(self, text, variant):
        self._action_text = text
        super().__init__(text, variant=variant)
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def setText(self, text):
        self._action_text = str(text)
        self.setAccessibleName(self._action_text)
        self.fit_label()

    def fit_label(self):
        available = max(1, self.width() - 2 * t.SPACE_MD - 2 * t.STROKE_PX)
        metrics = QtGui.QFontMetrics(self.font())
        lines = [""]
        for word in self._action_text.split():
            candidate = (lines[-1] + " " + word).strip()
            if lines[-1] and metrics.horizontalAdvance(candidate) > available:
                lines.append(word)
            else:
                lines[-1] = candidate
        rendered = "\n".join(lines)
        if rendered != super().text():
            super().setText(rendered)
            self.updateGeometry()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_label()


class FarmToolCall(QtCore.QThread):
    """One model-free request off the GUI thread, with neutral failure wording."""

    succeeded = QtCore.Signal(object)
    failed = QtCore.Signal(str)

    def __init__(self, tool_name, arguments, *, transport=None):
        super().__init__(None)
        self.tool_name = tool_name
        self.arguments = deepcopy(arguments)
        self._transport = transport

    def run(self):
        try:
            transport = self._transport
            if transport is None:
                from .tool_executor import try_mcp_tool_call
                transport = try_mcp_tool_call
            result = perform_farm_call(self.tool_name, self.arguments, transport)
        except Exception as exc:
            self.failed.emit(str(exc)[:2000] or "The render service could not be reached.")
        else:
            self.succeeded.emit(result)


def _retain_until_finished(worker):
    # A parent-owned QThread is unsafe when a panel can be destroyed mid-call.
    worker.setParent(None)
    keepers = _ACTIVE_FARM_CALLS
    keepers.add(worker)

    def release():
        keepers.discard(worker)
        worker.deleteLater()

    worker.finished.connect(release)


def _deliver(reference, envelope):
    dialog = reference()
    if dialog is not None:
        try:
            dialog._received.emit(envelope)
        except RuntimeError:
            pass  # The Qt dialog may already have been destroyed.


def _destination_for_scene(path):
    paths = ntpath if ntpath.splitdrive(path)[0] or "\\" in path else os.path
    return paths.join(paths.dirname(path), "renders", "synapse") if path else ""


class RenderWorkspaceDialog(QtWidgets.QDialog):
    _received = QtCore.Signal(object)
    job_changed = QtCore.Signal(dict)

    def __init__(self, parent=None, *, transport_factory=None):
        super().__init__(parent)
        self.setWindowTitle("SYNAPSE · Render")
        self.setObjectName("DsRoot")
        self.setProperty("panel_popup", "render")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setModal(False)
        self.setMinimumSize(320, 320)
        self._host_scale = max(1.0, float(getattr(parent, "_chrome_scale", 1.0)))
        self._scale = self._host_scale
        self._model = RenderWorkspaceModel()
        self._transport_factory = transport_factory or FarmToolCall
        self._inflight = set()
        self._profiles = {}
        self._capability_note = "Checking available render profiles…"
        self._inspection_note = "Checking the saved scene…"
        self._unsaved = True
        self._inspected_once = False
        self._updating_form = False
        self._opener = QtWidgets.QApplication.focusWidget()
        self._received.connect(self._on_response)
        self._build_ui()
        self._poll_timer = QtCore.QTimer(self)
        self._poll_timer.setInterval(1500)
        self._poll_timer.timeout.connect(self._poll)
        self._apply_scale()
        self.resize(round(520 * min(self._scale, 1.5)), round(680 * min(self._scale, 1.3)))
        self._refresh_state()

    def _label(self, text, role="body"):
        label = c.label(text, role=role, scale=self._scale)
        label.setWordWrap(True)
        label.setTextFormat(QtCore.Qt.PlainText)
        label.setMinimumWidth(0)
        return label

    def _button(self, text, name, callback, variant="secondary"):
        button = _RenderButton(text, variant=variant)
        button.setProperty("render_action", name)
        button.setAccessibleName(text)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.clicked.connect(callback)
        return button

    def _field(self, label, widget, name, layout):
        widget.setObjectName("DsField")
        widget.setProperty("render_field", name)
        widget.setAccessibleName(label)
        widget.setMinimumWidth(0)
        widget.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        caption = self._label(label, "label")
        caption.setBuddy(widget)
        # Spanning rows constrain wrapped captions as well as their fields.
        # QFormLayout's LabelRole can keep an over-wide label at large fonts.
        layout.addRow(caption)
        layout.addRow(widget)
        return widget

    def _form_layout(self):
        layout = QtWidgets.QFormLayout()
        layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapAllRows)
        layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        return layout

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("DsRenderScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._scroll.setMinimumWidth(0)
        self._page = QtWidgets.QWidget()
        self._page.setObjectName("DsRenderPage")
        self._page.setProperty("rhythm_role", "stack")
        self._page.setMinimumWidth(0)
        self._scroll.setWidget(self._page)
        outer.addWidget(self._scroll, 1)
        body = QtWidgets.QVBoxLayout(self._page)
        body.addWidget(self._label("Render", "title"))
        self.scene_label = self._label("Save a scene to prepare a render.")
        self.scene_label.setAccessibleName("Saved scene")
        body.addWidget(self.scene_label)
        form = self._form_layout()
        self.source = self._field("Source", QtWidgets.QComboBox(), "RenderSource", form)
        self.source.setEditable(True)
        self.source.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.source.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.frames = self._field("Frames", QtWidgets.QLineEdit("1"), "RenderFrames", form)
        self.frames.setPlaceholderText("1001-1012 or 1001, 1005, 1010")
        self.destination = self._field("Destination", QtWidgets.QLineEdit(), "RenderDestination", form)
        self.profile = self._field("Render profile", QtWidgets.QComboBox(), "RenderProfile", form)
        self.profile.addItem("Checking available profiles…", "")
        self.profile.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        body.addLayout(form)
        self.profile_note = self._label("")
        body.addWidget(self.profile_note)
        self.recheck = self._button("Check scene again", "RenderInspect", lambda: self._inspect(force=True), "ghost")
        body.addWidget(self.recheck)

        self.settings_toggle = self._button("Settings", "RenderSettingsToggle", self._toggle_settings, "ghost")
        self.settings_toggle.setCheckable(True)
        body.addWidget(self.settings_toggle)
        self.settings_page = QtWidgets.QWidget()
        self.settings_page.setObjectName("DsRenderSettings")
        self.settings_page.setProperty("rhythm_role", "stack")
        settings = self._form_layout()
        self.image_width = self._field("Width", QtWidgets.QSpinBox(), "RenderWidth", settings)
        self.image_height = self._field("Height", QtWidgets.QSpinBox(), "RenderHeight", settings)
        self.samples = self._field("Samples", QtWidgets.QSpinBox(), "RenderSamples", settings)
        for field in (self.image_width, self.image_height):
            field.setRange(1, 16384)
            field.setValue(256)
        self.samples.setRange(1, 4096)
        self.samples.setValue(8)
        self.zoom = self._field("Text size", QtWidgets.QComboBox(), "RenderTextSize", settings)
        for label, factor in (("Standard", 1.0), ("Larger", 1.25), ("Largest", 1.5)):
            self.zoom.addItem(label, factor)
        self.settings_page.setLayout(settings)
        self.settings_page.hide()
        body.addWidget(self.settings_page)
        self.setup_note = self._label(
            "This computer prepares the saved scene and renders through TOPs. HQueue needs a configured "
            "controller, shared storage and worker licenses before it becomes available.", "caption")
        settings.addRow(self.setup_note)

        self.status = self._label("")
        self.status.setObjectName("RenderStatus")
        self.status.setAccessibleName("Render status")
        body.addWidget(self.status)
        self.note = self._label("")
        body.addWidget(self.note)
        self.progress = c.ProgressBar()
        self.progress.setAccessibleName("Verified render frames")
        self.progress.setTextVisible(False)
        body.addWidget(self.progress)
        self.progress_label = self._label("")
        body.addWidget(self.progress_label)
        self.summary = self._label("")
        self.summary.setObjectName("RenderSummary")
        self.summary.setAccessibleName("Exact prepared render")
        body.addWidget(self.summary)
        self.primary = self._button("Prepare render", "RenderPrepare", self._primary_action, "primary")
        body.addWidget(self.primary)
        self.open_output = self._button("Open output", "RenderOpen", self._open_output, "primary")
        body.addWidget(self.open_output)
        actions = QtWidgets.QVBoxLayout()
        self.cancel = self._button("Cancel render", "RenderCancel", self._cancel, "secondary")
        self.new_render = self._button("New render", "RenderNew", self._new_render, "ghost")
        actions.addWidget(self.cancel)
        actions.addWidget(self.new_render)
        body.addLayout(actions)
        recent = self._form_layout()
        self.recent = self._field("Recent renders", QtWidgets.QComboBox(), "RenderRecent", recent)
        self.recent.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.recent.addItem("Choose a saved render…", "")
        body.addLayout(recent)
        self.details_toggle = self._button("Details", "RenderDetailsToggle", self._toggle_details, "ghost")
        self.details_toggle.setCheckable(True)
        body.addWidget(self.details_toggle)
        self.details = QtWidgets.QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self.details.setAccessibleName("Render record details")
        self.details.setMinimumWidth(0)
        self.details.hide()
        body.addWidget(self.details)
        self.copy_details = self._button("Copy details", "RenderCopyDetails", self._copy_details, "ghost")
        self.copy_details.hide()
        body.addWidget(self.copy_details)
        body.addStretch(1)
        footer = QtWidgets.QVBoxLayout()
        self.refresh_button = self._button("Refresh status", "RenderRefresh", self._refresh)
        self.close_button = self._button("Close", "RenderClose", self.close, "ghost")
        footer.addWidget(self.refresh_button)
        footer.addWidget(self.close_button)
        outer.addLayout(footer)

        for field in (self.frames, self.destination):
            field.textChanged.connect(self._form_changed)
        self.source.currentTextChanged.connect(self._form_changed)
        self.profile.currentIndexChanged.connect(self._form_changed)
        for field in (self.image_width, self.image_height, self.samples):
            field.valueChanged.connect(self._form_changed)
        self.zoom.currentIndexChanged.connect(self._zoom_changed)
        self.recent.currentIndexChanged.connect(self._select_recent)
        # Enter in an editable field never activates the preparation button.
        for field in (self.frames, self.destination, self.source.lineEdit()):
            field.returnPressed.connect(self._form_changed)
        rhythm.apply(self._page)

    def _apply_scale(self):
        qss.prepare_render_dialog(self, self._scale)
        for label in self.findChildren(QtWidgets.QLabel):
            c.apply_font_role(label, label.property("role") or "body", self._scale)
        for button in self.findChildren(_RenderButton):
            button.fit_label()
        self.details.setMaximumHeight(t.scaled(t.SIZE_BODY * 12, self._scale))

    def _zoom_changed(self):
        self._scale = self._host_scale * float(self.zoom.currentData() or 1.0)
        self._apply_scale()

    def _toggle_settings(self):
        self.settings_page.setVisible(self.settings_toggle.isChecked())

    def _toggle_details(self):
        visible = self.details_toggle.isChecked()
        self.details.setVisible(visible)
        self.copy_details.setVisible(visible)

    def _form_values(self):
        text = self.source.currentText().strip()
        selected = self.source.currentIndex()
        source = (self.source.currentData() if selected >= 0 and text == self.source.itemText(selected)
                  else text)
        return {"source_node": source or text,
                "frames": self.frames.text().strip(), "output_root": self.destination.text().strip(),
                "profile_id": self.profile.currentData() or "", "width": self.image_width.value(),
                "height": self.image_height.value(), "samples": self.samples.value()}

    def _form_changed(self, *_):
        if self._updating_form:
            return
        self._model.edit(self._form_values())
        self._refresh_state()

    def _write_form(self):
        self._updating_form = True
        try:
            form = self._model.form
            source_index = self.source.findData(form["source_node"])
            if source_index < 0 and form["source_node"]:
                self.source.addItem(form["source_node"], form["source_node"])
                source_index = self.source.count() - 1
            self.source.setCurrentIndex(source_index)
            self.frames.setText(str(form["frames"]))
            self.destination.setText(str(form["output_root"]))
            self.profile.setCurrentIndex(self.profile.findData(form["profile_id"]))
            for field, key in ((self.image_width, "width"), (self.image_height, "height"), (self.samples, "samples")):
                value = form.get(key)
                if isinstance(value, int) and not isinstance(value, bool):
                    field.setValue(value)
        finally:
            self._updating_form = False

    def _call(self, kind, tool, arguments, *, open_after=False):
        if kind in self._inflight:
            return False
        self._inflight.add(kind)
        context = {"kind": kind, "request_id": arguments.get("request_id"), "open_after": open_after,
                   "form_revision": self._model.form_revision}
        reference = weakref.ref(self)
        try:
            worker = self._transport_factory(tool, deepcopy(arguments))
            worker.succeeded.connect(lambda data, ctx=context: _deliver(reference, (ctx, True, data)))
            worker.failed.connect(lambda error, ctx=context: _deliver(reference, (ctx, False, error)))
            _retain_until_finished(worker)
            worker.start()
        except Exception as exc:
            if "worker" in locals() and worker in _ACTIVE_FARM_CALLS:
                try:
                    if not worker.isRunning():
                        _ACTIVE_FARM_CALLS.discard(worker)
                        worker.deleteLater()
                except (AttributeError, RuntimeError):
                    pass
            self._on_response((context, False, str(exc)))
            return False
        return True

    def _inspect(self, *, force=False):
        if force and self._model.pending:
            return
        self._call("inspect", "synapse_farm_inspect", {})

    def _refresh(self):
        self._call("capabilities", "synapse_farm_capabilities", {})
        self._call("jobs", "synapse_farm_jobs", {"limit": 20})
        if self._model.job and not self._model.pending:
            if self._model.job.get("state") in ("prepared", "complete"):
                self._model.observation_note = "Checking the saved render status…"
                self._refresh_state()
            self._call("job", "synapse_farm_job", {"request_id": self._model.job["request_id"]})
        elif not self._model.job:
            self._inspect()

    def _poll(self):
        if self.isVisible() and self._model.job and not self._model.pending:
            presentation = job_presentation(self._model.job, observation_note=self._model.observation_note)
            if presentation["poll"]:
                self._call("job", "synapse_farm_job", {"request_id": self._model.job["request_id"]})

    def refresh(self):
        """Read capabilities, history and the current source/job; never execute."""
        self._refresh()

    @QtCore.Slot(object)
    def _on_response(self, envelope):
        context, succeeded, response = envelope
        kind = context["kind"]
        self._inflight.discard(kind)
        if kind == "job" and self._model.pending:
            # A read begun before Prepare/Submit/Cancel cannot acknowledge it.
            # Wait for that exact mutation reply (or its uncertainty record).
            return
        if not succeeded:
            self._handle_failure(kind, response, context)
            return
        try:
            data = decode_response(response)
            if kind == "inspect":
                self._apply_inspection(data, context)
            elif kind == "capabilities":
                self._apply_capabilities(data)
            elif kind == "jobs":
                jobs = data.get("jobs")
                if not isinstance(jobs, list):
                    raise FarmResponseError("The service did not return readable render history.")
                for job in jobs:
                    if isinstance(job, dict) and isinstance(job.get("request_id"), str):
                        previous = self._model.jobs.get(job["request_id"], {})
                        if (not isinstance(previous.get("revision"), int) or
                                isinstance(job.get("revision"), int) and job["revision"] >= previous["revision"]):
                            self._model.jobs[job["request_id"]] = deepcopy(job)
                self._update_recent()
            else:
                accepted = self._model.receive_job(data, request_id=context.get("request_id"))
                if accepted:
                    self._write_form()
                    self.job_changed.emit(deepcopy(data))
                    if context.get("open_after"):
                        self._open_verified_record(data)
                self._update_recent()
        except Exception as exc:
            self._handle_failure(kind, str(exc), context)
            return
        self._refresh_state()

    def _handle_failure(self, kind, error, context):
        message = str(error or "The render service could not be reached.")[:2000]
        if kind == "capabilities":
            self._profiles = {}
            self._capability_note = message
        elif kind == "inspect":
            self._inspection_note = message
            if not self._inspected_once:
                self._unsaved = True
        elif kind == "jobs":
            self.recent.setToolTip("Saved history is unavailable: " + message)
        elif not context.get("request_id") or not self._model.job or context["request_id"] == self._model.job.get("request_id"):
            self._model.transport_failed(kind, message)
        self._update_recent()
        self._refresh_state()

    def _apply_inspection(self, data, context):
        if data.get("status") not in ("ready", "needs_attention") or "source_hip" not in data:
            raise FarmResponseError("The service did not return a readable scene inspection.")
        self._inspection_note = str(data.get("note") or "")
        self._unsaved = data.get("unsaved") is not False
        nodes = data.get("source_nodes") or []
        if not isinstance(nodes, list):
            raise FarmResponseError("The service did not return readable render sources.")
        selected_source = self._model.form["source_node"]
        self._updating_form = True
        try:
            self.source.clear()
            for node in nodes:
                if isinstance(node, dict) and isinstance(node.get("path"), str):
                    self.source.addItem(str(node.get("label") or node["path"]), node["path"])
        finally:
            self._updating_form = False
        if not self._model.job and context["form_revision"] == self._model.form_revision:
            previous_hip = self._model.form["source_hip"]
            hip = str(data.get("source_hip") or "")
            values = {"source_hip": hip, "source_node": str(data.get("source_node") or "")}
            if not self._inspected_once:
                values["frames"] = inspection_frame_text(data.get("frames")) or "1"
            if not self._model.form["output_root"] or self._model.form["output_root"] == _destination_for_scene(previous_hip):
                values["output_root"] = str(data.get("output_root") or _destination_for_scene(hip))
            self._model.edit(values)
        elif selected_source and self.source.findData(selected_source) < 0:
            self.source.addItem(selected_source, selected_source)
        self._inspected_once = True
        self._write_form()

    def _apply_capabilities(self, data):
        profiles = data.get("profiles")
        if not isinstance(profiles, list):
            raise FarmResponseError("The service did not return readable render profiles.")
        self._profiles = {profile["id"]: deepcopy(profile) for profile in profiles
                          if isinstance(profile, dict) and isinstance(profile.get("id"), str)}
        self._capability_note = ""
        if "hqueue" not in self._profiles:
            self._profiles["hqueue"] = {"id": "hqueue", "label": "HQueue", "available": False,
                                        "reason": "HQueue is not configured by this service."}
        selected = self._model.form["profile_id"]
        self._updating_form = True
        try:
            self.profile.clear()
            for key in sorted(self._profiles, key=lambda value: (value != "local", value)):
                profile = self._profiles[key]
                label = "This computer" if key == "local" else str(profile.get("label") or key)
                if profile.get("available") is not True:
                    label += " · unavailable"
                self.profile.addItem(label, key)
            self.profile.setCurrentIndex(self.profile.findData(selected))
        finally:
            self._updating_form = False

    def _primary_action(self):
        try:
            profile = self._profiles.get(self._model.form["profile_id"], {})
            if profile.get("available") is not True:
                raise ValueError(str(profile.get("reason") or "An available render profile is required."))
            if self._model.can_submit:
                payload = self._model.begin_submit()
                self._call("submit", "synapse_farm_submit", payload)
            else:
                if self._unsaved:
                    raise ValueError("A saved scene and an available render profile are required.")
                payload = self._model.begin_prepare()
                self._call("prepare", "synapse_farm_prepare", payload)
        except (ValueError, FarmResponseError) as exc:
            self._model.observation_note = str(exc)
        self._refresh_state()

    def _cancel(self):
        try:
            self._call("cancel", "synapse_farm_cancel", self._model.begin_cancel())
        except ValueError as exc:
            self._model.observation_note = str(exc)
        self._refresh_state()

    def _new_render(self):
        try:
            self._model.new_render()
        except ValueError:
            return
        self._write_form()
        self._update_recent()
        self._inspect(force=True)
        self._refresh_state()

    def _update_recent(self):
        selected = self._model.job.get("request_id") if self._model.job else ""
        self.recent.blockSignals(True)
        try:
            self.recent.clear()
            self.recent.addItem("Choose a saved render…", "")
            records = list(self._model.jobs.values())
            records.sort(key=lambda job: str(job.get("updated_at") or ""), reverse=True)
            for job in records[:20]:
                plan = job.get("plan") or {}
                if not isinstance(plan, dict):
                    plan = {}
                name = ntpath.basename(str(plan.get("source_hip") or "Render"))
                self.recent.addItem("%s · %s" % (name, str(job.get("state") or "unknown").replace("_", " ")), job["request_id"])
            self.recent.setCurrentIndex(max(0, self.recent.findData(selected)))
        finally:
            self.recent.blockSignals(False)

    def _select_recent(self):
        request_id = self.recent.currentData()
        if not request_id or self._model.pending:
            return
        try:
            self._model.select_job(request_id)
        except (ValueError, KeyError):
            return
        self._model.observation_note = "Checking the saved render status…"
        self._write_form()
        self._refresh_state()
        self._call("job", "synapse_farm_job", {"request_id": request_id})

    def _refresh_state(self):
        model = self._model
        job = model.job
        presentation = job_presentation(job, observation_note=model.observation_note)
        state = job.get("state") if job else None
        profile = self._profiles.get(model.form["profile_id"], {})
        limits = profile.get("limits") or {}
        limit_keys = ("max_frames", "max_width", "max_height", "max_samples")
        setup = "HQueue needs a configured controller, shared storage and worker licenses before it becomes available."
        if isinstance(limits, dict) and all(type(limits.get(key)) is int and limits[key] > 0 for key in limit_keys):
            setup = ("This profile allows up to %s frames, %s × %s pixels and %s samples. " %
                     tuple(limits[key] for key in limit_keys)) + setup
        elif profile.get("reason"):
            setup = str(profile["reason"]) + "\n" + setup
        self.setup_note.setText(setup)
        self.scene_label.setText("Saved scene: " + str(model.form["source_hip"]) if model.form["source_hip"] else "Save a scene to prepare a render.")
        self.profile_note.setText(str(profile.get("reason") or self._capability_note or "This profile is unavailable.")
                                  if profile.get("available") is not True else "")
        self.status.setText(presentation["title"])
        self.note.setText(presentation["note"] or (self._inspection_note if not job else ""))
        can_prepare = not model.pending and (not job or state == "prepared" and not model.can_submit and not model.observation_note)
        can_prepare = (can_prepare and not self._unsaved and profile.get("available") is True and
                       all(str(model.form.get(key) or "").strip() for key in ("source_hip", "source_node", "frames", "output_root")))
        if model.can_submit:
            total = len(expected_frames(job))
            self.primary.setText("Render %d frame%s" % (total, "" if total == 1 else "s"))
        else:
            self.primary.setText("Prepare render")
            if job and state == "prepared" and not model.pending and not model.observation_note:
                self.status.setText("Settings changed. Prepare this render again.")
        self.primary.setEnabled(bool(model.can_submit and profile.get("available") is True or can_prepare))
        self.primary.setVisible(state != "complete")
        self.open_output.setVisible(state == "complete")
        self.open_output.setEnabled(presentation["can_open"] and not model.pending)
        self.cancel.setVisible(bool(job) and state not in ("complete", "failed", "cancelled"))
        self.cancel.setEnabled(presentation["can_cancel"] and not model.pending)
        self.new_render.setVisible(bool(job))
        self.new_render.setEnabled(not model.pending)
        self.recent.setEnabled(not model.pending)
        self.refresh_button.setEnabled(not model.pending)
        self.recheck.setEnabled(not model.pending and not job)
        locked = bool(model.pending or job and state != "prepared")
        for field in (self.source, self.frames, self.destination, self.profile, self.image_width, self.image_height, self.samples):
            field.setEnabled(not locked)
        count, total = presentation["verified"], presentation["total"]
        show_progress = bool(job) and state != "prepared"
        self.progress.setVisible(show_progress)
        self.progress_label.setVisible(show_progress)
        if count is not None and total:
            self.progress.setRange(0, total)
            self.progress.setValue(count)
            self.progress_label.setText("%d of %d frames verified" % (count, total))
            self.progress.setAccessibleDescription(self.progress_label.text())
        else:
            self.progress.setRange(0, 1 if t.reduced_motion() or state not in ACTIVE_STATES else 0)
            self.progress.setValue(0)
            self.progress_label.setText("Verified frame count is not available yet.")
        self.summary.setText(prepared_summary(job) if job and expected_frames(job) else "")
        self.summary.setVisible(bool(job) and bool(expected_frames(job)))
        self.details.setPlainText(json.dumps(job or {"form": model.form, "profiles": self._profiles}, indent=2, ensure_ascii=False, sort_keys=True))

    def _open_output(self):
        if verified_output_paths(self._model.job):
            self._call("job", "synapse_farm_job", {"request_id": self._model.job["request_id"]}, open_after=True)

    def _open_verified_record(self, job):
        paths = verified_output_paths(job)
        if not paths:
            self._model.observation_note = "Verified output is unavailable for this record."
            return
        if not QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(paths[0])):
            self._model.observation_note = "No application accepted this image. Copy its verified path from Details."

    def _copy_details(self):
        QtWidgets.QApplication.clipboard().setText(self.details.toPlainText())

    def showEvent(self, event):
        super().showEvent(event)
        self._poll_timer.start()
        self._refresh()

    def hideEvent(self, event):
        self._poll_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self._poll_timer.stop()
        # Keep the model and outstanding requests. Closing never cancels work.
        super().closeEvent(event)
        try:
            if self._opener is not None:
                self._opener.setFocus()
        except RuntimeError:
            pass
