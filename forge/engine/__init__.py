# FORGE Engine
# Factory for Optimized Recursive Growth Engine
"""
Core engine modules for SYNAPSE self-improvement loop.
Designed to be imported by Claude Code orchestrator.
"""

__version__ = "1.0.0"

from .schemas import (
    FailureCategory,
    AgentRole,
    ScenarioDomain,
    ScenarioComplexity,
    ScenarioFocus,
    CorpusStage,
    ToolCall,
    ScenarioDefinition,
    ScenarioResult,
    CorpusEntry,
    CycleMetrics,
    BacklogItem,
    AgentAssignment,
)
from .orchestrator import ForgeOrchestrator
from .metrics import MetricsTracker
from .corpus_manager import CorpusManager

__all__ = [
    # Schemas
    "FailureCategory",
    "AgentRole",
    "ScenarioDomain",
    "ScenarioComplexity",
    "ScenarioFocus",
    "CorpusStage",
    "ToolCall",
    "ScenarioDefinition",
    "ScenarioResult",
    "CorpusEntry",
    "CycleMetrics",
    "BacklogItem",
    "AgentAssignment",
    # Engine
    "ForgeOrchestrator",
    "MetricsTracker",
    "CorpusManager",
]
