"""Native UI checks: delayed responses may never import after dismissal."""
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Real Qt required, not a mock QApplication", allow_module_level=True)

from PySide6 import QtTest

from synapse.panel.worldlabs_dialog import WorldLabsDialog, QtCore, QtWidgets
from synapse.panel.inset_footer import InsetFooter
from synapse.panel.designsystem import components as c


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


class PendingCall(QtCore.QObject):
    delivered = QtCore.Signal(object)
    finished = QtCore.Signal()
    calls = []

    def __init__(self, action):
        super().__init__()
        self.action = action
        self.calls.append(self)

    def start(self):
        pass

    def complete(self):
        self.delivered.emit({"value": self.action()})
        self.finished.emit()


@pytest.fixture
def dialog(app):
    PendingCall.calls.clear()
    imports = []
    def importer(path, metadata):
        imports.append((path, metadata))
        return {"node_path": "/stage/worldlabs", "warnings": ["Scale is uncalibrated."]}
    widget = WorldLabsDialog(importer=importer, task_factory=PendingCall)
    widget.show()
    app.processEvents()
    yield widget, imports
    widget.close()
    for call in list(PendingCall.calls):
        try:
            call.finished.emit()
        except RuntimeError:
            pass
    widget.deleteLater()
    app.processEvents()


def test_missing_key_cannot_start_network_work(dialog):
    widget, imports = dialog
    widget.key.clear()
    widget.connect_button.click()
    widget.source.setText("sample-world")
    widget.import_button.click()
    assert PendingCall.calls == []
    assert imports == []
    assert "API key" in widget.status.text()


def test_import_is_single_explicit_action_and_reports_normalization(dialog, tmp_path, app):
    widget, imports = dialog
    asset = tmp_path / "world.ply"
    asset.write_text("ply\nformat ascii 1.0\nend_header\n")
    widget.source.setText(str(asset))
    widget.import_button.click()
    widget.import_button.click()
    assert len(PendingCall.calls) == 1
    assert imports == []
    PendingCall.calls[-1].complete()
    app.processEvents()
    assert imports == [(str(asset), {})]
    assert "Scale is uncalibrated" in widget.status.text()
    assert widget.import_button.isEnabled()


def test_close_and_reopen_cannot_apply_a_stale_download(dialog, tmp_path, app):
    widget, imports = dialog
    asset = tmp_path / "world.ply"
    asset.write_text("ply\n")
    widget.source.setText(str(asset))
    widget.import_button.click()
    stale = PendingCall.calls[-1]
    widget.close()
    widget.show()
    widget.import_button.click()
    current = PendingCall.calls[-1]
    stale.complete()
    app.processEvents()
    assert imports == []
    assert not widget.import_button.isEnabled()
    current.complete()
    app.processEvents()
    assert len(imports) == 1


@pytest.mark.parametrize("reopen_before_delivery", [False, True])
def test_escape_discards_pending_import_and_reopens_ready(dialog, tmp_path, app,
                                                        reopen_before_delivery):
    widget, imports = dialog
    asset = tmp_path / "world.ply"
    asset.write_text("ply\n")
    widget.source.setText(str(asset))
    widget.import_button.click()
    stale = PendingCall.calls[-1]
    QtTest.QTest.keyClick(widget, QtCore.Qt.Key_Escape)
    assert not widget.isVisible()
    if reopen_before_delivery:
        widget.show()
    stale.complete()
    app.processEvents()
    if not reopen_before_delivery:
        widget.show()
    assert imports == [], "Escape-dismissed work must not import after reopening"
    assert widget.import_button.isEnabled()
    widget.import_button.click()
    PendingCall.calls[-1].complete()
    app.processEvents()
    assert len(imports) == 1


def test_connection_lists_worlds_without_importing_or_generating(dialog, app):
    widget, imports = dialog
    requests = []
    class Client:
        def __init__(self, key):
            assert key == "private-session-key"
        def check_connection(self):
            requests.append("check")
            return {"remaining_credits": 42}
        def list_worlds(self):
            requests.append("list")
            return [{"id": "world-123", "title": "Harbour"}]
    widget._client_factory = Client
    widget.key.setText("private-session-key")
    widget.connect_button.click()
    assert requests == []
    PendingCall.calls[-1].complete()
    app.processEvents()
    assert requests == ["check", "list"]
    assert "42 API credits" in widget.status.text()
    widget.recent.setCurrentIndex(1)
    widget._pick_recent(1)
    assert widget.source.text() == "world-123"
    assert imports == []
    assert widget.key.echoMode() == QtWidgets.QLineEdit.Password


@pytest.mark.parametrize("width", [330, 640, 1100])
def test_worldlabs_is_adjacent_to_cloud_with_equal_inset_widths(app, width):
    controls = [c.Button(title) for title in ("Commands", "Saved networks",
                "Updates", "Cloud relay", "World Labs", "Connect models")]
    footer = InsetFooter(controls, scale=1.0)
    footer.resize(width, footer.heightForWidth(width))
    footer.show()
    app.processEvents()
    boxes = [button.geometry() for button in controls]
    assert len({box.width() for box in boxes}) == 1
    assert all(footer.rect().contains(box) for box in boxes)
    assert all(not left.intersects(right) for i, left in enumerate(boxes) for right in boxes[i+1:])
    if footer._columns == 3:
        assert boxes[3].top() == boxes[4].top()
        assert boxes[3].right() < boxes[4].left()
    assert boxes[-1].right() == max(box.right() for box in boxes)
    footer.close()
