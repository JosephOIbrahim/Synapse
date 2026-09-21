# rag/quarantine/prose — H22 prose phantom-gate quarantine

Written by `rag/ingest/help_archive.py --build`. When a prose chunk carries a
`[Node:context/type]` cross-reference whose unqualified type is absent from the live node
catalogue (`rag/catalog/h<build>/`), the **chunk** is written here as one JSONL row per
scope file (`<scope>.jsonl`) instead of into the corpus — **never dropped, never filtered at
read time** (HARVEST_SPEC: "Quarantine is a place to fix from, not a filter").

**The rows are generated and are NOT committed.** Prose ships under the Houdini EULA, so the
same posture as `rag/corpus/h22_prose/` applies: build it from your own install to review it.
Each row is **metadata only** — `id`, `scope`, `page`, `title`, `chunk_index`, `failing_refs`,
`reason`, `content_sha`, `build`, `licence` — and carries **no prose body**, so even a
committed row would leak no EULA text. Only this README is tracked.

## Gate authority (reconciliation)

The mission brief and HARVEST_SPEC name `h22_symbol_table.json`, but that table is 36,472
dotted `hou.*` API symbols — node *type* names are not in it, so gating node names against it
would quarantine every real node and empty the corpus. The node-type authority is the live
catalogue `rag/catalog/h<build>/` (CLAUDE.md rulebook discipline). The gate resolves node
references (from the corpus's own `[Node:ctx/type]` markup, OP contexts; `apex` is a separate
graph-node surface and is exempt) against that catalogue. Measured quarantine on 22.0.400:
**106 chunks of 36,168 (~0.3%)** — reviewable, and it includes genuine SideFX doc typos
(e.g. `cop/pyro_sourcehape`) and pedagogical placeholders (`sop/mynamespace--myasset`).

To review the current run: `hython rag/ingest/help_archive.py --build`, then read
`rag/quarantine/prose/*.jsonl`.
