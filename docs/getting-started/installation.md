# Installation (developers)

> **Just want to use SYNAPSE in Houdini?** The 5-minute artist setup lives in the
> [README ▸ Install](../../README.md#-install--5-minutes) — download, run the installer, paste your
> API key, open the panel, type "make a box". This page is the editable-install + test
> path for contributors.

## Editable install

```bash
git clone https://github.com/JosephOIbrahim/Synapse.git
cd Synapse
pip install -e ".[dev]"
```

Optional feature extras (websocket adapter, MCP, routing, encryption):

```bash
pip install -e ".[dev,websocket,mcp,routing,encryption]"
```

## Register the Houdini package

The package ships in-repo at `packages/synapse.json`. Register it once so the SYNAPSE
panel, shelves, and the `synapse` Python package load on launch:

```bash
python scripts/install_synapse_package.py            # auto-detects your houdini prefs
python scripts/install_synapse_package.py --dry-run  # preview without writing
python scripts/install_synapse_package.py --verify   # read-only: did it actually work?
```

Alternatively — the **portable route, no install** — add the repo's `packages/` directory
to `$HOUDINI_PACKAGE_DIR` in your `houdini.env`; Houdini then loads the version-controlled
`packages/synapse.json` directly. Either way, **restart Houdini** afterward — packages load
at launch.

### Confirming the install

`--verify` writes nothing. It re-checks each install condition and prints one screen of
`PASS` / `FAIL` / `MANUAL` rows: the checkout's key paths, which Houdini pref dirs are wired
to *this* checkout (and whether the pref dir your installed build actually reads is among
them), the vendored-SDK ABI, API-key presence, and discoverable Houdini installs.

`MANUAL` rows are the three things no process outside Houdini can observe — the Pane Tab
menu entry, "make a box" creating a node, and the Connect button's state. They are never
rendered as `PASS` and never affect the exit code. Exit is `0` only when no row `FAIL`s.

*Note on `--verify` and the pref dir:* the installer writes into **every** candidate pref
dir it finds, so on a seat with several Houdini majors "the installer succeeded" does not by
itself prove the right one was hit. `--verify` closes that gap — it derives the pref-dir name
each discovered build reads and `FAIL`s when an installed build is not covered.

## Run the tests

```bash
python -m pytest tests/ -q
```

Most of the suite (~4,700 collected) runs with **no Houdini required**. ~100 tests skip
automatically on a clean clone / CI — the Moneta-gated ones need the optional `moneta`
package, the rest need a live Houdini.

> **Upgrading Houdini?** Follow `docs/studio/UPGRADE.md` — symbol-table regen, vendor ABI check, installer re-run, gate confirmation.
