"""The provenance rung scale — single source of truth (v5 §2 / §4a.2).

v4 collapsed three real rungs into ``V1``. v5 (ratified Option C, 2026-06-08)
refines the scale and makes it the gate for BOTH assertion (the Floor) and
exposure (the panel). This module is the ONE place the five tokens are defined;
``ledger.deposit`` validates against it, ``verified_claim`` gates "verified"
against it, and the DOC-1 conformance pin binds it so it cannot drift.

Pure: stdlib only, zero ``hou``/``pxr``. Importable from ``ledger`` (which is
heavier) WITHOUT a cycle.

    doc_only  →  V0_membership  →  V1_cook  →  V1_output      (+ V1-degraded, orthogonal)
    (prose;       (exists per       (cooks,     (the eval signal IS the
     backs         dir()/catalog)    no errors)   intended output: a rendered
     nothing)                                     pixel, or a bug reproduced
                                                  then resolved on a fresh seed)
"""

from __future__ import annotations

# The five canonical v5 rungs, weakest → strongest (V1-degraded is orthogonal).
RUNGS = ("doc_only", "V0_membership", "V1_cook", "V1_output", "V1-degraded")

# The rungs that may back the reserved word "verified" (v5 §4a.2). doc_only and
# V0_membership may NOT — existence/prose is not verification.
VERIFYING_RUNGS = ("V1_cook", "V1_output", "V1-degraded")

# The L0–L3 lattice layers a VerifiedClaim may name (L3/intent is not a
# "verified" layer — it is retrieval, not a cook).
LAYERS = ("L0", "L1", "L2")

# Legacy → v5 read shim (v5 §2 / RFC §1.1). Append-only: the source markdown and
# the immutable per-record files are NEVER rewritten; this maps at READ/backfill
# time. The CONSERVATIVE rule is load-bearing: legacy ``V1`` collapsed cook+output,
# so it reads as the WEAKER ``V1_cook`` and is NEVER auto-promoted to ``V1_output``
# — output-correctness must be re-earned by a fresh V1_output verification.
LEGACY_RUNG_MAP = {
    "V0": "V0_membership",
    "V1": "V1_cook",          # conservative — never V1_output
    "V1-degraded": "V1-degraded",
}


def _leading_token(s: str) -> str:
    """The leading token of an annotated value: ``"V1 (deterministic pin)"`` → ``"V1"``.
    Drops a trailing parenthetical, then takes the first whitespace-delimited word."""
    head = (s or "").split("(", 1)[0].strip()
    parts = head.split()
    return parts[0] if parts else ""


def migrate_verified_by(raw: str) -> str:
    """Map a raw ``verified_by`` token to the canonical v5 rung.

    v5 token → itself; legacy token → its conservative v5 mapping; anything else
    (empty, unknown) → ``""`` (the caller treats empty as a fail-closed reject).

    Annotated forms (``"V1 (deterministic pin)"`` / ``"V0 (citation self-check)"``)
    are recovered via the leading token so a real verified record is NEVER silently
    dropped on backfill (D-2 lossless). The conservative rule still holds: a leading
    ``V1`` maps to ``V1_cook``, never ``V1_output``.
    """
    tok = (raw or "").strip()
    for cand in (tok, _leading_token(tok)):
        if cand in RUNGS:
            return cand
        if cand in LEGACY_RUNG_MAP:
            return LEGACY_RUNG_MAP[cand]
    return ""


def is_verifying(verified_by: str) -> bool:
    """True iff this rung may back a "verified" claim (v5 §4a.2)."""
    return migrate_verified_by(verified_by) in VERIFYING_RUNGS
