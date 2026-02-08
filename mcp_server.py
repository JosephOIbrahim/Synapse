#!/usr/bin/env python3
"""
Synapse MCP Server — Bridge between Claude Desktop and Houdini via WebSocket.

Connects Claude Desktop (stdio/JSON-RPC) to the Synapse WebSocket server
running inside Houdini, giving Claude Desktop full access to Houdini scene
manipulation and project memory.

Architecture:
    Claude Desktop  <-[stdio/JSON-RPC]->  mcp_server.py  <-[WebSocket]->  Synapse (Houdini)

Install: pip install mcp websockets
Run: python mcp_server.py
"""

import asyncio
import logging
import os
import time
import uuid

try:
    import orjson
    def _dumps(obj): return orjson.dumps(obj).decode()
    def _loads(s): return orjson.loads(s)
except ImportError:
    import json
    _dumps = json.dumps
    _loads = json.loads

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

import websockets

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Transport configuration
# - hwebserver backend (default): SYNAPSE_PATH="/synapse" (production inside Houdini)
# - websocket.py backend:         SYNAPSE_PATH="" (standalone testing/CI)
# Note: websocket.py accepts any path, so "/synapse" works for both backends.
SYNAPSE_PORT = int(os.environ.get("SYNAPSE_PORT", "9999"))
SYNAPSE_PATH = os.environ.get("SYNAPSE_PATH", "/synapse")
SYNAPSE_URL = f"ws://localhost:{SYNAPSE_PORT}{SYNAPSE_PATH}"
PROTOCOL_VERSION = "4.0.0"
MAX_RETRIES = 2
RETRY_DELAY = 0.3
COMMAND_TIMEOUT = 10.0
_SLOW_COMMANDS = {"execute_python": 30.0, "execute_vex": 30.0, "capture_viewport": 30.0, "render": 120.0}

logger = logging.getLogger("synapse-mcp")


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

_ws_connection = None
_ws_lock = asyncio.Lock()
_cmd_lock = asyncio.Lock()  # Serialize send+recv to prevent response interleaving


def _is_connected() -> bool:
    """Check if the WebSocket connection is open."""
    try:
        return _ws_connection is not None and _ws_connection.state.name == "OPEN"
    except (AttributeError, Exception):
        return False


async def _get_connection():
    """Get or create a persistent WebSocket connection.

    Skips ping health check — just reuse if open. If the connection is
    dead, send_command's try/except will catch it and reconnect next call.
    Saves ~1-2ms per command vs await ping().
    """
    global _ws_connection
    async with _ws_lock:
        if _is_connected():
            return _ws_connection
        _ws_connection = None

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                _ws_connection = await websockets.connect(
                    SYNAPSE_URL,
                    open_timeout=3.0,
                    close_timeout=1.0,
                    ping_interval=None,
                    compression=None,
                )
                logger.info("Connected to Synapse at %s", SYNAPSE_URL)
                return _ws_connection
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise ConnectionError(
            f"Could not connect to Synapse at {SYNAPSE_URL} after {MAX_RETRIES} attempts: {last_error}\n\n"
            "Houdini not running or Synapse server not started. "
            "Launch Houdini and start the Synapse server from the Python Panel."
        )


async def send_command(cmd_type: str, payload: dict | None = None) -> dict:
    """
    Send a SynapseCommand over WebSocket and return the response data.

    Follows the SynapseCommand wire format from core/protocol.py.
    Uses response ID matching to handle stale messages on reconnect.
    """
    command_id = uuid.uuid4().hex[:16]
    command = {
        "type": cmd_type,
        "id": command_id,
        "payload": payload or {},
        "sequence": 0,
        "timestamp": time.time(),
        "protocol_version": PROTOCOL_VERSION,
    }

    # Serialize send+recv so parallel tool calls don't steal each other's responses
    async with _cmd_lock:
        last_err = None
        for _attempt in range(2):  # One transparent retry on connection failure
            ws = await _get_connection()

            try:
                await ws.send(_dumps(command))

                # Recv loop with ID matching — discard stale responses from reconnect
                cmd_timeout = _SLOW_COMMANDS.get(cmd_type, COMMAND_TIMEOUT)
                start = time.monotonic()
                while True:
                    remaining = cmd_timeout - (time.monotonic() - start)
                    if remaining <= 0:
                        raise TimeoutError(f"Timed out waiting for response to {cmd_type}")

                    raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    response = _loads(raw)

                    if response.get("id") == command_id:
                        break  # Matched — this is our response

                    # Stale or mismatched response — discard and try next
                    logger.warning(
                        "Response ID mismatch: expected %s, got %s (discarding)",
                        command_id, response.get("id"),
                    )
                break  # Success — exit retry loop

            except TimeoutError:
                # Close stale connection on timeout to prevent resource leak
                global _ws_connection
                try:
                    if ws:
                        await ws.close()
                except Exception:
                    pass
                _ws_connection = None
                raise  # Don't retry timeouts — the command may have executed
            except Exception as e:
                # Connection dropped — close and clear, then retry once
                try:
                    if ws:
                        await ws.close()
                except Exception:
                    pass
                _ws_connection = None
                last_err = e
                logger.warning("Connection lost during %s, reconnecting... (%s)", cmd_type, e)

        else:
            raise ConnectionError(f"Failed to send {cmd_type} after reconnect: {last_err}")

    if not response.get("success", False):
        error_msg = response.get("error", "Unknown error from Synapse")
        data = response.get("data") or {}
        if isinstance(data, dict) and "retry_after" in data:
            error_msg += f" (retry after {data['retry_after']}s)"
        raise RuntimeError(error_msg)

    return response.get("data", {})


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server("synapse")


@server.list_tools()
async def list_tools():
    """Register all 18 Synapse MCP tools."""
    return [
        # -- Utility --
        Tool(
            name="synapse_ping",
            description="Check if Houdini/Synapse is connected and responding.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="synapse_health",
            description="Get system health status including resilience layer (circuit breaker, rate limiter).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # -- Scene --
        Tool(
            name="houdini_scene_info",
            description="Get current Houdini scene info: HIP file path, current frame, FPS, and frame range.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="houdini_get_selection",
            description="Get the currently selected nodes in Houdini.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # -- Node operations --
        Tool(
            name="houdini_create_node",
            description="Create a new node in Houdini. Returns the path of the created node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "parent": {
                        "type": "string",
                        "description": "Parent node path (e.g. '/obj', '/obj/geo1')",
                    },
                    "type": {
                        "type": "string",
                        "description": "Node type to create (e.g. 'geo', 'null', 'sphere')",
                    },
                    "name": {
                        "type": "string",
                        "description": "Optional name for the new node",
                    },
                },
                "required": ["parent", "type"],
            },
        ),
        Tool(
            name="houdini_delete_node",
            description="Delete a node in Houdini by its path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Full path of the node to delete (e.g. '/obj/geo1')",
                    },
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="houdini_connect_nodes",
            description="Connect the output of one node to the input of another.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source node path (output from)",
                    },
                    "target": {
                        "type": "string",
                        "description": "Target node path (input to)",
                    },
                    "source_output": {
                        "type": "integer",
                        "description": "Source output index (default: 0)",
                    },
                    "target_input": {
                        "type": "integer",
                        "description": "Target input index (default: 0)",
                    },
                },
                "required": ["source", "target"],
            },
        ),
        # -- Parameters --
        Tool(
            name="houdini_get_parm",
            description="Read a parameter value from a Houdini node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Node path (e.g. '/obj/geo1')",
                    },
                    "parm": {
                        "type": "string",
                        "description": "Parameter name (e.g. 'tx', 'scale', 'file')",
                    },
                },
                "required": ["node", "parm"],
            },
        ),
        Tool(
            name="houdini_set_parm",
            description="Set a parameter value on a Houdini node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Node path (e.g. '/obj/geo1')",
                    },
                    "parm": {
                        "type": "string",
                        "description": "Parameter name (e.g. 'tx', 'scale', 'file')",
                    },
                    "value": {
                        "description": "Value to set (number, string, or array for tuple parms)",
                    },
                },
                "required": ["node", "parm", "value"],
            },
        ),
        # -- Execution --
        Tool(
            name="houdini_execute_python",
            description=(
                "Execute Python code in Houdini's runtime environment. "
                "The code runs with 'hou' module available. "
                "Set a 'result' variable to return data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute in Houdini",
                    },
                },
                "required": ["code"],
            },
        ),
        # -- USD/Solaris --
        Tool(
            name="houdini_stage_info",
            description="Get USD stage information: prim list and types. Optionally specify a LOP node path.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Optional LOP node path. If omitted, uses current selection.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="houdini_get_usd_attribute",
            description="Read a USD attribute value from a prim on the stage. Returns value and type info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node path. If omitted, uses current selection.",
                    },
                    "prim_path": {
                        "type": "string",
                        "description": "USD prim path (e.g. '/World/geo/mesh1')",
                    },
                    "attribute_name": {
                        "type": "string",
                        "description": "USD attribute name (e.g. 'xformOp:translate', 'visibility')",
                    },
                },
                "required": ["prim_path", "attribute_name"],
            },
        ),
        Tool(
            name="houdini_set_usd_attribute",
            description="Set a USD attribute on a prim. Creates a Python LOP node wired into the graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to wire after. If omitted, uses current selection.",
                    },
                    "prim_path": {
                        "type": "string",
                        "description": "USD prim path (e.g. '/World/geo/mesh1')",
                    },
                    "attribute_name": {
                        "type": "string",
                        "description": "USD attribute name (e.g. 'xformOp:translate')",
                    },
                    "value": {
                        "description": "Value to set (number, string, or array for vector types)",
                    },
                },
                "required": ["prim_path", "attribute_name", "value"],
            },
        ),
        Tool(
            name="houdini_create_usd_prim",
            description="Create a USD prim on the stage. Creates a Python LOP node wired into the graph.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to wire after. If omitted, uses current selection.",
                    },
                    "prim_path": {
                        "type": "string",
                        "description": "USD prim path to create (e.g. '/World/lights/key_light')",
                    },
                    "prim_type": {
                        "type": "string",
                        "description": "USD prim type (e.g. 'Xform', 'Mesh', 'DomeLight', 'Material'). Default: Xform",
                    },
                },
                "required": ["prim_path"],
            },
        ),
        Tool(
            name="houdini_modify_usd_prim",
            description="Modify USD prim metadata: kind, purpose, or active state. Creates a Python LOP node.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to wire after. If omitted, uses current selection.",
                    },
                    "prim_path": {
                        "type": "string",
                        "description": "USD prim path to modify",
                    },
                    "kind": {
                        "type": "string",
                        "description": "Model kind (e.g. 'component', 'group', 'assembly')",
                    },
                    "purpose": {
                        "type": "string",
                        "description": "Prim purpose (e.g. 'default', 'render', 'proxy', 'guide')",
                    },
                    "active": {
                        "type": "boolean",
                        "description": "Whether the prim is active (visible in composition)",
                    },
                },
                "required": ["prim_path"],
            },
        ),
        # -- Viewport --
        Tool(
            name="houdini_capture_viewport",
            description=(
                "Capture the Houdini viewport as an image. "
                "Returns the image directly for visual analysis of lighting, layout, and composition."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "width": {
                        "type": "integer",
                        "description": "Optional width to resize the capture to (maintains aspect ratio)",
                    },
                    "height": {
                        "type": "integer",
                        "description": "Optional height to resize the capture to (maintains aspect ratio)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["jpeg", "png"],
                        "description": "Image format (default: jpeg). JPEG is smaller, PNG is lossless.",
                    },
                },
                "required": [],
            },
        ),
        # -- Render --
        Tool(
            name="houdini_render",
            description=(
                "Render a frame using Karma XPU, Karma CPU, Mantra, or any ROP node. "
                "Returns the rendered image and reports which engine was used. "
                "Auto-discovers a render ROP if 'node' is omitted."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "ROP node path (e.g. '/stage/karma1'). Auto-discovers if omitted.",
                    },
                    "frame": {
                        "type": "number",
                        "description": "Frame to render. Defaults to current frame.",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Override resolution width in pixels.",
                    },
                    "height": {
                        "type": "integer",
                        "description": "Override resolution height in pixels.",
                    },
                },
            },
        ),
        # -- Memory --
        Tool(
            name="synapse_context",
            description="Get project context from Synapse memory (shot info, decisions, notes).",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="synapse_search",
            description="Search project memory for relevant entries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="synapse_recall",
            description="Recall relevant memories for a given context or question.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Context or question to recall memories for",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="synapse_decide",
            description="Record a decision in project memory with reasoning.",
            inputSchema={
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "description": "The decision made",
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why this decision was made",
                    },
                    "alternatives": {
                        "type": "string",
                        "description": "Alternatives that were considered",
                    },
                },
                "required": ["decision"],
            },
        ),
        Tool(
            name="synapse_add_memory",
            description="Add a memory entry to the project (note, context, reference, etc.).",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string",
                        "description": "Memory content to store",
                    },
                    "memory_type": {
                        "type": "string",
                        "description": "Type of memory (note, context, reference, task). Default: note",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional tags for categorization",
                    },
                },
                "required": ["content"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

# Map MCP tool name → (synapse_command_type, payload_builder)
# payload_builder receives the MCP arguments dict and returns the Synapse payload dict

def _passthrough(_args: dict) -> dict:
    return {}


def _execute_python_payload(args: dict) -> dict:
    # MCP uses 'code', Synapse handler resolves 'content'
    return {"content": args["code"]}


def _stage_info_payload(args: dict) -> dict:
    p = {}
    if "node" in args:
        p["node"] = args["node"]
    return p


def _decide_payload(args: dict) -> dict:
    p = {"decision": args["decision"]}
    if "reasoning" in args:
        p["reasoning"] = args["reasoning"]
    if "alternatives" in args:
        p["alternatives"] = args["alternatives"]
    return p


def _add_memory_payload(args: dict) -> dict:
    p = {"content": args["content"]}
    if "memory_type" in args:
        p["memory_type"] = args["memory_type"]
    if "tags" in args:
        p["tags"] = args["tags"]
    return p


TOOL_DISPATCH: dict[str, tuple[str, callable]] = {
    "synapse_ping":          ("ping",            _passthrough),
    "synapse_health":        ("get_health",      _passthrough),
    "houdini_scene_info":    ("get_scene_info",  _passthrough),
    "houdini_get_selection": ("get_selection",    _passthrough),
    "houdini_create_node":   ("create_node",     lambda a: {k: a[k] for k in a}),
    "houdini_delete_node":   ("delete_node",     lambda a: {"node": a["node"]}),
    "houdini_connect_nodes": ("connect_nodes",   lambda a: {k: a[k] for k in a}),
    "houdini_get_parm":      ("get_parm",        lambda a: {"node": a["node"], "parm": a["parm"]}),
    "houdini_set_parm":      ("set_parm",        lambda a: {"node": a["node"], "parm": a["parm"], "value": a["value"]}),
    "houdini_execute_python":("execute_python",  _execute_python_payload),
    "houdini_stage_info":    ("get_stage_info",  _stage_info_payload),
    "houdini_get_usd_attribute": ("get_usd_attribute", lambda a: {
        k: a[k] for k in ("node", "prim_path", "attribute_name") if k in a
    }),
    "houdini_set_usd_attribute": ("set_usd_attribute", lambda a: {
        k: a[k] for k in ("node", "prim_path", "attribute_name", "value") if k in a
    }),
    "houdini_create_usd_prim": ("create_usd_prim", lambda a: {
        k: a[k] for k in ("node", "prim_path", "prim_type") if k in a
    }),
    "houdini_modify_usd_prim": ("modify_usd_prim", lambda a: {
        k: a[k] for k in ("node", "prim_path", "kind", "purpose", "active") if k in a
    }),
    "houdini_capture_viewport": ("capture_viewport", lambda a: {k: a[k] for k in a}),
    "houdini_render":           ("render",           lambda a: {k: a[k] for k in a}),
    "synapse_context":       ("context",         _passthrough),
    "synapse_search":        ("search",          lambda a: {"query": a["query"]}),
    "synapse_recall":        ("recall",          lambda a: {"query": a["query"]}),
    "synapse_decide":        ("decide",          _decide_payload),
    "synapse_add_memory":    ("add_memory",      _add_memory_payload),
}


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch MCP tool call to Synapse via WebSocket."""
    if name not in TOOL_DISPATCH:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    cmd_type, build_payload = TOOL_DISPATCH[name]

    try:
        payload = build_payload(arguments)
        data = await send_command(cmd_type, payload)

        # Image-producing tools: read file and return as ImageContent
        if name in ("houdini_capture_viewport", "houdini_render"):
            import base64
            image_path = data.get("image_path", "")
            try:
                with open(image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("utf-8")
                mime = "image/jpeg" if data.get("format") == "jpeg" else "image/png"
                meta = {
                    "width": data.get("width"),
                    "height": data.get("height"),
                    "format": data.get("format"),
                }
                # Include render-specific metadata
                if "engine" in data:
                    meta["rop"] = data.get("rop")
                    meta["rop_type"] = data.get("rop_type")
                    meta["engine"] = data.get("engine")
                return [
                    ImageContent(type="image", data=b64, mimeType=mime),
                    TextContent(type="text", text=_dumps(meta)),
                ]
            except FileNotFoundError:
                return [TextContent(type="text", text=f"Capture succeeded but file not found: {image_path}")]

        return [TextContent(type="text", text=_dumps(data))]
    except ConnectionError as e:
        return [TextContent(type="text", text=f"Connection error: {e}")]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Synapse error: {e}")]
    except Exception as e:
        logger.exception("Unexpected error in tool %s", name)
        return [TextContent(type="text", text=f"Error: {e}")]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def _warmup():
    """Pre-connect to Synapse on startup — makes first tool call instant."""
    global _ws_connection
    try:
        _ws_connection = await websockets.connect(
            SYNAPSE_URL,
            open_timeout=3.0,
            close_timeout=1.0,
            ping_interval=None,
            compression=None,
        )
        logger.info("Warmup: connected to %s", SYNAPSE_URL)
    except Exception:
        logger.info("Warmup: Synapse not available yet (will retry on first tool call)")


async def main():
    """Run the Synapse MCP server on stdio."""
    await _warmup()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    # Logging to stderr only — never print to stdout (corrupts stdio JSON-RPC)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=__import__("sys").stderr,
    )
    asyncio.run(main())
