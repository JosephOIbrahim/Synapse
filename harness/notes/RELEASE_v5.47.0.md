# v5.47.0 — The Memory Wave

The Moneta memory store goes real. Shipped through the AUTOREVISE harness as wave 3
(9 legs, crucible-gated, receipts in-tree), on top of the W1 store recovery and the
wave-2 latency work — everything since v5.46.0 in one lineage.

## Headline: memory is production-honest

- **The one root cause, closed** — the 384/256 embedding-dim mismatch that silently
  dropped the store to jsonl while claiming moneta. The vector index now takes its
  dim from the ACTIVE embedder; a persisted index that disagrees is treated as
  derived data and rebuilt from source payloads, loudly, with zero memory loss.
  The historical raise-on-mismatch behaviour is re-pinned in tests as fixed.
- **cortex_root.usda materialized** — typed MonetaMemory root, write/query as typed
  prims keyed (kind, id), with dual-write to JSONL armed as the permanent safety net.
- **Typed kinds** — note / context / reference / task / decision each carry their own
  schema; synapse_recall and synapse_search route on the typed prim, no full-store slurp.
- **Vector recall** — a derived, rebuildable index over the store; ranked neighbors
  with real scores. Delete-and-rebuild reproduces results (derived-data proof).
- **Consolidation with consent** — synapse_evolve_memory dry-runs a full prune audit
  (merges, prunes, before/after counts) and mutates nothing without an explicit
  approval token. Protected memories are structurally excluded from pruning.
- **Migration, copy-and-verify** — JSONL memories become typed prims with ids
  preserved, behind a hard backup gate; count parity + field-fidelity spot checks;
  keep-both-never-delete on collisions; write-through fallback stays armed post-flip.
- **Hardening** — crash-interrupted writes leave the root intact; two concurrent
  writers both survive (observed semantics receipted); write_plane now reports the
  STORE, not just the bridge.

## Also in this release

- **W1 memory-store recovery merged** — resolver guards against literal env-token
  path segments, canonical unsaved-scene base, WAL-poison-safe reopen, idempotent
  keep-both store consolidation, store_census probe kind in the autoresearch harness.
- **Wave-2 latency authority** — doctor fully off-main (marshalled hou closure),
  the 2s context tick off Houdini-main, format_synapse_message on the worker with
  prerendered HTML insert, a busy/stalled indicator fed by real _set_busy edges,
  and the freeze discriminator probe with conditional bridge-lookup cache.
- **Seam compositions, receipted** — W1 x W2-S1 in store.py (W1 path semantics under
  S1's _read_on_main marshal; 40 tests green) and the autoresearch probe-kind
  registry union (usd_schema_probe + store_census coexist). Resolvers committed
  under harness/autorevise/bus/_runs/.

## Integrity notes

- Crucible verdict on wave 3: substance CLEAR on all seven legs; the wave was
  blocked solely on durability (uncommitted worktree state, the standing wave-2
  lesson) and remedied with one named-file commit per leg before merge.
- Both standing failure classes re-attacked and CLOSED: silent-fallback-claiming-
  moneta, and data-loss in migration/consolidation. The live 473-memory corpus was
  never touched during review; leg tests were re-executed tmp-dir-isolated.
- Unobtainable renders UNKNOWN — never zero, never an estimate.
- Live-seat conformance: the running bridge still executes pre-merge code; the
  doctor SHOWS the memory section honest-green after the next Houdini relaunch
  and reinstall (RELEASE_CARD step 8).

## Held for ruling

- W3-LOCK — cross-process owner-lock hardening on from_storage_dir.
- MONETA-DIM-HYDRATE — vendor-side typed EmbeddingDimMismatchError / re-derive.

## Paper trail

harness/notes/receipts/ (W3-DIM..W3-PAPER, W3-CRUX), W3-MIGRATE evidence file,
wave3.live.json (base ruling receipted), and the session capsule.
