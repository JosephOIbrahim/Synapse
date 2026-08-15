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


def _exists_in_runtime(out: dict, symbol: str) -> Optional[bool]:
    """The membership verdict from scout's introspected symbol table (Spike 2.5).
    None = scout did not ground the symbol, or no trustworthy table was loaded."""
    for s in out.get("symbols", []):
        if s.get("symbol") == symbol:
            v = s.get("exists_in_runtime")
            return None if v is None else bool(v)
    return None


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
        if _exists_in_runtime(out, sym) is not True:
            real_missing.append(sym)

    phantom_leaked: list[str] = []
    for sym in ground_truth.phantom:
        out = scout_fn(sym, k=1)
        if _exists_in_runtime(out, sym) is True:
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


# --------------------------------------------------------------------------- #
#  W4-KNOW Target 6 / predicate 6 — the type-name retrieval scorecard          #
#                                                                              #
#  The original scorecard above answers "does scout resolve API SYMBOLS?". The #
#  retrieval-repair leg added the NODE corpus (id + searchable_text at promote #
#  time), so scout can now be asked "does a bare NODE TYPE query land its       #
#  corpus entry, and does an ambiguous type disambiguate rather than guess?".   #
#                                                                              #
#  This is an INDEPENDENT instrument (append-only — the Scorecard/run_eval      #
#  above are untouched, so every existing scout_eval test still holds). It is   #
#  the number W4-CRUX re-runs adversarially; it is not trusted from this leg's  #
#  own output.                                                                  #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TypeNameScorecard:
    p_at_1: float                          # top-1 hit is an entry OF the queried type
    disambiguation_rate: Optional[float]   # bare-ambiguous -> full list; ctx-qualified -> exact
    served_phantom_rate: Optional[float]   # served type absent from the live catalogue -> phantom
    cop_lop_floor_clearing: float          # a cop/lop entry is retrievable in top-k
    p_at_1_total: int
    p_at_1_hits: int
    disambiguation_total: int
    disambiguation_ok: int
    served_phantom_checked: int
    served_phantom_leaked: tuple           # served types with no live-catalogue backing
    floor_total: int
    floor_cleared: int

    def to_dict(self) -> dict:
        return {
            "p_at_1": self.p_at_1,
            "disambiguation_rate": self.disambiguation_rate,
            "served_phantom_rate": self.served_phantom_rate,
            "cop_lop_floor_clearing": self.cop_lop_floor_clearing,
            "p_at_1_detail": {"total": self.p_at_1_total, "hits": self.p_at_1_hits},
            "disambiguation_detail": {"total": self.disambiguation_total,
                                      "ok": self.disambiguation_ok},
            "served_phantom_detail": {"checked": self.served_phantom_checked,
                                      "leaked": list(self.served_phantom_leaked)},
            "floor_detail": {"total": self.floor_total, "cleared": self.floor_cleared},
        }


def _parse_h22_id(hit_id: str):
    """('cop', 'blur') from 'h22:cop/blur' (or 'h22:cop/blur#2'); None if not an
    h22 node id."""
    s = str(hit_id or "")
    if not s.startswith("h22:"):
        return None
    body = s[4:].split("#", 1)[0]
    if "/" not in body:
        return None
    ctx, ntype = body.split("/", 1)
    return ctx, ntype.lower()


def load_served_node_corpus(corpus_path=None) -> list:
    """The served h22 node entries — the artifact promote writes. Defaults to the
    canonical rag/corpus/h22_nodes.json."""
    from pathlib import Path
    if corpus_path is None:
        corpus_path = (Path(__file__).resolve().parents[4]
                       / "rag" / "corpus" / "h22_nodes.json")
    import json as _json
    blob = _json.loads(Path(corpus_path).read_text(encoding="utf-8"))
    return blob.get("entries") or []


def live_types_by_context(cop_catalog=None, lop_catalog=None) -> dict:
    """Live node-type name sets per context from the committed live catalogues -
    the INDEPENDENT authority for served_phantom (promote's build-time gate is one
    source; this is a second). Missing catalogue => that context is absent from the
    map => its served types are not phantom-checkable (reported, never faked)."""
    from pathlib import Path
    import json as _json
    root = Path(__file__).resolve().parents[4] / "harness" / "notes"
    cop_catalog = cop_catalog or (root / "h22_cop_catalog_live_22.0.368.json")
    lop_catalog = lop_catalog or (root / "h22_lop_catalog_live_22.0.368.json")
    out: dict = {}
    try:
        cop = _json.loads(Path(cop_catalog).read_text(encoding="utf-8"))
        cats = cop.get("categories") or {}
        for cat_key, ctx in (("copNodeTypeCategory", "cop"),
                             ("cop2NodeTypeCategory", "cop2")):
            types = ((cats.get(cat_key) or {}).get("types")) or []
            names = types.keys() if isinstance(types, dict) else types
            out[ctx] = {str(t).lower() for t in names}
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    try:
        lop = _json.loads(Path(lop_catalog).read_text(encoding="utf-8"))
        types = lop.get("types") or {}
        names = types.keys() if isinstance(types, dict) else types
        out["lop"] = {str(t).lower() for t in names}
    except (OSError, ValueError, KeyError, AttributeError):
        pass
    return out


def run_type_name_eval(scout_fn: Callable[..., dict] = synapse_scout,
                       knowledge_index=None,
                       corpus_entries=None,
                       live_types=None,
                       k: int = 6,
                       sample: Optional[int] = None,
                       seed: int = 1234) -> TypeNameScorecard:
    """Score node-type retrieval + disambiguation on the served corpus.

    * P@1 — for each unique served type, scout(type, k=1) top-1 is an h22 entry OF
      that type (target >= 0.98).
    * disambiguation — for each type spanning >1 context, a bare KnowledgeIndex
      lookup returns a disambiguation listing ALL its contexts, and each
      context-qualified lookup returns that exact context's datasheet (target 1.00).
      None when no knowledge_index is available.
    * served_phantom — served types with no live-catalogue backing (target 0.00);
      None when no catalogue is available for any served context.
    * cop/lop floor-clearing — a cop/lop (context, type) entry is retrievable in
      scout's top-k (target 1.00, must not regress).

    scout_fn / knowledge_index / corpus_entries / live_types are injectable so a
    test can drive a controlled corpus; the defaults score the shipped artifact."""
    import random
    entries = corpus_entries if corpus_entries is not None else load_served_node_corpus()

    by_type: dict = {}
    for e in entries:
        t = str(e.get("type") or "").lower()
        if t:
            by_type.setdefault(t, set()).add(str(e.get("context") or ""))

    types = sorted(by_type)
    if sample and sample < len(types):
        types = random.Random(seed).sample(types, sample)

    # (a) P@1 on bare type-name queries.
    p_hits = 0
    for t in types:
        out = scout_fn(t, k=1)
        hits = out.get("hits") or []
        parsed = _parse_h22_id(hits[0].get("id")) if hits else None
        if parsed and parsed[1] == t:
            p_hits += 1
    p_total = len(types)

    # (b) disambiguation on the collision set (types with >1 context).
    dis_total = dis_ok = 0
    dis_rate: Optional[float] = None
    collisions = [t for t in types if len(by_type[t]) > 1]
    # Auto-build a KnowledgeIndex over the canonical rag/ ONLY when scoring the
    # shipped artifact (corpus_entries defaulted). An INJECTED corpus_entries is a
    # controlled fixture the shipped index would not match, so without an explicit
    # knowledge_index the disambiguation rate is UNKNOWN (None), never faked.
    if knowledge_index is None and corpus_entries is None:
        try:
            from pathlib import Path
            from synapse.routing.knowledge import KnowledgeIndex
            knowledge_index = KnowledgeIndex(
                rag_root=str(Path(__file__).resolve().parents[4] / "rag"))
        except Exception:
            knowledge_index = None
    if knowledge_index is not None:
        for t in collisions:
            dis_total += 1
            bare = knowledge_index.lookup(t)
            listed = {d.get("context") for d in (bare.disambiguation or [])}
            ok = bool(bare.disambiguation) and listed == by_type[t]
            for ctx in by_type[t]:
                r = knowledge_index.lookup(t, context=ctx)
                ok = ok and r.found and r.context == ctx and not r.disambiguation
            dis_ok += 1 if ok else 0
        dis_rate = round(dis_ok / dis_total, 4) if dis_total else 1.0

    # (c) served_phantom — served type absent from its context's live catalogue.
    if live_types is None:
        live_types = live_types_by_context()
    checked = 0
    leaked = []
    for e in entries:
        ctx = str(e.get("context") or "")
        t = str(e.get("type") or "").lower()
        if ctx in live_types:
            checked += 1
            if t not in live_types[ctx]:
                leaked.append("%s/%s" % (ctx, t))
    phantom_rate: Optional[float] = round(len(leaked) / checked, 4) if checked else None

    # (d) cop/lop floor-clearing — the shipped, non-legacy contexts must not regress.
    floor_total = floor_cleared = 0
    for e in entries:
        ctx = str(e.get("context") or "")
        t = str(e.get("type") or "").lower()
        if ctx not in ("cop", "lop"):
            continue
        floor_total += 1
        out = scout_fn(t, k=k)
        found = any((_parse_h22_id(h.get("id")) == (ctx, t))
                    for h in (out.get("hits") or []))
        floor_cleared += 1 if found else 0

    return TypeNameScorecard(
        p_at_1=round(p_hits / p_total, 4) if p_total else 0.0,
        disambiguation_rate=dis_rate,
        served_phantom_rate=phantom_rate,
        cop_lop_floor_clearing=round(floor_cleared / floor_total, 4) if floor_total else 0.0,
        p_at_1_total=p_total, p_at_1_hits=p_hits,
        disambiguation_total=dis_total, disambiguation_ok=dis_ok,
        served_phantom_checked=checked, served_phantom_leaked=tuple(leaked),
        floor_total=floor_total, floor_cleared=floor_cleared,
    )


# --------------------------------------------------------------------------- #
#  W5-DENSE — (context,type) dedup census + retrieval-side dedup probe          #
#                                                                              #
#  The node corpus carries same-(context,type) duplicates (the "+9 collapse"    #
#  W4-CRUX observed: 8 pyro twins + cop2/denoise, each with a "#2" id). Adding  #
#  the node-dense index MUST NOT silently change how those twins are indexed or  #
#  retrieved. These are append-only instruments (the Scorecard/run_eval/        #
#  run_type_name_eval above are untouched) so the dedup behaviour is receiptable #
#  and pinnable, not asserted from prose.                                        #
# --------------------------------------------------------------------------- #


def dedup_summary(corpus_entries=None) -> dict:
    """Corpus-level (context, type) duplicate census — pure structure of the
    served corpus, independent of any index. Reports entries, unique types,
    unique (context, type) pairs, and every duplicate group with its ids."""
    from collections import defaultdict
    entries = corpus_entries if corpus_entries is not None else load_served_node_corpus()
    groups: dict = defaultdict(list)
    for e in entries:
        ctx = str(e.get("context") or "")
        t = str(e.get("type") or "").lower()
        if ctx and t:
            groups[(ctx, t)].append(str(e.get("id")))
    dup = {"%s/%s" % (c, t): ids for (c, t), ids in groups.items() if len(ids) > 1}
    return {
        "entries": len(entries),
        "unique_types": len({str(e.get("type") or "").lower()
                             for e in entries if e.get("type")}),
        "unique_context_type": len(groups),
        "dup_groups": len(dup),
        "dup_detail": dict(sorted(dup.items())),
    }


def run_dedup_probe(scout_fn: Callable[..., dict] = synapse_scout,
                    corpus_entries=None, k: int = 6) -> dict:
    """Retrieval-side dedup behaviour: for each duplicate (context, type) group,
    which of its ids surface in scout(type, k). Receipts that the node-dense index
    neither silently drops nor multiplies a twin (crucible criterion). Compare the
    output across the lexical-only and hybrid scouts to prove no silent change."""
    summary = dedup_summary(corpus_entries)
    per_group: dict = {}
    for key in summary["dup_detail"]:
        ctx, t = key.split("/", 1)
        out = scout_fn(t, k=k)
        ids = [h.get("id") for h in (out.get("hits") or [])]
        surfaced = [i for i in ids if _parse_h22_id(i) == (ctx, t)]
        per_group[key] = {"expected_ids": summary["dup_detail"][key],
                          "surfaced_in_topk": surfaced}
    return {"census": summary, "per_group": per_group}


if __name__ == "__main__":             # pragma: no cover
    import sys
    # Point the live scout at the materialized canonical corpus (build-if-absent),
    # mirroring the mcp_server wiring, then score it.
    from pathlib import Path
    from synapse.cognitive.tools import scout as _scout, scout_ingest as _ingest
    info = _ingest.ensure_corpus()
    _scout.RAG_ROOT = Path(info["store_root"]); _scout.VEX_ROOT = Path(info["store_root"])
    for _c in (_scout._CORPUS, _scout._FTS, _scout._DENSE, _scout._SYMS, _scout._TABLE_CACHE):
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
    # W4-KNOW type-name scorecard (Target 6 / predicate 6).
    tn = run_type_name_eval().to_dict()
    w("\n=== TYPE-NAME SCORECARD (W4-KNOW) ===\n")
    w(f"p_at_1                 : {tn['p_at_1']}  (target >= 0.98)  {tn['p_at_1_detail']}\n")
    w(f"disambiguation_rate    : {tn['disambiguation_rate']}  (target 1.00)  {tn['disambiguation_detail']}\n")
    w(f"served_phantom_rate    : {tn['served_phantom_rate']}  (target 0.00)  {tn['served_phantom_detail']}\n")
    w(f"cop_lop_floor_clearing : {tn['cop_lop_floor_clearing']}  (target 1.00)  {tn['floor_detail']}\n")
