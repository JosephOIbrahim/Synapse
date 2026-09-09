# Install SYNAPSE on Windows

[Back to README](../../README.md) · [First session](quickstart.md)

The Windows Setup wizard installs SYNAPSE, its panel, shelf, icons and required
Python dependencies in one pass. Ordinary installation needs no terminal, Git,
system Python, pip, or internet connection. Houdini must already be installed.

This branch contains an **unsigned local review build**, not a newly published
release. Obtain `SYNAPSE-5.67.4-Setup.exe` from the reviewed build output. The
current native validation target is **Windows, Houdini 22.0.400, Python 3.13**.
See the [verification record](windows-installer-verification.md) for its limits.

## Install

1. Save your scene and close Houdini. Setup asks you to close a running Houdini;
   it never terminates it.
2. Open **SYNAPSE-5.67.4-Setup.exe**. Review the license and included components.
   This local build is unsigned, so Windows may show an unknown publisher.
3. Choose your **Houdini application folder**. Setup lists detected builds and
   checks their actual Python version. Other builds need an explicit
   compatibility acknowledgement; unsupported Python versions are blocked.
4. Choose your **Houdini preference folder**. Setup offers the launch environment
   override, Windows Documents (including redirection), and existing OneDrive
   folders. Confirm the folder your Houdini launcher actually uses. You can
   browse to a custom folder.
5. Keep the suggested application folder, normally
   `%LOCALAPPDATA%\Programs\SYNAPSE`, or choose a separate empty folder that you
   can write to. It must be separate from Houdini preferences.
6. Review the choices and click **Install**. Setup verifies the payload before
   activation and checks installed files and registration afterward.
7. Launch the selected Houdini build. Open **New Pane Tab → Synapse** (or choose
   Synapse under Python Panels), then run **Doctor**. Enable the Synapse shelf
   if desired.

Only the selected preference folder is registered on the first installation.
Running Setup again can add another preference folder; later upgrades update
all preference folders already owned by that installation. Multiple Houdini
builds can share a preference folder, so the choice applies to those builds.
Launch settings hidden inside a studio launcher must be checked in that launcher.

## Moving from a source installation

If Setup finds old SYNAPSE package, panel, shelf or icon files, select **Back up
and replace existing SYNAPSE registration**. Setup records their exact original
contents and activates one package pointing to the installed runtime. It does
not move or delete the source checkout.

A duplicate loaded from a studio package directory or `package_path` link blocks
installation with its location. Change the launch configuration before retrying;
Setup cannot safely choose which studio registration should win. Unresolved
conditional package links also need an explicit launch configuration.

Backups are retained in the installation receipt. Uninstall restores these old
registrations, so **the old source installation may load again** afterward.

## Connect a model

Model access is a separate step. Open **Connect models** below the prompt:

1. Choose an engine and model. For Ollama, start its local service first.
2. Enter a key if the service requires one.
3. For node creation, choose **Task needs → Build and edit networks**.
4. Choose **Check connection**, then **Use this model** after it succeeds.

The connection check requests model metadata; it does not send your scene or
prompt. Keys entered here remain in the panel session and clear when it closes;
an in-flight request can finish afterward. Existing environment keys are also
supported. The separate **Connect** button starts the local Houdini bridge.

[Continue to your first build →](quickstart.md)

## Verify and troubleshoot

Choose **Verify SYNAPSE installation** from the Windows Start menu. It checks
recorded file hashes, panel/shelf XML, runtime version and package registration.
It does not require a provider key. A successful file check does not prove that
Houdini loaded the package or that a model can answer.

Inside Houdini, open the panel and run **Doctor**. Read each result: absent
optional components, a missing bridge, and untested memory storage are separate
from a missing installation file. In the native review probe, Moneta imported
and its USD schema registered, but Doctor's `moneta_substrate` row failed because
no active USD root was supplied to demonstrate schema use. That row remains
unresolved; it is not a passing storage test.

If the panel is absent, confirm that Houdini uses the same preference folder
shown in Setup. If a recorded package or runtime file was edited after install,
Setup preserves the edit and explains the conflict instead of overwriting it.
Edited maintenance files block upgrade or uninstall; save your edit elsewhere and restore the original helper file before continuing. The setup log is in the Windows temporary folder (`Setup Log ...txt`).

## Upgrade and uninstall

Save and close Houdini, then run the newer Setup in the same application folder.
A new version folder is staged and verified before the registration switches.
Old runtime folders remain available until uninstall; removed code files do not
appear in the new active runtime. Downgrades are refused; uninstall first if you
intentionally need an older build.

Use **Windows Settings → Apps → Installed apps → SYNAPSE → Uninstall**, or the
Start menu shortcut. Uninstall removes the unchanged runtime files owned by
Setup, its package registration and Windows integration. Projects, HIP files,
memory stores, credentials, unrelated preferences, added files and changed
runtime files are preserved. The application folder may remain with an
`uninstall-receipt.json` and retained data. Do not delete it without reviewing it.

Panel settings and configurable ledgers/reports use persistent locations under
`%USERPROFILE%\.synapse` by default; existing environment overrides still apply.
Project memory continues to use the runtime's established project storage
rules. Derived scout caches regenerate after an upgrade. Agent health history
that was stored inside an older runtime is retained there, but is not carried
into the new runtime. Setup does not merge or rewrite memory databases.

If installation is interrupted, run the same Setup again. Its transaction
journal restores a prior registration before retrying. If uninstall is
interrupted, run uninstall again. Conflicting edits made during interruption
cause a preservation error and require review instead of automatic overwriting.

## Included components

The local review artifact includes the Anthropic SDK and its shipped dependencies,
WebSocket support, file locking, and an explicitly supplied **Moneta 1.2.0rc1**
archive with its USD schema. Houdini supplies Python, Qt and OpenUSD; Setup
contains a separate maintenance Python that does not replace Houdini's Python.
Moneta's source is proprietary; this local artifact grants no redistribution
rights. A builder can omit Moneta, in which case the package selects JSONL memory.

External MCP server environments, local models, semantic-model downloads,
Hanish, SALUS, Octavius, and optional analysis backends are separate installations.
The core panel does not need those optional services to install. An absent
optional capability must be treated as unavailable, not as a passing test.

## Source installs and contributors

The old scripts remain available for source development. Keep the checkout in
place because registration refers to it. Run both from the repository folder,
using the **same actual preference folder**:

```powershell
python scripts/install_synapse_package.py --pref-dir 'C:/Users/you/Documents/houdini22.0'
python install.py --houdini-prefs 'C:/Users/you/Documents/houdini22.0'
```

Both support `--dry-run` and `--verify`. The legacy package verifier still has an
Anthropic-specific key check; an Ollama-only setup can fail that row. Do not add
an unrelated provider key to silence it. The Windows maintenance verifier does
not have this key requirement. Avoid running the source installers over a
wizard-managed registration; migrate deliberately instead.

For stock-Python development, use a separate environment and follow the current
[CI configuration](../../.github/workflows/ci.yml). Native Houdini checks remain
separate from stock-Python tests. See [the two test environments](../CI_TWO_WORLDS.md),
[installer build instructions](../../installer/README.md), and the
[upgrade guide](../studio/UPGRADE.md).
