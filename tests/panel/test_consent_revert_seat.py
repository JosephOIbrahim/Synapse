"""F4 SEAT PIN — UNDO SENT on real Qt, measured instead of inferred.

WHY THIS FILE EXISTS
--------------------
``tests/panel/test_consent_way_back.py`` proves the F4 logic headlessly: it
execs the shipped method bodies out of source and cannot skip. What it CANNOT
prove is anything about real Qt. The merge of 5424853a therefore shipped one
labelled inference:

    "mark_revert_sent on real Qt is inferred from code-path reuse of
     _show_decision_tag/setEnabled, which the live-tested APPROVE/REJECT path
     exercises. That is an inference, not a measurement."

This file is that measurement. It answers the two questions the review left
open and nothing else:

  1. does ``UNDO SENT`` repolish and lay out in the FOOTER'S LEFT SLOT, the
     same slot the live-tested APPROVED tag occupies?
  2. does the disabled-parent-cannot-reenable-child quirk bite
     ``mark_revert_sent``, whose ``setEnabled(False)`` runs AFTER the tag's
     ``show()`` + ``repolish()``?

METHOD: differential, against the path that is already live-tested. Every
assertion compares ``mark_revert_sent()`` to ``mark_decided("approved")`` on
sibling cards built the same way. If the shared mechanism is sound both behave
identically; a divergence is the defect, and naming APPROVED as the reference
means this pin cannot pass by asserting something trivially true of both.

A SKIP HERE IS NOT A PASS. Real Qt only -- run it through the shim, which
resolves the symbol-table-stamped build rather than the newest installed one:

    python .synapse/hytest.py tests/panel/test_consent_revert_seat.py
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

sys.modules.setdefault("hou", types.ModuleType("hou"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SYNAPSE_REDUCED_MOTION", "1")
if not os.environ.get("SYNAPSE_PANEL_SETTINGS"):
    os.environ["SYNAPSE_PANEL_SETTINGS"] = os.path.join(
        tempfile.mkdtemp(prefix="synapse_seat_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets
    _HAVE_QT = True
except ImportError:  # pragma: no cover - stock CPython
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


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _root(density="standard"):
    _app()          # a QWidget built before the QApplication is a hard
                    # Qt crash, not an exception -- hython exits 127 with
                    # no traceback. Measured the slow way; do not reorder.
    from synapse.panel.designsystem import qss
    r = QtWidgets.QWidget()
    r.setObjectName("DsRoot")
    r.setProperty("density", density)
    r.setStyleSheet(qss.stylesheet())
    r.resize(340, 520)
    QtWidgets.QVBoxLayout(r)
    return r


def _two_cards(density="standard"):
    """Two sibling REVIEW cards, laid out together, settled differently."""
    from synapse.panel import gate_widget as gw
    from synapse.panel.designsystem import rhythm
    root = _root(density)
    made = {}
    for key in ("approved", "revert"):
        card = gw._ProposalCard(
            {"proposal_id": "p-%s" % key, "level": "review",
             "operation": "delete_node", "agent_id": "HANDS",
             "description": "seat pin", "created_at": ""}, parent=root)
        root.layout().addWidget(card)
        made[key] = card
    rhythm.apply(root, density)
    root.show()
    _app().processEvents()
    made["approved"].mark_decided("approved")
    made["revert"].mark_revert_sent()
    _app().processEvents()
    return root, made


def _tag(card):
    return card._decision_tag


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
def test_undo_sent_is_visible_and_reads_its_own_word(density):
    root, cards = _two_cards(density)
    try:
        t_ok, t_rv = _tag(cards["approved"]), _tag(cards["revert"])
        assert t_ok.isVisible(), "reference APPROVED tag is not visible"
        assert t_rv.isVisible(), (
            "UNDO SENT never became visible on real Qt while APPROVED did")
        assert t_rv.text() == "UNDO SENT", t_rv.text()
        assert t_ok.text() == "APPROVED", t_ok.text()
    finally:
        root.deleteLater()


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
def test_undo_sent_occupies_the_same_footer_slot_as_approved(density):
    """The footer's LEFT slot, not merely somewhere in the card."""
    root, cards = _two_cards(density)
    try:
        t_ok, t_rv = _tag(cards["approved"]), _tag(cards["revert"])
        g_ok, g_rv = t_ok.geometry(), t_rv.geometry()
        assert g_ok.width() > 0 and g_ok.height() > 0, ("reference collapsed", g_ok)
        assert g_rv.width() > 0 and g_rv.height() > 0, (
            "UNDO SENT laid out to a zero box: %r" % (g_rv,))
        assert g_rv.x() == g_ok.x(), (
            "UNDO SENT is not in the same footer slot as APPROVED: x=%d vs %d"
            % (g_rv.x(), g_ok.x()))
        assert g_rv.y() == g_ok.y(), (g_rv.y(), g_ok.y())
        assert g_rv.height() == g_ok.height(), (g_rv.height(), g_ok.height())
        # The countdown shared that slot before the decision landed.
        assert not cards["revert"]._countdown_label.isVisible()
    finally:
        root.deleteLater()


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
def test_the_disabled_card_does_not_swallow_the_tag(density):
    """setEnabled(False) runs AFTER show()+repolish() on both paths.

    Qt disables children with the parent and cannot re-enable them while the
    parent is disabled. This pins that the ordering leaves UNDO SENT in exactly
    the state APPROVED is left in -- visible, sized, and disabled-with-its-card.
    """
    root, cards = _two_cards(density)
    try:
        for key in ("approved", "revert"):
            assert not cards[key].isEnabled(), (key, "card should have settled")
            assert not _tag(cards[key]).isEnabled(), (
                key, "tag should inherit the card's disabled state")
            assert _tag(cards[key]).isVisible(), (
                key, "disabling the card must not hide its settled tag")
    finally:
        root.deleteLater()


@pytest.mark.parametrize("density", ("airy", "standard", "tight"))
def test_undo_sent_is_neutral_and_the_verbs_are_gone(density):
    """UNDO SENT is a request in flight: neither a block nor a grant."""
    root, cards = _two_cards(density)
    try:
        assert _tag(cards["revert"]).property("status") == "", (
            "UNDO SENT must not carry BLOCKED: %r"
            % _tag(cards["revert"]).property("status"))
        assert _tag(cards["approved"]).property("status") == ""
        for key in ("approved", "revert"):
            visible_verbs = [b.text() for b
                             in cards[key].findChildren(QtWidgets.QPushButton,
                                                        "DsVerb")
                             if b.isVisible()]
            assert visible_verbs == [], (key, visible_verbs)
    finally:
        root.deleteLater()
