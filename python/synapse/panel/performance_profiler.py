"""SYNAPSE Performance Profiler -- Network bottleneck analysis for Houdini.

Profiles all nodes in a Houdini network, identifies cook-time bottlenecks,
and suggests optimizations based on node type and geometry statistics.

Usage inside Houdini::

    from synapse.panel.performance_profiler import profile_network, format_profile_html
    report = profile_network("/obj/geo1")
    html   = format_profile_html(report)

Outside Houdini the module still imports cleanly -- profile_network()
returns an empty report immediately.
"""

from __future__ import annotations

import html as html_mod
import time
from dataclasses import dataclass, field
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]

    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Cap profiling to avoid hanging on massive networks.
_MAX_PROFILE_NODES = 100

# A node consuming more than this fraction of total cook time is a bottleneck.
_BOTTLENECK_THRESHOLD = 0.20

# Rough bytes-per-point for memory estimation (position + normals + Cd).
_BYTES_PER_POINT = 48  # 3*float32 position + 3*float32 normal + 4*float32 Cd


# ============================================================================
# Optimization hints
# ============================================================================

OPTIMIZATION_HINTS: dict[str, str] = {
    "copytopoints": (
        "Enable 'Pack and Instance' to reduce memory. "
        "Move expensive operations before copy."
    ),
    "polyreduce": "Apply before heavy operations to reduce input size.",
    "vdbfrompolygons": (
        "Reduce input poly count or increase voxel size."
    ),
    "scatter": (
        "Reduce count or use relaxation=0 for faster scatter."
    ),
    "mountain": (
        "Reduce element size iterations for faster noise."
    ),
    "subdivide": (
        "Reduce levels. 4->3 cuts poly count by 75%."
    ),
    "boolean": (
        "Simplify inputs. Boolean is O(n*m) on face count."
    ),
    "remesh": "Increase target edge length for fewer output polys.",
    "vellumsolve": (
        "Reduce substeps or increase constraint iterations instead."
    ),
    "flipsolve": (
        "Reduce particle separation or use adaptive resolution."
    ),
    "pyrosolver": (
        "Increase division size. Halving voxel size = 8x memory/time."
    ),
    "foreach_end": (
        "Check if the loop body can be replaced with a VEX wrangle."
    ),
    "foreach_begin": (
        "Ensure 'Piece Attribute' is set to avoid full-geo iterations."
    ),
    "attribwrangle": (
        "Minimize string operations in VEX. Pre-promote attribs to avoid "
        "point-level lookups."
    ),
    "volumerasterize": (
        "Reduce point count or increase voxel size for faster rasterization."
    ),
    "polybevel": (
        "Reduce offset or divisions. High divisions on dense meshes are slow."
    ),
    "convertvdb": (
        "Use fog-to-SDF only when needed. Avoid back-and-forth conversions."
    ),
    "heightfield_erode": (
        "Reduce iterations or increase grid spacing."
    ),
    "whitewatersolver": (
        "Reduce emit density. Whitewater particle counts explode quickly."
    ),
    "rbdsolver": (
        "Use convex decomposition instead of concave for collision shapes."
    ),
    "vellumdrape": (
        "Reduce drape substeps. 20->10 is usually sufficient."
    ),
    "heightfield_noise": (
        "Reduce octaves or increase element size for faster noise."
    ),
    "voronoifracture": (
        "Reduce point count fed into fracture. Use clustering for large meshes."
    ),
    "pointdeform": (
        "Reduce capture radius or use lower-resolution rest geometry."
    ),
    "trail": (
        "Only compute velocity when needed. Disable acceleration computation "
        "if not required."
    ),
    "sort": (
        "Sort by proximity is O(n^2). Use spatial sort when possible."
    ),
    "groupexpression": (
        "Prefer group-by-range over VEXpression for simple numeric thresholds."
    ),
    "detangle": (
        "Reduce search radius. Large radius on dense cloth is expensive."
    ),
}


# ============================================================================
# Data classes
# ============================================================================


@dataclass
class ProfileEntry:
    """Cook-time profile for a single node."""

    node_path: str
    node_type: str
    cook_time_ms: float
    cook_pct: float  # percentage of total
    memory_estimate_mb: float  # rough estimate
    point_count: int
    prim_count: int
    is_bottleneck: bool
    suggestion: str  # optimization suggestion or ""


@dataclass
class ProfileReport:
    """Aggregated profile for an entire network."""

    entries: List[ProfileEntry] = field(default_factory=list)
    total_cook_ms: float = 0.0
    total_points: int = 0
    network_path: str = ""
    bottlenecks: List[ProfileEntry] = field(default_factory=list)
    suggestions: List[Tuple[str, str]] = field(default_factory=list)
    summary: str = ""


# ============================================================================
# Core profiling
# ============================================================================


def _get_cook_time_ms(node) -> float:
    """Extract cook time in milliseconds from a Houdini node."""
    try:
        return node.cookTime() * 1000.0
    except Exception:
        return 0.0


def _get_geo_stats(node) -> Tuple[int, int]:
    """Return (point_count, prim_count) for a node, (0, 0) on failure."""
    try:
        geo = node.geometry()
        if geo is None:
            return 0, 0
        return geo.intrinsicValue("pointcount"), geo.intrinsicValue("primcount")
    except Exception:
        return 0, 0


def _estimate_memory_mb(point_count: int, prim_count: int) -> float:
    """Rough memory estimate based on point/prim counts."""
    # Points carry most of the attribute weight; prims add topology overhead.
    bytes_est = (point_count * _BYTES_PER_POINT) + (prim_count * 16)
    return round(bytes_est / (1024 * 1024), 2)


def _lookup_suggestion(node_type: str) -> str:
    """Look up optimization hint for a node type (base name, lowercase)."""
    # Strip version suffixes: "copytopoints::2.0" -> "copytopoints"
    base = node_type.split("::")[0].lower()
    return OPTIMIZATION_HINTS.get(base, "")


def profile_network(network_path: str = "") -> ProfileReport:
    """Profile all nodes in a Houdini network and identify bottlenecks.

    Parameters
    ----------
    network_path:
        Houdini network path (e.g. ``"/obj/geo1"``).  If empty, uses the
        current network pane context when available.

    Returns
    -------
    ProfileReport
        Sorted by cook_time descending, with bottleneck flags and suggestions.
    """
    if not _HOU_AVAILABLE:
        return ProfileReport(summary="Houdini not available.")

    # Resolve network node.
    if network_path:
        parent = hou.node(network_path)
    else:
        # Attempt to get the current network editor context.
        try:
            editors = [
                p for p in hou.ui.paneTabs() if p.type() == hou.paneTabType.NetworkEditor
            ]
            parent = editors[0].pwd() if editors else hou.node("/obj")
        except Exception:
            parent = hou.node("/obj")

    if parent is None:
        return ProfileReport(
            network_path=network_path,
            summary=f"Network not found: {network_path}",
        )

    # Gather children (capped).
    children = list(parent.children())[:_MAX_PROFILE_NODES]
    if not children:
        return ProfileReport(
            network_path=parent.path(),
            summary=f"No nodes in {parent.path()}.",
        )

    # Collect raw data.
    raw: list[dict] = []
    total_cook = 0.0
    total_pts = 0

    for node in children:
        cook_ms = _get_cook_time_ms(node)
        pts, prims = _get_geo_stats(node)
        mem_mb = _estimate_memory_mb(pts, prims)
        total_cook += cook_ms
        total_pts += pts
        raw.append({
            "path": node.path(),
            "type": node.type().name(),
            "cook_ms": cook_ms,
            "pts": pts,
            "prims": prims,
            "mem_mb": mem_mb,
        })

    # Sort descending by cook time.
    raw.sort(key=lambda r: r["cook_ms"], reverse=True)

    # Build entries with percentages and bottleneck flags.
    entries: list[ProfileEntry] = []
    bottlenecks: list[ProfileEntry] = []
    suggestions: list[tuple[str, str]] = []

    for r in raw:
        pct = (r["cook_ms"] / total_cook * 100.0) if total_cook > 0 else 0.0
        is_bn = pct >= (_BOTTLENECK_THRESHOLD * 100.0)
        hint = _lookup_suggestion(r["type"])

        # Only surface suggestions for bottleneck nodes.
        suggestion = hint if (is_bn and hint) else ""

        entry = ProfileEntry(
            node_path=r["path"],
            node_type=r["type"],
            cook_time_ms=round(r["cook_ms"], 2),
            cook_pct=round(pct, 1),
            memory_estimate_mb=r["mem_mb"],
            point_count=r["pts"],
            prim_count=r["prims"],
            is_bottleneck=is_bn,
            suggestion=suggestion,
        )
        entries.append(entry)

        if is_bn:
            bottlenecks.append(entry)
        if suggestion:
            suggestions.append((entry.node_path, suggestion))

    # Summary line.
    bn_detail = ""
    if bottlenecks:
        top = bottlenecks[0]
        top_name = top.node_path.rsplit("/", 1)[-1]
        bn_detail = f" Bottleneck: {top_name} ({top.cook_pct}%)"

    summary = (
        f"{len(entries)} nodes, {total_cook / 1000:.1f}s total.{bn_detail}"
    )

    return ProfileReport(
        entries=entries,
        total_cook_ms=round(total_cook, 2),
        total_points=total_pts,
        network_path=parent.path(),
        bottlenecks=bottlenecks,
        suggestions=suggestions,
        summary=summary,
    )


# ============================================================================
# HTML formatting
# ============================================================================


def format_profile_html(report: ProfileReport) -> str:
    """Render a profile report as styled HTML with bar chart.

    Returns a self-contained HTML fragment suitable for embedding in a
    QTextBrowser or Synapse chat panel.
    """
    if not report.entries:
        return (
            "<div style='color:#aaa; padding:12px;'>"
            f"{html_mod.escape(report.summary)}</div>"
        )

    lines: list[str] = []
    lines.append("<div style='font-family:monospace; font-size:13px; color:#ccc;'>")

    # Summary header.
    lines.append(
        f"<div style='padding:8px 12px; background:#2a2a2a; border-radius:6px; "
        f"margin-bottom:10px; font-size:14px;'>"
        f"<b>Profile:</b> {html_mod.escape(report.network_path)}<br/>"
        f"{html_mod.escape(report.summary)}</div>"
    )

    # Bar chart.
    max_cook = report.entries[0].cook_time_ms if report.entries else 1.0
    if max_cook <= 0:
        max_cook = 1.0

    for entry in report.entries:
        bar_pct = (entry.cook_time_ms / max_cook * 100.0) if max_cook > 0 else 0
        bar_pct = min(bar_pct, 100.0)

        bg_color = "#e8a020" if entry.is_bottleneck else "#4a90d9"
        border_color = "#d4881a" if entry.is_bottleneck else "#3a7bc8"
        row_bg = "rgba(232,160,32,0.08)" if entry.is_bottleneck else "transparent"

        node_name = entry.node_path.rsplit("/", 1)[-1]
        escaped_name = html_mod.escape(node_name)
        escaped_type = html_mod.escape(entry.node_type)

        lines.append(
            f"<div style='padding:4px 8px; margin:2px 0; background:{row_bg};'>"
            f"  <div style='display:flex; justify-content:space-between; "
            f"align-items:center;'>"
            f"    <span style='min-width:160px;'>"
            f"      <b>{escaped_name}</b> "
            f"      <span style='color:#888; font-size:11px;'>({escaped_type})</span>"
            f"    </span>"
            f"    <span style='min-width:80px; text-align:right;'>"
            f"      {entry.cook_time_ms:.1f}ms ({entry.cook_pct:.0f}%)"
            f"    </span>"
            f"  </div>"
            f"  <div style='background:#1a1a1a; border-radius:3px; height:8px; "
            f"margin-top:3px;'>"
            f"    <div style='background:{bg_color}; border:1px solid {border_color}; "
            f"border-radius:3px; height:100%; width:{bar_pct:.1f}%;'></div>"
            f"  </div>"
        )

        if entry.suggestion:
            escaped_hint = html_mod.escape(entry.suggestion)
            lines.append(
                f"  <div style='color:#e8a020; font-size:11px; margin:3px 0 0 8px;'>"
                f"    Tip: {escaped_hint}"
                f"  </div>"
            )

        lines.append("</div>")

    # Geometry summary.
    lines.append(
        f"<div style='padding:8px 12px; margin-top:8px; color:#888; font-size:11px;'>"
        f"Total points: {report.total_points:,} | "
        f"Nodes profiled: {len(report.entries)}"
        f"</div>"
    )

    # Apply suggestions prompt.
    if report.suggestions:
        lines.append(
            "<div style='padding:8px 12px; margin-top:6px; background:#2a2a2a; "
            "border-radius:6px; color:#e8a020;'>"
            f"<b>{len(report.suggestions)} optimization suggestion"
            f"{'s' if len(report.suggestions) != 1 else ''} available.</b> "
            "Ask me to apply them or explain further."
            "</div>"
        )

    lines.append("</div>")
    return "\n".join(lines)


# ============================================================================
# Message building for Claude interpretation
# ============================================================================


def build_profile_messages(report: ProfileReport) -> list[dict[str, str]]:
    """Build messages for Claude to interpret a profile and suggest deeper fixes.

    Returns a list of message dicts with ``role`` and ``content`` keys,
    suitable for feeding into a Claude conversation.
    """
    if not report.entries:
        return [
            {
                "role": "user",
                "content": (
                    f"I profiled the network at {report.network_path} but "
                    "there were no nodes to profile."
                ),
            }
        ]

    # System context.
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "You are SYNAPSE, a Houdini performance advisor. The user has "
                "profiled a network and wants optimization guidance. Focus on "
                "the biggest bottlenecks first. Suggest concrete parameter "
                "changes, alternative node approaches, or VEX replacements. "
                "Keep suggestions actionable and specific to Houdini 21."
            ),
        },
    ]

    # Build the profile data block.
    profile_lines = [
        f"Network: {report.network_path}",
        f"Total cook time: {report.total_cook_ms:.1f}ms "
        f"({report.total_cook_ms / 1000:.2f}s)",
        f"Total points: {report.total_points:,}",
        f"Nodes profiled: {len(report.entries)}",
        "",
        "Top nodes by cook time:",
    ]

    # Show top 20 or all if fewer.
    for entry in report.entries[:20]:
        bn_marker = " [BOTTLENECK]" if entry.is_bottleneck else ""
        profile_lines.append(
            f"  {entry.node_path} ({entry.node_type}): "
            f"{entry.cook_time_ms:.1f}ms ({entry.cook_pct:.0f}%)"
            f" | pts={entry.point_count:,} prims={entry.prim_count:,}"
            f" | ~{entry.memory_estimate_mb:.1f}MB{bn_marker}"
        )

    if report.suggestions:
        profile_lines.append("")
        profile_lines.append("Known optimization hints:")
        for path, hint in report.suggestions:
            node_name = path.rsplit("/", 1)[-1]
            profile_lines.append(f"  {node_name}: {hint}")

    messages.append({
        "role": "user",
        "content": (
            "Here is my network performance profile. Identify the biggest "
            "bottlenecks and suggest specific optimizations I can apply.\n\n"
            + "\n".join(profile_lines)
        ),
    })

    return messages
