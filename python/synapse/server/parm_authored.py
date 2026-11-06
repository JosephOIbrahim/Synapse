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
    ``expression_language`` when keyframes drive it, ``keyframe_count`` for the
    number of keys, ``raw`` when its string as written differs from
    ``evaluated``, otherwise nothing."""
    try:
        keyframes = parm.keyframes()
        if isinstance(keyframes, (list, tuple)) and keyframes:
            expression = parm.expression()
            if not isinstance(expression, str):
                return {}
            return {"expression": expression,
                    "expression_language": str(parm.expressionLanguage()),
                    "keyframe_count": len(keyframes)}
    except _READ_ERRORS:
        return {}
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
    """The parm this one is driven by, or None when it is its own source."""
    try:
        source = parm.getReferencedParm()
    except _READ_ERRORS:
        return None
    return None if source is None or source is parm else source


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
    if keys and mode in ("refuse", "write_source"):
        raise ParmWriteRefused(
            f"{_label(parm)} has {keys} keyframe(s), so a plain write would "
            "add a key or be ignored. Nothing was written. Pass "
            "mode='replace' to clear the keys, mode='key_at_frame' to add a "
            "key at the current frame, or edit the expression instead.")
    return parm, ("replace" if keys and mode == "replace" else "set")


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
    targets = [_plan_write(p, mode) for p in parms]

    plain = all(
        target[0] is parm and target[1] == "set"
        for parm, target in zip(parms, targets))
    if parm_tuple is not None and len(parms) > 1 and plain:
        # Nothing to unwrap or clear: keep the tuple write as one call, the
        # shape the handler has always used.
        parm_tuple.set(values)
    else:
        for (parm, action), value in zip(targets, values):
            if action == "replace":
                parm.deleteAllKeyframes()
            parm.set(value, follow_parm_reference=False)

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
