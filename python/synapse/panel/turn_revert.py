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
    if now != tuple(after):
        extra = len(now) - len(after)
        if extra > 0 and tuple(now[extra:]) == tuple(after):
            return _refused("\"%s\" happened after that turn, and REVERT never undoes "
                            "your own changes." % now[0])
        return _refused("the undo history changed after that turn.")
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
