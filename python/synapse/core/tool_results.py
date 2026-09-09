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
