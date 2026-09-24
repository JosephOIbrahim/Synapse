# How SYNAPSE works

[Back to README](../../README.md) · [Current limits](../status.md) · [Artist intent](../../INTENT.md)

These diagrams describe implemented behavior. Each section links to its source. Future modes in `INTENT.md` are not implied by an arrow here.

| Follow a workflow | Start here |
|---|---|
| A model calls a tool | [Execution paths](#execution-paths) |
| JEV offers advice | [JEV assistance](#jev-assistance) |
| A Marble world enters Houdini | [World Labs import](#world-labs-import) |
| Scout searches SideFX help | [Library ingestion and lookup](../studio/SIDEFX_LIBRARY.md#ingestion-and-lookup) |
| A project decision is remembered | [Memory](#project-and-scene-memory) |
| A build becomes a release | [Publication](#release-process) |

## Artist workflow

The artist chooses a model, a task and the permitted data destination. The panel worker applies its tool policy, then shows results, refusals or uncertainty. The artist inspects and edits the resulting scene.

Sources: [panel](../../python/synapse/panel/synapse_panel.py), [connections](../../python/synapse/panel/connections.py), [worker policy](../../python/synapse/panel/worker_policy.py).

## Execution paths

HTTP `/mcp` and WebSocket `/synapse` share one local Houdini server. **The connection determines the dispatch path.** Being inside Houdini does not remove the transport.

### Panel and HTTP clients

```mermaid
flowchart TD
    accTitle: HTTP dispatch separates scene mutations from other tools
    accDescr: Panel calls pass worker policy before HTTP dispatch. External HTTP clients enter dispatch directly. Ordinary scene mutations use the bridge; reads, farm controls and Doctor have separate routes.
    P["Panel worker"] --> W["Worker policy"]
    W --> H["HTTP /mcp"]
    E["External HTTP client"] --> H
    H -->|"scene mutation"| B["Execution bridge"]
    H -->|"read"| R["Read handler"]
    H -->|"farm control or Doctor"| D["Separate dispatch route"]
    B --> S["Main-thread scene action<br/>and operation receipt"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    class H,B synapse
```

Read-classified tools skip the mutation bridge. Farm controls use their own admission and job I/O; Doctor uses its own off-main handler path. Houdini API access still belongs on the main thread.

If bridge imports are unavailable, non-farm handlers can fall back to direct dispatch without bridge wrapping. Farm controls fail closed in that case.

**Cancel cook** and **Emergency halt** are direct artist actions. They dispatch off the UI thread without asking a model. Their re-entry guards are per tool, so one does not silently swallow the other.

Sources: [HTTP dispatch](../../python/synapse/mcp/tools.py), [HTTP server](../../python/synapse/mcp/server.py), [bridge adapter](../../python/synapse/panel/bridge_adapter.py), [direct safety controls](../../python/synapse/panel/direct_tool.py).

### Configured stdio and WebSocket clients

```mermaid
flowchart TD
    accTitle: Stdio forwards Houdini operations over WebSocket
    accDescr: The configured stdio MCP server handles local knowledge tools locally. It forwards Houdini operations over WebSocket to direct handlers, which do not use the HTTP execution bridge.
    C["Configured stdio client"] --> A["mcp_server.py"]
    A -->|"local knowledge tool"| L["Local response<br/>for example, Scout"]
    A -->|"Houdini operation"| W["WebSocket /synapse"]
    X["Direct WebSocket client"] --> W
    W --> H["Direct handlers<br/>auth and RBAC"]
    H --> S["Main-thread Houdini API"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    class W,H synapse
```

These handlers do not inherit the panel worker's restrictions or bridge consent. Tracked mutations produce path-qualified, observe-only `IntegrityBlock` evidence; an unavailable check is not recorded as a passed check.

Sources: [configured client](../../.mcp.json), [stdio adapter](../../mcp_server.py), [handlers](../../python/synapse/server/handlers.py), [integrity envelope](../../python/synapse/server/integrity_envelope.py).

### A missing reply is not permission to repeat

```mermaid
flowchart TD
    accTitle: Transport uncertainty does not replay a scene action
    accDescr: A received reply is decoded. A request known not to have been sent may use the off-main local fallback. A possibly sent request with a lost reply returns an unknown outcome without redispatch.
    T["Panel tool request"] --> Q{"Transport result"}
    Q -->|"reply received"| R["Decode result and receipt"]
    Q -->|"definitely not sent"| F["Off-main local fallback"]
    Q -->|"possibly sent; reply lost"| U["Outcome unknown<br/>No redispatch"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    class T synapse
```

Source: [panel tool executor](../../python/synapse/panel/tool_executor.py).

### Permission and undo boundaries

| Boundary | What it controls |
|---|---|
| Model-data permission | Which provider may receive permitted task data. |
| Standard panel worker | Allows classified reads and edits; refuses higher-risk tools and unknown tools. |
| Optional `proposal` worker | Allows reads, knowledge tools and declared proposals; blocks direct mutation and graph instantiation. Default remains `standard`. |
| Production bridge | Uses nonblocking auto-approval at its admission layer. No interactive approval card is attached. |
| Direct WebSocket handlers | Their own authentication, RBAC and handler rules. They do not inherit panel policy. |
| Undo grouping | Groups supported scene edits. It does not reverse file/network effects or guarantee exception rollback. |

The bridge has a `HumanGate` API, but attaching its blocking approval poll to the GUI thread would deadlock the panel. Panel worker refusals are a separate control. External direct handlers can still execute Python/VEX under their own rules.

If construction fails halfway, inspect the partial scene before undoing. Native Undo/Redo traverse existing history outside a new undo group. Composition checks and operation receipts do not guarantee a rollback.

Use the external bridge on a **single-user local machine**. [MCP setup and authentication](../mcp/SETUP.md).

Sources: [worker policy](../../python/synapse/panel/worker_policy.py), [bridge construction](../../shared/bridge.py), [nonblocking consent tests](../../tests/test_panel_consent_no_freeze.py).

## JEV assistance

JEV is an optional adviser. A saved TypeSafe key, enabled preferences and the required permission are separate conditions. **Saving the key does not validate it or enable assistance.**

- **Rank selected-network actions** reorders available local suggestions. Selecting one appends editable prompt text; the artist decides when to send.
- **Measure routing** records shadow judgments. It does not switch the generation model or change its input.

Neither mode grants scene permission. If assistance is unavailable, its status must remain explicit.

[Key setup and flow diagram](../getting-started/jev-setup.md) · [action ranking](../../python/synapse/jev/selection_suggestions.py) · [routing measurement](../../python/synapse/jev/panel_routing.py) · [credentials](../../python/synapse/jev/credentials.py)

## World Labs import

Open **World Labs** beside **Cloud relay**. This imports an existing world or a supported local Gaussian `.ply`; it does not generate a world.

```mermaid
flowchart TD
    accTitle: Import an existing Marble world or a local Gaussian PLY
    accDescr: A local Gaussian PLY needs no API key. An accessible API world requires a World Labs connection, export and download. Validated files enter a new Houdini branch on the main thread. The artist inspects the result.
    L["Local Gaussian .ply<br/>No API key needed"] --> V["Validate supported PLY"]
    A["API-accessible world<br/>World Labs key required"] --> D["Export PLY and download<br/>in a background worker"]
    D --> V
    V --> H["Main-thread import<br/>New SOP and Solaris branch"]
    H --> I["Artist inspects the splat"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    classDef artist fill:#87CDA5,stroke:#87CDA5,color:#1F1F1F
    class H synapse
    class I artist
```

For remote import, enter a key in the masked field, choose **Connect World Labs**, then supply a world ID/Marble URL or select an API world. Choose a resolution and **Import world**. The list does not represent all Marble-app history.

The native route is File SOP → Bake GSplats → SOP Import LOP. It creates a separate branch and an undo group; it does not merge into existing stage wiring. On failure it attempts to remove its own new nodes and reports cleanup errors.

**Format limits:** Gaussian PLY supports constant color (DC-only) or a complete degree-3 spherical-harmonic layout. Partial harmonic layouts, ordinary point PLY, direct SPZ and mesh GLB are unsupported. Coordinates and units are preserved; metric scale, grounding and rendered appearance need inspection.

Closing the dialog prevents a late scene import; it does not abort a download already running. Authenticated remote access and a Karma beauty render were not established by the [v5.83.0 validation](../releases/v5.83.0.md#world-labs-import).

Sources: [dialog](../../python/synapse/panel/worldlabs_dialog.py), [API client](../../python/synapse/worldlabs/client.py), [native importer](../../python/synapse/worldlabs/importer.py).

## Project and scene memory

Recording a decision retains context for later recall. It does not reconstruct a network or authorize a scene change.

```mermaid
flowchart TD
    accTitle: Saved decisions, notes and advisory recall
    accDescr: A decision is written to the configured record store and may also produce a scene note. Typed recall and scene-note queries return advisory context. Moneta can also write a USD inspection mirror, separate from the storage owner.
    D["Record a decision"] --> S["Configured record store"]
    D -.->|"also attempts"| N["Scene / project notes"]
    S --> R["Typed recall"]
    N --> Q["Context queries"]
    R --> C["Advisory context<br/>for later work"]
    Q --> C
    S -.->|"Moneta secondary write"| V["USD inspection mirror"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    class S synapse
```

| Normal saved-project location | Role |
|---|---|
| `.synapse/memory.jsonl` | Default JSONL records; also a secondary copy with Moneta. |
| `.synapse/.moneta/snapshot.json` | Persistent source for the Moneta-backed record store. |
| `.synapse/.moneta/cortex_root.usda` | Inspectable USD mirror when Moneta and USD authoring are available. |
| `$HIP/claude/memory.md`, `$JOB/claude/project.md` | Human-readable scene and project notes. |

Unsaved scenes or unwritable projects can use fallback locations. `SYNAPSE_MEMORY_BACKEND=moneta` selects Moneta; initialization failure falls back to JSONL with the reason recorded. Closing the USD view does not control persistence.

`synapse_recall` retrieves typed records, defaulting to decisions. `synapse_memory_query` searches loaded scene/project content. `synapse_project_setup` loads starting context.

**An ID alone does not prove durability.** Snapshot, mirror and note writes are independent. Reopen the project and retrieve the record before claiming cross-session persistence. Ordinary saved decisions do not require the optional LOOP.

Sources: [recording and recall](../../python/synapse/session/tracker.py), [store selection](../../python/synapse/memory/store.py), [Moneta persistence](../../python/synapse/memory/moneta_store.py), [scene notes](../../python/synapse/memory/scene_memory.py), [context queries](../../python/synapse/server/handlers_memory.py).

## Memory LOOP

The optional LOOP observes eligible operations. **It does not choose the scene action.**

| Substrate | Role |
|---|---|
| Moneta | Recall project records; retain settled feedback. |
| Octavius | Compose allowlisted context in a private USD stage. |
| Hanish | Retain a pre-action forecast and terminal evidence. |

```mermaid
sequenceDiagram
    accTitle: Optional observation around an existing scene action
    accDescr: The host borrows memory, composes context and records a forecast before the authorized action. It then records the result and retains settled feedback. Missing evidence remains unknown.
    participant Host as SYNAPSE host
    participant M as Moneta
    participant O as Octavius
    participant H as Hanish
    participant S as Scene action
    Host->>M: Borrow owner and recall context
    M-->>Host: Bounded advisory records
    Host->>O: Compose allowlisted context
    O-->>Host: Context and provenance
    Host->>H: Record EXPOSED forecast
    H-->>Host: Durable acknowledgement
    Host->>S: Use existing authorized route
    S-->>Host: Result or uncertainty
    Host->>H: Submit measured observation
    H-->>Host: Outcome or pending status
    opt Outcome settled
        Host->>M: Retain feedback with stable identity
    end
```

Enable with `SYNAPSE_LOOP_ENABLED=1`. The main-thread host borrows the existing memory owner; workers carry data, not handles. Octavius and Hanish run in bounded subprocesses.

The forecast concerns whether a synchronous handler returns without explicit failure. It does not predict an artist's next node or image quality.

- Missing Octavius can yield narrower local context, with the limit named.
- Missing Moneta ownership can leave the action uninstrumented.
- Recovery cannot invent a pre-action forecast after dispatch.
- Unknown stays unknown. Recovery retries observations, never scene actions.

[Configuration and evidence](../MEMORY_LOOP_REPAIR.md) · [Host observer](../../python/synapse/host/memory_loop.py) · [Coordinator](../../python/synapse/loop/coordinator.py)

## Checked suggestions and future assistance

Stage 0 supports a fixed lookdev procedure with a developer-imported checked record and an existing Moneta owner. It is distinct from JEV's action ranking.

```mermaid
flowchart TD
    accTitle: A checked lookdev suggestion becomes an editable draft
    accDescr: A saved suggestion requires a matching scene, store and exact environment. A compatible record can be placed into a draft by the artist. Missing compatibility is reported without inventing a suggestion.
    A["Request saved suggestion"] --> B{"Compatible checked record?"}
    B -->|"yes"| C["Show settings<br/>and verification limits"]
    B -->|"no / unavailable"| N["Explain the reason"]
    C -->|"Use in prompt"| D["Append editable text"]
    C -->|"Dismiss"| X["Close suggestion"]
    D --> S["Artist edits and sends"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    classDef artist fill:#87CDA5,stroke:#87CDA5,color:#1F1F1F
    class C synapse
    class S artist
```

A record does not replay node paths or authorize a build. Compatibility includes the exact SYNAPSE version; upgrading requires a matching rehearsal/import. [Stage 0 guide](../development/rsi_stage0.md).

Predictive network generation, frontier-model Computer Use and recursive improvement remain later stages described in [INTENT.md](../../INTENT.md).

The [staged workflow guides](../../rag/corpus/guides) retain upstream provenance; that corpus is not yet served by the product. It is separate from the connected SideFX library.

## Release process

```mermaid
flowchart TD
    accTitle: Publish only the reviewed and checked release commit
    accDescr: Review changes and independent evidence, prepare an authorized version commit, push it, and require CI for that exact commit. Publish its tag and release only after the checks pass, then verify the remote references and release state.
    A["Review scoped changes<br/>and independent evidence"] --> B["Authorized version update<br/>and release commit"]
    B --> P["Push reviewed commit"]
    P --> C{"CI passes for this commit?"}
    C -->|"yes"| T["Verify and publish<br/>tag + GitHub release"]
    C -->|"no / unknown"| H["Hold publication;<br/>investigate"]
    T --> V["Verify remote commit,<br/>tag and release state"]
    classDef default fill:#282828,stroke:#555555,color:#E5E5E5
    classDef synapse fill:#FF7457,stroke:#FF7457,color:#1F1F1F
    class T synapse
```

[Version agreement](../../scripts/sync_version.py), [tag gate](../../scripts/tag_release.py) and [CI publication gate](../../scripts/release_ci_gate.py) support this workflow. Historical tags retain their original commits.

Stock-Python [CI](../../.github/workflows/ci.yml), native Houdini qualification and Windows installer checks prove different things. A source release does not imply a new Setup executable. Read the release's recorded limits.

[Repository metadata](../../.github/repository-metadata.json) records desired GitHub topics and description; a maintainer must apply them. The file does not configure GitHub automatically.
