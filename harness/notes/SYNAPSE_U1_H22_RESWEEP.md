# SYNAPSE U.1-H22 Re-sweep — Discovery-Breadth Delta (THIN spec)

**Status:** candidate (proposal) · **Layer:** utility · **Mode:** A (spec + baseline are H21-legal; the H22 diff is a MODE-B drop-week step)
**Scope:** ONE delta only — *discovery breadth*. This spec does **not** re-specify the
probe -> candidate -> ratify flow. That flow is already binding and is cited, not rewritten:

- **Probe / sweep -> candidate deposit** — `.claude/workflows/h22-drop-week.js:46-56` (runbook **step 4**:
  re-run the sweep, diff vs the U.1 catalog, append a `status:"candidate"`, `ratified:false`,
  evidence-linked cycle to `harness/state/flywheel_queue.json`; "You NEVER write `ratified:true`").
- **Human ratify (the only flip)** — `.claude/workflows/h22-drop-week.js:98-103` (**step 10**: "human ratify.
  Flip nothing until every artifact reads clean").
- **Evidence-linked candidate append at REVIEW** — `harness/notes/spec-U1-wiring-flywheel.md:42-46`
  (new probeable-truth classes surfaced by the sweep are appended to the queue as
  evidence-linked candidates, `status "candidate"`, `ratified: false`).

Everything below plugs **into** those bindings. It adds no new ratify path, no new human gate,
no new deposit mechanism — only a wider left-hand set for the existing diff.

---

## 1. The verified gap: the sweep is emitter-seeded

Both host introspectors that feed the U.1 diff enumerate **only the node types SYNAPSE already
emits**, read from `python/synapse/cognitive/tools/data/emitted_node_types.json`:

- `host/introspect_connectivity.py:203-244` — `_collect_targets(...)` walks `emitted["entries"]`
  and (line 213-234) resolves each *emitted spelling* against every category, plus one pattern
  expansion for Sop types matching `solver|merge|switch|blend` (line 236-241). Its universe is
  `emitted ∪ {those Sop patterns}`.
- `host/introspect_nodetypes.py:343-360` — `build_catalog(...)` loops `emitted["entries"]` and calls
  `_resolve(...)` per emitted spelling. Same seed, same blind spot.

**Consequence.** A net-new H22 node *family* — one SYNAPSE has never emitted (Copernicus
heightfield SOPs, ML/ONNX inference nodes, splat trainers, new Solaris procedurals) — is **invisible**
to both probes. They can only re-confirm the wiring/parm truth of types already on the seed list;
they cannot *discover* that H22 grew a family the seed never named. Drop-week step 4 diffs the
*connectivity* of known types; it does not enumerate the *catalog* to find unknown ones.

This is a discovery-breadth hole, not a correctness hole. The fix is a **full-category inventory
diff** whose left side is a full-category H21 baseline, not the emitter seed.

---

## 2. Full-category inventory diff

The re-sweep enumerates the **entire** node-type catalog per category and subtracts an H21
full-category baseline. Mechanically, on the H22 build:

```
for cat_name, category in hou.nodeTypeCategories().items():   # every category, no seed
    for full_name in category.nodeTypes():                    # every type, no emitter filter
        H22_inventory[cat_name].add(full_name)

net_new[cat_name] = H22_inventory[cat_name] - H21_baseline[cat_name]
```

- Left side = the **H21 full-category baseline** artifact in §3 (frozen, hash-pinned).
- Right side = the live H22 full-category enumeration (same `hou.nodeTypeCategories()` ->
  `category.nodeTypes()` walk, run once under H22 hython).
- `net_new` per category is grouped into **families** by the common node-name stem (namespace
  prefix before `::`, or the leading token before the first underscore/digit) — a family is a
  reporting bucket, never an assertion that any member resolves.

Only the *set difference* is new work here; the arity/label/parm probing of any discovered type is
still the existing U.1 / nodetype probe machinery, run after a family is ratified.

---

## 3. Required NEW baseline artifact — `harness/notes/verified_node_inventory_21.0.671.json`

The diff needs a left side that **does not exist today**. `verified_nodetype_catalog_21.0.671.json`
is emitter-seeded (only resolved emitted spellings) and therefore cannot serve — a family missing
from the seed is missing from that catalog too. Author a **full-category inventory** baseline:

- **Producer:** a new host probe (sibling of the two in §1), zero-`synapse`-import, `hou` inside
  functions, deterministic (sorted, no wall-clock stamp), `blake2b` over the sorted body — same
  contract as `host/introspect_connectivity.py`.
- **Schema:** `verified_node_inventory/v1`.
- **Content:** for **every** category from `hou.nodeTypeCategories()`, the full sorted list of
  `category.nodeTypes()` keys — the complete per-category type roster, no emitter filter.

```
{
  "schema": "verified_node_inventory/v1",
  "houdini_version": "21.0.671",
  "blake2b": "<16-byte digest over sorted categories>",
  "generated": { "by": "host/introspect_node_inventory.py",
                 "note": "deterministic; full hou.nodeTypeCategories()->nodeTypes() enumeration" },
  "categories": { "Sop": ["<type>", ...], "Lop": [...], "Cop": [...], "Top": [...], ... }
}
```

Produced once on the **pinned H21.0.671** build (MODE-A legal — it is the frozen left side, not an
H22 write). The H22 run of the same producer yields the right side; the two are diffed by step 4b.

---

## 4. Plug-in point: drop-week **step 4b** (sibling of step 4)

Add one step to the runbook, immediately after step 4 (`.claude/workflows/h22-drop-week.js:46-56`),
reusing its exact deposit contract:

- **Runs:** the §2 full-category inventory diff — H22 enumeration minus
  `harness/notes/verified_node_inventory_21.0.671.json` (hash-checked against the frozen baseline
  first, like step 4 hash-checks `leg0_baselines.json`).
- **Emits:** `harness/notes/verified_node_inventory_H22.json` (the right side) + a per-family
  **candidate** append to `harness/state/flywheel_queue.json` `cycles[]`.
- **Never writes `ratified:true`** — identical to step 4's own constraint. Ratification stays the
  human gate at **step 10** (`:98-103`). Step 4b only *proposes*.

Step 4b is additive: step 4 keeps proving *wiring* truth on known types; step 4b proves *breadth*
by surfacing unknown families. Both deposit candidates the human adjudicates once.

---

## 5. Queue append contract + candidate example

Each discovered family becomes one cycle appended to `harness/state/flywheel_queue.json`
(schema `flywheel_queue/v1`). Per the queue `_doc` and `spec-U1-wiring-flywheel.md:42-46`:

- cycle shape = `{ id, title, status, evidence[], ratified, note }`
- `status` = `"candidate"` (a proposal, never a work order)
- `ratified` = `false` — flipped by a **human only**, at drop-week step 10
- `evidence[]` **must be non-empty** — an evidence-free entry is invalid and is rejected at review

Example candidate (illustrative — the family name below is **phantom-pending** a live H22 probe):

```
{
  "id": "N.0",
  "title": "Net-new H22 node-family discovery: full-category inventory diff -> per-family candidate cycles",
  "status": "candidate",
  "evidence": [
    "harness/notes/SYNAPSE_U1_H22_RESWEEP.md",
    "harness/notes/verified_node_inventory_21.0.671.json",
    "harness/notes/verified_node_inventory_H22.json"
  ],
  "ratified": false,
  "note": "Left side = the H21 full-category inventory baseline; right side = the H22 enumeration. Each net-new family (e.g. the ML/splat bucket whose whitepaper spelling top::gaussian_splat_train is UNVERIFIED and phantom-pending a live H22 probe) becomes its own candidate cycle here. No family member is emitted, wired, or catalogued until step 10 ratifies it."
}
```

Written in-band with drop-week's deposit style: `status: candidate`, `ratified: false`, evidence
pointing at the two inventory artifacts + this spec.

---

## 6. Phantom-discipline disclaimer (G-2 truth contract)

**Every H22 family name and every H22 node-type spelling produced by this re-sweep is a candidate —
phantom-pending until a live H22 probe confirms it.** The inventory diff reports *set membership in a
freshly enumerated catalog*; that is evidence a spelling appeared under `category.nodeTypes()` on one
build, and nothing more. It is **not** a runtime-existence verdict for SYNAPSE's emitter, and it never
promotes a spelling to confirmed API.

Concretely, for any H22 symbol surfaced here:

- No spelling may be written into any catalog, corpus, code path, or symbol table with an affirmative
  runtime verdict. The `exists_in_runtime` field stays `false` or `null` until a dedicated probe
  proves it under the H22 dir() symbol-table authority (the Scout membership gate, §11 rule 15).
- No spelling is described as verified live API, and none is emitted by any handler or recipe.
- A phantom-shaped spelling such as `top::gaussian_splat_train` is a **candidate / phantom-pending**
  example only — the whitepaper names it, the probe has not confirmed it, so it stays quarantined.
- Discovery breadth widens what we *look at*; it never widens what we *trust*. Trust still comes only
  from the introspected H22 symbol table and the CRUCIBLE after-the-fact check.

This keeps the re-sweep on the right side of SYNAPSE's #1 failure class (phantom APIs): it can name a
family as a candidate for adjudication without ever asserting that family is real.
