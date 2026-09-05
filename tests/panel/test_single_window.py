"""SYNAPSE launches exactly one window.

Joe, 2026-09-05: "a sub panel that does nothing floats independently alongside
the SYNAPSE panel after launch and just hangs". Root cause, reproduced headless
(harness/cto/runs/2026-09-05/probe_who_shows.py): the retired rail meter
(`_observe`, objectName DsRailMeter) was constructed with NO parent and the
profile manifests still declared `activity_meter` visible, so the compositor's
`setVisible(True)` turned a 3px strip into a top-level Qt window titled
"houdini" with nothing in it.

This pin builds the panel the way the pypanel does and asserts that, once
shown, the ONLY visible top-level widget is the panel itself. A parentless
widget that anything ever shows becomes a second window; this test is the
fence. Needs PySide (skips under stock CPython like the rest of tests/panel).
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest


class _Hou:  # the same minimal stub tests/panel/test_docking.py installs
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


sys.modules.setdefault("hou", _Hou)   # real hou under hython stays resident
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def _build():
    """Build one panel and report the top-level widgets IT created: other
    tests in the same process may leave their own windows behind, so the
    fence is the delta, not the absolute count."""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    before = set(id(w) for w in QtWidgets.QApplication.topLevelWidgets())
    from synapse.panel.synapse_panel import SynapsePanel
    panel = SynapsePanel()
    panel.show()
    app.processEvents()
    new_tops = [w for w in QtWidgets.QApplication.topLevelWidgets() if id(w) not in before]
    return app, panel, new_tops


def test_panel_is_the_only_visible_top_level_window():
    app, panel, new_tops = _build()
    try:
        strays = [w for w in new_tops if w is not panel and w.isVisible()]
        assert not strays, (
            "SYNAPSE launched %d extra window(s): %s -- a parentless widget was shown; "
            "parent it (or never show it). Joe's floating 'houdini' title bar, 2026-09-05."
            % (len(strays), ["%s#%s %dx%d" % (type(w).__name__, w.objectName(),
                                               w.width(), w.height()) for w in strays])
        )
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()


def test_rail_meter_is_parented_and_hidden():
    """The retired meter keeps its referent for _set_busy but can never float:
    it has a parent (never a top-level) and stays hidden at rest."""
    app, panel, _ = _build()
    try:
        meter = panel._observe
        assert meter.parent() is not None, "DsRailMeter has no parent: any setVisible(True) makes it a window"
        assert not meter.isVisible(), "DsRailMeter is visible at rest; it was retired from the header"
        assert not meter.isWindow()
    finally:
        panel.close()
        panel.deleteLater()
        app.processEvents()
