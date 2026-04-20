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
# Deterministic command IDs (He2025: same input -> same ID within a session)
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
    # TOPS/PDG commands -- PDG graph context initialization (getPDGGraphContext,
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
    # Copernicus (COPs) -- solvers and batch need longer timeouts
    "cops_reaction_diffusion": 60.0,
    "cops_growth_propagation": 60.0,
    "cops_temporal_analysis": 60.0,
    "cops_batch_cook": 120.0,
    "cops_composite_aovs": 60.0,
    "cops_bake_textures": 60.0,
    "cops_wetmap": 60.0,
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
                # Connection lost -- signal all pending futures
                logger.warning("Recv loop: connection lost (%s)", e)
                _signal_all_pending(ConnectionError(f"Connection lost: {e}"))
                break

            try:
                response = _loads(raw)
            except Exception:
                continue  # Malformed message -- skip

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

    v2: Lock-free fast path -- volatile check before acquiring the lock.
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

        # Force cleanup of stale state -- cancel lingering recv task
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

    Supports true parallel dispatch -- multiple concurrent send_command
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

            # Direct wait on future set -- avoids asyncio.wait_for's internal task overhead
            done, _ = await asyncio.wait({future}, timeout=cmd_timeout)
            if not done:
                # Timeout -- future still pending
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
# Tool group modules -- knowledge preambles and manifests
# ---------------------------------------------------------------------------
import mcp_tools_scene
import mcp_tools_render
import mcp_tools_usd
import mcp_tools_tops
import mcp_tools_memory
import mcp_tools_cops

TOOL_GROUPS = {
    "scene": mcp_tools_scene,
    "render": mcp_tools_render,
    "usd": mcp_tools_usd,
    "tops": mcp_tools_tops,
    "memory": mcp_tools_memory,
    "cops": mcp_tools_cops,
}

# ---------------------------------------------------------------------------
# Tool registry -- single source of truth for tool definitions and dispatch
# ---------------------------------------------------------------------------
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "python"))
from synapse.mcp._tool_registry import (
    TOOL_DEFS as _REGISTRY_TOOL_DEFS,
    TOOL_DISPATCH,
)

# ---------------------------------------------------------------------------
# Inspector tool wiring (Sprint 2 Week 1 / Sprint 3 Spike 1 — tool #44)
# ---------------------------------------------------------------------------
# Sprint 2 Week 1 shipped synapse_inspect_stage as a custom call_tool branch
# that composed the extraction script locally and awaited one execute_python
# round-trip over the WebSocket.
#
# Sprint 3 Spike 1 is the Strangler Fig port: the same branch now routes
# through the cognitive Dispatcher (synapse.cognitive.dispatcher.Dispatcher)
# with the Inspector tool registered as synapse.cognitive.tools.inspect_stage.
# JSON-RPC marshalling to MCP callers is unchanged — the error envelope
# shape is preserved byte-for-byte by mapping AgentToolError back to the
# {"error": ..., "message": ..., "target_path": ...} dict Sprint 2 used.
import textwrap as _inspector_textwrap
from synapse.inspector import (
    configure_transport as _inspector_configure_transport,
)
from synapse.cognitive.dispatcher import (
    AgentToolError as _AgentToolError,
    Dispatcher as _Dispatcher,
)
from synapse.cognitive.tools.inspect_stage import inspect_stage as _inspect_stage_tool

_INSPECTOR_TOOL_NAME = "synapse_inspect_stage"
_INSPECTOR_TOOL_DESC = (
    "Extracts the AST of the Houdini Solaris /stage context. Returns USD "
    "prim paths, topology, error states, and flags for every node. Enables "
    "scene-aware responses across sessions."
)
_INSPECTOR_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "target_path": {
            "type": "string",
            "description": (
                "Houdini context path to inspect. Defaults to '/stage'. "
                "Must be absolute and match /[a-zA-Z0-9_/]+."
            ),
        },
        "timeout": {
            "type": "number",
            "description": (
                "Per-call transport timeout in seconds (default 30)."
            ),
        },
    },
    "required": [],
}


def _inspector_wrap_stdout_capture(code: str) -> str:
    """Wrap code with per-call stdout capture so the extraction script's
    print() output returns through _handle_execute_python's "result" field.

    Per-call isolation: every wrapped script constructs its own io.StringIO
    locally inside Houdini. No module-level buffer; two concurrent calls
    cannot share state.
    """
    indented = _inspector_textwrap.indent(code, "    ")
    return (
        "import io as _synapse_io\n"
        "import contextlib as _synapse_cl\n"
        "_synapse_buf = _synapse_io.StringIO()\n"
        "with _synapse_cl.redirect_stdout(_synapse_buf):\n"
        f"{indented}\n"
        "result = _synapse_buf.getvalue()"
    )


# Lazy Dispatcher singleton. Built once on first invocation so the
# asyncio loop exists before we capture it in the transport closure.
# Caches across calls because the loop is stable for the MCP session.
_inspector_dispatcher: _Dispatcher | None = None


def _get_inspector_dispatcher() -> _Dispatcher:
    """Build the Dispatcher singleton on first use, return it thereafter.

    Must be called from within a running asyncio event loop (i.e. from
    inside an async handler) because the sync transport closure captures
    the loop to bridge back to it via ``run_coroutine_threadsafe``.
    """
    global _inspector_dispatcher
    if _inspector_dispatcher is not None:
        return _inspector_dispatcher

    loop = asyncio.get_running_loop()

    def _sync_transport(code: str, *, timeout=None) -> str:
        """Inspector transport: runs on a worker thread; marshals the
        execute_python command back onto the MCP event loop, waits for
        the response, returns the captured stdout string."""
        wrapped = _inspector_wrap_stdout_capture(code)
        fut = asyncio.run_coroutine_threadsafe(
            send_command(
                "execute_python",
                {"content": wrapped, "atomic": False},
            ),
            loop,
        )
        effective = timeout if timeout is not None else 30.0
        try:
            data = fut.result(timeout=effective)
        except Exception as e:
            raise RuntimeError(f"execute_python transport failed: {e}") from e
        return (data or {}).get("result", "") or ""

    _inspector_configure_transport(_sync_transport)
    _inspector_dispatcher = _Dispatcher(
        is_testing=True,
        tools={_INSPECTOR_TOOL_NAME: _inspect_stage_tool},
    )
    return _inspector_dispatcher


async def _inspector_call_tool(arguments: dict) -> list:
    """Handle synapse_inspect_stage MCP tool invocation via the Dispatcher.

    Spike 1 Strangler Fig port:
      1. The Dispatcher (cognitive layer) owns tool dispatch. Its
         ``is_testing=True`` path runs the tool synchronously on the
         worker thread — no Qt event loop required.
      2. The tool (``synapse.cognitive.tools.inspect_stage.inspect_stage``)
         is a pure-Python port of the Sprint 2 Inspector. It calls the
         Inspector's transport (configured above) under the hood.
      3. ``asyncio.to_thread`` runs the whole chain off the event loop;
         the transport closure posts work back onto it via
         ``run_coroutine_threadsafe``.

    Error handling: Dispatcher never raises. Tool exceptions come back
    as ``AgentToolError`` values and are mapped back to the Sprint 2 WS
    error envelope shape so external MCP consumers see no contract
    change.
    """
    target_path = arguments.get("target_path", "/stage")
    timeout_arg = arguments.get("timeout")

    kwargs: dict = {"target_path": target_path}
    if timeout_arg is not None:
        kwargs["timeout"] = float(timeout_arg)

    try:
        dispatcher = _get_inspector_dispatcher()
        result = await asyncio.to_thread(
            dispatcher.execute, _INSPECTOR_TOOL_NAME, kwargs,
        )
    except ConnectionError as e:
        return [TextContent(
            type="text",
            text=f"Couldn't reach Synapse \u2014 {e}",
        )]
    except Exception as e:
        logger.exception("Unexpected error dispatching synapse_inspect_stage")
        return [TextContent(
            type="text",
            text=_dumps_str({
                "error": type(e).__name__,
                "message": str(e),
                "target_path": target_path,
            }),
        )]

    if isinstance(result, _AgentToolError):
        # Preserve the Sprint 2 WS adapter error envelope shape so MCP
        # callers don't see a contract change from the Strangler Fig.
        return [TextContent(
            type="text",
            text=_dumps_str({
                "error": result.error_type,
                "message": result.error_message,
                "target_path": target_path,
            }),
        )]

    return [TextContent(type="text", text=_dumps_str(result))]


@server.list_tools()
async def list_tools():
    """Register all Synapse MCP tools.

    Tools generated from the canonical registry in synapse.mcp._tool_registry.
    Group-info tools are local-only (served without Houdini connection).
    """
    tools = []

    # All tools from the canonical registry
    for name, cmd_type, payload_fn, desc, schema, ro, destr, idemp in _REGISTRY_TOOL_DEFS:
        tools.append(Tool(
            name=name,
            description=desc,
            inputSchema=schema,
        ))

    # Group-info tools -- local knowledge preambles, no Houdini needed
    for group_name, knowledge in _GROUP_INFO_TOOLS.items():
        tools.append(Tool(
            name=group_name,
            description=f"[TOOL GROUP] {knowledge[:200]}...",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ))

    # Inspector tool #44 -- local Python composing one execute_python
    # round-trip plus client-side StageAST construction. Dispatched via
    # a dedicated branch in call_tool() rather than TOOL_DISPATCH.
    tools.append(Tool(
        name=_INSPECTOR_TOOL_NAME,
        description=_INSPECTOR_TOOL_DESC,
        inputSchema=_INSPECTOR_TOOL_SCHEMA,
    ))

    return tools


# Group knowledge -- served locally, no Houdini connection needed
_GROUP_INFO_TOOLS = {
    "synapse_group_scene": mcp_tools_scene.GROUP_KNOWLEDGE,
    "synapse_group_render": mcp_tools_render.GROUP_KNOWLEDGE,
    "synapse_group_usd": mcp_tools_usd.GROUP_KNOWLEDGE,
    "synapse_group_tops": mcp_tools_tops.GROUP_KNOWLEDGE,
    "synapse_group_memory": mcp_tools_memory.GROUP_KNOWLEDGE,
    "synapse_group_cops": mcp_tools_cops.GROUP_KNOWLEDGE,
}


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Dispatch MCP tool call to Synapse via WebSocket."""
    # Group-info tools return knowledge preamble directly (no Houdini)
    if name in _GROUP_INFO_TOOLS:
        return [TextContent(type="text", text=_GROUP_INFO_TOOLS[name])]

    # Inspector tool #44 -- custom pipeline (script composition, single
    # execute_python round-trip, StageAST parse, JSON serialization).
    if name == _INSPECTOR_TOOL_NAME:
        return await _inspector_call_tool(arguments)

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
    """Pre-connect to Synapse on startup -- makes first tool call instant.

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
    # Fire-and-forget warmup -- stdio server starts accepting immediately
    asyncio.get_running_loop().create_task(_warmup())
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    # Logging to stderr only -- never print to stdout (corrupts stdio JSON-RPC)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        stream=__import__("sys").stderr,
    )
    asyncio.run(main())
