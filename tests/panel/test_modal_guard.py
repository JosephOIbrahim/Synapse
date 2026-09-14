"""Pins for the seat suite's modal guard (tests/panel/conftest.py).

Everything in tests/panel/ now depends on that fixture, so it needs pins of its
own. Two properties matter and neither is obvious:

  1. it FIRES -- a modal exec() raises instead of blocking;
  2. it RESTORES -- the patch does not leak into a later test in the same
     process. A leaked patch would permanently break any later test that
     legitimately shows a dialog, and would do it silently, because the leak
     only shows up in whatever test happens to run next.

Property 2 is the one worth measuring. pytest's monkeypatch records the OLD
value with getattr, which on an inherited method reads through the base class --
so undo can leave a direct attribute shadowing an inherited one. Functionally
identical, but "functionally identical" is a claim, and this file checks it.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets
    _HAVE_QT = True
except ImportError:  # pragma: no cover
    try:
        from PySide2 import QtWidgets
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(
        reason="PySide unavailable - run via .synapse/hytest.py; a skip here "
               "measures nothing and must never be read as a pass")

_APP = None
#: captured at import, BEFORE any autouse fixture has patched anything.
_PRISTINE = {}
if _HAVE_QT:
    for _cls in (QtWidgets.QDialog, QtWidgets.QMessageBox):
        for _n in ("exec", "exec_"):
            if hasattr(_cls, _n):
                _PRISTINE[(_cls.__name__, _n)] = getattr(_cls, _n)


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def test_a_the_guard_fires_on_a_modal():
    """A modal raises, and the message carries the dialog's own words."""
    _app()
    box = QtWidgets.QMessageBox()
    box.setWindowTitle("Allow this model connection?")
    box.setText("a probe, not a real prompt")
    with pytest.raises(AssertionError) as caught:
        box.exec()
    msg = str(caught.value)
    assert "would have hung the run forever" in msg, msg
    assert "Allow this model connection?" in msg, msg
    assert "a probe, not a real prompt" in msg, msg
    assert "QMessageBox" in msg, msg


def test_b_the_guard_fires_for_a_plain_qdialog_too():
    """QDialog is the base every custom panel dialog inherits."""
    _app()
    with pytest.raises(AssertionError):
        QtWidgets.QDialog().exec()


@pytest.mark.no_modal_guard
def test_c_the_guard_does_not_leak_between_tests():
    """The patch must be gone by the time an unguarded caller runs.

    Carries @pytest.mark.no_modal_guard, WITHOUT WHICH THIS PIN IS A LIE: the
    autouse fixture is active during the very test that would check whether it
    tore down, so an unmarked version reads its own patch and reports a leak
    that is not there. Measured the wrong way round first.

    With the marker, the fixtures from the PREVIOUS tests have torn down and
    nothing has re-patched. If undo left the refusing function in place, the
    identity check below fails and the leak is named rather than discovered
    later by an unrelated test.
    """
    import tests.panel.conftest as guard
    for (cls_name, attr), original in _PRISTINE.items():
        cls = getattr(QtWidgets, cls_name)
        current = getattr(cls, attr)
        assert current is original or getattr(current, "__name__", "") != "_refuse", (
            "%s.%s is still the guard's _refuse after teardown -- the patch "
            "leaked and every later test that shows a dialog is broken"
            % (cls_name, attr))
    assert callable(guard.no_blocking_modal)
