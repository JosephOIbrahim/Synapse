"""
synapse_solaris_import_megascans — RELAY-SOLARIS Phase 3

Full Megascans/Fab .usdc import pipeline inside a Component Builder.
SOP pipeline: USD Import (unpack) → Transform (0.01) → Match Size → PolyReduce
Material trick: Reference LOP with /materials/* wildcard.

Source pattern: SOLARIS_P6_MEGASCANS_IMPORT
Atomic: undo-wrapped. Idempotent: checks for existing component by name.
"""

from typing import Any, Dict, List, Optional

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None
    HOU_AVAILABLE = False

try:
    from synapse.core.errors import NodeNotFoundError, HoudiniUnavailableError, ValidationError
except ImportError:
    class ValidationError(ValueError): pass
    class NodeNotFoundError(ValueError):
        def __init__(self, path, suggestion=""): super().__init__(f"Node not found: {path}")
    class HoudiniUnavailableError(RuntimeError):
        def __init__(self): super().__init__("Houdini unavailable")


_SOURCE_PATTERN = "SOLARIS_P6_MEGASCANS_IMPORT"
_TOOL_NAME = "synapse_solaris_import_megascans"


def _stamp_provenance(node, info: Dict[str, Any]) -> None:
    """Stamp provenance as user data on a Houdini node."""
    try:
        node.setUserData("synapse:tool", info.get("tool", _TOOL_NAME))
        node.setUserData("synapse:source_pattern", info.get("source_pattern", _SOURCE_PATTERN))
        node.setUserData("synapse:reasoning", info.get("reasoning", ""))
    except Exception:
        pass


def validate(params: Dict) -> None:
    """Validate parameters before any mutations."""
    usdc_path = params.get("usdc_path")
    if not usdc_path:
        raise ValidationError("usdc_path is required")
    asset_name = params.get("asset_name")
    if not asset_name:
        raise ValidationError("asset_name is required")
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', asset_name):
        raise ValidationError(
            f"asset_name '{asset_name}' contains invalid characters -- "
            "use only letters, digits, and underscores"
        )
    scale = params.get("scale_factor", 0.01)
    if scale <= 0:
        raise ValidationError(f"scale_factor must be positive, got {scale}")
    proxy = params.get("proxy_reduction", 0.05)
    if not (0.0 <= proxy <= 1.0):
        raise ValidationError(f"proxy_reduction must be 0.0-1.0, got {proxy}")


def plan(params: Dict) -> List[Dict[str, Any]]:
    """Return planned operations for testing/dry-run."""
    asset_name = params.get("asset_name", "megascan_asset")
    usdc_path = params.get("usdc_path", "")
    scale_factor = params.get("scale_factor", 0.01)
    ground_asset = params.get("ground_asset", True)
    rotation_correction = params.get("rotation_correction")
    proxy_reduction = params.get("proxy_reduction", 0.05)
    import_materials = params.get("import_materials", True)
    export_path = params.get("export_path")

    ops = []

    # Component Builder container
    ops.append({
        "op": "create_component",
        "name": f"component_{asset_name}",
    })

    # SOP pipeline inside Component Geometry
    ops.append({"op": "create_node", "node_type": "componentgeometry", "name": f"geo_{asset_name}"})

    # Inside SOPs: import → scale → matchsize → polyreduce → output
    sop_chain = [
        {"op": "sop_create", "node_type": "usdimport", "params": {"filepath": usdc_path, "unpack_to_polygons": True}},
        {"op": "sop_create", "node_type": "xform", "params": {"uniform_scale": scale_factor}},
    ]
    if ground_asset:
        sop_chain.append({"op": "sop_create", "node_type": "matchsize", "params": {"justify_y": "min"}})
    if rotation_correction:
        sop_chain.append({"op": "sop_create", "node_type": "xform", "params": {"rotation": rotation_correction}})
    sop_chain.append({"op": "sop_create", "node_type": "polyreduce", "params": {"percentage": proxy_reduction}})
    sop_chain.append({"op": "sop_create", "node_type": "output", "params": {}})
    ops.extend(sop_chain)

    # Material import trick
    if import_materials:
        ops.append({
            "op": "create_reference_lop",
            "filepath": usdc_path,
            "primpath": "/materials/*",
            "destpath": "asset/mtl/",
        })

    ops.append({"op": "create_node", "node_type": "componentmaterial"})
    ops.append({"op": "create_node", "node_type": "componentoutput", "params": {"name": asset_name}})

    ops.append({"op": "wire_chain", "sequence": [
        "usdimport", "xform", "matchsize", "polyreduce", "output",
    ]})

    ops.append({
        "op": "stamp_provenance",
        "tool": _TOOL_NAME,
        "source_pattern": _SOURCE_PATTERN,
    })

    return ops


def execute(params: Dict) -> Dict:
    """Execute the Megascans import pipeline.

    Creates a Component Builder with the SOP import chain and
    material Reference LOP inside.
    """
    if not HOU_AVAILABLE:
        raise HoudiniUnavailableError()

    validate(params)

    asset_name = params["asset_name"]
    usdc_path = params["usdc_path"]
    parent_path = params.get("parent", "/stage")
    scale_factor = params.get("scale_factor", 0.01)
    ground_asset = params.get("ground_asset", True)
    rotation_correction = params.get("rotation_correction")
    proxy_reduction = params.get("proxy_reduction", 0.05)
    import_materials = params.get("import_materials", True)
    export_path = params.get("export_path")

    parent = hou.node(parent_path)
    if parent is None:
        raise NodeNotFoundError(parent_path, suggestion="Check that /stage exists")

    # -- Idempotency guard --
    component_name = f"component_{asset_name}"
    existing = parent.node(component_name)
    if existing is not None:
        return {"status": "already_exists", "component_path": existing.path()}

    # -- Atomic execution --
    try:
        with hou.undos.group(f"SYNAPSE: Import Megascans {asset_name}"):
            # Create Component Builder subnet
            comp = parent.createNode("subnet", component_name)

            # Component Geometry
            geo_node = comp.createNode("componentgeometry", f"geo_{asset_name}")

            # Build SOP chain inside Component Geometry
            # componentgeometry contains a SOP network — access it
            sop_nodes = []

            # USD Import
            usd_imp = geo_node.createNode("usdimport", "import_usdc")
            filepath_parm = usd_imp.parm("filepath")
            if filepath_parm:
                filepath_parm.set(usdc_path)
            # unpack to polygons — parm name: "unpacktopolygons" or similar
            unpack_parm = usd_imp.parm("unpacktopolygons")
            if unpack_parm:
                unpack_parm.set(1)
            sop_nodes.append(usd_imp)

            # Transform (scale 0.01)
            xform_scale = geo_node.createNode("xform", "scale_to_houdini")
            scale_parm = xform_scale.parm("scale")
            if scale_parm:
                scale_parm.set(scale_factor)
            else:
                # Try uniform scale
                for pname in ("uniform_scale", "uniformscale"):
                    p = xform_scale.parm(pname)
                    if p:
                        p.set(scale_factor)
                        break
            xform_scale.setInput(0, usd_imp)
            sop_nodes.append(xform_scale)

            prev = xform_scale

            # Match Size (ground asset)
            if ground_asset:
                matchsize = geo_node.createNode("matchsize", "ground_asset")
                # Justify Y: Minimum — parm varies by H version
                for pname in ("justify_y", "justifyy"):
                    p = matchsize.parm(pname)
                    if p:
                        p.set(0)  # 0 = Min in most H versions
                        break
                matchsize.setInput(0, prev)
                sop_nodes.append(matchsize)
                prev = matchsize

            # Optional rotation correction
            if rotation_correction and len(rotation_correction) == 3:
                xform_rot = geo_node.createNode("xform", "rotation_fix")
                for i, axis in enumerate(("rx", "ry", "rz")):
                    p = xform_rot.parm(axis)
                    if p:
                        p.set(float(rotation_correction[i]))
                xform_rot.setInput(0, prev)
                sop_nodes.append(xform_rot)
                prev = xform_rot

            # PolyReduce for proxy
            polyreduce = geo_node.createNode("polyreduce", "proxy_reduce")
            pct_parm = polyreduce.parm("percentage")
            if pct_parm:
                pct_parm.set(proxy_reduction * 100)  # polyreduce uses 0-100
            polyreduce.setInput(0, prev)
            sop_nodes.append(polyreduce)

            # Wire to default output (render) and proxy output
            # The full-res chain connects to "default", polyreduce to "proxy"+"simproxy"
            # This wiring depends on componentgeometry's internal output structure

            geo_node.layoutChildren()

            # Material import via Reference LOP
            mat_ref_path = None
            if import_materials:
                ref_lop = comp.createNode("reference", f"mtl_ref_{asset_name}")
                fp = ref_lop.parm("filepath1")
                if fp:
                    fp.set(usdc_path)
                pp = ref_lop.parm("primpath")
                if pp:
                    pp.set("/materials/*")
                dp = ref_lop.parm("destpath")
                if dp:
                    dp.set("asset/mtl/")
                mat_ref_path = ref_lop.path()

            # Component Material
            mat_node = comp.createNode("componentmaterial", f"mat_{asset_name}")
            mat_node.setInput(0, geo_node)

            # Component Output
            out_node = comp.createNode("componentoutput", f"output_{asset_name}")
            out_node.setInput(0, mat_node)
            name_parm = out_node.parm("name")
            if name_parm:
                name_parm.set(asset_name)
            if export_path:
                fp = out_node.parm("filepath")
                if fp:
                    fp.set(export_path)

            comp.layoutChildren()
            parent.layoutChildren()

            # Provenance
            _stamp_provenance(comp, {
                "tool": _TOOL_NAME,
                "source_pattern": _SOURCE_PATTERN,
                "reasoning": f"Imported Megascans asset '{asset_name}' from {usdc_path}",
            })

            geometry_nodes = [n.path() for n in sop_nodes]

            return {
                "status": "created",
                "component_path": comp.path(),
                "geometry_nodes": geometry_nodes,
                "material_reference": mat_ref_path,
                "export_path": export_path,
            }

    except Exception:
        raise
