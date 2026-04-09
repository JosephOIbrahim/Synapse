"""
SYNAPSE Shared — Canonical types, Lossless Execution Bridge, Memory Evolution, MOE Router.

All agents import from this package. INTEGRATOR owns write access to types.py.
"""

from .types import (
    # Type aliases
    NodePath, PrimPath, Fingerprint, SceneHash,
    # Constants
    FIDELITY_DEGRADED,
    GATE_TIMEOUT_APPROVE, GATE_TIMEOUT_CRITICAL,
    # Enums
    AgentID, TaskStatus, DomainSignal, TaskType, Complexity, Urgency,
    # Dataclasses
    ExecutionResult, TaskSpec, AgentDispatch,
    ConnectionSpec, NodeSpec, NodeManifest,
    GraphNodeSpec, GraphConnectionSpec, GraphSpec,
    GeoSummary, RoutingFeatures,
    ChainStep, ChainSpec,
    # Registry
    FILE_OWNERSHIP,
)

from .bridge import (
    LosslessExecutionBridge,
    IntegrityBlock,
    GateLevel,
    Operation,
    AgentHandoff,
    EmergencyProtocol,
)

from .evolution import (
    LosslessEvolution,
    EvolutionCheck,
    EvolutionResult,
    EvolutionIntegrity,
    SessionEntry,
    Decision,
    AssetRef,
    ParameterRecord,
    ParsedMemory,
)

from .router import (
    MOERouter,
    RoutingDecision,
    extract_features,
    route_task,
    get_default_router,
    reset_default_router,
)

from .conductor_advisor import (
    ConductorAdvisor,
    HistoryEntry,
    Recommendation,
    RecommendationHistory,
    advise_from_bridge,
)

from . import constants

__all__ = [
    # --- types.py ---
    # Type aliases
    "NodePath", "PrimPath", "Fingerprint", "SceneHash",
    # Constants
    "FIDELITY_DEGRADED",
    "GATE_TIMEOUT_APPROVE", "GATE_TIMEOUT_CRITICAL",
    # Enums
    "AgentID", "TaskStatus", "DomainSignal", "TaskType", "Complexity", "Urgency",
    # Dataclasses
    "ExecutionResult", "TaskSpec", "AgentDispatch",
    "ConnectionSpec", "NodeSpec", "NodeManifest",
    "GraphNodeSpec", "GraphConnectionSpec", "GraphSpec",
    "GeoSummary", "RoutingFeatures",
    "ChainStep", "ChainSpec",
    # Registry
    "FILE_OWNERSHIP",
    # --- bridge.py ---
    "LosslessExecutionBridge",
    "IntegrityBlock",
    "GateLevel",
    "Operation",
    "AgentHandoff",
    "EmergencyProtocol",
    # --- evolution.py ---
    "LosslessEvolution",
    "EvolutionCheck",
    "EvolutionResult",
    "EvolutionIntegrity",
    "SessionEntry",
    "Decision",
    "AssetRef",
    "ParameterRecord",
    "ParsedMemory",
    # --- router.py ---
    "MOERouter",
    "RoutingDecision",
    "extract_features",
    "route_task",
    "get_default_router",
    "reset_default_router",
    # --- conductor_advisor.py ---
    "ConductorAdvisor",
    "HistoryEntry",
    "Recommendation",
    "RecommendationHistory",
    "advise_from_bridge",
    # --- constants.py ---
    "constants",
]
