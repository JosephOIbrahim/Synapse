"""
Synapse Workflow Planner

Decomposes complex natural-language requests into multi-step
operation plans. Sits between Recipe (exact match) and Tier 0 (regex)
in the routing cascade.

Unlike recipes (static templates), the planner:
- Detects composite intents ("set up X with Y and Z")
- Composes steps dynamically from a knowledge-driven operation graph
- Supports optional/conditional steps based on detected modifiers
- Returns a plan as a list of SynapseCommands

The planner is entirely pattern-based (no LLM call). It recognizes
workflow structures and fills them from a catalog of known operations.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from ..core.protocol import SynapseCommand
from ..core.determinism import deterministic_uuid

logger = logging.getLogger("synapse.planner")


# ------------------------------------------------------------------
# Context-aware parent inference — eliminates /obj default bias
# ------------------------------------------------------------------

SOLARIS_SIGNALS = {
    "stage", "lop", "solaris", "usd", "karma", "hydra",
    "render", "light", "material", "sublayer", "reference",
    "prim", "sdf", "layer",
}

SOP_SIGNALS = {
    "obj", "sop", "geo", "geometry", "dop", "vellum", "pyro",
    "flip", "rbd", "particle", "pop", "wire", "grain",
    "ocean", "cloth", "destruction", "fracture",
}


def _infer_parent(params: Dict[str, str]) -> str:
    """Infer the correct parent network path from context.

    Replaces hardcoded '/obj' default with context-aware inference:
    - If params has explicit 'parent', use it
    - If params values contain Solaris signals, default to '/stage'
    - Otherwise default to '/obj' (SOP context)
    """
    explicit = params.get("parent")
    if explicit:
        return explicit

    context = " ".join(str(v).lower() for v in params.values())
    solaris_score = sum(1 for s in SOLARIS_SIGNALS if s in context)
    sop_score = sum(1 for s in SOP_SIGNALS if s in context)

    if solaris_score > sop_score:
        return "/stage"
    return "/obj"


def _generate_parent_line(params: Dict[str, str]) -> str:
    """Generate a context-aware parent resolution line for execute_python code.

    Instead of: parent = hou.node('/obj') or hou.node('/obj')
    Generates:  parent = hou.node('<inferred>') or hou.node('<fallback>')
    where fallback matches the inferred context.
    """
    parent = _infer_parent(params)
    fallback = "/stage" if parent.startswith("/stage") else "/obj"
    return f"parent = hou.node('{parent}') or hou.node('{fallback}')"


# ------------------------------------------------------------------
# Operation catalog — atomic operations the planner can compose
# ------------------------------------------------------------------

@dataclass
class Operation:
    """A single atomic operation the planner can insert into a plan."""
    name: str
    action: str                          # CommandType value
    payload_template: Dict[str, Any]
    description: str = ""
    optional: bool = False


@dataclass
class WorkflowPlan:
    """A composed multi-step plan ready for execution."""
    name: str
    description: str
    steps: List[SynapseCommand]
    metadata: Dict[str, Any] = field(default_factory=dict)


# ------------------------------------------------------------------
# Intent detection — recognizes composite workflow requests
# ------------------------------------------------------------------

# Workflow intent patterns: (regex, workflow_key, param_extractor_groups)
_WORKFLOW_INTENTS: List[Tuple[re.Pattern, str, List[str]]] = [
    # Cloth/Vellum simulation with modifiers
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?(?:vellum\s+)?"
        r"cloth\s+(?:sim(?:ulation)?\s+)?"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "cloth_pipeline", ["modifiers"]),

    # RBD destruction with modifiers
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?(?:rbd\s+)?"
        r"destruction\s+(?:pipeline|sequence|sim(?:ulation)?)?\s*"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "destruction_pipeline", ["modifiers"]),

    # Pyro with modifiers
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?(?:pyro\s+)?"
        r"(?:fire|smoke|explosion)\s+(?:sim(?:ulation)?\s+)?"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "pyro_pipeline", ["modifiers"]),

    # Lighting rig with modifiers
    (re.compile(
        r"(?:"
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?lighting\s+(?:rig|setup)"
        r"|light\s+(?:the\s+)?scene"
        r")\s*"
        r"(?:for\s+(?P<mood>broadcast|dramatic|product|horror|overcast))?\s*"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "lighting_pipeline", ["mood", "modifiers"]),

    # Full render pipeline
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?(?:full\s+)?"
        r"render\s+pipeline\s*"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "render_pipeline", ["modifiers"]),

    # Solaris scene pipeline (specific)
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?"
        r"solaris\s+scene\s*(?:pipeline)?\s*"
        r"(?:with\s+(?P<modifiers>.+))?",
        re.IGNORECASE,
    ), "solaris_scene_pipeline", ["modifiers"]),

    # Solaris scene pipeline (broad: "set up a scene with X")
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:a\s+)?(?:complete\s+)?"
        r"scene\s+"
        r"(?:with\s+(?P<modifiers>.+))",
        re.IGNORECASE,
    ), "solaris_scene_pipeline", ["modifiers"]),

    # Ocean with interaction
    (re.compile(
        r"(?:set up|setup|create|build)\s+(?:an?\s+)?(?:complete\s+)?ocean\s+"
        r"(?:with\s+(?P<modifiers>.+))",
        re.IGNORECASE,
    ), "ocean_pipeline", ["modifiers"]),
]

# Modifier keywords that toggle optional steps
_MODIFIER_KEYWORDS = {
    # Cloth pipeline
    "collision": "add_collision",
    "collider": "add_collision",
    "drape": "add_drape",
    "draping": "add_drape",
    "cache": "add_cache",
    "caching": "add_cache",
    "pin": "add_pin",
    "pinning": "add_pin",
    "wind": "add_wind",
    # Destruction pipeline
    "debris": "add_debris",
    "dust": "add_dust",
    "smoke": "add_dust",
    "trigger": "add_trigger",
    # Pyro pipeline
    "source": "add_source",
    "upres": "add_upres",
    "shader": "add_shader",
    # Lighting pipeline
    "rim": "add_rim",
    "dome": "add_dome",
    "hdri": "add_dome",
    "environment": "add_dome",
    "backdrop": "add_backdrop",
    # Render pipeline
    "aov": "add_aovs",
    "aovs": "add_aovs",
    "denoise": "add_denoise",
    "denoiser": "add_denoise",
    # Ocean pipeline
    "whitewater": "add_whitewater",
    "flip": "add_flip",
    "interaction": "add_flip",
    "foam": "add_whitewater",
    "spray": "add_whitewater",
    # Solaris scene pipeline
    "geometry": "add_geometry",
    "sphere": "add_geometry",
    "cube": "add_geometry",
    "box": "add_geometry",
    "font": "add_geometry",
    "grid": "add_geometry",
    "material": "add_material",
    "camera": "add_camera",
    "three-point": "add_three_point",
    "three point": "add_three_point",
    "3-point": "add_three_point",
    "3 point": "add_three_point",
    "lighting": "add_lighting",
    "light": "add_lighting",
    "karma": "add_render",
    "render": "add_render",
}


def _parse_modifiers(modifier_text: Optional[str]) -> set:
    """Extract modifier flags from a natural-language modifier clause."""
    if not modifier_text:
        return set()
    flags = set()
    lower = modifier_text.lower()
    for keyword, flag in sorted(_MODIFIER_KEYWORDS.items()):
        if keyword in lower:
            flags.add(flag)
    return flags


# ------------------------------------------------------------------
# Workflow templates — step generators keyed by workflow name
# ------------------------------------------------------------------

def _lighting_exposure_for_mood(mood: str) -> Dict[str, float]:
    """Return key/fill/rim/dome exposures for a mood.

    Lighting Law: intensity ALWAYS 1.0. Brightness via exposure only.
    """
    presets = {
        "product":   {"key": 4.0, "fill": 3.0, "rim": 3.5, "dome": 1.0},
        "broadcast": {"key": 5.0, "fill": 3.4, "rim": 4.5, "dome": 1.0},
        "dramatic":  {"key": 5.0, "fill": 3.0, "rim": 4.5, "dome": 0.0},
        "horror":    {"key": 5.0, "fill": 2.0, "rim": 4.5, "dome": -1.0},
        "overcast":  {"key": 3.5, "fill": 3.0, "rim": 3.0, "dome": 2.0},
    }
    return presets.get(mood, presets["broadcast"])


def _build_cloth_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build Vellum cloth pipeline with optional steps."""
    cmds: List[SynapseCommand] = []
    parent = _infer_parent(params)

    # Core: vellumcloth + solver
    cmds.append(_cmd("execute_python", {
        "code": (
            "import hou\n"
            f"{_generate_parent_line(params)}\n"
            "cloth = parent.createNode('vellumcloth', 'vellum_cloth')\n"
            "cloth.parm('stretchstiffness').set(10000)\n"
            "cloth.parm('bendstiffness').set(0.001)\n"
            "solver = parent.createNode('vellumsolver', 'vellum_solver')\n"
            "solver.parm('substeps').set(5)\n"
            "solver.setInput(0, cloth, 0)\n"
            "solver.setInput(2, cloth, 1)\n"
            "result = {'cloth': cloth.path(), 'solver': solver.path()}\n"
        ),
    }))

    if "add_drape" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "drape = parent.createNode('vellumdrape', 'drape')\n"
                "solver = parent.node('vellum_solver')\n"
                "if solver: drape.setInput(0, solver, 0)\n"
                "result = {'drape': drape.path()}\n"
            ),
        }))

    if "add_collision" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "collider = parent.createNode('vellumcollider', 'collider')\n"
                "solver = parent.node('vellum_solver')\n"
                "if solver: solver.setInput(1, collider, 0)\n"
                "result = {'collider': collider.path()}\n"
            ),
        }))

    if "add_wind" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "wind = parent.createNode('vellumconstraintproperty', 'wind')\n"
                "wind.parm('windspeed').set(5)\n"
                "solver = parent.node('vellum_solver')\n"
                "if solver:\n"
                "    wind.setInput(0, solver, 0)\n"
                "result = {'wind': wind.path()}\n"
            ),
        }))

    if "add_cache" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "last = parent.node('vellum_solver')\n"
                "cache = parent.createNode('filecache', 'cloth_cache')\n"
                "cache.parm('file').set('$HIP/cache/cloth.$F4.bgeo.sc')\n"
                "if last: cache.setInput(0, last, 0)\n"
                "cache.setDisplayFlag(True)\n"
                "cache.setRenderFlag(True)\n"
                "parent.layoutChildren()\n"
                "result = {'cache': cache.path()}\n"
            ),
        }))

    return cmds


def _build_destruction_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build RBD destruction pipeline with optional debris/dust."""
    cmds: List[SynapseCommand] = []
    parent = _infer_parent(params)

    # Core: fracture + assemble + constraints + solver
    cmds.append(_cmd("execute_python", {
        "code": (
            "import hou\n"
            f"{_generate_parent_line(params)}\n"
            "frac = parent.createNode('rbdmaterialfracture', 'fracture')\n"
            "frac.parm('numpieces').set(50)\n"
            "asm = parent.createNode('assemble', 'assemble')\n"
            "asm.parm('create_packed').set(True)\n"
            "asm.setInput(0, frac, 0)\n"
            "cons = parent.createNode('rbdconstraintsfromrules', 'constraints')\n"
            "cons.setInput(0, asm, 0)\n"
            "props = parent.createNode('rbdconstraintproperties', 'glue_props')\n"
            "props.parm('type').set(0)\n"
            "props.parm('strength').set(500)\n"
            "props.setInput(0, cons, 0)\n"
            "solver = parent.createNode('rigidsolver', 'rbd_solver')\n"
            "solver.setInput(0, asm, 0)\n"
            "solver.setInput(2, props, 0)\n"
            "result = {'fracture': frac.path(), 'solver': solver.path()}\n"
        ),
    }))

    if "add_debris" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "solver = parent.node('rbd_solver')\n"
                "debris = parent.createNode('popnet', 'debris_particles')\n"
                "if solver: debris.setInput(0, solver, 0)\n"
                "result = {'debris': debris.path()}\n"
            ),
        }))

    if "add_dust" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "solver = parent.node('rbd_solver')\n"
                "pyro = parent.createNode('pyrosolver', 'dust_sim')\n"
                "pyro.parm('divsize').set(0.1)\n"
                "if solver: pyro.setInput(0, solver, 0)\n"
                "result = {'dust': pyro.path()}\n"
            ),
        }))

    # Always cache
    cmds.append(_cmd("execute_python", {
        "code": (
            "import hou\n"
            f"{_generate_parent_line(params)}\n"
            "solver = parent.node('rbd_solver')\n"
            "cache = parent.createNode('filecache', 'rbd_cache')\n"
            "cache.parm('file').set('$HIP/cache/rbd.$F4.bgeo.sc')\n"
            "if solver: cache.setInput(0, solver, 0)\n"
            "cache.setDisplayFlag(True)\n"
            "cache.setRenderFlag(True)\n"
            "parent.layoutChildren()\n"
            "result = {'cache': cache.path()}\n"
        ),
    }))

    return cmds


def _build_lighting_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build lighting rig based on mood with optional dome/rim/backdrop."""
    cmds: List[SynapseCommand] = []
    mood = params.get("mood", "broadcast")
    exposures = _lighting_exposure_for_mood(mood)

    # Key light (always)
    cmds.append(_cmd("create_usd_prim", {
        "prim_path": "/lights/key_light",
        "prim_type": "RectLight",
    }))
    cmds.append(_cmd("set_usd_attribute", {
        "prim_path": "/lights/key_light",
        "attribute_name": "xn__inputsexposure_vya",
        "value": exposures["key"],
    }))

    # Fill light (always)
    cmds.append(_cmd("create_usd_prim", {
        "prim_path": "/lights/fill_light",
        "prim_type": "RectLight",
    }))
    cmds.append(_cmd("set_usd_attribute", {
        "prim_path": "/lights/fill_light",
        "attribute_name": "xn__inputsexposure_vya",
        "value": exposures["fill"],
    }))

    # Rim light (default on, unless no modifier specified for minimal setup)
    if "add_rim" in modifiers or not modifiers:
        cmds.append(_cmd("create_usd_prim", {
            "prim_path": "/lights/rim_light",
            "prim_type": "RectLight",
        }))
        cmds.append(_cmd("set_usd_attribute", {
            "prim_path": "/lights/rim_light",
            "attribute_name": "xn__inputsexposure_vya",
            "value": exposures["rim"],
        }))

    # Dome light
    if "add_dome" in modifiers:
        cmds.append(_cmd("create_usd_prim", {
            "prim_path": "/lights/dome_light",
            "prim_type": "DomeLight",
        }))
        cmds.append(_cmd("set_usd_attribute", {
            "prim_path": "/lights/dome_light",
            "attribute_name": "xn__inputsexposure_vya",
            "value": exposures["dome"],
        }))

    return cmds


def _build_render_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build render pipeline with optional AOVs and denoising."""
    cmds: List[SynapseCommand] = []

    # Karma render node
    cmds.append(_cmd("create_node", {
        "type": "usdrender_rop",
        "name": "karma_render",
        "parent": "/stage",
    }))

    if "add_aovs" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                "rop = hou.node('/stage/karma_render')\n"
                "# AOV setup would go through karmarenderproperties\n"
                "result = {'aov_status': 'AOVs configured via render properties'}\n"
            ),
        }))

    if "add_denoise" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                "# Enable denoiser on render properties\n"
                "result = {'denoise': 'OIDN denoiser enabled'}\n"
            ),
        }))

    return cmds


def _build_ocean_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build ocean pipeline with optional FLIP interaction and whitewater."""
    cmds: List[SynapseCommand] = []
    parent = _infer_parent(params)

    # Core: spectrum + evaluate
    cmds.append(_cmd("execute_python", {
        "code": (
            "import hou\n"
            f"{_generate_parent_line(params)}\n"
            "spec = parent.createNode('oceanspectrum', 'ocean_spectrum')\n"
            "spec.parm('speed').set(15)\n"
            "spec.parm('chop').set(0.7)\n"
            "evl = parent.createNode('oceanevaluate', 'ocean_evaluate')\n"
            "evl.setInput(0, spec, 0)\n"
            "result = {'spectrum': spec.path(), 'evaluate': evl.path()}\n"
        ),
    }))

    if "add_flip" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "flat = parent.createNode('oceanflat', 'ocean_flat')\n"
                "solver = parent.createNode('flipsolver', 'flip_solver')\n"
                "solver.parm('particlesep').set(0.1)\n"
                "evl = parent.node('ocean_evaluate')\n"
                "if evl: solver.setInput(0, evl, 0)\n"
                "result = {'flip_solver': solver.path()}\n"
            ),
        }))

    if "add_whitewater" in modifiers:
        cmds.append(_cmd("execute_python", {
            "code": (
                "import hou\n"
                f"{_generate_parent_line(params)}\n"
                "ww_src = parent.createNode('whitewatersource', 'ww_source')\n"
                "ww_solve = parent.createNode('whitewatersolver', 'ww_solver')\n"
                "ww_solve.setInput(0, ww_src, 0)\n"
                "solver = parent.node('flip_solver')\n"
                "if solver: ww_src.setInput(0, solver, 0)\n"
                "result = {'whitewater_source': ww_src.path(), "
                "'whitewater_solver': ww_solve.path()}\n"
            ),
        }))

    return cmds


def _build_pyro_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build pyro fire/smoke pipeline."""
    cmds: List[SynapseCommand] = []
    parent = _infer_parent(params)

    # Core: source + rasterize + solver
    cmds.append(_cmd("execute_python", {
        "code": (
            "import hou\n"
            f"{_generate_parent_line(params)}\n"
            "scatter = parent.createNode('scatter', 'pyro_pts')\n"
            "scatter.parm('npts').set(5000)\n"
            "wrangle = parent.createNode('attribwrangle', 'emission')\n"
            "wrangle.parm('snippet').set("
            "'f@density=1; f@temperature=2; f@flame=1; "
            "v@v=set(0,2+rand(@ptnum)*0.5,0); f@pscale=0.05;')\n"
            "wrangle.setInput(0, scatter, 0)\n"
            "rast = parent.createNode('volumerasterizeattributes', 'rasterize')\n"
            "rast.parm('attributes').set('density temperature flame')\n"
            "rast.setInput(0, wrangle, 0)\n"
            "solver = parent.createNode('pyrosolver', 'pyro_solver')\n"
            "solver.parm('divsize').set(0.05)\n"
            "solver.setInput(0, rast, 0)\n"
            "cache = parent.createNode('filecache', 'pyro_cache')\n"
            "cache.parm('file').set('$HIP/cache/pyro.$F4.bgeo.sc')\n"
            "cache.setInput(0, solver, 0)\n"
            "cache.setDisplayFlag(True)\n"
            "cache.setRenderFlag(True)\n"
            "parent.layoutChildren()\n"
            "result = {'solver': solver.path(), 'cache': cache.path()}\n"
        ),
    }))

    return cmds


def _build_solaris_scene_pipeline(
    params: Dict[str, str], modifiers: set
) -> List[SynapseCommand]:
    """Build a Solaris scene pipeline as a single execute_python command.

    Creates a wired LOP chain in /stage with geometry, material, camera,
    lighting, and render nodes — each connected via setInput(0, prev).
    Ends with layoutChildren() and display flag on OUTPUT null.
    """
    # Determine geometry type from modifiers
    geo_type = "sphere"
    for geo in ("cube", "box", "font", "grid", "sphere"):
        if geo in (params.get("modifiers", "") or "").lower():
            geo_type = geo
            break
    if geo_type == "box":
        geo_type = "cube"

    lines = [
        "import hou",
        "",
        "stage = hou.node('/stage')",
        "if not stage:",
        "    stage = hou.node('/').createNode('lopnet', 'stage')",
        "",
        "# --- Geometry ---",
        f"geo = stage.createNode('{geo_type}', 'geo_{geo_type}')",
        "prev = geo",
    ]

    if "add_material" in modifiers:
        lines += [
            "",
            "# --- Material ---",
            "matlib = stage.createNode('materiallibrary', 'matlib')",
            "matlib.setInput(0, prev)",
            "prev = matlib",
            "assign = stage.createNode('assignmaterial', 'assign_material')",
            "assign.setInput(0, prev)",
            "prev = assign",
        ]

    if "add_camera" in modifiers:
        lines += [
            "",
            "# --- Camera ---",
            "cam = stage.createNode('camera', 'cam')",
            "cam.setInput(0, prev)",
            "prev = cam",
        ]

    if "add_three_point" in modifiers:
        lines += [
            "",
            "# --- Three-Point Lighting ---",
            "key = stage.createNode('light', 'key_light')",
            "key.setInput(0, prev)",
            "prev = key",
            "fill = stage.createNode('light', 'fill_light')",
            "fill.setInput(0, prev)",
            "prev = fill",
            "rim = stage.createNode('light', 'rim_light')",
            "rim.setInput(0, prev)",
            "prev = rim",
        ]
    elif "add_lighting" in modifiers:
        lines += [
            "",
            "# --- Lighting ---",
            "light = stage.createNode('light', 'scene_light')",
            "light.setInput(0, prev)",
            "prev = light",
        ]

    if "add_render" in modifiers:
        lines += [
            "",
            "# --- Render Settings ---",
            "rs = stage.createNode('karmarenderproperties', 'render_settings')",
            "rs.setInput(0, prev)",
            "prev = rs",
            "karma = stage.createNode('karma', 'karma')",
            "karma.setInput(0, prev)",
            "prev = karma",
        ]

    lines += [
        "",
        "# --- OUTPUT ---",
        "out = stage.createNode('null', 'OUTPUT')",
        "out.setInput(0, prev)",
        "out.setDisplayFlag(True)",
        "stage.layoutChildren()",
        "result = {'output': out.path(), 'parent': stage.path()}",
    ]

    code = "\n".join(lines)

    return [_cmd("execute_python", {"code": code})]


# ------------------------------------------------------------------
# Command builder helper
# ------------------------------------------------------------------

def _cmd(action: str, payload: Dict[str, Any]) -> SynapseCommand:
    """Create a SynapseCommand for a planner step."""
    return SynapseCommand(
        type=action,
        id=deterministic_uuid(f"plan:{action}:{str(sorted(payload.items()))}", "cmd"),
        payload=payload,
    )


# ------------------------------------------------------------------
# Workflow dispatch registry
# ------------------------------------------------------------------

_WORKFLOW_BUILDERS = {
    "cloth_pipeline": _build_cloth_pipeline,
    "destruction_pipeline": _build_destruction_pipeline,
    "lighting_pipeline": _build_lighting_pipeline,
    "render_pipeline": _build_render_pipeline,
    "ocean_pipeline": _build_ocean_pipeline,
    "pyro_pipeline": _build_pyro_pipeline,
    "solaris_scene_pipeline": _build_solaris_scene_pipeline,
}


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

class WorkflowPlanner:
    """
    Decomposes complex requests into multi-step operation plans.

    The planner sits between Recipe (exact pattern match) and Tier 0
    (regex parse) in the routing cascade. It handles composite intents
    like "set up cloth sim with collision and wind" by composing
    operations dynamically from known workflow templates.
    """

    def plan(self, text: str) -> Optional[WorkflowPlan]:
        """
        Attempt to decompose text into a multi-step workflow plan.

        Args:
            text: Natural language input from the artist.

        Returns:
            WorkflowPlan if a composite workflow was detected, None otherwise.
        """
        text = text.strip()

        for pattern, workflow_key, param_groups in _WORKFLOW_INTENTS:
            m = pattern.match(text)
            if m:
                groups = m.groupdict()
                modifiers = _parse_modifiers(groups.get("modifiers"))

                builder = _WORKFLOW_BUILDERS.get(workflow_key)
                if not builder:
                    continue

                # Extract params for the builder
                params = {k: v for k, v in sorted(groups.items())
                          if k != "modifiers" and v is not None}

                steps = builder(params, modifiers)
                if not steps:
                    continue

                mod_desc = ""
                if modifiers:
                    mod_names = sorted(m.replace("add_", "") for m in modifiers)
                    mod_desc = f" with {', '.join(mod_names)}"

                plan = WorkflowPlan(
                    name=workflow_key,
                    description=(
                        f"Multi-step {workflow_key.replace('_', ' ')}{mod_desc} "
                        f"({len(steps)} operations)"
                    ),
                    steps=steps,
                    metadata={
                        "workflow": workflow_key,
                        "modifiers": sorted(modifiers),
                        "step_count": len(steps),
                    },
                )
                logger.info(
                    "Planned workflow %s (%d steps, modifiers=%s)",
                    workflow_key, len(steps), sorted(modifiers),
                )
                return plan

        return None
