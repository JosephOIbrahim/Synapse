"""A reusable read-only network inspector and explicit prompt preparation.

The view owns no Houdini objects and never submits a generation request. Scene
facts stay local to the inspection and to the prompt the artist chooses to send.
"""
from __future__ import annotations

import threading

try:
    from PySide6 import QtCore, QtWidgets
except ImportError:  # pragma: no cover - supported older host
    from PySide2 import QtCore, QtWidgets

from synapse.jev.selection_actions import ACTIONS
from synapse.jev.selection_suggestions import SuggestionService
from .designsystem import components as c, qss, tokens as t
from .selection_inspection import InspectionController, inspection_request


def _settings():
    from .settings import load_settings
    return load_settings()


def _scope():
    from synapse.model_access import capture_scope
    return capture_scope()


class _InspectorButton(c.Button):
    """Wrap a native button label when large host text meets a narrow pane."""
    def __init__(self, text, variant="secondary"):
        self._full_text = text
        super().__init__(text, variant=variant)
        self.setMinimumWidth(0)
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)

    def setText(self, text):
        self._full_text = str(text)
        self.setAccessibleName(self._full_text)
        self._fit_text()

    def _fit_text(self):
        available = max(1, self.width() - 2 * t.SPACE_MD - 2 * t.STROKE_PX)
        metrics, lines = self.fontMetrics(), [""]
        for word in self._full_text.split():
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
        self._fit_text()

    def sizeHint(self):
        hint = super().sizeHint()
        # The parent decides whether the original label fits. Measuring the
        # already-wrapped text would keep a short row wrapped after widening.
        hint.setWidth(self.fontMetrics().horizontalAdvance(self._full_text)
                      + 2 * t.SPACE_MD + 2 * t.STROKE_PX)
        return hint


class SelectionInspectorDialog(QtWidgets.QDialog):
    draft_ready = QtCore.Signal(str)

    def __init__(self, parent=None, *, controller=None, service=None,
                 settings_reader=_settings, scope_factory=_scope, draft_reader=None):
        super().__init__(parent)
        self.setObjectName("DsRoot")
        self.setProperty("panel_popup", "selection_inspector")
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setWindowTitle("SYNAPSE · Selected network")
        self.setModal(False)
        self.setMinimumSize(320, 300)
        self._scale = max(1.0, float(getattr(parent, "_chrome_scale", 1.0)))
        self._controller = controller if controller is not None else InspectionController()
        self._service = service if service is not None else SuggestionService()
        self._settings_reader, self._scope_factory = settings_reader, scope_factory
        self._draft_reader = draft_reader or (lambda: "")
        self._rank_cancel = threading.Event()
        self._rank_generation, self._seen_revision = 0, -1
        self._rank_scope, self._rank_input = None, None
        self._rank_requested, self._last_rank = False, None
        self._render_key = self._rendered_snapshot = None
        self._enabled_preference = self._suggestions_enabled()
        self._build_ui()
        qss.prepare_selection_inspector(self, self._scale)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._poll)
        # QObject destruction need not deliver closeEvent (e.g. host pane tear-down).
        controller_ref, service_ref, cancel_ref = self._controller, self._service, self._rank_cancel
        self.destroyed.connect(lambda *_: (cancel_ref.set(), controller_ref.close(), service_ref.cancel()))
        screen = self.screen() or QtWidgets.QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else QtCore.QRect(0, 0, 1000, 800)
        self.resize(min(round(650 * min(self._scale, 1.4)), available.width() - 32),
                    min(round(820 * min(self._scale, 1.2)), available.height() - 32))

    def _label(self, text, role="body"):
        label = c.label(text, role=role, scale=self._scale)
        label.setTextFormat(QtCore.Qt.PlainText)
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        return label

    def _button(self, text, callback, variant="secondary"):
        button = _InspectorButton(text, variant=variant)
        c.apply_font_role(button, "body", self._scale)
        button.setAccessibleName(text)
        button.setAutoDefault(False)
        button.setDefault(False)
        button.clicked.connect(callback)
        return button

    def _tree(self, headers, name, height):
        tree = QtWidgets.QTreeWidget()
        tree.setObjectName("DsSelectionTable")
        tree.setAccessibleName(name)
        tree.setColumnCount(len(headers))
        tree.setHeaderLabels(headers)
        tree.setRootIsDecorated(False)
        tree.setAlternatingRowColors(False)
        tree.setWordWrap(False)
        tree.setTextElideMode(QtCore.Qt.ElideNone)
        tree.setMinimumWidth(0)
        tree.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        tree.setFixedHeight(t.scaled(height, self._scale))
        tree.setHorizontalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        tree.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        tree.header().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        tree.header().setStretchLastSection(False)
        c.apply_font_role(tree, "body", self._scale)
        c.apply_font_role(tree.header(), "label", self._scale)
        return tree

    def _build_ui(self):
        outer = QtWidgets.QVBoxLayout(self)
        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("DsSelectionScroll")
        self._scroll.viewport().setObjectName("DsSelectionViewport")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._page = QtWidgets.QWidget()
        self._page.setObjectName("DsSelectionPage")
        self._page.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        layout = QtWidgets.QVBoxLayout(self._page)
        self._title = self._label("Selected network", "display")
        layout.addWidget(self._title)
        layout.addWidget(self._label("Read nodes and exact connections before choosing a next step."))
        self._refresh_btn = self._button("Refresh", self._refresh)
        self._pin_btn = self._button("Pin inspection", self._toggle_pin)
        self._refresh_row = c.EdgeRow(self._refresh_btn, self._pin_btn, scale=self._scale)
        layout.addWidget(self._refresh_row)
        self._status = self._label("Ready to inspect the current selection.", "label")
        self._status.setAccessibleName("Inspection status")
        layout.addWidget(self._status)
        self._summary = self._label("No snapshot yet.")
        layout.addWidget(self._summary)
        self._scope_note = self._label(
            "Pinning keeps these nodes in this inspector. Review edit targets before applying changes.", "caption")
        layout.addWidget(self._scope_note)
        layout.addWidget(self._label("Captured nodes", "label"))
        self._nodes = self._tree(["Node", "Type / context"], "Captured nodes", 115)
        layout.addWidget(self._nodes)
        layout.addWidget(self._label("Observed wires · ports are zero-based", "label"))
        self._wires = self._tree(["Boundary", "From", "Out", "To", "In"], "Observed wires with exact ports", 195)
        # Keep port indices visible. Long paths elide in the flexible columns;
        # their complete values and physical wire-item details stay in tooltips.
        self._wires.setTextElideMode(QtCore.Qt.ElideMiddle)
        for column in (1, 3):
            self._wires.header().setSectionResizeMode(column, QtWidgets.QHeaderView.Stretch)
        layout.addWidget(self._wires)
        self._evidence_note = self._label("Unknown ports are shown as unknown. Parameters, geometry and USD stages are not read.", "caption")
        layout.addWidget(self._evidence_note)

        layout.addWidget(c.divider())
        layout.addWidget(self._label("Prepare a next step", "display"))
        layout.addWidget(self._label("Choose an action to append an editable prompt. Nothing is sent or changed."))
        self._intent = QtWidgets.QPlainTextEdit()
        self._intent.setObjectName("DsSelectionIntent")
        self._intent.setAccessibleName("Intent for action suggestions")
        self._intent.setPlaceholderText("Optional: what are you trying to understand or improve?")
        self._intent.setFixedHeight(t.scaled(78, self._scale))
        self._intent.setMinimumWidth(0)
        self._intent.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self._intent.textChanged.connect(self._invalidate_rank)
        layout.addWidget(self._intent)
        self._suggest_btn = self._button("Suggest actions", self._suggest)
        layout.addWidget(self._suggest_btn)
        self._rank_status = self._label("Default order. JEV suggestions are optional in Connect models.", "caption")
        layout.addWidget(self._rank_status)
        self._action_layout = QtWidgets.QVBoxLayout()
        self._action_buttons = {}
        for action in ACTIONS:
            button = self._button(action.label, lambda checked=False, aid=action.id: self._prepare(aid))
            button.setToolTip(action.description)
            button.setProperty("selection_action", action.id)
            button.setEnabled(False)
            self._action_buttons[action.id] = button
            self._action_layout.addWidget(button)
        layout.addLayout(self._action_layout)
        self._prepared_status = self._label("", "caption")
        layout.addWidget(self._prepared_status)

        layout.addWidget(c.divider())
        layout.addWidget(self._label("Preview a wire insertion", "display"))
        layout.addWidget(self._label("Select a wire above and an already captured intermediate node. This creates a read-only proposal from this scan."))
        self._via = QtWidgets.QComboBox()
        self._via.setAccessibleName("Intermediate node")
        self._via.setMinimumWidth(0)
        self._via.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Preferred)
        self._via.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._via.setMinimumContentsLength(1)
        layout.addWidget(self._label("Intermediate node", "label"))
        layout.addWidget(self._via)
        self._input_port, self._output_port = QtWidgets.QSpinBox(), QtWidgets.QSpinBox()
        for name, field in (("Intermediate input index", self._input_port), ("Intermediate output index", self._output_port)):
            field.setRange(0, 10000)
            field.setAccessibleName(name)
            layout.addWidget(self._label(name, "label"))
            layout.addWidget(field)
        self._preview_btn = self._button("Preview insertion", self._preview)
        layout.addWidget(self._preview_btn)
        self._preview_text = QtWidgets.QPlainTextEdit()
        self._preview_text.setObjectName("DsSelectionProposal")
        self._preview_text.setAccessibleName("Read-only insertion proposal")
        self._preview_text.setReadOnly(True)
        self._preview_text.setMinimumWidth(0)
        self._preview_text.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Fixed)
        self._preview_text.setFixedHeight(t.scaled(180, self._scale))
        self._preview_text.setPlaceholderText("No proposal. No connections have been changed.")
        layout.addWidget(self._preview_text)
        self._scroll.setWidget(self._page)
        outer.addWidget(self._scroll, 1)
        self._close_btn = self._button("Close", self.close, "ghost")
        outer.addWidget(self._close_btn, 0, QtCore.Qt.AlignRight)

    def open_inspection(self):
        if not self.isVisible():
            self._controller.open()
            self._timer.start()
            self._poll()
        self.show()
        self.raise_()
        self.activateWindow()

    def shutdown(self):
        self._timer.stop()
        self._invalidate_rank()
        self._controller.close()

    def closeEvent(self, event):
        self.shutdown()
        super().closeEvent(event)

    def reject(self):
        self.shutdown()  # Escape has the same cancellation semantics as closing.
        super().reject()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_refresh_row"):
            self._refresh_row.fit_width(max(0, self._scroll.viewport().width() - t.scaled(t.SPACE_XS, self._scale)))

    def _refresh(self):
        self._prepared_status.clear()
        self._controller.refresh()
        self._poll()

    def _toggle_pin(self):
        try:
            if self._controller.view()["pinned"]:
                self._controller.unpin()
            else:
                self._controller.pin()
        except ValueError as exc:
            self._prepared_status.setText(str(exc))
        self._poll()

    def _suggestions_enabled(self):
        try:
            return self._settings_reader().get("jev_suggestions_enabled") is True
        except Exception:
            return False

    def _invalidate_rank(self):
        self._rank_cancel.set()
        self._service.cancel()
        self._rank_generation += 1
        self._rank_scope, self._rank_input = None, None
        self._rank_requested, self._last_rank = False, None
        if hasattr(self, "_action_buttons"):
            self._show_rank(None)

    def _suggest(self):
        # Read Qt text once on its owner thread. The service receives no snapshot,
        # paths, categories, nodes, ports or prepared prompt context.
        text = self._intent.toPlainText().strip() or self._draft_reader().strip()
        enabled = self._suggestions_enabled()
        state = self._controller.view()
        if state["closed"]:
            return
        if text != self._rank_input or self._rank_scope is None:
            self._invalidate_rank()
            self._rank_scope = self._scope_factory()
            self._rank_input = text
            self._rank_cancel = threading.Event()
        self._rank_generation += 1
        generation, revision = self._rank_generation, state["revision"]
        cancel, controller, reader = self._rank_cancel, self._controller, self._settings_reader
        def aborted():
            if cancel.is_set() or not controller.is_current(revision):
                return True
            try:
                return reader().get("jev_suggestions_enabled") is not True
            except Exception:
                return True
        result = self._service.request(text, generation_key=generation, scope=self._rank_scope,
                                       enabled=enabled, should_abort=aborted)
        self._rank_requested = True
        self._show_rank(result)

    def _show_rank(self, result):
        if result == self._last_rank and result is not None:
            return
        self._last_rank = result
        known = list(self._action_buttons)
        ordered = [row.get("id") for row in (result or {}).get("ordered_actions", [])]
        if len(ordered) != len(known) or set(ordered) != set(known):
            ordered = known
        for index, action_id in enumerate(ordered):
            self._action_layout.insertWidget(index, self._action_buttons[action_id])
        status, reason = (result or {}).get("status"), (result or {}).get("reason")
        if (result or {}).get("source") == "jev" and status == "ranked":
            message = "JEV suggested order · ranked for relevance, not correctness."
        elif status == "pending":
            message = "JEV is ranking these actions. The default actions remain available."
        elif reason == "private_or_scene_request":
            message = "Default order. This text contains a path; scene and file paths are not sent to JEV."
        elif status in ("unavailable", "discarded"):
            message = "Default order. JEV is unavailable or its permission changed."
        else:
            message = "Default order. JEV suggestions are optional in Connect models."
        self._rank_status.setText(message)

    def _prepare(self, action_id):
        # Recheck authorization before consuming a cached suggested order. The
        # clicked action is still one of the same local, always-available five.
        if self._rank_requested:
            self._show_rank(self._service.snapshot(self._rank_generation))
        try:
            self._controller.prepare(action_id)
            self._prepared_status.setText("Checking the captured target before preparing the prompt…")
        except (ValueError, KeyError) as exc:
            self._prepared_status.setText(str(exc))
        self._poll()

    def _poll(self):
        state = self._controller.view()
        enabled = self._suggestions_enabled()
        if state["revision"] != self._seen_revision or enabled != self._enabled_preference:
            self._seen_revision, self._enabled_preference = state["revision"], enabled
            self._invalidate_rank()
        if self._rank_requested:
            effective_text = self._intent.toPlainText().strip() or self._draft_reader().strip()
            if effective_text != self._rank_input:
                self._invalidate_rank()
        if self._rank_requested:
            self._show_rank(self._service.snapshot(self._rank_generation))
        render_key = (state["revision"], state["status"], state["pinned"], state["error"])
        if render_key != self._render_key:
            self._render_key = render_key
            self._render_state(state)
        prompt = self._controller.take_prepared()
        if prompt is not None and not state["closed"]:
            self.draft_ready.emit(prompt)
            self._prepared_status.setText("Prompt appended to the composer. Review it, then send when ready.")

    def _render_state(self, state):
        snapshot = state["snapshot"]
        target = "Pinned inspection" if state["pinned"] else "Current selection capture"
        status = state["status"]
        if status in ("loading", "validating"):
            self._status.setText(target + " · checking…")
        elif status in ("stale", "unavailable"):
            self._status.setText(("Capture is stale. " if status == "stale" else "Inspection unavailable. ") + state["error"])
        else:
            self._status.setText(target)
        self._pin_btn.setText("Unpin" if state["pinned"] else "Pin inspection")
        valid = False
        try:
            inspection_request(snapshot)
            valid = status == "ready"
        except ValueError:
            pass
        self._pin_btn.setEnabled(state["pinned"] or valid)
        self._preview_btn.setEnabled(valid)
        for button in self._action_buttons.values():
            button.setEnabled(valid)
        if snapshot is not None and snapshot != self._rendered_snapshot:
            self._rendered_snapshot = snapshot
            self._render_snapshot(snapshot)
        if status != "ready":
            self._preview_text.clear()
        self._refresh_row.fit_width(self._scroll.viewport().width() - t.scaled(t.SPACE_XS, self._scale))

    def _render_snapshot(self, snapshot):
        wires = snapshot.get("wires", {})
        counts = [len(wires.get(group, [])) for group in ("internal", "entering", "leaving")]
        selected, observed = snapshot.get("selected_count", "unknown"), snapshot.get("observed_count", "unknown")
        self._summary.setText(f"{observed} of {selected} selected nodes observed · "
                              f"{counts[0]} internal / {counts[1]} entering / {counts[2]} leaving wires")
        if selected == 0:
            self._summary.setText("No nodes selected. Select nodes in Houdini, then Refresh.")
        warnings = snapshot.get("warnings", [])
        complete = snapshot.get("complete") is True
        note = "Complete bounded topology scan." if complete else "Incomplete scan. Pinning and prompt preparation are unavailable."
        if snapshot.get("truncated"):
            note += f" {snapshot.get('omitted_count', 'Unknown')} nodes omitted; wire evidence may also be truncated."
        if warnings:
            note += " " + "; ".join(str(value) for value in warnings)
        self._evidence_note.setText(note + " Parameters, geometry and USD stages were not read.")
        self._nodes.clear(); self._wires.clear(); self._via.clear(); self._preview_text.clear()
        for node in snapshot.get("nodes", []):
            path = str(node.get("path", "unknown"))
            row = QtWidgets.QTreeWidgetItem([path, str(node.get("type", "unknown")) + " / " + str(node.get("category", "unknown"))])
            for column in range(2): row.setToolTip(column, row.text(column))
            self._nodes.addTopLevelItem(row)
            self._via.addItem(path, path)
        for group in ("internal", "entering", "leaving"):
            for edge in wires.get(group, []):
                def port(index):
                    return str(index) if type(index) is int else "unknown"
                row = QtWidgets.QTreeWidgetItem([group.capitalize(), str(edge.get("source") or "unknown"),
                    port(edge.get("source_output")), str(edge.get("target") or "unknown"), port(edge.get("target_input"))])
                row.setData(0, QtCore.Qt.UserRole, edge)
                for column in range(5): row.setToolTip(column, row.text(column))
                if edge.get("source_item") and edge["source_item"] != edge.get("source"):
                    row.setToolTip(1, row.text(1) + "\nVia wire item: " + str(edge["source_item"])
                                   + " [out " + port(edge.get("source_item_output")) + "]")
                self._wires.addTopLevelItem(row)

    def _preview(self):
        from .wire_preview import build_insertion_preview, format_insertion_preview
        state = self._controller.view()
        if state["status"] != "ready":
            self._preview_text.setPlainText("Refresh the inspection before preparing a proposal.")
            return
        item = self._wires.currentItem()
        wire = item.data(0, QtCore.Qt.UserRole) if item is not None else None
        try:
            proposal = build_insertion_preview(state["snapshot"], wire, self._via.currentData(),
                input_index=self._input_port.value(), output_index=self._output_port.value())
            text = format_insertion_preview(proposal)
        except ValueError as exc:
            text = str(exc)
        self._preview_text.setPlainText(text)
