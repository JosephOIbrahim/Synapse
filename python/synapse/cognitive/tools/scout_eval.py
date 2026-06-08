"""
synapse.cognitive.tools.scout_eval
===================================

The phantom-rate & coverage eval — Spike 2 of the Scout Hardening harness, and
the standing efficacy pin for scout (it is also Spike 3's verdict instrument:
you cannot honestly claim semantic "beats" lexical without it).

It measures THREE things against a FIXED, EXTERNAL known-answer ground truth.
None of them is satisfiable by loosening a threshold — the ground truth is the
H21.0.671 reality, not whatever the corpus happens to contain today:

  (a) known-REAL symbols  → MUST be found        → **false-phantom rate** (target 0,
      release-blocking: a real API flagged fake actively tells the model a real
      thing is fake, which is worse than no gate at all).
  (b) known-PHANTOM symbols (incl. the four quarantined) → MUST be flagged
      not-found → **true-phantom recall** (target 1.0).
  (c) conceptual queries with a known-relevant doc → SHOULD land top-k →
      **conceptual top-k hit-rate** (the number that justifies or denies the
      semantic spike).

This module is a pure-Python measurement instrument — ZERO ``hou``
(tests/test_cognitive_boundary.py). It runs the LIVE scout and reports; it never
mutates scout, the corpus, or the ground truth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from synapse.cognitive.tools.scout import synapse_scout

# --------------------------------------------------------------------------- #
#  FIXED EXTERNAL GROUND TRUTH                                                 #
#  Reality = Houdini 21.0.671 / OpenUSD / PDG, NOT the corpus. Trimming this   #
#  to dodge a metric is gaming the eval (Commandment 7); test_scout_eval.py    #
#  guards the load-bearing members so the coverage gap cannot be hidden.       #
# --------------------------------------------------------------------------- #

# (a) Real, central H21.0.671 APIs (all match scout's dotted-symbol regex).
REAL_SYMBOLS: tuple[str, ...] = (
    "hou.LopNode", "hou.SopNode", "hou.RopNode", "hou.LopNetwork",
    "hou.Node", "hou.Geometry", "hou.node", "hou.parm",
    "pdg.EventType", "pdg.PyEventHandler",
    "pxr.Usd", "pxr.Sdf",
)

# (b) Phantoms that MUST flag not-found. The first four are SYNAPSE's quarantined
# canon (CLAUDE.md §11.15) — they must stay flagged-false through every change.
QUARANTINED: tuple[str, ...] = (
    "hou.pdg.workItem", "hou.secure", "hou.lopNetworks", "hou.updateGraphTick",
)
PHANTOM_SYMBOLS: tuple[str, ...] = QUARANTINED + (
    "hou.pdg.cookWorkItems", "hou.cookPDGGraph",
)

# (c) Conceptual queries → the doc id (reference-file stem) that should land top-k.
# Phrased to lean on meaning over keyword overlap, so they stress lexical recall.
CONCEPTUAL: tuple[tuple[str, str], ...] = (
    ("keep colors consistent between nuke and the houdini render", "aces_color_management"),
    ("split a render into separate passes for compositing later", "karma_aov"),
    ("simulate water pouring and splashing", "flip_simulation"),
    ("make a believable city full of moving people", "crowds"),
    ("build a layered shader network for a hero asset", "materialx_shaders"),
    ("warp a character mesh so it follows a skeleton", "kinefx_rigging"),
)


@dataclass(frozen=True)
class GroundTruth:
    real: tuple[str, ...] = REAL_SYMBOLS
    phantom: tuple[str, ...] = PHANTOM_SYMBOLS
    conceptual: tuple[tuple[str, str], ...] = CONCEPTUAL


DEFAULT_GROUND_TRUTH = GroundTruth()


# --------------------------------------------------------------------------- #
#  Scorecard                                                                   #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Scorecard:
    false_phantom_rate: float          # (a) real flagged not-found / total real   → 0
    true_phantom_recall: float         # (b) phantom flagged not-found / total      → 1
    conceptual_topk_hitrate: float     # (c) expected doc in top-k / total          → quality
    release_blocking: bool             # any real symbol missing → Sev-1
    real_total: int
    real_found: int
    real_missing: tuple[str, ...]      # the false phantoms — the coverage gap, named
    phantom_total: int
    phantom_flagged: int
    phantom_leaked: tuple[str, ...]    # phantoms NOT flagged (corpus holds a fake token)
    conceptual_total: int
    conceptual_hits: int
    conceptual_misses: tuple[str, ...] # queries whose expected doc missed top-k

    def to_dict(self) -> dict:
        return {
            "false_phantom_rate": self.false_phantom_rate,
            "true_phantom_recall": self.true_phantom_recall,
            "conceptual_topk_hitrate": self.conceptual_topk_hitrate,
            "release_blocking": self.release_blocking,
            "real": {"total": self.real_total, "found": self.real_found,
                     "missing": list(self.real_missing)},
            "phantom": {"total": self.phantom_total, "flagged": self.phantom_flagged,
                        "leaked": list(self.phantom_leaked)},
            "conceptual": {"total": self.conceptual_total, "hits": self.conceptual_hits,
                           "misses": list(self.conceptual_misses)},
        }

    def verdict(self) -> str:
        """The probe-first branch this scorecard implies (see harness §SPIKE 2)."""
        if self.release_blocking:
            return ("COVERAGE-GAP HALT — false-phantom rate > 0 outranks semantic. "
                    "Expand ingest scope (rag/ coverage / fold in G:'s real entries) "
                    "before the semantic spike.")
        if self.true_phantom_recall < 1.0:
            return ("PHANTOM LEAK — a quarantined/known-fake symbol resolved as real. "
                    "Corpus contains a fake token; fix before anything else.")
        if self.conceptual_topk_hitrate >= 0.8:
            return ("SEMANTIC LOW-VALUE — lexical conceptual recall already high. "
                    "Spike 3 may be unnecessary; pin the eval and stop.")
        return ("SEMANTIC JUSTIFIED — conceptual recall poor, coverage clean. "
                "Proceed to the human embedder gate.")


def _found_in_corpus(out: dict, symbol: str) -> Optional[bool]:
    for s in out.get("symbols", []):
        if s.get("symbol") == symbol:
            return bool(s.get("found_in_corpus"))
    return None        # scout did not ground the symbol at all (regex miss / no corpus)


def run_eval(
    scout_fn: Callable[..., dict] = synapse_scout,
    ground_truth: GroundTruth = DEFAULT_GROUND_TRUTH,
    k: int = 6,
) -> Scorecard:
    """Run the live scout over the fixed ground truth and score it.

    ``scout_fn`` is injectable so a test can bind it to a controlled corpus; the
    DEFAULT is the live ``synapse_scout`` and the DEFAULT ``ground_truth`` is the
    fixed external constant above (which the eval test guards)."""
    # (a) + (b): symbol grounding. A symbol scout fails to ground at all counts
    #            as not-found (real → false phantom; phantom → correctly flagged).
    real_missing: list[str] = []
    for sym in ground_truth.real:
        out = scout_fn(sym, k=1)
        if _found_in_corpus(out, sym) is not True:
            real_missing.append(sym)

    phantom_leaked: list[str] = []
    for sym in ground_truth.phantom:
        out = scout_fn(sym, k=1)
        if _found_in_corpus(out, sym) is True:
            phantom_leaked.append(sym)

    # (c): conceptual top-k retrieval.
    conceptual_misses: list[str] = []
    for query, expected_id in ground_truth.conceptual:
        out = scout_fn(query, k=k)
        if expected_id not in {h.get("id") for h in out.get("hits", [])}:
            conceptual_misses.append(query)

    n_real = len(ground_truth.real)
    n_phantom = len(ground_truth.phantom)
    n_concept = len(ground_truth.conceptual)
    real_found = n_real - len(real_missing)
    phantom_flagged = n_phantom - len(phantom_leaked)
    concept_hits = n_concept - len(conceptual_misses)

    return Scorecard(
        false_phantom_rate=round(len(real_missing) / n_real, 4) if n_real else 0.0,
        true_phantom_recall=round(phantom_flagged / n_phantom, 4) if n_phantom else 1.0,
        conceptual_topk_hitrate=round(concept_hits / n_concept, 4) if n_concept else 0.0,
        release_blocking=len(real_missing) > 0,
        real_total=n_real, real_found=real_found, real_missing=tuple(real_missing),
        phantom_total=n_phantom, phantom_flagged=phantom_flagged,
        phantom_leaked=tuple(phantom_leaked),
        conceptual_total=n_concept, conceptual_hits=concept_hits,
        conceptual_misses=tuple(conceptual_misses),
    )


if __name__ == "__main__":             # pragma: no cover
    import sys
    # Point the live scout at the materialized canonical corpus (build-if-absent),
    # mirroring the mcp_server wiring, then score it.
    from pathlib import Path
    from synapse.cognitive.tools import scout as _scout, scout_ingest as _ingest
    info = _ingest.ensure_corpus()
    _scout.RAG_ROOT = Path(info["store_root"]); _scout.VEX_ROOT = Path(info["store_root"])
    for _c in (_scout._CORPUS, _scout._FTS, _scout._DENSE, _scout._SYMS):
        _c.clear()
    card = run_eval()
    d = card.to_dict()
    w = sys.stdout.write
    w("=== SCOUT EVAL SCORECARD ===\n")
    w(f"false_phantom_rate      : {d['false_phantom_rate']}  (target 0, release-blocking)\n")
    w(f"true_phantom_recall     : {d['true_phantom_recall']}  (target 1.0)\n")
    w(f"conceptual_topk_hitrate : {d['conceptual_topk_hitrate']}\n")
    w(f"release_blocking        : {d['release_blocking']}\n")
    w(f"real    {d['real']['found']}/{d['real']['total']} found; missing={d['real']['missing']}\n")
    w(f"phantom {d['phantom']['flagged']}/{d['phantom']['total']} flagged; leaked={d['phantom']['leaked']}\n")
    w(f"concept {d['conceptual']['hits']}/{d['conceptual']['total']} top-k; misses={d['conceptual']['misses']}\n")
    w(f"VERDICT: {card.verdict()}\n")
