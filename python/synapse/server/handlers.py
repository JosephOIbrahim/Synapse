"""
Synapse Command Handlers

Registry-based command handler system for the Synapse WebSocket server.
Routes incoming commands to appropriate handler functions.
"""

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
from ..core.aliases import resolve_param, resolve_param_with_default


# Reuse 2 threads for fire-and-forget memory logging (avoids Thread() per command)
_log_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synapse-log")

# Idempotent guard functions — injected into execute_python namespace
try:
    from .guards import GUARD_FUNCTIONS as _GUARD_FUNCTIONS
except ImportError:
    _GUARD_FUNCTIONS = {}  # Graceful fallback if guards not available

# Commands that don't modify state — skip memory logging for these
_READ_ONLY_COMMANDS = frozenset({
    "ping", "get_health", "get_help", "heartbeat",
    "get_parm", "get_scene_info", "get_selection",
    "get_stage_info", "get_usd_attribute",
    "context", "search", "recall",
    "capture_viewport",
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
                    error=f"Unknown command type: {command.type}",
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

        # Build execution namespace with Houdini access + idempotent guards
        exec_globals = {"hou": hou, "__builtins__": __builtins__}
        try:
            from .guards import GUARD_FUNCTIONS
            exec_globals.update(GUARD_FUNCTIONS)
        except ImportError:
            pass
        exec_locals = {}

        # Execute inside undo group (allows manual undo, but no auto-rollback
        # — render errors and other operational failures would incorrectly
        # undo node creation that succeeded before the error)
        compiled = compile(code, "<synapse_exec>", "exec")
        with hou.undos.group("synapse_execute"):
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
            raise ValueError("No modifications specified. Provide kind, purpose, or active.")

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
            raise RuntimeError("Houdini not available")

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
                raise ValueError("No SceneViewer pane found in the current desktop")

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
            raise RuntimeError(f"Flipbook capture failed — file not found: {actual_path}")

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
            raise RuntimeError("Houdini not available")
        from pathlib import Path

        rop_path = resolve_param(payload, "node", required=False)
        frame = resolve_param_with_default(payload, "frame", None)
        width = resolve_param_with_default(payload, "width", None)
        height = resolve_param_with_default(payload, "height", None)

        def _render_on_main():
            if rop_path:
                node = hou.node(rop_path)
                if node is None:
                    raise ValueError(f"Node not found: {rop_path}")
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
                raise RuntimeError(f"Render output not found: {out_path}")
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
            raise RuntimeError("Houdini not available")
        node_path = resolve_param(payload, "node")
        parm_name = resolve_param(payload, "parm")
        value = resolve_param(payload, "value")
        frame = resolve_param_with_default(payload, "frame", None)

        node = hou.node(node_path)
        if node is None:
            raise ValueError(f"Node not found: {node_path}")
        parm = node.parm(parm_name)
        if parm is None:
            raise ValueError(f"Parameter not found: {node_path}/{parm_name}")

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
            raise RuntimeError("Houdini not available")
        node_path = resolve_param(payload, "node")

        node = hou.node(node_path)
        if node is None:
            raise ValueError(f"Node not found: {node_path}")

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
            for k, v in overrides.items():
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
            raise RuntimeError("Houdini not available")

        import hdefereval

        top_path = resolve_param(payload, "node")  # TOP network or wedge node
        wedge_parm = resolve_param(payload, "parm", required=False)
        values = resolve_param(payload, "values", required=False)

        if values is not None and not isinstance(values, list):
            raise ValueError("'values' must be a list")

        def _run_wedge():
            node = hou.node(top_path)
            if node is None:
                raise ValueError(f"Node not found: {top_path}")

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
                    raise ValueError(f"No wedge node found in {top_path}")
            else:
                raise ValueError(f"Node {top_path} is not a TOP network or node")

        result = hdefereval.executeInMainThreadWithResult(_run_wedge)
        return result

    # =========================================================================
    # USD SCENE ASSEMBLY (REFERENCE / SUBLAYER)
    # =========================================================================

    def _handle_reference_usd(self, payload: Dict) -> Dict:
        """Import a USD file into the stage via reference or sublayer."""
        if not HOU_AVAILABLE:
            raise RuntimeError("Houdini not available")

        file_path = resolve_param(payload, "file")
        prim_path = resolve_param_with_default(payload, "prim_path", "/")
        mode = resolve_param_with_default(payload, "mode", "reference")
        parent = resolve_param_with_default(payload, "parent", "/stage")

        parent_node = hou.node(parent)
        if parent_node is None:
            raise ValueError(f"Parent node not found: {parent}")

        if mode == "sublayer":
            node = parent_node.createNode("sublayer", "sublayer_import")
            node.parm("filepath1").set(file_path)
        elif mode == "reference":
            node = parent_node.createNode("reference", "ref_import")
            node.parm("filepath1").set(file_path)
            if prim_path != "/":
                node.parm("primpath").set(prim_path)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'reference' or 'sublayer'.")

        return {
            "node": node.path(),
            "file": file_path,
            "mode": mode,
            "prim_path": prim_path,
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
        "No render ROP found. Specify 'node' parameter with the ROP path "
        "(e.g. '/stage/karma1' or '/out/mantra1')."
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
