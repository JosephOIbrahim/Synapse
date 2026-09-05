"""design/joe-five J5 - air above the identity row (Joe, 2026-09-05).

Joe's word: "The top of SYNAPSE just needs a spacer so the text doesnt feel
choked by the panels top edge."  CTO ruling J5
(harness/cto/runs/2026-09-05/RULING_JOE_FIVE.md): the rail's shell inset gets
a top margin one grid step larger than its sides' vertical inset - SPACE_MD
(16 at standard, scaled with density) - carried by the rhythm role, never a
literal. Measured: wordmark top y >= 16 at 340x760 in the composed panel.

Two tests, committed RED before the fix (today y == 8 in all three profiles;
regions_{expert,curious,ml}.json, harness/design_review/2026-09-05):

  1. expert - the wordmark's top is one SPACE_MD below the pane's top edge and
     the rail's margins read (GUTTER, gap(SPACE_MD), GUTTER, SPACE_SM); the
     `shell` role's other edge containers (ribbon, direct face) keep the
     role's default (GUTTER, SPACE_SM, GUTTER, SPACE_SM) - the air is the
     rail's condition, not the role's default, so nothing under the rail moves.
  2. density - `_recompose('curious')` puts the wordmark at gap(SPACE_MD, airy)
     == 24 and `_recompose('ml')` at gap(SPACE_MD, tight) == 12: the value
     lives in the role table (rhythm._EDGE_TOP) and scales through tokens.gap,
     the same machinery path every other role margin takes.

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. Same
construction as harness/design_review/2026-09-05/measure_regions.py (compose,
340x760, CHAT face) against a scratch settings file so the artist's real
picks are never read or written (settings.py honours SYNAPSE_PANEL_SETTINGS).
"""
import os
import sys
import tempfile
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_hou = types.ModuleType("hou")
sys.modules.setdefault("hou", _hou)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_j5_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets, QtCore
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtCore
        _HAVE_QT = True
    except ImportError:
        _HAVE_QT = False

if _HAVE_QT:
    try:
        _qapp = getattr(QtWidgets, "QApplication", None)
        if not (isinstance(_qapp, type) and "PySide" in getattr(_qapp, "__module__", "")):
            _HAVE_QT = False
    except Exception:
        _HAVE_QT = False

import pytest

if not _HAVE_QT:
    pytestmark = pytest.mark.skip(reason="PySide unavailable - run via hython")

W, H = 340, 760

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _panel(profile="expert"):
    """A composed panel at the docking pref width, driven to the CHAT face."""
    _app()
    from synapse.panel.synapse_panel import SynapsePanel
    p = SynapsePanel()
    p._recompose(profile)
    p.resize(W, H)
    p.show()
    _app().processEvents()
    p._set_face("direct")
    p._converse_stack.setCurrentIndex(0)
    _app().processEvents()
    return p


def _top_y(panel, widget):
    return widget.mapTo(panel, QtCore.QPoint(0, 0)).y()


def _margins(widget):
    m = widget.layout().contentsMargins()
    return (m.left(), m.top(), m.right(), m.bottom())


def test_expert_rail_has_space_md_air_above_the_identity_row():
    from synapse.panel.designsystem import tokens as t
    p = _panel("expert")
    try:
        assert p.property("density") == "standard"
        rail = p._region_cache["_build_rail"]
        assert rail.property("rhythm_role") == "shell"
        air = t.gap(t.SPACE_MD, "standard")
        assert air == 16
        # J5: the wordmark top sits one SPACE_MD below the pane's top edge
        # (was 8 = SPACE_SM, the shell role's default; regions_expert.json).
        y = _top_y(p, p._wordmark)
        assert y == air, ("wordmark top y", y, "expected", air)
        # The whole identity row moves together: mark, wordmark, model token.
        assert _top_y(p, p._mark) == y
        assert _top_y(p, p._author_lbl) == y
        # The rail's margins: GUTTER sides, SPACE_MD top, SPACE_SM bottom -
        # the air under the rail is unchanged.
        assert _margins(rail) == (t.GUTTER, air, t.GUTTER, t.SPACE_SM), _margins(rail)
        # The other `shell` edge containers keep the role's default inset:
        # the air is the rail's edge condition, not the role's default.
        ribbon = p._region_cache["_build_context_ribbon"]
        direct_face = p._recall_card.parentWidget()
        for shell in (ribbon, direct_face):
            assert shell.property("rhythm_role") == "shell", shell.objectName()
            assert _margins(shell) == (t.GUTTER, t.SPACE_SM, t.GUTTER, t.SPACE_SM), (
                shell.objectName(), _margins(shell))
        assert _margins(ribbon) == (30, 8, 30, 8)
        # BC-5's measured goal still holds with the rail 8px taller: the
        # conversation keeps a majority of the pane at 340x760.
        share = p._chat.height() / H
        assert share >= 0.5, (p._chat.height(), share)
    finally:
        p.close()


def test_rail_air_scales_with_density_through_the_role_table():
    from synapse.panel.designsystem import rhythm, tokens as t
    # The value lives in the role table, keyed by the edge condition, and is
    # the SPACE_MD token - never a literal in synapse_panel.py.
    edge_top = getattr(rhythm, "_EDGE_TOP", None)
    assert edge_top is not None, "rhythm._EDGE_TOP: the shell role's top-edge condition"
    assert edge_top == {"shell": t.SPACE_MD}
    assert rhythm._MARGINS["shell"] == (t.GUTTER, t.SPACE_SM, t.GUTTER, t.SPACE_SM)
    p = _panel("expert")
    try:
        rail = p._region_cache["_build_rail"]
        assert rail.property("rhythm_edge") == "top"
        for profile, density, expected in (("curious", "airy", 24), ("ml", "tight", 12),
                                           ("expert", "standard", 16)):
            p._recompose(profile)
            _app().processEvents()
            assert p.property("density") == density, profile
            assert t.gap(t.SPACE_MD, density) == expected
            # Recompose reuses the cached rail widget; the edge condition rides
            # on it, so every density re-resolves the top through tokens.gap.
            assert p._region_cache["_build_rail"] is rail
            y = _top_y(p, p._wordmark)
            assert y == expected, (profile, "wordmark top y", y, "expected", expected)
            assert _margins(rail) == (t.GUTTER, expected, t.GUTTER, t.SPACE_SM), (
                profile, _margins(rail))
    finally:
        p.close()
