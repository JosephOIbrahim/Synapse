# BP2-STORE — store-truth notes (2026-09-01)

Branch `bp2/store`. Companion to `harness/notes/receipts/BP2-STORE.json`.
Runtime is truth; every claim below carries a `file:line`.

## 1. FU-1 (Memory.id) was already landed — this wave PINS it, it did not re-fix it

`Memory.__post_init__` already defaults `created_at` **before** `_generate_id()`
(`python/synapse/memory/models.py:141-149`), and the id hashes
`content:created_at:memory_type` (`:157-160`). Provenance: commit `3c4f07f9`
*"feat(memory): Moneta follow-ups — FU-1 (Memory.id) + FU-2 (…) (#16)"* — it is
on the branch base (master `7fc09482`). The model-level pins also already exist
(`tests/test_memory_models.py::test_defaulted_created_at_participates_in_id`,
`::test_explicit_created_at_participates_in_id`,
`::test_same_content_same_second_still_collides`).

Empirical re-confirmation (Python 3.14.2, Moneta importable this seat):
distinct ids at different `created_at`; same id at identical
content+type+created_at; format `mem_` + 12-hex (len 16); legacy `mem_*`
round-trips.

**`docs/MONETA_FOLLOWUPS.md` FU-1 is STALE** — it still lists FU-1 as a deferred
follow-up ("land before/with cutover"), but the fix shipped in #16. That doc is
outside STORE's `touches` (docs/ is not claimed), so it was not edited here.
FINDING → a doc-owning pass should mark FU-1 DONE (`3c4f07f9`). See receipt
`for_ruling`.

What this wave ADDED (the gaps #16 left):
- `tests/test_moneta_crucible.py:244` `test_repeat_deposits_distinct_ids_count_equals_all_divergence_gone`
  — the brief's MonetaBackedStore test: two identical-content deposits at
  different `created_at` → distinct ids → `count() == len(all()) == 2`; jsonl now
  also holds 2 (the dict-overwrite-vs-append gap that WAS the FU-1 divergence is
  gone).
- `tests/test_store_backend_health.py:150` `test_identical_content_type_created_at_dedups_in_jsonl`
  — the "keep a test that identical content+type+created_at still dedups"
  clause: jsonl overwrite → `count() == 1`.
- `tests/test_memory_models.py:52` `test_legacy_mem_id_round_trips_and_format_unchanged`
  — pins "a legacy mem_* id still round-trips" + format unchanged.

## 2. T2/T3 — honest backend health, in STORE territory

New in-territory accessor: `python/synapse/memory/store.py:818`
`backend_health(store=None)` (helper `_classify_backend` `:802`; declared
vocabulary `_BACKEND_STATUS` `:799`). It is the operator-facing twin of the
existing `backend_fallback()` (`:771`): a non-mutating dict carrying the five W1
operator-acceptance fields **and** a `status` in the ratified vocabulary.

- Five fields: `requested_backend`, `active_backend`, `embedder_id`,
  `embedding_dim`, `row_count` (T3). embedder/dim are honest `None` on jsonl.
- Status: `SUCCESS` when the served backend satisfies the request; `UNAVAILABLE`
  when a requested substrate is absent (Moneta not importable → jsonl fallback);
  `BLOCKED` when present-but-broke (init failed). A `moneta`/`shadow` request
  served by jsonl is **never** `SUCCESS` — the M-5 anti-masquerade rule.
- OBSERVER, not an authority: never constructs a store; adds no
  `memory_handle_census()` key. Authorities stay exactly two
  (`store.py:1692` `get_synapse_memory`, `ledger.py:398` `ledger_moneta_store`).
- Vocabulary conformance to the ratified `loop/ports.py:28` `STATUS` is pinned by
  `tests/test_store_backend_health.py::test_backend_health_status_in_ratified_vocabulary`
  — with **no** memory→loop import (literals + a test, not a coupling).

### Reconciliation: "sec.4 tool surface byte-identical" vs "report BLOCKED/UNAVAILABLE"

The five sec.4 memory tools (`add_memory`, `recall`, `memory_query`,
`memory_write`, `memory_status`) are left **byte-identical** (git diff of
`handlers_memory.py`, `handlers.py`, `tracker.py`, `_tool_registry.py`,
`scene_memory.py`, `write_plane.py` = empty). So the honest
BLOCKED/UNAVAILABLE verdict is surfaced via `backend_health()` (memory layer)
and by the EXISTING honest server row, not by mutating any tool response shape.

The anti-masquerade property is **already true** at the `synapse_health` surface:
`write_plane.store_health()` reports `status="degraded"` +
`requested_backend="moneta"` + `serving_jsonl=True` when moneta is requested but
a jsonl store serves (`python/synapse/server/write_plane.py:350-358,390`).
Pinned live by `tests/test_store_backend_health.py:87`
`test_health_row_does_not_masquerade_jsonl_as_moneta`.

## 3. DRAFT (HELD — server/ is outside STORE territory)

Two residual gaps live in `python/synapse/server/` (not in STORE's `touches`;
changing `write_plane`'s own `ok/degraded/unknown` vocabulary would ripple into
`doctor`, the panel strip, and `test_w3_harden_write_plane_store.py`). Drafted
here, applied by a server-owning pass:

1. **Operator health ROW lacks embedder id + dim.** `write_plane.store_health()`
   carries requested/active/count but not embedder/dim. Wire it to call
   `synapse.memory.store.backend_health(store)` and merge `embedder_id` /
   `embedding_dim` into `info` — additive keys only.
2. **The row's word is `degraded`, not the ratified `UNAVAILABLE`/`BLOCKED`.**
   Rather than renaming write_plane's status (breaks its consumers), attach
   `backend_health()`'s dict under a new `info["backend_health"]` key so the
   ratified verdict rides alongside without disturbing the existing field.

Both are ~2-line additive merges once `backend_health()` (this wave) exists.
Proposed as a `spawn` in the receipt; class is a server build (outside STORE's
`spawn_classes=["probe"]`), so it lands **held** for Joe.
