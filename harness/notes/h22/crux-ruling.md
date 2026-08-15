# W4-RULING — Crucible on the bookish-AST source ruling (feeds Gate P)

**Leg:** W4-RULING · branch `wave4/ruling` · notes-only · **Date:** 2026-08-15 · **Live build:** 22.0.400
**Target under attack:** the late-arriving *xref cache-vs-zip* ruling, recorded RESOLVED in
`docs/reviews/h22-context-knowledge-recon-2026-08-15.md:178` and banked verbatim at
`.token-saver/h22-context-recon-wave2.md:481-534`. That ruling shipped self-flagged:
*"has NOT been through a crucible; its execution claims were artifact-corroborated and spot-checked only."*
This leg is that crucible.

> **This leg holds itself to the bar it enforces.** Every number below is OBSERVED by this run —
> a fresh detached regen, three read-only forensics legs, and direct source reads — each carrying a
> probe path or `file:line`. No claim is carried forward on the original agent's word. Where I could
> not observe something, it says UNKNOWN with the reason.

---

## TL;DR — the ruling survives the crucible on substance; four numbers are corrected

The xref agent's technical measurements are **accurate**. A fresh headless regen on 22.0.400 reproduced
its headline to the integer: **5,481 /nodes/ pages, 0 errors, 72.1 MB**, and the seven `attrs.id`
coverage figures (cop 99 / top 97 / lop 75 / sop 64 / vop 57 / dop 25 / chop 3) landed within 1% each.
The "OneDrive cache is unusable" finding reproduced with its mechanism intact (build-blind cache +
backwards-dated `.400` zip members under a `cachedt >= srcdt` rule). The internal-API risk it named is
**real and priced HIGH** with source receipts.

**Four corrections** (all minor, none load-bearing, all the kind of thing a crucible exists to catch):
1. **File count 6,281 → 5,827.** A clean regen writes 5,827 JSON (5,481 pages + 346 include fragments), not 6,281.
2. **"6 top-level keys" → 8.** The cache also carries `examplefile`/`examplefor`; the "no version stamp" core holds.
3. **Zip-date inversion is 95.8%, not total.** 212 of 5,034 `.400` members are *newer* — the staleness is broad, not universal.
4. **"805 lines i1_extract reimplements" is ~2× inflated.** ~400 lines are include+section machinery an AST replaces; the other ~400 are work an AST does **not** give for free.

**The decisive qualifier for Gate P:** the ID-join upgrade the ruling calls "the single largest correctness
upgrade" is real but **concentrated**. `attrs.id` is dense only in cop/top/lop/sop; in the legacy/heavy
contexts (chop 3%, cop2 8%, dop 25%, out 35%, obj 42%) LABEL and `#channels` must carry the join — and
LABEL is the higher-*resolving* key today (~89% vs ~43-53% for `#id`). The **multiparm-semantics question
and the mandatory runtime probe are owed on BOTH fork branches.** Neither branch is "done" without
SYNAPSE-side, kind-aware handling.

---

## 1. Method & provenance

| Instrument | What it did | Evidence artifact |
|---|---|---|
| **Fresh regen** | Detached `hython 22.0.400`, the exact call chain the ruling claims, into a SYNAPSE-owned scratch cache (never the user's OneDrive). Sentinels DONE/FAILED; STEP-tracked. | `harness/notes/h22/w4_regen_probe.py`; result `harness/notes/h22/w4_regen_result.json`; log `…/scratchpad/w4regen/regen.log` |
| **OneDrive forensics** (read-only) | Re-derived the "unusable" ruling from the on-disk cache + both `nodes.zip` archives, pure-Python (no `hou`). | measured in-leg; numbers cited inline below |
| **Parser forensics** (read-only) | Costed branch A (`i1_extract` + 4 patches) + the multiparm question, `file:line`. | `harness/notes/ingest/i1_extract.py`, `i1_build.py`, `i1_calibrate.py` |
| **API-risk forensics** (read-only) | Priced the internal-API surface of branch B against the live 22.0.400 `bookish`/`houdinihelp` source. | `…/Houdini 22.0.400/houdini/python3.13libs/{bookish,houdinihelp}` |

The regen call chain, verified against live source *before* running (so a rename would have STEP-failed loudly,
not guessed): `houdinihelp.hconfig.read_houdini_config` (`hconfig.py:269`) → override `cfg["CACHE_DIR"]`
(default is the OneDrive dir, `hconfig.py:32`) → `houdinihelp.hpages.pages_from_config` (`hpages.py:35`) →
`bookish.util.get_prefixed_paths(pages, "/nodes/")` (`util.py:80`) filtered by `is_wiki_source`/`exists`
(`wikipages.py:551,577`) → `pages.json(p, conditional=False, postprocess=False, save_to_cache=True)`
(`wikipages.py:720`). Regen wall time **199.6 s** (the ruling's 170 s is same-order; this run was ~17% slower
under concurrent load — page count and error tally are load-independent and reproduce exactly).

---

## 2. Claim ledger — every ruling claim, verdict + anchor

| # | Ruling claim (`…recon-2026-08-15.md:178` / `…wave2.md:481-534`) | Verdict | Anchor / probe |
|---|---|---|---|
| C1 | **5,481 /nodes/ pages parsed, 0 errors** | **REPRODUCED** (exact) | `w4_regen_result.json`: `paths_wiki_exists=5481, parsed_ok=5481, parse_errors=0` |
| C1b | **170 s, 31 ms/page, 72 MB** | **REPRODUCED** (size exact; timing same-order) | `elapsed_s=199.6, ms_per_page=36.4, cache_mb=72.1` — 72 MB exact; 170 s vs 199.6 s is load variance |
| C2 | **6,281 JSON files on disk** | **REFUTED as stated** → fresh count **5,827** | `cache_files_written=5827` = 5,481 /nodes/ + 346 include-target fragments (shelf 310, copernicus 6, …) |
| C3 | **attrs.id coverage cop 99 / top 97 / lop 75 / sop 64 / vop 57** | **REPRODUCED** (all to the integer) | `ctx_id_coverage_pct`: cop **99.4**, top **97.8**, lop **75.8**, sop **64.9**, vop **57.9** |
| C3b | **dop 25 / chop 3** (id-sparse tail, ruling risk #5) | **REPRODUCED** | `dop 25.0`, `chop 3.1`; also cop2 7.5, obj 42.4, out 35.0, shop 30.4 |
| C4 | **sop/xform carries attrs.id = t, r, s** | **REPRODUCED** | on-disk AST `nodes/sop/xform.json` → `parameters_item` ids `[xOrd, rOrd, t, r, s, shear, scale, p, pr, …]` |
| C4b | **APEX 618 pages, typed as ports, 0 parameters_item** | **REPRODUCED** (exact) | `apex_pages=618, apex_inputs_section=594, apex_outputs_section=598, apex_parameters_item=0` |
| C4c | **root attrs {type,context,internal,icon,tags,since,version,namespace}** | **REPRODUCED** | `nodes/apex/*.json` root attrs keys = exactly those eight |
| C5 | **OneDrive cache ~30% populated (1,629 pages)** | **REPRODUCED** | on-disk `nodes\**\*.json` = **1,629** pages; ÷ live universe 5,481 (my regen) = **29.7%** |
| C5b | **no version stamp anywhere in the format** | **REPRODUCED** | 2,266 cache files scanned, `{version,build,houdini_version,…}` → **0 hits** |
| C5c | **"only keys {attrs,body,included,summary,title,type}"** | **SHARPENED** — 8 keys, not 6 | real union adds `examplefile`/`examplefor` (75 files each); "no version field" still holds |
| C5d | **AssetIndexer burst: 1,435 files in one minute, 2026-07-15 13:32** | **REPRODUCED** | busiest 60 s (nodes) = **1,435** at `2026-07-15 13:32`; whole-cache = 1,973 same minute; then day-dribble |
| C5e | **AssetIndexer is `api.py:718`; sop/attribwrangle absent, attribwranglecore present** | **REPRODUCED** | `houdinihelp/api.py:718 class AssetIndexer(threading.Thread)`; `sop\attribwrangle.json` ABSENT, `…core.json` PRESENT |
| C5f | **staleness rule `cachedt >= srcdt` (wikipages.py:200-209); `.400` zip dates OLDER than `.368`** | **REPRODUCED** (sharpened: 95.8%, not total) | `PageCache._cached_dt` :200-209 quoted; `.400` members min **2026-05-02**, `.368` min **2026-07-03**; 4,822/5,034 `.400`-older; `lop/light` .400=05-02 vs .368=07-03; **caveat** 212 members newer in .400 |
| C6 | **free #include/#contentfrom resolution → the ~800 lines i1_extract reimplements** | **REPRODUCED (mechanism); SHARPENED (~400, not 805)** | `Includes` splices `objs[i:i+1]=icontent` `pipeline.py:587`, `included` list `includes.py:262-269`, `ContentFroms` `hpages.py:769`. i1_extract include+section machinery ≈ **400 lines**, file total 805 |
| C6b | **+43% params (12,645 AST ids vs 8,844 raw #id:, 731 pages)** | **PARTIAL** — magnitude consistent, exact Δ not independently recomputed | my lop+cop+top items-with-id = 4,209+5,281+3,331 = **12,821** over 760 pages; consistent order; raw `#id:` baseline not recounted here |
| C7 | **bookish/houdinihelp is an internal, undocumented API a major can break silently** | **REPRODUCED — priced HIGH** | no `__all__`/module docstrings/stability markers; `bookish` = vendored BSD (Whoosh author); see §4 |
| C7b | **regen requires hython; `--disablehou` dies at `hstores.py:179` during list_all** | **REPRODUCED** | `AssetStore.list_all` `hstores.py:178-201` drives enumeration through `hou.nodeTypeCategories()` — no `hou`, no enumeration → no plain-CI regen |
| C8 | **coverage beyond zip: 5,481 vs 5,034 .txt; sop 1563 / lop 209 / out 78** | **REPRODUCED** | `ctx_pages`: sop **1563**, lop **209**, out **78**; live universe 5,481 vs `.400\nodes.zip` **5,038** .txt members |
| M | **multiparm-semantics question survives either fork branch** | **REPRODUCED (confirmed against code)** | neither `i1_extract` fold (`:575-586`) nor a doc-only `parameters_item` tree distinguishes menu-value from multiparm-instance — see §5 |

**Nothing in the ruling was refuted on substance.** C2 (file count) is wrong-as-stated; C5c and C5f are
*sharpened* (the ruling under-counted keys and over-stated the inversion as total); C6 is *sharpened* (its
"805 lines" is a ~2× over-attribution). All are honesty corrections, not reversals.

---

## 3. Internal-API risk, priced (target 2)

### 3a. What breaks on a Houdini major

The adapter binds to an **undocumented, third-party-vendored, `hou`-coupled internal surface.** Fragility, with receipts:

| Dependency | Fragility | Why (`file:line`) |
|---|---|---|
| `WikiPages.json(...)` | **HIGH** | Real signature `wikipages.py:720` carries `wcontext, process` *between* `path` and the kwargs the adapter assumes — a positional call is already wrong; a reorder breaks it silently or loudly |
| `store.list_all` | **HIGH** | base `stores.py:198` + **8 overrides**; the node-help override `hstores.py:178` hard-requires `hou` — the very enumeration the regen needs is both multi-implementation and `hou`-bound |
| AST vocab `inputs_section`/`outputs_section`/`attrs.channels` | **HIGH** | **not a Python token anywhere in `python3.13libs`** — a doc-authoring convention, not a code contract; a rename yields empty parses with **no error to catch** |
| `read_houdini_config` | **MED** | `hconfig.py:269`; 5 kwargs, internal `import hou`, config-class swap `HoudiniHfsConfig`/`HoudiniShdConfig` |
| `get_prefixed_paths` | **MED-HIGH** | `util.py:80`; trivial wrapper, but inherits the `list_all`/`hou` hazard; unexported |
| `parameters_section`/`parameters_item` | **MED** | string-typed node names (`api.py:881`, `hpages.py:670`), no enum/constant — silent on rename |
| `attrs.id` | **LOW-MED** | ubiquitous but string-keyed; a schema move breaks lookups silently |
| `pages_from_config`, `is_wiki_source`, `exists` | **LOW-MED** | stable shapes; `exists` for node help still routes through `hou` (`hstores.py:159-160`) |

Corroborating churn evidence: `bookish/compat.py` is a live **Py2→Py3 shim** (`b()`/`u()`, `xrange=range`,
`with_metaclass`, `time.clock` win32 branch) imported pervasively — the codebase already absorbed one
language-era migration behind a shim, and the whole tree has moved to `python3.13libs` (an ABI-keyed dir).
A major that bumps embedded CPython is exactly when this surface refactors. **The "silent break" risk is real,
not theoretical.** The one genuine upside — free `#include`/`#contentfrom` splicing + a resolved `included`
manifest — is purchased against ≥3 HIGH-fragility symbols and one breakage class (AST section vocab) that
**no static check can detect**.

### 3b. CI cost of a hython-coupled regen

`get_prefixed_paths → store.list_all → AssetStore.list_all` (`hstores.py:178`) drives node enumeration through
`hou.nodeTypeCategories()`. There is **no filesystem fallback** — node help exists only inside a running
Houdini. So the regen **cannot run in plain CI**; it needs a licensed hython + a full Houdini install per build.
This run confirmed the cost envelope: **~200 s wall, 72 MB, one license checkout**, alongside a live session
(this host ran it while the bridge was connected). Branch A (`i1_extract` over `nodes.zip`) needs neither `hou`
nor a license — it runs on a stock CI runner.

### 3c. LABEL-fallback coverage where attrs.id is absent (target 2)

The ID join is an upgrade **only where `attrs.id` is dense.** Per-context, from the regen (`ctx_items` /
`ctx_items_with_id` / `ctx_items_with_channels`):

| ctx | parameters_item | attrs.id cov | **id-absent → LABEL/channels needed** | #channels items (legacy fallback) |
|---|---:|---:|---:|---:|
| cop | 5,314 | 99.4% | **0.6%** | 0 |
| top | 3,406 | 97.8% | **2.2%** | 0 |
| lop | 5,555 | 75.8% | **24.2%** | 0 |
| sop | 28,839 | 64.9% | **35.1%** | 554 |
| vop | 3,787 | 57.9% | **42.1%** | 3 |
| obj | 1,777 | 42.4% | **57.6%** | 43 |
| out | 2,090 | 35.0% | **65.0%** | 8 |
| shop | 795 | 30.4% | **69.6%** | 20 |
| dop | 9,095 | 25.0% | **75.0%** | 1,163 |
| cop2 | 1,997 | 7.5% | **92.5%** | 670 |
| chop | 1,975 | 3.1% | **96.9%** | 370 |
| apex | 0 (ports) | — | uses `inputs_section`/`outputs_section` | 0 |

**Two things this table forces into the Gate P decision:**
1. `attrs.id` **coverage ≠ join resolution.** A stable id is a *better key* than a fuzzy label where present,
   but LABEL is present on 100% of records and resolves **~89%** today, while `#id` (present 62-85%) resolves
   only **~43-53%** (`i1_build.py:116-119`). The AST's ID join raises join *precision* where dense; it does
   **not** remove the LABEL fallback, and cannot be the sole key.
2. The contexts where LABEL/channels must still carry the join (chop, cop2, dop, out, obj, shop) are precisely
   the legacy/heavy ones. So the "single largest correctness upgrade" framing should be read **per-context**:
   decisive for cop/top/lop/sop, marginal-to-irrelevant for the id-sparse tail.

---

## 4. The multiparm-semantics carry (survives both branches)

In the help source, a **menu value** and a **multiparm per-instance parameter** are written identically —
an item indented under a parent item. `i1_extract` classifies by indentation only (`parse_text` depth at
`:534-539`, re-resolve `:562-567`, the **fold** at `:575-586` that absorbs every depth-1 item into its
ancestor's `description`, and `Page.params` returning only depth-0 at `:378-382`). For COP menu values this is
correct (calibration control `P2d`/`B7`); for a SOP multiparm folder it **silently deletes** the real
per-instance parameters into prose.

A bookish AST does **not** fix this. It hands back a typed `@parameters` section and a `parameters_item` tree
with the *same indentation-derived nesting* — but "menu value vs multiparm instance" is **not encoded in the
help markup at all.** The distinction lives in the parameter's runtime *kind* (ordinal/menu vs multiparm
template), which no doc source carries. So:

- **Branch A** must add SYNAPSE-side kind-aware logic before the fold.
- **Branch B** must add the **same** kind-aware disambiguation — the AST removes the *tree-reconstruction*
  cost, not the *leaf-labelling* cost.

This is why the ruling says the question survives either way, and it is **confirmed against the code.**
Related and equally branch-agnostic: **no source (AST or raw) carries parameter TYPE / DEFAULT / RANGE / menu
items** — so the live runtime probe (`i1_runtime`, extended per context) stays mandatory regardless of which
fork wins.

---

## 5. Gate P fork memo — both branches, costed with receipts

> **This is the crucible's advisory input to Gate P, not a ruling.** The parser-source fork is a human word.
> Both branches are laid out with receipts; the recommendation at the end is advisory.

### Branch A — `i1_extract` hand parser + 4 patches

**Cost (all anchors confirmed present in `i1_extract.py`):**
- **Patch 1** — widen `PARAM_SECTIONS` (`:121`, currently `("parameters","top_attributes","properties")`) to add `@inputs`/`@outputs`. One-tuple edit; ripples free through `:274`,`:382`,`:523`. Recovers APEX + VOP's missing half.
- **Patch 2** — fix tab-indent math in `_indent()` (`:153-155`). 3-line fix; propagates to item depth + body capture.
- **Patch 4** — resolve/record `:includeprop` (already parsed at `RE_INCLUDE` `:97-98`; 266/266 unresolved because targets live in `houdini/soho/parameters/*.ds`, outside `load_corpus` `:693-701`). "Point the resolver at the `.ds` files or record the external-source gap" — no new grammar.
- **Patch 3** — the multiparm fold (`:575-586`). The one hard patch; **owed on both branches** (§4).

**Keeps / strengths:**
- **Supported surface:** reads `nodes.zip` only; no internal `hou` API; **runs in plain CI, no license.**
- **Calibrated & green:** `i1_calibrate.py` (436 lines) — **35/35 controls pass** (`_i1_calibration.json`), each with a `fails_if`, spanning COP/COP2/LOP. *Nuance for the memo:* the sha-pinned re-entry guard (`i1_verify_reentry.py` V6/V8) attaches to the sibling `i1b_reader.py` lineage; `i1_extract.py`'s own record proves-by-rerun, not by hash-pin. State it precisely.
- **LABEL join** (`i1_build.py:124`, `norm_label` `i1_extract.py:133-150`) — resolves ~89%, the higher-resolving key today.

**Weakness:** LABEL is a weaker *key* than a stable id where id is dense (cop/top/lop/sop); ~400 lines of
include+section machinery to maintain; `:includeprop` external gap unresolved.

### Branch B — bookish-AST adapter

**Buys (reproduced this leg):**
- Free `#include`/`#contentfrom` resolution + a resolved `included` manifest (`pipeline.py:542`, `includes.py:262-269`, `hpages.py:769`) — replaces **~400** hand lines (not 805).
- Typed sections (no indentation inference); APEX typed as ports for free (618/594/598/0); richer root attrs (`{type,context,internal,icon,tags,since,version,namespace}`).
- **ID join** where `attrs.id` present — cop 99 / top 97 / lop 75 / sop 64 / vop 57 (reproduced exactly). A precision upgrade, **concentrated** (§3c).

**Costs (priced this leg):**
- **Internal, undocumented, `hou`-coupled API** — HIGH fragility on ≥3 load-bearing symbols; one breakage class (AST section vocab) undetectable by static check (§3a).
- **No plain-CI regen** — hython + license + full install per build (§3b).
- **No version stamp in the AST** — SYNAPSE must self-stamp `hou.applicationVersionString()`; the cache is build-blind by construction (`cachedt >= srcdt` + backwards-dated `.400` members), so a `.368→.400` change is invisible to bookish and must be caught by us.
- **Moots patches 1, 2, 4 — but NOT patch 3** (multiparm) and NOT the runtime probe.

### Carried on both branches (non-negotiable, either way)
1. **Multiparm disambiguation** — runtime parm-kind lookup; neither doc source supplies it (§4).
2. **Runtime probe stays mandatory** — no source carries TYPE/DEFAULT/RANGE/menu.
3. **LABEL / `#channels` fallback stays mandatory** — id is sparse in the legacy/heavy tail (§3c).

### Advisory recommendation (human rules at Gate P)
The evidence points to a **staged** answer rather than a straight either/or:

- **Ship Branch A's 4 patches now.** They are cheap, localized, calibration-guarded, CI-portable, and needed
  at today's scale *regardless* of the fork. Patch 3 is the multiparm carry — do it kind-aware once, reuse on both.
- **Treat Branch B as an opt-in enrichment, gated — not a replacement of the hand parser.** Its decisive win
  (ID join) is concentrated in cop/top/lop/sop; adopt it there behind (a) a schema-shape assertion on the AST
  node vocabulary, (b) a self-stamped build guard that fails when `cache.build != hou.applicationVersionString()`,
  and (c) a pinned adapter over a minimal symbol set. Do not let it delete the LABEL/`#channels` join or the
  `nodes.zip`/CI path.
- **Do not** book Branch B as "805 lines saved" (it's ~400) or as "the join problem solved" (LABEL still
  resolves better and is still required in six contexts).

The ruling is **sound enough to act on**; the fork is a genuine trade (portability + calibration vs. join
precision + typed sections), and the honest framing is *both, staged* — not *one instead of the other*.

---

## 6. Reproduction

```
# fresh regen (detached; ~200 s; writes to scratch, never OneDrive):
"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
    harness/notes/h22/w4_regen_probe.py
# → DONE sentinel + regen_result.json (counts, per-context coverage, spot-checks)

# on-disk forensics (pure python, no hou): OneDrive cache + both nodes.zip archives
# parser forensics (read-only): harness/notes/ingest/i1_extract.py + i1_build.py + i1_calibrate.py
# api-risk forensics (read-only): .../Houdini 22.0.400/houdini/python3.13libs/{bookish,houdinihelp}
```

Result artifact committed alongside this ruling: `harness/notes/h22/w4_regen_result.json`
(the 72 MB regenerated AST cache itself is scratch-only, deliberately not committed).

*Crucible complete. This receipt feeds Gate P; it flips nothing — the parser-source fork is a human word.*
