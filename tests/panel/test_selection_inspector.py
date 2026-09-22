"""Real offscreen Qt, injected reads/ranking; no Houdini or model calls."""
from copy import deepcopy
import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui
if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Real Qt is required", allow_module_level=True)

from synapse.jev.selection_actions import ACTIONS
from synapse.panel.selection_inspection import InspectionController
from synapse.panel.selection_inspector import SelectionInspectorDialog
from .test_panel_editorial import make_panel

_APP = None


def report():
    paths = ["/stage/source", "/stage/destination", "/stage/intermediate"]
    return {"schema": "synapse-selection-v1", "selection_source": "live",
            "selected_count": 3, "observed_count": 3, "omitted_count": 0,
            "complete": True, "can_pin": True, "truncated": False,
            "identities": [{"path": path, "session_id": index + 40} for index, path in enumerate(paths)],
            "scene": {"session_token": "test-scene", "hip_path": "/private/artist.hip", "houdini_version": "22.0.400"},
            "topology_hash": "a" * 64,
            "nodes": [{"path": path, "session_id": index + 40, "parent": "/stage",
                       "type": "null", "category": "Lop", "input_capacity": 4, "output_capacity": 4}
                      for index, path in enumerate(paths)],
            "wires": {"internal": [{"source": paths[0], "source_output": 2,
                                      "target": paths[1], "target_input": 3,
                                      "source_item": paths[0], "target_item": paths[1]}],
                      "entering": [], "leaving": []}, "warnings": []}


class Ranker:
    def __init__(self):
        self.calls, self.cancels, self.reads = [], 0, []
        self.result = None
    def request(self, text, **kwargs):
        self.calls.append((text, kwargs))
        self.result = {"generation_key": kwargs["generation_key"], "status": "ranked", "source": "jev",
                       "ordered_actions": [{"id": action.id, "score": 2.5} for action in reversed(ACTIONS)]}
        return deepcopy(self.result)
    def snapshot(self, key):
        self.reads.append(key)
        return deepcopy(self.result)
    def cancel(self):
        self.cancels += 1


def settle():
    for _ in range(5):
        _APP.processEvents()


@pytest.fixture
def inspector():
    global _APP
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialogs = []
    def build(scale=1.0, width=650, height=768, data=None):
        h = SimpleNamespace(jobs=[], requests=[], result=deepcopy(data or report()), enabled=True, draft="Explain this network")
        def scanner(request, cancelled):
            h.requests.append(deepcopy(request))
            if isinstance(h.result, Exception): raise h.result
            return deepcopy(h.result)
        h.controller = InspectionController(scanner=scanner, launch=h.jobs.append)
        h.ranker = Ranker()
        h.parent = QtWidgets.QWidget()
        h.parent._chrome_scale = scale
        h.dialog = SelectionInspectorDialog(h.parent, controller=h.controller, service=h.ranker,
            settings_reader=lambda: {"jev_suggestions_enabled": h.enabled},
            scope_factory=lambda: object(), draft_reader=lambda: h.draft)
        h.dialog.resize(width, height)
        def finish():
            h.jobs.pop(0)(); h.dialog._poll(); settle()
        h.finish = finish
        h.dialog.open_inspection(); h.dialog._timer.stop(); settle()
        h.finish()
        dialogs.append(h)
        return h
    yield build
    for h in dialogs:
        h.dialog.close(); h.dialog.deleteLater(); h.parent.deleteLater()
    settle()


@pytest.mark.parametrize("scale,width", [(1, 340), (1, 650), (1.25, 340), (1.25, 650), (2.25, 340), (2.25, 780)])
def test_native_controls_stay_within_page_and_scroll_at_narrow_large_type(inspector, scale, width):
    h = inspector(scale, width); d = h.dialog
    assert d.width() == width
    assert not d.isModal()
    assert d._scroll.horizontalScrollBar().maximum() == 0
    assert d._scroll.verticalScrollBar().maximum() > 0
    for widget in (d._title, d._refresh_btn, d._pin_btn, d._intent, d._suggest_btn,
                   d._via, d._input_port, d._preview_btn, *d._action_buttons.values()):
        origin = widget.mapTo(d._page, QtCore.QPoint())
        assert origin.x() >= 0
        assert origin.x() + widget.width() <= d._page.width()
        if isinstance(widget, QtWidgets.QPushButton):
            assert widget.width() >= max(widget.fontMetrics().horizontalAdvance(line) for line in widget.text().splitlines())
            assert widget.height() >= widget.fontMetrics().height() * len(widget.text().splitlines())
            assert widget.accessibleName() == " ".join(widget.text().splitlines())
    refresh = QtCore.QRect(d._refresh_btn.mapTo(d._page, QtCore.QPoint()), d._refresh_btn.size())
    pin = QtCore.QRect(d._pin_btn.mapTo(d._page, QtCore.QPoint()), d._pin_btn.size())
    assert not refresh.intersects(pin)
    assert d._close_btn.geometry().bottom() < d.height()
    assert d._close_btn.geometry().top() > d._scroll.geometry().bottom()
    d._scroll.ensureWidgetVisible(d._preview_btn); settle()
    visible = d._preview_btn.mapTo(d._scroll.viewport(), QtCore.QPoint())
    assert 0 <= visible.y() < d._scroll.viewport().height()


def test_exact_wire_ports_and_unknown_are_displayed_as_observed(inspector):
    data = report(); data["wires"]["entering"] = [{"source": None, "source_output": None, "target": "/stage/source", "target_input": 1}]
    data.update(complete=False, can_pin=False, warnings=["Connection endpoint unavailable."])
    h = inspector(data=data); d = h.dialog
    assert [d._wires.topLevelItem(0).text(i) for i in range(5)] == ["Internal", "/stage/source", "2", "/stage/destination", "3"]
    assert d._wires.topLevelItem(1).text(1) == d._wires.topLevelItem(1).text(2) == "unknown"
    assert "Incomplete" in d._evidence_note.text()
    assert not d._pin_btn.isEnabled() and not any(b.isEnabled() for b in d._action_buttons.values())


def test_empty_selection_and_physical_wire_item_are_honest(inspector):
    data = report(); data["wires"]["internal"][0].update(source_item="/stage/dot1", source_item_output=0)
    h = inspector(data=data)
    assert "/stage/dot1 [out 0]" in h.dialog._wires.topLevelItem(0).toolTip(1)
    empty = report(); empty.update(selected_count=0, observed_count=0, nodes=[], identities=[], can_pin=False)
    empty["wires"] = {"internal": [], "entering": [], "leaving": []}
    d = inspector(data=empty).dialog
    assert "No nodes selected" in d._summary.text()
    assert not any(b.isEnabled() for b in d._action_buttons.values())


def test_ranking_is_explicit_and_scene_facts_never_enter_request(inspector):
    h = inspector(); d = h.dialog
    assert h.ranker.calls == []
    d._intent.setPlainText("Help me understand the wiring")
    d._poll(); assert h.ranker.calls == []
    d._suggest_btn.click()
    text, kwargs = h.ranker.calls[-1]
    assert text == "Help me understand the wiring"
    assert set(kwargs) == {"generation_key", "scope", "enabled", "should_abort"}
    assert "/stage" not in text and ".hip" not in text
    assert not kwargs["should_abort"]()
    assert d._action_layout.itemAt(0).widget() is d._action_buttons[ACTIONS[-1].id]
    scope = kwargs["scope"]
    d._suggest_btn.click()
    assert h.ranker.calls[-1][1]["scope"] is scope
    h.enabled = False
    assert kwargs["should_abort"]()
    d._poll()
    assert d._action_layout.itemAt(0).widget() is d._action_buttons[ACTIONS[0].id]
    assert "Default order" in d._rank_status.text()


def test_pin_refresh_and_prompt_click_revalidate_without_submission(inspector):
    h = inspector(); d = h.dialog; prepared = []
    d.draft_ready.connect(prepared.append)
    d._pin_btn.click(); d._refresh_btn.click(); h.finish()
    assert h.requests[-1]["node_paths"] == [r["path"] for r in report()["identities"]]
    d._action_buttons["check_wiring"].click()
    assert prepared == []
    h.finish()
    assert len(prepared) == 1 and '"source_output": 2' in prepared[0]
    assert h.ranker.calls == []
    d._poll(); assert len(prepared) == 1
    h.result["identities"][0]["session_id"] = 999
    d._action_buttons["fix_selection"].click(); h.finish()
    assert len(prepared) == 1 and "stale" in d._status.text()
    assert not any(b.isEnabled() for b in d._action_buttons.values())


@pytest.mark.parametrize("status", ["pending", "ranked"])
def test_composer_edit_invalidates_old_rank_without_another_request(inspector, status):
    h = inspector(); d = h.dialog
    d._suggest_btn.click()
    h.ranker.result["status"] = status
    abort = h.ranker.calls[-1][1]["should_abort"]
    h.draft = "I changed my mind: check the output ports."
    d._poll()
    assert abort()
    assert len(h.ranker.calls) == 1
    assert d._action_layout.itemAt(0).widget() is d._action_buttons[ACTIONS[0].id]
    assert "Default order" in d._rank_status.text()


def test_close_cancels_pending_scan_and_rank_and_reopen_reuses_dialog(inspector):
    h = inspector(); d = h.dialog
    d._suggest_btn.click(); abort = h.ranker.calls[-1][1]["should_abort"]
    d._refresh_btn.click(); before = len(h.requests)
    d.close(); assert abort()
    h.finish()
    assert len(h.requests) == before and h.controller.view()["closed"]
    d.open_inspection(); d._timer.stop(); h.finish()
    assert d.isVisible() and len(h.requests) == before + 1


def test_insertion_preview_is_local_and_preserves_original_ports(inspector):
    h = inspector(); d = h.dialog; prepared = []
    d.draft_ready.connect(prepared.append)
    d._wires.setCurrentItem(d._wires.topLevelItem(0))
    d._via.setCurrentIndex(2)
    d._input_port.setValue(1); d._output_port.setValue(0)
    d._preview_btn.click()
    text = d._preview_text.toPlainText()
    assert "/stage/source [out 2] → /stage/intermediate [in 1]" in text
    assert "/stage/intermediate [out 0] → /stage/destination [in 3]" in text
    assert "No connections have been changed" in text and "not been verified" in text
    assert len(h.requests) == 1 and not h.jobs and not h.ranker.calls and not prepared


def test_panel_tools_entry_is_reusable_and_appends_draft_without_sending(make_panel, monkeypatch):
    panel = make_panel()
    import synapse.panel.selection_inspector as module
    dialogs = []
    class ProbeDialog:
        def __init__(self, parent, draft_reader):
            self.draft_ready = SimpleNamespace(connect=lambda callback: setattr(self, "ready", callback))
            self.opens = 0; self.closed = False; dialogs.append(self)
        def open_inspection(self): self.opens += 1
        def close(self): self.closed = True
    monkeypatch.setattr(module, "SelectionInspectorDialog", ProbeDialog)
    sent = []
    monkeypatch.setattr(panel, "_send", lambda *a: sent.append(a))
    panel._input.setPlainText("Keep my existing draft.")
    menu = panel._build_overflow_menu()
    action = next(a for a in menu.actions() if a.text() == "Selected network…")
    action.trigger(); action.trigger()
    assert len(dialogs) == 1 and dialogs[0].opens == 2
    dialogs[0].ready("Prepared inspection prompt.")
    assert panel._input.toPlainText() == "Keep my existing draft.\n\nPrepared inspection prompt."
    assert sent == []
    panel.close(); assert dialogs[0].closed
    menu.deleteLater()


def test_real_panel_close_closes_inspector_and_reopen_revalidates_pin(make_panel, monkeypatch):
    global _APP
    panel = make_panel()
    _APP = QtWidgets.QApplication.instance()
    import synapse.panel.selection_inspector as module
    jobs, requests, sent = [], [], []
    def scanner(request, cancelled):
        assert not cancelled()
        requests.append(deepcopy(request))
        return report()
    controller = InspectionController(scanner=scanner, launch=jobs.append)
    ranker = Ranker()
    real_dialog = module.SelectionInspectorDialog
    def factory(parent, **kwargs):
        return real_dialog(parent, controller=controller, service=ranker,
            settings_reader=lambda: {"jev_suggestions_enabled": False}, **kwargs)
    monkeypatch.setattr(module, "SelectionInspectorDialog", factory)
    monkeypatch.setattr(panel, "_send", lambda *a: sent.append(a))
    panel._input.setPlainText("Keep this draft through close and reopen.")
    panel._open_selection_inspector()
    dialog = panel._selection_inspector
    assert isinstance(dialog, real_dialog) and dialog.isVisible() and dialog._timer.isActive()
    jobs.pop(0)(); dialog._poll(); settle()
    dialog._pin_btn.click()
    dialog._refresh_btn.click()  # One queued read must be cancelled on parent close.
    panel.close(); settle()
    assert not panel.isVisible() and not dialog.isVisible()
    assert controller.view()["closed"] and not dialog._timer.isActive()
    jobs.pop(0)()
    assert len(requests) == 1
    panel.show(); panel._open_selection_inspector(); settle()
    assert panel._selection_inspector is dialog
    assert dialog.isVisible() and dialog._timer.isActive()
    assert controller.view()["status"] == "loading" and controller.view()["pinned"]
    assert not any(button.isEnabled() for button in dialog._action_buttons.values())
    jobs.pop(0)(); dialog._poll(); settle()
    assert controller.view()["status"] == "ready"
    assert requests[-1]["expected_identities"] == report()["identities"]
    assert requests[-1]["expected_topology_hash"] == report()["topology_hash"]
    assert panel._input.toPlainText() == "Keep this draft through close and reopen."
    assert not sent and not ranker.calls
