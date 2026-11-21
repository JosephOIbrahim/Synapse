"""What may an agent's history call step over? (R-012 / SIDEFXCTO-2)

``houdini_undo`` / ``houdini_redo`` used to call ``hou.undos.performUndo()`` /
``performRedo()`` blind on Houdini's global history. The top entry could be the
artist's own edit, so an agent trying to take back its own last step could take
back the artist's instead. The panel's REVERT button has carried the safe rule
since the 10/1 take (``panel/turn_revert.py``): read ``undoLabels()`` and refuse
unless the step is SYNAPSE's own. This module applies that rule to the history
tools.

The extra qualifier is the session. ``UndoScope`` records how many entries of
each label the undo and redo stacks held when the handler first found them (B).
Houdini's history is one linear list and every new action drops the redo
entries, so the entries that survive from before the session always sit at the
bottom, at most B[label] of each label. Labels repeat (every create is
``synapse_node_create``), so the rule counts the UNDO stack only:

- undo is allowed when the undo stack holds more entries of the top's label than
  B -- then at least one is this session's, and this session's entries are the
  newest, so the top is one of them;
- redo is allowed when the undo stack already holds at least B entries of the
  redo top's label -- then every surviving pre-session entry of that label is
  applied, so the redo top cannot be one of them.

Both can refuse a legitimate step (for example when a pre-session redo entry of
the same label was dropped), never allow an old one. A SYNAPSE-labelled entry
from a previous SYNAPSE run (a panel reload) is refused like any foreign entry.
With no baseline, a history call refuses: the handler captures one first when
it can, so everything already present counts as pre-session.

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

    ``note_session_start()`` records the baseline: both stacks, counted together
    per label (B). ``refusal()`` then answers why a given direction must be
    refused, or None to allow it, by the undo-stack rule in the module docstring. The handler runs the refusal and the step in one
    main-thread call, so nothing can land on the history between them.
    """

    def __init__(self) -> None:
        self._captured = False
        self._baseline: Optional[Counter] = None

    @property
    def needs_baseline(self) -> bool:
        return not self._captured

    def note_session_start(self, undos) -> bool:
        """Capture the history this session started from. First success wins.

        Both directions must be readable; otherwise nothing is captured and the
        caller tries again later. A readable empty history is a valid baseline.
        """
        if self._captured:
            return True
        undo = _labels(undos, "undoLabels")
        redo = _labels(undos, "redoLabels")
        if undo is None or redo is None:
            return False
        self._baseline = Counter(undo) + Counter(redo)
        self._captured = True
        return True

    def refusal(self, undos, direction: str) -> Optional[str]:
        """Why the next ``direction`` step must be refused, or None to allow it.

        The refusal names the top label: the caller (and the agent) must be
        able to see exactly which step was refused.
        """
        if direction not in ("undo", "redo"):
            raise ValueError("direction must be 'undo' or 'redo'")
        if direction == "undo":
            attr, other_attr, other_name = "undoLabels", "redoLabels", "redo"
        else:
            attr, other_attr, other_name = "redoLabels", "undoLabels", "undo"
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
        if self._baseline is None:
            return (
                '%s refused: SYNAPSE has no record of where this session started, '
                'so it cannot tell whether "%s" is its own step. Nothing was '
                "changed; Ctrl+Z still works." % (verb, top)
            )
        if direction == "undo":
            applied = labels
        else:
            applied = _labels(undos, other_attr)
            if applied is None:
                return (
                    "%s refused: Houdini's %s history is unreadable, so SYNAPSE cannot "
                    'tell whether "%s" is from this session. Nothing was changed; '
                    "Ctrl+Z still works." % (verb, other_name, top)
                )
        held = Counter(applied)[top]
        before = self._baseline.get(top, 0)
        if (held <= before) if direction == "undo" else (held < before):
            return (
                '%s refused: the next %s step is "%s", recorded before this '
                "SYNAPSE session started. Nothing was changed; Ctrl+Z still "
                "works." % (verb, direction, top)
            )
        return None
