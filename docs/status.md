# Current status and limits

[Back to README](../README.md) · [Architecture](architecture/overview.md) · [Latest release](https://github.com/JosephOIbrahim/Synapse/releases/latest)

This feature map was reviewed on **2026-09-28**. For the published version and its validation, use the [README banner](../README.md) and matching release notes. A documentation update does not qualify a new installer or a live scene.

## Recent changes

| Area | Available now | Read next |
|---|---|---|
| Identify | Select nodes, then **Identify** or `/identify`: a short local bubble beside each node, drawn over the network editor, from its type, changed parameters, state and the SideFX library. No model call, and nothing is written to the scene. | [Identify release](releases/v5.85.0.md), [overlay and help paths](releases/v5.86.0.md), [how it works](architecture/overview.md#identify). |
| Panel | Shared dark-gray/coral styling, welcome motion, inset footer controls and a taller prompt with **Resize**. | [Panel release](releases/v5.83.0.md), [resize and library update](releases/v5.84.0.md), [shorter Resize label](releases/v5.84.1.md). |
| JEV / TypeSafe | Discoverable key setup with masked entry and explicit session save/clear. Ranking and routing measurement remain optional. | [Key setup](getting-started/jev-setup.md), [JEV release](releases/v5.84.2.md). |
| World Labs | Artist-triggered import of an existing API-accessible world or supported local Gaussian PLY. | [Import flow and limits](architecture/overview.md#world-labs-import). |
| SideFX help | Resumable installed-help/Markdown ingestion, published SQLite search generations and bounded local Scout retrieval. | [Build and connect](studio/SIDEFX_LIBRARY.md). |

**Installation:** the current release, **v5.94.0**, is a source release. The latest Windows Setup is **v5.86.0**; it contains the changes above but not the changes in v5.87.0 through v5.94.0. See [installation](getting-started/installation.md).

**Validation:** [v5.85.0](releases/v5.85.0.md) records live Identify gates in Houdini 22.0.400 and two independent reviews. [v5.86.0](releases/v5.86.0.md) records the Windows Setup qualification. [v5.87.0](releases/v5.87.0.md) records live MCP session, read-only and Identify checks. [v5.88.0](releases/v5.88.0.md) records the tests for failed calls flagged as errors and for the readiness check; it was not checked live in Houdini. [v5.89.0](releases/v5.89.0.md) records a live grounded import of a local Marble export and a Karma XPU frame of it, rendered, decoded and verified through the render workspace. [v5.90.0](releases/v5.90.0.md) records the workstation profile rendering the same scene with the GPU taking most of the samples, and the Render row opening the render workspace live. [v5.91.0](releases/v5.91.0.md) records a live one-call insertion of two lights between existing LOP nodes on the demo scene, with the new nodes' error badges checked clean. [v5.92.0](releases/v5.92.0.md) records three H22 Solaris workflows (Scatter Instances, a Karma blocker light filter and Render Pass LOPs) built by the panel agent in nine of nine headless runs. [v5.92.1](releases/v5.92.1.md) records a forced round limit ending a turn in words and the corrected message of a failed build, both headless. [v5.93.0](releases/v5.93.0.md) records a camera's move measured and its path drawn in the demo scene: live in hython, through the panel agent in twelve of twelve headless runs, and from the panel's Spatial control in a recorded GUI check that the build harness drove. [v5.93.1](releases/v5.93.1.md) records the read saying whether the camera's path is drawn, the path's undo step named in words, and a receipt going after a hand undo, all in hython or with the panel offscreen; the undo step's name and the receipt going were then seen in the GUI on 3 October. [v5.93.2](releases/v5.93.2.md) records the panel's tool calls no longer waiting two seconds each, measured in the GUI, and two changes not seen there: an up-facing mask in the Scatter Instances recipe, checked in hython, and a memory card that no longer shows a knowledge article; both were then seen in the GUI the same day. [v5.93.3](releases/v5.93.3.md) records that recipe's mask tightened to near-level ground, measured in hython and not seen in the GUI. [v5.94.0](releases/v5.94.0.md) records the Scatter request building that recipe as written through a one-call resolver, and a scene's landing record coming back through project setup, each seen once in the GUI; its other changes are unit-tested and not exercised in Houdini. GitHub CI checks stock Python on Linux, macOS and Windows; the GitHub release links the run for its exact commit. None of these establishes an authenticated World Labs import.

**Known gaps remain:** short docks at high UI scale can overflow, the measured SideFX download has missing pages, and alternate Houdini themes lack qualification. See the [inherited release limits](releases/v5.84.1.md#validation-and-limits). The first save of an untitled scene can also freeze Houdini for minutes while memory is copied; the [v5.85.0 limits](releases/v5.85.0.md#validation-and-limits) cover that and Identify.

## Artist control

The default panel worker mode is `standard`. It allows classified reads and edits, plus explicitly permitted composite builders. It refuses higher-risk tools such as node deletion, arbitrary Python/VEX, rendering, exporting and PDG cooking. Unknown tools fail closed.

The opt-in `proposal` mode narrows the worker to reads, knowledge tools and declared proposals. It does not grant direct graph mutation.

**There is no universal interactive approval gate.** Production bridge admission uses nonblocking auto-approval. Panel restrictions are separate, and direct WebSocket handlers do not inherit them. The existing blocking bridge approval poll would deadlock the Houdini GUI if attached there.

Keep external bridge use on a single-user local machine. Read the [permission map](architecture/overview.md#permission-and-undo-boundaries) and [MCP authentication guide](mcp/SETUP.md) before connecting clients.

Sources: [worker policy](../python/synapse/panel/worker_policy.py), [bridge adapter](../python/synapse/panel/bridge_adapter.py), [consent regression tests](../tests/test_panel_consent_no_freeze.py).

## Undo, Stop and rendering

| Control | Limit to remember |
|---|---|
| Undo | Reverses supported recorded scene operations, not a conversation or files written to disk. |
| Failed build | Grouping does not guarantee rollback. Inspect partial nodes before undoing. |
| Stop | Stops further panel work; it does not prove an active cook or renderer has ended. |
| Cancel cook | Targets one known cooking node. |
| Emergency halt | Cancels cooking TOP networks under `/tasks`, `/obj`, `/stage`, `/out` and captures a report. Background renders are reported, not killed. |

The render workspace opens from **Render**, in the last row of the panel footer beside **Identify** and **Spatial**, or from Commands and `/render`. Validate the resulting frames: a file's existence alone does not prove a complete render.

[Stop controls](../README.md#three-ways-to-stop) · [Render operator guide](render-freeze-operator-card.md) · [Farm implementation](../python/synapse/farm)

## Optional services and knowledge

- **JEV:** saving a key does not authenticate it, enable assistance or grant data permission. Session keys expire when Houdini closes. Ranking prepares editable suggestions; routing measurement does not change the generation model. [Setup and data boundaries](getting-started/jev-setup.md).
- **World Labs:** the shipped action imports existing worlds; it does not generate them. Local import needs a supported Gaussian PLY. Direct SPZ, mesh GLB and plain-point PLY are unsupported. API access, units, grounding and rendered appearance need their own checks. [Import boundaries](architecture/overview.md#world-labs-import).
- **SideFX:** library searches do not download or build documentation. Ingestion runs separately; partial web fetches remain visible. Documentation is evidence about an API, not proof that the symbol exists in the running build. [Coverage definitions](studio/SIDEFX_LIBRARY.md#stored-material-and-coverage).

Runtime symbol membership is determined by the [introspected table](../python/synapse/cognitive/tools/data/h22_symbol_table.json); node references use the [build-specific catalogue](../rag/catalog/h22.0.400). Installed packages and GUI-only APIs affect that evidence. Newer documentation does not certify an older runtime.

## Memory and suggestions

Configured stores and scene/project notes retain context. A returned record ID alone does not prove persistence across a restart; secondary writes can fail independently.

The optional memory LOOP observes eligible operations. Its forecast concerns a narrow handler outcome, not image quality or the artist's next node. Unknown results remain unknown; observation recovery does not replay scene actions.

Stage 0 offers a checked lookdev record as editable prompt text. It needs an existing project store and a compatible imported record. Exact SYNAPSE version matching can produce `NO_MATCH` after an upgrade; retained records need a matching rehearsal/import.

[Storage and recall](architecture/overview.md#project-and-scene-memory) · [LOOP setup](MEMORY_LOOP_REPAIR.md) · [Stage 0 guide](development/rsi_stage0.md)

Earlier memory investigations include degraded-store recovery, same-second ID collisions and pre-migration plaintext/mirror-only records. They are retained in the [dated status snapshot](https://github.com/JosephOIbrahim/Synapse/blob/322c50bd4a9d682d44f52b61c10ba5a13bd5b278/docs/status.md#memory-and-suggestions). This documentation refresh does not close those investigations.

## Direction, not shipped capability

General predictive node-network creation, frontier-model Computer Use and full recursive self-improvement remain development directions. Their intended artist controls are described in [INTENT.md](../INTENT.md).
