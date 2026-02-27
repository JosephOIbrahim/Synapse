"""Conversation Bookmarks for SYNAPSE.

Artists can bookmark important moments in their conversation with SYNAPSE.
Bookmarks persist in scene memory ($HIP/claude/bookmarks.json) so other
artists opening the same scene can see previous bookmarks.
"""

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional

# Houdini import guard
_HOU_AVAILABLE = False
try:
    import hou
    _HOU_AVAILABLE = True
except ImportError:
    hou = None

# Session ID generated once at module load
_SESSION_ID: str = datetime.now().strftime("%Y%m%d_%H%M")


@dataclass
class Bookmark:
    """A single conversation bookmark."""

    id: str
    label: str
    timestamp: str
    message_index: int
    message_preview: str
    tags: list = field(default_factory=list)
    session_id: str = ""


class BookmarkManager:
    """Manages conversation bookmarks with JSON persistence."""

    def __init__(self, storage_dir: str = "") -> None:
        self._lock = threading.Lock()
        self._bookmarks: list[Bookmark] = []

        if storage_dir:
            self._storage_dir = storage_dir
        elif _HOU_AVAILABLE:
            try:
                hip_path = hou.hipFile.path()
                hip_dir = os.path.dirname(hip_path)
                self._storage_dir = os.path.join(hip_dir, "claude")
            except Exception:
                self._storage_dir = os.path.join(tempfile.gettempdir(), "synapse_bookmarks")
        else:
            self._storage_dir = os.path.join(tempfile.gettempdir(), "synapse_bookmarks")

        self._filepath = os.path.join(self._storage_dir, "bookmarks.json")
        self._load()

    def add(
        self,
        label: str,
        message_index: int,
        message_preview: str,
        tags: list | None = None,
    ) -> Bookmark:
        """Create and persist a new bookmark."""
        bookmark = Bookmark(
            id=f"bm_{int(time.time() * 1000)}",
            label=label,
            timestamp=datetime.now(timezone.utc).isoformat(),
            message_index=message_index,
            message_preview=message_preview[:100],
            tags=tags if tags is not None else [],
            session_id=_SESSION_ID,
        )
        with self._lock:
            self._bookmarks.append(bookmark)
            self._save()
        return bookmark

    def remove(self, bookmark_id: str) -> bool:
        """Remove a bookmark by ID. Returns True if found and removed."""
        with self._lock:
            before = len(self._bookmarks)
            self._bookmarks = [b for b in self._bookmarks if b.id != bookmark_id]
            if len(self._bookmarks) < before:
                self._save()
                return True
            return False

    def search(self, query: str) -> list[Bookmark]:
        """Case-insensitive search across label, message_preview, and tags."""
        q = query.lower()
        results = []
        for b in self._bookmarks:
            haystack = f"{b.label} {b.message_preview} {' '.join(b.tags)}".lower()
            if q in haystack:
                results.append(b)
        results.sort(key=lambda b: b.timestamp, reverse=True)
        return results

    def get_all(self) -> list[Bookmark]:
        """Return all bookmarks, most recent first."""
        return sorted(self._bookmarks, key=lambda b: b.timestamp, reverse=True)

    def get_by_session(self, session_id: str = "") -> list[Bookmark]:
        """Return bookmarks from a specific session (default: current)."""
        sid = session_id if session_id else _SESSION_ID
        results = [b for b in self._bookmarks if b.session_id == sid]
        results.sort(key=lambda b: b.timestamp, reverse=True)
        return results

    def _save(self) -> None:
        """Write bookmarks to disk (caller must hold self._lock)."""
        os.makedirs(self._storage_dir, exist_ok=True)
        data = [asdict(b) for b in self._bookmarks]
        with open(self._filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)

    def _load(self) -> None:
        """Read bookmarks from disk, tolerating missing or corrupt files."""
        with self._lock:
            try:
                with open(self._filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._bookmarks = [Bookmark(**entry) for entry in data]
            except (FileNotFoundError, json.JSONDecodeError, TypeError, KeyError):
                self._bookmarks = []


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: Optional[BookmarkManager] = None


def get_bookmark_manager(storage_dir: str = "") -> BookmarkManager:
    """Return the singleton BookmarkManager instance."""
    global _manager
    if _manager is None:
        _manager = BookmarkManager(storage_dir)
    return _manager


# ---------------------------------------------------------------------------
# HTML formatting
# ---------------------------------------------------------------------------

def _escape_html(text: str) -> str:
    """Minimal HTML escaping."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def format_bookmarks_html(bookmarks: list[Bookmark], query: str = "") -> str:
    """Format bookmarks for display in the panel's QTextEdit."""
    if not bookmarks:
        return (
            '<div style="color:#888; padding:12px; text-align:center;">'
            "No bookmarks yet. Use /bookmark to save a moment."
            "</div>"
        )

    count = len(bookmarks)
    if query:
        header = f"{count} bookmark{'s' if count != 1 else ''} matching '{_escape_html(query)}'"
    else:
        header = f"{count} bookmark{'s' if count != 1 else ''}"

    parts = [f'<div style="padding:4px 0; color:#aaa; font-size:13px;">{header}</div>']

    for b in bookmarks:
        label_html = _escape_html(b.label)
        preview_html = _escape_html(b.message_preview)

        # Highlight matching terms
        if query:
            q_esc = _escape_html(query)
            label_html = _highlight(label_html, q_esc)
            preview_html = _highlight(preview_html, q_esc)

        # Tags as small badges
        tags_html = ""
        if b.tags:
            badges = []
            for tag in b.tags:
                tag_text = _escape_html(tag)
                if query:
                    tag_text = _highlight(tag_text, _escape_html(query))
                badges.append(
                    f'<span style="background:#444; color:#ccc; padding:1px 6px; '
                    f'border-radius:3px; font-size:11px; margin-right:4px;">{tag_text}</span>'
                )
            tags_html = f'<div style="margin-top:2px;">{"".join(badges)}</div>'

        # Format timestamp for display
        try:
            dt = datetime.fromisoformat(b.timestamp)
            ts_display = dt.strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            ts_display = b.timestamp

        parts.append(
            f'<div style="padding:6px 0; border-bottom:1px solid #3C3C3C;">'
            f'<div style="font-weight:bold; color:#E0E0E0;">'
            f"\U0001F516 {label_html}</div>"
            f'<div style="color:#777; font-size:11px;">{ts_display}</div>'
            f'<div style="color:#999; font-style:italic; font-size:12px; '
            f'margin-top:2px;">{preview_html}</div>'
            f"{tags_html}"
            f"</div>"
        )

    return "\n".join(parts)


def _highlight(text: str, term: str) -> str:
    """Case-insensitive highlight of term in text."""
    lower = text.lower()
    term_lower = term.lower()
    if term_lower not in lower:
        return text

    result = []
    idx = 0
    while idx < len(text):
        pos = lower.find(term_lower, idx)
        if pos == -1:
            result.append(text[idx:])
            break
        result.append(text[idx:pos])
        matched = text[pos : pos + len(term)]
        result.append(f'<span style="background:#665500; color:#FFD700;">{matched}</span>')
        idx = pos + len(term)
    return "".join(result)


# ---------------------------------------------------------------------------
# Command parsing
# ---------------------------------------------------------------------------

def parse_bookmark_command(text: str) -> dict:
    """Parse a /bookmark command string into an action dict.

    /bookmark                       -> list
    /bookmark this is the approach  -> add with label
    /bookmark search <query>        -> search
    /bookmark remove <id>           -> remove
    /bookmarks                      -> alias for /bookmark (list)
    """
    text = text.strip()

    # Strip the command prefix
    for prefix in ("/bookmarks", "/bookmark"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
            break

    if not text:
        return {"action": "list", "query": ""}

    # Check for sub-commands
    lower = text.lower()
    if lower.startswith("search "):
        return {"action": "search", "query": text[7:].strip()}
    if lower.startswith("remove "):
        return {"action": "remove", "id": text[7:].strip()}

    # Default: add a bookmark with the rest as the label
    return {"action": "add", "label": text}
