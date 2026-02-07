"""
Synapse Command Handlers

Registry-based command handler system for the Synapse WebSocket server.
Routes incoming commands to appropriate handler functions.
"""

import time
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
from ..core.aliases import resolve_param, resolve_param_with_default


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
                    error=f"Unknown command type: {command.type}",
                    sequence=command.sequence,
                )

            result = handler(command.payload)

            # Log action to session
            bridge = self._get_bridge()
            if bridge and self._session_id:
                bridge.log_action(
                    f"Executed: {cmd_type}",
                    session_id=self._session_id,
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
                error=f"Handler error: {e}",
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

        # USD/Solaris
        reg.register("get_stage_info", self._handle_get_stage_info)
        reg.register("get_usd_attribute", self._handle_get_usd_attribute)
        reg.register("set_usd_attribute", self._handle_set_usd_attribute)
        reg.register("create_usd_prim", self._handle_create_usd_prim)
        reg.register("modify_usd_prim", self._handle_modify_usd_prim)

        # Memory operations (new names)
        reg.register("context", self._handle_memory_context)
        reg.register("search", self._handle_memory_search)
        reg.register("add_memory", self._handle_memory_add)
        reg.register("decide", self._handle_memory_decide)
        reg.register("recall", self._handle_memory_recall)

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
    # NODE HANDLERS
    # =========================================================================

    def _handle_create_node(self, payload: Dict) -> Dict:
        """Handle create_node command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        parent = resolve_param(payload, "parent")
        node_type = resolve_param(payload, "type")
        name = resolve_param(payload, "name", required=False)

        parent_node = hou.node(parent)
        if parent_node is None:
            raise ValueError(f"Parent node not found: {parent}")

        if name:
            new_node = parent_node.createNode(node_type, name)
        else:
            new_node = parent_node.createNode(node_type)

        new_node.moveToGoodPosition()

        # Log node creation
        bridge = self._get_bridge()
        if bridge and self._session_id:
            bridge.log_node_created(
                new_node.path(), node_type, session_id=self._session_id
            )

        return {
            "path": new_node.path(),
            "type": node_type,
            "name": new_node.name(),
        }

    def _handle_delete_node(self, payload: Dict) -> Dict:
        """Handle delete_node command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        node_path = resolve_param(payload, "node")
        node = hou.node(node_path)
        if node is None:
            raise ValueError(f"Node not found: {node_path}")

        node_name = node.name()
        node.destroy()

        return {"deleted": node_path, "name": node_name}

    def _handle_connect_nodes(self, payload: Dict) -> Dict:
        """Handle connect_nodes command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        source_path = resolve_param(payload, "source")
        target_path = resolve_param(payload, "target")
        source_output = resolve_param_with_default(payload, "source_output", 0)
        target_input = resolve_param_with_default(payload, "target_input", 0)

        source_node = hou.node(source_path)
        target_node = hou.node(target_path)

        if source_node is None:
            raise ValueError(f"Source node not found: {source_path}")
        if target_node is None:
            raise ValueError(f"Target node not found: {target_path}")

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
            raise RuntimeError("Houdini not available")

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(f"Node not found: {node_path}")

        parm = node.parm(parm_name)
        if parm is None:
            # Try as parm tuple
            parm_tuple = node.parmTuple(parm_name)
            if parm_tuple is not None:
                return {
                    "node": node_path,
                    "parm": parm_name,
                    "value": [p.eval() for p in parm_tuple],
                    "is_tuple": True,
                }
            raise ValueError(f"Parameter not found: {parm_name} on {node_path}")

        return {
            "node": node_path,
            "parm": parm_name,
            "value": parm.eval(),
            "is_tuple": False,
        }

    def _handle_set_parm(self, payload: Dict) -> Dict:
        """Handle set_parm command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(f"Node not found: {node_path}")

        parm = node.parm(parm_name)
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

        raise ValueError(f"Parameter not found: {parm_name} on {node_path}")

    # =========================================================================
    # SCENE HANDLERS
    # =========================================================================

    def _handle_get_scene_info(self, payload: Dict) -> Dict:
        """Handle get_scene_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        return {
            "hip_file": hou.hipFile.name(),
            "frame": int(hou.frame()),
            "fps": hou.fps(),
            "frame_range": [int(hou.playbar.frameRange()[0]), int(hou.playbar.frameRange()[1])],
        }

    def _handle_get_selection(self, payload: Dict) -> Dict:
        """Handle get_selection command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

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
        """
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        code = resolve_param(payload, "content")

        # Build execution namespace with Houdini access
        exec_globals = {"hou": hou, "__builtins__": __builtins__}
        exec_locals = {}

        # Execute the provided code in Houdini's namespace
        # This is intentional DCC automation, not shell execution
        compiled = compile(code, "<synapse_exec>", "exec")
        _run_compiled(compiled, exec_globals, exec_locals)

        # Try to extract a result variable
        result = exec_locals.get("result", "executed")

        return {
            "executed": True,
            "result": str(result) if result else "executed",
        }

    # =========================================================================
    # USD/SOLARIS HANDLERS
    # =========================================================================

    def _handle_get_stage_info(self, payload: Dict) -> Dict:
        """Handle get_stage_info command."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

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
            raise ValueError("No USD stage found. Select a LOP node or specify node path.")

        stage = node.stage()
        if stage is None:
            raise ValueError("Node has no active stage")

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
            raise RuntimeError("Houdini not available")

        if node_path:
            node = hou.node(node_path)
            if node is None:
                raise ValueError(f"Node not found: {node_path}")
            if not hasattr(node, 'stage'):
                raise ValueError(f"Node is not a LOP node: {node_path}")
            return node

        # Search selection for a LOP node
        for n in hou.selectedNodes():
            if hasattr(n, 'stage'):
                return n

        raise ValueError("No LOP node found. Select a LOP node or specify node path.")

    def _handle_get_usd_attribute(self, payload: Dict) -> Dict:
        """Handle get_usd_attribute command — read a USD attribute from a prim."""
        node = self._resolve_lop_node(
            resolve_param(payload, "node", required=False)
        )

        prim_path = resolve_param(payload, "prim_path")
        attr_name = resolve_param(payload, "usd_attribute")

        stage = node.stage()
        if stage is None:
            raise ValueError("Node has no active stage")

        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            raise ValueError(f"Prim not found: {prim_path}")

        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            # List available attributes to help the caller
            attrs = [a.GetName() for a in prim.GetAttributes()][:30]
            raise ValueError(
                f"Attribute '{attr_name}' not found on {prim_path}. "
                f"Available: {', '.join(attrs)}"
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
            f"prim = stage.GetPrimAtPath('{prim_path}')\n"
            "if prim:\n"
            f"    attr = prim.GetAttribute('{attr_name}')\n"
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
            f"stage.DefinePrim('{prim_path}', '{prim_type}')\n"
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
            f"prim = stage.GetPrimAtPath('{prim_path}')",
            "if prim:",
        ]
        mods = {}
        if kind is not None:
            lines.append(f"    Usd.ModelAPI(prim).SetKind('{kind}')")
            mods["kind"] = kind
        if purpose is not None:
            lines.append(f"    UsdGeom.Imageable(prim).GetPurposeAttr().Set('{purpose}')")
            mods["purpose"] = purpose
        if active is not None:
            lines.append(f"    prim.SetActive({active})")
            mods["active"] = active

        if not mods:
            raise ValueError("No modifications specified. Provide kind, purpose, or active.")

        code = "\n".join(lines)
        py_lop.parm("python").set(code)

        return {
            "created_node": py_lop.path(),
            "prim_path": prim_path,
            "modifications": mods,
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
