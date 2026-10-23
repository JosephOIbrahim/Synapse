# Install SYNAPSE

[Back to README](../../README.md) · [First session](quickstart.md)

**Current validation target:** Windows, Houdini 22.0.400, bundled Python 3.13.
Houdini runs SYNAPSE with its own Python.

## Windows installer

**[Download Windows Setup v5.97.7](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.7/SYNAPSE-5.97.7-Setup.exe)**

Setup packages this release's source and the pinned Moneta 1.3.0 Python backend.
Setup includes the panel as of v5.97.7, including Spatial, the Render footer row and the scene-reading Scatter recipe.
Setup includes a pinned native Rust artifact. Fresh supported Windows x64 / H22.0.400 / Python 3.13.10 setups receive ON only after actual isolated native execution and encrypted-mirror reopen checks. Explicit OFF and existing default-OFF registrations remain OFF. An existing ON setup must pass qualification; unsupported ON or failed checks refuse activation.

**Already using native Rust or custom package settings?** Read the
[existing-setup instructions](../../INSTRUCTIONS.md#existing-native-on-or-off-setups).
Supported custom environment entries and extra paths are retained. Edited managed
packages, multiple registrations, conditional settings and custom Houdini paths
stop automatic migration. The previous 5.97.6 tag and downloads are preserved.

[Release notes and validation limits](../releases/v5.97.7.md) ·
[SHA-256 checksums](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.7/SHA256SUMS.txt)

1. Save your scene and close Houdini.
2. Open Setup. This installer is unsigned, so Windows may show an unknown publisher.
3. Select the Houdini application and the preference folder used by your launcher.
4. Install into the suggested application folder, or another dedicated folder.
5. Start Houdini, open **New Pane Tab → Synapse**, then run **Doctor**.
   Continue with [Connect a model](#3-connect-a-model).

Setup includes required Python dependencies and the separately licensed Moneta
bundle; it needs no terminal, Git or system Python. Model credentials and optional
external services are separate.

**Read the downloaded installer's own validation record.** The
[5.97.7 verification asset](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.7/installer-verification.json)
binds its checks to the actual Setup hash and source commit. Extraction and
isolated execution of its embedded maintenance engine are distinct from the
interactive Windows wizard, registry/shortcut integration and clean-machine
qualification. See the [release limits](../releases/v5.97.7.md#limits).

The source installation steps below are an alternative route. Avoid running
the source scripts over a registration managed by the Setup wizard.

## Source installation

Source scripts do not install or automatically enable the optional native Rust artifact.

Use a terminal with Python available for these scripts. Installing a system
Python does not replace Houdini's own runtime.

### 1. Keep a copy of the repository

Download the source ZIP from [release 5.97.7](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.97.7)
and extract it into a permanent folder. Open a terminal in the folder containing
`install.py`.

If you use Git instead:

```shell
git clone --branch v5.97.7 https://github.com/JosephOIbrahim/Synapse.git
cd Synapse
```

### 2. Run both installers

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

For Setup installations, choose **Verify SYNAPSE installation** from the Windows
Start menu, then use **Doctor** inside Houdini for live diagnostics.

For source installations, run from the repository folder:

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

For Setup installations, save and close Houdini, then run a newer reviewed Setup
in the same application folder. To uninstall, use Windows **Installed apps →
SYNAPSE → Uninstall**. Setup preserves projects, memory, credentials, preferences
and user-added files.

For source installations, download the new release or update your clean Git
checkout, rerun both scripts, and restart Houdini. Read the
[upgrade guide](../studio/UPGRADE.md) for build changes.

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

Windows Setup includes pinned Moneta 1.3.0. Source installs need a separately
available Moneta checkout for that backend. Optional Hanish and Octavius setup
is separate from the basic install:
[LOOP configuration](../MEMORY_LOOP_REPAIR.md) and
[Stage 0 experience setup](../development/rsi_stage0.md).
