"""
Process- and reopen-durable conversation store — session survival (R.2 target 3).

Why disk, not a module global
-----------------------------
The panel's conversation history used to live ONLY as ``self._messages`` on the
``SynapsePanel`` QWidget (``synapse_panel.py:335``). Closing the panel destroyed
the widget and the list with it; reopen built a fresh panel with an empty
conversation — "reopen met a fresh runtime, no chat history" (g5, 2026-08-16).

A module-level singleton would NOT survive reopen either: the Houdini
python-panel loader (``houdini/python_panels/synapse_panel.pypanel``) deletes
every ``synapse.*`` module from ``sys.modules`` on each panel creation, so any
in-memory ``synapse.*`` global is reset on reopen. The only stores that survive
BOTH the widget destruction AND that module flush live outside the ``synapse.*``
namespace: on disk (this module) or ``hou.session``. This store is disk-backed,
keyed by the HIP file (a "session" is per-scene), so a close → reopen on the
same scene restores the same conversation. It mirrors ``session_journal.py``'s
HIP-derived path so both land under ``$HIP/claude/``.

The conversation is Anthropic message format (``[{"role", "content"}, ...]``) —
JSON-serialisable by construction (it is what the API is fed). Writes are
atomic (``.tmp`` + ``os.replace``, the repo's durability idiom) and
thread-safe; reads tolerate a missing or corrupt file by returning ``[]`` so a
damaged store degrades to "fresh session", never a crash.

Headless: with no ``hou`` the path falls back to a temp dir, so the whole
save/restore round-trip is exercisable in pytest. Zero ``hou`` required; ``hou``
is only consulted, guarded, to resolve the HIP directory.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from typing import List, Optional

logger = logging.getLogger("synapse.session_store")

# ---------------------------------------------------------------------------
# Houdini import guard (path resolution only)
# ---------------------------------------------------------------------------
_HOU_AVAILABLE = False
try:  # pragma: no cover - host dependent
    import hou  # type: ignore[import-untyped]
    _HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]

_CONVERSATION_FILENAME = "conversation.json"
_lock = threading.Lock()


def _resolve_store_dir() -> str:
    """Derive the store directory from the current HIP file, or fall back to a
    stable temp directory. Mirrors ``session_journal._resolve_log_dir`` so the
    conversation lands beside the journal under ``$HIP/claude/``."""
    if _HOU_AVAILABLE and hou is not None:
        try:
            hip_path = hou.hipFile.path()
            if hip_path:
                hip_dir = os.path.dirname(hip_path)
                if hip_dir and os.path.isdir(hip_dir):
                    return os.path.join(hip_dir, "claude")
        except Exception:
            pass
    return os.path.join(tempfile.gettempdir(), "synapse_session")


def conversation_path(path: Optional[str] = None) -> str:
    """The resolved conversation-store path. Pass an explicit *path* to override
    HIP resolution (tests, or a caller that already knows the file)."""
    if path:
        return path
    return os.path.join(_resolve_store_dir(), _CONVERSATION_FILENAME)


def save_conversation(messages: List[dict], path: Optional[str] = None) -> bool:
    """Persist *messages* (Anthropic conversation format) durably.

    Atomic (``.tmp`` + ``os.replace``) and thread-safe. Best-effort: any I/O or
    serialisation failure is logged and returns ``False`` — persisting the
    transcript must never break the caller (a closing panel, a finishing
    worker). Returns ``True`` on a successful write.
    """
    if not isinstance(messages, list):
        logger.warning("session store: refusing to save non-list conversation (%s)",
                       type(messages).__name__)
        return False
    target = conversation_path(path)
    tmp = target + ".tmp"
    with _lock:
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                # default=str is the safety net for any exotic block; the
                # Anthropic format is JSON-native so it is rarely exercised.
                json.dump(messages, fh, ensure_ascii=False, default=str)
            os.replace(tmp, target)
            return True
        except Exception as exc:
            logger.warning("session store: save failed (%s): %s", target, exc)
            # Clean up a partial temp file so it can't masquerade as state.
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False


def load_conversation(path: Optional[str] = None) -> List[dict]:
    """Restore the persisted conversation, or ``[]`` if there is none.

    A missing file (fresh scene / first run) returns ``[]``. A corrupt or
    non-list file returns ``[]`` and warns — a damaged store degrades to a
    fresh session rather than crashing the panel on reopen.
    """
    target = conversation_path(path)
    with _lock:
        try:
            with open(target, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except FileNotFoundError:
            return []
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("session store: load failed (%s): %s — starting fresh",
                           target, exc)
            return []
    if not isinstance(data, list):
        logger.warning("session store: stored conversation is %s, not a list — "
                       "starting fresh", type(data).__name__)
        return []
    return data


def has_conversation(path: Optional[str] = None) -> bool:
    """True when a persisted conversation with at least one message exists."""
    return len(load_conversation(path)) > 0


def clear_conversation(path: Optional[str] = None) -> bool:
    """Delete the persisted conversation. Returns ``True`` if a file was
    removed, ``False`` if there was nothing to remove. Best-effort."""
    target = conversation_path(path)
    with _lock:
        try:
            os.remove(target)
            return True
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.warning("session store: clear failed (%s): %s", target, exc)
            return False
