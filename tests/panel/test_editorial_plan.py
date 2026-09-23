"""Exercise the real rounded plan with live text, links and a second document."""
import os
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Requires real Qt", allow_module_level=True)
from PySide6 import QtCore, QtGui, QtTest
from synapse.panel.chat_display import ChatDisplay
from synapse.panel.designsystem import qss, tokens as t


@pytest.fixture
def display():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    widget = ChatDisplay()
    widget.setStyleSheet(qss.stylesheet())
    yield app, widget
    widget.shutdown()
    widget.close()


def pump(app):
    for _ in range(3):
        app.processEvents()


def plan_bounds(image):
    """Find the painted cell from pixels, independently of the frame math."""
    raised = QtGui.QColor(t.RAISED)
    middle = image.width() // 2
    ys = [y for y in range(image.height()) if image.pixelColor(middle, y) == raised]
    assert ys, "numbered response has no raised cell"
    top, bottom = min(ys), max(ys)
    middle_y = (top + bottom) // 2
    xs = [x for x in range(image.width()) if image.pixelColor(x, middle_y) == raised]
    return min(xs), top, max(xs), bottom


@pytest.mark.parametrize("scale,width", [(1.0, 380), (1.25, 580), (2.25, 760)])
def test_plan_has_soft_corners_dividers_live_links_and_survives_clear(display, scale, width):
    app, widget = display
    widget.font_scale = scale
    widget.resize(width, 900)
    widget.show()
    clicked = []
    widget.node_clicked.connect(clicked.append)
    for attempt in range(2):
        widget.clear()
        widget.append_synapse_message(
            "Before the plan.\n\n1. Geometry /stage/geo\n"
            "2. Cameras /stage/cam\n3. Render /out/karma\n\nAfter the plan.")
        pump(app)
        widget.verticalScrollBar().setValue(0)
        image = widget.viewport().grab().toImage()
        left, top, right, bottom = plan_bounds(image)
        panel = QtGui.QColor(t.PANEL)
        raised = QtGui.QColor(t.RAISED)
        # All four outer corners are cut out; the smaller lower-left cut is
        # distinct from the other three. Neither a square nor a pill passes.
        for x, y in ((left + 1, top + 1), (right - 1, top + 1),
                     (left + 1, bottom - 1), (right - 1, bottom - 1)):
            assert image.pixelColor(x, y).red() < raised.red()
        d = max(3, round(3 * scale))
        assert image.pixelColor(left + d, bottom - d) == raised
        assert image.pixelColor(right - d, bottom - d) == panel
        # Each separator spans the empty gap between list rows.
        mid = (left + right) // 2
        dividers = [y for y in range(top, bottom + 1)
                    if all(image.pixelColor(x, y) == QtGui.QColor(t.BORDER)
                           for x in (mid - 12, mid, mid + 12))]
        # Antialiased 1px lines may occupy two adjoining raster rows.
        runs = [y for i, y in enumerate(dividers) if i == 0 or y > dividers[i - 1] + 1]
        assert len(runs) == 2, dividers
        plain = widget.toPlainText()
        assert plain.index("Before") < plain.index("Geometry") < plain.index("Cameras") < plain.index("After")
        hit = widget.document().find("/stage/geo")
        assert not hit.isNull()
        assert hit.charFormat().anchorHref() == "node:/stage/geo"
        widget.setTextCursor(hit)
        assert widget.textCursor().selectedText() == "/stage/geo"
        # Actual mouse hit-testing still reaches the same node after decoration.
        hit.setPosition(hit.selectionStart() + 3)
        point = widget.cursorRect(hit).center()
        QtTest.QTest.mouseClick(widget.viewport(), QtCore.Qt.LeftButton, pos=point)
        assert clicked == ["/stage/geo"] * (attempt + 1)
        # Scroll-away and return repaint the same cell without stale masks.
        widget.append_synapse_message("\n\n".join("A quiet line" for _ in range(60)))
        pump(app)
        assert widget.verticalScrollBar().maximum() > 0
        widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum())
        pump(app)
        widget.verticalScrollBar().setValue(0)
        pump(app)
        restored = widget.viewport().grab().toImage()
        l2, t2, r2, b2 = plan_bounds(restored)
        assert (t2, b2) == (top, bottom)
        assert restored.pixelColor(r2 - 1, b2 - 1).red() < raised.red()


def test_ordinary_prose_and_bullets_do_not_become_plan_cells(display):
    app, widget = display
    widget.resize(480, 600)
    widget.show()
    widget.append_synapse_message("A useful answer.\n\n- Geometry\n- Cameras\n\nLiteral `1. code`.")
    pump(app)
    image = widget.viewport().grab().toImage()
    assert not any(image.pixelColor(image.width() // 2, y) == QtGui.QColor(t.RAISED)
                   for y in range(image.height()))
    assert "Geometry" in widget.toPlainText()
