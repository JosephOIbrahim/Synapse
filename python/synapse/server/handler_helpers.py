"""
Shared handler helpers.

Utilities used across multiple handler files (handlers.py, handlers_render.py).
Extracted to avoid circular imports between handler modules.
"""

import os

from ..core.aliases import USD_PARM_ALIASES


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
    # Check USD alias -- if the invalid name maps to an encoded USD parm, include hint
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


def _char_similarity(a: str, b: str) -> float:
    """Simple character-level similarity ratio between two strings.

    Returns a float between 0.0 and 1.0 based on longest common subsequence
    length divided by the longer string length.  No external dependencies.
    """
    if not a or not b:
        return 0.0
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower:
        return 1.0
    # Count matching characters (order-aware, simple approach)
    shorter, longer = (a_lower, b_lower) if len(a_lower) <= len(b_lower) else (b_lower, a_lower)
    matches = 0
    used = set()
    for ch in shorter:
        for idx, ch2 in enumerate(longer):
            if idx not in used and ch == ch2:
                matches += 1
                used.add(idx)
                break
    return matches / len(longer) if longer else 0.0


def _suggest_prim_paths(stage, invalid_path, max_suggestions=3):
    """Suggest similar USD prim paths when an invalid path is given.

    Walks the stage hierarchy and scores each prim path by:
    - Path segment overlap (segments in common between the invalid path and candidate)
    - Prefix match on the final segment (character-level similarity)

    Returns a formatted string like:
    " Similar prims: /scene/rubbertoy/geo, /scene/rubbertoy/geo/shape"

    Returns empty string if stage is None or no good matches found.
    """
    if stage is None:
        return ""

    try:
        all_prims = [p for p in stage.Traverse()]
    except Exception:
        return ""

    if not all_prims:
        return ""

    invalid_segments = [s for s in invalid_path.split("/") if s]
    if not invalid_segments:
        return ""

    invalid_last = invalid_segments[-1]
    invalid_set = set(s.lower() for s in invalid_segments)

    scored = []
    for prim in all_prims:
        prim_path = str(prim.GetPath())
        prim_segments = [s for s in prim_path.split("/") if s]
        if not prim_segments:
            continue

        # Score: segment overlap (how many segments match by name)
        prim_set = set(s.lower() for s in prim_segments)
        overlap = len(invalid_set & prim_set)

        # Score: final segment similarity
        prim_last = prim_segments[-1]
        last_sim = _char_similarity(invalid_last, prim_last)

        # Combined score (segment overlap weighted higher)
        score = overlap * 2.0 + last_sim

        if score > 0.5:
            scored.append((score, prim_path))

    if not scored:
        return ""

    # Sort by score descending, then path alphabetically for determinism
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = [path for _, path in scored[:max_suggestions]]
    return " Similar prims: " + ", ".join(top)


def _render_diagnostic_checklist(node):
    """Build a render readiness checklist for a LOP/ROP node.

    Returns a dict:
    {
        "camera_set": bool,
        "materials_bound": bool,
        "output_path_exists": bool,
        "output_dir_writable": bool,
        "resolution_set": bool,
        "renderer_valid": bool
    }

    Used by safe_render and error messages to give artists actionable next steps.
    Returns all-False dict if node is None.
    """
    result = {
        "camera_set": False,
        "materials_bound": False,
        "output_path_exists": False,
        "output_dir_writable": False,
        "resolution_set": False,
        "renderer_valid": False,
    }

    if node is None:
        return result

    # Check camera parameter
    for cam_parm in ("camera", "cam"):
        try:
            p = node.parm(cam_parm)
            if p is not None:
                val = p.eval()
                if val and str(val).strip():
                    result["camera_set"] = True
                    break
        except (AttributeError, TypeError):
            pass

    # Check output path
    output_path = None
    for out_parm in ("picture", "outputimage", "lopoutput"):
        try:
            p = node.parm(out_parm)
            if p is not None:
                val = p.eval()
                if val and str(val).strip():
                    output_path = str(val)
                    break
        except (AttributeError, TypeError):
            pass

    if output_path:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            result["output_path_exists"] = os.path.isdir(out_dir)
            if result["output_path_exists"]:
                result["output_dir_writable"] = os.access(out_dir, os.W_OK)

    # Check resolution
    for res_parm in ("res", "res1", "res2", "override_res"):
        try:
            p = node.parm(res_parm)
            if p is not None:
                result["resolution_set"] = True
                break
        except (AttributeError, TypeError):
            pass

    # Check renderer
    try:
        p = node.parm("renderer")
        if p is not None:
            val = p.eval()
            if val and str(val).strip():
                result["renderer_valid"] = True
    except (AttributeError, TypeError):
        pass

    # Check materials_bound -- heuristic: node is in a LOP context
    try:
        node_type = node.type()
        if node_type is not None:
            cat = node_type.category()
            if cat is not None and cat.name() == "Lop":
                # In LOP context, check if stage has any material bindings
                try:
                    stage = node.stage()
                    if stage:
                        for prim in stage.Traverse():
                            # Check for material binding relationship
                            rel = prim.GetRelationship("material:binding")
                            if rel and rel.GetTargets():
                                result["materials_bound"] = True
                                break
                except Exception:
                    pass
    except (AttributeError, TypeError):
        pass

    return result
