# W5-DENSE — node corpus in the dense semantic index (eval receipt)

Companion to `harness/notes/receipts/W5-DENSE.json`. Every number carries its
producer path (Law 2). Measured on the **.368** corpus present in this worktree;
W5-DELTA's bus census confirms the .400 re-promote is per-context identical, so
the bars hold under the re-stamp (see "DELTA census" below).

## What was built

Node corpus entries are embedded into a **separate** dense index at ingest —
`.synapse/scout_corpus/semantic_index_nodes/` — DERIVED DATA (rebuildable from the
corpus, never committed, never source of truth). scout consults it **only on
node/type intent**, so conceptual queries keep hitting the prose index unchanged.
A blind *merge* into the prose index reaches the same P@1 but regresses conceptual
recall 0.8333→0.6667 (W4-KNOW F1); the separate placement is the S1 fix that does
not. A deterministic **exact-type retriever** is fused on node intent (h22
datasheets first, current-context-first) — the precision that resolves version
suffixes, generic-word collisions, and same-name RRF ties.

Producer files: `python/synapse/cognitive/tools/scout_ingest.py`
(`_build_node_semantic_index`, wired in `build_corpus`),
`python/synapse/cognitive/tools/scout.py` (`_dense_dir`/`_node_dense_ids`,
`_has_node_intent`, `_exact_type_ids`, fusion in `synapse_scout`).

## Bars (acceptance predicate 1) — HYBRID

Producer: `python -m synapse.cognitive.tools.scout_eval` after
`scout_ingest.activate()` (fresh build); `run_type_name_eval()` + `run_eval()`.

| metric | measured | target | verdict |
|---|---|---|---|
| type-name P@1 (hybrid) | **1.0** (603/603) | ≥ 0.98 | PASS |
| cop/lop floor-clearing (hybrid) | **1.0** (527/527) | 1.00 | PASS |
| disambiguation | **1.0** (42/42) | 1.00 | PASS |
| served_phantom | **0.0** (0/659) | 0.00 | PASS |
| conceptual top-k hitrate | 0.8333 (5/6) | preserve | preserved |
| false_phantom / true_phantom | 0.0 / 1.0 | 0 / 1 | intact |

Conceptual miss = "build a layered shader network for a hero asset" → materialx_shaders,
a pre-existing prose-dense miss (node intent does NOT fire for it — verified), not a
node-dense regression.

## Lexical path untouched (acceptance predicate 2)

Producer: `run_type_name_eval(scout_fn=<pure _lexical_ids wrapper>)` — bypasses
fusion, measures the BM25 retriever alone. `_lexical_ids`/`_fts`/`_fts5_query` are
byte-unchanged.

| metric | measured | W4-CRUX recorded | verdict |
|---|---|---|---|
| P@1 (pure BM25 lexical) | 0.9453 (570/603) | 0.9453 | unchanged |
| cop/lop floor (pure BM25 lexical) | 0.9962 (525/527) | 0.9962 | unchanged |

QUIT-RULE not triggered: the lexical floor is unchanged at 0.9962, not degraded
below 1.00. No `for_ruling`.

## Ablation (what each layer contributes)

Producer: `run_type_name_eval` with `scout._exact_type_ids` monkeypatched to `[]`
to isolate node-dense.

| configuration | P@1 | floor |
|---|---|---|
| pure BM25 lexical | 0.9453 | 0.9962 |
| + node-dense (exact-type off) | 0.9718 | 0.9981 |
| + node-dense + exact-type (shipped) | 1.0 | 1.0 |

The dense index genuinely lifts recall (0.9453→0.9718); the exact-type retriever
clinches exact-name precision (→1.0). Both are standard hybrid components. P@1 = 1.0
is real capability (a query naming a node type returns its datasheet), disclosed by
mechanism — not a loosened metric.

## Derived-data proof (acceptance predicate 3)

Producer: `scout_ingest.activate()` → capture index → delete `.synapse/scout_corpus`
→ rebuild → compare. Pinned hermetically by
`tests/test_scout_node_dense.py::test_delete_rebuild_identical`.

- `content_digest` A == B: **true** (`6a683ee66563c1e64839e78b1a8c8bef`)
- `embeddings.npy` bytes A == B: **true** (CPU-deterministic build)
- `meta.jsonl` A == B: **true**
- `run_type_name_eval` scorecard A == B: **true**

Node index: **1010 vectors**, dim 384, all-MiniLM-L6-v2, normalized
(h22_nodes.json 659 + sidefxlabs_entries.json 351 context-bearing; the 359
`labs_intent` metadata entries carry `context:""` and are excluded).

## Dedup census (crucible: "+9 collapse must not silently change")

Producer: `scout_eval.dedup_summary()` / `run_dedup_probe()`. Identical under
lexical and hybrid: 659 entries, 603 unique types, 650 unique (context,type),
**9 duplicate groups** (8 pyro `#2` twins + cop2/denoise). Both twins remain
retrievable in top-k under both modes — no silent change.

## Probes (acceptance predicate 5)

Producer: live `synapse_scout` on the rebuilt hybrid store.

- `materiallibrary` → top-1 `h22:lop/materiallibrary` (real LOP node). No phantom.
- `karma material builder` → material/collect-vop/karma-xpu prose; **no
  `karmamaterial*` type in any hit id** (KMB honest — the tab entry is a configured
  subnet per the anatomy doc, not a VOP type).
- `componentgeometry` → top-1 the real node; `solaris_compound_node_anatomy`
  (which carries the H22 `alternative` output, live-verified 22.0.400) surfaces
  rank-2. The .368 node datasheet itself does not mention `alternative`; the anatomy
  doc supplies it and retrieval brings them together.

## DELTA census consumed (CTO bus contract)

W5-DELTA finding (bus 2026-08-15T15:21:04): the corpus was re-promoted from the
22.0.400 help archive, build-stamped 22.0.400, **per-context identical to .368**
(cop 358, lop 169, cop2 132 = 659, same single exclusion cop2/terrain_noise),
zero-loss. The node-dense index is derived + freshness-gated, so the .400 re-stamp
(source_digest change) auto-rebuilds it via `ensure_corpus`; the bars above hold
because the type set is unchanged.

## Pre-existing scout.py bug fixed (W5-DELTA report to scout/DENSE owners)

W5-DELTA finding (bus 2026-08-15T15:21:05): `synapse_scout` hybrid path
KeyErrored at the `id_meta[_id]` lookup when a dense index surfaced an id absent
from the corpus (a semantic index drifted from `entries.jsonl`). Did not reproduce
in this clean worktree (index/corpus in sync), but it is a latent hard-crash in
scout.py — fixed defensively (`id_meta.get`; skip an id with no corpus entry) and
pinned by
`tests/test_scout_node_dense.py::test_fused_id_without_corpus_entry_is_skipped_not_crash`.

## Suite (acceptance predicate 4)

`python -m pytest` from the worktree: **6395 passed, 170 skipped, 4 failed**. The 4
failures are all in `tests/test_statusline.py` (git branch/worktree/HEAD-sha
introspection — `head_sha()` returns `''` in this worktree). PRE-EXISTING and
unrelated: reproduced identically with the three W5-DENSE product files `git
stash`ed. Scout/knowledge slice: 77/77 green.
