"""
synapse_solaris_create_variants — RELAY-SOLARIS Phase 3

Creates material and/or geometry variants on a Component Builder.
Material: duplicate Component Material nodes with different KMBs.
Geometry: duplicate Component Geometry + Component Geometry Variants node.

Source pattern: SOLARIS_P5_VARIANTS
Atomic: undo-wrapped. Idempotent: checks for existing variant set.
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


_SOURCE_PATTERN = "SOLARIS_P5_VARIANTS"
_TOOL_NAME = "synapse_solaris_create_variants"


def _stamp_provenance(node, info: Dict[str, Any]) -> None:
    try:
        node.setUserData("synapse:tool", info.get("tool", _TOOL_NAME))
        node.setUserData("synapse:source_pattern", info.get("source_pattern", _SOURCE_PATTERN))
        node.setUserData("synapse:reasoning", info.get("reasoning", ""))
    except Exception:
        pass


def validate(params: Dict) -> None:
    """Validate parameters."""
    component_path = params.get("component_path")
    if not component_path:
        raise ValidationError("component_path is required")
    variant_type = params.get("variant_type")
    if variant_type not in ("material", "geometry"):
        raise ValidationError(f"variant_type must be 'material' or 'geometry', got '{variant_type}'")
    variants = params.get("variants", [])
    if len(variants) < 2:
        raise ValidationError("At least 2 variants are required to create a variant set")
    for v in variants:
        if not v.get("name"):
            raise ValidationError("Each variant must have a 'name' field")


def plan(params: Dict) -> List[Dict[str, Any]]:
    """Return planned operations."""
    component_path = params.get("component_path", "/stage/component")
    variant_type = params.get("variant_type", "material")
    variants = params.get("variants", [])
    add_explore = params.get("add_explore_node", True)

    ops = []

    if variant_type == "material":
        # Duplicate Component Material for each variant
        for v in variants:
            ops.append({
                "op": "duplicate_component_material",
                "name": v["name"],
                "material_params": v.get("material", {}),
            })
        ops.append({
            "op": "note",
            "message": "Component Builder auto-creates material variant set from duplicates",
        })
    else:
        # Duplicate Component Geometry + merge with Component Geometry Variants
        for v in variants:
            ops.append({
                "op": "duplicate_component_geometry",
                "name": v["name"],
                "geometry_source": v.get("geometry_source"),
            })
        ops.append({
            "op": "create_node",
            "node_type": "componentgeometryvariants",
            "note": "Merges geometry variants into a variant set",
        })

    if add_explore:
        ops.append({
            "op": "create_node",
            "node_type": "explorevariants",
            "note": "Interactive variant preview (non-committing)",
        })

    ops.append({
        "op": "stamp_provenance",
        "tool": _TOOL_NAME,
        "source_pattern": _SOURCE_PATTERN,
    })

    return ops


def execute(params: Dict) -> Dict:
    """Execute variant creation."""
    if not HOU_AVAILABLE:
        raise HoudiniUnavailableError()

    validate(params)

    component_path = params["component_path"]
    variant_type = params["variant_type"]
    variants = params["variants"]
    add_explore = params.get("add_explore_node", True)

    comp = hou.node(component_path)
    if comp is None:
        raise NodeNotFoundError(component_path, suggestion="Check component builder path")

    # Find the parent LOP network for the explore node
    parent = comp.parent()

    # -- Idempotency guard --
    # Check if variant nodes already exist with these names
    existing_names = {c.name() for c in comp.children()}
    variant_names = [v["name"] for v in variants]
    if all(f"mat_{vn}" in existing_names or f"geo_{vn}" in existing_names for vn in variant_names):
        return {
            "status": "already_exists",
            "variant_set_name": f"{variant_type}_variants",
            "variants_created": variant_names,
        }

    try:
        with hou.undos.group(f"SYNAPSE: Create {variant_type} variants"):
            created = []

            if variant_type == "material":
                # Find existing componentmaterial to duplicate
                base_mat = None
                for child in comp.children():
                    if child.type().name().lower() == "componentmaterial":
                        base_mat = child
                        break

                # F4: hou.copyNodesTo does NOT carry connections that originate
                # outside the copied set, so the duplicates land unwired.
                # Capture the base node's inputs and re-establish them explicitly.
                base_inputs = list(base_mat.inputs()) if base_mat else []

                for v in variants:
                    vname = v["name"]
                    # Duplicate componentmaterial
                    if base_mat:
                        new_mat = hou.copyNodesTo([base_mat], comp)[0]
                        new_mat.setName(f"mat_{vname}", unique_name=True)
                    else:
                        new_mat = comp.createNode("componentmaterial", f"mat_{vname}")

                    # F4: re-establish the connections the copy dropped.
                    for idx, src in enumerate(base_inputs):
                        if src is not None:
                            new_mat.setInput(idx, src)

                    # Apply material params if provided
                    mat_params = v.get("material", {})
                    for pname, pval in mat_params.items():
                        p = new_mat.parm(pname)
                        if p:
                            p.set(pval)

                    created.append(new_mat)

            else:  # geometry
                base_geo = None
                for child in comp.children():
                    if child.type().name().lower() == "componentgeometry":
                        base_geo = child
                        break

                for v in variants:
                    vname = v["name"]
                    if base_geo:
                        new_geo = hou.copyNodesTo([base_geo], comp)[0]
                        new_geo.setName(f"geo_{vname}", unique_name=True)
                    else:
                        new_geo = comp.createNode("componentgeometry", f"geo_{vname}")
                    created.append(new_geo)

                # Create Component Geometry Variants node to merge.
                # F6: no bare `except: pass` here. If this cannot be built the
                # call raises — a status of "created" must never describe a
                # component whose variant merge silently never happened.
                geo_variants = comp.createNode("componentgeometryvariants", "geo_variants")

                # Wire the base geometry plus every variant copy into it.
                merge_sources = ([base_geo] if base_geo is not None else []) + created
                for i, geo_node in enumerate(merge_sources):
                    geo_variants.setInput(i, geo_node)

                # F5: the merge node must reach the terminal. Whatever used to
                # consume the base geometry (componentmaterial, typically) now
                # consumes the variant set instead, so the component presents
                # ONE terminal LOP rather than two.
                if base_geo is not None:
                    gv_path = geo_variants.path()
                    for consumer in base_geo.outputs():
                        if consumer.path() == gv_path:
                            continue
                        for idx, src in enumerate(consumer.inputs()):
                            if src is not None and src.path() == base_geo.path():
                                consumer.setInput(idx, geo_variants)

                created.append(geo_variants)

            # Add Explore Variants node (outside the component, in the parent)
            # F6: failures propagate rather than being swallowed into a
            # "created" status with an unbuilt node.
            explore_path = None
            if add_explore:
                explore = parent.createNode("explorevariants", f"explore_{comp.name()}")
                explore.setInput(0, comp)
                explore_path = explore.path()

            comp.layoutChildren()
            if parent:
                parent.layoutChildren()

            # Provenance
            for node in created:
                _stamp_provenance(node, {
                    "tool": _TOOL_NAME,
                    "source_pattern": _SOURCE_PATTERN,
                    "reasoning": f"Created {variant_type} variant '{node.name()}'",
                })

            return {
                "status": "created",
                "variant_set_name": f"{variant_type}_variants",
                "variants_created": variant_names,
                "explore_node": explore_path,
            }

    except Exception:
        raise
