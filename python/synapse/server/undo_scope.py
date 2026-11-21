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
the same label was dropped), never allow an old one.

Only labels an agent tool writes count (``AGENT_PREFIXES``): panel actions the
artist starts ("SYNAPSE insert saved network", "SYNAPSE Identify cleanup") are
the artist's own work, and so is the panel's Spatial footer click, which writes
the same label as the agent's trail tool (``ARTIST_STARTED_LABELS``; the agent's
own trail is refused with it, a safe refusal).

Redo is further limited to entries this handler itself undid. Labels cannot
tell two entries of one label apart, so the handler records both stacks right
after each of its own undo/redo steps, and how many entries at the top of the
redo stack its own undos put there. A redo is allowed only while the history is
exactly as the handler left it: anything in between (the artist's Ctrl+Z or
Ctrl+Y, a new edit, a failed build's rollback) changes the stacks and ends the
run. So a group a failed build rolled back, or one the artist undid, is never
re-applied by an agent.

A session is one handler's lifetime. Every client of the same route shares it
(the in-Houdini /mcp server, the WebSocket server), so one client can undo
another client's agent step on that route, and a new chat can undo an earlier
chat's; a step from before the handler started is refused.
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


logger = logging.getLogger(__name__)

#: Labels SYNAPSE's agent tools write: the execution bridge's "SYNAPSE: <summary>"
#: groups and the live handlers' "synapse_<op>" groups. Panel actions the artist
#: starts use "SYNAPSE " with a space and are the artist's own work.
AGENT_PREFIXES = ("SYNAPSE: ", "synapse_")


#: Agent-prefixed labels a panel click also writes, with no model turn: the
#: Spatial footer button runs ``synapse_spatial_trail`` through the bridge, whose
#: group is named from ``handlers_spatial.TRAIL_UNDO``. The label cannot tell the
#: click from an agent call, so both are refused.
ARTIST_STARTED_LABELS = frozenset({"SYNAPSE: Draw camera path"})


def is_agent_label(label) -> bool:
    return (isinstance(label, str) and label.startswith(AGENT_PREFIXES)
            and label not in ARTIST_STARTED_LABELS)


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


def history(undos):
    """Both stacks' labels as ``(undo, redo)``, or None if either is unreadable."""
    undo = _labels(undos, "undoLabels")
    redo = _labels(undos, "redoLabels")
    if undo is None or redo is None:
        return None
    return undo, redo


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
        # The history right after this handler's last undo/redo, and how many
        # entries at the top of the redo stack its own undos put there.
        self._left_history = None
        self._redoable = 0
        self.capture_failures = 0

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
        undo = _ready_labels(undos, "undoLabels")
        redo = _ready_labels(undos, "redoLabels")
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
        if not is_agent_label(top):
            return (
                '%s refused: the next %s step is "%s", which a SYNAPSE agent tool '
                "did not record. Taking it back would reverse the artist's own work. "
                "Nothing was changed; Ctrl+Z still works." % (verb, direction, top)
            )
        if direction == "redo" and not self._redo_is_ours(undos):
            return (
                'Redo refused: the next redo step is "%s", which this SYNAPSE '
                "session did not undo, or the history changed after it did. It may "
                "have been taken back for a reason "
                "(a failed build, or the artist's own Ctrl+Z). Nothing was changed; "
                "Ctrl+Y still works." % (top,)
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

    def _redo_is_ours(self, undos) -> bool:
        """The redo top is one this handler undid and nothing happened since."""
        return (self._redoable > 0 and self._left_history is not None
                and history(undos) == self._left_history)

    def note_agent_step(self, direction: str, before, after) -> None:
        """Record a step this handler took; ``before``/``after`` come from ``history()``.

        An undo that starts from the history this handler last left extends its
        run of redoable entries; any other undo starts a new run of one. A redo
        uses one up. A history that cannot be read ends the run.
        """
        chained = before is not None and before == self._left_history
        if direction == "undo":
            self._redoable = (self._redoable if chained else 0) + 1
        else:
            self._redoable = self._redoable - 1 if chained else 0
        self._left_history = after
        if after is None:
            self._redoable = 0
