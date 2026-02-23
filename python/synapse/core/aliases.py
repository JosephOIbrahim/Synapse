"""
Synapse Parameter Aliasing

Centralized parameter aliasing system to accept multiple naming conventions.
Allows clients to use different naming conventions (camelCase, snake_case, etc.)
"""

from typing import Dict, List, Any, Optional


# =============================================================================
# PARAMETER ALIASES
# =============================================================================

PARAM_ALIASES: Dict[str, List[str]] = {
    # Node references
    "source": ["source", "from_node", "from", "src", "input_node"],
    "target": ["target", "to_node", "to", "dst", "output_node", "dest"],
    "node": ["node", "path", "node_path"],
    "parent": ["parent", "parent_path", "parent_node"],

    # Input/output indices
    "source_output": ["source_output", "from_output", "output_index", "out_idx"],
    "target_input": ["target_input", "to_input", "input_index", "in_idx"],

    # Parameters
    "parm": ["parm", "parameter", "param", "attr", "attribute"],
    "value": ["value", "val", "v"],

    # Node creation
    "type": ["type", "node_type", "nodeType"],
    "name": ["name", "node_name", "nodeName"],

    # USD
    "prim_path": ["prim_path", "path", "primPath"],
    "prim_type": ["prim_type", "type", "primType"],
    "usd_attribute": ["usd_attribute", "attribute_name", "attrName", "attr_name"],

    # Memory operations
    "query": ["query", "q", "search", "text"],
    "content": ["content", "text", "message", "body"],
    "memory_type": ["memory_type", "type", "memoryType"],
    "tags": ["tags", "labels", "categories"],
    "keywords": ["keywords", "keys", "concepts"],
    "limit": ["limit", "max", "count"],
    "decision": ["decision", "what", "choice"],
    "reasoning": ["reasoning", "why", "rationale", "reason"],
    "alternatives": ["alternatives", "options", "other_options", "otherOptions"],

    # Viewport capture / render
    "format": ["format", "fmt", "image_format"],
    "width": ["width", "w", "res_x"],
    "height": ["height", "h", "res_y"],
    "frame": ["frame", "f", "frame_number", "frame_num"],
    # Wedge / TOPs
    "values": ["values", "wedge_values", "vals"],
    # TOPS / PDG
    "topnet_path": ["topnet_path", "topnet", "network_path"],
    "state_filter": ["state_filter", "filter_state", "state"],
    "include_attributes": ["include_attributes", "include_attrs", "attrs"],
    "generate_only": ["generate_only", "gen_only"],
    "blocking": ["blocking", "block", "wait"],
    "top_down": ["top_down", "topdown", "cook_upstream"],
    "scheduler_type": ["scheduler_type", "scheduler", "sched_type"],
    "max_concurrent": ["max_concurrent", "max_procs", "concurrency"],
    "working_dir": ["working_dir", "work_dir", "pdg_workingdir"],
    "dirty_upstream": ["dirty_upstream", "upstream", "recursive"],
    "wedge_name": ["wedge_name", "name"],
    "attributes": ["attributes", "wedge_attributes", "wedge_attrs"],
    "node_paths": ["node_paths", "nodes", "paths"],
    "stop_on_error": ["stop_on_error", "stop_on_fail", "fail_fast"],
    "query_attribute": ["query_attribute", "attribute_name", "attr_name", "attrib"],
    "filter_op": ["filter_op", "operator", "op"],
    "filter_value": ["filter_value", "value", "match_value"],
    "max_retries": ["max_retries", "retries", "retry_count"],
    "validate_states": ["validate_states", "validate", "check_states"],
    "include_scheduler": ["include_scheduler", "check_scheduler"],
    "include_dependencies": ["include_dependencies", "deps", "check_deps"],
    "include_items": ["include_items", "show_items"],

    # USD scene assembly
    "file": ["file", "filepath", "file_path", "path", "usd_file"],
    "mode": ["mode", "import_mode"],
    "settings": ["settings", "overrides", "params"],

    # Introspection
    "depth": ["depth", "input_depth"],
    "root": ["root", "root_path"],
    "max_depth": ["max_depth", "maxDepth"],
    "context_filter": ["context_filter", "contextFilter", "filter"],
    "include_code": ["include_code", "includeCode"],
    "include_geometry": ["include_geometry", "includeGeometry"],
    "include_expressions": ["include_expressions", "includeExpressions"],

    # Execute options
    "dry_run": ["dry_run", "dryRun", "syntax_check"],
    "atomic": ["atomic", "use_undo"],

    # Materials
    "material_path": ["material_path", "mat_path", "matspecpath", "shader_path"],
    "prim_pattern": ["prim_pattern", "geometry", "geo_path", "primpattern"],
    "shader_type": ["shader_type", "shader", "mtlx_type"],
    "base_color": ["base_color", "color", "diffuse_color", "baseColor"],
    "metalness": ["metalness", "metallic", "metal"],
    "roughness": ["roughness", "specular_roughness"],

    # VEX execution
    "snippet": ["snippet", "vex_code", "vex", "code"],
    "run_over": ["run_over", "runover", "class", "geo_class"],
    "input_node": ["input_node", "input", "input_geo"],

    # Frame validation
    "image_path": ["image_path", "image", "file_path", "frame_path"],
    "checks": ["checks", "validations", "check_list"],
    "thresholds": ["thresholds", "threshold_overrides", "limits"],

    # Copernicus (COPs)
    "cop_path": ["cop_path", "cop_node", "cop"],
    "kernel_code": ["kernel_code", "kernelcode", "opencl_code", "kernel"],
    "kernel_name": ["kernel_name", "kernelname", "entry_point"],
    "cop_type": ["cop_type", "cop_node_type"],
    "layer": ["layer", "plane", "channel"],
    "precision": ["precision", "bit_depth", "data_type"],
    "initial_nodes": ["initial_nodes", "init_nodes"],
    "exr_path": ["exr_path", "exr_file", "exr"],
    "aov_list": ["aov_list", "aovs", "aov_layers", "layers"],
    "material_input": ["material_input", "input_name", "tex_input"],
    "material_node": ["material_node", "mat_node", "shader_node"],
    "comp_mode": ["comp_mode", "blend_mode", "composite_mode"],
    "seed_mask": ["seed_mask", "seed", "mask"],
    "growth_rate": ["growth_rate", "growth", "rate"],
    "feed_rate": ["feed_rate", "F", "feed"],
    "kill_rate": ["kill_rate", "k", "kill"],
    "noise_type": ["noise_type", "noise", "noise_basis"],
    "sort_direction": ["sort_direction", "direction", "sort_dir"],
    "sort_by": ["sort_by", "sort_criteria", "sort_mode"],
    "style_type": ["style_type", "style", "effect"],
    "threshold_low": ["threshold_low", "low_threshold", "min_threshold"],
    "threshold_high": ["threshold_high", "high_threshold", "max_threshold"],
    "sop_path": ["sop_path", "sop_node", "geometry_source"],
    "decay": ["decay", "decay_rate", "falloff"],
    "map_types": ["map_types", "bake_maps", "maps"],
    "stamp_source": ["stamp_source", "stamp_image", "stamp"],
    "scale_range": ["scale_range", "scale_min_max"],
    "rotation_range": ["rotation_range", "rot_range"],
    "parallel": ["parallel", "use_tops", "batch_parallel"],
    "diffusion_a": ["diffusion_a", "da", "diff_a"],
    "diffusion_b": ["diffusion_b", "db", "diff_b"],
}


# Pre-computed reverse alias map: alias -> canonical name (O(1) lookup)
_REVERSE_ALIASES: Dict[str, str] = {}
for _canonical, _aliases in PARAM_ALIASES.items():
    for _alias in _aliases:
        _REVERSE_ALIASES[_alias] = _canonical


# =============================================================================
# USD PARAMETER ALIASES
# =============================================================================

USD_PARM_ALIASES: Dict[str, str] = {
    # Lights — intensity
    "intensity": "xn__inputsintensity_i0a",
    "light_intensity": "xn__inputsintensity_i0a",
    # Lights — exposure
    "exposure": "xn__inputsexposure_vya",
    "light_exposure": "xn__inputsexposure_vya",
    "exposure_control": "xn__inputsexposure_control_wcb",
    # Lights — color
    "color": "xn__inputscolor_kya",
    "light_color": "xn__inputscolor_kya",
    "color_control": "xn__inputscolor_control_r0b",
    # Lights — temperature
    "color_temperature": "xn__inputscolortemperature_job",
    "temperature": "xn__inputscolortemperature_job",
    "enable_temperature": "xn__inputsenablecolortemperature_yxb",
    # Lights — shape
    "normalize": "xn__inputsnormalize_01a",
    "diffuse": "xn__inputsdiffuse_vya",
    "specular": "xn__inputsspecular_i0a",
    # DomeLight
    "texture_file": "xn__inputstexturefile_c5b",
    "texture_format": "xn__inputstextureformat_d8b",
    # Camera
    "focal_length": "xn__inputsfocallength_e4b",
    "focus_distance": "xn__inputsfocusdistance_f7b",
    "fstop": "xn__inputsfstop_vya",
    "horizontal_aperture": "xn__inputshorizontalaperture_ohb",
    "vertical_aperture": "xn__inputsverticalaperture_gfb",
    "clipping_range": "xn__inputsclippingrange_e4b",
    # Xform
    "translate": "xformOp:translate",
    "rotate": "xformOp:rotateXYZ",
    "scale": "xformOp:scale",
    # Visibility
    "visibility": "visibility",
    "purpose": "purpose",
}



def resolve_param(payload: Dict, canonical: str, required: bool = True) -> Any:
    """
    Resolve a parameter from payload using aliasing.

    Args:
        payload: The command payload dictionary
        canonical: The canonical parameter name
        required: Whether the parameter is required

    Returns:
        The parameter value, or None if not found and not required

    Raises:
        ValueError: If required parameter is not found
    """
    # Fast path: direct canonical key match
    if canonical in payload:
        return payload[canonical]

    # Fast path: reverse-lookup payload keys against pre-computed map
    for key in payload:
        if _REVERSE_ALIASES.get(key) == canonical:
            return payload[key]

    # Fallback: check known aliases for this canonical name (handles dynamic aliases)
    aliases = PARAM_ALIASES.get(canonical, [canonical])
    for alias in aliases:
        if alias in payload:
            return payload[alias]

    if required:
        alias_list = ", ".join(f"'{a}'" for a in aliases)
        raise ValueError(
            f"Missing required parameter. Expected one of: {alias_list}\n"
            f"HINT: Common names are '{canonical}' or '{aliases[1] if len(aliases) > 1 else canonical}'"
        )

    return None


def resolve_param_with_default(payload: Dict, canonical: str, default: Any) -> Any:
    """Resolve parameter with a default value if not found."""
    result = resolve_param(payload, canonical, required=False)
    return result if result is not None else default


def get_all_aliases(canonical: str) -> List[str]:
    """Get all aliases for a canonical parameter name."""
    return PARAM_ALIASES.get(canonical, [canonical])


def add_alias(canonical: str, alias: str):
    """Add a new alias for a canonical parameter name."""
    if canonical not in PARAM_ALIASES:
        PARAM_ALIASES[canonical] = [canonical]
    if alias not in PARAM_ALIASES[canonical]:
        PARAM_ALIASES[canonical].append(alias)


def resolve_usd_parm(name: str) -> Optional[str]:
    """Resolve a human-readable USD parameter name to its encoded form.

    Returns the encoded USD parm name if found, None otherwise.
    Pure function, static dict. No determinism concern.
    """
    return USD_PARM_ALIASES.get(name.lower())
