"""REVERT for one panel turn, by Houdini's own undo of SYNAPSE's undo groups.

THE PROBLEM (10/1, 12:22 take). The turn receipt's REVERT sent a new turn to
the model ("Undo the last change using houdini_undo..."). The model, correctly
unable to see what that one global undo step would hit, declined. Nothing was
reverted, on camera.

THE SAFETY PROPERTY. A panel button must never undo an artist's own edit. So
REVERT undoes ONLY the undo entries that (a) appeared on Houdini's undo stack
during that turn and (b) carry a SYNAPSE label, and only while they are STILL
the top of the stack, exactly as the turn left it. Anything else above them --
a manual edit, a "Change Selection" from a click in the network editor, a
later turn, an artist Ctrl+Z -- makes it refuse with nothing changed. A
refusal is cheap: Ctrl+Z still works.

Selection entries are refused like any other foreign entry. Undoing an
artist's selection is harmless in itself, but it is still the artist's action,
and "only SYNAPSE's groups" is the property the button promises.

Everything here takes the ``hou.undos`` module as a parameter (undoLabels(),
performUndo(), areEnabled() -- verified on 22.0.400; undoLabels()[0] is the
next entry to be undone), so it is testable against a fake stack.
"""

import logging

logger = logging.getLogger(__name__)

# Top-level undo labels SYNAPSE writes: the bridge's "SYNAPSE: <tool>: {...}",
# tool-impl groups ("SYNAPSE: Create ...", "SYNAPSE insert ..."), and the
# handler-level "synapse_*" groups when a handler runs outside the bridge.
SYNAPSE_PREFIXES = ("SYNAPSE: ", "SYNAPSE ", "synapse_")


def hou_undos():
    """hou.undos inside Houdini; None headless (REVERT then refuses)."""
    try:
        import hou
        return hou.undos
    except Exception as exc:  # noqa: BLE001
        logger.debug("turn_revert: hou.undos unavailable: %s", exc)
        return None


def is_synapse_label(label) -> bool:
    return isinstance(label, str) and label.startswith(SYNAPSE_PREFIXES)


def snapshot(undos):
    """The undo stack's labels (next-to-undo first), or None if unreadable."""
    try:
        if undos is None or not undos.areEnabled():
            return None
        return tuple(undos.undoLabels())
    except Exception as exc:  # noqa: BLE001 -- unreadable history: REVERT will refuse
        logger.debug("turn_revert: undo labels unreadable: %s", exc)
        return None


def turn_entries(before, after):
    """Labels added on top of ``before`` to reach ``after`` (next-to-undo
    first), or None when ``after`` is not ``before`` plus new entries (the
    artist undid past the turn's start, or the stack was trimmed)."""
    if before is None or after is None:
        return None
    added = len(after) - len(before)
    if added < 0 or tuple(after[added:]) != tuple(before):
        return None
    return tuple(after[:added])


def turn_gone(before, after, now) -> bool:
    """True when the undo stack, read as ``now``, no longer holds the turn the
    way the turn left it (``before`` -> ``after``).

    That is what an artist's own undo does: the turn's step comes off the top
    and ``now`` stops ending in ``after``. Newer entries on top of the turn (a
    click in the network editor, a manual edit) do not make it gone: the step
    is still there, under them. It is the comparison ``revert_turn`` makes
    before it undoes anything, so the receipt and REVERT agree.

    Only a readable history is evidence. A snapshot that is None, a turn whose
    record is not a clean extension, and a turn that left no step on the stack
    all answer False: nothing can be said to be gone.
    """
    if not turn_entries(before, after) or now is None:
        return False
    return turn_entries(after, now) is None


def _refused(reason):
    return False, "REVERT refused: %s Nothing was changed. Ctrl+Z still works." % reason


def revert_turn(undos, before, after):
    """Undo the turn recorded as ``before`` -> ``after``. Returns
    ``(reverted, message)``; ``message`` is for the panel, in plain words."""
    entries = turn_entries(before, after)
    if entries is None:
        return _refused("the undo history for that turn could not be read.")
    if not entries:
        return _refused("that turn left nothing on the undo stack.")
    foreign = [label for label in entries if not is_synapse_label(label)]
    if foreign:
        return _refused("something other than SYNAPSE was recorded during that turn (%s)."
                        % foreign[0])
    now = snapshot(undos)
    if now is None:
        return _refused("undo is disabled or unreadable right now.")
    newer = turn_entries(after, now)         # what sits on top of the turn now
    if newer is None:
        return _refused("the undo history changed after that turn.")
    if newer:
        return _refused("\"%s\" happened after that turn, and REVERT never undoes "
                        "your own changes." % newer[0])
    for expected in entries:
        try:
            top = tuple(undos.undoLabels())[:1]
        except Exception as exc:  # noqa: BLE001
            logger.debug("turn_revert: undo labels unreadable mid-revert: %s", exc)
            top = ()
        if top != (expected,):
            return False, ("REVERT stopped: the next undo step was not SYNAPSE's (%s). "
                           "Check the scene; Ctrl+Z still works." % (top[0] if top else "none"))
        undos.performUndo()
    if snapshot(undos) != tuple(before):
        return False, "REVERT ran, but the undo history does not match the turn's start. Check the scene."
    return True, "Reverted %d SYNAPSE change%s from the last turn." % (
        len(entries), "" if len(entries) == 1 else "s")
