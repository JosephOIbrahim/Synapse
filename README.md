<p align="center">
  <img src="assets/SYNAPSE.png" alt="SYNAPSE" width="160">
</p>

<p align="center"><strong>Your AI assistant inside Houdini.</strong><br>Describe a task. Inspect the nodes. Keep creative control.</p>

<p align="center"><sub>v5.95.0 · Houdini 22.0.400 · Python 3.13 runtime<br>tags: v5.95.0 is Latest</sub></p>

[![Latest release](https://img.shields.io/github/v/release/JosephOIbrahim/Synapse)](https://github.com/JosephOIbrahim/Synapse/releases/latest)
[![CI](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml/badge.svg)](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**[Install](docs/getting-started/installation.md)** · [First session](docs/getting-started/quickstart.md) · [JEV key setup](docs/getting-started/jev-setup.md) · [Help](#when-you-get-stuck) · [What's new](docs/releases/v5.95.0.md)

## Start here

**The current release is v5.95.0, and it installs from source.** It runs on **Windows + Houdini 22.0.400**, using Houdini's bundled Python 3.13. See [installation requirements and steps](docs/getting-started/installation.md).

**There is also an older one-click installer.** The latest [Windows Setup](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.86.0/SYNAPSE-5.86.0-Setup.exe) is v5.86.0. It includes Identify and the latest panel, JEV and SideFX library changes, but not the changes in v5.87.0 through v5.95.0.

The Setup is unsigned, so check it against that release's [SHA-256 checksums](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.86.0/SHA256SUMS.txt) before you run it.

**Pick one path, then follow these four steps.**

1. Save your scene and close Houdini. Follow **[source installation](docs/getting-started/installation.md#source-installation)** for v5.95.0, or run the v5.86.0 **[Windows Setup](docs/getting-started/installation.md#windows-installer)**.
2. Restart Houdini. Open **New Pane Tab → Synapse**.
3. Open **Connect models**. Choose a provider and model; add its key if needed.
4. For node creation, select **Build and edit networks**. Choose **Check connection → Use this model**.

Using Ollama? Start its service first. **Connect** starts the separate Houdini bridge; **Doctor** checks the setup without a model.

## Your first build

In a scratch scene, send:

```text
make a box
```

Inspect the nodes, change a parameter, then try **Undo**.

```mermaid
flowchart LR
    accTitle: From a prompt to an inspected result
    accDescr: You describe a task. Your selected model uses permitted tools. SYNAPSE shows the result or a reason it could not run. You inspect the scene.
    U["Describe a task"] --> M["Model +<br/>permitted tools"]
    M --> R["Result or<br/>reason shown"]
    R --> I["Inspect in<br/>Houdini"]
    classDef default fill:#F6B26B,stroke:#D07020,color:#000000
    classDef artist fill:#F6B26B,stroke:#D07020,color:#000000
    classDef synapse fill:#D07020,stroke:#D07020,color:#000000
    class U,I artist
    class M synapse
    linkStyle default stroke:#D07020
```

**Undo covers a recorded operation.** It does not reverse a whole conversation or files written to disk. A failed build can leave partial nodes until you deliberately undo them.

The normal panel worker blocks node deletion, arbitrary Python/VEX, rendering, exporting and PDG cooking. See [tool policy and execution boundaries](docs/architecture/overview.md#permission-and-undo-boundaries).

## Build from a verified recipe

Some requests have a recipe that was built and checked on Houdini 22.0.400. Scatter Instances on an imported Gaussian-splat world is the first recipe that reads the scene for you.

Ask in plain words:

```text
Scatter rocks along the cobblestone lane.
```

SYNAPSE reads the scene before it builds. It finds the camera, the world, the world's collider and the place in the chain where the new nodes go, and it tells you where it read each one.

If anything is missing or ambiguous, the answer is **UNKNOWN** and nothing is built.

If everything is known, it builds the recipe with the recipe's own values. An older note in memory cannot change them, and any value it had to correct is listed in the reply.

```mermaid
flowchart LR
    accTitle: A verified recipe reads the scene before it builds
    accDescr: You ask for a scatter in plain words. SYNAPSE reads the scene for the camera, the world, its collider and the splice point. If anything is missing or ambiguous it answers UNKNOWN and builds nothing. If everything is known it builds with the recipe's fixed values and shows a receipt you can revert.
    A["Ask in<br/>plain words"] --> R["Read the scene<br/>for five bindings"]
    R -->|"missing or ambiguous"| U["UNKNOWN<br/>nothing built"]
    R -->|"all known"| B["Build with the<br/>recipe's values"]
    B --> C["Receipt<br/>and Revert"]
    classDef default fill:#F6B26B,stroke:#D07020,color:#000000
    classDef artist fill:#F6B26B,stroke:#D07020,color:#000000
    classDef synapse fill:#D07020,stroke:#D07020,color:#000000
    class A,C artist
    class R,B synapse
    linkStyle default stroke:#D07020
```

The reader knows one scene shape today: a `/stage` network, one camera, and a Camera node feeding the render settings directly. The [release notes](docs/releases/v5.94.1.md) list what was seen in Houdini and what was not.

## See what nodes do

Select one or more nodes in a network editor. Then click **Identify** at the bottom of the panel, or send `/identify`.

A short bubble appears beside each node, drawn over the network editor. It says what the node does, which parameters you changed, and whether the node has an error, a warning or a bypass.

The bubble comes from the node itself and its page in your local SideFX help library, found the way Houdini's own help finds it, or from an HDA's own help when the library has no page for it. No model runs, and nothing leaves your machine.

Click **Identify** again, or send `/identify off`, to clear the bubbles. They are drawn over the editor, so nothing is written to your scene.

```mermaid
flowchart LR
    accTitle: How Identify explains selected nodes
    accDescr: You select nodes and click Identify. SYNAPSE reads each node and finds its exact page in the local SideFX help library, the way Houdini's own help does, or uses an HDA's own help, without a model. A short bubble appears beside each node, drawn over the network editor. Nothing is written to the scene.
    S["Select nodes"] --> I["Click Identify"]
    I --> R["Read the node +<br/>its exact help page"]
    R --> N["Short bubble<br/>beside each node"]
    N --> F["Nothing written<br/>to the scene"]
    classDef default fill:#F6B26B,stroke:#D07020,color:#000000
    classDef artist fill:#F6B26B,stroke:#D07020,color:#000000
    classDef synapse fill:#D07020,stroke:#D07020,color:#000000
    class S,I artist
    class R,N synapse
    linkStyle default stroke:#D07020
```

Each click shows up to 60 bubbles. The [release notes](docs/releases/v5.85.0.md) explain the details and current limits.

## Find the right control

| I want to… | Open or use… |
|---|---|
| Change the generation model | The model name at the top, or **Connect models**. |
| Add my JEV / TypeSafe key | **Connect models → JEV / TypeSafe key setup → Save session key**. [Setup guide](docs/getting-started/jev-setup.md). |
| Make more room for my prompt | Drag **Resize** above the input box. |
| Find an action | **Commands** below the input box. |
| See what selected nodes do | **Identify** at the bottom of the panel, or send `/identify`. |
| Read how the shot's camera moves | **Spatial** at the bottom of the panel, or send `/spatial`. It draws the path in one undo step, with no model call. |
| Ask what SYNAPSE remembers about this scene | Ask in plain words. It reads this scene's saved notes first, and it says the answer is recalled, not measured again. |
| Import a Marble world or Gaussian `.ply` | **World Labs** beside **Cloud relay**. [Import flow and limits](docs/architecture/overview.md#world-labs-import). |
| Connect the SideFX help library | Follow **[Build and connect](docs/studio/SIDEFX_LIBRARY.md#build-and-connect)**; Scout searches the published local index. |
| Check a connection | **Connect**, then **Doctor**. |

Saving a JEV key keeps it in memory until Houdini closes. **It does not enable JEV, verify the key or grant data permission.** The setup guide walks through those separate controls.

### Three ways to stop

| Control | What it reaches | Limit |
|---|---|---|
| **Stop** | The panel's current turn. | Does not prove an active cook or render has stopped. |
| **Cancel cook** · overflow menu | One known cooking node. | Unavailable when SYNAPSE cannot identify the node. |
| **Emergency halt** · overflow menu | Cooking TOP networks under `/tasks`, `/obj`, `/stage`, `/out`; captures a session report. | Background renders are reported, not stopped. |

**A turn also stops itself.** It ends after 25 tool rounds, 10 minutes or 3,000,000 input tokens, whichever comes first. The last line of the reply says which limit it reached, and no tool runs after that line.

## What's ready

- **Network work:** build and inspect through permitted tools; keep the result editable in Houdini.
- **Verified recipes:** Scatter Instances reads its scene bindings in one call and builds with fixed values, or answers UNKNOWN and builds nothing.
- **Identify:** a short bubble beside each selected node, built from the node and local SideFX help with no model call.
- **Model choice:** Claude, Gemini, NVIDIA Nemotron, Ollama and custom OpenAI-compatible endpoints. Tool support varies.
- **Claude Code:** use SYNAPSE's tools from Claude Code through [MCP](docs/mcp/SETUP.md#claude-code). It asks before each tool call unless you allow that tool.
- **Optional JEV assistance:** rank selected-network actions or measure routing. Your generation model stays selected.
- **Local knowledge:** [SideFX library](docs/studio/SIDEFX_LIBRARY.md), [project memory](docs/architecture/overview.md#project-and-scene-memory) and [checked lookdev suggestions](docs/development/rsi_stage0.md).

[Current limits](docs/status.md) · [Latest release notes](docs/releases/v5.95.0.md) · [Changelog](CHANGELOG.md)

## When you get stuck

| What you see | Try this first |
|---|---|
| No Synapse pane | Restart Houdini, then [verify installation](docs/getting-started/installation.md#verify-the-installation). |
| Missing Ollama models | Start Ollama; reopen **Connect models → Check connection**. |
| Unsure where the TypeSafe key goes | [JEV key setup](docs/getting-started/jev-setup.md#add-your-key). |
| No saved suggestion | Read its reason. A checked record, matching version and project memory owner are required. |
| Build running away | Use [Cancel cook or Emergency halt](#three-ways-to-stop), then inspect the scene. |
| Identify bubbles say **Not in the local SideFX library** | [Build and connect the SideFX library](docs/studio/SIDEFX_LIBRARY.md#build-and-connect), then restart Houdini. |

[Report a bug](https://github.com/JosephOIbrahim/Synapse/issues/new/choose) · [First-session walkthrough](docs/getting-started/quickstart.md)

## Watch it work

[![Play the SYNAPSE tool demonstration](assets/demo_v2_video_thumb.jpg)](https://vimeo.com/1225720538)

[Watch the recorded demonstration on Vimeo →](https://vimeo.com/1225720538)

<details>
<summary><strong>For developers: architecture, checks and memory</strong></summary>

**139 tools, two paths.** The registry count comes from [`TOOL_DEFS`](python/synapse/mcp/_tool_registry.py), checked by [tool-count tests](tests/test_phase0c_doc1_toolcount.py).

Panel requests prefer HTTP `/mcp`; its ordinary mutations use the execution bridge. Reads, farm controls and Doctor route separately. The configured stdio client forwards Houdini calls over WebSocket `/synapse` to direct handlers. Those paths have different policy and evidence boundaries. Setting `SYNAPSE_MCP_READ_ONLY=1` limits every `/mcp` and WebSocket caller, the panel included, to read-only tools; stop controls always pass ([read-only mode](docs/mcp/SETUP.md#read-only-mode)).

[Execution diagrams and limits](docs/architecture/overview.md#execution-paths) · [External MCP setup](docs/mcp/SETUP.md) · [Source development and tests](docs/getting-started/installation.md#for-contributors)

### How SYNAPSE remembers

Configured memory and scene/project notes supply recalled context. Recall is advice; it does not authorize a scene action.

A scene's notes come back through `synapse_project_setup`. Search and recall read saved decisions, and they do not cover those notes. The panel asks for the notes first when you ask what it remembers about a scene.

Only what you ask it to remember is stored. Automatic session and action rows are off unless `SYNAPSE_AUTO_MEMORY=1`.

Moneta's USD mirror is an inspection view, not the storage owner. Missing services and unknown outcomes remain visible. A memory store that cannot be read is reported as a failure, not as an empty answer.

[Storage and recall diagram](docs/architecture/overview.md#project-and-scene-memory) · [Optional memory LOOP](docs/architecture/overview.md#memory-loop) · [Saved suggestions](docs/development/rsi_stage0.md)

**CI covers stock Python on Linux, macOS and Windows.** Native Houdini behavior and Windows installer qualification are separate checks. See each [release's evidence](docs/releases/v5.95.0.md) before relying on it.

</details>

## License

[MIT](LICENSE). Bundled Moneta retains its separate proprietary terms.

Patent applications pending on the USD cognitive-state substrate, digital injection, and predictive lighting — see [PATENTS](PATENTS).
