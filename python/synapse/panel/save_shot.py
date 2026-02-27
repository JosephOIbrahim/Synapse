"""Save Shot -- capture a complete session snapshot for SYNAPSE.

Captures conversation highlights, tool actions, scene state, and session
metadata into a markdown file at $HIP/claude/sessions/.  Provides /save-shot
and /shots commands for the panel.

Thread-safe, works with or without Houdini (hou).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from html import escape as html_escape
from typing import Any, Dict, List, Optional

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
# Data model
# ---------------------------------------------------------------------------
@dataclass
class ShotSnapshot:
    """Complete context snapshot of a SYNAPSE session."""

    hip_file: str
    timestamp: str  # ISO format
    note: str  # user-provided note
    session_duration_min: int
    tool_count: int
    command_count: int
    node_count: int
    scene_summary: str  # brief scene state
    conversation_highlights: list = field(default_factory=list)  # max 10
    tool_actions: list = field(default_factory=list)  # max 20
    memory_stage: str = "flat"  # flat/structured/composed
    save_path: str = ""  # where the snapshot was saved


# ---------------------------------------------------------------------------
# Scene helpers
# ---------------------------------------------------------------------------
def _get_hip_file() -> str:
    """Return the current HIP file path, or a fallback."""
    if _HOU_AVAILABLE and hou is not None:
        try:
            return hou.hipFile.path()
        except Exception:
            pass
    return "untitled.hip"


def _get_node_count() -> int:
    """Count all nodes in the scene."""
    if _HOU_AVAILABLE and hou is not None:
        try:
            return len(hou.node("/").allSubChildren())
        except Exception:
            pass
    return 0


def _get_scene_summary() -> str:
    """Build a brief scene state summary."""
    if not _HOU_AVAILABLE or hou is None:
        return "No Houdini session available"

    parts: List[str] = []
    try:
        hip = hou.hipFile.path()
        parts.append(f"File: {os.path.basename(hip)}")
    except Exception:
        parts.append("File: unknown")

    try:
        frame = hou.frame()
        frame_range = hou.playbar.frameRange()
        parts.append(f"Frame: {int(frame)} ({int(frame_range[0])}-{int(frame_range[1])})")
    except Exception:
        pass

    # Count nodes by network type
    try:
        root = hou.node("/")
        children = root.children()
        for child in children:
            sub_count = len(child.allSubChildren())
            if sub_count > 0:
                parts.append(f"{child.path()}: {sub_count} nodes")
    except Exception:
        pass

    return " | ".join(parts) if parts else "Empty scene"


def _detect_memory_stage() -> str:
    """Detect the current memory evolution stage."""
    if not _HOU_AVAILABLE or hou is None:
        return "flat"

    try:
        hip_dir = os.path.dirname(hou.hipFile.path())
        claude_dir = os.path.join(hip_dir, "claude")
        usd_path = os.path.join(claude_dir, "memory.usd")
        md_path = os.path.join(claude_dir, "memory.md")

        if os.path.exists(usd_path):
            # Check for composition arcs (charizard)
            try:
                with open(usd_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
                if "references" in content or "sublayers" in content:
                    return "composed"
            except Exception:
                pass
            return "structured"
        elif os.path.exists(md_path):
            return "flat"
    except Exception:
        pass
    return "flat"


# ---------------------------------------------------------------------------
# Conversation extraction
# ---------------------------------------------------------------------------
def _extract_highlights(
    messages: Optional[List[Dict[str, Any]]], max_count: int = 10
) -> List[str]:
    """Extract conversation highlights from message history.

    Filters out tool_result messages and keeps only substantive exchanges.
    Returns at most *max_count* highlights.
    """
    if not messages:
        return []

    highlights: List[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Skip tool_result messages
        if role == "tool_result":
            continue
        # Skip tool_use blocks (list-of-dicts content)
        if isinstance(content, list):
            # Extract text blocks only
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            content = " ".join(text_parts)

        if not isinstance(content, str) or not content.strip():
            continue

        # Skip very short or purely structural messages
        stripped = content.strip()
        if len(stripped) < 20:
            continue

        # Truncate to a reasonable preview length
        preview = stripped[:200]
        if len(stripped) > 200:
            preview += "..."

        prefix = "User" if role == "user" else "SYNAPSE"
        highlights.append(f"[{prefix}] {preview}")

    # Keep the most recent highlights up to max_count
    return highlights[-max_count:]


# ---------------------------------------------------------------------------
# Tool actions from journal
# ---------------------------------------------------------------------------
def _get_tool_actions(max_count: int = 20) -> List[str]:
    """Get recent tool actions from the session journal."""
    try:
        from synapse.panel.session_journal import get_journal

        journal = get_journal()
        entries = journal.get_entries(limit=100)
        # Filter for TOOL entries
        tool_entries = [e for e in entries if " TOOL " in e]
        return tool_entries[-max_count:]
    except Exception:
        return []


def _get_session_stats() -> Dict[str, int]:
    """Get session duration and counts from the journal."""
    stats = {"duration_min": 0, "tool_count": 0, "command_count": 0}
    try:
        from synapse.panel.session_journal import get_journal

        journal = get_journal()
        elapsed = int((time.time() - journal._start_time) / 60)
        stats["duration_min"] = elapsed
        stats["tool_count"] = journal._tool_count
        stats["command_count"] = journal._cmd_count
    except Exception:
        pass
    return stats


# ---------------------------------------------------------------------------
# Resolve sessions directory
# ---------------------------------------------------------------------------
def _resolve_sessions_dir(claude_dir: str = "") -> str:
    """Derive the sessions directory from $HIP/claude/sessions/ or fallback."""
    if claude_dir:
        return os.path.join(claude_dir, "sessions")

    if _HOU_AVAILABLE and hou is not None:
        try:
            hip_path = hou.hipFile.path()
            if hip_path:
                hip_dir = os.path.dirname(hip_path)
                if hip_dir and os.path.isdir(hip_dir):
                    return os.path.join(hip_dir, "claude", "sessions")
        except Exception:
            pass
    return os.path.join(tempfile.gettempdir(), "synapse_sessions")


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------
def save_shot(
    note: str = "",
    messages: Optional[List[Dict[str, Any]]] = None,
    login_data: Optional[Dict[str, Any]] = None,
) -> ShotSnapshot:
    """Create a complete session snapshot and write it to disk.

    Parameters
    ----------
    note : str
        User-provided note describing what was accomplished.
    messages : list, optional
        Conversation message history for highlight extraction.
    login_data : dict, optional
        Shot login data (currently unused, reserved for future context).

    Returns
    -------
    ShotSnapshot
        The completed snapshot with save_path populated.
    """
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()

    # Gather scene state
    hip_file = _get_hip_file()
    node_count = _get_node_count()
    scene_summary = _get_scene_summary()
    memory_stage = _detect_memory_stage()

    # Extract conversation highlights
    highlights = _extract_highlights(messages, max_count=10)

    # Get tool actions from journal
    tool_actions = _get_tool_actions(max_count=20)

    # Get session stats
    stats = _get_session_stats()

    # Build snapshot
    snapshot = ShotSnapshot(
        hip_file=hip_file,
        timestamp=timestamp,
        note=note if note else "(no note)",
        session_duration_min=stats["duration_min"],
        tool_count=stats["tool_count"],
        command_count=stats["command_count"],
        node_count=node_count,
        scene_summary=scene_summary,
        conversation_highlights=highlights,
        tool_actions=tool_actions,
        memory_stage=memory_stage,
    )

    # Write to disk
    sessions_dir = _resolve_sessions_dir()
    os.makedirs(sessions_dir, exist_ok=True)

    filename = now.strftime("%Y-%m-%d_%H%M") + ".md"
    save_path = os.path.join(sessions_dir, filename)

    md_content = format_snapshot_md(snapshot)
    with open(save_path, "w", encoding="utf-8") as fh:
        fh.write(md_content)

    snapshot.save_path = save_path
    return snapshot


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------
def format_snapshot_md(snapshot: ShotSnapshot) -> str:
    """Format a snapshot as markdown for the saved file."""
    lines: List[str] = []

    # Header
    lines.append(f"# Session Snapshot -- {snapshot.timestamp}")
    lines.append("")
    lines.append(f"**File:** {snapshot.hip_file}")
    lines.append(f"**Note:** {snapshot.note}")
    lines.append(
        f"**Duration:** {snapshot.session_duration_min}min | "
        f"**Tools:** {snapshot.tool_count} | "
        f"**Commands:** {snapshot.command_count}"
    )
    lines.append(f"**Memory:** {snapshot.memory_stage}")
    lines.append("")

    # Scene State
    lines.append("## Scene State")
    lines.append("")
    lines.append(f"{snapshot.scene_summary}")
    lines.append(f"**Nodes:** {snapshot.node_count}")
    lines.append("")

    # Conversation Highlights
    lines.append("## Conversation Highlights")
    lines.append("")
    if snapshot.conversation_highlights:
        for highlight in snapshot.conversation_highlights:
            lines.append(f"- {highlight}")
    else:
        lines.append("- (no highlights captured)")
    lines.append("")

    # Tool Actions
    lines.append("## Tool Actions")
    lines.append("")
    if snapshot.tool_actions:
        for action in snapshot.tool_actions:
            lines.append(f"- {action}")
    else:
        lines.append("- (no tool actions recorded)")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML formatting for panel display
# ---------------------------------------------------------------------------
def format_save_html(snapshot: ShotSnapshot) -> str:
    """HTML confirmation for the panel chat display showing what was saved."""
    note_html = html_escape(snapshot.note)
    path_html = html_escape(snapshot.save_path)
    scene_html = html_escape(snapshot.scene_summary)

    highlight_count = len(snapshot.conversation_highlights)
    action_count = len(snapshot.tool_actions)

    return (
        '<div style="padding:8px; border-left:3px solid #4a9; background:#2a2a2a;">'
        '<div style="font-weight:bold; color:#4a9; margin-bottom:6px;">'
        "Session Snapshot Saved</div>"
        f'<div style="color:#ccc; margin:2px 0;"><b>Note:</b> {note_html}</div>'
        f'<div style="color:#aaa; margin:2px 0;">'
        f"Duration: {snapshot.session_duration_min}min | "
        f"Tools: {snapshot.tool_count} | "
        f"Commands: {snapshot.command_count} | "
        f"Nodes: {snapshot.node_count}"
        "</div>"
        f'<div style="color:#aaa; margin:2px 0;">'
        f"Highlights: {highlight_count} | "
        f"Actions: {action_count} | "
        f"Memory: {snapshot.memory_stage}"
        "</div>"
        f'<div style="color:#888; margin:2px 0;">Scene: {scene_html}</div>'
        f'<div style="color:#666; font-size:11px; margin-top:4px;">'
        f"Saved to: {path_html}</div>"
        "</div>"
    )


# ---------------------------------------------------------------------------
# List / search snapshots
# ---------------------------------------------------------------------------
def list_snapshots(claude_dir: str = "") -> List[Dict[str, str]]:
    """List all saved snapshots in $HIP/claude/sessions/.

    Returns list of {filename, timestamp, note_preview} dicts, most recent first.
    """
    sessions_dir = _resolve_sessions_dir(claude_dir)
    if not os.path.isdir(sessions_dir):
        return []

    results: List[Dict[str, str]] = []
    try:
        for filename in os.listdir(sessions_dir):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(sessions_dir, filename)
            note_preview = ""
            timestamp = ""

            try:
                with open(filepath, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line.startswith("# Session Snapshot"):
                            # Extract timestamp from header
                            parts = line.split("--", 1)
                            if len(parts) > 1:
                                timestamp = parts[1].strip()
                        elif line.startswith("**Note:**"):
                            note_preview = line.replace("**Note:**", "").strip()
                            break
            except OSError:
                continue

            results.append(
                {
                    "filename": filename,
                    "timestamp": timestamp,
                    "note_preview": note_preview[:80],
                }
            )
    except OSError:
        return []

    # Sort by filename descending (filenames are date-based)
    results.sort(key=lambda x: x["filename"], reverse=True)
    return results


def format_snapshots_html(snapshots: List[Dict[str, str]]) -> str:
    """HTML listing of saved snapshots for /shots command."""
    if not snapshots:
        return (
            '<div style="color:#888; padding:12px; text-align:center;">'
            "No snapshots saved yet. Use /save-shot to capture a session."
            "</div>"
        )

    count = len(snapshots)
    parts: List[str] = [
        f'<div style="padding:4px 0; color:#aaa; font-size:13px;">'
        f'{count} snapshot{"s" if count != 1 else ""}</div>'
    ]

    for snap in snapshots:
        filename_html = html_escape(snap["filename"])
        ts_html = html_escape(snap.get("timestamp", ""))
        note_html = html_escape(snap.get("note_preview", "(no note)"))

        parts.append(
            f'<div style="padding:6px 0; border-bottom:1px solid #3C3C3C;">'
            f'<div style="font-weight:bold; color:#E0E0E0;">{filename_html}</div>'
            f'<div style="color:#777; font-size:11px;">{ts_html}</div>'
            f'<div style="color:#999; font-style:italic; font-size:12px; '
            f'margin-top:2px;">{note_html}</div>'
            f"</div>"
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------
def parse_save_command(text: str) -> Dict[str, str]:
    """Parse a /save-shot or /shots command string.

    /save-shot finished lookdev  -> {"action": "save", "note": "finished lookdev"}
    /save-shot                   -> {"action": "save", "note": ""}
    /shots                       -> {"action": "list"}
    /shots search lookdev        -> {"action": "search", "query": "lookdev"}
    """
    text = text.strip()

    # Handle /shots first (before /save-shot, since /save-shot contains "shot")
    if text.lower().startswith("/shots"):
        remainder = text[6:].strip()
        if not remainder:
            return {"action": "list"}
        lower_rem = remainder.lower()
        if lower_rem.startswith("search "):
            return {"action": "search", "query": remainder[7:].strip()}
        # Treat anything else as a search query
        return {"action": "search", "query": remainder}

    # Handle /save-shot
    if text.lower().startswith("/save-shot"):
        remainder = text[10:].strip()
        return {"action": "save", "note": remainder}

    # Fallback -- treat as save with the whole text as note
    return {"action": "save", "note": text}
