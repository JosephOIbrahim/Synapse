# parity_seat — prove the SYNAPSE panel "seat" resolves 1:1 to the repo

**Leg:** W5-SEAT (wave5/seat) · panel parity 2/2. Disjoint from **W5-PARITY**
(`parity_modules/`, which proves the modules are byte-equal). This leg proves the
**load path**: the package loads, resources resolve from the repo, and nothing
shadows it.

## What it proves (first-hand, under live hython)

- **T1 package + hpath** — the synapse Houdini package actually loaded:
  `hou.houdiniPath()` contains `<repo>/houdini` **and** `SYNAPSE_ROOT` == the repo.
- **T2 resources** — `toolbar/synapse.shelf` + all **7** `config/Icons/SYNAPSE_*.png`
  (incl. `SYNAPSE_synapse.png`) resolve via `hou.findFile` to paths inside the repo.
- **T3 shadow sweep** — every `synapse`-named entry on `sys.path` + site-packages +
  `importlib.metadata` is enumerated; repo/python is the first **importable**
  provider; **zero shadows** is a counted claim.
- **T4 multi-build** — installed Houdini builds are listed; every 22.x maps to the
  one `houdini22.0` prefs dir. Which build the GUI launched stays **UNKNOWN**
  unless a prefs/log artifact proves it.
- **T5 pypanel flush** — the live-loaded `synapse_panel.pypanel` (resolved via
  `hou.findFile`) carries the `sys.modules` flush block, with no shadow copy on
  HOUDINI_PATH.

## Run it (the seat recipe)

```bash
env -u SYNAPSE_ROOT -u HOUDINI_PACKAGE_DIR \
    HOUDINI_USER_PREF_DIR="C:/Users/User/OneDrive/Documents/houdini22.0" \
    "C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe" \
    harness/probes/parity_seat/probe_seat.py \
    --expect-root "C:/Users/User/SYNAPSE" \
    --out harness/probes/parity_seat/results.json
```

`SYNAPSE_ROOT` and `HOUDINI_PACKAGE_DIR` are **unset on purpose** so the package
can only load through the prefs-dir scan — the exact mechanism the GUI seat uses.
Exit **0** = all acceptance predicates + T5 pass. Exit **2** = something failed
or `hou` was unavailable (recorded, never faked).

## Files

- `probe_seat.py` — the probe (pure introspection; no scene mutation).
- `results.json` — structured verdict from the last run.
- `hython_stdout.txt` — the raw hython stdout receipt (the `hou.findFile` lines).

## Known findings (recorded, not shadows)

- Multi-build: 5 installed 22.0.x builds share one `houdini22.0` prefs dir →
  which build the GUI launched is **UNKNOWN** (the honest gap Joe closes at his seat).
- Two repo-own `dist-info` (`synapse` 5.2.0, `synapse-houdini` 5.8.0) live inside
  `repo/python` — repo's own editable metadata, **not** a shadow; stale, worth a prune.
- Two stale non-json sidecars in the seat packages dir
  (`synapse.json.bak-115750`, `synapse.json.bom-bak`) — Houdini never scans them.
- Two lower-index `synapse/` **namespace** dirs (no `__init__.py`) on `sys.path`
  (worktree + repo root) — non-importable, so the repo/python regular package wins
  the import; not shadows.
