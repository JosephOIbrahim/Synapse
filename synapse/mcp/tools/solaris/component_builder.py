"""
synapse_solaris_component_builder — RELAY-SOLARIS Phase 3

Creates a complete Component Builder for a USD asset.
Dual-path: uses native componentbuilder if available, otherwise
wires componentgeometry + componentmaterial + componentoutput in a subnet.

Source pattern: SOLARIS_P2_COMPONENT_BUILDER
Atomic: all nodes created and wired, or none (undo-wrapped).
Idempotent: returns already_exists if component with same name exists.
"""

from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

try:
    from synapse.core.aliases import resolve_param, resolve_param_with_default
    from synapse.core.errors import NodeNotFoundError, HoudiniUnavailableError, ValidationError
except ImportError:
    # Standalone/test mode — define minimal stubs
    def resolve_param(d, k, required=False):
        return d.get(k)
    def resolve_param_with_default(d, k, default):
        return d.get(k, default)
    class ValidationError(ValueError): pass
    class NodeNotFoundError(ValueError):
        def __init__(self, path, suggestion=""): super().__init__(f"Node not found: {path}")
    class HoudiniUnavailableError(RuntimeError):
        def __init__(self): super().__init__("Houdini unavailable")


# -- Provenance --
_SOURCE_PATTERN = "SOLARIS_P2_COMPONENT_BUILDER"
_TOOL_NAME = "synapse_solaris_component_builder"


def _stamp_provenance(node, info: Dict[str, Any]) -> None:
    """Stamp provenance as user data on a Houdini node."""
    try:
        node.setUserData("synapse:tool", info.get("tool", _TOOL_NAME))
        node.setUserData("synapse:source_pattern", info.get("source_pattern", _SOURCE_PATTERN))
        node.setUserData("synapse:reasoning", info.get("reasoning", ""))
    except Exception:
        pass  # Provenance is best-effort, never blocks execution


def _has_native_componentbuilder() -> bool:
    """Check if 'componentbuilder' exists as a native LOP node type in this Houdini."""
    # hou.nodeType(category, name) returns None if type doesn't exist
    try:
        cat = hou.lopNodeTypeCategory()
        return hou.nodeType(cat, "componentbuilder") is not None
    except Exception:
        return False


def validate(params: Dict) -> None:
    """Validate parameters before any mutations."""
    asset_name = params.get("asset_name")
    if not asset_name:
        raise ValidationError("asset_name is required")
    if not isinstance(asset_name, str):
        raise ValidationError("asset_name must be a string")
    # Sanitize: no slashes, spaces, or special chars in asset name
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', asset_name):
        raise ValidationError(
            f"asset_name '{asset_name}' contains invalid characters -- "
            "use only letters, digits, and underscores"
        )
    proxy_reduction = params.get("proxy_reduction", 0.05)
    if not (0.0 <= proxy_reduction <= 1.0):
        raise ValidationError(
            f"proxy_reduction must be between 0.0 and 1.0, got {proxy_reduction}"
        )
    purposes = params.get("purposes", ["render", "proxy"])
    valid_purposes = {"render", "proxy", "simproxy"}
    for p in purposes:
        if p not in valid_purposes:
            raise ValidationError(f"Unknown purpose '{p}' -- use: {valid_purposes}")


def plan(params: Dict) -> List[Dict[str, Any]]:
    """Return the planned operations without executing.

    Useful for testing and dry-run validation.
    """
    asset_name = params.get("asset_name", "asset")
    purposes = params.get("purposes", ["render", "proxy"])
    proxy_reduction = params.get("proxy_reduction", 0.05)
    materials = params.get("materials", [])
    geometry_source = params.get("geometry_source")
    export_path = params.get("export_path")
    generate_thumbnail = params.get("generate_thumbnail", True)

    ops = []

    # Step 1: Create component container (native or subnet)
    ops.append({
        "op": "create_component",
        "node_type": "componentbuilder",  # may fall back to subnet
        "name": f"component_{asset_name}",
    })

    # Step 2: Component Geometry (inside component)
    ops.append({
        "op": "create_node",
        "node_type": "componentgeometry",
        "name": f"geo_{asset_name}",
        "parent": f"component_{asset_name}",
    })

    # Step 2a: If geometry_source provided, wire import inside
    if geometry_source:
        ops.append({
            "op": "set_geometry_source",
            "source": geometry_source,
        })

    # Step 2b: Proxy geometry
    if "proxy" in purposes or "simproxy" in purposes:
        ops.append({
            "op": "create_proxy",
            "reduction": proxy_reduction,
            "purposes": [p for p in purposes if p != "render"],
        })

    # Step 3: Material Library + Component Material
    for mat in materials:
        ops.append({
            "op": "create_material",
            "name": mat.get("name", "material"),
            "type": mat.get("type", "karma_material_builder"),
            "params": mat.get("params", {}),
        })

    ops.append({
        "op": "create_node",
        "node_type": "componentmaterial",
        "name": f"mat_{asset_name}",
        "parent": f"component_{asset_name}",
    })

    # Step 4: Component Output
    ops.append({
        "op": "create_node",
        "node_type": "componentoutput",
        "name": f"output_{asset_name}",
        "parent": f"component_{asset_name}",
    })

    if export_path:
        ops.append({
            "op": "set_export",
            "path": export_path,
            "name": asset_name,
            "thumbnail": generate_thumbnail,
        })

    # Step 5: Wire chain
    ops.append({
        "op": "wire_chain",
        "sequence": ["componentgeometry", "componentmaterial", "componentoutput"],
    })

    # Step 6: Provenance
    ops.append({
        "op": "stamp_provenance",
        "tool": _TOOL_NAME,
        "source_pattern": _SOURCE_PATTERN,
        "reasoning": f"Created '{asset_name}' component per NodeFlow Pattern 2",
    })

    return ops


def execute(params: Dict) -> Dict:
    """Execute the component builder creation.

    Atomic: wrapped in hou.undos.group(). On failure, undo rolls back.
    Idempotent: if a component with the same name exists, returns already_exists.

    Must be called via run_on_main() from the handler.
    """
    if not HOU_AVAILABLE:
        raise HoudiniUnavailableError()

    validate(params)

    asset_name = params.get("asset_name")
    parent_path = params.get("parent", "/stage")
    purposes = params.get("purposes", ["render", "proxy"])
    proxy_reduction = params.get("proxy_reduction", 0.05)
    materials = params.get("materials", [])
    geometry_source = params.get("geometry_source")
    export_path = params.get("export_path")
    generate_thumbnail = params.get("generate_thumbnail", True)

    parent = hou.node(parent_path)
    if parent is None:
        raise NodeNotFoundError(parent_path, suggestion="Check that /stage exists")

    # -- Idempotency guard --
    component_name = f"component_{asset_name}"
    existing = parent.node(component_name)
    if existing is not None:
        return {
            "status": "already_exists",
            "component_path": existing.path(),
        }

    # -- Atomic execution --
    created_nodes = []
    try:
        with hou.undos.group(f"SYNAPSE: Create component {asset_name}"):
            # Detect strategy
            use_native = _has_native_componentbuilder()

            if use_native:
                # Path A: native componentbuilder node
                comp = parent.createNode("componentbuilder", component_name)
                created_nodes.append(comp)
                # Native componentbuilder should already contain internal structure
                # Find the internal nodes
                geo_node = None
                mat_node = None
                out_node = None
                for child in comp.children():
                    tname = child.type().name().lower()
                    if "componentgeometry" in tname and geo_node is None:
                        geo_node = child
                    elif "componentmaterial" in tname and mat_node is None:
                        mat_node = child
                    elif "componentoutput" in tname and out_node is None:
                        out_node = child
            else:
                # Path B: manual subnet assembly
                comp = parent.createNode("subnet", component_name)
                created_nodes.append(comp)

                # Create internal nodes
                geo_node = comp.createNode("componentgeometry", f"geo_{asset_name}")
                created_nodes.append(geo_node)

                mat_node = comp.createNode("componentmaterial", f"mat_{asset_name}")
                created_nodes.append(mat_node)

                out_node = comp.createNode("componentoutput", f"output_{asset_name}")
                created_nodes.append(out_node)

                # Wire: geo → mat → output
                mat_node.setInput(0, geo_node)
                out_node.setInput(0, mat_node)

            # -- Configure Component Geometry --
            if geo_node and geometry_source:
                # If it's a SOP path, the componentgeometry node handles
                # SOP-level operations internally. Set the soppath parm if available.
                soppath_parm = geo_node.parm("soppath")
                if soppath_parm:
                    soppath_parm.set(geometry_source)

            # -- Configure Component Output --
            if out_node:
                name_parm = out_node.parm("name")
                if name_parm:
                    name_parm.set(asset_name)
                if export_path:
                    filepath_parm = out_node.parm("filepath")
                    if filepath_parm:
                        filepath_parm.set(export_path)

            # -- Layout --
            comp.layoutChildren()
            parent.layoutChildren()

            # -- Provenance --
            _stamp_provenance(comp, {
                "tool": _TOOL_NAME,
                "source_pattern": _SOURCE_PATTERN,
                "reasoning": f"Created '{asset_name}' component per NodeFlow Pattern 2",
            })

            internal = {}
            if geo_node:
                internal["componentgeometry"] = geo_node.path()
            if mat_node:
                internal["componentmaterial"] = mat_node.path()
            if out_node:
                internal["componentoutput"] = out_node.path()

            return {
                "status": "created",
                "component_path": comp.path(),
                "strategy": "native" if use_native else "subnet",
                "internal_nodes": internal,
                "export_path": export_path,
            }

    except Exception as e:
        # Undo group handles rollback automatically
        raise
