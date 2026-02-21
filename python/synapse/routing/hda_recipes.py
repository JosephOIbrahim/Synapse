"""HDA recipe definitions for prompt-to-HDA generation.

Each recipe is a structured specification that ``hda_package`` can execute:
node types, connections, promoted parameters, and quality presets.

Recipes are matched by keyword overlap between the user's prompt and
the recipe's name/description. The controller in ``hda_controller.py``
handles the matching logic.
"""

# Category mapping: user-facing context -> Houdini internal category
CONTEXT_TO_CATEGORY = {
    "SOP": "Sop",
    "LOP": "Lop",
    "DOP": "Dop",
    "COP": "Cop2",
    "TOP": "Top",
}


HDA_RECIPES = {
    # ── SOP Recipes ─────────────────────────────────────────────

    "sop_scatter": {
        "name": "scatter_points",
        "context": "SOP",
        "description": "Scatter points on a surface with density and seed control",
        "node_graph": [
            {
                "type": "scatter",
                "name": "scatter1",
                "parms": {"npts": 10000},
            },
            {
                "type": "null",
                "name": "OUT",
                "parms": {},
            },
        ],
        "connections": [
            ["__input0", "scatter1", "0"],
            ["scatter1", "OUT", "0"],
        ],
        "promote_parameters": [
            {
                "node": "scatter1",
                "parm": "npts",
                "label": "Point Count",
            },
            {
                "node": "scatter1",
                "parm": "seed",
                "label": "Random Seed",
            },
        ],
    },

    "sop_deformer": {
        "name": "noise_deformer",
        "context": "SOP",
        "description": "Deform geometry with noise displacement bend twist wave",
        "node_graph": [
            {
                "type": "mountain",
                "name": "mountain1",
                "parms": {"height": 0.5, "freq": 2.0},
            },
            {
                "type": "null",
                "name": "OUT",
                "parms": {},
            },
        ],
        "connections": [
            ["__input0", "mountain1", "0"],
            ["mountain1", "OUT", "0"],
        ],
        "promote_parameters": [
            {
                "node": "mountain1",
                "parm": "height",
                "label": "Amplitude",
            },
            {
                "node": "mountain1",
                "parm": "freq",
                "label": "Frequency",
            },
        ],
    },

    # ── LOP Recipes ─────────────────────────────────────────────

    "lop_light_rig": {
        "name": "three_point_light_rig",
        "context": "LOP",
        "description": (
            "3-point light rig with key fill and rim lights plus dome "
            "lighting setup studio"
        ),
        "node_graph": [
            {
                "type": "light::2.0",
                "name": "key_light",
                "parms": {
                    "lighttype": "distant",
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": 1.0,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "light::2.0",
                "name": "fill_light",
                "parms": {
                    "lighttype": "distant",
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": -0.585,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "light::2.0",
                "name": "rim_light",
                "parms": {
                    "lighttype": "distant",
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": 0.4,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "domelight::2.0",
                "name": "dome_light",
                "parms": {
                    "xn__inputsintensity_i0a": 1.0,
                    "xn__inputsexposure_vya": 0.25,
                    "xn__inputsexposure_control_wcb": "set",
                },
            },
            {
                "type": "merge",
                "name": "light_merge",
                "parms": {},
            },
        ],
        "connections": [
            ["key_light", "light_merge", "0"],
            ["fill_light", "light_merge", "1"],
            ["rim_light", "light_merge", "2"],
            ["dome_light", "light_merge", "3"],
        ],
        "promote_parameters": [
            {
                "node": "key_light",
                "parm": "xn__inputsexposure_vya",
                "label": "Key Exposure",
            },
            {
                "node": "fill_light",
                "parm": "xn__inputsexposure_vya",
                "label": "Fill Exposure",
            },
            {
                "node": "rim_light",
                "parm": "xn__inputsexposure_vya",
                "label": "Rim Exposure",
            },
            {
                "node": "dome_light",
                "parm": "xn__inputsexposure_vya",
                "label": "Dome Exposure",
            },
        ],
    },

    "lop_karma_quality": {
        "name": "karma_render_setup",
        "context": "LOP",
        "description": (
            "Karma XPU render with draft preview production quality presets "
            "render setup resolution samples"
        ),
        "node_graph": [
            {
                "type": "karmarenderproperties",
                "name": "render_settings",
                "parms": {
                    "karma:global:pathtracedsamples": 64,
                    "karma:global:convergencemode": "automatic",
                },
            },
            {
                "type": "null",
                "name": "OUT",
                "parms": {},
            },
        ],
        "connections": [
            ["__input0", "render_settings", "0"],
            ["render_settings", "OUT", "0"],
        ],
        "promote_parameters": [
            {
                "node": "render_settings",
                "parm": "karma:global:pathtracedsamples",
                "label": "Pixel Samples",
            },
        ],
        "quality_presets": {
            "draft": {
                "karma:global:pathtracedsamples": 16,
            },
            "preview": {
                "karma:global:pathtracedsamples": 64,
            },
            "production": {
                "karma:global:pathtracedsamples": 256,
            },
        },
    },

    "lop_material_assign": {
        "name": "material_assignment",
        "context": "LOP",
        "description": (
            "Material library with assignment material assign shader "
            "principled surface"
        ),
        "node_graph": [
            {
                "type": "materiallibrary",
                "name": "matlib1",
                "parms": {},
            },
            {
                "type": "null",
                "name": "OUT",
                "parms": {},
            },
        ],
        "connections": [
            ["__input0", "matlib1", "0"],
            ["matlib1", "OUT", "0"],
        ],
        "promote_parameters": [],
    },
}


def get_recipe(key):
    """Look up a recipe by key. Returns None if not found."""
    return HDA_RECIPES.get(key)


def list_recipes():
    """Return a summary of all available recipes."""
    return [
        {
            "key": key,
            "name": recipe["name"],
            "context": recipe["context"],
            "description": recipe["description"],
        }
        for key, recipe in sorted(HDA_RECIPES.items())
    ]
