"""
Synapse Recipe Registry

Pre-built, pre-approved multi-step operation templates.
Recipes execute at Tier 0 speed by expanding triggers into
sequences of SynapseCommands without any LLM involvement.

Artists can register custom recipes via registry.register().
"""

import re
import time
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
                f"recipe:{self.action}:{str(payload)}:{time.time()}", "cmd"
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
            description="Create a color correction chain (color_correct → grade → null merge point)",
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
