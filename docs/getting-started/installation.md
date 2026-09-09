# Install SYNAPSE

[Back to README](../../README.md) · [First session](quickstart.md)

**Current validation target:** Windows, Houdini 22.0.400, bundled Python 3.13.
Use a terminal with Python available for the installers. Houdini runs SYNAPSE
with its own Python; installing a system Python does not replace that runtime.

## 1. Keep a copy of the repository

Download the source ZIP from the [latest release](https://github.com/JosephOIbrahim/Synapse/releases/latest)
and extract it into a permanent folder. Open a terminal in the folder containing
`install.py`.

If you use Git instead:

```shell
git clone https://github.com/JosephOIbrahim/Synapse.git
cd Synapse
```

## 2. Run both installers

```shell
python scripts/install_synapse_package.py
python install.py
```

The first registers the package and its source paths. The second installs panel,
shelf and icon files. Restart Houdini after both finish.

<details>
<summary><strong>OneDrive, custom preferences, or multiple Houdini versions?</strong></summary>

Give both installers the **same actual Houdini preference folder**. The panel
installer does not automatically discover every OneDrive/custom location.

Replace this example path before running:

```shell
python scripts/install_synapse_package.py --pref-dir "C:/Users/you/OneDrive/Documents/houdini22.0"
python install.py --houdini-prefs "C:/Users/you/OneDrive/Documents/houdini22.0"
```

Both support `--dry-run` to preview writes. Keep the source repository in place;
the package refers to that location.

</details>

## 3. Connect a model

Open **New Pane Tab → Synapse**, then **Connect models** below the prompt.

1. Choose the engine and model.
2. Enter an API key if the service needs one. For Ollama, start the local service first.
3. Set **Task needs** to **Build and edit networks** for node creation.
4. Click **Check connection**, then **Use this model** when the check succeeds.

The check requests model metadata; it does not send your scene or prompt.
Keys entered here stay in the panel session and are cleared when the panel closes.
An in-flight response may finish after closing. Existing environment keys are
also supported.

**Connect models** selects the AI service. The separate **Connect** button starts
the local Houdini bridge. Use **Doctor** for model-free diagnostics.

[Continue to your first build →](quickstart.md)

## Verify the installation

Run from the repository folder:

```shell
python scripts/install_synapse_package.py --verify
python install.py --verify
```

For a custom folder, include the same `--pref-dir` or `--houdini-prefs` option you
used during installation. These verification commands do not write files.

The package verifier reports `PASS`, `FAIL` and `MANUAL`. A `MANUAL` row needs
a check inside Houdini; it is not a completed test.

**Known verifier limitation:** it still requires `ANTHROPIC_API_KEY` in its key
check. An Ollama-only setup, another provider, or a key entered only in the panel
can therefore fail that row even when its model connection works. Check the
reported paths, use **Check connection**, and read **Doctor** for the running setup.
Do not add an unrelated provider key just to silence this row.

## Updating

Download the new release or update your clean Git checkout, rerun both installers,
and restart Houdini. Read the [upgrade guide](../studio/UPGRADE.md) for build changes.

Stage 0 saved suggestions match the exact SYNAPSE version. Existing records are
retained, but need a matching rehearsal and import before they qualify for a new
version. The ordinary panel works without this optional suggestion setup.

## For contributors

Use a separate environment for stock-Python development. Match the current
[CI configuration](../../.github/workflows/ci.yml):

```shell
python -m pip install -e ".[dev,websocket,mcp]"
python -m pytest tests/ -m "not needs_houdini" -q -rs
```

Use `python -m pytest tests/ -q -rs` for the unfiltered suite. Missing runtimes and
optional substrates report explicit skips; there is no fixed test-count promise.
Native Python/Qt/USD checks are separate from a live Houdini session.

The shipped SDK wheels target Windows Python 3.11/3.13. Other interpreter/OS
combinations use installed dependencies and require their own native qualification.
See [the two test environments](../CI_TWO_WORLDS.md).

Optional Moneta, Hanish and Octavius setup is separate from the basic install:
[LOOP configuration](../MEMORY_LOOP_REPAIR.md) and
[Stage 0 experience setup](../development/rsi_stage0.md).
