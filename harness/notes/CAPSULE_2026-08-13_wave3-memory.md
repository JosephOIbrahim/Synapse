# CAPSULE 2026-08-13 — wave 3 memory ("Moneta materialization")

**Wave:** SYNAPSE memory substrate, blueprint `docs/SYNAPSE-memory-blueprint.md`
§4 phases 0–6 · S5 acceptance · S6 guardrails.
**Position at close:** paper leg (W3-PAPER) closing the wave's paper trail. The wave
is **substance-sound but durability-BLOCKED** — not done. Merge is Joe's word, per act.

## Position (where the wave actually is)

The seven builder legs all delivered green-with-findings work that W3-CRUX independently
re-executed (136 leg tests re-run from inside each worktree, all pass on Python 3.14.2,
standalone scope). **All 7 builder legs are committed** — DIM (`16cf1543`), VEC
(`6600295b`), STORE (`e8b691de`), KIND (`a82492a3`), EVOLVE (`c2bedf31`), MIGRATE
(`0c87a835`), HARDEN (`1b8d1e80`) — each with its receipt committed in-tree (the last five
landed at 16:47 on 2026-08-13). The **only** uncommitted leg is the **CRUX gate**
(`wave3/crux @ 5e933c13`, `W3-CRUX.json` untracked). Nothing is **merged** — so the live
seat still runs base code.

The live seat is **base code** (nothing merged): `synapse_doctor` on 2026-08-13 reports
`moneta_substrate=fail`, honest jsonl fallback (`requested=moneta, served=jsonl,
reason="embedding dim mismatch: expected 384, got 256"`), 473-entry real corpus,
`evolution=charmander`; downstream moneta checks **skipped, not faked-ok**. Per blueprint
S9/S6 "doctor is the source of truth", the wave is **not done on the live seat** until at
least W3-DIM merges and the server restarts.

**Whole-wave verdict (W3-CRUX):** `BLOCKED` — solely on durability. A green crux receipt
is a precondition for merge, not a permission; that receipt is not green.

## What landed (honest commit state)

| Leg | Contract | Committed | State |
|---|---|---|---|
| W3-DIM | dim authority (Phase 0) | ✅ `16cf1543` | committed |
| W3-STORE | dual-write + cortex (Phase 1) | ✅ `e8b691de` | committed |
| W3-KIND | typed schema + kind routing (Phase 2) | ✅ `a82492a3` | committed |
| W3-VEC | derived vector recall (Phase 3) | ✅ `6600295b` | committed |
| W3-EVOLVE | consolidation dry-run/approve (Phase 4) | ✅ `c2bedf31` | committed |
| W3-MIGRATE | migration parity + cut-over (Phase 5) | ✅ `0c87a835` | committed |
| W3-HARDEN | crash/concurrency/write_plane (Phase 6) | ✅ `1b8d1e80` | committed |
| W3-CRUX | adversarial gate | ❌ base | uncommitted (receipt untracked) |

Full ledger + receipt locations: `harness/notes/W3_RECEIPTS_INDEX.md`.

## S5 acceptance readout (honest)

- **No JSONL memory lost in migration** — test-proven standalone + real-data (R10/R8:
  backup byte-verified, 5/5 spot-checks). Go-live human-gated. *Not yet live.*
- **doctor memory checks all `ok` or a clean true fallback, never unknown/skipped** —
  the fallback IS clean/true/honest today, but the live seat still `skips` downstream
  (moneta not in use). **Not green live** until merge + restart + schema registration.
- **recall/search off typed prims, filter by kind** — kind filter (KIND) + scored recall
  (VEC) exist at **module level**; tool wiring held; typed prims are DEAD BYTES until
  registration. *Partial.*
- **evolve dry-runs, applies on approval, prune audit** — proven standalone; real-Moneta
  apply raises `ConsolidationUnsupported` (deferred to a hardening pass). *Dry-run proven.*
- **Moneta OR JSONL fallback, doctor says which honestly** — **MET on the live seat today**
  (the fallback is loud and honest). The one box already green.
- **Every P1–P7 has a failing-if-violated test** — 136 leg tests, standalone scope. *Proven.*

## Findings (durable / carried)

1. **Live production seat is degraded by the dim bug right now** (W3-DIM). `moneta` falls
   back to jsonl (384≠256); merge + restart recovers it. Not hypothetical.
2. **Cross-process snapshot CLOBBER — carried data-loss risk** (W3-HARDEN F1). Moneta's URI
   lock is process-local (`moneta/api.py:199`); two OS processes on one store dir both open
   and last-writer-wins on `snapshot.json` (observed live, survivors 1 of 2). Acceptable
   inside single-user-localhost; a real risk for any multi-session use. Held spawn W3-LOCK.
3. **DEAD BYTES** (W3-STORE / W3-MIGRATE F4). `schema_in_use=True` but
   `schema_registered=False` (`PXR_PLUGINPATH_NAME` unset), so typed `.usda` authoring is
   schema-blind; a literal typed-prim count is UNKNOWN. Migration verified on the durable
   `snapshot.json` ECS rows, not on typed prims.
4. **Crash durability is process-kill only, not power-loss** (W3-HARDEN). Atomic
   tmp→fsync→replace, but no directory fsync. Must not be read as power-loss-durable.
5. **Consolidation merge-fidelity gap** (W3-EVOLVE / CRUX). `_union_into` fills only empty
   scalars; a differing non-empty scalar on an absorbed duplicate is dropped from the
   survivor. Recoverable via backup-before-mutation; bounded (exact-content-only prune).
6. **Vendor root cause, boundary respected** (W3-DIM). `Moneta.__init__` rebuilds its vector
   index from persisted vectors without validating against `config.embedding_dim`
   (`Moneta/src/moneta/api.py:229`) → bare `ValueError`. SYNAPSE-side reconcile pre-empts it;
   the true fix is a held moneta-side spawn (MONETA-DIM-HYDRATE, separate repo, no harness).
7. **Both wave failure-classes CLOSED** (W3-CRUX): silent-fallback-claiming-moneta (absent
   live); data-loss-in-migration/consolidation (in-scope closed; two carried risks named).
8. **Provenance note:** `docs/SYNAPSE-memory-blueprint.md` + `-engineering-spec.md` are
   committed on master (`7117a6de`) but absent from base `5e933c13`; legs executed against
   the self-contained brief-embedded targets. Consistent across STORE/MIGRATE/DIM receipts.

## Ruling items (for Joe / INTEGRATOR — decisions, not yet made)

- **R-merge-order:** land DIM before/with STORE (both edit `moneta_store.py`; STORE is
  post-dim-check + new-names-only, rebase-compat verified). Pick **one** dual-write path —
  W3-STORE in-add vs W3-MIGRATE `WriteThroughStore` — to avoid a double write-through.
- **R-durable-location (P1):** move the Moneta/cortex/JSONL store off `$HOUDINI_TEMP_DIR`
  onto a durable address (a Temp cleanup/reboot wipes all three together). Changes where
  every seat's memory lives — a human call. Recorded by W3-STORE, no code change made.
- **R-schema-registration:** set `PXR_PLUGINPATH_NAME` (packages/synapse.json /
  `fix/moneta-schema-registration` lane) to move moneta_substrate DEAD BYTES → registered.
- **R-concurrency posture:** accept the single-user-localhost bound, or require a
  cross-process owner lock before any multi-session use (held spawn W3-LOCK, W3-STORE lane).
- **R-consolidation-fidelity:** tighten `_union_into` to full scalar-union before any
  real-corpus apply, or accept backup-recoverability.
- **R-held-spawns:** MONETA-DIM-HYDRATE (vendor); VEC tool wiring (`synapse_recall`→scored
  recall); MIGRATE backup→export structural chaining; KIND `tracker.py` scope-glob
  (ratify or move). All `held` for Joe — classes outside the legs' spawn_classes.

## L-tasks left for Joe (open, human-gated)

- **L1 — Commit the CRUX gate receipt.** The 7 builder legs committed their named files at
  16:47 on 2026-08-13; the only uncommitted leg is the **CRUX gate** — `W3-CRUX.json` is
  untracked on `wave3/crux @ 5e933c13`. Its owner `git commit`s that named file so the
  whole-wave adjudication has a durable home. (The builder-leg durability gap an early draft
  flagged is already closed — git re-derive on 2026-08-13 confirms all 7 committed.)
- **L2 — Merge (Joe's word).** Apply R-merge-order. Nothing pushed/merged/tagged by any leg.
- **L3 — GUI relaunch + live-doctor confirmation (S9).** After merge (≥ DIM), **restart the
  running SYNAPSE server / Houdini seat** and re-run `synapse_doctor`: confirm
  `moneta_substrate` no longer dim-fails — `write_plane` degraded→ok, moneta serves, count
  preserved, snapshot rebuilt to the live dim, no "embedding dim mismatch" in the init log.
  **This is UNKNOWN headless — it requires the live GUI relaunch** (backend_fallback is
  process-local, set at `_make_store` time). Probe: W3-DIM-POSTDEPLOY-DOCTOR.
- **L4 — USD schema registration.** `PXR_PLUGINPATH_NAME` (R-schema-registration) → typed
  substrate; the second half of a live `moneta_substrate=ok` after L3.
- **L5 — Durable store location.** Execute R-durable-location if adopting Moneta for real.
- **L6 — Migration go-live runbook** (W3-MIGRATE R1, reversible): backup (execute) → per-store
  export (in-place, idempotent, dim-pinned) → flip backend in packages/synapse.json.
  **Preconditions:** DIM merged (else jsonl fallback) AND STORE merged (or WriteThroughStore
  wired). Reversible via `SYNAPSE_MEMORY_BACKEND=jsonl`.
- **L7 — Decide the carried rulings** R-concurrency-posture, R-consolidation-fidelity,
  R-held-spawns.

## Provenance

Compiled by W3-PAPER on `wave3/paper` (docs + notes only; any code diff on this branch is a
BLOCK). Sources: the 8 sibling receipts (2 committed, 6 working-tree), the wave3 bus, and a
re-read of the blueprint S5/S6 anchor on master `7117a6de`. Receipt:
`harness/notes/receipts/W3-PAPER.json`.
