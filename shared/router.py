"""
SYNAPSE Agent Team -- MOE (Mixture of Experts) Router
Sparse routing: extract 4 features -> top-K agents -> dispatch.

Revisions:
  R5  -- Precise lexical boundary routing (\b word boundaries)
  R11 -- Module-level singleton for route_task() so calibration / fast paths
         are not reset on every call
  R12 -- Internal auto-promotion: fingerprints seen FAST_PATH_PROMOTION_THRESHOLD
         times are promoted to session fast paths from inside route()
  R13 -- Score-based task type extraction (no insertion-order dependency)
  R14 -- Complexity classification by domain count + COMPLEX_SOLO_DOMAINS;
         word count of an LLM-rewritten prompt no longer drives complexity
  R15 -- Relative advisory threshold via ADVISORY_GAP_RATIO (gap-aware top-K)
  R16 -- CONSTANTS_HASH stamping: session fast paths invalidated on
         constants drift; loud failure rather than silent miss
  R17 -- Empty domain_signals tuple instead of GEOMETRY fallback (no
         silent OBSERVER/HANDS bias on keyword-less prompts)
"""

from __future__ import annotations

__all__ = [
    "MOERouter", "RoutingDecision",
    "extract_features", "route_task",
    "get_default_router", "reset_default_router",
]

from dataclasses import dataclass, field
import re
from datetime import datetime
from shared.types import (
    AgentID, TaskType, Complexity, Urgency, DomainSignal,
    RoutingFeatures, TaskSpec, TaskStatus
)
from shared.constants import (
    ADVISORY_SCORE_THRESHOLD,
    ADVISORY_GAP_RATIO,
    BLOCKING_URGENCY_BOOST,
    COMPLEX_SCORE_MULTIPLIER,
    COMPLEX_SOLO_DOMAINS,
    CONSTANTS_HASH,
    DOMAIN_AFFINITY,
    DOMAIN_KEYWORDS,
    FAST_PATHS,
    FAST_PATH_PROMOTION_THRESHOLD,
    RESEARCH_INTEGRATOR_FLOOR,
    ROUTER_CALIBRATION_PERIOD,
    TASK_TYPE_BOOST,
    TASK_TYPE_KEYWORDS,
    URGENCY_BLOCKING_PATTERN,
    URGENCY_EXPLORATORY_PATTERN,
)


# ── Router ───────────────────────────────────────────────────────

@dataclass
class RoutingDecision:
    primary: AgentID
    advisory: AgentID | None
    scores: dict[AgentID, float]
    method: str
    features: RoutingFeatures


class MOERouter:
    """Sparse Mixture-of-Experts router for agent dispatch."""

    def __init__(self, k: int = 2):
        self.k = k
        self._call_count = 0
        self._dense_threshold = ROUTER_CALIBRATION_PERIOD
        # R16: stamp constants hash so session fast paths are invalidated
        # if the keyword tables drift between hot reloads.
        self._constants_hash = CONSTANTS_HASH
        # R12: fingerprint frequency counter feeds auto-promotion.
        self._fingerprint_counts: dict[str, int] = {}
        # Session fast paths stored as {fingerprint: (primary, advisory, hash)}
        self._session_fast_paths: dict[str, tuple[AgentID, AgentID | None, str]] = {}

    def route(self, features: RoutingFeatures) -> RoutingDecision:
        """Route a task to primary + optional advisory agent.

        Decision hierarchy (first match wins):
          1. Hand-tuned FAST_PATHS (after calibration period)
          2. Session-learned fast paths (R12 auto-promoted, R16 hash-validated)
          3. Full scoring across all 6 agents

        Advisory selection (R15): second-highest agent must clear both an
        absolute score floor (ADVISORY_SCORE_THRESHOLD) and a relative gap
        ratio (ADVISORY_GAP_RATIO * primary_score) to be included.

        Auto-promotion (R12): fingerprints hitting FAST_PATH_PROMOTION_THRESHOLD
        are promoted to session fast paths, stamped with CONSTANTS_HASH so
        they auto-invalidate if the keyword tables change.

        Args:
            features: 4-dimension feature vector (task_type, complexity,
                      domain_signals, urgency) with .fingerprint() for
                      fast-path lookup.

        Returns:
            RoutingDecision with primary agent, optional advisory, scores,
            method ('fast_path', 'session_fast_path', or 'scored'), and
            the input features for audit.
        """
        self._call_count += 1
        fingerprint = features.fingerprint()
        self._fingerprint_counts[fingerprint] = (
            self._fingerprint_counts.get(fingerprint, 0) + 1
        )

        # Fast paths after calibration
        if self._call_count > self._dense_threshold:
            if fingerprint in FAST_PATHS:
                primary, advisory = FAST_PATHS[fingerprint]
                return self._fast_path_decision(
                    primary, advisory, features, "fast_path"
                )
            entry = self._session_fast_paths.get(fingerprint)
            # R16: skip stale entries from a different constants snapshot
            if entry is not None and entry[2] == self._constants_hash:
                primary, advisory, _ = entry
                return self._fast_path_decision(
                    primary, advisory, features, "session_fast_path"
                )

        # Full scoring
        scores = self._score_all_agents(features)
        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_agent, primary_score = sorted_agents[0]

        # R15: advisory must clear BOTH the absolute floor AND the relative gap
        advisory: AgentID | None = None
        if len(sorted_agents) > 1:
            adv_agent, adv_score = sorted_agents[1]
            min_relative = ADVISORY_GAP_RATIO * primary_score if primary_score > 0 else 0
            if adv_score >= ADVISORY_SCORE_THRESHOLD and adv_score >= min_relative:
                advisory = adv_agent

        decision = RoutingDecision(
            primary=primary_agent, advisory=advisory,
            scores=scores, method="scored", features=features
        )

        # R12: auto-promote frequent fingerprints from inside route().
        # Cheap O(1) check; promotion happens on the call that crosses the
        # threshold so the next request hits the fast path immediately.
        if (
            self._fingerprint_counts[fingerprint] >= FAST_PATH_PROMOTION_THRESHOLD
            and fingerprint not in FAST_PATHS
            and fingerprint not in self._session_fast_paths
        ):
            self._session_fast_paths[fingerprint] = (
                primary_agent, advisory, self._constants_hash
            )

        return decision

    def _fast_path_decision(
        self,
        primary: AgentID,
        advisory: AgentID | None,
        features: RoutingFeatures,
        method: str,
    ) -> RoutingDecision:
        scores = {primary: 1.0}
        if advisory is not None:
            scores[advisory] = 0.8
        return RoutingDecision(
            primary=primary, advisory=advisory, scores=scores,
            method=method, features=features,
        )

    def _score_all_agents(self, features: RoutingFeatures) -> dict[AgentID, float]:
        scores: dict[AgentID, float] = {agent: 0.0 for agent in AgentID}

        for signal in features.domain_signals:
            affinities = DOMAIN_AFFINITY.get(signal, {})
            for agent, affinity in affinities.items():
                scores[agent] += affinity

        boosts = TASK_TYPE_BOOST.get(features.task_type, {})
        for agent, boost in boosts.items():
            scores[agent] += boost

        if features.complexity == Complexity.COMPLEX:
            max_agent = max(scores, key=scores.get)
            scores[max_agent] *= COMPLEX_SCORE_MULTIPLIER
        elif features.complexity == Complexity.RESEARCH:
            scores[AgentID.INTEGRATOR] = max(
                scores[AgentID.INTEGRATOR], RESEARCH_INTEGRATOR_FLOOR
            )

        if features.urgency == Urgency.BLOCKING:
            scores[AgentID.BRAINSTEM] += BLOCKING_URGENCY_BOOST

        return scores

    def learn_fast_path(
        self, fingerprint: str, primary: AgentID, advisory: AgentID | None
    ) -> None:
        """External fast-path injection (used by panel/RoutingLog)."""
        self._session_fast_paths[fingerprint] = (
            primary, advisory, self._constants_hash
        )

    # Pass 8: public accessor so the ConductorAdvisor can read fingerprint
    # frequency without poking private state. Returns a copy — caller cannot
    # mutate the router's internal counter.
    def fingerprint_counts(self) -> dict[str, int]:
        """Return a snapshot of fingerprint → call-count mapping."""
        return dict(self._fingerprint_counts)


# ── R13 / R14 / R17: Feature Extraction ─────────────────────────

def _classify_complexity(
    domain_signals: tuple[DomainSignal, ...], task_type: TaskType
) -> Complexity:
    """R14: Domain-driven complexity. Word count is no longer consulted.

    Rules (validated against FAST_PATHS):
      - 4+ domains                          -> RESEARCH
      - any solo-complex domain (apex/cops) -> COMPLEX
      - ORCHESTRATION + 2+ domains          -> COMPLEX
      - 2-3 domains                         -> MODERATE
      - 1 domain + OBSERVATION              -> TRIVIAL
      - 1 domain                            -> MODERATE
      - 0 domains                           -> TRIVIAL
    """
    n = len(domain_signals)
    if n >= 4:
        return Complexity.RESEARCH
    if any(d in COMPLEX_SOLO_DOMAINS for d in domain_signals):
        return Complexity.COMPLEX
    if task_type == TaskType.ORCHESTRATION and n >= 2:
        return Complexity.COMPLEX
    if n >= 2:
        return Complexity.MODERATE
    if n == 1:
        return Complexity.TRIVIAL if task_type == TaskType.OBSERVATION else Complexity.MODERATE
    return Complexity.TRIVIAL


def _extract_task_type(text: str) -> TaskType:
    """R13: Score every matched keyword. Most-matched task type wins.
    Tiebreaker is alphabetical task type name -> deterministic and
    independent of TASK_TYPE_KEYWORDS dict insertion order.
    """
    scores: dict[TaskType, int] = {}
    for keyword, tt in TASK_TYPE_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            scores[tt] = scores.get(tt, 0) + 1
    if not scores:
        return TaskType.GENERATION
    # max by (count, -alphabetical) — deterministic
    return max(scores.items(), key=lambda kv: (kv[1], -ord(kv[0].value[0])))[0]


def extract_features(task_description: str) -> RoutingFeatures:
    """Extract routing features. R5 word boundaries + R13/R14/R17."""
    text = task_description.lower()

    # Domain signals -- word boundary matching (R5)
    domain_signals: set[DomainSignal] = set()
    for keyword, signal in DOMAIN_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            domain_signals.add(signal)

    task_type = _extract_task_type(text)

    # R17: empty tuple instead of GEOMETRY fallback. _score_all_agents handles
    # empty domain_signals correctly — no agent gets a domain affinity boost,
    # routing falls through to task-type boosts only. No silent OBSERVER bias.
    domain_tuple = tuple(domain_signals)

    complexity = _classify_complexity(domain_tuple, task_type)

    # Urgency -- word boundary matching with expanded vocabulary
    urgency = Urgency.NORMAL
    if re.search(URGENCY_BLOCKING_PATTERN, text):
        urgency = Urgency.BLOCKING
    elif re.search(URGENCY_EXPLORATORY_PATTERN, text):
        urgency = Urgency.EXPLORATORY

    return RoutingFeatures(
        task_type=task_type,
        complexity=complexity,
        domain_signals=domain_tuple,
        urgency=urgency,
    )


# ── Convenience ──────────────────────────────────────────────────

# R11: Module-level singleton. Previously route_task() constructed a fresh
# MOERouter on every call, which reset _call_count and made the entire
# fast-path mechanism unreachable. Callers wanting an isolated router can
# still construct MOERouter() directly.
_DEFAULT_ROUTER: MOERouter | None = None


def get_default_router() -> MOERouter:
    global _DEFAULT_ROUTER
    if _DEFAULT_ROUTER is None:
        _DEFAULT_ROUTER = MOERouter()
    return _DEFAULT_ROUTER


def reset_default_router() -> None:
    """Test/REPL helper — clear the singleton state."""
    global _DEFAULT_ROUTER
    _DEFAULT_ROUTER = None


def route_task(description: str) -> RoutingDecision:
    """One-shot: extract features and route via the module-level singleton."""
    features = extract_features(description)
    return get_default_router().route(features)
