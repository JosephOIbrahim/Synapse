"""Convert SYNAPSE responses to styled HTML for QTextEdit rendering.

Handles plain text, code blocks (```python, ```vex), node paths
(/obj/geo1/scatter1), parameter names, lists, and status indicators.

Supports message grouping (WhatsApp-style), timestamps, and font scaling.
"""

import html
import re

# -- Design tokens (from canonical design system) -------------------------
try:
    from synapse.panel import tokens as _t
    _NEAR_BLACK = _t.NEAR_BLACK
    _CARBON = _t.CARBON
    _VOID = _t.VOID
    _GRAPHITE = _t.GRAPHITE
    _SIGNAL = _t.SIGNAL
    _TEXT = _t.TEXT
    _TEXT_DIM = _t.TEXT_DIM
    _ERROR = _t.ERROR
    _WARNING = _t.WARN
    _SUCCESS = _t.GROW
    _FONT_MONO = _t.FONT_MONO
    _FONT_SANS = _t.FONT_SANS
    _BODY_PX = _t.SIZE_BODY
    _SMALL_PX = _t.SIZE_SMALL
    _LABEL_PX = _t.SIZE_LABEL
    _BUBBLE_PAD = _t.CHAT_BUBBLE_PADDING
    _BUBBLE_RAD = _t.CHAT_BUBBLE_RADIUS
    _BUBBLE_MARGIN_Y = _t.CHAT_BUBBLE_MARGIN_Y
    _GROUP_MARGIN_Y = _t.CHAT_GROUP_MARGIN_Y
    _TIMESTAMP_SZ = _t.CHAT_TIMESTAMP_SIZE
except ImportError:
    _NEAR_BLACK = "#3C3C3C"
    _CARBON = "#333333"
    _VOID = "#252525"
    _GRAPHITE = "#222222"
    _SIGNAL = "#00D4FF"
    _TEXT = "#E0E0E0"
    _TEXT_DIM = "#999999"
    _ERROR = "#FF3D71"
    _WARNING = "#FFAB00"
    _SUCCESS = "#00E676"
    _FONT_MONO = "JetBrains Mono"
    _FONT_SANS = "DM Sans"
    _BODY_PX = 26
    _SMALL_PX = 22
    _LABEL_PX = 22
    _BUBBLE_PAD = 14
    _BUBBLE_RAD = 12
    _BUBBLE_MARGIN_Y = 2
    _GROUP_MARGIN_Y = 16
    _TIMESTAMP_SZ = 18

# Monospace font stack
_MONO = "'{mono}', 'Consolas', 'Courier New', monospace".format(mono=_FONT_MONO)

# Regex patterns
_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_NODE_PATH_RE = re.compile(r"(/(?:obj|out|stage|shop|mat|ch|tasks|vex)/[\w/]+)")
_LIST_ITEM_RE = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)


def _scale(px, font_scale=1.0):
    """Scale a pixel value by font_scale, return int."""
    return int(round(px * font_scale))


def _status_prefix(status):
    """Return a colored Unicode prefix for status strings."""
    if status in ("ok", "success"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_SUCCESS)
    if status in ("warning", "warn"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_WARNING)
    if status in ("error", "fail"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_ERROR)
    return ""


def _format_code_block(match, font_scale=1.0):
    """Render a fenced code block as a styled <pre>."""
    lang = match.group(1) or ""
    code = html.escape(match.group(2).rstrip())
    lang_label = ""
    if lang:
        lang_label = (
            '<div style="color:{dim}; font-size:{sz}px; '
            'margin-bottom:4px;">{lang}</div>'
        ).format(dim=_TEXT_DIM, sz=_scale(_SMALL_PX, font_scale), lang=lang)
    return (
        '<div style="background:{bg}; border-radius:6px; padding:10px; '
        'margin:6px 0;">'
        "{label}"
        '<pre style="margin:0; color:{fg}; font-family:{mono}; '
        'font-size:{sz}px; white-space:pre-wrap;">{code}</pre>'
        "</div>"
    ).format(
        bg=_NEAR_BLACK,
        fg=_TEXT,
        mono=_MONO,
        sz=_scale(_SMALL_PX, font_scale),
        label=lang_label,
        code=code,
    )


def _format_inline_code(match, font_scale=1.0):
    """Render `inline code` with styled background."""
    code = html.escape(match.group(1))
    return (
        '<code style="background:{bg}; color:{fg}; font-family:{mono}; '
        'padding:2px 5px; border-radius:3px; font-size:{sz}px;">'
        "{code}</code>"
    ).format(
        bg=_NEAR_BLACK, fg=_SIGNAL, mono=_MONO,
        sz=_scale(_SMALL_PX, font_scale), code=code,
    )


def _format_node_path(match, font_scale=1.0):
    """Render a Houdini node path as a clickable link."""
    path = match.group(1)
    return (
        '<a href="node:{path}" style="color:{c}; text-decoration:none; '
        'font-family:{mono}; font-size:{sz}px;">{path}</a>'
    ).format(
        path=path, c=_SIGNAL, mono=_MONO,
        sz=_scale(_SMALL_PX, font_scale),
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
    """Apply code block, inline code, node path, and list formatting."""
    raw = _CODE_BLOCK_RE.sub(
        lambda m: _format_code_block(m, font_scale), raw
    )
    raw = _INLINE_CODE_RE.sub(
        lambda m: _format_inline_code(m, font_scale), raw
    )
    raw = _NODE_PATH_RE.sub(
        lambda m: _format_node_path(m, font_scale), raw
    )
    raw = _format_list_items(raw)

    # Newlines to <br> (but not inside <pre> blocks)
    parts = re.split(r"(<pre.*?</pre>)", raw, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith("<pre"):
            parts[i] = part.replace("\n", "<br>")
    return "".join(parts)


def _timestamp_html(timestamp, font_scale=1.0):
    """Render a right-aligned dimmed timestamp below the message body."""
    if not timestamp:
        return ""
    return (
        '<div style="text-align:right; color:{dim}; font-size:{sz}px; '
        'margin-top:4px; font-family:{mono};">{ts}</div>'
    ).format(
        dim=_TEXT_DIM, sz=_scale(_TIMESTAMP_SZ, font_scale),
        mono=_MONO, ts=html.escape(str(timestamp)),
    )


def format_response(response, font_scale=1.0):
    """Convert a SYNAPSE response dict to styled HTML for QTextEdit.

    Parameters
    ----------
    response : dict or str
        If dict, expects optional keys: ``status``, ``message``, ``result``,
        ``content``, ``text``.  If str, treated as plain text.
    font_scale : float
        Multiplier for all font sizes (default 1.0).

    Returns
    -------
    str
        HTML fragment suitable for QTextEdit.insertHtml().
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
        '<div style="color:{fg}; font-size:{sz}px;">'
        "{prefix}{body}</div>"
    ).format(
        fg=_TEXT, sz=_scale(_BODY_PX, font_scale),
        prefix=prefix, body=raw,
    )


def format_user_message(text, grouped=False, timestamp=None, font_scale=1.0):
    """Format a user message bubble with WhatsApp-style spacing.

    Parameters
    ----------
    text : str
        The user's message text.
    grouped : bool
        If True, suppress sender label and use tight margin (same-sender continuation).
    timestamp : str or None
        Timestamp string to display below the message.
    font_scale : float
        Multiplier for all font sizes.

    Returns
    -------
    str
        HTML fragment for the user message bubble.
    """
    escaped = html.escape(text)
    escaped = escaped.replace("\n", "<br>")

    pad = _scale(_BUBBLE_PAD, font_scale)
    pad_h = _scale(_BUBBLE_PAD + 4, font_scale)  # Horizontal gets a bit more
    margin_y = _BUBBLE_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    body_sz = _scale(_BODY_PX, font_scale)
    label_sz = _scale(_SMALL_PX, font_scale)

    # WhatsApp-style directional radius: user bubbles rounded on left, flat top-right when grouped
    if grouped:
        radius = "{r}px {flat}px {r}px {r}px".format(
            r=_BUBBLE_RAD, flat=4
        )
    else:
        radius = "{r}px {r}px {r}px {r}px".format(r=_BUBBLE_RAD)

    sender_label = ""
    if not grouped:
        sender_label = (
            '<span style="color:{dim}; font-size:{sz}px; '
            'font-family:{mono}; letter-spacing:1px;">You</span><br>'
        ).format(dim=_TEXT_DIM, sz=label_sz, mono=_MONO)

    ts_html = _timestamp_html(timestamp, font_scale)

    return (
        '<div style="background:{bg}; border: 1px solid {border}; '
        'border-radius:{radius}; padding:{pad}px {padh}px; '
        'margin:{my}px 0 {my}px 40px; color:{fg}; font-size:{sz}px;">'
        '{label}{body}{ts}</div>'
    ).format(
        bg=_CARBON, border=_GRAPHITE, radius=radius,
        pad=pad, padh=pad_h, my=margin_y,
        fg=_TEXT, sz=body_sz, label=sender_label,
        body=escaped, ts=ts_html,
    )


def format_synapse_message(content, grouped=False, timestamp=None, font_scale=1.0):
    """Format a SYNAPSE response bubble with WhatsApp-style spacing.

    Parameters
    ----------
    content : dict or str
        Response payload from the server.
    grouped : bool
        If True, suppress sender label and use tight margin.
    timestamp : str or None
        Timestamp string to display below the message.
    font_scale : float
        Multiplier for all font sizes.

    Returns
    -------
    str
        HTML fragment for the synapse message bubble.
    """
    body = format_response(content, font_scale)

    pad = _scale(_BUBBLE_PAD, font_scale)
    pad_h = _scale(_BUBBLE_PAD + 4, font_scale)
    margin_y = _BUBBLE_MARGIN_Y if grouped else _GROUP_MARGIN_Y
    label_sz = _scale(_SMALL_PX, font_scale)

    # WhatsApp-style: synapse bubbles rounded on right, flat top-left when grouped
    if grouped:
        radius = "{flat}px {r}px {r}px {r}px".format(
            r=_BUBBLE_RAD, flat=4
        )
    else:
        radius = "{r}px {r}px {r}px {r}px".format(r=_BUBBLE_RAD)

    sender_label = ""
    if not grouped:
        sender_label = (
            '<span style="color:{accent}; font-size:{sz}px; '
            'font-weight:bold; font-family:{mono}; '
            'letter-spacing:2px;">SYNAPSE</span><br>'
        ).format(accent=_SIGNAL, sz=label_sz, mono=_MONO)

    ts_html = _timestamp_html(timestamp, font_scale)

    return (
        '<div style="background:{bg}; border: 1px solid {border}; '
        'border-radius:{radius}; padding:{pad}px {padh}px; '
        'margin:{my}px 40px {my}px 0;">'
        '{label}{body}{ts}</div>'
    ).format(
        bg=_VOID, border=_GRAPHITE, radius=radius,
        pad=pad, padh=pad_h, my=margin_y,
        label=sender_label, body=body, ts=ts_html,
        mono=_MONO,
    )


def format_system_message(text, font_scale=1.0):
    """Format a system/status message (centered, dimmed).

    Returns
    -------
    str
        HTML fragment for the system message.
    """
    escaped = html.escape(text)
    return (
        '<div style="text-align:center; color:{dim}; font-size:{sz}px; '
        'margin:6px 0; font-style:italic;">{text}</div>'
    ).format(
        dim=_TEXT_DIM, sz=_scale(_SMALL_PX, font_scale), text=escaped,
    )


def format_timestamp_divider(timestamp_text, font_scale=1.0):
    """Format a centered timestamp divider between message groups.

    Parameters
    ----------
    timestamp_text : str
        e.g. "2:34 PM" or "Today 2:34 PM"

    Returns
    -------
    str
        HTML fragment for the timestamp divider.
    """
    return (
        '<div style="text-align:center; color:{dim}; font-size:{sz}px; '
        'margin:{my}px 0; font-family:{mono}; letter-spacing:0.5px;">'
        '{text}</div>'
    ).format(
        dim=_TEXT_DIM, sz=_scale(_TIMESTAMP_SZ, font_scale),
        my=_GROUP_MARGIN_Y // 2, mono=_MONO,
        text=html.escape(str(timestamp_text)),
    )
