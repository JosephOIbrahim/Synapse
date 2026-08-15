# Filling out the other Houdini 22 contexts — recon report

**Date:** 2026-08-15 · **Live build:** 22.0.400 · **Question:** what does it take for SYNAPSE to understand every context of SideFX Houdini 22, not just COP and LOP?

**Bar for this report** (chosen at intake): the **knowledge layer only**. Success is `scout` / `knowledge_lookup` / `recall` answering node-and-parameter questions for every relevant context, phantom-guarded, at the same bar COP and LOP already meet. Not new MCP tool families. Not planner or recipe coverage.

---

## The answer, in one paragraph

**The machinery already exists and it works.** The wiki parser built for COP/LOP was run this session against 2,581 pages across 10 contexts on 22.0.400 and threw **zero exceptions**, reproducing the shipped corpus's COP count exactly (358/358). The corpus's COP/LOP skew is an artifact of what one ingest leg happened to extract — **not** a code filter. New entries would load and serve with zero changes to `knowledge.py`.

So the work is not "build an ingest system." It is: **widen the scope, patch four known parser defects, fix a retrieval path that is already failing at today's scale, and move the store off a single eager JSON before it becomes a memory regression inside Houdini.**

The uncomfortable finding is the third one. **Retrieval fails at 1x, not 8x.** More knowledge poured into the current path would make SYNAPSE more confidently wrong, not more useful.

---

## What was run

Two waves, 19 agents, ~1.9M subagent tokens.

**Wave 1 — seven context dives + serving seam + adversarial pass.** 9/9 returned. Each context agent sampled real doc pages, judged parser fit, designed the live probe and join key, and priced the work.

**Wave 2 — nine build-side agents + adversarial pass.** 7/9 returned. The parser spike, scale, retrieval, runtime-truth, harness shape, evals, and law agents all reported.

**What did not return, and is therefore not covered here:**

- The **cache-vs-zip source ruling** agent. I answer it below from my own evidence, but it lacks the formal cross-check.
- The **non-node surfaces** agent (VEX functions, hscript expressions, HOM). This is a real gap — see Open Items.
- The **wave-2 crucible**. Wave 2's numbers have not been adversarially attacked. Wave 1's have.

---

## Five findings that change the plan

### 1. The parser generalizes — this is measured, not estimated

The spike executed `i1_extract.py` against the 22.0.400 archive rather than judging it by reading.

| context | sampled | summary | parameters | note |
|---|---|---|---|---|
| **top** | 148 (full) | 98.0% | 89.9% | every param-bearing page carries internal names |
| **chop** | 135 (full) | 97.8% | 98.5% | but internal-name evidence on only 47% |
| **sop** | 400 of 1,172 | 96.5% | 94.3% | 7,749 params, 19.4/page |
| **dop** | 400 of 502 | 88.3% | 95.8% | heaviest include user — 363/400 pages |
| **vop** | 400 of 1,207 | 82.0% | **45.0%** | 55% of pages carry no `@parameters` at all |
| **apex** | 400 of 612 | 96.5% | **0.0%** | total structural miss — see below |

**APEX's zero is a one-line fix, not a rewrite.** Its pages use `@inputs`/`@outputs` port sections, which the `PARAM_SECTIONS` whitelist at `i1_extract.py:121` excludes. Widening that whitelist takes APEX from 0/400 to **390/400 (97.5%)**, yielding 1,944 ports of which 1,915 carry descriptions. The same widening recovers VOP's missing half.

Verdict: **reusable with patches.**

### 2. Retrieval is already broken at today's scale

This is the finding that should reorder the work.

- **40 of 40** natural-language node questions returned a confident **wrong** answer. `knowledge.py:141` bails out of the node path when a query exceeds 2 tokens, so any question phrased as a sentence falls through to an H21 prose index that answers `found=True` at 0.4–0.9 confidence.
- **Scout cannot see the node corpus at all.** Its serving store holds 906 entries and shares **zero rows** with the 659 node entries — they are silently dropped at ingest because they carry no `id` or `searchable_text` field. An agent following the CLAUDE.md §11.15 instruction to scout before emitting an API gets nothing from the corpus.
- **The key is context-blind.** Entries are keyed on bare type name, and the collision magnitude is real under either of two measures: by doc-page filename stems at target scope, **182 stems span more than one context, destroying 253 of 4,345 unique stems** (reproduced independently in pre-flight; the wave-2 agent's 254/4,393 differs only in folder filtering); by `#internal:` header names across all 11 doc folders, **239 names collide** (the eval agent's measure, used for the disambiguation metric below). `noise` exists in COP, SOP, VOP and CHOP simultaneously.
- **Half the corpus is invisible.** Only the first 12 parameter *labels* are returned; **336 of 659 entries (51%)** exceed 12 params, one has 279. Internal names and channels — the fields needed to actually set a parm — are never returned.

Pouring 4,000 more entries into this path multiplies the wrong answers.

### 3. Storage becomes a memory regression inside Houdini

Measured, not projected: **11,970 bytes per entry** on disk (re-verified: 7,888,653 / 659), of which the `parameters` array is **97.7%** (re-verified: 0.977). Load is eager, whole-file, uncached — and SYNAPSE holds **two resident** `KnowledgeIndex` instances inside the Houdini process (`router.py:186` and `handlers.py:1772`, both verified; a third construction site at `scout_ingest.py:99` is build-time only).

Calibrated against the archive (2.041x doc-bytes-to-corpus-bytes expansion, measured on the three built contexts), full coverage of nine contexts across 4,029 pages projects to **31.2 MB compact / 37.6 MB on disk** — roughly a **76 MB resident regression** in the artist's Houdini session.

SOP alone is **44.9%** of that. VOP has the most pages (1,212) but only 9.7% of the bytes — page count badly mispredicts cost.

**Ruling: SQLite with an FTS5 table over parameter text, served lazily**, with per-context JSONL shards kept as the git-tracked, human-reviewable build source the existing gate writes.

Good news on the other side: **serve cost is already capped and does not grow.** Responses measure mean 495 B (~124 tokens), max 966 B. Eight times the data changes what is *searched*, not what is *returned*.

### 4. Three things I told the team were wrong

Worth stating plainly because two of them were my errors, propagated into agent prompts.

- **The scout symbol table is already 22.0.400** — 35,908 symbols, commit `86af98c4`, +5/−0 versus .368. I briefed it as .368 and three of seven context agents repeated that without checking. Only the **corpus** is .368-stale.
- **The recall→RAG gap is closed.** `handlers_memory.py::_augment_with_knowledge` is wired into both the search and recall handlers and pinned by a test. My memory said recall sees Moneta only; that is out of date.
- **The semantic index is live in the serving path**, not write-only — 103 vectors at dim 384, RRF-fused with lexical BM25 in scout's dense path.

There is also an **unresolved denominator discrepancy**: my live GUI-session probe counted SOP 1746 / VOP 1310 / Object 189; the crucible's headless `hython` probe on the same host counted **1690 / 1305 / 186**. Neither is wrong — they are different processes with different packages loaded. The reproducible denominator must come from headless `hython`, and every published coverage number must split **HFS-native from third-party** (194 of the SOP types are Labs/MOPs HDAs).

### 5. The law permits this, and the guards do not cover it

**INGEST-01** — the standing rule at `harness/SYNAPSE_INGEST.md:62` that forbade wiring doc-derived entries into the corpus — was **already discharged** by RULING 175. What satisfies it is a *build-time* filter: `rag_promote_h22.py` writes an entry only if it matched a live type, so a phantom is never served because it is never stored. That same mechanism satisfies it identically at 5,000 entries.

But: **neither phantom lint would see a single new corpus entry.** Both scan `python/synapse/**/*.py` source or `emitted_node_types.json`. Node-type strings inside `createNode("...")` are AST constants the lint never judges. `emitted_node_types.json` is a **mirror of source, not a permission list** — corpus growth cannot widen it.

So the corpus is guarded at build time and unguarded at every downstream checkpoint. That asymmetry needs a new conformance test, not a new rule.

**One hard prohibition:** do **not** add `apex`/`rig`/`kinefx` to `authoring_domains.json`. That is a deterministic hard fail in `check_no_rigging_drift` (`checks.py:361-363`), enforcing ruling D-H22-2 — APEX knowledge is **federated to SideFX's own APEX MCP**, and SYNAPSE owns no local APEX corpus by decision. The parser can read APEX pages beautifully; policy says don't ship them.

---

## Per-context assessment

| context | live (headless) | doc pages | parser | ingest | priority |
|---|---|---|---|---|---|
| **SOP** | 1,690 (~1,55x native¹) | 1,203 | needs multiparm fix | **L** | 1 |
| **TOP** | 183 | 158 | needs adaptation | M | 2 |
| **VOP** | 1,305 | 1,212 | needs `@inputs` policy | M–L | 2 |
| **DOP** | 505 | 591 | needs tab-indent fix | M | 2 |
| **OBJ + ROP** | 186 + 90 | 98 + 57 | needs `:includeprop` | M | 2 |
| **CHOP** | 149 | 137 | generalizes | **S** | 4 |
| **APEX** | n/a — no `hou` category | 618 | one-line fix reads it | L | **blocked by policy** |

¹ The native/third-party split was measured in a GUI session whose totals ran higher than headless; the exact native count must come from the headless probe's `bucket` field when the ING-SOP leg runs (`s0_typedump.py::classify()`).

**SOP is first** — the geometry core, the largest surface, zero coverage today, and the routing layer already emits ~40 SOP types with nothing backing them.

**TOP is the sharpest asymmetry in the repo:** 19 shipped `tops_*` MCP tools against zero node-semantics knowledge, in the context with SYNAPSE's worst historical phantom-API record. It is also cheap — 148 pages, full population already parsed at 98% summary / 89.9% params.

**CHOP is the freebie** — S effort, proven parser, 135 pages — but lowest artist leverage today.

**APEX is where the parser succeeds and policy stops us.** Worth a decision, not a build.

---

## The four parser patches

1. **Widen `PARAM_SECTIONS`** to include `@inputs`/`@outputs` (`i1_extract.py:121`). Recovers APEX entirely and VOP's missing half. One line.
2. **Fix the tab-indent math in `_indent()`.** A tab counts as one column, so tab-indented body lines under space-indented items drop their descriptions — 23 lines lost on a single sampled DOP microsolver page.
3. **Stop folding depth-1 nesting into menu values on SOP.** Correct for COP menu values; wrong for SOP multiparm *instances*, which are real per-instance parameters.
4. **Resolve or record `:includeprop`.** 266 of 266 occurrences unresolved (100%) — targets live in `houdini/soho/parameters/*.ds`, outside the help archive. Dominant on OBJ/ROP.

Two further constructs need a decision rather than a fix: `#type:` on documented items is silently dropped (the pending-item binder handles only id/channels/contentfrom), and VEX attribute references at line start (`@P`, `@Cd`) are false-matched as section markers.

Also: **repoint the pinned build.** `harness/notes/h9/helpdoc.py:45` hardcodes `BUILD="22.0.368"` and other legs import it — parameterize, don't mutate.

---

## How this runs

**Reuse `harness/autoresearch/`, do not build a new harness.** It already is an unattended per-context probe campaign: mission JSON → detached `hython` → atomic evidence plus a DONE/FAILED sentinel. The only new construction is a per-context ledger over `legs.json` and a freshness gate in `checks.py`.

**One leg per context**, `ING-<CTX>`, each writing only `harness/notes/ingest/<ctx>/` plus a receipt. Because those paths are disjoint, **the data legs need no worktree** — dying at context 4 of 8 leaves 1–3 untouched structurally, not luckily. The two *code* legs (parser patches, `knowledge.py` changes) **do** need worktree isolation.

**Six human gates**, four non-negotiable: scope ratification before any leg runs; consumer-fix review on `knowledge.py`; the per-context wiring flip into `rag/corpus/`; and merge to master. Calibration sign-off and build re-ratification are delegable.

---

## How we prove it

**Reuse `scout_eval.py`** — the 211-line scorecard that drove the false-phantom rate from 0.667 to 0, already release-blocking via `test_gate6`.

**No human writes an answer key.** All four sources are machine-derived: the live catalogue snapshot for existence and context, and the archive's own `#internal:`/`#context:`/`#tags:` headers for identity. 120 items per context, seeded RNG, committed sha256 so a regenerate-to-pass shows up in the diff.

| metric | bar |
|---|---|
| live coverage vs **native** types | ≥ 0.80 |
| floor-clearing among served entries | **1.00** (measured 1.00 today) |
| served phantom rate | **0.00**, release-blocking |
| retrieval precision@1 on type-name queries | ≥ 0.98 |
| context disambiguation on the 239-name collision set | **1.00** |

Everything except the live probes runs on a stock CI runner — the precedent is already in `ci.yml:109`.

---

## Recommended sequence

**Do the retrieval fixes before the bulk ingest.** They are small, they are needed at today's scale regardless, and without them every added entry increases confident-wrong answers.

1. **Retrieval repair.** Emit `id` + `searchable_text` at promote time so scout can see the corpus at all. Key by `(context, type)` with a disambiguation list instead of a silent pick. Add `context` and `k` parameters to the tool schema. Replace the 2-token bail-out with a type-name intent test. Return internal names, not just 12 labels. Add a similarity floor so the dense path can say "not found."
2. **Parser step — now a fork needing a human ruling** (see the resolved source-ruling item below): either the four patches above on `i1_extract` (proven, calibrated, supported doc surface), or a bookish-AST adapter that replaces the hand parser and upgrades the join from LABEL to ID (`attrs.id`), at the cost of depending on an internal SideFX API and a hython-coupled regen step. Either way, calibration regression on COP/LOP/COP2 proves nothing already-shipped regresses.
3. **Storage move** to SQLite + FTS5 before SOP lands, since SOP alone is 45% of the projected mass.
4. **Ingest, cheapest-proof-first:** CHOP (S, proves the loop) → TOP (highest asymmetry) → DOP → OBJ/ROP → VOP → SOP.
5. **APEX:** a policy decision, not a build.

---

## Open items

- ~~The cache-vs-zip source ruling lacks its formal agent.~~ **RESOLVED (late arrival, post-publication).** The xref agent returned after the report shipped, and its ruling is **neither source as-found**: regenerate Houdini's own help AST **headlessly on the running build** via `houdinihelp.hconfig/hpages` + `bookish`, into a SYNAPSE-owned cache dir. Verified by execution, artifact corroborated: **5,481 `/nodes/` pages parsed in 170s with 0 errors** (6,281 JSON files on disk, spot-checked: `sop/xform` carries `attrs.id` with real runtime parm names — `t`, `r`, `s` — and APEX pages arrive typed as `inputs_section` ports). What the AST buys over `i1_extract`: include/`#contentfrom` resolution for free (the exact 805 lines the hand parser reimplements), typed sections instead of indentation inference, and **an ID join** (`attrs.id` coverage: cop 99%, top 97%, lop 75%, sop 64%, vop 57%) with LABEL as fallback — "the single largest correctness upgrade available." What it costs: `bookish`/`houdinihelp` is an **internal, undocumented SideFX API** (a Houdini major can break it silently), and regeneration **requires hython** (build-coupled; no plain-CI regen). The on-disk OneDrive cache is confirmed unusable as a source: 30% populated, build-mixed across .368/.400, **no version stamp anywhere in the format** — and the AssetIndexer burst (1,435 files written in one minute on 2026-07-15) explains its shape. This creates a **fork the human must rule on** at the parser step: proven-calibrated `i1_extract` + 4 patches (supported surface, weaker join) vs. bookish-AST adapter (richer, ID join, internal API). The adapter path moots patches 1, 2 and 4; the multiparm-semantics question survives either way. This ruling has **not** been through a crucible; its execution claims were artifact-corroborated and spot-checked only.
- **Non-node surfaces are uncovered** — VEX functions, hscript expressions, HOM. "Understanding a context" includes these, and no agent reported on them. This is the largest hole in the recon.
- **`knowledge.py:160` hardcodes "Houdini 22.0.368"** in its agent hint (verified verbatim), and the corpus loads with **zero build-stamp check** — silent staleness, where scout is loud on the same mismatch. Fix before mixing .400 entries in.

## Pre-flight verification (2026-08-15, second-model re-check)

The report was re-checked claim-by-claim after assembly, prioritizing wave-2 findings that had not been through a crucible. Method: deterministic local re-computation and independent re-execution — no reliance on the original agents' outputs.

**Reproduced independently:**
- **Parser spine.** A fresh 36-page sample (different seed, `.400` archive, `parse_page` via a live `helpdoc` repoint to 22.0.400): **zero exceptions**; APEX 7/8 summaries with **0/8 parameters**; SOP 8/8 params; VOP only 1/6 param-bearing; DOP/TOP/CHOP at spike-consistent rates. The spike's pattern holds exactly. Side proof: the `.368→.400` repoint is two module attributes (`helpdoc.BUILD`, `helpdoc.HELP_DIR`), confirming the parameterization work item.
- **Retrieval failure.** 5/5 natural-language node questions through the real `KnowledgeIndex`: all `found=True` at 0.58–0.78 confidence, all answered from H21-era prose — including a Copernicus blur question served legacy `cop2net` guidance. The confident-wrong class is live, not theoretical.
- **Headless denominator — settled.** One clean `hython` run on 22.0.400: Sop 1690, Vop 1305, Object 186, Lop 222, Top 183, Dop 505, Chop 149, Driver 90. Matches the wave-1 crucible and the table above. The earlier GUI-session counts (Sop 1746) were inflated by session-loaded types; publish headless numbers only.
- **Collision counts.** Stem-based recount: 4,345 unique stems, 182 multi-context, 253 destroyed — matching the wave-2 agent to within folder-filtering (their 254/4,393).

**Verified verbatim at source:** `knowledge.py:45` (`_CONTEXT_RANK`), `:141` (2-token gate), `:160` (hardcoded .368 hint), the 12-label cap, the type-keyed index; corpus math (11,970 B/entry, 97.7% parameters, 336/659 entries over 12 params, max 279); `PARAM_SECTIONS` at `i1_extract.py:121`; `scout_ingest`'s id/`searchable_text` requirement; INGEST-01 at `SYNAPSE_INGEST.md:62`; RULING 175; `check_no_rigging_drift` at `checks.py:361-363`; symbol table stamped 22.0.400 / 35,908; `scout_eval.py` at 211 lines; `harness/autoresearch/` exists; `ci.yml:109`.

**Status change:** wave 2 is now *spot-verified on its load-bearing claims*, though still short of a full adversarial pass. No claim in this report was refuted by the pre-flight; three were sharpened (collision labeling, resident-instance count, denominator).

---

*Produced by a 19-agent two-wave recon; assembled under Opus 5, pre-flight re-verified under Fable 5. Full findings banked at `.token-saver/h22-context-recon.md` (wave 1) and `.token-saver/h22-context-recon-wave2.md` (wave 2).*
