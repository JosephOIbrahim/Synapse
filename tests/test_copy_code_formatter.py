"""Every fenced code block carries a Copy control whose payload IS the code.

WHY THIS FILE EXISTS. Joe, 2026-10-07: "SYNAPSE needs a COPY button the way Claude
Desktop has a copy button, if an artist wants to copy code from SYNAPSE to another
parameter in Houdini manually." Drag-selecting a wrangle out of the transcript picks
up the language label and loses nothing visible -- until a tab or a trailing space
goes missing in a VEX snippet and the parameter no longer compiles. The button has
to hand over the code exactly as it was written.

These are the pure, Qt-free half: the formatter runs on a worker thread, so the
payload must live in the HTML itself (no registry). The rendered-document half,
and the click -> clipboard path, live in tests/panel/test_copy_code_anchor.py.

The payload is decoded here with the stdlib, NOT with the module's own helper, so
a helper that agreed with a broken encoder could not turn this file green.
"""
from __future__ import annotations

import base64
import binascii
import re

import pytest

from synapse.panel import message_formatter as mf

_HREF = re.compile(r'href="(synapse-copy:[^"]*)"')


def _hrefs(html_text):
    return _HREF.findall(html_text)


def _stdlib_decode(href):
    body = href[len("synapse-copy:"):]
    body += "=" * (-len(body) % 4)
    return base64.b64decode(body, altchars=b"-_", validate=True).decode("utf-8")


CODES = {
    "tabs": "int n = 3;\n\tfor (int i = 0; i < n; i++)\n\t\tv@P.y += 0.1;",
    "vex_quotes_lt_gt_amp": ('if (@P.y < 0 && s@name != "a&b") {\n'
                             '    i@hit = @ptnum > 10 ? 1 : 0;  // <tag>\n}'),
    "trailing_spaces": "float a = 1.0;   \nfloat b = 2.0;  ",
    "unicode": 's@label = "naïve → ✓ 日本";',
    "python_indent": 'import hou\nfor p in hou.node("/obj/geo1").parms():\n    print(p.name())',
    "blank_lines_inside": "a = 1\n\n\nb = 2",
}


@pytest.mark.parametrize("name", sorted(CODES))
def test_payload_decodes_to_exact_code(name):
    code = CODES[name]
    out = mf.format_response("Here:\n```vex\n" + code + "\n```\nDone.")
    hrefs = _hrefs(out)
    assert len(hrefs) == 1, hrefs
    assert _stdlib_decode(hrefs[0]) == code


def test_one_anchor_per_fenced_block_in_order():
    first, second = CODES["tabs"], CODES["python_indent"]
    out = mf.format_response("```vex\n" + first + "\n```\nthen\n```python\n"
                             + second + "\n```\n")
    hrefs = _hrefs(out)
    assert [_stdlib_decode(h) for h in hrefs] == [first, second]


def test_block_without_language_still_gets_copy():
    out = mf.format_response("```\necho hi\n```")
    hrefs = _hrefs(out)
    assert [_stdlib_decode(h) for h in hrefs] == ["echo hi"]


def test_inline_code_gets_no_copy_control():
    out = mf.format_response("Set `@P.y += 1;` on the wrangle at /obj/geo1/attribwrangle1.")
    assert _hrefs(out) == []
    assert "synapse-copy" not in out
    assert ">Copy<" not in out


def test_language_label_stays_left_of_copy():
    out = mf.format_response("```vex\nv@P.y = 1;\n```")
    assert ">vex<" in out
    assert out.index(">vex<") < out.index(">Copy<") < out.index("<pre")


def test_payload_is_url_safe_and_unpadded():
    # A '+', '/' or '=' would be fair game for URL normalisation on the way back
    # through QUrl; the alphabet is restricted so the round trip is not a gamble.
    out = mf.format_response("```vex\n" + "\xff?>>>" * 40 + "\n```")
    body = _hrefs(out)[0][len("synapse-copy:"):]
    assert re.fullmatch(r"[A-Za-z0-9_-]*", body), body


def test_code_body_still_escaped_and_free_of_anchors():
    out = mf.format_response('```vex\ns@x = "<a href=\'node:/obj\'>";\n```')
    pre = out.split("<pre", 1)[1].split("</pre>", 1)[0]
    assert "<a " not in pre
    assert "&lt;a href=" in pre


def test_copy_label_uses_tokens_not_new_hex():
    out = mf.format_response("```vex\nv@P.y = 1;\n```")
    header = out[out.index("<table"):out.index("<pre")]   # the header row only
    used = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}", header)}
    allowed = {mf._GROUND.upper(), mf._TEXT_DIM.upper()}
    assert used <= allowed, used - allowed


# -- the pure decode helper chat_display uses --------------------------------

@pytest.mark.parametrize("name", sorted(CODES))
def test_decode_helper_round_trips(name):
    code = CODES[name]
    href = _hrefs(mf.format_response("```\n" + code + "\n```"))[0]
    assert mf.decode_copy_href(href) == code


@pytest.mark.parametrize("href", [
    "synapse-copy:!!!!",
    "synapse-copy:abc$def",
    "synapse-copy:a",                                   # impossible length
    "synapse-copy:" + base64.urlsafe_b64encode(b"\xff\xfe\xfd").decode().rstrip("="),
    "node:/obj/geo1",
    "https://example.com/x",
    "",
    None,
])
def test_decode_helper_rejects_malformed(href):
    assert mf.decode_copy_href(href) is None


def test_decode_helper_accepts_empty_block():
    assert mf.decode_copy_href("synapse-copy:") == ""


# -- export paths read raw messages, never the rendered control ---------------

def test_transcript_export_carries_no_copy_control():
    # dnd imports Qt at module level, so this runs under hython and skips on
    # stock CPython; transcript_to_markdown itself is pure.
    dnd = pytest.importorskip("synapse.panel.dnd")
    md = dnd.transcript_to_markdown([
        {"role": "user", "content": "wrangle please"},
        {"role": "assistant", "content": "```vex\nv@P.y += 1;\n```"},
    ])
    assert "synapse-copy" not in md
    assert "Copy" not in md
    assert "```vex\nv@P.y += 1;\n```" in md


def test_decision_log_strip_carries_no_copy_control():
    from synapse.panel import decision_log
    text = decision_log._strip_markdown("Use this:\n```vex\nv@P.y += 1;\n```\nok")
    assert "synapse-copy" not in text and "Copy" not in text


def test_formatter_module_stays_qt_free():
    # The payload lives in the HTML precisely so the formatter can keep running
    # on the worker thread; a Qt import here would undo that.
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(mf))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    assert not names & {"PySide6", "PySide2", "hou", "hdefereval"}, names


def test_binascii_is_what_malformed_raises():
    # Pins the stdlib behaviour decode_copy_href relies on catching.
    with pytest.raises(binascii.Error):
        base64.b64decode("abc$", altchars=b"-_", validate=True)
