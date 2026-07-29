# H9 — drift log

Reality contradicting the governing documents for this leg (`harness/prompts/h9.md`,
`harness/legs.json`, `harness/notes/CTO_RULINGS_01.md`). Per Article VI: cosmetic ⇒ resume,
structural ⇒ escalate. Written from the tree and the live build, not from recall.

---

## D-H9-1 · `D2` and `D3` name different things in different governing documents — STRUCTURAL

**Doc claim** `harness/prompts/h9.md:25` — *"Documentation supplies D2 (semantic). It CANNOT
supply D3 (behavioural)."* Same definition in `harness/notes/_doc_coverage.py:4-6`.

**Reality** `VERIFIED-STATIC` — `harness/notes/receipts/L1.json:36-37`, the **producer of the
18.3% and 6.2% baselines this leg exists to lift**, defines them the other way:

    "D2_literal_emission": { "n": 31, "pct": 14.2 },
    "D3_semantic":         { "n": 27, "pct": 12.4 },

and `L1.json:41` records `Cop` as `D1 24, D2 24, D3 0`. Under L1, the SEMANTIC slot is **D3**
and it is **0** for both COP categories. Under the H9 brief, semantic is **D2**.

`RULING 2` (`CTO_RULINGS_01.md:39`) rules `D2 ∪ D3` canonical and quotes 40/218 = 18.3%, but
never defines either letter — so it is consistent with both readings and settles neither.

**Impact** The two composite figures are unaffected (the union is the same set either way).
What is affected is any figure reported *per letter*. A doc-derived semantic number labelled
"D2" would be read by an L1-shaped reader as a literal-emission number, and would be compared
against 31/218 instead of 27/218 — a 4-type error in the wrong direction, in a document whose
whole subject is not merging incomparable numbers.

**Disposition** Resumed, with the labels avoided. Every figure this leg emits is named in words
— **PROJECTED-DOC (semantic, documentation-derived)** — and never as a bare `D2`. Escalated as
a ruling item (`H9-R1`) because two governing documents cannot keep using the same two symbols
for swapped concepts.

---

## D-H9-2 · the coverage figures in the brief and in `legs.json` are not reproducible — COSMETIC

**Doc claim** `harness/prompts/h9.md:19-20` and `harness/legs.json` (H9 `note`) —
*"LOP 179/198 = 90%, COP 460/491 = 94%"*.

**Reality** `VERIFIED-RUNTIME` — producer `harness/notes/h9/build_corpus.py`, against the live
catalogues:

| surface | live | has a page | |
|---|---|---|---|
| Lop  | 218 | 193 | 88.5% |
| Cop  | 384 | 380 | 99.0% |
| Cop2 | 169 | 149 | 88.2% |

*(These are the post-audit figures. The first pass of this leg reported 181/371/139, having
never walked the reference's `manager/` directory — see the receipt's `corrected_after_audit`.)*

Both stated figures are wrong on **both** terms:

* **198** is not a count of live LOP types. `_doc_coverage.py:61` does
  `n.split("::")[-1].lower()` over the catalogue keys, so `cache::2.0` becomes `2.0` and
  `Labs::biome_plant_scatter_import::1.0` becomes `1.0`. 218 distinct type names collapse to
  198 strings, three of which are version numbers. The brief flagged the parse as approximate;
  this records exactly how.
* **491** is a **merged** `Cop` + `Cop2` denominator — `_doc_coverage.py:33` passes
  `("cop", "cop2")` as one key set. `RULING 3` (`CTO_RULINGS_01.md:63-66`) makes `Cop` the
  target surface, freezes `Cop2` as maintenance-only, and **bans "COP coverage" as a bare
  phrase** for exactly this reason.

**Disposition** Resumed — the brief pre-declared the first pass approximate and asked for the
comparison to be redone, which is work item 1. Recorded because the same figures also sit in
`harness/legs.json`, which is deny-listed from agent edit, so they will outlive this leg unless
a human corrects them.

---

## D-H9-3 · the `karmarenderproperties` page size is not reproducible on this build — COSMETIC

**Doc claim** `harness/prompts/h9.md:29` — *"a 69,921-character page"*.

**Reality** `VERIFIED-RUNTIME` — `nodes.zip!lop/karmarenderproperties.txt` on 22.0.368 is
**56,325 bytes and 56,325 characters** (pure ASCII; `compress_size` 16,012).

**The load-bearing half of the claim holds and was re-verified.** A case-insensitive search of
the decoded page for `deprecat` returns **False**, and `obsolete` / `legacy` / `superseded` /
`no longer` are all absent — while `hou.nodeType('Lop','karmarenderproperties').deprecated()`
is `True`. The runtime flags it; the reference is silent, at length.

**Disposition** Resumed with the figure corrected to the measured one. The finding stands; only
its size adjective changes.

**Self-correction, 2026-07-27, after the adversarial audit (H9-TIER-03).** This entry first
claimed the class was wider — *three* silent types, adding `Cop2/loop`. That was wrong, and it
was wrong in the direction that made the finding look bigger. `cop2/loop.txt` line 12 carries

    :include /composite/_old_cops_deprecated:

whose target lives in a **sibling archive** (`composite.zip`, which this harvest does not open)
and reads *"As of Houdini 20.5, use Copernicus nodes instead of Compositing nodes"*. The page is
not silent; it states the deprecation by reference. The silence test was scanning only the
parsed summary and prose sections, where an include directive never appears. It now scans the
raw page source and treats an include whose name states the deprecation as a mention.

**Corrected finding:** **two** deprecated types have a page and neither mentions it —
`Lop/karma` and `Lop/karmarenderproperties`. A third, `Cop2/swap`, is deprecated with no page at
all. The whole Cop2 surface carries its deprecation banner by include reference, which is a
better-documented posture than this leg first credited it with.
