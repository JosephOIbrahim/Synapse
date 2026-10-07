"""Shared decoding of raw host results and MCP CallToolResult envelopes."""
import json


def _validate_content_block(block):
    """Check required fields without discarding annotations or extension data."""
    valid = False
    if isinstance(block, dict):
        kind = block.get("type")
        if kind == "text":
            valid = isinstance(block.get("text"), str)
        elif kind in ("image", "audio"):
            valid = (isinstance(block.get("data"), str)
                     and isinstance(block.get("mimeType"), str))
        elif kind == "resource_link":
            valid = (isinstance(block.get("uri"), str)
                     and isinstance(block.get("name"), str))
        elif kind == "resource":
            resource = block.get("resource")
            valid = (isinstance(resource, dict)
                     and isinstance(resource.get("uri"), str)
                     and any(key in resource for key in ("text", "blob"))
                     and all(isinstance(resource[key], str)
                             for key in ("text", "blob") if key in resource))
    if not valid:
        raise RuntimeError("MCP returned unreadable tool content; outcome is unconfirmed.")


def unpack_tool_result(value):
    """Return (payload, is_error), retaining receipt fields in the payload.

    A direct handler dictionary is already a payload. Our MCP serializer puts
    that dictionary in one JSON text block; external structured content has the
    same role. Other content blocks remain intact rather than being discarded.
    A malformed envelope is an error, never evidence that dispatch did not run.
    """
    if not isinstance(value, dict):
        return value, False
    content = value.get("content")
    # Successful MCP serializers may omit isError. A malformed block list
    # must still be validated instead of mistaken for an ordinary payload.
    is_envelope = ("isError" in value or "structuredContent" in value
                   or isinstance(content, list))
    if not is_envelope:
        return value, False
    is_error = value.get("isError", False)
    if type(is_error) is not bool:
        raise RuntimeError("MCP returned an unreadable tool error flag; outcome is unconfirmed.")
    if "content" in value:
        if not isinstance(content, list):
            raise RuntimeError("MCP returned unreadable tool content; outcome is unconfirmed.")
        for block in content:
            _validate_content_block(block)
    if "structuredContent" in value:
        payload = value["structuredContent"]
        if not isinstance(payload, dict):
            raise RuntimeError("MCP returned unreadable structured tool content; outcome is unconfirmed.")
        return payload, is_error
    if not isinstance(content, list):
        raise RuntimeError("MCP returned unreadable tool content; outcome is unconfirmed.")
    if len(content) == 1 and isinstance(content[0], dict) and content[0].get("type") == "text":
        text = content[0].get("text")
        if not isinstance(text, str):
            raise RuntimeError("MCP returned unreadable tool text; outcome is unconfirmed.")
        try:
            return json.loads(text), is_error
        except (ValueError, TypeError):
            return text, is_error
    return value, is_error


#: The opening words of every artist-facing undo receipt. Minted by
#: ``synapse.server.handler_helpers.undo_receipt``; read back by the panel
#: (``synapse.panel.activity``). One spelling, shared, so the two never drift.
UNDO_RECEIPT_PREFIX = "One Ctrl+Z reverses: "


def undo_receipt_line(result):
    """The artist-facing undo sentence a handler result carries, or ``""``.

    Only a receipt minted by ``undo_receipt`` (prefix intact) counts: a
    hand-built or truncated ``undo`` block renders nothing rather than a
    promise nobody computed.
    """
    if not isinstance(result, dict):
        return ""
    undo = result.get("undo")
    if not isinstance(undo, dict):
        return ""
    artist = undo.get("artist")
    if isinstance(artist, str) and artist.startswith(UNDO_RECEIPT_PREFIX):
        return artist
    return ""


# 9/30: one 24 MB tool result made every later request exceed the model service's payload limit (HTTP 413)
# until the history was reset by hand. Each result is bounded before it enters history.
_MAX_TOOL_RESULT_CHARS = 96_000


def cap_tool_results(blocks, limit=_MAX_TOOL_RESULT_CHARS):
    """Copy of ``blocks`` with every string tool_result content cut to ``limit`` characters plus a note."""
    capped = []
    for block in blocks:
        content = block.get("content") if isinstance(block, dict) else None
        if (isinstance(block, dict) and block.get("type") == "tool_result"
                and isinstance(content, str) and len(content) > limit):
            note = ("\n[SYNAPSE kept the first %d of %d characters of this tool result. Ask for a narrower "
                    "query, a count, bounds, or specific items instead of the full data.]" % (limit, len(content)))
            block = dict(block, content=content[:limit] + note)
        capped.append(block)
    return capped


def cap_history(messages, limit=_MAX_TOOL_RESULT_CHARS):
    """Apply cap_tool_results to every user message in a stored conversation (a restored history may predate the cap)."""
    out = []
    for message in messages or []:
        if isinstance(message, dict) and message.get("role") == "user" and isinstance(message.get("content"), list):
            message = dict(message, content=cap_tool_results(message["content"], limit))
        out.append(message)
    return out


# TT-1: a tool can succeed and still report that part of its work did not land.
# v5.95.0 taught 17 tools to say so, but most say it INSIDE a success payload,
# where an envelope-only check (isError) reads it as a clean result. These are
# the keys that carry such a miss. Each is tested for TRUTHINESS, not presence:
# an empty ``parms_missed`` is the claim that every guarded write landed
# (core/parm_report.py), and ``"cook_error": None`` is no error.
_MISS_TEXT_KEYS = ("cook_error", "settings_error", "background_error", "callback_error")
_MISS_LIST_KEYS = (("parms_missed", "parms missed"), ("inputs_missed", "inputs missed"),
                   ("handler_removal_errors", "handler removal errors"))
# Lists of per-item results that carry their own misses (batch COP cook, the
# progressive render's passes, tops_batch_cook's per-node entries under "nodes",
# handlers_tops/cook.py). ``None`` entries (a failed batch step) are skipped.
_MISS_NESTED_KEYS = ("results", "passes", "nodes")


def _join(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _own_misses(payload):
    misses = []
    for key in _MISS_TEXT_KEYS:
        value = payload.get(key)
        if value:
            misses.append(_join(value))
    for key, label in _MISS_LIST_KEYS:
        value = payload.get(key)
        if value:
            misses.append("%s: %s" % (label, _join(value)))
    error = payload.get("error")
    error_text = error.strip() if isinstance(error, str) else ""
    if error_text:
        misses.append(error_text)
    if payload.get("status") == "error":
        detail = payload.get("message") or payload.get("errors")
        detail_text = _join(detail) if detail else ""
        # status=error alongside an 'error' string already named above is one miss.
        if not error_text:
            misses.append("status error" + (": " + detail_text if detail_text else ""))
    elif isinstance(payload.get("errors"), (list, tuple)):
        # synapse_batch keeps one slot per step: a clean batch is [None, None],
        # a failed step is a non-empty string in its slot.
        for i, step_error in enumerate(payload["errors"]):
            if isinstance(step_error, str) and step_error.strip():
                misses.append("step %d: %s" % (i, step_error.strip()))
    return misses


def result_misses(payload):
    """Name every miss a tool result reports inside a success, or ``[]``.

    A miss is: a truthy ``cook_error`` / ``settings_error`` /
    ``background_error`` / ``callback_error``; a non-empty ``parms_missed`` /
    ``inputs_missed`` / ``handler_removal_errors``; ``status == "error"``; or a
    non-empty top-level ``error`` string. Dict entries of a ``results`` or
    ``passes`` list are scanned the same way and named by their index. Any
    non-dict payload has no misses.
    """
    if not isinstance(payload, dict):
        return []
    misses = _own_misses(payload)
    for key in _MISS_NESTED_KEYS:
        items = payload.get(key)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if isinstance(item, dict):
                misses.extend("%s[%d]: %s" % (key, index, miss) for miss in _own_misses(item))
    return misses
