"""Convert SYNAPSE responses to styled HTML for the chat display.

Mile 3 (Pentagram pass) — *speakers are told apart by type, not bubbles.*
The human voice carries a single signal-blue hairline rule and brighter text;
the agent voice is plain, dimmer body copy with no chrome. Node references
render as **artifact chips** — a node mark + mono path, a thing you can click,
not a sentence. Signal blue is the one chromatic event; it comes from the
vendored design system (#8FB3D9), not the legacy cyan.

Public surface is unchanged (chat_display.py depends on it):
``format_response``, ``format_user_message``, ``format_synapse_message``,
``format_system_message``, ``format_timestamp_divider``.
"""

import html
import re

# -- Design tokens — the vendored single source of truth.
#    The literal fallback that used to sit behind this import is gone. It held
#    a full second copy of the palette, and a copy drifts: it was written when
#    these values were current and had no way to follow the seeded ramp, so on
#    any host but the default it painted the WRONG greys while reporting
#    success. One authority means one, including in the degraded path.
from synapse.panel.designsystem import tokens as _t

_SIGNAL      = _t.SIGNAL          # the one chromatic event
_TEXT        = _t.TEXT_PRIMARY    # agent voice / body
_TEXT_BRIGHT = _t.TEXT_BRIGHT     # human voice (emphasis)
_TEXT_DIM    = _t.TEXT_TERTIARY   # system lines / captions
_GROUND      = _t.GROUND          # chip + code-block inset
_LINE        = _t.GRAPHITE        # hairline borders
_ERROR       = _t.ERROR
_WARNING     = _t.WARN
_SUCCESS     = _t.GROW
_BODY_PX     = _t.SIZE_BODY
_SMALL_PX    = _t.SIZE_SMALL
_LABEL_PX    = _t.SIZE_LABEL
_GROUP_MARGIN_Y = _t.SPACE_MD
_MSG_MARGIN_Y   = _t.SPACE_XS
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
                 mono=_MONO, lang=lang)
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
    state = {"signed_used": False}

    def _node(m):
        return _format_node_path(m, font_scale, signed=None)

    raw = _CODE_BLOCK_RE.sub(lambda m: _format_code_block(m, font_scale), raw)
    raw = _INLINE_CODE_RE.sub(lambda m: _format_inline_code(m, font_scale), raw)
    raw = _NODE_PATH_RE.sub(_node, raw)
    raw = _format_list_items(raw)

    # Newlines to <br> (but not inside <pre> blocks)
    parts = re.split(r"(<pre.*?</pre>)", raw, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith("<pre"):
            parts[i] = part.replace("\n", "<br>")
    return "".join(parts), state["signed_used"]


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
    #DEDEDE for the human, #C5C5C5 for the agent, plus a 2px rule on the human
    side. Twenty-five points of grey on a dim panel is not a speaker signal.
    The v9 design said "type and the rule tell the speaker apart"; in practice
    the reader has to infer, every message.

    Rendered as chrome, not content: mono, small, letterspaced, dim — so it
    reads as a label and never competes with what was said. Returns "" for a
    grouped message, which is what makes it Slack rather than a chat log.
    """
    sz = _scale(_SMALL_PX, font_scale)
    ts = ('<span style="color:{d}; font-size:{s}px;">&#160;&#160;{t}</span>'
          .format(d=_TEXT_DIM, s=max(sz - 1, 8), t=html.escape(timestamp))
          if timestamp else "")
    return ('<div style="font-family:{m}; font-size:{s}px; letter-spacing:1.2px; '
            'color:{c}; margin-bottom:3px;">{who}{ts}</div>').format(
        m=_MONO, s=sz, c=_TEXT_DIM, who=html.escape(who), ts=ts)


def format_user_message(text, grouped=False, timestamp=None, font_scale=1.0):
    """The human voice: a signal-blue hairline rule, brighter text, and a
    speaker label at the head of a group.

    A two-cell table carries the rule: QTextDocument paints table-cell
    backgrounds reliably where it ignores block ``border-left``.
    """
    escaped = html.escape(text).replace("\n", "<br>")
    body_sz = _scale(_BODY_PX, font_scale)
    my = _MSG_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    label = "" if grouped else _speaker_label("YOU", timestamp, font_scale)
    escaped = label + escaped
    # v9 comp .you: 2px SIGNAL rule · 14px gap · bright text at 1.5 line-height
    # (line-height is best-effort — harmless if the QTextDocument subset drops it).
    return (
        '<table border="0" cellspacing="0" cellpadding="0" width="100%" '
        'style="margin:{my}px 0;"><tr>'
        '<td width="2" style="background:{sig};"></td>'
        '<td width="14"></td>'
        '<td style="color:{fg}; font-size:{sz}px; line-height:150%;">{body}</td>'
        "</tr></table>"
    ).format(my=my, sig=_SIGNAL, fg=_TEXT_BRIGHT, sz=body_sz, body=escaped)


def format_synapse_message(content, grouped=False, timestamp=None, font_scale=1.0,
                           signed=None):
    """The agent voice: plain, dimmer body copy — no rule, no bubble, no label.
    Results inside it surface as artifact chips via the rich-text pipeline.

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
    return '<div style="margin:{my}px 0;">{label}{body}{note}</div>'.format(
        my=my, label=label, body=body, note=note)


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
