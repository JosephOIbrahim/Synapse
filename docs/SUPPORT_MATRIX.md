# SUPPORT MATRIX · SYNAPSE

Support claims name exact tested builds (W9 acceptance). Rows are dated
receipts; the newest row is the live claim. Unmeasured renders as *pending*,
never as a pass.

| Build | Symbol table | E2E | Node-type assay | Punycode | Dated |
|---|---|---|---|---|---|
| H22.0.400 | 35,908 · stamped · gate armed (verified-runtime, hython) | **pending** | open — 2 missing types (`instancer`, `layout` → `test_setdressing_recipe.py`) + 266 parm deltas (predominantly `apex::autorigbuilder`; rigging domain, refused without re-litigation) | 27 match / 0 changed / 0 vanished / **99 new, adoption pending** (lockstep rule) | 2026-08-09 |
| H22.0.368 | 35,903 · superseded | verified | — | 27 match | 2026-08-06 |
| H21.0.671 | 33,255 (`h21_symbol_table.json`) · H21 authority, untouched | verified | baseline catalog | — | — |

Probe of record: `.claude/probe_delta.json` (`h22_probe_delta/v1`) — 268
unpatched drift items, all inside the deferred node-type assay; counted by
`harness/verify/checks.py::check_probe_clean` (red until the assay lands —
declared here rather than silently absorbed).

## A4 pin census — 2026-08-09 (scope-declared)

Scope: `python/synapse/` · `fixtures/` (1 file, 0 matches) · `docs/`.
Counts: `22.0.368` ×469 · `22.0.397` ×35 · `22.0.382` ×7
(adoption baseline 422 / 18 / 2 — growth is the documents written *about*
the pins, counted honestly rather than excluded).

Classification: **live claims moved to 22.0.400** — `README.md:9` banner,
`CLAUDE.md:3` target, and the README e2e line amended to declare pending
rather than imply re-verification. **Everything else is dated historical
receipts, retained** per A4: review / adjudication / ticket documents,
provenance stamps in knowledge data (`lop_solaris_knowledge_22.json`),
probe-truth annotations in code (`handlers_cops.py`), and illustrative
constants (`scene_memory.py:243`, `canonical.py:96`, `scout.py:470`).
Zeroing provenance is prohibited.
Test-side: `tests/solaris/test_live_wiring.py::PINNED_BUILD` stays `22.0.368` —
its expected-red set was observed on that build; re-pinning requires the live
tier re-run inside 22.0.400 (part of e2e pending), never a string swap.

Re-stamp ritual: run `hython host/introspect_runtime.py` inside the target
build → commit the table → scout's stamp check does the rest
(`python/synapse/panel/gate_stamp.py`). Pin of record: `harness/state/drop.json`
(human file-write, single-writer).


## `lastCookTime()` cook-time contract — 2026-08-09 (observed, both contexts)

`hou.OpNode.lastCookTime()` on 22.0.400, live-assayed same day from both sides:

- **GUI session** (`hou.isUIAvailable()` true): returns **milliseconds**, wall-clock-accurate
  to ~0.2%. Receipt: `harness/notes/cache_h22_gui_assay_22.0.400.json`
  (wall 0.1714 s → raw 171.14; wall 0.1473 s → raw 147.17; run via `houdini -waitforui`).
- **Headless hython**: returns **0.0 unconditionally** for real cooks — perfMon on or off
  (wall 67–96 ms while `cookCount` increments normally). Receipt:
  `harness/notes/cache_h22_contract_assay_22.0.400.json` item 3, held as a **declared
  delta**: the assay expects 0.0 headless and fails loudly only if that behavior changes.

Probe consequence (R-CACHE-1 / M3b): `host/cache_host_probe.py` converts ms→s exactly
once, and classifies any non-positive reading that carries cook evidence as **UNKNOWN**
with provenance `lastCookTime_unreported` — never a fabricated zero. Farm, test, and
hbatch contexts therefore report UNKNOWN cook time by design; in-session GUI use is the
verified measurement path.


## Wave-3 memory-substrate contracts — 2026-08-13 (observed scope; durability-gated)

Wave 3 ("Moneta materialization", blueprint `docs/SYNAPSE-memory-blueprint.md` §4
phases 0–6) established four observed contracts on the memory substrate. **Scope
discipline (blueprint P5 *Honest* / S6 "doctor is the source of truth"):** each row
reports what was observed *at the layer named*, never store-level production health.

The live seat is **not** moneta-backed yet: on 2026-08-13 `synapse_doctor` reports
`moneta_substrate=fail` with an honest jsonl fallback (`requested=moneta, served=jsonl,
reason="embedding dim mismatch: expected 384, got 256"`, 473-entry real corpus,
`evolution=charmander`); downstream `moneta_consolidation`/`vector_recall`/`use_real_usd`
are **skipped, not faked-ok** (first-party `synapse_doctor` re-probe 2026-08-13:
`fail=1, ok=8, skipped=4`). All four contracts below cite a **committed** receipt — their
legs committed at 16:47 on 2026-08-13 — and each reports observed scope only; none asserts
`moneta_substrate=ok`. Nothing is **merged**, so the live seat still runs base code (fail)
and the wave is not yet live-doctor-confirmed. Whole-wave adjudication: W3-CRUX (`BLOCKED`
— the CRUX gate receipt is itself uncommitted and nothing is merged; builder-leg substance
sound). Full provenance and commit state: `harness/notes/W3_RECEIPTS_INDEX.md`.

### Committed-receipt contracts (observed scope only)

- **Dim authority** — blueprint Phase 0 (harden the honest signal). `from_storage_dir`
  resolves the embedding dim **once** from the active embedder
  (`python/synapse/memory/moneta_store.py:266` `_resolve_embedding_dim`); a stale-dim
  persisted snapshot is re-embedded from its **source payloads** before Moneta hydrates
  (`_reconcile_snapshot_dim`), so a provider change rebuilds the *derived* vectors instead
  of aborting into fallback. Both construction paths feed `embedding_dim=dim`
  (`:275`, `:305`). **Observed scope:** the leg-owned dim contract **passes** — 13/13
  `tests/test_w3_dim_contract.py`, both `[384→256]` and `[256→384]`; a forced init failure
  still records `served=jsonl/requested=moneta` and the doctor never shows `in_use moneta`
  (negative control). The live-seat `moneta_substrate=ok` conjunct is recorded **UNKNOWN**
  (USD schema registration is a separate lane + observing the flip needs a server restart)
  — never a fabricated ok. Receipt: **`harness/notes/receipts/W3-DIM.json`** (committed,
  `wave3/dim @ 16cf1543`). Carried finding: the running seat is degraded by this bug
  *today*; merge + restart recovers the moneta backend.

The three contracts below committed at 16:47 on 2026-08-13; each cites its committed
receipt and is substantively proven in standalone tests (independently re-executed by
W3-CRUX). Each stays bounded to **adapter-level** scope — none claims `moneta_substrate=ok`
(that stays `fail`, DEAD BYTES) — per blueprint P5 and the matrix rule.

- **Dual-write** — Phase 1 guardrail *("never move pages until the cabinet is proven")*.
  `MonetaBackedStore.add` mirrors every deposit to a typed cortex (`cortex_root.usda`,
  `write(kind,id,payload)→/MonetaMemory/{kind}/{id}`) **and** a plain JSONL safety net,
  byte-for-byte (`loaded.to_json()==m.to_json()`), gated to `backend==moneta` so the
  shadow path never double-writes; no memory lands only in Moneta. **Observed at the
  store-adapter level** (write→`.usda`→query; add→`memory.jsonl`), *not* store-level
  health: `moneta_substrate` overall stays `fail` because `schema_registered=False`
  (DEAD BYTES — `PXR_PLUGINPATH_NAME` unset, separate lane). Anchor:
  `python/synapse/memory/moneta_store.py:550`. Receipt:
  **`harness/notes/receipts/W3-STORE.json`** (committed, `wave3/store @ e8b691de`).
- **Migration parity** — Phase 5 (no JSONL memory lost: count + field-fidelity). JSONL→Moneta
  copy-and-verify: hard backup gate (sha256, sources proven byte-untouched), id-preserving
  keep-both-never-overwrite exporter (idempotent, dim-pinned), disk-independent count parity
  + ≥5 field-by-field spot-checks. Count is measured on **memories** (the decrypting loader
  collapses an append-log to distinct current memories — R10 39 lines → 21 memories), with
  `source_jsonl_lines` reported alongside; "USD prim count" maps to Moneta `snapshot.json`
  ECS rows — a **literal typed-`.usda`-prim count is UNKNOWN today** (registration-gated),
  not reported as a pass. Real-data run receipted for stores R10/R8 (backup byte-verified,
  5/5 spot-checks). Anchor: `python/synapse/memory/migrate.py`. Receipt:
  **`harness/notes/receipts/W3-MIGRATE.json`** (committed, `wave3/migrate @ 0c87a835`).
- **Concurrency semantics** — Phase 6 (production hardening). **Observed, not asserted from
  docs:** an in-process 2nd open on one store URI raises `MonetaResourceLockedError`
  (single-owner); two USD sublayers compose into `cortex_root` and both prims survive a real
  `Stage.Traverse()`; two sessions serialized through the single-owner lock keep both
  deposits. **Carried data-loss risk:** the URI lock is *process-local* — two OS processes on
  one store dir both open and last-writer-wins on `snapshot.json`, silently CLOBBERING a
  deposit (observed live, survivors 1 of 2). Acceptable inside the single-user-localhost
  envelope; a cross-process owner lock is a held spawn (W3-STORE lane). Kill-mid-write reopen
  is **process-kill-durable** (atomic tmp→fsync→replace) but **not power-loss-durable** (no
  directory fsync). Anchor: `moneta/api.py:199`; `python/synapse/server/write_plane.py`
  (store-level `write_plane` truth). Receipt:
  **`harness/notes/receipts/W3-HARDEN.json`** (committed, `wave3/harden @ 1b8d1e80`).
