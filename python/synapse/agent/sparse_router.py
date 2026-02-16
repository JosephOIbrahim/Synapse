"""
Sparse Tool Router (v8-DSA)

Lightweight signal indexer for MCP tool pre-scoring, adapted from
DeepSeek-V3.2's Sparse Attention pattern (arxiv:2512.02556).

Instead of evaluating all 61 tools for every request, the indexer
scores a cheap 4-feature signal vector against tool signatures and
returns only the top-k candidates. This reduces routing latency
for the common case while preserving accuracy.

Phase 1: Standalone module with no integration wiring. The indexer
can be called independently for benchmarking and testing.
"""

import json
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from ..core.determinism import round_float


# =============================================================================
# SIGNAL TYPES
# =============================================================================

class Domain(Enum):
    """Tool domain classification."""
    SCENE = "scene"
    LIGHTING = "lighting"
    MATERIAL = "material"
    RENDER = "render"
    MEMORY = "memory"
    TOPS = "tops"
    USD = "usd"
    GENERAL = "general"


class CostTier(Enum):
    """Relative cost of invoking a tool."""
    FREE = 0       # Reads, pings
    CHEAP = 1      # Parameter sets, node creation
    MODERATE = 2   # VEX/Python execution, viewport capture
    EXPENSIVE = 3  # Renders, wedges, batch operations


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class ToolSignature:
    """Immutable descriptor for a single MCP tool.

    Built once at startup from the tool registry, then used for
    fast signal matching during routing.
    """
    name: str
    domain: Domain
    keywords: FrozenSet[str]
    param_patterns: FrozenSet[str]  # Expected parameter names
    cost_tier: CostTier
    read_only: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.domain.value,
            "keywords": sorted(self.keywords),
            "param_patterns": sorted(self.param_patterns),
            "cost_tier": self.cost_tier.value,
            "read_only": self.read_only,
        }


@dataclass
class RouteCandidate:
    """A scored tool candidate from the indexer."""
    tool_name: str
    score: float
    match_signals: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "score": round_float(self.score, 4),
            "match_signals": {
                k: round_float(v, 4)
                for k, v in sorted(self.match_signals.items())
            },
        }


@dataclass
class SparseRouterConfig:
    """Configuration for the sparse tool indexer."""
    # How many candidates to return
    top_k: int = 3

    # Signal weights (must sum to ~1.0 for interpretability)
    keyword_weight: float = 0.4
    domain_weight: float = 0.3
    param_weight: float = 0.2
    recency_weight: float = 0.1

    # Recency boost: how many recent selections to track
    recency_window: int = 10

    # Calibration: run dense for first N calls to establish ground truth
    calibration_calls: int = 10

    # Mode: "dense" (evaluate all), "sparse" (top-k only)
    mode: str = "dense"


# =============================================================================
# SPARSE TOOL INDEXER
# =============================================================================

class SparseToolIndexer:
    """Pre-scores MCP tools against a query signal vector.

    Maintains a registry of tool signatures and scores incoming
    requests against them using keyword overlap, domain matching,
    parameter pattern matching, and recency boost.

    After calibration_calls dense evaluations, switches to sparse
    mode automatically (returning only top-k candidates).
    """

    def __init__(self, config: Optional[SparseRouterConfig] = None):
        self._config = config or SparseRouterConfig()
        self._signatures: Dict[str, ToolSignature] = {}
        self._recent_selections: deque = deque(
            maxlen=self._config.recency_window
        )
        self._call_count: int = 0
        self._calibration_hits: int = 0
        self._calibration_total: int = 0

    @property
    def config(self) -> SparseRouterConfig:
        return self._config

    @property
    def tool_count(self) -> int:
        return len(self._signatures)

    def register_tool(self, sig: ToolSignature) -> None:
        """Register a tool signature for indexing."""
        self._signatures[sig.name] = sig

    def register_tools(self, sigs: Sequence[ToolSignature]) -> None:
        """Register multiple tool signatures."""
        for sig in sigs:
            self._signatures[sig.name] = sig

    def index(
        self,
        query_keywords: Sequence[str],
        query_domain: Optional[Domain] = None,
        query_params: Optional[Sequence[str]] = None,
    ) -> List[RouteCandidate]:
        """Score all registered tools and return top-k candidates.

        Args:
            query_keywords: Words extracted from the user query.
            query_domain: Detected domain of the request (or None).
            query_params: Parameter names present in the request.

        Returns:
            List of RouteCandidate sorted by descending score,
            limited to top_k in sparse mode.
        """
        self._call_count += 1
        kw_set = frozenset(w.lower() for w in query_keywords)
        param_set = frozenset(p.lower() for p in (query_params or []))

        candidates: List[RouteCandidate] = []
        for sig in self._signatures.values():
            signals: Dict[str, float] = {}

            # Keyword overlap
            if kw_set and sig.keywords:
                overlap = len(kw_set & sig.keywords)
                signals["keyword"] = overlap / max(len(kw_set), 1)
            else:
                signals["keyword"] = 0.0

            # Domain match
            if query_domain is not None and sig.domain == query_domain:
                signals["domain"] = 1.0
            else:
                signals["domain"] = 0.0

            # Parameter pattern match
            if param_set and sig.param_patterns:
                p_overlap = len(param_set & sig.param_patterns)
                signals["param"] = p_overlap / max(len(param_set), 1)
            else:
                signals["param"] = 0.0

            # Recency boost
            if sig.name in self._recent_selections:
                signals["recency"] = 1.0
            else:
                signals["recency"] = 0.0

            # Weighted score
            score = (
                self._config.keyword_weight * signals["keyword"]
                + self._config.domain_weight * signals["domain"]
                + self._config.param_weight * signals["param"]
                + self._config.recency_weight * signals["recency"]
            )

            candidates.append(RouteCandidate(
                tool_name=sig.name,
                score=round_float(score, 6),
                match_signals=signals,
            ))

        # Deterministic sort: by score descending, then name ascending
        candidates.sort(key=lambda c: (-c.score, c.tool_name))

        # In sparse mode, truncate to top_k
        effective_mode = self._effective_mode()
        if effective_mode == "sparse":
            candidates = candidates[:self._config.top_k]

        return candidates

    def record_selection(self, tool_name: str, was_correct: bool = True) -> None:
        """Record that a tool was actually selected by the full router.

        Used for calibration accuracy tracking and recency boost.
        """
        self._recent_selections.appendleft(tool_name)
        if self._call_count <= self._config.calibration_calls:
            self._calibration_total += 1
            if was_correct:
                self._calibration_hits += 1

    def calibration_accuracy(self) -> Optional[float]:
        """Return calibration accuracy, or None if not enough data."""
        if self._calibration_total == 0:
            return None
        return round_float(
            self._calibration_hits / self._calibration_total, 4
        )

    def _effective_mode(self) -> str:
        """Determine whether to run dense or sparse."""
        if self._config.mode == "sparse":
            return "sparse"
        if self._config.mode == "dense":
            # Auto-switch after calibration period
            if self._call_count > self._config.calibration_calls:
                return "sparse"
            return "dense"
        return "dense"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize indexer state for diagnostics."""
        return {
            "tool_count": self.tool_count,
            "call_count": self._call_count,
            "mode": self._effective_mode(),
            "config_mode": self._config.mode,
            "calibration_accuracy": self.calibration_accuracy(),
            "recent_selections": list(self._recent_selections),
        }


# =============================================================================
# SIGNATURE BUILDER
# =============================================================================

# Domain detection by tool name prefix
_DOMAIN_PREFIXES: Dict[str, Domain] = {
    "tops_": Domain.TOPS,
    "render": Domain.RENDER,
    "capture_viewport": Domain.RENDER,
    "create_material": Domain.MATERIAL,
    "assign_material": Domain.MATERIAL,
    "read_material": Domain.MATERIAL,
}

# Keyword extraction from tool name (split on underscore)
def _extract_keywords(name: str) -> FrozenSet[str]:
    """Extract searchable keywords from a tool name."""
    parts = name.replace("houdini_", "").replace("synapse_", "").split("_")
    return frozenset(p.lower() for p in parts if len(p) > 1)


def _detect_domain(name: str, annotations: Optional[Dict[str, Any]] = None) -> Domain:
    """Detect domain from tool name and annotations."""
    for prefix, domain in sorted(_DOMAIN_PREFIXES.items()):
        if name.startswith(prefix):
            return domain

    # USD tools
    if "usd" in name or "stage" in name or "prim" in name:
        return Domain.USD

    # Memory tools
    if any(kw in name for kw in ("memory", "context", "search", "recall", "decide")):
        return Domain.MEMORY

    # Scene tools
    if any(kw in name for kw in ("node", "scene", "selection", "parm")):
        return Domain.SCENE

    # Lighting
    if "light" in name or "keyframe" in name:
        return Domain.LIGHTING

    return Domain.GENERAL


def _detect_cost(name: str, annotations: Optional[Dict[str, Any]] = None) -> CostTier:
    """Detect cost tier from tool name and annotations."""
    read_only = False
    if annotations:
        read_only = annotations.get("readOnlyHint", False)

    if read_only:
        return CostTier.FREE

    if any(kw in name for kw in ("render", "wedge", "batch", "sequence")):
        return CostTier.EXPENSIVE

    if any(kw in name for kw in ("execute", "capture", "inspect")):
        return CostTier.MODERATE

    if any(kw in name for kw in ("get_", "ping", "list", "info", "search", "recall")):
        return CostTier.FREE

    return CostTier.CHEAP


def build_signatures_from_registry(
    tools: Sequence[Dict[str, Any]],
) -> List[ToolSignature]:
    """Auto-generate ToolSignatures from MCP tool definitions.

    Args:
        tools: List of tool definition dicts, each with at minimum
               'name' and optionally 'inputSchema' and 'annotations'.

    Returns:
        List of ToolSignature instances ready for register_tools().
    """
    signatures: List[ToolSignature] = []
    for tool_def in tools:
        name = tool_def["name"]
        annotations = tool_def.get("annotations", {})
        schema = tool_def.get("inputSchema", {})

        # Extract parameter names from JSON Schema
        props = schema.get("properties", {})
        param_patterns = frozenset(p.lower() for p in props.keys())

        sig = ToolSignature(
            name=name,
            domain=_detect_domain(name, annotations),
            keywords=_extract_keywords(name),
            param_patterns=param_patterns,
            cost_tier=_detect_cost(name, annotations),
            read_only=annotations.get("readOnlyHint", False),
        )
        signatures.append(sig)

    return signatures
