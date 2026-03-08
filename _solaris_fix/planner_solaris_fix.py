"""
Solaris Context Fix — planner_solaris_fix.py
=============================================

Drop-in replacement logic for python/synapse/routing/planner.py
Eliminates the hardcoded `/obj` default that causes Solaris network
creation to land in the wrong context.

INSTALLATION:
    1. Add _infer_parent() and SOLARIS_SIGNALS to planner.py
    2. Replace all `params.get("parent", "/obj")` with
       `_infer_parent(params)` or `_infer_parent(params, intent)`
    3. Replace all fallback strings `or hou.node('/obj')` with
       `or hou.node('{_infer_parent(params)}')` in generated code

AGENT TEAM ASSIGNMENT: ROUTING specialist
"""

from __future__ import annotations

from typing import Dict, Optional, Set

# ─────────────────────────────────────────────────────────────────────
# Signal sets for context inference
# ─────────────────────────────────────────────────────────────────────

SOLARIS_SIGNALS: Set[str] = {
    # Node types that only exist in LOPs
    "sopcreate", "sopimport", "materiallibrary", "assignmaterial",
    "domelight", "rectlight", "spherelight", "distantlight", "disklight",
    "cylinderlight", "camera", "karmarenderproperties", "karmarendersettings",
    "rendergeometrysettings", "rendersettings", "renderproduct",
    "usdrender", "reference", "sublayer", "merge",  # merge is ambiguous but common in LOPs
    "edit", "configureprimitive", "componentoutput", "instancer",
    "sceneimport", "null",  # null is ambiguous but in LOP chains it's OUTPUT
    "configurestage", "materiallinker",
    # Intent keywords from natural language
    "light", "lighting", "camera", "render", "karma", "material",
    "shader", "materialx", "mtlx", "usd", "solaris", "lop", "stage",
    "dome", "hdri", "environment", "scene", "prim", "primpath",
    "exposure", "intensity",
    # Render-related
    "beauty", "aov", "denoise", "samples", "xpu", "cpu",
}

SOP_SIGNALS: Set[str] = {
    # Node types that only exist in SOPs
    "box", "sphere", "grid", "tube", "torus", "circle", "line",
    "scatter", "attribwrangle", "pointwrangle", "primitivewrangle",
    "vellumcloth", "vellumsolver", "vellumdrape",
    "pyrosolver", "pyrosource", "filecache",
    "rbdmaterialfracture", "assemble", "dopimport",
    "boolean", "vdbfrompolygons", "heightfield",
    "foreach_begin", "foreach_end", "compile_begin", "compile_end",
    # Intent keywords
    "geometry", "mesh", "points", "vex", "wrangle", "sim", "simulation",
    "fracture", "vellum", "pyro", "flip", "rbd", "cache",
    "deform", "procedural", "scatter", "noise",
}


def _infer_parent(
    params: Dict[str, str],
    intent: Optional[str] = None,
    current_network: Optional[str] = None,
) -> str:
    """Infer the correct parent context from parameters and intent.

    Priority order:
        1. Explicit parent in params (artist specified it)
        2. Current network context from scene (if passed by caller)
        3. Signal-based inference from params + intent text
        4. Default to /obj (SOP work is still the common case)

    Args:
        params: Recipe parameters dict. May contain "parent" key.
        intent: Optional natural language intent string (user's message).
        current_network: Current Houdini network path from scene context.

    Returns:
        "/stage" for Solaris work, "/obj" for SOP work.
    """
    # 1. Explicit parent always wins
    explicit = params.get("parent")
    if explicit:
        return explicit

    # 2. If we know the artist is currently IN /stage, default there
    if current_network and current_network.startswith("/stage"):
        return "/stage"

    # 3. Signal-based inference: scan all param values + intent for signals
    search_text = " ".join(str(v) for v in params.values()).lower()
    if intent:
        search_text += " " + intent.lower()

    # Count signals in each direction
    solaris_hits = sum(1 for sig in SOLARIS_SIGNALS if sig in search_text)
    sop_hits = sum(1 for sig in SOP_SIGNALS if sig in search_text)

    # Strong Solaris signal: any LOP-only node type or 2+ intent keywords
    lop_only_types = {
        "sopcreate", "sopimport", "materiallibrary", "assignmaterial",
        "domelight", "rectlight", "spherelight", "distantlight",
        "karmarenderproperties", "karmarendersettings", "renderproduct",
        "configureprimitive", "componentoutput", "configurestage",
    }
    if any(t in search_text for t in lop_only_types):
        return "/stage"

    if solaris_hits >= 2 and solaris_hits > sop_hits:
        return "/stage"

    # 4. Default: /obj for SOP work
    return "/obj"


def _generate_parent_line(params: Dict[str, str], intent: Optional[str] = None) -> str:
    """Generate the Python code line for parent node resolution.

    Instead of the old:
        parent = hou.node('{parent}') or hou.node('/obj')

    This generates context-aware fallback:
        parent = hou.node('/stage') or hou.node('/obj')  # for Solaris
        parent = hou.node('/obj')                        # for SOPs

    Args:
        params: Recipe parameters dict.
        intent: Optional natural language intent.

    Returns:
        Python code string for parent resolution.
    """
    parent = _infer_parent(params, intent)

    if parent == "/stage":
        return (
            f"parent = hou.node('{parent}')\n"
            f"if parent is None:\n"
            f"    parent = hou.node('/').createNode('lopnet', 'stage')\n"
        )
    else:
        return f"parent = hou.node('{parent}') or hou.node('/obj')\n"


# ─────────────────────────────────────────────────────────────────────
# Migration helper: find all locations that need patching
# ─────────────────────────────────────────────────────────────────────

MIGRATION_PATTERNS = """
SEARCH & REPLACE GUIDE for planner.py
======================================

Find all instances of these patterns and replace:

PATTERN 1 — Default parent extraction:
  OLD:  parent = params.get("parent", "/obj")
  NEW:  parent = _infer_parent(params, intent=intent_text)

PATTERN 2 — Fallback in generated code:
  OLD:  f"parent = hou.node('{parent}') or hou.node('/obj')\\n"
  NEW:  _generate_parent_line(params, intent=intent_text)

PATTERN 3 — Hardcoded /obj in recipe steps:
  OLD:  "parent": "/obj"
  NEW:  # Remove this line; let _infer_parent handle it at runtime

Locations in planner.py (as of current codebase):
  Lines 186, 192, 208, 220, 232, 246, 266, 272, 295, 307, 320, 432, 438, 452, 466, 485, 491

Total replacements needed: ~19 locations
"""


# ─────────────────────────────────────────────────────────────────────
# Test cases (for test_solaris_ordering.py integration)
# ─────────────────────────────────────────────────────────────────────

def _self_test():
    """Verify inference logic. Run with: python planner_solaris_fix.py"""

    # Explicit parent always wins
    assert _infer_parent({"parent": "/obj/geo1"}) == "/obj/geo1"
    assert _infer_parent({"parent": "/stage"}) == "/stage"

    # Current network context
    assert _infer_parent({}, current_network="/stage") == "/stage"
    assert _infer_parent({}, current_network="/stage/subnet1") == "/stage"
    assert _infer_parent({}, current_network="/obj") == "/obj"

    # Signal inference: Solaris node types
    assert _infer_parent({"type": "domelight"}) == "/stage"
    assert _infer_parent({"type": "rectlight"}) == "/stage"
    assert _infer_parent({"type": "materiallibrary"}) == "/stage"
    assert _infer_parent({"type": "karmarenderproperties"}) == "/stage"
    assert _infer_parent({"type": "sopcreate"}) == "/stage"

    # Signal inference: SOP node types default to /obj
    assert _infer_parent({"type": "box"}) == "/obj"
    assert _infer_parent({"type": "scatter"}) == "/obj"

    # Intent-based inference
    assert _infer_parent({}, intent="create a camera and light setup") == "/stage"
    assert _infer_parent({}, intent="set up karma render") == "/stage"
    assert _infer_parent({}, intent="build a vex wrangle for scatter") == "/obj"

    # Ambiguous defaults to /obj
    assert _infer_parent({}) == "/obj"
    assert _infer_parent({}, intent="create something") == "/obj"

    # Code generation
    line = _generate_parent_line({"type": "domelight"})
    assert "/stage" in line
    assert "createNode('lopnet'" in line  # auto-create /stage if missing

    line = _generate_parent_line({"type": "box"})
    assert "/obj" in line

    print("All self-tests passed ✓")


if __name__ == "__main__":
    _self_test()
