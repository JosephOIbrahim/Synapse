"""The allocation pre-gate (v5 §3) — *whether* a target deserves the substrate.

Runs BEFORE the search-vs-build test (``run_search``): one cheap structural
question per target — does it serve **authoring / composition / the render that
proves them**? Substrate-aligned → admit. Post-proof polishing (downstream) →
admit only on an explicit, recorded operator override. Out-of-scope → defer, not
worked. The verdict is recorded as an :class:`Allocation` (a first-class Ledger
kind) so a target **cannot be worked without one** (Ledger violation #6).

Pure: stdlib only, zero ``hou``/``pxr``. A future composer calls :func:`allocate`
at its head; today it is a standalone, testable primitive (like ``probe``).
"""

from __future__ import annotations

from dataclasses import dataclass

# thesis_locus → disposition.
SUBSTRATE_LOCI = ("authoring", "composition", "proof")   # the substrate itself → admit
DEFER_LOCI = ("out-of-scope",)                            # not worked → defer
OVERRIDE_LOCI = ("adjacent", "downstream")                # post/near-proof → operator-override
THESIS_LOCI = SUBSTRATE_LOCI + OVERRIDE_LOCI + DEFER_LOCI

VERDICTS = ("admit", "downstream", "defer")
DECIDERS = ("gate", "operator-override")


class AllocationHalt(Exception):
    """A downstream/adjacent target reached the gate with NO operator override —
    HALT-AND-SURFACE; do not decompose it (v5 §3)."""


@dataclass
class Allocation:
    """The substrate-relevance verdict (v5 §2). ``verified_by`` is usually
    ``V0_membership`` — the verdict is itself an artifact; ``against_build`` is
    mandatory (Task B). Projects to ``/SYNAPSE/agent/ledger/`` via
    :func:`to_ledger_record` (RFC Option C)."""

    target: str = ""
    verdict: str = ""                # admit | downstream | defer
    thesis_locus: str = ""
    rationale: str = ""
    decided_by: str = "gate"         # gate | operator-override
    verified_by: str = "V0_membership"
    against_build: str = ""

    def admits(self) -> bool:
        """May this target enter the Workflow graph? ``downstream`` admits ONLY
        with an operator override; ``defer`` never admits."""
        if self.verdict == "admit":
            return True
        if self.verdict == "downstream":
            return self.decided_by == "operator-override"
        return False


def allocate(target: str, thesis_locus: str, rationale: str, *,
             against_build: str, operator_override: bool = False,
             adjacent_admits: bool = False) -> Allocation:
    """The pre-gate. Returns an :class:`Allocation`, or raises
    :class:`AllocationHalt` for an un-overridden downstream/adjacent target.

    - ``authoring`` / ``composition`` / ``proof`` → **admit** (substrate-aligned)
    - ``out-of-scope`` → **defer**
    - ``downstream`` → requires ``operator_override`` (else HALT)
    - ``adjacent`` (one hop downstream — e.g. procedural-texture-feeds-material;
      the v5 §7 open question) → requires ``operator_override`` by DEFAULT
      (conservative); pass ``adjacent_admits=True`` to treat one-hop as admit.
    """
    if not (target or "").strip():
        raise ValueError("[allocate] target is empty — a gate cannot admit an unnamed target.")
    locus = (thesis_locus or "").strip()
    if locus in SUBSTRATE_LOCI:
        return Allocation(target, "admit", locus, rationale, "gate",
                          against_build=against_build)
    if locus in DEFER_LOCI:
        return Allocation(target, "defer", locus, rationale, "gate",
                          against_build=against_build)
    if locus == "adjacent" and adjacent_admits:
        return Allocation(target, "admit", locus, rationale, "gate",
                          against_build=against_build)
    if locus in OVERRIDE_LOCI:
        if operator_override:
            return Allocation(target, "downstream", locus, rationale,
                              "operator-override", against_build=against_build)
        raise AllocationHalt(
            f"target {target!r} is {locus!r} (post-proof / one-hop downstream) — "
            "requires an explicit operator override; HALT, do not decompose (v5 §3)."
        )
    raise ValueError(f"unknown thesis_locus {locus!r}; expected one of {THESIS_LOCI}")


def is_barred(allocation) -> bool:
    """A target with NO ``Allocation`` (``None``), or one that does not admit, is
    BARRED from the Workflow graph (Ledger violation #6). ``downstream`` never
    auto-admits; ``defer`` never admits."""
    return allocation is None or not allocation.admits()


def detect_redundant_pass(target: str, prior_allocations, *, new_evidence: bool = False) -> bool:
    """Self-policing (v5 §3): a SECOND allocation pass on an ALREADY-ADMITTED
    target with NO new evidence is the framework-edit-as-avoidance tell. ``True``
    → surface it (the way the constitution surfaces a third framework edit), don't
    re-run the gate."""
    already = any(
        getattr(a, "target", None) == target and a.admits()
        for a in (prior_allocations or [])
    )
    return already and not new_evidence


def to_ledger_record(a: Allocation, *, timestamp: str = ""):
    """Project an :class:`Allocation` to a ``kind="Allocation"`` LedgerRecord
    (RFC Option C — its modeled fields auto-project to ``/SYNAPSE/agent/ledger/``
    namespaced string attrs). Lazy import to avoid import-time coupling."""
    from synapse.memory.ledger import LedgerRecord
    return LedgerRecord(
        kind="Allocation",
        verified_by=a.verified_by or "V0_membership",
        against_build=a.against_build,
        target=a.target, verdict=a.verdict, thesis_locus=a.thesis_locus,
        rationale=a.rationale, decided_by=a.decided_by, timestamp=timestamp,
    )
