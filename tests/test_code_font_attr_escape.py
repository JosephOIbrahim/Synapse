"""Every transcript style attribute that names a font keeps its whole value.

DES-D01 (2026-10-08). ``tokens.FONT_MONO_CSS`` quotes its family names
(``"Space Mono", ...``). Interpolated raw into a double-quoted ``style="..."``,
the first quote ended the attribute at ``font-family:`` -- an HTML parser
(stdlib ``html.parser`` here, Qt's in tests/panel/test_code_font_family_qt.py)
sees ``style="color:#C5C5C5; font-family:"`` and the code falls back to the
generic monospace face. This file is the no-Qt half, so a regression reddens
on stock CPython CI where the Qt file skips.

The assertion is on what a PARSER reads back, not on a substring of the
source: every parsed ``style`` that contains ``font-family`` must carry the
token's first family, and every one that the formatter sized must still
carry its ``font-size``.
"""
from __future__ import annotations

from html.parser import HTMLParser

import pytest

from synapse.panel import message_formatter as mf
from synapse.panel.designsystem import tokens as t

MESSAGE = ("Wrangle for /obj/geo1:\n```vex\nfloat h = chf(\"height\");\n```\n"
           "Then run `hou.node` and stop.")


class _Styles(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.styles = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "style" and value and "font-family" in value:
                self.styles.append((tag, value))


def _font_styles(html_text):
    p = _Styles()
    p.feed(html_text)
    p.close()
    return p.styles


@pytest.mark.parametrize("html_text", [
    mf.format_synapse_message(MESSAGE, timestamp="6:48 AM"),
    mf.format_response(MESSAGE),
], ids=["synapse_message", "response"])
def test_font_family_attributes_survive_parsing(html_text):
    styles = _font_styles(html_text)
    # <pre>, the "vex" label, inline <code>, the node chip (+ the timestamp).
    assert len(styles) >= 4, styles
    for tag, style in styles:
        assert t.FONT_MONO in style, (tag, style)
        assert not style.rstrip().endswith("font-family:"), (tag, style)


def test_sized_code_faces_keep_their_font_size():
    """font-size sits AFTER font-family on <pre>, <code> and the chip span."""
    for tag, style in _font_styles(mf.format_synapse_message(MESSAGE)):
        if tag in ("pre", "code") or "background" in style:
            assert "font-size:" in style, (tag, style)


def test_mono_constant_is_attribute_safe():
    assert '"' not in mf._MONO
