"""
SYNAPSE Agent Team — MOE (Mixture of Experts) Router
Sparse routing: extract 4 features → top-K agents → dispatch.

Elegant Revision R5: Precise lexical boundary routing
  - re.search(r'\b...\b') replaces substring matching
  - 'usd' no longer matches 'paused', 'cop' no longer matches 'scope'
  - Urgency extraction uses word boundaries for accurate intent detection
"""

from __future__ import annotations
from dataclasses import dataclass, field
import re
from datetime import datetime
from shared.types import (
    AgentID, TaskType, Complexity, Urgency, DomainSignal,
    RoutingFeatures, TaskSpec, TaskStatus
)


# ── Routing Table ────────────────────────────────────────────────

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


# ── Fast Paths ───────────────────────────────────────────────────

FAST_PATHS: dict[str, tuple[AgentID, AgentID | None]] = {
    "architecture|moderate|async+mcp|normal":           (AgentID.SUBSTRATE, AgentID.INTEGRATOR),
    "execution|moderate|error_handling+vex|blocking":   (AgentID.BRAINSTEM, AgentID.SUBSTRATE),
    "observation|trivial|geometry|normal":              (AgentID.OBSERVER, None),
    "generation|moderate|materialx+usd|normal":         (AgentID.HANDS, AgentID.OBSERVER),
    "generation|complex|apex|normal":                   (AgentID.HANDS, AgentID.OBSERVER),
    "generation|complex|cops|normal":                   (AgentID.HANDS, AgentID.OBSERVER),
    "orchestration|complex|pdg+rendering|normal":       (AgentID.CONDUCTOR, AgentID.BRAINSTEM),
    "integration|moderate|testing|normal":              (AgentID.INTEGRATOR, None),
}


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
        self._dense_threshold = 10
        self._session_fast_paths: dict[str, tuple[AgentID, AgentID | None]] = {}

    def route(self, features: RoutingFeatures) -> RoutingDecision:
        self._call_count += 1
        fingerprint = features.fingerprint()

        # Fast paths after calibration
        if self._call_count > self._dense_threshold:
            if fingerprint in FAST_PATHS:
                primary, advisory = FAST_PATHS[fingerprint]
                return RoutingDecision(
                    primary=primary, advisory=advisory,
                    scores={primary: 1.0, **(({advisory: 0.8} if advisory else {}))},
                    method="fast_path", features=features
                )
            if fingerprint in self._session_fast_paths:
                primary, advisory = self._session_fast_paths[fingerprint]
                return RoutingDecision(
                    primary=primary, advisory=advisory,
                    scores={primary: 1.0, **(({advisory: 0.8} if advisory else {}))},
                    method="session_fast_path", features=features
                )

        # Full scoring
        scores = self._score_all_agents(features)
        sorted_agents = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        primary = sorted_agents[0][0]
        advisory = sorted_agents[1][0] if len(sorted_agents) > 1 and sorted_agents[1][1] > 0.3 else None

        return RoutingDecision(
            primary=primary, advisory=advisory,
            scores=scores, method="scored", features=features
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
            scores[max_agent] *= 1.2
        elif features.complexity == Complexity.RESEARCH:
            scores[AgentID.INTEGRATOR] = max(scores[AgentID.INTEGRATOR], 0.5)

        if features.urgency == Urgency.BLOCKING:
            scores[AgentID.BRAINSTEM] += 0.2

        return scores

    def learn_fast_path(self, fingerprint: str, primary: AgentID,
                         advisory: AgentID | None):
        self._session_fast_paths[fingerprint] = (primary, advisory)


# ── Domain & Task Type Keywords ──────────────────────────────────

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

    # Geometry
    "geometry": DomainSignal.GEOMETRY, "mesh": DomainSignal.GEOMETRY,
    "points": DomainSignal.GEOMETRY, "prims": DomainSignal.GEOMETRY,
    "introspect": DomainSignal.GEOMETRY, "inspect": DomainSignal.GEOMETRY,

    # USD / Solaris
    "usd": DomainSignal.USD, "solaris": DomainSignal.USD,
    "lop": DomainSignal.USD, "stage": DomainSignal.USD,
    "prim": DomainSignal.USD, "composition": DomainSignal.USD,
    "variant": DomainSignal.USD, "layer": DomainSignal.USD,

    # MaterialX
    "materialx": DomainSignal.MATERIALX, "mtlx": DomainSignal.MATERIALX,
    "shader": DomainSignal.MATERIALX, "material": DomainSignal.MATERIALX,

    # APEX
    "apex": DomainSignal.APEX, "rig": DomainSignal.APEX,
    "autorig": DomainSignal.APEX, "skeleton": DomainSignal.APEX,

    # Copernicus
    "copernicus": DomainSignal.COPS, "cop": DomainSignal.COPS,
    "gpu": DomainSignal.COPS, "compositing": DomainSignal.COPS,

    # Rendering
    "render": DomainSignal.RENDERING, "karma": DomainSignal.RENDERING,
    "wedge": DomainSignal.RENDERING, "lookdev": DomainSignal.RENDERING,

    # PDG
    "pdg": DomainSignal.PDG, "tops": DomainSignal.PDG,
    "farm": DomainSignal.PDG, "batch": DomainSignal.PDG,
    "pipeline": DomainSignal.PDG, "orchestrat": DomainSignal.PDG,

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


# ── R5: Feature Extraction with Word Boundaries ─────────────────

def extract_features(task_description: str) -> RoutingFeatures:
    """
    R5: Extract routing features using precise lexical boundaries.
    \b ensures exact word matching: 'usd' won't match 'paused',
    'cop' won't match 'scope', 'fix' won't match 'prefix'.
    """
    text = task_description.lower()

    # Domain signals — word boundary matching
    domain_signals = set()
    for keyword, signal in DOMAIN_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            domain_signals.add(signal)

    # Task type — first word-boundary match wins
    task_type = TaskType.GENERATION
    for keyword, tt in TASK_TYPE_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', text):
            task_type = tt
            break

    # Complexity heuristic (unchanged — works on counts)
    words = text.split()
    word_count = len(words)
    domain_count = len(domain_signals)
    if word_count < 10 and domain_count <= 1:
        complexity = Complexity.TRIVIAL
    elif word_count < 30 and domain_count <= 2:
        complexity = Complexity.MODERATE
    elif domain_count <= 3:
        complexity = Complexity.COMPLEX
    else:
        complexity = Complexity.RESEARCH

    # Urgency — word boundary matching with expanded vocabulary
    urgency = Urgency.NORMAL
    if re.search(r'\b(urgent|blocking|broken|crash|fix|halt|immediately)\b', text):
        urgency = Urgency.BLOCKING
    elif re.search(r'\b(explore|experiment|maybe|could|try)\b', text):
        urgency = Urgency.EXPLORATORY

    return RoutingFeatures(
        task_type=task_type,
        complexity=complexity,
        domain_signals=list(domain_signals) if domain_signals else [DomainSignal.GEOMETRY],
        urgency=urgency
    )


# ── Convenience ──────────────────────────────────────────────────

def route_task(description: str) -> RoutingDecision:
    """One-shot: extract features and route."""
    features = extract_features(description)
    router = MOERouter()
    return router.route(features)
