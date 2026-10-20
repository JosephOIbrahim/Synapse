# Start using SYNAPSE 5.97.6

[README](README.md) · [Versions and tags](TAGS.md) · [Full installation guide](docs/getting-started/installation.md)

## 1. 📦 Choose one install path

Save your scene and close Houdini before installing. The native qualification target is **Windows x64, Houdini 22.0.400 and Python 3.13.10**. Setup never closes Houdini for you.

| I want… | Use… |
|---|---|
| The packaged installation | [Windows Setup 5.97.6](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-Setup.exe), then the [wizard steps](docs/getting-started/installation.md#windows-installer). |
| A source installation | The [5.97.6 source ZIP](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SYNAPSE-5.97.6-source.zip), then [both source scripts](docs/getting-started/installation.md#source-installation). Source scripts do not provision the optional native artifact. |

🔎 Setup is **unsigned**: the inspected local signing setup has no configured publisher identity. Check [SHA256SUMS.txt](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/SHA256SUMS.txt). Do not bypass a security warning. The [verification record](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.97.6/installer-verification.json) states exactly which final-installer checks ran.

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

- **Explicit OFF stays OFF.** Existing registrations without an explicit opt-in also remain OFF.
- **Existing ON is preserved only after qualification.** Setup checks the pinned compatible artifact, actual primary Moneta backend, Rust scan/decay, encrypted mirror and fresh-process reopen on disposable data. An unsupported host or failed check refuses activation; it does not hide fallback.
- **Manual/source migration:** select “Back up and replace” only for the intended registration. Supported custom environment entries and extra import paths are retained; the original bytes are backed up and restored by uninstall.
- **Edited managed packages, multiple registrations in one preference folder, conditional settings or custom Houdini paths:** Setup refuses automatic migration. Preserve the files and resolve the reported ambiguity. Do not discard a deliberate OFF setting to pass a check.
- **Edits during qualification:** Setup rechecks package contents and namespace before activation; it refuses a changed plan.

Fresh installations receive ON only on the exact supported host after the same execution checks. Without an explicit ON choice, missing native artifacts or unsupported fresh hosts keep native mode OFF and report the reason. An explicit inherited ON choice requires qualification and refuses installation if unavailable. These checks use disposable data/keys and do not qualify every artist store, scene or future configuration.

[Installer flow](docs/architecture/overview.md#published-5976-installation) · [Release tests and limits](docs/releases/v5.97.6.md) · [Current status](docs/status.md).

The original [5.97.5 release](docs/releases/v5.97.5.md) remains unchanged and contains no native wheel.
