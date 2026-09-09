"""Shared decoding of raw host results and MCP CallToolResult envelopes."""
import json


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
    is_envelope = ("isError" in value or "structuredContent" in value or
                   (isinstance(content, list) and all(
                       isinstance(block, dict) and "type" in block for block in content)))
    if not is_envelope:
        return value, False
    is_error = value.get("isError", False)
    if type(is_error) is not bool:
        raise RuntimeError("MCP returned an unreadable tool error flag; outcome is unconfirmed.")
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
