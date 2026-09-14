"""Seat-suite guards.

WHY THIS FILE EXISTS
--------------------
A modal dialog under ``QT_QPA_PLATFORM=offscreen`` blocks forever: there is
nobody to click it. ``test_bc_wave.py::test_turn_receipt_offers_revert_on_chat``
did exactly that -- ``_send`` -> ``_allow_connection`` -> ``QMessageBox.exec()``
-- and took the rest of the file with it. Three tests after it had never run on
any machine, and anything queued behind the file never started. Nothing
reported a failure, because nothing got far enough to report one.

The file is PySide-gated, so under stock CPython it skips and a skip exits 0.
That is how a suite can be a third unrunnable and still read green.

This makes that class LOUD: a blocking call raises, naming the dialog's own
words, instead of hanging.

WHAT IS COVERED, EXACTLY
------------------------
The first version of this file claimed "any modal ``exec()``" and that was
FALSE. Two whole families escaped it, and both were measured still hanging
(``timeout`` exit 124) with that patch installed:

  * The C++ static convenience helpers -- ``QMessageBox.warning/question/...``,
    ``QFileDialog.get*``, ``QInputDialog.get*`` -- build and exec their dialog
    inside C++ and never consult the Python attribute that was replaced. Live
    call sites include ``gate_widget.py:311``, which is a CONSENT surface.

The static helpers are patched below. The list is explicit rather than clever,
because a guard that reads as total protection while one family still hangs is
worse than no guard at all.

``QMenu`` IS NOT COVERED, AND CANNOT BE COVERED THIS WAY
--------------------------------------------------------
``QMenu`` is not a ``QDialog`` and spins its own nested loop. It was the
obvious next thing to add, and it does not work. Measured on hython 22.0.400:

    setattr(QtWidgets.QMenu, "exec", boom)   ->  reported OK
    QtWidgets.QMenu().exec(QPoint(0, 0))     ->  returned None, never raised

The assignment is accepted and the patch is INERT -- PySide does not consult
the Python attribute for this call. The mechanism is UNKNOWN; only the
behaviour is measured. It was removed from the patch list rather than left in,
because an inert entry still increments the ``patched`` self-check and would
make the guard's own proof-of-installation lie.

So four live ``QMenu.exec`` call sites remain unguarded: ``chat_panel.py:535``
and ``synapse_panel.py:1749``, ``:1787``, ``:2690``. A seat test that opens one
of those menus can still hang. Closing that needs a different mechanism (a
watchdog on ``QApplication.activePopupWidget()``, or not driving menus from a
seat test at all) and is not attempted here.

One mitigating measurement, not a defence: an EMPTY ``QMenu().exec()`` returns
immediately on this build. Only a populated menu blocks.

WHY IT RAISES A ``BaseException``
---------------------------------
``synapse_panel.py`` carries 126 ``except Exception`` blocks, one of them
directly on the send path around ``_prepare_connection``. An ``AssertionError``
reached inside any of them becomes a plausible system message and a clean
``return False``: the test would not hang, would not fail, and would go GREEN
on a path it never exercised. That is strictly worse than the hang, because
the hang was at least honest.

WHAT THIS DOES NOT DO
---------------------
It does not auto-answer the dialog. Answering would be a consent surface
deciding itself, which is the defect class SYNAPSE names R18. A test that needs
to get past a consent gate must arrange the permission it is entitled to --
``_allow_connection`` returns early on an existing task grant and on an
existing session grant, before any dialog is built.

Known and unaddressed: the guard cannot exercise a dialog's DENY branch, so
"Keep editing" (which sets ``scope.active = False``) has no seat coverage here.
That belongs to a test that drives the outcome directly, not to this fixture.
"""
import pytest


class ModalInOffscreenTest(BaseException):
    """Not an ``Exception``: no product ``except Exception`` may swallow it."""


_ADVICE = ("Arrange the permission or input the test is entitled to rather "
           "than reaching the dialog. Do not auto-answer it.")

#: instance methods that block. QMenu is NOT a QDialog and must be named.
_BLOCKING_METHODS = {
    "QDialog": ("exec", "exec_"),
    "QMessageBox": ("exec", "exec_"),
    "QFileDialog": ("exec", "exec_"),
    "QInputDialog": ("exec", "exec_"),
    "QProgressDialog": ("exec", "exec_"),
    "QColorDialog": ("exec", "exec_"),
    "QFontDialog": ("exec", "exec_"),
    # NOT QMenu -- see the module docstring. The patch installs and is inert.
}

#: C++ static helpers that build and exec their own dialog internally.
_BLOCKING_STATICS = {
    "QMessageBox": ("warning", "question", "critical", "information", "about"),
    "QFileDialog": ("getOpenFileName", "getOpenFileNames", "getSaveFileName",
                    "getExistingDirectory"),
    "QInputDialog": ("getText", "getItem", "getInt", "getDouble",
                     "getMultiLineText"),
    "QColorDialog": ("getColor",),
    "QFontDialog": ("getFont",),
}


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "no_modal_guard: run WITHOUT the modal guard. A test that opts out and "
        "then reaches a modal hangs the whole run forever -- only the guard's "
        "own leak pin has a reason to use this.")


def _qtwidgets():
    try:
        from PySide6 import QtWidgets
        return QtWidgets
    except ImportError:
        try:
            from PySide2 import QtWidgets
            return QtWidgets
        except ImportError:
            return None


def _describe(obj):
    def ask(name):
        try:
            return getattr(obj, name)()
        except Exception:  # noqa: BLE001 - diagnostics only
            return ""
    return "  class : {0}\n  title : {1!r}\n  text  : {2!r}".format(
        type(obj).__name__, ask("windowTitle"), ask("text"))


def _refuse(self, *args, **kwargs):
    raise ModalInOffscreenTest(
        "a modal was opened in an offscreen test and would have hung the run "
        "forever.\n{0}\n{1}".format(_describe(self), _ADVICE))


def _refuse_static(label):
    def _inner(*args, **kwargs):
        raise ModalInOffscreenTest(
            "the blocking helper {0}() was called in an offscreen test and "
            "would have hung the run forever.\n  args  : {1!r}\n{2}".format(
                label, args[:3], _ADVICE))
    return staticmethod(_inner)


@pytest.fixture
def modal_error():
    """The guard's refusal class, by identity.

    Importing ``tests.panel.conftest`` from a test gets a DIFFERENT module
    object than the one pytest loaded as the conftest (pytest imports it as
    plain ``conftest``), so the two ``ModalInOffscreenTest`` classes are not
    the same object and ``pytest.raises`` silently fails to match. Take it
    from here instead.
    """
    return ModalInOffscreenTest


@pytest.fixture(autouse=True)
def no_blocking_modal(request, monkeypatch):
    """A modal in an offscreen test is a hang. Make it a failure instead.

    Opt out with ``@pytest.mark.no_modal_guard`` -- visible and greppable,
    unlike the silent hang it replaces. The guard's own leak pin needs it,
    because an autouse fixture is active during the very test that would
    check whether it tore down.
    """
    if request.node.get_closest_marker("no_modal_guard"):
        yield
        return
    qtw = _qtwidgets()
    if qtw is None:
        yield
        return

    patched = []

    def _patch(cls, name, value):
        try:
            monkeypatch.setattr(cls, name, value, raising=False)
            patched.append("{0}.{1}".format(cls.__name__, name))
        except Exception:  # noqa: BLE001 - surfaced by the self-check below
            pass

    for cls_name, names in _BLOCKING_METHODS.items():
        cls = getattr(qtw, cls_name, None)
        if cls is None:
            continue
        for name in names:
            if hasattr(cls, name):
                _patch(cls, name, _refuse)

    for cls_name, names in _BLOCKING_STATICS.items():
        cls = getattr(qtw, cls_name, None)
        if cls is None:
            continue
        for name in names:
            if hasattr(cls, name):
                _patch(cls, name, _refuse_static("{0}.{1}".format(cls_name, name)))

    # A guard that silently installed nothing is worse than no guard: it reads
    # as protection while the next modal still hangs the run.
    assert patched, (
        "the modal guard installed nothing -- PySide refused every patch, so "
        "this suite is still one dialog away from hanging forever")
    yield
