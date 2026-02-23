"""
Synapse Recipe Registry

Pre-built, pre-approved multi-step operation templates.
Recipes execute at Tier 0 speed by expanding triggers into
sequences of SynapseCommands without any LLM involvement.

Artists can register custom recipes via registry.register().
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from ..core.protocol import SynapseCommand
from ..core.gates import GateLevel
from ..core.determinism import deterministic_uuid


@dataclass
class RecipeStep:
    """A single step in a recipe template."""
    action: str                        # CommandType value
    payload_template: Dict[str, Any]   # Values may contain {placeholders}
    gate_level: GateLevel = GateLevel.REVIEW
    output_var: str = ""               # If set, response data stored as ${var}.{field}

    def instantiate(self, params: Dict[str, str]) -> SynapseCommand:
        """Fill placeholders and return a SynapseCommand."""
        payload = {}
        for key, value in sorted(self.payload_template.items()):
            if isinstance(value, str) and "{" in value:
                payload[key] = value.format(**params)
            else:
                payload[key] = value

        return SynapseCommand(
            type=self.action,
            id=deterministic_uuid(
                f"recipe:{self.action}:{json.dumps(payload, sort_keys=True, default=str)}", "cmd"
            ),
            payload=payload,
        )

    def instantiate_with_vars(self, variables: Dict[str, str]) -> SynapseCommand:
        """Fill placeholders using accumulated variables (supports $var.field syntax)."""
        payload = {}
        for key, value in sorted(self.payload_template.items()):
            if isinstance(value, str):
                # Replace $var.field references first
                resolved = value
                for var_key in sorted(variables.keys(), key=len, reverse=True):
                    resolved = resolved.replace(var_key, str(variables[var_key]))
                # Then standard {param} placeholders
                if "{" in resolved:
                    resolved = resolved.format(**{
                        k: v for k, v in sorted(variables.items())
                        if not k.startswith("$")
                    })
                payload[key] = resolved
            else:
                payload[key] = value

        return SynapseCommand(
            type=self.action,
            id=deterministic_uuid(
                f"recipe:{self.action}:{json.dumps(payload, sort_keys=True, default=str)}", "cmd"
            ),
            payload=payload,
        )


@dataclass
class Recipe:
    """A pre-built multi-step operation template."""
    name: str
    description: str
    triggers: List[str]                # Regex patterns (case-insensitive)
    parameters: List[str]              # Named capture groups expected
    steps: List[RecipeStep]
    gate_level: GateLevel = GateLevel.REVIEW
    category: str = "general"

    _compiled: List["re.Pattern[str]"] = field(default_factory=list, repr=False)

    def __post_init__(self):
        self._compiled = [
            re.compile(t, re.IGNORECASE) for t in self.triggers
        ]

    def match(self, text: str) -> Optional[Dict[str, str]]:
        """
        Try to match text against trigger patterns.

        Returns extracted parameters on match, None otherwise.
        """
        text = text.strip()
        for pattern in self._compiled:
            m = pattern.match(text)
            if m:
                params = m.groupdict()
                # Fill defaults for missing optional params
                for p in self.parameters:
                    if p not in params or params[p] is None:
                        params[p] = ""
                return params
        return None

    def instantiate(self, params: Dict[str, str]) -> List[SynapseCommand]:
        """Fill templates with extracted params, return command list."""
        return [step.instantiate(params) for step in self.steps]

    def execute(
        self,
        params: Dict[str, str],
        command_fn,
    ) -> List[Tuple[SynapseCommand, Any]]:
        """Execute recipe with data flow between steps.

        Each step can declare output_var. After execution, response data
        fields become ${var}.{field} variables available to later steps.

        Args:
            params: Initial parameters from trigger match.
            command_fn: Callable(SynapseCommand) -> SynapseResponse.

        Returns:
            List of (command, response) tuples.
        """
        variables: Dict[str, str] = dict(params)
        results: List[Tuple[SynapseCommand, Any]] = []
        for step in self.steps:
            cmd = step.instantiate_with_vars(variables)
            resp = command_fn(cmd)
            results.append((cmd, resp))
            if step.output_var and hasattr(resp, "data") and isinstance(resp.data, dict):
                for k, v in sorted(resp.data.items()):  # sorted: He2025
                    variables[f"${step.output_var}.{k}"] = str(v)
        return results


class RecipeRegistry:
    """
    Registry of pre-built recipes.

    Matches input text against all registered recipes.
    Built-in recipes are registered on construction.
    """

    def __init__(self, include_builtins: bool = True):
        self._recipes: List[Recipe] = []
        if include_builtins:
            self._register_builtins()

    def register(self, recipe: Recipe):
        """Register a custom recipe."""
        self._recipes.append(recipe)

    def match(self, text: str) -> Optional[Tuple[Recipe, Dict[str, str]]]:
        """
        Try to match text against all registered recipes.

        Returns (recipe, params) on match, None otherwise.
        """
        text = text.strip()
        for recipe in self._recipes:
            params = recipe.match(text)
            if params is not None:
                return (recipe, params)
        return None

    @property
    def recipes(self) -> List[Recipe]:
        """List of registered recipes."""
        return list(self._recipes)

    def _register_builtins(self):
        """Register the built-in recipe library."""

        # --- Three-Point Lighting ---
        self.register(Recipe(
            name="three_point_lighting",
            description="Create a three-point lighting setup (key, fill, rim)",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?three[\s-]point\s+light(?:ing)?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="lighting",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "hlight",
                        "name": "key_light",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/key_light",
                        "parm": "light_exposure",
                        "value": 4,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "hlight",
                        "name": "fill_light",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/fill_light",
                        "parm": "light_exposure",
                        "value": 2,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "hlight",
                        "name": "rim_light",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/rim_light",
                        "parm": "light_exposure",
                        "value": 3,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Scatter & Copy ---
        self.register(Recipe(
            name="scatter_copy",
            description="Scatter source points onto target geometry using copy-to-points",
            triggers=[
                r"^scatter\s+(?P<source>[\w\-./]+)\s+(?:on(?:to)?|over)\s+(?P<target>[\w\-./]+)$",
            ],
            parameters=["source", "target"],
            gate_level=GateLevel.REVIEW,
            category="geometry",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "scatter",
                        "name": "scatter1",
                        "parent": "{target}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "copytopoints",
                        "name": "copytopoints1",
                        "parent": "{target}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="connect_nodes",
                    payload_template={
                        "source": "{source}",
                        "target": "{target}/copytopoints1",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Null Controller ---
        self.register(Recipe(
            name="null_controller",
            description="Create a null node as a controller with display flag",
            triggers=[
                r"^create\s+(?:a\s+)?(?:null\s+)?controller(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="utility",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "null",
                        "name": "controller",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/controller",
                        "parm": "controltype",
                        "value": 1,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Color Correction Setup (COPs) ---
        self.register(Recipe(
            name="color_correction_setup",
            description="Create a color correction chain (color_correct -> grade -> null merge point)",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?color\s+correct(?:ion)?(?:\s+(?:chain|setup|stack))?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="compositing",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "colorcorrect",
                        "name": "color_correct1",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/color_correct1",
                        "parm": "saturation",
                        "value": 1.0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "grade",
                        "name": "grade1",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="connect_nodes",
                    payload_template={
                        "source": "{parent}/color_correct1",
                        "target": "{parent}/grade1",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Dome Light Environment ---
        self.register(Recipe(
            name="dome_light_environment",
            description="Create a dome light with texture and exposure for environment lighting",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?dome\s*light(?:\s+(?:with|using)\s+(?P<texture>.+))?$",
                r"^(?:add|create)\s+(?:an?\s+)?(?:environment|env|hdri)\s+light(?:\s+(?:with|using)\s+(?P<texture>.+))?$",
            ],
            parameters=["texture"],
            gate_level=GateLevel.REVIEW,
            category="lighting",
            steps=[
                RecipeStep(
                    action="create_usd_prim",
                    payload_template={
                        "prim_path": "/lights/dome_light",
                        "prim_type": "DomeLight",
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="dome",
                ),
                RecipeStep(
                    action="set_usd_attribute",
                    payload_template={
                        "prim_path": "/lights/dome_light",
                        "attribute_name": "xn__inputsexposure_vya",
                        "value": 0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Camera Rig ---
        self.register(Recipe(
            name="camera_rig",
            description="Create a camera with focal length and position",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?camera(?:\s+(?:at|in)\s+(?P<parent>.+))?$",
                r"^(?:add)\s+(?:a\s+)?(?:render\s+)?camera(?:\s+(?:at|in)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="camera",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "cam",
                        "name": "render_cam",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="cam",
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "{parent}/render_cam",
                        "parm": "focal",
                        "value": 50,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Pyro Source Setup ---
        self.register(Recipe(
            name="pyro_source_setup",
            description="Create a pyro source setup with scatter and attribute wrangle",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?pyro\s+source(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "scatter",
                        "name": "pyro_scatter",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "attribwrangle",
                        "name": "pyro_source_attrs",
                        "parent": "{parent}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="connect_nodes",
                    payload_template={
                        "source": "{parent}/pyro_scatter",
                        "target": "{parent}/pyro_source_attrs",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Material Quick Setup ---
        self.register(Recipe(
            name="material_quick_setup",
            description="Create a MaterialX standard surface material and assign it",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:quick\s+)?material\s+(?:named?\s+)?(?P<name>\w+)$",
            ],
            parameters=["name"],
            gate_level=GateLevel.REVIEW,
            category="materials",
            steps=[
                RecipeStep(
                    action="create_material",
                    payload_template={
                        "name": "{name}",
                        "base_color": [0.8, 0.8, 0.8],
                        "roughness": 0.4,
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="mat",
                ),
            ],
        ))

        # --- Karma Render Setup ---
        self.register(Recipe(
            name="karma_render_setup",
            description="Create a Karma render setup with resolution and camera",
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?karma\s+render(?:\s+setup)?$",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "usdrender_rop",
                        "name": "karma_render",
                        "parent": "/stage",
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="rop",
                ),
            ],
        ))

        # --- SOPImport Chain ---
        self.register(Recipe(
            name="sopimport_chain",
            description="Create a SOP Import LOP to bring SOP geometry into the USD stage",
            triggers=[
                r"^(?:import|bring)\s+(?P<sop_path>[\w\-./]+)\s+(?:into|to)\s+(?:the\s+)?(?:usd\s+)?stage$",
            ],
            parameters=["sop_path"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "sopimport",
                        "name": "sopimport1",
                        "parent": "/stage",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "/stage/sopimport1",
                        "parm": "soppath",
                        "value": "{sop_path}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Edit Transform ---
        self.register(Recipe(
            name="edit_transform",
            description="Create an edit node for transforming USD prims",
            triggers=[
                r"^(?:edit|transform)\s+(?P<prim_path>[\w\-./]+)\s+(?:position|translate|move)$",
            ],
            parameters=["prim_path"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="create_node",
                    payload_template={
                        "type": "edit",
                        "name": "edit_xform",
                        "parent": "/stage",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "/stage/edit_xform",
                        "parm": "primpattern",
                        "value": "{prim_path}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # ==================================================================
        # PRODUCTION RECIPES — Real VFX workflows
        # ==================================================================

        # --- Vellum Cloth Simulation ---
        self.register(Recipe(
            name="vellum_cloth_sim",
            description=(
                "Set up a complete Vellum cloth simulation: "
                "vellumcloth configure -> vellumsolver -> filecache. "
                "Configures stretch/bend stiffness, substeps, and collision."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:vellum\s+)?cloth\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:add|create)\s+(?:a\s+)?vellum\s+cloth(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Create Vellum cloth configure\n"
                            "cloth = parent.createNode('vellumcloth', 'vellum_cloth')\n"
                            "cloth.parm('stretchstiffness').set(10000)\n"
                            "cloth.parm('bendstiffness').set(0.001)\n"
                            "cloth.parm('thickness').set(0.01)\n"
                            "# Create Vellum solver\n"
                            "solver = parent.createNode('vellumsolver', 'vellum_solver')\n"
                            "solver.parm('substeps').set(5)\n"
                            "# Wire: cloth geo output -> solver input 1\n"
                            "solver.setInput(0, cloth, 0)\n"
                            "# Wire: cloth constraints output -> solver input 2\n"
                            "solver.setInput(2, cloth, 1)\n"
                            "# File cache for sim output\n"
                            "cache = parent.createNode('filecache', 'cloth_cache')\n"
                            "cache.parm('file').set('$HIP/cache/cloth.$F4.bgeo.sc')\n"
                            "cache.setInput(0, solver, 0)\n"
                            "cache.setDisplayFlag(True)\n"
                            "cache.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': cache.path(), 'solver': solver.path(), "
                            "'cloth': cloth.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="cloth_sim",
                ),
            ],
        ))

        # --- RBD Destruction ---
        self.register(Recipe(
            name="rbd_destruction",
            description=(
                "Set up an RBD destruction pipeline: "
                "rbdmaterialfracture -> assemble -> rbdconstraintsfromrules -> "
                "rbdconstraintproperties (glue) -> rigidsolver -> filecache."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:rbd\s+)?destruction(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:rbd\s+)?fracture\s+(?:sim|simulation|pipeline)(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:destroy|fracture|break)\s+(?P<parent>[\w\-./]+)$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Fracture\n"
                            "frac = parent.createNode('rbdmaterialfracture', 'fracture')\n"
                            "frac.parm('numpieces').set(50)\n"
                            "# Assemble into packed prims\n"
                            "asm = parent.createNode('assemble', 'assemble')\n"
                            "asm.parm('create_packed').set(True)\n"
                            "asm.setInput(0, frac, 0)\n"
                            "# Constraints from proximity\n"
                            "cons = parent.createNode('rbdconstraintsfromrules', 'constraints')\n"
                            "cons.setInput(0, asm, 0)\n"
                            "# Glue constraint properties\n"
                            "props = parent.createNode('rbdconstraintproperties', 'glue_props')\n"
                            "props.parm('type').set(0)  # Glue\n"
                            "props.parm('strength').set(500)\n"
                            "props.setInput(0, cons, 0)\n"
                            "# Rigid body solver\n"
                            "solver = parent.createNode('rigidsolver', 'rbd_solver')\n"
                            "solver.setInput(0, asm, 0)\n"
                            "solver.setInput(2, props, 0)\n"
                            "# Cache\n"
                            "cache = parent.createNode('filecache', 'rbd_cache')\n"
                            "cache.parm('file').set('$HIP/cache/rbd.$F4.bgeo.sc')\n"
                            "cache.setInput(0, solver, 0)\n"
                            "cache.setDisplayFlag(True)\n"
                            "cache.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': cache.path(), 'solver': solver.path(), "
                            "'fracture': frac.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="rbd",
                ),
            ],
        ))

        # --- Turntable Render ---
        self.register(Recipe(
            name="turntable_render",
            description=(
                "Set up a render-ready turntable: orbiting camera (360 deg "
                "over frame range), three-point lighting with Lighting Law "
                "exposure, dome light environment, Karma render settings with AOVs."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?turntable(?:\s+render)?(?:\s+(?:for|of|at|in)\s+(?P<target>.+))?$",
                r"^(?:add|create)\s+(?:a\s+)?(?:render\s+)?turntable(?:\s+(?:for|of|at|in)\s+(?P<target>.+))?$",
            ],
            parameters=["target"],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "stage = hou.node('/stage') or hou.node('/obj')\n"
                            "# Camera with orbit expression\n"
                            "cam = stage.createNode('cam', 'turntable_cam')\n"
                            "cam.parm('focal').set(50)\n"
                            "# Orbit: rotate Y over frame range\n"
                            "cam.parm('tx').set(0)\n"
                            "cam.parm('ty').set(1)\n"
                            "cam.parm('tz').set(5)\n"
                            "cam.parm('ry').setExpression("
                            "'$FF / ($FEND - $FSTART + 1) * 360')\n"
                            "result = {{'camera': cam.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="tt_cam",
                ),
                # Key light — Lighting Law: intensity 1.0, brightness via exposure
                RecipeStep(
                    action="create_usd_prim",
                    payload_template={
                        "prim_path": "/lights/turntable_key",
                        "prim_type": "RectLight",
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="tt_key",
                ),
                RecipeStep(
                    action="set_usd_attribute",
                    payload_template={
                        "prim_path": "/lights/turntable_key",
                        "attribute_name": "xn__inputsexposure_vya",
                        "value": 5.0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                # Fill light — 2 stops below key (4:1 ratio)
                RecipeStep(
                    action="create_usd_prim",
                    payload_template={
                        "prim_path": "/lights/turntable_fill",
                        "prim_type": "RectLight",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_usd_attribute",
                    payload_template={
                        "prim_path": "/lights/turntable_fill",
                        "attribute_name": "xn__inputsexposure_vya",
                        "value": 3.0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                # Rim light
                RecipeStep(
                    action="create_usd_prim",
                    payload_template={
                        "prim_path": "/lights/turntable_rim",
                        "prim_type": "RectLight",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_usd_attribute",
                    payload_template={
                        "prim_path": "/lights/turntable_rim",
                        "attribute_name": "xn__inputsexposure_vya",
                        "value": 4.5,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                # Dome light for environment fill
                RecipeStep(
                    action="create_usd_prim",
                    payload_template={
                        "prim_path": "/lights/turntable_dome",
                        "prim_type": "DomeLight",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_usd_attribute",
                    payload_template={
                        "prim_path": "/lights/turntable_dome",
                        "attribute_name": "xn__inputsexposure_vya",
                        "value": 0.0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Ocean Setup ---
        self.register(Recipe(
            name="ocean_setup",
            description=(
                "Set up an ocean: oceanspectrum -> oceanevaluate for "
                "displaced surface. Configurable wind speed and chop."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:an?\s+)?ocean(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:add|create)\s+(?:an?\s+)?ocean\s+(?:surface|sim|fx)(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Ocean spectrum — wave frequency data\n"
                            "spec = parent.createNode('oceanspectrum', 'ocean_spectrum')\n"
                            "spec.parm('speed').set(15)  # wind m/s\n"
                            "spec.parm('chop').set(0.7)\n"
                            "spec.parm('gridsize').set(6)  # 2^6 = 64 resolution\n"
                            "spec.parm('depth').set(200)\n"
                            "# Ocean evaluate — displaced geometry\n"
                            "evl = parent.createNode('oceanevaluate', 'ocean_evaluate')\n"
                            "evl.setInput(0, spec, 0)\n"
                            "# Output null\n"
                            "out = parent.createNode('null', 'OCEAN_OUT')\n"
                            "out.setInput(0, evl, 0)\n"
                            "out.setDisplayFlag(True)\n"
                            "out.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': out.path(), 'spectrum': spec.path(), "
                            "'evaluate': evl.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="ocean",
                ),
            ],
        ))

        # --- Full Pyro Fire Simulation ---
        self.register(Recipe(
            name="pyro_fire_sim",
            description=(
                "Set up a complete pyro fire simulation: scatter source points "
                "-> attribwrangle (density/temperature/flame/velocity) -> "
                "volumerasterizeattributes -> pyrosolver -> filecache."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:pyro\s+)?fire\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:full\s+)?pyro\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Scatter source points\n"
                            "scatter = parent.createNode('scatter', 'pyro_source_pts')\n"
                            "scatter.parm('npts').set(5000)\n"
                            "# Emission attributes wrangle\n"
                            "wrangle = parent.createNode('attribwrangle', 'emission_attrs')\n"
                            "wrangle.parm('snippet').set("
                            "'f@density = 1;\\n"
                            "f@temperature = 2;\\n"
                            "f@flame = 1;\\n"
                            "v@v = set(0, 2 + rand(@ptnum)*0.5, 0);\\n"
                            "f@pscale = 0.05;')\n"
                            "wrangle.setInput(0, scatter, 0)\n"
                            "# Rasterize to volumes\n"
                            "rast = parent.createNode('volumerasterizeattributes', "
                            "'rasterize')\n"
                            "rast.parm('attributes').set('density temperature flame')\n"
                            "rast.setInput(0, wrangle, 0)\n"
                            "# Pyro solver\n"
                            "solver = parent.createNode('pyrosolver', 'pyro_solver')\n"
                            "solver.parm('divsize').set(0.05)\n"
                            "solver.parm('tempcooling').set(0.6)\n"
                            "solver.parm('dissipation').set(0.1)\n"
                            "solver.setInput(0, rast, 0)\n"
                            "# Cache\n"
                            "cache = parent.createNode('filecache', 'pyro_cache')\n"
                            "cache.parm('file').set('$HIP/cache/pyro.$F4.bgeo.sc')\n"
                            "cache.setInput(0, solver, 0)\n"
                            "cache.setDisplayFlag(True)\n"
                            "cache.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': cache.path(), 'solver': solver.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="pyro",
                ),
            ],
        ))

        # --- Vellum Hair / Wire Simulation ---
        self.register(Recipe(
            name="vellum_wire_sim",
            description=(
                "Set up Vellum hair/wire simulation for cables, ropes, or "
                "strands: vellumhair configure -> vellumsolver -> filecache."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:vellum\s+)?(?:wire|cable|rope|hair)\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:add|sim(?:ulate)?)\s+(?:a\s+)?(?:vellum\s+)?(?:wire|cable|rope|hair)s?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="fx",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Vellum hair configure (used for wires/cables)\n"
                            "hair = parent.createNode('vellumhair', 'vellum_wire')\n"
                            "hair.parm('stretchstiffness').set(50000)\n"
                            "hair.parm('bendstiffness').set(1.0)\n"
                            "# Vellum solver\n"
                            "solver = parent.createNode('vellumsolver', 'wire_solver')\n"
                            "solver.parm('substeps').set(3)\n"
                            "solver.setInput(0, hair, 0)\n"
                            "solver.setInput(2, hair, 1)\n"
                            "# Cache\n"
                            "cache = parent.createNode('filecache', 'wire_cache')\n"
                            "cache.parm('file').set('$HIP/cache/wires.$F4.bgeo.sc')\n"
                            "cache.setInput(0, solver, 0)\n"
                            "cache.setDisplayFlag(True)\n"
                            "cache.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': cache.path(), 'solver': solver.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="wire_sim",
                ),
            ],
        ))

        # --- Terrain with Erosion ---
        self.register(Recipe(
            name="terrain_environment",
            description=(
                "Create a heightfield terrain with noise shaping and "
                "hydraulic/thermal erosion for environment work."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?terrain(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?heightfield(?:\s+terrain)?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
                r"^(?:add|build)\s+(?:a\s+)?(?:terrain|landscape|environment\s+ground)(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="environment",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "parent = hou.node('{parent}') or hou.node('/obj')\n"
                            "# Heightfield base\n"
                            "hf = parent.createNode('heightfield', 'terrain_base')\n"
                            "hf.parm('sizex').set(500)\n"
                            "hf.parm('sizey').set(500)\n"
                            "hf.parm('gridspacing').set(1.0)\n"
                            "# Noise for shape\n"
                            "noise = parent.createNode('heightfield_noise', "
                            "'terrain_noise')\n"
                            "noise.parm('height').set(80)\n"
                            "noise.parm('noisefreq').set(0.005)\n"
                            "noise.parm('octaves').set(6)\n"
                            "noise.setInput(0, hf, 0)\n"
                            "# Hydraulic erosion\n"
                            "erode = parent.createNode('heightfield_erode', "
                            "'erosion')\n"
                            "erode.parm('iterations').set(50)\n"
                            "erode.setInput(0, noise, 0)\n"
                            "# Output null\n"
                            "out = parent.createNode('null', 'TERRAIN_OUT')\n"
                            "out.setInput(0, erode, 0)\n"
                            "out.setDisplayFlag(True)\n"
                            "out.setRenderFlag(True)\n"
                            "parent.layoutChildren()\n"
                            "result = {{'node': out.path(), 'erosion': erode.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="terrain",
                ),
            ],
        ))

        # --- Lookdev Scene ---
        self.register(Recipe(
            name="lookdev_scene",
            description=(
                "Set up a standard lookdev/turntable scene in LOPs: "
                "dome light (environment fill), key light (exposure 5), "
                "fill light (exposure 3, 4:1 ratio), backdrop grid, camera. "
                "Lighting Law compliant: all intensities 1.0."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?lookdev(?:\s+scene)?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?(?:lookdev|look\s+dev)\s+(?:environment|setup|stage)$",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="lighting",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "stage = hou.node('/stage')\n"
                            "if not stage:\n"
                            "    stage = hou.node('/obj')\n"
                            "# Dome light for environment fill\n"
                            "dome = stage.createNode('domelight', 'env_dome')\n"
                            "# Key light\n"
                            "key = stage.createNode('rectlight', 'key_light')\n"
                            "key.parm('tx').set(3)\n"
                            "key.parm('ty').set(4)\n"
                            "key.parm('tz').set(3)\n"
                            "key.parm('rx').set(-35)\n"
                            "key.parm('ry').set(40)\n"
                            "# Fill light — 2 stops below key for 4:1 ratio\n"
                            "fill = stage.createNode('rectlight', 'fill_light')\n"
                            "fill.parm('tx').set(-3)\n"
                            "fill.parm('ty').set(2)\n"
                            "fill.parm('tz').set(2)\n"
                            "fill.parm('rx').set(-15)\n"
                            "fill.parm('ry').set(-45)\n"
                            "# Camera\n"
                            "cam = stage.createNode('cam', 'lookdev_cam')\n"
                            "cam.parm('tx').set(0)\n"
                            "cam.parm('ty').set(1)\n"
                            "cam.parm('tz').set(5)\n"
                            "cam.parm('rx').set(-10)\n"
                            "cam.parm('focal').set(85)\n"
                            "stage.layoutChildren()\n"
                            "result = {{'dome': dome.path(), 'key': key.path(), "
                            "'fill': fill.path(), 'camera': cam.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="lookdev",
                ),
                # Set exposures via USD (Lighting Law: intensity stays 1.0)
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "$lookdev.dome",
                        "parm": "light_exposure",
                        "value": 0,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "$lookdev.key",
                        "parm": "light_exposure",
                        "value": 5,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="set_parm",
                    payload_template={
                        "node": "$lookdev.fill",
                        "parm": "light_exposure",
                        "value": 3,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- File Cache ---
        self.register(Recipe(
            name="file_cache",
            description=(
                "Add a file cache node to cache any SOP output to disk. "
                "Uses bgeo.sc format with frame padding."
            ),
            triggers=[
                r"^cache\s+(?P<source>[\w\-./]+)(?:\s+to\s+disk)?$",
                r"^(?:add|create)\s+(?:a\s+)?(?:file\s*)?cache\s+(?:for|on|after)\s+(?P<source>[\w\-./]+)$",
            ],
            parameters=["source"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "src = hou.node('{source}')\n"
                            "if not src:\n"
                            "    result = {{'error': 'Could not find node: {source}'}}\n"
                            "else:\n"
                            "    parent = src.parent()\n"
                            "    cache = parent.createNode('filecache', "
                            "src.name() + '_cache')\n"
                            "    cache.parm('file').set("
                            "'$HIP/cache/' + src.name() + '.$F4.bgeo.sc')\n"
                            "    cache.setInput(0, src, 0)\n"
                            "    cache.setDisplayFlag(True)\n"
                            "    cache.setRenderFlag(True)\n"
                            "    parent.layoutChildren()\n"
                            "    result = {{'node': cache.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="cached",
                ),
            ],
        ))

        # ==================================================================
        # TOPS / PDG RECIPES — Autonomous pipeline operations
        # ==================================================================

        # --- TOPS Parameter Sweep ---
        self.register(Recipe(
            name="tops_parameter_sweep",
            description=(
                "Set up a wedge parameter sweep and cook it with validation. "
                "Sweeps an attribute from start to end in N steps."
            ),
            triggers=[
                r"^sweep\s+(?P<attr_name>\w+)\s+from\s+(?P<start>[\d.]+)\s+to\s+(?P<end>[\d.]+)(?:\s+in\s+(?P<steps>\d+)\s+steps?)?(?:\s+(?:in|on|at)\s+(?P<topnet>[\w\-./]+))?$",
            ],
            parameters=["attr_name", "start", "end", "steps", "topnet"],
            gate_level=GateLevel.REVIEW,
            category="tops",
            steps=[
                RecipeStep(
                    action="tops_setup_wedge",
                    payload_template={
                        "topnet_path": "{topnet}",
                        "attributes": [{"name": "{attr_name}", "type": "float",
                                        "start": "{start}", "end": "{end}",
                                        "steps": 10}],
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="wedge",
                ),
                RecipeStep(
                    action="tops_cook_and_validate",
                    payload_template={
                        "node": "$wedge.wedge_node",
                        "max_retries": 1,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
                RecipeStep(
                    action="tops_get_cook_stats",
                    payload_template={
                        "node": "$wedge.wedge_node",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- TOPS Quick Cook ---
        self.register(Recipe(
            name="tops_quick_cook",
            description="Cook a TOP node and validate results with one retry.",
            triggers=[
                r"^(?:cook\s+and\s+check|quick\s+cook)\s+(?P<node>[\w\-./]+)$",
            ],
            parameters=["node"],
            gate_level=GateLevel.REVIEW,
            category="tops",
            steps=[
                RecipeStep(
                    action="tops_cook_and_validate",
                    payload_template={
                        "node": "{node}",
                        "max_retries": 1,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- TOPS Diagnose ---
        self.register(Recipe(
            name="tops_diagnose_recipe",
            description="Diagnose failures on a TOP node.",
            triggers=[
                r"^diagnose\s+(?P<node>[\w\-./]+)$",
                r"^what(?:'s|\s+is)\s+wrong\s+with\s+(?P<node>[\w\-./]+)$",
            ],
            parameters=["node"],
            gate_level=GateLevel.REVIEW,
            category="tops",
            steps=[
                RecipeStep(
                    action="tops_diagnose",
                    payload_template={
                        "node": "{node}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Quick Render Preview ---
        self.register(Recipe(
            name="render_preview",
            description=(
                "Render a quick preview: 640x360, 32 samples, Karma XPU. "
                "Optimized for fast iteration during layout and lighting."
            ),
            triggers=[
                r"^(?:quick\s+)?(?:render|preview)\s+(?:at\s+)?(?:low|preview|draft)\s*(?:quality|res)?$",
                r"^(?:render|do)\s+(?:a\s+)?(?:quick|fast)\s+(?:render|preview)$",
                r"^(?:test|preview)\s+render$",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="render",
                    payload_template={
                        "width": 640,
                        "height": 360,
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- HDA Scaffold ---
        self.register(Recipe(
            name="hda_scaffold",
            description=(
                "Scaffold a complete HDA: create subnet with IN/OUT nulls, "
                "create digital asset definition, add standard parameter "
                "interface, and save to $HIP/otls/."
            ),
            triggers=[
                r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)\s+(?:called|named)\s+(?P<name>[\w]+)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
                r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)\s+(?P<name>[\w]+)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
                r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
                r"^(?:new|setup)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
                r"^hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
            ],
            parameters=["name", "description"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import os\n"
                            "import re\n"
                            "# Parameters from trigger\n"
                            "raw_name = '{name}'.strip()\n"
                            "description = '{description}'.strip()\n"
                            "# Derive names\n"
                            "if not raw_name:\n"
                            "    raw_name = 'custom_tool'\n"
                            "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                            "raw_name.lower()).strip('_')\n"
                            "hda_label = raw_name.replace('_', ' ').title()\n"
                            "# Find parent context\n"
                            "sel = hou.selectedNodes()\n"
                            "if sel and sel[0].type().category() == "
                            "hou.sopNodeTypeCategory():\n"
                            "    parent = sel[0].parent()\n"
                            "elif sel:\n"
                            "    parent = sel[0]\n"
                            "else:\n"
                            "    obj = hou.node('/obj')\n"
                            "    parent = obj.createNode('geo', "
                            "hda_name + '_dev')\n"
                            "    parent.moveToGoodPosition()\n"
                            "# Create subnet structure\n"
                            "subnet = parent.createNode('subnet', hda_name)\n"
                            "input_null = subnet.createNode('null', 'IN')\n"
                            "input_null.setPosition(hou.Vector2(0, 0))\n"
                            "output_null = subnet.createNode('null', 'OUT')\n"
                            "output_null.setPosition(hou.Vector2(0, -3))\n"
                            "output_null.setInput(0, input_null)\n"
                            "output_null.setDisplayFlag(True)\n"
                            "output_null.setRenderFlag(True)\n"
                            "input_null.setInput(0, "
                            "subnet.indirectInputs()[0])\n"
                            "subnet.layoutChildren()\n"
                            "subnet.moveToGoodPosition()\n"
                            "# Create HDA definition\n"
                            "otls_dir = os.path.join("
                            "hou.getenv('HIP', ''), 'otls')\n"
                            "if not os.path.exists(otls_dir):\n"
                            "    os.makedirs(otls_dir)\n"
                            "hda_path = os.path.join(otls_dir, "
                            "hda_name + '.hda')\n"
                            "hda_node = subnet.createDigitalAsset(\n"
                            "    name=hda_name,\n"
                            "    hda_file_name=hda_path,\n"
                            "    description=hda_label,\n"
                            "    min_num_inputs=1,\n"
                            "    max_num_inputs=1,\n"
                            ")\n"
                            "# Configure HDA definition\n"
                            "definition = hda_node.type().definition()\n"
                            "help_text = '= ' + hda_label + ' =\\n\\n'\n"
                            "if description:\n"
                            "    help_text += description + '\\n\\n'\n"
                            "help_text += '== Parameters ==\\n\\n'\n"
                            "help_text += 'See parameter interface "
                            "for controls.\\n'\n"
                            "definition.setExtraFileOption("
                            "'Help', help_text)\n"
                            "definition.setIcon('SOP_subnet')\n"
                            "definition.setExtraFileOption("
                            "'CreatedBy', 'Synapse HDA Scaffold')\n"
                            "# Standard parameter interface\n"
                            "ptg = hda_node.parmTemplateGroup()\n"
                            "main_folder = hou.FolderParmTemplate(\n"
                            "    'main_folder', 'Main', "
                            "folder_type=hou.folderType.Tabs)\n"
                            "if description:\n"
                            "    main_folder.addParmTemplate(\n"
                            "        hou.LabelParmTemplate("
                            "'info_label', 'Purpose', "
                            "column_labels=[description]))\n"
                            "main_folder.addParmTemplate(\n"
                            "    hou.FloatParmTemplate("
                            "'blend', 'Blend', 1, "
                            "default_value=(1.0,),\n"
                            "        min=0.0, max=1.0, "
                            "min_is_strict=True, "
                            "max_is_strict=True))\n"
                            "main_folder.addParmTemplate(\n"
                            "    hou.ToggleParmTemplate("
                            "'enable', 'Enable', "
                            "default_value=True))\n"
                            "ptg.append(main_folder)\n"
                            "hda_node.setParmTemplateGroup(ptg)\n"
                            "# Save and select\n"
                            "definition.save(hda_path, hda_node)\n"
                            "hda_node.setSelected(True, "
                            "clear_all_selected=True)\n"
                            "hda_node.setDisplayFlag(True)\n"
                            "hda_node.setRenderFlag(True)\n"
                            "result = {{\n"
                            "    'node': hda_node.path(),\n"
                            "    'hda_file': hda_path,\n"
                            "    'hda_name': hda_name,\n"
                            "    'hda_label': hda_label,\n"
                            "    'definition': 'Sop/' + hda_name,\n"
                            "    'description': description "
                            "or '(none provided)',\n"
                            "}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="hda",
                ),
            ],
        ))

        # --- LOP HDA Scaffold ---
        self.register(Recipe(
            name="lop_hda_scaffold",
            description=(
                "Scaffold a Solaris (LOP) HDA: create subnet in /stage with "
                "stage passthrough, edit properties and configure primitive "
                "nodes, convert to HDA, promote primpath, and save to "
                "$HIP/otls/synapse/."
            ),
            triggers=[
                r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:solaris|lop|usd)\s+(?:hda|digital asset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
                r"^(?:create|make|build)\s+(?:an?\s+)?(?:lop|solaris|usd)\s+(?:hda|digital asset)\s+(?P<name>[\w]+)(?:\s+(?P<description>.+))?$",
                r"^(?:new|setup)\s+(?:lop|solaris)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
                r"^(?:lop|solaris)\s+hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
                r"^build\s+(?:an?\s+)?usd\s+digital\s+asset(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
            ],
            parameters=["name", "description"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import os\n"
                            "import re\n"
                            "# Parameters from trigger\n"
                            "raw_name = '{name}'.strip()\n"
                            "description = '{description}'.strip()\n"
                            "if not raw_name:\n"
                            "    raw_name = 'custom_lop_tool'\n"
                            "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                            "raw_name.lower()).strip('_')\n"
                            "hda_label = raw_name.replace('_', ' ').title()\n"
                            "# Find or create /stage context\n"
                            "stage = hou.node('/stage')\n"
                            "if not stage:\n"
                            "    stage = hou.node('/obj')\n"
                            "# Create LOP subnet\n"
                            "subnet = stage.createNode('subnet', hda_name)\n"
                            "# Wire subnet indirect input for stage passthrough\n"
                            "indirect = subnet.indirectInputs()[0]\n"
                            "# Create internal nodes\n"
                            "edit_props = subnet.createNode("
                            "'editproperties::2.0', 'edit_properties')\n"
                            "edit_props.setInput(0, indirect)\n"
                            "config_prim = subnet.createNode("
                            "'configureprimitive', 'configure_prim')\n"
                            "config_prim.setInput(0, edit_props)\n"
                            "config_prim.setDisplayFlag(True)\n"
                            "subnet.layoutChildren()\n"
                            "subnet.moveToGoodPosition()\n"
                            "# Create HDA definition\n"
                            "otls_dir = os.path.join("
                            "hou.getenv('HIP', ''), 'otls', 'synapse')\n"
                            "os.makedirs(otls_dir, exist_ok=True)\n"
                            "hda_path = os.path.join(otls_dir, "
                            "hda_name + '.hda')\n"
                            "hda_node = subnet.createDigitalAsset(\n"
                            "    name=hda_name,\n"
                            "    hda_file_name=hda_path,\n"
                            "    description=hda_label,\n"
                            "    min_num_inputs=1,\n"
                            "    max_num_inputs=1,\n"
                            ")\n"
                            "# Set LOP category\n"
                            "definition = hda_node.type().definition()\n"
                            "import time as _time\n"
                            "definition.setExtraInfo(\n"
                            "    'author=synapse;version=1.0.0;'\n"
                            "    'created=' + _time.strftime("
                            "'%Y-%m-%d %H:%M:%S'))\n"
                            "# Promote primpath from edit_properties\n"
                            "ptg = hda_node.parmTemplateGroup()\n"
                            "ep_node = hda_node.node('edit_properties')\n"
                            "if ep_node:\n"
                            "    pp = ep_node.parm('primpath')\n"
                            "    if pp:\n"
                            "        tpl = pp.parmTemplate().clone()\n"
                            "        tpl.setName('primpath')\n"
                            "        tpl.setLabel('Prim Path')\n"
                            "        ptg.append(tpl)\n"
                            "        hda_node.setParmTemplateGroup(ptg)\n"
                            "# Help text\n"
                            "help_text = '= ' + hda_label + ' =\\n\\n'\n"
                            "if description:\n"
                            "    help_text += description + '\\n\\n'\n"
                            "help_text += '#type: node\\n'\n"
                            "help_text += '#context: Lop\\n'\n"
                            "definition.addSection('HelpText', help_text)\n"
                            "# Save and select\n"
                            "definition.save(hda_path, hda_node)\n"
                            "hda_node.setSelected(True, "
                            "clear_all_selected=True)\n"
                            "hda_node.setDisplayFlag(True)\n"
                            "result = {{\n"
                            "    'node': hda_node.path(),\n"
                            "    'hda_file': hda_path,\n"
                            "    'hda_name': hda_name,\n"
                            "    'hda_label': hda_label,\n"
                            "    'definition': 'Lop/' + hda_name,\n"
                            "    'description': description "
                            "or '(none provided)',\n"
                            "}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="lop_hda",
                ),
            ],
        ))

        # --- Karma Quality HDA ---
        self.register(Recipe(
            name="karma_quality_hda",
            description=(
                "Create a Karma render quality preset HDA with draft/medium/final "
                "quality tiers, resolution control, and HScript-switched pixel samples."
            ),
            triggers=[
                r"^(?:create|make|build)\s+(?:a\s+)?karma\s+quality\s+(?:hda|digital asset|preset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?$",
                r"^(?:create|make|build)\s+(?:a\s+)?render\s+quality\s+(?:hda|digital asset|preset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?$",
                r"^(?:build|make)\s+(?:a\s+)?render\s+(?:settings|quality)\s+(?:hda|preset)(?:\s+(?P<name>[\w]+))?$",
                r"^karma\s+(?:quality|preset)\s+hda(?:\s+(?P<name>[\w]+))?$",
            ],
            parameters=["name"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import os\n"
                            "import re\n"
                            "import time as _time\n"
                            "raw_name = '{name}'.strip()\n"
                            "if not raw_name:\n"
                            "    raw_name = 'karma_quality'\n"
                            "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                            "raw_name.lower()).strip('_')\n"
                            "hda_label = raw_name.replace('_', ' ').title()\n"
                            "# Create in /stage\n"
                            "stage = hou.node('/stage')\n"
                            "if not stage:\n"
                            "    stage = hou.node('/obj')\n"
                            "subnet = stage.createNode('subnet', hda_name)\n"
                            "indirect = subnet.indirectInputs()[0]\n"
                            "# Karma render properties\n"
                            "karma_props = subnet.createNode("
                            "'karmarenderproperties', 'karma_props')\n"
                            "karma_props.setInput(0, indirect)\n"
                            "# Pixel samples switched by quality tier\n"
                            "# 0=draft(16), 1=medium(64), 2=final(256)\n"
                            "karma_props.parm('karma:global:pathtracedsamples'"
                            ").setExpression(\n"
                            "    'if(ch(\"../quality_tier\")==0, 16, "
                            "if(ch(\"../quality_tier\")==1, 64, 256))',\n"
                            "    hou.exprLanguage.Hscript)\n"
                            "# Resolution via edit properties\n"
                            "edit_res = subnet.createNode("
                            "'editproperties::2.0', 'resolution')\n"
                            "edit_res.setInput(0, karma_props)\n"
                            "edit_res.setDisplayFlag(True)\n"
                            "subnet.layoutChildren()\n"
                            "subnet.moveToGoodPosition()\n"
                            "# Create HDA\n"
                            "otls_dir = os.path.join("
                            "hou.getenv('HIP', ''), 'otls', 'synapse')\n"
                            "os.makedirs(otls_dir, exist_ok=True)\n"
                            "hda_path = os.path.join(otls_dir, "
                            "hda_name + '.hda')\n"
                            "hda_node = subnet.createDigitalAsset(\n"
                            "    name=hda_name,\n"
                            "    hda_file_name=hda_path,\n"
                            "    description=hda_label,\n"
                            "    min_num_inputs=1,\n"
                            "    max_num_inputs=1,\n"
                            ")\n"
                            "definition = hda_node.type().definition()\n"
                            "definition.setExtraInfo(\n"
                            "    'author=synapse;version=1.0.0;'\n"
                            "    'created=' + _time.strftime("
                            "'%Y-%m-%d %H:%M:%S'))\n"
                            "# Add quality_tier menu parameter\n"
                            "ptg = hda_node.parmTemplateGroup()\n"
                            "quality_menu = hou.MenuParmTemplate(\n"
                            "    'quality_tier', 'Quality Tier',\n"
                            "    menu_items=['0', '1', '2'],\n"
                            "    menu_labels=['Draft (16 spp)', "
                            "'Medium (64 spp)', 'Final (256 spp)'],\n"
                            "    default_value=0)\n"
                            "ptg.append(quality_menu)\n"
                            "# Promote resolution\n"
                            "res_node = hda_node.node('resolution')\n"
                            "if res_node:\n"
                            "    rp = res_node.parm('primpath')\n"
                            "    if rp:\n"
                            "        tpl = rp.parmTemplate().clone()\n"
                            "        tpl.setName('res_primpath')\n"
                            "        tpl.setLabel('Render Prim')\n"
                            "        ptg.append(tpl)\n"
                            "hda_node.setParmTemplateGroup(ptg)\n"
                            "# Help text\n"
                            "help_text = ('= ' + hda_label + ' =\\n\\n'\n"
                            "    'Karma render quality preset with three '\n"
                            "    'tiers: Draft (16 spp), Medium (64 spp), '\n"
                            "    'Final (256 spp).\\n\\n'\n"
                            "    '@parameters\\n\\n'\n"
                            "    'quality_tier:\\n'\n"
                            "    '    Select render quality level.\\n')\n"
                            "definition.addSection('HelpText', help_text)\n"
                            "definition.save(hda_path, hda_node)\n"
                            "hda_node.setSelected(True, "
                            "clear_all_selected=True)\n"
                            "hda_node.setDisplayFlag(True)\n"
                            "result = {{\n"
                            "    'node': hda_node.path(),\n"
                            "    'hda_file': hda_path,\n"
                            "    'hda_name': hda_name,\n"
                            "    'hda_label': hda_label,\n"
                            "    'definition': 'Lop/' + hda_name,\n"
                            "}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="karma_hda",
                ),
            ],
        ))

        # --- VEX Debug Wrangle ---
        self.register(Recipe(
            name="vex_debug_wrangle",
            description=(
                "Debug a VEX wrangle node: inspect inputs, check for "
                "errors, read attribute state, and suggest fixes."
            ),
            triggers=[
                r"^(?:debug|diagnose|check|inspect)\s+(?:the\s+)?(?:vex|wrangle|attribwrangle)(?:\s+(?:on|at|node)?\s*(?P<node>.+))?$",
                r"^what(?:'s| is)\s+wrong\s+with\s+(?:the\s+)?(?:vex|wrangle)(?:\s+(?:on|at)?\s*(?P<node>.+))?$",
                r"^fix\s+(?:the\s+)?(?:vex|wrangle)\s+(?:on|at)\s+(?P<node>.+)$",
            ],
            parameters=["node"],
            gate_level=GateLevel.REVIEW,
            category="utility",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import json\n"
                            "node_path = '{node}'.strip()\n"
                            "# Find wrangle node\n"
                            "node = None\n"
                            "if node_path:\n"
                            "    node = hou.node(node_path)\n"
                            "if node is None:\n"
                            "    # Try to find selected wrangle\n"
                            "    sel = hou.selectedNodes()\n"
                            "    for s in sel:\n"
                            "        if 'wrangle' in s.type().name():\n"
                            "            node = s\n"
                            "            break\n"
                            "if node is None:\n"
                            "    result = {{'error': 'No wrangle node found "
                            "-- select one or provide a path'}}\n"
                            "else:\n"
                            "    info = {{'node': node.path(), "
                            "'type': node.type().name()}}\n"
                            "    # Get snippet\n"
                            "    snip_parm = node.parm('snippet') or "
                            "node.parm('code')\n"
                            "    if snip_parm:\n"
                            "        info['snippet'] = snip_parm.eval()\n"
                            "    # Get run-over class\n"
                            "    class_parm = node.parm('class')\n"
                            "    if class_parm:\n"
                            "        class_map = {{0: 'Detail', 1: 'Points', "
                            "2: 'Vertices', 3: 'Primitives'}}\n"
                            "        info['run_over'] = class_map.get("
                            "class_parm.eval(), 'unknown')\n"
                            "    # Check errors\n"
                            "    try:\n"
                            "        errs = node.errors()\n"
                            "        if errs:\n"
                            "            info['errors'] = list(errs)\n"
                            "    except Exception:\n"
                            "        pass\n"
                            "    try:\n"
                            "        warns = node.warnings()\n"
                            "        if warns:\n"
                            "            info['warnings'] = list(warns)\n"
                            "    except Exception:\n"
                            "        pass\n"
                            "    # Input geometry info\n"
                            "    inputs = []\n"
                            "    for i in range(4):\n"
                            "        inp = node.input(i)\n"
                            "        if inp:\n"
                            "            geo = inp.geometry()\n"
                            "            if geo:\n"
                            "                attrs = [a.name() for a in "
                            "geo.pointAttribs()]\n"
                            "                inputs.append({{'index': i, "
                            "'node': inp.path(), 'points': "
                            "len(geo.points()), 'attributes': attrs}})\n"
                            "    info['inputs'] = inputs\n"
                            "    result = info\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="debug",
                ),
            ],
        ))

        # --- Material Assign ---
        self.register(Recipe(
            name="material_assign",
            description=(
                "Assign a material to geometry prims on the USD stage."
            ),
            triggers=[
                r"^assign\s+(?:material\s+)?(?P<material>[\w/]+)\s+to\s+(?P<target>.+)$",
                r"^(?:bind|apply)\s+material\s+(?P<material>[\w/]+)\s+(?:to|on)\s+(?P<target>.+)$",
            ],
            parameters=["material", "target"],
            gate_level=GateLevel.REVIEW,
            category="materials",
            steps=[
                RecipeStep(
                    action="assign_material",
                    payload_template={
                        "material_path": "{material}",
                        "prim_pattern": "{target}",
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- VEX Noise Deformer ---
        self.register(Recipe(
            name="vex_noise_deformer",
            description=(
                "Create a wrangle that deforms geometry with layered "
                "noise displacement along normals. Standard fBm pattern."
            ),
            triggers=[
                r"^(?:create|make|add)\s+(?:a\s+)?noise\s+(?:deform(?:er|ation)?|displacement)(?:\s+(?:on|to|at|in)\s+(?P<parent>.+))?$",
                r"^(?:create|make|add)\s+(?:a\s+)?(?:vex\s+)?(?:fbm|fractal)\s+(?:noise|deform)(?:\s+(?:on|to|at|in)\s+(?P<parent>.+))?$",
            ],
            parameters=["parent"],
            gate_level=GateLevel.REVIEW,
            category="geometry",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"  # noqa: E501
                            "parent_path = '{parent}'.strip()\n"
                            "parent = hou.node(parent_path) if parent_path "
                            "else None\n"
                            "if parent is None:\n"
                            "    sel = hou.selectedNodes()\n"
                            "    if sel:\n"
                            "        parent = sel[0].parent() if "
                            "sel[0].type().category() == "
                            "hou.sopNodeTypeCategory() else sel[0]\n"
                            "    else:\n"
                            "        parent = hou.node('/obj').createNode("
                            "'geo', 'noise_deform')\n"
                            "        parent.moveToGoodPosition()\n"
                            "wrangle = parent.createNode('attribwrangle', "
                            "'noise_deform')\n"
                            "wrangle.parm('snippet').set("
                            "'// fBm Noise Displacement\\n"
                            "float n = 0;\\n"
                            "float amp = chf(\"amplitude\");\\n"
                            "float freq = chf(\"frequency\");\\n"
                            "int octaves = chi(\"octaves\");\\n"
                            "float a = 1.0;\\n"
                            "float f = freq;\\n"
                            "for (int i = 0; i < octaves; i++) {{\\n"
                            "    n += snoise(@P * f + @Time * "
                            "chf(\"speed\")) * a;\\n"
                            "    f *= 2.0;\\n"
                            "    a *= 0.5;\\n"
                            "}}\\n"
                            "@P += @N * n * amp;\\n')\n"
                            "# Create channel references\n"
                            "ptg = wrangle.parmTemplateGroup()\n"
                            "ptg.append(hou.FloatParmTemplate("
                            "'amplitude', 'Amplitude', 1, "
                            "default_value=(0.5,)))\n"
                            "ptg.append(hou.FloatParmTemplate("
                            "'frequency', 'Frequency', 1, "
                            "default_value=(2.0,)))\n"
                            "ptg.append(hou.IntParmTemplate("
                            "'octaves', 'Octaves', 1, "
                            "default_value=(4,), min=1, max=8))\n"
                            "ptg.append(hou.FloatParmTemplate("
                            "'speed', 'Animation Speed', 1, "
                            "default_value=(0.5,)))\n"
                            "wrangle.setParmTemplateGroup(ptg)\n"
                            "# Wire to last selected or first input\n"
                            "sel = hou.selectedNodes()\n"
                            "if sel and sel[0].parent() == parent:\n"
                            "    wrangle.setInput(0, sel[0])\n"
                            "wrangle.setDisplayFlag(True)\n"
                            "wrangle.setRenderFlag(True)\n"
                            "wrangle.moveToGoodPosition()\n"
                            "result = {{'node': wrangle.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="deformer",
                ),
            ],
        ))

        # --- HDA Generate (Content from Description) ---
        self.register(Recipe(
            name="hda_generate",
            description=(
                "Generate a functional HDA from a natural-language description. "
                "Matches keywords to pre-built VEX templates (scatter, deformer, "
                "color, mask, extrude) and populates the HDA with working code "
                "and parameter interface."
            ),
            triggers=[
                r"^generate\s+(?:an?\s+)?(?:hda|digital asset|tool)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
                r"^generate\s+(?:an?\s+)?(?P<name>[\w]+)\s+(?:hda|digital asset|tool)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
                r"^generate\s+(?:an?\s+)?(?:hda|digital asset|tool)\s+(?:called|named)\s+(?P<name>[\w]+)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
                r"^hda\s+generate\s+(?P<description>.+)$",
            ],
            parameters=["name", "description"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import os\n"
                            "import re\n"
                            "raw_name = '{name}'.strip()\n"
                            "description = '{description}'.strip()\n"
                            "desc = description.lower()\n"
                            "\n"
                            "# --- Match description to template ---\n"
                            "template = 'generic'\n"
                            "vex_code = ''\n"
                            "parms = []\n"
                            "\n"
                            "if any(w in desc for w in "
                            "['scatter', 'distribute', 'sprinkle', "
                            "'random point']):\n"
                            "    template = 'scatter'\n"
                            "    if not raw_name: raw_name = 'point_scatter'\n"
                            "    vex_code = ("
                            "'// Point removal by noise threshold\\n'"
                            "'float density = chf(\"density\");\\n'"
                            "'float seed = chf(\"seed\");\\n'"
                            "'float n = noise(@P * density + "
                            "set(seed, seed*0.7, seed*1.3));\\n'"
                            "'if (n < chf(\"cutoff\"))\\n'"
                            "'    removepoint(0, @ptnum);\\n')\n"
                            "    parms = [\n"
                            "        ('density', 'Density', 'float', 5.0),\n"
                            "        ('cutoff', 'Cutoff', 'float', 0.5),\n"
                            "        ('seed', 'Seed', 'float', 0.0),\n"
                            "    ]\n"
                            "\n"
                            "elif any(w in desc for w in "
                            "['deform', 'bend', 'twist', 'wave', "
                            "'displace']):\n"
                            "    template = 'deformer'\n"
                            "    if not raw_name: raw_name = 'deformer'\n"
                            "    vex_code = ("
                            "'// fBm noise deformation\\n'"
                            "'float amp = chf(\"amplitude\");\\n'"
                            "'float freq = chf(\"frequency\");\\n'"
                            "'int oct = chi(\"octaves\");\\n'"
                            "'float n = 0, a = 1.0, f = freq;\\n'"
                            "'for (int i = 0; i < oct; i++) {{\\n'"
                            "'    n += snoise(@P * f + @Time * "
                            "chf(\"speed\")) * a;\\n'"
                            "'    f *= 2.0; a *= 0.5;\\n'"
                            "'}}\\n'"
                            "'@P += @N * n * amp * chf(\"blend\");\\n')\n"
                            "    parms = [\n"
                            "        ('amplitude', 'Amplitude', "
                            "'float', 0.5),\n"
                            "        ('frequency', 'Frequency', "
                            "'float', 2.0),\n"
                            "        ('octaves', 'Octaves', 'int', 4),\n"
                            "        ('speed', 'Speed', 'float', 0.0),\n"
                            "        ('blend', 'Blend', 'float', 1.0),\n"
                            "    ]\n"
                            "\n"
                            "elif any(w in desc for w in "
                            "['color', 'paint', 'gradient', 'ramp', "
                            "'visualize']):\n"
                            "    template = 'color'\n"
                            "    if not raw_name: raw_name = 'color_tool'\n"
                            "    vex_code = ("
                            "'// Color by height gradient\\n'"
                            "'vector bmin, bmax;\\n'"
                            "'getbbox(0, bmin, bmax);\\n'"
                            "'int axis = chi(\"axis\");\\n'"
                            "'float t = fit(@P[axis], bmin[axis], "
                            "bmax[axis], 0, 1);\\n'"
                            "'vector ca = chv(\"color_a\");\\n'"
                            "'vector cb = chv(\"color_b\");\\n'"
                            "'@Cd = lerp(ca, cb, "
                            "chramp(\"gradient\", t));\\n')\n"
                            "    parms = [\n"
                            "        ('axis', 'Axis (0=X 1=Y 2=Z)', "
                            "'int', 1),\n"
                            "        ('color_a', 'Color A', "
                            "'vector', (0, 0, 1)),\n"
                            "        ('color_b', 'Color B', "
                            "'vector', (1, 0, 0)),\n"
                            "    ]\n"
                            "\n"
                            "elif any(w in desc for w in "
                            "['mask', 'group', 'select', 'filter', "
                            "'isolate']):\n"
                            "    template = 'mask'\n"
                            "    if not raw_name: raw_name = 'mask_tool'\n"
                            "    vex_code = ("
                            "'// Proximity-based point mask\\n'"
                            "'vector center = chv(\"center\");\\n'"
                            "'float rad = chf(\"radius\");\\n'"
                            "'float d = distance(@P, center);\\n'"
                            "'f@mask = 1.0 - smooth(rad * 0.5, "
                            "rad, d);\\n'"
                            "'if (chi(\"invert\")) "
                            "f@mask = 1.0 - f@mask;\\n'"
                            "'if (f@mask > chf(\"threshold\"))\\n'"
                            "'    setpointgroup(0, \"masked\", "
                            "@ptnum, 1);\\n')\n"
                            "    parms = [\n"
                            "        ('center', 'Center', "
                            "'vector', (0, 0, 0)),\n"
                            "        ('radius', 'Radius', "
                            "'float', 1.0),\n"
                            "        ('threshold', 'Threshold', "
                            "'float', 0.5),\n"
                            "        ('invert', 'Invert', "
                            "'toggle', False),\n"
                            "    ]\n"
                            "\n"
                            "elif any(w in desc for w in "
                            "['extrude', 'push', 'inflate', "
                            "'thicken', 'offset']):\n"
                            "    template = 'extrude'\n"
                            "    if not raw_name: "
                            "raw_name = 'extrude_tool'\n"
                            "    vex_code = ("
                            "'// Push along normals with noise\\n'"
                            "'float dist = chf(\"distance\");\\n'"
                            "'float namt = chf(\"noise_amount\");\\n'"
                            "'float n = 0;\\n'"
                            "'if (namt > 0)\\n'"
                            "'    n = snoise(@P * chf(\"noise_freq\"))"
                            " * namt;\\n'"
                            "'@P += @N * (dist + n) * "
                            "chf(\"blend\");\\n')\n"
                            "    parms = [\n"
                            "        ('distance', 'Distance', "
                            "'float', 0.1),\n"
                            "        ('noise_amount', 'Noise Amount', "
                            "'float', 0.0),\n"
                            "        ('noise_freq', 'Noise Frequency', "
                            "'float', 2.0),\n"
                            "        ('blend', 'Blend', "
                            "'float', 1.0),\n"
                            "    ]\n"
                            "\n"
                            "else:\n"
                            "    if not raw_name: "
                            "raw_name = 'custom_tool'\n"
                            "    vex_code = ("
                            "'// Custom tool: ' + description + '\\n'"
                            "'float blend = chf(\"blend\");\\n'"
                            "'// @P += @N * blend;\\n')\n"
                            "    parms = [\n"
                            "        ('blend', 'Blend', "
                            "'float', 1.0),\n"
                            "    ]\n"
                            "\n"
                            "# --- Derive names ---\n"
                            "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                            "raw_name.lower()).strip('_')\n"
                            "hda_label = raw_name.replace('_', "
                            "' ').title()\n"
                            "\n"
                            "# --- Find parent context ---\n"
                            "sel = hou.selectedNodes()\n"
                            "if sel and sel[0].type().category() == "
                            "hou.sopNodeTypeCategory():\n"
                            "    parent = sel[0].parent()\n"
                            "elif sel:\n"
                            "    parent = sel[0]\n"
                            "else:\n"
                            "    obj = hou.node('/obj')\n"
                            "    parent = obj.createNode('geo', "
                            "hda_name + '_dev')\n"
                            "    parent.moveToGoodPosition()\n"
                            "\n"
                            "# --- Create subnet with content ---\n"
                            "subnet = parent.createNode("
                            "'subnet', hda_name)\n"
                            "input_null = subnet.createNode("
                            "'null', 'IN')\n"
                            "input_null.setPosition("
                            "hou.Vector2(0, 0))\n"
                            "wrangle = subnet.createNode("
                            "'attribwrangle', template + '_wrangle')\n"
                            "wrangle.parm('snippet').set(vex_code)\n"
                            "wrangle.setPosition("
                            "hou.Vector2(0, -2))\n"
                            "wrangle.setInput(0, input_null)\n"
                            "output_null = subnet.createNode("
                            "'null', 'OUT')\n"
                            "output_null.setPosition("
                            "hou.Vector2(0, -4))\n"
                            "output_null.setInput(0, wrangle)\n"
                            "output_null.setDisplayFlag(True)\n"
                            "output_null.setRenderFlag(True)\n"
                            "input_null.setInput(0, "
                            "subnet.indirectInputs()[0])\n"
                            "subnet.layoutChildren()\n"
                            "subnet.moveToGoodPosition()\n"
                            "\n"
                            "# --- Create HDA definition ---\n"
                            "otls_dir = os.path.join("
                            "hou.getenv('HIP', ''), 'otls')\n"
                            "if not os.path.exists(otls_dir):\n"
                            "    os.makedirs(otls_dir)\n"
                            "hda_path = os.path.join(otls_dir, "
                            "hda_name + '.hda')\n"
                            "hda_node = subnet.createDigitalAsset(\n"
                            "    name=hda_name,\n"
                            "    hda_file_name=hda_path,\n"
                            "    description=hda_label,\n"
                            "    min_num_inputs=1,\n"
                            "    max_num_inputs=1,\n"
                            ")\n"
                            "definition = hda_node.type().definition()\n"
                            "ht = '= ' + hda_label + ' =\\n\\n'\n"
                            "ht += 'Template: ' + template + '\\n\\n'\n"
                            "if description:\n"
                            "    ht += description + '\\n\\n'\n"
                            "ht += '== Parameters ==\\n\\n'\n"
                            "ht += 'See parameter interface.\\n'\n"
                            "definition.setExtraFileOption('Help', ht)\n"
                            "definition.setIcon('SOP_subnet')\n"
                            "definition.setExtraFileOption("
                            "'CreatedBy', 'Synapse HDA Generate')\n"
                            "\n"
                            "# --- Build parameter interface ---\n"
                            "ptg = hda_node.parmTemplateGroup()\n"
                            "mf = hou.FolderParmTemplate(\n"
                            "    'main_folder', 'Main', "
                            "folder_type=hou.folderType.Tabs)\n"
                            "for pd in parms:\n"
                            "    pn, pl, pt = pd[0], pd[1], pd[2]\n"
                            "    pv = pd[3]\n"
                            "    if pt == 'float':\n"
                            "        mf.addParmTemplate("
                            "hou.FloatParmTemplate("
                            "pn, pl, 1, default_value=(pv,)))\n"
                            "    elif pt == 'int':\n"
                            "        mf.addParmTemplate("
                            "hou.IntParmTemplate("
                            "pn, pl, 1, default_value=(pv,)))\n"
                            "    elif pt == 'vector':\n"
                            "        mf.addParmTemplate("
                            "hou.FloatParmTemplate("
                            "pn, pl, 3, default_value=pv))\n"
                            "    elif pt == 'toggle':\n"
                            "        mf.addParmTemplate("
                            "hou.ToggleParmTemplate("
                            "pn, pl, default_value=bool(pv)))\n"
                            "    elif pt == 'string':\n"
                            "        mf.addParmTemplate("
                            "hou.StringParmTemplate("
                            "pn, pl, 1, default_value=(pv,)))\n"
                            "ptg.append(mf)\n"
                            "hda_node.setParmTemplateGroup(ptg)\n"
                            "definition.save(hda_path, hda_node)\n"
                            "hda_node.setSelected(True, "
                            "clear_all_selected=True)\n"
                            "hda_node.setDisplayFlag(True)\n"
                            "hda_node.setRenderFlag(True)\n"
                            "result = {{\n"
                            "    'node': hda_node.path(),\n"
                            "    'hda_file': hda_path,\n"
                            "    'hda_name': hda_name,\n"
                            "    'hda_label': hda_label,\n"
                            "    'template': template,\n"
                            "    'definition': 'Sop/' + hda_name,\n"
                            "    'description': description "
                            "or '(none provided)',\n"
                            "    'vex_lines': len("
                            "vex_code.split('\\n')),\n"
                            "    'parameters': len(parms),\n"
                            "}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="hda",
                ),
            ],
        ))

        # ==================================================================
        # RENDER FARM RECIPES — Autonomous render pipeline
        # ==================================================================

        # --- Render Sequence ---
        self.register(Recipe(
            name="render_sequence",
            description=(
                "Render a frame sequence with per-frame validation, "
                "automatic issue diagnosis, and self-improving fixes. "
                "Learns from each render to start smarter next time."
            ),
            triggers=[
                r"^render\s+(?:sequence|frames?)\s+(?P<start>\d+)\s*[-\u2013to]+\s*(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
                r"^render\s+(?:from\s+)?(?P<start>\d+)\s+to\s+(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
                r"^batch\s+render\s+(?P<start>\d+)\s*[-\u2013to]+\s*(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
            ],
            parameters=["start", "end", "rop"],
            gate_level=GateLevel.APPROVE,
            category="render",
            steps=[
                RecipeStep(
                    action="render_sequence",
                    payload_template={
                        "start_frame": "{start}",
                        "end_frame": "{end}",
                        "rop": "{rop}",
                        "auto_fix": True,
                        "max_retries": 3,
                    },
                    gate_level=GateLevel.APPROVE,
                ),
            ],
        ))

        # --- Render and Validate (single frame) ---
        self.register(Recipe(
            name="render_validate_frame",
            description=(
                "Render the current frame and validate it for quality "
                "issues (fireflies, black frames, clipping)."
            ),
            triggers=[
                r"^render\s+and\s+validate$",
                r"^test\s+render$",
                r"^render\s+(?:and\s+)?check$",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="render",
                    payload_template={},
                    gate_level=GateLevel.REVIEW,
                    output_var="render_result",
                ),
                RecipeStep(
                    action="validate_frame",
                    payload_template={
                        "image_path": "${render_result.image_path}",
                    },
                    gate_level=GateLevel.INFORM,
                ),
            ],
        ))

        # --- Setup Render Farm ---
        self.register(Recipe(
            name="setup_render_farm",
            description=(
                "Configure render farm settings: classify the scene, "
                "query memory for known-good settings, and prepare "
                "the ROP for batch rendering."
            ),
            triggers=[
                r"^(?:set up|setup)\s+render\s+farm(?:\s+(?:on|for|with)\s+(?P<rop>[\w\-./]+))?$",
                r"^(?:prepare|configure)\s+(?:for\s+)?batch\s+render(?:ing)?(?:\s+(?:on|for|with)\s+(?P<rop>[\w\-./]+))?$",
            ],
            parameters=["rop"],
            gate_level=GateLevel.APPROVE,
            category="render",
            steps=[
                RecipeStep(
                    action="get_stage_info",
                    payload_template={},
                    gate_level=GateLevel.INFORM,
                    output_var="stage",
                ),
                RecipeStep(
                    action="render_settings",
                    payload_template={
                        "node": "{rop}",
                    },
                    gate_level=GateLevel.INFORM,
                    output_var="settings",
                ),
            ],
        ))

        # ==================================================================
        # PRODUCTION RECIPES — Advanced Solaris / Render / Comp workflows
        # ==================================================================

        # --- Production Turntable ---
        self.register(Recipe(
            name="render_turntable_production",
            description=(
                "Full production turntable: camera orbit (configurable radius, "
                "height, 120 frames), 3-point lighting rig with 4:1 key:fill "
                "ratio, ground plane shadow catcher, Karma XPU at 1920x1080 "
                "128 samples, AOVs (beauty, depth, normal, motion vector, "
                "crypto matte), motion blur enabled."
            ),
            triggers=[
                r"^(?:render\s+)?production\s+turntable(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
                r"^render\s+turntable\s+production(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
                r"^turntable\s+production(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
            ],
            parameters=["subject"],
            gate_level=GateLevel.APPROVE,
            category="render",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import math\n"
                            "subject = '{subject}'.strip()\n"
                            "stage = hou.node('/stage')\n"
                            "if stage is None:\n"
                            "    stage = hou.node('/obj').createNode("
                            "'lopnet', 'stage')\n"
                            "\n"
                            "# --- Camera orbit ---\n"
                            "cam = stage.createNode('camera', 'turntable_cam')\n"
                            "cam.parm('primpath').set('/cameras/turntable_cam')\n"
                            "cam.parm('focalLength').set(50)\n"
                            "radius = 5.0\n"
                            "height = 1.5\n"
                            "frames = 120\n"
                            "for f in range(1, frames + 1):\n"
                            "    angle = (f - 1) * (2 * math.pi / frames)\n"
                            "    x = radius * math.cos(angle)\n"
                            "    z = radius * math.sin(angle)\n"
                            "    cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(x, hou.frameToTime(f)),), 0)\n"
                            "    cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(height, hou.frameToTime(f)),), 1)\n"
                            "    cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(z, hou.frameToTime(f)),), 2)\n"
                            "\n"
                            "# --- 3-point lighting (4:1 key:fill ratio) ---\n"
                            "# Key light: exposure 5\n"
                            "key = stage.createNode('light', 'key_light')\n"
                            "key.parm('primpath').set('/lights/key_light')\n"
                            "key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "key.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "key.parm('xn__inputsexposure_vya').set(5.0)\n"
                            "key.parmTuple('t').set((3, 4, 2))\n"
                            "key.parmTuple('r').set((-35, 45, 0))\n"
                            "\n"
                            "# Fill light: exposure 3 (4:1 ratio = 2 stops diff)\n"
                            "fill = stage.createNode('light', 'fill_light')\n"
                            "fill.parm('primpath').set('/lights/fill_light')\n"
                            "fill.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "fill.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "fill.parm('xn__inputsexposure_vya').set(3.0)\n"
                            "fill.parmTuple('t').set((-3, 3, 2))\n"
                            "fill.parmTuple('r').set((-25, -45, 0))\n"
                            "\n"
                            "# Rim light: exposure 4.5\n"
                            "rim = stage.createNode('light', 'rim_light')\n"
                            "rim.parm('primpath').set('/lights/rim_light')\n"
                            "rim.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "rim.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "rim.parm('xn__inputsexposure_vya').set(4.5)\n"
                            "rim.parmTuple('t').set((0, 3, -4))\n"
                            "rim.parmTuple('r').set((-20, 180, 0))\n"
                            "\n"
                            "# --- Ground plane with shadow catcher ---\n"
                            "ground = stage.createNode('sopimport', 'ground_plane')\n"
                            "ground.parm('primpath').set('/geo/ground_plane')\n"
                            "\n"
                            "# --- Merge scene ---\n"
                            "merge = stage.createNode('merge', 'scene_merge')\n"
                            "inputs = [cam, key, fill, rim, ground]\n"
                            "for i, node in enumerate(inputs):\n"
                            "    merge.setInput(i, node)\n"
                            "\n"
                            "# --- Render settings: Karma XPU 1920x1080 ---\n"
                            "rs = stage.createNode('karmarenderproperties', "
                            "'render_settings')\n"
                            "rs.setInput(0, merge)\n"
                            "rs.parm('resolutionx').set(1920)\n"
                            "rs.parm('resolutiony').set(1080)\n"
                            "rs.parm('engine').set('XPU')\n"
                            "rs.parm('samplesperpixel').set(128)\n"
                            "rs.parm('diffuselimit').set(4)\n"
                            "rs.parm('specularlimit').set(6)\n"
                            "\n"
                            "# --- Motion blur ---\n"
                            "rs.parm('xformsamples').set(2)\n"
                            "rs.parm('geosamples').set(2)\n"
                            "\n"
                            "# --- Karma LOP ---\n"
                            "karma = stage.createNode('karma', 'karma_render')\n"
                            "karma.setInput(0, rs)\n"
                            "karma.parm('camera').set('/cameras/turntable_cam')\n"
                            "karma.parm('picture').set("
                            "'$HIP/render/$HIPNAME/$HIPNAME.$F4.exr')\n"
                            "\n"
                            "# --- AOV passes ---\n"
                            "# Beauty is default; add utility passes\n"
                            "aovs = ['depth', 'N', 'motionvector', "
                            "'cryptomatte']\n"
                            "for idx, aov in enumerate(aovs):\n"
                            "    try:\n"
                            "        karma.parm('ar_aov_name_' + str(idx + 1)"
                            ").set(aov)\n"
                            "    except Exception:\n"
                            "        pass\n"
                            "\n"
                            "stage.layoutChildren()\n"
                            "result = {{'camera': cam.path(), "
                            "'karma': karma.path(), "
                            "'output': '$HIP/render/$HIPNAME/$HIPNAME.$F4.exr', "
                            "'frames': frames, 'resolution': '1920x1080', "
                            "'samples': 128, "
                            "'key_exposure': 5.0, 'fill_exposure': 3.0, "
                            "'rim_exposure': 4.5, "
                            "'motion_blur': True, "
                            "'aovs': ['beauty'] + aovs}}\n"
                        ),
                    },
                    gate_level=GateLevel.APPROVE,
                    output_var="turntable",
                ),
            ],
        ))

        # --- Character Cloth Setup ---
        self.register(Recipe(
            name="character_cloth_setup",
            description=(
                "Solaris character with cloth pipeline: sublayer LOP for "
                "character USD reference, materiallibrary with skin/cloth/hair "
                "MaterialX subnets, SOP Import for Vellum cloth cache, "
                "subdivision + displacement on render geometry settings, "
                "purpose tagging (render vs proxy)."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+character\s+cloth(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?character\s+with\s+cloth(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
                r"^character\s+cloth\s+setup(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
            ],
            parameters=["char_path"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "char_path = '{char_path}'.strip()\n"
                            "stage = hou.node('/stage')\n"
                            "if stage is None:\n"
                            "    stage = hou.node('/obj').createNode("
                            "'lopnet', 'stage')\n"
                            "\n"
                            "# --- Sublayer for character USD reference ---\n"
                            "sublayer = stage.createNode('sublayer', "
                            "'char_reference')\n"
                            "if char_path:\n"
                            "    sublayer.parm('filepath1').set(char_path)\n"
                            "\n"
                            "# --- Material Library: skin, cloth, hair ---\n"
                            "matlib = stage.createNode('materiallibrary', "
                            "'char_materials')\n"
                            "matlib.setInput(0, sublayer)\n"
                            "matlib.parm('matpathprefix').set("
                            "'/materials')\n"
                            "matlib.cook(force=True)\n"
                            "\n"
                            "# Skin MaterialX subnet\n"
                            "skin = matlib.createNode('subnet', 'skin_mtl')\n"
                            "skin_surf = skin.createNode("
                            "'mtlxstandard_surface', 'skin_shader')\n"
                            "skin_surf.parm('base_color').set("
                            "(0.8, 0.6, 0.5))\n"
                            "skin_surf.parm('specular_roughness').set(0.4)\n"
                            "skin_surf.parm('subsurface').set(0.3)\n"
                            "skin_out = skin.createNode("
                            "'subnetconnector', 'surface_output')\n"
                            "skin_out.setInput(0, skin_surf)\n"
                            "\n"
                            "# Cloth MaterialX subnet\n"
                            "cloth = matlib.createNode('subnet', 'cloth_mtl')\n"
                            "cloth_surf = cloth.createNode("
                            "'mtlxstandard_surface', 'cloth_shader')\n"
                            "cloth_surf.parm('base_color').set("
                            "(0.3, 0.3, 0.35))\n"
                            "cloth_surf.parm('specular_roughness').set(0.7)\n"
                            "cloth_surf.parm('sheen').set(0.5)\n"
                            "cloth_out = cloth.createNode("
                            "'subnetconnector', 'surface_output')\n"
                            "cloth_out.setInput(0, cloth_surf)\n"
                            "\n"
                            "# Hair MaterialX subnet\n"
                            "hair = matlib.createNode('subnet', 'hair_mtl')\n"
                            "hair_surf = hair.createNode("
                            "'mtlxstandard_surface', 'hair_shader')\n"
                            "hair_surf.parm('base_color').set("
                            "(0.15, 0.1, 0.08))\n"
                            "hair_surf.parm('specular_roughness').set(0.35)\n"
                            "hair_out = hair.createNode("
                            "'subnetconnector', 'surface_output')\n"
                            "hair_out.setInput(0, hair_surf)\n"
                            "\n"
                            "# --- SOP Import for Vellum cloth cache ---\n"
                            "cloth_import = stage.createNode('sopimport', "
                            "'cloth_cache_import')\n"
                            "cloth_import.parm('primpath').set("
                            "'/characters/cloth_sim')\n"
                            "cloth_import.setInput(0, matlib)\n"
                            "\n"
                            "# --- Render Geometry Settings: "
                            "subdivision + displacement ---\n"
                            "rendergeo = stage.createNode("
                            "'rendergeometrysettings', 'char_render_geo')\n"
                            "rendergeo.setInput(0, cloth_import)\n"
                            "rendergeo.parm('primpattern').set("
                            "'/characters/**')\n"
                            "try:\n"
                            "    rendergeo.parm("
                            "'xn__karmasubdivisionmesh_control_kfb'"
                            ").set('set')\n"
                            "    rendergeo.parm("
                            "'xn__karmasubdivisionmesh_beb'"
                            ").set(True)\n"
                            "except Exception:\n"
                            "    pass\n"
                            "\n"
                            "# --- Purpose tagging ---\n"
                            "configure = stage.createNode("
                            "'configureprimitive', 'purpose_tags')\n"
                            "configure.setInput(0, rendergeo)\n"
                            "configure.parm('primpattern').set("
                            "'/characters/**')\n"
                            "try:\n"
                            "    configure.parm('purpose').set('render')\n"
                            "except Exception:\n"
                            "    pass\n"
                            "\n"
                            "stage.layoutChildren()\n"
                            "result = {{'sublayer': sublayer.path(), "
                            "'matlib': matlib.path(), "
                            "'materials': ['skin_mtl', 'cloth_mtl', "
                            "'hair_mtl'], "
                            "'cloth_import': cloth_import.path(), "
                            "'render_geo': rendergeo.path(), "
                            "'purpose_config': configure.path()}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="char_setup",
                ),
            ],
        ))

        # --- Destruction Sequence ---
        self.register(Recipe(
            name="destruction_sequence",
            description=(
                "RBD cache to Solaris multi-pass render: SOP imports for "
                "RBD cache, debris instancing, volumetric dust/smoke, "
                "destruction materials, and multi-pass Karma render settings "
                "(beauty, depth, motion vectors, crypto mattes)."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?destruction\s+sequence(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
                r"^(?:set up|setup|create)\s+destruction(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
                r"^rbd\s+to\s+solaris\s+render(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
            ],
            parameters=["cache_path"],
            gate_level=GateLevel.APPROVE,
            category="render",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "cache_path = '{cache_path}'.strip()\n"
                            "stage = hou.node('/stage')\n"
                            "if stage is None:\n"
                            "    stage = hou.node('/obj').createNode("
                            "'lopnet', 'stage')\n"
                            "\n"
                            "# --- SOP Import: RBD cache ---\n"
                            "rbd_import = stage.createNode('sopimport', "
                            "'rbd_cache')\n"
                            "rbd_import.parm('primpath').set("
                            "'/fx/rbd_fragments')\n"
                            "if cache_path:\n"
                            "    rbd_import.parm('soppath').set(cache_path)\n"
                            "\n"
                            "# --- SOP Import: debris instancing ---\n"
                            "debris_import = stage.createNode('sopimport', "
                            "'debris_instances')\n"
                            "debris_import.parm('primpath').set("
                            "'/fx/debris')\n"
                            "\n"
                            "# --- SOP Import: volumetric dust/smoke ---\n"
                            "vol_import = stage.createNode('sopimport', "
                            "'dust_volume')\n"
                            "vol_import.parm('primpath').set("
                            "'/fx/dust_smoke')\n"
                            "\n"
                            "# --- Material library for destruction ---\n"
                            "matlib = stage.createNode('materiallibrary', "
                            "'destruction_materials')\n"
                            "matlib.parm('matpathprefix').set("
                            "'/materials')\n"
                            "matlib.cook(force=True)\n"
                            "\n"
                            "# Concrete material\n"
                            "concrete = matlib.createNode('subnet', "
                            "'concrete_mtl')\n"
                            "concrete_surf = concrete.createNode("
                            "'mtlxstandard_surface', 'concrete_shader')\n"
                            "concrete_surf.parm('base_color').set("
                            "(0.6, 0.58, 0.55))\n"
                            "concrete_surf.parm('specular_roughness').set("
                            "0.85)\n"
                            "\n"
                            "# Dust volume material\n"
                            "dust = matlib.createNode('subnet', "
                            "'dust_mtl')\n"
                            "dust_vol = dust.createNode("
                            "'mtlxstandard_volume', 'dust_shader')\n"
                            "\n"
                            "# --- Merge all FX layers ---\n"
                            "merge = stage.createNode('merge', "
                            "'fx_merge')\n"
                            "merge.setInput(0, rbd_import)\n"
                            "merge.setInput(1, debris_import)\n"
                            "merge.setInput(2, vol_import)\n"
                            "merge.setInput(3, matlib)\n"
                            "\n"
                            "# --- Render settings: multi-pass ---\n"
                            "rs = stage.createNode("
                            "'karmarenderproperties', "
                            "'destruction_render_settings')\n"
                            "rs.setInput(0, merge)\n"
                            "rs.parm('resolutionx').set(1920)\n"
                            "rs.parm('resolutiony').set(1080)\n"
                            "rs.parm('engine').set('XPU')\n"
                            "rs.parm('samplesperpixel').set(256)\n"
                            "rs.parm('diffuselimit').set(4)\n"
                            "rs.parm('specularlimit').set(6)\n"
                            "\n"
                            "# Motion blur for RBD\n"
                            "rs.parm('xformsamples').set(2)\n"
                            "rs.parm('geosamples').set(2)\n"
                            "\n"
                            "# --- Karma LOP ---\n"
                            "karma = stage.createNode('karma', "
                            "'karma_destruction')\n"
                            "karma.setInput(0, rs)\n"
                            "karma.parm('picture').set("
                            "'$HIP/render/destruction/"
                            "beauty.$F4.exr')\n"
                            "\n"
                            "# --- AOV config ---\n"
                            "passes = {{\n"
                            "    'beauty': 'beauty.$F4.exr',\n"
                            "    'depth': 'depth.$F4.exr',\n"
                            "    'motionvector': 'motionvector.$F4.exr',\n"
                            "    'cryptomatte_obj': "
                            "'cryptomatte_obj.$F4.exr',\n"
                            "    'cryptomatte_mtl': "
                            "'cryptomatte_mtl.$F4.exr',\n"
                            "    'cryptomatte_asset': "
                            "'cryptomatte_asset.$F4.exr',\n"
                            "}}\n"
                            "for idx, (aov, _) in enumerate("
                            "passes.items()):\n"
                            "    try:\n"
                            "        karma.parm('ar_aov_name_' + "
                            "str(idx)).set(aov)\n"
                            "    except Exception:\n"
                            "        pass\n"
                            "\n"
                            "stage.layoutChildren()\n"
                            "result = {{'rbd_import': rbd_import.path(), "
                            "'debris': debris_import.path(), "
                            "'volume': vol_import.path(), "
                            "'matlib': matlib.path(), "
                            "'karma': karma.path(), "
                            "'passes': list(passes.keys()), "
                            "'resolution': '1920x1080', "
                            "'samples': 256}}\n"
                        ),
                    },
                    gate_level=GateLevel.APPROVE,
                    output_var="destruction",
                ),
            ],
        ))

        # --- Multi-Shot Composition ---
        self.register(Recipe(
            name="multi_shot_composition",
            description=(
                "Shot-based USD layer composition: sublayer chain for "
                "base assets and shot overrides, per-shot camera prim, "
                "per-shot lighting overrides as stronger opinion layer, "
                "and render layer management."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+multi\s*shot\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?shot\s+based\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
                r"^multi\s+shot\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
            ],
            parameters=["shot_name"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "shot_name = '{shot_name}'.strip() or 'shot_010'\n"
                            "stage = hou.node('/stage')\n"
                            "if stage is None:\n"
                            "    stage = hou.node('/obj').createNode("
                            "'lopnet', 'stage')\n"
                            "\n"
                            "# --- Base asset sublayer ---\n"
                            "base_layer = stage.createNode('sublayer', "
                            "'base_assets')\n"
                            "base_layer.parm('filepath1').set("
                            "'$HIP/usd/assets.usda')\n"
                            "\n"
                            "# --- Shot overrides sublayer "
                            "(stronger opinion) ---\n"
                            "shot_layer = stage.createNode('sublayer', "
                            "shot_name + '_overrides')\n"
                            "shot_layer.setInput(0, base_layer)\n"
                            "shot_layer.parm('filepath1').set("
                            "'$HIP/usd/' + shot_name + '_overrides.usda')\n"
                            "\n"
                            "# --- Per-shot camera ---\n"
                            "cam = stage.createNode('camera', "
                            "shot_name + '_cam')\n"
                            "cam.parm('primpath').set("
                            "'/cameras/' + shot_name + '_cam')\n"
                            "cam.parm('focalLength').set(35)\n"
                            "cam.setInput(0, shot_layer)\n"
                            "\n"
                            "# --- Per-shot lighting overrides ---\n"
                            "light_layer = stage.createNode('sublayer', "
                            "shot_name + '_lighting')\n"
                            "light_layer.setInput(0, cam)\n"
                            "\n"
                            "# Key light override for this shot\n"
                            "key = stage.createNode('light', "
                            "shot_name + '_key')\n"
                            "key.parm('primpath').set("
                            "'/lights/' + shot_name + '_key')\n"
                            "key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "key.parm("
                            "'xn__inputsexposure_control_wcb').set('set')\n"
                            "key.parm('xn__inputsexposure_vya').set(5.0)\n"
                            "\n"
                            "# Merge lighting into shot layer\n"
                            "light_merge = stage.createNode('merge', "
                            "shot_name + '_light_merge')\n"
                            "light_merge.setInput(0, light_layer)\n"
                            "light_merge.setInput(1, key)\n"
                            "\n"
                            "# --- Render layer management ---\n"
                            "rs = stage.createNode("
                            "'karmarenderproperties', "
                            "shot_name + '_render_settings')\n"
                            "rs.setInput(0, light_merge)\n"
                            "rs.parm('resolutionx').set(1920)\n"
                            "rs.parm('resolutiony').set(1080)\n"
                            "\n"
                            "karma = stage.createNode('karma', "
                            "shot_name + '_karma')\n"
                            "karma.setInput(0, rs)\n"
                            "karma.parm('camera').set("
                            "'/cameras/' + shot_name + '_cam')\n"
                            "karma.parm('picture').set("
                            "'$HIP/render/' + shot_name + "
                            "'/' + shot_name + '.$F4.exr')\n"
                            "\n"
                            "stage.layoutChildren()\n"
                            "result = {{'shot': shot_name, "
                            "'base_layer': base_layer.path(), "
                            "'shot_overrides': shot_layer.path(), "
                            "'camera': cam.path(), "
                            "'camera_prim': '/cameras/' + shot_name + '_cam', "
                            "'lighting': light_merge.path(), "
                            "'karma': karma.path(), "
                            "'output': '$HIP/render/' + shot_name + "
                            "'/' + shot_name + '.$F4.exr'}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="shot_comp",
                ),
            ],
        ))

        # --- Multi-Shot Render (TOPS pipeline) ---
        self.register(Recipe(
            name="multi_shot_render",
            description=(
                "Multi-shot render pipeline via TOPS/PDG: creates per-shot "
                "work items from a shot list, configures camera and frame "
                "range per shot, renders via ropfetch, partitions results "
                "by shot name, and optionally encodes per-shot movies."
            ),
            triggers=[
                r"^(?:render|batch render)\s+(?:all\s+)?shots?\s+(?P<shots>.+?)(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
                r"^multi[- ]?shot\s+render(?:\s+(?P<shots>.+?))?(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
                r"^render\s+all\s+shots?(?:\s+(?P<shots>.+?))?(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
                r"^batch\s+render\s+shots?\s+(?P<shots>.+?)(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
            ],
            parameters=["shots", "frame_range"],
            gate_level=GateLevel.APPROVE,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou, json\n"
                            "shots_str = '{shots}'.strip()\n"
                            "frame_range_str = '{frame_range}'.strip()\n"
                            "\n"
                            "# Parse shot names\n"
                            "shot_names = [s.strip() for s in shots_str.split(',') if s.strip()]\n"
                            "if not shot_names:\n"
                            "    shot_names = ['sq010_sh010', 'sq010_sh020', 'sq010_sh030']\n"
                            "\n"
                            "# Parse frame range\n"
                            "frame_start, frame_end = 1001, 1048\n"
                            "if frame_range_str and '-' in frame_range_str:\n"
                            "    parts = frame_range_str.split('-')\n"
                            "    frame_start, frame_end = int(parts[0]), int(parts[1])\n"
                            "\n"
                            "# Build shot definitions for tops_multi_shot\n"
                            "shot_defs = []\n"
                            "for name in shot_names:\n"
                            "    shot_defs.append({{\n"
                            "        'name': name,\n"
                            "        'frame_start': frame_start,\n"
                            "        'frame_end': frame_end,\n"
                            "        'camera': '/cameras/' + name + '_cam',\n"
                            "    }})\n"
                            "\n"
                            "result = {{\n"
                            "    'shot_count': len(shot_defs),\n"
                            "    'shots': shot_defs,\n"
                            "    'frame_range': '{{}}-{{}}'.format(frame_start, frame_end),\n"
                            "}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="shot_list",
                ),
                RecipeStep(
                    action="tops_multi_shot",
                    payload_template={
                        "shots": "$shot_list.shots",
                        "output_dir": "$HIP/render",
                        "renderer": "karma_xpu",
                        "camera_pattern": "/cameras/{{shot}}_cam",
                    },
                    gate_level=GateLevel.APPROVE,
                    output_var="multi_shot_job",
                ),
            ],
        ))

        # --- Copernicus Render Comp ---
        self.register(Recipe(
            name="copernicus_render_comp",
            description=(
                "Render pass compositing via Copernicus GPU nodes: "
                "load beauty EXR and utility AOVs as file COPs, "
                "grade (exposure/contrast), tonemap, and output "
                "composited result."
            ),
            triggers=[
                r"^(?:set up|setup|create)\s+(?:a\s+)?copernicus\s+render\s+comp(?:osite|ositing)?(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
                r"^(?:set up|setup|create)\s+(?:a\s+)?render\s+comp(?:osite|ositing)?(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
                r"^composite\s+render\s+passes(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
            ],
            parameters=["exr_path"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "exr_path = '{exr_path}'.strip()\n"
                            "if not exr_path:\n"
                            "    exr_path = '$HIP/render/$HIPNAME/"
                            "$HIPNAME.$F4.exr'\n"
                            "\n"
                            "# --- Create COP network ---\n"
                            "root = hou.node('/stage') or hou.node('/out')\n"
                            "cop = root.createNode('cop2net', "
                            "'render_comp')\n"
                            "\n"
                            "# --- File COP: beauty pass ---\n"
                            "beauty_file = cop.createNode('file', "
                            "'beauty_input')\n"
                            "beauty_file.parm('filename1').set(exr_path)\n"
                            "\n"
                            "# --- File COP: depth AOV ---\n"
                            "depth_path = exr_path.replace("
                            "'$HIPNAME.$F4', 'depth.$F4')\n"
                            "depth_file = cop.createNode('file', "
                            "'depth_input')\n"
                            "depth_file.parm('filename1').set(depth_path)\n"
                            "\n"
                            "# --- File COP: normal AOV ---\n"
                            "normal_path = exr_path.replace("
                            "'$HIPNAME.$F4', 'N.$F4')\n"
                            "normal_file = cop.createNode('file', "
                            "'normal_input')\n"
                            "normal_file.parm('filename1').set("
                            "normal_path)\n"
                            "\n"
                            "# --- Grade node: exposure/contrast ---\n"
                            "grade = cop.createNode('colorcorrect', "
                            "'grade')\n"
                            "grade.setInput(0, beauty_file)\n"
                            "try:\n"
                            "    grade.parm('gamma').set(1.0)\n"
                            "    grade.parm('gain').set(1.0)\n"
                            "except Exception:\n"
                            "    pass\n"
                            "\n"
                            "# --- Tonemap node ---\n"
                            "tonemap = cop.createNode('tonemap', "
                            "'tonemap')\n"
                            "tonemap.setInput(0, grade)\n"
                            "\n"
                            "# --- ROP Composite Output ---\n"
                            "rop_out = cop.createNode('rop_comp', "
                            "'comp_output')\n"
                            "rop_out.setInput(0, tonemap)\n"
                            "output_path = exr_path.replace("
                            "'$HIPNAME.$F4', 'comp.$F4')\n"
                            "rop_out.parm('copoutput').set(output_path)\n"
                            "\n"
                            "cop.layoutChildren()\n"
                            "result = {{'cop_net': cop.path(), "
                            "'beauty': beauty_file.path(), "
                            "'depth': depth_file.path(), "
                            "'normal': normal_file.path(), "
                            "'grade': grade.path(), "
                            "'tonemap': tonemap.path(), "
                            "'output': rop_out.path(), "
                            "'output_path': output_path}}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="comp_setup",
                ),
            ],
        ))

        # --- Camera Match Real ---
        self.register(Recipe(
            name="camera_match_real",
            description=(
                "Create a USD camera prim that matches a real-world cinema "
                "camera body. Looks up sensor dimensions from a built-in "
                "database of 8 cameras (ARRI Alexa 35, ARRI Alexa Mini LF, "
                "RED V-Raptor [X], RED Komodo-X, Sony Venice 2, Sony FX6, "
                "Blackmagic URSA Mini Pro 12K, Canon EOS C500 Mark II). "
                "Sets horizontalAperture, verticalAperture, focalLength, "
                "clippingRange, and optional fStop/focusDistance overrides."
            ),
            triggers=[
                r"^(?:match|set up|setup|create)\s+(?:an?\s+)?(?:arri|red|sony|bmpcc|blackmagic|canon)\s*(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
                r"^camera\s+(?:match|like)\s+(?:an?\s+)?(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
                r"^(?:set up|setup|create)\s+(?:an?\s+)?camera\s+(?:match(?:ing)?|like)\s+(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
            ],
            parameters=["camera_body", "lens_mm", "f_stop", "focus_distance"],
            gate_level=GateLevel.REVIEW,
            category="pipeline",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import re\n"
                            "\n"
                            "SENSORS = {{\n"
                            "    'arri_alexa_35': {{'width': 27.99, 'height': 19.22, 'name': 'ARRI Alexa 35'}},\n"
                            "    'arri_alexa_mini_lf': {{'width': 36.70, 'height': 25.54, 'name': 'ARRI Alexa Mini LF'}},\n"
                            "    'red_v_raptor_x': {{'width': 40.96, 'height': 21.60, 'name': 'RED V-Raptor [X]'}},\n"
                            "    'red_komodo_x': {{'width': 27.03, 'height': 14.26, 'name': 'RED Komodo-X'}},\n"
                            "    'sony_venice_2': {{'width': 36.20, 'height': 24.10, 'name': 'Sony Venice 2'}},\n"
                            "    'sony_fx6': {{'width': 35.60, 'height': 23.80, 'name': 'Sony FX6'}},\n"
                            "    'bmpcc_ursa_12k': {{'width': 27.03, 'height': 14.26, 'name': 'Blackmagic URSA Mini Pro 12K'}},\n"
                            "    'canon_c500_ii': {{'width': 38.10, 'height': 20.10, 'name': 'Canon EOS C500 Mark II'}},\n"
                            "}}\n"
                            "\n"
                            "camera_body = '{camera_body}'.strip().lower()\n"
                            "# Normalize body name to match sensor keys\n"
                            "slug = re.sub(r'[\\s\\-\\[\\]]+', '_', camera_body).strip('_')\n"
                            "# Try direct match first, then fuzzy prefix match\n"
                            "sensor = SENSORS.get(slug)\n"
                            "if sensor is None:\n"
                            "    for key, val in sorted(SENSORS.items()):\n"
                            "        if slug in key or key in slug:\n"
                            "            sensor = val\n"
                            "            slug = key\n"
                            "            break\n"
                            "    # Try matching against display names\n"
                            "    if sensor is None:\n"
                            "        for key, val in sorted(SENSORS.items()):\n"
                            "            if camera_body in val['name'].lower():\n"
                            "                sensor = val\n"
                            "                slug = key\n"
                            "                break\n"
                            "if sensor is None:\n"
                            "    available = ', '.join(v['name'] for k, v in sorted(SENSORS.items()))\n"
                            "    result = {{'error': True, 'message': "
                            "\"Couldn't find camera body '\" + camera_body + "
                            "\"' in the sensor database. Available cameras: \" + available}}\n"
                            "else:\n"
                            "    lens_mm = int('{lens_mm}' or '50') if '{lens_mm}'.strip() else 50\n"
                            "    f_stop_str = '{f_stop}'.strip()\n"
                            "    focus_str = '{focus_distance}'.strip()\n"
                            "\n"
                            "    stage = hou.node('/stage')\n"
                            "    if stage is None:\n"
                            "        stage = hou.node('/obj').createNode('lopnet', 'stage')\n"
                            "\n"
                            "    cam_name = slug + '_cam'\n"
                            "    cam = stage.createNode('camera', cam_name)\n"
                            "    cam.parm('primpath').set('/cameras/' + cam_name)\n"
                            "    cam.parm('horizontalAperture').set(sensor['width'])\n"
                            "    cam.parm('verticalAperture').set(sensor['height'])\n"
                            "    cam.parm('focalLength').set(lens_mm)\n"
                            "    cam.parm('clippingRange1').set(0.1)\n"
                            "    cam.parm('clippingRange2').set(10000)\n"
                            "\n"
                            "    if f_stop_str:\n"
                            "        cam.parm('fStop').set(float(f_stop_str))\n"
                            "    if focus_str:\n"
                            "        cam.parm('focusDistance').set(float(focus_str))\n"
                            "\n"
                            "    stage.layoutChildren()\n"
                            "    result = {{'camera': cam.path(), "
                            "'prim_path': '/cameras/' + cam_name, "
                            "'sensor': sensor['name'], "
                            "'horizontal_aperture': sensor['width'], "
                            "'vertical_aperture': sensor['height'], "
                            "'focal_length': lens_mm, "
                            "'clipping_range': [0.1, 10000]}}\n"
                            "    if f_stop_str:\n"
                            "        result['f_stop'] = float(f_stop_str)\n"
                            "    if focus_str:\n"
                            "        result['focus_distance'] = float(focus_str)\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="camera",
                ),
            ],
        ))

        # --- Camera Match Turntable ---
        self.register(Recipe(
            name="camera_match_turntable",
            description=(
                "Create a production turntable render using a real-world "
                "camera match. Combines camera_match_real sensor lookup with "
                "a full turntable orbit, 3-point lighting (4:1 key:fill "
                "ratio), Karma XPU render at 1920x1080 with configurable "
                "samples and frame count."
            ),
            triggers=[
                r"^turntable\s+(?:with|using)\s+(?:an?\s+)?(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
                r"^(?:production\s+)?turntable\s+(?P<camera_body>arri|red|sony|bmpcc|blackmagic|canon)[\w\s\-\[\]]*?(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
                r"^(?:render\s+)?turntable\s+(?:with|using)\s+(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
            ],
            parameters=["camera_body", "lens_mm", "frames", "samples"],
            gate_level=GateLevel.APPROVE,
            category="render",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "import re\n"
                            "import math\n"
                            "\n"
                            "SENSORS = {{\n"
                            "    'arri_alexa_35': {{'width': 27.99, 'height': 19.22, 'name': 'ARRI Alexa 35'}},\n"
                            "    'arri_alexa_mini_lf': {{'width': 36.70, 'height': 25.54, 'name': 'ARRI Alexa Mini LF'}},\n"
                            "    'red_v_raptor_x': {{'width': 40.96, 'height': 21.60, 'name': 'RED V-Raptor [X]'}},\n"
                            "    'red_komodo_x': {{'width': 27.03, 'height': 14.26, 'name': 'RED Komodo-X'}},\n"
                            "    'sony_venice_2': {{'width': 36.20, 'height': 24.10, 'name': 'Sony Venice 2'}},\n"
                            "    'sony_fx6': {{'width': 35.60, 'height': 23.80, 'name': 'Sony FX6'}},\n"
                            "    'bmpcc_ursa_12k': {{'width': 27.03, 'height': 14.26, 'name': 'Blackmagic URSA Mini Pro 12K'}},\n"
                            "    'canon_c500_ii': {{'width': 38.10, 'height': 20.10, 'name': 'Canon EOS C500 Mark II'}},\n"
                            "}}\n"
                            "\n"
                            "camera_body = '{camera_body}'.strip().lower()\n"
                            "slug = re.sub(r'[\\s\\-\\[\\]]+', '_', camera_body).strip('_')\n"
                            "sensor = SENSORS.get(slug)\n"
                            "if sensor is None:\n"
                            "    for key, val in sorted(SENSORS.items()):\n"
                            "        if slug in key or key in slug:\n"
                            "            sensor = val\n"
                            "            slug = key\n"
                            "            break\n"
                            "    if sensor is None:\n"
                            "        for key, val in sorted(SENSORS.items()):\n"
                            "            if camera_body in val['name'].lower():\n"
                            "                sensor = val\n"
                            "                slug = key\n"
                            "                break\n"
                            "if sensor is None:\n"
                            "    available = ', '.join(v['name'] for k, v in sorted(SENSORS.items()))\n"
                            "    result = {{'error': True, 'message': "
                            "\"Couldn't find camera body '\" + camera_body + "
                            "\"' in the sensor database. Available cameras: \" + available}}\n"
                            "else:\n"
                            "    lens_mm = int('{lens_mm}' or '50') if '{lens_mm}'.strip() else 50\n"
                            "    frames = int('{frames}' or '120') if '{frames}'.strip() else 120\n"
                            "    samples = int('{samples}' or '128') if '{samples}'.strip() else 128\n"
                            "\n"
                            "    stage = hou.node('/stage')\n"
                            "    if stage is None:\n"
                            "        stage = hou.node('/obj').createNode('lopnet', 'stage')\n"
                            "\n"
                            "    # --- Camera with real sensor match ---\n"
                            "    cam_name = slug + '_cam'\n"
                            "    cam = stage.createNode('camera', cam_name)\n"
                            "    cam.parm('primpath').set('/cameras/' + cam_name)\n"
                            "    cam.parm('horizontalAperture').set(sensor['width'])\n"
                            "    cam.parm('verticalAperture').set(sensor['height'])\n"
                            "    cam.parm('focalLength').set(lens_mm)\n"
                            "    cam.parm('clippingRange1').set(0.1)\n"
                            "    cam.parm('clippingRange2').set(10000)\n"
                            "\n"
                            "    # --- Camera orbit keyframes ---\n"
                            "    radius = 5.0\n"
                            "    height = 1.5\n"
                            "    for f in range(1, frames + 1):\n"
                            "        angle = (f - 1) * (2 * math.pi / frames)\n"
                            "        x = radius * math.cos(angle)\n"
                            "        z = radius * math.sin(angle)\n"
                            "        cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(x, hou.frameToTime(f)),), 0)\n"
                            "        cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(height, hou.frameToTime(f)),), 1)\n"
                            "        cam.parmTuple('t').setKeyframe("
                            "(hou.Keyframe(z, hou.frameToTime(f)),), 2)\n"
                            "\n"
                            "    # --- 3-point lighting (4:1 key:fill ratio) ---\n"
                            "    key = stage.createNode('light', 'key_light')\n"
                            "    key.parm('primpath').set('/lights/key_light')\n"
                            "    key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "    key.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "    key.parm('xn__inputsexposure_vya').set(5.0)\n"
                            "    key.parmTuple('t').set((3, 4, 2))\n"
                            "    key.parmTuple('r').set((-35, 45, 0))\n"
                            "\n"
                            "    fill = stage.createNode('light', 'fill_light')\n"
                            "    fill.parm('primpath').set('/lights/fill_light')\n"
                            "    fill.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "    fill.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "    fill.parm('xn__inputsexposure_vya').set(3.0)\n"
                            "    fill.parmTuple('t').set((-3, 3, 2))\n"
                            "    fill.parmTuple('r').set((-25, -45, 0))\n"
                            "\n"
                            "    rim = stage.createNode('light', 'rim_light')\n"
                            "    rim.parm('primpath').set('/lights/rim_light')\n"
                            "    rim.parm('xn__inputsintensity_i0a').set(1.0)\n"
                            "    rim.parm('xn__inputsexposure_control_wcb').set('set')\n"
                            "    rim.parm('xn__inputsexposure_vya').set(4.5)\n"
                            "    rim.parmTuple('t').set((0, 3, -4))\n"
                            "    rim.parmTuple('r').set((-20, 180, 0))\n"
                            "\n"
                            "    # --- Merge scene ---\n"
                            "    merge = stage.createNode('merge', 'scene_merge')\n"
                            "    inputs = [cam, key, fill, rim]\n"
                            "    for i, node in enumerate(inputs):\n"
                            "        merge.setInput(i, node)\n"
                            "\n"
                            "    # --- Render settings: Karma XPU 1920x1080 ---\n"
                            "    rs = stage.createNode('karmarenderproperties', "
                            "'render_settings')\n"
                            "    rs.setInput(0, merge)\n"
                            "    rs.parm('resolutionx').set(1920)\n"
                            "    rs.parm('resolutiony').set(1080)\n"
                            "    rs.parm('engine').set('XPU')\n"
                            "    rs.parm('samplesperpixel').set(samples)\n"
                            "\n"
                            "    # --- Karma LOP ---\n"
                            "    karma = stage.createNode('karma', 'karma_render')\n"
                            "    karma.setInput(0, rs)\n"
                            "    karma.parm('camera').set('/cameras/' + cam_name)\n"
                            "    karma.parm('picture').set("
                            "'$HIP/render/$HIPNAME/$HIPNAME.$F4.exr')\n"
                            "\n"
                            "    stage.layoutChildren()\n"
                            "    result = {{'camera': cam.path(), "
                            "'prim_path': '/cameras/' + cam_name, "
                            "'sensor': sensor['name'], "
                            "'horizontal_aperture': sensor['width'], "
                            "'vertical_aperture': sensor['height'], "
                            "'focal_length': lens_mm, "
                            "'frames': frames, "
                            "'samples': samples, "
                            "'resolution': '1920x1080', "
                            "'karma': karma.path(), "
                            "'output': '$HIP/render/$HIPNAME/$HIPNAME.$F4.exr', "
                            "'key_exposure': 5.0, 'fill_exposure': 3.0, "
                            "'rim_exposure': 4.5}}\n"
                        ),
                    },
                    gate_level=GateLevel.APPROVE,
                    output_var="turntable_cam",
                ),
            ],
        ))

        # --- Safe Render (pre-flight validation) ---
        self.register(Recipe(
            name="safe_render",
            description=(
                "Render with pre-flight validation -- checks camera, "
                "materials, output path before rendering"
            ),
            triggers=[
                r"^(?:safe|validated?)\s+render",
                r"^render\s+(?:safe|with\s+validation)",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="safe_render",
                    payload_template={},
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Progressive Render (3-pass) ---
        self.register(Recipe(
            name="render_progressively",
            description=(
                "Progressive 3-pass render: test (256x256) -> "
                "preview (720p) -> production"
            ),
            triggers=[
                r"^(?:progressive|incremental)\s+render",
                r"^render\s+progressive(?:ly)?",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="render",
            steps=[
                RecipeStep(
                    action="render_progressively",
                    payload_template={},
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- DOP Network Setup ---
        self.register(Recipe(
            name="dop_network_setup",
            description=(
                "Create a properly wired DOP network with solver, "
                "object, and merge nodes"
            ),
            triggers=[
                r"^(?:set\s*up|create|build)\s+(?:a\s+)?dop\s+(?:network|sim)",
                r"^(?:simulation|dynamics)\s+setup",
            ],
            parameters=[],
            gate_level=GateLevel.REVIEW,
            category="sim",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import hou\n"
                            "\n"
                            "# Create DOP network\n"
                            "obj = hou.node('/obj')\n"
                            "dopnet = obj.createNode('dopnet', 'simulation')\n"
                            "\n"
                            "# Create gravity force\n"
                            "gravity = dopnet.createNode('gravity', 'gravity_force')\n"
                            "\n"
                            "# Create RBD solver\n"
                            "solver = dopnet.createNode('rigidbodysolver', 'rbd_solver')\n"
                            "\n"
                            "# Create RBD packed object\n"
                            "rbd_obj = dopnet.createNode('rbdpackedobject', 'rbd_object')\n"
                            "\n"
                            "# Create merge to wire forces into solver "
                            "(DOP convention: merge, not direct wires)\n"
                            "merge = dopnet.createNode('merge', 'force_merge')\n"
                            "merge.setInput(0, gravity)\n"
                            "\n"
                            "# Wire: object + merged forces -> solver\n"
                            "solver.setInput(0, merge)\n"
                            "solver.setInput(1, rbd_obj)\n"
                            "\n"
                            "# Create output null\n"
                            "out = dopnet.createNode('output', 'OUT')\n"
                            "out.setInput(0, solver)\n"
                            "out.setDisplayFlag(True)\n"
                            "out.setRenderFlag(True)\n"
                            "\n"
                            "# Layout\n"
                            "dopnet.layoutChildren()\n"
                            "\n"
                            "result = {'dopnet': dopnet.path(), "
                            "'solver': solver.path(), "
                            "'object': rbd_obj.path(), "
                            "'gravity': gravity.path(), "
                            "'output': out.path()}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        # --- Verify Installation ---
        self.register(Recipe(
            name="verify_installation",
            description=(
                "Compare source and deployed file checksums to "
                "detect installation drift"
            ),
            triggers=[
                r"^verify\s+(?:install(?:ation)?|deployment|sync)",
                r"^check\s+(?:install|drift|sync)",
            ],
            parameters=[],
            gate_level=GateLevel.INFORM,
            category="utility",
            steps=[
                RecipeStep(
                    action="execute_python",
                    payload_template={
                        "code": (
                            "import os\n"
                            "import hashlib\n"
                            "import json\n"
                            "\n"
                            "def _file_hash(path):\n"
                            "    try:\n"
                            "        with open(path, 'rb') as f:\n"
                            "            return hashlib.sha256(f.read()).hexdigest()\n"
                            "    except (OSError, IOError):\n"
                            "        return None\n"
                            "\n"
                            "home = os.path.expanduser('~')\n"
                            "source_dir = os.path.join(home, '.synapse', 'houdini')\n"
                            "deploy_dir = os.path.join(home, 'houdini21.0')\n"
                            "\n"
                            "file_map = {\n"
                            "    'python_panels/synapse_panel.pypanel': "
                            "'python_panels/synapse_panel.pypanel',\n"
                            "    'toolbar/synapse.shelf': "
                            "'toolbar/synapse.shelf',\n"
                            "    'scripts/python/synapse_shelf.py': "
                            "'scripts/python/synapse_shelf.py',\n"
                            "}\n"
                            "\n"
                            "drift = []\n"
                            "missing = []\n"
                            "synced = []\n"
                            "\n"
                            "for src_rel, dst_rel in sorted(file_map.items()):\n"
                            "    src_path = os.path.join(source_dir, src_rel)\n"
                            "    dst_path = os.path.join(deploy_dir, dst_rel)\n"
                            "    src_hash = _file_hash(src_path)\n"
                            "    dst_hash = _file_hash(dst_path)\n"
                            "    if src_hash is None:\n"
                            "        missing.append({'file': src_rel, "
                            "'issue': 'source missing'})\n"
                            "    elif dst_hash is None:\n"
                            "        missing.append({'file': dst_rel, "
                            "'issue': 'not deployed'})\n"
                            "    elif src_hash != dst_hash:\n"
                            "        drift.append({'file': src_rel, "
                            "'source_hash': src_hash[:12], "
                            "'deployed_hash': dst_hash[:12]})\n"
                            "    else:\n"
                            "        synced.append(src_rel)\n"
                            "\n"
                            "result = json.dumps({'synced': len(synced), "
                            "'drift': drift, 'missing': missing"
                            "}, sort_keys=True)\n"
                            "if drift:\n"
                            "    result = json.dumps({'synced': len(synced), "
                            "'drift': drift, 'missing': missing, "
                            "'suggestion': "
                            "'Run: python ~/.synapse/install.py --verify'"
                            "}, sort_keys=True)\n"
                            "print(result)\n"
                        ),
                    },
                    gate_level=GateLevel.INFORM,
                ),
            ],
        ))

        # --- TOPS Workflow Recipes ---

        self.register(Recipe(
            name="resume_failed_tops_cook",
            description="Dirty failed work items and re-cook a TOP node",
            triggers=[
                r"^(?:re-?)?cook\s+failed\s+(?:items?\s+)?(?:in\s+|on\s+)?(?P<node>.+)$",
                r"^retry\s+failed\s+(?:tops?\s+)?(?:in\s+|on\s+)?(?P<node>.+)$",
                r"^resume\s+(?:failed\s+)?(?:tops?\s+)?cook\s+(?:in\s+|on\s+)?(?P<node>.+)$",
            ],
            parameters=["node"],
            gate_level=GateLevel.REVIEW,
            category="tops",
            steps=[
                RecipeStep(
                    action="tops_dirty_node",
                    payload_template={"node": "{node}", "dirty_upstream": False},
                    gate_level=GateLevel.INFORM,
                ),
                RecipeStep(
                    action="tops_cook_node",
                    payload_template={"node": "{node}", "block": True},
                    gate_level=GateLevel.REVIEW,
                ),
            ],
        ))

        self.register(Recipe(
            name="tops_monitored_render",
            description="Render a frame sequence via TOPS with live monitoring",
            triggers=[
                r"^render\s+(?:frames?\s+)?(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)\s+with\s+monitor(?:ing)?$",
                r"^(?:tops?\s+)?render\s+(?:and\s+)?monitor\s+(?:frames?\s+)?(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)$",
                r"^monitored?\s+render\s+(?P<frame_start>\d+)\s*[-\u2013to]+\s*(?P<frame_end>\d+)$",
            ],
            parameters=["frame_start", "frame_end"],
            gate_level=GateLevel.REVIEW,
            category="tops",
            steps=[
                RecipeStep(
                    action="tops_render_sequence",
                    payload_template={
                        "frame_range": ["{frame_start}", "{frame_end}"],
                        "blocking": False,
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="render",
                ),
                RecipeStep(
                    action="tops_monitor_stream",
                    payload_template={
                        "node": "$render.topnet",
                    },
                    gate_level=GateLevel.INFORM,
                ),
            ],
        ))
