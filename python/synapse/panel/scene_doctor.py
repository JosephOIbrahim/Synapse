"""
SYNAPSE Scene Doctor -- Diagnostic engine for Houdini scenes.

Scans the scene for common problems (missing files, broken references,
cook errors, out-of-range parameters, render readiness, etc.) and offers
auto-fixes where possible.  All fixes are wrapped in a single undo group
so the artist can revert everything with one Ctrl-Z.

Designed to run on the main thread inside the Synapse panel.
Outside Houdini the module still imports cleanly -- diagnose_scene()
returns an empty report immediately.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# Performance threshold -- skip expensive checks when scene is large.
_LARGE_SCENE_THRESHOLD = 1000


# ============================================================================
# Data classes
# ============================================================================

@dataclass
class DiagnosticIssue:
    """A single problem found during scene diagnosis."""

    severity: str  # "critical", "error", "warning", "info"
    category: str  # "missing_file", "broken_ref", "bad_parm", "cook_error", ...
    node_path: str  # affected node
    message: str  # human-readable description
    fix_available: bool
    fix_description: str  # what the fix would do (empty if no fix)
    fix_fn: Optional[Callable] = None  # callable that fixes it


@dataclass
class DiagnosticReport:
    """Aggregated result of a full scene diagnosis."""

    issues: List[DiagnosticIssue] = field(default_factory=list)
    nodes_checked: int = 0
    time_elapsed: float = 0.0
    summary: str = ""


# ============================================================================
# Node gathering
# ============================================================================

def _get_all_nodes(scope: str) -> list:
    """Return nodes to inspect based on *scope*.

    Scopes:
        ``"all"``              -- every node in the scene
        ``"current_network"``  -- children of the active network editor pane
        ``"render"``           -- ROP nodes in /out + LOP nodes in /stage
        ``"materials"``        -- nodes whose type contains "material" or "shader"
    """
    if not _HOU_AVAILABLE:
        return []

    try:
        if scope == "current_network":
            pane = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
            if pane is not None:
                return list(pane.pwd().children())
            return []

        if scope == "render":
            nodes: list = []
            out = hou.node("/out")
            if out is not None:
                nodes.extend(out.allSubChildren())
            stage = hou.node("/stage")
            if stage is not None:
                nodes.extend(stage.allSubChildren())
            return nodes

        if scope == "materials":
            root = hou.node("/")
            if root is None:
                return []
            all_nodes = root.allSubChildren()
            return [
                n for n in all_nodes
                if any(
                    kw in n.type().name().lower()
                    for kw in ("material", "shader", "mtlx", "principled")
                )
            ]

        # scope == "all" (default)
        root = hou.node("/")
        if root is None:
            return []
        return list(root.allSubChildren())

    except Exception:
        return []


# ============================================================================
# Individual check functions
# ============================================================================

# Each returns List[DiagnosticIssue].  They must never raise -- one broken
# check should not prevent the others from running.

_FILE_PARM_NAMES = frozenset({
    "file", "filepath", "sopoutput", "filename", "filepath1",
    "picture", "vm_picture", "outputimage", "tex0",
    "shop_materialpath", "geo_file", "soppath",
})


def check_missing_files(nodes: list) -> List[DiagnosticIssue]:
    """Inspect file-referencing parameters for missing paths."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                for parm in node.parms():
                    try:
                        tmpl = parm.parmTemplate()
                        if tmpl.type() != hou.parmTemplateType.String:
                            continue
                        # Check by parm name or file_type tag.
                        name_lower = tmpl.name().lower()
                        tags = tmpl.tags()
                        is_file_parm = (
                            name_lower in _FILE_PARM_NAMES
                            or "file_type" in tags
                            or tags.get("filechooser_mode", "") != ""
                        )
                        if not is_file_parm:
                            continue
                        raw = parm.evalAsString()
                        if not raw or raw.isspace():
                            continue
                        expanded = hou.text.expandString(raw)
                        if not expanded or expanded.isspace():
                            continue
                        # Skip expressions / variables that don't resolve to real paths.
                        if expanded.startswith("op:") or expanded.startswith("opinput:"):
                            continue
                        if not os.path.exists(expanded):
                            issues.append(DiagnosticIssue(
                                severity="error",
                                category="missing_file",
                                node_path=node.path(),
                                message=f"File not found: {expanded} (parm: {tmpl.name()})",
                                fix_available=False,
                                fix_description="",
                            ))
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return issues


def check_broken_inputs(nodes: list) -> List[DiagnosticIssue]:
    """Check for required but unconnected inputs."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                min_inputs = node.type().minNumInputs()
                if min_inputs <= 0:
                    continue
                connected = len(node.inputConnections())
                if connected < min_inputs:
                    issues.append(DiagnosticIssue(
                        severity="error",
                        category="broken_ref",
                        node_path=node.path(),
                        message=(
                            f"Missing required inputs: {connected}/{min_inputs} connected"
                        ),
                        fix_available=False,
                        fix_description="",
                    ))
            except Exception:
                continue
    except Exception:
        pass
    return issues


def check_cook_errors(nodes: list) -> List[DiagnosticIssue]:
    """Collect cook errors and warnings from nodes."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                for err in node.errors():
                    issues.append(DiagnosticIssue(
                        severity="error",
                        category="cook_error",
                        node_path=node.path(),
                        message=f"Cook error: {err}",
                        fix_available=False,
                        fix_description="",
                    ))
                for warn in node.warnings():
                    issues.append(DiagnosticIssue(
                        severity="warning",
                        category="cook_error",
                        node_path=node.path(),
                        message=f"Cook warning: {warn}",
                        fix_available=False,
                        fix_description="",
                    ))
            except Exception:
                continue
    except Exception:
        pass
    return issues


def check_parameter_ranges(nodes: list) -> List[DiagnosticIssue]:
    """Flag parameters whose values exceed strict min/max bounds."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                for parm in node.parms():
                    try:
                        tmpl = parm.parmTemplate()
                        ptype = tmpl.type()
                        if ptype not in (
                            hou.parmTemplateType.Float,
                            hou.parmTemplateType.Int,
                        ):
                            continue

                        value = parm.eval()

                        # Check strict minimum.
                        if tmpl.minIsStrict():
                            min_val = tmpl.minValue()
                            if value < min_val:
                                def _clamp_min(p=parm, v=min_val):
                                    p.set(v)

                                issues.append(DiagnosticIssue(
                                    severity="warning",
                                    category="bad_parm",
                                    node_path=node.path(),
                                    message=(
                                        f"Parm '{tmpl.name()}' = {value} "
                                        f"below strict min {min_val}"
                                    ),
                                    fix_available=True,
                                    fix_description=f"Clamp to {min_val}",
                                    fix_fn=_clamp_min,
                                ))

                        # Check strict maximum.
                        if tmpl.maxIsStrict():
                            max_val = tmpl.maxValue()
                            if value > max_val:
                                def _clamp_max(p=parm, v=max_val):
                                    p.set(v)

                                issues.append(DiagnosticIssue(
                                    severity="warning",
                                    category="bad_parm",
                                    node_path=node.path(),
                                    message=(
                                        f"Parm '{tmpl.name()}' = {value} "
                                        f"above strict max {max_val}"
                                    ),
                                    fix_available=True,
                                    fix_description=f"Clamp to {max_val}",
                                    fix_fn=_clamp_max,
                                ))
                    except Exception:
                        continue
            except Exception:
                continue
    except Exception:
        pass
    return issues


def check_render_readiness() -> List[DiagnosticIssue]:
    """Check the render pipeline for cameras, ROPs, and output paths."""
    issues: List[DiagnosticIssue] = []
    if not _HOU_AVAILABLE:
        return issues

    try:
        # -- Cameras --
        has_camera = False
        obj = hou.node("/obj")
        if obj is not None:
            for child in obj.allSubChildren():
                try:
                    if child.type().name() in ("cam", "camera"):
                        has_camera = True
                        break
                except Exception:
                    continue

        if not has_camera:
            stage = hou.node("/stage")
            if stage is not None:
                for child in stage.allSubChildren():
                    try:
                        if child.type().name() in ("camera", "cam"):
                            has_camera = True
                            break
                    except Exception:
                        continue

        if not has_camera:
            def _create_default_camera():
                obj_net = hou.node("/obj")
                if obj_net is not None:
                    cam = obj_net.createNode("cam", "camera1")
                    cam.moveToGoodPosition()

            issues.append(DiagnosticIssue(
                severity="error",
                category="render_readiness",
                node_path="/obj",
                message="No camera found in /obj or /stage",
                fix_available=True,
                fix_description="Create default camera at /obj/camera1",
                fix_fn=_create_default_camera,
            ))

        # -- ROPs in /out --
        out = hou.node("/out")
        if out is not None:
            rops = out.children()
            if not rops:
                issues.append(DiagnosticIssue(
                    severity="warning",
                    category="render_readiness",
                    node_path="/out",
                    message="No ROP nodes found in /out",
                    fix_available=False,
                    fix_description="",
                ))
            else:
                for rop in rops:
                    try:
                        for pname in ("picture", "vm_picture", "outputimage"):
                            p = rop.parm(pname)
                            if p is not None:
                                val = p.evalAsString()
                                if val:
                                    out_dir = os.path.dirname(
                                        hou.text.expandString(val)
                                    )
                                    if out_dir and not os.path.isdir(out_dir):
                                        issues.append(DiagnosticIssue(
                                            severity="warning",
                                            category="render_readiness",
                                            node_path=rop.path(),
                                            message=(
                                                f"Output directory does not exist: "
                                                f"{out_dir} (parm: {pname})"
                                            ),
                                            fix_available=False,
                                            fix_description="",
                                        ))
                    except Exception:
                        continue

        # -- Karma LOPs in /stage: check camera parm --
        stage = hou.node("/stage")
        if stage is not None:
            for child in stage.allSubChildren():
                try:
                    if "karma" in child.type().name().lower():
                        cam_parm = child.parm("camera")
                        if cam_parm is not None:
                            cam_val = cam_parm.evalAsString()
                            if not cam_val or cam_val.isspace():
                                issues.append(DiagnosticIssue(
                                    severity="error",
                                    category="render_readiness",
                                    node_path=child.path(),
                                    message="Karma LOP has no camera set",
                                    fix_available=False,
                                    fix_description="",
                                ))
                except Exception:
                    continue

    except Exception:
        pass
    return issues


def check_display_flags(network_path: str) -> List[DiagnosticIssue]:
    """Check whether at least one node has the display flag in a SOP network."""
    issues: List[DiagnosticIssue] = []
    if not _HOU_AVAILABLE:
        return issues

    try:
        network = hou.node(network_path)
        if network is None:
            return issues
        # Only meaningful for SOP/OBJ contexts.
        children = network.children()
        if not children:
            return issues

        has_display = False
        last_node = None
        for child in children:
            try:
                if child.isDisplayFlagSet():
                    has_display = True
                    break
                last_node = child
            except AttributeError:
                # Not all node types have display flags.
                continue

        if not has_display and last_node is not None:
            def _set_display(n=last_node):
                n.setDisplayFlag(True)

            issues.append(DiagnosticIssue(
                severity="warning",
                category="display_flag",
                node_path=network_path,
                message="No display flag set in this network",
                fix_available=True,
                fix_description=f"Set display flag on {last_node.name()}",
                fix_fn=_set_display,
            ))
    except Exception:
        pass
    return issues


def check_empty_merges(nodes: list) -> List[DiagnosticIssue]:
    """Find merge nodes with gaps in their input connections."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                if node.type().name() != "merge":
                    continue
                inputs = node.inputs()
                if not inputs:
                    continue
                gaps = sum(1 for inp in inputs if inp is None)
                if gaps > 0:
                    issues.append(DiagnosticIssue(
                        severity="info",
                        category="empty_merge",
                        node_path=node.path(),
                        message=f"Merge has {gaps} disconnected input(s)",
                        fix_available=False,
                        fix_description="",
                    ))
            except Exception:
                continue
    except Exception:
        pass
    return issues


def check_unused_nodes(nodes: list) -> List[DiagnosticIssue]:
    """Find orphan nodes with no consumers and no flag set."""
    issues: List[DiagnosticIssue] = []
    try:
        for node in nodes:
            try:
                # Skip ROPs -- they are endpoints by design.
                if node.type().category().name() == "Driver":
                    continue
                if node.outputConnections():
                    continue
                # Has display or render flag?
                try:
                    if node.isDisplayFlagSet():
                        continue
                except AttributeError:
                    pass
                try:
                    if node.isRenderFlagSet():
                        continue
                except AttributeError:
                    pass
                issues.append(DiagnosticIssue(
                    severity="info",
                    category="unused_node",
                    node_path=node.path(),
                    message="Node has no outputs and no display/render flag",
                    fix_available=False,
                    fix_description="",
                ))
            except Exception:
                continue
    except Exception:
        pass
    return issues


# ============================================================================
# Main diagnosis entry point
# ============================================================================

def diagnose_scene(scope: str = "all") -> DiagnosticReport:
    """Run all diagnostic checks and compile a report.

    Parameters
    ----------
    scope : str
        ``"all"`` | ``"current_network"`` | ``"render"`` | ``"materials"``

    Returns
    -------
    DiagnosticReport
    """
    if not _HOU_AVAILABLE:
        return DiagnosticReport(
            summary="Houdini not available -- no diagnosis performed.",
        )

    start = time.perf_counter()
    all_issues: List[DiagnosticIssue] = []

    nodes = _get_all_nodes(scope)
    node_count = len(nodes)

    large_scene = node_count > _LARGE_SCENE_THRESHOLD

    # -- Always-run checks --
    all_issues.extend(check_missing_files(nodes))
    all_issues.extend(check_broken_inputs(nodes))
    all_issues.extend(check_cook_errors(nodes))
    all_issues.extend(check_empty_merges(nodes))

    # -- Render readiness (not filtered by node list) --
    if scope in ("all", "render"):
        all_issues.extend(check_render_readiness())

    # -- Display flags for SOP networks --
    if scope in ("all", "current_network"):
        try:
            seen_networks: set = set()
            for node in nodes:
                try:
                    parent = node.parent()
                    if parent is not None:
                        pp = parent.path()
                        if pp not in seen_networks:
                            seen_networks.add(pp)
                            # Only check SOP-level networks.
                            if parent.childTypeCategory() == hou.sopNodeTypeCategory():
                                all_issues.extend(check_display_flags(pp))
                except Exception:
                    continue
        except Exception:
            pass

    # -- Expensive checks (skipped for large scenes) --
    if large_scene:
        all_issues.append(DiagnosticIssue(
            severity="info",
            category="performance",
            node_path="/",
            message=(
                f"Scene has {node_count} nodes (>{_LARGE_SCENE_THRESHOLD}). "
                "Skipped: check_unused_nodes, check_parameter_ranges."
            ),
            fix_available=False,
            fix_description="",
        ))
    else:
        all_issues.extend(check_unused_nodes(nodes))
        all_issues.extend(check_parameter_ranges(nodes))

    elapsed = time.perf_counter() - start

    # Build summary string.
    counts: dict = {}
    for issue in all_issues:
        counts[issue.severity] = counts.get(issue.severity, 0) + 1
    parts = [
        f"{counts.get(s, 0)} {s}" for s in ("critical", "error", "warning", "info")
        if counts.get(s, 0) > 0
    ]
    total = len(all_issues)
    summary = f"Found {total} issue{'s' if total != 1 else ''}"
    if parts:
        summary += ": " + ", ".join(parts)
    summary += f" ({node_count} nodes checked in {elapsed:.2f}s)"

    return DiagnosticReport(
        issues=all_issues,
        nodes_checked=node_count,
        time_elapsed=elapsed,
        summary=summary,
    )


# ============================================================================
# Auto-fix application
# ============================================================================

def apply_fixes(issues: list) -> dict:
    """Apply all auto-fixable issues inside a single undo group.

    Parameters
    ----------
    issues : list[DiagnosticIssue]
        Typically ``report.issues`` from :func:`diagnose_scene`.

    Returns
    -------
    dict
        ``{"fixed": int, "failed": int, "skipped": int}``
    """
    result = {"fixed": 0, "failed": 0, "skipped": 0}

    fixable = [i for i in issues if i.fix_available and i.fix_fn is not None]
    if not fixable:
        result["skipped"] = len(issues)
        return result

    result["skipped"] = len(issues) - len(fixable)

    if _HOU_AVAILABLE:
        with hou.undos.group("SYNAPSE Scene Doctor Fixes"):
            for issue in fixable:
                try:
                    issue.fix_fn()
                    result["fixed"] += 1
                except Exception:
                    result["failed"] += 1
    else:
        # Outside Houdini -- just attempt the callables directly.
        for issue in fixable:
            try:
                issue.fix_fn()
                result["fixed"] += 1
            except Exception:
                result["failed"] += 1

    return result


# ============================================================================
# HTML report formatting
# ============================================================================

_SEVERITY_ICONS = {
    "critical": '<span style="color:#e74c3c; font-weight:bold;">&#10007;</span>',
    "error": '<span style="color:#e67e22; font-weight:bold;">&#10007;</span>',
    "warning": '<span style="color:#f1c40f;">&#9888;</span>',
    "info": '<span style="color:#95a5a6;">&#8505;</span>',
}

_SEVERITY_ORDER = ("critical", "error", "warning", "info")


def format_report_html(report: DiagnosticReport) -> str:
    """Format a :class:`DiagnosticReport` as HTML for display in the panel."""

    lines: List[str] = [
        '<div style="font-family: monospace; font-size: 13px;">',
        f'<p style="font-weight:bold;">{report.summary}</p>',
    ]

    if not report.issues:
        lines.append('<p style="color:#2ecc71;">No issues found.</p>')
        lines.append("</div>")
        return "\n".join(lines)

    fixable_count = sum(1 for i in report.issues if i.fix_available)
    if fixable_count:
        lines.append(
            f'<p style="color:#3498db;">'
            f"{fixable_count} issue{'s' if fixable_count != 1 else ''} "
            f"can be auto-fixed.</p>"
        )

    # Group by severity.
    grouped: dict = {}
    for issue in report.issues:
        grouped.setdefault(issue.severity, []).append(issue)

    for sev in _SEVERITY_ORDER:
        group = grouped.get(sev)
        if not group:
            continue
        icon = _SEVERITY_ICONS.get(sev, "")
        lines.append(
            f'<h4 style="margin-top:10px;">'
            f'{icon} {sev.upper()} ({len(group)})</h4>'
        )
        lines.append("<ul>")
        for issue in group:
            fix_tag = ""
            if issue.fix_available:
                fix_tag = (
                    ' <span style="color:#3498db; font-size:11px;">'
                    f"[fix: {issue.fix_description}]</span>"
                )
            lines.append(
                f"<li><b>{issue.node_path}</b> "
                f"<span style='color:#888;'>[{issue.category}]</span><br/>"
                f"{issue.message}{fix_tag}</li>"
            )
        lines.append("</ul>")

    lines.append("</div>")
    return "\n".join(lines)
