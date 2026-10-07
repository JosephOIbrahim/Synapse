"""Clicking Copy on a code block puts exactly that code on the clipboard.

WHY THIS FILE EXISTS. Joe, 2026-10-07: SYNAPSE needs a Copy button on code, the
way Claude Desktop has one, so an artist can paste a snippet into another Houdini
parameter by hand. The formatter half (payload == code) is pinned by
tests/test_copy_code_formatter.py; this file pins what only Qt can show:

  * the control exists in the RENDERED QTextDocument, as an anchor whose text is
    "Copy" -- not merely in an HTML string Qt might have re-parsed differently;
  * the anchor does not bleed over the code or the prose around it;
  * a click (handler call AND a real mouse click through anchorClicked/QUrl)
    lands the exact code on QApplication.clipboard() and never navigates;
  * the "Copied" acknowledgement touches the clicked control only and reverts;
  * a malformed payload is a quiet no-op; node: and https links are unchanged.

Module-level cached app + widget, the house shape (test_transcript_readability.py):
a per-test fixture that built and deleteLater()'d a root hung the seat runner.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets")
pytest.importorskip("PySide6.QtGui")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from synapse.panel import chat_display as cd  # noqa: E402
from synapse.panel.chat_display import ChatDisplay  # noqa: E402
from synapse.panel.designsystem import components  # noqa: E402

VEX = ('// lift\nfloat h = chf("height");\n\tv@P.y += h * (@ptnum < 10 && s@name != "a&b");  \n'
       's@label = "naïve → ✓";')
PY = 'import hou\nnode = hou.node("/obj/geo1")\nfor p in node.parms():\n    print(p.name())'
MESSAGE = ("Here is the wrangle:\n```vex\n" + VEX + "\n```\n"
           "Run `hou.node` on /obj/geo1 then [docs](https://www.sidefx.com/docs/).\n"
           "```python\n" + PY + "\n```\nPaste either.")

_APP = None
_BUILT = []


def _app():
    global _APP
    if _APP is None:
        _APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        from synapse.panel.designsystem import fontload
        fontload.load_application_fonts()
    return _APP


def _chat():
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
    root.resize(900, 700)
    root.show()
    _app().processEvents()
    widget.append_user_message("Give me a wrangle and a lister.")
    widget.append_synapse_message(MESSAGE)
    widget._flush_pending_formats()
    _app().processEvents()
    _BUILT.append((root, widget))
    return _BUILT[0]


def _fragments(doc):
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                yield frag
            it += 1
        block = block.next()


def _copy_fragments(doc):
    return [f for f in _fragments(doc)
            if f.charFormat().anchorHref().startswith("synapse-copy:")]


def test_rendered_document_has_one_copy_anchor_per_block():
    _root, w = _chat()
    frags = _copy_fragments(w.document())
    assert [f.text() for f in frags] == ["Copy", "Copy"]
    decoded = [cd.decode_copy_href(f.charFormat().anchorHref()) for f in frags]
    assert decoded == [VEX, PY]


def test_anchor_does_not_bleed_over_code_or_prose():
    _root, w = _chat()
    for frag in _fragments(w.document()):
        text = frag.text()
        if any(s in text for s in ("chf(", "print(p.name", "Here is the wrangle",
                                   "Paste either", "hou.node")):
            assert not frag.charFormat().anchorHref().startswith("synapse-copy:"), text
    # inline `hou.node` is code-styled but carries no control of its own
    inline = [f for f in _fragments(w.document()) if f.text() == "hou.node"]
    assert inline and not any(f.charFormat().isAnchor() for f in inline)


def test_handler_puts_exact_code_on_clipboard_and_never_navigates(monkeypatch):
    _root, w = _chat()
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda u: opened.append(u))
    monkeypatch.setattr(cd, "_COPIED_HOLD_MS", 30)
    nodes = []
    w.node_clicked.connect(nodes.append)
    cb = QtWidgets.QApplication.clipboard()
    for want, frag in zip((VEX, PY), _copy_fragments(w.document())):
        cb.setText("SENTINEL")
        w._on_anchor_clicked(QtCore.QUrl(frag.charFormat().anchorHref()))
        assert cb.text() == want
    assert opened == [] and nodes == []
    w.node_clicked.disconnect(nodes.append)
    QTest.qWait(120)


def test_real_mouse_click_round_trips_through_qurl(monkeypatch):
    _root, w = _chat()
    monkeypatch.setattr(cd, "_COPIED_HOLD_MS", 30)
    doc = w.document()
    cb = QtWidgets.QApplication.clipboard()
    for want, frag in zip((VEX, PY), _copy_fragments(doc)):
        cb.setText("SENTINEL")
        cur = QtGui.QTextCursor(doc)
        cur.setPosition(frag.position() + 1)
        rect = w.cursorRect(cur)
        QTest.mouseClick(w.viewport(), QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, rect.center())
        _app().processEvents()
        assert cb.text() == want
    QTest.qWait(120)


def test_copied_acknowledgement_is_local_and_reverts(monkeypatch):
    _root, w = _chat()
    monkeypatch.setattr(cd, "_COPIED_HOLD_MS", 40)
    doc = w.document()
    prose = [f for f in _fragments(doc) if "Here is the wrangle" in f.text()][0]
    prose_font = prose.charFormat().font().toString()
    plain_before = doc.toPlainText()
    first = _copy_fragments(doc)[0]
    w._on_anchor_clicked(QtCore.QUrl(first.charFormat().anchorHref()))
    assert [f.text() for f in _copy_fragments(doc)] == ["Copied", "Copy"]
    # still the same control: payload intact, so a second click still copies
    assert cd.decode_copy_href(_copy_fragments(doc)[0].charFormat().anchorHref()) == VEX
    QTest.qWait(200)
    assert [f.text() for f in _copy_fragments(doc)] == ["Copy", "Copy"]
    assert doc.toPlainText() == plain_before
    prose_after = [f for f in _fragments(doc) if "Here is the wrangle" in f.text()][0]
    assert prose_after.charFormat().font().toString() == prose_font


@pytest.mark.parametrize("href", ["synapse-copy:!!!!", "synapse-copy:a",
                                  "synapse-copy:%E2%9C%93"])
def test_malformed_payload_is_a_quiet_no_op(monkeypatch, href):
    _root, w = _chat()
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda u: opened.append(u))
    cb = QtWidgets.QApplication.clipboard()
    cb.setText("SENTINEL")
    before = w.document().toHtml()
    w._on_anchor_clicked(QtCore.QUrl(href))
    _app().processEvents()
    assert cb.text() == "SENTINEL"
    assert w.document().toHtml() == before
    assert opened == []


def test_node_and_https_links_unchanged(monkeypatch):
    _root, w = _chat()
    opened = []
    monkeypatch.setattr(QtGui.QDesktopServices, "openUrl", lambda u: opened.append(u.toString()))
    nodes = []
    w.node_clicked.connect(nodes.append)
    w._on_anchor_clicked(QtCore.QUrl("node:/obj/geo1"))
    w._on_anchor_clicked(QtCore.QUrl("https://www.sidefx.com/docs/"))
    w._on_anchor_clicked(QtCore.QUrl("javascript:alert(1)"))
    w.node_clicked.disconnect(nodes.append)
    assert nodes == ["/obj/geo1"]
    assert opened == ["https://www.sidefx.com/docs/"]


_LONG = []


def _long_line_chat():
    """A second, separately cached widget: one fence with a line far wider than
    the reading measure. Kept apart so the counts above stay exact."""
    if _LONG:
        return _LONG[0]
    _app()
    root = QtWidgets.QWidget()
    root.setObjectName("DsRoot")
    root.setProperty("density", "standard")
    components.apply_stylesheet(root)
    lay = QtWidgets.QVBoxLayout(root)
    widget = ChatDisplay(root)
    lay.addWidget(widget)
    root.resize(700, 500)
    root.show()
    _app().processEvents()
    line = "v@P.y += " + " + ".join("chf(\"amp%d\") * sin(@Time * %d)" % (i, i) for i in range(12)) + ";"
    widget.append_synapse_message("Long one:\n```vex\n" + line + "\n```\n")
    widget._flush_pending_formats()
    _app().processEvents()
    _LONG.append((root, widget, line))
    return _LONG[0]


def test_long_code_line_wraps_so_copy_stays_on_screen():
    # Qt marks every <pre> block non-breakable whatever white-space the
    # formatter declares; one long VEX line then widened the document past the
    # viewport (horizontal scrollbar off) and pushed the right-aligned Copy
    # out of sight -- on exactly the snippets an artist most wants to copy.
    _root, w, line = _long_line_chat()
    doc = w.document()
    code_blocks = []
    block = doc.begin()
    while block.isValid():
        if block.text().startswith("v@P.y += "):
            code_blocks.append(block)
        block = block.next()
    assert code_blocks, "the long code line never reached the document"
    assert code_blocks[0].layout().lineCount() > 1
    assert doc.idealWidth() <= doc.textWidth() + 1
    frag = _copy_fragments(doc)[0]
    cur = QtGui.QTextCursor(doc)
    cur.setPosition(frag.position() + frag.length())
    assert w.cursorRect(cur).right() <= w.viewport().width()
    assert cd.decode_copy_href(frag.charFormat().anchorHref()) == line
