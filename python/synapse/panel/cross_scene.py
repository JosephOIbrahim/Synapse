"""Cross-scene knowledge surfacing for SYNAPSE.

Scans project-level memory (decisions, materials, wedge results, warnings)
from other scenes and presents relevant insights when loading a new scene.

Thread-safe, works with or without Houdini (hou).
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from html import escape as html_escape
from typing import List, Optional

logger = logging.getLogger("synapse.cross_scene")

# ---------------------------------------------------------------------------
# Houdini import guard
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_SCENE_FILES = 20
MAX_INSIGHTS = 50
_SEVEN_DAYS_S = 7 * 24 * 3600

# Category constants
CAT_DECISION = "decision"
CAT_MATERIAL = "material"
CAT_WEDGE = "wedge"
CAT_RENDER = "render"
CAT_WARNING = "warning"
CAT_CONVENTION = "convention"

# ---------------------------------------------------------------------------
# Relevance keywords
# ---------------------------------------------------------------------------
_RENDER_MATERIAL_KW = re.compile(
    r"\b(render|material|shader|karma|arnold|mantra|materialx|texture)\b",
    re.IGNORECASE,
)
_WARNING_CRITICAL_KW = re.compile(
    r"\b(warning|critical|caution|error|broken|artifact)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Decision / warning extraction patterns
# ---------------------------------------------------------------------------
_DECISION_PREFIX = re.compile(
    r"^\s*[-*]?\s*(Decided|Decision|Approved|Standard)\s*:\s*",
    re.IGNORECASE,
)
_DECISION_CONTAINS = re.compile(
    r"\b(chose|agreed|using|prefer)\b",
    re.IGNORECASE,
)
_DECISION_SECTION = re.compile(
    r"^#{1,4}\s.*(Decisions|Conventions)",
    re.IGNORECASE,
)
_WARNING_PREFIX = re.compile(
    r"^\s*[-*]?\s*(Warning|Caution|Gotcha|Note)\s*:\s*",
    re.IGNORECASE,
)
_WARNING_CONTAINS = re.compile(
    r"\b(careful|avoid|don't|dont|causes)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class ProjectInsight:
    """A single piece of knowledge surfaced from project memory."""

    source_scene: str
    category: str  # decision, material, wedge, render, warning, convention
    summary: str
    detail: str
    timestamp: str
    relevance: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_job() -> Optional[str]:
    """Return $JOB from Houdini, or None."""
    if _HOU_AVAILABLE and hou is not None:
        try:
            val = hou.getenv("JOB") or hou.expandString("$JOB")
            if val and val != "$JOB":
                return val
        except Exception:
            pass
    return os.environ.get("JOB")


def _scene_name_from_path(path: str) -> str:
    """Extract a short scene/shot name from a file path."""
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return name


def _shared_prefix_length(a: str, b: str) -> int:
    """Count shared leading tokens (split on _ or -)."""
    if not a or not b:
        return 0
    parts_a = re.split(r"[_\-]", a.lower())
    parts_b = re.split(r"[_\-]", b.lower())
    count = 0
    for pa, pb in zip(parts_a, parts_b):
        if pa == pb:
            count += 1
        else:
            break
    return count


def _compute_relevance(
    insight: ProjectInsight,
    current_scene: str,
    now: float,
) -> float:
    """Score relevance 0.0-1.0 based on heuristics."""
    score = 0.0

    # Same shot/sequence name overlap
    if current_scene:
        if _shared_prefix_length(insight.source_scene, current_scene) >= 1:
            score += 0.3

    # Recency bonus (last 7 days)
    if insight.timestamp:
        try:
            ts = float(insight.timestamp)
            if (now - ts) < _SEVEN_DAYS_S:
                score += 0.2
        except (ValueError, TypeError):
            pass

    # Render / material keyword bonus
    text = f"{insight.summary} {insight.detail}"
    if _RENDER_MATERIAL_KW.search(text):
        score += 0.1

    # Warning / critical keyword bonus
    if _WARNING_CRITICAL_KW.search(text):
        score += 0.2

    return min(score, 1.0)


def _read_file(path: str) -> Optional[str]:
    """Read a UTF-8 text file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Extraction functions
# ---------------------------------------------------------------------------

def extract_decisions_from_md(content: str, source: str) -> List[ProjectInsight]:
    """Parse a markdown file for decision-like content.

    Looks for:
    - Lines starting with Decided:, Decision:, Approved:, Standard:
    - Lines containing chose, agreed, using, prefer
    - Section headers with Decisions or Conventions
    """
    insights: List[ProjectInsight] = []
    in_decision_section = False
    now_str = str(time.time())

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Check section headers
        if _DECISION_SECTION.match(stripped):
            in_decision_section = True
            continue

        # A new section header ends the decision section
        if in_decision_section and re.match(r"^#{1,4}\s", stripped):
            if not _DECISION_SECTION.match(stripped):
                in_decision_section = False
                continue

        matched = False
        category = CAT_DECISION

        # Prefix match (Decided:, Approved:, etc.)
        m = _DECISION_PREFIX.match(stripped)
        if m:
            summary = stripped[m.end():].strip()
            matched = True
            prefix_lower = m.group(1).lower()
            if prefix_lower == "standard":
                category = CAT_CONVENTION
        elif in_decision_section and stripped.startswith(("-", "*")):
            # Bullet inside a Decisions section
            summary = re.sub(r"^[-*]\s*", "", stripped)
            matched = True
        elif _DECISION_CONTAINS.search(stripped):
            summary = re.sub(r"^[-*]\s*", "", stripped)
            matched = True

        if matched and summary:
            insights.append(ProjectInsight(
                source_scene=source,
                category=category,
                summary=summary[:200],
                detail=stripped,
                timestamp=now_str,
            ))

    return insights


def extract_warnings_from_md(content: str, source: str) -> List[ProjectInsight]:
    """Parse a markdown file for warnings and gotchas.

    Looks for:
    - Lines starting with Warning:, Caution:, Gotcha:, Note:
    - Lines containing careful, avoid, don't, causes
    """
    insights: List[ProjectInsight] = []
    now_str = str(time.time())

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        matched = False
        summary = ""

        m = _WARNING_PREFIX.match(stripped)
        if m:
            summary = stripped[m.end():].strip()
            matched = True
        elif _WARNING_CONTAINS.search(stripped):
            summary = re.sub(r"^[-*]\s*", "", stripped)
            matched = True

        if matched and summary:
            insights.append(ProjectInsight(
                source_scene=source,
                category=CAT_WARNING,
                summary=summary[:200],
                detail=stripped,
                timestamp=now_str,
            ))

    return insights


def _extract_wedge_insights(wedge_dir: str) -> List[ProjectInsight]:
    """Scan a wedges directory for result files."""
    insights: List[ProjectInsight] = []
    if not os.path.isdir(wedge_dir):
        return insights

    now_str = str(time.time())
    try:
        entries = sorted(os.listdir(wedge_dir))
    except OSError:
        return insights

    for entry in entries[:MAX_SCENE_FILES]:
        path = os.path.join(wedge_dir, entry)
        if not os.path.isfile(path):
            continue
        content = _read_file(path)
        if not content:
            continue

        # Extract a one-line summary from the first non-empty line
        for raw_line in content.splitlines():
            first_line = raw_line.strip()
            if first_line:
                break
        else:
            first_line = entry

        insights.append(ProjectInsight(
            source_scene=_scene_name_from_path(entry),
            category=CAT_WEDGE,
            summary=first_line[:200],
            detail=content[:500],
            timestamp=now_str,
        ))

    return insights


# ---------------------------------------------------------------------------
# Main gathering function
# ---------------------------------------------------------------------------

def gather_project_context(
    project_dir: str,
    current_scene: str = "",
) -> List[ProjectInsight]:
    """Scan project memory for insights relevant to the current scene.

    Sources:
      a) Project memory at ``project_dir/claude/project.md``
      b) Session snapshots at ``project_dir/claude/sessions/*.md``
      c) Wedge results at ``project_dir/claude/wedges/``

    Returns a list of :class:`ProjectInsight` sorted by relevance (desc),
    capped at :data:`MAX_INSIGHTS`.
    """
    if not project_dir:
        project_dir = _resolve_job() or ""
    if not project_dir or not os.path.isdir(project_dir):
        logger.debug("gather_project_context: no valid project_dir, returning empty")
        return []

    claude_dir = os.path.join(project_dir, "claude")
    if not os.path.isdir(claude_dir):
        return []

    all_insights: List[ProjectInsight] = []
    now = time.time()

    # --- a) Project memory file ---
    for fname in ("project.md", "project.usd"):
        proj_path = os.path.join(claude_dir, fname)
        content = _read_file(proj_path)
        if content:
            source = "project"
            all_insights.extend(extract_decisions_from_md(content, source))
            all_insights.extend(extract_warnings_from_md(content, source))
            break  # prefer .md, fall back to .usd text content

    # --- b) Session snapshots from other scenes ---
    sessions_dir = os.path.join(claude_dir, "sessions")
    if os.path.isdir(sessions_dir):
        try:
            md_files = [
                f for f in os.listdir(sessions_dir)
                if f.endswith(".md") and os.path.isfile(os.path.join(sessions_dir, f))
            ]
        except OSError:
            md_files = []

        # Sort by modification time (newest first), cap at MAX_SCENE_FILES
        md_files_with_mtime = []
        for f in md_files:
            fpath = os.path.join(sessions_dir, f)
            try:
                mtime = os.path.getmtime(fpath)
            except OSError:
                mtime = 0
            md_files_with_mtime.append((f, fpath, mtime))
        md_files_with_mtime.sort(key=lambda x: x[2], reverse=True)

        for fname, fpath, mtime in md_files_with_mtime[:MAX_SCENE_FILES]:
            content = _read_file(fpath)
            if not content:
                continue
            scene_name = _scene_name_from_path(fname)
            mtime_str = str(mtime)

            for insight in extract_decisions_from_md(content, scene_name):
                insight.timestamp = mtime_str
                all_insights.append(insight)

            for insight in extract_warnings_from_md(content, scene_name):
                insight.timestamp = mtime_str
                all_insights.append(insight)

    # --- c) Wedge results ---
    wedges_dir = os.path.join(claude_dir, "wedges")
    all_insights.extend(_extract_wedge_insights(wedges_dir))

    # --- Score relevance and sort ---
    current_name = _scene_name_from_path(current_scene) if current_scene else ""
    for insight in all_insights:
        insight.relevance = _compute_relevance(insight, current_name, now)

    all_insights.sort(key=lambda i: i.relevance, reverse=True)
    return all_insights[:MAX_INSIGHTS]


# ---------------------------------------------------------------------------
# Formatting functions
# ---------------------------------------------------------------------------

_CATEGORY_COLORS = {
    CAT_DECISION: "#5B9BD5",
    CAT_MATERIAL: "#A5D6A7",
    CAT_WEDGE: "#CE93D8",
    CAT_RENDER: "#FFB74D",
    CAT_WARNING: "#EF9A9A",
    CAT_CONVENTION: "#80CBC4",
}


def format_project_context_html(
    insights: List[ProjectInsight],
    limit: int = 10,
) -> str:
    """Format insights as HTML for the SYNAPSE panel.

    Shows a header with counts, then top insights as bullet points
    with source scene and category badge.
    """
    if not insights:
        return "<p style='color:#888;'>No project context available.</p>"

    shown = insights[:limit]
    scenes = {i.source_scene for i in insights}
    header = (
        f"<p style='color:#AAA; margin:4px 0;'>"
        f"Project context loaded: <b>{len(insights)}</b> insight"
        f"{'s' if len(insights) != 1 else ''} from "
        f"<b>{len(scenes)}</b> scene{'s' if len(scenes) != 1 else ''}.</p>"
    )

    items: List[str] = []
    for ins in shown:
        color = _CATEGORY_COLORS.get(ins.category, "#888")
        badge = (
            f"<span style='background:{color}; color:#111; "
            f"padding:1px 6px; border-radius:3px; font-size:11px;'>"
            f"{html_escape(ins.category)}</span>"
        )
        source = html_escape(ins.source_scene)
        summary = html_escape(ins.summary)
        items.append(
            f"<li style='margin:3px 0;'>"
            f"{badge} {summary} "
            f"<span style='color:#666; font-size:11px;'>(from {source})</span>"
            f"</li>"
        )

    body = "<ul style='margin:4px 0; padding-left:18px;'>" + "".join(items) + "</ul>"
    return header + body


def format_project_context_for_prompt(
    insights: List[ProjectInsight],
    limit: int = 5,
) -> str:
    """Format insights as plain text for injection into Claude's system prompt.

    Kept concise -- this goes into every API call.
    """
    if not insights:
        return ""

    lines = ["Project Knowledge:"]
    for ins in insights[:limit]:
        lines.append(f"- {ins.summary} (from {ins.source_scene})")
    return "\n".join(lines)
