"""Convert SYNAPSE responses to styled HTML for the chat display.

Mile 3 (Pentagram pass) — *speakers are told apart by type, not bubbles.*
J3 (RULING_JOE_FIVE, 2026-09-05) — *and by one colour each.* Every turn leads
with a 2px hairline rule and, at the head of a group, a label (dot + name) in
its speaker's colour: USER = SIGNAL, SYNAPSE = CONIFEROUS. Body copy keeps its
text-ramp colour on both sides; no bubbles, no chrome. Node references render
as **artifact chips** — a node mark + mono path, a thing you can click, not a
sentence. One accent for actions (SIGNAL, the artist's next move) and two
speaker marks; every colour comes from the vendored design system, never the
legacy cyan, never a new hex.

Public surface is unchanged (chat_display.py depends on it):
``format_response``, ``format_user_message``, ``format_synapse_message``,
``format_system_message``, ``format_timestamp_divider``.
"""

import html
import re
from urllib.parse import urlsplit


class TrustedHtml(str):
    """Explicit opt-in for HTML authored by application code, never model prose."""

# -- Design tokens — the vendored single source of truth.
#    The literal fallback that used to sit behind this import is gone. It held
#    a full second copy of the palette, and a copy drifts: it was written when
#    these values were current and had no way to follow the seeded ramp, so on
#    any host but the default it painted the WRONG greys while reporting
#    success. One authority means one, including in the degraded path.
from synapse.panel.designsystem import tokens as _t

_SIGNAL      = _t.SIGNAL          # the accent: actions, chips, the artist
_TEXT        = _t.TEXT_PRIMARY    # agent voice / body
_TEXT_BRIGHT = _t.TEXT_BRIGHT     # human voice (emphasis)
_TEXT_DIM    = _t.TEXT_TERTIARY   # system lines / captions / timestamps
# J3: one colour per speaker, decided HERE and nowhere else. The label (dot +
# name) and the turn's leading rule both take it; body text never does.
#   YOU     -> SIGNAL      the accent already means "the artist"
#   SYNAPSE -> CONIFEROUS  4.58:1 on GROUND (>= 4.5 AA at SIZE_BODY 12 / 500).
#              MUSHROOM measured 4.64:1 but its chroma is exactly 24 - not
#              > 24 - so the panel's own chromatic predicate reads it as grey,
#              which is the complaint this fixes. WARM (the busy mark) leaves
#              the transcript: one hue means "SYNAPSE, alive" everywhere.
_SPEAKER = {"YOU": _t.SIGNAL, "SYNAPSE": _t.CONIFEROUS}
_GROUND      = _t.GROUND          # chip + code-block inset
_LINE        = _t.GRAPHITE        # hairline borders
_ERROR       = _t.ERROR
_WARNING     = _t.WARN
_SUCCESS     = _t.GROW
_BODY_PX     = _t.SIZE_BODY
_SMALL_PX    = _t.SIZE_SMALL
_LABEL_PX    = _t.SIZE_LABEL
# Dialogue rhythm. 1.5x the previous values, because the chat read tight.
#
# The obvious lever - line-height:150% - was already in this file, marked
# "best-effort", and it has never done anything: QTextDocument's HTML subset
# does not implement CSS line-height. I then tried QTextBlockFormat with
# ProportionalHeight three ways, measured each, and the document height came
# back IDENTICAL at 1.0 and 1.5 every time. Qt is not giving us intra-paragraph
# leading in a QTextEdit, and no amount of restating it will.
#
# BLOCK MARGINS Qt does honour, and they are most of what "tight" actually
# means in a dialogue: the air BETWEEN turns, not between wrapped lines. So the
# rhythm is bought where the mechanism is real rather than where the CSS
# analogy suggested.
_GROUP_MARGIN_Y = _t.SPACE_LG           # 24 - between speakers (was SPACE_MD 16)
_MSG_MARGIN_Y   = _t.SPACE_SM           # 8  - between a speaker's own lines (was 4)
_TIMESTAMP_SZ   = _t.SIZE_LABEL

# Monospace font stack for genuine code/paths — a NEUTRAL host monospace
# (Consolas/Courier on Windows), not the designed Space Mono, so code reads as
# native Houdini rather than web-app type. Body/prose carry no family (inherit).
_MONO = "'Consolas', 'Courier New', monospace"

# Regex patterns
_CODE_BLOCK_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
# Houdini node-network roots + the USD prim roots the comp surfaces as artifacts
# (/materials/AMD/Dark_Glass, /Render/Products/...). Curated, not a catch-all,
# so prose slashes don't accidentally become chips.
_NODE_PATH_RE = re.compile(
    r"(/(?:obj|out|stage|shop|mat|ch|tasks|vex|"
    r"materials|Render|World|cameras|lights|geo)/[\w/]+)"
)
_LIST_ITEM_RE = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)


def _scale(px, font_scale=1.0):
    """Scale a pixel value by font_scale, return int."""
    return int(round(px * font_scale))


def _status_prefix(status):
    """Return a colored Unicode dot for status strings (the only place status
    hues appear — body copy stays neutral)."""
    if status in ("ok", "success"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_SUCCESS)
    if status in ("warning", "warn"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_WARNING)
    if status in ("error", "fail"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_ERROR)
    return ""


def _format_code_block(match, font_scale=1.0):
    """Render a fenced code block as a quiet inset (no heavy chrome)."""
    lang = match.group(1) or ""
    code = html.escape(match.group(2).rstrip())
    lang_label = ""
    if lang:
        lang_label = (
            '<div style="color:{dim}; font-size:{sz}px; '
            'margin-bottom:4px; font-family:{mono};">{lang}</div>'
        ).format(dim=_TEXT_DIM, sz=_scale(_SMALL_PX, font_scale),
                 mono=_MONO, lang=html.escape(lang))
    return (
        '<div style="background:{bg}; padding:10px; margin:6px 0;">'
        "{label}"
        '<pre style="margin:0; color:{fg}; font-family:{mono}; '
        'font-size:{sz}px; white-space:pre-wrap;">{code}</pre>'
        "</div>"
    ).format(
        bg=_GROUND, fg=_TEXT, mono=_MONO,
        sz=_scale(_SMALL_PX, font_scale), label=lang_label, code=code,
    )


def _format_inline_code(match, font_scale=1.0):
    """Render `inline code` as mono signal text — a thing named in the line,
    no bubble (matches the comp's `.code`)."""
    code = html.escape(match.group(1))
    return (
        '<code style="color:{fg}; font-family:{mono}; font-size:{sz}px;">'
        "{code}</code>"
    ).format(
        fg=_SIGNAL, mono=_MONO, sz=_scale(_SMALL_PX, font_scale), code=code,
    )


def _format_node_path(match, font_scale=1.0, signed=None):
    """Render a Houdini node path as a clickable **artifact chip** — a node
    mark + the mono path, a thing rather than a sentence fragment. The
    ``node:`` href keeps click-to-locate (ChatDisplay.node_clicked) intact.
    ``signed`` (v9 comp) appends a quiet ``· signed <model>`` authorship
    suffix inside the chip — display-only, once per message."""
    path = match.group(1)
    sz = _scale(_SMALL_PX, font_scale)
    note = ""
    if signed:
        note = (
            '&#160;&#183;&#160;<span style="color:{dim}; '
            'font-size:{ssz}px;">signed {who}</span>'
        ).format(dim=_TEXT_DIM, ssz=_scale(10, font_scale),
                 who=html.escape(str(signed)))
    return (
        '<a href="node:{path}" style="text-decoration:none;">'
        '<span style="background:{bg}; font-family:{mono}; font-size:{sz}px;">'
        '<span style="color:{mark};">&#9642;</span> '
        '<span style="color:{fg};">{path}</span>'
        "{note}&#160;</span></a>"
    ).format(
        path=path, bg=_GROUND, mark=_SIGNAL, fg=_TEXT_BRIGHT,
        mono=_MONO, sz=sz, note=note,
    )


def _format_list_items(text):
    """Wrap runs of consecutive list items in <ul>, IN PLACE.

    2026-07-27, found on a live 2,727-node explain of karma_user_guide.hip:
    sections rendered EMPTY and every bullet appeared as one block at the bottom
    of the message.

    The previous implementation harvested every list item in the whole message
    with findall(), deleted them all with sub(""), and appended a single <ul> at
    the end. The bullets survived; their POSITION and their GROUPING did not. A
    message with three bulleted sections became three empty headings followed by
    one undifferentiated list - which is worse than no formatting, because the
    structure the answer was carrying is exactly what got destroyed.

    Now: walk line by line, and close a <ul> the moment the run of list items
    ends. A bullet renders between the heading it follows and the heading that
    follows it, which is the only property that matters here.
    """
    lines = text.split("\n")
    out = []
    run = []

    def _flush():
        if not run:
            return
        out.append('<ul style="margin:4px 0; padding-left:20px;">'
                   + "".join("<li>{}</li>".format(i) for i in run)
                   + "</ul>")
        run.clear()

    for line in lines:
        m = _LIST_ITEM_RE.match(line.strip())
        if m:
            # group(1) when the pattern captures the item body, else the line
            run.append(m.group(1) if m.groups() else line.strip())
        else:
            _flush()
            out.append(line)
    _flush()
    return "\n".join(out)


def _inline_markdown(text, font_scale):
    """Render text once; never run substitutions through generated HTML/code."""
    atom = re.compile(r"(`[^`\n]+`|\[[^\]\n]+\]\([^\s)]+\)|" + _NODE_PATH_RE.pattern + r")")

    def prose(value):
        value = html.escape(value)
        value = re.sub(r"\*\*([^*\n]+)\*\*", r"<strong>\1</strong>", value)
        value = re.sub(r"(?<!\w)__([^_\n]+)__(?!\w)", r"<strong>\1</strong>", value)
        value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", value)
        return value

    out, pos = [], 0
    for match in atom.finditer(text):
        out.append(prose(text[pos:match.start()]))
        value = match.group(0)
        if value.startswith("`"):
            out.append(_format_inline_code(_INLINE_CODE_RE.fullmatch(value), font_scale))
        elif value.startswith("["):
            label, url = re.fullmatch(r"\[([^\]]+)\]\(([^)]+)\)", value).groups()
            try:
                parsed = urlsplit(url)
                safe = parsed.scheme in ("https", "http") and parsed.hostname and not parsed.username
            except ValueError:
                safe = False
            out.append('<a href="%s">%s</a>' % (html.escape(url, quote=True), html.escape(label))
                       if safe else html.escape(value))
        else:
            out.append(_format_node_path(_NODE_PATH_RE.fullmatch(value), font_scale))
        pos = match.end()
    out.append(prose(text[pos:]))
    return "".join(out)


def _markdown_blocks(raw, font_scale):
    out, paragraph, items = [], [], []
    list_kind = None

    def flush_paragraph():
        if paragraph:
            out.append('<p style="margin:6px 0;">' + "<br>".join(paragraph) + "</p>")
            paragraph.clear()

    def flush_list():
        if items:
            out.append('<%s style="margin:4px 0;">' % list_kind +
                       "".join("<li>%s</li>" % item for item in items) + '</%s>' % list_kind)
            items.clear()

    for line in raw.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        item = re.match(r"^\s*(?:([-+*])|\d+[.)])\s+(.+)$", line)
        if item:
            flush_paragraph()
            kind = "ul" if item.group(1) else "ol"
            if kind != list_kind:
                flush_list()
                list_kind = kind
            items.append(_inline_markdown(item.group(2), font_scale))
        else:
            flush_list()
            if heading:
                flush_paragraph()
                n = len(heading.group(1))
                out.append('<h{n} style="font-size:{sz}px; margin:10px 0 4px;">{text}</h{n}>'.format(
                    n=n, sz=_scale(_BODY_PX + max(0, 4 - n), font_scale),
                    text=_inline_markdown(heading.group(2), font_scale)))
            elif not line.strip():
                flush_paragraph()
            else:
                paragraph.append(_inline_markdown(line, font_scale))
    flush_list()
    flush_paragraph()
    return "".join(out)


def _process_rich_text(raw, font_scale=1.0, signed=None):
    """Apply code block, inline code, node-chip, and list formatting. Returns
    ``(html, signed_used)``.

    2026-07-27, found on a live 2,727-node explain of karma_user_guide.hip:
    the v9 design attached the authorship suffix to the FIRST node chip in a
    message. That chip is wherever the first node path happens to fall - and on
    a structured answer it fell INSIDE A MARKDOWN TABLE CELL, rendering as
    ``/stage/lights - signed GLM 5.2`` mid-table. It reads as a text bug rather
    than a credit.

    Two docstrings described this feature differently: chat_display.py said
    "shown once at the head of a SYNAPSE group", this module said "the FIRST
    node chip carries the suffix". The implementation followed the second. The
    first is the better behaviour and the standalone note that renders it
    already existed as the fallback.

    So: chips never take the signature now, `signed_used` is always False, and
    the caller's standalone note always renders. Credit belongs to the message,
    not to whichever path was mentioned first.
    """
    if isinstance(raw, TrustedHtml):
        return str(raw), False
    parts = re.split(r"(```[^\n]*\n.*?```)", str(raw), flags=re.DOTALL)
    for i, part in enumerate(parts):
        if i % 2:
            match = re.fullmatch(r"```([^\n]*)\n(.*?)```", part, flags=re.DOTALL)
            parts[i] = _format_code_block(match, font_scale)
        else:
            parts[i] = _markdown_blocks(part, font_scale)
    return "".join(parts), False


def _format_response_ex(response, font_scale=1.0, signed=None):
    """format_response + ``signed_used`` (did a node chip carry the authorship
    suffix?). Internal — the public surface stays unchanged."""
    if isinstance(response, str):
        raw = response
        status = None
    else:
        raw = (
            response.get("message")
            or response.get("result")
            or response.get("content")
            or response.get("text")
            or str(response)
        )
        status = response.get("status")

    raw, signed_used = _process_rich_text(raw, font_scale, signed=signed)
    prefix = _status_prefix(status) if status else ""

    return (
        '<div style="color:{fg}; font-size:{sz}px;">{prefix}{body}</div>'
    ).format(
        fg=_TEXT, sz=_scale(_BODY_PX, font_scale), prefix=prefix, body=raw,
    ), signed_used


def format_response(response, font_scale=1.0):
    """Convert a SYNAPSE response (dict or str) to styled HTML.

    The agent voice: neutral body copy, no chrome. Node refs become artifact
    chips; a status, if present, leads with a single colored dot.
    """
    return _format_response_ex(response, font_scale)[0]


def _speaker_label(who, timestamp, font_scale):
    """Slack's actual dialogue anatomy: a NAME at the head of a group, the time
    beside it, and nothing repeated on continuations.

    Measured 2026-07-27, the only thing separating the two voices was tone —
    TEXT_BRIGHT for the human, TEXT_PRIMARY for the agent, plus a 2px rule on the human
    side. Twenty-five points of grey on a dim panel is not a speaker signal.
    The v9 design said "type and the rule tell the speaker apart"; in practice
    the reader has to infer, every message.

    A COLOURED DOT leads the label, because tone alone still asks the reader
    to compare. J3 (2026-09-05): the dot alone was not enough either — the
    widget's label pass painted the whole block one grey over it and Joe read
    "grey for both". So the NAME carries the speaker colour too (``_SPEAKER``:
    YOU = SIGNAL, SYNAPSE = CONIFEROUS), the dot beside it, and only the
    timestamp stays dim. The dot is a text glyph rather than a styled box:
    QTextDocument's HTML subset drops background-colour and border-radius on
    inline spans, so a coloured bullet is the shape that actually survives.

    Rendered as chrome, not content: mono, small, letterspaced — so it reads
    as a label and never competes with what was said. Callers pass "" for a
    grouped message, which is what makes it Slack rather than a chat log.
    """
    sz = _scale(_SMALL_PX, font_scale)
    ts = ('<span style="color:{d}; font-size:{s}px;">&#160;&#160;{t}</span>'
          .format(d=_TEXT_DIM, s=max(sz - 1, 8), t=html.escape(timestamp))
          if timestamp else "")
    colour = _speaker_colour(who)
    dot = ('<span style="color:{c}; font-size:{s}px;">&#9679;</span>&#160;&#160;'
           .format(c=colour, s=sz))
    return ('<div style="font-family:{m}; font-size:{s}px; letter-spacing:1.2px; '
            'color:{c}; margin-bottom:3px;">{dot}{who}{ts}</div>').format(
        m=_MONO, s=sz, c=colour, dot=dot, who=html.escape(who), ts=ts)


def _speaker_colour(who):
    """The one place a speaker's colour is decided (J3)."""
    return _SPEAKER["SYNAPSE" if str(who).upper().startswith("SYNAPSE") else "YOU"]


def _ruled_turn(body, rule, fg, body_sz, my):
    """The turn anatomy both voices share: a 2px rule in the SPEAKER's colour ·
    14px gap · body (the v9 comp's ``.you``, extended to SYNAPSE by J3 so each
    turn leads with its speaker's mark). A two-cell table carries the rule:
    QTextDocument paints table-cell backgrounds reliably where it ignores block
    ``border-left``. ``line-height`` is best-effort — harmless if the
    QTextDocument subset drops it."""
    return (
        '<table border="0" cellspacing="0" cellpadding="0" width="100%" '
        'style="margin:{my}px 0;"><tr>'
        '<td width="2" style="background:{rule};"></td>'
        '<td width="14"></td>'
        '<td style="color:{fg}; font-size:{sz}px; line-height:150%;">{body}</td>'
        "</tr></table>"
    ).format(my=my, rule=rule, fg=fg, sz=body_sz, body=body)


def format_user_message(text, grouped=False, timestamp=None, font_scale=1.0):
    """The human voice: a SIGNAL hairline rule, brighter text, and a speaker
    label at the head of a group (``_ruled_turn`` carries the anatomy)."""
    escaped = html.escape(text).replace("\n", "<br>")
    body_sz = _scale(_BODY_PX, font_scale)
    my = _MSG_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    label = "" if grouped else _speaker_label("YOU", timestamp, font_scale)
    return _ruled_turn(label + escaped, _SPEAKER["YOU"], _TEXT_BRIGHT, body_sz, my)


def format_synapse_message(content, grouped=False, timestamp=None, font_scale=1.0,
                           signed=None):
    """The agent voice: plain body copy behind a CONIFEROUS hairline rule, with
    a speaker label at the head of a group — no bubble. J3 gave it the same
    turn anatomy as the human voice (``_ruled_turn``) so the speaker reads
    without reading. Results inside it surface as artifact chips via the
    rich-text pipeline.

    ``signed`` adds a quiet, display-only authorship note (the model that
    produced the result) once at the head of a SYNAPSE group — never per
    message. It is a label, not a substrate write. v9: when the result carries
    a node chip, the FIRST chip carries the ``signed`` suffix (comp anatomy);
    otherwise the standalone note renders as before — exactly one either way."""
    body, chip_signed = _format_response_ex(
        content, font_scale, signed=None if grouped else signed)
    my = _MSG_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    label = "" if grouped else _speaker_label("SYNAPSE", timestamp, font_scale)
    note = ""
    if signed and not grouped and not chip_signed:
        note = (
            '<div style="color:{dim}; font-size:{sz}px; letter-spacing:1px; '
            'margin-top:2px;">signed {who}</div>'
        ).format(dim=_TEXT_DIM, sz=_scale(_SMALL_PX, font_scale),
                 who=html.escape(str(signed)))
    return _ruled_turn(label + body + note, _SPEAKER["SYNAPSE"], _TEXT,
                       _scale(_BODY_PX, font_scale), my)


def format_system_message(text, font_scale=1.0):
    """A quiet, centered status interjection (not a speaker)."""
    escaped = html.escape(text)
    return (
        '<div style="text-align:center; color:{dim}; font-size:{sz}px; '
        'margin:6px 0; font-style:italic;">{text}</div>'
    ).format(dim=_TEXT_DIM, sz=_scale(_SMALL_PX, font_scale), text=escaped)


def format_timestamp_divider(timestamp_text, font_scale=1.0):
    """Group breaks are carried by negative space now, not timestamp chrome.
    Returns empty — kept so ChatDisplay's grouping call site is unchanged."""
    return ""
