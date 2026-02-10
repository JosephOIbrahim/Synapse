"""
Synapse Recipe Registry

Pre-built, pre-approved multi-step operation templates.
Recipes execute at Tier 0 speed by expanding triggers into
sequences of SynapseCommands without any LLM involvement.

Artists can register custom recipes via registry.register().
"""

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
        for key, value in self.payload_template.items():
            if isinstance(value, str) and "{" in value:
                payload[key] = value.format(**params)
            else:
                payload[key] = value

        return SynapseCommand(
            type=self.action,
            id=deterministic_uuid(
                f"recipe:{self.action}:{str(payload)}", "cmd"
            ),
            payload=payload,
        )

    def instantiate_with_vars(self, variables: Dict[str, str]) -> SynapseCommand:
        """Fill placeholders using accumulated variables (supports $var.field syntax)."""
        payload = {}
        for key, value in self.payload_template.items():
            if isinstance(value, str):
                # Replace $var.field references first
                resolved = value
                for var_key in sorted(variables.keys(), key=len, reverse=True):
                    resolved = resolved.replace(var_key, str(variables[var_key]))
                # Then standard {param} placeholders
                if "{" in resolved:
                    resolved = resolved.format(**{
                        k: v for k, v in variables.items()
                        if not k.startswith("$")
                    })
                payload[key] = resolved
            else:
                payload[key] = value

        return SynapseCommand(
            type=self.action,
            id=deterministic_uuid(
                f"recipe:{self.action}:{str(payload)}", "cmd"
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
                            "result = {'node': cache.path(), 'solver': solver.path(), "
                            "'cloth': cloth.path()}\n"
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
                            "result = {'node': cache.path(), 'solver': solver.path(), "
                            "'fracture': frac.path()}\n"
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
                            "result = {'camera': cam.path()}\n"
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
                            "result = {'node': out.path(), 'spectrum': spec.path(), "
                            "'evaluate': evl.path()}\n"
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
                            "result = {'node': cache.path(), 'solver': solver.path()}\n"
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
                            "result = {'node': cache.path(), 'solver': solver.path()}\n"
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
                            "result = {'node': out.path(), 'erosion': erode.path()}\n"
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
                            "result = {'dome': dome.path(), 'key': key.path(), "
                            "'fill': fill.path(), 'camera': cam.path()}\n"
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
                            "    result = {'error': 'Could not find node: {source}'}\n"
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
                            "    result = {'node': cache.path()}\n"
                        ),
                    },
                    gate_level=GateLevel.REVIEW,
                    output_var="cached",
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
