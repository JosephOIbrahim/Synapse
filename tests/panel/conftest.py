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

This makes that class LOUD. Any modal ``exec()`` reached from a test in
``tests/panel/`` raises, naming the dialog's own words, instead of hanging.

WHAT THIS DOES NOT DO
---------------------
It does not auto-answer the dialog. Answering would be a consent surface
deciding itself, which is the defect class SYNAPSE names R18. A test that needs
to get past a consent gate must arrange the permission it is entitled to --
``_allow_connection`` returns early on both an existing task grant and an
existing session grant, before any dialog is built.
"""
import pytest


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

    def _refuse(self, *args, **kwargs):
        def _ask(name, default=""):
            try:
                return getattr(self, name)()
            except Exception:  # noqa: BLE001 - diagnostics only
                return default
        raise AssertionError(
            "a modal dialog was opened in an offscreen test and would have "
            "hung the run forever.\n"
            "  class : %s\n"
            "  title : %r\n"
            "  text  : %r\n"
            "Arrange the permission the test is entitled to (see "
            "_allow_connection's early returns) rather than reaching the "
            "dialog. Do not auto-answer it."
            % (type(self).__name__, _ask("windowTitle"), _ask("text"))
        )

    patched = []
    for cls in (getattr(qtw, "QDialog", None), getattr(qtw, "QMessageBox", None),
                getattr(qtw, "QFileDialog", None), getattr(qtw, "QInputDialog", None)):
        if cls is None:
            continue
        for name in ("exec", "exec_"):
            if hasattr(cls, name):
                try:
                    monkeypatch.setattr(cls, name, _refuse, raising=False)
                    patched.append("%s.%s" % (cls.__name__, name))
                except Exception:  # noqa: BLE001 - reported by the self-check
                    pass
    # A guard that silently failed to install is worse than no guard: it reads
    # as protection while the next modal still hangs the run.
    assert patched, (
        "the modal guard installed nothing -- PySide refused every patch, so "
        "this suite is still one dialog away from hanging forever")
    yield
