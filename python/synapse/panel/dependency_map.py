"""Dependency Map -- trace every external reference in a Houdini scene.

Scans for textures, geo caches, HDAs, USD layers, audio files and reports
their on-disk status (present / missing / modified).

Usage inside Houdini::

    from synapse.panel.dependency_map import scan_dependencies, format_deps_html
    report = scan_dependencies()          # scope="all"
    html   = format_deps_html(report)

Outside Houdini the module imports cleanly -- scan_dependencies() returns an
empty report immediately.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# -- Houdini import guard ---------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]

    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

# -- Performance caps --------------------------------------------------------
_MAX_NODES = 500
_MAX_DEPS = 200

# -- File extension sets -----------------------------------------------------
_TEXTURE_EXTS = frozenset({
    ".exr", ".hdr", ".tex", ".rat", ".png", ".jpg", ".jpeg",
    ".tif", ".tiff", ".tga", ".bmp", ".pic",
})
_GEO_EXTS = frozenset({
    ".bgeo", ".bgeo.sc", ".bgeo.gz", ".bgeo.lz4",
    ".abc", ".vdb", ".obj", ".ply", ".stl", ".fbx",
})
_AUDIO_EXTS = frozenset({".wav", ".mp3", ".aif", ".aiff", ".flac", ".ogg"})
_HDA_EXTS = frozenset({".hda", ".hdanc", ".hdalc", ".otl", ".otlnc", ".otllc"})

# -- Texture parameter heuristics -------------------------------------------
_TEXTURE_PARM_NAMES = frozenset({
    "map", "texture", "file", "filename", "basecolor_texture",
    "rough_texture", "normal_texture", "opaccolor_texture",
    "env_map", "reflectmap", "bumpmap", "displacemap",
    "baseColorMap", "roughnessMap", "normalMap", "metallicMap",
    "emissiveMap", "occlusionMap",
})


# ====================================================================
# Data classes
# ====================================================================

@dataclass
class Dependency:
    """Single external file reference found in the scene."""

    path: str  # resolved file path
    raw_path: str  # original path with $JOB/$HIP vars
    dep_type: str  # "texture", "geo_cache", "hda", "usd_layer", "audio", "other"
    status: str  # "ok", "missing", "modified", "outdated"
    node_path: str  # which node references this
    file_size: int  # bytes, 0 if missing
    modified_time: str  # ISO timestamp of last modification
    detail: str  # extra info


@dataclass
class DependencyReport:
    """Aggregated result of a full dependency scan."""

    dependencies: List[Dependency] = field(default_factory=list)
    by_type: Dict[str, int] = field(default_factory=dict)
    missing_count: int = 0
    total_size_bytes: int = 0
    summary: str = ""

    def _build_summary(self) -> None:
        """Recompute *by_type*, *missing_count*, *total_size_bytes*, *summary*."""
        type_counts: Dict[str, int] = {}
        type_sizes: Dict[str, int] = {}
        missing = 0
        total = 0
        for dep in self.dependencies:
            type_counts[dep.dep_type] = type_counts.get(dep.dep_type, 0) + 1
            type_sizes[dep.dep_type] = type_sizes.get(dep.dep_type, 0) + dep.file_size
            total += dep.file_size
            if dep.status == "missing":
                missing += 1

        self.by_type = type_counts
        self.missing_count = missing
        self.total_size_bytes = total

        parts: List[str] = []
        for dtype in ("texture", "geo_cache", "hda", "usd_layer", "audio", "other"):
            count = type_counts.get(dtype, 0)
            if count == 0:
                continue
            size = type_sizes.get(dtype, 0)
            type_missing = sum(
                1 for d in self.dependencies
                if d.dep_type == dtype and d.status == "missing"
            )
            type_outdated = sum(
                1 for d in self.dependencies
                if d.dep_type == dtype and d.status == "outdated"
            )
            label = dtype.replace("_", " ") + ("s" if count != 1 else "")
            info = f"{count} {label} ({_human_size(size)})"
            if type_missing:
                info += f", {type_missing} MISSING"
            if type_outdated:
                info += f", {type_outdated} outdated"
            parts.append(info)

        self.summary = " | ".join(parts) if parts else "No dependencies found"


# ====================================================================
# Helpers
# ====================================================================

def _human_size(nbytes: int) -> str:
    """Format bytes as human-readable string."""
    if nbytes == 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(nbytes) < 1024.0:
            return f"{nbytes:.1f} {unit}" if unit != "B" else f"{nbytes} B"
        nbytes /= 1024.0  # type: ignore[assignment]
    return f"{nbytes:.1f} PB"


def _file_stat(path: str) -> tuple:
    """Return (size_bytes, iso_mtime) or (0, '') if missing."""
    try:
        st = os.stat(path)
        mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
        return st.st_size, mtime
    except OSError:
        return 0, ""


def _expand_path(raw: str) -> str:
    """Expand Houdini variables in *raw* path."""
    if not _HOU_AVAILABLE:
        return raw
    try:
        return hou.text.expandString(raw)
    except Exception:
        return raw


def _classify_by_ext(path: str) -> str:
    """Guess dependency type from file extension."""
    lower = path.lower()
    # Handle compound extensions like .bgeo.sc
    for ext in (".bgeo.sc", ".bgeo.gz", ".bgeo.lz4"):
        if lower.endswith(ext):
            return "geo_cache"
    _, ext = os.path.splitext(lower)
    if ext in _TEXTURE_EXTS:
        return "texture"
    if ext in _GEO_EXTS:
        return "geo_cache"
    if ext in _AUDIO_EXTS:
        return "audio"
    if ext in _HDA_EXTS:
        return "hda"
    if ext in (".usd", ".usda", ".usdc", ".usdz"):
        return "usd_layer"
    return "other"


def _is_texture_parm(parm) -> bool:
    """Heuristic: does this parm look like a texture reference?"""
    name = parm.name().lower()
    if name in _TEXTURE_PARM_NAMES:
        return True
    # Check parm template file type
    try:
        tmpl = parm.parmTemplate()
        if hasattr(tmpl, "fileType"):
            ft = str(tmpl.fileType()).lower()
            if "image" in ft:
                return True
    except Exception:
        pass
    return False


def _make_dependency(raw_path: str, resolved: str, dep_type: str,
                     node_path: str) -> Dependency:
    """Build a Dependency with on-disk status."""
    exists = os.path.isfile(resolved)
    size, mtime = _file_stat(resolved) if exists else (0, "")
    status = "ok" if exists else "missing"

    detail = ""
    if exists and dep_type == "texture":
        detail = _human_size(size)
    elif not exists:
        detail = "file not found on disk"

    return Dependency(
        path=resolved,
        raw_path=raw_path,
        dep_type=dep_type,
        status=status,
        node_path=node_path,
        file_size=size,
        modified_time=mtime,
        detail=detail,
    )


# ====================================================================
# Scanners (one per dep type)
# ====================================================================

def _scan_file_parms(nodes: list, deps: List[Dependency],
                     scope_filter: Optional[str]) -> None:
    """Walk nodes looking for file-referencing parameters."""
    seen: set = set()
    for node in nodes:
        if len(deps) >= _MAX_DEPS:
            break
        try:
            parms = node.parms()
        except Exception:
            continue
        for parm in parms:
            if len(deps) >= _MAX_DEPS:
                break
            try:
                tmpl = parm.parmTemplate()
                if not hasattr(tmpl, "type"):
                    continue
                # Only look at string parms
                parm_type = tmpl.type()
                if str(parm_type) != "parmTemplateType.String":
                    continue
            except Exception:
                continue

            try:
                raw = parm.unexpandedString()
            except Exception:
                continue
            if not raw or len(raw) < 3:
                continue
            # Quick check: must look like a path
            if "/" not in raw and "\\" not in raw and "$" not in raw:
                continue

            resolved = _expand_path(raw)
            if not resolved or resolved == raw and "$" in raw:
                continue  # expansion failed

            dep_type = _classify_by_ext(resolved)
            if dep_type == "other" and _is_texture_parm(parm):
                dep_type = "texture"

            # Apply scope filter
            if scope_filter and dep_type != scope_filter:
                continue

            # Deduplicate by resolved path
            key = (resolved, node.path())
            if key in seen:
                continue
            seen.add(key)

            deps.append(_make_dependency(raw, resolved, dep_type, node.path()))


def _scan_hdas(deps: List[Dependency], scope_filter: Optional[str]) -> None:
    """Scan loaded HDA files for non-builtin HDAs."""
    if not _HOU_AVAILABLE:
        return
    if scope_filter and scope_filter != "hda":
        return
    if len(deps) >= _MAX_DEPS:
        return

    seen: set = set()
    try:
        hda_files = hou.hda.loadedFiles()
    except Exception:
        return

    hfs = ""
    try:
        hfs = hou.text.expandString("$HFS").replace("\\", "/").rstrip("/")
    except Exception:
        pass

    for hda_path in hda_files:
        if len(deps) >= _MAX_DEPS:
            break
        normalized = hda_path.replace("\\", "/")
        # Skip built-in HDAs shipped with Houdini
        if hfs and normalized.startswith(hfs):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)

        deps.append(_make_dependency(hda_path, normalized, "hda", "/"))


def _scan_usd_layers(nodes: list, deps: List[Dependency],
                     scope_filter: Optional[str]) -> None:
    """Scan LOP nodes for USD layer references."""
    if not _HOU_AVAILABLE:
        return
    if scope_filter and scope_filter != "usd_layer":
        return

    seen: set = set()
    for node in nodes:
        if len(deps) >= _MAX_DEPS:
            break
        try:
            type_name = node.type().name()
        except Exception:
            continue
        if type_name not in ("sublayer", "reference", "payload",
                             "sublayer::2.0", "reference::2.0", "payload::2.0"):
            continue
        for parm_name in ("filepath1", "filepath", "file"):
            parm = node.parm(parm_name)
            if parm is None:
                continue
            try:
                raw = parm.unexpandedString()
            except Exception:
                continue
            if not raw or len(raw) < 3:
                continue
            resolved = _expand_path(raw)
            key = (resolved, node.path())
            if key in seen:
                continue
            seen.add(key)
            deps.append(_make_dependency(raw, resolved, "usd_layer", node.path()))


# ====================================================================
# Public API
# ====================================================================

_SCOPE_MAP = {
    "textures": "texture",
    "geo": "geo_cache",
    "hda": "hda",
    "usd": "usd_layer",
    "all": None,
}


def scan_dependencies(scope: str = "all") -> DependencyReport:
    """Scan the current Houdini scene for external file dependencies.

    Parameters
    ----------
    scope : str
        One of ``"all"``, ``"textures"``, ``"geo"``, ``"hda"``, ``"usd"``.

    Returns
    -------
    DependencyReport
        Populated report with all found dependencies.
    """
    report = DependencyReport()

    if not _HOU_AVAILABLE:
        report.summary = "Houdini not available -- no dependencies scanned"
        return report

    scope_filter = _SCOPE_MAP.get(scope)
    if scope != "all" and scope not in _SCOPE_MAP:
        report.summary = f"Unknown scope '{scope}' -- use all/textures/geo/hda/usd"
        return report

    # Gather nodes (capped at _MAX_NODES)
    try:
        root = hou.node("/")
        all_nodes = root.allSubChildren()[:_MAX_NODES]
    except Exception:
        report.summary = "Failed to enumerate scene nodes"
        return report

    deps: List[Dependency] = []

    _scan_file_parms(all_nodes, deps, scope_filter)
    _scan_hdas(deps, scope_filter)
    _scan_usd_layers(all_nodes, deps, scope_filter)

    report.dependencies = deps
    report._build_summary()
    return report


# ====================================================================
# Formatters
# ====================================================================

_STATUS_ICONS = {
    "ok": '<span style="color:#4CAF50;">&#10004;</span>',       # green check
    "missing": '<span style="color:#F44336;">&#10008;</span>',   # red X
    "modified": '<span style="color:#FFC107;">&#9888;</span>',   # yellow warning
    "outdated": '<span style="color:#FFC107;">&#9888;</span>',   # yellow warning
}

_STATUS_TEXT = {
    "ok": "[OK]",
    "missing": "[MISSING]",
    "modified": "[MODIFIED]",
    "outdated": "[OUTDATED]",
}


def format_deps_html(report: DependencyReport) -> str:
    """Format a DependencyReport as HTML for panel display.

    Groups dependencies by type with status icons.
    """
    if not report.dependencies:
        return "<p style='color:#999;'>No external dependencies found.</p>"

    parts: List[str] = []
    parts.append("<div style='font-family:monospace; font-size:13px;'>")

    # Group by type
    grouped: Dict[str, List[Dependency]] = {}
    for dep in report.dependencies:
        grouped.setdefault(dep.dep_type, []).append(dep)

    type_labels = {
        "texture": "Textures",
        "geo_cache": "Geo Caches",
        "hda": "HDAs",
        "usd_layer": "USD Layers",
        "audio": "Audio",
        "other": "Other",
    }

    for dtype in ("texture", "geo_cache", "hda", "usd_layer", "audio", "other"):
        deps_list = grouped.get(dtype, [])
        if not deps_list:
            continue
        label = type_labels.get(dtype, dtype)
        total_size = sum(d.file_size for d in deps_list)
        parts.append(
            f"<h3 style='margin:8px 0 4px 0; color:#DDD;'>"
            f"{label} ({len(deps_list)}) &mdash; {_human_size(total_size)}</h3>"
        )
        parts.append("<table style='width:100%; border-collapse:collapse;'>")
        for dep in deps_list:
            icon = _STATUS_ICONS.get(dep.status, "")
            basename = os.path.basename(dep.path) if dep.path else dep.raw_path
            size_str = _human_size(dep.file_size) if dep.file_size else ""
            node_display = dep.node_path if len(dep.node_path) < 40 else (
                "..." + dep.node_path[-37:]
            )
            detail_str = f" &mdash; {dep.detail}" if dep.detail else ""
            parts.append(
                f"<tr style='border-bottom:1px solid #444;'>"
                f"<td style='padding:2px 6px;'>{icon}</td>"
                f"<td style='padding:2px 6px; color:#CCC;'>{basename}</td>"
                f"<td style='padding:2px 6px; color:#999;'>{size_str}</td>"
                f"<td style='padding:2px 6px; color:#888;'>{node_display}"
                f"{detail_str}</td>"
                f"</tr>"
            )
        parts.append("</table>")

    # Summary footer
    parts.append(
        f"<p style='margin-top:10px; color:#AAA; border-top:1px solid #555; "
        f"padding-top:6px;'>{report.summary}</p>"
    )
    parts.append("</div>")
    return "\n".join(parts)


def format_deps_text(report: DependencyReport) -> str:
    """Format a DependencyReport as plain text for Claude interpretation."""
    if not report.dependencies:
        return "No external dependencies found."

    lines: List[str] = []
    lines.append(f"=== Dependency Report ({len(report.dependencies)} files) ===")
    lines.append("")

    grouped: Dict[str, List[Dependency]] = {}
    for dep in report.dependencies:
        grouped.setdefault(dep.dep_type, []).append(dep)

    for dtype in ("texture", "geo_cache", "hda", "usd_layer", "audio", "other"):
        deps_list = grouped.get(dtype, [])
        if not deps_list:
            continue
        lines.append(f"--- {dtype.upper().replace('_', ' ')} ({len(deps_list)}) ---")
        for dep in deps_list:
            status = _STATUS_TEXT.get(dep.status, f"[{dep.status.upper()}]")
            size_str = _human_size(dep.file_size) if dep.file_size else "0 B"
            lines.append(f"  {status} {dep.path}")
            lines.append(f"         raw: {dep.raw_path}")
            lines.append(f"         node: {dep.node_path}  size: {size_str}")
            if dep.detail:
                lines.append(f"         detail: {dep.detail}")
        lines.append("")

    lines.append(f"Summary: {report.summary}")
    if report.missing_count:
        lines.append(f"WARNING: {report.missing_count} missing file(s)")
    lines.append(f"Total size: {_human_size(report.total_size_bytes)}")
    return "\n".join(lines)
