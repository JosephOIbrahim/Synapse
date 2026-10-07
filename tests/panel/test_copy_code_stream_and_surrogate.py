"""Clicking Copy must never change what the transcript shows (review of 1f0e7136).

B1. The "Copied" acknowledgement rewrites the control in place, 4 chars -> 6 and
back 1.5 s later. Both rewrites sit BEFORE the streaming anchor, which
begin_stream used to keep as a plain int, and end_stream deletes from that
anchor to the end. The panel streams every reply, so:

  * click Copy on the previous reply while the next one streams, and the stream
    ends inside 1.5 s -> the delete started 2 chars early and Qt took the whole
    previous reply out of view;
  * click Copy, the next reply starts streaming inside 1.5 s, the label reverts
    mid-stream -> 2 streamed chars were left behind as junk.

Each case runs twice -- once with the click, once without -- and the transcript
text must be identical once the timer has been waited out on the real event loop.

B2. A lone surrogate in a code block used to raise inside the formatter, so
append_synapse_message raised and the reply vanished. It must render, and its
Copy control must copy without raising.

Standalone ChatDisplay widgets, never SynapsePanel. Widgets are kept alive in a
module list rather than deleteLater()'d per test (the seat-runner hang shape
noted in test_copy_code_anchor.py).
"""
from __future__ import annotations

import re

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtTest")

from PySide6 import QtCore, QtWidgets  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

import synapse  # noqa: E402
from synapse.panel import chat_display as cd  # noqa: E402
from synapse.panel.chat_display import ChatDisplay  # noqa: E402

print("synapse from", synapse.__file__)

PREVIOUS = "Here:\n```vex\nv@P.y += 1;\n```\nTail sentence END."
FINAL = "FINAL reply."
_KEEP = []
_TIME = re.compile(r"\b\d{1,2}:\d{2}(?:\s*[AP]M)?\b")


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _wait_out_copied_timer():
    QTest.qWait(cd._COPIED_HOLD_MS + 400)
    _app().processEvents()


def _transcript(w):
    """Plain text with clock times masked: the two runs of a case are seconds
    apart and may straddle a minute boundary."""
    return _TIME.sub("<t>", w.document().toPlainText())


def _copy_fragments(doc):
    out = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().anchorHref().startswith(cd.COPY_SCHEME):
                out.append(frag)
            it += 1
        block = block.next()
    return out


def _fresh(previous=PREVIOUS):
    _app()
    w = ChatDisplay()
    w.resize(700, 500)
    w.show()
    _app().processEvents()
    w.append_user_message("give me vex")
    w.append_synapse_message(previous)
    w._flush_pending_formats()
    _app().processEvents()
    _KEEP.append(w)
    return w


def _click_copy(w):
    frag = _copy_fragments(w.document())[0]
    w._on_anchor_clicked(QtCore.QUrl(frag.charFormat().anchorHref()))
    _app().processEvents()


def _click_mid_stream_then_end(click):
    w = _fresh()
    w.begin_stream()
    w.stream_chunk("streaming partial tokens")
    if click:
        _click_copy(w)
    w.end_stream(FINAL)
    w._flush_pending_formats()
    _app().processEvents()
    _wait_out_copied_timer()
    return w


def _click_then_stream_reverts_mid_stream(click):
    w = _fresh()
    if click:
        _click_copy(w)
    w.begin_stream()
    w.stream_chunk("streaming ")
    _wait_out_copied_timer()          # "Copied" -> "Copy" lands mid-stream
    w.stream_chunk("partial tokens")
    w.end_stream(FINAL)
    w._flush_pending_formats()
    _app().processEvents()
    return w


@pytest.mark.parametrize("scenario", [_click_mid_stream_then_end,
                                      _click_then_stream_reverts_mid_stream],
                         ids=["click-mid-stream-end-within-hold",
                              "click-then-stream-revert-mid-stream"])
def test_copy_click_never_changes_the_transcript(scenario):
    ref = scenario(click=False)
    hit = scenario(click=True)
    assert _transcript(hit) == _transcript(ref)
    text = hit.document().toPlainText()
    assert "Tail sentence END." in text and "v@P.y += 1;" in text
    assert text.count(FINAL) == 1
    assert "streaming" not in text and "partial tokens" not in text
    assert [f.text() for f in _copy_fragments(hit.document())] == ["Copy"]


def test_lone_surrogate_reply_renders_and_copies_without_raising():
    w = _fresh(previous="Here:\n```python\nx = '\ud800'\n```\nSurrogate tail END.")
    assert "Surrogate tail END." in w.document().toPlainText()
    frags = _copy_fragments(w.document())
    assert [f.text() for f in frags] == ["Copy"]
    assert cd.decode_copy_href(frags[0].charFormat().anchorHref()) == "x = '\ud800'"
    cb = QtWidgets.QApplication.clipboard()
    cb.setText("SENTINEL")
    _click_copy(w)
    # Qt itself maps the unpaired surrogate to '?' on the way in; the point is
    # that the copy happened and nothing raised.
    assert cb.text() != "SENTINEL" and cb.text().startswith("x = '")
    _wait_out_copied_timer()
    assert [f.text() for f in _copy_fragments(w.document())] == ["Copy"]
