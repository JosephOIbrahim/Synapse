"""
synapse_solaris_scene_template — RELAY-SOLARIS Phase 3

Creates the full canonical Solaris scene skeleton:
  Primitive (Xform/Group) → SOP Import(s) → Camera → Material Library
  → Karma Physical Sky → Karma Render Settings → USD Render ROP

SOP imports chain sequentially — NEVER merge (Pattern 1 constraint).

Source patterns: SOLARIS_P1_CANONICAL_LOP_CHAIN, SOLARIS_P4_HIERARCHY_DISCIPLINE
Atomic: undo-wrapped. Idempotent: checks for existing scene root.
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


_SOURCE_PATTERN = "SOLARIS_P1_CANONICAL_LOP_CHAIN"
_TOOL_NAME = "synapse_solaris_scene_template"

# Canonical primitive path conventions (Pattern 4)
_PATH_TEMPLATES = {
    "root": "/{scene_name}",
    "geometry": "/{scene_name}/geo/$OS",
    "lighting": "/{scene_name}/LGT/$OS",
    "materials": "/{scene_name}/MTL/$OS",
    "cameras": "/{scene_name}/cam/$OS",
}


def _stamp_provenance(node, info: Dict[str, Any]) -> None:
    try:
        node.setUserData("synapse:tool", info.get("tool", _TOOL_NAME))
        node.setUserData("synapse:source_pattern", info.get("source_pattern", _SOURCE_PATTERN))
        node.setUserData("synapse:reasoning", info.get("reasoning", ""))
    except Exception:
        pass


def validate(params: Dict) -> None:
    """Validate parameters."""
    scene_name = params.get("scene_name", "shot")
    import re
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', scene_name):
        raise ValidationError(
            f"scene_name '{scene_name}' contains invalid characters"
        )
    resolution = params.get("resolution", [1920, 1080])
    if len(resolution) != 2 or any(r <= 0 for r in resolution):
        raise ValidationError(f"resolution must be [width, height] with positive values")
    engine = params.get("render_engine", "karma_xpu")
    if engine not in ("karma_xpu", "karma_cpu"):
        raise ValidationError(f"render_engine must be 'karma_xpu' or 'karma_cpu', got '{engine}'")


def plan(params: Dict) -> List[Dict[str, Any]]:
    """Return planned operations."""
    scene_name = params.get("scene_name", "shot")
    sop_paths = params.get("sop_paths", [])
    render_engine = params.get("render_engine", "karma_xpu")
    resolution = params.get("resolution", [1920, 1080])
    output_path = params.get("output_path", "$HIP/render/$HIPNAME.png")

    ops = []

    # 1. Primitive LOP — Xform hierarchy with Kind=Group
    ops.append({
        "op": "create_node",
        "node_type": "primitive",
        "params": {
            "primpath": f"/{scene_name}",
            "primtype": "Xform",
            "primkind": "Group",
        },
    })

    # 2. SOP Imports — chained sequentially, NEVER merged
    for i, sop_path in enumerate(sop_paths):
        ops.append({
            "op": "create_node",
            "node_type": "sopimport",
            "name": f"geo_{i}",
            "params": {
                "soppath": sop_path,
                "primpath": f"/{scene_name}/geo/$OS",
            },
            "chain": True,  # sequential chaining
        })

    # 3. Camera
    ops.append({
        "op": "create_node",
        "node_type": "camera",
        "params": {"primpath": f"/{scene_name}/cam/$OS"},
    })

    # 4. Material Library
    ops.append({
        "op": "create_node",
        "node_type": "materiallibrary",
        "params": {"primpath": f"/{scene_name}/MTL/$OS"},
    })

    # 5. Karma Physical Sky
    ops.append({
        "op": "create_node",
        "node_type": "karmaphysicalsky",
        "params": {"primpath": f"/{scene_name}/LGT/$OS"},
    })

    # 6. Karma Render Settings
    ops.append({
        "op": "create_node",
        "node_type": "karmarendersettings",
        "params": {"engine": render_engine, "resolution": resolution},
    })

    # 7. USD Render ROP
    ops.append({
        "op": "create_node",
        "node_type": "usdrender_rop",
        "params": {"outputpath": output_path},
    })

    # 8. Wire all sequentially
    ops.append({
        "op": "wire_chain",
        "sequence": [
            "primitive", "sopimport", "camera", "materiallibrary",
            "karmaphysicalsky", "karmarendersettings", "usdrender_rop",
        ],
    })

    ops.append({
        "op": "stamp_provenance",
        "tool": _TOOL_NAME,
        "source_pattern": _SOURCE_PATTERN,
    })

    return ops


def execute(params: Dict) -> Dict:
    """Execute the scene template creation."""
    if not HOU_AVAILABLE:
        raise HoudiniUnavailableError()

    validate(params)

    scene_name = params.get("scene_name", "shot")
    parent_path = params.get("parent", "/stage")
    sop_paths = params.get("sop_paths", [])
    render_engine = params.get("render_engine", "karma_xpu")
    resolution = params.get("resolution", [1920, 1080])
    output_path = params.get("output_path", "$HIP/render/$HIPNAME.png")

    parent = hou.node(parent_path)
    if parent is None:
        raise NodeNotFoundError(parent_path, suggestion="Check that /stage exists")

    # -- Idempotency guard --
    existing = parent.node(f"primitive_{scene_name}")
    if existing is not None:
        return {
            "status": "already_exists",
            "hierarchy_root": f"/{scene_name}",
        }

    # -- Atomic execution --
    try:
        with hou.undos.group(f"SYNAPSE: Create scene template '{scene_name}'"):
            chain = []

            # 1. Primitive LOP — hierarchy root
            prim = parent.createNode("primitive", f"primitive_{scene_name}")
            primpath_parm = prim.parm("primpath")
            if primpath_parm:
                primpath_parm.set(f"/{scene_name}")
            primtype_parm = prim.parm("primtype")
            if primtype_parm:
                primtype_parm.set("Xform")
            primkind_parm = prim.parm("primkind")
            if primkind_parm:
                primkind_parm.set("group")
            chain.append(prim)
            prev = prim

            # 2. SOP Imports — CHAINED SEQUENTIALLY, never merged
            for i, sop_path in enumerate(sop_paths):
                imp = parent.createNode("sopimport", f"geo_{i}")
                soppath_parm = imp.parm("soppath")
                if soppath_parm:
                    soppath_parm.set(sop_path)
                pp = imp.parm("primpath")
                if pp:
                    pp.set(f"/{scene_name}/geo/$OS")
                imp.setInput(0, prev)
                chain.append(imp)
                prev = imp

            # 3. Camera
            cam = parent.createNode("camera", "camera1")
            cp = cam.parm("primpath")
            if cp:
                cp.set(f"/{scene_name}/cam/$OS")
            cam.setInput(0, prev)
            chain.append(cam)
            prev = cam

            # 4. Material Library
            matlib = parent.createNode("materiallibrary", "materials")
            mp = matlib.parm("primpath")
            if mp:
                mp.set(f"/{scene_name}/MTL/$OS")
            matlib.setInput(0, prev)
            chain.append(matlib)
            prev = matlib

            # 5. Karma Physical Sky
            sky = parent.createNode("karmaphysicalsky", "physical_sky")
            sp = sky.parm("primpath")
            if sp:
                sp.set(f"/{scene_name}/LGT/$OS")
            sky.setInput(0, prev)
            chain.append(sky)
            prev = sky

            # 6. Karma Render Settings
            # The "karma" node creates render settings + properties
            rs = parent.createNode("karmarendersettings", "render_settings")
            # Engine selection
            eng_parm = rs.parm("engine")
            if eng_parm:
                eng_parm.set("XPU" if render_engine == "karma_xpu" else "CPU")
            # Resolution
            resx = rs.parm("resx")
            resy = rs.parm("resy")
            if resx:
                resx.set(resolution[0])
            if resy:
                resy.set(resolution[1])
            # Camera
            cam_parm = rs.parm("camera")
            if cam_parm:
                cam_parm.set(f"/{scene_name}/cam/camera1")
            rs.setInput(0, prev)
            chain.append(rs)
            prev = rs

            # 7. USD Render ROP
            rop = parent.createNode("usdrender_rop", "render")
            out_parm = rop.parm("outputimage")
            if out_parm:
                out_parm.set(output_path)
            rop.setInput(0, prev)
            chain.append(rop)

            # Layout
            parent.layoutChildren()

            # Provenance on all nodes
            for node in chain:
                _stamp_provenance(node, {
                    "tool": _TOOL_NAME,
                    "source_pattern": _SOURCE_PATTERN,
                    "reasoning": f"Scene template '{scene_name}' — NodeFlow Pattern 1+4",
                })

            chain_paths = [n.path() for n in chain]

            return {
                "status": "created",
                "chain": chain_paths,
                "hierarchy_root": f"/{scene_name}",
                "render_rop": rop.path(),
                "primitive_paths": {
                    k: v.format(scene_name=scene_name)
                    for k, v in _PATH_TEMPLATES.items()
                },
            }

    except Exception:
        raise
