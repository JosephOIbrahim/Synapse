"""SYNAPSE benchmark arm -- the panel path over ws://localhost:9999/synapse.

The panel WS transport, NOT the external MCP surface: HARVEST_SPEC fairness rule
"SYNAPSE runs the panel path ... since synapse_inspect_scene is known to hang" on the
external MCP path. Command envelope (server/websocket.py): a JSON
``{type, id, sequence, payload}`` command; response ``{id, success, data|error}``.
``ping`` / ``get_health`` bypass RBAC and are the connectivity probe.

Isolation (crucible: the two arms never share a port, a process or a scene file): this
arm is PINNED to 9999 and PINNED to one scene copy. It will NOT drive a server it did
not start unless ``allow_foreign=True`` is passed explicitly -- so it can never touch a
live artist session by accident (memory: constructing the panel destroyed an artist
session; a benchmark must stay off the artist's process).
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _agent  # noqa: E402

PORT = 9999           # pinned by HARVEST_SPEC; the runner never changes it
PATH = "/synapse"

# A real, core slice of the SYNAPSE command surface (every name below is a live command
# `type` in server/handlers*). Enough to drive the SOP/empty-scene proof prompt. The full
# 137-tool surface is loaded from the running server / MCP registry at live-run time; this
# core set is what ships committed so the arm is inspectable without a live server.
CORE_TOOLS = [
    {"name": "houdini_scene_info", "description": "Summarise the current scene: contexts, node counts, key nodes.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "houdini_create_node",
     "description": "Create a node of a given type under a parent path. Returns the new node path.",
     "input_schema": {"type": "object",
                      "properties": {"parent_path": {"type": "string"}, "node_type": {"type": "string"},
                                     "name": {"type": "string"}},
                      "required": ["parent_path", "node_type"]}},
    {"name": "houdini_connect_nodes",
     "description": "Wire one node's output into another node's input.",
     "input_schema": {"type": "object",
                      "properties": {"from_path": {"type": "string"}, "to_path": {"type": "string"},
                                     "input_index": {"type": "integer"}},
                      "required": ["from_path", "to_path"]}},
    {"name": "houdini_set_parm",
     "description": "Set a parameter value on a node.",
     "input_schema": {"type": "object",
                      "properties": {"node_path": {"type": "string"}, "parm_name": {"type": "string"},
                                     "value": {}},
                      "required": ["node_path", "parm_name", "value"]}},
    {"name": "houdini_execute_python",
     "description": "Run a short Python snippet in the Houdini session (hou available).",
     "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}},
]


class SynapseArm:
    name = "synapse"

    def __init__(self, scene: str, *, host: str = "localhost", port: int = PORT,
                 allow_foreign: bool = False, started_by_runner: bool = False):
        self.scene = scene
        self.host = host
        self.port = port
        self.allow_foreign = allow_foreign
        self.started_by_runner = started_by_runner
        self._ws = None
        self._seq = 0

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}{PATH}"

    def available(self) -> tuple[bool, str]:
        """Honest connectivity + isolation probe. Never mutates anything."""
        try:
            from websockets.sync.client import connect  # noqa: F401
        except Exception as e:  # noqa: BLE001
            return False, f"websockets sync client unavailable: {e}"
        if not self.started_by_runner and not self.allow_foreign:
            # A listener the benchmark did not start may be the artist's live session.
            import socket
            with socket.socket() as s:
                s.settimeout(0.5)
                held = s.connect_ex((self.host, self.port)) == 0
            if held:
                return (False,
                        f"port {self.port} is held by a server this benchmark did not start; "
                        f"refusing to touch a possibly-live artist session (pass allow_foreign to override)")
            return False, f"no benchmark server on {self.url} (runner must start an isolated hython server first)"
        ok, reason = self._connect()
        self.close()
        return ok, reason

    def _connect(self) -> tuple[bool, str]:
        try:
            from websockets.sync.client import connect
            self._ws = connect(self.url, open_timeout=8, close_timeout=3)
        except Exception as e:  # noqa: BLE001
            return False, f"connect failed: {type(e).__name__}: {e}"
        try:
            resp = self._call_raw("ping", {})
            if not resp.get("success", False):
                return False, f"ping refused: {resp.get('error')}"
            return True, "connected"
        except Exception as e:  # noqa: BLE001
            return False, f"ping failed: {type(e).__name__}: {e}"

    def _call_raw(self, cmd_type: str, payload: dict) -> dict:
        self._seq += 1
        msg = {"type": cmd_type, "id": uuid.uuid4().hex, "sequence": self._seq, "payload": payload}
        self._ws.send(json.dumps(msg))
        return json.loads(self._ws.recv(timeout=60))

    def tools(self) -> list:
        return CORE_TOOLS

    def tool_runner(self, name: str, tool_input: dict):
        resp = self._call_raw(name, tool_input or {})
        if not resp.get("success", False):
            raise RuntimeError(resp.get("error") or "command failed")
        return resp.get("data", {})

    def run(self, *, client, prompt: str, model: str, max_turns: int = 12) -> dict:
        if self._ws is None:
            ok, reason = self._connect()
            if not ok:
                r = _agent.new_result()
                r["error"] = f"arm unavailable: {reason}"
                return r
        system = ("You are a Houdini technical artist working headless. Use the tools to build "
                  "the requested setup in the current scene. When done, briefly say what you built.")
        return _agent.run_agent(client=client, prompt=prompt, tools=self.tools(),
                                tool_runner=self.tool_runner, model=model, system=system,
                                max_turns=max_turns)

    def save_scene(self) -> tuple[bool, str]:
        """Ask the arm's Houdini to save its scene copy, via the execute_python command."""
        try:
            self._call_raw("houdini_execute_python",
                           {"code": f"import hou; hou.hipFile.save({self.scene!r})"})
            return True, self.scene
        except Exception as e:  # noqa: BLE001
            return False, f"save failed: {type(e).__name__}: {e}"

    def close(self):
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:  # noqa: BLE001
                pass
            self._ws = None
