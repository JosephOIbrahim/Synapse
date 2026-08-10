# W2 — MonetaMemory schema registration · session capsule · 2026-08-09

**Branch:** `fix/moneta-schema-registration` (worktree `.claude/worktrees/w2-moneta-reg`, off master@0f98ef1b)
**Wave shape:** scout (read-only) → enumerated 4-act batch → single "go" → execute → receipts.

## What was wrong (observed chain, no link asserted)

1. `C:/Users/User/Moneta/schema/` — codeless USD plugin (plugInfo.json +
   generatedSchema.usda) declaring `MonetaMemory` — present and well-formed.
2. Tracked `packages/synapse.json` — sets `PXR_PLUGINPATH_NAME` at that dir — correct.
3. Nothing loaded it: `HOUDINI_PACKAGE_DIR` unset (User+Machine), no deployed
   copy in any pref dir, `houdini.env` stock.
4. `scripts/install_synapse_package.py::build_package()` drifted schema-blind:
   omitted `PXR_PLUGINPATH_NAME` and `SYNAPSE_MEMORY_BACKEND`. The blessed
   deploy path could not have fixed the seat.
5. Result: `MonetaBackedStore` `use_real_usd=True` init failed schema lookup →
   silent degrade to `MockUsdTarget` (moneta_store.py:283) → panel diagnostic.
   Same disease family as W1 fragmented stores: env truth not reaching the process.

## What changed

- **Installer parity** (`scripts/install_synapse_package.py`): `moneta_schema_for()`
  helper (observed plugInfo required, never asserted); Moneta trio authored inside
  the `if moneta:` block; new `schema env` verify row (PASS/FAIL/MANUAL-UNKNOWN
  postures per house rule).
- **Parity invariant** (`tests/test_install_package_parity.py`, 4 tests): resolver
  env-var NAME set == tracked package env-var NAME set; schema var requires a real
  plugInfo on disk; no-Moneta seats author none of the trio.
- **Autoresearch extension**: new `usd_schema_probe` kind (mission_schema + runner
  dispatch + `probes.probe_usd_schema`), deterministic, zero-model, pxr-only,
  UNKNOWN for unobservables. Mission `missions/w2_moneta_registration.json`.
- **Deploy** (workstation, INFORM gate): resolved package written to
  `C:/Users/User/OneDrive/Documents/houdini22.0/packages/synapse.json` — the pref
  dir the runtime itself reports. First deploy went to `C:/Users/User/houdini22.0`
  (wrong; H22 does not scan it — probe returned an honest all-false); that artifact
  was removed same session.

## Receipts

- `harness/autoresearch/runs/w2_moneta_registration_live/` — the honest FALSE run
  (wrong pref dir): pluginpath_set=false. Kept: it is the before-picture.
- `harness/autoresearch/runs/w2_moneta_registration_live2/` — the after: all four
  conditions true on 22.0.400 hython, roundtrip_typed=true, 0 failures.
- Mission `--validate-only` VALID; parity tests 4/4.

## Open at capsule close

- GUI observation pending: fresh Houdini launch → panel doctor line flips.
  Process-global registration cannot be confirmed from outside the GUI session (L-task).
- Crucible review of `usd_schema_probe` + mission (dispatched as W2 team leg).
- Push + merge: per-act human words, not in the batch.
- `use_real_usd=True` REVIEW gate (architecture doc §1.3) — the store already
  attempts it with loud fallback; with registration live the fallback should stop
  firing. Observe on next session before any further flip.

## Crucible verdict — post-review addendum (2026-08-09)

Verdict: **FINDINGS (16)** — 1 BLOCK · 8 SHOULD · 7 NOTE. Full text:
`harness/notes/W2_CRUCIBLE_VERDICT.md`.

**B1 (BLOCK) — closed before merge.** The receipt narrated store-level health
(`MonetaBackedStore ... has what it needs`) from a registration-only probe, and
mislabeled condition-3 facets as "the four moneta_runtime.py conditions" (there
are five, per R64). Fix applied: mission note truncated to observed scope,
receipt of record rebuilt to carry BOTH the negative control (pre-deploy
all-false run, verbatim) and the corrected pass, SUPPORT_MATRIX row reworded
("same process" not "fresh", no store claim) and repointed at the committed
receipt (also closes the receipt half of S9). Evidence regenerated live
(run `w2_moneta_registration_live3`, all facets true).

**Queued follow-ups (not in this merge — declared, not absorbed):**
- S1/S3: subprocess re-probe with scrubbed env (provenance: package vs shell)
  + genuinely fresh reopen. One change closes both.
- S2: `note_source: "mission"` marker in runner entries (model-text boundary).
- S4: except-guard the roundtrip block; bank partial observations as UNKNOWN.
- S5/S6/S7: `check_schema_env` build-targets arg; compare against the observed
  schema path (not any plugInfo); decouple PXR var from `src` presence.
- S8: parity test to (var, method) pairs + top-level keys + check_schema_env cases.
- N1–N7: unconditional roundtrip/IsConcrete, `method: append` on
  PXR_PLUGINPATH_NAME (both surfaces), plugInfo file-path entry shape,
  `unknowns` in DONE, mission_schema docstring, plugin_path UNKNOWN shape.
- B1 second half (recommended next probe): `moneta_provenance_probe` kind
  reading `moneta_runtime.schema_in_use()` / `moneta_provenance()` verbatim —
  the probe R64 actually ruled for; natural W1-merge companion.
