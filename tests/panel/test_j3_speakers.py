"""Two distinct speaker identities on the real Qt widget.

Joe: "The chat used to have a color for USER and a color for SYNAPSE now its
grey for both. That is confusing for the user."

Root cause of "grey for both": message_formatter already painted a coloured
dot, but ``ChatDisplay._apply_turn_rhythm`` merged ``TEXT_SECONDARY`` over the
WHOLE label block, flattening dot + name to one grey - and the SYNAPSE turn
had no rule at all. After J3 the label block keeps its label typography but
its foreground is the SPEAKER's colour, read from the speaker the block
already carries in ``UserProperty + 1``:

PNL-L5 (2026-09-21) moved that typography from mono/LABEL to sans/LABEL_SM,
ALL CAPS - mono has no 500, so the MEDIUM this file asserts was a weight the
face could not draw. The assertion below is unchanged and now measures a
weight that is really there; no colour pin moved.

Soft Editorial (user approval 2026-09-23) supersedes the old J3 palette:
YOU is CHAT_USER sea-green, SYNAPSE is CHAT_ASSISTANT coral and carries a
hollow ring image. The original anti-regression guarantee remains: label
colors must survive the rhythm pass, and label typography must not spread.

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
    from PySide6 import QtWidgets, QtGui, QtCore
    _HAVE_QT = True
except ImportError:
    try:
        from PySide2 import QtWidgets, QtGui, QtCore
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

# Hue sectors for the approved sea-green/coral identity, independently of
# text labels: green-cyan and red-orange, respectively.
_USER_BUCKET = 9
_ASSISTANT_BUCKET = 0

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


def _speaker_colour(doc, who):
    # The first assistant fragment is an image, so measure the name itself.
    c = doc.find(who)
    assert not c.isNull(), who
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
        you_ink = _speaker_colour(doc, "YOU")
        syn_ink = _speaker_colour(doc, "SYNAPSE")
        assert you_ink == QtGui.QColor(t.CHAT_USER), you_ink.name()
        assert syn_ink == QtGui.QColor(t.CHAT_ASSISTANT), syn_ink.name()
        # Neither speaker is the grey that flattened both before J3.
        assert QtGui.QColor(t.TEXT_SECONDARY) not in (you_ink, syn_ink)
        # The label typography survives the colour: sans, medium, tracked,
        # ALL CAPS (PNL-L5; it was mono before, which could not draw 500).
        c = doc.find("SYNAPSE")
        font = c.charFormat().font()
        assert font.weight() == t.WEIGHT_MEDIUM, font.weight()
    finally:
        root.close()


def test_transcript_carries_both_speaker_hues():
    assert _bucket_of(t.CHAT_USER) == _USER_BUCKET
    assert _bucket_of(t.CHAT_ASSISTANT) == _ASSISTANT_BUCKET
    root, chat = _chat()
    try:
        _one_turn(chat)
        buckets = _hue_buckets(chat)
        # Both identities survive rendering, and neutral prose adds no hue.
        assert {_USER_BUCKET, _ASSISTANT_BUCKET} <= buckets, sorted(buckets)
        assert buckets <= {_USER_BUCKET, _ASSISTANT_BUCKET}, sorted(buckets)
    finally:
        root.close()


@pytest.mark.parametrize("scale", [1.0, 1.25, 2.25])
def test_assistant_mark_is_a_registered_hollow_image_not_a_missing_glyph(scale):
    root, chat = _chat()
    try:
        chat.font_scale = scale
        # Clearing also removes QTextDocument's resource cache. The second
        # conversation must still resolve the local ring without a font reset.
        for conversation in range(2):
            if conversation:
                chat.clear()
            _one_turn(chat)
            doc = chat.document()
            images = []
            block = _label_block(doc, "SYNAPSE")
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                it += 1
                if frag.isValid() and frag.charFormat().isImageFormat():
                    image_format = frag.charFormat().toImageFormat()
                    images.append(image_format.name())
                    # Inspect paint BEFORE asking resource(), which could
                    # populate the cache and conceal a first-render failure.
                    cursor = QtGui.QTextCursor(doc)
                    cursor.setPosition(frag.position())
                    bounds = chat.cursorRect(cursor)
                    rect = QtCore.QRect(bounds.x(), bounds.y(),
                                        int(image_format.width()), bounds.height())
                    assert chat.viewport().rect().contains(rect)
                    raster = chat.viewport().grab().toImage()
                    dpr = raster.devicePixelRatio()
                    painted = QtCore.QRect(round(rect.x() * dpr), round(rect.y() * dpr),
                                           round(rect.width() * dpr), round(rect.height() * dpr))
                    ink = [(x, y) for y in range(painted.top(), painted.bottom() + 1)
                           for x in range(painted.left(), painted.right() + 1)
                           if raster.pixelColor(x, y) == QtGui.QColor(t.CHAT_ASSISTANT)]
                    assert ink, (conversation, "assistant ring missing from first raster")
                    center = QtCore.QPoint((min(x for x, _ in ink) + max(x for x, _ in ink)) // 2,
                                          (min(y for _, y in ink) + max(y for _, y in ink)) // 2)
                    assert raster.pixelColor(center) == QtGui.QColor(t.PANEL), (
                        conversation, "painted assistant mark has no hole")
            assert images == ["synapse:assistant-ring"]
            ring = doc.resource(QtGui.QTextDocument.ImageResource,
                                QtCore.QUrl(images[0]))
            assert isinstance(ring, QtGui.QImage) and not ring.isNull(), conversation
            assert ring.pixelColor(ring.width() // 2, ring.height() // 2).alpha() == 0
            visible = [ring.pixelColor(x, y) for y in range(ring.height())
                       for x in range(ring.width()) if ring.pixelColor(x, y).alpha() > 128]
            assert visible, "the ring resource is empty"
            assert any(c.rgb() == QtGui.QColor(t.CHAT_ASSISTANT).rgb() for c in visible)
    finally:
        root.close()
