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
    ``expression_language`` when keyframes drive it, ``raw`` when its string
    as written differs from ``evaluated``, otherwise nothing."""
    try:
        keyframes = parm.keyframes()
        if isinstance(keyframes, (list, tuple)) and keyframes:
            expression = parm.expression()
            if not isinstance(expression, str):
                return {}
            return {"expression": expression,
                    "expression_language": str(parm.expressionLanguage())}
    except _READ_ERRORS:
        return {}
    raw = raw_string(parm, evaluated)
    return {"raw": raw} if raw is not None else {}


def authored_tuple_fields(parms, values) -> Dict[str, List[Any]]:
    """``authored_fields`` for a parm tuple: one list per field, aligned with
    ``values``, present only when some component has that field."""
    per = [authored_fields(p, v) for p, v in zip(parms, values)]
    out: Dict[str, List[Any]] = {}
    for key in ("raw", "expression", "expression_language"):
        if any(key in fields for fields in per):
            out[key] = [fields.get(key) for fields in per]
    return out
