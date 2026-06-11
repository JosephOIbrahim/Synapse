# Installation (developers)

> **Just want to use SYNAPSE in Houdini?** The 5-minute artist setup lives in the
> [README ▸ Install](../../README.md#install) — download, run the installer, paste your
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
```

Alternatively, add the repo's `packages/` directory to `$HOUDINI_PACKAGE_DIR` in your
`houdini.env` (see the README's *Portable / no-install setup*). Either way, **restart
Houdini** afterward — packages load at launch.

## Run the tests

```bash
python -m pytest tests/ -q
```

Most of the suite (~3,000 tests) runs with **no Houdini required**. ~70 Moneta-gated tests
skip automatically on a clean clone / CI without the optional `moneta` package.

> **Upgrading Houdini?** Follow `docs/studio/UPGRADE.md` — symbol-table regen, vendor ABI check, installer re-run, gate confirmation.
