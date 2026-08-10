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
