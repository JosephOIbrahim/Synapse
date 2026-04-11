"""SYNAPSE constants -- single source of truth.

Every magic number, keyword list, threshold, and timeout lives here.
Other modules import from this file. No module defines its own constants.
"""

from __future__ import annotations

__all__ = [
    # Gate system
    "GATE_TIMEOUT_APPROVE",
    "GATE_TIMEOUT_CRITICAL",
    "GATE_POLL_INTERVAL",
    "OPERATION_GATES",
    "READ_ONLY_OPS",
    "READ_ONLY_PREFIXES",
    # Fidelity
    "FIDELITY_PERFECT",
    "FIDELITY_DEGRADED",
    # Hashing
    "HASH_LENGTH",
    # Routing — domain & task keywords
    "DOMAIN_KEYWORDS",
    "TASK_TYPE_KEYWORDS",
    "URGENCY_BLOCKING_PATTERN",
    "URGENCY_EXPLORATORY_PATTERN",
    # Routing — affinity tables
    "DOMAIN_AFFINITY",
    "TASK_TYPE_BOOST",
    "FAST_PATHS",
    # Routing — scoring
    "ROUTER_CALIBRATION_PERIOD",
    "ADVISORY_SCORE_THRESHOLD",
    "ADVISORY_GAP_RATIO",
    "FAST_PATH_PROMOTION_THRESHOLD",
    "BLOCKING_URGENCY_BOOST",
    "COMPLEX_SCORE_MULTIPLIER",
    "RESEARCH_INTEGRATOR_FLOOR",
    "COMPLEX_SOLO_DOMAINS",
    "CONSTANTS_HASH",
    # Evolution
    "EVOLUTION_TRIGGERS",
    "EVOLUTION_STAGE_FLAT",
    "EVOLUTION_STAGE_STRUCTURED",
    "EVOLUTION_STAGE_COMPOSED",
    # Pipeline stages
    "PIPELINE_STAGES",
    # Agent context requirements
    "AGENT_CONTEXT_REQUIREMENTS",
    # Render validation
    "RENDER_VALIDATE_CHECKS",
    "RENDER_VALIDATE_DEFAULTS",
    # PDG
    "PDG_DEFER_TIMEOUT",
]


# We need the enums for type-safe constant definitions.
# Avoid circular imports: types.py has no dependency on constants.py.
from shared.types import (
    AgentID,
    DomainSignal,
    TaskType,
)


# ---------------------------------------------------------------------------
# Gate System
# ---------------------------------------------------------------------------

GATE_TIMEOUT_APPROVE: float = 120.0
GATE_TIMEOUT_CRITICAL: float = 300.0
GATE_POLL_INTERVAL: float = 0.25

# Gate level strings are used as keys; the GateLevel enum lives in bridge.py
# because it is tightly coupled to Operation. We store the mapping as strings
# here to avoid importing GateLevel (which would create a circular dep).
# bridge.py converts them at module load via GateLevel(value).
OPERATION_GATES: dict[str, str] = {
    "read_network": "inform",
    "inspect_geometry": "inform",
    "read_stage": "inform",
    "capture_viewport": "inform",
    "create_node": "inform",
    "set_parameter": "inform",
    "connect_nodes": "inform",
    "apply_vex": "inform",
    "create_material": "inform",
    "lock_seed": "inform",
    "delete_node": "review",
    "build_from_manifest": "review",
    "build_rig_logic": "review",
    "evolve_memory": "review",
    "submit_render": "approve",
    "export_file": "approve",
    "cook_pdg_chain": "approve",
    "prune_memory": "approve",
    "execute_python": "critical",
    "execute_vex": "critical",
}

READ_ONLY_OPS: tuple[str, ...] = (
    "read_only",
    "read_network",
    "inspect_geometry",
    "read_stage",
    "capture_viewport",
)

READ_ONLY_PREFIXES: tuple[str, ...] = ("read_", "inspect_", "capture_")


# ---------------------------------------------------------------------------
# Fidelity
# ---------------------------------------------------------------------------

FIDELITY_PERFECT: float = 1.0
FIDELITY_DEGRADED: float = 0.5


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

HASH_LENGTH: int = 16


# ---------------------------------------------------------------------------
# Routing — Domain & Task Type Keywords
# ---------------------------------------------------------------------------

DOMAIN_KEYWORDS: dict[str, DomainSignal] = {
    # Async / Transport
    "async": DomainSignal.ASYNC, "websocket": DomainSignal.ASYNC,
    "thread": DomainSignal.ASYNC, "deferred": DomainSignal.ASYNC,
    "mcp": DomainSignal.MCP, "server": DomainSignal.MCP,
    "tool": DomainSignal.MCP, "protocol": DomainSignal.MCP,
    # Error handling
    "error": DomainSignal.ERROR_HANDLING, "fix": DomainSignal.ERROR_HANDLING,
    "debug": DomainSignal.ERROR_HANDLING, "crash": DomainSignal.ERROR_HANDLING,
    "retry": DomainSignal.ERROR_HANDLING, "recover": DomainSignal.ERROR_HANDLING,
    # VEX
    "vex": DomainSignal.VEX, "wrangle": DomainSignal.VEX,
    "snippet": DomainSignal.VEX, "attrib": DomainSignal.VEX,
    "expression": DomainSignal.VEX, "channel": DomainSignal.VEX,
    # Geometry
    "geometry": DomainSignal.GEOMETRY, "mesh": DomainSignal.GEOMETRY,
    "points": DomainSignal.GEOMETRY, "prims": DomainSignal.GEOMETRY,
    "introspect": DomainSignal.GEOMETRY, "inspect": DomainSignal.GEOMETRY,
    "sop": DomainSignal.GEOMETRY, "volume": DomainSignal.GEOMETRY,
    "polygon": DomainSignal.GEOMETRY,
    # USD / Solaris
    "usd": DomainSignal.USD, "solaris": DomainSignal.USD,
    "lop": DomainSignal.USD, "stage": DomainSignal.USD,
    "prim": DomainSignal.USD, "composition": DomainSignal.USD,
    "variant": DomainSignal.USD, "layer": DomainSignal.USD,
    "payload": DomainSignal.USD, "sublayer": DomainSignal.USD,
    "collection": DomainSignal.USD,
    "inherits": DomainSignal.USD, "specializes": DomainSignal.USD,
    "reference": DomainSignal.USD, "relationship": DomainSignal.USD,
    "attribute": DomainSignal.USD, "schema": DomainSignal.USD,
    "scenegraph": DomainSignal.USD,
    # MaterialX
    "materialx": DomainSignal.MATERIALX, "mtlx": DomainSignal.MATERIALX,
    "shader": DomainSignal.MATERIALX, "material": DomainSignal.MATERIALX,
    "texture": DomainSignal.MATERIALX, "bsdf": DomainSignal.MATERIALX,
    "nodegraph": DomainSignal.MATERIALX,
    # APEX
    "apex": DomainSignal.APEX, "rig": DomainSignal.APEX,
    "autorig": DomainSignal.APEX, "skeleton": DomainSignal.APEX,
    # Copernicus
    "copernicus": DomainSignal.COPS, "cop": DomainSignal.COPS,
    "gpu": DomainSignal.COPS, "compositing": DomainSignal.COPS,
    # Rendering
    "render": DomainSignal.RENDERING, "karma": DomainSignal.RENDERING,
    "wedge": DomainSignal.RENDERING, "lookdev": DomainSignal.RENDERING,
    "xpu": DomainSignal.RENDERING, "mantra": DomainSignal.RENDERING,
    "ipr": DomainSignal.RENDERING, "denoiser": DomainSignal.RENDERING,
    "aov": DomainSignal.RENDERING, "lpe": DomainSignal.RENDERING,
    # PDG
    "pdg": DomainSignal.PDG, "tops": DomainSignal.PDG,
    "farm": DomainSignal.PDG, "batch": DomainSignal.PDG,
    "pipeline": DomainSignal.PDG, "orchestrat": DomainSignal.PDG,
    "work_item": DomainSignal.PDG, "scheduler": DomainSignal.PDG,
    # Testing
    "test": DomainSignal.TESTING, "pytest": DomainSignal.TESTING,
    "validate": DomainSignal.TESTING, "ci": DomainSignal.TESTING,
}

TASK_TYPE_KEYWORDS: dict[str, TaskType] = {
    "build": TaskType.GENERATION, "create": TaskType.GENERATION,
    "generate": TaskType.GENERATION, "make": TaskType.GENERATION,
    "architect": TaskType.ARCHITECTURE, "design": TaskType.ARCHITECTURE,
    "refactor": TaskType.ARCHITECTURE, "structure": TaskType.ARCHITECTURE,
    "read": TaskType.OBSERVATION, "inspect": TaskType.OBSERVATION,
    "observe": TaskType.OBSERVATION, "capture": TaskType.OBSERVATION,
    "run": TaskType.EXECUTION, "execute": TaskType.EXECUTION,
    "cook": TaskType.EXECUTION, "apply": TaskType.EXECUTION,
    "orchestrate": TaskType.ORCHESTRATION, "schedule": TaskType.ORCHESTRATION,
    "wedge": TaskType.ORCHESTRATION, "farm": TaskType.ORCHESTRATION,
    "test": TaskType.INTEGRATION, "merge": TaskType.INTEGRATION,
    "validate": TaskType.INTEGRATION, "review": TaskType.INTEGRATION,
}

URGENCY_BLOCKING_PATTERN: str = r"\b(urgent|blocking|broken|crash|fix|halt|immediately)\b"
URGENCY_EXPLORATORY_PATTERN: str = r"\b(explore|experiment|maybe|could|try)\b"


# ---------------------------------------------------------------------------
# Routing — Affinity Tables
# ---------------------------------------------------------------------------

DOMAIN_AFFINITY: dict[DomainSignal, dict[AgentID, float]] = {
    DomainSignal.ASYNC:          {AgentID.SUBSTRATE: 1.0, AgentID.INTEGRATOR: 0.3},
    DomainSignal.MCP:            {AgentID.SUBSTRATE: 1.0, AgentID.INTEGRATOR: 0.4},
    DomainSignal.ERROR_HANDLING: {AgentID.BRAINSTEM: 1.0, AgentID.SUBSTRATE: 0.3},
    DomainSignal.VEX:            {AgentID.BRAINSTEM: 0.8, AgentID.HANDS: 0.5},
    DomainSignal.GEOMETRY:       {AgentID.OBSERVER: 0.9, AgentID.HANDS: 0.6},
    DomainSignal.USD:            {AgentID.HANDS: 1.0, AgentID.OBSERVER: 0.4},
    DomainSignal.MATERIALX:      {AgentID.HANDS: 1.0, AgentID.OBSERVER: 0.3},
    DomainSignal.APEX:           {AgentID.HANDS: 1.0},
    DomainSignal.COPS:           {AgentID.HANDS: 1.0, AgentID.OBSERVER: 0.3},
    DomainSignal.RENDERING:      {AgentID.CONDUCTOR: 0.7, AgentID.HANDS: 0.6, AgentID.OBSERVER: 0.5},
    DomainSignal.PDG:            {AgentID.CONDUCTOR: 1.0, AgentID.BRAINSTEM: 0.3},
    DomainSignal.TESTING:        {AgentID.INTEGRATOR: 1.0},
}

TASK_TYPE_BOOST: dict[TaskType, dict[AgentID, float]] = {
    TaskType.ARCHITECTURE:   {AgentID.SUBSTRATE: 0.4, AgentID.INTEGRATOR: 0.3},
    TaskType.EXECUTION:      {AgentID.BRAINSTEM: 0.4, AgentID.SUBSTRATE: 0.2},
    TaskType.OBSERVATION:    {AgentID.OBSERVER: 0.5},
    TaskType.GENERATION:     {AgentID.HANDS: 0.4, AgentID.BRAINSTEM: 0.2},
    TaskType.ORCHESTRATION:  {AgentID.CONDUCTOR: 0.5},
    TaskType.INTEGRATION:    {AgentID.INTEGRATOR: 0.5},
}

FAST_PATHS: dict[str, tuple[AgentID, AgentID | None]] = {
    "architecture|moderate|async+mcp|normal":           (AgentID.SUBSTRATE, AgentID.INTEGRATOR),
    "execution|moderate|error_handling+vex|blocking":   (AgentID.BRAINSTEM, AgentID.SUBSTRATE),
    "observation|trivial|geometry|normal":              (AgentID.OBSERVER, None),
    "generation|moderate|materialx+usd|normal":         (AgentID.HANDS, AgentID.OBSERVER),
    "generation|complex|apex|normal":                   (AgentID.HANDS, AgentID.OBSERVER),
    "generation|complex|cops|normal":                   (AgentID.HANDS, AgentID.OBSERVER),
    "orchestration|complex|pdg+rendering|normal":       (AgentID.CONDUCTOR, AgentID.BRAINSTEM),
    "integration|moderate|testing|normal":              (AgentID.INTEGRATOR, None),
    "generation|moderate|materialx+rendering|normal":  (AgentID.HANDS, AgentID.CONDUCTOR),
    "execution|moderate|rendering|blocking":           (AgentID.CONDUCTOR, AgentID.BRAINSTEM),
}


# ---------------------------------------------------------------------------
# Routing — Scoring Thresholds
# ---------------------------------------------------------------------------

ROUTER_CALIBRATION_PERIOD: int = 10
ADVISORY_SCORE_THRESHOLD: float = 0.3       # absolute floor — never route on noise
ADVISORY_GAP_RATIO: float = 0.6             # advisory must be >= ratio * primary score
FAST_PATH_PROMOTION_THRESHOLD: int = 3      # fingerprint count → auto-promoted to session fast path
BLOCKING_URGENCY_BOOST: float = 0.2
COMPLEX_SCORE_MULTIPLIER: float = 1.2
RESEARCH_INTEGRATOR_FLOOR: float = 0.5

# Domains intrinsically complex even when seen alone — APEX rigging and COPs
# graphs require COMPLEX classification regardless of how many other signals
# co-occur. Mirrors hand-tuned entries in FAST_PATHS.
COMPLEX_SOLO_DOMAINS: frozenset = frozenset({
    DomainSignal.APEX,
    DomainSignal.COPS,
})


# Legacy word-count thresholds removed in April 2026 — never consulted by
# extract_features(). Word count of an LLM-rewritten prompt has no
# relationship to task complexity.


# ---------------------------------------------------------------------------
# Evolution
# ---------------------------------------------------------------------------

EVOLUTION_TRIGGERS: dict[str, int | float] = {
    "structured_data_count": 5,
    "asset_references": 3,
    "parameter_records": 5,
    "wedge_results": 1,
    "session_count": 10,
    "file_size_kb": 100,
    "node_path_references": 10,
}

# Canonical evolution stage values use the Pokémon model documented in
# CLAUDE.md §6 and referenced by the forge corpus, scene memory tests, and
# the living-memory design plan. The variable names below are internal
# aliases that describe the *technical* layer (flat text → structured prims
# → composition arcs); the *value* is what gets serialized into agent.usd
# and round-tripped by every consumer.
EVOLUTION_STAGE_FLAT: str = "charmander"        # memory.md, no schema
EVOLUTION_STAGE_STRUCTURED: str = "charmeleon"  # memory.usd, typed prims
EVOLUTION_STAGE_COMPOSED: str = "charizard"     # memory.usd + composition arcs


# ---------------------------------------------------------------------------
# Pipeline Stages
# ---------------------------------------------------------------------------

PIPELINE_STAGES: tuple[str, ...] = (
    "observe",
    "constraint",
    "plan",
    "specialize",
    "execute",
    "verify",
)


# ---------------------------------------------------------------------------
# Agent Context Requirements
# ---------------------------------------------------------------------------

AGENT_CONTEXT_REQUIREMENTS: dict[AgentID, set[str]] = {
    AgentID.SUBSTRATE: {"operation_type"},
    AgentID.BRAINSTEM: {"node_path"},
    AgentID.OBSERVER: {"network_path"},
    AgentID.HANDS: {"domain"},
    AgentID.CONDUCTOR: set(),
    AgentID.INTEGRATOR: {"files_touched"},
}


# ---------------------------------------------------------------------------
# PDG / TOPS
# ---------------------------------------------------------------------------

PDG_DEFER_TIMEOUT: float = 60.0    # extended timeout for PDG graph context cold-start


# ---------------------------------------------------------------------------
# Render Validation
# ---------------------------------------------------------------------------

RENDER_VALIDATE_CHECKS: tuple[str, ...] = (
    "file_integrity", "black_frame", "nan_check",
    "clipping", "underexposure", "saturation",
)

RENDER_VALIDATE_DEFAULTS: dict[str, float] = {
    "black_frame_mean": 0.001,
    "clipping_pct": 0.5,
    "underexposure_mean": 0.05,
    "saturation_pct": 0.1,
    "saturation_multiplier": 10.0,
}


# ---------------------------------------------------------------------------
# Constants Hash — feature schema fingerprint
# ---------------------------------------------------------------------------
# Computed at module load from the routing tables that influence fingerprint
# generation. If any of these change, CONSTANTS_HASH changes, and any
# session-learned fast paths stamped with the old hash are invalidated by
# MOERouter on the next call. Hand-maintained FAST_PATHS entries are NOT
# invalidated automatically — they're validated by tests/test_router_internals.py.

import hashlib as _hashlib

def _compute_constants_hash() -> str:
    parts = [
        repr(sorted((k, v.value) for k, v in DOMAIN_KEYWORDS.items())),
        repr(sorted((k, v.value) for k, v in TASK_TYPE_KEYWORDS.items())),
        URGENCY_BLOCKING_PATTERN,
        URGENCY_EXPLORATORY_PATTERN,
        repr(sorted(FAST_PATHS.keys())),
    ]
    return _hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]

CONSTANTS_HASH: str = _compute_constants_hash()
