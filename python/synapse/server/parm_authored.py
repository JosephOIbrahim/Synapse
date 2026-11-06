"""What a parameter holds as written, next to what it evaluates to.

Parameter reads return ``hou.Parm.eval()``. For a string parameter written with
variables, such as ``$HIP/render/$HIPNAME.$OS.$F4.exr``, that is the expanded
path, so an agent that wrote the variables cannot confirm its write by reading
it back. On 2026-09-29 Claude Code reported a successful write of Karma's
output picture as failed for exactly this reason (BP12 item 15).

Houdini 22.0.400, probed in hython: ``unexpandedString()`` raises
hou.OperationFailed for a non-string parm ("Only string parms have unexpanded
strings") and for a keyframed one ("Cannot get unexpanded string for parms
with keyframes"), and ``expression()`` raises it for a parm that is not
animated. Those are the only errors swallowed here.
"""
import math
from typing import Any, Dict, List, Optional

try:
    import hou
except ImportError:
    hou = None  # type: ignore[assignment]

_OPERATION_FAILED = getattr(hou, "OperationFailed", None)
if not (isinstance(_OPERATION_FAILED, type)
        and issubclass(_OPERATION_FAILED, Exception)):
    _OPERATION_FAILED = RuntimeError

# A parm without the asked-for value raises one of these; nothing else is
# swallowed.
_READ_ERRORS = (_OPERATION_FAILED, AttributeError, TypeError)

# A restore must never mask the write failure it is answering, so it also
# absorbs the errors a setter can raise for a bad value.
_RESTORE_ERRORS = _READ_ERRORS + (RuntimeError, ValueError)


def raw_string(parm, evaluated) -> Optional[str]:
    """The string a string parm holds as written, when it differs from
    ``evaluated``. None for other parms, keyframed parms, or no difference."""
    try:
        raw = parm.unexpandedString()
    except _READ_ERRORS:
        return None
    if isinstance(raw, str) and raw != evaluated:
        return raw
    return None


def authored_fields(parm, evaluated) -> Dict[str, Any]:
    """Extra read fields for one parm: ``expression`` and
    ``expression_language`` when exactly one key drives it, ``keyframe_count``
    for the number of keys, ``raw`` when its string as written differs from
    ``evaluated``, otherwise nothing.

    The count is measured on its own: ``expression()`` raises for a parameter
    with several keys, and the count must survive that (a multi-key parameter
    is the case H1-1 was about).
    """
    try:
        keyframes = parm.keyframes()
    except _READ_ERRORS:
        keyframes = ()
    count = len(keyframes) if isinstance(keyframes, (list, tuple)) else 0
    if count:
        fields: Dict[str, Any] = {"keyframe_count": count}
        try:
            expression = parm.expression()
        except _READ_ERRORS:
            return fields
        if isinstance(expression, str):
            fields["expression"] = expression
            fields["expression_language"] = str(parm.expressionLanguage())
        return fields
    raw = raw_string(parm, evaluated)
    return {"raw": raw} if raw is not None else {}


def authored_tuple_fields(parms, values) -> Dict[str, List[Any]]:
    """``authored_fields`` for a parm tuple: one list per field, aligned with
    ``values``, present only when some component has that field."""
    per = [authored_fields(p, v) for p, v in zip(parms, values)]
    out: Dict[str, List[Any]] = {}
    for key in ("raw", "expression", "expression_language", "keyframe_count"):
        if any(key in fields for fields in per):
            out[key] = [fields.get(key) for fields in per]
    return out


# ---------------------------------------------------------------------------
# Writes: what the parm will hold after this, not what the caller asked for
# ---------------------------------------------------------------------------

#: How a write may meet an animated or referenced parm.
WRITE_MODES = ("refuse", "replace", "key_at_frame", "write_source")


class ParmWriteRefused(ValueError):
    """The write cannot land as asked; nothing was written."""


def keyframe_count(parm) -> int:
    """Number of keys on the parm, 0 when it carries none or cannot say."""
    try:
        keyframes = parm.keyframes()
    except _READ_ERRORS:
        return 0
    return len(keyframes) if isinstance(keyframes, (list, tuple)) else 0


def reference_source(parm):
    """The parm this one is driven by, or None when it is its own source.

    Compared by equality, not identity: Houdini 22.0.400 returns a distinct
    wrapper for the same parameter (probed in hython — ``getReferencedParm()
    is parm`` is False for a plain parm, ``==`` is True), so an identity check
    would call every parameter a reference to itself.
    """
    try:
        source = parm.getReferencedParm()
    except _READ_ERRORS:
        return None
    if source is None:
        return None
    try:
        return None if source == parm else source
    except _READ_ERRORS:
        # A comparison that cannot answer is not a reference.
        return None


def _label(parm) -> str:
    """A human name for a parm, without requiring a real hou node."""
    name = None
    try:
        name = parm.name()
    except _READ_ERRORS:
        name = None
    try:
        node = parm.node()
        return f"{node.path()}/{name}" if name else str(node.path())
    except _READ_ERRORS:
        return str(name) if name else "this parameter"


def _plan_write(parm, mode):
    """Resolve what will actually be written, or refuse before any mutation."""
    source = reference_source(parm)
    if source is not None:
        if mode != "write_source":
            raise ParmWriteRefused(
                f"{_label(parm)} is driven by {_label(source)}. Nothing was "
                "written. Pass mode='write_source' to write that parameter, "
                "or change the expression that drives it.")
        parm = source

    keys = keyframe_count(parm)
    if keys and mode == "refuse":
        raise ParmWriteRefused(
            f"{_label(parm)} has {keys} keyframe(s). Nothing was written. "
            "Pass mode='replace' to clear them, mode='key_at_frame' to add a "
            "key at the current frame, or edit the expression instead.")
    if mode == "replace":
        return parm, "replace"
    if mode == "key_at_frame":
        return parm, "key_at_frame"
    if keys:
        # write_source landed on an animated source; refuse rather than
        # replace its animation without being asked.
        raise ParmWriteRefused(
            f"{_label(parm)} has {keys} keyframe(s); write_source will not "
            "replace them. Nothing was written.")
    return parm, "set"


def _set_plain(parm, value) -> None:
    parm.set(value, follow_parm_reference=False)


def _set_key_at_frame(parm, value) -> None:
    """Add a key at the current frame, keeping the ones already there.

    ``parm.set(value, follow_parm_reference=False)`` clears the animation on
    22.0.400 (probed), so it is never used for this mode.
    """
    if hou is None or not hasattr(hou, "Keyframe"):
        raise ParmWriteRefused(
            f"Cannot add a key to {_label(parm)}: Houdini is not available.")
    key = hou.Keyframe()
    key.setFrame(hou.frame())
    key.setValue(value)
    parm.setKeyframe(key)


def _snapshot(parm) -> Dict[str, Any]:
    """Everything a failed write must put back: value, keys, extrapolation.

    The keys alone are not enough. Houdini 22.0.400 resets a channel's
    extrapolation to Extend when keys are re-added (probed), so a Cycle
    channel restored from keys alone evaluates differently outside its keyed
    range.
    """
    snap: Dict[str, Any] = {"value": None, "keys": [], "extrapolation": (None, None)}
    try:
        snap["value"] = parm.eval()
    except _READ_ERRORS:
        pass
    try:
        keys = parm.keyframes()
    except _READ_ERRORS:
        keys = ()
    if isinstance(keys, (list, tuple)):
        snap["keys"] = list(keys)
    extrap = []
    for before in (True, False):
        try:
            extrap.append(parm.keyframeExtrapolation(before))
        except _READ_ERRORS:
            extrap.append(None)
    snap["extrapolation"] = tuple(extrap)
    return snap


def _restore(parm, snap: Dict[str, Any]) -> None:
    """Put the snapshot back. Best effort: the original failure is what the
    caller sees."""
    if snap["keys"]:
        try:
            parm.deleteAllKeyframes()
        except _RESTORE_ERRORS:
            pass
        for key in snap["keys"]:
            try:
                parm.setKeyframe(key)
            except _RESTORE_ERRORS:
                pass
        for before, value in zip((True, False), snap["extrapolation"]):
            if value is None:
                continue
            try:
                parm.setKeyframeExtrapolation(before, value)
            except _RESTORE_ERRORS:
                pass
    elif snap["value"] is not None:
        try:
            parm.set(snap["value"], follow_parm_reference=False)
        except _RESTORE_ERRORS:
            pass


def _replace(parm, value) -> None:
    """Clear the keys, then write the value.

    Restoration is the caller's: it snapshots every target before the first
    write and puts all of them back when any write fails, because a tuple
    replacement can fail on a later component after earlier ones committed.
    """
    try:
        keys = parm.keyframes()
    except _READ_ERRORS:
        keys = ()
    if keys:
        parm.deleteAllKeyframes()
    parm.set(value, follow_parm_reference=False)


def _close(a, b) -> bool:
    """Whether two values are the same value for this purpose."""
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def author_parm_write(parms, values, mode: str = "refuse", parm_tuple=None) -> Dict[str, Any]:
    """Write one parm or a tuple, then report what the parm actually holds.

    Every component is checked before any is written, so a tuple write is
    all-or-none. The write is not followed through a parameter reference
    unless ``mode='write_source'`` says so. The returned ``value`` is the
    request; ``observed`` is ``eval()`` after the write; ``mismatch`` is True
    when the parm did not take the value, which is what a clamped or
    expression-driven parm does.
    """
    if mode not in WRITE_MODES:
        raise ValueError(
            f"Unknown mode {mode!r}. Use one of: {', '.join(WRITE_MODES)}.")

    parms = list(parms)
    values = list(values)
    if len(values) != len(parms):
        # A tuple of 3 refuses [7, 8] with InvalidSize; refuse it here, before
        # anything is written, rather than letting zip truncate.
        raise ValueError(
            f"{len(values)} value(s) for {len(parms)} parameter(s). Nothing "
            "was written.")
    targets = [_plan_write(p, mode) for p in parms]

    plain = all(
        target[0] is parm and target[1] == "set"
        for parm, target in zip(parms, targets))

    # Snapshot every target before the first write. A tuple write commits each
    # component in turn, so a value the last component refuses must not cost
    # the earlier ones their value or their animation.
    target_parms = [target[0] for target in targets]
    snapshots = [_snapshot(parm) for parm in target_parms]
    try:
        if parm_tuple is not None and len(parms) > 1 and plain:
            # Nothing to unwrap or clear: keep the tuple write as one call, the
            # shape the handler has always used.
            parm_tuple.set(values)
        else:
            for (parm, action), value in zip(targets, values):
                if action == "replace":
                    _replace(parm, value)
                elif action == "key_at_frame":
                    _set_key_at_frame(parm, value)
                else:
                    _set_plain(parm, value)
    except Exception:
        for parm, snap in zip(target_parms, snapshots):
            _restore(parm, snap)
        raise

    observed = [parm.eval() for parm, _ in targets]  # noqa: S307
    mismatch = [not _close(requested, held)
                for requested, held in zip(values, observed)]
    return {
        "value": values if len(values) > 1 else values[0],
        "observed": observed if len(observed) > 1 else observed[0],
        "authored": {
            "mode": mode,
            "keyframe_count": [keyframe_count(parm) for parm, _ in targets],
            "wrote": [_label(parm) for parm, _ in targets],
        },
        "mismatch": any(mismatch),
    }
