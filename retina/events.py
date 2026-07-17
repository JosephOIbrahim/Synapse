"""The shared perception-event layer — the sibling contract every tier speaks.

Blueprint §3 fixes ONE versioned event shape for the whole tier ladder, and §7
fixes ONE persistence rule (sidecar JSONL; NO USD writes — RFC-gated, holder
M. Gold). T0 (tier 0, file truth) and T1 (tier 1, deterministic pixels) publish
the *same* envelope by importing these primitives, so siblinghood is
**structural**, not a copy-paste convention that can drift: change the shape here
and every tier moves together, and the conformance test
(``tests/test_retina_t1_schema.py``) fails loud if a tier stops matching.

Envelope (blueprint §3)::

    {"ch": PERCEPTION_CHANNEL, "v": EVENT_VERSION, "tier": <int>,
     "claim": <str>, "checks": [<check>...], "verdict": <str>,
     "proof": <path|None>, "at": <caller-supplied ISO timestamp>}

Check (``make_check``)::

    {"name": <str>, "pass": True|False|None, "detail": <str>, **extra}

``pass=None`` is the honest "could not run" (blueprint §7): a tier that cannot
run — no baseline yet, absent AOV, unreadable product — returns ``None``, NEVER a
silent pass. Roll-up is **fail > inconclusive > pass**: a single red fails the
frame; an inconclusive never masquerades as green.

Determinism: nothing here reads the clock — ``now`` is caller-supplied — so the
same inputs yield a byte-identical event (the ``perception_baseline`` purity
convention). This module imports zero ``hou`` and zero ``cv2``; it is pure stdlib.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import EVENT_VERSION, PERCEPTION_CHANNEL

# A check verdict: pass True/False, or None for the honest "could not run".
CheckVerdict = Optional[bool]


def make_check(name: str, passed: CheckVerdict, detail: str, **extra: Any) -> Dict[str, Any]:
    """One check record. ``passed`` is tri-state; ``extra`` carries numeric
    evidence (T1 checks attach measured value + threshold, e.g. ``leak_px=14,
    eps=32`` or ``val=0.9971, min=0.995``)."""
    d: Dict[str, Any] = {"name": name, "pass": passed, "detail": detail}
    d.update(extra)
    return d


def roll_up(checks: List[Dict[str, Any]]) -> str:
    """fail > inconclusive > pass — a single red fails the frame; an inconclusive
    never masquerades as green."""
    verdicts = [c["pass"] for c in checks]
    if any(v is False for v in verdicts):
        return "fail"
    if any(v is None for v in verdicts):
        return "inconclusive"
    return "pass"


def make_event(
    *,
    tier: int,
    claim: str,
    checks: List[Dict[str, Any]],
    proof: Optional[str],
    now: str,
) -> Dict[str, Any]:
    """Assemble a versioned perception event (blueprint §3 shape). The overall
    ``verdict`` is rolled up from the checks; ``now`` is caller-supplied so the
    event is a pure function of its inputs."""
    return {
        "ch": PERCEPTION_CHANNEL,
        "v": EVENT_VERSION,
        "tier": tier,
        "claim": claim,
        "checks": checks,
        "verdict": roll_up(checks),
        "proof": proof,
        "at": now,
    }


def emit_verdict(event: Dict[str, Any], jsonl_path: str | Path) -> None:
    """Append one verdict event as a line to the sidecar JSONL (blueprint §7:
    sidecar JSONL persistence until the customData RFC lands — NO USD writes).

    Append-only by construction, so a partial line is the worst failure mode; we
    write the whole JSON in one ``write`` call under a single open handle to keep
    each record atomic at the line level. ``sort_keys=True`` makes the line a
    deterministic function of the event.
    """
    p = Path(jsonl_path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(line)
