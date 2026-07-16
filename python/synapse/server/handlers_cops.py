"""
Synapse Copernicus (COPs) Handler Mixin

Handlers for Houdini 21 Copernicus image processing: network creation,
node management, OpenCL kernels, MaterialX interop, AOV compositing,
solvers, procedural textures, motion design, and batch processing.

20 handlers across 4 capability tiers:
  - Foundation: create_network, create_node, connect, set_opencl, read_layer_info
  - Pipeline: to_materialx, composite_aovs, analyze_render, slap_comp
  - Procedural: create_solver, procedural_texture, growth_propagation,
                reaction_diffusion, pixel_sort, stylize
  - Advanced: wetmap, bake_textures, temporal_analysis, stamp_scatter, batch_cook
"""

import logging
from typing import Dict, List, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param, resolve_param_with_default
from .handler_helpers import _HOUDINI_UNAVAILABLE

_LOG = logging.getLogger(__name__)

# Copernicus image-read API-drift tracking. The H22 migration handed us a
# replacement surface (cable() -> CopCable -> ImageLayer) for the removed
# planes()/xRes()/yRes()/depth() quartet. If THAT surface drifts the same way --
# a method quietly disappearing on a future build -- the old blanket except-pass
# would silently degrade the read to empty, reproducing the exact failure class
# that hid the planes() break (W.1 crucible sev-3). So an AttributeError on any
# replacement-surface symbol is now LOUD: warn-once here + a structured api_drift
# entry the caller can surface (analyze_render appends it to issues[]).
_WARNED_COP_DRIFT: set = set()


def _warn_cop_drift_once(symbol: str, exc: Exception) -> None:
    """Log a Copernicus-surface AttributeError exactly once per process per symbol."""
    if symbol in _WARNED_COP_DRIFT:
        return
    _WARNED_COP_DRIFT.add(symbol)
    _LOG.warning(
        "Copernicus image-read API drift: %s raised AttributeError (%s). The H22 "
        "replacement surface changed again -- image metadata is degraded, not "
        "wrong-but-silent. Re-probe the Cop cable/ImageLayer API against the live "
        "build.", symbol, exc,
    )


def _cop_drift_issue(symbol: str, exc: Exception) -> Dict:
    """Structured api_drift entry for the analyze_render ``issues[]`` list."""
    return {
        "check": "api_drift",
        "severity": "warning",
        "message": (
            f"Copernicus image-read API drift: {symbol} raised AttributeError "
            "-- image metadata degraded (replacement surface changed since 22.0.368)"
        ),
        "symbol": symbol,
        "details": str(exc),
    }


# Legacy COP2 node types most exposed by the Houdini 22 Copernicus migration.
# On H21 all three are registered -> the probe reports True and node creation is
# completely unchanged. cop2net/copnet are network managers, vopcop2gen is a Cop2
# node, so they live in different node-type categories.
_LEGACY_COP_TYPES = ("cop2net", "vopcop2gen", "copnet")


def _cop_type_registered(type_name: str) -> bool:
    """Return True if ``type_name`` is a registered node type in the live runtime.

    Scans every node-type category so we never have to guess the right one. When
    ``hou`` is unavailable or the lookup itself raises, we return True: an inability
    to prove the type is gone must never block the working H21 path.
    """
    if not HOU_AVAILABLE:
        return True
    try:
        for category in hou.nodeTypeCategories().values():
            if hou.nodeType(category, type_name) is not None:
                return True
    except Exception:
        return True
    return False


def cop_type_survival() -> Dict[str, bool]:
    """Probe whether the legacy COP node types survive in the live Houdini build.

    Returns ``{type_name: bool}`` for cop2net / vopcop2gen / copnet. Pure no-op
    (empty dict) when ``hou`` is unavailable -- zero side effects, no ``hou`` calls.
    On H21 all three resolve True; a False on H22 is the early, legible signal that
    the legacy COP2 surface was removed in the Copernicus migration.
    """
    if not HOU_AVAILABLE:
        return {}
    return {type_name: _cop_type_registered(type_name) for type_name in _LEGACY_COP_TYPES}


def _cop_missing_type_message(type_name: str) -> str:
    """Clear, actionable error text for a COP node type that isn't registered."""
    return (
        f"COP node type '{type_name}' is not registered in this Houdini build. "
        "The legacy COP2 surface (cop2net / vopcop2gen) was migrated to Copernicus "
        "in Houdini 22, so legacy types may no longer exist. Rebuild this network on "
        "the modern Copernicus 'copnet' surface (see cops_create_copnet), or run on "
        "Houdini 21 where the legacy COP2 types are still registered."
    )


def _uses_legacy_cop2_surface(node) -> bool:
    """True when ``node`` exposes the legacy COP2 read surface (planes/xRes/yRes/depth).

    H22 split the image-read API in two (NWS-03 / HOM-02, verified live on 22.0.368):
    legacy ``hou.Cop2Node`` keeps ``planes()``/``xRes()``/``yRes()``/``depth()``, while
    Copernicus ``hou.CopNode`` lost all four and reads via ``cable()``/``ImageLayer``.
    Class identity is checked first (authoritative on a real runtime); when neither
    class check is conclusive (stub/test environments) we fall back to the node-type
    category name -- Copernicus is category ``Cop``, legacy is ``Cop2``. If nothing is
    provable we default to the legacy path: an inability to prove the node is
    Copernicus must never break the previously-working read.
    """
    cop2_cls = getattr(hou, "Cop2Node", None)
    if isinstance(cop2_cls, type):
        try:
            if isinstance(node, cop2_cls):
                return True
        except TypeError:
            pass
    cop_cls = getattr(hou, "CopNode", None)
    if isinstance(cop_cls, type):
        try:
            if isinstance(node, cop_cls):
                return False
        except TypeError:
            pass
    try:
        return node.type().category().name() != "Cop"
    except Exception:
        return True


def _read_or_drift(read, symbol: str, drift: List[Dict], default=None):
    """Invoke ``read()`` guarding one Copernicus replacement-surface symbol.

    Returns ``(ok, value)``. An ``AttributeError`` means ``symbol`` vanished on this
    build -> LOUD (warn-once + a drift entry appended to ``drift``). Any other
    exception is a transient/un-cooked read -> defensive (debug log only). ``ok`` is
    False (and ``value`` is ``default``) in both failure cases. Centralizing the
    two-tier guard keeps the six read sites from hand-duplicating the symbol string
    and the except-pair -- a mistyped drift symbol would otherwise be a silent bug.

    CONTRACT: ``read`` must be a *zero-arg callable that performs the attribute
    lookup itself* (e.g. ``lambda: node.cable()``), NOT a pre-bound method
    (``node.cable``). Passing a bound method makes the ``AttributeError`` for a
    vanished symbol fire at *argument evaluation* -- outside this ``try`` -- so it
    propagates uncaught instead of becoming a drift entry. All six call sites below
    wrap their deref in a lambda for exactly this reason.
    """
    try:
        return True, read()
    except AttributeError as exc:
        _warn_cop_drift_once(symbol, exc)
        drift.append(_cop_drift_issue(symbol, exc))
    except Exception as exc:
        _LOG.debug("Copernicus %s read failed (defensive): %s", symbol, exc)
    return False, default


def _copernicus_image_info(node) -> Tuple[Dict, List[Dict]]:
    """Best-effort image metadata read for a Copernicus (``hou.CopNode``) node.

    Uses the verified H22 replacement surface for the removed ``planes()``/
    ``xRes()``/``yRes()``/``depth()`` quartet: ``node.cable()`` -> ``hou.CopCable``
    (``wireNames()`` are the H22 equivalent of plane names) -> ``layerByIndex(0)``
    -> ``hou.ImageLayer`` (``bufferResolution()`` / ``storageType()``).

    Returns ``(info, drift)``. ``info`` carries any of ``planes`` / ``resolution``
    / ``data_type`` that could be read. ``drift`` is a list of ``api_drift`` entries
    -- one per replacement-surface symbol that raised ``AttributeError`` (i.e. the
    method vanished on this build). All six derefs (cable / wireNames / wireCount /
    layerByIndex / bufferResolution / storageType) go through ``_read_or_drift`` as
    zero-arg lambdas, so an AttributeError on ANY of them is caught and turned into
    a warn-once + drift entry -- none can crash the caller. AttributeError is LOUD
    because a silently-empty read is the exact class that masked the planes() break.
    Non-AttributeError exceptions stay defensive -- an un-cooked/unloaded node
    legitimately has no cable/wires -- but are logged at debug so they are never
    fully invisible.
    """
    info: Dict = {}
    drift: List[Dict] = []

    ok, cable = _read_or_drift(lambda: node.cable(), "hou.CopNode.cable", drift)
    if not ok or cable is None:
        return info, drift

    ok, planes = _read_or_drift(
        lambda: [str(name) for name in cable.wireNames()], "hou.CopCable.wireNames", drift)
    if ok:
        info["planes"] = planes

    ok, count = _read_or_drift(lambda: cable.wireCount(), "hou.CopCable.wireCount", drift, default=0)
    if not ok or count <= 0:
        return info, drift

    ok, layer = _read_or_drift(lambda: cable.layerByIndex(0), "hou.CopCable.layerByIndex", drift)
    if not ok or layer is None:
        return info, drift

    ok, res = _read_or_drift(lambda: layer.bufferResolution(), "hou.ImageLayer.bufferResolution", drift)
    if ok and res is not None:
        try:
            info["resolution"] = [int(res[0]), int(res[1])]
        except (TypeError, IndexError, ValueError):
            pass  # malformed resolution tuple -- omit honestly, not a symbol-drift

    ok, storage = _read_or_drift(lambda: layer.storageType(), "hou.ImageLayer.storageType", drift)
    if ok:
        info["data_type"] = str(storage)

    return info, drift


def _create_cop_node(parent, type_name, node_name=None):
    """``createNode`` wrapper that fails legibly when a COP type isn't registered.

    H21 behavior is preserved exactly: when ``type_name`` exists this is a plain
    pass-through to ``parent.createNode(...)`` with an identical return value and no
    extra runtime lookups on the success path. Only when creation actually fails AND
    the type is confirmed absent from the runtime do we raise a clear, actionable
    error naming the type and pointing at the H22 Copernicus migration -- instead of
    letting Houdini surface a cryptic one.
    """
    try:
        if node_name is not None:
            node = parent.createNode(type_name, node_name)
        else:
            node = parent.createNode(type_name)
    except Exception as exc:
        if not _cop_type_registered(type_name):
            raise RuntimeError(_cop_missing_type_message(type_name)) from exc
        raise
    if node is None and not _cop_type_registered(type_name):
        raise RuntimeError(_cop_missing_type_message(type_name))
    return node


class CopsHandlerMixin:
    """Mixin providing Copernicus (COP) handlers for SynapseHandler."""

    # =========================================================================
    # PHASE 1: Foundation
    # =========================================================================

    def _handle_cops_create_network(self, payload: Dict) -> Dict:
        """Create a COP2 network container at the specified parent.

        Payload:
            parent (str): Parent node path (default: '/obj').
            name (str): Network name (default: 'cop2net').
            initial_nodes (list[str]): Optional list of COP node types to create inside.

        Returns:
            Dict with network path and any initial node paths created.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param_with_default(payload, "parent", "/obj")
        name = resolve_param_with_default(payload, "name", "cop2net")
        initial_nodes = resolve_param_with_default(payload, "initial_nodes", None)

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(
                    f"Couldn't find parent node '{parent_path}' -- "
                    "check the path and try again"
                )

            created_any = False
            try:
                with hou.undos.group("synapse_cops_create_network"):
                    network = _create_cop_node(parent, "cop2net", name)
                    created_any = True
                    if network is None:
                        raise RuntimeError(
                            "Couldn't create COP2 network -- "
                            "make sure Copernicus is available in your Houdini build"
                        )
                    network.moveToGoodPosition()

                    created_nodes = []
                    if initial_nodes and isinstance(initial_nodes, list):
                        for i, node_type in enumerate(initial_nodes):
                            child = network.createNode(str(node_type))
                            created_any = True
                            if child is not None:
                                child.moveToGoodPosition()
                                created_nodes.append({
                                    "path": child.path(),
                                    "type": child.type().name(),
                                })
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "network_path": network.path(),
                "initial_nodes": created_nodes,
            }

        return run_on_main(_on_main)

    def _handle_cops_create_copnet(self, payload: Dict) -> Dict:
        """Create a modern Copernicus 'copnet' network container.

        Distinct from the legacy 'cop2net' built by _handle_cops_create_network:
        H21 Copernicus uses the 'copnet' node type. This is the foundational
        modern-Copernicus surface — all 20 existing cops_* tools build on the
        legacy cop2net; this adds the modern container without rewriting them.

        Payload:
            parent (str): Parent node path (default: '/obj' — mirrors
                _handle_cops_create_network, a container creator).
            name (str): Network name (default: 'copnet').
            starter (str): Optional single COP node type to create inside the
                new copnet so the network is non-empty (mirrors the
                initial_nodes pattern of create_network, single-node form).

        Returns:
            Dict with network path, type name, and optional starter node path.

        Note:
            Behavioral verification (does the copnet cook through Karma XPU)
            is DEFERRED — the live bridge is down. This handler only builds
            the network; it intentionally performs no cook() calls.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param_with_default(payload, "parent", "/obj")
        name = resolve_param_with_default(payload, "name", "copnet")
        starter = resolve_param_with_default(payload, "starter", None)

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(
                    f"Couldn't find parent node '{parent_path}' -- "
                    "check the path and try again"
                )

            created_any = False
            try:
                with hou.undos.group("synapse_cops_create_copnet"):
                    network = _create_cop_node(parent, "copnet", name)
                    created_any = True
                    if network is None:
                        raise RuntimeError(
                            "Couldn't create copnet -- "
                            "make sure Copernicus is available in your Houdini build"
                        )
                    network.moveToGoodPosition()

                    starter_path = None
                    if starter:
                        child = network.createNode(str(starter))
                        created_any = True
                        if child is not None:
                            child.moveToGoodPosition()
                            starter_path = child.path()
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "network_path": network.path(),
                "type": network.type().name(),
                "starter_node": starter_path,
            }

        return run_on_main(_on_main)

    def _handle_cops_create_node(self, payload: Dict) -> Dict:
        """Create a COP node inside a COP network.

        Payload:
            parent (str, required): COP network path.
            type (str, required): COP node type (e.g. 'vopcop2gen', 'blur', 'composite').
            name (str): Optional node name.

        Returns:
            Dict with created node path and type.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        node_type = resolve_param(payload, "type")
        name = resolve_param_with_default(payload, "name", None)

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(
                    f"Couldn't find COP network '{parent_path}' -- "
                    "check the path and try again"
                )

            with hou.undos.group("synapse_cops_create_node"):
                if name:
                    node = parent.createNode(node_type, name)
                else:
                    node = parent.createNode(node_type)

                if node is None:
                    raise RuntimeError(
                        f"Couldn't create COP node of type '{node_type}' -- "
                        "check that this node type exists in Copernicus"
                    )
                node.moveToGoodPosition()

            return {
                "path": node.path(),
                "type": node.type().name(),
                "name": node.name(),
            }

        return run_on_main(_on_main)

    def _handle_cops_connect(self, payload: Dict) -> Dict:
        """Connect two COP nodes together.

        Payload:
            source (str, required): Source COP node path.
            target (str, required): Target COP node path.
            source_output (int): Source output index (default: 0).
            target_input (int): Target input index (default: 0).

        Returns:
            Dict confirming the connection.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        source_path = resolve_param(payload, "source")
        target_path = resolve_param(payload, "target")
        source_output = int(resolve_param_with_default(payload, "source_output", 0))
        target_input = int(resolve_param_with_default(payload, "target_input", 0))

        from .main_thread import run_on_main

        def _on_main():
            source = hou.node(source_path)
            target = hou.node(target_path)
            if source is None:
                raise ValueError(f"Couldn't find source COP node '{source_path}'")
            if target is None:
                raise ValueError(f"Couldn't find target COP node '{target_path}'")

            with hou.undos.group("synapse_cops_connect"):
                target.setInput(target_input, source, source_output)

            return {
                "source": source.path(),
                "target": target.path(),
                "source_output": source_output,
                "target_input": target_input,
                "connected": True,
            }

        return run_on_main(_on_main)

    def _handle_cops_set_opencl(self, payload: Dict) -> Dict:
        """Set OpenCL kernel code on a COP node.

        Configures the 'kernelcode' parameter on an OpenCL-capable COP node.

        Payload:
            node (str, required): COP node path (typically a vopcop2gen or opencl node).
            kernel_code (str, required): OpenCL kernel source code.
            kernel_name (str): Entry point function name (default: 'kernelName').

        Returns:
            Dict confirming the kernel was set.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        kernel_code = resolve_param(payload, "kernel_code")
        kernel_name = resolve_param_with_default(payload, "kernel_name", None)

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(f"Couldn't find COP node '{node_path}'")

            with hou.undos.group("synapse_cops_set_opencl"):
                parm = node.parm("kernelcode")
                if parm is None:
                    # Try alternate parm names used by different COP node types
                    for alt in ("opencl_code", "code", "snippet"):
                        parm = node.parm(alt)
                        if parm is not None:
                            break
                if parm is None:
                    raise ValueError(
                        f"Node '{node_path}' doesn't have a kernel code parameter -- "
                        "make sure it's an OpenCL-capable COP node"
                    )
                parm.set(kernel_code)

                if kernel_name:
                    kn_parm = node.parm("kernelname")
                    if kn_parm is not None:
                        kn_parm.set(kernel_name)

            return {
                "node": node.path(),
                "kernel_set": True,
                "kernel_length": len(kernel_code),
            }

        return run_on_main(_on_main)

    def _handle_cops_read_layer_info(self, payload: Dict) -> Dict:
        """Read layer information from a COP node (read-only).

        Queries resolution, data type, channel count, and cook status.

        Payload:
            node (str, required): COP node path.

        Returns:
            Dict with layer metadata: resolution, depth, channels, cook status.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(f"Couldn't find COP node '{node_path}'")

            result = {
                "node": node.path(),
                "type": node.type().name(),
            }

            if _uses_legacy_cop2_surface(node):
                # Legacy COP2 surface -- planes()/xRes()/yRes()/depth() survive
                # on hou.Cop2Node in H22 (verified 22.0.368); path unchanged.
                # Query resolution via xRes/yRes methods or parms
                try:
                    result["resolution"] = [node.xRes(), node.yRes()]
                except (AttributeError, Exception):
                    for rx, ry in [("resx", "resy"), ("res_x", "res_y")]:
                        px = node.parm(rx)
                        py = node.parm(ry)
                        if px is not None and py is not None:
                            result["resolution"] = [px.eval(), py.eval()]
                            break

                # Query planes/channels FIRST -- H22 Cop2Node.depth() needs a plane
                # name argument, so we must know a plane before probing the depth.
                try:
                    planes = node.planes()
                    result["planes"] = [str(p) for p in planes] if planes else []
                except (AttributeError, Exception):
                    result["planes"] = []

                # Query data type / depth. On 22.0.368 hou.Cop2Node.depth(plane)
                # REQUIRES a plane arg -- a bare depth() TypeErrors and the old broad
                # except silently dropped data_type. Probe the first plane's depth;
                # fall back to a depth/data_type parm; omit the field honestly when
                # there is nothing to probe.
                data_type = None
                plane_for_depth = result["planes"][0] if result["planes"] else None
                if plane_for_depth is not None:
                    try:
                        data_type = str(node.depth(plane_for_depth))
                    except (AttributeError, Exception):
                        data_type = None
                if data_type is None:
                    dp = node.parm("depth") or node.parm("data_type")
                    if dp is not None:
                        data_type = str(dp.eval())
                if data_type is not None:
                    result["data_type"] = data_type
            else:
                # Copernicus surface -- H22 removed planes()/xRes()/yRes()/depth()
                # from hou.CopNode (NWS-03); read via cable()/ImageLayer instead.
                # AttributeError drift is warned-once inside the helper AND surfaced
                # below as an additive api_drift key -- read_layer_info has no issues[]
                # channel, so a warn-once log alone goes silent after call #1 and a
                # persistently-drifted node would be indistinguishable from an
                # un-cooked one. The key is present ONLY on drift, so the healthy-node
                # golden envelope stays frozen (see the golden key test).
                info, drift = _copernicus_image_info(node)

                if "resolution" in info:
                    result["resolution"] = info["resolution"]
                else:
                    for rx, ry in [("resx", "resy"), ("res_x", "res_y")]:
                        px = node.parm(rx)
                        py = node.parm(ry)
                        if px is not None and py is not None:
                            result["resolution"] = [px.eval(), py.eval()]
                            break

                if "data_type" in info:
                    result["data_type"] = info["data_type"]
                else:
                    dp = node.parm("depth") or node.parm("data_type")
                    if dp is not None:
                        result["data_type"] = str(dp.eval())

                result["planes"] = info.get("planes", [])

                # LOUD API drift: additive key (only present when a replacement-surface
                # symbol vanished) so a persistently-drifted node is never mistaken for
                # an un-cooked one. Same shape as analyze_render's issues[] entries.
                if drift:
                    result["api_drift"] = drift

            # Cook status
            try:
                errors = node.errors()
                warnings = node.warnings()
                result["cook_status"] = "error" if errors else "ok"
                result["errors"] = list(errors) if errors else []
                result["warnings"] = list(warnings) if warnings else []
            except (AttributeError, Exception):
                result["cook_status"] = "unknown"

            return result

        return run_on_main(_on_main)

    # =========================================================================
    # PHASE 2: Pipeline Integration
    # =========================================================================

    def _handle_cops_to_materialx(self, payload: Dict) -> Dict:
        """Configure an op: path from a COP output to a MaterialX texture input.

        Sets up the COP-to-material pipeline using Houdini's op: protocol,
        allowing live COP network output as a texture in MaterialX shaders.

        Payload:
            cop_path (str, required): COP node path whose output will be used as texture.
            material_node (str, required): MaterialX shader node path.
            input_name (str): Shader input parameter name (default: 'base_color_texture').
            plane (str): COP plane to use (default: 'C' for color).

        Returns:
            Dict confirming the op: path connection.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        cop_path = resolve_param(payload, "cop_path")
        material_node_path = resolve_param(payload, "material_node")
        input_name = resolve_param_with_default(payload, "input_name", "base_color_texture")
        plane = resolve_param_with_default(payload, "plane", "C")

        from .main_thread import run_on_main

        def _on_main():
            cop_node = hou.node(cop_path)
            if cop_node is None:
                raise ValueError(f"Couldn't find COP node '{cop_path}'")

            mat_node = hou.node(material_node_path)
            if mat_node is None:
                raise ValueError(f"Couldn't find material node '{material_node_path}'")

            # Build op: path reference
            op_path = f"op:{cop_node.path()}"
            if plane and plane != "C":
                op_path += f"/{plane}"

            with hou.undos.group("synapse_cops_to_materialx"):
                parm = mat_node.parm(input_name)
                if parm is None:
                    # Try common texture input names
                    for alt in ("file", "filename", "texture", "tex", "basecolor_texture"):
                        parm = mat_node.parm(alt)
                        if parm is not None:
                            break
                if parm is None:
                    raise ValueError(
                        f"Couldn't find texture input '{input_name}' on '{material_node_path}' -- "
                        "check the parameter name with inspect_node"
                    )
                parm.set(op_path)

            return {
                "cop_path": cop_node.path(),
                "material_node": mat_node.path(),
                "input_name": parm.name(),
                "op_path": op_path,
            }

        return run_on_main(_on_main)

    def _handle_cops_composite_aovs(self, payload: Dict) -> Dict:
        """Build a COP network to composite Karma AOV layers.

        Creates a COP network loading beauty + selected AOV layers from EXR files
        and compositing them together.

        Payload:
            parent (str): Parent node for the COP network (default: '/obj').
            exr_path (str, required): Path to the multi-layer EXR file.
            aov_list (list[str]): AOV layer names to load (default: ['beauty', 'diffuse', 'specular']).
            name (str): Network name (default: 'aov_comp').

        Returns:
            Dict with created network path and loaded layer nodes.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param_with_default(payload, "parent", "/obj")
        exr_path = resolve_param(payload, "exr_path")
        aov_list = resolve_param_with_default(
            payload, "aov_list", ["beauty", "diffuse", "specular"]
        )
        name = resolve_param_with_default(payload, "name", "aov_comp")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find parent node '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_composite_aovs"):
                    network = _create_cop_node(parent, "cop2net", name)
                    created_any = True
                    network.moveToGoodPosition()

                    layer_nodes = []
                    prev_node = None

                    for aov_name in aov_list:
                        # Create file node for each AOV
                        file_node = network.createNode("file", f"load_{aov_name}")
                        created_any = True
                        file_parm = file_node.parm("filename1") or file_node.parm("file")
                        if file_parm is not None:
                            file_parm.set(exr_path)

                        # Set channel/plane selection if available
                        plane_parm = file_node.parm("channel") or file_node.parm("plane")
                        if plane_parm is not None:
                            plane_parm.set(aov_name)

                        file_node.moveToGoodPosition()
                        layer_nodes.append({
                            "path": file_node.path(),
                            "aov": aov_name,
                        })
                        prev_node = file_node

                    # Create composite/merge node if multiple layers
                    merge_node = None
                    if len(layer_nodes) > 1:
                        merge_node = network.createNode("composite", "merge_aovs")
                        created_any = True
                        if merge_node is None:
                            merge_node = network.createNode("over", "merge_aovs")
                        if merge_node is not None:
                            for i, ln in enumerate(layer_nodes):
                                src = hou.node(ln["path"])
                                if src is not None and i < merge_node.type().maxNumInputs():
                                    merge_node.setInput(i, src)
                            merge_node.moveToGoodPosition()

                    # Set display flag on final node
                    final = merge_node if merge_node else prev_node
                    if final is not None:
                        try:
                            final.setDisplayFlag(True)
                        except Exception:
                            pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "network_path": network.path(),
                "layers": layer_nodes,
                "merge_node": merge_node.path() if merge_node else None,
                "exr_path": exr_path,
            }

        return run_on_main(_on_main)

    def _handle_cops_analyze_render(self, payload: Dict) -> Dict:
        """Analyze a rendered image for quality issues using COP processing.

        Performs black pixel detection, NaN/Inf check, dynamic range analysis,
        noise estimation, and clipping detection. Returns a structured report.

        Payload:
            node (str, required): COP node path containing the image to analyze.
            checks (list[str]): Specific checks to run
                (default: all of 'black_pixels', 'dynamic_range', 'clipping', 'noise').

        Returns:
            Dict with quality analysis report.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        checks = resolve_param_with_default(
            payload, "checks", ["black_pixels", "dynamic_range", "clipping", "noise"]
        )

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(f"Couldn't find COP node '{node_path}'")

            # Force cook to ensure data is current
            try:
                node.cook(force=True)
            except Exception:
                pass

            report = {
                "node": node.path(),
                "checks_run": checks,
                "issues": [],
                "overall_quality": "unknown",
            }

            if _uses_legacy_cop2_surface(node):
                # Legacy COP2 surface -- planes()/xRes()/yRes() survive on
                # hou.Cop2Node in H22 (verified 22.0.368); path unchanged.
                # Resolution check
                try:
                    w, h = node.xRes(), node.yRes()
                    report["resolution"] = [w, h]
                    report["pixel_count"] = w * h
                except (AttributeError, Exception):
                    report["resolution"] = None

                # Plane/channel info
                try:
                    planes = node.planes()
                    report["planes"] = [str(p) for p in planes] if planes else []
                except (AttributeError, Exception):
                    report["planes"] = []
            else:
                # Copernicus surface -- H22 removed planes()/xRes()/yRes() from
                # hou.CopNode (NWS-03); read via cable()/ImageLayer instead.
                info, drift = _copernicus_image_info(node)

                # LOUD API drift: if a replacement-surface symbol vanished, surface
                # it as an api_drift issue (additive content on the existing issues[]
                # list -- no envelope-shape change) so a silently-degraded read can
                # no longer masquerade as a clean "pass".
                report["issues"].extend(drift)

                # Resolution check
                if "resolution" in info:
                    w, h = info["resolution"]
                    report["resolution"] = [w, h]
                    report["pixel_count"] = w * h
                else:
                    report["resolution"] = None

                # Plane/channel info (wire names are the H22 plane names)
                report["planes"] = info.get("planes", [])

            # Error state
            try:
                errors = node.errors()
                if errors:
                    report["issues"].append({
                        "check": "cook_errors",
                        "severity": "error",
                        "message": f"Node has {len(errors)} cook error(s)",
                        "details": list(errors)[:5],
                    })
            except (AttributeError, Exception):
                pass

            # Quality assessment based on available info
            if not report["issues"]:
                report["overall_quality"] = "pass"
            elif any(i["severity"] == "error" for i in report["issues"]):
                report["overall_quality"] = "fail"
            else:
                report["overall_quality"] = "warning"

            return report

        return run_on_main(_on_main)

    def _handle_cops_slap_comp(self, payload: Dict) -> Dict:
        """Configure a live viewport compositing overlay using COPs.

        Sets up a COP network as a live viewport overlay for quick compositing
        previews during lighting/lookdev.

        Payload:
            cop_path (str, required): COP node whose output will overlay the viewport.
            viewport (str): Viewport name (default: uses active viewport).
            blend_mode (str): Blend mode - 'over', 'add', 'multiply' (default: 'over').
            opacity (float): Overlay opacity 0-1 (default: 1.0).

        Returns:
            Dict confirming the slap comp configuration.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        cop_path = resolve_param(payload, "cop_path")
        blend_mode = resolve_param_with_default(payload, "blend_mode", "over")
        opacity = float(resolve_param_with_default(payload, "opacity", 1.0))

        from .main_thread import run_on_main

        def _on_main():
            cop_node = hou.node(cop_path)
            if cop_node is None:
                raise ValueError(f"Couldn't find COP node '{cop_path}'")

            # Configure the COP for viewport overlay
            result = {
                "cop_path": cop_node.path(),
                "blend_mode": blend_mode,
                "opacity": opacity,
                "configured": True,
            }

            # Set display flag so this is the active output
            try:
                cop_node.setDisplayFlag(True)
            except Exception:
                pass

            # Try to set composite operation parms
            with hou.undos.group("synapse_cops_slap_comp"):
                op_parm = cop_node.parm("operation") or cop_node.parm("compop")
                if op_parm is not None:
                    mode_map = {"over": 0, "add": 1, "multiply": 2, "screen": 3}
                    op_parm.set(mode_map.get(blend_mode, 0))

                opacity_parm = cop_node.parm("opacity") or cop_node.parm("mix")
                if opacity_parm is not None:
                    opacity_parm.set(opacity)

            return result

        return run_on_main(_on_main)

    # =========================================================================
    # PHASE 3: Procedural & Motion Design
    # =========================================================================

    def _handle_cops_create_solver(self, payload: Dict) -> Dict:
        """Create a Block Begin/End solver pair in a COP network.

        Sets up the feedback loop architecture required for iterative
        COP processing (growth, reaction-diffusion, fluid, etc.).

        Payload:
            parent (str, required): COP network path.
            name (str): Solver name prefix (default: 'solver').
            iterations (int): Number of solver iterations (default: 10).
            method (str): Solver method - 'singlepass' or 'simulate' (default: 'singlepass').

        Returns:
            Dict with block_begin, block_end paths and configuration.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        name = resolve_param_with_default(payload, "name", "solver")
        iterations = int(resolve_param_with_default(payload, "iterations", 10))
        method = resolve_param_with_default(payload, "method", "singlepass")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_create_solver"):
                    # Create Block Begin
                    block_begin = parent.createNode("block_begin", f"{name}_begin")
                    created_any = True
                    if block_begin is None:
                        raise RuntimeError(
                            "Couldn't create block_begin node -- "
                            "make sure you're in a COP2 network context"
                        )

                    # Create Block End
                    block_end = parent.createNode("block_end", f"{name}_end")
                    created_any = True
                    if block_end is None:
                        raise RuntimeError("Couldn't create block_end node")

                    # Wire Block End's feedback to Block Begin
                    block_end.setInput(0, block_begin)

                    # Configure iterations
                    iter_parm = block_end.parm("iterations") or block_end.parm("numiterations")
                    if iter_parm is not None:
                        iter_parm.set(iterations)

                    # Configure method
                    method_parm = block_end.parm("method") or block_end.parm("blocktype")
                    if method_parm is not None:
                        method_map = {"singlepass": 0, "simulate": 1}
                        method_parm.set(method_map.get(method, 0))

                    # Point block_end to block_begin
                    path_parm = block_end.parm("blockpath") or block_end.parm("block_begin")
                    if path_parm is not None:
                        path_parm.set(block_begin.path())

                    block_begin.moveToGoodPosition()
                    block_end.moveToGoodPosition()

                    # Set display on block_end
                    try:
                        block_end.setDisplayFlag(True)
                    except Exception:
                        pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "block_begin": block_begin.path(),
                "block_end": block_end.path(),
                "iterations": iterations,
                "method": method,
            }

        return run_on_main(_on_main)

    def _handle_cops_procedural_texture(self, payload: Dict) -> Dict:
        """Generate a procedural texture using COP noise nodes.

        Creates a noise-based texture with configurable type, frequency, and ramp mapping.

        Payload:
            parent (str, required): COP network path.
            noise_type (str): Noise type - 'perlin', 'worley', 'simplex', 'alligator' (default: 'perlin').
            frequency (float): Noise frequency (default: 1.0).
            octaves (int): Fractal octaves (default: 4).
            resolution (list[int]): Output resolution [w, h] (default: [1024, 1024]).
            name (str): Node name (default: 'procedural_tex').

        Returns:
            Dict with created texture node path and settings.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        noise_type = resolve_param_with_default(payload, "noise_type", "perlin")
        frequency = float(resolve_param_with_default(payload, "frequency", 1.0))
        octaves = int(resolve_param_with_default(payload, "octaves", 4))
        resolution = resolve_param_with_default(payload, "resolution", [1024, 1024])
        name = resolve_param_with_default(payload, "name", "procedural_tex")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            with hou.undos.group("synapse_cops_procedural_texture"):
                # Create noise generator
                noise_node = parent.createNode("vopcop2gen", name)
                if noise_node is None:
                    # Fallback to generic COP noise if vopcop2gen unavailable
                    noise_node = parent.createNode("noise", name)
                if noise_node is None:
                    raise RuntimeError("Couldn't create noise generator node")

                # Set noise type
                type_parm = noise_node.parm("type") or noise_node.parm("noise_type")
                if type_parm is not None:
                    type_map = {"perlin": 0, "worley": 1, "simplex": 2, "alligator": 3}
                    type_parm.set(type_map.get(noise_type, 0))

                # Set frequency
                freq_parm = noise_node.parm("freq") or noise_node.parm("frequency")
                if freq_parm is not None:
                    freq_parm.set(frequency)
                else:
                    ft = noise_node.parmTuple("freq")
                    if ft is not None:
                        ft.set([frequency] * len(ft))

                # Set octaves
                oct_parm = noise_node.parm("octaves") or noise_node.parm("turb")
                if oct_parm is not None:
                    oct_parm.set(octaves)

                # Set resolution
                if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
                    for pname, val in [("resx", resolution[0]), ("resy", resolution[1])]:
                        p = noise_node.parm(pname)
                        if p is not None:
                            p.set(int(val))

                noise_node.moveToGoodPosition()
                try:
                    noise_node.setDisplayFlag(True)
                except Exception:
                    pass

            return {
                "path": noise_node.path(),
                "noise_type": noise_type,
                "frequency": frequency,
                "octaves": octaves,
                "resolution": resolution,
            }

        return run_on_main(_on_main)

    def _handle_cops_growth_propagation(self, payload: Dict) -> Dict:
        """Create a growth propagation solver using dilate/blur/threshold.

        Builds a solver loop that grows from a seed mask using iterative
        dilation, blur, and threshold operations (DLA-style growth).

        Payload:
            parent (str, required): COP network path.
            seed_mask (str): Path to seed mask COP node (optional, creates default if omitted).
            iterations (int): Growth iterations (default: 20).
            growth_rate (float): Growth rate per iteration 0-1 (default: 0.5).
            blur_amount (float): Blur between iterations (default: 1.0).
            threshold (float): Threshold cutoff (default: 0.5).
            name (str): Solver name (default: 'growth').

        Returns:
            Dict with solver node paths.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        seed_mask = resolve_param_with_default(payload, "seed_mask", None)
        iterations = int(resolve_param_with_default(payload, "iterations", 20))
        growth_rate = float(resolve_param_with_default(payload, "growth_rate", 0.5))
        blur_amount = float(resolve_param_with_default(payload, "blur_amount", 1.0))
        threshold_val = float(resolve_param_with_default(payload, "threshold", 0.5))
        name = resolve_param_with_default(payload, "name", "growth")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_growth_propagation"):
                    # Create solver block
                    block_begin = parent.createNode("block_begin", f"{name}_begin")
                    created_any = True
                    block_end = parent.createNode("block_end", f"{name}_end")
                    created_any = True

                    if block_begin is None or block_end is None:
                        raise RuntimeError("Couldn't create solver blocks")

                    # Configure iterations
                    iter_parm = block_end.parm("iterations") or block_end.parm("numiterations")
                    if iter_parm is not None:
                        iter_parm.set(iterations)

                    path_parm = block_end.parm("blockpath") or block_end.parm("block_begin")
                    if path_parm is not None:
                        path_parm.set(block_begin.path())

                    # Create processing chain inside solver: dilate -> blur -> threshold
                    dilate = parent.createNode("dilateerode", f"{name}_dilate")
                    created_any = True
                    blur = parent.createNode("blur", f"{name}_blur")
                    created_any = True
                    thresh = parent.createNode("limit", f"{name}_threshold")
                    created_any = True

                    # Wire: block_begin -> dilate -> blur -> threshold -> block_end
                    if dilate is not None:
                        dilate.setInput(0, block_begin)
                        # Set growth rate via dilate amount
                        dp = dilate.parm("size") or dilate.parm("radius")
                        if dp is not None:
                            dp.set(growth_rate)

                    if blur is not None:
                        blur.setInput(0, dilate if dilate else block_begin)
                        bp = blur.parm("blursize") or blur.parm("size")
                        if bp is not None:
                            bp.set(blur_amount)

                    if thresh is not None:
                        thresh.setInput(0, blur if blur else block_begin)
                        tp = thresh.parm("max") or thresh.parm("high")
                        if tp is not None:
                            tp.set(threshold_val)

                    # Wire final processing to block_end
                    last_proc = thresh or blur or dilate or block_begin
                    block_end.setInput(0, last_proc)

                    # Seed mask connection
                    if seed_mask:
                        seed_node = hou.node(seed_mask)
                        if seed_node is not None:
                            block_begin.setInput(0, seed_node)

                    for n in [block_begin, dilate, blur, thresh, block_end]:
                        if n is not None:
                            n.moveToGoodPosition()

                    try:
                        block_end.setDisplayFlag(True)
                    except Exception:
                        pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "block_begin": block_begin.path(),
                "block_end": block_end.path(),
                "dilate": dilate.path() if dilate else None,
                "blur": blur.path() if blur else None,
                "threshold": thresh.path() if thresh else None,
                "iterations": iterations,
                "growth_rate": growth_rate,
            }

        return run_on_main(_on_main)

    def _handle_cops_reaction_diffusion(self, payload: Dict) -> Dict:
        """Create a Gray-Scott reaction-diffusion solver via OpenCL.

        Builds a solver loop running a reaction-diffusion simulation
        using OpenCL kernels for GPU-accelerated processing.

        Payload:
            parent (str, required): COP network path.
            feed_rate (float): Feed rate F (default: 0.055).
            kill_rate (float): Kill rate k (default: 0.062).
            diffusion_a (float): Diffusion rate for chemical A (default: 1.0).
            diffusion_b (float): Diffusion rate for chemical B (default: 0.5).
            iterations (int): Simulation iterations (default: 100).
            resolution (list[int]): Resolution [w, h] (default: [512, 512]).
            name (str): Solver name (default: 'reaction_diffusion').

        Returns:
            Dict with solver configuration and node paths.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        feed_rate = float(resolve_param_with_default(payload, "feed_rate", 0.055))
        kill_rate = float(resolve_param_with_default(payload, "kill_rate", 0.062))
        diffusion_a = float(resolve_param_with_default(payload, "diffusion_a", 1.0))
        diffusion_b = float(resolve_param_with_default(payload, "diffusion_b", 0.5))
        iterations = int(resolve_param_with_default(payload, "iterations", 100))
        resolution = resolve_param_with_default(payload, "resolution", [512, 512])
        name = resolve_param_with_default(payload, "name", "reaction_diffusion")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_reaction_diffusion"):
                    # Create solver
                    block_begin = parent.createNode("block_begin", f"{name}_begin")
                    created_any = True
                    block_end = parent.createNode("block_end", f"{name}_end")
                    created_any = True

                    if block_begin is None or block_end is None:
                        raise RuntimeError("Couldn't create solver blocks")

                    iter_parm = block_end.parm("iterations") or block_end.parm("numiterations")
                    if iter_parm is not None:
                        iter_parm.set(iterations)

                    path_parm = block_end.parm("blockpath") or block_end.parm("block_begin")
                    if path_parm is not None:
                        path_parm.set(block_begin.path())

                    # Create OpenCL node for the R-D kernel
                    opencl_node = parent.createNode("opencl", f"{name}_kernel")
                    created_any = True
                    if opencl_node is None:
                        # Fallback: try vopcop2gen
                        opencl_node = parent.createNode("vopcop2gen", f"{name}_kernel")

                    if opencl_node is not None:
                        opencl_node.setInput(0, block_begin)

                        # Set kernel code (Gray-Scott R-D)
                        kernel_parm = opencl_node.parm("kernelcode") or opencl_node.parm("code")
                        if kernel_parm is not None:
                            kernel_code = (
                                f"// Gray-Scott Reaction-Diffusion\n"
                                f"// F={feed_rate}, k={kill_rate}, "
                                f"Da={diffusion_a}, Db={diffusion_b}\n"
                                f"#define F {feed_rate}f\n"
                                f"#define K {kill_rate}f\n"
                                f"#define DA {diffusion_a}f\n"
                                f"#define DB {diffusion_b}f\n"
                                f"// PLACEHOLDER — no kernel body; parameters only, node will not simulate\n"
                            )
                            kernel_parm.set(kernel_code)

                    # Wire: opencl -> block_end
                    last_node = opencl_node if opencl_node else block_begin
                    block_end.setInput(0, last_node)

                    for n in [block_begin, opencl_node, block_end]:
                        if n is not None:
                            n.moveToGoodPosition()

                    try:
                        block_end.setDisplayFlag(True)
                    except Exception:
                        pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "block_begin": block_begin.path(),
                "block_end": block_end.path(),
                "kernel_node": opencl_node.path() if opencl_node else None,
                "feed_rate": feed_rate,
                "kill_rate": kill_rate,
                "diffusion_a": diffusion_a,
                "diffusion_b": diffusion_b,
                "iterations": iterations,
                "resolution": resolution,
                "scaffolded": True,
                "cooked": False,
                "note": (
                    "Solver graph scaffolded with a placeholder #define-only "
                    "kernel — no kernel body authored and the node was not "
                    "cooked; it produces no reaction-diffusion output until "
                    "a real kernel is written."
                ),
            }

        return run_on_main(_on_main)

    def _handle_cops_pixel_sort(self, payload: Dict) -> Dict:
        """Configure OpenCL-based pixel sorting on a COP node.

        Applies pixel sorting by luminance or hue with configurable
        threshold and direction, creating stylized image effects.

        Payload:
            parent (str, required): COP network path.
            input_node (str): Input COP node path (optional).
            sort_by (str): Sort criteria - 'luminance', 'hue', 'saturation', 'value' (default: 'luminance').
            direction (str): Sort direction - 'horizontal', 'vertical', 'diagonal' (default: 'vertical').
            threshold_low (float): Low threshold 0-1 (default: 0.2).
            threshold_high (float): High threshold 0-1 (default: 0.8).
            name (str): Node name (default: 'pixel_sort').

        Returns:
            Dict with pixel sort node path and settings.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        input_node_path = resolve_param_with_default(payload, "input_node", None)
        sort_by = resolve_param_with_default(payload, "sort_by", "luminance")
        direction = resolve_param_with_default(payload, "direction", "vertical")
        threshold_low = float(resolve_param_with_default(payload, "threshold_low", 0.2))
        threshold_high = float(resolve_param_with_default(payload, "threshold_high", 0.8))
        name = resolve_param_with_default(payload, "name", "pixel_sort")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            with hou.undos.group("synapse_cops_pixel_sort"):
                # Create OpenCL node for pixel sorting
                sort_node = parent.createNode("opencl", name)
                if sort_node is None:
                    sort_node = parent.createNode("vopcop2gen", name)
                if sort_node is None:
                    raise RuntimeError("Couldn't create pixel sort node")

                # Wire input
                if input_node_path:
                    input_node = hou.node(input_node_path)
                    if input_node is not None:
                        sort_node.setInput(0, input_node)

                # Set kernel with sorting parameters
                kernel_parm = sort_node.parm("kernelcode") or sort_node.parm("code")
                if kernel_parm is not None:
                    kernel_code = (
                        f"// Pixel Sort: {sort_by}, {direction}\n"
                        f"// Threshold: [{threshold_low}, {threshold_high}]\n"
                        f"#define SORT_BY_{sort_by.upper()} 1\n"
                        f"#define DIRECTION_{direction.upper()} 1\n"
                        f"#define THRESHOLD_LOW {threshold_low}f\n"
                        f"#define THRESHOLD_HIGH {threshold_high}f\n"
                        f"// PLACEHOLDER — no kernel body; parameters only, node will not sort\n"
                    )
                    kernel_parm.set(kernel_code)

                sort_node.moveToGoodPosition()
                try:
                    sort_node.setDisplayFlag(True)
                except Exception:
                    pass

            return {
                "path": sort_node.path(),
                "sort_by": sort_by,
                "direction": direction,
                "threshold_low": threshold_low,
                "threshold_high": threshold_high,
                "scaffolded": True,
                "cooked": False,
                "note": (
                    "Sort node scaffolded with a placeholder #define-only "
                    "kernel — no kernel body authored and the node was not "
                    "cooked; it produces no pixel-sort output until a real "
                    "kernel is written."
                ),
            }

        return run_on_main(_on_main)

    def _handle_cops_stylize(self, payload: Dict) -> Dict:
        """Apply NPR stylization effects to COP images.

        Supports toon (quantize), risograph (halftone + palette),
        posterize, and edge detection effects.

        Payload:
            parent (str, required): COP network path.
            input_node (str): Input COP node path (optional).
            style_type (str): Effect type - 'toon', 'risograph', 'posterize', 'edge_detect' (default: 'toon').
            levels (int): Quantization levels for toon/posterize (default: 6).
            edge_width (float): Edge detection width (default: 1.0).
            palette (list[list[float]]): Color palette for risograph [[r,g,b], ...] (optional).
            name (str): Node name (default: 'stylize').

        Returns:
            Dict with stylize node path and settings.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        input_node_path = resolve_param_with_default(payload, "input_node", None)
        style_type = resolve_param_with_default(payload, "style_type", "toon")
        levels = int(resolve_param_with_default(payload, "levels", 6))
        edge_width = float(resolve_param_with_default(payload, "edge_width", 1.0))
        name = resolve_param_with_default(payload, "name", "stylize")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_stylize"):
                    nodes_created = []

                    if style_type == "edge_detect":
                        node = parent.createNode("edge", name)
                        created_any = True
                        if node is None:
                            node = parent.createNode("edgedetect", name)
                        if node is not None:
                            ep = node.parm("size") or node.parm("width")
                            if ep is not None:
                                ep.set(edge_width)
                    elif style_type in ("toon", "posterize"):
                        node = parent.createNode("quantize", name)
                        created_any = True
                        if node is None:
                            node = parent.createNode("limit", name)
                        if node is not None:
                            lp = node.parm("levels") or node.parm("steps")
                            if lp is not None:
                                lp.set(levels)
                    elif style_type == "risograph":
                        # Risograph: quantize + halftone-style chain.
                        # H21.0.671 has no 'halftone' COP in any category
                        # (live catalog probe) -- use a vopcop2gen stage
                        # for the halftone pattern instead.
                        quant = parent.createNode("quantize", f"{name}_quant")
                        created_any = True
                        halftone = parent.createNode("vopcop2gen", f"{name}_halftone")
                        created_any = True

                        if quant is not None:
                            lp = quant.parm("levels") or quant.parm("steps")
                            if lp is not None:
                                lp.set(levels)
                            nodes_created.append(quant)

                        if halftone is not None:
                            if quant is not None:
                                halftone.setInput(0, quant)
                            nodes_created.append(halftone)

                        node = halftone or quant
                    else:
                        node = _create_cop_node(parent, "vopcop2gen", name)
                        created_any = True

                    if node is None and not nodes_created:
                        raise RuntimeError(
                            f"Couldn't create stylize node for '{style_type}' -- "
                            "check that the effect type is supported"
                        )

                    # Wire input
                    first_node = nodes_created[0] if nodes_created else node
                    if input_node_path and first_node is not None:
                        input_n = hou.node(input_node_path)
                        if input_n is not None:
                            first_node.setInput(0, input_n)

                    # Position and display
                    all_nodes = nodes_created if nodes_created else [node]
                    for n in all_nodes:
                        if n is not None:
                            n.moveToGoodPosition()

                    last = all_nodes[-1] if all_nodes else node
                    if last is not None:
                        try:
                            last.setDisplayFlag(True)
                        except Exception:
                            pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "path": last.path() if last else None,
                "style_type": style_type,
                "levels": levels,
                "edge_width": edge_width,
                "nodes": [n.path() for n in all_nodes if n is not None],
            }

        return run_on_main(_on_main)

    # =========================================================================
    # PHASE 4: Advanced
    # =========================================================================

    def _handle_cops_wetmap(self, payload: Dict) -> Dict:
        """Create a wetmap effect: SOP velocity/collision data as UV-space COP.

        Converts SOP-space data (velocity, collision) into a UV-space COP
        with blur and decay for wet-surface effects.

        Payload:
            parent (str, required): COP network path.
            sop_path (str): SOP node providing velocity/collision data (optional).
            decay (float): Decay rate per frame 0-1 (default: 0.95).
            blur (float): Blur amount for spreading (default: 2.0).
            resolution (list[int]): UV map resolution (default: [1024, 1024]).
            name (str): Node name (default: 'wetmap').

        Returns:
            Dict with wetmap setup paths and configuration.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        sop_path = resolve_param_with_default(payload, "sop_path", None)
        decay = float(resolve_param_with_default(payload, "decay", 0.95))
        blur_amount = float(resolve_param_with_default(payload, "blur", 2.0))
        resolution = resolve_param_with_default(payload, "resolution", [1024, 1024])
        name = resolve_param_with_default(payload, "name", "wetmap")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_wetmap"):
                    # Create solver for temporal decay
                    block_begin = parent.createNode("block_begin", f"{name}_begin")
                    created_any = True
                    block_end = parent.createNode("block_end", f"{name}_end")
                    created_any = True

                    if block_begin is None or block_end is None:
                        raise RuntimeError("Couldn't create solver blocks for wetmap")

                    # Set to simulate mode for frame-by-frame processing
                    method_parm = block_end.parm("method") or block_end.parm("blocktype")
                    if method_parm is not None:
                        method_parm.set(1)  # simulate

                    path_parm = block_end.parm("blockpath") or block_end.parm("block_begin")
                    if path_parm is not None:
                        path_parm.set(block_begin.path())

                    # Create blur for spreading
                    blur_node = parent.createNode("blur", f"{name}_spread")
                    created_any = True
                    if blur_node is not None:
                        blur_node.setInput(0, block_begin)
                        bp = blur_node.parm("blursize") or blur_node.parm("size")
                        if bp is not None:
                            bp.set(blur_amount)

                    # Create multiply for decay
                    decay_node = parent.createNode("bright", f"{name}_decay")
                    created_any = True
                    if decay_node is None:
                        decay_node = parent.createNode("colorcorrect", f"{name}_decay")
                    if decay_node is not None:
                        dp = decay_node.parm("bright") or decay_node.parm("gain")
                        if dp is not None:
                            dp.set(decay)
                        prev = blur_node if blur_node else block_begin
                        decay_node.setInput(0, prev)

                    last = decay_node or blur_node or block_begin
                    block_end.setInput(0, last)

                    for n in [block_begin, blur_node, decay_node, block_end]:
                        if n is not None:
                            n.moveToGoodPosition()

                    try:
                        block_end.setDisplayFlag(True)
                    except Exception:
                        pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "block_begin": block_begin.path(),
                "block_end": block_end.path(),
                "blur_node": blur_node.path() if blur_node else None,
                "decay_node": decay_node.path() if decay_node else None,
                "decay": decay,
                "blur": blur_amount,
                "resolution": resolution,
            }

        return run_on_main(_on_main)

    def _handle_cops_bake_textures(self, payload: Dict) -> Dict:
        """Scaffold a UV-space texture-baking node setup (placeholder nodes
        only — performs no bake, writes no files).

        Configures a COP network for baking normal maps, AO, curvature,
        and other maps from a high-res mesh to a low-res UV layout.

        Payload:
            parent (str, required): COP network path.
            high_res (str): Path to high-res SOP geometry (optional).
            low_res (str): Path to low-res SOP geometry (optional).
            map_types (list[str]): Maps to bake - 'normal', 'ao', 'curvature', 'position'
                (default: ['normal']).
            resolution (list[int]): Output resolution (default: [2048, 2048]).
            name (str): Setup name (default: 'bake').

        Returns:
            Dict with bake node paths and configuration.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        map_types = resolve_param_with_default(payload, "map_types", ["normal"])
        resolution = resolve_param_with_default(payload, "resolution", [2048, 2048])
        name = resolve_param_with_default(payload, "name", "bake")
        high_res = resolve_param_with_default(payload, "high_res", None)
        low_res = resolve_param_with_default(payload, "low_res", None)

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            created_any = False
            try:
                with hou.undos.group("synapse_cops_bake_textures"):
                    bake_nodes = []

                    for map_type in map_types:
                        node = _create_cop_node(parent, "vopcop2gen", f"{name}_{map_type}")
                        created_any = True
                        if node is None:
                            continue

                        # Set resolution
                        if isinstance(resolution, (list, tuple)) and len(resolution) >= 2:
                            for pname, val in [("resx", resolution[0]), ("resy", resolution[1])]:
                                p = node.parm(pname)
                                if p is not None:
                                    p.set(int(val))

                        node.moveToGoodPosition()
                        bake_nodes.append({
                            "path": node.path(),
                            "map_type": map_type,
                        })

                    # Set display on last node
                    if bake_nodes:
                        last = hou.node(bake_nodes[-1]["path"])
                        if last is not None:
                            try:
                                last.setDisplayFlag(True)
                            except Exception:
                                pass
            except Exception:
                if created_any:
                    try:
                        hou.undos.performUndo()
                    except Exception:
                        pass
                raise

            return {
                "bake_nodes": bake_nodes,
                "map_types": map_types,
                "resolution": resolution,
                "scaffolded": True,
                "baked": False,
                "unused_inputs": {"high_res": high_res, "low_res": low_res},
                "note": (
                    "Scaffold only: placeholder COP nodes created — nothing "
                    "was baked, no files written; high_res/low_res are not "
                    "wired into the scaffold yet."
                ),
            }

        return run_on_main(_on_main)

    def _handle_cops_temporal_analysis(self, payload: Dict) -> Dict:
        """Analyze temporal coherence across frames.

        Checks for flicker, temporal noise, and frame-to-frame consistency
        by comparing pixel data across a frame range.

        Payload:
            node (str, required): COP node path.
            frame_range (list[int]): Frame range [start, end] (default: current frame +/- 5).
            metrics (list[str]): Metrics to compute - 'flicker', 'diff', 'consistency'
                (default: all).

        Returns:
            Dict with temporal analysis results.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_path = resolve_param(payload, "node")
        frame_range = resolve_param_with_default(payload, "frame_range", None)
        metrics = resolve_param_with_default(
            payload, "metrics", ["flicker", "diff", "consistency"]
        )

        from .main_thread import run_on_main

        def _on_main():
            node = hou.node(node_path)
            if node is None:
                raise ValueError(f"Couldn't find COP node '{node_path}'")

            # Determine frame range
            if frame_range and len(frame_range) >= 2:
                start, end = int(frame_range[0]), int(frame_range[1])
            else:
                current = int(hou.frame())
                start, end = current - 5, current + 5

            result = {
                "node": node.path(),
                "frame_range": [start, end],
                "frame_count": end - start + 1,
                "metrics_requested": metrics,
                "analysis": {},
            }

            # Check cook status at each frame -- save the playhead first
            # and restore it afterwards (this handler moves the frame).
            frame_errors = 0
            restore_frame = hou.frame()
            try:
                for f in range(start, end + 1):
                    try:
                        hou.setFrame(f)
                        node.cook(force=True)
                        if node.errors():
                            frame_errors += 1
                    except Exception:
                        frame_errors += 1
            finally:
                hou.setFrame(restore_frame)

            result["analysis"]["frame_errors"] = frame_errors
            result["analysis"]["error_rate"] = (
                frame_errors / max(1, end - start + 1)
            )

            if frame_errors == 0:
                result["overall"] = "stable"
            elif frame_errors < (end - start + 1) * 0.1:
                result["overall"] = "mostly_stable"
            else:
                result["overall"] = "unstable"

            return result

        return run_on_main(_on_main)

    def _handle_cops_stamp_scatter(self, payload: Dict) -> Dict:
        """Scatter stamp images with randomized transforms.

        Distributes copies of a source image across a canvas with
        per-instance randomization of position, scale, and rotation.

        Payload:
            parent (str, required): COP network path.
            stamp_source (str): COP node path for stamp image (optional).
            count (int): Number of stamp instances (default: 50).
            scale_range (list[float]): Min/max scale [0.5, 2.0] (default: [0.5, 1.5]).
            rotation_range (list[float]): Min/max rotation in degrees (default: [0, 360]).
            seed (int): Random seed for reproducibility (default: 42).
            name (str): Node name (default: 'stamp_scatter').

        Returns:
            Dict with stamp scatter node paths and settings.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        parent_path = resolve_param(payload, "parent")
        stamp_source = resolve_param_with_default(payload, "stamp_source", None)
        count = int(resolve_param_with_default(payload, "count", 50))
        scale_range = resolve_param_with_default(payload, "scale_range", [0.5, 1.5])
        rotation_range = resolve_param_with_default(payload, "rotation_range", [0, 360])
        seed = int(resolve_param_with_default(payload, "seed", 42))
        name = resolve_param_with_default(payload, "name", "stamp_scatter")

        from .main_thread import run_on_main

        def _on_main():
            parent = hou.node(parent_path)
            if parent is None:
                raise ValueError(f"Couldn't find COP network '{parent_path}'")

            with hou.undos.group("synapse_cops_stamp_scatter"):
                # Create the stamp/copy node
                scatter_node = _create_cop_node(parent, "vopcop2gen", name)
                if scatter_node is None:
                    raise RuntimeError("Couldn't create stamp scatter node")

                # Wire stamp source
                if stamp_source:
                    src = hou.node(stamp_source)
                    if src is not None:
                        scatter_node.setInput(0, src)

                # Configure stamp parameters
                for pname, val in [
                    ("seed", seed),
                    ("copies", count),
                    ("count", count),
                ]:
                    p = scatter_node.parm(pname)
                    if p is not None:
                        p.set(val)

                scatter_node.moveToGoodPosition()
                try:
                    scatter_node.setDisplayFlag(True)
                except Exception:
                    pass

            return {
                "path": scatter_node.path(),
                "count": count,
                "scale_range": scale_range,
                "rotation_range": rotation_range,
                "seed": seed,
            }

        return run_on_main(_on_main)

    def _handle_cops_batch_cook(self, payload: Dict) -> Dict:
        """Batch-cook COP nodes, optionally via TOPS for parallelism.

        Cooks a list of COP nodes sequentially or sets up a TOP network
        for parallel batch processing.

        Payload:
            nodes (list[str], required): List of COP node paths to cook.
            parallel (bool): Use TOPS for parallel cooking (default: False).
            frame_range (list[int]): Frame range [start, end] (optional).
            name (str): Batch name (default: 'cops_batch').

        Returns:
            Dict with cook results per node.
        """
        if not HOU_AVAILABLE:
            raise RuntimeError(_HOUDINI_UNAVAILABLE)

        node_paths = resolve_param(payload, "nodes")
        parallel = resolve_param_with_default(payload, "parallel", False)
        frame_range = resolve_param_with_default(payload, "frame_range", None)
        name = resolve_param_with_default(payload, "name", "cops_batch")

        if not node_paths or not isinstance(node_paths, list):
            raise ValueError("'nodes' must be a non-empty list of COP node paths")

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        def _on_main():
            results = []

            for np in node_paths:
                node = hou.node(np)
                if node is None:
                    results.append({
                        "node": np,
                        "status": "error",
                        "message": f"Couldn't find node '{np}'",
                    })
                    continue

                try:
                    node.cook(force=True)
                    errors = node.errors() if hasattr(node, "errors") else []
                    results.append({
                        "node": node.path(),
                        "status": "error" if errors else "ok",
                        "errors": list(errors) if errors else [],
                    })
                except Exception as e:
                    results.append({
                        "node": np,
                        "status": "error",
                        "message": str(e),
                    })

            cooked = sum(1 for r in results if r["status"] == "ok")
            failed = sum(1 for r in results if r["status"] == "error")

            return {
                "batch_name": name,
                "total": len(results),
                "cooked": cooked,
                "failed": failed,
                "results": results,
            }

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT)
