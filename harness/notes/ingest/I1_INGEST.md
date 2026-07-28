# I1 — EXECUTE: the extractor, and the corpus it produced

**Leg** `I1` · **Harness** `INGEST-01` · **Run** 2026-07-27
**Subject** `$HFS/houdini/help/nodes.zip` — Houdini **22.0.368**, plus every other help zip behind it
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/i1.md` · **Gated on** `I0`
**Deliverable** `harness/notes/ingest/h22_node_corpus.json` — 693 entries, tiered per entry and per field
**Wiring** NONE. No file under `rag/`, no emission-path file, no product file was written.

---

## 0 · The gate, and two problems with it

`I1` is gated on `I0` because the join key is its finding. **At the time this leg ran, I0's product
was uncommitted** — it existed only in the working tree of a neighbouring worktree
(`.claude/worktrees/i0-ingest`), untracked.

That is R127's defect exactly: a claim resting on a copy nobody declared existed, reached by
globbing a neighbour. So this leg did not inherit I0's numbers. It:

1. recorded the **sha256 of every I0 artifact it read** (receipt → `inputs.i0_artifacts`), so the
   exact bytes this leg built against remain identifiable even if that worktree is pruned;
2. treated I0's findings as **design inputs** — *build against this shape* — and **re-measured
   every load-bearing number with this leg's own producers**.

Where the two agree, that is two independent instruments agreeing, which is worth more than
inheritance. Where they disagree, §4 and §6 say so.

**Second problem: a second `I1` agent ran concurrently in this same worktree** and overwrote this
leg's calibration artifact mid-run. Article V requires one worktree per parallel agent; two agents
in one directory produce interleaved work and findings that cannot be attributed. Its product was
**preserved, not deleted** (Law 4) as `_i1a_*`, and turned into a second instrument — §6.

**The R60 gate is what caught it.** `i1b_extract.py` refuses to build unless the calibration on
disk was produced against the reader's current source hash. It refused, for real, this run.
Escalated as `I1-R1`.

---

## 1 · The instrument, before any number

Every figure below comes from one reader, `i1b_reader.py`, **calibrated before it was trusted** (R60).

```
i1b_calibrate.py          72/72 controls pass
  POSITIVE  43   five pages read BY HAND in this leg's transcript, whose expected
                 values were written down BEFORE the parser was pointed at them
  NEGATIVE  10   the same pages mutated — a count that does not move when the
                 thing it counts is deleted is not measuring anything
  BLIND     19   eight deliberately naive readers, each shown returning the WRONG
                 answer where this reader returns the right one
```

**And the controls were themselves mutation-tested**, because Law 1 applies to them too:
each of the reader's six guards was reverted in turn and the calibration re-run. A guard whose
removal turns nothing red is not pinned — it is decorative, and it will be cited as evidence.

| guard reverted | controls that go red |
|---|---:|
| decode `utf-8-sig` → `utf-8` (BOM) | 2 |
| EOL normalisation | **9** |
| item scope closed by a `:xxx:` directive | **1** ← was **0** |
| page directives at column 0 only (D4) | 2 |
| `#channels` counted as an internal name | 5 |
| `@section` include anchors | 2 |

**The third row is the finding.** Reverting the `:vimeo:` scope-close guard originally turned
**nothing** red: the blind control used `sop/xform`'s *Combine*, which already carries
`#id: combine` **before** the `:vimeo:` block, so first-wins alone defended it and the scope close
was never exercised. The control proved a guard it was not actually testing.

Replaced with `sop/copyxform`'s *Copy Number Attribute* — no `#id` of its own, immediately
followed by `:vimeo:` + `#id: 406958778`. Without the scope close **that parameter is keyed to a
video id**; with it, the id binds to nothing. That control fails when the guard goes.

The five hand-read pages span the measured hazards rather than the easy cases: `cop/chromakey`
(CRLF, parameters at column 0), `cop/camerablend` (a preamble trap, `#since: 22.0`), `cop2/blur`
(parameters at indent 8, the deprecation banner), `lop/distantlight` (title-first, zero raw
parameters), `cop2/emboss` (BOM, `#channels` instead of `#id`).

**The calibration was not ceremony — it caught two defects in this leg's own work**, each of which
returns a plausible number and raises nothing:

| # | Defect | Silent consequence | Caught by |
|---|---|---|---|
| **A** | `include_targets_recursive` scanned with `finditer` on `^…$` patterns not compiled `MULTILINE` | matched **nothing**, so the `_old_cops_deprecated` banner was invisible and 141 cop2 pages read as current | control `blur.doc_deprecated` |
| **B** | an include anchor naming an **`@section`** (`#parameters`) resolved to nothing | `cop/rop_image` — a newly-named Copernicus node — read as having **zero** parameters and fell below the floor | cross-validation (§6), **not** by these controls |

Defect **B** is the more useful one: a calibrated first instrument missed it and a second
independent instrument caught it. That is the argument for §6 existing at all.

Four further defects were inherited from I0 as design inputs and are guarded from the first line —
CRLF line splitting, BOM decoding, the `:vimeo:` id trap — plus one this leg adds: **D4**, an
indented `NOTE:` + `#id:` in a page's *preamble* being recorded as a page-level directive
(`cop/camerablend`).

---

## 2 · What was built

```
i1b_reader.py     parser + include resolver (3 verbs, all help zips + loose dirs)
i1b_calibrate.py  72 controls        -> _i1b_calibration.json          [R60 GATE]
i1b_the161.py     the named set      -> _i1b_the161.json
i1b_extract.py    VERIFIED-DOC axis  -> _i1b_doc.json      [refuses without the gate]
i1b_runtime.py    VERIFIED-RUNTIME   -> _i1b_runtime.json  [hython, live 22.0.368]
i1b_merge.py      join + xvalidate   -> h22_node_corpus.json
```

**The two axes are separate producers writing separate artifacts, and that separation is
structural rather than a reporting convention.** Documentation supplies what a node is FOR; only a
probe supplies what it DOES. They are joined at the end with **every field keeping the tier of the
producer that measured it**, and they are never summed into one grounding number.

---

## 3 · The number that matters: exists vs clears the floor

**I0-FLOOR, adopted verbatim** so the two legs' numbers are comparable rather than merely similar:
a page clears the floor when it carries a `"""summary"""` **and** at least one documented parameter
with a non-empty description.

Two denominators answer two different questions, and merging them would hide the gap that matters.

### Per live type — what SYNAPSE can actually speak about

*Producer: `i1b_per_live_type.py` -> `_i1b_per_live_type.json`. Catalogue totals are
VERIFIED-RUNTIME, probed this session by `i1b_runtime.py`, not inherited from the brief.*

| context | live catalogue | has a page | **grounded to the floor** | % | known-thin | **no page at all** |
|---|---:|---:|---:|---:|---:|---:|
| **cop** (Copernicus) | **384** | 363 | **350** | **91.1%** | 13 | **21** |
| **lop** (Solaris) | **218** | 181 | **169** | **77.5%** | 12 | **37** |
| **cop2** (legacy) | **169** | 139 | **131** | **77.5%** | 8 | **30** |

The `no page at all` column is the part a page-only view cannot see: **88 live node types across
the three contexts ship with no help page whatsoever.** For those, documentation grounding is not
thin — it is absent, and only a probe can close them.

### Per help page — what the archive holds

| context | pages | node pages (EXISTS) | **clears the floor** | **known-thin** | ingested |
|---|---:|---:|---:|---:|---:|
| cop | 375 | 371 | **358** | **13** | 371 |
| lop | 198 | 181 | **169** | **12** | 181 |
| cop2 | 150 | 141 | **133** | **8** | 141 |

**The exists-minus-clears gap, per context, as integers: `cop 13 · lop 12 · cop2 8` — 33 of 693.**

Every one of those 33 is **ingested and recorded `known_thin: true`** with its rung and the reason
it fell short. None is padded to look complete; none is dropped to flatter the coverage number.
By rung: 26 reach `SUMMARY` (a summary, but no parameter carries a description); 7 reach only
`EXISTS` (no summary at all).

Reported beside the floor and never merged into it — a UI label with no internal name cannot
ground an emission:

| context | EXISTS | SUMMARY | FLOOR | ACTIONABLE |
|---|---:|---:|---:|---:|
| cop | 0 | 13 | 0 | **358** |
| lop | 7 | 5 | 21 | **148** |
| cop2 | 0 | 8 | 31 | **102** |

**Include resolution is load-bearing, and the pages it rescues concentrate where it matters.**
9 entries clear the floor **only** because `:include` / `:includeprop` / `:import` were resolved
across every help zip — **7 of them in `lop/`**. `lop/distantlight` documents **0** parameters raw
and **87** resolved. An extractor that skips resolution reports fully-documented Solaris nodes as
ungrounded.

Transclusion, measured: **2,523 include statements seen, 2,466 resolved, 54 unresolved across 17
pages.** Unresolved targets are **marked in the entry, never dropped** — a silently-dropped include
is an undercount that looks like a clean parse.

---

## 4 · The named Copernicus set — and the governing number is wrong

The brief and `docs/H22_FRONTIER.md` both rest on **"Houdini 22's what's-new names 161 new
Copernicus nodes; SYNAPSE grounds 3."** This leg re-derived that number from the shipped source
rather than inheriting it.

*Producer: `i1b_the161.py` → `_i1b_the161.json`.*

```
shipped  news.zip!22/copernicus.txt, matching node paths whole   171
the governing 161, reproduced exactly                            161
named nodes INVISIBLE to the governing number                     12
every named node has a cop/ page                                 yes
```

**Why 161 is wrong, precisely.** The shipped page uses **two** link forms:

```
[Label|Node:/cop/name]     169 occurrences     leading slash
[Node:cop/name]             12 occurrences     NO leading slash
```

A pattern requiring the leading slash silently drops **10 distinct node types** — including the
entire `adjacency_*` family, *which has its own section on that very page*, and the ripple and
reaction-diffusion solver blocks:

```
adjacency_attribsample  adjacency_distort  adjacency_extrapolate  adjacency_spacetransform
geotoadjacency  layerattribcreate  layerattribdelete
reactiondiffusion_block_begin  ripple_block_begin  ripple_block_end
```

**Two different defects converge on the same wrong number, which is why it read as verified.**
`harness/notes/_h22_frontier_xref.py:30` derives 161 from the **browsing cache** using `[a-z0-9_]+`
— a pattern that also truncates `bakegeometrytextures-2.0` to `bakegeometrytextures`. A
slash-requiring pattern on the **shipped** page also yields 161. **They are not the same 161:** the
two sets differ on `bakegeometrytextures-2.0` / `layertogeo-2.0` versus their truncated forms.
Same cardinality, different membership, both missing the same 10 nodes.

> This **refutes** I0's Q3 finding of *"exact set overlap: 161 in both, 0 shipped-only, 0
> cache-only"*, and supersedes `I0-R3`'s judgement that re-pointing the producer at `news.zip` is
> *"a provenance upgrade rather than a number correction."* It is a number correction.
> Escalated as `I1-R2`.

**A second imprecision, in the word "new".** The page's own section structure separates new nodes
from improvements to existing ones:

```
named in new-flavoured sections                       98
named ONLY under "== Copernicus improvements =="      73
                                                     ---
total named                                          171
```

So "161 new Copernicus nodes" is imprecise twice over: the count of *named* nodes is **171**, and
the count named *as new* is **98**. Both are reported; neither is merged into the other.

### The named set, at the floor rather than at the page

```
named (shipped)                 171
have a page                     171
INGESTED                        171
CLEAR the floor                 168      98.2%
below the floor                   3
```

**The three that need a runtime probe, named:** `layertogeo-2.0`, `pointmerge`, `usdmaterial`.
All three reach `SUMMARY` — they carry an authored summary and zero described parameters, so the
documentation can say what they are FOR and cannot say how to drive them. **A probe is the only
thing that closes them**, and they are reported here rather than quietly dropped. All 171 resolve
to a live node type on 22.0.368.

The forward statement this replaces *"161 vs 3"* with: **the shipped reference grounds 168 of the
171 named Copernicus nodes to the floor, and 358 of the 384 live Copernicus types — from a file
that ships with the product.**

---

## 5 · The 20-node cross-check against the live runtime

*Producer: `i1b_runtime.py:crosscheck` → `h22_node_corpus.json:crosscheck_20`. These 20 are the
only part of the run that **instantiates** nodes and reads real `node.parms()` / `node.parmTuples()`.*

Chosen to span the measured hazards, not to flatter: column-0 and indent-8 parameter pages, a CRLF
page, a BOM page, an `#id`-keyed and a `#channels`-keyed page, a page whose parameters exist only
after include resolution, the pathological USD-attribute-id page, both runtime-deprecated Karma
LOPs, and six newly-named Copernicus nodes.

```
nodes created and probed                    20 / 20
documented parameter LABELS      1,174   agree  919   78.3%
documented INTERNAL NAMES        1,030   agree  637   61.8%
```

**Label beats internal name by 16.5 points on live evidence from this build** — R97 and I0's
join-key finding independently re-confirmed rather than assumed. The corpus is keyed on label
accordingly; `#id` and `#channels` are recorded as evidence and are never the key.

The pathological case, and it is not rare:

| node | live parms | documented | internal names agree | labels agree |
|---|---:|---:|---:|---:|
| `lop/rendersettings` | 428 | 200 | **22 (12%)** | **183 (92%)** |
| `lop/distantlight` | 203 | 87 | 31 (40%) | 80 (92%) |
| `cop/chromakey` | 26 | 15 | 15 (100%) | 15 (100%) |

`lop/rendersettings` documents 200 parameters whose ids are USD-attribute-shaped
(`karma:global:…`). **A corpus keyed on `#id` would carry 200 entries for that node and resolve 22
of them — and would not fail loudly.**

Across the full corpus, not just the 20: **12,696 documented parameters, 11,057 label-resolved
against the live runtime (87.1%)** — recorded **per parameter**, so precision is a per-entry fact
rather than a corpus-wide unknown, and the corpus re-audits itself on the next build.
Per context: cop 92.4%, cop2 90.9%, lop 80.6%.

---

## 6 · Cross-validation — two independent extractors

A second `I1` extractor ran concurrently in this worktree (§0) and was used as a **second
instrument**, on I0 §7's precedent: two parsers disagreeing is information, and averaging it away
destroys it.

Cross-validation runs against **its final build**, `h22_node_corpus.i1-orchestrator.json`.
When this leg took the oracle path it copied what was there to `_i1a_h22_node_corpus.json` — and
that agent's own remediation ticket records that copy as its **second-to-last** build, so
comparing against it would have judged work its author had already replaced. Its report is
preserved beside it as `_i1a_I1_INGEST.md`. **Both agents independently detected the collision**;
it filed `.claude/remediation_ticket.md` and correctly declined to commit a tree a second process
was still mutating.

```
entries compared                        660
agree on the floor verdict              660      100.00%
disagree                                  0
```

**It did not start at 100%.** The single initial disagreement was `cop/rop_image` — the other
extractor resolved a section-anchored include this reader could not see. **It was right and this
reader had a gap** (defect B, §1). Fixed forward, a blind control added to pin it, and agreement
closed to 660/660. The disagreement was adjudicated against the page, never split.

The per-live-type table in §3 was independently recomputed here and reproduces the second
extractor's figures exactly (cop 350 / lop 169 / cop2 131). Three of this leg's headline numbers —
the per-context floor counts — also reproduce I0's independently measured 357/169/133 (cop moved
to 358 only after defect B was fixed).

33 entries exist in this corpus and not the other: it stopped at floor-clearing entries, where this
one ingests the known-thin as well and counts them.

---

## 7 · Deprecation travels with the entry

R72: deprecation is the **union** of runtime `deprecationInfo()` and authored help, and the two
disagree. The doc side is tiered — only STRONG signals count (`#status: deprecated`, the
`_old_cops_deprecated` banner, `:warning:Deprecated`). WEAK prose mentions are recorded beside
STRONG and **never merged**: `lop/reference.txt` says *"($IIDX is deprecated)"* about an expression
variable, not the node, and SYNAPSE emits that type 78 times.

*Producers: doc side `i1b_extract.py`, runtime side `i1b_runtime.py`, union `i1b_merge.py`.*

| context | both | **doc says, runtime does not** | **runtime says, doc does not** | neither |
|---|---:|---:|---:|---:|
| cop | 0 | 0 | 0 | 371 |
| lop | 0 | 2 | **2** | 177 |
| cop2 | 1 | 140 | 0 | 0 |
| **total** | **1** | **142** | **2** | **548** |

**Union: 145 of 693 entries carry a deprecation signal from at least one side.**

**The dangerous direction — the runtime flags it and every human-facing surface reads clean:**
`lop/karma` and `lop/karmarenderproperties`. R72 / H7-F2 confirmed independently on this build.
`karmarenderproperties` carries 56 KB of documentation that never mentions it, and SYNAPSE emits
these two types 123 and 31 times. **An artist reading the documentation has no way to learn they
are decaying.**

**The other direction — the vendor announced removal in prose while the runtime still reports the
types as current:** 140 `cop2/` pages, all via the `_old_cops_deprecated` banner, whose target
lives in `composite.zip` and **not** in `nodes.zip`. A reader that opens only `nodes.zip` cannot
resolve it and reproduces H5's defect exactly — an entire vendor-deprecated subsystem reading as
current. **A runtime-only oracle misses this whole subsystem.**

The two directions mean different things to an artist, so the corpus records which side fired, per
entry. They are never collapsed into one boolean.

---

## 8 · What this leg does NOT establish

A leg that hides a gap is worse than one that names it.

| gap | what would answer it |
|---|---|
| **Are the 358 floor-clearing COP entries *correct*, not merely present?** Everything measured here is shape and resolution, never truth. A description can resolve perfectly and still be wrong. | A semantic spot-check against live behaviour, n≈30. Needs a human or a second model, not a parser. |
| **The 12.9% of parameters whose labels do not resolve** (1,639 of 12,696) — reader over-extraction, or genuinely undocumented-but-live parameters? | Adjudicate a sample against `parmTemplateGroup()` by hand. This leg records the per-parameter flag that makes it cheap; it did not run the sweep. |
| **Whether `lop/` at 80.6% is a reader bias or a real documentation gap.** I0 measured the two available parsers failing in opposite directions on `lop/`, and this reader inherits the high-recall bias. | The label-vs-live adjudication over all 181 LOP pages. |
| **The 88 live types with no help page at all.** Counted, never characterised. | A probe sweep: which are internal, which are managers/networks, which are genuinely undocumented user-facing nodes. |
| **`#contentfrom`** — a parameter whose description lives on another page — is recorded but not resolved. | Extend the resolver to follow it; neither `helpdoc` nor this reader does today. |
| **Whether the doc is right and the runtime wrong** in the 142 doc-only cases. | Vendor confirmation. Both sources are authored by SideFX and they disagree; the archive cannot adjudicate itself. |
| **The 54 unresolved includes over 17 pages** are marked, not diagnosed. | Follow each target by hand; some are defects in the shipped documentation. |

---

## 9 · Scope

**Nothing was wired.** No file under `rag/`, no emission-path file, and no product file was
modified. `rag/skills/houdini21-reference` was not touched — R119: it **is** H21 documentation,
accurately labelled, and relabelling it would make the corpus lie about its own provenance.

U.6 found 15 phantom `createNode` sites already living in the RAG corpus, outside the emission
gate, re-teaching phantoms through `knowledge_lookup`. **Adding 693 doc-derived entries to that
surface without a gate is that mistake at scale.** Wiring is a separate decision with its own
oracle, and this leg deliberately does not make it.

---

## Producers

```
harness/notes/ingest/i1b_reader.py        the calibrated reader (all doc numbers)
harness/notes/ingest/i1b_calibrate.py     70/70 controls   -> _i1b_calibration.json
harness/notes/ingest/i1b_the161.py        the named set    -> _i1b_the161.json
harness/notes/ingest/i1b_extract.py       VERIFIED-DOC     -> _i1b_doc.json
harness/notes/ingest/i1b_runtime.py      VERIFIED-RUNTIME -> _i1b_runtime.json   (hython)
harness/notes/ingest/i1b_merge.py        join + xvalidate -> h22_node_corpus.json
                                                              _i1b_counts.json
                                                              _i1b_crossvalidate.json
harness/notes/ingest/i1b_per_live_type.py per-live-type    -> _i1b_per_live_type.json
harness/notes/h9/helpdoc.py               include resolver + corpus loader (reused, committed)

preserved from the concurrent second agent, used as a second instrument:
harness/notes/ingest/_i1a_h22_node_corpus.json
harness/notes/ingest/_i1a_I1_INGEST.md
harness/notes/ingest/i1_*.py
```

Every number in this document is emitted by one of the above. No figure is inherited from a
conversation, from a prior receipt, or from this leg's own brief — and of the figures the brief
handed this leg, **one was re-derived and corrected** (§4).
