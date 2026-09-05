"""
Agent Health Panel Data Provider (OBSERVER + CONDUCTOR roles).

Bridges the recursive observability loop (shared/conductor_advisor.py) to the
Houdini panel. Collects per-agent stats from the bridge, recommendations from
the advisor, and evolution stage — all with graceful fallback when shared/ is
not importable or no bridge is running.

Called by the panel's _poll_server_health every 3 seconds. Never blocks.
"""

from __future__ import annotations

import gc
import logging
import os
import time
import weakref
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Lazy imports from shared/ ────────────────────────────────────
# shared/ lives at repo root, not inside python/synapse/. The panel
# bootstrap adds SYNAPSE_ROOT to sys.path so this import works when
# the env var is set.

_SHARED_AVAILABLE = False
try:
    from shared.bridge import LosslessExecutionBridge
    from shared.conductor_advisor import (
        ConductorAdvisor,
        RecommendationHistory,
        advise_from_bridge,
        KIND_AGENT_HEALTH,
        SEVERITY_CRITICAL,
        SEVERITY_WARN,
    )
    from shared.router import MOERouter, get_default_router
    _SHARED_AVAILABLE = True
except ImportError:
    LosslessExecutionBridge = None
    ConductorAdvisor = None
    RecommendationHistory = None


_BRIDGE_REF = None  # weakref cache — full-heap gc scans are expensive at poll cadence


def _find_bridge_instance():
    """Find a running LosslessExecutionBridge via gc introspection.

    The scan over gc.get_objects() can be costly in a large Houdini session,
    and the panel polls on a timer — so we cache the bridge in a weakref and
    only re-scan if the cached instance has been collected. The weakref means
    a dead bridge never keeps a session alive.
    """
    global _BRIDGE_REF
    if not _SHARED_AVAILABLE:
        return None
    if _BRIDGE_REF is not None:
        cached = _BRIDGE_REF()
        if cached is not None:
            return cached
    for obj in gc.get_objects():
        if isinstance(obj, LosslessExecutionBridge):
            _BRIDGE_REF = weakref.ref(obj)
            return obj
    return None


def _find_router_instance():
    """Find the module-level default router."""
    if not _SHARED_AVAILABLE:
        return None
    try:
        return get_default_router()
    except Exception:
        return None


# ── Evolution stage display names ────────────────────────────────

_STAGE_DISPLAY = {
    "charmander": {"icon": "\U0001F525", "label": "Charmander", "desc": "Flat markdown"},
    "charmeleon": {"icon": "\u2728", "label": "Charmeleon", "desc": "Structured USD"},
    "charizard": {"icon": "\U0001F409", "label": "Charizard", "desc": "Composed USD + arcs"},
    # Legacy fallback
    "flat": {"icon": "\U0001F525", "label": "Charmander", "desc": "Flat markdown"},
    "structured": {"icon": "\u2728", "label": "Charmeleon", "desc": "Structured USD"},
    "composed": {"icon": "\U0001F409", "label": "Charizard", "desc": "Composed USD + arcs"},
    "none": {"icon": "\u2B55", "label": "None", "desc": "No memory"},
}


def get_evolution_display(login_data: dict | None) -> dict[str, str]:
    """Return display info for the current evolution stage."""
    if not login_data:
        return _STAGE_DISPLAY["none"]
    stage = ""
    for key in ("scene", "project"):
        mem = login_data.get(key, {})
        if isinstance(mem, dict):
            stage = mem.get("evolution", "") or ""
            if stage and stage != "none":
                break
    return _STAGE_DISPLAY.get(stage, _STAGE_DISPLAY["none"])


# ── Agent Health Snapshot ────────────────────────────────────────

def get_agent_health() -> dict[str, Any] | None:
    """Collect per-agent health data from the running bridge.

    Returns None if no bridge is available. Otherwise returns:
    {
        "bridge_stats": {...},
        "per_agent": {agent: {total, verified, rate}, ...},
        "recommendations": [Recommendation, ...],
        "available": True,
    }
    """
    bridge = _find_bridge_instance()
    if bridge is None:
        return None

    try:
        stats = bridge.operation_stats()
    except Exception:
        return None

    per_agent: dict[str, dict] = {}
    for agent_key, total in stats.get("per_agent", {}).items():
        verified = stats.get("per_agent_verified", {}).get(agent_key, 0)
        rate = stats.get("per_agent_success_rate", {}).get(agent_key, 0.0)
        per_agent[agent_key] = {
            "total": total,
            "verified": verified,
            "rate": rate,
        }

    # Get recommendations if advisor is available
    recommendations = []
    if _SHARED_AVAILABLE and ConductorAdvisor is not None:
        try:
            router = _find_router_instance()
            recommendations = advise_from_bridge(bridge, router=router)
        except Exception:
            pass

    return {
        "bridge_stats": stats,
        "per_agent": per_agent,
        "recommendations": recommendations,
        "available": True,
    }


# ── RSI Line O: persistent recommendation history + meta-recursion ──
# get_agent_health() above is a PURE collector (no side effects). The functions
# below close the recursive-observability loop (CLAUDE.md §16): they RECORD the
# advisor's recommendations into a capped, JSONL-persisted RecommendationHistory
# that survives restarts, then run the meta-recursion analyzer (analyze_history)
# so a recommendation that keeps recurring escalates. This is the live runtime
# the §16 API surface was built for — previously wired up but never driven.

#: Coarse record cadence. The panel polls every few seconds for a live display,
#: but recording every tick would make the meta-recursion threshold (5 repeats)
#: trip in seconds. We throttle recording so "5x" reads as a genuinely chronic
#: issue (~5 minutes of persistence), not 15 seconds of polling.
RECORD_INTERVAL_SEC: float = 60.0

_HISTORY = None            # module-singleton RecommendationHistory (lazy from_jsonl)
_HISTORY_PATH = None       # resolved Path of the JSONL backing file
_LAST_RECORD_MONO = [0.0]  # monotonic clock of the last throttled record


def history_path() -> Path:
    """Resolve the JSONL backing file. Prefers $SYNAPSE_ROOT/.synapse/ (repo
    convention, gitignored), else ~/.synapse/. One file per machine, shared
    across scenes — recommendation history is a behavior-tier signal."""
    root = os.environ.get("SYNAPSE_ROOT") or os.path.expanduser("~")
    return Path(root) / ".synapse" / "agent_health_history.jsonl"


def get_history():
    """The lazily-loaded, persistent RecommendationHistory singleton (or None
    when shared/ is unavailable). Reloaded from disk on first access so prior
    sessions' recommendations carry forward across restarts."""
    global _HISTORY, _HISTORY_PATH
    if not _SHARED_AVAILABLE or RecommendationHistory is None:
        return None
    if _HISTORY is None:
        _HISTORY_PATH = history_path()
        try:
            _HISTORY = RecommendationHistory.from_jsonl(_HISTORY_PATH)
        except Exception:
            _HISTORY = RecommendationHistory()
    return _HISTORY


def _history_tally(history) -> dict[str, Any]:
    """A graphable summary of the persistent history: total size, per-kind
    counts (a bar chart), and the per-timestamp recommendation-count series
    (a sparkline of advisory activity over time)."""
    entries = history.all()
    kind_counts = Counter(e.recommendation.kind for e in entries)
    per_ts = OrderedDict()
    for e in entries:
        per_ts[e.timestamp] = per_ts.get(e.timestamp, 0) + 1
    return {
        "size": len(entries),
        "kind_counts": dict(kind_counts),
        "recent_counts": list(per_ts.values())[-24:],
    }


def enrich_with_history(
    health: dict[str, Any] | None,
    history=None,
    history_path_override=None,
    record: bool = True,
    record_interval: float | None = None,
) -> dict[str, Any] | None:
    """Record this snapshot's recommendations into the persistent history
    (throttled), run the meta-recursion analyzer, and attach both the meta
    recommendations and a graphable tally. Pure w.r.t. its inputs except the
    history it records into — testable with an injected history + temp path.
    """
    if health is None:
        return None
    hist = history if history is not None else get_history()
    path = history_path_override if history_path_override is not None else _HISTORY_PATH
    meta: list = []
    tally: dict[str, Any] = {}
    if hist is not None:
        recs = health.get("recommendations", [])
        interval = RECORD_INTERVAL_SEC if record_interval is None else record_interval
        if record and recs:
            now = time.monotonic()
            if now - _LAST_RECORD_MONO[0] >= interval:
                try:
                    hist.record(recs)
                    if path is not None:
                        hist.to_jsonl(path)
                    _LAST_RECORD_MONO[0] = now
                except Exception:
                    pass
        if ConductorAdvisor is not None:
            try:
                meta = ConductorAdvisor().analyze_history(hist)
            except Exception:
                meta = []
        tally = _history_tally(hist)
    health = dict(health)
    health["meta_recommendations"] = meta
    health["history"] = tally
    return health


def poll_agent_health() -> dict[str, Any] | None:
    """The panel timer's entry point: collect health, record + persist into the
    history, compute meta-recursion + tally. Returns the enriched dict (or None
    when no bridge is running). Never raises."""
    try:
        return enrich_with_history(get_agent_health())
    except Exception:
        logger.debug("poll_agent_health failed", exc_info=True)
        return None
