# Deploy SYNAPSE

Deploy changes from repo source to Houdini prefs via the installer.

## Workflow

1. **Verify source**: Confirm all changes are in the repo source (`$SYNAPSE_ROOT/houdini/`, i.e. `<repo>/houdini/`) — NOT in deployed copies (`houdini22.0/` under your Houdini prefs root)
2. **Run installer**: Execute `python <repo>/install.py` to redeploy shelf, panel, toolbar, and icons
3. **Confirm deployment**: Check file timestamps in `houdini22.0/` match the source
4. **Report**: List what changed and whether Houdini needs to be restarted to pick up the changes

The prefs root is `$HOUDINI_USER_PREF_DIR` when set; otherwise `install.py` scans `~/Documents/houdini22.0` (then 21.x, 20.x, 19.x) on Windows. On a host where Documents is OneDrive-redirected the scan misses — set the variable (see below).

## Notes

- Use `--dry-run` to preview what would be copied without making changes
- Use `--verify` to check current deployment matches source
- Use `--uninstall` to remove all Synapse files from Houdini prefs
- Panel changes require closing and reopening the Python Panel tab in Houdini
- Shelf changes require restarting Houdini

## Fresh machine

The build is pinned to **Houdini 22.0.400** (`python/synapse/recipes/contracts.py::SUPPORTED_BUILD`; the committed symbol table `python/synapse/cognitive/tools/data/h22_symbol_table.json` is stamped `22.0.400`). Newer 22.0.x installs are not substitutes: they pass the pytest+PySide6 usability gate and then run against a runtime no symbol table describes.

1. **Install Houdini 22.0.400.** It embeds Python 3.13 (`python313`), so anything added to hython must be cp313: `hython -m pip install pytest` (PySide6 ships with Houdini). Vendored wheels are checked by `python scripts/install_synapse_package.py --verify` (H22_ABI = cp313).
2. **Pin the hython.** Copy `.env.example` to `.env` and keep `SYNAPSE_HYTHON=C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe`. `.env` is read by `synapse.host.auth` at Houdini boot only — for shell tools export it too: `$env:SYNAPSE_HYTHON = 'C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe'`. Confirm with `python .synapse/hytest.py --which` (prints the selected hython; stderr says why).
3. **Prefs dir.** `$env:HOUDINI_USER_PREF_DIR = '<Documents>/houdini22.0'` — explicit, because Documents may be OneDrive-redirected and both `install.py` and hython otherwise look at the pre-redirect path.
4. **Package file.** Either `python scripts/install_synapse_package.py` (writes a resolved `packages/synapse.json` into the prefs dir) or `$env:HOUDINI_PACKAGE_DIR = '<repo>/packages'` to load the repo copy in place. `load_package_once` guards the double-load if both are set.
5. **Moneta checkout.** `packages/synapse.json` sets `MONETA_SRC=$SYNAPSE_ROOT/../Moneta/src` and `PXR_PLUGINPATH_NAME=$MONETA_SRC/../schema`, so clone Moneta **beside** the SYNAPSE repo (`<parent>/Moneta`). Headless hython runs that bypass the package need both exported by hand, or `MemoryPort` reports UNAVAILABLE.
6. **Windows deep paths.** `git config core.longpaths true` before a deep-path clone.
7. Then the Workflow above: `python <repo>/install.py`, restart Houdini, run `synapse_doctor`.
