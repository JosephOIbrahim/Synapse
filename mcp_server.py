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
import hashlib

try:
    import orjson
    def _dumps(obj): return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode()
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
# Deterministic command IDs (He2025: same input → same ID within a session)
# ---------------------------------------------------------------------------
_cmd_seq = 0

def _cmd_id(cmd_type: str, payload: dict | None) -> str:
    global _cmd_seq
    _cmd_seq += 1
    content = f"{cmd_type}:{_dumps(payload or {})}:{_cmd_seq}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

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
_SLOW_COMMANDS = {
    "execute_python": 30.0, "execute_vex": 30.0, "capture_viewport": 30.0,
    "render": 120.0, "wedge": 120.0,
    "inspect_selection": 30.0, "inspect_scene": 30.0, "inspect_node": 30.0,
    "batch_commands": 60.0,
}

logger = logging.getLogger("synapse-mcp")


# ---------------------------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------------------------

_ws_connection = None
_ws_lock = asyncio.Lock()
_pending: dict[str, asyncio.Future] = {}
_recv_task: asyncio.Task | None = None


def _is_connected() -> bool:
    """Check if the WebSocket connection is open."""
    try:
        return _ws_connection is not None and _ws_connection.state.name == "OPEN"
    except (AttributeError, Exception):
        return False


async def _recv_loop():
    """Background task: read messages and dispatch to pending futures by ID."""
    global _ws_connection, _recv_task
    try:
        while _ws_connection is not None:
            try:
                raw = await _ws_connection.recv()
            except Exception as e:
                # Connection lost — signal all pending futures
                logger.warning("Recv loop: connection lost (%s)", e)
                _signal_all_pending(ConnectionError(f"Connection lost: {e}"))
                break

            try:
                response = _loads(raw)
            except Exception:
                continue  # Malformed message — skip

            resp_id = response.get("id")
            future = _pending.pop(resp_id, None) if resp_id else None
            if future and not future.done():
                future.set_result(response)
            elif resp_id:
                logger.warning("No pending future for response ID %s (discarding)", resp_id)
    finally:
        _recv_task = None


def _signal_all_pending(exc: Exception):
    """Signal all pending futures with an exception (connection lost)."""
    for fut in _pending.values():
        if not fut.done():
            fut.set_exception(exc)
    _pending.clear()


def _start_recv_loop():
    """Ensure the background recv loop is running."""
    global _recv_task
    if _recv_task is None or _recv_task.done():
        _recv_task = asyncio.get_event_loop().create_task(_recv_loop())


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
                _start_recv_loop()
                logger.info("Connected to Synapse at %s", SYNAPSE_URL)
                return _ws_connection
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise ConnectionError(
            f"Couldn't connect to Synapse at {SYNAPSE_URL} after {MAX_RETRIES} attempts: {last_error}\n\n"
            "Houdini might not be running, or the Synapse server hasn't started yet. "
            "Launch Houdini and start the Synapse server from the Python Panel."
        )


async def send_command(cmd_type: str, payload: dict | None = None) -> dict:
    """
    Send a SynapseCommand over WebSocket and return the response data.

    Supports true parallel dispatch — multiple concurrent send_command
    calls share a single recv loop that routes responses by ID.
    """
    command_id = _cmd_id(cmd_type, payload)
    command = {
        "type": cmd_type,
        "id": command_id,
        "payload": payload or {},
        "sequence": 0,
        "timestamp": time.time(),
        "protocol_version": PROTOCOL_VERSION,
    }

    cmd_timeout = _SLOW_COMMANDS.get(cmd_type, COMMAND_TIMEOUT)
    last_err = None

    for _attempt in range(2):  # One transparent retry on connection failure
        ws = await _get_connection()

        # Register a future for this command's response
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        _pending[command_id] = future

        try:
            await ws.send(_dumps(command))

            response = await asyncio.wait_for(future, timeout=cmd_timeout)
            break  # Success

        except asyncio.TimeoutError:
            _pending.pop(command_id, None)
            # Close stale connection on timeout
            global _ws_connection
            try:
                if ws:
                    await ws.close()
            except Exception:
                pass
            _ws_connection = None
            raise TimeoutError(
                f"The {cmd_type} command took too long to respond \u2014 "
                "Houdini may be busy with a heavy operation"
            )
        except ConnectionError:
            # Future was signaled by _recv_loop disconnect
            _pending.pop(command_id, None)
            try:
                if ws:
                    await ws.close()
            except Exception:
                pass
            _ws_connection = None
            last_err = ConnectionError(f"Connection lost during {cmd_type}")
            logger.warning("Connection lost during %s, reconnecting...", cmd_type)
        except Exception as e:
            _pending.pop(command_id, None)
            try:
                if ws:
                    await ws.close()
            except Exception:
                pass
            _ws_connection = None
            last_err = e
            logger.warning("Connection lost during %s, reconnecting... (%s)", cmd_type, e)
    else:
        raise ConnectionError(
            f"Lost connection while sending {cmd_type} and couldn't reconnect: {last_err}"
        )

    if not response.get("success", False):
        error_msg = response.get("error", "Something went wrong on the Synapse side")
        data = response.get("data") or {}
        if isinstance(data, dict) and "retry_after" in data:
            error_msg += f" (retry after {data['retry_after']}s)"
        raise RuntimeError(error_msg)

    return response.get("data", {})


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

# Load TONE.md as server instructions (shapes LLM behavior when Synapse is active)
_tone_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TONE.md")
_tone_instructions = ""
try:
    with open(_tone_path, encoding="utf-8") as _f:
        _tone_instructions = _f.read()
except FileNotFoundError:
    pass

server = Server("synapse", instructions=_tone_instructions or None)


@server.list_tools()
async def list_tools():
    """Register all Synapse MCP tools."""
    return [
        # -- Utility --
        Tool(
            name="synapse_ping",
            description=(
                "Check if Houdini/Synapse is connected and responding. "
                "A quick health check \u2014 if it fails, Houdini may not be running yet."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="synapse_health",
            description=(
                "Get system health status including resilience layer (circuit breaker, rate limiter). "
                "Use this to diagnose connection issues before retrying operations."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # -- Scene --
        Tool(
            name="houdini_scene_info",
            description=(
                "Get current Houdini scene info: HIP file path, current frame, FPS, and frame range. "
                "Good starting point to orient yourself in the artist's scene."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="houdini_get_selection",
            description=(
                "Get the currently selected nodes in Houdini. "
                "Useful for understanding what the artist is focused on before making changes."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # -- Node operations --
        Tool(
            name="houdini_create_node",
            description=(
                "Create a new node in Houdini. Returns the path of the created node. "
                "When reporting back, share what was created and where \u2014 "
                "e.g. 'Created rim_light, it's ready at /stage/rim_light'."
            ),
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
            description=(
                "Delete a node in Houdini by its path. "
                "Confirm with the artist before deleting if the node wasn't just created in this session."
            ),
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
            description=(
                "Connect the output of one node to the input of another. "
                "If it fails, check both nodes exist and indices are valid."
            ),
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
            description=(
                "Read a parameter value from a Houdini node. "
                "If the parameter name doesn't match, Synapse will suggest similar names. "
                "Houdini parameter names can be cryptic \u2014 "
                "help the artist by translating to plain language."
            ),
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
            description=(
                "Set a parameter value on a Houdini node. "
                "When reporting success, describe the change in artist-friendly terms "
                "(e.g. 'Bumped the light intensity to 5.0') rather than raw parameter names."
            ),
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
                "Set a 'result' variable to return data. "
                "When presenting results: celebrate progress, explain errors in "
                "plain language with next steps, and frame everything as "
                "collaborative iteration \u2014 'we tried X, let's adjust' not 'X failed'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "Python code to execute in Houdini",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "Syntax-check only \u2014 compile the code without running it. Returns {valid: true/false}.",
                    },
                    "atomic": {
                        "type": "boolean",
                        "description": "Wrap execution in an undo group (default: true). Set false to skip undo tracking.",
                    },
                },
                "required": ["code"],
            },
        ),
        # -- USD/Solaris --
        Tool(
            name="houdini_stage_info",
            description=(
                "Get USD stage information: prim list and types. Optionally specify a LOP node path. "
                "Great for understanding what's on the stage before making USD changes."
            ),
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
            description=(
                "Read a USD attribute value from a prim on the stage. Returns value and type info. "
                "If the attribute name doesn't match, Synapse lists available attributes to help."
            ),
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
            description=(
                "Set a USD attribute on a prim. Creates a Python LOP node wired into the graph. "
                "Describe changes naturally \u2014 "
                "'Moved the key light to (2, 5, 3)' not 'Set xformOp:translate'."
            ),
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
            description=(
                "Create a USD prim on the stage. Creates a Python LOP node wired into the graph. "
                "Share what was created in context \u2014 "
                "'Added a DomeLight at /World/lights/env' tells the artist what happened."
            ),
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
            description=(
                "Modify USD prim metadata: kind, purpose, or active state. Creates a Python LOP node. "
                "Explain what the change means \u2014 "
                "'Set as component so it shows up in asset browsers'."
            ),
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
                "Returns the image directly for visual analysis of lighting, layout, and composition. "
                "This is the artist's window into their work \u2014 "
                "comment on what's working well before suggesting changes. Lead with what's strong."
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
                "Auto-discovers a render ROP if 'node' is omitted. "
                "If the render succeeds, share the result with enthusiasm \u2014 the artist made something. "
                "If it fails, diagnose calmly: check output path, camera, and render settings."
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
        # -- Keyframe / Render Settings --
        Tool(
            name="houdini_set_keyframe",
            description=(
                "Set a keyframe on a node parameter at a specific frame. "
                "Confirm the keyframe was set by reporting the value and frame number."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "Node path (e.g. '/obj/geo1')"},
                    "parm": {"type": "string", "description": "Parameter name (e.g. 'tx')"},
                    "value": {"type": "number", "description": "Value to set"},
                    "frame": {"type": "number", "description": "Frame number. Defaults to current frame."},
                },
                "required": ["node", "parm", "value"],
            },
        ),
        Tool(
            name="houdini_render_settings",
            description=(
                "Read and optionally modify render settings on a ROP or Karma node. "
                "Pass settings dict to override values. "
                "When reporting changes, translate parameter names into plain language "
                "where possible (e.g. 'Set resolution to 1920x1080')."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "ROP or render settings node path"},
                    "settings": {"type": "object", "description": "Optional dict of parm_name: value overrides to apply"},
                },
                "required": ["node"],
            },
        ),
        # -- TOPs / PDG --
        Tool(
            name="houdini_wedge",
            description=(
                "Run a TOPs/PDG wedge to explore parameter variations. "
                "Point to a TOP network or wedge node. "
                "Great for quickly testing different looks \u2014 "
                "present results as creative options, not just data."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP network or wedge node path"},
                    "parm": {"type": "string", "description": "Parameter to wedge"},
                    "values": {"type": "array", "items": {"type": "number"}, "description": "List of values to wedge over"},
                },
                "required": ["node"],
            },
        ),
        # -- USD Scene Assembly --
        Tool(
            name="houdini_reference_usd",
            description=(
                "Import a USD file into the stage via reference or sublayer. "
                "Confirm the asset loaded by reporting its path and what's on the stage now."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to USD file (.usd, .usdc, .usda)"},
                    "prim_path": {"type": "string", "description": "Target prim path for reference. Default: /"},
                    "mode": {"type": "string", "enum": ["reference", "sublayer"], "description": "Import mode. Default: reference"},
                    "parent": {"type": "string", "description": "Parent LOP network path. Default: /stage"},
                },
                "required": ["file"],
            },
        ),
        # -- Materials --
        Tool(
            name="houdini_create_material",
            description=(
                "Create a material with a shader in the LOP network. "
                "When reporting back, share what was created \u2014 "
                "'Set up a new brushed metal material at /materials/chrome'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to wire after. If omitted, uses current selection.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Material name (default: 'material')",
                    },
                    "shader_type": {
                        "type": "string",
                        "description": "Shader node type (default: 'mtlxstandard_surface')",
                    },
                    "base_color": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[r, g, b] floats 0-1",
                    },
                    "metalness": {
                        "type": "number",
                        "description": "Metalness value 0-1",
                    },
                    "roughness": {
                        "type": "number",
                        "description": "Roughness value 0-1",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="houdini_assign_material",
            description=(
                "Assign a material to geometry prims. Creates an assign node wired into "
                "the graph. Confirm what got connected \u2014 'Bound the chrome material to "
                "all meshes under /World/props'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to wire after. If omitted, uses current selection.",
                    },
                    "prim_pattern": {
                        "type": "string",
                        "description": "Geometry prim path or pattern (e.g. '/World/geo/*')",
                    },
                    "material_path": {
                        "type": "string",
                        "description": "USD material path (e.g. '/materials/plastic')",
                    },
                },
                "required": ["prim_pattern", "material_path"],
            },
        ),
        Tool(
            name="houdini_read_material",
            description=(
                "Read what material is assigned to a prim and its shader settings. "
                "Present findings naturally \u2014 'That mesh is using a gold material "
                "with roughness at 0.3'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "LOP node to read stage from. If omitted, uses current selection.",
                    },
                    "prim_path": {
                        "type": "string",
                        "description": "USD prim to inspect",
                    },
                },
                "required": ["prim_path"],
            },
        ),
        # -- Knowledge / RAG --
        Tool(
            name="synapse_knowledge_lookup",
            description=(
                "Look up Houdini knowledge: parameter names, node types, "
                "workflow guides, FX setup, rendering, and lighting. "
                "Uses the RAG index for fast, grounded answers. "
                "Use this before guessing parameter names or node types \u2014 "
                "it's faster and more reliable than trial and error."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g. 'dome light intensity parameter', 'pyro setup chain')",
                    },
                },
                "required": ["query"],
            },
        ),
        # -- Introspection --
        Tool(
            name="synapse_inspect_selection",
            description=(
                "Inspect the currently selected nodes in detail \u2014 modified parameters, "
                "connections, geometry stats, warnings/errors, and the upstream input graph. "
                "Start here to understand what the artist is working on before making changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "depth": {
                        "type": "integer",
                        "description": "How many levels of input nodes to traverse (default: 1). Use 0 for just the selected nodes, 2+ to see deeper upstream context.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="synapse_inspect_scene",
            description=(
                "Get a bird's-eye view of the Houdini scene \u2014 node tree, context breakdown "
                "(SOP/LOP/OBJ counts), warnings/errors, and sticky notes. "
                "Use this to orient in an unfamiliar scene before diving into specifics."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "root": {
                        "type": "string",
                        "description": "Starting node path (default: '/'). Use '/obj' or '/stage' to focus on a specific context.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "How deep to traverse the hierarchy (default: 3).",
                    },
                    "context_filter": {
                        "type": "string",
                        "description": "Only include nodes of this category (e.g. 'Sop', 'Lop', 'Object').",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="synapse_inspect_node",
            description=(
                "Deep-dive into a single node \u2014 every parameter (grouped by folder), "
                "expressions, keyframes, VEX/Python code, geometry attributes with samples, "
                "spare parameters, and HDA info. Use this when you need the full picture "
                "of how a specific node is configured."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Full path to the node (e.g. '/obj/geo1/mountain1').",
                    },
                    "include_code": {
                        "type": "boolean",
                        "description": "Include VEX/Python code from wrangle/script nodes (default: true).",
                    },
                    "include_geometry": {
                        "type": "boolean",
                        "description": "Include geometry attribute summary (default: true).",
                    },
                    "include_expressions": {
                        "type": "boolean",
                        "description": "Include parameter expressions and keyframe info (default: true).",
                    },
                },
                "required": ["node"],
            },
        ),
        # -- Memory --
        Tool(
            name="synapse_context",
            description=(
                "Get project context from Synapse memory (shot info, decisions, notes). "
                "Check this at the start of a session to understand the project history."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="synapse_search",
            description=(
                "Search project memory for relevant entries. "
                "Helps avoid repeating past mistakes or rediscovering solutions."
            ),
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
            description=(
                "Recall relevant memories for a given context or question. "
                "Use before starting work to surface past decisions and learnings."
            ),
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
            description=(
                "Record a decision in project memory with reasoning. "
                "Future sessions will benefit from knowing why a choice was made."
            ),
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
            description=(
                "Add a memory entry to the project (note, context, reference, etc.). "
                "Good for capturing insights, gotchas, or creative direction for future reference."
            ),
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
        # -- Batch --
        Tool(
            name="synapse_batch",
            description=(
                "Execute multiple Synapse commands in a single round-trip. "
                "Each command runs in declared order. Wraps in a single undo group "
                "by default so Ctrl+Z reverts the whole batch."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "commands": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Command type (e.g. 'create_node', 'set_parm')"},
                                "payload": {"type": "object", "description": "Command payload"},
                            },
                            "required": ["type"],
                        },
                        "description": "List of commands to execute in order",
                    },
                    "atomic": {
                        "type": "boolean",
                        "description": "Wrap in single undo group (default: true)",
                    },
                    "stop_on_error": {
                        "type": "boolean",
                        "description": "Stop on first error (default: false)",
                    },
                },
                "required": ["commands"],
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
    p = {"content": args["code"]}
    if "dry_run" in args:
        p["dry_run"] = args["dry_run"]
    if "atomic" in args:
        p["atomic"] = args["atomic"]
    return p


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
        alt = args["alternatives"]
        p["alternatives"] = [a.strip() for a in alt.split(",") if a.strip()] if isinstance(alt, str) else alt
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
    "houdini_set_keyframe":     ("set_keyframe",     lambda a: {k: a[k] for k in a}),
    "houdini_render_settings":  ("render_settings",  lambda a: {k: a[k] for k in a}),
    "houdini_wedge":         ("wedge",          lambda a: {k: a[k] for k in a}),
    "houdini_reference_usd": ("reference_usd",  lambda a: {k: a[k] for k in a}),
    "houdini_create_material":  ("create_material",  lambda a: {k: a[k] for k in a}),
    "houdini_assign_material":  ("assign_material",  lambda a: {k: a[k] for k in a}),
    "houdini_read_material":    ("read_material",    lambda a: {k: a[k] for k in a}),
    "synapse_knowledge_lookup": ("knowledge_lookup", lambda a: {"query": a["query"]}),
    "synapse_inspect_selection": ("inspect_selection", lambda a: {k: a[k] for k in a}),
    "synapse_inspect_scene":    ("inspect_scene",     lambda a: {k: a[k] for k in a}),
    "synapse_inspect_node":     ("inspect_node",      lambda a: {k: a[k] for k in a}),
    "synapse_context":       ("context",         _passthrough),
    "synapse_search":        ("search",          lambda a: {"query": a["query"]}),
    "synapse_recall":        ("recall",          lambda a: {"query": a["query"]}),
    "synapse_decide":        ("decide",          _decide_payload),
    "synapse_add_memory":    ("add_memory",      _add_memory_payload),
    "synapse_batch":         ("batch_commands",  lambda a: {k: a[k] for k in a}),
}


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch MCP tool call to Synapse via WebSocket."""
    if name not in TOOL_DISPATCH:
        return [TextContent(type="text", text=f"I don't recognize the tool '{name}' \u2014 check the available tools list")]

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
                return [TextContent(type="text", text=(
                    f"The capture ran but the image file wasn't found at {image_path} \u2014 "
                    "it may have been cleaned up or the path changed"
                ))]

        return [TextContent(type="text", text=_dumps(data))]
    except ConnectionError as e:
        return [TextContent(type="text", text=(
            f"Couldn't reach Synapse \u2014 {e}"
        ))]
    except RuntimeError as e:
        return [TextContent(type="text", text=f"Synapse hit a snag: {e}")]
    except Exception as e:
        logger.exception("Unexpected error in tool %s", name)
        return [TextContent(type="text", text=f"Something unexpected happened: {e}")]


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
        _start_recv_loop()
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
