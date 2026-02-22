"""
Synapse Tiered Routing System

Dispatches artist input to the fastest capable handler:
  Recipe  → Pre-built multi-step templates (<200ms)
  Tier 0  → Regex-based command parsing (<200ms)
  Tier 1  → In-memory knowledge lookup (<1s)
  Tier 2  → Haiku LLM + RAG context (<5s)
  Tier 3  → Full agent loop (async, <15s)

LLM tiers (2-3) require optional `anthropic` dependency.
All other tiers have zero external dependencies.
"""

from .parser import CommandParser, ParseResult
from .knowledge import KnowledgeIndex, KnowledgeLookupResult
from .recipes import Recipe, RecipeStep, RecipeRegistry
from .cache import ResponseCache
from .router import (
    TieredRouter,
    RoutingResult,
    RoutingTier,
    RoutingConfig,
)
from .adaptation import EpochAdapter, TierEpoch, TierThresholds

__all__ = [
    # Tier 0
    "CommandParser",
    "ParseResult",
    # Tier 1
    "KnowledgeIndex",
    "KnowledgeLookupResult",
    # Recipes
    "Recipe",
    "RecipeStep",
    "RecipeRegistry",
    # Cache (He2025)
    "ResponseCache",
    # Router
    "TieredRouter",
    "RoutingResult",
    "RoutingTier",
    "RoutingConfig",
    # Adaptation (He2025)
    "EpochAdapter",
    "TierEpoch",
    "TierThresholds",
]
