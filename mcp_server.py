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
import json
import logging
import os
import time
import uuid

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

import websockets

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SYNAPSE_PORT = int(os.environ.get("SYNAPSE_PORT", "9999"))
SYNAPSE_URL = f"ws://localhost:{SYNAPSE_PORT}"
PROTOCOL_VERSION = "4.0.0"
MAX_RETRIES = 3
RETRY_DELAY = 1.0
COMMAND_TIMEOUT = 30.0

logger = logging.getLogger("synapse-mcp")

# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

_ws_connection = None
_ws_lock = asyncio.Lock()


async def _get_connection():
    """Get or create a persistent WebSocket connection."""
    global _ws_connection
    async with _ws_lock:
        if _ws_connection is not None:
            try:
                await _ws_connection.ping()
                return _ws_connection
            except Exception:
                _ws_connection = None

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                _ws_connection = await asyncio.wait_for(
                    websockets.connect(SYNAPSE_URL),
                    timeout=5.0,
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
    """
    command = {
        "type": cmd_type,
        "id": uuid.uuid4().hex[:16],
        "payload": payload or {},
        "sequence": 0,
        "timestamp": time.time(),
        "protocol_version": PROTOCOL_VERSION,
    }

    ws = await _get_connection()

    try:
        await ws.send(json.dumps(command))
        raw = await asyncio.wait_for(ws.recv(), timeout=COMMAND_TIMEOUT)
    except Exception:
        # Connection may have dropped — clear it so next call reconnects
        global _ws_connection
        _ws_connection = None
        raise

    response = json.loads(raw)

    if not response.get("success", False):
        error_msg = response.get("error", "Unknown error from Synapse")
        # Check for rate limiting
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
    """Register all 16 Synapse MCP tools."""
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
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
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

async def main():
    """Run the Synapse MCP server on stdio."""
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
