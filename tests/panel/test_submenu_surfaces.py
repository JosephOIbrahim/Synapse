"""Real Qt checks for window ownership and responsive submenu actions."""
import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets")
from PySide6 import QtCore, QtGui

if not isinstance(QtWidgets.QApplication, type):
    pytest.skip("Native Qt required", allow_module_level=True)

_APP = None

@pytest.fixture
def app():
    # Bundled application fonts live as long as QApplication. Keep one owner
    # across this file and the existing native panel suites.
    global _APP, c, submenus
    _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.designsystem import components as c, submenus
    return _APP


def settle(app):
    for _ in range(6):
        app.processEvents()


def test_parent_restyle_does_not_cross_a_child_window(app):
    root = QtWidgets.QDialog()
    root.setObjectName("DsRoot")
    QtWidgets.QVBoxLayout(root).addWidget(c.label("Parent"))
    child = QtWidgets.QDialog(root)
    outer = QtWidgets.QVBoxLayout(child)
    label = QtWidgets.QLabel("Child has its own typography")
    custom = QtGui.QFont("Consolas", 17)
    custom.setLetterSpacing(QtGui.QFont.AbsoluteSpacing, 2)
    label.setFont(custom)
    outer.addWidget(label)
    row = QtWidgets.QHBoxLayout()
    row.setDirection(QtWidgets.QBoxLayout.RightToLeft)
    row.addWidget(c.Button("First"))
    row.addWidget(c.Button("Second"))
    outer.addLayout(row)
    form = QtWidgets.QFormLayout()
    form.addRow("Label", QtWidgets.QLineEdit())
    form.setVerticalSpacing(3)
    form.setRowWrapPolicy(QtWidgets.QFormLayout.DontWrapRows)
    outer.addLayout(form)
    child.show()
    settle(app)
    saved_font = label.font().toString()
    submenus.prepare(root, 2.25, kind="connection")
    root.show()
    settle(app)
    root.resize(450, 500)
    submenus.prepare(root, 1.0, kind="connection")
    settle(app)
    assert label.font().toString() == saved_font
    assert row.direction() == QtWidgets.QBoxLayout.RightToLeft
    assert form.rowWrapPolicy() == QtWidgets.QFormLayout.DontWrapRows
    assert form.verticalSpacing() == 3
    assert len(root.findChildren(QtWidgets.QLabel, "DsSubmenuHeading")) == 1
    child.close()
    root.close()
    root.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)


def test_action_row_stacks_then_returns_without_changing_state(app):
    root = QtWidgets.QDialog()
    root.setObjectName("DsRoot")
    outer = QtWidgets.QVBoxLayout(root)
    outer.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
    row = QtWidgets.QHBoxLayout()
    buttons = [c.Button("Check connection", "secondary"), c.Button("Cancel", "ghost"),
               c.Button("Use this model", "primary")]
    buttons[-1].setEnabled(False)
    clicks = []
    buttons[0].clicked.connect(lambda: clicks.append("check"))
    for button in buttons:
        row.addWidget(button)
    outer.addLayout(row)
    submenus.prepare(root, 2.25, kind="connection")
    root.resize(420, 450)
    root.show()
    settle(app)
    assert row.direction() == QtWidgets.QBoxLayout.TopToBottom
    for button in buttons:
        assert root.rect().contains(button.geometry())
        assert button.width() >= button.sizeHint().width()
    assert buttons[0].geometry().bottom() < buttons[1].geometry().top()
    assert buttons[1].geometry().bottom() < buttons[2].geometry().top()
    root.resize(1100, 450)
    settle(app)
    assert row.direction() == QtWidgets.QBoxLayout.LeftToRight
    assert buttons[0].geometry().right() < buttons[1].geometry().left()
    assert not buttons[-1].isEnabled()
    buttons[0].click()
    assert clicks == ["check"]
    root.close()
    root.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.DeferredDelete)
