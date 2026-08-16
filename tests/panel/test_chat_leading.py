"""W5-PANEL item 5 — chat text gains +0.75pt of leading, PROVEN against the
widget's effective line spacing.

The trap this file exists to avoid: message_formatter.py:43 records that CSS
line-height AND QTextBlockFormat ProportionalHeight both left the document height
IDENTICAL — they render inert in this QTextDocument. So "+0.75pt leading" must be
proven to actually change the laid-out height, never merely set. These tests
measure the layout height with and without the leading and assert it moves.

The pure token math runs everywhere; the layout proof needs a real QTextDocument
(hython), so it skips in stock-Python CI.
"""
import os
import sys
import types

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.join(_ROOT, "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.modules.setdefault("hou", types.ModuleType("hou"))

import pytest

from synapse.panel.designsystem import tokens as t


# ----------------------------------------------------------------------
# Pure — the leading token + its pt->px conversion (always runs)
# ----------------------------------------------------------------------

def test_leading_token_is_075pt():
    assert t.CHAT_LEADING_PT == 0.75


def test_leading_px_is_pt_at_96dpi_and_positive():
    # 0.75pt at Qt's 96-DPI logical default = 1.0px exactly.
    assert t.chat_leading_px() == pytest.approx(0.75 * 96.0 / 72.0)
    assert t.chat_leading_px() > 0
    # explicit pt argument scales linearly
    assert t.chat_leading_px(1.5) == pytest.approx(1.5 * 96.0 / 72.0)


# ----------------------------------------------------------------------
# Qt-gated — the effective-spacing proof (run under hython)
# ----------------------------------------------------------------------

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

_qt = pytest.mark.skipif(not _HAVE_QT, reason="PySide unavailable — run via hython")

if _HAVE_QT:
    try:
        _LDH = QtGui.QTextBlockFormat.LineHeightType.LineDistanceHeight
        _SINGLE = QtGui.QTextBlockFormat.LineHeightType.SingleHeight
        _DOC_SEL = QtGui.QTextCursor.SelectionType.Document
    except AttributeError:  # some PySide6 builds shadow the nested enum; PySide2 flattens it
        _LDH = QtGui.QTextBlockFormat.LineDistanceHeight
        _SINGLE = QtGui.QTextBlockFormat.SingleHeight
        _DOC_SEL = QtGui.QTextCursor.Document

    def _as_int(x):
        # PySide6 LineHeightTypes doesn't coerce via int(); use .value.
        return int(x.value) if hasattr(x, "value") else int(x)

    _LDH_INT = _as_int(_LDH)
    _SINGLE_INT = _as_int(_SINGLE)

_APP = None


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    return _APP


def _doc_height(doc):
    return doc.documentLayout().documentSize().height()


@_qt
def test_line_distance_height_is_not_inert():
    # THE landmine check: unlike CSS line-height / ProportionalHeight (measured
    # identical at 1.0 and 1.5 — message_formatter.py:43), LineDistanceHeight must
    # actually grow the laid-out height, by ~lead per line.
    _app()
    lead = t.chat_leading_px()
    doc = QtGui.QTextDocument()
    f = QtGui.QFont(); f.setPixelSize(12); doc.setDefaultFont(f)
    doc.setTextWidth(80)                        # narrow -> multiple wrapped lines
    cur = QtGui.QTextCursor(doc)
    cur.insertText("word " * 24)
    h0 = _doc_height(doc)
    lines = doc.firstBlock().layout().lineCount()
    assert lines >= 2, ("need a multi-line block", lines)

    bf = QtGui.QTextBlockFormat()
    bf.setLineHeight(lead, _LDH_INT)
    cur.select(_DOC_SEL)
    cur.mergeBlockFormat(bf)
    h1 = _doc_height(doc)

    assert h1 > h0, ("leading rendered inert — like the two mechanisms before it",
                     h0, h1)
    # brackets both readings (leading added to every line, or only between lines)
    assert lead * (lines - 1) - 0.5 <= (h1 - h0) <= lead * lines + 0.5, \
        (h0, h1, lead, lines)


@_qt
def test_chat_display_carries_and_renders_the_leading():
    _app()
    from synapse.panel.chat_display import ChatDisplay
    lead = t.chat_leading_px()

    d = ChatDisplay()
    d.append_synapse_message("word " * 60)      # a real multi-line reply
    doc = d.document()
    doc.setTextWidth(200)                        # force wrapping
    h_with = _doc_height(doc)

    # a message block carries exactly +0.75pt of absolute leading
    found = False
    b = doc.firstBlock()
    while b.isValid():
        bf = b.blockFormat()
        if _as_int(bf.lineHeightType()) == _LDH_INT \
                and abs(bf.lineHeight() - lead) < 1e-6:
            found = True
            break
        b = b.next()
    assert found, "no block carries LineDistanceHeight == chat_leading_px()"

    # stripping the leading shrinks the effective spacing -> it was REAL, and the
    # widget's line spacing is +0.75pt over the un-led baseline.
    cur = QtGui.QTextCursor(doc)
    cur.select(_DOC_SEL)
    flat = QtGui.QTextBlockFormat(); flat.setLineHeight(0, _SINGLE_INT)
    cur.mergeBlockFormat(flat)
    h_without = _doc_height(doc)

    assert h_with > h_without, ("chat leading did not change effective spacing",
                                h_with, h_without)


@_qt
def test_user_message_also_gets_the_leading():
    _app()
    from synapse.panel.chat_display import ChatDisplay
    lead = t.chat_leading_px()
    d = ChatDisplay()
    d.append_user_message("word " * 60)
    doc = d.document()
    doc.setTextWidth(200)
    found = False
    b = doc.firstBlock()
    while b.isValid():
        bf = b.blockFormat()
        if _as_int(bf.lineHeightType()) == _LDH_INT \
                and abs(bf.lineHeight() - lead) < 1e-6:
            found = True
            break
        b = b.next()
    assert found, "user message did not receive the +0.75pt leading"
