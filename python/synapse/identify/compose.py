"""Pure composition of Identify bubble lines from per-node facts.

No ``hou`` and no Qt import lives here by contract (IDENTIFY_BLUEPRINT sec. 4):
``compose`` turns a plain fact dict into at most three bubble lines so it runs
off Houdini's main thread and is testable on system Python. The main-thread
writer (``apply``) only writes the text this module returns.

Fact dict shape consumed here (all values already resolved by ``facts`` off the
main thread — this module reads them, it never touches a live node)::

    {
      "type_label": "PolyBevel",           # type().description()
      "type_name":  "polybevel::3.0",       # fallback label only
      "category":   "Sop",                  # node category name
      "summary":    "Bevels polygonal ...", # library/HDA first sentence, or None
      "summary_source": "library"|"hda"|"unknown",
      "params": [                            # non-default parms, filtered HERE
        {"name": "offset", "label": "Offset", "kind": "float",
         "value": 0.07, "multi": False, "is_expression": False, "hidden": False},
        ...
      ],
      "lop_writes": {"first": "/stage/geo", "count": 3} | None,
      "errors": ["..."], "warnings": ["..."],
      "bypassed": False, "beta": False,
    }
"""
from __future__ import annotations

import re
from typing import Any


#: Per-line character budget. A starting value to tune at the GUI gate
#: (IDENTIFY_BLUEPRINT sec. 2), not a measurement.
WIDTH = 56

#: How many changed parameters the HERE line shows at most.
HERE_PARMS = 2

#: A single string parameter value is cut to this before the line-level cut.
_VALUE_STR_MAX = 24

#: Parameter kinds that never carry artist intent worth a bubble.
_STRUCTURAL_KINDS = frozenset({"folder", "folderset", "separator", "label"})

#: Ramp component internals: ``profileramp1value``, ``remapramp2pos`` ...
#: ``re.search`` so any ``ramp<digits><pos|value|interp>`` tail is dropped.
_RAMP_INTERNAL = re.compile(r"ramp\d+(pos|value|interp)$")


def _truncate(text: str, width: int = WIDTH) -> str:
    """Cut *text* to *width*, ending in ``...`` when it overflows."""
    text = text.replace("\n", " ").replace("\r", " ").rstrip()
    if len(text) <= width:
        return text
    if width <= 3:
        return "." * width
    return text[: width - 3].rstrip() + "..."


def _significant(value: float) -> str:
    """Three significant digits, without a trailing ``.0`` for round floats."""
    if value != value:  # NaN
        return "nan"
    if value in (float("inf"), float("-inf")):
        return "inf" if value > 0 else "-inf"
    text = f"{value:.3g}"
    return text


def _format_value(param: dict) -> str:
    """Render one parameter's value per the sec. 2 formatting rules."""
    if param.get("is_expression"):
        return "(expr)"
    if param.get("multi"):
        return "..."
    value = param.get("value")
    kind = param.get("kind")
    if kind == "toggle":
        return "on" if value else "off"
    if isinstance(value, bool):
        return "on" if value else "off"
    if isinstance(value, float):
        return _significant(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        text = value.strip()
        if len(text) > _VALUE_STR_MAX:
            return text[: _VALUE_STR_MAX - 3].rstrip() + "..."
        return text
    if value is None:
        return "..."
    return _truncate(str(value), _VALUE_STR_MAX)


def meaningful_params(params: list[dict]) -> list[dict]:
    """Drop folders, folder sets, separators, labels, hidden and ramp internals.

    This is the sec. 3 rule-6 filter, kept pure: it reads the ``kind``,
    ``hidden`` and ``name`` that ``facts`` already recorded, never a live parm.
    """
    kept: list[dict] = []
    for param in params or ():
        if not isinstance(param, dict):
            continue
        if param.get("kind") in _STRUCTURAL_KINDS:
            continue
        if param.get("hidden"):
            continue
        name = str(param.get("name", ""))
        if _RAMP_INTERNAL.search(name):
            continue
        kept.append(param)
    return kept


def _what_line(facts: dict, width: int) -> str:
    source = facts.get("summary_source")
    summary = facts.get("summary")
    if source in ("library", "hda") and summary:
        return _truncate(str(summary), width)
    label = facts.get("type_label") or facts.get("type_name") or "unknown"
    return _truncate(f"{label} - not in library", width)


def _here_line(facts: dict, width: int) -> str | None:
    # A LOP names the prims it last wrote, when the runtime provided them.
    writes = facts.get("lop_writes")
    if isinstance(writes, dict) and writes.get("first"):
        first = str(writes["first"])
        count = int(writes.get("count", 1) or 1)
        extra = max(count - 1, 0)
        line = f"writes {first}" + (f" (+{extra})" if extra else "")
        return _truncate(line, width)

    kept = meaningful_params(facts.get("params", []))
    if not kept:
        return None
    parts = []
    for param in kept[:HERE_PARMS]:
        label = str(param.get("label") or param.get("name") or "?")
        parts.append(f"{label} {_format_value(param)}".rstrip())
    return _truncate(", ".join(parts), width)


def _state_line(facts: dict, width: int) -> str | None:
    parts: list[str] = []
    errors = facts.get("errors") or []
    warnings = facts.get("warnings") or []
    if errors:
        parts.append(f"error: {str(errors[0])}")
    elif warnings:
        parts.append(f"warning: {str(warnings[0])}")
    if facts.get("bypassed"):
        parts.append("bypassed")
    if facts.get("beta"):
        parts.append("beta")
    if not parts:
        return None
    return _truncate(", ".join(parts), width)


def compose(facts: dict, width: int = WIDTH) -> list[str]:
    """Return at most three bubble lines: What, Here (optional), State (optional).

    The What line is always present. Here and State are added only when they
    carry content, so a clean node with no changes and no trouble is a single
    line.
    """
    if not isinstance(facts, dict):
        raise TypeError("compose expects a facts dict")
    lines = [_what_line(facts, width)]
    here = _here_line(facts, width)
    if here:
        lines.append(here)
    state = _state_line(facts, width)
    if state:
        lines.append(state)
    return lines


def bubble_text(facts: dict, width: int = WIDTH) -> str:
    """The composed lines as one newline-joined block (no sentinel)."""
    return "\n".join(compose(facts, width))
