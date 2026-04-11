"""
SYNAPSE Conductor Advisor — the read side of the self-observability loop.

Closes the recursive loop sketched across pass 1–5 of the substrate review.
The substrate writes telemetry; this module reads it and recommends tuning.

Data sources (all shipped in earlier passes):
  - LosslessExecutionBridge.operation_stats() — pass 4 (B1/B2/B3)
  - EvolutionIntegrity.failures with content-drift detail — pass 5 (E5)
  - MOERouter._fingerprint_counts via RoutingLog — pass 3 (R12)
  - constants.FAST_PATHS / FAST_PATH_PROMOTION_THRESHOLD — pass 3 (R11/R12)

Design constraints (from CLAUDE.md):
  - Recommendations are NEVER applied automatically. Each Recommendation is
    a structured proposal that the artist/orchestrator may approve. The
    advisor is read-only by construction — it has no write access to
    constants, no ability to mutate router state, no side effects.
  - Severity is informational, not actionable on its own. Even 'critical'
    recommendations require artist consent through the bridge gate system.
  - The advisor mines clusters, not single events. A one-off failure is
    noise; a pattern of three is signal.

This is the CONDUCTOR-owned consumer that the OBSERVER pillar depends on.
SUBSTRATE wrote the data, the bridge exposed it, evolution surfaced its
failure modes — now CONDUCTOR interprets it for action.
"""

from __future__ import annotations

import json
import threading
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from shared.constants import (
    FAST_PATHS,
    FAST_PATH_PROMOTION_THRESHOLD,
)
from shared.evolution import EvolutionIntegrity


# ── Recommendation Schema ────────────────────────────────────────


# Severity levels — purely informational. Decision authority lives with the
# artist via the bridge gate system.
SEVERITY_INFO: str = "info"
SEVERITY_WARN: str = "warn"
SEVERITY_CRITICAL: str = "critical"

# Recommendation kinds
KIND_AGENT_HEALTH: str = "agent_health"
KIND_EVOLUTION_WRITER_FIX: str = "evolution_writer_fix"
KIND_ROUTER_PROMOTE: str = "router_promote"
KIND_TRIGGER_TUNE: str = "trigger_tune"
KIND_REPEATED_RECOMMENDATION: str = "repeated_recommendation"  # pass 8: meta-recursion


@dataclass(frozen=True, slots=True)
class Recommendation:
    """Structured tuning proposal. Read-only — never auto-applied."""

    kind: str
    target: str
    rationale: str
    confidence: float
    severity: str = SEVERITY_INFO
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "rationale": self.rationale,
            "confidence": round(self.confidence, 3),
            "severity": self.severity,
            "evidence": self.evidence,
        }


# ── Conductor Advisor ────────────────────────────────────────────


class ConductorAdvisor:
    """Mines runtime telemetry to recommend substrate tuning."""

    #: Below this success rate the advisor flags an agent for review.
    LOW_SUCCESS_RATE: float = 0.85

    #: Minimum operation count before any per-agent or per-bridge verdict
    #: is statistically meaningful. Below this, we stay silent.
    MIN_OPS_FOR_VERDICT: int = 10

    #: How many evolution failures of the same category before we flag the
    #: companion writer/parser as the suspected cause. Less than this is
    #: treated as noise (single content edits, transient issues).
    DRIFT_FIELD_CLUSTER_THRESHOLD: int = 3

    #: Pass 8 — meta-recursion. If the same (kind, target) pair appears in
    #: history this many times, the underlying issue has not been addressed
    #: and we escalate the recommendation to remind the artist.
    REPEATED_RECOMMENDATION_THRESHOLD: int = 5

    def analyze(
        self,
        bridge_stats: dict[str, Any] | None = None,
        evolution_failures: list[EvolutionIntegrity] | None = None,
        routing_fingerprints: dict[str, int] | None = None,
    ) -> list[Recommendation]:
        """Run all analyzers and return the merged recommendation set.

        Each input is optional — pass only the data you have. The advisor
        runs each analyzer independently and tolerates missing sources.
        """
        recs: list[Recommendation] = []
        recs.extend(self._analyze_bridge_health(bridge_stats or {}))
        recs.extend(self._analyze_evolution_drift(evolution_failures or []))
        recs.extend(self._analyze_routing_promotions(routing_fingerprints or {}))
        return recs

    # ── Analyzers ────────────────────────────────────────────────

    def _analyze_bridge_health(
        self, stats: dict[str, Any]
    ) -> list[Recommendation]:
        recs: list[Recommendation] = []
        total = stats.get("operations_total", 0)
        success_rate = stats.get("success_rate", 0.0)
        anchor_violations = stats.get("anchor_violations", 0)

        # Low success rate — only meaningful with enough samples
        if total >= self.MIN_OPS_FOR_VERDICT and success_rate < self.LOW_SUCCESS_RATE:
            recs.append(Recommendation(
                kind=KIND_AGENT_HEALTH,
                target="bridge",
                rationale=(
                    f"Overall success rate {success_rate:.0%} is below the "
                    f"{self.LOW_SUCCESS_RATE:.0%} health threshold over "
                    f"{total} operations"
                ),
                confidence=min(1.0, total / 100.0),
                severity=SEVERITY_WARN,
                evidence={
                    "operations_total": total,
                    "success_rate": success_rate,
                },
            ))

        # Any anchor violation is critical, no threshold needed
        if anchor_violations > 0:
            recs.append(Recommendation(
                kind=KIND_AGENT_HEALTH,
                target="bridge",
                rationale=(
                    f"{anchor_violations} anchor violation(s) detected — "
                    f"investigate undo / thread / consent / composition gates"
                ),
                confidence=1.0,
                severity=SEVERITY_CRITICAL,
                evidence={"anchor_violations": anchor_violations},
            ))

        # Pass 7: per-agent success rate analysis. A bridge can pass overall
        # health while one specific agent silently fails — that's exactly the
        # blind spot the per-agent counters were added to fix. We recommend
        # *the agent*, not the bridge, so the artist knows which pillar to
        # investigate first.
        per_agent_total = stats.get("per_agent", {})
        per_agent_rate = stats.get("per_agent_success_rate", {})
        for agent_key, agent_total in per_agent_total.items():
            if agent_total < self.MIN_OPS_FOR_VERDICT:
                continue
            agent_rate = per_agent_rate.get(agent_key, 0.0)
            if agent_rate < self.LOW_SUCCESS_RATE:
                recs.append(Recommendation(
                    kind=KIND_AGENT_HEALTH,
                    target=agent_key,
                    rationale=(
                        f"Agent {agent_key} success rate {agent_rate:.0%} is "
                        f"below the {self.LOW_SUCCESS_RATE:.0%} threshold "
                        f"over {agent_total} operations — check this pillar"
                    ),
                    confidence=min(1.0, agent_total / 100.0),
                    severity=SEVERITY_WARN,
                    evidence={
                        "agent": agent_key,
                        "operations_total": agent_total,
                        "success_rate": agent_rate,
                    },
                ))

        return recs

    def _analyze_evolution_drift(
        self, failures: list[EvolutionIntegrity]
    ) -> list[Recommendation]:
        """Cluster evolution failures by category prefix.

        After E5 the verifier emits structured failure strings like
        ``"Decision content drift: render_engine"`` — the prefix before the
        colon is the category. If three or more failures share a category,
        the companion writer or parser is the likely culprit, not the
        original markdown.
        """
        recs: list[Recommendation] = []
        if not failures:
            return recs

        category_counter: Counter[str] = Counter()
        for integrity in failures:
            for failure in integrity.failures:
                # Everything before the first colon is the category prefix
                prefix = failure.split(":", 1)[0].strip()
                if prefix:
                    category_counter[prefix] += 1

        for category, count in category_counter.most_common():
            if count >= self.DRIFT_FIELD_CLUSTER_THRESHOLD:
                severity = SEVERITY_CRITICAL if count >= 5 else SEVERITY_WARN
                recs.append(Recommendation(
                    kind=KIND_EVOLUTION_WRITER_FIX,
                    target=category,
                    rationale=(
                        f"{count} occurrences of '{category}' across recent "
                        f"evolutions suggest the companion writer or parser "
                        f"drops this field type — patch the round-trip"
                    ),
                    confidence=min(1.0, count / 10.0),
                    severity=severity,
                    evidence={"count": count, "category": category},
                ))

        return recs

    # ── Pass 8: Meta-Recursion ───────────────────────────────────

    def analyze_history(
        self, history: RecommendationHistory
    ) -> list[Recommendation]:
        """Look for patterns in past recommendations.

        This is the meta-recursive layer: the advisor analyzes its own
        output. The intuition: if the same recommendation has fired N times
        without being addressed, the artist either missed it, deferred it,
        or it's a false positive — either way, escalating its severity is
        useful information.

        Returns a fresh list of meta-Recommendations (kind=
        REPEATED_RECOMMENDATION). These coexist with — they don't replace —
        the originals.
        """
        recs: list[Recommendation] = []
        if history is None or len(history) == 0:
            return recs

        # Group by (kind, target) — same recommendation appearing repeatedly
        pair_counter: Counter[tuple[str, str]] = Counter()
        latest_by_pair: dict[tuple[str, str], HistoryEntry] = {}
        for entry in history.all():
            pair = (entry.recommendation.kind, entry.recommendation.target)
            pair_counter[pair] += 1
            latest_by_pair[pair] = entry

        for (kind, target), count in pair_counter.most_common():
            if count < self.REPEATED_RECOMMENDATION_THRESHOLD:
                continue
            latest = latest_by_pair[(kind, target)]
            severity = (
                SEVERITY_CRITICAL if count >= self.REPEATED_RECOMMENDATION_THRESHOLD * 2
                else SEVERITY_WARN
            )
            recs.append(Recommendation(
                kind=KIND_REPEATED_RECOMMENDATION,
                target=f"{kind}:{target}",
                rationale=(
                    f"Recommendation {kind!r} for {target!r} has appeared "
                    f"{count} times across history without being addressed — "
                    f"either action it or accept it as a tuning baseline"
                ),
                confidence=min(1.0, count / 10.0),
                severity=severity,
                evidence={
                    "kind": kind,
                    "target": target,
                    "occurrences": count,
                    "latest_timestamp": latest.timestamp,
                    "latest_rationale": latest.recommendation.rationale,
                },
            ))

        return recs

    def _analyze_routing_promotions(
        self, fingerprints: dict[str, int]
    ) -> list[Recommendation]:
        """Recommend canonical FAST_PATHS entries for hot fingerprints.

        The router auto-promotes to session fast paths internally (R12), but
        session promotions die with the process. A fingerprint that's been
        seen many times across sessions deserves a hand-tuned entry in
        ``constants.FAST_PATHS`` so it survives restarts.
        """
        recs: list[Recommendation] = []
        for fingerprint, count in fingerprints.items():
            if (
                count >= FAST_PATH_PROMOTION_THRESHOLD
                and fingerprint not in FAST_PATHS
            ):
                recs.append(Recommendation(
                    kind=KIND_ROUTER_PROMOTE,
                    target=fingerprint,
                    rationale=(
                        f"Fingerprint seen {count}× and is not in the "
                        f"hand-tuned FAST_PATHS table — consider promoting "
                        f"to a canonical entry for cross-session persistence"
                    ),
                    confidence=min(1.0, count / 10.0),
                    severity=SEVERITY_INFO,
                    evidence={"count": count, "fingerprint": fingerprint},
                ))
        return recs


# ── Recommendation History ───────────────────────────────────────


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One timestamped recommendation in the persistent history.

    Frozen for the same reason Recommendation is — these get serialized to
    disk and shipped through the agent.usd schema (Phase 4 of CLAUDE.md §9).
    """

    timestamp: str
    recommendation: Recommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "recommendation": self.recommendation.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HistoryEntry:
        rd = d["recommendation"]
        return cls(
            timestamp=d["timestamp"],
            recommendation=Recommendation(
                kind=rd["kind"],
                target=rd["target"],
                rationale=rd["rationale"],
                confidence=float(rd["confidence"]),
                severity=rd.get("severity", SEVERITY_INFO),
                evidence=rd.get("evidence", {}),
            ),
        )


class RecommendationHistory:
    """Append-only ring buffer with JSONL persistence.

    Capped to bound memory in long-running sessions (same pattern as the
    bridge operation log from pass 4). Each `record()` call appends one or
    more entries; `recent(n)` returns the most recent. Persistence is JSONL
    so it's diff-friendly, append-friendly, and survives partial writes.

    Thread-safe: all mutations and reads are protected by a lock. The
    CONDUCTOR agent may run in a background thread while the panel reads
    history for display — the lock prevents deque corruption.
    """

    DEFAULT_CAPACITY: int = 500

    def __init__(self, capacity: int | None = None):
        cap = capacity if capacity is not None else self.DEFAULT_CAPACITY
        self._capacity: int = cap
        self._entries: deque[HistoryEntry] = deque(maxlen=cap)
        self._lock = threading.Lock()

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def record(
        self,
        recommendations: Iterable[Recommendation],
        timestamp: str | None = None,
    ) -> int:
        """Append recommendations with a single timestamp. Returns count."""
        ts = timestamp or datetime.now().isoformat()
        n = 0
        with self._lock:
            for rec in recommendations:
                self._entries.append(HistoryEntry(timestamp=ts, recommendation=rec))
                n += 1
        return n

    def recent(self, n: int = 50) -> list[HistoryEntry]:
        if n <= 0:
            return []
        with self._lock:
            return list(self._entries)[-n:]

    def all(self) -> list[HistoryEntry]:
        with self._lock:
            return list(self._entries)

    def clear(self) -> int:
        with self._lock:
            n = len(self._entries)
            self._entries.clear()
        return n

    # ── Persistence ────────────────────────────────────────────

    def to_jsonl(self, path: str | Path) -> int:
        """Atomic-ish write: serialize all entries to a JSONL file. Returns
        the number of entries written."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        with self._lock:
            snapshot = list(self._entries)
        with tmp.open("w", encoding="utf-8") as f:
            for entry in snapshot:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        tmp.replace(p)
        return len(snapshot)

    @classmethod
    def from_jsonl(
        cls, path: str | Path, capacity: int | None = None
    ) -> RecommendationHistory:
        """Read entries from a JSONL file. Missing or empty file → empty
        history. Malformed lines are skipped (best-effort recovery)."""
        history = cls(capacity=capacity)
        p = Path(path)
        if not p.exists():
            return history
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = HistoryEntry.from_dict(json.loads(line))
                    history._entries.append(entry)
                except (json.JSONDecodeError, KeyError, TypeError):
                    # Best-effort: skip malformed lines, don't crash recovery
                    continue
        return history


# ── Convenience ──────────────────────────────────────────────────


def advise_from_bridge(
    bridge,
    evolution_failures: list[EvolutionIntegrity] | None = None,
    routing_fingerprints: dict[str, int] | None = None,
    router=None,
) -> list[Recommendation]:
    """One-shot helper: pull stats from a bridge instance and analyze.

    If a router is provided, fingerprint counts are pulled from it
    automatically (pass 8). Explicit ``routing_fingerprints`` overrides
    the router accessor.
    """
    advisor = ConductorAdvisor()
    if routing_fingerprints is None and router is not None:
        try:
            routing_fingerprints = router.fingerprint_counts()
        except AttributeError:
            routing_fingerprints = None
    return advisor.analyze(
        bridge_stats=bridge.operation_stats(),
        evolution_failures=evolution_failures,
        routing_fingerprints=routing_fingerprints,
    )
