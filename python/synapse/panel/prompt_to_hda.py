"""Prompt-to-HDA workflow module for the SYNAPSE panel.

Provides the orchestration layer that helps Claude design good HDAs from
natural language descriptions. Includes:

- ``HDA_DESIGN_PROMPT``: System prompt addendum injected when /hda is active
- ``HDA_RECIPES``: Fast-path recipe lookup for common HDA patterns
- ``parse_hda_command()``: Parse /hda command input from the user
- ``build_hda_messages()``: Build the message list for the design conversation
- ``default_save_path()``: Resolve a sensible save path for the .hda file
"""

import os
import re

# ---------------------------------------------------------------------------
# HDA Recipes -- fast-path patterns keyed by keyword
# ---------------------------------------------------------------------------

HDA_RECIPES = {
    "scatter": {
        "category": "Sop",
        "nodes": [
            {"type": "grid", "name": "grid1", "parms": {"sizex": 10.0, "sizey": 10.0, "rows": 50, "cols": 50}},
            {"type": "scatter", "name": "scatter1", "parms": {"npts": 5000}},
            {"type": "copytopoints", "name": "copytopoints1", "parms": {}},
            {"type": "null", "name": "OUT", "parms": {}},
        ],
        "connections": [
            ["grid1", "scatter1", "0"],
            ["__input0", "copytopoints1", "0"],
            ["scatter1", "copytopoints1", "1"],
            ["copytopoints1", "OUT", "0"],
        ],
        "promoted_parms": [
            {"node": "grid1", "parm": "sizex", "label": "Grid Width"},
            {"node": "grid1", "parm": "sizey", "label": "Grid Height"},
            {"node": "scatter1", "parm": "npts", "label": "Point Count"},
            {"node": "scatter1", "parm": "seed", "label": "Random Seed"},
        ],
    },

    "fracture": {
        "category": "Sop",
        "nodes": [
            {"type": "voronoifracture", "name": "fracture1", "parms": {"npts": 20}},
            {"type": "assemble", "name": "assemble1", "parms": {"create_packed": 1}},
            {"type": "null", "name": "OUT", "parms": {}},
        ],
        "connections": [
            ["__input0", "fracture1", "0"],
            ["fracture1", "assemble1", "0"],
            ["assemble1", "OUT", "0"],
        ],
        "promoted_parms": [
            {"node": "fracture1", "parm": "npts", "label": "Fracture Pieces"},
            {"node": "fracture1", "parm": "seed", "label": "Random Seed"},
            {"node": "assemble1", "parm": "create_packed", "label": "Pack Pieces"},
        ],
    },

    "deform": {
        "category": "Sop",
        "nodes": [
            {"type": "mountain", "name": "mountain1", "parms": {"height": 0.5, "freq": 2.0}},
            {"type": "smooth", "name": "smooth1", "parms": {"iterations": 10}},
            {"type": "null", "name": "OUT", "parms": {}},
        ],
        "connections": [
            ["__input0", "mountain1", "0"],
            ["mountain1", "smooth1", "0"],
            ["smooth1", "OUT", "0"],
        ],
        "promoted_parms": [
            {"node": "mountain1", "parm": "height", "label": "Noise Amplitude"},
            {"node": "mountain1", "parm": "freq", "label": "Noise Frequency"},
            {"node": "smooth1", "parm": "iterations", "label": "Smooth Iterations"},
        ],
    },

    "uv_layout": {
        "category": "Sop",
        "nodes": [
            {"type": "uvflatten", "name": "uvflatten1", "parms": {}},
            {"type": "uvlayout", "name": "uvlayout1", "parms": {"padding": 0.005}},
            {"type": "null", "name": "OUT", "parms": {}},
        ],
        "connections": [
            ["__input0", "uvflatten1", "0"],
            ["uvflatten1", "uvlayout1", "0"],
            ["uvlayout1", "OUT", "0"],
        ],
        "promoted_parms": [
            {"node": "uvlayout1", "parm": "padding", "label": "Island Padding"},
        ],
    },

    "light_rig": {
        "category": "Lop",
        "nodes": [
            {
                "type": "light::2.0", "name": "key_light",
                "parms": {
                    "lighttype": "distant",
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": 1.0,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "light::2.0", "name": "fill_light",
                "parms": {
                    "lighttype": "distant",
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": -0.585,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "domelight::2.0", "name": "dome_light",
                "parms": {
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": 0.25,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {"type": "merge", "name": "light_merge", "parms": {}},
        ],
        "connections": [
            ["key_light", "light_merge", "0"],
            ["fill_light", "light_merge", "1"],
            ["dome_light", "light_merge", "2"],
        ],
        "promoted_parms": [
            {"node": "key_light", "parm": "xn__inputsexposure_vya", "label": "Key Exposure"},
            {"node": "fill_light", "parm": "xn__inputsexposure_vya", "label": "Fill Exposure"},
            {"node": "dome_light", "parm": "xn__inputsexposure_vya", "label": "Dome Exposure"},
        ],
    },

    "material_setup": {
        "category": "Lop",
        "nodes": [
            {"type": "materiallibrary", "name": "matlib1", "parms": {}},
            {"type": "assignmaterial", "name": "assign1", "parms": {}},
            {"type": "null", "name": "OUT", "parms": {}},
        ],
        "connections": [
            ["__input0", "matlib1", "0"],
            ["matlib1", "assign1", "0"],
            ["assign1", "OUT", "0"],
        ],
        "promoted_parms": [],
    },
}


# ---------------------------------------------------------------------------
# HDA Design Prompt -- injected into system prompt when /hda is active
# ---------------------------------------------------------------------------

HDA_DESIGN_PROMPT = """\
## HDA Design Mode

You are now in HDA design mode. The artist wants you to design and build a
Houdini Digital Asset (HDA) from their description. Follow these principles
and use the `hda_package` tool to create the HDA.

### Design Principles

1. **Clean parameter interface** -- only expose what the artist needs to control.
   Internal plumbing stays hidden. Every promoted parameter should have a
   descriptive label, not the raw internal name.
2. **Sensible defaults** -- every parameter must have a reasonable default value
   so the HDA works out of the box without any tweaking.
3. **Standard nodes only** -- build the internal network from standard Houdini
   nodes (SOPs, LOPs, etc.). Do NOT use `execute_python` or `attribwrangle`
   with complex VEX unless explicitly requested. Keep it maintainable.
4. **Naming conventions**:
   - `operator_name`: lowercase_underscore (e.g. `scatter_on_surface`)
   - `operator_label`: Title Case (e.g. `Scatter On Surface`)
   - Node names inside: descriptive lowercase (e.g. `scatter1`, `grid_base`)
5. **Version**: always start at `1.0.0`.
6. **Save path**: default to `$HIP/hda/<name>.hda`. If no `$HIP` is set,
   use `$HOUDINI_USER_PREF_DIR/hda/<name>.hda`.
7. **Finish with a null node named OUT** -- set display/render flags on it.
   This is standard Houdini practice for clean subnet outputs.
8. **Inputs**: use `__input0` as the source name for the first subnet input,
   `__input1` for the second, etc. Only add inputs when the HDA needs
   upstream geometry.

### Category Selection Guide

Choose the category based on what the HDA does:

| Category   | When to Use                                          | Examples                               |
|------------|------------------------------------------------------|----------------------------------------|
| **Sop**    | Geometry operations (most common)                    | Scatter, fracture, deform, UV, meshing |
| **Lop**    | USD / Solaris scene composition                      | Light rigs, material setup, render     |
| **Object** | Object-level containers (rare for HDAs)              | Character rig, asset container         |
| **Driver** | Render / output operators                            | Custom render submit, export pipeline  |
| **Top**    | PDG / TOPS task graph operators                      | Batch processing, wedging              |

Most artist requests will be **Sop** or **Lop**. Default to **Sop** if unclear.

### Common SOP Recipes

Use these as starting points when the request matches:

- **Scatter points on surface**: grid -> scatter -> copytopoints -> OUT
  Promote: grid size, point count, seed
- **Deform geometry**: input -> mountain -> smooth -> OUT
  Promote: amplitude, frequency, smooth iterations
- **Fracture**: input -> voronoifracture -> assemble -> OUT
  Promote: piece count, seed, pack option
- **UV layout**: input -> uvflatten -> uvlayout -> OUT
  Promote: island padding
- **Remesh**: input -> remesh -> OUT
  Promote: target edge length
- **Boolean**: input0 + input1 -> boolean -> OUT
  Promote: operation type (union/intersect/subtract)

### Common LOP Recipes

- **Light rig**: key_light + fill_light + dome_light -> merge
  Promote: each light's exposure. Intensity always 1.0 (Lighting Law).
  Use `light::2.0` for directional, `domelight::2.0` for environment.
  Exposure controls brightness -- NEVER set intensity above 1.0.
- **Material setup**: materiallibrary -> assignmaterial -> OUT
  Promote: material paths, geometry assignments
- **Render setup**: karmarenderproperties -> OUT
  Promote: pixel samples, convergence mode

### Parameter Promotion Rules

1. **Promote the primary control** of each internal node -- the parameter
   the artist is most likely to adjust.
2. **Group related parameters** by using descriptive labels that form a
   logical reading order.
3. **Use descriptive labels**: "Point Count" not "npts", "Noise Amplitude"
   not "height", "Random Seed" not "seed".
4. **Include min/max context** in the label when helpful:
   "Smooth Iterations (1-100)" for iteration counts.

### hda_package Tool Schema

Call the `hda_package` tool with this structure:

```json
{
  "description": "What the HDA does (free text)",
  "name": "operator_name_lowercase",
  "category": "Sop",
  "save_path": "$HIP/hda/operator_name.hda",
  "inputs": ["Input geometry description"],
  "nodes": [
    {"type": "node_type", "name": "node_name", "parms": {"parm": value}},
    {"type": "null", "name": "OUT", "parms": {}}
  ],
  "connections": [
    ["__input0", "first_node", "0"],
    ["first_node", "second_node", "0"],
    ["second_node", "OUT", "0"]
  ],
  "promoted_parms": [
    {"node": "node_name", "parm": "parm_name", "label": "Artist-Friendly Label"}
  ]
}
```

**Connection format**: `[source_name, destination_name, destination_input_index]`
- Use `"__input0"` for the first subnet input, `"__input1"` for the second
- `destination_input_index` is a string (e.g. `"0"`, `"1"`)

### Workflow

1. Analyze the artist's description
2. Choose the right category (Sop/Lop/Object/Driver/Top)
3. Design the internal node network (types, names, default parm values)
4. Decide which parameters to promote (artist-facing controls)
5. Set up connections (linear chain or branching as needed)
6. Call `hda_package` with the complete specification
7. Report the result: HDA path, operator type, promoted parameters
"""


# ---------------------------------------------------------------------------
# Command parser
# ---------------------------------------------------------------------------

_HDA_CMD_PATTERN = re.compile(
    r"^/hda\s+(.+)$",
    re.IGNORECASE | re.DOTALL,
)


def parse_hda_command(text: str) -> dict:
    """Parse a ``/hda`` command string into a structured dict.

    Parameters
    ----------
    text : str
        The raw command text, e.g. ``"/hda scatter points on a grid"``.

    Returns
    -------
    dict
        ``{"description": str, "raw": str}`` on success,
        ``{"description": "", "raw": str}`` if no description was provided.
    """
    text = text.strip()
    match = _HDA_CMD_PATTERN.match(text)
    if match:
        description = match.group(1).strip()
    else:
        description = ""
    return {
        "description": description,
        "raw": text,
    }


# ---------------------------------------------------------------------------
# Message builder
# ---------------------------------------------------------------------------

def build_hda_messages(description: str, context: dict | None = None) -> list:
    """Build the initial message list for the HDA design conversation.

    Parameters
    ----------
    description : str
        The artist's natural language description of the desired HDA.
    context : dict, optional
        Scene context dict. Recognized keys:

        - ``network`` (str): Current network path (e.g. ``"/obj/geo1"``)
        - ``selected_nodes`` (list[str]): Currently selected node paths
        - ``hip_path`` (str): Current HIP file path

    Returns
    -------
    list[dict]
        A list of message dicts suitable for the Anthropic API.
    """
    if context is None:
        context = {}

    network = context.get("network", "/obj")
    selected = context.get("selected_nodes", [])
    hip_path = context.get("hip_path", "")

    parts = [f"Design and build an HDA: {description}"]

    if network:
        parts.append(f"Current network context: {network}")

    if selected:
        parts.append(f"Selected nodes: {', '.join(selected)}")

    if hip_path:
        parts.append(f"HIP file: {hip_path}")

    parts.append(
        "Use the hda_package tool to create it. "
        "Save to $HIP/hda/ if no path specified."
    )

    user_content = "\n".join(parts)

    return [
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Default save path
# ---------------------------------------------------------------------------

def default_save_path(name: str) -> str:
    """Return a default save path for an HDA file.

    Tries ``$HIP/hda/<name>.hda`` first (requires ``hou`` module).
    Falls back to ``$HOUDINI_USER_PREF_DIR/hda/<name>.hda``.
    Creates the parent directory if it does not exist.

    Parameters
    ----------
    name : str
        The operator name (e.g. ``"scatter_on_surface"``).

    Returns
    -------
    str
        Absolute path to the .hda file.
    """
    hda_dir = None

    # Try $HIP/hda/ via hou module
    try:
        import hou
        hip = hou.getenv("HIP")
        if hip:
            hda_dir = os.path.join(hip, "hda")
    except ImportError:
        pass

    # Fallback: $HOUDINI_USER_PREF_DIR/hda/
    if hda_dir is None:
        pref_dir = os.environ.get("HOUDINI_USER_PREF_DIR", "")
        if not pref_dir:
            # Best-effort default
            pref_dir = os.path.expanduser("~/houdini21.0")
        hda_dir = os.path.join(pref_dir, "hda")

    # Ensure directory exists
    os.makedirs(hda_dir, exist_ok=True)

    return os.path.join(hda_dir, f"{name}.hda")
