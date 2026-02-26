"""
SYNAPSE Agent Team — Shared Type Definitions
All agents import from this module. INTEGRATOR owns write access.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal
from enum import Enum
import json


# ── Agent Identity ──────────────────────────────────────────────

class AgentID(str, Enum):
    SUBSTRATE = "SUBSTRATE"
    BRAINSTEM = "BRAINSTEM"
    OBSERVER = "OBSERVER"
    HANDS = "HANDS"
    CONDUCTOR = "CONDUCTOR"
    INTEGRATOR = "INTEGRATOR"


# ── Task Status ─────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


# ── Execution Results ───────────────────────────────────────────

@dataclass
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
    def ok(cls, result: Any = None, agent_id: AgentID | None = None) -> ExecutionResult:
        return cls(success=True, result=result, agent_id=agent_id)

    @classmethod
    def fail(cls, error: str, error_type: str = "unknown",
             retry_hint: str | None = None,
             agent_id: AgentID | None = None) -> ExecutionResult:
        return cls(success=False, error=error, error_type=error_type,
                   retry_hint=retry_hint, agent_id=agent_id)


# ── Task Specification ──────────────────────────────────────────

@dataclass
class TaskSpec:
    """Task specification for inter-agent dispatch."""
    task_id: str
    summary: str
    primary_agent: AgentID
    advisory_agent: AgentID | None = None
    context: dict = field(default_factory=dict)
    constraints: dict = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    deliverable_format: str = "ExecutionResult"


@dataclass
class AgentDispatch:
    """Dispatch message from Orchestrator to Agent."""
    agent_id: AgentID
    task: TaskSpec
    upstream_results: dict[str, ExecutionResult] = field(default_factory=dict)


# ── Node Manifest (Declarative Network Builder) ────────────────

@dataclass
class ConnectionSpec:
    from_node: str
    from_output: int = 0
    to_input: int = 0


@dataclass
class NodeSpec:
    type: str
    name: str
    parms: dict[str, Any] = field(default_factory=dict)
    connections: list[ConnectionSpec] = field(default_factory=list)
    vex_snippet: str | None = None


@dataclass
class NodeManifest:
    """Declarative network specification for atomic construction."""
    parent: str
    nodes: list[NodeSpec] = field(default_factory=list)

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


# ── Geometry Summary ────────────────────────────────────────────

@dataclass
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
    groups: list[str]
    has_normals: bool
    has_uvs: bool
    memory_mb: float

    def token_estimate(self) -> int:
        """Estimate token count of this summary."""
        return len(json.dumps(asdict(self))) // 4


# ── MOE Routing ─────────────────────────────────────────────────

class DomainSignal(str, Enum):
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
    ARCHITECTURE = "architecture"
    EXECUTION = "execution"
    OBSERVATION = "observation"
    GENERATION = "generation"
    ORCHESTRATION = "orchestration"
    INTEGRATION = "integration"


class Complexity(str, Enum):
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"
    RESEARCH = "research_grade"


class Urgency(str, Enum):
    BLOCKING = "blocking"
    NORMAL = "normal"
    EXPLORATORY = "exploratory"


@dataclass
class RoutingFeatures:
    """Feature vector for MOE sparse routing."""
    task_type: TaskType
    complexity: Complexity
    domain_signals: list[DomainSignal]
    urgency: Urgency

    def fingerprint(self) -> str:
        """Unique fingerprint for fast-path matching."""
        domains = "+".join(sorted(d.value for d in self.domain_signals))
        return f"{self.task_type.value}|{self.complexity.value}|{domains}|{self.urgency.value}"


# ── PDG Chain Specification ─────────────────────────────────────

@dataclass
class ChainStep:
    id: str
    agent: AgentID
    prompt: str
    depends_on: list[str] = field(default_factory=list)


@dataclass
class ChainSpec:
    name: str
    steps: list[ChainStep] = field(default_factory=list)
    parallel_groups: list[list[str]] = field(default_factory=list)


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
