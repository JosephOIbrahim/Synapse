# Houdini Upgrade Runbook

**Current release: [SYNAPSE 5.97.5](../releases/v5.97.5.md), measured on
Windows Houdini 22.0.400 / Python 3.13.** Updating SYNAPSE and upgrading Houdini
are separate actions. This contributor runbook does not qualify another Houdini
build. For ordinary installation, use the [user instructions](../../INSTRUCTIONS.md).

**A Houdini build change can disarm the phantom-API gate.** The symbol
table is build-stamped; the moment `hou.applicationVersionString()` differs
from the table stamp the corpus/table reads stale — precisely the week API
drift peaks. The default `refuse` policy is **fail-closed**: `synapse_scout`
raises rather than serve unverified verdicts. (Opt into graceful degradation
with `SYNAPSE_SCOUT_DRIFT_POLICY=warn`, under which every membership verdict
degrades to `null` / `gate_armed: false` and a warning instead.) This is the
per-upgrade checklist. Conformance-pinned by
`tests/test_m3_upgrade_surface.py`.

## When to run this

Any Houdini build change — **point releases included** (the stamp is the
full version string: `21.0.631` ≠ `21.0.671`). Three things break
otherwise:

1. **Scout refuses** — by default (`SYNAPSE_SCOUT_DRIFT_POLICY=refuse`)
   `synapse_scout` raises on the stale table; under `warn` it instead
   degrades — the panel footer shows *"API gate stale"* and every
   `exists_in_runtime` is `null` with an `unverified_reason`.
2. **Panel absent** in the new build's pref dir (the package was never
   installed there).
3. **Vendor ABI cliff** if the new build changed Houdini's Python version.

## Step 1 — Regenerate the symbol table

The generator is `host/introspect_runtime.py`. From the repo root:

```powershell
& "C:\Program Files\Side Effects Software\Houdini <NEW_BUILD>\bin\hython.exe" host\introspect_runtime.py
```

Success looks like `TABLE: version=<NEW_BUILD> symbols=~33000
truncated=False` plus five `check ... True` lines. The output overwrites
the matching major's committed authority under
`python/synapse/cognitive/tools/data/` (`h22_symbol_table.json` for H22).
Review and commit that generated table as part of the separately authorized upgrade.
Regeneration is **per-build mandatory**.

Drift policy: the default is `SYNAPSE_SCOUT_DRIFT_POLICY=refuse` (fail-closed)
— scout raises on a stale corpus/table instead of degrading to null verdicts.
Set `SYNAPSE_SCOUT_DRIFT_POLICY=warn` to opt into graceful degradation (serve
hits + null verdicts with a warning) during a controlled upgrade.

> **Per-major tables:** the regen inside an H22 build writes
> `h22_symbol_table.json` ALONGSIDE the committed H21 file (never overwrites
> it), and scout auto-selects the table matching the running major —
> dual-build support is free. (Doctor's artifact check follows the same
> per-major rule.)

## Step 2 — Verify the vendored-dependency ABI

```powershell
& "...\bin\hython.exe" -c "import sys; print(sys.version_info[:2])"
```

- `(3, 11)` or `(3, 13)` on Windows x64: matching native SDK files are already
  bundled. Confirm the actual imports in the new Houdini build; a matching ABI
  alone does not qualify the build.
- Another ABI or platform: inspect
  [the vendor inventory](../../python/synapse/_vendor/README.md) and arrange a
  separately reviewed dependency refresh. Do not widen a gate without matching binaries.

Either way, verify: `python -m pytest tests/test_vendored_deps.py -v`.

### Step 2a - Changing bundled dependencies

The native SDK dependencies `pydantic_core` and `jiter` have CPython-specific
Windows binaries for 3.11 and 3.13. This is separate from the optional Moneta Rust
wheel: published 5.97.5 Setup does not bundle that wheel or enable native mode.

For an approved new ABI, pin exact dependency versions and artifact hashes,
include required notices, update the activation logic/tests together, and verify
imports in a fresh target Houdini process. Stock-Python tests are an additional
check, not a substitute for that execution. See the
[vendor instructions](../../python/synapse/_vendor/README.md) and
[installer build inputs](../../installer/README.md).

## Step 3 — Re-run the package installer

For a Setup-managed installation, use a reviewed Setup and choose the new
build's actual preference folder. Do not run the source scripts over its owned
registration. The steps below apply to source installations only.

The new build's pref dir **does not exist until first launch**, and
auto-detect **silently skips** missing dirs. Either:

- (a) Launch the new Houdini once, quit, run
  `python scripts/install_synapse_package.py`, relaunch; **or**
- (b) Skip the first launch:
  `python scripts/install_synapse_package.py --pref-dir "C:/Users/<you>/Documents/houdini<MAJOR.MINOR>"`
  (the installer creates `packages/` itself).

Facts worth knowing:

- Auto-detect writes into **every** existing `houdini2*` pref dir.
- `synapse.json` bakes **absolute repo paths per seat** — moving the repo
  also requires a re-run.
- Old-version pref dirs keep a working `synapse.json` (harmless; delete it
  to uninstall).
- Source installation uses **both** `scripts/install_synapse_package.py` for
  package registration and root `install.py` for the panel, shelf and icons.
  Give both the same explicit preference folder; see
  [source installation](../getting-started/installation.md#source-installation).
- The run writes `~/.synapse/install_stamp.json` (read by
  `synapse_doctor`).

## Step 4 — Confirm fonts and corpus

- **Fonts** are bundled in-repo (`panel/designsystem/fonts/`, loaded via
  QFontDatabase at panel init) — no install step. Wrong-looking type →
  check the Houdini console log for a fontload `build_mismatch`.
- **Corpus** is build-independent (digest-keyed to the repo `rag/` tree,
  auto-materialized at `<repo>/.synapse/scout_corpus`).

Final confirmation is one `synapse_scout` call (e.g. query
`hou.LopNode`): expect `gate_armed: true`, `stale: false`,
`table.houdini_version == <NEW_BUILD>`, `exists_in_runtime: true` — and
the panel footer shows no *"API gate stale"* warning.

## Checklist

For installation diagnostics, click **Doctor** beside **Connect / Bridge**
at the top of the SYNAPSE panel. The **Check SYNAPSE** window runs
`synapse_doctor` directly with `bundle: false`, without a model request or
scene changes. It distinguishes passed, failed, and unrun checks. Use
**Run again** to refresh or **Copy report** to copy the displayed findings.

| # | Step | Command | Pass signal |
|---|------|---------|-------------|
| 1 | Regen symbol table | `hython host\introspect_runtime.py` | `TABLE: version=<NEW_BUILD> ... truncated=False`; commit the JSON |
| 2 | Verify vendor ABI | `hython -c "import sys; print(sys.version_info[:2])"` | Bundled ABI plus successful imports in the actual new build |
| 3 | Install for the new prefs | Reviewed Setup, or both source scripts with the same prefs | Correct registration, UI assets and diagnostic stamp |
| 4 | Confirm gate | `synapse_scout` query `hou.LopNode` | `gate_armed: true`, footer clean |
