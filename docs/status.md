# Current status and limits

[Back to README](../README.md) · [Architecture](architecture/overview.md) · [Latest release](https://github.com/JosephOIbrahim/Synapse/releases/latest)

This feature map was reviewed on **2026-09-24**. For the published version and its validation, use the [README banner](../README.md) and matching release notes. A documentation update does not qualify a new installer or a live scene.

## Recent changes

| Area | Available now | Read next |
|---|---|---|
| Panel | Shared dark-gray/coral styling, welcome motion, inset footer controls and a taller prompt with **Resize**. | [Panel release](releases/v5.83.0.md), [resize and library update](releases/v5.84.0.md), [shorter Resize label](releases/v5.84.1.md). |
| JEV / TypeSafe | Discoverable key setup with masked entry and explicit session save/clear. Ranking and routing measurement remain optional. | [Key setup](getting-started/jev-setup.md), [JEV release](releases/v5.84.2.md). |
| World Labs | Artist-triggered import of an existing API-accessible world or supported local Gaussian PLY. | [Import flow and limits](architecture/overview.md#world-labs-import). |
| SideFX help | Resumable installed-help/Markdown ingestion, published SQLite search generations and bounded local Scout retrieval. | [Build and connect](studio/SIDEFX_LIBRARY.md). |

**Installation:** the current release is source-only. Windows Setup remains the older **v5.75.2** package. It does not contain the recent changes above. Use [source installation](getting-started/installation.md#source-installation) for the current version.

**Validation:** [v5.84.2](releases/v5.84.2.md) records targeted native checks. Its [GitHub CI run](https://github.com/JosephOIbrahim/Synapse/actions/runs/36061873013) checks stock Python on Linux and macOS. Neither establishes an authenticated World Labs import, a Karma beauty render or a new Windows installer.

**Known gaps remain:** short docks at high UI scale can overflow, the measured SideFX download has missing pages, and alternate Houdini themes lack qualification. See the [inherited release limits](releases/v5.84.1.md#validation-and-limits).

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

The render farm remains available even though the panel's footer Render shortcut was removed. Validate the resulting frames: a file's existence alone does not prove a complete render.

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
