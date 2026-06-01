"""Area 4 — pins the live runtime that closes RSI Line O.

The §16 recursive-observability API surface (RecommendationHistory, to_jsonl/
from_jsonl, analyze_history) was already built and tested. What was missing —
and what these tests pin — is the *driver*: agent_health.enrich_with_history /
poll_agent_health, which record the advisor's output into a persistent,
JSONL-backed history across restarts and run the meta-recursion analyzer. If
that wiring regresses, the panel's observability surface silently stops
learning. These tests fail loud if it does.

Pure logic only (no Qt). The painted HealthInfographic widget is verified under
hython offscreen, not here.
"""

import os

import pytest

from synapse.panel import agent_health as ah
from shared.conductor_advisor import (
    Recommendation,
    RecommendationHistory,
    KIND_AGENT_HEALTH,
    KIND_REPEATED_RECOMMENDATION,
    SEVERITY_WARN,
    SEVERITY_CRITICAL,
)


def _rec(target="HANDS"):
    return Recommendation(
        kind=KIND_AGENT_HEALTH, target=target,
        rationale=f"{target} success 70% over 20 ops",
        confidence=0.5, severity=SEVERITY_WARN,
    )


def _health(recs):
    return {
        "available": True,
        "bridge_stats": {"operations_total": 20, "success_rate": 0.7,
                         "anchor_violations": 0},
        "per_agent": {"HANDS": {"total": 20, "verified": 14, "rate": 0.7}},
        "recommendations": list(recs),
    }


def test_shared_is_available():
    # If shared/ isn't importable the whole loop is a no-op — fail loud, since
    # the test environment is supposed to exercise the real advisor.
    assert ah._SHARED_AVAILABLE is True


def test_history_path_respects_synapse_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SYNAPSE_ROOT", str(tmp_path))
    p = ah.history_path()
    assert p == tmp_path / ".synapse" / "agent_health_history.jsonl"


def test_enrich_records_persists_and_roundtrips(tmp_path):
    hist = RecommendationHistory()
    jsonl = tmp_path / "h.jsonl"
    out = ah.enrich_with_history(
        _health([_rec()]), history=hist, history_path_override=jsonl,
        record_interval=0.0,
    )
    assert len(hist) == 1
    assert jsonl.exists()
    # the enriched dict carries meta + tally for the infographic
    assert "meta_recommendations" in out and "history" in out
    # survives a restart: reload from disk gets the entry back
    assert len(RecommendationHistory.from_jsonl(jsonl)) == 1


def test_enrich_skips_recording_when_no_recommendations(tmp_path):
    hist = RecommendationHistory()
    jsonl = tmp_path / "h.jsonl"
    out = ah.enrich_with_history(
        _health([]), history=hist, history_path_override=jsonl,
        record_interval=0.0,
    )
    assert len(hist) == 0
    assert not jsonl.exists()          # nothing to persist → no file churn
    assert out["history"]["size"] == 0


def test_meta_recursion_escalates_chronic_recommendation():
    hist = RecommendationHistory()
    out = None
    for _ in range(5):                 # == REPEATED_RECOMMENDATION_THRESHOLD
        out = ah.enrich_with_history(_health([_rec()]), history=hist,
                                     record_interval=0.0)
    meta = out["meta_recommendations"]
    assert meta, "5 repeats of the same (kind,target) must escalate"
    assert meta[0].kind == KIND_REPEATED_RECOMMENDATION
    assert meta[0].severity == SEVERITY_WARN

    for _ in range(5):                 # 10 total → critical
        out = ah.enrich_with_history(_health([_rec()]), history=hist,
                                     record_interval=0.0)
    assert out["meta_recommendations"][0].severity == SEVERITY_CRITICAL


def test_tally_is_graphable():
    hist = RecommendationHistory()
    for tgt in ("HANDS", "HANDS", "OBSERVER"):
        ah.enrich_with_history(_health([_rec(tgt)]), history=hist,
                               record_interval=0.0)
    tally = ah._history_tally(hist)
    assert tally["size"] == 3
    assert tally["kind_counts"] == {KIND_AGENT_HEALTH: 3}
    assert isinstance(tally["recent_counts"], list)
    assert sum(tally["recent_counts"]) == 3   # one rec per distinct timestamp


def test_record_throttle_collapses_rapid_polls():
    hist = RecommendationHistory()
    # Seed the throttle clock far in the past so the first poll always records
    # regardless of the machine's monotonic origin; the immediate second poll
    # is then inside the (huge) interval and must be throttled out.
    ah._LAST_RECORD_MONO[0] = -1e12
    ah.enrich_with_history(_health([_rec()]), history=hist, record_interval=1e6)
    ah.enrich_with_history(_health([_rec()]), history=hist, record_interval=1e6)
    assert len(hist) == 1


def test_enrich_none_health_returns_none():
    assert ah.enrich_with_history(None) is None


def test_poll_is_graceful_when_collector_empty(monkeypatch):
    # When no bridge is found the collector yields None and the whole poll
    # degrades to None — never raises, never persists.
    monkeypatch.setattr(ah, "get_agent_health", lambda: None)
    assert ah.poll_agent_health() is None


def test_poll_swallows_collector_errors(monkeypatch):
    # Even a throwing collector must not propagate into the panel timer.
    def _boom():
        raise RuntimeError("bridge exploded")
    monkeypatch.setattr(ah, "get_agent_health", _boom)
    assert ah.poll_agent_health() is None
