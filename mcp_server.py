#!/usr/bin/env python3
"""
Synapse MCP Server v2 — Bridge between Claude Desktop and Houdini via WebSocket.

Connects Claude Desktop (stdio/JSON-RPC) to the Synapse WebSocket server
running inside Houdini, giving Claude Desktop full access to Houdini scene
manipulation and project memory.

v2 latency overhaul:
    - Auth handshake: skip 2s recv wait when no local key configured
    - orjson bytes passthrough: send bytes directly over WebSocket, zero-copy
    - Lock-free fast path: volatile check before acquiring _ws_lock
    - asyncio.wait() replaces wait_for() — avoids internal task overhead
    - Recv task race condition fix: explicit cancel + cleanup on reconnect
    - Fire-and-forget warmup: stdio server starts accepting immediately
    - max_size=None: skip frame validation on localhost
    - get_running_loop() everywhere (deprecated get_event_loop removed)

Architecture:
    Claude Desktop  <-[stdio/JSON-RPC]->  mcp_server.py  <-[WebSocket]->  Synapse (Houdini)

Install: pip install mcp websockets
Run: python mcp_server.py
"""

import asyncio
import atexit
import logging
import os
import time
try:
    import orjson
    def _dumps(obj) -> bytes: return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)
    def _dumps_str(obj) -> str: return orjson.dumps(obj, option=orjson.OPT_SORT_KEYS).decode()
    def _loads(s): return orjson.loads(s)
except ImportError:
    import json
    def _dumps(obj) -> bytes: return json.dumps(obj, sort_keys=True).encode()
    def _dumps_str(obj) -> str: return json.dumps(obj, sort_keys=True)
    _loads = json.loads

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ImageContent

import websockets

# ---------------------------------------------------------------------------
# Authentication (client-side handshake)
# ---------------------------------------------------------------------------

def _get_auth_key() -> str | None:
    """Get API key for authenticating with Synapse server.

    Sources (checked in order):
    1. SYNAPSE_API_KEY environment variable
    2. ~/.synapse/auth.key file (first non-empty, non-comment line)
    3. None (auth disabled)
    """
    env_key = os.environ.get("SYNAPSE_API_KEY", "").strip()
    if env_key:
        return env_key
    key_path = os.path.join(os.path.expanduser("~"), ".synapse", "auth.key")
    try:
        if os.path.exists(key_path):
            with open(key_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
    except OSError:
        pass
    return None


async def _auth_handshake(ws) -> None:
    """Handle auth handshake if server requires it.

    v2 optimization: If no local key is configured, skip the 2s recv wait
    entirely. If the server requires auth, the first command will fail with
    a clear error — acceptable trade-off for eliminating 2s dead time on
    every reconnect when auth is disabled (the common case).
    """
    key = _get_auth_key()
    if not key:
        # No key configured — skip the recv wait entirely (saves ~2s)
        return

    # Key exists — wait for auth_required from server
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
        msg = _loads(raw)
    except (asyncio.TimeoutError, Exception):
        # Server didn't send auth_required — auth not enabled server-side
        return

    if msg.get("type") != "auth_required":
        logger.warning("Expected auth_required, got %s (auth may be disabled)", msg.get("type"))
        return

    await ws.send(_dumps({
        "type": "authenticate",
        "id": "auth-handshake",
        "payload": {"key": key},
    }))

    # Wait for auth_success or auth_failed
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
        response = _loads(raw)
    except asyncio.TimeoutError:
        raise ConnectionError("Synapse server didn't respond to authentication within 5s")

    if response.get("type") == "auth_failed":
        raise ConnectionError(
            f"Authentication failed: {response.get('error', 'invalid API key')}. "
            "Check your SYNAPSE_API_KEY or ~/.synapse/auth.key"
        )

    if response.get("type") == "auth_success":
        logger.info("Authenticated with Synapse server")
        return

    logger.warning("Unexpected auth response type: %s", response.get("type"))


# ---------------------------------------------------------------------------
# Deterministic command IDs (He2025: same input → same ID within a session)
# ---------------------------------------------------------------------------
_cmd_seq = 0

def _cmd_id(cmd_type: str, payload: dict | None) -> str:
    global _cmd_seq
    _cmd_seq += 1
    return f"{cmd_type}-{_cmd_seq}"

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
PROTOCOL_VERSION = "5.4.0"
MAX_RETRIES = 2
RETRY_DELAY = 0.05
COMMAND_TIMEOUT = 10.0
_SLOW_COMMANDS = {
    "execute_python": 30.0, "execute_vex": 30.0, "capture_viewport": 30.0,
    "render": 120.0, "wedge": 120.0, "validate_frame": 30.0,
    "render_sequence": 600.0,
    "inspect_selection": 30.0, "inspect_scene": 30.0, "inspect_node": 30.0,
    "network_explain": 30.0,
    "batch_commands": 60.0,
    # TOPS/PDG commands — PDG graph context initialization (getPDGGraphContext,
    # getPDGNode) can block Houdini's main thread for 5-15s on first access.
    # All tops_ commands need at least 60s to survive this cold-start stall.
    "tops_get_work_items": 60.0,
    "tops_get_dependency_graph": 60.0,
    "tops_get_cook_stats": 60.0,
    "tops_cook_node": 120.0,
    "tops_generate_items": 60.0,
    "tops_configure_scheduler": 30.0,
    "tops_cancel_cook": 30.0,
    "tops_dirty_node": 60.0,
    "tops_batch_cook": 300.0,
    "tops_setup_wedge": 30.0,
    "tops_query_items": 60.0,
    "tops_cook_and_validate": 600.0,
    "tops_diagnose": 60.0,
    "tops_pipeline_status": 60.0,
    "tops_monitor_stream": 30.0,
    "tops_render_sequence": 600.0,
    "tops_multi_shot": 600.0,
    "autonomous_render": 600.0,
    "safe_render": 120.0,
    "render_progressively": 120.0,
    "hda_package": 120.0,
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
        return _ws_connection is not None and _ws_connection.state == websockets.connection.State.OPEN
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
        _recv_task = asyncio.get_running_loop().create_task(_recv_loop())


async def _get_connection():
    """Get or create a persistent WebSocket connection.

    v2: Lock-free fast path — volatile check before acquiring the lock.
    The common case (connection alive) skips the lock entirely.
    Double-check inside lock for safety.
    """
    global _ws_connection, _recv_task

    # Lock-free fast path: if connected, return immediately
    if _is_connected():
        return _ws_connection

    async with _ws_lock:
        # Double-check after acquiring lock
        if _is_connected():
            return _ws_connection

        # Force cleanup of stale state — cancel lingering recv task
        # to prevent the race where _start_recv_loop() sees the old
        # task as "not done" and skips creating a new recv loop.
        _ws_connection = None
        if _recv_task is not None and not _recv_task.done():
            _recv_task.cancel()
            try:
                await _recv_task
            except (asyncio.CancelledError, Exception):
                pass
        _recv_task = None
        # Clear any orphaned futures from the dead connection
        _signal_all_pending(ConnectionError("Connection recycled"))

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                _ws_connection = await websockets.connect(
                    SYNAPSE_URL,
                    open_timeout=3.0,
                    close_timeout=5.0,
                    ping_interval=None,
                    compression=None,
                    max_size=None,  # Skip frame size validation on localhost
                )
                await _auth_handshake(_ws_connection)
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
        loop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        _pending[command_id] = future

        try:
            await ws.send(_dumps_str(command))

            # Direct wait on future set — avoids asyncio.wait_for's internal task overhead
            done, _ = await asyncio.wait({future}, timeout=cmd_timeout)
            if not done:
                # Timeout — future still pending
                _pending.pop(command_id, None)
                future.cancel()
                raise asyncio.TimeoutError()
            response = future.result()
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

# ---------------------------------------------------------------------------
# Tool group modules — knowledge preambles and manifests
# ---------------------------------------------------------------------------
import mcp_tools_scene
import mcp_tools_render
import mcp_tools_usd
import mcp_tools_tops
import mcp_tools_memory

TOOL_GROUPS = {
    "scene": mcp_tools_scene,
    "render": mcp_tools_render,
    "usd": mcp_tools_usd,
    "tops": mcp_tools_tops,
    "memory": mcp_tools_memory,
}


@server.list_tools()
async def list_tools():
    """Register all Synapse MCP tools.

    Tools are organized into 5 groups with domain knowledge preambles:
    - Scene: Node graph manipulation, parameters, execution, introspection
    - Render: Karma/Mantra rendering, viewport, validation, farm
    - USD: Stage assembly, materials, composition, light linking
    - TOPS: PDG pipelines, wedging, batch cooking, monitoring
    - Memory: Project memory, knowledge lookup, HDA, metrics
    """
    return [
        # ===================================================================
        # GROUP: SCENE (mcp_tools_scene.py)
        # Knowledge: Always inspect before mutating. One mutation per call.
        # Parameter names on USD nodes use encoded format.
        # ===================================================================
        Tool(
            name="synapse_group_scene",
            description=(
                "[TOOL GROUP: Scene / Node / Parameters] "
                + mcp_tools_scene.GROUP_KNOWLEDGE
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
                "For USD/Solaris nodes, parameter names are encoded "
                "(e.g. xn__inputsintensity_i0a not 'intensity'). "
                "Use houdini_inspect_node first to discover exact names. "
                "When reporting success, describe the change in artist-friendly terms "
                "(e.g. 'Bumped the light exposure to 3.0') rather than raw parameter names."
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
                "ONE mutation per call. Never combine node creation + connection + "
                "parameter setting in a single call. "
                "The code runs with 'hou' module available. "
                "Set a 'result' variable to return data. "
                "Result is wrapped in undo group -- automatic rollback on failure. "
                "When presenting results: celebrate progress, explain errors in "
                "plain language with next steps, and frame everything as "
                "collaborative iteration -- 'we tried X, let's adjust' not 'X failed'."
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
        Tool(
            name="houdini_execute_vex",
            description=(
                "Execute VEX code by creating an Attribute Wrangle node. "
                "Specify the VEX snippet, run-over class (Points/Primitives/Vertices/Detail), "
                "and optional input geometry node. Returns the wrangle node path."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "snippet": {
                        "type": "string",
                        "description": "VEX code to execute (the wrangle snippet)",
                    },
                    "run_over": {
                        "type": "string",
                        "description": "What to run over: Points, Primitives, Vertices, or Detail (default: Points)",
                    },
                    "input_node": {
                        "type": "string",
                        "description": "Optional input geometry node path to wire into the wrangle",
                    },
                },
                "required": ["snippet"],
            },
        ),
        # ===================================================================
        # GROUP: USD / SOLARIS / MATERIALS (mcp_tools_usd.py)
        # Knowledge: Encoded parameter names (xn__inputs*). Inspect first.
        # Composition: stronger opinions win. Layer order matters.
        # matlib.cook(force=True) before createNode() on shader children.
        # ===================================================================
        Tool(
            name="synapse_group_usd",
            description=(
                "[TOOL GROUP: USD / Solaris / Materials] "
                + mcp_tools_usd.GROUP_KNOWLEDGE
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
        # ===================================================================
        # GROUP: RENDER / VIEWPORT (mcp_tools_render.py)
        # Knowledge: Intensity ALWAYS 1.0. Brightness via exposure (stops).
        # Start at 256x256 with 4-8 samples. Never soho_foreground=1 for
        # heavy scenes. Karma camera = USD prim path, not node path.
        # ===================================================================
        Tool(
            name="synapse_group_render",
            description=(
                "[TOOL GROUP: Render / Viewport / Keyframe] "
                + mcp_tools_render.GROUP_KNOWLEDGE
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
        # -- Frame Validation --
        Tool(
            name="synapse_validate_frame",
            description=(
                "Validate a rendered frame for common quality issues: black frames, "
                "NaN/Inf pixels, clipping (overexposure), underexposure, and firefly "
                "artifacts. Uses OpenImageIO for fast C++-level pixel analysis. "
                "Returns structured pass/fail results per check. "
                "Great for automated QC after rendering."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "image_path": {
                        "type": "string",
                        "description": "Path to the rendered image file (EXR, JPEG, PNG, etc.)",
                    },
                    "checks": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of checks to run. Default: all. "
                            "Available: file_integrity, black_frame, nan_check, "
                            "clipping, underexposure, saturation"
                        ),
                    },
                    "thresholds": {
                        "type": "object",
                        "description": (
                            "Optional threshold overrides. Keys: black_frame_mean, "
                            "clipping_pct, underexposure_mean, saturation_pct, "
                            "saturation_multiplier"
                        ),
                    },
                },
                "required": ["image_path"],
            },
        ),
        Tool(
            name="synapse_configure_render_passes",
            description=(
                "Configure render passes (AOVs) for Karma. Creates RenderVar prims for compositing. "
                "Presets: beauty, diffuse, specular, emission, normal, depth, position, albedo, "
                "crypto_material, crypto_object, motion, sss."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node to wire after (optional)"},
                    "passes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of pass names (e.g. ['beauty', 'diffuse', 'normal', 'crypto_object'])",
                    },
                    "clear_existing": {"type": "boolean", "description": "Clear existing render vars first (default: false)"},
                },
                "required": ["passes"],
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
        # ===================================================================
        # GROUP: TOPS / PDG (mcp_tools_tops.py)
        # Knowledge: Generate items first, then cook. pipeline_status for
        # health checks, diagnose for failures. cook_and_validate auto-retries.
        # tops_render_sequence for frame ranges. tops_multi_shot for cameras.
        # ===================================================================
        Tool(
            name="synapse_group_tops",
            description=(
                "[TOOL GROUP: TOPS / PDG] "
                + mcp_tools_tops.GROUP_KNOWLEDGE
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
        # -- TOPS / PDG (Phase 1) --
        Tool(
            name="tops_get_work_items",
            description=(
                "Get work items from a TOP node with optional state filtering. "
                "Returns item details including id, index, name, state, cook time, "
                "and attributes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "state_filter": {
                        "type": "string",
                        "description": "Filter by state: all, cooked, failed, cooking, scheduled, uncooked, cancelled (default: all)",
                    },
                    "include_attributes": {
                        "type": "boolean",
                        "description": "Include work item attributes (default: true)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items to return (default: 100)",
                    },
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_get_dependency_graph",
            description=(
                "Get the dependency graph for a TOP network: nodes, types, "
                "work item counts by state, and edges between nodes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topnet_path": {"type": "string", "description": "TOP network path"},
                    "depth": {"type": "integer", "description": "Traversal depth (-1 for full, default: -1)"},
                },
                "required": ["topnet_path"],
            },
        ),
        Tool(
            name="tops_get_cook_stats",
            description=(
                "Get cook statistics for a TOP node or network: "
                "work item counts by state and total cook times."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node or network path"},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_cook_node",
            description=(
                "Cook a TOP node. Supports blocking (wait for completion) and "
                "non-blocking modes. Use generate_only=true to create work items "
                "without cooking them."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "generate_only": {"type": "boolean", "description": "Generate only, don't cook (default: false)"},
                    "blocking": {"type": "boolean", "description": "Wait for cook to complete (default: true)"},
                    "top_down": {"type": "boolean", "description": "Cook upstream first (default: true)"},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_generate_items",
            description=(
                "Generate work items for a TOP node without cooking. "
                "Preview what a node will produce before running the cook."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                },
                "required": ["node"],
            },
        ),
        # -- TOPS / PDG (Phase 2: Scheduler & Control) --
        Tool(
            name="tops_configure_scheduler",
            description=(
                "Configure the scheduler for a TOP network: type, max concurrent "
                "processes, and working directory."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topnet_path": {"type": "string", "description": "TOP network path"},
                    "scheduler_type": {"type": "string", "description": "Scheduler type (default: local)"},
                    "max_concurrent": {"type": "integer", "description": "Max concurrent processes"},
                    "working_dir": {"type": "string", "description": "PDG working directory"},
                },
                "required": ["topnet_path"],
            },
        ),
        Tool(
            name="tops_cancel_cook",
            description=(
                "Cancel an active cook on a TOP node or network. "
                "Currently cooking items may finish before cancellation takes effect."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node or network path"},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_dirty_node",
            description=(
                "Dirty a TOP node to clear cached work item results, forcing a re-cook. "
                "Use dirty_upstream=true to also dirty upstream dependencies."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "dirty_upstream": {"type": "boolean", "description": "Also dirty upstream (default: false)"},
                },
                "required": ["node"],
            },
        ),
        # -- TOPS / PDG (Phase 3: Advanced) --
        Tool(
            name="tops_setup_wedge",
            description=(
                "Set up a Wedge TOP node for parameter variation exploration. "
                "Define attributes with name, type, start, end, and steps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topnet_path": {"type": "string", "description": "TOP network path"},
                    "wedge_name": {"type": "string", "description": "Wedge node name (default: wedge1)"},
                    "attributes": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of {name, type, start, end, steps}",
                    },
                },
                "required": ["topnet_path", "attributes"],
            },
        ),
        Tool(
            name="tops_batch_cook",
            description=(
                "Cook multiple TOP nodes in sequence. Collects per-node results "
                "including status, work item counts, and cook times."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of TOP node paths to cook",
                    },
                    "blocking": {"type": "boolean", "description": "Wait for each cook (default: true)"},
                    "stop_on_error": {"type": "boolean", "description": "Stop on first error (default: true)"},
                },
                "required": ["node_paths"],
            },
        ),
        Tool(
            name="tops_query_items",
            description=(
                "Query work items by attribute value. Supports operators: "
                "eq, gt, lt, gte, lte, contains, regex."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "query_attribute": {"type": "string", "description": "Attribute name to filter on"},
                    "filter_op": {
                        "type": "string",
                        "enum": ["eq", "gt", "lt", "gte", "lte", "contains", "regex"],
                        "description": "Filter operator (default: eq)",
                    },
                    "filter_value": {"description": "Value to match against"},
                },
                "required": ["node", "query_attribute", "filter_value"],
            },
        ),
        # -- TOPS / PDG (Phase 4: Autonomous Operations) --
        Tool(
            name="tops_cook_and_validate",
            description=(
                "Cook a TOP node with automatic retry on failure. "
                "Self-healing pipeline: cook -> validate states -> "
                "dirty -> retry. Returns per-attempt details and aggregate stats."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "max_retries": {"type": "integer", "description": "Max retry attempts on failure (default: 0)"},
                    "validate_states": {"type": "boolean", "description": "Check work item states after cook (default: true)"},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_diagnose",
            description=(
                "Diagnose failures on a TOP node: inspect failed work items, "
                "scheduler config, upstream dependencies, and generate suggestions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node path"},
                    "include_scheduler": {"type": "boolean", "description": "Include scheduler info (default: true)"},
                    "include_dependencies": {"type": "boolean", "description": "Include upstream check (default: true)"},
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_pipeline_status",
            description=(
                "Full health check for a TOP network: per-node status, "
                "aggregate stats, issues, and suggestions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topnet_path": {"type": "string", "description": "TOP network path"},
                    "include_items": {"type": "boolean", "description": "Include per-node work items (default: false)"},
                },
                "required": ["topnet_path"],
            },
        ),
        # -- TOPS / PDG (Phase 5: Streaming & Render Integration) --
        Tool(
            name="tops_monitor_stream",
            description=(
                "Start, stop, or check status of event-driven TOPS cook monitoring. "
                "Push-based alternative to polling \u2014 registers PDG event callbacks "
                "that track work_item_started, work_item_completed, work_item_failed, "
                "cook_progress, and cook_complete events. "
                "Use action='start' to begin, action='status' to check, action='stop' to end."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "TOP node or network path to monitor"},
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "status"],
                        "description": "Action: start monitoring, stop monitoring, or check status (default: start)",
                    },
                    "monitor_id": {
                        "type": "string",
                        "description": "Monitor ID (required for stop/status, returned by start)",
                    },
                },
                "required": ["node"],
            },
        ),
        Tool(
            name="tops_render_sequence",
            description=(
                "Render a frame sequence via TOPS/PDG. Single-call interface for "
                "'render frames 1\u201348'. Validates the Solaris stage, creates (or reuses) "
                "a TOPS network with ROP fetch, sets frame range and render settings, "
                "generates work items, and starts the cook. Returns a job_id for tracking. "
                "Idempotent \u2014 reuses existing network if one matches."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "start_frame": {"type": "integer", "description": "First frame to render"},
                    "end_frame": {"type": "integer", "description": "Last frame to render (inclusive)"},
                    "step": {"type": "integer", "description": "Frame step (default: 1)"},
                    "camera": {"type": "string", "description": "Camera USD prim path (e.g. /cameras/render_cam)"},
                    "output_dir": {"type": "string", "description": "Output directory for rendered frames"},
                    "output_prefix": {"type": "string", "description": "Filename prefix (default: render)"},
                    "rop_node": {"type": "string", "description": "ROP node path (auto-discovers if omitted)"},
                    "topnet_path": {"type": "string", "description": "Existing TOP network path to reuse"},
                    "pixel_samples": {"type": "integer", "description": "Override pixel samples"},
                    "resolution": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Override resolution [width, height]",
                    },
                    "blocking": {"type": "boolean", "description": "Wait for cook to complete (default: false)"},
                },
                "required": ["start_frame", "end_frame"],
            },
        ),
        Tool(
            name="tops_multi_shot",
            description=(
                "Create a TOPS network for multi-shot rendering. Accepts a list "
                "of shot definitions (name, frame range, camera, overrides), creates "
                "per-shot work items in a genericgenerator, feeds into ropfetch for "
                "rendering, partitions results by shot name. Returns a job_id for monitoring."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "shots": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Shot name (e.g. sq010_sh010)"},
                                "frame_start": {"type": "integer", "description": "First frame (default: 1001)"},
                                "frame_end": {"type": "integer", "description": "Last frame (default: 1048)"},
                                "camera": {"type": "string", "description": "Camera USD prim path"},
                                "overrides": {"type": "object", "description": "Shot-specific parameter overrides"},
                            },
                            "required": ["name"],
                        },
                        "description": "List of shot definitions",
                    },
                    "topnet_path": {"type": "string", "description": "Existing TOP network path to reuse"},
                    "renderer": {"type": "string", "description": "Renderer (default: karma_xpu)"},
                    "output_dir": {"type": "string", "description": "Base output directory (default: $HIP/render)"},
                    "camera_pattern": {"type": "string", "description": "Camera path template (default: /cameras/{shot}_cam)"},
                    "rop_node": {"type": "string", "description": "ROP node path (auto-discovers if omitted)"},
                    "blocking": {"type": "boolean", "description": "Wait for cook to complete (default: false)"},
                    "encode_movie": {"type": "boolean", "description": "Add ffmpeg encode per shot (default: false)"},
                },
                "required": ["shots"],
            },
        ),
        # -- USD Scene Assembly --
        Tool(
            name="houdini_reference_usd",
            description=(
                "Import a USD file into the stage via reference, payload, or sublayer. "
                "Payload mode uses deferred loading for heavy assets. "
                "For Karma rendering, sublayer is the most reliable import mode."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {"type": "string", "description": "Path to USD file (.usd, .usdc, .usda)"},
                    "prim_path": {"type": "string", "description": "Target prim path for reference. Default: /"},
                    "mode": {"type": "string", "enum": ["reference", "payload", "sublayer"],
                             "description": "Import mode: reference (default), payload (deferred load), or sublayer (most Karma-compatible)"},
                    "parent": {"type": "string", "description": "Parent LOP network path. Default: /stage"},
                },
                "required": ["file"],
            },
        ),
        Tool(
            name="houdini_query_prims",
            description=(
                "Query USD stage prims with filtering by type, purpose, and name pattern. "
                "Returns matching prims with their paths, types, and metadata."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node path. If omitted, uses current selection."},
                    "root_path": {"type": "string", "description": "USD prim path to start walking from (default: /)"},
                    "prim_type": {"type": "string", "description": "Filter by USD type name (e.g. 'Mesh', 'DomeLight', 'Material')"},
                    "purpose": {"type": "string", "description": "Filter by purpose (e.g. 'default', 'render', 'proxy', 'guide')"},
                    "name_pattern": {"type": "string", "description": "Regex or substring filter on prim name"},
                    "max_depth": {"type": "integer", "description": "Max traversal depth (default: 10)"},
                    "limit": {"type": "integer", "description": "Max prims to return (default: 100)"},
                },
                "required": [],
            },
        ),
        Tool(
            name="houdini_manage_variant_set",
            description=(
                "Manage USD variant sets on a prim: list, create, or select variants. "
                "Use 'list' to see existing variant sets, 'create' to add a new set "
                "with named variants, or 'select' to switch the active variant."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node path. If omitted, uses current selection."},
                    "prim_path": {"type": "string", "description": "USD prim path to manage variants on"},
                    "action": {"type": "string", "enum": ["list", "create", "select"],
                               "description": "Action to perform (default: list)"},
                    "variant_set": {"type": "string", "description": "Variant set name (required for create/select)"},
                    "variants": {"type": "array", "items": {"type": "string"},
                                 "description": "Variant names to create (required for create action)"},
                    "variant": {"type": "string", "description": "Variant to select (required for select action)"},
                },
                "required": ["prim_path"],
            },
        ),
        Tool(
            name="houdini_manage_collection",
            description=(
                "Manage USD collections on a prim for light linking, material assignment, "
                "and grouping. Use 'list' to see existing collections, 'create' to make a "
                "new collection with include/exclude paths, 'add'/'remove' to modify paths."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node path. If omitted, uses current selection."},
                    "prim_path": {"type": "string", "description": "USD prim path to manage collections on"},
                    "action": {"type": "string", "enum": ["list", "create", "add", "remove"],
                               "description": "Action to perform (default: list)"},
                    "collection_name": {"type": "string", "description": "Collection name (required for create/add/remove)"},
                    "paths": {"type": "array", "items": {"type": "string"},
                              "description": "Prim paths to include (required for create/add/remove)"},
                    "exclude_paths": {"type": "array", "items": {"type": "string"},
                                      "description": "Prim paths to exclude (optional, create only)"},
                    "expansion_rule": {"type": "string", "enum": ["expandPrims", "expandPrimsAndProperties", "explicitOnly"],
                                       "description": "Collection expansion rule (default: expandPrims)"},
                },
                "required": ["prim_path"],
            },
        ),
        # -- Materials --
        Tool(
            name="houdini_create_textured_material",
            description=(
                "Create a production MaterialX material with texture file inputs. "
                "Supports diffuse, roughness, metalness, normal, opacity, and displacement maps. "
                "Handles UDIM textures and UV coordinate wiring automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node to wire after (optional)"},
                    "name": {"type": "string", "description": "Material name (default: textured_material)"},
                    "diffuse_map": {"type": "string", "description": "Path to diffuse/albedo texture file"},
                    "roughness_map": {"type": "string", "description": "Path to roughness texture file"},
                    "metalness_map": {"type": "string", "description": "Path to metalness texture file"},
                    "normal_map": {"type": "string", "description": "Path to normal map texture file"},
                    "displacement_map": {"type": "string", "description": "Path to displacement map texture file"},
                    "opacity_map": {"type": "string", "description": "Path to opacity/alpha texture file"},
                    "roughness": {"type": "number", "description": "Scalar roughness fallback if no texture (0-1)"},
                    "metalness": {"type": "number", "description": "Scalar metalness fallback if no texture (0-1)"},
                    "geo_pattern": {"type": "string", "description": "Optional geometry prim pattern to auto-assign material"},
                },
                "required": [],
            },
        ),
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
                    "opacity": {
                        "type": "number",
                        "description": "Opacity 0-1 (1=fully opaque)",
                    },
                    "emission": {
                        "type": "number",
                        "description": "Emission weight 0-1",
                    },
                    "emission_color": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Emission color [r, g, b] 0-1",
                    },
                    "subsurface": {
                        "type": "number",
                        "description": "Subsurface scattering weight 0-1",
                    },
                    "subsurface_color": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Subsurface color [r, g, b] 0-1",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="houdini_configure_light_linking",
            description=(
                "Configure light linking between lights and geometry via USD collections. "
                "Control which geometry a light illuminates or casts shadows on."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {"type": "string", "description": "LOP node path. If omitted, uses current selection."},
                    "light_path": {"type": "string", "description": "USD prim path of the light"},
                    "action": {
                        "type": "string",
                        "enum": ["include", "exclude", "shadow_include", "shadow_exclude", "reset"],
                        "description": "Light linking action (default: include)",
                    },
                    "geo_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Geometry prim paths to include/exclude (not needed for reset)",
                    },
                },
                "required": ["light_path"],
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
        # ===================================================================
        # GROUP: MEMORY / KNOWLEDGE / HDA (mcp_tools_memory.py)
        # Knowledge: Call synapse_project_setup FIRST in every session.
        # Use knowledge_lookup before guessing parameter names.
        # Memory: Charmander->Charmeleon->Charizard evolution.
        # HDA: hda_package is the high-level orchestrator.
        # ===================================================================
        Tool(
            name="synapse_group_memory",
            description=(
                "[TOOL GROUP: Memory / Knowledge / HDA] "
                + mcp_tools_memory.GROUP_KNOWLEDGE
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
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
        # -- Network Explain --
        Tool(
            name="houdini_network_explain",
            description=(
                "Walk a Houdini node network and produce a structured explanation: "
                "data flow order, detected workflow patterns (scatter, terrain, simulation, "
                "VDB, etc.), non-default parameter values, and suggested parameters to "
                "promote for HDA interfaces."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "root_path": {
                        "type": "string",
                        "description": "Path to network root (e.g. '/obj/geo1')",
                    },
                    "depth": {
                        "type": "integer",
                        "description": "How deep to traverse subnets (default: 2, max: 5)",
                    },
                    "detail_level": {
                        "type": "string",
                        "enum": ["summary", "standard", "detailed"],
                        "description": "Level of detail (default: standard)",
                    },
                    "include_parameters": {
                        "type": "boolean",
                        "description": "Include key non-default parameter values (default: true)",
                    },
                    "include_expressions": {
                        "type": "boolean",
                        "description": "Include channel expressions (default: false)",
                    },
                    "format": {
                        "type": "string",
                        "enum": ["prose", "structured", "help_card"],
                        "description": "Output format (default: structured)",
                    },
                },
                "required": ["root_path"],
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
        # -- Scene Memory (Living Memory System) --
        Tool(
            name="synapse_project_setup",
            description=(
                "Call this FIRST in every session. "
                "Returns project memory, scene memory, agent state, and evolution stage. "
                "Without this, you have no context about the artist's project. "
                "Creates project directories and seeds memory files if needed. "
                "Idempotent -- safe to call multiple times."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force_refresh": {
                        "type": "boolean",
                        "description": "Force re-read all memory files even if cached. Default: false",
                    },
                },
            },
        ),
        Tool(
            name="synapse_memory_write",
            description=(
                "Write a memory entry to scene or project memory. "
                "Handles markdown vs USD format automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_type": {
                        "type": "string",
                        "enum": [
                            "decision", "parameter_experiment", "blocker",
                            "blocker_resolved", "asset_reference", "wedge_result",
                            "note", "session_end",
                        ],
                        "description": "Type of memory entry",
                    },
                    "content": {
                        "type": "object",
                        "description": "Entry content -- structure depends on entry_type",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["scene", "project", "both"],
                        "description": "Where to write. Default: scene",
                    },
                },
                "required": ["entry_type", "content"],
            },
        ),
        Tool(
            name="synapse_memory_query",
            description=(
                "Query scene or project memory. Text search in Charmander (markdown), "
                "structured queries in Charmeleon+ (USD)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["scene", "project", "all"],
                        "description": "Search scope. Default: all",
                    },
                    "type_filter": {
                        "type": "string",
                        "enum": [
                            "all", "decisions", "parameters",
                            "blockers", "assets", "sessions",
                        ],
                        "description": "Filter by entry type. Default: all",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="synapse_memory_status",
            description=(
                "Get memory system status: evolution stage, file sizes, "
                "session count, agent state."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        # -- Evolution --
        Tool(
            name="synapse_evolve_memory",
            description=(
                "Manually trigger memory evolution (Charmander->Charmeleon "
                "or Charmeleon->Charizard). Use dry_run=true to preview."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["scene", "project"]},
                    "target_stage": {"type": "string", "enum": ["charmeleon", "charizard"]},
                    "dry_run": {"type": "boolean", "description": "Preview without evolving. Default: true"},
                },
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
        # -- Metrics / Stats --
        Tool(
            name="synapse_metrics",
            description=(
                "Get Synapse metrics in Prometheus text format. "
                "Includes per-tier request counts, latencies, circuit breaker state, "
                "and memory store size. Use for observability and debugging."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="synapse_router_stats",
            description=(
                "Get tier cascade routing statistics. Shows per-tier counts, latencies, "
                "epoch adaptation state, cache hit rates, and knowledge index coverage. "
                "Helps the LLM reason about its own routing performance."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="synapse_list_recipes",
            description=(
                "List all available recipes with names, descriptions, trigger patterns, "
                "and categories. Artists can ask 'what recipes are available?' to discover "
                "pre-built automation workflows."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="synapse_live_metrics",
            description=(
                "Get live metrics snapshot: scene health, routing performance, "
                "resilience state, and session stats. Pass history_count > 0 for "
                "historical snapshots (newest first)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "history_count": {
                        "type": "integer",
                        "description": "Number of historical snapshots to return (0 = latest only)",
                    },
                },
                "required": [],
            },
        ),
        # -- Render Farm --
        Tool(
            name="synapse_render_sequence",
            description=(
                "Render a frame range with per-frame validation, automatic issue "
                "diagnosis, and self-improving fixes. Learns from each render to "
                "start smarter next time."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rop": {
                        "type": "string",
                        "description": "ROP node path (auto-discovers if omitted)",
                    },
                    "start_frame": {
                        "type": "integer",
                        "description": "First frame to render",
                    },
                    "end_frame": {
                        "type": "integer",
                        "description": "Last frame to render (inclusive)",
                    },
                    "step": {
                        "type": "integer",
                        "description": "Frame step (default: 1)",
                    },
                    "auto_fix": {
                        "type": "boolean",
                        "description": "Auto-diagnose and fix issues (default: true)",
                    },
                    "max_retries": {
                        "type": "integer",
                        "description": "Max retries per frame (default: 3)",
                    },
                },
                "required": ["start_frame", "end_frame"],
            },
        ),
        Tool(
            name="synapse_render_farm_status",
            description=(
                "Check progress of a running render farm job: running state, "
                "scene tags, current frame."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        # -- Autonomous Render --
        Tool(
            name="synapse_autonomous_render",
            description=(
                "Execute an autonomous render loop: plan the render from intent, "
                "validate the scene, execute via TOPS, evaluate quality, and "
                "re-render if needed. Returns a full report with plan, evaluation, "
                "decisions, and success flag."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "What to render (e.g., 'render frames 1-48', 'render turntable with ARRI Alexa 35 at 50mm')",
                    },
                    "max_iterations": {
                        "type": "integer",
                        "default": 3,
                        "description": "Max re-render attempts if quality check fails",
                    },
                    "quality_threshold": {
                        "type": "number",
                        "default": 0.85,
                        "description": "Minimum quality score (0.0-1.0) for frames to pass",
                    },
                },
                "required": ["intent"],
            },
        ),
        # -- Safe / Progressive Render --
        Tool(
            name="synapse_safe_render",
            description=(
                "Render with pre-flight validation. Checks camera, materials, and "
                "output path before rendering. Auto-forces background mode for "
                "high-resolution renders to prevent Houdini lockup."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rop_path": {
                        "type": "string",
                        "description": "Path to the usdrender ROP node (auto-discovered if omitted)",
                    },
                    "soho_foreground": {
                        "type": "integer",
                        "enum": [0, 1],
                        "description": "Force foreground (1) or background (0) rendering. If omitted, auto-decides based on resolution.",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="synapse_render_progressively",
            description=(
                "Progressive 3-pass render: test (256x256, 4 samples) -> preview "
                "(720p, 16 samples) -> production (user settings). Validates each "
                "pass before proceeding."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "rop_path": {
                        "type": "string",
                        "description": "Path to the usdrender ROP node (auto-discovered if omitted)",
                    },
                    "resolution": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Production resolution [width, height]. Default: [1920, 1080]",
                    },
                    "samples": {
                        "type": "integer",
                        "description": "Production pixel samples. Default: 64",
                    },
                },
                "required": [],
            },
        ),
        # -- Undo / Redo --
        Tool(
            name="houdini_undo",
            description=(
                "Undo the last Houdini operation. Steps back one undo level. "
                "Use this to roll back a change that didn't work out."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="houdini_redo",
            description=(
                "Redo the last undone Houdini operation. Steps forward one undo level. "
                "Use this to restore a change after an undo."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # -- Solaris Ordering Validation --
        Tool(
            name="synapse_validate_ordering",
            description=(
                "Walk a LOP network backwards from the render node, detecting "
                "ambiguous merge points where input order affects USD opinion "
                "strength. Flags merge and sublayer LOPs with 2+ inputs as "
                "potential ordering issues. Use this before rendering to catch "
                "unintended layer composition problems."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "node": {
                        "type": "string",
                        "description": "Starting node path (render ROP or Karma LOP). Auto-discovers if omitted.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum traversal depth (default: 50)",
                    },
                },
                "required": [],
            },
        ),
        # -- HDA (Houdini Digital Asset) --
        Tool(
            name="houdini_hda_create",
            description=(
                "Convert a subnet into a Houdini Digital Asset (HDA). "
                "Wraps the subnet, sets metadata (author, version), and installs the .hda file. "
                "The subnet must already exist -- use create_node to build it first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "subnet_path": {
                        "type": "string",
                        "description": "Path to the subnet node to convert (e.g. '/obj/geo1/my_subnet')",
                    },
                    "operator_name": {
                        "type": "string",
                        "description": "Internal operator type name (e.g. 'my_tool')",
                    },
                    "operator_label": {
                        "type": "string",
                        "description": "Human-readable label (e.g. 'My Tool')",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Sop", "Object", "Driver", "Lop", "Top"],
                        "description": "Node category for the HDA",
                    },
                    "version": {
                        "type": "string",
                        "description": "SemVer version string (default: '1.0.0')",
                    },
                    "save_path": {
                        "type": "string",
                        "description": "File path to save the .hda file",
                    },
                    "min_inputs": {
                        "type": "integer",
                        "description": "Minimum number of inputs (default: 0)",
                    },
                    "max_inputs": {
                        "type": "integer",
                        "description": "Maximum number of inputs (default: 1)",
                    },
                    "icon": {
                        "type": "string",
                        "description": "Optional icon name (e.g. 'SOP_subnet')",
                    },
                },
                "required": ["subnet_path", "operator_name", "operator_label", "category", "save_path"],
            },
        ),
        Tool(
            name="houdini_hda_promote_parm",
            description=(
                "Promote an internal node parameter to the HDA's top-level interface. "
                "Creates a channel reference so the promoted parm drives the internal one. "
                "Idempotent -- re-promoting updates rather than duplicates."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hda_path": {
                        "type": "string",
                        "description": "Path to the HDA instance node",
                    },
                    "internal_node": {
                        "type": "string",
                        "description": "Relative path to internal node (e.g. 'scatter1')",
                    },
                    "parm_name": {
                        "type": "string",
                        "description": "Parameter name on the internal node",
                    },
                    "label": {
                        "type": "string",
                        "description": "Optional label override for the promoted parameter",
                    },
                    "folder": {
                        "type": "string",
                        "description": "Optional folder/tab name to place the parameter in",
                    },
                    "callback": {
                        "type": "string",
                        "description": "Optional Python callback script",
                    },
                    "conditions": {
                        "type": "object",
                        "description": "Optional visibility conditions",
                    },
                },
                "required": ["hda_path", "internal_node", "parm_name"],
            },
        ),
        Tool(
            name="houdini_hda_set_help",
            description=(
                "Set help documentation on an HDA. Generates Houdini wiki markup "
                "from structured inputs -- summary, description, per-parameter help, and tips."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "hda_path": {
                        "type": "string",
                        "description": "Path to the HDA instance node",
                    },
                    "summary": {
                        "type": "string",
                        "description": "Short summary for the HDA",
                    },
                    "description": {
                        "type": "string",
                        "description": "Full description (supports Houdini wiki markup)",
                    },
                    "parameters_help": {
                        "type": "object",
                        "description": "Mapping of {parm_name: help_text}",
                    },
                    "tips": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tip strings",
                    },
                    "author": {
                        "type": "string",
                        "description": "Author name",
                    },
                },
                "required": ["hda_path"],
            },
        ),
        Tool(
            name="houdini_hda_package",
            description=(
                "High-level HDA orchestrator: create a subnet, convert to HDA, promote parameters, "
                "and set help documentation -- all in one call. Runs inside a single undo group "
                "so the whole thing rolls back on failure. This is the go-to tool for creating "
                "HDAs from a description."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "What the HDA should do",
                    },
                    "name": {
                        "type": "string",
                        "description": "Operator name (e.g. 'scatter_on_surface')",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Sop", "Object", "Driver", "Lop", "Top"],
                        "description": "Node category for the HDA",
                    },
                    "save_path": {
                        "type": "string",
                        "description": "File path to save the .hda file",
                    },
                    "inputs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of input descriptions",
                    },
                    "promoted_parms": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "node": {"type": "string", "description": "Internal node name"},
                                "parm": {"type": "string", "description": "Parameter name"},
                                "label": {"type": "string", "description": "Display label"},
                            },
                            "required": ["node", "parm"],
                        },
                        "description": "Parameters to promote to HDA interface",
                    },
                    "nodes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string", "description": "Node type to create"},
                                "name": {"type": "string", "description": "Node name"},
                                "parms": {"type": "object", "description": "Parameter values to set"},
                            },
                            "required": ["type"],
                        },
                        "description": "Internal nodes to create inside the subnet before HDA conversion",
                    },
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "description": (
                            "Connections as [src_name, dst_name, dst_input_idx] triples. "
                            "Use '__input0' for the subnet's first indirect input."
                        ),
                    },
                },
                "required": ["description", "name", "category", "save_path"],
            },
        ),
        Tool(
            name="houdini_hda_list",
            description=(
                "List all Synapse-authored HDAs currently loaded in Houdini. "
                "Scans loaded HDA files and filters for definitions with "
                "author=synapse metadata. Read-only, no scene changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

# Payload builders imported from synapse.mcp.tools (single source of truth).
# mcp/tools.py only imports json, time, orjson (optional), and core.protocol — no hou dependency.
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "python"))
from synapse.mcp.tools import (
    passthrough as _passthrough,
    identity as _identity,
    execute_python_payload as _execute_python_payload,
    stage_info_payload as _stage_info_payload,
    decide_payload as _decide_payload,
    add_memory_payload as _add_memory_payload,
    filter_keys as _filter_keys,
)

# Map MCP tool name -> (synapse_command_type, payload_builder)
TOOL_DISPATCH: dict[str, tuple[str, callable]] = {
    "synapse_ping":          ("ping",            _passthrough),
    "synapse_health":        ("get_health",      _passthrough),
    "houdini_scene_info":    ("get_scene_info",  _passthrough),
    "houdini_get_selection": ("get_selection",    _passthrough),
    "houdini_create_node":   ("create_node",     _identity),
    "houdini_delete_node":   ("delete_node",     _filter_keys(["node"])),
    "houdini_connect_nodes": ("connect_nodes",   _identity),
    "houdini_get_parm":      ("get_parm",        _filter_keys(["node", "parm"])),
    "houdini_set_parm":      ("set_parm",        _filter_keys(["node", "parm", "value"])),
    "houdini_execute_python":("execute_python",  _execute_python_payload),
    "houdini_execute_vex":   ("execute_vex",    _identity),
    "houdini_stage_info":    ("get_stage_info",  _stage_info_payload),
    "houdini_get_usd_attribute":  ("get_usd_attribute",  _filter_keys(["node", "prim_path", "attribute_name"])),
    "houdini_set_usd_attribute":  ("set_usd_attribute",  _filter_keys(["node", "prim_path", "attribute_name", "value"])),
    "houdini_create_usd_prim":    ("create_usd_prim",    _filter_keys(["node", "prim_path", "prim_type"])),
    "houdini_modify_usd_prim":    ("modify_usd_prim",    _filter_keys(["node", "prim_path", "kind", "purpose", "active"])),
    "houdini_capture_viewport": ("capture_viewport", _identity),
    "houdini_render":           ("render",           _identity),
    "houdini_set_keyframe":     ("set_keyframe",     _identity),
    "houdini_render_settings":  ("render_settings",  _identity),
    "houdini_wedge":         ("wedge",          _identity),
    "tops_get_work_items":        ("tops_get_work_items",        _identity),
    "tops_get_dependency_graph":  ("tops_get_dependency_graph",  _identity),
    "tops_get_cook_stats":        ("tops_get_cook_stats",        _identity),
    "tops_cook_node":             ("tops_cook_node",             _identity),
    "tops_generate_items":        ("tops_generate_items",        _identity),
    "tops_configure_scheduler":   ("tops_configure_scheduler",   _identity),
    "tops_cancel_cook":           ("tops_cancel_cook",           _identity),
    "tops_dirty_node":            ("tops_dirty_node",            _identity),
    "tops_setup_wedge":           ("tops_setup_wedge",           _identity),
    "tops_batch_cook":            ("tops_batch_cook",            _identity),
    "tops_query_items":           ("tops_query_items",           _identity),
    "tops_cook_and_validate":     ("tops_cook_and_validate",     _identity),
    "tops_diagnose":              ("tops_diagnose",              _identity),
    "tops_pipeline_status":       ("tops_pipeline_status",       _identity),
    "tops_monitor_stream":        ("tops_monitor_stream",        _identity),
    "tops_render_sequence":       ("tops_render_sequence",       _identity),
    "tops_multi_shot":            ("tops_multi_shot",            _identity),
    "houdini_reference_usd": ("reference_usd",  _identity),
    "houdini_query_prims":   ("query_prims",    _identity),
    "houdini_manage_variant_set": ("manage_variant_set", _identity),
    "houdini_manage_collection": ("manage_collection", _identity),
    "houdini_configure_light_linking": ("configure_light_linking", _identity),
    "houdini_create_textured_material": ("create_textured_material", _identity),
    "houdini_create_material":  ("create_material",  _identity),
    "houdini_assign_material":  ("assign_material",  _identity),
    "houdini_read_material":    ("read_material",    _identity),
    "synapse_validate_frame":   ("validate_frame",   _identity),
    "synapse_configure_render_passes": ("configure_render_passes", _identity),
    "synapse_knowledge_lookup": ("knowledge_lookup", _filter_keys(["query"])),
    "synapse_inspect_selection": ("inspect_selection", _identity),
    "synapse_inspect_scene":    ("inspect_scene",     _identity),
    "synapse_inspect_node":     ("inspect_node",      _identity),
    "houdini_network_explain":  ("network_explain",  lambda a: {**{k: v for k, v in a.items() if k != "root_path"}, "node": a["root_path"]}),
    "synapse_context":       ("context",         _passthrough),
    "synapse_search":        ("search",          _filter_keys(["query"])),
    "synapse_recall":        ("recall",          _filter_keys(["query"])),
    "synapse_decide":        ("decide",          _decide_payload),
    "synapse_add_memory":    ("add_memory",      _add_memory_payload),
    "synapse_batch":         ("batch_commands",  _identity),
    "synapse_metrics":       ("get_metrics",     _passthrough),
    "synapse_router_stats":  ("router_stats",    _passthrough),
    "synapse_list_recipes":  ("list_recipes",    _passthrough),
    "synapse_live_metrics":  ("get_live_metrics", _identity),
    "synapse_project_setup": ("project_setup",   _identity),
    "synapse_memory_write":  ("memory_write",    _identity),
    "synapse_memory_query":  ("memory_query",    _identity),
    "synapse_memory_status": ("memory_status",   _passthrough),
    "synapse_evolve_memory": ("evolve_memory",   _passthrough),
    "synapse_render_sequence":    ("render_sequence",      _identity),
    "synapse_render_farm_status": ("render_farm_status",   _passthrough),
    "synapse_autonomous_render":  ("autonomous_render",    _identity),
    "synapse_safe_render":        ("safe_render",          _identity),
    "synapse_render_progressively": ("render_progressively", _identity),
    "synapse_validate_ordering": ("solaris_validate_ordering", _identity),
    "houdini_undo":              ("undo",                     _passthrough),
    "houdini_redo":              ("redo",                     _passthrough),
    # HDA operations
    "houdini_hda_create":        ("hda_create",               _identity),
    "houdini_hda_promote_parm":  ("hda_promote_parm",         _identity),
    "houdini_hda_set_help":      ("hda_set_help",             _identity),
    "houdini_hda_package":       ("hda_package",              _identity),
    "houdini_hda_list":          ("hda_list",                 _passthrough),
}


# Group knowledge — served locally, no Houdini connection needed
_GROUP_INFO_TOOLS = {
    "synapse_group_scene": mcp_tools_scene.GROUP_KNOWLEDGE,
    "synapse_group_render": mcp_tools_render.GROUP_KNOWLEDGE,
    "synapse_group_usd": mcp_tools_usd.GROUP_KNOWLEDGE,
    "synapse_group_tops": mcp_tools_tops.GROUP_KNOWLEDGE,
    "synapse_group_memory": mcp_tools_memory.GROUP_KNOWLEDGE,
}


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch MCP tool call to Synapse via WebSocket."""
    # Group-info tools return knowledge preamble directly (no Houdini)
    if name in _GROUP_INFO_TOOLS:
        return [TextContent(type="text", text=_GROUP_INFO_TOOLS[name])]

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
                    TextContent(type="text", text=_dumps_str(meta)),
                ]
            except FileNotFoundError:
                return [TextContent(type="text", text=(
                    f"The capture ran but the image file wasn't found at {image_path} \u2014 "
                    "it may have been cleaned up or the path changed"
                ))]

        return [TextContent(type="text", text=_dumps_str(data))]
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
    """Pre-connect to Synapse on startup — makes first tool call instant.

    Uses _get_connection() to avoid a race with concurrent tool calls
    that would create a second connection and orphan the recv loop.
    """
    try:
        await _get_connection()
        logger.info("Warmup: connected to %s", SYNAPSE_URL)
    except Exception:
        logger.info("Warmup: Synapse not available yet (will retry on first tool call)")


def _atexit_cleanup():
    """Close the persistent WebSocket on interpreter shutdown."""
    global _ws_connection
    if _ws_connection is not None:
        try:
            loop = asyncio.get_event_loop()
            if not loop.is_closed():
                loop.run_until_complete(_ws_connection.close())
        except Exception:
            pass
        _ws_connection = None
    _signal_all_pending(ConnectionError("MCP server shutting down"))

atexit.register(_atexit_cleanup)


async def main():
    """Run the Synapse MCP server on stdio."""
    # Fire-and-forget warmup — stdio server starts accepting immediately
    asyncio.get_running_loop().create_task(_warmup())
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
