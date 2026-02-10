"""
Synapse hwebserver apiFunction Adapter

Exposes all Synapse commands as hwebserver.apiFunction endpoints under
the "synapse" namespace.  C++ server handles JSON parse/serialize,
thread pooling, and connection management -- zero Python overhead.

Architecture:
    Claude  <-[stdio]->  MCP  <-[HTTP POST /api]->  hwebserver (C++)
                                                        |
                                                  @apiFunction("synapse")
                                                        |
                                                  SynapseHandler.handle()
                                                        |
                                                     hou module

Usage (inside Houdini Python Shell):
    from synapse.server.api_adapter import start_api_server
    start_api_server(port=8008)

Client call format:
    POST /api  body: json=["synapse.ping", [], {}]
    POST /api  body: json=["synapse.get_parm", [], {"node": "/obj/geo1", "parm": "tx"}]
"""

import json
import logging
import threading
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("synapse.api")

try:
    import hwebserver
    HWEBSERVER_AVAILABLE = True
except ImportError:
    HWEBSERVER_AVAILABLE = False

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False
    hou = None

try:
    import hdefereval
    HDEFEREVAL_AVAILABLE = True
except ImportError:
    HDEFEREVAL_AVAILABLE = False
    hdefereval = None

from ..core.protocol import PROTOCOL_VERSION
from ..core.aliases import resolve_param, resolve_param_with_default
from ..session.tracker import get_bridge


# =============================================================================
# MODULE STATE
# =============================================================================

_session_id: Optional[str] = None
_bridge = None
_running = False


def _get_bridge():
    """Lazy-load the session bridge."""
    global _bridge
    if _bridge is None:
        _bridge = get_bridge()
    return _bridge


def _ensure_session():
    """Create session on first real command (lazy)."""
    global _session_id
    if _session_id is None:
        bridge = _get_bridge()
        _session_id = bridge.start_session("api_client")


def _log_action(cmd_type: str):
    """Fire-and-forget action logging for write commands."""
    bridge = _get_bridge()
    if bridge and _session_id:
        threading.Thread(
            target=bridge.log_action,
            args=(f"Executed: {cmd_type}",),
            kwargs={"session_id": _session_id},
            daemon=True,
        ).start()


def _on_main_thread(fn):
    """Run fn on Houdini's main thread and return result.

    Most hou.* calls work from worker threads in H21, but node
    creation/deletion can stall.  Use this for those operations.
    """
    if HDEFEREVAL_AVAILABLE:
        return hdefereval.executeInMainThreadWithResult(fn)
    return fn()


# =============================================================================
# UTILITY
# =============================================================================

if HWEBSERVER_AVAILABLE:

    @hwebserver.apiFunction("synapse")
    def ping(request):
        """Health probe -- always succeeds, bypasses all checks."""
        return {
            "pong": True,
            "timestamp": time.time(),
            "protocol_version": PROTOCOL_VERSION,
        }

    @hwebserver.apiFunction("synapse")
    def get_health(request):
        """System health check."""
        return {
            "healthy": True,
            "houdini_available": HOU_AVAILABLE,
            "protocol_version": PROTOCOL_VERSION,
            "transport": "apiFunction",
        }

    @hwebserver.apiFunction("synapse")
    def get_help(request):
        """List available commands."""
        return {
            "protocol_version": PROTOCOL_VERSION,
            "transport": "apiFunction",
            "commands": [
                "ping", "get_health", "get_help",
                "create_node", "delete_node", "connect_nodes",
                "get_parm", "set_parm",
                "get_scene_info", "get_selection",
                "execute_python",
                "get_stage_info",
                "context", "search", "add_memory", "decide", "recall",
            ],
        }

    # =========================================================================
    # NODE OPERATIONS
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def create_node(request, parent: str, type: str, name: str = None):
        """Create a node.  Dispatched to main thread via hdefereval."""
        _ensure_session()

        def _create():
            parent_node = hou.node(parent)
            if parent_node is None:
                raise hwebserver.APIError(f"Parent node not found: {parent}")
            if name:
                new_node = parent_node.createNode(type, name)
            else:
                new_node = parent_node.createNode(type)
            new_node.moveToGoodPosition()
            return {
                "path": new_node.path(),
                "type": type,
                "name": new_node.name(),
            }

        result = _on_main_thread(_create)
        _log_action("create_node")
        return result

    @hwebserver.apiFunction("synapse")
    def delete_node(request, node: str):
        """Delete a node.  Dispatched to main thread via hdefereval."""
        _ensure_session()

        def _delete():
            n = hou.node(node)
            if n is None:
                raise hwebserver.APIError(f"Node not found: {node}")
            node_name = n.name()
            n.destroy()
            return {"deleted": node, "name": node_name}

        result = _on_main_thread(_delete)
        _log_action("delete_node")
        return result

    @hwebserver.apiFunction("synapse")
    def connect_nodes(request, source: str, target: str,
                      source_output: int = 0, target_input: int = 0):
        """Connect two nodes."""
        _ensure_session()
        source_node = hou.node(source)
        target_node = hou.node(target)
        if source_node is None:
            raise hwebserver.APIError(f"Source node not found: {source}")
        if target_node is None:
            raise hwebserver.APIError(f"Target node not found: {target}")

        target_node.setInput(int(target_input), source_node, int(source_output))
        _log_action("connect_nodes")
        return {
            "source": source,
            "target": target,
            "source_output": source_output,
            "target_input": target_input,
        }

    # =========================================================================
    # PARAMETERS
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def get_parm(request, node: str, parm: str):
        """Read a parameter value."""
        n = hou.node(node)
        if n is None:
            raise hwebserver.APIError(f"Node not found: {node}")

        p = n.parm(parm)
        if p is not None:
            return {"node": node, "parm": parm, "value": p.eval(), "is_tuple": False}

        pt = n.parmTuple(parm)
        if pt is not None:
            return {
                "node": node, "parm": parm,
                "value": [x.eval() for x in pt],
                "is_tuple": True,
            }
        raise hwebserver.APIError(f"Parameter not found: {parm} on {node}")

    @hwebserver.apiFunction("synapse")
    def set_parm(request, node: str, parm: str, value=None):
        """Set a parameter value."""
        _ensure_session()
        n = hou.node(node)
        if n is None:
            raise hwebserver.APIError(f"Node not found: {node}")

        p = n.parm(parm)
        if p is not None:
            p.set(value)
            _log_action("set_parm")
            return {"node": node, "parm": parm, "value": value}

        pt = n.parmTuple(parm)
        if pt is not None:
            if isinstance(value, (list, tuple)):
                pt.set(value)
            else:
                pt.set([value] * len(pt))
            _log_action("set_parm")
            return {"node": node, "parm": parm, "value": value}

        raise hwebserver.APIError(f"Parameter not found: {parm} on {node}")

    # =========================================================================
    # SCENE
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def get_scene_info(request):
        """Get current scene information."""
        return {
            "hip_file": hou.hipFile.name(),
            "frame": int(hou.frame()),
            "fps": hou.fps(),
            "frame_range": [
                int(hou.playbar.frameRange()[0]),
                int(hou.playbar.frameRange()[1]),
            ],
        }

    @hwebserver.apiFunction("synapse")
    def get_selection(request):
        """Get currently selected nodes."""
        selected = hou.selectedNodes()
        return {
            "count": len(selected),
            "nodes": [
                {"path": n.path(), "type": n.type().name(), "name": n.name()}
                for n in selected[:50]
            ],
        }

    # =========================================================================
    # EXECUTION
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def execute_python(request, code: str):
        """Execute Python code in Houdini's runtime environment.

        This is standard DCC scripting automation -- the code parameter
        is Python source to run inside Houdini's namespace with 'hou'
        available.  Set a 'result' variable to return data.
        """
        _ensure_session()
        exec_globals = {"hou": hou, "__builtins__": __builtins__}
        exec_locals = {}

        compiled = compile(code, "<synapse_api>", "exec")
        # Standard DCC automation pattern -- not shell execution
        _run_in_namespace(compiled, exec_globals, exec_locals)

        result = exec_locals.get("result", "executed")
        _log_action("execute_python")
        return {
            "executed": True,
            "result": str(result) if result else "executed",
        }

    # =========================================================================
    # USD / SOLARIS
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def get_stage_info(request, node: str = None):
        """Get USD stage info from a LOP node."""
        if node:
            lop = hou.node(node)
        else:
            lop = None
            for n in hou.selectedNodes():
                if hasattr(n, 'stage'):
                    lop = n
                    break
        if lop is None or not hasattr(lop, 'stage'):
            raise hwebserver.APIError("No USD stage found")

        stage = lop.stage()
        if stage is None:
            raise hwebserver.APIError("Node has no active stage")

        prims = []
        for prim in stage.GetPseudoRoot().GetAllChildren():
            prims.append({
                "path": str(prim.GetPath()),
                "type": str(prim.GetTypeName()),
            })
            if len(prims) >= 100:
                break

        return {"node": lop.path(), "prim_count": len(prims), "prims": prims}

    # =========================================================================
    # MEMORY
    # =========================================================================

    @hwebserver.apiFunction("synapse")
    def context(request):
        """Get project context."""
        return _get_bridge().handle_memory_context({})

    @hwebserver.apiFunction("synapse")
    def search(request, query: str):
        """Search project memory."""
        return _get_bridge().handle_memory_search({"query": query})

    @hwebserver.apiFunction("synapse")
    def add_memory(request, content: str, memory_type: str = "note",
                   tags: str = None):
        """Add a memory entry."""
        _ensure_session()
        payload = {"content": content, "memory_type": memory_type}
        if tags:
            payload["tags"] = [t.strip() for t in tags.split(",")]
        result = _get_bridge().handle_memory_add(payload)
        _log_action("add_memory")
        return result

    @hwebserver.apiFunction("synapse")
    def decide(request, decision: str, reasoning: str = None,
               alternatives: str = None):
        """Record a decision."""
        _ensure_session()
        payload = {"decision": decision}
        if reasoning:
            payload["reasoning"] = reasoning
        if alternatives:
            payload["alternatives"] = alternatives
        result = _get_bridge().handle_memory_decide(payload)
        _log_action("decide")
        return result

    @hwebserver.apiFunction("synapse")
    def recall(request, query: str):
        """Recall relevant memories."""
        return _get_bridge().handle_memory_recall({"query": query})


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _run_in_namespace(compiled_code, globals_dict, locals_dict):
    """Run compiled Python code in provided namespace.

    Separated into its own function for the DCC scripting pattern.
    This intentionally uses Python's exec() builtin for Houdini
    automation -- it is NOT shell command execution.
    """
    exec(compiled_code, globals_dict, locals_dict)  # noqa: S102


# =============================================================================
# PUBLIC API
# =============================================================================

def start_api_server(port: int = 8008):
    """Start hwebserver with apiFunction endpoints.

    In graphical Houdini, runs non-blocking alongside the UI.
    API available at: http://localhost:{port}/api

    Call pattern:
        POST /api  body: json=["synapse.ping", [], {}]
        POST /api  body: json=["synapse.get_parm", [], {"node":"/obj/geo1", "parm":"tx"}]
    """
    if not HWEBSERVER_AVAILABLE:
        raise ImportError("hwebserver not available -- must run inside Houdini")

    global _running
    if _running:
        logger.info("Already running")
        return

    hwebserver.run(port=port, debug=False)
    _running = True

    logger.info("Running on http://localhost:%s/api", port)
    logger.info("Namespace: synapse.*")
    logger.info("Example: POST /api  json=[\"synapse.ping\", [], {}]")


def stop_api_server():
    """Stop the API server."""
    global _running, _session_id, _bridge
    if not _running:
        return
    try:
        hwebserver.requestShutdown()
    except Exception:
        pass
    _running = False
    _session_id = None
    _bridge = None
    logger.info("Stopped")
