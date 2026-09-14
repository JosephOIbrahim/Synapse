<p align="center">
  <img src="assets/SYNAPSE.png" alt="SYNAPSE" width="160">
</p>

<p align="center"><strong>Your AI assistant inside Houdini.</strong><br>Describe a task. Inspect the nodes. Keep creative control.</p>

<p align="center"><sub>v5.69.0 · Houdini 22.0.400 · Python 3.13 runtime<br>tags: v5.69.0 is Preview · v5.68.0 is Latest</sub></p>

[![Latest release](https://img.shields.io/github/v/release/JosephOIbrahim/Synapse)](https://github.com/JosephOIbrahim/Synapse/releases/latest)
[![CI](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml/badge.svg)](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml)
[![MIT license](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**[Download Windows Setup 5.68.0](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.68.0/SYNAPSE-5.68.0-Setup.exe)** · [What's new in 5.69.0](docs/releases/v5.69.0.md) · [Help](#when-you-get-stuck)

> **5.69.0 is a Preview; 5.68.0 stays Latest.** The Preview has no installer yet, so the
> button above is the 5.68.0 Setup — it exists and it works. Running from source? Pull
> `v5.69.0`. [What that means →](docs/releases/v5.69.0.md#update)

## Start here

**You need:** Windows and Houdini **22.0.400**. Setup includes the Python dependencies.

1. **Save your scene and close Houdini.**
2. **Run Setup.** Choose your Houdini installation and its preference folder.
3. **Open Houdini → New Pane Tab → Synapse.**
4. **Connect models → choose a model → Check connection → Use this model.**

For node creation, select **Build and edit networks** in the model dialog.
Cloud models need your API key. For Ollama, start Ollama and choose an installed model.

The installer is unsigned. [Checksums](https://github.com/JosephOIbrahim/Synapse/releases/download/v5.68.0/SHA256SUMS.txt) · [Full setup guide](docs/getting-started/installation.md) · [Source installation](docs/getting-started/installation.md#source-installation)

## Your first build

Open a scratch scene and send:

```text
make a box
```

Inspect the nodes, change a parameter, then try **Undo**. Undo reverses a recorded
operation; it does not reverse an entire conversation or external file writes.

**Three controls to know**

| Control | Use it for |
|---|---|
| **Connect models** | Choose the AI service and model. |
| **Connect** | Start Houdini's local SYNAPSE bridge. |
| **Doctor** | Check the setup without asking a model. |

**Three ways to stop — they are not the same**

| Control | What it reaches | What it does not do |
|---|---|---|
| **Stop** | The panel's current turn. | Does not prove a cook or render already running has finished. |
| **Cancel cook** *(overflow menu)* | The one cooking node it names. | Only offered when SYNAPSE knows which node; it says so when it doesn't. |
| **Emergency halt** *(overflow menu)* | Cancels PDG cooks under `/obj` and captures a session report. | Does not stop background renders. Those are reported back so you can stop them deliberately. |

Three verbs, three consequences. They are kept apart on purpose — the one you
want when a build is running away is not the one you want when a model is
rambling.

[First-session walkthrough →](docs/getting-started/quickstart.md)

## What's ready

- **Build and inspect networks** through the panel's permitted tools.
- **Choose local or cloud models:** Claude, Gemini, NVIDIA Nemotron, Ollama, or a custom OpenAI-compatible endpoint. Tool support varies.
- **Recall project decisions** when the memory store is configured.
- **Use a saved lookdev suggestion** through the optional Stage 0 workflow.

**New in 5.69.0:** the stop controls actually stop. Emergency halt used to be
dropped in silence when another panel tool was running; it now fires, and a
refused request says so instead of returning quietly. A REVIEW consent card no
longer records a rejection that never happened. Preview channel — see the
note at the top. [Release details and limits →](docs/releases/v5.69.0.md)

Predictive creation, product-level Computer Use controls, and recursive
self-improvement remain development work. The attended operator checks in this
release do not make those features complete. [Artist-first intent →](INTENT.md)

## Watch it work

[![Play the SYNAPSE tool demonstration](assets/demo_v2_video_thumb.jpg)](https://vimeo.com/1225720538)

**[Watch the recorded demonstration on Vimeo →](https://vimeo.com/1225720538)**

## When you get stuck

| What you see | Try this first |
|---|---|
| No Synapse pane | Restart Houdini, then [verify installation](docs/getting-started/installation.md#verify-the-installation). |
| Missing Ollama models | Start Ollama, reopen **Connect models**, then **Check connection**. |
| Connection trouble | Click **Connect**, then **Doctor**. |
| No saved suggestion | Read the card's reason; a matching experience and project memory owner are required. |

A failed build can leave partial nodes. **Stop** prevents further panel work; it
does not prove an active cook or render has finished — see [the three stop
controls](#your-first-build) for the ones that reach work already running.
Review results in Houdini.

[Current status](docs/status.md) · [Report a bug](https://github.com/JosephOIbrahim/Synapse/issues/new/choose)

<details>
<summary><strong>How SYNAPSE remembers</strong></summary>

Ask SYNAPSE to remember a decision, then ask about it later. Configured memory
and scene/project notes provide context for the answer.

With Moneta active, records can also appear in the USD inspection mirror,
`cortex_root.usda`. Closing that view leaves saved memory intact.

The optional observation loop connects Moneta, Octavius and Hanish. Recalled
records remain advice; scene changes still use action tools. Missing substrates
and unknown outcomes remain visible.

[Storage and recall diagram](docs/architecture/overview.md#project-and-scene-memory) · [LOOP setup](docs/MEMORY_LOOP_REPAIR.md) · [Saved suggestions](docs/development/rsi_stage0.md)

</details>

<details>
<summary><strong>For developers: policy, evidence and source setup</strong></summary>

**128 tools, two paths.** The external MCP bridge and live
WebSocket handlers have different consent and integrity boundaries. Panel workers
add their own tool restrictions.

The new `proposal` worker mode permits registered reads, real knowledge tools and
declared proposals. Direct mutation and graph instantiation are denied to the
worker. It is opt-in; the default remains `standard`. Host graph instantiation is
classified for review. These changes do not add consent gating to the separate
live WebSocket path.

- [Architecture and diagrams](docs/architecture/overview.md)
- [Installer build and tests](installer/README.md)
- [Source installation and tests](docs/getting-started/installation.md#for-contributors)
- [MCP setup](docs/mcp/SETUP.md)
- [Release notes](docs/releases/v5.69.0.md) · [Changelog](CHANGELOG.md)

GitHub CI tests stock Python on Linux and macOS. Native Houdini and Windows
installer checks are separate. A green CI badge does not establish a live render
or a clean-machine installation. Older Stage 0 experiences need matching
qualification after a SYNAPSE version bump.

</details>

## License

[MIT](LICENSE). Bundled Moneta retains its separate proprietary terms.
Patent applications pending on the USD cognitive-state substrate, digital injection,
and predictive lighting.
