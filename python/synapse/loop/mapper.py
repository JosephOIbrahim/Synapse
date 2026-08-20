"""mapper.py — deterministic gate policy for THE LOOP v5.1.

Pure spec, no side effects, no I/O: ALLOW iff every predicate is True;
BLOCK otherwise — a False predicate and an unevaluable (None) predicate
both block. Exercised by tests/probes only in V0.0; it is never a live
gate (the live gates are the port substrates in ports.py).
"""

from __future__ import annotations

from typing import Iterable, Optional, Union

ALLOW = "ALLOW"
BLOCK = "BLOCK"


def GATE_POLICY(predicates: Iterable[Union[bool, None]]) -> str:
    """Deterministic truth table:
        all True  -> ALLOW
        any False -> BLOCK
        any None  -> BLOCK   (unevaluable blocks: absent evidence is a block,
                              never a pass-by-omission)

    No I/O, no randomness, no exceptions for valid inputs. A non-bool/non-None
    predicate is a caller bug and raises — the policy never guesses.
    """
    seen_unevaluable = False
    for p in predicates:
        if p is None:
            seen_unevaluable = True
            continue
        if not isinstance(p, bool):
            raise TypeError(f"GATE_POLICY predicates must be bool or None, got {type(p).__name__}")
        if p is False:
            return BLOCK
    return ALLOW if not seen_unevaluable else BLOCK
