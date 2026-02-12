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
from ..core.errors import (
    SynapseUserError,
    SynapseServiceError,
    NodeNotFoundError,
    ParameterError,
    HoudiniUnavailableError,
)
from .handlers_node import NodeHandlerMixin
from .handlers_usd import UsdHandlerMixin
from .handlers_render import RenderHandlerMixin
from .handlers_memory import MemoryHandlerMixin



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
        """Get handler for a command type (expects pre-normalized type)."""
        return self._handlers.get(command_type)

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

class SynapseHandler(NodeHandlerMixin, UsdHandlerMixin, RenderHandlerMixin, MemoryHandlerMixin):
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
            cmd_type = normalize_command_type(command.type)
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
                self._submit_logs(cmd_type, command.payload, result)

            return SynapseResponse(
                id=command.id,
                success=True,
                data=result,
                sequence=command.sequence,
            )

        except SynapseUserError as e:
            # User errors: bad input, missing node, bad parm. Don't trip CB.
            return SynapseResponse(
                id=command.id,
                success=False,
                error=str(e),
                sequence=command.sequence,
            )
        except ValueError as e:
            # Legacy ValueError path -- still user error, don't trip CB.
            return SynapseResponse(
                id=command.id,
                success=False,
                error=str(e),
                sequence=command.sequence,
            )
        except SynapseServiceError as e:
            # Service errors: Houdini down, execution crash. DO trip CB.
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

    def _submit_logs(self, cmd_type: str, payload: Dict, result: Any):
        """Submit bridge + audit log in a single executor call."""
        bridge = self._get_bridge()
        sid = self._session_id
        category = _CMD_CATEGORY.get(cmd_type, AuditCategory.SYNAPSE)
        output = result if isinstance(result, dict) else {}

        def _do_log():
            if bridge and sid:
                bridge.log_action(f"Executed: {cmd_type}", session_id=sid)
            audit_log().log(
                operation=cmd_type,
                message=f"Executed {cmd_type}",
                level=AuditLevel.AGENT_ACTION,
                category=category,
                input_data=payload,
                output_data=output,
            )

        _log_executor.submit(_do_log)

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
        reg.register("evolve_memory", self._handle_evolve_memory)

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
    # PARAMETER HANDLERS
    # =========================================================================

    def _handle_get_parm(self, payload: Dict) -> Dict:
        """Handle get_parm command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")

        node = hou.node(node_path)
        if node is None:
            raise NodeNotFoundError(node_path)

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
            raise ParameterError(node_path, parm_name, suggestion=hint.strip() if hint else "")

        return {
            "node": node_path,
            "parm": parm_name,
            "value": parm.eval(),
            "is_tuple": False,
        }

    def _handle_set_parm(self, payload: Dict) -> Dict:
        """Handle set_parm command."""
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")

        node = hou.node(node_path)
        if node is None:
            raise NodeNotFoundError(node_path)

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
        raise ParameterError(node_path, parm_name, suggestion=hint.strip() if hint else "")

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

def _run_compiled(compiled_code, globals_dict, locals_dict):
    """
    Run compiled Python code. Separated for DCC scripting pattern.

    This uses Python's exec() builtin intentionally for Houdini automation -
    it is NOT shell command execution.
    """
    exec(compiled_code, globals_dict, locals_dict)  # noqa: S102


# Backwards compatibility
NexusHandler = SynapseHandler

# Re-export module-level helpers that moved to mixin modules
# (tests and external code may reference them via handlers_mod)
from .handlers_render import _find_render_rop, _detect_karma_engine  # noqa: E402,F401
from .handlers_usd import _usd_to_json  # noqa: E402,F401
from .handlers_node import _suggest_children  # noqa: E402,F401
