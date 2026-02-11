"""
Synapse Command Handlers

Registry-based command handler system for the Synapse WebSocket server.
Routes incoming commands to appropriate handler functions.
"""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Callable, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.protocol import (
    CommandType,
    SynapseCommand,
    SynapseResponse,
    PROTOCOL_VERSION,
    normalize_command_type,
)
from ..core.aliases import resolve_param, resolve_param_with_default, USD_PARM_ALIASES
from ..core.audit import audit_log, AuditLevel, AuditCategory


# ---------------------------------------------------------------------------
# Coaching-tone message helpers
# ---------------------------------------------------------------------------

_HOUDINI_UNAVAILABLE = (
    "Houdini isn't reachable right now \u2014 make sure it's running "
    "and Synapse is started from the Python Panel"
)


def _suggest_parms(node, invalid_name: str, limit: int = 8) -> str:
    """Find similar parameter names on a node for error enrichment."""
    try:
        all_names = [p.name() for p in node.parms()]
    except Exception:
        return ""
    needle = invalid_name.lower()
    matches = [n for n in all_names if needle in n.lower() or n.lower() in needle]
    if not matches:
        # Fallback: common prefix match
        matches = [n for n in all_names if n.lower().startswith(needle[:3])]
    # Check USD alias — if the invalid name maps to an encoded USD parm, include hint
    usd_hint = ""
    usd_encoded = USD_PARM_ALIASES.get(invalid_name.lower())
    if usd_encoded and usd_encoded in all_names:
        usd_hint = f" Try '{usd_encoded}' (the encoded USD name for '{invalid_name}')."
    if not matches and not usd_hint:
        return ""
    parts = []
    if usd_hint:
        parts.append(usd_hint)
    if matches:
        parts.append(" Similar parameters: " + ", ".join(matches[:limit]))
    return "".join(parts)


def _suggest_children(parent_path: str) -> str:
    """List children of a parent path for error enrichment."""
    try:
        parent = hou.node(parent_path)
        if parent and parent.children():
            names = [c.name() for c in parent.children()[:10]]
            return " Children at that path: " + ", ".join(names)
    except Exception:
        pass
    return ""


# Reuse 2 threads for fire-and-forget memory logging (avoids Thread() per command)
_log_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synapse-log")

# Idempotent guard functions — injected into execute_python namespace
try:
    from .guards import GUARD_FUNCTIONS as _GUARD_FUNCTIONS
except ImportError:
    _GUARD_FUNCTIONS = {}  # Graceful fallback if guards not available

# Coding-bug errors that trigger auto-rollback in execute_python.
# These indicate the script itself is broken — partial mutations are unwanted.
# Operational errors (RuntimeError, hou.OperationFailed, IOError, etc.) do NOT
# trigger rollback because earlier mutations (node creation, wiring) may be valid.
_ROLLBACK_ERRORS = (NameError, SyntaxError, TypeError, AttributeError, IndexError)

# Map command types to audit categories for structured logging
_CMD_CATEGORY: Dict[str, AuditCategory] = {
    "create_node": AuditCategory.PIPELINE,
    "delete_node": AuditCategory.PIPELINE,
    "connect_nodes": AuditCategory.PIPELINE,
    "set_parm": AuditCategory.PIPELINE,
    "set_keyframe": AuditCategory.PIPELINE,
    "execute_python": AuditCategory.PIPELINE,
    "execute_vex": AuditCategory.PIPELINE,
    "render": AuditCategory.RENDER,
    "render_settings": AuditCategory.RENDER,
    "wedge": AuditCategory.RENDER,
    "capture_viewport": AuditCategory.RENDER,
    "create_usd_prim": AuditCategory.PIPELINE,
    "modify_usd_prim": AuditCategory.PIPELINE,
    "set_usd_attribute": AuditCategory.PIPELINE,
    "reference_usd": AuditCategory.PIPELINE,
    "create_material": AuditCategory.MATERIAL,
    "assign_material": AuditCategory.MATERIAL,
    "add_memory": AuditCategory.ENGRAM,
    "decide": AuditCategory.ENGRAM,
    "batch_commands": AuditCategory.SYNAPSE,
}

# Commands that don't modify state — skip memory logging for these
_READ_ONLY_COMMANDS = frozenset({
    "ping", "get_health", "get_help", "heartbeat",
    "get_parm", "get_scene_info", "get_selection",
    "get_stage_info", "get_usd_attribute",
    "context", "search", "recall",
    "capture_viewport",
    "knowledge_lookup",
    "inspect_selection", "inspect_scene", "inspect_node",
    "read_material",
    "get_metrics", "router_stats", "list_recipes",
})


# =============================================================================
# COMMAND HANDLER REGISTRY
# =============================================================================

class CommandHandlerRegistry:
    """
    Registry for command handlers.

    Allows registering handler functions for specific command types.
    Supports both built-in and custom handlers.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def register(self, command_type: str, handler: Callable):
        """Register a handler for a command type."""
        self._handlers[command_type] = handler

    def get(self, command_type: str) -> Optional[Callable]:
        """Get handler for a command type."""
        # Try exact match first, then normalized
        handler = self._handlers.get(command_type)
        if handler is None:
            normalized = normalize_command_type(command_type)
            handler = self._handlers.get(normalized)
        return handler

    def has(self, command_type: str) -> bool:
        """Check if a handler exists for a command type."""
        return self.get(command_type) is not None

    @property
    def registered_types(self):
        """Get list of registered command types."""
        return list(self._handlers.keys())


# =============================================================================
# SYNAPSE HANDLER
# =============================================================================

class SynapseHandler:
    """
    Main command handler for the Synapse server.

    Routes commands to appropriate handler functions and manages
    integration with the session tracker / memory bridge.
    """

    def __init__(self):
        self._registry = CommandHandlerRegistry()
        self._session_id: Optional[str] = None
        self._bridge = None
        self._register_handlers()

    def set_session_id(self, session_id: str):
        """Set the current session ID for action logging."""
        self._session_id = session_id

    def _get_bridge(self):
        """Lazy-load the bridge to avoid circular imports."""
        if self._bridge is None:
            from ..session.tracker import get_bridge
            self._bridge = get_bridge()
        return self._bridge

    def handle(self, command: SynapseCommand) -> SynapseResponse:
        """
        Handle an incoming command.

        Args:
            command: The command to handle

        Returns:
            SynapseResponse with the result
        """
        try:
            cmd_type = command.normalized_type()
            handler = self._registry.get(cmd_type)

            if handler is None:
                return SynapseResponse(
                    id=command.id,
                    success=False,
                    error=f"I don't recognize the command '{command.type}' \u2014 try get_help to see what's available",
                    sequence=command.sequence,
                )

            result = handler(command.payload)

            # Log action asynchronously — don't block the response path
            if cmd_type not in _READ_ONLY_COMMANDS:
                bridge = self._get_bridge()
                if bridge and self._session_id:
                    sid = self._session_id
                    _log_executor.submit(
                        bridge.log_action,
                        f"Executed: {cmd_type}",
                        session_id=sid,
                    )

                # Audit log — fire-and-forget via existing thread pool
                _log_executor.submit(
                    audit_log().log,
                    operation=cmd_type,
                    message=f"Executed {cmd_type}",
                    level=AuditLevel.AGENT_ACTION,
                    category=_CMD_CATEGORY.get(cmd_type, AuditCategory.SYNAPSE),
                    input_data=command.payload,
                    output_data=result if isinstance(result, dict) else {},
                )

            return SynapseResponse(
                id=command.id,
                success=True,
                data=result,
                sequence=command.sequence,
            )

        except ValueError as e:
            return SynapseResponse(
                id=command.id,
                success=False,
                error=str(e),
                sequence=command.sequence,
            )
        except Exception as e:
            return SynapseResponse(
                id=command.id,
                success=False,
                error=f"Hit a snag processing that request: {e}",
                sequence=command.sequence,
            )

    def _register_handlers(self):
        """Register all built-in command handlers."""
        reg = self._registry

        # Utility
        reg.register("ping", self._handle_ping)
        reg.register("get_health", self._handle_get_health)
        reg.register("get_help", self._handle_get_help)

        # Node operations
        reg.register("create_node", self._handle_create_node)
        reg.register("delete_node", self._handle_delete_node)
        reg.register("connect_nodes", self._handle_connect_nodes)

        # Parameters
        reg.register("get_parm", self._handle_get_parm)
        reg.register("set_parm", self._handle_set_parm)

        # Scene
        reg.register("get_scene_info", self._handle_get_scene_info)
        reg.register("get_selection", self._handle_get_selection)

        # Execution
        reg.register("execute_python", self._handle_execute_python)
        reg.register("execute_vex", self._handle_execute_vex)

        # USD/Solaris
        reg.register("get_stage_info", self._handle_get_stage_info)
        reg.register("get_usd_attribute", self._handle_get_usd_attribute)
        reg.register("set_usd_attribute", self._handle_set_usd_attribute)
        reg.register("create_usd_prim", self._handle_create_usd_prim)
        reg.register("modify_usd_prim", self._handle_modify_usd_prim)

        # Viewport / Render
        reg.register("capture_viewport", self._handle_capture_viewport)
        reg.register("render", self._handle_render)

        # TOPs / PDG wedging
        reg.register("wedge", self._handle_wedge)

        # USD scene assembly (reference / sublayer)
        reg.register("reference_usd", self._handle_reference_usd)

        # Keyframe / Render Settings
        reg.register("set_keyframe", self._handle_set_keyframe)
        reg.register("render_settings", self._handle_render_settings)

        # Materials
        reg.register("create_material", self._handle_create_material)
        reg.register("assign_material", self._handle_assign_material)
        reg.register("read_material", self._handle_read_material)

        # Knowledge lookup (RAG)
        reg.register("knowledge_lookup", self._handle_knowledge_lookup)

        # Introspection (Phase 1)
        reg.register("inspect_selection", self._handle_inspect_selection)
        reg.register("inspect_scene", self._handle_inspect_scene)
        reg.register("inspect_node", self._handle_inspect_node)

        # Batch
        reg.register("batch_commands", self._handle_batch_commands)

        # Metrics / Router stats / Recipes
        reg.register("get_metrics", self._handle_get_metrics)
        reg.register("router_stats", self._handle_router_stats)
        reg.register("list_recipes", self._handle_list_recipes)

        # Memory operations (new names)
        reg.register("context", self._handle_memory_context)
        reg.register("search", self._handle_memory_search)
        reg.register("add_memory", self._handle_memory_add)
        reg.register("decide", self._handle_memory_decide)
        reg.register("recall", self._handle_memory_recall)

        # Scene memory operations (Living Memory)
        reg.register("project_setup", self._handle_project_setup)
        reg.register("memory_write", self._handle_memory_write)
        reg.register("memory_query", self._handle_memory_query)
        reg.register("memory_status", self._handle_memory_status)

    # =========================================================================
    # UTILITY HANDLERS
    # =========================================================================

    def _handle_ping(self, payload: Dict) -> Dict:
        """Handle ping command."""
        return {
            "pong": True,
            "timestamp": time.time(),
            "protocol_version": PROTOCOL_VERSION,
        }

    def _handle_get_health(self, payload: Dict) -> Dict:
        """Handle health check command."""
        return {
            "healthy": True,
            "houdini_available": HOU_AVAILABLE,
            "protocol_version": PROTOCOL_VERSION,
        }

    def _handle_get_help(self, payload: Dict) -> Dict:
        """Handle help command."""
        return {
            "protocol_version": PROTOCOL_VERSION,
            "commands": self._registry.registered_types,
            "description": "Synapse AI-Houdini Bridge v" + PROTOCOL_VERSION,
        }

    # =========================================================================
    # BATCH HANDLER
    # =========================================================================

    def _handle_batch_commands(self, payload: Dict) -> Dict:
        """Execute a batch of commands in declared order.

        Payload:
            commands: list of {type: str, payload: dict}
            atomic: bool (default True) — wrap in single undo group
            stop_on_error: bool (default False) — halt on first error
        """
        commands = payload.get("commands")
        if not commands or not isinstance(commands, list):
            raise ValueError("'commands' must be a non-empty list")

        atomic = payload.get("atomic", True)
        stop_on_error = payload.get("stop_on_error", False)

        results: list = []
        statuses: list = []
        errors: list = []

        if atomic and HOU_AVAILABLE:
            hou.undos.beginGroup()

        try:
            for i, cmd_spec in enumerate(commands):
                cmd_type = cmd_spec.get("type", "")
                cmd_payload = cmd_spec.get("payload", {})
                handler = self._registry.get(cmd_type)

                if handler is None:
                    err = f"Step {i}: unknown command '{cmd_type}'"
                    errors.append(err)
                    statuses.append("error")
                    results.append(None)
                    if stop_on_error:
                        break
                    continue

                try:
                    result = handler(cmd_payload)
                    results.append(result)
                    statuses.append("ok")
                    errors.append(None)
                except Exception as e:
                    results.append(None)
                    statuses.append("error")
                    errors.append(f"Step {i}: {e}")
                    if stop_on_error:
                        break
        finally:
            if atomic and HOU_AVAILABLE:
                hou.undos.endGroup()

        return {
            "results": results,
            "statuses": statuses,
            "errors": errors,
        }

    # =========================================================================
    # NODE HANDLERS
    # =========================================================================

    def _handle_create_node(self, payload: Dict) -> Dict:
        """Handle create_node command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent = resolve_param(payload, "parent")
        node_type = resolve_param(payload, "type")
        name = resolve_param(payload, "name", required=False)

        parent_node = hou.node(parent)
        if parent_node is None:
            raise ValueError(
                f"Couldn't find the parent node at {parent} \u2014 "
                "verify this path exists in your scene"
            )

        if name:
            new_node = parent_node.createNode(node_type, name)
        else:
            new_node = parent_node.createNode(node_type)

        new_node.moveToGoodPosition()

        # Track node in session (logging handled by generic executor in handle())
        bridge = self._get_bridge()
        if bridge and self._session_id:
            session = bridge.get_session(self._session_id)
            if session:
                session.nodes_created.append(new_node.path())

        return {
            "path": new_node.path(),
            "type": node_type,
            "name": new_node.name(),
        }

    def _handle_delete_node(self, payload: Dict) -> Dict:
        """Handle delete_node command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} \u2014 "
                "it may have been renamed or moved"
            )

        node_name = node.name()
        node.destroy()

        return {"deleted": node_path, "name": node_name}

    def _handle_connect_nodes(self, payload: Dict) -> Dict:
        """Handle connect_nodes command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        source_path = resolve_param(payload, "source")
        target_path = resolve_param(payload, "target")
        source_output = resolve_param_with_default(payload, "source_output", 0)
        target_input = resolve_param_with_default(payload, "target_input", 0)

        source_node = hou.node(source_path)
        target_node = hou.node(target_path)

        if source_node is None:
            raise ValueError(
                f"Couldn't find the source node at {source_path} \u2014 "
                "make sure it exists before connecting"
            )
        if target_node is None:
            raise ValueError(
                f"Couldn't find the target node at {target_path} \u2014 "
                "make sure it exists before connecting"
            )

        target_node.setInput(int(target_input), source_node, int(source_output))

        return {
            "source": source_path,
            "target": target_path,
            "source_output": source_output,
            "target_input": target_input,
        }

    # =========================================================================
    # PARAMETER HANDLERS
    # =========================================================================

    def _handle_get_parm(self, payload: Dict) -> Dict:
        """Handle get_parm command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} \u2014 "
                "double-check the path exists"
            )

        parm = node.parm(parm_name)
        # USD alias fallback -- resolve human-readable name to encoded parm
        if parm is None:
            usd_encoded = USD_PARM_ALIASES.get(parm_name.lower())
            if usd_encoded:
                parm = node.parm(usd_encoded)
                if parm is not None:
                    parm_name = usd_encoded  # use resolved name in response
        if parm is None:
            # Try as parm tuple
            parm_tuple = node.parmTuple(parm_name)
            if parm_tuple is not None:
                return {
                    "node": node_path,
                    "parm": parm_name,
                    # hou.Parm.eval() reads parameter value — not Python eval()
                    "value": [p.eval() for p in parm_tuple],  # noqa: S307
                    "is_tuple": True,
                }
            hint = _suggest_parms(node, parm_name)
            raise ValueError(
                f"Couldn't find parameter '{parm_name}' on {node_path} \u2014 "
                f"check the spelling or try get_parm to explore what's available.{hint}"
            )

        return {
            "node": node_path,
            "parm": parm_name,
            "value": parm.eval(),
            "is_tuple": False,
        }

    def _handle_set_parm(self, payload: Dict) -> Dict:
        """Handle set_parm command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} \u2014 "
                "double-check the path exists"
            )

        parm = node.parm(parm_name)
        # USD alias fallback -- resolve human-readable name to encoded parm
        if parm is None:
            usd_encoded = USD_PARM_ALIASES.get(parm_name.lower())
            if usd_encoded:
                parm = node.parm(usd_encoded)
                if parm is not None:
                    parm_name = usd_encoded
        if parm is not None:
            parm.set(value)
            return {"node": node_path, "parm": parm_name, "value": value}

        # Try as parm tuple
        parm_tuple = node.parmTuple(parm_name)
        if parm_tuple is not None:
            if isinstance(value, (list, tuple)):
                parm_tuple.set(value)
            else:
                parm_tuple.set([value] * len(parm_tuple))
            return {"node": node_path, "parm": parm_name, "value": value}

        hint = _suggest_parms(node, parm_name)
        raise ValueError(
            f"Couldn't find parameter '{parm_name}' on {node_path} \u2014 "
            f"check the spelling or list the node's parameters first.{hint}"
        )

    # =========================================================================
    # SCENE HANDLERS
    # =========================================================================

    def _handle_get_scene_info(self, payload: Dict) -> Dict:
        """Handle get_scene_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        return {
            "hip_file": hou.hipFile.name(),
            "frame": int(hou.frame()),
            "fps": hou.fps(),
            "frame_range": [int(hou.playbar.frameRange()[0]), int(hou.playbar.frameRange()[1])],
        }

    def _handle_get_selection(self, payload: Dict) -> Dict:
        """Handle get_selection command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        selected = hou.selectedNodes()
        return {
            "count": len(selected),
            "nodes": [
                {"path": n.path(), "type": n.type().name(), "name": n.name()}
                for n in selected[:50]
            ],
        }

    # =========================================================================
    # EXECUTION HANDLERS
    # =========================================================================

    def _handle_execute_python(self, payload: Dict) -> Dict:
        """
        Handle execute_python command.

        Executes Python code in Houdini's runtime environment.
        This is a standard DCC scripting pattern for automation.

        Options:
            dry_run (bool): Compile-only syntax check — no execution.
            atomic (bool): Wrap in undo group with rollback (default True).
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        code = resolve_param(payload, "content")
        dry_run = resolve_param_with_default(payload, "dry_run", False)
        atomic = resolve_param_with_default(payload, "atomic", True)

        # Compile first — catches SyntaxError for both dry_run and real runs
        try:
            compiled = compile(code, "<synapse_exec>", "exec")
        except SyntaxError as e:
            if dry_run:
                return {"valid": False, "error": str(e), "dry_run": True}
            raise

        if dry_run:
            return {"valid": True, "dry_run": True}

        # Build execution namespace with Houdini access + idempotent guards
        exec_globals = {"hou": hou, "__builtins__": __builtins__}
        try:
            from .guards import GUARD_FUNCTIONS
            exec_globals.update(GUARD_FUNCTIONS)
        except ImportError:
            pass
        exec_locals: dict = {}

        # Execute inside undo group with smart rollback:
        # - Coding bugs (NameError, SyntaxError, TypeError, AttributeError)
        #   → auto-rollback, since the script is broken and partial state is bad
        # - Operational errors (render timeout, file not found, hou.OperationFailed)
        #   → keep mutations, since node creation/wiring may have succeeded
        if atomic:
            with hou.undos.group("synapse_execute"):
                try:
                    _run_compiled(compiled, exec_globals, exec_locals)
                except _ROLLBACK_ERRORS:
                    hou.undos.performUndo()
                    raise
        else:
            _run_compiled(compiled, exec_globals, exec_locals)

        # Try to extract a result variable
        result = exec_locals.get("result", "executed")

        return {
            "executed": True,
            "result": str(result) if result else "executed",
        }

    def _handle_execute_vex(self, payload: Dict) -> Dict:
        """
        Handle execute_vex command.

        Creates a temporary attribwrangle node, sets the VEX snippet,
        optionally wires an input geometry, and returns the node path.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        snippet = resolve_param(payload, "snippet")
        run_over = resolve_param_with_default(payload, "run_over", "Points")
        input_node = resolve_param_with_default(payload, "input_node", None)

        # Find or create a working SOP context
        parent = None
        if input_node:
            src = hou.node(input_node)
            if src is not None:
                parent = src.parent()

        if parent is None:
            # Default to /obj — create a temp geo container
            obj = hou.node("/obj")
            parent = obj.createNode("geo", "synapse_vex_temp")

        wrangle = parent.createNode("attribwrangle", "synapse_vex")
        wrangle.parm("snippet").set(snippet)

        # Map run_over string to class menu value
        run_over_map = {
            "detail": 0, "points": 1, "vertices": 2, "primitives": 3,
        }
        class_val = run_over_map.get(run_over.lower(), 1)
        wrangle.parm("class").set(class_val)

        # Wire input if provided
        if input_node:
            src = hou.node(input_node)
            if src is not None:
                wrangle.setInput(0, src)

        wrangle.setDisplayFlag(True)
        wrangle.setRenderFlag(True)

        return {
            "node": wrangle.path(),
            "snippet": snippet,
            "run_over": run_over,
            "class": class_val,
        }

    # =========================================================================
    # USD/SOLARIS HANDLERS
    # =========================================================================

    def _handle_get_stage_info(self, payload: Dict) -> Dict:
        """Handle get_stage_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node", required=False)

        if node_path:
            node = hou.node(node_path)
        else:
            # Try to find the current LOP network
            node = None
            for n in hou.selectedNodes():
                if hasattr(n, 'stage'):
                    node = n
                    break

        if node is None or not hasattr(node, 'stage'):
            raise ValueError(
                "No USD stage found \u2014 select a LOP node or pass "
                "a node path so I know which stage to look at"
            )

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet \u2014 "
                "it may need to cook first, or check the LOP network is set up"
            )

        root = stage.GetPseudoRoot()
        prims = []
        for prim in root.GetAllChildren():
            prims.append({
                "path": str(prim.GetPath()),
                "type": str(prim.GetTypeName()),
            })
            if len(prims) >= 100:
                break

        return {
            "node": node.path(),
            "prim_count": len(prims),
            "prims": prims,
        }

    def _resolve_lop_node(self, node_path: str = None):
        """Resolve a LOP node from path or selection."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        if node_path:
            node = hou.node(node_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {node_path} \u2014 "
                    "double-check the path exists"
                )
            if not hasattr(node, 'stage'):
                raise ValueError(
                    f"The node at {node_path} isn't a LOP node \u2014 "
                    "I need a Solaris/LOP node to access the USD stage"
                )
            return node

        # Search selection for a LOP node
        for n in hou.selectedNodes():
            if hasattr(n, 'stage'):
                return n

        raise ValueError(
            "Couldn't find a LOP node in your selection \u2014 "
            "select one in the Solaris network or specify the node path"
        )

    def _handle_get_usd_attribute(self, payload: Dict) -> Dict:
        """Handle get_usd_attribute command — read a USD attribute from a prim."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet \u2014 "
                "it may need to cook first, or check the LOP network is set up"
            )

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(
                f"Couldn't find a prim at {prim_path} \u2014 "
                "double-check the path on the USD stage"
            )

        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            # List available attributes to help the caller
            attrs = [a.GetName() for a in prim.GetAttributes()][:30]
            raise ValueError(
                f"That attribute name didn't match ('{attr_name}') on {prim_path}. "
                f"Available attributes: {', '.join(attrs)}"
            )

        value = attr.Get()

        return {
            "node": node.path(),
            "prim_path": prim_path,
            "attribute": attr_name,
            "value": _usd_to_json(value),
            "type_name": str(attr.GetTypeName()),
        }

    def _handle_set_usd_attribute(self, payload: Dict) -> Dict:
        """Handle set_usd_attribute command — set a USD attribute via Python LOP."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")
        value = resolve_param(payload, "value")

        parent = node.parent()
        safe_name = f"set_{attr_name.replace(':', '_').replace('.', '_')}"
        py_lop = parent.createNode("pythonscript", safe_name)
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        code = (
            "from pxr import Sdf\n"
            "stage = hou.pwd().editableStage()\n"
            f"prim = stage.GetPrimAtPath({repr(prim_path)})\n"
            "if prim:\n"
            f"    attr = prim.GetAttribute({repr(attr_name)})\n"
            "    if attr:\n"
            f"        attr.Set({repr(value)})\n"
        )
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "attribute": attr_name,
            "value": value,
        }

    def _handle_create_usd_prim(self, payload: Dict) -> Dict:
        """Handle create_usd_prim command — define a USD prim via Python LOP."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        prim_type = resolve_param_with_default(payload, "prim_type", "Xform")

        parent = node.parent()
        safe_name = prim_path.rstrip("/").rsplit("/", 1)[-1] or "prim"
        py_lop = parent.createNode("pythonscript", f"create_{safe_name}")
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        code = (
            "stage = hou.pwd().editableStage()\n"
            f"stage.DefinePrim({repr(prim_path)}, {repr(prim_type)})\n"
        )
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "prim_type": prim_type,
        }

    def _handle_modify_usd_prim(self, payload: Dict) -> Dict:
        """Handle modify_usd_prim command — set metadata/properties on a prim."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")

        # Collect optional modifications
        kind = resolve_param(payload, "kind", required=False)
        purpose = resolve_param(payload, "purpose", required=False)
        active = resolve_param(payload, "active", required=False)

        parent = node.parent()
        safe_name = prim_path.rstrip("/").rsplit("/", 1)[-1] or "prim"
        py_lop = parent.createNode("pythonscript", f"modify_{safe_name}")
        py_lop.setInput(0, node)
        py_lop.moveToGoodPosition()

        lines = [
            "from pxr import Usd, UsdGeom, Sdf, Kind",
            "stage = hou.pwd().editableStage()",
            f"prim = stage.GetPrimAtPath({repr(prim_path)})",
            "if prim:",
        ]
        mods = {}
        if kind is not None:
            lines.append(f"    Usd.ModelAPI(prim).SetKind({repr(kind)})")
            mods["kind"] = kind
        if purpose is not None:
            lines.append(f"    UsdGeom.Imageable(prim).GetPurposeAttr().Set({repr(purpose)})")
            mods["purpose"] = purpose
        if active is not None:
            lines.append(f"    prim.SetActive({active})")
            mods["active"] = active

        if not mods:
            raise ValueError(
                "No changes specified \u2014 pass at least one of: kind, purpose, or active"
            )

        code = "\n".join(lines)
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "modifications": mods,
        }

    # =========================================================================
    # VIEWPORT HANDLERS
    # =========================================================================

    def _handle_capture_viewport(self, payload: Dict) -> Dict:
        """Capture the Houdini viewport as an image file.

        Uses Houdini's flipbook API for a single-frame capture. This correctly
        reads the OpenGL framebuffer (QWidget.grab() returns black for GL surfaces).
        Must run on the main thread via hdefereval.executeInMainThreadWithResult().
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        from pathlib import Path

        fmt = resolve_param_with_default(payload, "format", "jpeg")
        width = resolve_param_with_default(payload, "width", 800)
        height = resolve_param_with_default(payload, "height", 600)

        temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
        ext = "jpg" if fmt == "jpeg" else "png"
        timestamp = int(time.time() * 1000)
        # Flipbook requires $F4 frame pattern in output path
        out_pattern = str(temp_dir / f"synapse_cap_{timestamp}.$F4.{ext}")

        def _flipbook_on_main_thread():
            """Runs on Houdini's main thread."""
            desktop = hou.ui.curDesktop()
            sv = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
            if sv is None:
                raise ValueError(
                    "Couldn't find a viewport \u2014 make sure a Scene Viewer pane "
                    "is open in your current desktop layout"
                )

            vp = sv.curViewport()
            settings = sv.flipbookSettings()
            cur = int(hou.frame())
            settings.frameRange((cur, cur))
            settings.output(out_pattern)
            settings.useResolution(True)
            settings.resolution((int(width), int(height)))
            sv.flipbook(viewport=vp, settings=settings, open_dialog=False)

            # Resolve the actual output filename (replaces $F4 with frame number)
            actual = out_pattern.replace("$F4", f"{cur:04d}")
            return actual

        import hdefereval
        actual_path = hdefereval.executeInMainThreadWithResult(
            _flipbook_on_main_thread
        )

        if not Path(actual_path).exists():
            raise RuntimeError(
                f"The viewport capture ran but the image wasn't created at {actual_path} \u2014 "
                "this can happen if the viewport is minimized or occluded"
            )

        return {
            "image_path": actual_path,
            "width": int(width),
            "height": int(height),
            "format": fmt,
        }

    # =========================================================================
    # RENDER HANDLERS
    # =========================================================================

    def _handle_render(self, payload: Dict) -> Dict:
        """Render a frame via Karma, Mantra, or any ROP node.

        Uses hdefereval.executeInMainThreadWithResult() since hou.RopNode.render()
        must run on Houdini's main thread. Outputs to a temp JPEG for AI preview.

        Supports Karma XPU (GPU+CPU hybrid), Karma CPU, and Mantra ROPs.
        For Karma nodes, detects and reports the rendering engine variant.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from pathlib import Path

        rop_path = resolve_param(payload, "node", required=False)
        frame = resolve_param_with_default(payload, "frame", None)
        width = resolve_param_with_default(payload, "width", None)
        height = resolve_param_with_default(payload, "height", None)

        def _render_on_main():
            if rop_path:
                node = hou.node(rop_path)
                if node is None:
                    raise ValueError(
                        f"Couldn't find a render ROP at {rop_path} \u2014 "
                        "double-check the path to your ROP node"
                    )
            else:
                node = _find_render_rop()

            # Detect Karma engine variant for metadata
            node_type = node.type().name()
            engine = _detect_karma_engine(node, node_type)

            # For usdrender ROPs in /out, ensure loppath is set
            lp = node.parm("loppath")
            if lp and not lp.eval():
                # Auto-find a LOP node with a stage
                for lop_path in ["/stage"]:
                    lop = hou.node(lop_path)
                    if lop and lop.children():
                        # Find last display node or last child
                        display = [c for c in lop.children() if hasattr(c, 'isDisplayFlagSet') and c.isDisplayFlagSet()]
                        target = display[0] if display else lop.children()[-1]
                        lp.set(target.path())
                        break

            # Output to temp JPEG (AI preview, not final EXR)
            temp_dir = Path(hou.text.expandString("$HOUDINI_TEMP_DIR"))
            timestamp = int(time.time() * 1000)
            out_path = str(temp_dir / f"synapse_render_{timestamp}.jpg")

            cur = int(hou.frame()) if frame is None else int(frame)

            # Resolution override — res= is a scale factor, so set parms directly
            if width and height:
                w, h = int(width), int(height)
                for rx, ry in [("resolutionx", "resolutiony"), ("res_user1", "res_user2")]:
                    if node.parm(rx):
                        node.parm(rx).set(w)
                        node.parm(ry).set(h)
                        break
                # Enable override if available (usdrender string menu)
                ov = node.parm("override_res")
                if ov and ov.eval() != "specific":
                    ov.set("specific")

            # Set output path on the node parm (output_file kwarg doesn't
            # work reliably for usdrender/karma ROPs)
            for parm_name in ("outputimage", "picture"):
                p = node.parm(parm_name)
                if p:
                    p.set(out_path)
                    break

            node.render(
                frame_range=(cur, cur),
                verbose=False,
            )

            # Karma XPU has a delayed file flush — poll up to ~15s
            for _ in range(60):
                if Path(out_path).exists() and Path(out_path).stat().st_size > 0:
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError(
                    f"The render finished but the output wasn't created at {out_path} \u2014 "
                    "check if the output directory is writable and the renderer didn't error"
                )
            return out_path, node.path(), node_type, engine

        import hdefereval
        result_path, used_rop, used_type, engine = (
            hdefereval.executeInMainThreadWithResult(_render_on_main)
        )
        return {
            "image_path": result_path,
            "rop": used_rop,
            "rop_type": used_type,
            "engine": engine,
            "width": int(width) if width else None,
            "height": int(height) if height else None,
            "format": "jpeg",
        }


    # =========================================================================
    # KEYFRAME / RENDER SETTINGS HANDLERS
    # =========================================================================

    def _handle_set_keyframe(self, payload: Dict) -> Dict:
        """Set a keyframe on a node parameter at a specific frame."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")
        frame = resolve_param_with_default(payload, "frame", None)

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} \u2014 "
                "double-check the path exists"
            )
        parm = node.parm(parm_name)
        if parm is None:
            hint = _suggest_parms(node, parm_name)
            raise ValueError(
                f"Couldn't find parameter '{parm_name}' on {node_path}.{hint}"
            )

        if frame is not None:
            key = hou.Keyframe()
            key.setFrame(float(frame))
            key.setValue(float(value))
            parm.setKeyframe(key)
        else:
            key = hou.Keyframe()
            key.setFrame(float(hou.frame()))
            key.setValue(float(value))
            parm.setKeyframe(key)

        return {
            "node": node_path,
            "parm": parm_name,
            "value": float(value),
            "frame": float(frame) if frame is not None else float(hou.frame()),
        }

    def _handle_render_settings(self, payload: Dict) -> Dict:
        """Read and optionally modify render settings on a ROP or Karma node."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        node_path = resolve_param(payload, "node")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(
                f"Couldn't find a node at {node_path} \u2014 "
                "double-check the path to your render settings node"
            )

        settings = {}
        # Read current render settings
        for parm in node.parms():
            try:
                val = parm.eval()
                if isinstance(val, (int, float, str)):
                    settings[parm.name()] = val
            except Exception:
                pass

        # Apply overrides if provided
        overrides = resolve_param_with_default(payload, "settings", {})
        if isinstance(overrides, dict):
            for k, v in sorted(overrides.items()):
                p = node.parm(k)
                if p:
                    p.set(v)
                    settings[k] = v

        return {"node": node_path, "settings": settings}


    # =========================================================================
    # TOPS / PDG WEDGE
    # =========================================================================

    def _handle_wedge(self, payload: Dict) -> Dict:
        """Run a TOPs/PDG wedge to explore parameter variations."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        import hdefereval

        top_path = resolve_param(payload, "node")  # TOP network or wedge node
        wedge_parm = resolve_param(payload, "parm", required=False)
        values = resolve_param(payload, "values", required=False)

        if values is not None and not isinstance(values, list):
            raise ValueError(
                "'values' should be a list (e.g. [0.5, 1.0, 2.0]) \u2014 "
                "wrap your values in square brackets"
            )

        def _run_wedge():
            node = hou.node(top_path)
            if node is None:
                raise ValueError(
                    f"Couldn't find a node at {top_path} \u2014 "
                    "double-check the path to your TOP network or wedge node"
                )

            # If it's a TOP network, find or create wedge node
            if node.type().category().name() == "Top":
                # It's already a TOP node -- cook it
                node.cook(block=True)
                return {"node": top_path, "status": "cooked"}
            elif node.type().category().name() == "TopNet":
                # It's a TOP network -- find wedge nodes and cook
                wedge_nodes = [n for n in node.children() if "wedge" in n.type().name().lower()]
                if wedge_nodes:
                    wedge_nodes[0].cook(block=True)
                    return {"node": wedge_nodes[0].path(), "status": "cooked"}
                else:
                    raise ValueError(
                        f"Couldn't find a wedge node inside {top_path} \u2014 "
                        "create a wedge TOP or point to one directly"
                    )
            else:
                raise ValueError(
                    f"The node at {top_path} isn't a TOP network \u2014 "
                    "point to a TOP network or a specific wedge/TOP node"
                )

        result = hdefereval.executeInMainThreadWithResult(_run_wedge)
        return result

    # =========================================================================
    # USD SCENE ASSEMBLY (REFERENCE / SUBLAYER)
    # =========================================================================

    def _handle_reference_usd(self, payload: Dict) -> Dict:
        """Import a USD file into the stage via reference or sublayer."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        file_path = resolve_param(payload, "file")
        prim_path = resolve_param_with_default(payload, "prim_path", "/")
        mode = resolve_param_with_default(payload, "mode", "reference")
        parent = resolve_param_with_default(payload, "parent", "/stage")

        parent_node = hou.node(parent)
        if parent_node is None:
            raise ValueError(
                f"Couldn't find the parent node at {parent} \u2014 "
                "verify this path exists (default is /stage)"
            )

        if mode == "sublayer":
            node = parent_node.createNode("sublayer", "sublayer_import")
            node.parm("filepath1").set(file_path)
        elif mode == "reference":
            node = parent_node.createNode("reference", "ref_import")
            node.parm("filepath1").set(file_path)
            if prim_path != "/":
                node.parm("primpath").set(prim_path)
        else:
            raise ValueError(
                f"'{mode}' isn't a recognized import mode \u2014 "
                "use 'reference' or 'sublayer'"
            )

        return {
            "node": node.path(),
            "file": file_path,
            "mode": mode,
            "prim_path": prim_path,
        }


    # =========================================================================
    # MATERIAL HANDLERS
    # =========================================================================

    def _handle_create_material(self, payload: Dict) -> Dict:
        """Create a materiallibrary LOP with a MaterialX shader inside it.

        Uses native Houdini nodes (materiallibrary + shader child) so the
        material is visible and editable in the artist's network.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )
        name = resolve_param_with_default(payload, "name", "material")
        shader_type = resolve_param_with_default(
            payload, "shader_type", "mtlxstandard_surface"
        )
        base_color = resolve_param(payload, "base_color", required=False)
        metalness = resolve_param(payload, "metalness", required=False)
        roughness = resolve_param(payload, "roughness", required=False)

        parent = node.parent()

        # Create materiallibrary node and wire it after the resolved LOP node
        matlib = parent.createNode("materiallibrary", name)
        matlib.setInput(0, node)
        matlib.moveToGoodPosition()

        # Cook the matlib so its internal network is ready for child creation
        matlib.cook(force=True)

        # Create shader node inside the materiallibrary
        shader = matlib.createNode(shader_type, name + "_shader")
        if shader is None:
            raise RuntimeError(
                f"Couldn't create a '{shader_type}' shader inside the material library "
                "— check that this shader type is available in your Houdini build"
            )

        # Set optional shader parameters
        if base_color is not None:
            if isinstance(base_color, (list, tuple)) and len(base_color) >= 3:
                for i, ch in enumerate(("r", "g", "b")):
                    p = shader.parm(f"base_color{ch}")
                    if p:
                        p.set(float(base_color[i]))
        if metalness is not None:
            p = shader.parm("metalness")
            if p:
                p.set(float(metalness))
        if roughness is not None:
            p = shader.parm("specular_roughness")
            if p:
                p.set(float(roughness))

        # Read the USD material path that the matlib auto-generates
        material_usd_path = f"/materials/{name}"

        return {
            "matlib_path": matlib.path(),
            "shader_path": shader.path(),
            "material_usd_path": material_usd_path,
            "shader_type": shader_type,
            "name": name,
        }

    def _handle_assign_material(self, payload: Dict) -> Dict:
        """Create an assignmaterial LOP to bind a material to geometry prims."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )
        prim_pattern = resolve_param(payload, "prim_pattern")
        material_path = resolve_param(payload, "material_path")

        parent = node.parent()
        # Safe node name from the material path
        safe_name = material_path.rstrip("/").rsplit("/", 1)[-1] or "mat"
        assign_node = parent.createNode("assignmaterial", f"assign_{safe_name}")
        assign_node.setInput(0, node)
        assign_node.moveToGoodPosition()

        # Set the prim pattern and material spec path
        assign_node.parm("primpattern1").set(prim_pattern)
        assign_node.parm("matspecpath1").set(material_path)

        return {
            "node_path": assign_node.path(),
            "prim_pattern": prim_pattern,
            "material_path": material_path,
        }

    def _handle_read_material(self, payload: Dict) -> Dict:
        """Read material binding and shader parameters from a USD prim.

        Pure stage query — no node creation. Uses UsdShade API to inspect
        material bindings and shader inputs.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )
        prim_path = resolve_param(payload, "prim_path")

        stage = node.stage()
        if stage is None:
            raise ValueError(
                "That node doesn't have an active USD stage yet — "
                "it may need to cook first, or check the LOP network is set up"
            )

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(
                f"Couldn't find a prim at {prim_path} — "
                "double-check the path on the USD stage"
            )

        from pxr import UsdShade

        binding_api = UsdShade.MaterialBindingAPI(prim)
        bound = binding_api.GetDirectBinding()
        mat_path_str = str(bound.GetMaterialPath()) if bound.GetMaterial() else ""

        if not mat_path_str:
            return {
                "prim_path": prim_path,
                "has_material": False,
                "material_path": "",
                "shader_type": "",
                "shader_params": {},
            }

        material = bound.GetMaterial()
        shader_type = ""
        shader_params = {}

        # Get the surface shader output
        surface_output = material.GetSurfaceOutput()
        if surface_output:
            source = surface_output.GetConnectedSources()
            if source and source[0]:
                shader_prim = UsdShade.Shader(source[0][0].source.GetPrim())
                shader_type = str(shader_prim.GetIdAttr().Get() or "")

                for shader_input in shader_prim.GetInputs():
                    input_name = shader_input.GetBaseName()
                    val = shader_input.Get()
                    if val is not None:
                        shader_params[input_name] = _usd_to_json(val)

        return {
            "prim_path": prim_path,
            "has_material": True,
            "material_path": mat_path_str,
            "shader_type": shader_type,
            "shader_params": shader_params,
        }

    # =========================================================================
    # MEMORY HANDLERS
    # =========================================================================

    def _handle_memory_context(self, payload: Dict) -> Dict:
        """Handle context/engram_context command."""
        bridge = self._get_bridge()
        return bridge.handle_memory_context(payload)

    def _handle_memory_search(self, payload: Dict) -> Dict:
        """Handle search/engram_search command."""
        bridge = self._get_bridge()
        return bridge.handle_memory_search(payload)

    def _handle_memory_add(self, payload: Dict) -> Dict:
        """Handle add_memory/engram_add command."""
        bridge = self._get_bridge()
        return bridge.handle_memory_add(payload)

    def _handle_memory_decide(self, payload: Dict) -> Dict:
        """Handle decide/engram_decide command."""
        bridge = self._get_bridge()
        return bridge.handle_memory_decide(payload)

    def _handle_memory_recall(self, payload: Dict) -> Dict:
        """Handle recall/engram_recall command."""
        bridge = self._get_bridge()
        return bridge.handle_memory_recall(payload)

    # =========================================================================
    # SCENE MEMORY HANDLERS (Living Memory System)
    # =========================================================================

    def _handle_project_setup(self, payload: Dict) -> Dict:
        """Initialize or load SYNAPSE project structure for current scene."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import ensure_scene_structure, load_full_context

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))

        paths = ensure_scene_structure(hip_path, job_path)
        hip_dir = os.path.dirname(hip_path)
        ctx = load_full_context(hip_dir, job_path)

        return {
            "paths": paths,
            "project_memory": ctx["project"].get("content", "")[:2000],
            "scene_memory": ctx["scene"].get("content", "")[:3000],
            "agent_state": ctx["agent"],
            "evolution_stage": ctx["scene"].get("evolution", "none"),
            "suspended_tasks": [],
        }

    def _handle_memory_write(self, payload: Dict) -> Dict:
        """Write a memory entry to scene or project memory."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import write_memory_entry, ensure_scene_structure

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
        paths = ensure_scene_structure(hip_path, job_path)

        entry_type = resolve_param(payload, "entry_type")
        content = resolve_param(payload, "content")
        scope = resolve_param_with_default(payload, "scope", "scene")

        if isinstance(content, str):
            content = {"content": content}
        content["scope"] = scope

        write_memory_entry(paths["scene_dir"], content, entry_type)
        return {"written": True, "entry_type": entry_type, "scope": scope}

    def _handle_memory_query(self, payload: Dict) -> Dict:
        """Query scene or project memory."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import load_full_context

        hip_path = hou.hipFile.path()
        job_path = hou.getenv("JOB", os.path.dirname(hip_path))
        hip_dir = os.path.dirname(hip_path)

        query = resolve_param(payload, "query")
        scope = resolve_param_with_default(payload, "scope", "all")

        ctx = load_full_context(hip_dir, job_path)
        results = []

        # Simple text search in markdown for Phase 1
        query_lower = query.lower()
        for layer_name in ("project", "scene"):
            if scope not in ("all", layer_name):
                continue
            content = ctx[layer_name].get("content", "")
            if query_lower in content.lower():
                # Find matching lines
                for i, line in enumerate(content.split("\n")):
                    if query_lower in line.lower():
                        results.append({
                            "layer": layer_name,
                            "line": i + 1,
                            "text": line.strip(),
                        })

        return {
            "query": query,
            "scope": scope,
            "count": len(results),
            "results": results[:50],
        }

    def _handle_memory_status(self, payload: Dict) -> Dict:
        """Get memory system status."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from ..memory.scene_memory import get_memory_status

        hip_path = hou.hipFile.path()
        hip_dir = os.path.dirname(hip_path)
        job_path = hou.getenv("JOB", hip_dir)

        return get_memory_status(hip_dir, job_path)

    # =========================================================================
    # INTROSPECTION HANDLERS (Phase 1)
    # =========================================================================

    def _handle_inspect_selection(self, payload: Dict) -> Dict:
        """Inspect currently selected nodes — connections, parms, geometry, input graph."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_selection
        depth = resolve_param_with_default(payload, "depth", 1)
        return inspect_selection(depth=int(depth))

    def _handle_inspect_scene(self, payload: Dict) -> Dict:
        """Hierarchical scene overview with issues and artist notes."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_scene
        root = resolve_param_with_default(payload, "root", "/")
        max_depth = resolve_param_with_default(payload, "max_depth", 3)
        context_filter = resolve_param_with_default(payload, "context_filter", None)
        return inspect_scene(
            root=root,
            max_depth=int(max_depth),
            context_filter=context_filter,
        )

    def _handle_inspect_node(self, payload: Dict) -> Dict:
        """Deep single-node dump: all parms, expressions, code, geometry, HDA info."""
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)
        from .introspection import inspect_node_detail
        node_path = resolve_param(payload, "node")
        include_code = resolve_param_with_default(payload, "include_code", True)
        include_geometry = resolve_param_with_default(payload, "include_geometry", True)
        include_expressions = resolve_param_with_default(payload, "include_expressions", True)
        return inspect_node_detail(
            node_path=node_path,
            include_code=bool(include_code),
            include_geometry=bool(include_geometry),
            include_expressions=bool(include_expressions),
        )

    def _handle_get_metrics(self, payload: Dict) -> Dict:
        """Return Prometheus-format metrics text."""
        from .metrics import render_prometheus

        router_stats = None
        if hasattr(self, "_router"):
            router_stats = self._router.stats()

        cb_state = "closed"
        memory_count = 0
        try:
            bridge = self._get_bridge()
            if hasattr(bridge, "_memory") and bridge._memory:
                memory_count = len(bridge._memory.get_all())
        except Exception:
            pass

        text = render_prometheus(
            router_stats=router_stats,
            circuit_breaker_state=cb_state,
            memory_entry_count=memory_count,
        )
        return {"format": "prometheus", "text": text}

    def _handle_router_stats(self, payload: Dict) -> Dict:
        """Return tier cascade statistics for LLM self-reflection."""
        if not hasattr(self, "_router"):
            return {"error": "Router not initialized"}
        return self._router.stats()

    def _handle_list_recipes(self, payload: Dict) -> Dict:
        """List all available recipes for artist discovery."""
        from ..routing.recipes import RecipeRegistry
        registry = RecipeRegistry()
        recipes = []
        for recipe in registry.recipes:
            recipes.append({
                "name": recipe.name,
                "description": recipe.description,
                "category": recipe.category,
                "triggers": recipe.triggers,
                "parameters": recipe.parameters,
                "step_count": len(recipe.steps),
            })
        return {
            "count": len(recipes),
            "recipes": sorted(recipes, key=lambda r: r["name"]),
        }

    def _handle_knowledge_lookup(self, payload: Dict) -> Dict:
        """Look up Houdini knowledge from the RAG index.

        Queries the Tier 1 knowledge index for parameter names,
        node types, workflow guides, and FX setup instructions.
        """
        query = resolve_param(payload, "query")

        # Lazy-init the knowledge index
        if not hasattr(self, "_knowledge"):
            from pathlib import Path as _Path
            from ..routing.knowledge import KnowledgeIndex
            import os
            rag_root = os.environ.get(
                "SYNAPSE_RAG_ROOT",
                str(_Path(__file__).resolve().parent.parent.parent.parent / "rag"),
            )
            memory = None
            try:
                from ..memory.store import get_synapse_memory
                memory = get_synapse_memory()
            except Exception:
                pass
            self._knowledge = KnowledgeIndex(
                rag_root=rag_root if _Path(rag_root).exists() else None,
                memory=memory,
            )

        result = self._knowledge.lookup(query)
        return {
            "found": result.found,
            "answer": result.answer,
            "confidence": result.confidence,
            "topic": result.topic,
            "sources": result.sources,
            "agent_hint": result.agent_hint,
        }


def _find_render_rop():
    """Auto-discover a render ROP node. Searches /stage then /out."""
    _RENDER_TYPES = {
        "karma", "karmarendersettings",
        "usdrender", "usdrender_rop",
        "ifd",
        "opengl",
    }
    for parent_path in ["/stage", "/out"]:
        parent = hou.node(parent_path)
        if parent is None:
            continue
        for child in parent.children():
            if child.type().name() in _RENDER_TYPES:
                return child
    raise ValueError(
        "Couldn't auto-find a render ROP \u2014 specify the 'node' parameter "
        "with the path to your ROP (e.g. '/stage/karma1' or '/out/mantra1')"
    )


def _detect_karma_engine(node, node_type: str) -> str:
    """Detect Karma XPU vs CPU vs Mantra vs other renderer.

    Karma XPU is the GPU+CPU hybrid renderer; Karma CPU is pure CPU.
    The engine is selected by a parm on the ROP or Karma Render Settings LOP.
    """
    if node_type == "ifd":
        return "mantra"
    if node_type == "opengl":
        return "opengl"
    if node_type not in ("karma", "karmarendersettings", "usdrender", "usdrender_rop"):
        return node_type

    # Check common parm names for Karma engine variant
    for parm_name in ("renderer", "karmarenderertype", "renderengine"):
        parm = node.parm(parm_name)
        if parm is not None:
            # hou.Parm.eval() reads the parameter value — not Python eval()
            val = str(parm.eval()).lower()  # noqa: S307
            if "xpu" in val:
                return "karma_xpu"
            if "cpu" in val:
                return "karma_cpu"
            return f"karma_{val}" if val else "karma"

    return "karma"


def _usd_to_json(value):
    """Convert USD attribute values to JSON-serializable Python types."""
    if value is None:
        return None
    # Scalars
    if isinstance(value, (bool, int, float, str)):
        return value
    # Matrix types (GfMatrix4d, GfMatrix3d) — check BEFORE generic sequence
    if hasattr(value, 'GetRow'):
        try:
            size = 4 if hasattr(value, 'IsIdentity') else 3
            return [[float(value[r][c]) for c in range(size)] for r in range(size)]
        except Exception:
            pass
    # Tuples/vectors (GfVec2f, GfVec3f, GfVec4f, GfQuatf, etc.)
    if hasattr(value, '__len__') and hasattr(value, '__getitem__'):
        try:
            return [float(v) for v in value]
        except (TypeError, ValueError):
            return [_usd_to_json(v) for v in value]
    # Asset paths
    if hasattr(value, 'path'):
        return str(value.path)
    return str(value)


def _run_compiled(compiled_code, globals_dict, locals_dict):
    """
    Run compiled Python code. Separated for DCC scripting pattern.

    This uses Python's exec() builtin intentionally for Houdini automation -
    it is NOT shell command execution.
    """
    exec(compiled_code, globals_dict, locals_dict)  # noqa: S102


# Backwards compatibility
NexusHandler = SynapseHandler
