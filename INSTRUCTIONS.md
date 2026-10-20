# Start using SYNAPSE 5.97.5

[README](README.md) · [Versions and tags](TAGS.md) · [Full installation guide](docs/getting-started/installation.md)

## 1. 📦 Choose one install path

Save your scene and close Houdini before installing. The measured target is **Windows x64, Houdini 22.0.400 and its Python 3.13 runtime**.

| I want… | Use… |
|---|---|
| The packaged installation | [Windows Setup 5.97.5](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/SYNAPSE-5.97.5-Setup.exe), then the [wizard steps](docs/getting-started/installation.md#windows-installer). |
| A source installation | The [5.97.5 source ZIP](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/SYNAPSE-5.97.5-source.zip), then [both source scripts](docs/getting-started/installation.md#source-installation). |

🔎 Setup is **unsigned**. Check [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/SHA256SUMS.txt) before running it. Isolated final-installer checks passed; the interactive wizard, Windows registration/shortcuts and a clean-machine install remain untested. [Verification record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.5/installer-verification.json).

## 2. 🔌 Connect and check

1. Restart Houdini. Open **New Pane Tab → Synapse**.
2. Run **Doctor** for live setup diagnostics.
3. Open **Connect models**. Pick a provider/model and enter its key if needed. Start Ollama first if you use it.
4. Select **Build and edit networks**, then **Check connection → Use this model**.

**Connect models** chooses the model. The separate **Connect** button starts the Houdini bridge. [Model and key details](docs/getting-started/installation.md#3-connect-a-model).

## 3. 🧱 Try one small task

In a scratch scene, send `make a box`. Inspect the nodes, change a parameter and try Undo. [First-session walkthrough](docs/getting-started/quickstart.md).

**Stop** ends further panel work; it does not prove an active cook or render has stopped. **Undo** covers supported recorded operations, not a conversation or files on disk. [Stop controls](README.md#three-ways-to-stop).

## Existing native ON or OFF setups

🦀 **5.97.5 Setup bundles the Moneta Python backend, not the native Rust wheel.** A separately verified local Rust-ON setup is not the public default.

- **Installer-owned package edited outside Setup:** maintenance refuses it before changing the registration. Save the edited package; do not discard your choices just to pass maintenance.
- **Manual/source installation migrated with “Back up and replace”:** 5.97.5 saves the old package, then generates a new registration. Explicit `MONETA_NATIVE`, extra native import paths and other custom environment entries are not carried into that new registration.

If you rely on these settings, retain your working setup and review the migration before proceeding. The proposed preservation/native-artifact correction is **unreleased**. No replacement 5.97.5 download is implied. [Published installer code](https://github.com/JosephOIbrahim/Synapse/blob/v5.97.5/installer/synapse_setup/engine.py) · [Installation flow diagram](docs/architecture/overview.md#published-5975-installation).

## What 5.97.5 adds

- Moneta 1.3.0 pinned and packaged with its redistribution notice.
- One experimental LIGHT operation qualified in disposable headless fixtures. It is not a panel command or full RC+ξ activation.
- Reviewed release-content exclusions and downloadable verification reports.

[Release tests and limits](docs/releases/v5.97.5.md) · [Current status](docs/status.md) · [Troubleshooting](README.md#when-you-get-stuck).
