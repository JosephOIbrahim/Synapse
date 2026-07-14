"""perception_baseline — pure envelope builder for the Mile-5 perception baseline.

The perception channel (``synapse.host.tops_bridge.TopsEventBridge`` →
``TopsEvent``) had no frozen baseline: ``harness/state/leg0_baselines.json``
covers the connectivity, symbol-table, quarantine and test-pass channels but
NOT the stream of typed PDG events the agent perceives from inside Houdini.

This module supplies the one pure primitive that turns a captured sequence of
event dicts into a fixed, JSON-serializable envelope — the LEFT SIDE a future
drop-week diff can compare a live H22 perception capture against.

Purity contract
---------------
Zero ``hou`` / ``pdg`` at import time. The only Houdini-adjacent name,
``TopsEvent``, is referenced solely under ``TYPE_CHECKING`` (never imported at
runtime), so this module imports cleanly headless and in CI. The nondeterministic
``captured_at`` timestamp is a PASSED-IN argument — this function never calls
``now()`` — so the same events + the same ``captured_at`` always produce a
byte-identical envelope. The host-layer capture script
(``host/capture_perception_baseline.py``) owns the clock and the ``hou``/``pdg``
surface; this function owns only the shape.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Union

if TYPE_CHECKING:  # pragma: no cover - typing only, never imported at runtime
    from synapse.host.tops_bridge import TopsEvent

# An event may arrive as a live ``TopsEvent`` (duck-typed via ``.to_dict()``)
# or as an already-serialized event dict. The string forward ref keeps this a
# pure typing hint — no runtime import of ``TopsEvent`` occurs.
EventLike = Union["TopsEvent", Dict[str, Any]]

SCHEMA = "perception_baseline/v1"


def _event_to_dict(event: EventLike) -> Dict[str, Any]:
    """Normalize one event into a fresh, snapshot-independent dict.

    Accepts either a ``TopsEvent``-like object (anything exposing a callable
    ``to_dict()`` — the frozen per-event schema at
    ``tops_bridge.TopsEvent.to_dict``) or a mapping already in dict form.
    Returns a deep copy so the envelope is a value snapshot that cannot alias
    (or be mutated through) the caller's originals.
    """
    to_dict = getattr(event, "to_dict", None)
    if callable(to_dict):
        return copy.deepcopy(dict(to_dict()))
    if isinstance(event, Mapping):
        return copy.deepcopy(dict(event))
    raise TypeError(
        "perception_baseline events must be TopsEvent-like (with .to_dict()) "
        f"or a mapping; got {type(event).__name__!r}"
    )


def build_perception_baseline(
    events: Iterable[EventLike] | None,
    *,
    runtime: str,
    captured_at: str,
) -> Dict[str, Any]:
    """Wrap captured perception events in the fixed ``perception_baseline/v1`` envelope.

    Args:
        events: Iterable of captured events — ``TopsEvent``-like objects
            (normalized via ``.to_dict()``) or already-serialized event dicts.
            ``None`` is treated as an empty capture (a well-formed EMPTY
            baseline: ``count`` 0, ``events`` ``[]``).
        runtime: Free-text runtime label the capture ran against, e.g.
            ``"H21.0.671"`` or ``"headless"``. Keyword-only.
        captured_at: ISO-8601 timestamp string, PASSED IN by the caller so the
            pure function stays deterministic. Keyword-only.

    Returns:
        A new dict::

            {
                "schema": "perception_baseline/v1",
                "captured_at": <captured_at>,
                "runtime": <runtime>,
                "count": <N>,
                "events": [<event dict>, ...],
            }

        JSON-serializable whenever every event value is JSON-serializable.
    """
    event_dicts: List[Dict[str, Any]] = (
        [_event_to_dict(e) for e in events] if events is not None else []
    )
    return {
        "schema": SCHEMA,
        "captured_at": captured_at,
        "runtime": runtime,
        "count": len(event_dicts),
        "events": event_dicts,
    }
