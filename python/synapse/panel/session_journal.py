"""Session journal for SYNAPSE — append-only log of tool executions,
slash commands, and events.  Stored at $HIP/claude/journal.log and
searchable via /journal.  Feeds into scene memory.

Thread-safe, works with or without Houdini (hou).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
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
# Tool summarisation helpers
# ---------------------------------------------------------------------------
TOOL_SUMMARIES: Dict[str, Any] = {
    "houdini_create_node": lambda inp, res, err: (
        f"Created {inp.get('type', '')} at {inp.get('path', '')}"
    ),
    "houdini_set_parm": lambda inp, res, err: (
        f"Set {inp.get('path', '')}/{inp.get('parm', '')} = {inp.get('value', '')}"
    ),
    "houdini_connect_nodes": lambda inp, res, err: (
        f"Connected {inp.get('source', '')} -> {inp.get('destination', '')}"
    ),
    "houdini_delete_node": lambda inp, res, err: (
        f"Deleted {inp.get('path', '')}"
    ),
    "houdini_execute_python": lambda inp, res, err: (
        f"Ran Python ({len(inp.get('code', ''))} chars)"
    ),
    "houdini_execute_vex": lambda inp, res, err: (
        f"Ran VEX on {inp.get('node_path', '')}"
    ),
    "houdini_render": lambda inp, res, err: (
        f"Rendered {inp.get('rop_path', '')}"
    ),
    "houdini_hda_package": lambda inp, res, err: (
        f"Packaged HDA '{inp.get('name', '')}'"
    ),
}


def _summarize_tool(
    tool_name: str,
    tool_input: dict,
    result: Any,
    error: Optional[str],
) -> str:
    """Return a concise one-line summary for a tool execution."""
    summarizer = TOOL_SUMMARIES.get(tool_name)
    if summarizer is not None:
        try:
            summary = summarizer(tool_input, result, error)
        except Exception:
            summary = _truncate_input(tool_input)
    else:
        summary = _truncate_input(tool_input)

    if error:
        truncated_err = error[:60]
        summary = f"{summary} [FAILED: {truncated_err}]"

    return summary


def _truncate_input(tool_input: dict, max_len: int = 80) -> str:
    """JSON-dump *tool_input* and truncate to *max_len* characters."""
    try:
        raw = json.dumps(tool_input, ensure_ascii=False, default=str)
    except Exception:
        raw = str(tool_input)
    if len(raw) > max_len:
        return raw[: max_len - 3] + "..."
    return raw


def _resolve_log_dir() -> str:
    """Derive a log directory from the current Houdini scene or fall back to
    a temp directory.
    """
    if _HOU_AVAILABLE and hou is not None:
        try:
            hip_path = hou.hipFile.path()
            if hip_path:
                hip_dir = os.path.dirname(hip_path)
                if hip_dir and os.path.isdir(hip_dir):
                    return os.path.join(hip_dir, "claude")
        except Exception:
            pass
    return os.path.join(tempfile.gettempdir(), "synapse_journal")


# ---------------------------------------------------------------------------
# SessionJournal
# ---------------------------------------------------------------------------
class SessionJournal:
    """Append-only session journal.  One line per entry, plain text."""

    def __init__(self, log_dir: str = "") -> None:
        if not log_dir:
            log_dir = _resolve_log_dir()

        self._log_dir: str = log_dir
        os.makedirs(self._log_dir, exist_ok=True)

        self._log_path: str = os.path.join(self._log_dir, "journal.log")
        self._lock = threading.Lock()

        # In-memory counters
        self._tool_count: int = 0
        self._cmd_count: int = 0
        self._event_count: int = 0
        self._start_time: float = time.time()

    # -- internal helpers ---------------------------------------------------

    @staticmethod
    def _timestamp() -> str:
        return time.strftime("%H:%M:%S", time.localtime())

    def _append(self, line: str) -> None:
        """Thread-safe append of a single line to the journal file."""
        with self._lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except OSError as exc:
                print(
                    f"[synapse.journal] write error: {exc}",
                    file=sys.stderr,
                )

    # -- public API ---------------------------------------------------------

    def log_tool(
        self,
        tool_name: str,
        tool_input: dict,
        result: Any,
        error: Optional[str] = None,
        duration_ms: int = 0,
    ) -> None:
        """Log a tool execution."""
        summary = _summarize_tool(tool_name, tool_input, result, error)
        ts = self._timestamp()
        line = f"[{ts}] TOOL {tool_name}: {summary} ({duration_ms} ms)"
        self._append(line)
        self._tool_count += 1

    def log_command(self, command: str, result_summary: str = "") -> None:
        """Log a slash command execution."""
        ts = self._timestamp()
        line = f"[{ts}] CMD {command}: {result_summary}"
        self._append(line)
        self._cmd_count += 1

    def log_event(self, event_type: str, message: str) -> None:
        """Log a generic event (shot_login, diagnosis, preflight, error, etc.)."""
        ts = self._timestamp()
        line = f"[{ts}] {event_type.upper()} {message}"
        self._append(line)
        self._event_count += 1

    def search(self, query: str, limit: int = 50) -> List[str]:
        """Search journal entries matching *query* (case-insensitive).

        Returns matching lines most-recent-first.  If *query* is empty,
        returns the last *limit* entries.
        """
        if not query:
            return self.get_entries(limit)

        query_lower = query.lower()
        try:
            with self._lock:
                with open(self._log_path, "r", encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
        except FileNotFoundError:
            return []
        except OSError as exc:
            print(
                f"[synapse.journal] read error: {exc}",
                file=sys.stderr,
            )
            return []

        matched = [ln for ln in lines if query_lower in ln.lower()]
        matched.reverse()
        return matched[:limit]

    def get_session_summary(self) -> str:
        """Brief summary of the current session from in-memory counters."""
        elapsed_min = int((time.time() - self._start_time) / 60)
        return (
            f"Session: {elapsed_min}min, "
            f"{self._tool_count} tools, "
            f"{self._cmd_count} commands"
        )

    def get_entries(self, limit: int = 50) -> List[str]:
        """Return the last *limit* entries from the journal file."""
        try:
            with self._lock:
                with open(self._log_path, "r", encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
        except FileNotFoundError:
            return []
        except OSError as exc:
            print(
                f"[synapse.journal] read error: {exc}",
                file=sys.stderr,
            )
            return []

        return lines[-limit:]


# ---------------------------------------------------------------------------
# HTML formatter
# ---------------------------------------------------------------------------

def format_journal_html(entries: List[str], query: str = "") -> str:
    """Format journal entries as HTML for a QTextEdit widget.

    - Monospace font for log lines.
    - Matching *query* terms highlighted in bold orange.
    - Header line with counts.
    """
    parts: List[str] = [
        "<div style='font-family: monospace; font-size: 13px;'>"
    ]

    # Header
    if query:
        header = f"Found {len(entries)} entries matching '<b>{html_escape(query)}</b>'"
    else:
        header = f"Last {len(entries)} entries"
    parts.append(f"<p style='color: #aaa;'>{header}</p>")

    # Entries
    for entry in entries:
        safe = html_escape(entry)
        if query:
            # Case-insensitive highlight
            lower_safe = safe.lower()
            lower_q = query.lower()
            idx = 0
            highlighted: List[str] = []
            while idx < len(safe):
                pos = lower_safe.find(lower_q, idx)
                if pos == -1:
                    highlighted.append(safe[idx:])
                    break
                highlighted.append(safe[idx:pos])
                matched_text = safe[pos : pos + len(query)]
                highlighted.append(
                    f"<b style='color: #f0a030;'>{matched_text}</b>"
                )
                idx = pos + len(query)
            safe = "".join(highlighted)
        parts.append(f"<div style='margin: 2px 0;'>{safe}</div>")

    parts.append("</div>")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_journal_instance: Optional[SessionJournal] = None


def get_journal(log_dir: str = "") -> SessionJournal:
    """Get or create the singleton journal instance."""
    global _journal_instance
    if _journal_instance is None:
        _journal_instance = SessionJournal(log_dir)
    return _journal_instance
