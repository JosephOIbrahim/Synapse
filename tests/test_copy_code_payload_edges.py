"""Copy payload edges the first cut missed (review of 1f0e7136, B2 + N1).

B2: a lone surrogate in a code block made ``copy_href`` raise UnicodeEncodeError,
so ``format_response`` raised and the whole reply vanished from the transcript
(b78abfb0, before the Copy control existed, rendered it). A Copy control must
never cost the artist the message it sits on.

N1: a CRLF code block copied with a stray trailing ``\\r`` -- only the ``\\n``
before the closing fence was peeled.

Pure, Qt-free. The rendered-document + click half is in
tests/panel/test_copy_code_stream_and_surrogate.py.
"""
from __future__ import annotations

import base64
import re

import synapse
from synapse.panel import message_formatter as mf

print("synapse from", synapse.__file__)

_HREF = re.compile(r'href="(synapse-copy:[^"]*)"')


def _hrefs(html_text):
    return _HREF.findall(html_text)


def _stdlib_decode(href):
    """Decoded with the stdlib, not the module's helper, so a helper that agreed
    with a broken encoder cannot turn this green."""
    body = href[len("synapse-copy:"):]
    body += "=" * (-len(body) % 4)
    return base64.b64decode(body, altchars=b"-_", validate=True).decode(
        "utf-8", "surrogatepass")


LONE = "x = '\ud800'\ny = 'a\udcffb'"


def test_lone_surrogate_formats_without_raising():
    out = mf.format_response("Here:\n```python\n" + LONE + "\n```\nTail END.")
    assert "Tail END." in out
    assert len(_hrefs(out)) == 1


def test_lone_surrogate_round_trips_exactly():
    out = mf.format_response("```\n" + LONE + "\n```")
    (href,) = _hrefs(out)
    assert _stdlib_decode(href) == LONE
    assert mf.decode_copy_href(href) == LONE
    assert mf.decode_copy_href(mf.copy_href(LONE)) == LONE


def test_crlf_block_copies_without_trailing_cr():
    out = mf.format_response("Here:\r\n```c\r\nint a = 1;\r\nint b = 2;\r\n```\r\nDone.")
    (href,) = _hrefs(out)
    assert _stdlib_decode(href) == "int a = 1;\r\nint b = 2;"


def test_lf_block_still_keeps_an_intentional_blank_line():
    out = mf.format_response("```\nint a = 1;\n\n```")
    (href,) = _hrefs(out)
    assert _stdlib_decode(href) == "int a = 1;\n"
