"""The only writer in Identify: node comments and the comment-display flag.

Everything here is reversible and never reaches disk (IDENTIFY_BLUEPRINT rule
2/3/4). Text is appended below an ASCII sentinel line so an encoding round trip
cannot corrupt the marker; artist text above the sentinel is never touched. One
``hou.undos.group('SYNAPSE Identify')`` wraps a whole show and a whole clear, so
one Ctrl+Z reverses a click. A BeforeSave callback strips every block with undo
disabled and an AfterSave callback re-applies it, so a saved ``.hip`` carries no
sentinel.

``hou`` is import-guarded; tests inject a fake ``hou`` with ``undos.group`` /
``undos.disabler`` context managers and ``nodeFlag.DisplayComment``.
"""
from __future__ import annotations

from contextlib import contextmanager

try:  # pragma: no cover - exercised live under hython
    import hou
except Exception:  # pragma: no cover
    hou = None


#: ASCII so no cp1252/utf round trip can corrupt it (rule 2).
SENTINEL = "~ identify ~"

#: Selection cap. A starting value to tune at the GUI gate (rule 5).
CAP = 60

#: Undo group name — one entry per click (rule 3).
UNDO_LABEL = "SYNAPSE Identify"

#: sessionId -> {"path": str, "prior_flag": bool}. Per-session, in-memory only.
_REGISTRY: dict[int, dict] = {}

#: Filled by BeforeSave, drained by AfterSave: (path, comment, flag).
_SAVE_STASH: list[tuple] = []

#: The registered hipFile callback, so install is idempotent.
_SAVE_CALLBACK = None


@contextmanager
def _nullcontext():
    yield


def _undo_group(label: str):
    if hou is None:
        return _nullcontext()
    return hou.undos.group(label)


def _undo_disabler():
    if hou is None:
        return _nullcontext()
    return hou.undos.disabler()


def _display_flag():
    return hou.nodeFlag.DisplayComment


# ---------------------------------------------------------------------------
# Sentinel block: append and its clean inverse
# ---------------------------------------------------------------------------

def _block_start(comment: str) -> int:
    """Index of the line that begins *our* block, or -1.

    The sentinel is matched only as a standalone line, so artist prose that
    quotes ``~ identify ~`` inline is never mistaken for our block. We append
    last, so the *last* standalone sentinel line is ours; an artist's own
    standalone sentinel (earlier) is left in place.
    """
    lines = (comment or "").split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() == SENTINEL:
            return i
    return -1


def strip_block(comment: str) -> str:
    """Artist text with our block removed — the exact inverse of :func:`_compose_comment`."""
    idx = _block_start(comment)
    if idx == -1:
        return comment or ""
    return "\n".join((comment or "").split("\n")[:idx])


def _compose_comment(artist: str, bubble: str) -> str:
    """Artist text, then the sentinel line, then the bubble."""
    if artist:
        return f"{artist}\n{SENTINEL}\n{bubble}"
    return f"{SENTINEL}\n{bubble}"


def has_block(comment: str) -> bool:
    return _block_start(comment) != -1


# ---------------------------------------------------------------------------
# Show / clear / toggle
# ---------------------------------------------------------------------------

def _flash(editor, text: str) -> None:
    if editor is None:
        return
    try:
        editor.flashMessage(None, text, 6)
    except Exception:
        pass


def show(items, total=None, editor=None) -> dict:
    """Draw a bubble under each node. *items* is ``[(node, lines), ...]``.

    Capped at :data:`CAP`. One undo group wraps the whole show. Re-showing a
    node first strips its prior block, so the operation is idempotent and never
    stacks blocks. The prior display-comment flag is recorded once per node.
    """
    items = list(items)
    total = len(items) if total is None else total
    capped = items[:CAP]
    with _undo_group(UNDO_LABEL):
        for node, lines in capped:
            existing = node.comment() or ""
            artist = strip_block(existing)
            bubble = "\n".join(lines) if not isinstance(lines, str) else lines
            new_comment = _compose_comment(artist, bubble)
            sid = node.sessionId()
            if sid not in _REGISTRY:
                _REGISTRY[sid] = {
                    "path": node.path(),
                    "prior_flag": bool(node.isGenericFlagSet(_display_flag())),
                }
            else:
                _REGISTRY[sid]["path"] = node.path()
            node.setComment(new_comment)
            node.setGenericFlag(_display_flag(), True)
    shown = len(capped)
    _flash(editor, f"Identify: {shown} of {total} nodes")
    return {"shown": shown, "total": total}


def clear(nodes, editor=None) -> dict:
    """Remove every Identify block from *nodes* and restore the prior flag.

    Registry entries restore their exact prior display-comment flag. Orphan
    blocks (no registry entry, e.g. left by a prior session) are removed too;
    their flag is set to whether artist text remains, since the prior value is
    unknown. One undo group wraps the whole clear.
    """
    removed = 0
    with _undo_group(UNDO_LABEL):
        for node in nodes:
            existing = node.comment() or ""
            if not has_block(existing):
                continue
            artist = strip_block(existing)
            node.setComment(artist)
            sid = node.sessionId()
            entry = _REGISTRY.pop(sid, None)
            if entry is not None:
                node.setGenericFlag(_display_flag(), entry["prior_flag"])
            else:
                node.setGenericFlag(_display_flag(), bool(artist))
            removed += 1
    return {"removed": removed}


def toggle(items, total=None, editor=None) -> dict:
    """Show if no selected node carries a block, else clear (idempotent toggle)."""
    items = list(items)
    nodes = [node for node, _ in items]
    active = any(has_block(node.comment() or "") for node in nodes)
    if active:
        result = clear(nodes, editor=editor)
        result["action"] = "clear"
        return result
    result = show(items, total=total, editor=editor)
    result["action"] = "show"
    return result


# ---------------------------------------------------------------------------
# Save safety: strip on BeforeSave, re-apply on AfterSave, undo disabled
# ---------------------------------------------------------------------------

def _active_nodes():
    for sid, entry in list(_REGISTRY.items()):
        node = hou.node(entry["path"]) if hou is not None else None
        if node is not None:
            yield sid, node


def before_save(*_event) -> None:
    """Strip every Identify block so the saved file carries no sentinel."""
    with _undo_disabler():
        _SAVE_STASH.clear()
        for _sid, node in _active_nodes():
            comment = node.comment() or ""
            if not has_block(comment):
                continue
            flag = bool(node.isGenericFlagSet(_display_flag()))
            _SAVE_STASH.append((node.path(), comment, flag))
            node.setComment(strip_block(comment))


def after_save(*_event) -> None:
    """Put every stripped block back exactly as it was before the save."""
    with _undo_disabler():
        for path, comment, flag in _SAVE_STASH:
            node = hou.node(path) if hou is not None else None
            if node is None:
                continue
            node.setComment(comment)
            node.setGenericFlag(_display_flag(), flag)
        _SAVE_STASH.clear()


def _save_dispatch(event) -> None:
    name = getattr(event, "name", lambda: str(event))
    label = name() if callable(name) else str(event)
    label = str(label).rsplit(".", 1)[-1]
    if label == "BeforeSave":
        before_save()
    elif label == "AfterSave":
        after_save()


def install_save_callbacks() -> None:
    """Register the BeforeSave/AfterSave hipFile callbacks once."""
    global _SAVE_CALLBACK
    if hou is None or _SAVE_CALLBACK is not None:
        return
    hou.hipFile.addEventCallback(_save_dispatch)
    _SAVE_CALLBACK = _save_dispatch


def remove_save_callbacks() -> None:
    global _SAVE_CALLBACK
    if hou is None or _SAVE_CALLBACK is None:
        return
    try:
        hou.hipFile.removeEventCallback(_SAVE_CALLBACK)
    finally:
        _SAVE_CALLBACK = None


def _reset_state() -> None:
    """Clear in-memory registry/stash — test hook, not a scene operation."""
    global _SAVE_CALLBACK
    _REGISTRY.clear()
    _SAVE_STASH.clear()
    _SAVE_CALLBACK = None
