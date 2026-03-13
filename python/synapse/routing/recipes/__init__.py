"""
Synapse Recipe Registry

Pre-built, pre-approved multi-step operation templates.
Recipes execute at Tier 0 speed by expanding triggers into
sequences of SynapseCommands without any LLM involvement.

Artists can register custom recipes via registry.register().

This package maintains full backward compatibility with the
original monolith recipes.py module.
"""

from .base import RecipeStep, Recipe, RecipeRegistry

__all__ = [
    "RecipeStep",
    "Recipe",
    "RecipeRegistry",
]
