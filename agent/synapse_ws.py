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
import os
import time
import uuid
from typing import Any, Optional

import websockets

logger = logging.getLogger("synapse.ws")

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
    "tops_cook_and_validate": 600.0,
    "tops_pipeline_status": 60.0,
    "tops_diagnose": 30.0,
    "tops_setup_wedge": 120.0,
    "tops_get_work_items": 30.0,
    "tops_get_cook_stats": 30.0,
    "batch_commands": 60.0,
}


class SynapseConnectionError(Exception):
    """Raised when we can't reach Synapse."""


class SynapseExecutionError(Exception):
    """Raised when Houdini-side execution fails."""

    def __init__(self, message: str, partial_result: Any = None):
        super().__init__(message)
        self.partial_result = partial_result


def _get_auth_key() -> Optional[str]:
    """Get API key for authenticating with Synapse server.

    Sources (checked in order):
    1. SYNAPSE_API_KEY environment variable
    2. ~/.synapse/auth.key file (first non-empty, non-comment line)
    3. None (auth disabled)
    """
    env_key = os.environ.get("SYNAPSE_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        key_path = os.path.join(os.path.expanduser("~"), ".synapse", "auth.key")
        if os.path.exists(key_path):
            with open(key_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        return line
    except OSError:
        pass
    return None


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

    async def _auth_handshake(self) -> None:
        """Handle auth handshake if server requires it."""
        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=2.0)
            msg = json.loads(raw)
        except (asyncio.TimeoutError, Exception):
            return  # No auth_required — server doesn't need auth

        if msg.get("type") != "auth_required":
            logger.warning("Expected auth_required, got %s", msg.get("type"))
            return

        key = _get_auth_key()
        if not key:
            raise SynapseConnectionError(
                "Synapse server requires authentication but no API key is configured. "
                "Set SYNAPSE_API_KEY environment variable or create ~/.synapse/auth.key"
            )

        await self._ws.send(json.dumps({
            "type": "authenticate",
            "id": "auth-handshake",
            "payload": {"key": key},
        }))

        try:
            raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            response = json.loads(raw)
        except asyncio.TimeoutError:
            raise SynapseConnectionError(
                "Synapse server didn't respond to authentication within 5s"
            )

        if response.get("type") == "auth_failed":
            raise SynapseConnectionError(
                f"Authentication failed: {response.get('error', 'invalid API key')}. "
                "Check your SYNAPSE_API_KEY or ~/.synapse/auth.key"
            )

        if response.get("type") == "auth_success":
            logger.info("Authenticated with Synapse server")
            return

        logger.warning("Unexpected auth response: %s", response.get("type"))

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
            await self._auth_handshake()
            self._connected = True
            logger.info("Connected to Synapse at %s", self.uri)
            return True
        except asyncio.TimeoutError:
            raise SynapseConnectionError(
                f"Couldn't reach Synapse at {self.uri} — is Houdini running with the Synapse server active?"
            )
        except SynapseConnectionError:
            raise
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

        command_id = uuid.uuid4().hex[:16]
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
                await self._ws.send(json.dumps(command))

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

    # --- Living Memory ---

    async def project_setup(self) -> dict:
        """Initialize Living Memory structure for the current scene."""
        return await self._send_command("project_setup")

    async def memory_write(self, entry_type: str, content: dict, scope: str = "scene") -> dict:
        """Write a memory entry (decision, note, blocker, parameter, etc.)."""
        return await self._send_command("memory_write", {
            "entry_type": entry_type,
            "content": content,
            "scope": scope,
        })

    async def memory_query(self, query: str, scope: str = "all", type_filter: str = "") -> dict:
        """Search scene/project memory with ranked results."""
        return await self._send_command("memory_query", {
            "query": query,
            "scope": scope,
            "type_filter": type_filter,
        })

    async def memory_status(self) -> dict:
        """Get Living Memory evolution stage, file sizes, session count."""
        return await self._send_command("memory_status")

    # --- TOPS / Pipeline ---

    async def tops_cook(self, node: str, max_retries: int = 0, validate: bool = True) -> dict:
        """Cook a TOP node with optional retry and state validation."""
        payload = {"node": node, "max_retries": max_retries, "validate_states": validate}
        return await self._send_command("tops_cook_and_validate", payload)

    async def tops_status(self, topnet_path: str, include_items: bool = False) -> dict:
        """Get pipeline health status for a TOP network."""
        payload = {"topnet_path": topnet_path, "include_items": include_items}
        return await self._send_command("tops_pipeline_status", payload)

    async def tops_diagnose(self, node: str) -> dict:
        """Diagnose failures in a TOP node."""
        return await self._send_command("tops_diagnose", {"node": node})

    async def tops_wedge(self, topnet_path: str, attribute_name: str, values: list) -> dict:
        """Set up and cook a parameter wedge."""
        payload = {"topnet_path": topnet_path, "attribute_name": attribute_name, "values": values}
        return await self._send_command("tops_setup_wedge", payload)

    async def tops_work_items(self, node: str, state_filter: str = "") -> dict:
        """Query work items from a TOP node."""
        payload = {"node": node}
        if state_filter:
            payload["state_filter"] = state_filter
        return await self._send_command("tops_get_work_items", payload)

    async def tops_cook_stats(self, node: str) -> dict:
        """Get cook timing and throughput stats for a TOP node."""
        return await self._send_command("tops_get_cook_stats", {"node": node})

    async def batch_commands(self, commands: list, atomic: bool = True, stop_on_error: bool = False) -> dict:
        """Execute multiple commands atomically in one round-trip."""
        payload = {"commands": commands, "atomic": atomic, "stop_on_error": stop_on_error}
        return await self._send_command("batch_commands", payload)
