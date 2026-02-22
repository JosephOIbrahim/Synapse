"""
synapse_ws.py — Async WebSocket client for Synapse/Houdini bridge.

Connects directly to the Synapse server running inside Houdini.
Matches the SynapseCommand/SynapseResponse wire format from core/protocol.py.

This module is the ONLY place that touches the WebSocket connection.
All other modules call functions from here.
"""

import asyncio
import json
import logging
import time
import hashlib
from typing import Any, Optional

import websockets

logger = logging.getLogger("synapse.ws")

# --- Deterministic command IDs (He2025) ---
_cmd_seq = 0

def _cmd_id(cmd_type: str, payload: dict | None) -> str:
    global _cmd_seq
    _cmd_seq += 1
    content = f"{cmd_type}:{json.dumps(payload or {}, sort_keys=True)}:{_cmd_seq}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# --- Configuration ---
SYNAPSE_HOST = "localhost"
SYNAPSE_PORT = 9999
SYNAPSE_PATH = "/synapse"
SYNAPSE_URI = f"ws://{SYNAPSE_HOST}:{SYNAPSE_PORT}{SYNAPSE_PATH}"
PROTOCOL_VERSION = "4.0.0"
CONNECT_TIMEOUT = 10.0
CALL_TIMEOUT = 30.0
RENDER_TIMEOUT = 120.0

# Commands that need extra time
_SLOW_COMMANDS = {
    "execute_python": 30.0,
    "execute_vex": 30.0,
    "capture_viewport": 30.0,
    "render": 120.0,
    "wedge": 120.0,
    "inspect_selection": 30.0,
    "inspect_scene": 30.0,
    "inspect_node": 30.0,
}


class SynapseConnectionError(Exception):
    """Raised when we can't reach Synapse."""


class SynapseExecutionError(Exception):
    """Raised when Houdini-side execution fails."""

    def __init__(self, message: str, partial_result: Any = None):
        super().__init__(message)
        self.partial_result = partial_result


class SynapseClient:
    """
    Async WebSocket client for Synapse.

    Sends SynapseCommand-format JSON and receives SynapseResponse-format JSON.
    Uses request ID matching to handle stale responses on reconnect.

    Usage:
        async with SynapseClient() as client:
            result = await client.ping()
            info = await client.scene_info()
    """

    def __init__(self, uri: str = SYNAPSE_URI):
        self.uri = uri
        self._ws = None
        self._connected = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Establish WebSocket connection to Synapse."""
        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(
                    self.uri,
                    open_timeout=3.0,
                    close_timeout=1.0,
                    ping_interval=None,
                    compression=None,
                ),
                timeout=CONNECT_TIMEOUT,
            )
            self._connected = True
            logger.info("Connected to Synapse at %s", self.uri)
            return True
        except asyncio.TimeoutError:
            raise SynapseConnectionError(
                f"Couldn't reach Synapse at {self.uri} — is Houdini running with the Synapse server active?"
            )
        except Exception as e:
            raise SynapseConnectionError(
                f"Connection to Synapse failed: {e}. Check that Houdini is running and Synapse is loaded."
            )

    async def disconnect(self):
        """Close the WebSocket connection."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._connected = False
            logger.info("Disconnected from Synapse")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()

    async def _send_command(
        self, cmd_type: str, payload: dict | None = None, timeout: float | None = None
    ) -> dict:
        """
        Send a SynapseCommand and wait for the matching SynapseResponse.

        Wire format matches core/protocol.py:
          Command:  {type, id, payload, sequence, timestamp, protocol_version}
          Response: {id, success, data, error, sequence, timestamp, protocol_version}
        """
        if not self._connected or not self._ws:
            raise SynapseConnectionError("Not connected to Synapse. Call connect() first.")

        if timeout is None:
            timeout = _SLOW_COMMANDS.get(cmd_type, CALL_TIMEOUT)

        command_id = _cmd_id(cmd_type, payload)
        command = {
            "type": cmd_type,
            "id": command_id,
            "payload": payload or {},
            "sequence": 0,
            "timestamp": time.time(),
            "protocol_version": PROTOCOL_VERSION,
        }

        async with self._lock:
            try:
                await self._ws.send(json.dumps(command, sort_keys=True))

                # Recv loop with ID matching — discard stale responses
                start = time.monotonic()
                while True:
                    remaining = timeout - (time.monotonic() - start)
                    if remaining <= 0:
                        raise asyncio.TimeoutError()

                    raw = await asyncio.wait_for(self._ws.recv(), timeout=remaining)
                    response = json.loads(raw)

                    if response.get("id") == command_id:
                        break

                    logger.warning(
                        "Response ID mismatch: expected %s, got %s (discarding)",
                        command_id,
                        response.get("id"),
                    )

            except asyncio.TimeoutError:
                raise SynapseExecutionError(
                    f"Synapse didn't respond within {timeout}s — "
                    "the operation might still be running in Houdini. "
                    "Check the Houdini viewport."
                )
            except Exception as e:
                if "timeout" in str(e).lower():
                    raise
                raise SynapseExecutionError(f"Communication error: {e}")

        # Check response
        if not response.get("success", False):
            error_msg = response.get("error", "Something went wrong on the Synapse side")
            raise SynapseExecutionError(error_msg, partial_result=response.get("data"))

        return response.get("data", {})

    # --- High-Level API ---

    async def ping(self) -> dict:
        """Check Synapse connectivity. Returns protocol version info."""
        return await self._send_command("ping", timeout=5.0)

    async def scene_info(self) -> dict:
        """Get current scene metadata (HIP path, frame range, FPS)."""
        return await self._send_command("get_scene_info")

    async def execute_python(self, code: str, timeout: float | None = None, dry_run: bool = False, atomic: bool = True) -> Any:
        """
        Execute Python code inside Houdini. Returns the value of the `result` variable.

        The Synapse server wraps execution in hou.undos.group() and auto-injects
        guard functions (ensure_node, ensure_connection, etc.) into the namespace.

        Args:
            code: Python source code to execute. Set a `result` variable for return value.
            timeout: Max seconds to wait.
            dry_run: If True, only syntax-check the code (compile without executing).
            atomic: If True (default), wrap in undo group.
        """
        payload = {"content": code}
        if dry_run:
            payload["dry_run"] = True
        if not atomic:
            payload["atomic"] = False
        result = await self._send_command("execute_python", payload, timeout=timeout)
        # Handler returns {"result": ...} in data
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return result

    async def capture_viewport(self, **kwargs) -> dict:
        """Capture a viewport screenshot. Returns dict with image_path, format, etc."""
        return await self._send_command("capture_viewport", kwargs or {}, timeout=30.0)

    async def inspect_scene(self, root: str = "/", max_depth: int = 3, context_filter: str = "") -> dict:
        """Get structured scene overview."""
        payload = {}
        if root != "/":
            payload["root"] = root
        if max_depth != 3:
            payload["max_depth"] = max_depth
        if context_filter:
            payload["context_filter"] = context_filter
        return await self._send_command("inspect_scene", payload)

    async def inspect_selection(self, depth: int = 1) -> dict:
        """Analyze currently selected nodes."""
        payload = {}
        if depth != 1:
            payload["depth"] = depth
        return await self._send_command("inspect_selection", payload)

    async def inspect_node(self, node: str, include_code: bool = True, include_geometry: bool = True, include_expressions: bool = True) -> dict:
        """Deep inspection of a single node."""
        payload = {"node": node}
        if not include_code:
            payload["include_code"] = False
        if not include_geometry:
            payload["include_geometry"] = False
        if not include_expressions:
            payload["include_expressions"] = False
        return await self._send_command("inspect_node", payload)

    async def create_node(self, parent: str, node_type: str, name: str = "") -> dict:
        """Create a node in Houdini."""
        payload = {"parent": parent, "type": node_type}
        if name:
            payload["name"] = name
        return await self._send_command("create_node", payload)

    async def delete_node(self, node: str) -> dict:
        """Delete a node."""
        return await self._send_command("delete_node", {"node": node})

    async def get_parm(self, node: str, parm: str) -> dict:
        """Read a parameter value."""
        return await self._send_command("get_parm", {"node": node, "parm": parm})

    async def set_parm(self, node: str, parm: str, value: Any) -> dict:
        """Set a parameter value."""
        return await self._send_command("set_parm", {"node": node, "parm": parm, "value": value})

    async def connect_nodes(self, source: str, target: str, source_output: int = 0, target_input: int = 0) -> dict:
        """Connect two nodes."""
        return await self._send_command("connect_nodes", {
            "source": source, "target": target,
            "source_output": source_output, "target_input": target_input,
        })

    async def render(self, **kwargs) -> dict:
        """Trigger a render. Returns dict with image_path, engine, etc."""
        return await self._send_command("render", kwargs or {}, timeout=RENDER_TIMEOUT)

    async def knowledge_lookup(self, query: str) -> dict:
        """Look up Houdini knowledge from the RAG index."""
        return await self._send_command("knowledge_lookup", {"query": query})
