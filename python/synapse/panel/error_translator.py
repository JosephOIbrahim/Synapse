"""Translate cryptic Houdini errors into plain-English explanations.

Intercepts error messages from tool failures, node cook errors, and render
issues, then returns human-friendly explanations with suggested fixes.

All regex patterns are compiled at module level for speed. The hou module
is imported lazily only in get_error_context() -- translate_error and
translate_tool_error work without Houdini.
"""

from __future__ import annotations

import html
import re
from typing import Optional

# -- Design tokens (for HTML formatting) ------------------------------------
try:
    from synapse.panel import tokens as _t
    _ERROR = _t.ERROR
    _WARNING = _t.WARN
    _SIGNAL = _t.SIGNAL
    _TEXT = _t.TEXT
    _TEXT_DIM = _t.TEXT_DIM
    _CARBON = _t.CARBON
    _FONT_MONO = _t.FONT_MONO
    _BODY_PX = _t.SIZE_BODY
    _SMALL_PX = _t.SIZE_SMALL
except ImportError:
    _ERROR = "#FF3D71"
    _WARNING = "#FFAB00"
    _SIGNAL = "#00D4FF"
    _TEXT = "#E0E0E0"
    _TEXT_DIM = "#999999"
    _CARBON = "#333333"
    _FONT_MONO = "JetBrains Mono"
    _BODY_PX = 26
    _SMALL_PX = 22


# ---------------------------------------------------------------------------
# Severity colors (for HTML border styling)
# ---------------------------------------------------------------------------
_SEVERITY_COLORS = {
    "critical": _ERROR,
    "error": _ERROR,
    "warning": _WARNING,
}


# ---------------------------------------------------------------------------
# Error pattern definitions -- ordered by specificity (most specific first)
# ---------------------------------------------------------------------------
_RAW_PATTERNS = [
    # ── VEX errors (specific before generic) ──────────────────────────────
    {
        "pattern": r"Syntax error,\s*unexpected\s+(.+)",
        "category": "vex_syntax",
        "explain": "VEX hit a syntax snag near {match_1}.",
        "suggest": (
            "Check for missing semicolons, unmatched braces, or typos "
            "near that token. VEX syntax is C-like -- every statement "
            "needs a semicolon."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Cannot find function\s+(.+)",
        "category": "vex_function",
        "explain": (
            "VEX can't find a function called {match_1}."
        ),
        "suggest": (
            "Double-check the function name spelling and make sure you're "
            "using the right context (SOP vs CVEX). Some functions are "
            "context-specific."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Type mismatch",
        "category": "vex_type",
        "explain": (
            "VEX found a type mismatch -- a value is being used as "
            "the wrong type (e.g., assigning a vector to a float)."
        ),
        "suggest": (
            "Check variable types on both sides of assignments. Use "
            "explicit casts like float() or vector() where needed."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Possible loss of precision",
        "category": "vex_precision",
        "explain": (
            "VEX is warning that a numeric conversion may lose data "
            "(e.g., double to float, or int to shorter int)."
        ),
        "suggest": (
            "This is usually safe to ignore for visual work. If precision "
            "matters (simulation, IDs), use explicit casts to silence it."
        ),
        "severity": "warning",
    },
    {
        "pattern": r"VEX error:\s*(.+)",
        "category": "vex_error",
        "explain": "VEX ran into a problem: {match_1}.",
        "suggest": (
            "Open the VEX code editor and check the line mentioned in "
            "the error. Common causes: undeclared variables, wrong "
            "attribute types, or missing @-prefix on attributes."
        ),
        "severity": "error",
    },

    # ── USD / Solaris errors ──────────────────────────────────────────────
    {
        "pattern": r"Failed to compose prim\s+(.+)",
        "category": "usd_composition",
        "explain": (
            "USD composition failed for prim {match_1}. The scene's "
            "layer stack has a conflict or broken reference."
        ),
        "suggest": (
            "Check for circular references, missing sublayers, or "
            "conflicting opinions on the same prim. The Scene Graph "
            "Details panel can help trace composition arcs."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Cannot resolve asset path\s+(.+)",
        "category": "usd_asset_path",
        "explain": (
            "USD can't resolve the asset path {match_1}. The file or "
            "reference target doesn't exist where expected."
        ),
        "suggest": (
            "Verify the file path is correct and the asset exists on "
            "disk. Check $JOB and other Houdini variables in the path. "
            "Relative paths resolve from the USD file's directory."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Invalid layer\s+(.+)",
        "category": "usd_layer",
        "explain": (
            "USD layer {match_1} is invalid -- it may be corrupt, "
            "missing, or contain syntax errors."
        ),
        "suggest": (
            "Try opening the .usd/.usda file in a text editor to check "
            "for obvious syntax issues. If it's a binary .usdc, try "
            "re-exporting from the source."
        ),
        "severity": "error",
    },

    # ── Render errors ─────────────────────────────────────────────────────
    {
        "pattern": r"Out of memory",
        "category": "oom",
        "explain": (
            "The system ran out of memory. This typically happens during "
            "heavy renders or simulations with large datasets."
        ),
        "suggest": (
            "Try reducing texture resolution, geometry detail, or render "
            "resolution. For Karma, lower the pixel samples or use "
            "adaptive sampling. Check Task Manager for memory usage."
        ),
        "severity": "critical",
    },
    {
        "pattern": r"License not available",
        "category": "license",
        "explain": (
            "Houdini can't find a valid license for this operation. "
            "The license server may be down or all seats are in use."
        ),
        "suggest": (
            "Open the License Administrator (hkey) to check license "
            "status. If using a floating license, another user may have "
            "the last seat. Apprentice/Indie have render limitations."
        ),
        "severity": "critical",
    },
    {
        "pattern": r"Karma:\s*(.+)",
        "category": "karma",
        "explain": "Karma reported an issue: {match_1}.",
        "suggest": (
            "Check the Karma render settings and ensure all referenced "
            "materials and textures exist. For XPU issues, try switching "
            "to CPU mode to isolate the problem."
        ),
        "severity": "error",
    },

    # ── Cook errors ───────────────────────────────────────────────────────
    {
        "pattern": r"Maximum recursion depth exceeded",
        "category": "recursion",
        "explain": (
            "A circular dependency was detected -- nodes are referencing "
            "each other in a loop, causing infinite recursion."
        ),
        "suggest": (
            "Look for feedback loops in node connections or channel "
            "references that point back to the same node. Use the "
            "dependency graph (RMB > Show Dependencies) to trace the cycle."
        ),
        "severity": "critical",
    },
    {
        "pattern": r"SOP cook error:\s*(.+)",
        "category": "sop_cook",
        "explain": "A SOP node failed to cook: {match_1}.",
        "suggest": (
            "Click on the erroring node and check the info panel for "
            "details. Common causes: missing inputs, invalid group names, "
            "or incompatible geometry types."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Error cooking DOP",
        "category": "dop_cook",
        "explain": (
            "A simulation (DOP) node failed to cook. This can happen "
            "when simulation parameters are invalid or inputs are missing."
        ),
        "suggest": (
            "Check the DOP network for red nodes. Verify that all "
            "collision geometry and force inputs are connected. Try "
            "resetting the simulation (Ctrl+Shift+Up) and recooking."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Cook error in\s+(.+)",
        "category": "cook_error",
        "explain": "Node {match_1} failed to cook.",
        "suggest": (
            "Select the node and press MMB to see cook details. Check "
            "for missing inputs, invalid parameters, or upstream errors "
            "that may have cascaded down."
        ),
        "severity": "error",
    },

    # ── File / path errors ────────────────────────────────────────────────
    {
        "pattern": r"Permission denied:\s*(.+)",
        "category": "permission",
        "explain": (
            "Houdini doesn't have permission to access {match_1}."
        ),
        "suggest": (
            "Check file permissions and make sure Houdini isn't trying "
            "to write to a read-only location. On Windows, try running "
            "Houdini as administrator if the file is in a protected folder."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Error loading texture\s+(.+)",
        "category": "texture_error",
        "explain": (
            "Houdini couldn't load the texture at {match_1}."
        ),
        "suggest": (
            "Verify the file exists and is a supported format (EXR, PNG, "
            "JPG, HDR, TIFF). Check that the path uses forward slashes "
            "or $HIP/$JOB variables correctly."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Cannot find asset\s+(.+)",
        "category": "missing_hda",
        "explain": (
            "Houdini can't locate the digital asset (HDA) {match_1}."
        ),
        "suggest": (
            "Make sure the HDA file is installed in a scanned OTL "
            "directory. Check File > Asset Manager for registered paths. "
            "The HDA may need to be reinstalled or the path updated."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Unable to read file\s+(.+)",
        "category": "file_not_found",
        "explain": (
            "Houdini couldn't read the file at {match_1}. It may not "
            "exist, or the path may be incorrect."
        ),
        "suggest": (
            "Double-check the file path -- look for typos, missing drive "
            "letters, or incorrect $HIP/$JOB variables. Verify the file "
            "exists on disk."
        ),
        "severity": "error",
    },

    # ── General errors ────────────────────────────────────────────────────
    {
        "pattern": r"Node\s+(.+)\s+is not installed",
        "category": "missing_node",
        "explain": (
            "The node type {match_1} isn't available in this Houdini "
            "installation."
        ),
        "suggest": (
            "This usually means a required plugin or HDA isn't installed. "
            "Check if you need a specific Houdini product (Core vs FX) "
            "or a third-party plugin for this node type."
        ),
        "severity": "error",
    },
    {
        "pattern": r"Invalid group name\s+(.+)",
        "category": "bad_group",
        "explain": (
            "The group name {match_1} doesn't exist on the input geometry."
        ),
        "suggest": (
            "Check that the group was created upstream and spelled "
            "correctly. Group names are case-sensitive. Use the Geometry "
            "Spreadsheet to see available groups."
        ),
        "severity": "warning",
    },
]


# ---------------------------------------------------------------------------
# Compile patterns at module level
# ---------------------------------------------------------------------------
ERROR_PATTERNS: list[dict] = []

for _entry in _RAW_PATTERNS:
    compiled = dict(_entry)
    compiled["_compiled"] = re.compile(_entry["pattern"], re.IGNORECASE)
    ERROR_PATTERNS.append(compiled)

# Clean up module namespace
del _entry


# ---------------------------------------------------------------------------
# Core translation functions
# ---------------------------------------------------------------------------

def translate_error(error_text: str) -> Optional[dict]:
    """Match an error string against known patterns and return a translation.

    Returns a dict with explanation and suggestion on first match, or None
    if no pattern matches.  Pattern matching is case-insensitive.
    """
    if not error_text:
        return None

    for entry in ERROR_PATTERNS:
        m = entry["_compiled"].search(error_text)
        if m:
            # Build substitution dict from regex groups
            subs = {
                f"match_{i}": g
                for i, g in enumerate(m.groups(), start=1)
            }

            explanation = entry["explain"].format(**subs) if subs else entry["explain"]
            suggestion = entry["suggest"].format(**subs) if subs else entry["suggest"]

            return {
                "original": error_text,
                "category": entry["category"],
                "explanation": explanation,
                "suggestion": suggestion,
                "severity": entry["severity"],
                "matched_pattern": entry["category"],
            }

    return None


def translate_tool_error(tool_name: str, error_text: str) -> str:
    """Wrap translate_error with tool context and coaching tone.

    Returns a formatted plain-English string.  If no pattern matches,
    returns a generic message preserving the raw error.
    """
    if not error_text:
        return f"The {tool_name} tool returned an empty error."

    result = translate_error(error_text)

    if result:
        return (
            f"The {tool_name} tool hit a snag: {result['explanation']} "
            f"{result['suggestion']}"
        )

    # No pattern matched -- generic fallback with coaching tone
    return f"The {tool_name} tool returned an error: {error_text}"


# ---------------------------------------------------------------------------
# Node context gathering (requires hou -- lazy import)
# ---------------------------------------------------------------------------

def get_error_context(node_path: str) -> dict:
    """Gather context about an erroring node for diagnostic purposes.

    Returns a dict with node metadata, errors, warnings, and connection
    info.  If hou is unavailable, returns a minimal dict with just the
    node_path.
    """
    result: dict = {
        "node_path": node_path,
        "node_type": "unknown",
        "errors": [],
        "warnings": [],
        "input_types": [],
        "parm_count": 0,
        "has_expression": False,
        "cook_count": 0,
    }

    try:
        import hou  # noqa: F811 -- lazy import, no module-level hou
    except ImportError:
        return result

    try:
        node = hou.node(node_path)
        if node is None:
            result["errors"] = [f"Node not found: {node_path}"]
            return result

        result["node_type"] = node.type().name()
        result["errors"] = list(node.errors())
        result["warnings"] = list(node.warnings())

        # Input connection types
        for inp in node.inputs():
            if inp is not None:
                result["input_types"].append(inp.type().name())

        # Parameter info
        parms = node.parms()
        result["parm_count"] = len(parms)

        # Check for expressions on any parameter
        for p in parms:
            try:
                if p.expression():
                    result["has_expression"] = True
                    break
            except hou.OperationFailed:
                # No expression on this parm -- normal
                pass

        result["cook_count"] = node.cookCount()

    except Exception as exc:
        result["errors"].append(f"Context gathering failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# HTML formatting for panel display
# ---------------------------------------------------------------------------

def format_translation_html(translation: dict) -> str:
    """Format a translation result as styled HTML for the chat panel.

    Uses the SYNAPSE coaching tone with severity-colored left border.
    """
    severity = translation.get("severity", "error")
    border_color = _SEVERITY_COLORS.get(severity, _ERROR)

    explanation = html.escape(translation.get("explanation", ""))
    suggestion = html.escape(translation.get("suggestion", ""))
    category = html.escape(translation.get("category", ""))

    # Coaching-tone header based on severity
    if severity == "critical":
        header = "We hit a serious snag"
    elif severity == "warning":
        header = "Heads up"
    else:
        header = "We hit a snag"

    return (
        f'<div style="'
        f"border-left: 3px solid {border_color}; "
        f"padding: 8px 12px; "
        f"margin: 4px 0; "
        f"background: {_CARBON}; "
        f"border-radius: 4px; "
        f"font-family: '{_FONT_MONO}', Consolas, monospace; "
        f'">'
        f'<div style="'
        f"color: {border_color}; "
        f"font-size: {_SMALL_PX}px; "
        f"font-weight: bold; "
        f"margin-bottom: 4px; "
        f'">'
        f"{header} ({category})"
        f"</div>"
        f'<div style="'
        f"color: {_TEXT}; "
        f"font-size: {_BODY_PX}px; "
        f"margin-bottom: 6px; "
        f'">'
        f"Looks like {explanation}"
        f"</div>"
        f'<div style="'
        f"color: {_TEXT_DIM}; "
        f"font-size: {_SMALL_PX}px; "
        f'">'
        f"{suggestion}"
        f"</div>"
        f"</div>"
    )
