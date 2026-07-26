"""
MCP JSON-RPC 2.0 Protocol Utilities

Message parsing, response formatting, and error codes for the Synapse MCP
endpoint. Implements MCP 2025-06-18 (Streamable HTTP transport).

No external dependencies beyond stdlib (+ optional orjson).
"""

import json
from typing import Any, Optional

# He2025: sort_keys in all JSON serialization
try:
    import orjson

    def _dumps(obj: dict) -> bytes:
        return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)

    def _loads(data) -> dict:
        return orjson.loads(data)
except ImportError:
    def _dumps(obj: dict) -> bytes:
        return json.dumps(obj, sort_keys=True).encode("utf-8")

    def _loads(data) -> dict:
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return json.loads(data)


# =========================================================================
# JSON-RPC 2.0 standard error codes
# =========================================================================

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP-specific custom error codes
SAFETY_GUARD_REJECTION = -32001
NODE_NOT_FOUND = -32002
COOK_ERROR = -32003
SESSION_INVALID = -32004

# MCP protocol version
MCP_PROTOCOL_VERSION = "2025-06-18"


# =========================================================================
# Exceptions
# =========================================================================

class JsonRpcError(Exception):
    """Base JSON-RPC error with code and optional data."""

    def __init__(self, code: int, message: str, data: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.data = data


class JsonRpcParseError(JsonRpcError):
    def __init__(self, detail: str = ""):
        msg = f"Parse error: {detail}" if detail else "Parse error"
        super().__init__(PARSE_ERROR, msg)


class JsonRpcInvalidRequest(JsonRpcError):
    def __init__(self, detail: str = ""):
        msg = f"Invalid request: {detail}" if detail else "Invalid request"
        super().__init__(INVALID_REQUEST, msg)


class JsonRpcMethodNotFound(JsonRpcError):
    def __init__(self, method: str):
        super().__init__(METHOD_NOT_FOUND, f"Method not found: {method}")


class JsonRpcInvalidParams(JsonRpcError):
    def __init__(self, detail: str = ""):
        msg = f"Invalid params: {detail}" if detail else "Invalid params"
        super().__init__(INVALID_PARAMS, msg)


# =========================================================================
# Message parsing
# =========================================================================

def parse_request(body: bytes) -> dict:
    """Parse and validate a JSON-RPC 2.0 request.

    Args:
        body: Raw request bytes.

    Returns:
        Parsed JSON-RPC message dict with keys: jsonrpc, method, params, id.

    Raises:
        JsonRpcParseError: Invalid JSON.
        JsonRpcInvalidRequest: Missing required fields or wrong version.
    """
    try:
        msg = _loads(body)
    except (json.JSONDecodeError, ValueError) as e:
        raise JsonRpcParseError(str(e))

    if not isinstance(msg, dict):
        raise JsonRpcInvalidRequest("Request must be a JSON object")

    if msg.get("jsonrpc") != "2.0":
        raise JsonRpcInvalidRequest("Missing or invalid jsonrpc version (must be '2.0')")

    if "method" not in msg:
        raise JsonRpcInvalidRequest("Missing 'method' field")

    return msg


def is_notification(msg: dict) -> bool:
    """Check if a JSON-RPC message is a notification (no id field)."""
    return "id" not in msg


# =========================================================================
# Response formatting
# =========================================================================

def jsonrpc_result(msg_id: Any, result: dict) -> bytes:
    """Format a successful JSON-RPC 2.0 response."""
    return _dumps({
        "id": msg_id,
        "jsonrpc": "2.0",
        "result": result,
    })


def jsonrpc_error(msg_id: Any, code: int, message: str,
                  data: Optional[dict] = None) -> bytes:
    """Format a JSON-RPC 2.0 error response."""
    error: dict = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return _dumps({
        "error": error,
        "id": msg_id,
        "jsonrpc": "2.0",
    })


def error_from_exception(msg_id: Any, exc: JsonRpcError) -> bytes:
    """Format a JSON-RPC error response from a JsonRpcError exception."""
    return jsonrpc_error(msg_id, exc.code, str(exc), exc.data)
