"""Code in the transcript renders in Space Mono, under Qt, at the size asked for.

WHY THIS FILE EXISTS (DES-D01, 2026-10-08). The mono stack is
``tokens.FONT_MONO_CSS`` = ``"Space Mono", "JetBrains Mono", "Consolas",
"monospace"`` -- the family names carry double quotes. ``message_formatter``
interpolated it RAW into double-quoted ``style="..."`` attributes (the fenced
block's ``<pre>`` and language label, inline ``<code>``, the node-path chip),
and ``chat_display`` did the same with ``FONT_SANS_CSS`` on the typing
indicator. The first quote of the stack closed the attribute at
``font-family:``. Measured offscreen on hython 22.0.400 before the fix:

    'float h = 1;'   fontFamilies() == ['monospace']   (the <pre> default)
    'hou.node'       fontFamilies() == ['monospace']   (the <code> default)
    '/obj/geo1'      fontFamilies() is None            (chip lost its mono)
    'SYNAPSE...'     fontFamilies() is None            (indicator lost its sans)

while ``QFontDatabase.families()`` DID contain "Space Mono". Everything after
``font-family`` in the attribute was lost too. Two of those losses are visible
and pinned here: the family, and the ``<pre>``'s ``white-space:pre-wrap``
(the block came back ``nonBreakableLines() == True``, i.e. plain ``pre``).
The lost ``font-size`` is NOT pinned: ``SIZE_SMALL == SIZE_BODY`` (tokens.py),
so the code inherits the same pixel size from the turn wrapper and the loss is
invisible -- a size assertion passed on the broken base (measured), so it
would prove nothing.

What only Qt can show, so what this pins: the CHARACTER FORMAT of the rendered
QTextDocument -- family list and block wrap mode -- not the HTML string. The string
half (stdlib html.parser) is pinned without Qt in
tests/test_code_font_attr_escape.py so CPython CI still sees a regression.

Skips cleanly without PySide6. Module-level cached app + widget, the house
shape (test_copy_code_anchor.py): a per-test root hung the seat runner.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtGui")

from PySide6 import QtGui, QtWidgets  # noqa: E402

from synapse.panel import message_formatter as mf  # noqa: E402
from synapse.panel.designsystem import tokens as t  # noqa: E402

MESSAGE = ("Wrangle for /obj/geo1:\n```vex\nfloat h = chf(\"height\");\n```\n"
           "Then run `hou.node` and stop.")
MONO_STACK = [t.FONT_MONO, *t.FONT_MONO_FALLBACKS]
SANS_STACK = [t.FONT_SANS, *t.FONT_SANS_FALLBACKS]

_APP = None
_BUILT = []


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _fragments(doc):
    """(text, QTextCharFormat) for every non-blank fragment, in order."""
    out = []
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.text().strip():
                out.append((frag.text(), frag.charFormat()))
            it += 1
        block = block.next()
    return out


def _fmt(doc, needle):
    hits = [cf for text, cf in _fragments(doc) if needle in text]
    assert hits, "no fragment contains %r; fragments: %r" % (
        needle, [text for text, _ in _fragments(doc)])
    return hits[0]


def _doc():
    _app()
    doc = QtGui.QTextDocument()
    doc.setHtml(mf.format_synapse_message(MESSAGE))
    return doc


def test_space_mono_is_installed_offscreen():
    """Precondition: the fallback is not 'Space Mono is missing'."""
    _app()
    assert t.FONT_MONO in QtGui.QFontDatabase.families()


@pytest.mark.parametrize("needle", [
    'float h = chf("height");',   # fenced block <pre>
    "hou.node",                   # inline <code>
    "/obj/geo1",                  # node-path artifact chip
    "vex",                        # fenced block language label
])
def test_code_faces_get_the_whole_mono_stack(needle):
    cf = _fmt(_doc(), needle)
    assert cf.fontFamilies() == MONO_STACK, (
        "%r rendered with families %r -- the style attribute was cut short"
        % (needle, cf.fontFamilies()))


def test_fenced_block_keeps_pre_wrap():
    """white-space:pre-wrap follows font-family in the <pre> attribute; a cut
    attribute left the block non-breaking (plain <pre>)."""
    doc = _doc()
    block = doc.begin()
    while block.isValid():
        if 'float h = chf("height");' in block.text():
            assert block.blockFormat().nonBreakableLines() is False
            return
        block = block.next()
    pytest.fail("fenced block not found in the rendered document")


def _chat():
    if _BUILT:
        return _BUILT[0]
    _app()
    from synapse.panel.chat_display import ChatDisplay
    from synapse.panel.designsystem import components
    root = QtWidgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", "standard")
    components.apply_stylesheet(root)
    lay = QtWidgets.QVBoxLayout(root)
    widget = ChatDisplay(root)
    lay.addWidget(widget)
    root.resize(720, 480)
    root.show()
    _app().processEvents()
    widget.append_user_message("hello")
    widget._insert_typing_html()
    _app().processEvents()
    _BUILT.append((root, widget))
    return _BUILT[0]


def test_typing_indicator_speaks_in_the_sans_stack():
    """chat_display's own interpolation of FONT_SANS_CSS, read off the live
    widget's document (not a re-parse of the string)."""
    _root, widget = _chat()
    frags = [(text, cf) for text, cf in _fragments(widget.document())
             if text.strip() == "SYNAPSE"]
    assert frags, "typing indicator 'SYNAPSE' fragment not found"
    cf = frags[-1][1]
    assert cf.fontFamilies() == SANS_STACK, cf.fontFamilies()
