# I1 — INGEST: the extractor, and the corpus it produced

**Leg** `I1` · **Harness** `INGEST-01` · **Run** 2026-07-27
**Subject** `$HFS/houdini/help` at Houdini **22.0.368** · **Gated on** `I0`
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/i1.md`
**Status** Wrote `harness/notes/ingest/**` only. No product file, no `rag/`, no emission path.

> **Gated on I0 because the join key is its finding, not this leg's assumption.**
> I0 measured LABEL as the key against the live runtime, four ways. This leg builds on
> that and confirms it independently: **366 of 407 documented parameters (89.9%) match
> by label** on twenty freshly instantiated nodes.

---

## 0 · The headline, both denominators, neither flattering

Two different questions get two different numbers, and merging them would hide the gap
that matters.

**Per live type — SYNAPSE's view. This is the number the leg exists to produce.**

| context | live catalogue | **grounded to the floor** | % | known-thin | no page at all |
|---|---:|---:|---:|---:|---:|
| **cop** (Copernicus) | 384 | **350** | **91.1%** | 13 | 21 |
| **lop** (Solaris) | 218 | **169** | **77.5%** | 12 | 37 |
| **cop2** (legacy compositing) | 169 | **131** | **77.5%** | 8 | 30 |

**Per help page — the archive's view.**

| context | EXISTS | node pages | **clears the floor** | known-thin |
|---|---:|---:|---:|---:|
| cop | 375 | 371 | **358** | 13 |
| lop | 198 | 181 | **169** | 12 |
| cop2 | 150 | 141 | **133** | 8 |

**The exists-vs-clears gap, as integers, per context: `cop 13 · lop 12 · cop2 8` — 33 of 693.**

*Producers: `i1_build.py` → `h22_node_corpus.json`, `_i1_counts.json`. Denominators from
`i1_runtime.py` under hython on the live build, not from a committed constant.*

### Against the measured frontier gap

`docs/H22_FRONTIER.md` measured **COP grounding at 6.2%**, and **161 new Copernicus nodes
against 3 SYNAPSE could speak about**. Both numbers move, from a file that ships with the
product:

```
COP grounding      6.2%  ->  91.1%   (350 of 384 live Copernicus types)
the 161            3     ->  158     ingested, at the floor, live-type-matched
```

**This is not wired to anything.** See §7.

---

## 1 · The 161

*Producer: `i1_extract.the_161()` reading `news.zip!22/copernicus.txt` — the SHIPPED
what's-new page, version-pinned by construction, not the browsing help cache.*

```
named in the shipped what's-new      161
have a cop/<name>.txt                161      0 absent
INGESTED (clear the floor)           158      97.5%
known-thin                             3
of those, still needing a probe        0      <- probed; see below
```

**The three, named, with the probe already run:**

| stem | live type | live parameter tuples | verdict |
|---|---|---:|---|
| `layertogeo-2.0` | `layertogeo::2.0` | **0** | parameterless node |
| `pointmerge` | `pointmerge` | **0** | parameterless node |
| `usdmaterial` | `usdmaterial` | **0** | parameterless node |

**All three document node types that carry zero parameters on the live build.** Their pages
are not stubs — there is nothing further to document, and no floor requiring a described
parameter can ever be cleared by a parameterless node. **Zero of the 161 have an
outstanding runtime probe.** The brief asked how many need one; the honest answer is none,
and it took a probe to be able to say so.

> **Disagreement with I0, adjudicated rather than averaged.** I0 named the three as
> `pointmerge`, `rop_image`, `usdmaterial`. This leg ingests `rop_image` and flags
> `layertogeo-2.0` instead. `cop/rop_image.txt` documents its parameters entirely through
> `:include /nodes/out/image#parameters/:` — an **`@section` anchor**, a form neither
> available resolver handled. Adding it (§3) rescues the page: 0 documented parameters → 58.
> `cop/layertogeo-2.0.txt` is 623 characters with no `@parameters` section at all, and both
> this leg's reader *and* the committed `helpdoc.py` score it below the floor. The totals
> agree at 158; the membership differs by one in each direction. Escalated as `I1-R1`.

---

## 2 · The instrument, before any number

Every figure above comes from one reader, `harness/notes/ingest/i1_extract.py`, and that
reader was **calibrated before it was trusted** (R60).

```
i1_calibrate.py     33/33 controls pass
  POSITIVE  18   pages read BY HAND whose exact answer the parser must reproduce
  NEGATIVE   7   mutations that must drive a count to zero or flip a verdict
  BLIND      7   deliberately naive readers, shown returning the WRONG answer
  CROSS-CHECK 1  an archive fact I0 measured independently (nodes.zip BOM count = 58)
```

Four pages were transcribed by hand first and are the ground truth the parser is held to:

| page | why this one | hand-read answer |
|---|---|---|
| `cop/chromakey` | one of the 161, **and CRLF** | 15 parameters, 15 `#id`, all described |
| `cop2/emboss` | **BOM**, indent-4, `#channels`-only | 10 raw parameters, 0 `#id`, 10 `#channels` |
| `lop/distantlight` | title-first, all-by-`:include` | **0 raw parameters, 87 resolved** |
| `cop/adjacency_distort` | `#contentfrom` with no inline prose | 11 parameters, 2 described by reference |

Every control states the condition under which it fails. **Two controls went red on first
run and in both cases the CONTROL was wrong, not the reader** — recorded inline rather than
quietly repaired:

- **N7** kept nested entries while stripping descriptions, so the fold pass turned a
  surviving `TIP:` label into the parent's description and the page still read ACTIONABLE.
- **B3** expected the Vimeo trap to bind **one** video id to `sop/xform`'s `Combine`
  parameter. It binds **four** — `sop/xform` ships four consecutive `:vimeo:` blocks.
  **The trap is worse than I0 recorded.**

---

## 3 · What the extractor does that neither prior reader did

I0 §7 measured that the two available parsers fail in opposite directions on `lop/` — one
at ~18× the recall and lower precision, the other precise and under-extracting a
402-parameter node down to 12 — and that **neither carries a precision pass**. Four
additions, each forced by a measurement:

### 3.1 `@section` anchors resolve (`:import`, and `rop_image`)

`lop/usd_rop.txt` is the archive's single `:import`, and it reads
`:import /nodes/out/usd#parameters:` into a page that has **no `@parameters` marker of its
own**. Splicing the bare body in leaves every imported parameter in the preamble, where a
parameter parser correctly ignores it — the page reports **0** parameters while carrying
**36**. So when the anchor names an `@section`, the section header travels with the section.

```
lop/usd_rop      0 -> 36 parameters
cop/rop_image    0 -> 58 parameters   (and crosses the floor)
```

### 3.2 `#contentfrom` is followed

1,199 records carry it archive-wide (I0's census, not re-measured here).
`cop/adjacency_distort`'s `Signature` parameter has a label, an
`#id` and **no inline prose at all** — its description lives on `cop/distort`. I0-F4 asked
for a deliberate decision about these; the decision is to follow the reference. A floor
that requires "has a description" otherwise scores documented parameters as described-by-
nothing.

### 3.3 Menu values fold into the parameter they document

`cop2/emboss`'s `Specular Model` carries zero own prose — its entire body is `Phong:` and
`Blinn:` and their descriptions. Unfolded, a fully-documented parameter reads as a stub, on
a page whose whole parameter surface is `#channels`-keyed.

### 3.4 A declared `#version:` beats the filename — 10 LOP pages were binding to the wrong type

**The single largest defect this leg found in its own first output.** Ten `lop/` pages match
**two** live types, and taking the first candidate binds them to the **older** one:

| page | declares | was binding to | now binds to | parameters |
|---|---|---|---|---:|
| `lop/sceneimport` | `#version: 2.0` | `sceneimport` | `sceneimport::2.0` | 94 |
| `lop/light` | `#version: 2.0` | `light` | `light::2.0` | 93 |
| `lop/distantlight` | `#version: 2.0` | `distantlight` | `distantlight::2.0` | 87 |
| `lop/domelight` | `#version: 3.0` | `domelight` | `domelight::3.0` | 73 |
| + `capsule`, `cylinder`, `reference`, `collection`, `cache` | | | | 120 |

Filename-first hands those parameters to the legacy type and reports the **current** type —
the one an artist gets when they create the node — as undocumented. The page states which
version it documents; believing it is not a heuristic.

**It is also falsifiable, and it was falsified in the right direction.** If the new binding
were wrong the live-label match rate would fall. It rose:

```
live-label matched   10,744 (85.4%)  ->  10,843 (86.2%)      +99 parameters
lop specifically      78.8%          ->   80.7%
```

### 3.5 Per-entry precision (I0-R2, in scope and delivered)

Every extracted parameter records whether its label resolved against the live build at
corpus-build time. That converts precision from an unknown into a per-entry fact, keeps
R119's per-entry provenance, and makes the corpus **self-auditing on the next build**.

| context | documented parameters | live-label matched | rate |
|---|---:|---:|---:|
| cop | 5,294 | 4,771 | **90.1%** |
| lop | 5,345 | 4,311 | **80.7%** |
| cop2 | 1,943 | 1,761 | **90.6%** |
| **all** | **12,582** | **10,843** | **86.2%** |

---

## 4 · The 20-node cross-check, against the live runtime

*Producer: `i1_crosscheck.py` under hython. Twenty entries, **deterministically** selected —
evenly spaced through each context's sorted ingested list, 10 cop (all drawn from the 161),
6 lop, 4 cop2. No seed, no shuffle. **20 of 20 instantiated.** Controls 2/2.*

| axis | present on | agreed | rate of all 407 records |
|---|---:|---:|---:|
| **LABEL → live parm / parmTuple labels** | **407** | **366** | **89.9%** ← the join key |
| `#id` → parmTuples first, then parms | 272 | 241 | 59.2% ← evidence |
| `#id` → parm level only | 272 | 233 | 57.2% |
| `#channels` → parm or tuple names | 4 | 4 | — |

**I0-F3 is confirmed on independent evidence.** Label wins on availability (present on
**100%** of the 407 records against **66.8%** for `#id`) *and* on accuracy, and tuple-first beats parm-level
for `#id` by 8 records at no cost — exactly I0's finding, reproduced by a different
instrument on freshly created nodes.

Controls: a fabricated label (`Unobtainium Threshold`) must **not** match, and a known-real
one (`Screen Color`) on the same node must. Without both, 89.9% is unfalsifiable.

---

## 5 · Deprecation travels with the entry

R72: deprecation is the **union** of runtime `deprecationInfo()` and authored help, and they
disagree. Recorded per side, per entry, never merged into one boolean.

| context | doc says | runtime says | union | **doc-only** | **runtime-only** |
|---|---:|---:|---:|---:|---:|
| cop | 0 | 0 | 0 | 0 | 0 |
| lop | 2 | 2 | 4 | 2 | **2** |
| cop2 | 141 | 1 | 141 | **140** | 0 |
| **total** | **143** | **3** | **145** | **142** | **2** |

**Direction 1 — doc says, runtime does not: 142.** 140 are `cop2/`, every one via
`:include /composite/_old_cops_deprecated:`. **That target is not in `nodes.zip`** — it
lives in `composite.zip`, so a `nodes.zip`-only reader cannot resolve it and reads an
entire vendor-deprecated subsystem as current (H7-F4 / I0-F9). The corpus loader opens
every `*.zip` in the help directory plus the loose directories: **11,709 pages, against
5,032 in `nodes.zip` alone.** A blind control in the calibration proves the nodes.zip-only
case still fails.

**Direction 2 — runtime says, doc does not: 2. The dangerous cell.**

```
lop/karma                  "Replaced by Karma Render Settings and USD Render."
lop/karmarenderproperties  "Use karmarendersettings instead"
```

Both read completely clean to a human. R72's canonical pair, confirmed live for a third
time. A corpus without this axis teaches decaying nodes as current — and `karmarenderproperties`
is a node the brief records SYNAPSE emitting 123 times (that figure is the brief's, not
this leg's — no producer for it was run here).

**WEAK signals are recorded beside STRONG ones and never merged into them.** Only
`#status: deprecated`, the `_old_cops_deprecated` banner, and `:warning:Deprecated` count as
"the page states a deprecation". The word *deprecated* appearing anywhere does not —
`lop/reference` says *"($IIDX is deprecated)"* about an expression variable.

**One runtime-deprecated type ships with no page at all:** `cop2/swap`.

---

## 6 · A stub is not knowledge — and "thin" is a diagnosis, not a verdict

An entry clearing the floor is **ingested**. One that does not is recorded in `known_thin`
with the reason, and **counted — never padded** with a title and an empty parameter list so
the totals look better.

But the floor alone mislabels a whole class of page, and reporting the unflattering number
without that distinction would be the flattering number's mirror image:

| context | known-thin | **parameterless-node** | **doc-gap** |
|---|---:|---:|---:|
| cop | 13 | **13** | **0** |
| lop | 12 | 4 | **8** |
| cop2 | 8 | 6 | **2** |

**All 13 thin `cop/` pages document node types with zero live parameters.** Copernicus has
**no documentation gap at all** at this floor — a result that only appears once the live
parameter count is joined in.

**The real gap is 10 pages, and it is in Solaris and legacy compositing:**

| page | live parameter tuples | why it misses the floor |
|---|---:|---|
| `lop/usdrender_rop` | **166** | no summary and no described parameter |
| `cop2/rop_comp` | 73 | summary only |
| `lop/usd_rop` | 51 | 36 described parameters, **no authored summary** |
| `cop2/erftable` | 31 | summary only |
| `lop/geoclipsequence` | 30 | 29 described parameters, no summary |
| `lop/valueclip` | 20 | 17 described, no summary |
| `lop/additionalrendervars` | 18 | summary only |
| `lop/editcontextoptions` | 17 | 19 described, no summary |
| `lop/loadlayer` | 6 | 6 described, no summary |
| `lop/layerbreak` | 3 | summary only |

Six of the eight LOP misses fail on **the summary half of the floor while carrying fully
described parameters**. The floor is I0's, taken verbatim so the two legs compare; the
classification is reported beside it, never merged into it.

---

## 7 · What is NOT wired, and why that is the point

**Nothing here touches `rag/`, the emission corpus, or any product file.** `git status` for
this leg shows exactly one new directory: `harness/notes/ingest/`.

U.6 found **15 phantom `createNode` sites already living in the RAG corpus**, outside the
emission gate, re-teaching phantoms through `knowledge_lookup`. Adding 660 doc-derived
entries and 12,582 parameter records to that surface without a gate is that mistake at
scale. **Wiring is a separate decision with its own oracle.**

`rag/skills/houdini21-reference` was not touched. R119: it **is** H21 documentation,
accurately labelled, and relabelling it would make the corpus lie about its own provenance.

**Provenance is per entry, never per corpus.** Every record carries `tier: VERIFIED-DOC`,
its build, and its path inside the archive (`nodes.zip!cop/chromakey.txt`). The runtime
fields in each entry are labelled `VERIFIED-RUNTIME` and sit beside the doc fields.
**The two are never summed into one grounding number** — documentation supplies what a node
is FOR, only a probe supplies what it DOES.

---

## 8 · How the read went, measured

*Over the 660 ingested entries.*

```
include statements seen        2,500     verbs: :include 2,500
resolved                       2,443
UNRESOLVED anchor                 44     marked in place, never dropped
UNRESOLVED page                    2     marked in place, never dropped
CRLF pages ingested               67     all in cop/ -- the frontier surface
BOM pages ingested                 3
```

Unresolved includes are **defects in the shipped documentation**, not parse failures. They
are replaced by a marker and counted; a silently-dropped include is an undercount that looks
like a clean parse.

---

## 9 · What this leg could NOT settle

| gap | what would settle it |
|---|---|
| **Are the 350 grounded COP entries *correct*, not merely present?** Every number here measures shape and live-name agreement, never semantic truth. | A semantic spot-check: sample n≈30, compare each documented description against observed behaviour. Needs a human or a second model, not a parser. |
| **The 41 documented parameters (of 407) that do NOT match a live label.** Some are real drift, some are parser over-extraction. Not separated. | Adjudicate each by hand against the live node. Cheap at n=41; out of this leg's scope. |
| **88 live types across the three catalogues ship with no help page.** 21 cop, 37 lop, 30 cop2 — mostly network managers (`chopnet`, `sopnet`) and `labs::` HDAs. | A runtime-only grounding pass. Documentation cannot ground what it does not document. |
| **Whether the `#version:`-wins rule is right for pages that declare a version no live type carries.** Not observed on this build; unexercised branch. | A build where it occurs, or a deliberate synthetic case. |
| **Whether I0's `rop_image` / `layertogeo-2.0` membership or this leg's is right.** Both totals are 158. | `I1-R1` — I0's Q4 producer is uncommitted, so its verdict cannot be re-run from the tree. |

---

## Producers

```
harness/notes/ingest/i1_extract.py       the calibrated reader (all doc-side numbers)
harness/notes/ingest/i1_calibrate.py     33/33 controls        -> _i1_calibration.json
harness/notes/ingest/i1_runtime.py       hython, live 22.0.368 -> _i1_runtime.json
harness/notes/ingest/i1_build.py         the corpus            -> h22_node_corpus.json
                                                               -> _i1_counts.json
harness/notes/ingest/i1_crosscheck.py    hython, 20 nodes      -> _i1_crosscheck.json
harness/notes/h9/helpdoc.py              include resolver + corpus loader (committed, reused)
```

Every number in this document is emitted by one of the above. No figure is inherited from a
conversation, a prior receipt, or this leg's own brief.
