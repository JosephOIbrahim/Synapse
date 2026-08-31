# LAUNCH_PATH_FIX — the `env` bucket, for Joe's hands

**Leg:** BP1-HONESTY · **Bucket:** `env` (from BP1-TRIAGE, via the BATTLEPLAN bus)
**Bus line:** `n=18d0f229ca7d5418` · `2026-08-31T12:55:13` · `frm=BP1-TRIAGE` · `body.bucket="env"`
**Build:** Houdini 22.0.417 · hython (agent lane)

---

## Why this file exists

BP1-HONESTY made the **code side** honest: recall now says
`UNAVAILABLE / env_unset` (or `plugin_unregistered`, or `layer_uncomposed`)
instead of returning a green, empty result that reads like "nothing to recall".

The code can now **name** the failure. It cannot **fix** it — the failure is a
launch-path defect, not a code defect. That is what this file is for.

The bucket is `env` because **TRIAGE's first failing gate was G1 ENV**
(`PXR_PLUGINPATH_NAME` unset). `env` is a launch-path bucket by rule
(docs/BATTLEPLAN.md §2), so the remedy is operator-side — the three options
below.

---

## The defect, in one breath

`packages/synapse.json` is installed **only** in the OneDrive-redirected prefs
dir, and **hython does not follow that redirect**.

| Where | `synapse.json`? | Consequence |
|---|---|---|
| `OneDrive/Documents/houdini22.0/packages/` | **present** | GUI (live prefs live in OneDrive) may load it → G1/G2 may pass |
| classic `C:/Users/User/houdini22.0/packages/` | **absent** | hython resolves `HOUDINI_USER_PREF_DIR` here → package never loads |

Package never loads → its env block never runs → `PXR_PLUGINPATH_NAME` (and
`MONETA_SRC`) stay unset → Moneta is unimportable → **G1 fail, G2 fail**, and
G3/G4 can't even be observed.

*TRIAGE evidence:* `harness/battleplan/notes/BP1-TRIAGE_launch_path.md`;
`harness/battleplan/runs/2026-08-31/silent_recall_hython.json`;
`packages/synapse.json:22-25`; `scripts/install_synapse_package.py:73-77,92-121`.

---

## The fix — pick one (recommended first)

**1. Point Houdini at the repo package (best for headless / CI).**
Add `<repo>/packages` to `HOUDINI_PACKAGE_DIR` before launching hython. Paths in
`synapse.json` derive from `$HOUDINI_PACKAGE_PATH`, so nothing is hard-coded and
the same package serves GUI and headless.

```
setx HOUDINI_PACKAGE_DIR "C:\Users\User\SYNAPSE\packages"   # persistent, new shells
# or, per-session (PowerShell):
$env:HOUDINI_PACKAGE_DIR = "C:\Users\User\SYNAPSE\packages"
```

**2. Deploy a resolved copy into the classic prefs dir.**
Run the installer, which globs the candidate pref dirs and writes a resolved
`synapse.json`:

```
hython C:\Users\User\SYNAPSE\scripts\install_synapse_package.py
```

Make sure it lands in **classic** `C:/Users/User/houdini22.0/packages/`
(the one hython reads), not only the OneDrive copy.

**3. Make hython honor the OneDrive redirect.**
Set `HOUDINI_USER_PREF_DIR` to the OneDrive prefs dir for the hython process so
it finds the already-deployed package:

```
$env:HOUDINI_USER_PREF_DIR = "C:\Users\User\OneDrive\Documents\houdini22.0"
```

Option **1** is the durable one — it makes the repo the source of truth and
removes the OneDrive/classic split entirely.

---

## How to know it worked

After applying a fix, re-run TRIAGE's probe:

```
hython C:\Users\User\SYNAPSE\harness\battleplan\notes\probe_silent_recall.py
```

**Working looks like:** G1 ENV `pass` (`PXR_PLUGINPATH_NAME` set) → G2 PLUGIN
`pass` (moneta importable) → G3 LAYER + G4 RECALL now observable. With the layer
composed, recall returns `SUCCESS` with `hit=true/false` — never
`UNAVAILABLE / env_unset`.

---

## Still UNKNOWN — the GUI half (Joe's hands)

TRIAGE proved the **hython** half. The **GUI** half is `gui_required`
(acceptance predicate 4) and stays **UNKNOWN** until Joe pastes a live GUI
round-trip. The GUI's live prefs are in OneDrive, so the GUI may already pass
G1/G2 — but that is a hypothesis until measured, not a pass. Do not record it
green from here.
