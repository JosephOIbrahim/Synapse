"""Recipe Book module for SYNAPSE.

Organized, buildable network patterns that artists can browse, explain,
or build directly inside Houdini. Each recipe defines nodes, connections,
key parameters, and explanatory context.

Usage:
    /recipes                          - List all categories
    /recipes scatter                  - List recipes in category
    /recipes scatter uniform_scatter  - Show recipe detail
    /recipes build scatter uniform_scatter - Build the recipe
    /recipes search noise             - Search all recipes
"""

import html
import re

# -- Design tokens (fallback for standalone use) ------------------------------
try:
    from synapse.panel import tokens as _t
    _SIGNAL = _t.SIGNAL
    _TEXT = _t.TEXT
    _TEXT_DIM = _t.TEXT_DIM
    _SUCCESS = _t.GROW
    _WARNING = _t.WARN
    _BODY_PX = _t.SIZE_BODY
    _SMALL_PX = _t.SIZE_SMALL
    _FONT_SANS = _t.FONT_SANS
except ImportError:
    _SIGNAL = "#00D4FF"
    _TEXT = "#E0E0E0"
    _TEXT_DIM = "#999999"
    _SUCCESS = "#00E676"
    _WARNING = "#FFAB00"
    _BODY_PX = 26
    _SMALL_PX = 22
    _FONT_SANS = "DM Sans"


# =============================================================================
# RECIPES -- The canonical recipe database
# =============================================================================

RECIPES = {
    # -------------------------------------------------------------------------
    # SCATTER
    # -------------------------------------------------------------------------
    "scatter": {
        "uniform_scatter": {
            "title": "Uniform Scatter",
            "description": "Basic point scatter on a grid surface",
            "context": "SOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "grid", "name": "grid1", "parms": {"rows": 50, "cols": 50, "sizex": 10, "sizey": 10}},
                {"type": "scatter", "name": "scatter1", "parms": {"npts": 1000}},
            ],
            "connections": [["grid1", "scatter1", 0]],
            "key_parms": ["npts", "rows", "cols"],
            "explanation": (
                "Creates a grid and scatters points uniformly across its surface. "
                "The scatter SOP distributes points based on primitive area by default, "
                "giving even coverage across the mesh."
            ),
            "tips": [
                "Increase grid rows/cols for smoother scatter distribution",
                "Use the 'Relax Iterations' parm on scatter to reduce clumping",
                "Pipe the output into a Copy to Points for instancing",
            ],
        },
        "density_scatter": {
            "title": "Density-Painted Scatter",
            "description": "Scatter driven by a painted density attribute",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "grid", "name": "grid1", "parms": {"rows": 50, "cols": 50, "sizex": 10, "sizey": 10}},
                {"type": "attribpaint", "name": "paint_density", "parms": {"attribname": "density", "attribtype": 2}},
                {"type": "scatter", "name": "scatter1", "parms": {"npts": 5000, "densityattrib": "density", "usedensityattrib": 1}},
            ],
            "connections": [
                ["grid1", "paint_density", 0],
                ["paint_density", "scatter1", 0],
            ],
            "key_parms": ["npts", "densityattrib", "attribname"],
            "explanation": (
                "Paints a density attribute onto a grid, then uses it to control "
                "scatter distribution. Areas with higher density values receive more "
                "points, allowing artistic control over point placement."
            ),
            "tips": [
                "Paint density values between 0 and 1 for predictable results",
                "Use a Volume VOP or Attribute VOP for procedural density instead of painting",
                "Combine with Copy to Points and vary instance scale by density",
            ],
        },
        "poisson_scatter": {
            "title": "Poisson Disk Scatter",
            "description": "Relaxed scatter with minimum distance between points",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "grid", "name": "grid1", "parms": {"rows": 50, "cols": 50, "sizex": 10, "sizey": 10}},
                {"type": "scatter", "name": "scatter1", "parms": {"npts": 500, "relaxiterations": 50}},
            ],
            "connections": [["grid1", "scatter1", 0]],
            "key_parms": ["npts", "relaxiterations"],
            "explanation": (
                "Produces a blue-noise distribution by using high relax iterations "
                "on the scatter SOP. Points maintain a minimum distance from each "
                "other, avoiding both clumping and regular grid artifacts."
            ),
            "tips": [
                "Higher relax iterations give better Poisson distribution but cook slower",
                "50+ iterations is a good starting point for quality",
                "Useful for foliage placement where natural spacing matters",
            ],
        },
        "weighted_scatter": {
            "title": "Texture-Weighted Scatter",
            "description": "Scatter distribution controlled by a texture map",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "grid", "name": "grid1", "parms": {"rows": 50, "cols": 50, "sizex": 10, "sizey": 10}},
                {"type": "uvtexture", "name": "uvtexture1", "parms": {}},
                {"type": "attribfrommap", "name": "attribfrommap1", "parms": {"attribname": "density"}},
                {"type": "scatter", "name": "scatter1", "parms": {"npts": 5000, "densityattrib": "density", "usedensityattrib": 1}},
            ],
            "connections": [
                ["grid1", "uvtexture1", 0],
                ["uvtexture1", "attribfrommap1", 0],
                ["attribfrommap1", "scatter1", 0],
            ],
            "key_parms": ["npts", "densityattrib", "attribname"],
            "explanation": (
                "Applies UV coordinates, samples a texture map into a density "
                "attribute, then scatters points weighted by that density. White "
                "areas of the texture get more points, black areas get fewer."
            ),
            "tips": [
                "Use a grayscale texture for clearest control",
                "The texture path is set on the Attribute from Map SOP",
                "Combine with COP networks for procedural density textures",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # VOLUMES
    # -------------------------------------------------------------------------
    "volumes": {
        "pyro_basic": {
            "title": "Basic Pyro Simulation",
            "description": "Simple pyro source with smoke/fire solver",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "sphere", "name": "sphere1", "parms": {"rad": [0.5, 0.5, 0.5]}},
                {"type": "pyrosource", "name": "pyrosource1", "parms": {"mode": 0}},
                {"type": "pyrosolver", "name": "pyrosolver1", "parms": {"timescale": 1.0}},
                {"type": "output", "name": "OUT_pyro", "parms": {}},
            ],
            "connections": [
                ["sphere1", "pyrosource1", 0],
                ["pyrosource1", "pyrosolver1", 0],
                ["pyrosolver1", "OUT_pyro", 0],
            ],
            "key_parms": ["timescale", "mode", "rad"],
            "explanation": (
                "Creates a sphere as the emission source, converts it to a pyro "
                "source volume, then feeds it into a pyro solver. The solver simulates "
                "buoyancy, turbulence, and dissipation to produce smoke and fire."
            ),
            "tips": [
                "Set the timeline to at least 100 frames for visible simulation",
                "Increase 'Disturbance' on the solver for more turbulent smoke",
                "Use a Volume Visualization SOP after the solver to preview density",
            ],
        },
        "vdb_from_mesh": {
            "title": "VDB from Mesh",
            "description": "Convert polygon mesh to VDB signed distance field",
            "context": "SOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {"type": "vdbfrompolygons", "name": "vdbfrompolygons1", "parms": {"voxelsize": 0.02}},
            ],
            "connections": [["rubbertoy1", "vdbfrompolygons1", 0]],
            "key_parms": ["voxelsize"],
            "explanation": (
                "Converts a polygon mesh into a VDB signed distance field. The voxel "
                "size controls resolution -- smaller values capture finer detail but "
                "use more memory. Essential for volume-based operations and collisions."
            ),
            "tips": [
                "Voxel size of 0.02 is high-res; start at 0.05 for faster iteration",
                "Enable 'Fog Volume' output for rendering volumetric effects",
                "Chain with VDB Smooth SDF to clean up noisy conversions",
            ],
        },
        "cloud_model": {
            "title": "Simple Cloud Model",
            "description": "Procedural cloud from sphere with volume noise",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "sphere", "name": "sphere1", "parms": {"rad": [2, 1, 2], "type": 2}},
                {"type": "vdbfrompolygons", "name": "vdbfrompolygons1", "parms": {"voxelsize": 0.05, "fog": 1}},
                {"type": "cloudnoise", "name": "cloudnoise1", "parms": {}},
            ],
            "connections": [
                ["sphere1", "vdbfrompolygons1", 0],
                ["vdbfrompolygons1", "cloudnoise1", 0],
            ],
            "key_parms": ["voxelsize", "rad"],
            "explanation": (
                "Starts with a flattened sphere, converts to fog VDB, then applies "
                "cloud noise to break up the shape into a natural-looking cumulus "
                "form. Adjusting the sphere radii controls the overall cloud shape."
            ),
            "tips": [
                "Flatten the sphere on Y (e.g., radii 2, 1, 2) for cumulus shapes",
                "Layer multiple cloud noise SOPs with different frequencies",
                "Render with volume shader for realistic cloud lighting",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # MATERIALS
    # -------------------------------------------------------------------------
    "materials": {
        "principled_basic": {
            "title": "Principled Shader Setup",
            "description": "Basic PBR material with principled shader in Solaris",
            "context": "LOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "materiallibrary", "name": "matlib1", "parms": {}},
                {"type": "assignmaterial", "name": "assign1", "parms": {}},
            ],
            "connections": [["matlib1", "assign1", 0]],
            "key_parms": ["basecolor", "rough", "metallic"],
            "explanation": (
                "Creates a material library with a Principled Shader inside, then "
                "assigns it to geometry. The principled shader is Houdini's standard "
                "PBR material supporting metallic/roughness workflow."
            ),
            "tips": [
                "Set basecolor to a texture path for texture-mapped materials",
                "Roughness of 0.3-0.5 gives a nice semi-glossy look",
                "Use Metallic = 1.0 only for actual metals (gold, chrome, etc.)",
            ],
        },
        "layered_material": {
            "title": "Layered Material",
            "description": "Multi-layer material with blend mask between layers",
            "context": "LOP",
            "difficulty": "advanced",
            "nodes": [
                {"type": "materiallibrary", "name": "matlib1", "parms": {}},
                {"type": "assignmaterial", "name": "assign1", "parms": {}},
            ],
            "connections": [["matlib1", "assign1", 0]],
            "key_parms": ["basecolor", "rough", "metallic", "coat_enable", "coat_rough"],
            "explanation": (
                "Builds a material with a base layer and a clearcoat overlay. The "
                "clearcoat simulates a glossy protective coating over the base "
                "material, commonly used for car paint and lacquered surfaces."
            ),
            "tips": [
                "Use coat_rough near 0 for a mirror-like clear coat",
                "Combine with a noise mask to reveal the base layer selectively",
                "For car paint: metallic base + low-roughness coat = classic look",
            ],
        },
        "procedural_texture": {
            "title": "Procedural Noise Material",
            "description": "Noise-driven procedural material without texture files",
            "context": "LOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "materiallibrary", "name": "matlib1", "parms": {}},
                {"type": "assignmaterial", "name": "assign1", "parms": {}},
            ],
            "connections": [["matlib1", "assign1", 0]],
            "key_parms": ["basecolor", "rough", "displace_enable", "displace_scale"],
            "explanation": (
                "Creates a material using procedural noise for color variation and "
                "optional displacement. No texture files needed -- everything is "
                "generated mathematically, making it resolution-independent."
            ),
            "tips": [
                "Use Unified Noise VOP inside the material for consistent noise across channels",
                "Pipe noise into roughness for natural surface variation",
                "Add displacement with small scale (0.01-0.05) for subtle surface detail",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # DEFORMATION
    # -------------------------------------------------------------------------
    "deformation": {
        "mountain_displace": {
            "title": "Mountain Displacement",
            "description": "Terrain-like displacement using Mountain SOP",
            "context": "SOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "grid", "name": "grid1", "parms": {"rows": 100, "cols": 100, "sizex": 10, "sizey": 10}},
                {"type": "mountain", "name": "mountain1", "parms": {"height": 1.5, "elementsize": 2.0}},
            ],
            "connections": [["grid1", "mountain1", 0]],
            "key_parms": ["height", "elementsize"],
            "explanation": (
                "Applies fractal noise displacement to a high-resolution grid, "
                "creating terrain-like surface variation. The Mountain SOP adds "
                "positional noise along surface normals."
            ),
            "tips": [
                "Use 100x100 grid minimum for smooth-looking terrain",
                "Layer multiple Mountain SOPs with different element sizes for realism",
                "Add an Attribute Noise afterward to break up the regularity",
            ],
        },
        "vex_deform": {
            "title": "Custom VEX Deformation",
            "description": "Point wrangle with custom deformation code",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {
                    "type": "attribwrangle",
                    "name": "deform_wrangle",
                    "parms": {
                        "snippet": (
                            "float amp = chf('amplitude');\n"
                            "float freq = chf('frequency');\n"
                            "@P.y += amp * sin(@P.x * freq + @Time * 2);\n"
                        ),
                    },
                },
            ],
            "connections": [["rubbertoy1", "deform_wrangle", 0]],
            "key_parms": ["snippet", "amplitude", "frequency"],
            "explanation": (
                "Uses an Attribute Wrangle to apply a custom VEX deformation. This "
                "example creates a sine-wave displacement along Y based on X position "
                "and time, producing an animated wave effect."
            ),
            "tips": [
                "Use chf() to create spare parameters for interactive control",
                "Access @Time for animation; @Frame for frame-based effects",
                "Combine sin/cos at different frequencies for organic deformation",
            ],
        },
        "bend_twist": {
            "title": "Bend + Twist Chain",
            "description": "Chained bend and twist deformers for organic shapes",
            "context": "SOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "tube", "name": "tube1", "parms": {"rows": 30, "cols": 20, "height": 5}},
                {"type": "bend", "name": "bend1", "parms": {"bendangle": 45}},
                {"type": "twist", "name": "twist1", "parms": {"twist": 180}},
            ],
            "connections": [
                ["tube1", "bend1", 0],
                ["bend1", "twist1", 0],
            ],
            "key_parms": ["bendangle", "twist"],
            "explanation": (
                "Chains a bend and twist deformer on a tube. The bend curves the "
                "geometry along one axis, then the twist rotates points progressively "
                "along the length, creating spiral-like organic forms."
            ),
            "tips": [
                "Increase tube rows for smoother deformation (30+ recommended)",
                "Try negative bend angles for opposite curvature",
                "Add a Smooth SOP after twist to reduce faceting artifacts",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # USD
    # -------------------------------------------------------------------------
    "usd": {
        "asset_structure": {
            "title": "Proper USD Asset Structure",
            "description": "USD asset with geometry, material, and variant sets",
            "context": "LOP",
            "difficulty": "advanced",
            "nodes": [
                {"type": "sopimport", "name": "import_geo", "parms": {}},
                {"type": "materiallibrary", "name": "matlib1", "parms": {}},
                {"type": "assignmaterial", "name": "assign1", "parms": {}},
                {"type": "configureprimitive", "name": "configure1", "parms": {"setkind": 1}},
                {"type": "usdrop", "name": "usdrop1", "parms": {}},
            ],
            "connections": [
                ["import_geo", "assign1", 0],
                ["matlib1", "assign1", 1],
                ["assign1", "configure1", 0],
                ["configure1", "usdrop1", 0],
            ],
            "key_parms": ["setkind"],
            "explanation": (
                "Builds a properly structured USD asset with geometry import, "
                "material assignment, and primitive configuration. The Configure "
                "Primitive sets the kind metadata required for correct asset resolution "
                "in production pipelines."
            ),
            "tips": [
                "Set kind to 'component' for leaf assets, 'assembly' for groups",
                "Add a Variant Block before export to create switchable variants",
                "Use Add Variant after Configure for LOD or look-dev variants",
            ],
        },
        "light_rig": {
            "title": "3-Point Light Rig",
            "description": "Classic key/fill/rim lighting setup in Solaris",
            "context": "LOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "light", "name": "key_light", "parms": {"lighttype": "distantlight", "xn__inputsexposure_vya": 1.0, "xn__inputsenableColorTemperature_k5b": 1, "xn__inputscolorTemperature_oib": 5500}},
                {"type": "light", "name": "fill_light", "parms": {"lighttype": "distantlight", "xn__inputsexposure_vya": -0.585}},
                {"type": "light", "name": "rim_light", "parms": {"lighttype": "distantlight", "xn__inputsexposure_vya": 0.5}},
                {"type": "merge", "name": "merge_lights", "parms": {}},
            ],
            "connections": [
                ["key_light", "merge_lights", 0],
                ["fill_light", "merge_lights", 1],
                ["rim_light", "merge_lights", 2],
            ],
            "key_parms": ["xn__inputsexposure_vya", "xn__inputscolorTemperature_oib", "lighttype"],
            "explanation": (
                "Creates a classic 3-point lighting setup: key light (main illumination "
                "with warm color temperature), fill light (softer, 3:1 ratio below key), "
                "and rim light (edge separation). Intensity is always 1.0 -- brightness "
                "is controlled by exposure only (Lighting Law)."
            ),
            "tips": [
                "Key:fill ratio of 3:1 = 1.585 stops difference in exposure",
                "Enable color temperature on key for natural warmth (5000-6500K)",
                "Rotate rim light 135-180 degrees from key for best edge definition",
            ],
        },
        "material_assign": {
            "title": "Material Library + Assignment",
            "description": "Material library with multiple materials and geo assignment",
            "context": "LOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "materiallibrary", "name": "matlib1", "parms": {}},
                {"type": "assignmaterial", "name": "assign1", "parms": {}},
            ],
            "connections": [["matlib1", "assign1", 0]],
            "key_parms": ["basecolor", "rough", "metallic"],
            "explanation": (
                "Creates a material library containing multiple material subnets, "
                "then assigns them to geometry prims. The material library approach "
                "keeps all materials in one node for clean organization."
            ),
            "tips": [
                "Add multiple material subnets inside the matlib for different surfaces",
                "Assign geo paths using exact USD prim paths (/asset/geo/shape)",
                "Use material overrides on the assign node for per-prim variation",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # MOTION
    # -------------------------------------------------------------------------
    "motion": {
        "trail_effect": {
            "title": "Point Trail with Fade",
            "description": "Animated trail lines from moving points with opacity fade",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "sphere", "name": "sphere1", "parms": {"rad": [0.1, 0.1, 0.1]}},
                {"type": "scatter", "name": "scatter1", "parms": {"npts": 50}},
                {
                    "type": "attribwrangle",
                    "name": "animate_pts",
                    "parms": {
                        "snippet": (
                            "@P += set(sin(@ptnum * 0.5 + @Time), "
                            "cos(@ptnum * 0.3 + @Time), 0) * 0.05;\n"
                        ),
                    },
                },
                {"type": "trail", "name": "trail1", "parms": {"traillength": 10, "result": 1}},
                {
                    "type": "attribwrangle",
                    "name": "fade_alpha",
                    "parms": {
                        "snippet": (
                            "float u = float(vertexprimindex(0, @vtxnum)) "
                            "/ max(primvertexcount(0, @primnum) - 1, 1);\n"
                            "@Alpha = u;\n"
                        ),
                    },
                },
            ],
            "connections": [
                ["sphere1", "scatter1", 0],
                ["scatter1", "animate_pts", 0],
                ["animate_pts", "trail1", 0],
                ["trail1", "fade_alpha", 0],
            ],
            "key_parms": ["traillength", "result", "npts"],
            "explanation": (
                "Scatters points on a sphere, animates them with VEX, then creates "
                "trail lines from their motion. A second wrangle fades the alpha "
                "along each trail so the tail disappears smoothly."
            ),
            "tips": [
                "Set Trail result to 'Connect as Trails' (1) for line output",
                "Increase trail length for longer motion streaks",
                "Use the Alpha attribute in a material for transparency rendering",
            ],
        },
        "velocity_blur": {
            "title": "Velocity Motion Blur",
            "description": "Proper velocity attribute setup for motion blur rendering",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {"type": "timeshift", "name": "timeshift_prev", "parms": {"frame": {"expression": "$FF - 1"}}},
                {"type": "trail", "name": "trail1", "parms": {"result": 3}},
            ],
            "connections": [
                ["rubbertoy1", "trail1", 0],
            ],
            "key_parms": ["result"],
            "explanation": (
                "Computes per-point velocity (v) attribute from frame-to-frame motion. "
                "The Trail SOP in 'Compute Velocity' mode calculates the velocity "
                "vector that renderers use for motion blur without extra render samples."
            ),
            "tips": [
                "Trail result mode 3 = 'Compute Velocity' (the v attribute)",
                "Ensure your render settings have motion blur enabled",
                "For Karma: set motion samples to 2 on the Karma render settings",
            ],
        },
    },

    # -------------------------------------------------------------------------
    # UTILITY
    # -------------------------------------------------------------------------
    "utility": {
        "uv_layout": {
            "title": "UV Flatten + Layout Pipeline",
            "description": "Automatic UV unwrap and packing for clean UVs",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {"type": "uvflatten", "name": "uvflatten1", "parms": {}},
                {"type": "uvlayout", "name": "uvlayout1", "parms": {"padding": 4}},
            ],
            "connections": [
                ["rubbertoy1", "uvflatten1", 0],
                ["uvflatten1", "uvlayout1", 0],
            ],
            "key_parms": ["padding"],
            "explanation": (
                "Automatically flattens UVs using ABF (Angle-Based Flattening), "
                "then packs UV islands efficiently into 0-1 space. The padding "
                "parameter prevents texture bleeding between islands at render time."
            ),
            "tips": [
                "Add edge selections before UV Flatten for manual seam placement",
                "Padding of 4-8 pixels prevents bleeding at common texture resolutions",
                "Use UV Visualize SOP to inspect the result in the viewport",
            ],
        },
        "lod_setup": {
            "title": "Level of Detail Setup",
            "description": "LOD chain with switch node for distance-based selection",
            "context": "SOP",
            "difficulty": "intermediate",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {"type": "polyreduce", "name": "lod_medium", "parms": {"percentage": 50}},
                {"type": "polyreduce", "name": "lod_low", "parms": {"percentage": 10}},
                {"type": "switch", "name": "lod_switch", "parms": {"input": 0}},
            ],
            "connections": [
                ["rubbertoy1", "lod_medium", 0],
                ["rubbertoy1", "lod_low", 0],
                ["rubbertoy1", "lod_switch", 0],
                ["lod_medium", "lod_switch", 1],
                ["lod_low", "lod_switch", 2],
            ],
            "key_parms": ["percentage", "input"],
            "explanation": (
                "Creates three LOD levels: full-resolution original, 50% reduced "
                "medium, and 10% reduced low. The switch node selects between them. "
                "In production, the switch input is driven by camera distance."
            ),
            "tips": [
                "Use expressions on switch input: lod based on $OBJDIST or bbox size",
                "PolyReduce 'Keep Quads' option preserves subdivision-friendly topology",
                "For USD: export each LOD as a variant instead of using switch",
            ],
        },
        "group_workflow": {
            "title": "Group Create + Transfer",
            "description": "Group-based workflow with creation and transfer between geos",
            "context": "SOP",
            "difficulty": "beginner",
            "nodes": [
                {"type": "testgeometry_rubbertoy", "name": "rubbertoy1", "parms": {}},
                {"type": "groupcreate", "name": "groupcreate1", "parms": {"groupname": "top_half", "grouptype": 0, "groupbounding": 1, "boundtype": 0}},
                {"type": "color", "name": "color1", "parms": {"colorr": 1, "colorg": 0, "colorb": 0, "group": "top_half"}},
            ],
            "connections": [
                ["rubbertoy1", "groupcreate1", 0],
                ["groupcreate1", "color1", 0],
            ],
            "key_parms": ["groupname", "grouptype", "groupbounding", "group"],
            "explanation": (
                "Creates a point group using a bounding region, then applies an "
                "operation (color) only to that group. Groups are fundamental to "
                "selective operations in Houdini -- almost every SOP has a group field."
            ),
            "tips": [
                "Use bounding box or bounding sphere for quick spatial groups",
                "VEX expression groups: @P.y > 0 for everything above origin",
                "Group Transfer SOP moves groups between different geometries by proximity",
            ],
        },
    },
}


# =============================================================================
# Command Parsing
# =============================================================================

def parse_recipe_command(text: str) -> dict:
    """Parse a /recipes command into an action dict.

    Returns:
        dict with keys: action, category, recipe, query (depending on action)

    Examples:
        "/recipes"                              -> {"action": "list", ...}
        "/recipes scatter"                      -> {"action": "category", "category": "scatter", ...}
        "/recipes scatter uniform_scatter"      -> {"action": "detail", ...}
        "/recipes build scatter uniform_scatter" -> {"action": "build", ...}
        "/recipes search noise"                 -> {"action": "search", "query": "noise"}
    """
    # Strip the command prefix
    stripped = text.strip()
    if stripped.lower().startswith("/recipes"):
        stripped = stripped[len("/recipes"):].strip()
    elif stripped.lower().startswith("/recipe"):
        stripped = stripped[len("/recipe"):].strip()

    if not stripped:
        return {"action": "list", "category": "", "recipe": ""}

    parts = stripped.split()

    # /recipes search <query>
    if parts[0].lower() == "search" and len(parts) >= 2:
        return {"action": "search", "query": " ".join(parts[1:]), "category": "", "recipe": ""}

    # /recipes build <category> <recipe>
    if parts[0].lower() == "build" and len(parts) >= 3:
        return {"action": "build", "category": parts[1].lower(), "recipe": parts[2].lower()}

    # /recipes <category> <recipe>
    if len(parts) >= 2:
        return {"action": "detail", "category": parts[0].lower(), "recipe": parts[1].lower()}

    # /recipes <category>
    return {"action": "category", "category": parts[0].lower(), "recipe": ""}


# =============================================================================
# Lookup Helpers
# =============================================================================

def get_recipe(category: str, recipe_name: str):
    """Look up a recipe by category and name. Returns the recipe dict or None."""
    cat = RECIPES.get(category)
    if cat is None:
        return None
    return cat.get(recipe_name)


def list_categories() -> list:
    """Return a sorted list of category names."""
    return sorted(RECIPES.keys())


# =============================================================================
# Search
# =============================================================================

def search_recipes(query: str) -> list:
    """Search all recipes by title, description, explanation, and tips.

    Args:
        query: Search string (case-insensitive).

    Returns:
        List of (category, recipe_name, title, match_context) tuples.
    """
    results = []
    q = query.lower()

    for cat_name in sorted(RECIPES.keys()):
        cat = RECIPES[cat_name]
        for recipe_name in sorted(cat.keys()):
            recipe = cat[recipe_name]
            matches = []

            if q in recipe["title"].lower():
                matches.append(("title", recipe["title"]))
            if q in recipe["description"].lower():
                matches.append(("description", recipe["description"]))
            if q in recipe["explanation"].lower():
                matches.append(("explanation", recipe["explanation"]))
            for tip in recipe.get("tips", []):
                if q in tip.lower():
                    matches.append(("tip", tip))
                    break  # one tip match is enough

            if matches:
                # Use the first match as context
                match_type, match_text = matches[0]
                results.append((cat_name, recipe_name, recipe["title"], match_text))

    return results


# =============================================================================
# HTML Formatting
# =============================================================================

_DIFFICULTY_COLORS = {
    "beginner": _SUCCESS,
    "intermediate": _WARNING,
    "advanced": "#FF6B6B",
}


def format_categories_html() -> str:
    """Format all categories with recipe counts as HTML."""
    lines = []
    lines.append(
        f'<div style="font-family: {_FONT_SANS}; color: {_TEXT}; '
        f'font-size: {_BODY_PX}px; line-height: 1.6;">'
    )
    lines.append(
        f'<b style="color: {_SIGNAL};">Recipe Book</b> '
        f'<span style="color: {_TEXT_DIM};">({sum(len(v) for v in RECIPES.values())} recipes)</span>'
    )
    lines.append("<br><br>")

    for cat_name in sorted(RECIPES.keys()):
        count = len(RECIPES[cat_name])
        cat_display = cat_name.replace("_", " ").title()
        lines.append(
            f'<b>{html.escape(cat_display)}</b> '
            f'<span style="color: {_TEXT_DIM};">({count} recipe{"s" if count != 1 else ""})</span><br>'
        )

    lines.append("<br>")
    lines.append(
        f'<span style="color: {_TEXT_DIM}; font-size: {_SMALL_PX}px;">'
        "Type <b>/recipes &lt;category&gt;</b> to browse a category.</span>"
    )
    lines.append("</div>")
    return "\n".join(lines)


def format_category_html(category: str) -> str:
    """Format all recipes in a category as HTML.

    Args:
        category: Category name (must exist in RECIPES).

    Returns:
        HTML string listing recipes with difficulty badges and context tags.
    """
    cat = RECIPES.get(category)
    if cat is None:
        return (
            f'<span style="color: {_WARNING};">Category "{html.escape(category)}" '
            f"not found. Try /recipes to see all categories.</span>"
        )

    cat_display = category.replace("_", " ").title()
    lines = []
    lines.append(
        f'<div style="font-family: {_FONT_SANS}; color: {_TEXT}; '
        f'font-size: {_BODY_PX}px; line-height: 1.8;">'
    )
    lines.append(f'<b style="color: {_SIGNAL};">{html.escape(cat_display)}</b><br><br>')

    for recipe_name in sorted(cat.keys()):
        recipe = cat[recipe_name]
        diff_color = _DIFFICULTY_COLORS.get(recipe["difficulty"], _TEXT_DIM)
        lines.append(
            f'<b>{html.escape(recipe_name)}</b> '
            f'<span style="color: {_TEXT_DIM};">-</span> '
            f'{html.escape(recipe["description"])} '
            f'<span style="color: {diff_color}; font-size: {_SMALL_PX}px;">'
            f'[{html.escape(recipe["difficulty"])}]</span> '
            f'<span style="color: {_TEXT_DIM}; font-size: {_SMALL_PX}px;">'
            f'{html.escape(recipe["context"])}</span>'
            "<br>"
        )

    lines.append("<br>")
    lines.append(
        f'<span style="color: {_TEXT_DIM}; font-size: {_SMALL_PX}px;">'
        f"Type <b>/recipes {html.escape(category)} &lt;recipe&gt;</b> for details, "
        f"or <b>/recipes build {html.escape(category)} &lt;recipe&gt;</b> to create it.</span>"
    )
    lines.append("</div>")
    return "\n".join(lines)


def format_recipe_html(category: str, recipe_name: str) -> str:
    """Format full recipe detail as HTML.

    Args:
        category: Category name.
        recipe_name: Recipe name within the category.

    Returns:
        HTML string with complete recipe information.
    """
    recipe = get_recipe(category, recipe_name)
    if recipe is None:
        return (
            f'<span style="color: {_WARNING};">Recipe "{html.escape(recipe_name)}" '
            f'not found in category "{html.escape(category)}".</span>'
        )

    diff_color = _DIFFICULTY_COLORS.get(recipe["difficulty"], _TEXT_DIM)

    lines = []
    lines.append(
        f'<div style="font-family: {_FONT_SANS}; color: {_TEXT}; '
        f'font-size: {_BODY_PX}px; line-height: 1.6;">'
    )

    # Header
    lines.append(
        f'<b style="color: {_SIGNAL}; font-size: {_BODY_PX + 2}px;">'
        f'{html.escape(recipe["title"])}</b><br>'
    )
    lines.append(
        f'<span style="color: {_TEXT_DIM};">{html.escape(recipe["description"])}</span><br>'
    )
    lines.append(
        f'<span style="color: {diff_color}; font-size: {_SMALL_PX}px;">'
        f'{html.escape(recipe["difficulty"])}</span> '
        f'<span style="color: {_TEXT_DIM}; font-size: {_SMALL_PX}px;">'
        f'| {html.escape(recipe["context"])}</span>'
    )
    lines.append("<br><br>")

    # Nodes
    lines.append(f'<b style="color: {_SIGNAL};">Nodes</b><br>')
    for node in recipe["nodes"]:
        parm_summary = ""
        if node.get("parms"):
            parm_strs = []
            for k, v in sorted(node["parms"].items()):
                if k == "snippet":
                    parm_strs.append("snippet=...")
                else:
                    parm_strs.append(f"{k}={v}")
            parm_summary = f' <span style="color: {_TEXT_DIM};">({", ".join(parm_strs)})</span>'
        lines.append(
            f'&bull; <b>{html.escape(node["name"])}</b> '
            f'<span style="color: {_TEXT_DIM};">[{html.escape(node["type"])}]</span>'
            f'{parm_summary}<br>'
        )
    lines.append("<br>")

    # Key parameters
    if recipe.get("key_parms"):
        lines.append(f'<b style="color: {_SIGNAL};">Key Parameters</b><br>')
        lines.append(
            f'<span style="color: {_TEXT_DIM};">'
            + ", ".join(html.escape(p) for p in recipe["key_parms"])
            + "</span><br><br>"
        )

    # Explanation
    lines.append(f'<b style="color: {_SIGNAL};">How It Works</b><br>')
    lines.append(f'{html.escape(recipe["explanation"])}<br><br>')

    # Tips
    if recipe.get("tips"):
        lines.append(f'<b style="color: {_SIGNAL};">Tips</b><br>')
        for tip in recipe["tips"]:
            lines.append(f'&bull; {html.escape(tip)}<br>')
        lines.append("<br>")

    # Build prompt
    lines.append(
        f'<span style="color: {_SUCCESS}; font-size: {_SMALL_PX}px;">'
        f"Type <b>/recipes build {html.escape(category)} {html.escape(recipe_name)}</b> "
        f"to create this network.</span>"
    )
    lines.append("</div>")
    return "\n".join(lines)


# =============================================================================
# Build Messages
# =============================================================================

def build_recipe_messages(category: str, recipe_name: str, context: dict) -> list:
    """Build Claude API messages that instruct Claude to construct the recipe.

    Args:
        category: Category name.
        recipe_name: Recipe name.
        context: Current network context dict (e.g., {"parent_path": "/obj/geo1"}).

    Returns:
        List of message dicts for the Claude API, or empty list if recipe not found.
    """
    recipe = get_recipe(category, recipe_name)
    if recipe is None:
        return []

    parent_path = context.get("parent_path", "/obj/geo1")

    # Build node descriptions
    node_lines = []
    for i, node in enumerate(recipe["nodes"]):
        parm_desc = ""
        if node.get("parms"):
            parm_items = []
            for k, v in sorted(node["parms"].items()):
                parm_items.append(f"  {k} = {repr(v)}")
            parm_desc = "\n" + "\n".join(parm_items)
        node_lines.append(
            f"  {i + 1}. Create node type='{node['type']}' name='{node['name']}'"
            f"{parm_desc}"
        )

    # Build connection descriptions
    conn_lines = []
    for conn in recipe["connections"]:
        src, dst, idx = conn[0], conn[1], conn[2]
        conn_lines.append(f"  - Connect {src} output 0 -> {dst} input {idx}")

    instruction = (
        f"Build the '{recipe['title']}' recipe in {parent_path}.\n\n"
        f"Context: {recipe['context']} network\n\n"
        f"Create these nodes:\n"
        + "\n".join(node_lines)
        + "\n\n"
        f"Make these connections:\n"
        + "\n".join(conn_lines)
        + "\n\n"
        f"Use houdini_create_node, houdini_set_parm, and houdini_connect_nodes tools. "
        f"Set the display flag on the last node.\n\n"
        f"Key parameters to set: {', '.join(recipe['key_parms'])}"
    )

    return [
        {
            "role": "user",
            "content": instruction,
        }
    ]
