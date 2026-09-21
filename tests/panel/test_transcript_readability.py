"""The transcript must stay readable: sentence case, unbolded body, open spacing.

WHY THIS FILE EXISTS. v5.79.0 shipped a transcript in which EVERY message rendered
ALL CAPS at weight 500. The speaker-label pass selected `BlockUnderCursor` and merged
its label font across the whole block, and the label, the timestamp and the message
body share one block. Nothing caught it, because no test had ever asserted what the
body looks like. Measured on the shipped build: six of six fragments came back
AllUppercase.

Joe, 2026-09-21, on seeing it in the live panel: "the chat text in SYNAPSE is all caps
and tightly spaced. That makes it hard for neurodivergent users to read."

These assertions are about the RENDERED document, not about the source, because the
bug lived in a Qt format merge that no amount of reading the HTML would have revealed.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtGui")

from PySide6 import QtGui, QtWidgets  # noqa: E402

from synapse.panel.designsystem import components, rhythm, tokens as t  # noqa: E402
from synapse.panel.chat_display import ChatDisplay  # noqa: E402

BODY_USER = "The lighting ratio is reading well on this shot and the rim is warm."
BODY_SYNAPSE = ("That render came through clean. The grid has proper ST coordinates "
                "and the surface is in USD now, so the lookdev network is ready.")
SPEAKERS = {"YOU", "SYNAPSE"}

# Module-level, cached, never torn down -- the same shape tests/panel/test_j3_speakers.py
# uses. A pytest fixture that built and deleteLater()'d a root per test hung the seat
# runner past ten minutes; the house convention exists for a reason.
_APP = None
_BUILT = []


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _chat(w=900, h=600):
    if _BUILT:
        return _BUILT[0]
    _app()
    root = QtWidgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", "standard")
    components.apply_stylesheet(root)
    lay = QtWidgets.QVBoxLayout(root)
    widget = ChatDisplay(root)
    lay.addWidget(widget)
    root.resize(w, h)
    root.show()
    _app().processEvents()
    widget.append_user_message(BODY_USER)
    widget.append_synapse_message(BODY_SYNAPSE)
    widget._flush_pending_formats()
    _app().processEvents()
    _BUILT.append((root, widget))
    return _BUILT[0]


def _fragments(chat):
    """[(text, capitalization, weight, is_speaker_label)] for every visible run."""
    out = []
    doc = chat.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            it += 1
            if not frag.isValid() or not frag.text().strip():
                continue
            f = frag.charFormat().font()
            text = frag.text().strip()
            bare = text.lstrip("●• ").strip()
            out.append((text, f.capitalization(), f.weight(), bare.upper() in SPEAKERS))
        block = block.next()
    return out


def test_message_body_is_never_uppercase():
    """FAILS IF: the speaker-label caps reach the message body again."""
    _root, chat = _chat()
    upper = QtGui.QFont.Capitalization.AllUppercase
    shouting = [text for text, cap, _w, is_label in _fragments(chat)
                if not is_label and cap == upper]
    assert not shouting, (
        "message body rendered in caps, the v5.79.0 regression: %r" % shouting)


def test_message_body_is_not_bolded():
    """FAILS IF: the label's weight is merged over the body again.

    Joe asked to un-bold the transcript. The label may keep WEIGHT_MEDIUM -- it is a
    label -- but body text is regular, and the bug merged 500 across everything.
    """
    _root, chat = _chat()
    heavy = [(text, w) for text, _cap, w, is_label in _fragments(chat)
             if not is_label and w > t.WEIGHT_REGULAR]
    assert not heavy, "body text heavier than WEIGHT_REGULAR: %r" % heavy


def test_the_speaker_label_still_gets_its_own_typography():
    """FAILS IF: scoping the format to the label threw the label away with the body."""
    _root, chat = _chat()
    labels = [(text, w) for text, _cap, w, is_label in _fragments(chat) if is_label]
    assert labels, "no speaker label fragment found at all"
    assert all(w >= t.WEIGHT_MEDIUM for _text, w in labels), (
        "the label lost its weight when the format was scoped: %r" % labels)


def test_line_height_meets_the_accessibility_minimum():
    """FAILS IF: body line spacing drops below WCAG 1.4.12's 1.5x font size.

    Measured at 1.42x on the shipped v5.79.0 (a 17px step on a 12px body). Doubling
    the added leading takes the step to 18px, which is exactly 1.50x.

    Computed from the BLOCK FORMAT and the font metrics, never from QTextLayout.
    Reading layout.lineAt() here segfaulted Shiboken once other tests in this file
    had already walked the document: the layout the earlier walks left behind is not
    safe to index. Format plus metrics is the same number without the crash.
    """
    _root, chat = _chat()
    doc = chat.document()
    block = doc.begin()
    while block.isValid():
        text = block.text().strip()
        if len(text) > 60 and text not in (BODY_USER,) or len(text) > 90:
            added = block.blockFormat().lineHeight()
            px = None
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid() and len(frag.text().strip()) > 20:
                    font = frag.charFormat().font()
                    px = font.pixelSize()
                    natural = QtGui.QFontMetricsF(font).lineSpacing()
                    break
                it += 1
            if not px or px <= 0:
                block = block.next()
                continue
            step = natural + added
            assert step / px >= 1.5, (
                "line height %.2fpx on a %dpx body is %.2fx, under WCAG's 1.5x "
                "(natural %.2f + added %.2f)" % (step, px, step / px, natural, added))
            assert added >= 2.0, (
                "the added leading is %.2fpx; it was doubled to 2.0px" % added)
            return
        block = block.next()
    pytest.fail("no body block long enough to measure")


def test_the_transcript_gaps_stayed_doubled():
    """FAILS IF: the turn gaps shrink back, or someone moves the SHARED keys instead.

    The transcript owns "turn" and "turn_same" (PNL-L5). Doubling those is what opens
    the chat up; touching "group" or "row" would drag cards, parameter rows and the
    rail along with it, which is the thing that separation exists to prevent.
    """
    assert rhythm.ROLE_GAPS["turn"] == 48, "the between-turns gap is no longer doubled"
    assert rhythm.ROLE_GAPS["turn_same"] == 16, "the same-speaker gap is no longer doubled"
    assert rhythm.ROLE_GAPS["group"] == 16, "the SHARED group key moved; it must not"
    assert rhythm.ROLE_GAPS["row"] == 12, "the SHARED row key moved; it must not"
