"""
FORGE Schemas — Core data structures for the self-improvement loop.

All structured data in FORGE flows through these types.
ScenarioResult is the primary input. CorpusEntry is the primary output.
CycleMetrics tracks convergence toward v25.0.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# =============================================================================
# Enums
# =============================================================================


class FailureCategory(Enum):
    """Classification taxonomy for scenario failures.
    
    Categories are grouped by fix destination:
    - AUTOMATED: fixes generated and applied without human review
    - HUMAN_REVIEW: queued in backlog for human decision
    - OBSERVE: logged for pattern detection only
    """

    # Knowledge gaps (automated fix: skill files, RAG, corpus)
    MISSING_CONVENTION = "missing_convention"
    MISSING_KNOWLEDGE = "missing_knowledge"
    HALLUCINATED_API = "hallucinated_api"

    # Architectural (human review: design decisions)
    WRONG_TARGET = "wrong_target"
    WRONG_ORDERING = "wrong_ordering"
    COMPOSITION_ERROR = "composition_error"

    # Safety (human review: safety-critical changes)
    MISSING_GUARDRAIL = "missing_guardrail"
    PARTIAL_EXECUTION = "partial_execution"

    # UX/Efficiency (human review: tool design)
    TOOL_GAP = "tool_gap"
    WORKFLOW_FRICTION = "workflow_friction"
    PARAMETER_CONFUSION = "parameter_confusion"

    # Performance (observe + human review if systemic)
    SLOW_OPERATION = "slow_operation"
    MEMORY_PRESSURE = "memory_pressure"

    @property
    def fix_destination(self) -> str:
        """Where fixes for this category go."""
        automated = {
            self.MISSING_CONVENTION,
            self.MISSING_KNOWLEDGE,
            self.HALLUCINATED_API,
            self.WRONG_TARGET,
            self.PARAMETER_CONFUSION,
            self.WRONG_ORDERING,
        }
        observe = {self.PARTIAL_EXECUTION, self.MEMORY_PRESSURE}
        if self in automated:
            return "automated"
        if self in observe:
            return "observe"
        return "human_review"


class AgentRole(Enum):
    """The five FORGE agent roles."""

    SUPERVISOR = "SUPERVISOR"
    RESEARCHER = "RESEARCHER"
    ARCHITECT = "ARCHITECT"
    ENGINEER = "ENGINEER"
    PRODUCER = "PRODUCER"


class ScenarioDomain(Enum):
    """VFX domain categories for scenario routing."""

    LIGHTING = "lighting"
    FX = "fx"
    LOOKDEV = "lookdev"
    LAYOUT = "layout"
    PIPELINE = "pipeline"
    RENDER = "render"
    GENERAL = "general"


class ScenarioComplexity(Enum):
    """Scenario complexity tiers."""

    SINGLE_TOOL = "single_tool"  # Tier 1
    WORKFLOW = "workflow"  # Tier 2
    CROSS_DEPARTMENT = "cross_department"  # Tier 3
    PRODUCTION = "production"  # Tier 4


class ScenarioFocus(Enum):
    """What aspect the scenario primarily tests."""

    QUALITY = "quality"
    RELIABILITY = "reliability"
    PERFORMANCE = "performance"
    COVERAGE = "coverage"
    ARCHITECTURE = "architecture"


class CorpusStage(Enum):
    """Pokémon evolution stages for corpus entries."""

    OBSERVATION = "observation"  # Raw, single-source
    PATTERN = "pattern"  # Validated across multiple scenarios
    RULE = "rule"  # Crystallized into SYNAPSE knowledge


# =============================================================================
# Core Data Structures
# =============================================================================


@dataclass
class ToolCall:
    """Record of a single MCP tool invocation."""

    tool: str
    params: dict[str, Any]
    result: str  # "success" | "failure" | "unexpected" | "timeout"
    elapsed_ms: int = 0
    error_message: str | None = None
    notes: str = ""
    scene_state_after: str = ""


@dataclass
class ScenarioDefinition:
    """A scenario to be executed by agents."""

    id: str
    title: str
    description: str
    tier: int  # 1-4
    domain: ScenarioDomain
    complexity: ScenarioComplexity
    focus: ScenarioFocus
    tools_needed: list[str]
    steps: list[str]  # Human-readable step descriptions
    expected_outcome: str
    estimated_tool_calls: int  # For friction ratio calculation
    tags: list[str] = field(default_factory=list)
    prerequisite_scenarios: list[str] = field(default_factory=list)
    generated_by: str = "human"  # "human" | "researcher" | "improvement_engine"


@dataclass
class ScenarioResult:
    """The primary output of an agent running a scenario.
    
    This is the atomic unit of data that feeds the improvement engine.
    Every agent produces one of these per scenario execution.
    """

    # Identity
    cycle: int
    agent: AgentRole
    scenario_id: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Execution
    tool_calls: list[ToolCall] = field(default_factory=list)
    success: bool = False
    failure_point: str | None = None
    failure_category: FailureCategory | None = None
    error_message: str | None = None

    # Recovery
    workaround_found: bool = False
    workaround_description: str | None = None

    # Qualitative
    friction_notes: list[str] = field(default_factory=list)
    missing_tools: list[str] = field(default_factory=list)

    # Metrics
    total_elapsed_ms: int = 0
    tool_calls_count: int = 0
    estimated_optimal_calls: int = 0

    # Agent-specific payload (typed per agent role)
    agent_report: dict[str, Any] = field(default_factory=dict)

    # Corpus contribution
    corpus_contribution: str = ""  # One-sentence knowledge nugget

    @property
    def friction_ratio(self) -> float:
        """Actual vs optimal tool calls. 1.0 = perfect."""
        if self.estimated_optimal_calls == 0:
            return 0.0
        return self.tool_calls_count / self.estimated_optimal_calls

    def to_dict(self) -> dict:
        """Serialize for JSON storage."""
        d = asdict(self)
        if self.failure_category:
            d["failure_category"] = self.failure_category.value
        d["agent"] = self.agent.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ScenarioResult:
        """Deserialize from JSON."""
        if data.get("failure_category"):
            data["failure_category"] = FailureCategory(data["failure_category"])
        data["agent"] = AgentRole(data["agent"])
        # Reconstruct ToolCall objects
        if data.get("tool_calls"):
            data["tool_calls"] = [
                ToolCall(**tc) if isinstance(tc, dict) else tc
                for tc in data["tool_calls"]
            ]
        return cls(**data)


@dataclass
class CorpusEntry:
    """A unit of institutional knowledge in the FORGE corpus.
    
    Evolves through stages: observation → pattern → rule.
    """

    # Identity
    id: str
    created_cycle: int
    created_by: AgentRole
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Knowledge
    stage: CorpusStage = CorpusStage.OBSERVATION
    category: str = ""  # Free-form domain tag
    pattern: str = ""  # The reusable insight
    context: str = ""  # When this applies
    domain: ScenarioDomain = ScenarioDomain.GENERAL

    # Confidence tracking
    confidence: float = 0.1
    validation_count: int = 0
    recurrence_count: int = 1

    # Lineage
    derived_from: list[str] = field(default_factory=list)  # Scenario IDs
    validated_by: list[str] = field(default_factory=list)  # Scenario IDs
    supersedes: str | None = None  # Earlier entry this replaces

    # Evolution
    promoted_at: str | None = None  # When stage changed
    promoted_to_file: str | None = None  # Skill file / CLAUDE.md path

    @property
    def should_promote(self) -> bool:
        """Check if this entry should evolve to the next stage."""
        if self.stage == CorpusStage.OBSERVATION:
            return self.validation_count >= 3 and self.confidence >= 0.3
        if self.stage == CorpusStage.PATTERN:
            return self.confidence >= 0.7 and self.recurrence_count >= 5
        return False  # Rules don't promote further

    @property
    def content_hash(self) -> str:
        """SHA-256 of the knowledge content for dedup."""
        content = f"{self.category}:{self.pattern}:{self.context}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def validate(self, scenario_id: str) -> None:
        """Record a validation from a scenario."""
        if scenario_id not in self.validated_by:
            self.validated_by.append(scenario_id)
            self.validation_count += 1
            # Confidence grows with validation, diminishing returns
            self.confidence = min(1.0, self.confidence + 0.1 * (1 - self.confidence))

    def record_recurrence(self, scenario_id: str) -> None:
        """Record another occurrence of this pattern."""
        if scenario_id not in self.derived_from:
            self.derived_from.append(scenario_id)
            self.recurrence_count += 1

    def promote(self) -> CorpusStage | None:
        """Promote to next stage if criteria met. Returns new stage or None."""
        if not self.should_promote:
            return None
        if self.stage == CorpusStage.OBSERVATION:
            self.stage = CorpusStage.PATTERN
            self.promoted_at = datetime.utcnow().isoformat()
            return CorpusStage.PATTERN
        if self.stage == CorpusStage.PATTERN:
            self.stage = CorpusStage.RULE
            self.promoted_at = datetime.utcnow().isoformat()
            return CorpusStage.RULE
        return None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stage"] = self.stage.value
        d["created_by"] = self.created_by.value
        d["domain"] = self.domain.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> CorpusEntry:
        data["stage"] = CorpusStage(data["stage"])
        data["created_by"] = AgentRole(data["created_by"])
        data["domain"] = ScenarioDomain(data["domain"])
        return cls(**data)


@dataclass
class CycleMetrics:
    """Aggregate metrics for one improvement cycle.
    
    This is the heartbeat of the FORGE system.
    improvement_delta is the north star — when it flatlines, 
    automated fixes are exhausted and human architecture review is needed.
    """

    cycle_number: int
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Execution
    scenarios_run: int = 0
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    agents_active: list[str] = field(default_factory=list)
    tier: int = 1
    domains_tested: list[str] = field(default_factory=list)

    # Pass rate
    @property
    def pass_rate(self) -> float:
        if self.scenarios_run == 0:
            return 0.0
        return self.scenarios_passed / self.scenarios_run

    # Failures
    failure_categories: dict[str, int] = field(default_factory=dict)
    top_failure: str = ""
    top_failure_count: int = 0

    # Fixes
    fixes_generated: int = 0
    fixes_applied: int = 0
    fixes_validated: int = 0
    fixes_failed: int = 0
    fixes_queued_human: int = 0

    # Corpus
    corpus_entries_added: int = 0
    corpus_promotions: int = 0
    total_corpus_entries: int = 0

    # Efficiency
    avg_friction_ratio: float = 0.0
    total_elapsed_ms: int = 0

    # Convergence
    improvement_delta: float | None = None  # Change from last cycle
    regression_count: int = 0
    new_tool_gaps: list[str] = field(default_factory=list)
    new_scenarios_proposed: int = 0

    # Stop conditions
    @property
    def should_stop(self) -> bool:
        """Check if autonomous mode should halt."""
        if self.regression_count > 3:
            return True
        return False

    @property
    def should_tier_up(self) -> bool:
        """Check if scenario complexity should increase."""
        return self.pass_rate > 0.90 and self.tier < 4

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pass_rate"] = self.pass_rate
        return d


@dataclass
class BacklogItem:
    """An item queued for human review (Layer 3)."""

    id: str
    created_cycle: int
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    category: str = ""  # FailureCategory value
    title: str = ""
    description: str = ""
    evidence: list[str] = field(default_factory=list)  # Scenario IDs
    proposed_fix: str = ""
    priority: str = "medium"  # low | medium | high | critical
    status: str = "open"  # open | reviewed | accepted | rejected
    human_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentAssignment:
    """MoE router output: which agent gets which scenario."""

    agent: AgentRole
    scenario: ScenarioDefinition
    role_in_scenario: str  # "primary" | "secondary" | "observer"
    corpus_context: list[CorpusEntry] = field(default_factory=list)
    notes: str = ""


# =============================================================================
# Serialization Helpers
# =============================================================================


def save_json(data: Any, path: Path) -> None:
    """Atomic JSON write with SHA-256 manifest tracking."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, indent=2, default=str)
    path.write_text(content, encoding="utf-8")


def load_json(path: Path, default: Any = None) -> Any:
    """Safe JSON load with fallback."""
    if not path.exists():
        return default if default is not None else {}
    return json.loads(path.read_text(encoding="utf-8"))
