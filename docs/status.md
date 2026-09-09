# Current status and limits

[Back to README](../README.md) · [Architecture](architecture/overview.md)

This guide separates shipped behavior, optional scaffolds and future work.
It is not a claim that every feature has been exercised in a fresh live session.

## What the latest changes cover

The [v5.67.3 reliability release](https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.67.3)
contains the panel, Ollama discovery, native history, transport and memory
recovery repairs. v5.67.4 updates documentation and repository metadata.

The v5.67.3 release record reports **8,614 stock tests passed with 415 explicit
skips**, plus **433 focused native checks** with one stdio case deselected and
covered by stock Python. These selections overlap. Native means Houdini
22.0.400's Python/Qt/USD with isolated fixtures; it does not mean a new live demo
or final render was qualified. Its [four CI configurations](https://github.com/JosephOIbrahim/Synapse/actions/runs/34345414233)
also passed the explicit Moneta backend/environment steps.

For subsequent commits, read the [current CI run](https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml)
and the matching [release notes](https://github.com/JosephOIbrahim/Synapse/releases).

## Artist control

Normal panel chat checks model-data permissions and restricts available tools.
External HTTP MCP and direct WebSocket clients have different boundaries.
The production bridge's optional `HumanGate` API is not wired into every route;
universal per-operation approval is not a shipped guarantee.

[Source-backed permission map](architecture/overview.md#permission-and-undo-boundaries)

## Undo, Stop and rendering

- **Undo groups operations.** It does not promise a whole-conversation reversal or recovery of file/network effects.
- **A failed build may leave partial nodes.** Some bridge failures attempt guarded rollback; grouping alone does not guarantee that recovery.
- **Stop is a request to stop further work.** It is not evidence that an in-flight cook or external renderer has ended.
- **Validate render outputs.** File existence alone does not prove a complete frame. Historical render investigations, including interrupted mantra output, remain in the [render operator guide](render-freeze-operator-card.md).
- **TOPs/render-farm recovery work remains separate.** The [repair branch](https://github.com/JosephOIbrahim/Synapse/tree/fix/cto-render-20260908) is not included in this documentation release.

## Memory and suggestions

The three-substrate LOOP is opt-in. Moneta owns retained project records,
Octavius composes private context, and Hanish owns forecast/outcome evidence.
The forecast measures a narrow handler outcome; it is not predictive modeling.

Stage 0 recalls one compatible, checked lookdev procedure on request and offers
editable prompt text. It requires an existing project store and a developer-imported
record. It does not train a model, build a library by itself, or change the scene
when memory is recalled.

**Version upgrades:** exact SYNAPSE version matching can produce `NO_MATCH` for an
older experience. Records are not erased; use a matching rehearsal/import.

[LOOP configuration](MEMORY_LOOP_REPAIR.md) · [Stage 0 guide](development/rsi_stage0.md)

## Knowledge and qualification

Houdini symbol/node references are build-aware. Legacy H21 workflow prose and
newer, explicitly sourced H22 notes coexist; an H22 reference does not certify
every generated workflow. Inspect parameters and resulting scenes on the running
build. Rob Pieke reference intake preserves lecture-source status and does not
turn a transcript into a checked procedure.

See the [knowledge intake record](MEMORY_LOOP_REPAIR.md#solaris-reference-intake).
Older measurements and open investigations remain in the
[previous README](https://github.com/JosephOIbrahim/Synapse/blob/v5.67.3/README.md#known-limitations)
and [review archive](reviews). Their dates and scope matter; this documentation
refresh does not silently close those investigations.

## Direction, not shipped capability

General predictive node-network creation, frontier-model Computer Use, and full
recursive self-improvement remain development directions. Their intended controls
are defined in [INTENT.md](../INTENT.md): the artist chooses when assistance engages,
its scope, and when to take over.
