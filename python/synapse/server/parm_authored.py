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


def raw_authored(parm) -> Optional[str]:
    """The string a string parm holds as written, even when it equals
    ``eval()``. None for other parms, keyframed parms, or a parm that cannot
    say.

    ``raw_string`` above reports the authored text only when it *differs* from
    the evaluated value, because its callers add a field only when it is new
    information. A write comparison needs the authored text unconditionally:
    ``$HIP/render/$F4.exr`` is the value the caller asked for whether or not it
    happens to expand to itself.
    """
    try:
        raw = parm.unexpandedString()
    except _READ_ERRORS:
        return None
    return raw if isinstance(raw, str) else None


def inspection(parm) -> Dict[str, Any]:
    """What can be known about a parm's animation and reference state.

    ``known`` is False when the parm cannot say: ``keyframes()`` or
    ``getReferencedParm()`` raised an operation error, or the comparison that
    decides "is this a reference" could not answer. An unknown key count is
    ``None``, never 0, and an unknown source is ``None`` with ``known`` False,
    never "no reference" — the distinction the blueprint's pre-mutation check
    requires.

    A missing method (``AttributeError``) is an API that is not there, not a
    read that failed: it is treated as "no keys, no reference" so lightweight
    parm stand-ins keep working.
    """
    try:
        keyframes = parm.keyframes()
    except AttributeError:
        keyframes = ()
    except _READ_ERRORS:
        return {"keyframe_count": None, "source": None, "known": False}
    count = len(keyframes) if isinstance(keyframes, (list, tuple)) else 0

    try:
        source = parm.getReferencedParm()
    except AttributeError:
        source = None
    except _READ_ERRORS:
        return {"keyframe_count": count, "source": None, "known": False}
    if source is not None:
        try:
            if source == parm:
                source = None
        except _READ_ERRORS:
            return {"keyframe_count": count, "source": None, "known": False}
    return {"keyframe_count": count, "source": source, "known": True}


def authored_fields(parm, evaluated) -> Dict[str, Any]:
    """Extra read fields for one parm: ``expression`` and
    ``expression_language`` when exactly one key drives it, ``keyframe_count``
    for the number of keys, ``raw`` when its string as written differs from
    ``evaluated``, or ``inspection: "unknown"`` when the parm cannot say what
    it holds.

    The count is measured on its own: ``expression()`` raises for a parameter
    with several keys, and the count must survive that (a multi-key parameter
    is the case H1-1 was about).
    """
    state = inspection(parm)
    if not state["known"]:
        # No count and no source, and neither may be read as "none".
        return {"inspection": "unknown"}
    count = state["keyframe_count"] or 0
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
    for key in ("raw", "expression", "expression_language", "keyframe_count",
                "inspection"):
        if any(key in fields for fields in per):
            out[key] = [fields.get(key) for fields in per]
    return out


# ---------------------------------------------------------------------------
# Writes: what the parm will hold after this, not what the caller asked for
# ---------------------------------------------------------------------------

#: How a write may meet an animated or referenced parm.
WRITE_MODES = ("refuse", "replace", "key_at_frame", "write_source")


class ParmWriteRefused(ValueError):
    """The write cannot land as asked; nothing was written.

    ``code`` is the stable reason a receipt reports. ``receipt`` is filled in
    by ``author_parm_write`` (or ``write_refusal``) with the full structured
    record so a route that only sees the exception can still return it.
    """

    def __init__(self, message, code="parm.refused", receipt=None):
        super().__init__(message)
        self.code = code
        self.receipt = receipt


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


def _plan_write(parm, mode, frame=None):
    """Resolve what will actually be written, or refuse before any mutation.

    ``frame`` is the declared frame context for ``key_at_frame``; it is carried
    here so the plan and the setter can never disagree about it.
    """
    state = inspection(parm)
    if not state["known"]:
        raise ParmWriteRefused(
            f"Cannot inspect {_label(parm)}: its animation or reference state "
            "could not be read. Nothing was written.",
            code="parm.inspection_unknown")
    source = state["source"]
    if source is not None:
        if mode != "write_source":
            raise ParmWriteRefused(
                f"{_label(parm)} is driven by {_label(source)}. Nothing was "
                "written. Pass mode='write_source' to write that parameter, "
                "or change the expression that drives it.",
                code="parm.reference_requires_write_source")
        parm = source
        # The source is a different parameter; inspect that one.
        state = inspection(parm)
        if not state["known"]:
            raise ParmWriteRefused(
                f"Cannot inspect {_label(parm)}, which drives the requested "
                "parameter: its animation or reference state could not be "
                "read. Nothing was written.",
                code="parm.inspection_unknown")

    keys = state["keyframe_count"] or 0
    if keys and mode == "refuse":
        raise ParmWriteRefused(
            f"{_label(parm)} has {keys} keyframe(s). Nothing was written. "
            "Pass mode='replace' to clear them, mode='key_at_frame' to add a "
            "key at the declared frame, or edit the expression instead.",
            code="parm.animated_requires_mode")
    if mode == "replace":
        return parm, "replace"
    if mode == "key_at_frame":
        # A key writes a number onto an animation channel. A text parameter
        # has no numeric domain, so accepting one here only produces a
        # numeric readback mismatch after the setter — a write that "ran" but
        # could never have landed. Refuse before the first setter.
        try:
            held = parm.eval()  # noqa: S307
        except _READ_ERRORS as exc:
            raise ParmWriteRefused(
                f"Cannot read {_label(parm)} to decide its key domain: {exc}. "
                "Nothing was written.",
                code="parm.inspection_unknown")
        if isinstance(held, str):
            raise ParmWriteRefused(
                f"{_label(parm)} is a text parameter. key_at_frame writes "
                "numeric keys; nothing was written. Set the text value "
                "directly, or key a numeric parameter.",
                code="parm.key_domain")
        if hou is None or not hasattr(hou, "Keyframe"):
            raise ParmWriteRefused(
                f"Cannot add a key to {_label(parm)}: Houdini is not "
                "available. Nothing was written.",
                code="parm.houdini_unavailable")
        if frame is None:
            raise ParmWriteRefused(
                f"Cannot add a key to {_label(parm)}: no frame was declared "
                "and none could be read. Nothing was written.",
                code="parm.frame_unknown")
        return parm, "key_at_frame"
    if keys:
        # write_source landed on an animated source; refuse rather than
        # replace its animation without being asked.
        raise ParmWriteRefused(
            f"{_label(parm)} has {keys} keyframe(s); write_source will not "
            "replace them. Nothing was written.",
            code="parm.animated_write_source")
    return parm, "set"


def _set_plain(parm, value) -> None:
    parm.set(value, follow_parm_reference=False)


def _set_key_at_frame(parm, value, frame) -> None:
    """Add a key at the *declared* frame, keeping the ones already there.

    The frame is passed in, never read from the playhead here: a queued or
    evidence-derived write must not land at wherever an artist happened to
    scrub. ``parm.set(value, follow_parm_reference=False)`` clears the
    animation on 22.0.400 (probed), so it is never used for this mode.
    """
    if hou is None or not hasattr(hou, "Keyframe"):
        raise ParmWriteRefused(
            f"Cannot add a key to {_label(parm)}: Houdini is not available.",
            code="parm.houdini_unavailable")
    key = hou.Keyframe()
    key.setFrame(frame)
    key.setValue(value)
    parm.setKeyframe(key)


def _snapshot(parm) -> Dict[str, Any]:
    """Everything a failed write must put back: value, keys, extrapolation.

    The keys alone are not enough. Houdini 22.0.400 resets a channel's
    extrapolation to Extend when keys are re-added (probed), so a Cycle
    channel restored from keys alone evaluates differently outside its keyed
    range.
    """
    snap: Dict[str, Any] = {"value": None, "raw": None, "keys": [],
                            "extrapolation": (None, None)}
    try:
        snap["value"] = parm.eval()
    except _READ_ERRORS:
        pass
    try:
        raw = parm.unexpandedString()
    except _READ_ERRORS:
        raw = None
    if isinstance(raw, str):
        # The authored string, not the expanded one: restoring the expanded
        # path would strip $HIP/$OS/$F4 and freeze a frame-dependent output.
        snap["raw"] = raw
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


def _restore(parm, snap: Dict[str, Any]) -> Dict[str, Any]:
    """Put the snapshot back and say what actually happened.

    Best effort: the original failure is what the caller sees, so a restore
    error is recorded as evidence and never raised. The returned record is the
    receipt's ``recovery``: which actions ran, whether the captured state reads
    back, and what failed.
    """
    actions: List[str] = []
    errors: List[str] = []

    def attempt(name, fn):
        try:
            fn()
        except _RESTORE_ERRORS as exc:
            errors.append(f"{name}: {exc}")
        else:
            actions.append(name)

    if snap["keys"]:
        attempt("deleteAllKeyframes", parm.deleteAllKeyframes)
        for index, key in enumerate(snap["keys"]):
            attempt("setKeyframe[%d]" % index, lambda k=key: parm.setKeyframe(k))
        for before, value in zip((True, False), snap["extrapolation"]):
            if value is None:
                continue
            attempt("setKeyframeExtrapolation[%s]" % before,
                    lambda b=before, v=value: parm.setKeyframeExtrapolation(b, v))
    elif snap["value"] is not None:
        restore = snap["raw"] if snap["raw"] is not None else snap["value"]
        attempt("set", lambda: parm.set(restore, follow_parm_reference=False))
    else:
        return {"state": "not_needed", "actions": [],
                "evidence": {"target": _label(parm),
                             "skipped": "nothing was captured"}}

    evidence: Dict[str, Any] = {"target": _label(parm), "errors": errors}
    if errors:
        return {"state": "failed", "actions": actions, "evidence": evidence}

    # A restore that returned is not yet a restore that landed. Read the
    # captured state back; if it cannot be read, say unknown rather than
    # verified.
    try:
        if snap["keys"]:
            restored = [(k.frame(), k.value()) for k in parm.keyframes()]
            expected = [(k.frame(), k.value()) for k in snap["keys"]]
            ok = restored == expected
        elif snap["raw"] is not None:
            ok = raw_authored(parm) == snap["raw"]
        else:
            ok = _close(parm.eval(), snap["value"])
    except _RESTORE_ERRORS as exc:
        evidence["verification_error"] = str(exc)
        return {"state": "unknown", "actions": actions, "evidence": evidence}
    if not ok:
        evidence["verified"] = False
        return {"state": "unknown", "actions": actions, "evidence": evidence}
    return {"state": "verified", "actions": actions, "evidence": evidence}


def _restore_all(parms, snapshots) -> Dict[str, Any]:
    """Restore every target and fold the per-target records into one recovery."""
    results = [_restore(parm, snap) for parm, snap in zip(parms, snapshots)]
    actions: List[str] = []
    errors: List[str] = []
    for result in results:
        actions.extend(result.get("actions") or ())
        evidence = result.get("evidence")
        if isinstance(evidence, dict):
            errors.extend(evidence.get("errors") or ())
    if any(result.get("state") == "failed" for result in results):
        state = "failed"
    elif any(result.get("state") == "unknown" for result in results):
        state = "unknown"
    elif actions:
        state = "verified"
    else:
        state = "not_needed"
    return {"state": state, "actions": actions,
            "evidence": {"targets": results, "errors": errors}}


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


#: The receipt's schema. Bump the suffix when a field's meaning changes, never
#: to add an optional field: readers may ignore what they do not know.
PARM_WRITE_RECEIPT_SCHEMA = "synapse.parm-write/1"

# Bound every receipt before it can enter a tool result (the 24 MB result that
# broke a later request on 9/30 is the reason caps exist at this layer).
_RECEIPT_MAX_STRING = 512
_RECEIPT_MAX_ITEMS = 32


def _bounded(value):
    """A value a receipt may carry: strings and collections cut to a limit."""
    if isinstance(value, str):
        return value[:_RECEIPT_MAX_STRING]
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in list(value)[:_RECEIPT_MAX_ITEMS]]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _RECEIPT_MAX_ITEMS:
                break
            out[str(key)[:_RECEIPT_MAX_STRING]] = _bounded(item)
        return out
    return value


def _values(items):
    """The scalar shape a single-component write has always returned."""
    items = list(items)
    return items if len(items) > 1 else items[0]


def _request_fields(request, mode, values, frame, queued,
                    targets=None, expect=None) -> Dict[str, Any]:
    """The receipt's request block: what was asked, and in which context.

    ``expected_session`` is the session the write was authorized under;
    ``observed_session`` is the session read when it actually ran; and
    ``observed_frame`` is the frame Houdini was on at that moment (never the
    declared one — ``frame`` above is the declaration). ``observed_target`` is
    the parameter the write actually reached, which differs from the requested
    name under ``mode='write_source'``. ``expect`` is the precondition the
    write was actually checked against. A context the route could not read is
    ``None``, never a stand-in.
    """
    request = request if isinstance(request, dict) else {}
    fields: Dict[str, Any] = {
        "request_id": request.get("request_id"),
        "node": request.get("node"),
        "parm": request.get("parm"),
        "mode": mode,
        "value": _values(values),
        "frame": frame,
        "queued": bool(queued),
        "expected_session": request.get("expected_session"),
        "observed_session": request.get("observed_session"),
        "observed_frame": request.get("observed_frame"),
        "observed_target": None,
        "expect": expect,
    }
    if targets:
        fields["observed_target"] = _values(
            [_label(target) for target, _ in targets])
    return fields


def _not_attempted_readback(values) -> Dict[str, Any]:
    return {
        "state": "not_attempted",
        "domain": "numeric",
        "requested": _values(values),
        "observed": None,
        "raw_authored": None,
        "evaluated_equal": None,
    }


def _no_recovery() -> Dict[str, Any]:
    return {"state": "not_needed", "actions": [], "evidence": {}}


def _receipt(*, request, write, targets, readback, recovery, error) -> Dict[str, Any]:
    return _bounded({
        "schema": PARM_WRITE_RECEIPT_SCHEMA,
        "request": request,
        "write": write,
        "target": targets,
        "readback": readback,
        "recovery": recovery,
        "error": error,
    })


def _attach_receipt(exc, receipt) -> None:
    """Put the receipt on the exception without ever masking the exception.

    Some exception types refuse attribute assignment. The receipt is useful
    but never more important than the original failure reaching the caller.
    """
    try:
        exc.receipt = receipt
    except Exception:
        pass


def write_refusal(message, code="parm.refused", request=None, mode="refuse",
                  values=(), frame=None, queued=False,
                  expect=None) -> ParmWriteRefused:
    """A ``ParmWriteRefused`` that already carries its structured receipt.

    A route that refuses before it has a parm to hand (a queued write with no
    precondition, say) still owes the caller the same shape as a write that
    reached Houdini and failed.
    """
    values = list(values) if values else [None]
    refused = ParmWriteRefused(message, code=code)
    refused.receipt = _receipt(
        request=_request_fields(request, mode, values, frame, queued,
                                expect=expect),
        write="not_attempted",
        targets=[],
        readback=_not_attempted_readback(values),
        recovery=_no_recovery(),
        error={"code": code, "message": message},
    )
    return refused


def _target_mapping(parms, targets) -> List[Dict[str, Any]]:
    return [
        {"requested": _label(original), "target": _label(target),
         "action": action}
        for original, (target, action) in zip(parms, targets)
    ]


def _readback(targets, values) -> Dict[str, Any]:
    """What the targets hold after the write, in the domain that decides it.

    A string parameter is compared as authored text (``raw_authored``), because
    ``$HIP/render/$F4.exr`` expanding under ``eval()`` is not a failed authored
    write. Everything else keeps the numeric tolerance. ``evaluated_equal``
    reports the old ``eval()`` comparison beside it so nothing is silently
    dropped.
    """
    requested = list(values)
    try:
        observed = [target.eval() for target, _ in targets]  # noqa: S307
    except _READ_ERRORS as exc:
        return {
            "state": "unknown",
            "domain": "numeric",
            "requested": _values(requested),
            "observed": None,
            "raw_authored": None,
            "evaluated_equal": None,
            "error": str(exc),
        }

    raw = [raw_authored(target) for target, _ in targets]
    authored_domain = (all(isinstance(value, str) for value in requested)
                       and all(text is not None for text in raw))
    if authored_domain:
        match = [text == value for text, value in zip(raw, requested)]
        domain = "authored-text"
    else:
        match = [_close(value, held) for value, held in zip(requested, observed)]
        domain = "numeric"
    evaluated_equal = [_close(value, held)
                       for value, held in zip(requested, observed)]
    return {
        "state": "match" if all(match) else "mismatch",
        "domain": domain,
        "requested": _values(requested),
        "observed": _values(observed),
        "raw_authored": _values(raw),
        "evaluated_equal": _values(evaluated_equal),
    }


def _readback_key(targets, values, frame) -> Dict[str, Any]:
    """What the targets hold at the declared frame, and whether a key is there.

    ``eval()`` answers for the playhead, so a key written at frame 12 while the
    artist sits on frame 5 would be reported against the wrong frame (or, on a
    parm whose only key is elsewhere, as an unrelated value). ``evalAtFrame``
    is in the introspected H22 symbol table for ``hou.Parm``; a stand-in
    without it falls back to ``eval()`` rather than failing the write.
    """
    requested = list(values)
    observed: List[Any] = []
    present: List[bool] = []
    try:
        for target, _ in targets:
            try:
                held = target.evalAtFrame(frame)
            except AttributeError:
                held = target.eval()  # noqa: S307
            observed.append(held)
            keys = target.keyframes()
            present.append(any(_close(key.frame(), frame)
                               for key in (keys or ())))
    except _READ_ERRORS as exc:
        return {
            "state": "unknown",
            "domain": "numeric-at-frame",
            "frame": frame,
            "key_present": None,
            "requested": _values(requested),
            "observed": None,
            "raw_authored": None,
            "evaluated_equal": None,
            "error": str(exc),
        }

    match = [_close(value, held) and has_key
             for value, held, has_key in zip(requested, observed, present)]
    return {
        "state": "match" if all(match) else "mismatch",
        "domain": "numeric-at-frame",
        "frame": frame,
        "key_present": _values(present),
        "requested": _values(requested),
        "observed": _values(observed),
        "raw_authored": None,
        "evaluated_equal": _values(
            [_close(value, held) for value, held in zip(requested, observed)]),
    }


#: The only authored states a queued write's precondition may name. A
#: misspelled key used to satisfy the handler's truthiness test while checking
#: nothing, so the write landed unguarded and reported ``applied``.
_EXPECT_KEYS = ("value", "raw_authored")


def validate_expect(expect) -> None:
    """Refuse a precondition that names no state this module can evaluate.

    Called before the main-thread hop (so a typo costs zero setters) and again
    inside ``_check_expect`` (so a direct caller gets the same answer). At
    least one entry must be present, and every entry must be one of
    ``value`` / ``raw_authored`` — anything else is a precondition nobody will
    check, which is worse than none because it reads as protection.
    """
    if expect is None:
        return
    if not isinstance(expect, dict):
        raise ParmWriteRefused(
            "A queued write's precondition must be a mapping. Nothing was "
            "written.", code="parm.precondition_invalid")
    unknown = sorted(str(key) for key in expect if key not in _EXPECT_KEYS)
    if unknown or not expect:
        named = ", ".join(repr(key) for key in unknown) if unknown else "no state"
        raise ParmWriteRefused(
            f"A queued write's precondition names {named}; the states this "
            f"module evaluates are {' and '.join(repr(k) for k in _EXPECT_KEYS)}. "
            "Nothing was written.", code="parm.precondition_invalid")


def _check_expect(targets, expect) -> None:
    """Revalidate a queued write's precondition on the main thread, pre-write."""
    validate_expect(expect)
    if expect is None:
        return
    for target, _ in targets:
        if "value" in expect:
            try:
                held = target.eval()  # noqa: S307
            except _READ_ERRORS:
                raise ParmWriteRefused(
                    f"Cannot revalidate the precondition on {_label(target)}: "
                    "its value could not be read. Nothing was written.",
                    code="parm.inspection_unknown")
            if not _close(expect["value"], held):
                raise ParmWriteRefused(
                    f"The precondition on {_label(target)} did not hold: "
                    f"expected {expect['value']!r}, found {held!r}. Nothing "
                    "was written.", code="parm.precondition_failed")
        if "raw_authored" in expect:
            held_raw = raw_authored(target)
            if held_raw != expect["raw_authored"]:
                raise ParmWriteRefused(
                    f"The authored-text precondition on {_label(target)} did "
                    "not hold. Nothing was written.",
                    code="parm.precondition_failed")


def author_parm_write(parms, values, mode: str = "refuse", parm_tuple=None,
                      request=None, frame=None, queued=False,
                      expect=None) -> Dict[str, Any]:
    """Write one parm or a tuple, then report what the parm actually holds.

    Every component is checked before any is written, so a tuple write is
    all-or-none unless a setter itself fails part way: then the earlier writes
    are restored and the receipt says ``partial``. The write is not followed
    through a parameter reference unless ``mode='write_source'`` says so.

    The legacy fields keep their shapes: ``value`` is the request, ``observed``
    is ``eval()`` after the write, ``mismatch`` is decided in the readback's
    comparison domain (authored text for strings, tolerance for numbers).
    ``receipt`` adds the schema-versioned record: request context, write state,
    target mapping, readback domain, recovery and a stable error code. On
    failure the receipt rides on the raised exception (``exc.receipt``) and the
    original exception is re-raised unchanged.
    """
    if mode not in WRITE_MODES:
        raise write_refusal(
            f"Unknown mode {mode!r}. Use one of: {', '.join(WRITE_MODES)}. "
            "Nothing was written.",
            code="parm.mode_invalid", request=request, mode=mode,
            values=values, frame=frame, queued=queued, expect=expect)

    parms = list(parms)
    values = list(values)
    if len(values) != len(parms):
        # A tuple of 3 refuses [7, 8] with InvalidSize; refuse it here, before
        # anything is written, rather than letting zip truncate.
        raise write_refusal(
            f"{len(values)} value(s) for {len(parms)} parameter(s). Nothing "
            "was written.",
            code="parm.arity_mismatch", request=request, mode=mode,
            values=values, frame=frame, queued=queued, expect=expect)

    # A declared frame is the frame. Only an immediate legacy call with none
    # reads the playhead, and the frame it used is reported.
    declared_frame = frame
    if mode == "key_at_frame" and declared_frame is None:
        if hou is None or not hasattr(hou, "frame"):
            raise write_refusal(
                "Cannot add a key: Houdini is not available and no frame was "
                "declared. Nothing was written.",
                code="parm.frame_unknown", request=request, mode=mode,
                values=values, frame=None, queued=queued, expect=expect)
        declared_frame = hou.frame()

    # Planning refuses before any snapshot or setter. Attach the receipt the
    # planner could not build (it has no request context).
    try:
        targets = [_plan_write(parm, mode, declared_frame) for parm in parms]
    except ParmWriteRefused as exc:
        if not isinstance(exc.receipt, dict):
            _attach_receipt(exc, _receipt(
                request=_request_fields(request, mode, values,
                                        declared_frame, queued, targets=[],
                                        expect=expect),
                write="not_attempted",
                targets=[],
                readback=_not_attempted_readback(values),
                recovery=_no_recovery(),
                error={"code": exc.code, "message": str(exc)},
            ))
        raise

    plain = all(
        target[0] is parm and target[1] == "set"
        for parm, target in zip(parms, targets))

    # A queued proposal is revalidated here, on Houdini's main thread, right
    # before the first mutation — never on the caller's thread during preflight.
    try:
        _check_expect(targets, expect)
    except ParmWriteRefused as exc:
        if not isinstance(exc.receipt, dict):
            _attach_receipt(exc, _receipt(
                request=_request_fields(request, mode, values,
                                        declared_frame, queued, targets=targets,
                                        expect=expect),
                write="not_attempted",
                targets=_target_mapping(parms, targets),
                readback=_not_attempted_readback(values),
                recovery=_no_recovery(),
                error={"code": exc.code, "message": str(exc)},
            ))
        raise

    # Snapshot every target before the first write. A tuple write commits each
    # component in turn, so a value the last component refuses must not cost
    # the earlier ones their value or their animation.
    target_parms = [target[0] for target in targets]
    snapshots = [_snapshot(parm) for parm in target_parms]
    applied = 0
    try:
        if parm_tuple is not None and len(parms) > 1 and plain:
            # Nothing to unwrap or clear: keep the tuple write as one call, the
            # shape the handler has always used.
            parm_tuple.set(values)
            applied = len(values)
        else:
            for (parm, action), value in zip(targets, values):
                if action == "replace":
                    _replace(parm, value)
                elif action == "key_at_frame":
                    _set_key_at_frame(parm, value, declared_frame)
                else:
                    _set_plain(parm, value)
                applied += 1
    except Exception as exc:
        # Restoring must never replace the failure it answers. Every restore is
        # attempted; what it did is the receipt's recovery evidence.
        recovery = _restore_all(target_parms, snapshots)
        _attach_receipt(exc, _receipt(
            request=_request_fields(request, mode, values,
                                    declared_frame, queued, targets=targets,
                                    expect=expect),
            write="partial" if applied else "unknown",
            targets=_target_mapping(parms, targets),
            readback=_not_attempted_readback(values),
            recovery=recovery,
            error={"code": getattr(exc, "code", "parm.write_failed"),
                   "message": str(exc)},
        ))
        raise

    key_write = any(action == "key_at_frame" for _, action in targets)
    try:
        readback = (_readback_key(targets, values, declared_frame)
                    if key_write else _readback(targets, values))
    except Exception as exc:
        # A setter may have landed; without a readback it is applied but
        # unverified. Do not auto-restore an ambiguous result.
        _attach_receipt(exc, _receipt(
            request=_request_fields(request, mode, values,
                                    declared_frame, queued, targets=targets,
                                    expect=expect),
            write="applied",
            targets=_target_mapping(parms, targets),
            readback={
                "state": "unknown",
                "domain": "numeric",
                "requested": _values(values),
                "observed": None,
                "raw_authored": None,
                "evaluated_equal": None,
                "error": str(exc),
            },
            recovery=_no_recovery(),
            error={"code": "parm.readback_failed", "message": str(exc)},
        ))
        raise

    receipt = _receipt(
        request=_request_fields(request, mode, values, declared_frame, queued,
                                targets=targets, expect=expect),
        write="applied",
        targets=_target_mapping(parms, targets),
        readback=readback,
        recovery=_no_recovery(),
        error={"code": None, "message": None},
    )
    return {
        "value": _values(values),
        "observed": readback["observed"],
        "authored": {
            "mode": mode,
            "keyframe_count": [keyframe_count(parm) for parm, _ in targets],
            "wrote": [_label(parm) for parm, _ in targets],
            "frame": declared_frame,
        },
        "mismatch": readback["state"] != "match",
        "receipt": receipt,
    }

