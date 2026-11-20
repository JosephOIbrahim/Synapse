"""What may an agent's history call step over? (R-012 / SIDEFXCTO-2)

``houdini_undo`` / ``houdini_redo`` used to call ``hou.undos.performUndo()`` /
``performRedo()`` blind on Houdini's global history. The top entry could be the
artist's own edit, so an agent trying to take back its own last step could take
back the artist's instead. The panel's REVERT button has carried the safe rule
since the 10/1 take (``panel/turn_revert.py``): read ``undoLabels()`` and refuse
unless the step is SYNAPSE's own. This module applies that rule to the history
tools.

The extra qualifier is the session. ``UndoScope`` records the undo/redo stacks
as the handler first found them, and the top entry must be a SYNAPSE label that
appeared after that baseline -- i.e. one this SYNAPSE session created. A
SYNAPSE-labelled entry from a previous SYNAPSE run (a panel reload) is refused
like any foreign entry. When no baseline could be read (headless, or undo was
disabled when the first command ran), the rule degrades to the prefix check,
which still refuses the artist's work -- the dangerous case.

Everything takes the ``hou.undos`` module as a parameter (``areEnabled()``,
``undoLabels()``, ``redoLabels()`` -- verified on 22.0.400; element zero is the
next step), so the rule is testable against a fake stack. This module imports
no ``hou``.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Optional, Tuple

from ..panel.turn_revert import is_synapse_label

logger = logging.getLogger(__name__)


def _as_labels(value) -> Optional[Tuple[str, ...]]:
    """A tuple of label strings, or None when the value is not a label list."""
    if value is None or isinstance(value, str):
        return None
    try:
        labels = tuple(value)
    except TypeError:
        return None
    if not all(isinstance(label, str) for label in labels):
        return None
    return labels


def _labels(undos, attr: str) -> Optional[Tuple[str, ...]]:
    """One history direction's labels, or None if they cannot be read."""
    try:
        return _as_labels(getattr(undos, attr)())
    except Exception:  # noqa: BLE001 -- unreadable history is a refusal, not a crash
        logger.debug("hou.undos.%s() unreadable; refusing the step", attr,
                     exc_info=True)
        return None


def _ready_labels(undos, attr: str) -> Optional[Tuple[str, ...]]:
    """Labels only while history is enabled; None means 'refuse this step'."""
    try:
        if undos is None or not undos.areEnabled():
            return None
    except Exception:  # noqa: BLE001 -- an unreadable enabled-check refuses too
        logger.debug("hou.undos.areEnabled() failed; refusing the step",
                     exc_info=True)
        return None
    return _labels(undos, attr)


class UndoScope:
    """The session rule for the agent's history tools.

    Call ``note_session_start()`` once, before this handler's first command
    runs, to record the baseline. ``refusal()`` then answers why a given
    direction must be refused, or None to allow it.
    """

    def __init__(self) -> None:
        self._captured = False
        self._undo: Optional[Counter] = None
        self._redo: Optional[Counter] = None

    @property
    def needs_baseline(self) -> bool:
        return not self._captured

    def note_session_start(self, undos) -> bool:
        """Capture the history this session started from. First success wins.

        Returns False when even one direction could not be read, so the caller
        can try again on a later command; a readable empty stack is a valid
        baseline and captures True.
        """
        if self._captured:
            return True
        undo = _labels(undos, "undoLabels")
        redo = _labels(undos, "redoLabels")
        if undo is None and redo is None:
            return False
        self._undo = Counter(undo) if undo is not None else None
        self._redo = Counter(redo) if redo is not None else None
        self._captured = True
        return True

    def refusal(self, undos, direction: str) -> Optional[str]:
        """Why the next ``direction`` step must be refused, or None to allow it.

        The refusal names the top label: the caller (and the agent) must be
        able to see exactly which step was refused.
        """
        if direction not in ("undo", "redo"):
            raise ValueError("direction must be 'undo' or 'redo'")
        attr = "undoLabels" if direction == "undo" else "redoLabels"
        verb = direction.capitalize()
        labels = _ready_labels(undos, attr)
        if labels is None:
            return ("%s refused: Houdini's undo history is disabled or unreadable. "
                    "Nothing was changed." % verb)
        if not labels:
            return "%s refused: there is nothing to %s. Nothing was changed." % (
                verb, direction)
        top = labels[0]
        if not is_synapse_label(top):
            return (
                '%s refused: the next %s step is "%s", which SYNAPSE did not '
                "record. Taking it back would reverse the artist's own work. "
                "Nothing was changed; Ctrl+Z still works." % (verb, direction, top)
            )
        baseline = self._undo if direction == "undo" else self._redo
        if baseline is not None and Counter(labels)[top] <= baseline.get(top, 0):
            return (
                '%s refused: the next %s step is "%s", recorded before this '
                "SYNAPSE session started. Nothing was changed; Ctrl+Z still "
                "works." % (verb, direction, top)
            )
        return None
