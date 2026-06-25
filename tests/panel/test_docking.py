"""Goalpost — the panel must be usable at its own declared PANEL_MIN_HEIGHT.

Contract: docking-minimums (S2). Encodes Design §2.3:

    "vertical minimums stack hard … A ~900px floor means the panel forces the
    column open or scrolls its own chrome. … the panel should be usable at
    400px tall, which is its own declared PANEL_MIN_HEIGHT."

Today the stack is rail + ribbon + mode bar + faces (setMinimumHeight(380),
synapse_panel.py:401) + the Direct chat (setMinimumHeight(380), :360/:367) +
a 216px default composer + FaceReview's 168px hero — well past 400.

The ROBUST honest form is a COMPOSED-MINIMUM-HEIGHT assertion: read the
layout-computed minimumSizeHint(), not rendered pixels. minimumSizeHint()
returns the minimum the panel's own layout + child minimums demand, which is
exactly "does the chrome fit at the declared floor."

RUNTIME ENVIRONMENT — read before trusting a green:
    Composing a minimum height needs a live QWidget + layout, so this needs
    PySide. `synapse_panel.py` hard-imports PySide6/PySide2 at module top, so
    under stock CPython (no PySide) this module SKIPS — matching
    tests/test_panel_faces.py (panel widgets are verified via hython offscreen).
    A SKIP exits 0, which the harness reads as PASSING; run via hython for a
    real signal. See GOALPOST_TESTS_REPORT.md §(d).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# --- tiny hou stub so the panel's best-effort context reads don't explode ---
class _Hou:
    class _HipFile:
        def basename(self):
            return "untitled.hip"

    hipFile = _HipFile()

    @staticmethod
    def frame():
        return 1

    @staticmethod
    def selectedNodes():
        return []


sys.modules.setdefault("hou", _Hou)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6 import QtWidgets  # noqa: F401
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets  # noqa: F401
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

# Real Qt only — reject leaked PySide stubs (see tests/test_panel_faces.py).
if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

try:
    import pytest
    if not _HAVE_QT:
        pytestmark = pytest.mark.skip(reason="PySide unavailable — run via hython")
except Exception:
    pytest = None


_APP = None


def _make_panel():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from synapse.panel.synapse_panel import SynapsePanel
    return SynapsePanel()


def test_usable_at_min_height():
    # Design §2.3 — the panel's COMPOSED minimum height (what its layout + child
    # min-heights demand) must not exceed its own declared PANEL_MIN_HEIGHT, or
    # it forces the dock column open. Stacks to ~900px today -> FAILS; PASSES
    # once the hard min-heights are halved and faces collapse gracefully.
    from synapse.panel.designsystem import tokens as t

    floor = t.PANEL_MIN_HEIGHT  # 400
    panel = _make_panel()
    composed = panel.minimumSizeHint().height()
    assert composed <= floor, (
        "panel composed minimum height is %dpx, exceeding its declared "
        "PANEL_MIN_HEIGHT=%dpx — the stacked min-heights force the dock column "
        "(Design §2.3). Halve the hard minimums so it is usable at the floor."
        % (composed, floor)
    )
