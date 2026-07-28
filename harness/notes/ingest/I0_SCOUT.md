# I0 — SCOUT: what is actually in the shipped node reference

**Leg** `I0` · **Harness** `INGEST-01` · **Run** 2026-07-27
**Subject** `$HFS/houdini/help/nodes.zip` — Houdini **22.0.368**
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Brief** `harness/prompts/i0.md`
**Status** READ-ONLY. Wrote `harness/notes/ingest/**` and `harness/notes/receipts/I0.json`. Nothing else.

> **This leg measures the archive. It does not build the extractor.**
> Where the archive cannot answer a question, this says so and names what would.

---

## 0 · The instrument, before any number

Every figure below comes from **one reader**, `harness/notes/ingest/_i0_reader.py`, and that
reader is **calibrated before it is trusted** (R60).

```
_i0_calibrate.py          61/61 controls pass
  POSITIVE  10 hand-read pages the parser must reproduce exactly
  NEGATIVE   5 mutations that must drive a count to zero
  BLIND      2 deliberately naive readers, shown returning the WRONG answer
             where ours returns the right one
```

**The calibration was not ceremony. It found three defects in this leg's own reader,
each of which returns a plausible number and raises nothing.** They are reported as
findings because I1 will hit all three.

| # | Defect | Silent consequence | Measured blast radius |
|---|---|---|---|
| **D1** | split on `\n`, anchor items on `$` | page reads as **0 parameters** | **138 pages** — but **67 of 375 in `cop/` (17.9%)** |
| **D2** | decode `utf-8` instead of `utf-8-sig` | first `#directive` silently eaten | **58 BOM pages**; 32 lose a directive, 26 lose their title |
| **D3** | bind any indented `#id:` to the preceding label | real parm re-keyed to a **Vimeo video id** | `sop/xform` "Combine" → `combine` becomes `406959576` |

D1 lands hardest on Copernicus — the exact surface `docs/H22_FRONTIER.md` calls the frontier.
None of the three raises an exception. All three were caught by controls, not by the numbers
looking wrong.

**Second instrument.** Results are cross-validated against H9's independent parser
(`harness/notes/h9/helpdoc.py`) — see **§7**.

**Archive census** (producer `_i0_q1_structure.py`):

```
5,034 zip entries  =  5,033 .txt  +  1 .h  (dop/dragproperties.h)
5,033 .txt         =  5,032 context pages  +  1 root index.txt
19 context directories
```

---

## Q1 · STRUCTURE — is the format consistent across contexts?

**Answer: NO, and not by a small margin. Write one parser per context, or one parser with
per-context switches that are chosen from measurement rather than discovered by breakage.**

**Sample size: the FULL POPULATION of every context** (n = every page, not ≥20).
A census cost the same as a sample here — 5,032 pages in ~2s.
*Producer: `harness/notes/ingest/_i0_q1_structure.py` → `_i0_q1_structure.json`*

### The five contexts the brief names, plus cop2

| ctx | n | header order | line endings | pages w/ params | param records | `#id` rate | param base indent | pages w/ `:include` |
|---|---:|---|---|---:|---:|---:|---|---:|
| **cop** | 375 | dir-first 368 · dir-only 3 · **title-first 4** | LF 308 · **CRLF 67** | 357 | 4,617 | **99.3%** | all at col 0 | 163 |
| **lop** | 198 | **title-first 157** · dir-first 25 · dir-only 16 | LF 197 · CRLF 1 | 167 | 2,595 | 64.8% | 0 (166) · 4 (1) | 126 |
| **sop** | 1,203 | dir-first 752 · **title-first 415** · dir-only 34 · neither 2 | LF 1,176 · CRLF 26 · **MIXED 1** | 1,111 | 19,309 | 63.6% | 0 (947) · 4 (159) · 8 (4) · 3 (1) | 376 |
| **out** | 57 | dir-first 35 · **title-first 19** · dir-only 3 | LF 57 | 48 | 981 | 34.8% | 0 (37) · 4 (9) · 8 (2) | 41 |
| **top** | 158 | dir-first 107 · **title-first 42** · dir-only 9 | LF 158 | 132 | 2,220 | 86.4% | 0 (124) · 4 (7) · 8 (1) | 127 |
| **cop2** | 150 | dir-first 138 · dir-only 7 · title-first 5 | LF 147 · CRLF 3 | 132 | 909 | **4.4%** | **4 (44)** · 0 (19) · 2 (2) · 6 (1) | 143 |

**The two that will break a single parser hardest:**

- **`cop/` is 98% directives-first. `lop/` is 79% TITLE-first.** A reader that takes the header
  block from the top of the file returns no `#context`/`#internal` for 157 of 198 LOP pages.
- **`cop/` puts every parameter at column 0. `cop2/` puts most at indent 4 or deeper.**
  A column-0 reader scores **113 of 150 cop2 pages** as having zero parameters.

### Where a single parser breaks — measured over all 5,032 pages

| pages | % | the assumption that is false | consequence |
|---:|---:|---|---|
| 1,761 | 35.0% | a documented node has an `@parameters` section | pages documented via `@top_attributes` / `@inputs` / `@outputs` read as ungrounded |
| 1,595 | 31.7% | parameter text is inline (no `:include`) | transcluded parameters absent from the entry |
| 1,443 | 28.7% | `#id:` is present on documented parameters | an id-keyed corpus carries **nothing** for the page |
| 897 | 17.8% | directives come before `= Title =` | no `#context` / `#internal` recovered |
| 549 | 10.9% | the page carries a `"""summary"""` | a floor requiring one rejects the page |
| 527 | 10.5% | parameters are labels at **column 0** | **every** parameter on the page missed |
| 218 | 4.3% | `#internal:` names the node type | no join key; filename is the only fallback |
| 193 | 3.8% | the page carries a `= Title =` | no display name |
| 138 | 2.7% | lines are LF-terminated | **page reads as 0 parameters, silently** |

### The context that has no parameters at all

**`apex/` — 613 pages, 0 `@parameters` sections, 0 parameter records.**
APEX documents through `@inputs` (593) and `@outputs` (593) plus a `Name ||` table markup.
Its `#internal:` values are templated (`Add<T>`), so they do not join to a live type by string
equality. **A parameter-keyed corpus grounds nothing for 613 pages** — 12% of the archive.
`vop/` is the same shape in part: 1,212 pages but only 549 `@parameters`.

---

## Q2 · THE JOIN KEY — measured against the LIVE runtime

**Answer: LABEL. H9-F1 is CONFIRMED on independent evidence, and the margin is wider than
"label wins" suggests — label wins on *availability* as well as on *accuracy*.**

*Producers: `_i0_q2_joinkey.py` (raw pages) and `_i0_q2b_resolved.py` (includes resolved),
both run under `hython` on live 22.0.368. Controls 15/15 and 4/4. Seed 20260727.*

The runtime exposes parameters at **two levels** and the documentation is not consistent about
which one it names, so both are tested:

```
node.parms()       component level   tx, ty, tz     49 on sop/xform
node.parmTuples()  tuple level       t              29 on sop/xform
sop/xform documents  "Translate:  #id: t"  -> that is the TUPLE name
```

### Match rate per candidate key

**Sample A — the 15 the brief asks for.** Deliberately weighted toward the hard cases found in
Q1 (CRLF page, `#contentfrom`-only params, zero-`#id` cop2, the 199-id LOP, two of the 161 new
COPs, the Vimeo trap). All 15 join to the live runtime.

| key | field present on | matched | rate of present | **share of ALL 311 records** |
|---|---:|---:|---:|---:|
| K1 `#id` → `parms()` | 265 / 311 | 135 | 50.9% | **43.4%** |
| K2 `#id` → `parmTuples()` | 265 / 311 | 158 | 59.6% | **50.8%** |
| K3 `#id` suffix-stripped → `parms()` | 265 / 311 | 135 | 50.9% | 43.4% |
| **K4 label → parm labels** | **311 / 311** | **276** | **88.7%** | **88.7%** |
| **K5 label → parmTuple labels** | **311 / 311** | **276** | **88.7%** | **88.7%** |
| K6 `#channels` → `parms()` | 21 / 311 | 20 | 95.2% | 6.4% |

**Sample B — seeded population sweep, 25 pages × 6 contexts, 141 nodes joined, 1,473 records.**

| key | present on | matched | rate of present | share of ALL |
|---|---:|---:|---:|---:|
| K1 `#id` → `parms()` | 922 / 1,473 | 779 | 84.5% | 52.9% |
| K2 `#id` → `parmTuples()` | 922 / 1,473 | 806 | 87.4% | 54.7% |
| **K4 label → parm labels** | **1,473 / 1,473** | **1,311** | **89.0%** | **89.0%** |
| **K5 label → parmTuple labels** | **1,473 / 1,473** | **1,313** | **89.1%** | **89.1%** |
| K6 `#channels` → `parms()` | 88 / 1,473 | 69 | 78.4% | 4.7% |

**Sample C/D — the same two samples with `:include` resolved** (816 and 2,137 records):

| key | hand-picked, share of ALL | population, share of ALL |
|---|---:|---:|
| K1 `#id` → `parms()` | 42.2% | 49.7% |
| K2 `#id` → `parmTuples()` | 46.6% | 52.3% |
| **K4 label → parm labels** | **80.5%** | **84.1%** |
| K6 `#channels` → `parms()` | 4.7% | 7.3% |

**The verdict is stable across all four measurements.** Label wins raw and resolved,
hand-picked and population.

### Why label wins — two independent reasons, and the second is the one that matters

1. **Availability.** Label is present on **100%** of documented parameter records.
   `#id` is present on **62–85%**. 1,443 pages carry documented parameters with **no `#id` at all**.
2. **Accuracy.** Where both exist, label still matches more often.

**The pathological case, and it is not rare:** `lop/rendersettings` documents **106 parameters,
all 106 carrying `#id`**. Against the live type: **10 ids match**, **95 labels match**.
The ids are USD-attribute-shaped (`karma:global:...`), not parm names. A corpus keyed on `#id`
would carry 106 entries for this node and resolve ten of them — **and would not fail loudly.**

### `#channels` is a SECOND internal-name key, and it is not optional

`#channels` appears **1,833 times** archive-wide. In `cop2/` it is *dominant*:
**248 `#channels` vs 51 `#id`**. A reader following only `#id` reports the entire cop2
parameter surface as un-identifiable.

> ⚠ **The brief's own premise is stale here.** `harness/prompts/i0.md:14` and
> `harness/SYNAPSE_INGEST.md:40` state H9-F3 as *"7.7% of cop2 parameter records carry `#id`;
> only 13 of 139 pages have even one."* **Measured against `nodes.zip` at 22.0.368 that does not
> reproduce in any construction I can build:** 9 of 150 pages carry any raw `#id:` line, 51 lines
> total, 4.4% of top-level parameter records. H9's *own final artifact* supersedes its quoted
> figure — `h22_doc_grounding_corpus.json` yields cop2 at 42.7% once `#channels` is counted.
> **H9-F3's direction is right and its numbers are stale.** Escalated as `I0-R1`.

### Recommended key for I1

```
PRIMARY    label, normalised (collapse whitespace, casefold, normalise U+2019)
            -> matched against BOTH parm labels and parmTuple labels
SECONDARY  #id, tried against parmTuples() FIRST, then parms()
            (tuple-first is worth 2-8 points and costs nothing)
THIRD      #channels, leading '/' stripped, space-split
RECORDED   #id is EVIDENCE, never the key (R97, re-confirmed here)
```

Component-suffix stripping (K3) is **not** worth implementing: it recovered **2 records out of
2,137** in the resolved population sweep. Its stripper is proven live by a control, so the zero
is a measurement, not a dead branch.

---

## Q3 · COVERAGE OF THE 161

**Answer: 161 named, 161 present, 0 absent. The ingest is mechanical.**

*Producer: `_i0_q3_the161.py` → `_i0_q3_the161.json`. Controls 5/5.*

```
new Copernicus nodes named in What's New   161
have a cop/<name>.txt in nodes.zip         161      100%
ABSENT                                       0
```

**Absent list: empty.**

### Two independent sources, and this upgrades the governing number

| source | count | tier |
|---|---:|---|
| **S1 SHIPPED** `news.zip!22/copernicus.txt` | **161** | VERIFIED-STATIC, version-pinned by construction |
| S2 BROWSED `<userprefs>/config/Help/cache/news/22/copernicus.json` | 161 | the browsing cache |

**Set overlap is exact: 161 in both, 0 shipped-only, 0 cache-only.**

`docs/H22_FRONTIER.md`'s 161 came from the browsing cache via `_h22_frontier_xref.py`.
R72 warns that cache absence means "nobody browsed it" — so a cache-derived list was a floor,
not a total. **`news.zip` ships the same page and was not previously used.** The number is now
derivable from a shipped artifact. `_h22_frontier_xref.py` should be re-pointed at `news.zip`;
its *cop denominator* is separately wrong (25 cached pages, not 375 shipped) — `I0-R3`.

**But "has a page" is not "is grounded"** — see Q4 for the 161 at the floor.

---

## Q4 · THE QUALITY FLOOR — exists vs clears

### The floor, and why this one

```
I0-FLOOR  =  the page carries a """summary"""
             AND >= 1 documented parameter with a non-empty description
```

**Justification.** Those are the two questions an assistant must answer before it can say
anything useful about a node: *what is this for* (summary) and *how do I drive it* (a described
parameter). Neither alone is knowledge — a summary with no parameters cannot ground an action,
and parameters with no summary cannot be retrieved by intent. It is also **H9's FLOOR rung
verbatim**, so the two legs' numbers are comparable rather than merely similar.

Reported beside it, never merged into it:

```
EXISTS      a page maps to the context
SUMMARY     + an authored summary line
FLOOR       + >=1 described parameter                    <- the headline
ACTIONABLE  + >=1 parameter with an internal name (#id or #channels)
```

ACTIONABLE is kept separate because a UI label with no internal name cannot ground an emission.

*Producer: `_i0_q4_floor.py` → `_i0_q4_floor.json`, `_i0_q4_per_page.json`. Controls 7/7.
Resolver: `harness/notes/h9/helpdoc.py`. Sample size: every page in each context.*

### Exists vs clears, per context

| ctx | EXISTS | node-typed | clears RAW | **clears RESOLVED** | **clears %** | rescued by resolution | pages w/ broken include |
|---|---:|---:|---:|---:|---:|---:|---:|
| **cop** | 375 | 371 | 357 | **357** | **95.2%** | 0 | 3 |
| **lop** | 198 | 180 | 162 | **169** | **85.4%** | 7 | 14 |
| **sop** | 1,203 | 1,171 | 1,093 | **1,102** | **91.6%** | 9 | 43 |
| **out** | 57 | 53 | 45 | **48** | **84.2%** | 3 | 2 |
| **top** | 158 | 148 | 129 | **130** | **82.3%** | 1 | 7 |
| **cop2** | 150 | 141 | 132 | **133** | **88.7%** | 1 | 1 |

**The gap the harness turns on — pages that EXIST but do not CLEAR:**

```
cop    18      lop    29      sop   101
out     9      top    28      cop2   17          total 202 of 2,141
```

Rung breakdown (resolved):

| ctx | EXISTS | SUMMARY | FLOOR | ACTIONABLE |
|---|---:|---:|---:|---:|
| cop | 3 | 15 | 0 | **357** |
| lop | 23 | 6 | 21 | 148 |
| sop | 70 | 31 | 241 | 861 |
| out | 6 | 3 | 6 | 42 |
| top | 12 | 16 | 0 | 130 |
| cop2 | 8 | 9 | 31 | 102 |

### The floor answer DEPENDS on include resolution — this is the Q4 finding

**`lop/distantlight` documents 0 parameters raw and 87 resolved.** Its entire `@parameters`
section is 14 `:include` lines and nothing else. Raw, it scores `SUMMARY` — below the floor.
Resolved, it scores `ACTIONABLE`.

```
lop/distantlight     raw   0 params   rung SUMMARY      BELOW floor
                     res  87 params   rung ACTIONABLE   ABOVE floor
cop2/blur            raw   6 params -> res 17 params
cop/chromakey        raw  15 params -> res 15 params    (no includes; unchanged)
```

**21 pages across the six contexts cross the floor purely because includes were resolved.**
An extractor that skips resolution reports fully-documented nodes as ungrounded — and the pages
it loses are concentrated in `lop/`, the context that matters most for Solaris.

### The 161 new Copernicus nodes, at the floor rather than at the page

```
named                          161
have a page                    161
CLEAR the floor                158        97.5%
ACTIONABLE (internal name)     158        97.5%
below the floor                  3
```

**The three: `pointmerge`, `rop_image`, `usdmaterial`.**

This is the number that should replace "161 vs 3" in any forward statement: the shipped
reference can ground **158 of the 161** to ACTIONABLE, from a file that ships with the product.

---

## Q5 · RELATIONSHIPS AND BANNERS — every directive shape found

**Answer: 30 distinct block-directive shapes, THREE include verbs (not one), and the
deprecation banner's target is not in `nodes.zip` at all.**

*Producer: `_i0_q1_structure.py` + the shape sweep in `_i0_reader.py`'s grammar.
Sample size: every line of all 5,032 pages.*

### Three include verbs

| verb | occurrences | note |
|---|---:|---|
| `:include <target>:` | **9,986** | the common case |
| `:includeprop <target>:` | **307** | a second verb — a reader matching only `:include` drops these |
| `:import <target>:` | **1** | pulls an **entire `@parameters` section** across contexts: `lop/usd_rop.txt` ← `/nodes/out/usd#parameters` |

**10,294 total on the page surface; 7,467 of them carry an `#anchor`.**
Recursive expansion sees **11,359** statements (includes nested inside included fragments).

### Every block-directive shape found

| shape | count | example |
|---|---:|---|
| `:include <target>:` | 9,986 | `apex/Log.txt` |
| `:: <list-item>` | 3,593 | `apex/Abs.txt` `::value:` |
| `:task: <arg>` | 540 | `cop/bakegeometrytextures-2.0.txt` |
| `:fig: <arg>` | 508 | `apex/BoolToIntBitMask.txt` |
| `:includeprop <target>:` | 307 | `obj/cam.txt` |
| `:video:` | 243 | `apex/rig--SampleSplineTransforms.txt` |
| `:col:` | 179 | multi-column layout |
| `:changed: <arg>` | 115 | `sop/muscleconstraintpropertiesotis.txt` |
| `:improved: <arg>` | 115 | version-delta markers |
| `:compare_images:` | 46 | `cop/dropshadow.txt` |
| `:vimeo: <arg>` | 46 | **carries `#id: <video id>` — the D3 trap** |
| `:box:` / `:box: <arg>` | 43 / 20 | |
| `:warning: <arg>` | 30 | **`:warning:Deprecated:` ×23** |
| `:tip:` / `:tip: <arg>` / `:tips:` | 24 / 15 / 1 | |
| `:note:` / `:note: <arg>` | 21 / 13 | |
| `:disclosure: <arg>` | 18 | |
| `:list:` | 13 | |
| `:action: <arg>` | 12 | |
| `:null:` | 12 | |
| `:platform: <arg>` | 10 | `:platform:Mac` |
| `:warning:` (bare) | 9 | |
| `<other leading-colon>` | 9 | includes a bare `:` in `out/hq_render.txt` |
| `:tab: <arg>` | 4 | |
| `:import <target>:` | 1 | |
| `:WARNING: <arg>` | 1 | **uppercase variant** — a case-sensitive matcher misses it |

### Item-level `#directives` — 25 distinct keys

```
#id 27,013   #type 3,206   #channels 1,833   #contentfrom 1,199   #src 243
#display 220   #kagroup 210   #required 196   #width 121   #loop 81
#image1 46   #image2 46   #also 22   #query 13   #sortedby 13   #glyph 12
#hotkeys 12   #style 11   #hprop 8   #status 8   #fold 7   #on 7
#default 4   #idP 2   #autoplay 1
```

- **`#contentfrom` (1,199)** is a second indirection axis: the parameter's *description* lives on
  another page. `cop/adjacency_distort.txt` has parameters with a label, an `#id`, and **no inline
  prose at all** — they are documented purely by reference. A floor keyed on "has a description"
  must decide about these deliberately.
- **`#idP` (2)** is a typo'd/variant key. Named because a scout that guesses will not find it.

### The `:include` banner — H7-F4, and why it stays dangerous

```
:include /composite/_old_cops_deprecated:          145 pages
```

**The target is NOT in `nodes.zip`.** It is `composite.zip!_old_cops_deprecated.txt`.
A reader that opens only `nodes.zip` **cannot resolve it** and reproduces H5's defect exactly —
an entire vendor-deprecated subsystem reading as current. Its body:

> `:warning:Old network:` — *"As of Houdini 20.5, use Copernicus nodes instead of Compositing
> nodes… The Compositing network and its nodes will be deprecated and then removed in a future
> Houdini release."*

**I1 must glob every `*.zip` in `$HFS/houdini/help` plus the loose directories** — `helpdoc.py`
already does (11,709 pages loaded vs 5,032 in `nodes.zip` alone).

### Broken includes in the shipped documentation

```
include statements resolved   10,869 of 11,359
UNRESOLVED (anchor missing)      385
UNRESOLVED (page missing)          0
pages with >=1 broken include    158
distinct broken targets          272
```

These are **defects in the shipped docs, not parse failures** — e.g.
`/character/drawbones#drawbones`, `#remap_control_field`. They must be *marked*, never dropped:
a silently-dropped include is an undercount that looks like a clean parse.

### `@sections` are a relationship axis in their own right

`@related` (2,000+ pages) is an explicit see-also graph. `@inputs`/`@outputs` carry the
connection semantics and are the **only** documented surface for all 613 `apex/` pages.

---

## Q6 · THE DEPRECATION AXIS

**Answer: doc and runtime disagree on 195 node types. The union is 202. Both directions are
populated, and the dangerous direction has 51 members.**

*Producer: `_i0_q6_deprecation.py` → `_i0_q6_deprecation.json`, under `hython` on live 22.0.368.
Controls 10/10. Sample size: all 1,960 node-typed pages in six contexts that resolve to a live type.*

The doc signal is **tiered on purpose**, because H7-F12 caught the trap:

```
STRONG   '#status: deprecated'                            20 pages
         ':include /composite/_old_cops_deprecated:'     145 pages
         ':warning:Deprecated'                            24 pages
WEAK     the word 'deprecat'/'obsolete' anywhere        229 pages
```

Only STRONG counts as "the page states a deprecation." `lop/reference.txt` says
*"($IIDX is deprecated)"* — about an **expression variable**, not the node. Counting WEAK would
flag a node SYNAPSE emits 78 times. **WEAK is reported beside STRONG, never merged into it.**

### The disagreement, both directions

| ctx | both | **doc says, runtime does not** | **runtime says, doc does not** | neither |
|---|---:|---:|---:|---:|
| cop | 0 | 0 | 0 | 363 |
| lop | 0 | 2 | **2** | 176 |
| sop | 6 | 4 | **40** | 1,029 |
| out | 0 | 0 | **3** | 48 |
| top | 0 | 0 | **6** | 142 |
| cop2 | 1 | **138** | 0 | 0 |
| **TOTAL** | **7** | **144** | **51** | 1,758 |

```
UNION (the real deprecated surface)                202
node-typed pages with NO live type                 104
```

> **Not a copy error:** the Q4 exists-minus-clears gap is also **202**, of a different population
> (pages, not node types) from a different producer. The two integers coincide by chance.

**Direction 1 — doc says, runtime does not: 144.**
138 are `cop2/`, all via the `:include` banner. The vendor has announced the subsystem's removal
in prose while the runtime still reports the types as current. **A runtime-only oracle misses
this entire subsystem.**

**Direction 2 — runtime says, doc does not: 51. This is the dangerous cell.**
Every human-facing surface reads clean while the runtime flags the type:

```
lop/karma                    lop/karmarenderproperties     <- R72/H7-F2, CONFIRMED independently
sop/copy      sop/group      sop/point      sop/paint
sop/delete_overlapping_polygons             sop/particle
sop/break     sop/bridge     sop/cookie     sop/deform
sop/duplicate sop/falloff    sop/iso        sop/partition
+ 6 top/, 3 out/, and the remainder in sop/
```

Only **1 of the 51** carries even a WEAK prose mention. **An artist reading the documentation
has no way to learn these node types are decaying** — and several are among the most commonly
used SOPs in Houdini.

**R72 is confirmed on stronger evidence and extended:** R87 set the DECAY_CLOCK floor at 41 for
HOM symbols. At **node-type** level across six contexts the union is **202**.

**Deprecation must travel with the entry, as a two-source union with the source recorded per
side.** Neither axis alone is sufficient, and this measures exactly how insufficient.

---

## 7 · Cross-validation — two independent parsers

*Producer: `_i0_xvalidate.py` → `_i0_xvalidate.json`. Both readers run with includes resolved.*

| ctx | pages compared | exact agreement | agree % | mean abs delta |
|---|---:|---:|---:|---:|
| cop | 371 | 369 | **99.5%** | 0.01 |
| cop2 | 141 | 120 | 85.1% | 1.79 |
| lop | 181 | 140 | 77.3% | 6.99 |

**The `lop` disagreement is real and I did not average it away.** Adjudicated against the live
runtime by matching each parser's labels to live parm/parmTuple labels:

| node | live parms | I0 found | **I0 real** | H9 found | **H9 real** | I0 precision | H9 precision |
|---|---:|---:|---:|---:|---:|---:|---:|
| `lop/karmarendersettings` | 402 | 225 | **182** | 12 | 10 | 80.9% | 83.3% |
| `lop/componentoutput` | 111 | 189 | **114** | 19 | 19 | 60.3% | 100.0% |
| `lop/karmarenderproperties` | 359 | 179 | **138** | 15 | 12 | 77.1% | 80.0% |
| `lop/karma` | 275 | 251 | **146** | 140 | 84 | 58.2% | 60.0% |
| `cop2/light` | 60 | 38 | **34** | 1 | 0 | 89.5% | 0.0% |
| `cop2/levels` | 54 | 30 | **30** | 2 | 2 | 100.0% | 100.0% |

**They fail in opposite directions.** `_i0_reader` has far higher recall (182 real vs 10 on
`karmarendersettings`; 34 vs 0 on `cop2/light`) at somewhat lower precision. `helpdoc` is
precise but under-extracts badly on `lop/`.

**Neither is "the truth."** For I0's coverage questions high recall is the right bias, and the
precision cost is stated rather than hidden. **I1 needs a precision pass that neither reader
currently has** — see `I0-R2`.

---

## 8 · What I could NOT answer from the archive

A scout that guesses is worse than one that reports a gap.

| gap | what would answer it |
|---|---|
| **Are the 158 floor-clearing COP entries *correct*, not merely present?** Q4 measures shape, never truth. | A semantic spot-check: sample n≈30, compare each documented description against live behaviour. Needs a human or a second model, not a parser. |
| **Which of the two parsers is right on `lop/`** — the precision/recall trade is measured on 6 nodes, not the population. | Run the label-vs-live adjudication over all 181 LOP pages. Cheap; I ran the instrument, not the sweep. |
| **Do `apex/`'s 613 pages join to live types at all?** `#internal: Add<T>` is templated. | A live `hou.nodeTypeCategories()['Apex']` sweep matching template names. Out of this leg's six contexts. |
| **Is `#contentfrom` resolvable to real prose?** 1,199 occurrences; I measured presence, not resolution. | Extend the resolver to `#contentfrom`; `helpdoc` does not currently follow it. |
| **Whether H9-F1's "385" is recoverable at all.** No producer exists in the tree. | Only H9's author can say. It is not reconstructible from committed artifacts. |
| **Whether the doc is right and the runtime wrong** in the 144 doc-only cases. | Vendor confirmation. Both sources are authored by SideFX and they disagree; the archive cannot adjudicate itself. |

---

## 9 · What I1 should build against

1. **Key on label**, normalised. Record `#id` and `#channels` as evidence. Never key on `#id`.
2. **Try `#id` against `parmTuples()` before `parms()`** — free, worth 2–8 points.
3. **Resolve `:include`, `:includeprop` AND `:import`**, over **all** help zips plus loose dirs.
   Mark unresolved targets; never drop them.
4. **Decode `utf-8-sig`. Normalise line endings before parsing.** Both are silent-failure classes.
5. **Close the item scope on any `:xxx:` block directive** or a Vimeo id becomes a parameter name.
6. **Per-context parsing.** `cop`/`top` are directives-first + column-0. `lop`/`sop`/`out` are
   substantially title-first. `cop2` is indented. `apex` has no parameters at all.
7. **Deprecation is a two-source union**, recorded per side, STRONG signals only, with the
   `composite.zip` banner followed.
8. **Record the floor rung per entry.** A stub is `known-thin`, never padded.
9. **Nothing wires into RAG.** Standing rule, unchanged.

---

## Producers

```
harness/notes/ingest/_i0_reader.py           the calibrated reader (all numbers)
harness/notes/ingest/_i0_calibrate.py        61/61 controls -> _i0_calibration.json
harness/notes/ingest/_i0_q1_structure.py     Q1  -> _i0_q1_structure.json
harness/notes/ingest/_i0_q2_joinkey.py       Q2  -> _i0_q2_joinkey.json      (hython)
harness/notes/ingest/_i0_q2b_resolved.py     Q2b -> _i0_q2b_resolved.json    (hython)
harness/notes/ingest/_i0_q3_the161.py        Q3  -> _i0_q3_the161.json
harness/notes/ingest/_i0_q4_floor.py         Q4  -> _i0_q4_floor.json, _i0_q4_per_page.json
harness/notes/ingest/_i0_q6_deprecation.py   Q6  -> _i0_q6_deprecation.json  (hython)
harness/notes/ingest/_i0_xvalidate.py        §7  -> _i0_xvalidate.json
harness/notes/h9/helpdoc.py                  include resolver + second instrument (reused)
```

Every number in this document is emitted by one of the above. No figure is inherited from a
conversation, a prior receipt, or this leg's own brief.
