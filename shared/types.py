"""
SYNAPSE Agent Team — Shared Type Definitions
All agents import from this module. INTEGRATOR owns write access.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal
from enum import Enum
import json


# ── Type Aliases ───────────────────────────────────────────────

NodePath = str      # e.g., "/obj/geo1"
PrimPath = str      # e.g., "/World/Assets/Chair"
Fingerprint = str   # routing fingerprint, e.g. "architecture|moderate|async+mcp|normal"
SceneHash = str     # 16-char hex from topological hashing


# ── Constants ──────────────────────────────────────────────────
# Authoritative definitions live in shared/constants.py.
# Values here are kept in sync; constants.py is the source of truth.

FIDELITY_DEGRADED: float = 0.5

GATE_TIMEOUT_APPROVE: float = 120.0
GATE_TIMEOUT_CRITICAL: float = 300.0


# ── Agent Identity ──────────────────────────────────────────────

class AgentID(str, Enum):
    __slots__ = ()
    SUBSTRATE = "SUBSTRATE"
    BRAINSTEM = "BRAINSTEM"
    OBSERVER = "OBSERVER"
    HANDS = "HANDS"
    CONDUCTOR = "CONDUCTOR"
    INTEGRATOR = "INTEGRATOR"


# ── Task Status ─────────────────────────────────────────────────

class TaskStatus(str, Enum):
    __slots__ = ()
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


# ── Execution Results ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Universal result type — ALL agent operations return this."""
    success: bool
    result: Any | None = None
    error: str | None = None
    error_type: str | None = None
    retry_hint: str | None = None
    attempts: int = 1
    max_attempts: int = 3
    agent_id: AgentID | None = None
    integrity: Any | None = None  # IntegrityBlock when routed through bridge

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.agent_id:
            d["agent_id"] = self.agent_id.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def ok(cls, result: Any = None, agent_id: AgentID | None = None,
           integrity: Any | None = None) -> ExecutionResult:
        return cls(success=True, result=result, agent_id=agent_id,
                   integrity=integrity)

    @classmethod
    def fail(cls, error: str, error_type: str = "unknown",
             retry_hint: str | None = None,
             agent_id: AgentID | None = None) -> ExecutionResult:
        return cls(success=False, error=error, error_type=error_type,
                   retry_hint=retry_hint, agent_id=agent_id)

    def with_integrity(self, integrity: Any) -> ExecutionResult:
        """Return a new ExecutionResult with integrity attached."""
        return ExecutionResult(
            success=self.success,
            result=self.result,
            error=self.error,
            error_type=self.error_type,
            retry_hint=self.retry_hint,
            attempts=self.attempts,
            max_attempts=self.max_attempts,
            agent_id=self.agent_id,
            integrity=integrity,
        )


# ── Task Specification ──────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class TaskSpec:
    """Task specification for inter-agent dispatch."""
    task_id: str
    summary: str
    primary_agent: AgentID
    advisory_agent: AgentID | None = None
    context: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    status: TaskStatus = TaskStatus.PENDING
    deliverable_format: str = "ExecutionResult"


@dataclass(frozen=True, slots=True)
class AgentDispatch:
    """Dispatch message from Orchestrator to Agent."""
    agent_id: AgentID
    task: TaskSpec
    upstream_results: dict[str, ExecutionResult] = field(default_factory=dict)


# ── Node Manifest (Declarative Network Builder) ────────────────

@dataclass(frozen=True, slots=True)
class ConnectionSpec:
    from_node: str
    from_output: int = 0
    to_input: int = 0


@dataclass(frozen=True, slots=True)
class NodeSpec:
    type: str
    name: str
    parms: dict[str, Any] = field(default_factory=dict)
    connections: tuple[ConnectionSpec, ...] = ()
    vex_snippet: str | None = None


@dataclass(frozen=True, slots=True)
class NodeManifest:
    """Declarative network specification for atomic construction."""
    parent: str
    nodes: tuple[NodeSpec, ...] = ()

    def to_dict(self) -> dict:
        return {
            "parent": self.parent,
            "nodes": [
                {
                    "type": n.type,
                    "name": n.name,
                    "parms": n.parms,
                    "connections": [asdict(c) for c in n.connections],
                    **({"vex_snippet": n.vex_snippet} if n.vex_snippet else {})
                }
                for n in self.nodes
            ]
        }


# ── Graph Specification (DAG Assembly) ──────────────────────────

@dataclass(frozen=True, slots=True)
class GraphNodeSpec:
    """Node specification for graph assembly (uses local id for connections)."""
    id: str
    type: str
    name: str = ""
    parms: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GraphConnectionSpec:
    """Connection in a graph (references node ids, not paths)."""
    from_id: str
    to_id: str
    input: int = 0
    output: int = 0


@dataclass(frozen=True, slots=True)
class GraphSpec:
    """DAG specification for Solaris graph assembly."""
    parent: str = "/stage"
    nodes: tuple[GraphNodeSpec, ...] = ()
    connections: tuple[GraphConnectionSpec, ...] = ()
    display_node: str | None = None
    template: str | None = None


# ── Geometry Summary ────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class GeoSummary:
    """Token-efficient geometry summary. Target: <100 tokens."""
    geo_type: str
    point_count: int
    prim_count: int
    vertex_count: int
    point_attribs: dict[str, str]
    prim_attribs: dict[str, str]
    detail_attribs: dict[str, str]
    bounds: tuple[float, float, float, float, float, float]
    groups: tuple[str, ...]
    has_normals: bool
    has_uvs: bool
    memory_mb: float

    def token_estimate(self) -> int:
        """Estimate token count of this summary."""
        return len(json.dumps(asdict(self))) // 4


# ── MOE Routing ─────────────────────────────────────────────────

class DomainSignal(str, Enum):
    __slots__ = ()
    ASYNC = "async"
    ERROR_HANDLING = "error_handling"
    GEOMETRY = "geometry"
    USD = "usd"
    PDG = "pdg"
    MCP = "mcp"
    VEX = "vex"
    RENDERING = "rendering"
    TESTING = "testing"
    APEX = "apex"
    COPS = "cops"
    MATERIALX = "materialx"


class TaskType(str, Enum):
    __slots__ = ()
    ARCHITECTURE = "architecture"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    GENERATION = "generation"
    ORCHESTRATION = "orchestration"
    INTEGRATION = "integration"


class Complexity(str, Enum):
    __slots__ = ()
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
    RESEARCH = "research_grade"


class Urgency(str, Enum):
    __slots__ = ()
    BLOCKING = "blocking"
    NORMAL = "normal"
    EXPLORATORY = "exploratory"


@dataclass(frozen=True, slots=True)
class RoutingFeatures:
    """Feature vector for MOE sparse routing."""
    task_type: TaskType
    complexity: Complexity
    domain_signals: tuple[DomainSignal, ...]
    urgency: Urgency

    def fingerprint(self) -> Fingerprint:
        """Unique fingerprint for fast-path matching."""
        domains = "+".join(sorted(d.value for d in self.domain_signals))
        return f"{self.task_type.value}|{self.complexity.value}|{domains}|{self.urgency.value}"


# ── PDG Chain Specification ─────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ChainStep:
    id: str
    agent: AgentID
    prompt: str
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChainSpec:
    name: str
    steps: tuple[ChainStep, ...] = ()
    parallel_groups: tuple[tuple[str, ...], ...] = ()


# ── File Ownership Registry ─────────────────────────────────────

FILE_OWNERSHIP: dict[str, AgentID] = {
    "src/server/": AgentID.SUBSTRATE,
    "src/transport/": AgentID.SUBSTRATE,
    "src/mcp/": AgentID.SUBSTRATE,
    "src/execution/": AgentID.BRAINSTEM,
    "src/recovery/": AgentID.BRAINSTEM,
    "src/compiler/": AgentID.BRAINSTEM,
    "src/observation/": AgentID.OBSERVER,
    "src/introspection/": AgentID.OBSERVER,
    "src/viewport/": AgentID.OBSERVER,
    "src/houdini/": AgentID.HANDS,
    "src/solaris/": AgentID.HANDS,
    "src/apex/": AgentID.HANDS,
    "src/cops/": AgentID.HANDS,
    "src/pdg/": AgentID.CONDUCTOR,
    "src/memory/": AgentID.CONDUCTOR,
    "src/batch/": AgentID.CONDUCTOR,
    "src/api/": AgentID.INTEGRATOR,
    "src/types/": AgentID.INTEGRATOR,
    "tests/": AgentID.INTEGRATOR,
    "shared/": AgentID.INTEGRATOR,
}


# ── Public API ──────────────────────────────────────────────────

__all__ = [
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
]
