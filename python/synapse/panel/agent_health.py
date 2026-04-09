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


def _find_bridge_instance():
    """Find a running LosslessExecutionBridge via gc introspection."""
    if not _SHARED_AVAILABLE:
        return None
    for obj in gc.get_objects():
        if isinstance(obj, LosslessExecutionBridge):
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


def format_agent_health_html(health: dict[str, Any]) -> str:
    """Render agent health data as compact HTML for the panel display.

    Uses the Pentagram design system colors when available.
    """
    if not health or not health.get("available"):
        return '<span style="color:#888">No bridge data available</span>'

    stats = health["bridge_stats"]
    lines = []

    # Overall bridge health
    total = stats.get("operations_total", 0)
    rate = stats.get("success_rate", 0.0)
    violations = stats.get("anchor_violations", 0)

    rate_color = "#00E676" if rate >= 0.95 else "#FFAB00" if rate >= 0.85 else "#FF3D71"
    lines.append(
        '<div style="margin-bottom:4px">'
        '<span style="color:#AAAAAA">Bridge:</span> '
        '<span style="color:{c}">{r:.0%}</span> '
        '<span style="color:#888">({t} ops)</span>'
        '</div>'.format(c=rate_color, r=rate, t=total)
    )

    if violations > 0:
        lines.append(
            '<div style="color:#FF3D71; margin-bottom:4px">'
            '\u26A0 {v} anchor violation(s)</div>'.format(v=violations)
        )

    # Per-agent bars
    per_agent = health.get("per_agent", {})
    if per_agent:
        lines.append(
            '<div style="margin-top:6px; margin-bottom:2px">'
            '<span style="color:#AAAAAA">Per-Agent:</span></div>'
        )
        for agent, data in sorted(per_agent.items()):
            r = data["rate"]
            t = data["total"]
            bar_color = "#00E676" if r >= 0.95 else "#FFAB00" if r >= 0.85 else "#FF3D71"
            bar_width = max(2, int(r * 100))
            lines.append(
                '<div style="margin:1px 0">'
                '<span style="color:#CCCCCC; display:inline-block; width:90px">'
                '{agent}</span>'
                '<span style="background:{c}; display:inline-block; '
                'width:{w}px; height:8px; border-radius:2px; '
                'vertical-align:middle"></span>'
                ' <span style="color:#888; font-size:11px">'
                '{r:.0%} ({t})</span>'
                '</div>'.format(
                    agent=agent, c=bar_color, w=bar_width, r=r, t=t
                )
            )

    # Recommendations
    recs = health.get("recommendations", [])
    if recs:
        lines.append(
            '<div style="margin-top:8px; margin-bottom:2px">'
            '<span style="color:#AAAAAA">Advisor:</span></div>'
        )
        for rec in recs[:5]:  # Cap at 5 for display
            sev = getattr(rec, "severity", "info")
            icon = "\u26A0" if sev == "critical" else "\u26AB" if sev == "warn" else "\u2139"
            sev_color = "#FF3D71" if sev == "critical" else "#FFAB00" if sev == "warn" else "#888"
            lines.append(
                '<div style="margin:1px 0; color:{c}">'
                '{icon} <span style="color:#CCCCCC">{target}</span>: '
                '{rationale}</div>'.format(
                    c=sev_color, icon=icon,
                    target=getattr(rec, "target", ""),
                    rationale=getattr(rec, "rationale", ""),
                )
            )

    return "\n".join(lines)
