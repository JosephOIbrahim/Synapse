# Houdini Upgrade Runbook

**A Houdini build change silently disarms the phantom-API gate.** The
symbol table is build-stamped; under the default `warn` policy, every
`synapse_scout` membership verdict degrades to `null` (`gate_armed: false`)
the moment `hou.applicationVersionString()` differs from the table stamp —
precisely the week API drift peaks. This is the per-upgrade checklist.
Conformance-pinned by `tests/test_m3_upgrade_surface.py`.

## When to run this

Any Houdini build change — **point releases included** (the stamp is the
full version string: `21.0.631` ≠ `21.0.671`). Three things break
otherwise:

1. **Null scout verdicts** — the panel footer shows *"API gate stale"*,
   every `exists_in_runtime` is `null` with an `unverified_reason`.
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
the committed authority
`python/synapse/cognitive/tools/data/h21_symbol_table.json` — **commit
it** (expect a full-file ~1.1 MB diff per build; that is normal).
Regeneration is **per-build mandatory**.

Hard-gate option: `SYNAPSE_SCOUT_DRIFT_POLICY=refuse` makes scout raise on
a mismatch instead of degrading to null verdicts.

## Step 2 — Verify the vendored-dependency ABI

```powershell
& "...\bin\hython.exe" -c "import sys; print(sys.version_info[:2])"
```

- `(3, 11)` → nothing to do (the version gate covers H20.5/21.0/21.5).
- Anything else → follow `python/synapse/_vendor/README.md` ("Future
  cliff"): re-vendor via its refresh command, widen the version gate in
  `python/synapse/__init__.py`, update tests in lockstep.

Either way, verify: `python -m pytest tests/test_vendored_deps.py -v`.

## Step 3 — Re-run the package installer

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
- The legacy root `install.py` is retired — never run it.
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

| # | Step | Command | Pass signal |
|---|------|---------|-------------|
| 1 | Regen symbol table | `hython host\introspect_runtime.py` | `TABLE: version=<NEW_BUILD> ... truncated=False`; commit the JSON |
| 2 | Verify vendor ABI | `hython -c "import sys; print(sys.version_info[:2])"` | `(3, 11)` (else: `_vendor/README.md` cliff procedure) |
| 3 | Re-run installer | `python scripts/install_synapse_package.py` | `wrote: .../packages/synapse.json` + `stamp: ~/.synapse/install_stamp.json` |
| 4 | Confirm gate | `synapse_scout` query `hou.LopNode` | `gate_armed: true`, footer clean |
