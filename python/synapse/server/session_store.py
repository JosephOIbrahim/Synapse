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
import shutil
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


def save_conversation(messages: List[dict], path: Optional[str] = None,
                      token: Optional[str] = None) -> bool:
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
            _write_owner(target, token)
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


def save_conversation_pinned(messages: List[dict],
                             pinned_path: Optional[str] = None) -> bool:
    """Save *messages* to the file a caller loaded them from (PUX-01).

    ``save_conversation()`` with no path follows whatever scene ``hou.hipFile``
    points at NOW. A panel that loaded under scene A and saves after File >
    Open would write A's chat over scene B's store. The panel pins the path at
    load and saves through here. With no usable pinned path this is exactly
    the old unpinned call."""
    if isinstance(pinned_path, str) and pinned_path:
        return save_conversation(messages, path=pinned_path)
    return save_conversation(messages)


def same_store(path_a: Optional[str], path_b: Optional[str]) -> bool:
    """True when two conversation paths live in the same store directory."""
    if not path_a or not path_b:
        return False

    def norm(p):
        return os.path.normcase(os.path.abspath(os.path.dirname(p)))
    return norm(path_a) == norm(path_b)


# Stores this process has already followed into another folder: source store
# dir -> destination store dir (PUX-01b). Every panel pinned to a scene follows
# its Save As. The first carries the files (or parks the chat it finds there);
# a second finds nothing left to carry and must not park the first one's chat
# over the previous slot. Dropped when a panel binds to the source store again.
_carried: dict = {}


def _store_key(path: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.dirname(path)))


def _carry(src: str, dst: str) -> bool:
    if not os.path.exists(src):
        return False
    try:
        os.replace(src, dst)
    except OSError:
        shutil.move(src, dst)  # Save As to another drive
    return True


def move_conversation(src_path: str, dst_path: str) -> bool:
    """Carry a conversation store to the folder a scene was saved into (PUX-01b).

    Moves ``conversation.json``, its owner sidecar and the parked
    ``conversation.previous.json`` from beside *src_path* to beside *dst_path*.
    Same folder: nothing to do. A conversation already at the destination is
    parked into the destination's previous slot, never overwritten (parking
    replaces an older previous, as a new boot does); the source's own previous
    then stays where it is. A second panel following the same Save As finds
    its store already carried here and changes nothing, so the previous slot
    survives. Best-effort: returns ``True`` if anything moved.
    """
    if not src_path or not dst_path or same_store(src_path, dst_path):
        return False
    src_prev, dst_prev = previous_path(src_path), previous_path(dst_path)
    src_key, dst_key = _store_key(src_path), _store_key(dst_path)
    moved = False
    with _lock:
        if (_carried.get(src_key) == dst_key and not os.path.exists(src_path)
                and not os.path.exists(src_prev)):
            return False
        try:
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            parked = os.path.exists(dst_path)
            if parked:
                _carry(dst_path, dst_prev)
                _carry(_owner_path(dst_path), _owner_path(dst_prev))
            pairs = [(src_path, dst_path),
                     (_owner_path(src_path), _owner_path(dst_path))]
            if not os.path.exists(dst_prev):
                pairs += [(src_prev, dst_prev),
                          (_owner_path(src_prev), _owner_path(dst_prev))]
            for src, dst in pairs:
                moved = _carry(src, dst) or moved
            if moved or parked:
                _carried[src_key] = dst_key
        except OSError as exc:
            logger.warning("session store: move %s -> %s failed: %s",
                           src_path, dst_path, exc)
    return moved


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


# ---------------------------------------------------------------------------
# Boot-scoped ownership (W7-SESSCOPE, Joe word 2026-08-16)
# ---------------------------------------------------------------------------
# The disk store above survives EVERYTHING by design - widget death, the pypanel
# module flush, and full Houdini restarts. g5 wants the first two and not the
# third: close/reopen must reattach (P0.3 stays dead), but a NEW Houdini boot
# should start clean without destroying the old work. The mechanism is an owner
# stamp: a token minted once per host process, stored OUTSIDE the synapse.*
# namespace (hou.session in Houdini, builtins headless) so it survives the
# module flush but dies with the process - exactly the boot lifetime. A scoped
# load compares stamps: same boot -> reattach; different boot -> the current
# conversation is PARKED to a 'previous' slot (never deleted) and the panel
# starts clean, with restore_previous_conversation() as the one-call undo.

_OWNER_SUFFIX = ".owner.json"
_PREVIOUS_FILENAME = "conversation.previous.json"
_BOOT_ATTR = "__synapse_boot_token__"


def _boot_token(token: Optional[str] = None) -> str:
    """The per-host-process boot token. Explicit *token* wins (tests)."""
    if token:
        return token
    host = None
    if _HOU_AVAILABLE and hou is not None:
        host = getattr(hou, "session", None)
    if host is None:
        import builtins as host  # type: ignore[no-redef]
    tok = getattr(host, _BOOT_ATTR, None)
    if not tok:
        import uuid
        tok = uuid.uuid4().hex
        try:
            setattr(host, _BOOT_ATTR, tok)
        except Exception:
            pass
    return tok


def _owner_path(target: str) -> str:
    return target + _OWNER_SUFFIX


def previous_path(path: Optional[str] = None) -> str:
    """The parked-previous slot beside the active conversation."""
    return os.path.join(os.path.dirname(conversation_path(path)),
                        _PREVIOUS_FILENAME)


def _write_owner(target: str, token: Optional[str] = None) -> None:
    """Stamp *target*'s owner sidecar with the current boot token. Best-effort:
    a failed stamp degrades to 'unowned' (parked on next boot), never a crash."""
    try:
        opath = _owner_path(target)
        tmp = opath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"boot": _boot_token(token)}, fh)
        os.replace(tmp, opath)
    except Exception as exc:
        logger.warning("session store: owner stamp failed (%s): %s", target, exc)


def _read_owner(target: str) -> Optional[str]:
    try:
        with open(_owner_path(target), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("boot") if isinstance(data, dict) else None
    except Exception:
        return None


def load_conversation_scoped(path: Optional[str] = None,
                             token: Optional[str] = None):
    """Boot-scoped restore. Returns ``(messages, scope)`` where scope is one of
    ``"same_boot"`` (reattached - the close/reopen case), ``"empty"`` (nothing
    stored), or ``"previous_parked"`` (a conversation from an earlier boot -
    or with no owner stamp, the legacy case - was moved to the previous slot
    and the caller starts clean). Parking replaces any older previous: the slot
    always holds the most recent prior boot's work."""
    target = conversation_path(path)
    _carried.pop(_store_key(target), None)  # bound afresh: no longer a follower
    messages = load_conversation(path)
    if not messages:
        return [], "empty"
    if _read_owner(target) == _boot_token(token):
        return messages, "same_boot"
    prev = previous_path(path)
    with _lock:
        try:
            os.replace(target, prev)
            try:
                os.replace(_owner_path(target), _owner_path(prev))
            except OSError:
                pass
        except OSError as exc:
            logger.warning("session store: park failed (%s): %s - loading as-is",
                           target, exc)
            return messages, "same_boot"
    return [], "previous_parked"


def has_previous_conversation(path: Optional[str] = None) -> bool:
    """True when a parked previous-boot conversation exists."""
    return os.path.exists(previous_path(path))


def restore_previous_conversation(path: Optional[str] = None,
                                  token: Optional[str] = None) -> List[dict]:
    """Move the parked previous conversation back to the active slot, stamp it
    with the CURRENT boot token, and return its messages ([] if none parked)."""
    prev = previous_path(path)
    target = conversation_path(path)
    with _lock:
        try:
            os.replace(prev, target)
        except FileNotFoundError:
            return []
        except OSError as exc:
            logger.warning("session store: restore failed (%s): %s", prev, exc)
            return []
    _write_owner(target, token)
    return load_conversation(path)
