"""Convert SYNAPSE responses to styled HTML for QTextEdit rendering.

Handles plain text, code blocks (```python, ```vex), node paths
(/obj/geo1/scatter1), parameter names, lists, and status indicators.
"""

import html
import re

# -- Design tokens (from canonical design system) -------------------------
try:
    from synapse.panel import tokens as _t
    _NEAR_BLACK = _t.NEAR_BLACK
    _CARBON = _t.CARBON
    _VOID = _t.VOID
    _SIGNAL = _t.SIGNAL
    _TEXT = _t.TEXT
    _TEXT_DIM = _t.TEXT_DIM
    _ERROR = _t.ERROR        # Canonical #FF3D71
    _WARNING = _t.WARN       # Canonical #FFAB00
    _SUCCESS = _t.GROW       # Canonical #00E676
    _FONT_MONO = _t.FONT_MONO
    _FONT_SANS = _t.FONT_SANS
    _BODY_PX = _t.SIZE_BODY
    _SMALL_PX = _t.SIZE_SMALL
except ImportError:
    _NEAR_BLACK = "#3C3C3C"
    _CARBON = "#333333"
    _VOID = "#252525"
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

# Monospace font stack
_MONO = "'{mono}', 'Consolas', 'Courier New', monospace".format(mono=_FONT_MONO)

# Regex patterns
_CODE_BLOCK_RE = re.compile(
    r"```(\w*)\n(.*?)```", re.DOTALL
)
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_NODE_PATH_RE = re.compile(r"(/(?:obj|out|stage|shop|mat|ch|tasks|vex)/[\w/]+)")
_LIST_ITEM_RE = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)


def _status_prefix(status):
    """Return a colored Unicode prefix for status strings."""
    if status in ("ok", "success"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_SUCCESS)
    if status in ("warning", "warn"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_WARNING)
    if status in ("error", "fail"):
        return '<span style="color:{c}">&#9679;</span> '.format(c=_ERROR)
    return ""


def _format_code_block(match):
    """Render a fenced code block as a styled <pre>."""
    lang = match.group(1) or ""
    code = html.escape(match.group(2).rstrip())
    lang_label = ""
    if lang:
        lang_label = (
            '<div style="color:{dim}; font-size:{sz}px; '
            'margin-bottom:4px;">{lang}</div>'
        ).format(dim=_TEXT_DIM, sz=_SMALL_PX, lang=lang)
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
        sz=_SMALL_PX,
        label=lang_label,
        code=code,
    )


def _format_inline_code(match):
    """Render `inline code` with styled background."""
    code = html.escape(match.group(1))
    return (
        '<code style="background:{bg}; color:{fg}; font-family:{mono}; '
        'padding:2px 5px; border-radius:3px; font-size:{sz}px;">'
        "{code}</code>"
    ).format(
        bg=_NEAR_BLACK, fg=_SIGNAL, mono=_MONO, sz=_SMALL_PX, code=code
    )


def _format_node_path(match):
    """Render a Houdini node path as a clickable link."""
    path = match.group(1)
    return (
        '<a href="node:{path}" style="color:{c}; text-decoration:none; '
        'font-family:{mono}; font-size:{sz}px;">{path}</a>'
    ).format(path=path, c=_SIGNAL, mono=_MONO, sz=_SMALL_PX)


def _format_list_items(text):
    """Convert markdown-style list items to HTML <ul>."""
    items = _LIST_ITEM_RE.findall(text)
    if not items:
        return text
    ul_html = "<ul style=\"margin:4px 0; padding-left:20px;\">"
    for item in items:
        ul_html += "<li>{}</li>".format(item)
    ul_html += "</ul>"
    # Replace the original list block
    return _LIST_ITEM_RE.sub("", text).rstrip() + ul_html


def format_response(response):
    """Convert a SYNAPSE response dict to styled HTML for QTextEdit.

    Parameters
    ----------
    response : dict or str
        If dict, expects optional keys: ``status``, ``message``, ``result``,
        ``content``, ``text``.  If str, treated as plain text.

    Returns
    -------
    str
        HTML fragment suitable for QTextEdit.insertHtml().
    """
    if isinstance(response, str):
        text = response
        status = None
    else:
        text = (
            response.get("message")
            or response.get("result")
            or response.get("content")
            or response.get("text")
            or str(response)
        )
        status = response.get("status")

    # Escape base HTML entities first
    text = html.escape(text)

    # Restore fenced code blocks (they were escaped, undo the backticks)
    text = text.replace("&#x27;", "'")
    # Re-parse code blocks from the original (pre-escaped) value
    # We need to work on the raw text for code blocks
    if isinstance(response, str):
        raw = response
    else:
        raw = (
            response.get("message")
            or response.get("result")
            or response.get("content")
            or response.get("text")
            or str(response)
        )

    # Process code blocks on raw text
    raw = _CODE_BLOCK_RE.sub(_format_code_block, raw)

    # Inline code
    raw = _INLINE_CODE_RE.sub(_format_inline_code, raw)

    # Node paths
    raw = _NODE_PATH_RE.sub(_format_node_path, raw)

    # List items
    raw = _format_list_items(raw)

    # Newlines to <br> (but not inside <pre> blocks)
    parts = re.split(r"(<pre.*?</pre>)", raw, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith("<pre"):
            parts[i] = part.replace("\n", "<br>")
    raw = "".join(parts)

    prefix = _status_prefix(status) if status else ""

    return (
        '<div style="color:{fg}; font-size:{sz}px;">'
        "{prefix}{body}</div>"
    ).format(fg=_TEXT, sz=_BODY_PX, prefix=prefix, body=raw)


def format_user_message(text):
    """Format a user message with right-aligned subtle styling.

    Returns
    -------
    str
        HTML fragment for the user message bubble.
    """
    escaped = html.escape(text)
    escaped = escaped.replace("\n", "<br>")
    return (
        '<div style="background:{bg}; border-radius:8px; padding:10px 14px; '
        'margin:4px 0 4px 40px; color:{fg}; font-size:{sz}px;">'
        '<span style="color:{dim}; font-size:{sm}px; '
        'font-family:{mono}; letter-spacing:1px;">You</span><br>'
        "{body}</div>"
    ).format(
        bg=_CARBON, fg=_TEXT, sz=_BODY_PX, dim=_TEXT_DIM,
        sm=_SMALL_PX, body=escaped, mono=_MONO,
    )


def format_synapse_message(content):
    """Format a SYNAPSE response message with left-aligned styling.

    Parameters
    ----------
    content : dict or str
        Response payload from the server.

    Returns
    -------
    str
        HTML fragment for the synapse message bubble.
    """
    body = format_response(content)
    return (
        '<div style="background:{bg}; border-radius:8px; padding:10px 14px; '
        'margin:4px 40px 4px 0;">'
        '<span style="color:{accent}; font-size:{sm}px; '
        'font-weight:bold; font-family:{mono}; '
        'letter-spacing:2px;">SYNAPSE</span><br>'
        "{body}</div>"
    ).format(bg=_VOID, accent=_SIGNAL, sm=_SMALL_PX, body=body, mono=_MONO)


def format_system_message(text):
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
    ).format(dim=_TEXT_DIM, sz=_SMALL_PX, text=escaped)
