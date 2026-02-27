"""APEX Recipes module for SYNAPSE.

Production-ready APEX rigging recipes for Houdini 21. Each recipe defines
the node network, connections, key parameters, explanation, workflow steps,
and tips for building APEX rigs inside SOPs.

APEX (All-Purpose EXecution) is Houdini 21's graph-based rigging and
deformation framework, replacing the older KineFX workflow for new rigs.

Usage:
    from synapse.panel.apex_recipes import (
        APEX_RECIPES, list_apex_recipes, get_apex_recipe,
        format_apex_recipes_html, format_apex_recipe_detail_html,
        build_apex_recipe_messages, search_apex_recipes,
        KINEFX_MIGRATION_GUIDE,
    )
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
# APEX_RECIPES -- The canonical APEX recipe database
# =============================================================================

APEX_RECIPES = {
    # -------------------------------------------------------------------------
    # FK Chain
    # -------------------------------------------------------------------------
    "fk_chain": {
        "title": "FK Chain",
        "description": "Basic forward kinematics chain from a skeleton",
        "difficulty": "beginner",
        "context": "SOP",
        "prereqs": "A curve or skeleton input. If starting from scratch, a line SOP works.",
        "nodes": [
            {
                "type": "bonegenerator",
                "name": "skeleton1",
                "parms": {"length": 5, "bones": 5},
            },
            {
                "type": "rig_doctor",
                "name": "rig_doctor1",
                "parms": {},
            },
            {
                "type": "apex::rig::fkfull",
                "name": "fk_full1",
                "parms": {},
            },
        ],
        "connections": [
            ["skeleton1", "rig_doctor1", 0],
            ["rig_doctor1", "fk_full1", 0],
        ],
        "key_parms": ["length", "bones"],
        "explanation": (
            "Creates a skeleton using bonegenerator, validates it with rig_doctor "
            "to ensure joint hierarchy and naming are correct, then applies a full "
            "FK setup via apex::rig::fkfull. The FK node generates rotation controls "
            "for each joint in the chain, allowing direct rotational animation. "
            "This is the simplest APEX rig setup and the foundation for more "
            "complex configurations."
        ),
        "workflow": [
            "Create the network and set bone count/length on bonegenerator",
            "Check rig_doctor output for warnings about skeleton issues",
            "Enter the APEX rig viewer to see FK controls",
            "Rotate individual joint controls to pose the chain",
            "Add an Invoke SOP downstream to apply the rig to geometry",
        ],
        "tips": [
            "Use rig_doctor before any APEX rig node -- it catches naming and hierarchy issues early",
            "FK is best for tails, tentacles, hair chains, and mechanical linkages",
            "For character spines, FK gives direct control but IK may be more intuitive",
            "You can adjust control shapes after the fact with apex::rig::controlshapes",
        ],
    },

    # -------------------------------------------------------------------------
    # IK Chain
    # -------------------------------------------------------------------------
    "ik_chain": {
        "title": "IK Chain",
        "description": "Inverse kinematics chain with pole vector control",
        "difficulty": "intermediate",
        "context": "SOP",
        "prereqs": "A skeleton with at least 3 joints (root, mid, tip).",
        "nodes": [
            {
                "type": "skeleton",
                "name": "skeleton1",
                "parms": {},
            },
            {
                "type": "apex::rig::ikfull",
                "name": "ik_full1",
                "parms": {},
            },
            {
                "type": "null",
                "name": "pole_vector_ref",
                "parms": {},
            },
        ],
        "connections": [
            ["skeleton1", "ik_full1", 0],
        ],
        "key_parms": ["rootjoint", "tipjoint", "twist"],
        "explanation": (
            "Builds an IK chain from a skeleton input. The apex::rig::ikfull node "
            "creates an IK solver with an end effector (goal) and a pole vector "
            "control that determines the plane of the IK solve. The null node "
            "serves as a reference for pole vector placement. IK is essential for "
            "limbs -- the animator moves the hand/foot and the elbow/knee follows "
            "naturally. The twist parameter controls how twist distributes along "
            "the chain."
        ),
        "workflow": [
            "Create or import a skeleton with a clear joint chain",
            "Set root and tip joints on the IK node to define the solve range",
            "Position the pole vector control where the elbow/knee should point",
            "Move the IK goal (end effector) to pose the limb",
            "Adjust twist distribution for forearm/lower leg roll",
        ],
        "tips": [
            "Place pole vectors on the natural bend plane (in front of knees, behind elbows)",
            "IK chains should have a slight pre-bend so the solver knows which direction to fold",
            "For arms, a 3-joint chain (shoulder, elbow, wrist) is standard",
            "Use the twist parameter for forearm roll rather than adding extra joints",
        ],
    },

    # -------------------------------------------------------------------------
    # FK/IK Blend
    # -------------------------------------------------------------------------
    "fk_ik_blend": {
        "title": "FK/IK Blend",
        "description": "Combined FK and IK with a blend control for switching",
        "difficulty": "intermediate",
        "context": "SOP",
        "prereqs": "A skeleton suitable for both FK and IK (e.g., an arm or leg chain).",
        "nodes": [
            {
                "type": "skeleton",
                "name": "skeleton1",
                "parms": {},
            },
            {
                "type": "apex::rig::fkfull",
                "name": "fk_full1",
                "parms": {},
            },
            {
                "type": "apex::rig::ikfull",
                "name": "ik_full1",
                "parms": {},
            },
            {
                "type": "apex::rig::blendtransform",
                "name": "blend1",
                "parms": {"blend": 0.0},
            },
        ],
        "connections": [
            ["skeleton1", "fk_full1", 0],
            ["skeleton1", "ik_full1", 0],
            ["fk_full1", "blend1", 0],
            ["ik_full1", "blend1", 1],
        ],
        "key_parms": ["blend", "rootjoint", "tipjoint"],
        "explanation": (
            "Creates both FK and IK rigs from the same skeleton, then blends "
            "between them using apex::rig::blendtransform. A blend value of 0.0 "
            "uses pure FK, 1.0 uses pure IK, and values in between interpolate "
            "smoothly. This is the standard setup for character limbs in "
            "production -- animators switch between FK for arcs and follow-through, "
            "and IK for planted contacts and precise positioning."
        ),
        "workflow": [
            "Build the skeleton and connect it to both FK and IK nodes",
            "Wire both outputs into the blend transform node",
            "Set blend=0 to animate in FK mode, blend=1 for IK mode",
            "Keyframe the blend parameter to switch mid-shot",
            "Ensure FK and IK poses match at the blend transition frame",
        ],
        "tips": [
            "Always match FK and IK poses at the switch point to avoid pops",
            "Use FK for broad sweeping motions and follow-through (arms swinging)",
            "Use IK for contact poses (feet planted, hands on table)",
            "The blend parameter can be animated for seamless transitions",
            "Some studios keep blend at 0 or 1 and avoid mid-values to keep rigs predictable",
        ],
    },

    # -------------------------------------------------------------------------
    # Autorig Biped
    # -------------------------------------------------------------------------
    "autorig_biped": {
        "title": "Autorig Biped",
        "description": "Full character autorig from a skeleton definition",
        "difficulty": "advanced",
        "context": "SOP",
        "prereqs": (
            "A properly named biped skeleton with standard joint naming "
            "(spine, L_arm, R_arm, L_leg, R_leg hierarchy)."
        ),
        "nodes": [
            {
                "type": "bonegenerator",
                "name": "skeleton1",
                "parms": {},
            },
            {
                "type": "rig_doctor",
                "name": "rig_doctor1",
                "parms": {},
            },
            {
                "type": "apex::autorig::build",
                "name": "autorig1",
                "parms": {},
            },
        ],
        "connections": [
            ["skeleton1", "rig_doctor1", 0],
            ["rig_doctor1", "autorig1", 0],
        ],
        "key_parms": ["symmetry", "fkik_default"],
        "explanation": (
            "The APEX autorig analyzes a skeleton's joint hierarchy and naming "
            "conventions to automatically generate a full production rig. It "
            "creates FK/IK limbs, spine controls, head/neck, fingers, and a "
            "root/COG control. The rig_doctor step is critical -- it validates "
            "that joint names follow the expected conventions and that the "
            "hierarchy is clean. The autorig handles symmetry automatically "
            "when left/right naming is detected."
        ),
        "workflow": [
            "Create or import a biped skeleton with standard naming",
            "Run rig_doctor and fix any reported naming or hierarchy issues",
            "Apply autorig::build and check the generated rig in the viewer",
            "Customize FK/IK defaults per limb if needed",
            "Add custom control shapes or constraints on top of the autorig",
        ],
        "tips": [
            "Joint naming must follow conventions: spine_01, L_shoulder, R_hip, etc.",
            "Run rig_doctor FIRST -- autorig failures are almost always naming issues",
            "The autorig is a starting point -- production rigs usually add custom layers on top",
            "Use the symmetry option to ensure left/right limbs match exactly",
            "For quadrupeds or non-standard skeletons, use individual FK/IK recipes instead",
        ],
    },

    # -------------------------------------------------------------------------
    # Custom APEX Deformer
    # -------------------------------------------------------------------------
    "simple_deformer": {
        "title": "Custom APEX Deformer",
        "description": "Build a simple custom deformer as an APEX graph",
        "difficulty": "advanced",
        "context": "SOP",
        "prereqs": "Input geometry to deform. Familiarity with APEX graph concepts.",
        "nodes": [
            {
                "type": "apex::sop::graphdefaults",
                "name": "graph_defaults1",
                "parms": {},
            },
            {
                "type": "apex_editgraph",
                "name": "edit_graph1",
                "parms": {},
            },
            {
                "type": "invoke",
                "name": "invoke1",
                "parms": {},
            },
        ],
        "connections": [
            ["graph_defaults1", "edit_graph1", 0],
            ["edit_graph1", "invoke1", 0],
        ],
        "key_parms": ["graphname", "entry_point"],
        "explanation": (
            "APEX graphs are geometry -- they live in SOPs as packed data. "
            "The graphdefaults node creates a base APEX graph with standard "
            "inputs and outputs. The edit_graph node lets you add custom "
            "operations to the graph (math, transforms, blending). The "
            "invoke node executes the APEX graph on input geometry. This "
            "pattern is how you build custom deformers, solvers, or any "
            "procedural operation that runs as an APEX graph."
        ),
        "workflow": [
            "Create graph_defaults to initialize the APEX graph structure",
            "Open edit_graph and add nodes for your deformation logic",
            "Wire transform operations, math nodes, or VEX snippets inside the graph",
            "Connect the output to invoke with your target geometry",
            "Test the deformer by adjusting parameters on the graph nodes",
        ],
        "tips": [
            "APEX graphs are geometry -- you can inspect them with a geometry spreadsheet",
            "Start simple: a single transform operation before building complex logic",
            "The invoke SOP is the bridge between the APEX graph and regular SOP geometry",
            "Use apex::sop::graphdefaults rather than building graphs from scratch",
            "Custom deformers can be saved as digital assets for reuse",
        ],
    },

    # -------------------------------------------------------------------------
    # Control Shape Setup
    # -------------------------------------------------------------------------
    "control_shapes": {
        "title": "Control Shape Setup",
        "description": "Add viewport control shapes to an APEX rig",
        "difficulty": "beginner",
        "context": "SOP",
        "prereqs": "A skeleton or existing APEX rig to add controls to.",
        "nodes": [
            {
                "type": "skeleton",
                "name": "skeleton1",
                "parms": {},
            },
            {
                "type": "apex::rig::controlshapes",
                "name": "control_shapes1",
                "parms": {"shape": "circle"},
            },
            {
                "type": "apex::rig::fkfull",
                "name": "fk_full1",
                "parms": {},
            },
        ],
        "connections": [
            ["skeleton1", "control_shapes1", 0],
            ["control_shapes1", "fk_full1", 0],
        ],
        "key_parms": ["shape", "scale", "color"],
        "explanation": (
            "Control shapes are the visual handles animators interact with in "
            "the viewport. The controlshapes node assigns shape primitives "
            "(circles, squares, diamonds, cubes) to joints, making them "
            "selectable and visible. Shape, scale, and color can be set per "
            "joint or globally. Place this node before the rig solver (FK/IK) "
            "so the controls are part of the rig evaluation."
        ),
        "workflow": [
            "Create or import your skeleton",
            "Add controlshapes and choose a default shape (circle is standard)",
            "Adjust scale so controls are visible but not occluding the character",
            "Set different colors for left (blue), right (red), and center (yellow) controls",
            "Wire into the FK or IK rig node downstream",
        ],
        "tips": [
            "Color convention: blue=left, red=right, yellow=center is industry standard",
            "Scale controls relative to the joint they represent -- spine controls larger than fingers",
            "Circle shapes work for most joints; use squares for root/COG",
            "Control shapes do not affect the rig solve -- they are purely visual",
            "You can add controlshapes after an existing rig to customize the look",
        ],
    },

    # -------------------------------------------------------------------------
    # Constraint Setup
    # -------------------------------------------------------------------------
    "constraint_setup": {
        "title": "Constraint Setup",
        "description": "Parent, aim, and point constraints between joints",
        "difficulty": "intermediate",
        "context": "SOP",
        "prereqs": "A skeleton with at least two joints to constrain.",
        "nodes": [
            {
                "type": "skeleton",
                "name": "skeleton1",
                "parms": {},
            },
            {
                "type": "apex::rig::parentconstraint",
                "name": "parent_constraint1",
                "parms": {},
            },
        ],
        "connections": [
            ["skeleton1", "parent_constraint1", 0],
        ],
        "key_parms": ["driver", "driven", "maintain_offset", "weight"],
        "explanation": (
            "Constraints link one joint's transform to another. A parent "
            "constraint makes the driven joint follow the driver in both "
            "position and rotation (like parenting but without hierarchy "
            "changes). Aim constraints orient a joint to point at a target. "
            "Point constraints match position only. Constraints are essential "
            "for props (sword follows hand), space switching (hand follows "
            "body vs world), and mechanical rigs."
        ),
        "workflow": [
            "Set the driver joint (the one that leads)",
            "Set the driven joint (the one that follows)",
            "Enable maintain_offset if the driven joint should keep its current position",
            "Adjust weight to blend the constraint effect (1.0 = fully constrained)",
            "For space switching, use multiple constraints with animated weights",
        ],
        "tips": [
            "Parent constraint = position + rotation; Point constraint = position only",
            "Use aim constraints for eyes, turrets, or anything that needs to track a target",
            "maintain_offset=True is almost always what you want for props and accessories",
            "Animate constraint weights for space switching (hand picks up object, releases it)",
            "Stack multiple constraints with different weights for multi-target blending",
        ],
    },

    # -------------------------------------------------------------------------
    # KineFX to APEX Migration
    # -------------------------------------------------------------------------
    "kinefx_to_apex": {
        "title": "KineFX to APEX Migration",
        "description": "Convert existing KineFX rig components to APEX",
        "difficulty": "advanced",
        "context": "SOP",
        "prereqs": (
            "An existing KineFX rig setup (skeleton with rig pose, "
            "configure joints, capture)."
        ),
        "nodes": [
            {
                "type": "skeleton",
                "name": "kinefx_skeleton",
                "parms": {},
            },
            {
                "type": "apex::sop::fromkinefx",
                "name": "from_kinefx1",
                "parms": {},
            },
            {
                "type": "rig_doctor",
                "name": "rig_doctor1",
                "parms": {},
            },
            {
                "type": "apex::rig::fkfull",
                "name": "fk_full1",
                "parms": {},
            },
        ],
        "connections": [
            ["kinefx_skeleton", "from_kinefx1", 0],
            ["from_kinefx1", "rig_doctor1", 0],
            ["rig_doctor1", "fk_full1", 0],
        ],
        "key_parms": ["conversion_mode"],
        "explanation": (
            "Migrates an existing KineFX rig to APEX. The fromkinefx node "
            "converts KineFX skeleton data and attributes into the APEX "
            "format. After conversion, rig_doctor validates the result and "
            "you can apply APEX rig components (FK, IK, autorig) on top. "
            "The skeleton representation (points with transform attributes) "
            "stays the same -- what changes is how the rig logic is expressed "
            "(from SOPs to APEX graphs)."
        ),
        "workflow": [
            "Identify the KineFX skeleton source (skeleton SOP or imported FBX)",
            "Add the fromkinefx conversion node",
            "Run rig_doctor to validate the converted skeleton",
            "Replace KineFX rig pose nodes with APEX equivalents (fkfull, ikfull)",
            "Replace configure_joints with APEX character definition if needed",
            "Test the new APEX rig matches the old KineFX behavior",
        ],
        "tips": [
            "Keep the old KineFX chain as reference -- do not delete until APEX rig is verified",
            "Joint attributes (name, transform) transfer directly; rig logic does not",
            "KineFX Rig Pose = APEX FK/IK; KineFX Full Body IK = APEX FBIK",
            "Custom VEX in KineFX wrangles may need to become APEX graph nodes",
            "See KINEFX_MIGRATION_GUIDE for a detailed mapping of concepts",
        ],
    },
}


# =============================================================================
# KineFX to APEX Migration Guide
# =============================================================================

KINEFX_MIGRATION_GUIDE = """\
KineFX to APEX Migration Guide
===============================

Overview
--------
APEX (All-Purpose EXecution) is Houdini 21's evolution of the KineFX rigging
framework. While KineFX expressed rig logic as SOP node chains (each SOP doing
one operation on the skeleton), APEX uses graph-as-geometry: the rig logic
itself is packed geometry that flows through SOPs and is evaluated by an
Invoke node.

What Changes Conceptually
-------------------------
- KineFX: Rig logic = SOP network. Each SOP modifies the skeleton points.
- APEX: Rig logic = APEX graph (packed geometry). SOPs build/edit the graph,
  then Invoke evaluates it on the skeleton.

Think of it as: KineFX is "rig as node chain", APEX is "rig as data".

The key advantage is that APEX graphs can be inspected, serialized, shared,
and evaluated much more efficiently than SOP chains. APEX graphs also support
parallel evaluation and can be compiled for better performance.

Common KineFX Patterns and Their APEX Equivalents
--------------------------------------------------

1. Rig Pose (KineFX) -> FK/IK Full (APEX)
   - KineFX: rigpose SOP allows interactive posing of joints
   - APEX: apex::rig::fkfull creates FK controls; apex::rig::ikfull creates IK
   - The APEX versions generate proper rig controls with solve evaluation,
     whereas KineFX rig pose was more of a direct manipulation tool.

2. Full Body IK (KineFX) -> APEX FBIK
   - KineFX: fullbodyik SOP with targets and pins
   - APEX: apex::rig::fbik provides the same solver in graph form
   - Targets and pins are wired as graph inputs rather than SOP connections.

3. Configure Joints (KineFX) -> Character Definition (APEX)
   - KineFX: configurejoint SOP sets rotation order, limits, rest pose
   - APEX: Character definition nodes define the skeleton schema
   - Joint limits, rotation orders, and rest transforms are attributes on
     the skeleton that both systems read. The difference is how they are
     authored and validated.

4. Joint Capture Biharmonic (KineFX) -> APEX Capture
   - KineFX: jointcapturebiharmonic SOP computes skin weights
   - APEX: Capture operations work on the same weight attributes
   - Skin weights (boneCapture attribute) are compatible between KineFX and
     APEX -- you do not need to re-skin when migrating.

5. Skeleton Blend (KineFX) -> Blend Transform (APEX)
   - KineFX: skeletonblend SOP mixes two skeleton poses
   - APEX: apex::rig::blendtransform blends in graph context
   - The blend parameter (0-1) works the same way in both systems.

6. Rig Wrangle / VEX (KineFX) -> APEX Graph Nodes
   - KineFX: attribwrangle with VEX on skeleton points
   - APEX: Custom nodes inside the APEX graph, or apex_editgraph
   - Simple VEX operations (set transform, read attribute) map to standard
     APEX graph nodes. Complex custom VEX may need a dedicated APEX subgraph.

What Stays the Same
-------------------
- Skeleton representation: Points with name, transform, and hierarchy
  attributes. Both KineFX and APEX use the same point-based skeleton.
- Joint attributes: name (s@name), local/world transforms, parentIndex.
  These are identical between the two systems.
- Skin weights: The boneCapture attribute format is shared. Skinning done
  in KineFX works with APEX rigs and vice versa.
- Animation data: Keyframes on rig controls export the same way regardless
  of whether the rig was built in KineFX or APEX.
- SOP context: Both KineFX and APEX rigs live in SOPs. You are not changing
  contexts (unlike the old OBJ-level bone system).

Gotchas and Common Mistakes
----------------------------
1. Do not try to mix KineFX rig pose and APEX rig nodes in the same chain.
   Convert fully to one system or the other.

2. The apex::sop::fromkinefx node handles skeleton conversion, but it does
   NOT convert rig logic. You must rebuild FK/IK/constraints in APEX.

3. Joint naming matters more in APEX. The autorig and many rig components
   expect standard naming conventions. Run rig_doctor after conversion.

4. APEX graphs are geometry. If you merge or blast them incorrectly, you
   destroy the rig. Treat APEX graph prims with the same care as any other
   geometry data.

5. KineFX wrangles that modify point positions directly may not translate
   to APEX cleanly. APEX prefers graph-level operations over point-level
   VEX. Consider using apex_editgraph to replicate wrangle logic.

6. Performance: APEX rigs are generally faster than equivalent KineFX setups
   due to graph compilation and parallel evaluation. However, the initial
   build step (constructing the graph) adds overhead that KineFX does not
   have. For simple rigs, the difference is negligible.

7. APEX is still evolving in Houdini 21. Some KineFX workflows may not have
   direct APEX equivalents yet. Check SideFX documentation for the latest
   node availability.

Migration Checklist
-------------------
[ ] Identify all KineFX nodes in the current rig
[ ] Note which are skeleton sources vs. rig logic vs. deformation
[ ] Convert skeleton source (usually keeps the same skeleton SOP)
[ ] Replace rig logic nodes with APEX equivalents (see mapping above)
[ ] Run rig_doctor on the converted skeleton
[ ] Verify skin weights transfer correctly (boneCapture attribute)
[ ] Test rig controls match the old KineFX behavior
[ ] Check animation clips still evaluate correctly
[ ] Remove old KineFX chain once APEX rig is validated
"""


# =============================================================================
# Lookup Functions
# =============================================================================

def get_apex_recipe(name):
    """Look up an APEX recipe by name.

    Args:
        name: Recipe name (e.g., "fk_chain").

    Returns:
        The recipe dict, or None if not found.
    """
    return APEX_RECIPES.get(name)


def list_apex_recipes():
    """Return a sorted list of all APEX recipe names.

    Returns:
        Sorted list of recipe name strings.
    """
    return sorted(APEX_RECIPES.keys())


# =============================================================================
# Search
# =============================================================================

def search_apex_recipes(query):
    """Search APEX recipes by title, description, explanation, and tips.

    Args:
        query: Search string (case-insensitive).

    Returns:
        List of (name, title, match_context) tuples.
    """
    results = []
    q = query.lower()

    for name in sorted(APEX_RECIPES.keys()):
        recipe = APEX_RECIPES[name]
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
            _match_type, match_text = matches[0]
            results.append((name, recipe["title"], match_text))

    return results


# =============================================================================
# HTML Formatting
# =============================================================================

_DIFFICULTY_COLORS = {
    "beginner": _SUCCESS,
    "intermediate": _WARNING,
    "advanced": "#FF6B6B",
}


def format_apex_recipes_html():
    """Format an overview of all APEX recipes as HTML.

    Returns:
        HTML string with title, difficulty badge, and description for each recipe.
    """
    total = len(APEX_RECIPES)
    lines = []
    lines.append(
        f'<div style="font-family: {_FONT_SANS}; color: {_TEXT}; '
        f'font-size: {_BODY_PX}px; line-height: 1.8;">'
    )
    lines.append(
        f'<b style="color: {_SIGNAL};">APEX Rig Recipes</b> '
        f'<span style="color: {_TEXT_DIM};">({total} recipes)</span>'
    )
    lines.append("<br><br>")

    for name in sorted(APEX_RECIPES.keys()):
        recipe = APEX_RECIPES[name]
        diff_color = _DIFFICULTY_COLORS.get(recipe["difficulty"], _TEXT_DIM)
        lines.append(
            f'<b>{html.escape(name)}</b> '
            f'<span style="color: {_TEXT_DIM};">-</span> '
            f'{html.escape(recipe["description"])} '
            f'<span style="color: {diff_color}; font-size: {_SMALL_PX}px;">'
            f'[{html.escape(recipe["difficulty"])}]</span>'
            "<br>"
        )

    lines.append("<br>")
    lines.append(
        f'<span style="color: {_TEXT_DIM}; font-size: {_SMALL_PX}px;">'
        "Type a recipe name to see full details and build instructions.</span>"
    )
    lines.append("</div>")
    return "\n".join(lines)


def format_apex_recipe_detail_html(name):
    """Format full detail for a single APEX recipe as HTML.

    Args:
        name: Recipe name.

    Returns:
        HTML string with title, description, prereqs, nodes, explanation,
        workflow steps, and tips.
    """
    recipe = get_apex_recipe(name)
    if recipe is None:
        return (
            f'<span style="color: {_WARNING};">APEX recipe "{html.escape(name)}" '
            f"not found. Use list_apex_recipes() to see available recipes.</span>"
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

    # Prerequisites
    prereqs = recipe.get("prereqs", "")
    if prereqs:
        lines.append(f'<b style="color: {_SIGNAL};">Prerequisites</b><br>')
        lines.append(f'{html.escape(prereqs)}<br><br>')

    # Nodes
    lines.append(f'<b style="color: {_SIGNAL};">Nodes</b><br>')
    for node in recipe["nodes"]:
        parm_summary = ""
        if node.get("parms"):
            parm_strs = []
            for k, v in sorted(node["parms"].items()):
                parm_strs.append(f"{k}={v}")
            if parm_strs:
                parm_summary = (
                    f' <span style="color: {_TEXT_DIM};">'
                    f'({", ".join(parm_strs)})</span>'
                )
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

    # Workflow
    if recipe.get("workflow"):
        lines.append(f'<b style="color: {_SIGNAL};">Workflow</b><br>')
        for i, step in enumerate(recipe["workflow"], 1):
            lines.append(
                f'<span style="color: {_SIGNAL};">{i}.</span> '
                f'{html.escape(step)}<br>'
            )
        lines.append("<br>")

    # Tips
    if recipe.get("tips"):
        lines.append(f'<b style="color: {_SIGNAL};">Tips</b><br>')
        for tip in recipe["tips"]:
            lines.append(f'&bull; {html.escape(tip)}<br>')
        lines.append("<br>")

    lines.append("</div>")
    return "\n".join(lines)


# =============================================================================
# Build Messages
# =============================================================================

def build_apex_recipe_messages(name, context):
    """Build Claude API messages for constructing an APEX recipe with tools.

    Args:
        name: Recipe name.
        context: Current network context dict (e.g., {"parent_path": "/obj/geo1"}).

    Returns:
        List of message dicts for the Claude API, or empty list if recipe not found.
    """
    recipe = get_apex_recipe(name)
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
            if parm_items:
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

    # Build key parms list
    key_parms_str = ", ".join(recipe.get("key_parms", []))

    instruction = (
        f"Build the '{recipe['title']}' APEX rig recipe in {parent_path}.\n\n"
        f"Context: {recipe['context']} network (APEX rigging)\n\n"
        f"Prerequisites: {recipe.get('prereqs', 'None')}\n\n"
        f"Create these nodes:\n"
        + "\n".join(node_lines)
        + "\n\n"
        f"Make these connections:\n"
        + "\n".join(conn_lines)
        + "\n\n"
        f"Use houdini_create_node, houdini_set_parm, and houdini_connect_nodes tools. "
        f"Set the display flag on the last node.\n\n"
        f"Key parameters to set: {key_parms_str}\n\n"
        f"Note: APEX node types may vary by Houdini version. If a node type "
        f"is not found, check for similar types with 'apex' in the name. "
        f"The houdini_create_node tool handles type resolution."
    )

    return [
        {
            "role": "user",
            "content": instruction,
        }
    ]
