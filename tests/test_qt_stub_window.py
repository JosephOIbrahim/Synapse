"""Pins for ``tests/qt_stub_window`` — the scoped PySide6 stub window (Q1).

The defect these exist for: the window used to treat ``"PySide6" in sys.modules``
as "real Qt is present" and abdicate. A sibling file's blanket ``MagicMock``
PySide6 therefore satisfied it, ``SynapsePanel`` resolved to a ``Mock``, and
``tests/test_panel_stop_honest.py`` asserted against a Mock instead of
production code (``AttributeError: Mock object has no attribute '_on_stop'``).
Presence is not evidence; file-backing is.

Every test below drives ``sys.modules`` synthetically and restores it, so it is
interpreter-independent: it fails under its mutation on stock python AND under
hython (where real, file-backed PySide6 is resident).
"""

from __future__ import annotations

import sys
import types
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from qt_stub_window import capture_real_qt, qt_stub_window  # noqa: E402

_QT_PREFIXES = ("PySide6", "PySide2")


@contextmanager
def _isolated_sys_modules():
    """Save/restore every Qt-named ``sys.modules`` entry around a test body."""
    saved = {k: v for k, v in list(sys.modules.items()) if k.startswith(_QT_PREFIXES)}
    for key in saved:
        del sys.modules[key]
    try:
        yield
    finally:
        for key in [k for k in list(sys.modules) if k.startswith(_QT_PREFIXES)]:
            del sys.modules[key]
        sys.modules.update(saved)


def _file_backed_module(name):
    mod = types.ModuleType(name)
    mod.__file__ = rf"C:\fake\{name.replace('.', '/')}.pyd"
    return mod


def test_capture_real_qt_rejects_file_less_stubs():
    """FAILS IF the ``__file__`` filter is dropped or inverted.

    A file-less in-memory module (plain ``ModuleType`` or ``MagicMock``) would
    then be reported as real Qt, and the window would abdicate to it.
    """
    real = _file_backed_module("PySide6.QtCore")
    captured = capture_real_qt(
        {
            "PySide6.QtCore": real,
            "PySide6.QtWidgets": types.ModuleType("PySide6.QtWidgets"),
            "PySide6": MagicMock(),
            "json": _file_backed_module("json"),
        }
    )
    assert captured == {"PySide6.QtCore": real}, sorted(captured)


def test_window_takes_over_from_a_file_less_foreign_stub():
    """THE showstopper pin.

    FAILS IF the window abdicates on mere presence (``if "PySide6" in
    sys.modules: yield False``): it would then yield ``False`` and leave the
    foreign ``MagicMock`` resident, so importers get a Mock instead of a usable
    Qt surface.
    """
    with _isolated_sys_modules():
        foreign = MagicMock()
        sys.modules["PySide6"] = foreign
        sys.modules["PySide6.QtWidgets"] = MagicMock()

        with qt_stub_window() as planted:
            assert planted is True, (
                "window abdicated to a file-less foreign stub: presence was "
                "mistaken for real Qt"
            )
            assert sys.modules["PySide6"] is not foreign
            # adequate, not a blanket Mock: subclassable widget bases
            from PySide6.QtWidgets import QTextEdit  # noqa: PLC0415

            class _Derived(QTextEdit):
                pass

            assert isinstance(_Derived(), QTextEdit)


def test_window_restores_the_foreign_stub_by_identity():
    """FAILS IF the window leaks (never restores) or restores a rebuilt object.

    ``sys.modules`` must come back byte-for-object identical to how it was
    found, or the next file in the run sees a different Qt than it planted.
    """
    with _isolated_sys_modules():
        foreign = MagicMock()
        foreign_widgets = MagicMock()
        sys.modules["PySide6"] = foreign
        sys.modules["PySide6.QtWidgets"] = foreign_widgets
        before = {k: v for k, v in sys.modules.items() if k.startswith(_QT_PREFIXES)}

        with qt_stub_window():
            pass

        after = {k: v for k, v in sys.modules.items() if k.startswith(_QT_PREFIXES)}
        assert set(after) == set(before), (set(before), set(after))
        for key, mod in before.items():
            assert after[key] is mod, f"{key} was not restored by identity"


def test_window_plants_nothing_when_real_file_backed_qt_is_resident():
    """FAILS IF the window plants over real Qt.

    Evicting live Shiboken modules is unrecoverable in one process — the
    sibling panel suites take an access violation.
    """
    with _isolated_sys_modules():
        real = _file_backed_module("PySide6")
        real_core = _file_backed_module("PySide6.QtCore")
        sys.modules["PySide6"] = real
        sys.modules["PySide6.QtCore"] = real_core

        with qt_stub_window() as planted:
            assert planted is False
            assert sys.modules["PySide6"] is real
            assert sys.modules["PySide6.QtCore"] is real_core

        assert sys.modules["PySide6"] is real


def test_window_removes_by_identity_not_by_name():
    """FAILS IF teardown deletes ``sys.modules`` keys by name.

    A module authored *inside* the window (a real import, or another fixture's
    plant) must survive teardown; only what this window planted is removed.
    """
    with _isolated_sys_modules():
        sentinel = types.ModuleType("PySide6.QtCore")
        with qt_stub_window() as planted:
            assert planted is True
            sys.modules["PySide6.QtCore"] = sentinel

        assert sys.modules.get("PySide6.QtCore") is sentinel, (
            "teardown removed a key by NAME, destroying a replacement it did "
            "not plant"
        )
        assert "PySide6" not in sys.modules


def test_window_leaves_nothing_behind_when_qt_was_absent():
    """FAILS IF the window leaks its stub into the rest of the run."""
    with _isolated_sys_modules():
        with qt_stub_window() as planted:
            assert planted is True
            assert "PySide6" in sys.modules
        leftover = [k for k in sys.modules if k.startswith(_QT_PREFIXES)]
        assert leftover == [], leftover
