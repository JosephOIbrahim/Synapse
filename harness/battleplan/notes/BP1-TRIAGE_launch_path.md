# BP1-TRIAGE — GUI launch-path inspection (target 3)

**Question.** Where is `PXR_PLUGINPATH_NAME` injected for a Houdini GUI session,
and is the OneDrive prefs known-folder redirect honored? Every claim below
carries a `file:line`.

**Verdict.** The redirect is **honored where the demo runs (the GUI)** and
**NOT honored by hython** (the agent lane / CI / the hytest shim). That single
divergence is why the hython half reads env-absent (G1 fail, G2 fail, G3/G4
UNKNOWN) and named **bucket = env**. It is a headless-tooling launch-path
defect, not a production (GUI) recall bug.

---

## 1 · Where `PXR_PLUGINPATH_NAME` is injected — package env ONLY

There is **no** `456.py` / `123.py` / `pythonrc.py` / startup-script injection.
Registration is process-global and must be set **before** USD's plugin registry
first loads, so it lives in the Houdini **package `env` block**, never at
runtime (`packages/synapse.json:22-23` comment; `scripts/install_synapse_package.py:75-77` comment).

| Site | file:line | Sets |
|---|---|---|
| Tracked package descriptor | `packages/synapse.json:22-25` | `PXR_PLUGINPATH_NAME = $MONETA_SRC/../schema` |
| — its `MONETA_SRC` | `packages/synapse.json:18-20` | `$SYNAPSE_ROOT/../Moneta/src` |
| — its `SYNAPSE_ROOT` | `packages/synapse.json:8-10` | `$HOUDINI_PACKAGE_PATH/..` (= `<repo>`) |
| Install resolver (`build_package`) | `scripts/install_synapse_package.py:73-77` | appends `PXR_PLUGINPATH_NAME = moneta_schema_for(repo)` |
| — schema resolver (gated on plugInfo.json) | `scripts/install_synapse_package.py:43-48` | `<repo>/../Moneta/schema` iff `plugInfo.json` present |
| **Deployed (live) copy** | `C:/Users/User/OneDrive/Documents/houdini22.0/packages/synapse.json:23-25` | `PXR_PLUGINPATH_NAME = C:/Users/User/Moneta/schema` (absolute, resolved) |

The schema dir the injection points at is **verified present**:
`C:/Users/User/Moneta/schema/{plugInfo.json, generatedSchema.usda, MonetaSchema.usda}`.
`plugInfo.json:20` declares `"Name": "moneta"` (the literal `.name` G2 matches);
schemaIdentifier `MonetaMemory`, `concreteTyped`, bases `[UsdTyped]`.

---

## 2 · The OneDrive redirect

### Install side — HONORED (`file:line`)

`scripts/install_synapse_package.py:candidate_pref_dirs()` (92-121):

- line **105**: globs `home/"OneDrive"/"Documents"` for `houdini2*`.
- lines **106-108**: also globs `$OneDrive/Documents`.
- lines **96-99** docstring names the exact trap: *"H22's pref dir is
  `~/OneDrive/Documents/houdini22.0` when Documents is redirected to OneDrive
  … which the plain `~/Documents` glob would miss — bare auto-detect then
  silently installs into a stale non-OneDrive dir H22 never scans."*

So the installer **does** target the OneDrive prefs dir. There is even a
dedicated doctor check for the downstream registration:
`check_schema_env()` (`scripts/install_synapse_package.py:462-507`) FAILs a
wired pref dir whose `synapse.json` omits `PXR_PLUGINPATH_NAME` or points it at
a dir without `plugInfo.json` — the exact 2026-08-09 drift.

### GUI runtime — HONORED (evidence)

The live GUI prefs are in OneDrive: `houdini.pref`, `font.cache`, `package.pref`
under `C:/Users/User/OneDrive/Documents/houdini22.0/` were freshly written
2026-08-22, and `synapse.json` **is present** in that `packages/` dir. So the
GUI resolves Documents→OneDrive, loads the package, and sets
`PXR_PLUGINPATH_NAME` in the GUI session.

### hython runtime — NOT HONORED (the defect) — VERIFIED-RUNTIME

This probe + its preview (hython 22.0.400 and the shim's 22.0.417) both observe:

- `hou.homeHoudiniDirectory()` = `HOUDINI_USER_PREF_DIR` = **`C:/Users/User/houdini22.0`** (classic), NOT the OneDrive dir.
- The classic `C:/Users/User/houdini22.0/packages/` holds **no `synapse.json`** (only `cop_ibex.*.hdalc`).
- Therefore hython never loads the synapse package → `PXR_PLUGINPATH_NAME`,
  `MONETA_SRC`, `PYTHONPATH`, `SYNAPSE_MEMORY_BACKEND` all **unset** →
  G1 fail, G2 fail (no `moneta` plugin, 68 plugins total), `import moneta`
  fails → G3/G4 UNAVAILABLE → **UNKNOWN**.

Anchor: `harness/battleplan/runs/2026-08-31/silent_recall_hython.json`
(row `G1 ENV`.observed.homeHoudiniDirectory).

### Why the classic dir is bare

`candidate_pref_dirs():111` globs `home.glob("houdini2*")`, and
`C:/Users/User/houdini22.0` **exists** — so a full `install_synapse_package.py`
run (no `--pref-dir`) *would* write `synapse.json` there too (the deploy loop
writes to every candidate, `:574-577`). Its absence means the last install ran
with `--pref-dir` (OneDrive only) or with `HOUDINI_USER_PREF_DIR` set (`:101-103`
makes that the sole target). The classic dir is thus a **discovered-but-unwired**
pref candidate — invisible to hython, which resolves exactly it.

---

## 3 · Remediation (env/plugin = launch-path, not code)

For BP1-HONESTY's `LAUNCH_PATH_FIX.md` / Joe's hands. Pick one:

1. **Headless/CI/shim (cleanest):** before launching hython, set
   `HOUDINI_PACKAGE_DIR=<repo>/packages`. Loads the tracked package regardless
   of prefs dir (install-script docstring `:15-17`). This is the fix that makes
   the shim/agent-lane gates see the package.
2. **Wire the classic dir too:** run `python scripts/install_synapse_package.py`
   with **no** `--pref-dir`; it globs both OneDrive (`:105`) and classic
   (`:111`) and writes both. Verify it hits `C:/Users/User/houdini22.0`.
3. **Point hython at OneDrive prefs:** set
   `HOUDINI_USER_PREF_DIR=C:/Users/User/OneDrive/Documents/houdini22.0` for
   headless runs (`:101-103` makes it win).

Verify any of the above with the read-only doctor:
`python scripts/install_synapse_package.py --verify` (`:525-544`), whose
`check_schema_env` (`:462-507`) is the pin for `PXR_PLUGINPATH_NAME` registration.

> Note on scope: the GUI half is `gui_required` (Joe's hands). Until it runs,
> whether the GUI genuinely passes G1/G2 (and what its own first-fail bucket is)
> is **UNKNOWN**. This inspection establishes only that the injection wiring
> exists and points at a real schema dir, and that the divergence is a
> hython-vs-GUI prefs-dir mismatch.
