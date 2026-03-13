"""
Synapse Recipe Registry — Base classes and registry.

Pre-built, pre-approved multi-step operation templates.
Recipes execute at Tier 0 speed by expanding triggers into
sequences of SynapseCommands without any LLM involvement.

Artists can register custom recipes via registry.register().
"""

import json
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from ...core.protocol import SynapseCommand
from ...core.gates import GateLevel
from ...core.determinism import deterministic_uuid


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
        from .scene_recipes import register_scene_recipes
        from .render_recipes import register_render_recipes
        from .fx_recipes import register_fx_recipes
        from .pipeline_recipes import register_pipeline_recipes
        from .tops_recipes import register_tops_recipes

        register_scene_recipes(self)
        register_render_recipes(self)
        register_fx_recipes(self)
        register_pipeline_recipes(self)
        register_tops_recipes(self)
