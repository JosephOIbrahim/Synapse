"""Shared guards for the Solaris builder tools (R-007 / HANDS-3).

Two host-facing promises these tools made and never kept:

1. ``hou.undos.group()`` GROUPS undo entries; it does not roll back when the
   body raises. A failed build therefore left a half-built network in the
   scene until the artist pressed Ctrl+Z -- and the next retry saw the
   container's name and answered ``already_exists``. ``rollback_if_group_left_entry``
   snapshots the undo-stack labels before the group opens and calls
   ``performUndo()`` only when the stack top actually changed, so an empty
   group never takes back the artist's own last action. Same guard as
   ``build_graph`` (``server/handlers_solaris_graph.py``) and the render mixin
   (``server/handlers_render.py``).

2. A container's NAME is not proof that its chain is whole. ``missing_child_names``
   lets each tool verify the child nodes it actually builds and report
   ``incomplete`` when part of the chain is absent, instead of promising
   ``already_exists`` for a half-built asset.

Undo evidence (``areEnabled`` / ``undoLabels`` / ``performUndo``) is verified
present on H22.0.400 by ``python/synapse/recipes/transaction.py`` and the
``build_graph`` path. When the evidence cannot be read the rollback is
deliberately skipped: a blind ``performUndo()`` is worse than a half-build the
caller is told about.
"""

import logging

_log = logging.getLogger(__name__)


def undo_labels_snapshot(hou_mod):
    """Undo-stack labels before a group opens, or ``None`` when unreadable."""
    try:
        return tuple(hou_mod.undos.undoLabels())
    except Exception as exc:  # noqa: BLE001 -- evidence is best-effort
        _log.debug("undo labels unreadable; guarded rollback will be skipped: %s", exc)
        return None


def rollback_if_group_left_entry(hou_mod, labels_before):
    """One ``performUndo()`` when the group left a new undo-stack entry.

    Returns ``True`` when an undo was performed. ``labels_before is None``
    means the evidence was unreadable before the group opened, so nothing is
    popped -- the half-build stays visible rather than risking the artist's
    own work. Failure of the rollback itself is logged, never disguised as a
    successful one.
    """
    if labels_before is None:
        return False
    try:
        if tuple(hou_mod.undos.undoLabels()) != labels_before:
            hou_mod.undos.performUndo()
            return True
    except Exception as exc:  # noqa: BLE001 -- rollback is best-effort
        _log.warning("guarded undo rollback failed: %s", exc)
    return False


def missing_child_names(container, expected):
    """Names from ``expected`` absent from ``container``'s children.

    Returns ``None`` when the child list cannot be read -- the caller must
    report ``incomplete`` rather than assume the chain is present.
    """
    try:
        names = {child.name() for child in container.children()}
    except Exception as exc:  # noqa: BLE001 -- unreadable is reported, not assumed away
        _log.debug("could not read children of %r: %s", container, exc)
        return None
    return [name for name in expected if name not in names]
