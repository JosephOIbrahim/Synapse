"""
SYNAPSE Network Trace -- Data-flow tracer for Houdini networks.

Walks from source nodes to the display flag node, recording geometry
statistics, cook times, attribute deltas, and key parameters at each
step.  The result is a TraceReport that can be rendered as HTML (for
the Synapse panel QTextEdit) or plain text (for sending to Claude).

All hou access is individually guarded so one failing node never
breaks the whole trace.  Outside Houdini the module imports cleanly
and trace_network() returns an empty report immediately.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
_MAX_TRACE_NODES = 50
_KEY_PARMS_LIMIT = 3


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class TraceStep:
    """One node in the traced data-flow chain."""

    index: int                                # 1-based position in chain
    node_path: str
    node_type: str
    node_label: str                           # display label
    description: str                          # what this node does
    input_geo: Optional[Dict[str, Any]]       # {points, prims, attribs} BEFORE
    output_geo: Optional[Dict[str, Any]]      # {points, prims, attribs} AFTER
    geo_delta: str                            # "2,500 pts -> 10,000 pts (+7,500)"
    attrib_delta: str                         # "+Cd, +N" or "-rest" or "no change"
    key_parms: List[Dict[str, Any]]           # [{name, label, value}]
    cook_time_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TraceReport:
    """Aggregated result of tracing a full network chain."""

    network_path: str
    steps: List[TraceStep] = field(default_factory=list)
    total_cook_ms: float = 0.0
    bottleneck: Optional[str] = None          # node_path of slowest step
    bottleneck_pct: float = 0.0               # percentage of total cook time
    summary: str = ""


# ============================================================================
# Geometry stats helper
# ============================================================================

def _geo_stats(node: Any) -> Optional[Dict[str, Any]]:
    """Return {points, prims, attribs} for *node*, or None on failure."""
    if not _HOU_AVAILABLE or node is None:
        return None
    try:
        geo = node.geometry()
        if geo is None:
            return None

        def _attrib_names(owner: Any) -> List[str]:
            try:
                return [a.name() for a in geo.attribs(owner)]
            except Exception:
                return []

        return {
            "points": geo.intrinsicValue("pointcount"),
            "prims": geo.intrinsicValue("primitivecount"),
            "attribs": {
                "point": _attrib_names(hou.attribType.Point),
                "prim": _attrib_names(hou.attribType.Prim),
                "vertex": _attrib_names(hou.attribType.Vertex),
                "detail": _attrib_names(hou.attribType.Global),
            },
        }
    except Exception:
        return None


# ============================================================================
# Internal helpers
# ============================================================================

def _format_count(n: int) -> str:
    """Format an integer with thousands separators."""
    return f"{n:,}"


def _compute_geo_delta(input_geo: Optional[Dict], output_geo: Optional[Dict]) -> str:
    """Describe point-count change between input and output geometry."""
    if input_geo is None and output_geo is None:
        return "no geometry"
    if input_geo is None and output_geo is not None:
        pts = output_geo.get("points", 0)
        return f"-> {_format_count(pts)} pts (source)"
    if input_geo is not None and output_geo is None:
        return "geometry removed"
    # Both present
    pts_in = input_geo.get("points", 0)  # type: ignore[union-attr]
    pts_out = output_geo.get("points", 0)  # type: ignore[union-attr]
    if pts_in == pts_out:
        return f"{_format_count(pts_out)} pts (no change)"
    diff = pts_out - pts_in
    sign = "+" if diff > 0 else ""
    return f"{_format_count(pts_in)} pts -> {_format_count(pts_out)} pts ({sign}{_format_count(diff)})"


def _compute_attrib_delta(input_geo: Optional[Dict], output_geo: Optional[Dict]) -> str:
    """Describe attribute changes between input and output geometry."""
    if input_geo is None or output_geo is None:
        return "no change"

    def _all_attribs(geo_dict: Dict) -> set:
        attribs = geo_dict.get("attribs", {})
        result: set = set()
        for owner in ("point", "prim", "vertex", "detail"):
            for name in attribs.get(owner, []):
                result.add(f"{owner}:{name}")
        return result

    before = _all_attribs(input_geo)
    after = _all_attribs(output_geo)
    added = after - before
    removed = before - after

    parts: List[str] = []
    if added:
        # Strip owner prefix for readability -- just show attribute names
        names = sorted({a.split(":", 1)[1] for a in added})
        parts.append("+" + ", +".join(names))
    if removed:
        names = sorted({r.split(":", 1)[1] for r in removed})
        parts.append("-" + ", -".join(names))

    return ", ".join(parts) if parts else "no change"


def _get_node_description(node: Any) -> str:
    """Return a human-readable description of what this node type does."""
    try:
        node_type = node.type()
        desc = node_type.description()
        if desc:
            return desc
        return node_type.name()
    except Exception:
        return ""


def _get_key_parms(node: Any, limit: int = _KEY_PARMS_LIMIT) -> List[Dict[str, Any]]:
    """Return up to *limit* non-default parameters as {name, label, value}."""
    result: List[Dict[str, Any]] = []
    try:
        for parm in node.parms():
            try:
                if parm.isAtDefault():
                    continue
                # Skip invisible / folder parms
                template = parm.parmTemplate()
                if template.isHidden():
                    continue
                if template.type() == hou.parmTemplateType.FolderSet:
                    continue
                if template.type() == hou.parmTemplateType.Folder:
                    continue
                result.append({
                    "name": parm.name(),
                    "label": template.label(),
                    "value": parm.evalAsString(),
                })
                if len(result) >= limit:
                    break
            except Exception:
                continue
    except Exception:
        pass
    return result


def _get_cook_time_ms(node: Any) -> float:
    """Best-effort cook time in milliseconds for *node*."""
    # Try perfMon profile data first
    try:
        profile = hou.perfMon.activeProfile()
        if profile is not None:
            stats = profile.stats(node.path())
            if stats is not None:
                return stats.cookTime() * 1000.0
    except Exception:
        pass
    # Fallback: cookTime() if available (some node types expose this)
    try:
        ct = node.cookTime()
        if ct is not None:
            return ct * 1000.0
    except Exception:
        pass
    return 0.0


def _get_node_messages(node: Any) -> tuple:
    """Return (errors: list, warnings: list) for *node*."""
    errors: List[str] = []
    warnings: List[str] = []
    try:
        errors = list(node.errors())
    except Exception:
        pass
    try:
        warnings = list(node.warnings())
    except Exception:
        pass
    return errors, warnings


def _describe_secondary_inputs(node: Any) -> str:
    """Describe non-primary inputs for branch awareness."""
    parts: List[str] = []
    try:
        inputs = node.inputs()
        for i, inp in enumerate(inputs):
            if i == 0 or inp is None:
                continue
            label = inp.name()
            stats = _geo_stats(inp)
            if stats:
                pts = _format_count(stats["points"])
                parts.append(f"{label} (input {i}: {pts} pts)")
            else:
                parts.append(f"{label} (input {i})")
    except Exception:
        pass
    return parts[0] if len(parts) == 1 else ", ".join(parts) if parts else ""


# ============================================================================
# Primary trace function
# ============================================================================

def trace_network(network_path: str = "") -> TraceReport:
    """Trace data flow from source to display node in *network_path*.

    If *network_path* is empty, uses the current network editor's pwd().
    Returns an empty TraceReport if Houdini is unavailable or the network
    cannot be resolved.
    """
    if not _HOU_AVAILABLE:
        return TraceReport(network_path=network_path or "(unavailable)",
                           summary="Houdini not available")

    # Resolve network path ------------------------------------------------
    try:
        if not network_path:
            # Use the current network editor pane's working directory
            editors = [p for p in hou.ui.paneTabs()
                       if p.type() == hou.paneTabType.NetworkEditor]
            if editors:
                network_path = editors[0].pwd().path()
            else:
                network_path = "/obj"
        network_node = hou.node(network_path)
        if network_node is None:
            return TraceReport(network_path=network_path,
                               summary=f"Network not found: {network_path}")
    except Exception as exc:
        return TraceReport(network_path=network_path or "(error)",
                           summary=f"Error resolving network: {exc}")

    # Find the display node ------------------------------------------------
    display_node = None
    try:
        display_node = network_node.displayNode()
    except Exception:
        pass
    if display_node is None:
        # Fallback: look for render flag
        try:
            display_node = network_node.renderNode()
        except Exception:
            pass
    if display_node is None:
        return TraceReport(network_path=network_path,
                           summary="No display or render flag node found")

    # Walk backwards through input[0] to build chain ----------------------
    chain: List[Any] = []
    current = display_node
    visited: set = set()
    while current is not None:
        node_id = current.sessionId()
        if node_id in visited:
            break  # cycle guard
        visited.add(node_id)
        chain.append(current)
        try:
            inputs = current.inputs()
            current = inputs[0] if inputs and inputs[0] is not None else None
        except Exception:
            current = None

    chain.reverse()

    # Apply 50-node limit --------------------------------------------------
    truncated = False
    total_chain_len = len(chain)
    if total_chain_len > _MAX_TRACE_NODES:
        chain = chain[-_MAX_TRACE_NODES:]
        truncated = True

    # Build TraceSteps -----------------------------------------------------
    steps: List[TraceStep] = []
    prev_output: Optional[Dict[str, Any]] = None

    for idx, node in enumerate(chain, start=1):
        try:
            # Input geometry = previous node's output (or None for source)
            input_geo = prev_output

            # Output geometry
            output_geo = _geo_stats(node)

            # Deltas
            geo_delta = _compute_geo_delta(input_geo, output_geo)
            attrib_delta = _compute_attrib_delta(input_geo, output_geo)

            # Secondary inputs
            secondary = _describe_secondary_inputs(node)
            desc = _get_node_description(node)
            if secondary:
                desc = f"{desc}. Also receives: {secondary}"

            # Errors / warnings
            errors, warnings = _get_node_messages(node)

            step = TraceStep(
                index=idx,
                node_path=node.path(),
                node_type=node.type().name(),
                node_label=node.name(),
                description=desc,
                input_geo=input_geo,
                output_geo=output_geo,
                geo_delta=geo_delta,
                attrib_delta=attrib_delta,
                key_parms=_get_key_parms(node),
                cook_time_ms=_get_cook_time_ms(node),
                errors=errors,
                warnings=warnings,
            )
            steps.append(step)
            prev_output = output_geo

        except Exception as exc:
            # One node failing must not break the trace
            steps.append(TraceStep(
                index=idx,
                node_path=getattr(node, "path", lambda: "(unknown)")(),
                node_type="(error)",
                node_label=getattr(node, "name", lambda: "(error)")(),
                description=f"Error tracing node: {exc}",
                input_geo=prev_output,
                output_geo=None,
                geo_delta="error",
                attrib_delta="error",
                key_parms=[],
                cook_time_ms=0.0,
                errors=[str(exc)],
                warnings=[],
            ))
            # Don't update prev_output -- next node keeps prior context

    # Compute report-level stats -------------------------------------------
    total_cook = sum(s.cook_time_ms for s in steps)
    bottleneck_step: Optional[TraceStep] = None
    if steps:
        bottleneck_step = max(steps, key=lambda s: s.cook_time_ms)

    bottleneck_path: Optional[str] = None
    bottleneck_pct = 0.0
    if bottleneck_step and total_cook > 0:
        bottleneck_path = bottleneck_step.node_path
        bottleneck_pct = (bottleneck_step.cook_time_ms / total_cook) * 100.0

    # Summary line
    node_count_str = f"{len(steps)} nodes"
    if truncated:
        node_count_str = f"last {len(steps)} of {total_chain_len} nodes"
    cook_str = f"{total_cook:.1f}ms total cook"
    bn_str = ""
    if bottleneck_path and total_cook > 0:
        bn_str = f", bottleneck: {bottleneck_step.node_label} ({bottleneck_pct:.0f}%)"  # type: ignore[union-attr]

    summary = f"{node_count_str}, {cook_str}{bn_str}"

    return TraceReport(
        network_path=network_path,
        steps=steps,
        total_cook_ms=total_cook,
        bottleneck=bottleneck_path,
        bottleneck_pct=bottleneck_pct,
        summary=summary,
    )


# ============================================================================
# HTML formatter
# ============================================================================

def format_trace_html(report: TraceReport) -> str:
    """Render a TraceReport as HTML for the Synapse panel QTextEdit."""
    if not report.steps:
        return (
            f"<p style='color:#888;'>No trace data for "
            f"<b>{html.escape(report.network_path)}</b>: "
            f"{html.escape(report.summary)}</p>"
        )

    lines: List[str] = []
    lines.append(
        f"<h3 style='margin:4px 0;'>Network Trace: "
        f"{html.escape(report.network_path)}</h3>"
    )

    for step in report.steps:
        # Color coding
        is_bottleneck = (step.node_path == report.bottleneck and
                         report.bottleneck_pct > 0)
        is_trivial = step.cook_time_ms < 1.0

        if is_bottleneck:
            border_color = "#E8922E"  # orange
        elif is_trivial:
            border_color = "#666666"  # gray
        else:
            border_color = "#888888"

        # Geo delta color
        geo_color = "#AAAAAA"
        if step.output_geo and step.input_geo:
            pts_in = step.input_geo.get("points", 0)
            pts_out = step.output_geo.get("points", 0)
            if pts_out > pts_in:
                geo_color = "#6ABF69"  # green
            elif pts_out < pts_in:
                geo_color = "#E05555"  # red

        lines.append(
            f"<div style='border-left:3px solid {border_color}; "
            f"padding:4px 8px; margin:4px 0;'>"
        )

        # Header
        lines.append(
            f"<b>Step {step.index}:</b> "
            f"<b>{html.escape(step.node_label)}</b> "
            f"<span style='color:#888;'>({html.escape(step.node_type)})</span>"
        )

        # Description
        if step.description:
            lines.append(
                f"<br/><span style='color:#AAA;'>"
                f"{html.escape(step.description)}</span>"
            )

        # Geo delta + cook time
        lines.append(
            f"<br/>Geo: <span style='color:{geo_color};'>"
            f"{html.escape(step.geo_delta)}</span>"
            f"&nbsp;&nbsp;|&nbsp;&nbsp;"
            f"Cook: {step.cook_time_ms:.1f}ms"
        )

        # Key parms
        if step.key_parms:
            parm_strs = [
                f"{html.escape(p['label'])}={html.escape(str(p['value']))}"
                for p in step.key_parms
            ]
            lines.append(
                f"<br/><span style='color:#7AB;'>Parms: "
                f"{', '.join(parm_strs)}</span>"
            )

        # Attrib delta
        if step.attrib_delta and step.attrib_delta != "no change":
            lines.append(
                f"<br/><span style='color:#B9B;'>Attribs: "
                f"{html.escape(step.attrib_delta)}</span>"
            )

        # Errors / warnings
        for err in step.errors:
            lines.append(
                f"<br/><span style='color:#E05555;'>Error: "
                f"{html.escape(err)}</span>"
            )
        for warn in step.warnings:
            lines.append(
                f"<br/><span style='color:#E8922E;'>Warning: "
                f"{html.escape(warn)}</span>"
            )

        lines.append("</div>")

    # Summary
    lines.append("<hr/>")
    lines.append(
        f"<p><b>Summary:</b> {html.escape(report.summary)}</p>"
    )

    # Bottleneck suggestion
    if report.bottleneck and report.bottleneck_pct > 80:
        bn_label = report.bottleneck.rsplit("/", 1)[-1]
        lines.append(
            f"<p style='color:#E8922E;'><b>Bottleneck:</b> "
            f"{html.escape(bn_label)} takes {report.bottleneck_pct:.0f}% "
            f"of cook time. Consider optimizing.</p>"
        )

    return "\n".join(lines)


# ============================================================================
# Plain text formatter
# ============================================================================

def format_trace_text(report: TraceReport) -> str:
    """Render a TraceReport as plain text for Claude interpretation."""
    if not report.steps:
        return f"No trace data: {report.summary}"

    lines: List[str] = []
    lines.append(f"Network Trace: {report.network_path}")
    lines.append("")

    for step in report.steps:
        pts_in = "?"
        pts_out = "?"
        if step.input_geo is not None:
            pts_in = str(step.input_geo.get("points", "?"))
        elif step.index == 1:
            pts_in = "0"
        if step.output_geo is not None:
            pts_out = str(step.output_geo.get("points", "?"))

        line = (
            f"{step.index}. {step.node_label} ({step.node_type}): "
            f"{pts_in} -> {pts_out} pts, {step.cook_time_ms:.1f}ms"
        )
        lines.append(line)

        # Key parms on next line if present
        if step.key_parms:
            parm_strs = [f"{p['name']}={p['value']}" for p in step.key_parms]
            lines.append(f"   parms: {', '.join(parm_strs)}")

        # Errors
        for err in step.errors:
            lines.append(f"   ERROR: {err}")

    lines.append("")
    lines.append(f"Summary: {report.summary}")
    return "\n".join(lines)
