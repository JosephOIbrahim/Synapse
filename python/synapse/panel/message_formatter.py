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

# -- Design tokens — the vendored single source of truth (the chrome's blue,
#    not the legacy panel.tokens cyan). Robust literal fallback keeps the
#    formatter working if the package path is unavailable (runtime contract).
try:
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
    _FONT_MONO   = _t.FONT_MONO
    _BODY_PX     = _t.SIZE_BODY
    _SMALL_PX    = _t.SIZE_SMALL
    _LABEL_PX    = _t.SIZE_LABEL
    _GROUP_MARGIN_Y = _t.SPACE_MD
    _MSG_MARGIN_Y   = _t.SPACE_XS
    _TIMESTAMP_SZ   = _t.SIZE_LABEL
except Exception:  # pragma: no cover - exercised only without the package path
    _SIGNAL = "#8FB3D9"
    _TEXT = "#ADADAD"
    _TEXT_BRIGHT = "#C4C4C4"
    _TEXT_DIM = "#5E5E5E"
    _GROUND = "#262626"
    _LINE = "#2A2A2A"
    _ERROR = "#FF3D71"
    _WARNING = "#FFAB00"
    _SUCCESS = "#00E676"
    _FONT_MONO = "JetBrains Mono"
    _BODY_PX = 12
    _SMALL_PX = 14
    _LABEL_PX = 13
    _GROUP_MARGIN_Y = 16
    _MSG_MARGIN_Y = 4
    _TIMESTAMP_SZ = 13

# Monospace font stack
_MONO = "'{mono}', 'Consolas', 'Courier New', monospace".format(mono=_FONT_MONO)

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


def _format_node_path(match, font_scale=1.0):
    """Render a Houdini node path as a clickable **artifact chip** — a node
    mark + the mono path, a thing rather than a sentence fragment. The
    ``node:`` href keeps click-to-locate (ChatDisplay.node_clicked) intact."""
    path = match.group(1)
    sz = _scale(_SMALL_PX, font_scale)
    return (
        '<a href="node:{path}" style="text-decoration:none;">'
        '<span style="background:{bg}; font-family:{mono}; font-size:{sz}px;">'
        '<span style="color:{mark};">&#9642;</span> '
        '<span style="color:{fg};">{path}</span>'
        "&#160;</span></a>"
    ).format(
        path=path, bg=_GROUND, mark=_SIGNAL, fg=_TEXT_BRIGHT,
        mono=_MONO, sz=sz,
    )


def _format_list_items(text):
    """Convert markdown-style list items to HTML <ul>."""
    items = _LIST_ITEM_RE.findall(text)
    if not items:
        return text
    ul_html = "<ul style=\"margin:4px 0; padding-left:20px;\">"
    for item in items:
        ul_html += "<li>{}</li>".format(item)
    ul_html += "</ul>"
    return _LIST_ITEM_RE.sub("", text).rstrip() + ul_html


def _process_rich_text(raw, font_scale=1.0):
    """Apply code block, inline code, node-chip, and list formatting."""
    raw = _CODE_BLOCK_RE.sub(lambda m: _format_code_block(m, font_scale), raw)
    raw = _INLINE_CODE_RE.sub(lambda m: _format_inline_code(m, font_scale), raw)
    raw = _NODE_PATH_RE.sub(lambda m: _format_node_path(m, font_scale), raw)
    raw = _format_list_items(raw)

    # Newlines to <br> (but not inside <pre> blocks)
    parts = re.split(r"(<pre.*?</pre>)", raw, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith("<pre"):
            parts[i] = part.replace("\n", "<br>")
    return "".join(parts)


def format_response(response, font_scale=1.0):
    """Convert a SYNAPSE response (dict or str) to styled HTML.

    The agent voice: neutral body copy, no chrome. Node refs become artifact
    chips; a status, if present, leads with a single colored dot.
    """
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

    raw = _process_rich_text(raw, font_scale)
    prefix = _status_prefix(status) if status else ""

    return (
        '<div style="color:{fg}; font-size:{sz}px;">{prefix}{body}</div>'
    ).format(
        fg=_TEXT, sz=_scale(_BODY_PX, font_scale), prefix=prefix, body=raw,
    )


def format_user_message(text, grouped=False, timestamp=None, font_scale=1.0):
    """The human voice: a single signal-blue hairline rule + brighter text.
    No bubble, no label — type and the rule tell the speaker apart.

    A two-cell table carries the rule: QTextDocument paints table-cell
    backgrounds reliably where it ignores block ``border-left``. ``timestamp``
    is accepted for signature compatibility but no longer rendered (taut).
    """
    escaped = html.escape(text).replace("\n", "<br>")
    body_sz = _scale(_BODY_PX, font_scale)
    my = _MSG_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    return (
        '<table border="0" cellspacing="0" cellpadding="0" width="100%" '
        'style="margin:{my}px 0;"><tr>'
        '<td width="2" style="background:{sig};"></td>'
        '<td width="10"></td>'
        '<td style="color:{fg}; font-size:{sz}px;">{body}</td>'
        "</tr></table>"
    ).format(my=my, sig=_SIGNAL, fg=_TEXT_BRIGHT, sz=body_sz, body=escaped)


def format_synapse_message(content, grouped=False, timestamp=None, font_scale=1.0):
    """The agent voice: plain, dimmer body copy — no rule, no bubble, no label.
    Results inside it surface as artifact chips via the rich-text pipeline."""
    body = format_response(content, font_scale)
    my = _MSG_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    return '<div style="margin:{my}px 0;">{body}</div>'.format(my=my, body=body)


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
