# SYNAPSE — INGEST

**Harness ID** `INGEST-01` · **Authored** 2026-07-27
**Governed by** `harness/AGENT_CONSTITUTION.md` · **Ruled by** `harness/notes/CTO_RULINGS_01.md`
**Subject** `$HFS/houdini/help/nodes.zip` — 5,034 pages, version-pinned to 22.0.368

---

## 0 · The gap, and why it is not a capability gap

`docs/H22_FRONTIER.md`, measured: **Houdini 22's what's-new names 161 new Copernicus nodes. SYNAPSE grounds 3.**

There is no incumbent assistant to leapfrog — 22.0.368 registers no LLM, agent or MCP surface, proven by probe. So the frontier is the distance between what H22 shipped and what an assistant understands about it.

**That distance is gated on reading a 6 MB file that ships with the product.** Not on new capability.

---

## 1 · The design constraint: be wrong loudly, not plausibly

Written as if SideFX owned the outcome, because they effectively do — a confidently wrong answer about Houdini damages Houdini more than a refusal does.

Three consequences, and each one costs coverage on purpose:

**Provenance is per-entry, never per-corpus.** `VERIFIED-DOC` at 22.0.368, and never summed with probe-derived grounding into a single number. R119: an accurate H21 label is more useful than a confident H22 one, and this repository nearly destroyed 108 accurate labels believing otherwise.

**A stub is not knowledge.** An entry that clears a stated floor is ingested. One that does not is recorded as *known-thin*, not padded. **The gap between "has a page" and "is grounded" is the number that matters** — H9 measured 83% type coverage against 37.9% parameter coverage on the same surface.

**Deprecation travels with the entry.** R72: deprecation is the union of runtime `deprecationInfo()` and authored help, and they disagree. `karmarenderproperties` carries 56,325 characters of documentation that never mentions it is deprecated, while SYNAPSE emits it 123 times. An ingest without that axis teaches decaying nodes as current.

---

## 2 · Why a scout comes first

"5,034 pages" is a page count, not a knowledge count. An extractor written against an assumed structure produces a corpus that looks complete and joins to nothing.

The evidence that this is a real risk is already measured:

- **385 documented parameter ids are WRONG as names** while their labels resolve (H9-F1). Label is the join key; id is evidence.
- **Cop2 pages carry an explicit `#id:` on 7.7% of parameter records** — 13 of 139 pages have even one (H9-F3).
- **An `:include:` banner made a whole deprecated subsystem read as current** because H5's reader did not follow it (H7-F4).

`I0` measures the archive. `I1` builds against what `I0` found.

---

## 3 · Miles

```
I0  scout    READ-ONLY. What is IN those pages: structure, join keys,
             relationships, coverage of the 161, and the quality floor.
I1  execute  Build the extractor and the corpus against I0's findings.
             Nothing wires into RAG.
```

**`I1` is gated on `I0`.** Not for ceremony: the extractor's join key is the scout's finding, and getting it wrong produces a corpus that silently fails to match.

---

## 4 · Standing rules

- **Nothing wires into the RAG corpus in this harness.** U.6 found 15 phantom `createNode` sites already living there, outside the emission gate, re-teaching phantoms through `knowledge_lookup`. Adding thousands of doc-derived entries to that surface without a gate is the same mistake at scale.
- **Every number carries a producer path** (Law 2). Every reader is calibrated before it is trusted (R60).
- Commit product before the receipt (R93). Declare `touches` (R92). Read committed paths, never worktree globs (R127).
- Never push, never merge, never tag.
