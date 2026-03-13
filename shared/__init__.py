"""
SYNAPSE Shared — Canonical types, Lossless Execution Bridge, Memory Evolution, MOE Router.

All agents import from this package. INTEGRATOR owns write access to types.py.
"""

from .types import (
    # Type aliases
    NodePath, PrimPath, Fingerprint, SceneHash,
    # Constants
    FIDELITY_THRESHOLD, FIDELITY_DEGRADED,
    GATE_TIMEOUT_REVIEW, GATE_TIMEOUT_APPROVE, GATE_TIMEOUT_CRITICAL,
    GATE_LEVEL_INFORM, GATE_LEVEL_REVIEW, GATE_LEVEL_APPROVE, GATE_LEVEL_CRITICAL,
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
)

from . import constants

__all__ = [
    # --- types.py ---
    # Type aliases
    "NodePath", "PrimPath", "Fingerprint", "SceneHash",
    # Constants
    "FIDELITY_THRESHOLD", "FIDELITY_DEGRADED",
    "GATE_TIMEOUT_REVIEW", "GATE_TIMEOUT_APPROVE", "GATE_TIMEOUT_CRITICAL",
    "GATE_LEVEL_INFORM", "GATE_LEVEL_REVIEW", "GATE_LEVEL_APPROVE", "GATE_LEVEL_CRITICAL",
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
    # --- constants.py ---
    "constants",
]
