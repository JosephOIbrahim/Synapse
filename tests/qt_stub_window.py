"""Scoped, self-restoring PySide6 stub window (Q1 completion, D1).

Why this exists
---------------
``tests/test_panel_freeze_beat.py`` and ``tests/test_panel_stop_honest.py``
used ``pytest.importorskip("PySide6")``. On an interpreter without PySide6
(stock CI / system python) they collected ZERO tests when run alone, yet
reported 3 passed each inside the full suite — because an *unrelated* test
file happened to plant a PySide6 stub into ``sys.modules`` first. Those 6
passes were cross-file-residue-dependent: the suite count was partly fiction.

The fix is for each file to provide its OWN stub, live only for the duration
of its own imports, then removed. This module is that window.

Discipline (identical to ``tests/test_hda_panel.py``)
-----------------------------------------------------
* **Never evict real Qt.** If ``PySide6`` is already in ``sys.modules`` — real
  PySide6 under hython, or a sibling's stub — this window plants NOTHING and
  yields ``False``. Shiboken cannot re-initialise in one process; deleting a
  live real PySide6 and putting a rebuilt one back is what crashed sibling
  panel tests with an access violation.
* **Remove only what it planted, by object identity.** If some other module
  replaced a key while the window was open, that replacement is left alone.
* The stub is deliberately RICH (QtWidgets/QtGui as well as QtCore) because
  ``synapse.panel.synapse_panel`` subclasses ``QtWidgets.QTextEdit`` at import
  time. It is NOT planted unless PySide6 is absent, so it can never shadow a
  genuine PySide6 and can never trip the panel suite's genuine-PySide guard.

Failure conditions (Law 1)
--------------------------
* If the stub is too thin, the guarded import raises and the calling test file
  errors at collection — loudly, not silently skipped.
* If the teardown fails to remove the stub, ``tests/test_hda_panel.py``'s
  restore pin and the sibling-composition oracles go red.
"""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from unittest.mock import MagicMock

QT_STUB_KEYS = ("PySide6", "PySide6.QtCore", "PySide6.QtWidgets", "PySide6.QtGui")


class _AutoMockModule(types.ModuleType):
    """Module whose missing attributes resolve to a fresh ``MagicMock``.

    Lets ``from PySide6.QtWidgets import AnythingAtAll`` succeed regardless of
    which Qt class is asked for.
    """

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        mock = MagicMock()
        object.__setattr__(self, name, mock)
        return mock


class _FakeSignal:
    def __init__(self, *args, **kwargs):
        self._slots = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, *args):
        for slot in list(self._slots):
            slot(*args)

    def disconnect(self, slot=None):
        if slot is None:
            self._slots.clear()
        else:
            self._slots.remove(slot)


class _FakeQObject:
    def __init__(self, *args, **kwargs):
        pass


class _FakeQThread(_FakeQObject):
    def isRunning(self):
        return False

    def start(self):
        pass

    def wait(self, timeout=0):
        pass

    def msleep(self, ms):
        pass


class _FakeQWidget(_FakeQObject):
    """Subclassable widget base — the panel derives real classes from these."""

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return MagicMock()


def _build_stub_modules():
    """Construct a fresh, disposable PySide6 stub package."""
    pyside6 = _AutoMockModule("PySide6")
    pyside6.__path__ = []  # makes it a package

    core = _AutoMockModule("PySide6.QtCore")
    core.Signal = _FakeSignal
    core.Slot = lambda *a, **k: (lambda f: f)
    core.QObject = _FakeQObject
    core.QThread = _FakeQThread
    core.QTimer = MagicMock
    core.QMetaObject = MagicMock()
    core.Qt = MagicMock()
    core.Q_ARG = MagicMock()
    core.QUrl = MagicMock
    core.QSize = MagicMock
    core.QEvent = MagicMock
    core.QPropertyAnimation = MagicMock
    core.QEasingCurve = MagicMock()

    widgets = _AutoMockModule("PySide6.QtWidgets")
    for _name in (
        "QWidget", "QTextEdit", "QFrame", "QLabel", "QPushButton", "QComboBox",
        "QCheckBox", "QProgressBar", "QScrollArea", "QLineEdit", "QToolButton",
        "QStackedWidget", "QTableWidget", "QSizePolicy", "QSplitter",
    ):
        setattr(widgets, _name, type(_name, (_FakeQWidget,), {}))
    widgets.QVBoxLayout = MagicMock
    widgets.QHBoxLayout = MagicMock
    widgets.QGridLayout = MagicMock
    widgets.QTableWidgetItem = MagicMock
    widgets.QGraphicsOpacityEffect = MagicMock
    widgets.QAbstractItemView = MagicMock()
    widgets.QApplication = MagicMock

    gui = _AutoMockModule("PySide6.QtGui")
    gui.QCursor = MagicMock
    gui.QTextCursor = MagicMock()
    gui.QGuiApplication = MagicMock
    gui.QShortcut = MagicMock
    gui.QKeySequence = MagicMock
    gui.QFont = MagicMock
    gui.QFontDatabase = MagicMock()

    pyside6.QtCore = core
    pyside6.QtWidgets = widgets
    pyside6.QtGui = gui

    return {
        "PySide6": pyside6,
        "PySide6.QtCore": core,
        "PySide6.QtWidgets": widgets,
        "PySide6.QtGui": gui,
    }


@contextmanager
def qt_stub_window():
    """Plant a PySide6 stub for the body, then remove exactly what was planted.

    Yields ``True`` if a stub was planted, ``False`` if PySide6 (real or a
    sibling's stub) was already present and was therefore left untouched.
    """
    if "PySide6" in sys.modules:
        yield False
        return

    planted = _build_stub_modules()
    sys.modules.update(planted)
    try:
        yield True
    finally:
        for key, mod in planted.items():
            if sys.modules.get(key) is mod:
                del sys.modules[key]
