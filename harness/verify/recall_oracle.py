"""Recall-quality oracle: did this release's recall stack get better or worse?

Why this file exists
--------------------
The substring keyword scorer that ranks *every* returned memory
(``score_memories``, ``moneta_store.py:85-160``) has not been touched since
2026-05-31, and six waves of memory work went past it (review
``docs/reviews/synapse-review-2026-09-18.md:541``). Nobody could say whether a
release made recall better or worse except by one-off scratchpad scripts
(``:557,:587,:593``). This oracle is the answer key every retrieval change needs:
a fixed query set, replayed through the live recall stack on a **copy** of the
store, with each returned hit judged for relevance, and Precision@k / answer@1 /
IMPROVED-FLAT-REGRESSED computed in code.

Two independent halves, reported separately and honestly
-------------------------------------------------------
* **Live replay** (may be UNKNOWN). Copy ``<storage_dir>/.moneta`` to scratch,
  open ``MonetaBackedStore.from_storage_dir(scratch)`` with a DISTINCT storage
  URI (no lock collision with a live artist session), and replay the query set
  through BOTH entry points: ``store.search(MemoryQuery(...))`` (chat Tier-1) and
  ``SynapseMemory.recall(...)`` (typed lookup). If the backend/embedder cannot be
  provisioned in this interpreter (the known ``hython -m pytest`` env gotcha),
  this half is recorded UNKNOWN with a reason and **no number is faked**.
* **Jev relevance judgment** (always runs, needs no store). Each returned hit --
  or, when the live half is UNKNOWN, each pinned-probe pair from the review --
  is deterministically pre-labelled by content prefix in code; only the residual
  (ambiguous) pairs go to Jev, with ``scorer_score``/``cosine`` STRIPPED from the
  state so the judgment is not anchored on the existing scorer. Jev judges
  relevance only. Precision@k, answer@1 and the verdict are computed in code --
  Jev never emits the verdict.

Safety contract
---------------
* The live store is **only ever copied, never opened**. The store class is opened
  against the scratch copy under a distinct URI.
* ``SYNAPSE_LOG_DIR`` is redirected to scratch BEFORE any store import, so the
  ``Vector recall:`` telemetry never reaches ``~/.synapse/logs`` (this repo has a
  real "pytest pollutes the production log" incident;
  memory: synapse-pytest-pollutes-the-production-log).
* Read-only over the substrate. Mutates nothing but its own scratch copy and the
  report it prints. It does not touch the keyword scorer or any product code.

Answer key (review pinned probes, ``synapse-review-2026-09-18.md:555-593``)
--------------------------------------------------------------------------
1. stopword ``do I a to in on it up at``   -> NO returned hit is ``answers``/``on_topic``
2. ``banana bread recipe``                 -> every returned hit is ``unrelated``
3. ``how do I set up a karma render``      -> the superseded Solaris decisions are NOT ``answers``
4. ``Create a Solaris Network``            -> ``mem_9e0826890122`` is ``answers``

CLI::

    python harness/verify/recall_oracle.py                       # auto-locate live store, replay + judge
    python harness/verify/recall_oracle.py --storage-dir <dir>   # explicit .synapse dir (holds .moneta/)
    python harness/verify/recall_oracle.py --json                # emit the receipt-shaped JSON
    python harness/verify/recall_oracle.py --baseline b.json     # compare aggregates to a prior run
    SYNAPSE_JEV=off python harness/verify/recall_oracle.py        # skip Jev; deterministic pre-labels only

Exit code is 0 when every answer-key rule that could be judged PASSED (or was
UNKNOWN because Jev was off), 1 when any rule FAILED.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# the fixed query set + answer key
# ---------------------------------------------------------------------------

ANSWER_KEY_QUERIES: List[Dict[str, Any]] = [
    {
        "query": "do I a to in on it up at",
        "k": 5,
        "rule": "none_relevant",
        "note": "pure stopwords must not out-rank a real query (:555)",
    },
    {
        "query": "banana bread recipe",
        "k": 5,
        "rule": "all_unrelated",
        "note": "a cooking query shares only the generic word 'recipe' with the store (:557)",
    },
    {
        "query": "how do I set up a karma render",
        "k": 5,
        "rule": "not_answers",
        "targets": ["mem_5e63df8d83e6", "mem_cb67ac3da274", "mem_9e0826890122"],
        "note": "superseded Solaris set-dressing recipes are shared_words_only, not answers (:555)",
    },
    {
        "query": "Create a Solaris Network",
        "k": 10,
        "rule": "must_answer",
        "targets": ["mem_9e0826890122"],
        "note": "the exact trigger phrase must return its own v3 decision as an answer (:561)",
    },
]

PINNED_PROBE_PAIRS: List[Dict[str, str]] = [
    {
        "query": "do I a to in on it up at",
        "id": "mem_9e0826890122",
        "kind": "decision",
        "text": '**Decision:** "Create a Solaris Network" now = v3 recipe: '
                "GEO_sphere(sopcreate with embedded polygon sphere) -> "
                "MTL_matlib(materiallibrary, gold flake foil mtlxstandard_surface).",
    },
    {
        "query": "banana bread recipe",
        "id": "mem_9e0826890122",
        "kind": "decision",
        "text": '**Decision:** "Create a Solaris Network" now = v3 recipe: a Houdini '
                "Solaris/USD network of a gold sphere under studio lighting.",
    },
    {
        "query": "banana bread recipe",
        "id": "mem_cb67ac3da274",
        "kind": "decision",
        "text": '**Decision:** "Create a simple solaris network" now = v2 recipe: '
                "sopcreate sphere -> materiallibrary with GOLD FLAKE FOIL mtlx "
                "standard_surface -> rect area key light -> dome light.",
    },
    {
        "query": "how do I set up a karma render",
        "id": "mem_5e63df8d83e6",
        "kind": "decision",
        "text": '**Decision:** The phrase "Create a simple solaris network" should use '
                "THIS canned network: sopcreate sphere (in-place polygon) -> "
                "materiallibrary -> rect area key light -> dome light.",
    },
    {
        "query": "how do I set up a karma render",
        "id": "mem_cb67ac3da274",
        "kind": "decision",
        "text": '**Decision:** "Create a simple solaris network" now = v2 recipe: '
                "sopcreate sphere -> materiallibrary with GOLD FLAKE FOIL -> "
                "rect area key light -> dome light.",
    },
    {
        "query": "how do I set up a karma render",
        "id": "mem_9e0826890122",
        "kind": "decision",
        "text": '**Decision:** "Create a Solaris Network" now = v3 recipe: '
                "GEO_sphere -> MTL_matlib gold flake foil -> studio lighting.",
    },
    {
        "query": "Create a Solaris Network",
        "id": "mem_9e0826890122",
        "kind": "decision",
        "text": '**Decision:** "Create a Solaris Network" now = v3 recipe: '
                "GEO_sphere(sopcreate with embedded polygon sphere) -> "
                "MTL_matlib(materiallibrary, gold flake foil mtlxstandard_surface) "
                "-> rect area key light -> dome light. This is the canned network "
                "for that phrase.",
    },
]

MAX_HIT_CHARS = 1500

_TELEMETRY_PREFIXES = ('{"attempt":', '{"context_sha256"', '{"loop"', '{"rung"')
_TELEMETRY_KINDS = {"feedback"}


def prelabel(text: str, kind: str) -> Optional[str]:
    head = (text or "").lstrip()[:64]
    if any(head.startswith(p) for p in _TELEMETRY_PREFIXES):
        return "unrelated"
    if kind in _TELEMETRY_KINDS and head.startswith("{"):
        return "unrelated"
    return None


REL_OPTIONS = ("answers", "on_topic", "shared_words_only", "unrelated", "cannot_tell")

REL_INSTRUCTIONS = (
    "You judge whether a retrieved memory is relevant to a search query in a VFX / "
    "Houdini pipeline memory system. Judge relevance to the query's ACTUAL TASK, "
    "not mere word overlap. A memory that only shares vocabulary with the query but "
    "is about a different task is not a real answer. Choose exactly one level."
)

REL_CRITERIA = {
    "answers": "The memory directly answers the query's SPECIFIC task. If the query "
               "asks how to SET UP or CONFIGURE a render, an answer addresses render "
               "SETTINGS (samples, engine, denoiser, bounces, AOVs) -- NOT how to build "
               "or dress the scene. A scene- or network-BUILDING recipe is not an answer "
               "to a render-configuration query.",
    "on_topic": "The memory is about the same subject and would be useful context, "
                "though it does not directly answer the query.",
    "shared_words_only": "The memory shares meaningful subject vocabulary with the "
                         "query but is about a DIFFERENT task in a related area. "
                         "Headline case: a Solaris scene- or network-BUILDING, "
                         "set-dressing, or lighting recipe returned for a Karma "
                         "render-SETUP / render-configuration query is shared_words_only "
                         "(same domain, but building/dressing a scene is a different task "
                         "than configuring the render) -- NOT answers and NOT on_topic.",
    "unrelated": "The memory has nothing to do with the query's subject; at most it "
                 "shares an incidental generic word. Example: a Houdini Solaris recipe "
                 "returned for a 'banana bread recipe' cooking query is unrelated.",
    "cannot_tell": "There is not enough information in the memory text to judge.",
}


class JevClient:
    URL = "https://api.typesafe.ai/v1/systemone"

    def __init__(self, model: str = "jev-latest", timeout: float = 25.0):
        self.model = model
        self.timeout = timeout
        self.enabled = os.environ.get("SYNAPSE_JEV", "").strip().lower() != "off"
        self.key = os.environ.get("TYPESAFE_API_KEY", "").strip()
        self.calls = 0
        self.failures = 0
        self.last_error: Optional[str] = None
        if self.enabled and not self.key:
            self.enabled = False
            self.last_error = "TYPESAFE_API_KEY not set"

    def relevance(self, query: str, hit_text: str, kind: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        state = (
            f"QUERY: {query}\n"
            f"---\n"
            f"RETURNED MEMORY (kind: {kind}):\n"
            f"{(hit_text or '')[:MAX_HIT_CHARS]}"
        )
        body = {
            "state": state,
            "model": self.model,
            "questions": {
                "rel": {
                    "type": "choice",
                    "instructions": REL_INSTRUCTIONS,
                    "criteria": REL_CRITERIA,
                }
            },
        }
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            self.URL,
            data=data,
            headers={
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            self.failures += 1
            self.last_error = f"{type(exc).__name__}: {exc}"
            return None
        try:
            rel = payload["answers"]["rel"]
            return {
                "choice": rel["choice"],
                "confidence": rel.get("confidence"),
                "probabilities": rel.get("probabilities"),
            }
        except (KeyError, TypeError) as exc:
            self.failures += 1
            self.last_error = f"unexpected response shape: {type(exc).__name__}: {exc}"
            return None


def _default_storage_dir() -> Optional[Path]:
    candidates: List[Path] = []
    htd = os.environ.get("HOUDINI_TEMP_DIR")
    if htd:
        candidates.append(Path(htd) / "untitled" / ".synapse")
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()
    candidates.append(Path(tmp) / "houdini_temp" / "untitled" / ".synapse")
    candidates.append(Path(tmp) / "synapse" / "untitled" / ".synapse")
    best: Optional[Path] = None
    best_mtime = -1.0
    for c in candidates:
        snap = c / ".moneta" / "snapshot.json"
        if snap.exists():
            m = snap.stat().st_mtime
            if m > best_mtime:
                best_mtime, best = m, c
    return best


def _copy_store(storage_dir: Path, scratch: Path) -> Tuple[Optional[Path], Optional[str]]:
    src = storage_dir / ".moneta"
    if not (src / "snapshot.json").exists():
        return None, f"no snapshot.json under {src}"
    dst_store = scratch / "store"
    dst = dst_store / ".moneta"
    try:
        shutil.copytree(src, dst)
    except OSError as exc:
        return None, f"copy failed: {type(exc).__name__}: {exc}"
    try:
        with open(dst / "snapshot.json", encoding="utf-8") as fh:
            json.load(fh)
    except (ValueError, OSError) as exc:
        return None, f"copied snapshot did not parse (torn read?): {type(exc).__name__}: {exc}"
    return dst_store, None


def replay_live(storage_dir: Path, scratch: Path, k: int) -> Dict[str, Any]:
    out: Dict[str, Any] = {"status": None, "reason": None, "record_count": None,
                           "search": {}, "recall": {}, "storage_dir": str(storage_dir)}

    scratch_store, err = _copy_store(storage_dir, scratch)
    if err:
        out["status"] = f"UNKNOWN({err})"
        return out

    os.environ["SYNAPSE_LOG_DIR"] = str(scratch)
    os.environ.setdefault("SYNAPSE_MEMORY_BACKEND", "moneta")
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))

    try:
        from synapse.memory import moneta_runtime as mr
        if not mr.moneta_available():
            out["status"] = f"UNKNOWN(moneta backend not importable: {mr.import_error()})"
            return out
        from synapse.memory.moneta_store import MonetaBackedStore
        from synapse.memory.models import MemoryQuery, MemoryType
        from synapse.memory.store import SynapseMemory
    except Exception as exc:  # noqa: BLE001
        out["status"] = f"UNKNOWN(import failed: {type(exc).__name__}: {exc})"
        return out

    try:
        store = MonetaBackedStore.from_storage_dir(scratch_store)
    except Exception as exc:  # noqa: BLE001
        out["status"] = f"UNKNOWN(store open failed: {type(exc).__name__}: {exc})"
        return out

    sm = SynapseMemory.__new__(SynapseMemory)
    sm.store = store
    sm.storage_dir = scratch_store
    sm.project_path = None
    sm._on_memory_added = []
    sm._on_memory_updated = []

    try:
        out["record_count"] = int(getattr(getattr(store, "_handle", None), "ecs").n)
    except Exception:  # noqa: BLE001
        out["record_count"] = None

    for spec in ANSWER_KEY_QUERIES:
        q = spec["query"]
        kk = int(spec.get("k", k))
        try:
            results = store.search(MemoryQuery(text=q, limit=kk))
            out["search"][q] = [
                {"id": r.memory.id,
                 "kind": getattr(r.memory.memory_type, "value", str(r.memory.memory_type)),
                 "text": r.memory.content,
                 "scorer_score": float(r.score)}
                for r in results[:kk]
            ]
        except Exception as exc:  # noqa: BLE001
            out["search"][q] = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            mems = sm.recall(query=q, kinds=None, limit=kk)
            out["recall"][q] = [
                {"id": m.id,
                 "kind": getattr(m.memory_type, "value", str(m.memory_type)),
                 "text": m.content,
                 "scorer_score": None}
                for m in mems[:kk]
            ]
        except Exception as exc:  # noqa: BLE001
            out["recall"][q] = {"error": f"{type(exc).__name__}: {exc}"}

    try:
        store.close()
    except Exception:  # noqa: BLE001
        pass
    out["status"] = "ran"
    return out


def label_hits(pairs: List[Dict[str, Any]], jev: JevClient) -> List[Dict[str, Any]]:
    labelled: List[Dict[str, Any]] = []
    for p in pairs:
        det = prelabel(p.get("text", ""), p.get("kind", ""))
        if det is not None:
            p = {**p, "label": det, "label_source": "prelabel", "confidence": None}
        else:
            ans = jev.relevance(p["query"], p.get("text", ""), p.get("kind", ""))
            if ans is None:
                p = {**p, "label": None, "label_source": "jev_off_or_failed",
                     "confidence": None}
            else:
                p = {**p, "label": ans["choice"], "label_source": "jev",
                     "confidence": ans.get("confidence")}
        labelled.append(p)
    return labelled


_RELEVANT = {"answers", "on_topic"}


def compute_metrics(per_query: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    per: Dict[str, Any] = {}
    prec_vals: List[float] = []
    ans1_vals: List[float] = []
    for q, hits in per_query.items():
        judged = [h for h in hits if h.get("label") is not None]
        if not judged:
            per[q] = {"precision_at_k": None, "answer_at_1": None,
                      "n_hits": len(hits), "n_judged": 0}
            continue
        rel = sum(1 for h in judged if h["label"] in _RELEVANT)
        prec = rel / len(judged)
        ans1 = 1.0 if judged[0]["label"] == "answers" else 0.0
        per[q] = {"precision_at_k": round(prec, 3), "answer_at_1": ans1,
                  "n_hits": len(hits), "n_judged": len(judged),
                  "labels": [h["label"] for h in judged]}
        prec_vals.append(prec)
        ans1_vals.append(ans1)
    agg = {
        "mean_precision_at_k": round(sum(prec_vals) / len(prec_vals), 3) if prec_vals else None,
        "mean_answer_at_1": round(sum(ans1_vals) / len(ans1_vals), 3) if ans1_vals else None,
        "n_queries_judged": len(prec_vals),
    }
    return {"per_query": per, "aggregate": agg}


def verdict_vs_baseline(agg: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> str:
    cur = agg.get("mean_precision_at_k")
    if cur is None:
        return "UNKNOWN (nothing judged)"
    if not baseline:
        return "FLAT (baseline established)"
    base = baseline.get("mean_precision_at_k")
    if base is None:
        return "FLAT (baseline had no number)"
    if cur > base + 1e-9:
        return f"IMPROVED ({base:.3f} -> {cur:.3f})"
    if cur < base - 1e-9:
        return f"REGRESSED ({base:.3f} -> {cur:.3f})"
    return f"FLAT ({base:.3f} -> {cur:.3f})"


def check_answer_key(labelled_by_query: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    spec_by_q = {s["query"]: s for s in ANSWER_KEY_QUERIES}
    for q, hits in labelled_by_query.items():
        spec = spec_by_q.get(q)
        if not spec:
            continue
        rule = spec["rule"]
        judged = [h for h in hits if h.get("label") is not None]
        row = {"query": q, "rule": rule, "note": spec.get("note", "")}
        if not judged:
            row.update({"expected": rule, "jev": "no labels", "ok": None,
                        "detail": "nothing judged (Jev off/failed and no pre-label)"})
            results.append(row)
            continue

        if rule == "none_relevant":
            bad = [h for h in judged if h["label"] in _RELEVANT]
            row.update({"expected": "no hit answers/on_topic",
                        "jev": f"{len(bad)} relevant of {len(judged)}",
                        "ok": len(bad) == 0,
                        "detail": [f'{h["id"]}={h["label"]}' for h in bad] or "clean"})
        elif rule == "all_unrelated":
            bad = [h for h in judged if h["label"] != "unrelated"]
            row.update({"expected": "every hit unrelated",
                        "jev": f"{len(judged) - len(bad)}/{len(judged)} unrelated",
                        "ok": len(bad) == 0,
                        "detail": [f'{h["id"]}={h["label"]}' for h in bad] or "clean"})
        elif rule == "not_answers":
            targets = set(spec.get("targets", []))
            hit_targets = [h for h in judged
                           if (not targets or h["id"] in targets)]
            offenders = [h for h in hit_targets if h["label"] == "answers"]
            row.update({"expected": "superseded Solaris decisions NOT answers",
                        "jev": f"{len(offenders)} of {len(hit_targets)} labelled answers",
                        "ok": len(offenders) == 0,
                        "detail": [f'{h["id"]}={h["label"]}' for h in hit_targets]})
        elif rule == "must_answer":
            targets = set(spec.get("targets", []))
            named = [h for h in judged if h["id"] in targets]
            good = [h for h in named if h["label"] == "answers"]
            row.update({"expected": f"{sorted(targets)} labelled answers",
                        "jev": f"{len(good)}/{len(named)} of the named ids labelled answers",
                        "ok": (len(named) > 0 and len(good) == len(named)),
                        "detail": ([f'{h["id"]}={h["label"]}' for h in named]
                                   or f"named id not in returned hits ({sorted(targets)})")})
        else:
            row.update({"ok": None, "detail": f"unknown rule {rule}"})
        results.append(row)
    return results


def _pairs_from_live(live: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    by_q: Dict[str, List[Dict[str, Any]]] = {}
    for spec in ANSWER_KEY_QUERIES:
        q = spec["query"]
        hits = live.get("search", {}).get(q)
        if not isinstance(hits, list):
            by_q[q] = []
            continue
        by_q[q] = [{"query": q, "id": h["id"], "kind": h["kind"], "text": h["text"]}
                   for h in hits]
    return by_q


def _pairs_from_pinned() -> Dict[str, List[Dict[str, Any]]]:
    by_q: Dict[str, List[Dict[str, Any]]] = {}
    for p in PINNED_PROBE_PAIRS:
        by_q.setdefault(p["query"], []).append(
            {"query": p["query"], "id": p["id"], "kind": p["kind"], "text": p["text"]}
        )
    return by_q


def run(storage_dir: Optional[Path], k: int, baseline: Optional[Dict[str, Any]],
        jev: JevClient) -> Dict[str, Any]:
    scratch = Path(tempfile.mkdtemp(prefix="recall_oracle_"))
    live: Dict[str, Any] = {"status": "not attempted", "reason": None}
    try:
        sd = storage_dir or _default_storage_dir()
        if sd is None:
            live = {"status": "UNKNOWN(no live store located)", "search": {}, "recall": {},
                    "record_count": None, "storage_dir": None}
        else:
            live = replay_live(Path(sd), scratch, k)
    finally:
        try:
            shutil.rmtree(scratch, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass

    live_ran = str(live.get("status", "")).startswith("ran")

    if live_ran and any(isinstance(v, list) and v for v in live.get("search", {}).values()):
        pairs_by_q = _pairs_from_live(live)
        pair_source = "live_search_hits"
    else:
        pairs_by_q = _pairs_from_pinned()
        pair_source = "pinned_review_probes"

    labelled_by_q: Dict[str, List[Dict[str, Any]]] = {}
    for q, pairs in pairs_by_q.items():
        labelled_by_q[q] = label_hits(pairs, jev)

    metrics = compute_metrics(labelled_by_q)
    metrics["verdict"] = verdict_vs_baseline(metrics["aggregate"], baseline)
    answer_key = check_answer_key(labelled_by_q)

    return {
        "leg": "JEV-RECALL-ORACLE",
        "live_replay": live.get("status"),
        "live_record_count": live.get("record_count"),
        "live_storage_dir": live.get("storage_dir"),
        "pair_source": pair_source,
        "jev": {"enabled": jev.enabled, "model": jev.model, "calls": jev.calls,
                "failures": jev.failures, "last_error": jev.last_error},
        "labelled": labelled_by_q,
        "metrics": metrics,
        "answer_key_results": answer_key,
        "live_hits": {"search": live.get("search", {}), "recall": live.get("recall", {})},
    }


def render(report: Dict[str, Any]) -> str:
    L: List[str] = []
    add = L.append
    add("=" * 78)
    add("RECALL-QUALITY ORACLE")
    add("=" * 78)
    add(f"live replay        : {report['live_replay']}")
    if report.get("live_record_count") is not None:
        add(f"live record count  : {report['live_record_count']}")
    if report.get("live_storage_dir"):
        add(f"live storage dir   : {report['live_storage_dir']}")
    j = report["jev"]
    add(f"jev                : enabled={j['enabled']} model={j['model']} "
        f"calls={j['calls']} failures={j['failures']}"
        + (f" last_error={j['last_error']}" if j["last_error"] else ""))
    add(f"pairs judged from  : {report['pair_source']}")
    add("")
    add("METRICS (computed in code; Jev never emits the verdict)")
    agg = report["metrics"]["aggregate"]
    add(f"  mean Precision@k  : {agg['mean_precision_at_k']}")
    add(f"  mean answer@1     : {agg['mean_answer_at_1']}")
    add(f"  queries judged    : {agg['n_queries_judged']}")
    add(f"  VERDICT           : {report['metrics']['verdict']}")
    add("")
    add("  per-query:")
    for q, m in report["metrics"]["per_query"].items():
        add(f"    {q!r:42} P@k={m['precision_at_k']} answer@1={m['answer_at_1']} "
            f"({m['n_judged']}/{m['n_hits']} judged)")
        if m.get("labels"):
            add(f"        labels: {m['labels']}")
    add("")
    add("ANSWER KEY (review pinned probes :555-593)")
    all_ok = True
    for r in report["answer_key_results"]:
        mark = "PASS" if r["ok"] else ("UNKNOWN" if r["ok"] is None else "FAIL")
        if r["ok"] is False:
            all_ok = False
        add(f"  [{mark:7}] {r['query']!r}")
        add(f"            expected: {r['expected']}")
        add(f"            jev     : {r['jev']}")
        add(f"            detail  : {r['detail']}")
    add("")
    judged_rules = [r for r in report["answer_key_results"] if r["ok"] is not None]
    n_pass = sum(1 for r in judged_rules if r["ok"])
    add(f"RESULT: {n_pass}/{len(judged_rules)} judged answer-key rules PASSED"
        + ("" if all_ok else "  -- FAILURES PRESENT"))
    add("=" * 78)
    return "\n".join(L)


def _exit_code(report: Dict[str, Any]) -> int:
    return 0 if not any(r["ok"] is False for r in report["answer_key_results"]) else 1


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Recall-quality oracle: replay a fixed query set through the live "
                    "recall stack (on a store COPY) and judge relevance with Jev.",
    )
    ap.add_argument("--storage-dir", help="the .synapse dir holding .moneta/ "
                                          "(default: auto-locate the untitled store)")
    ap.add_argument("--k", type=int, default=5, help="top-k window (default 5)")
    ap.add_argument("--baseline", help="a prior run's aggregate JSON, to emit "
                                       "IMPROVED/FLAT/REGRESSED")
    ap.add_argument("--json", action="store_true", help="emit the receipt-shaped JSON")
    args = ap.parse_args(argv)

    baseline = None
    if args.baseline:
        try:
            with open(args.baseline, encoding="utf-8") as fh:
                loaded = json.load(fh)
            baseline = loaded.get("aggregate", loaded)
        except (OSError, ValueError) as exc:
            sys.stderr.write(f"warning: could not read baseline {args.baseline}: {exc}\n")

    jev = JevClient()
    report = run(Path(args.storage_dir) if args.storage_dir else None,
                 args.k, baseline, jev)

    if args.json:
        sys.stdout.write(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(render(report) + "\n")
    return _exit_code(report)


if __name__ == "__main__":
    raise SystemExit(main())
