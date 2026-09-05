"""J3 (RULING_JOE_FIVE, 2026-09-05) - two speakers, two colours, on the widget.

Joe: "The chat used to have a color for USER and a color for SYNAPSE now its
grey for both. That is confusing for the user."

Root cause of "grey for both": message_formatter already painted a coloured
dot, but ``ChatDisplay._apply_turn_rhythm`` merged ``TEXT_SECONDARY`` over the
WHOLE label block, flattening dot + name to one grey - and the SYNAPSE turn
had no rule at all. After J3 the label block keeps its LABEL typography (mono,
tracked, MEDIUM) but its foreground is the SPEAKER's colour, read from the
speaker the block already carries in ``UserProperty + 1``:

  YOU     -> SIGNAL      (the accent that already means "the artist")
  SYNAPSE -> CONIFEROUS  (4.58:1 on GROUND, >= 4.5 AA; the warden's pick)

Real Qt only (hython 22.0.400 offscreen); skips under stock Python. The
transcript is grabbed under a DsRoot carrying the design-system stylesheet so
it sits on GROUND exactly as it does in the panel (qss.py: ``QTextBrowser {
background: GROUND }``) - the hue arithmetic is the review's own predicate
(REVIEW.md P1 / F4: 15-degree buckets over chroma > 24), copied from
tests/panel/test_bc_wave so J3 never imports J1's file.

Committed RED first: before the fix both label foregrounds measured
``QColor(TEXT_SECONDARY)`` and the grab held no bucket 8 (CONIFEROUS) - only
bucket 14 from the user rule.
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
        tempfile.mkdtemp(prefix="synapse_j3_"), "panel_settings.json")

try:
    from PySide6 import QtWidgets, QtGui
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui
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

from synapse.panel.designsystem import tokens as t

# Hue buckets (15-degree) of the two speaker colours, from the tokens themselves
# so the pin follows the palette rather than a copied number.
_SIGNAL_BUCKET = 14
_CONIFEROUS_BUCKET = 8

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _chat(w=340, h=400):
    """A ChatDisplay under a DsRoot carrying the design-system stylesheet, so
    the transcript sits on GROUND as it does in the composed panel."""
    _app()
    from synapse.panel.designsystem import qss
    from synapse.panel.chat_display import ChatDisplay
    root = QtWidgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", "standard")
    root.setStyleSheet(qss.stylesheet())
    lay = QtWidgets.QVBoxLayout(root)
    chat = ChatDisplay(root)
    lay.addWidget(chat)
    root.resize(w, h)
    root.show()
    _app().processEvents()
    return root, chat


def _one_turn(chat):
    chat.append_user_message("a")
    chat.append_synapse_message("b")
    chat._flush_pending_formats()
    _app().processEvents()


def _label_block(doc, who):
    cur = doc.find(who)
    assert not cur.isNull(), who
    return cur.block()


def _first_char_colour(block):
    c = QtGui.QTextCursor(block)
    c.movePosition(QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.KeepAnchor)
    return c.charFormat().foreground().color()


def _hue_buckets(widget):
    """The review's hue predicate (REVIEW.md, P1 / F4): 15-degree hue buckets
    over every chromatic pixel (chroma > 24) of an offscreen grab."""
    import colorsys
    img = widget.grab().toImage().convertToFormat(QtGui.QImage.Format.Format_RGB888)
    w, h, bpl = img.width(), img.height(), img.bytesPerLine()
    raw = bytes(img.constBits())
    colours = set()
    for y in range(h):
        row = raw[y * bpl:y * bpl + 3 * w]
        colours.update(zip(row[0::3], row[1::3], row[2::3]))
    return {int(colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0] * 360) // 15
            for r, g, b in colours if max(r, g, b) - min(r, g, b) > 24}


def _bucket_of(hex_colour):
    import colorsys
    c = QtGui.QColor(hex_colour)
    return int(colorsys.rgb_to_hsv(c.redF(), c.greenF(), c.blueF())[0] * 360) // 15


def test_label_foreground_is_the_speaker_colour():
    root, chat = _chat()
    try:
        _one_turn(chat)
        doc = chat.document()
        you = _label_block(doc, "YOU")
        syn = _label_block(doc, "SYNAPSE")
        # The block the formatter's label lands in is the one the rhythm pass
        # tagged with the speaker - the merge reads the speaker from there.
        assert you.blockFormat().property(QtGui.QTextFormat.UserProperty + 1) == "YOU"
        assert syn.blockFormat().property(QtGui.QTextFormat.UserProperty + 1) == "SYNAPSE"
        you_ink = _first_char_colour(you)
        syn_ink = _first_char_colour(syn)
        assert you_ink == QtGui.QColor(t.SIGNAL), you_ink.name()
        assert syn_ink == QtGui.QColor(t.CONIFEROUS), syn_ink.name()
        # Neither speaker is the grey that flattened both before J3.
        assert QtGui.QColor(t.TEXT_SECONDARY) not in (you_ink, syn_ink)
        # The label typography survives the colour: mono, medium, tracked.
        c = QtGui.QTextCursor(syn)
        c.movePosition(QtGui.QTextCursor.NextCharacter, QtGui.QTextCursor.KeepAnchor)
        font = c.charFormat().font()
        assert font.weight() == t.WEIGHT_MEDIUM, font.weight()
    finally:
        root.close()


def test_transcript_carries_both_speaker_hues():
    assert _bucket_of(t.SIGNAL) == _SIGNAL_BUCKET
    assert _bucket_of(t.CONIFEROUS) == _CONIFEROUS_BUCKET
    root, chat = _chat()
    try:
        _one_turn(chat)
        buckets = _hue_buckets(chat)
        # Both speakers are on screen, pre-attentively: the SIGNAL rule + label
        # and the CONIFEROUS rule + label each survive the chroma > 24 gate.
        assert {_SIGNAL_BUCKET, _CONIFEROUS_BUCKET} <= buckets, sorted(buckets)
        # Two speakers, two colours - nothing else in a bare transcript is
        # chromatic (the warm mark lives in the rail, not here).
        assert buckets <= {_SIGNAL_BUCKET, _CONIFEROUS_BUCKET}, sorted(buckets)
    finally:
        root.close()
