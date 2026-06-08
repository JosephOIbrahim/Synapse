<p align="center">
  <img src="assets/synapse_logo.png" alt="Synapse" width="400"/>
</p>

<h3 align="center"><strong>Inside-out agent substrate for Houdini.</strong></h3>

<p align="center"><em>Talk to Houdini in plain English — it builds in your live scene.</em></p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="python/synapse/cognitive/dispatcher.py"><img src="https://img.shields.io/badge/dispatcher-Strangler%20Fig-1e293b.svg" alt="Dispatcher"></a>
  <a href="python/synapse/host/daemon.py"><img src="https://img.shields.io/badge/daemon-in--process-f59e0b.svg" alt="Daemon"></a>
  <a href="python/synapse/host/tops_bridge.py"><img src="https://img.shields.io/badge/perception-scaffolded-3b82f6.svg" alt="Perception"></a>
  <a href="python/synapse/memory/moneta_store.py"><img src="https://img.shields.io/badge/memory-Moneta%20backend-8b5cf6.svg" alt="Memory"></a>
  <a href="python/synapse/panel/synapse_panel.py"><img src="https://img.shields.io/badge/artist%20panel-chat%20%E2%86%92%20build-22c55e.svg" alt="Artist panel"></a>
  <a href="tests"><img src="https://img.shields.io/badge/tests-3168%20passing-brightgreen.svg" alt="Tests"></a>
</p>

---

## The artist surface — talk to Houdini, it builds

SYNAPSE's whole point is to be *used*. The payoff is a docked **SYNAPSE panel**: the artist types a request in plain language and SYNAPSE builds it in the live scene — chat in, nodes out, in-process. **"make a box" → a real geo node, confirmed in graphical Houdini 21.0.671 (2026-06-01).**

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    ART["Artist<br/>'make a box'"]:::artist --> PANEL["SYNAPSE panel<br/>rail + 3 faces, in-process"]:::panel
    PANEL --> LOOP["Agent loop<br/>streams Claude + 110 tools"]:::panel
    LOOP -->|"tool_use<br/>(e.g. execute_python)"| EXEC["Tool executor<br/>main thread"]:::panel
    EXEC --> BR["SynapseHandler<br/>undo-wrapped &middot; main-thread &middot; integrity"]:::bridge
    BR -->|in-process call| HOU[("hou.*<br/>node created")]:::hou
    LOOP -.->|state| FACE["state&rarr;face controller<br/>idle&middot;Direct / working&middot;Work / done&middot;Review"]:::obs
    BR -.->|telemetry &middot; provenance| FACE
    FACE -.->|surfaces the right face| PANEL
    classDef artist fill:#334155,stroke:#f59e0b,color:#f1f5f9
    classDef panel fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef bridge fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef hou fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef obs fill:#1e293b,stroke:#8b5cf6,color:#f1f5f9
```

The panel was rebuilt from first principles ("the Pentagram pass") over a thin `.pypanel` loader: one vendored design system (native Houdini 21 greys, a cool/warm dual accent, the signal blue `#8FB3D9` kept as the *one* chromatic event). A persistent **rail** keeps termination, live state, and bounded cost on screen; the surface itself is **three faces driven by a state→face controller** — **Direct** (speaker-by-type chat, agent results as artifact chips), **Work** (the walk-away glance: a cook preview, plan-with-progress, and per-agent health), and **Review** (the render is the hero — a taut verdict, credited provenance, quality flags, and a gated commit). A **Ctrl+K palette lets you self-identify two ways** — by verb (build / fix / explain / optimize / render) × context (SOP / LOP / COP / Karma / USD). Every mutation the agent makes is **undo-wrapped, thread-safe, and integrity-verified** — inline in the handlers on the live in-process path (the `LosslessExecutionBridge` is the integrity/audit layer, on the external-MCP path) — so the agent's hands stay structurally reversible. Consent is **non-blocking for artist-initiated work** (your chat request *is* the consent; autonomous / external-MCP operations still gate through `HumanGate`); the gate previously polled the GUI thread and dead-locked Houdini until that was root-caused live and fixed. The Work and Review faces surface a **recursive-observability** readout — per-agent success rates plus a recommendation history that persists across restarts and escalates if the same issue recurs.

---

## How it works: outside-in → inside-out

The standard pattern for AI-driven DCC work runs the agent in a separate process and reaches into the DCC through a bridge — WebSocket, RPC, stdio, a subprocess. The DCC is a service the agent calls. That shape has a ceiling: every interaction is a round-trip, every tool is a marshalling problem, and the agent never actually lives inside the creative environment.

SYNAPSE inverts that. The Claude Agent SDK runs **inside Houdini's own Python interpreter**, dispatching tools as direct in-process calls against `hou`. The WebSocket survives as a thin JSON-RPC adapter for external clients during migration, but the core loop is native. Same refactor pattern composes across the portfolio to **Moneta** (Nuke), **Octavius**, and the **Cognitive Bridge**.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    subgraph OUT ["Outside-in &mdash; the standard pattern"]
        direction LR
        A1["Agent process"] -.WebSocket / RPC.-> H1[("Houdini<br/>hou.*")]
    end
    subgraph IN ["Inside-out &mdash; SYNAPSE"]
        direction LR
        H2[("Houdini<br/>hou.*")]
        subgraph DAEMON ["Agent daemon (thread)"]
            A2["Agent SDK"] --> D["Dispatcher"]
        end
        D -- in-process call --> H2
    end
    OUT ~~~ IN
```

The flip changes more than transport. Tools become direct calls. Errors keep their stack trace. And — the part Sprint 3 is wiring now — **events flow the other way**. Houdini taps the agent on the shoulder when something cooks, instead of the agent polling to ask. See [Perception channel](#perception-channel--two-bridges-scaffolded) below.

---

## Architecture

### Inside-out runtime

Once the daemon boots inside graphical Houdini, three threads are in play: **main** (Qt event loop + `hou.*`), **daemon** (the agent loop), and a **short-lived worker** for each main-thread dispatch (so the daemon thread can enforce a timeout on blocking `hdefereval` calls). Tools are pure-Python functions under `synapse.cognitive.tools.*` behind a `Dispatcher` interface. The Dispatcher composes `suppress_modal_dialogs()` around `main_thread_exec()` so every tool call gets a narrowly-scoped dialog-suppression window — the artist's own UI stays untouched outside tool dispatches.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart TB
    subgraph HOU ["Graphical Houdini process"]
        direction TB
        subgraph MT ["Main thread &mdash; Qt event loop + hou.*"]
            HUI["Houdini UI"]
            HAPI["hou.* API surface"]
        end
        subgraph DT ["Daemon thread &mdash; synapse.host.daemon"]
            AL["Agent SDK loop<br/>(anthropic)"] --> DISP["Dispatcher<br/>synapse.cognitive.dispatcher"]
            DISP --> EXEC["main_thread_exec<br/>+ suppress_modal_dialogs"]
        end
        subgraph COG ["Cognitive layer &mdash; zero hou imports"]
            TOOLS["synapse.cognitive.tools.*<br/>(inspect_stage, ...)"]
        end
        EXEC -. hdefereval .-> HAPI
        DISP -- resolves --> TOOLS
        TOOLS -. pure Python .-> HAPI
    end
    EXT["External MCP clients<br/>(Claude Desktop, CLI)"] -.WS JSON-RPC.-> DISP
```

The `cognitive/` vs `host/` code split is structural. `synapse.cognitive.*` is pure Python, zero `hou` imports, enforced by a grep-based lint test at CI time (`tests/test_cognitive_boundary.py`). `synapse.host.*` is Houdini-specific — `hou`, `hdefereval`, Qt thread marshaling — and gets swapped per DCC. The substrate composes.

### Perception channel — two bridges scaffolded

Sprint 3 is wiring the agent's first **eyes**. The Dispatcher gives the agent hands; the Agent SDK gives it a brain; the perception channel lets it see what Houdini sees, in the same heartbeat as the scheduler. Two bridges compose to deliver that:

- **`TopsEventBridge`** (Spike 3.1, Phase A) — registers a `pdg` event handler against each TOP network's live `pdg.GraphContext`, surfaces 7 cook + work-item events as typed `TopsEvent` payloads. The handler reads `pdg.*` properties only — no `hou.*` calls inside — because PDG events **fire on a worker thread** (confirmed live by the Spike 3.3 prestage; the exact opposite of `hou.hipFile`, which fires on main). That shape isn't precautionary — it's load-bearing: a blocking or `hou.*`-touching handler off-main would reintroduce the Spike 2.4 deadlock.
- **`SceneLoadBridge`** (Spike 3.2, Phase B) — subscribes to `hou.hipFile.AfterLoad` and orchestrates an injected `TopsEventBridge`'s `cool_all` / `warm_all` cycle on every scene load. Mile 4's empirical audit captured all four hipFile events firing on `MainThread` (`is_main_thread=True`), so the AfterLoad handler calls `hou.*` and `tops_bridge.*` directly — **no `hdefereval` marshaling**. Adding it would be cargo-cult dispatch from main thread back to itself.

Composition, not inheritance: `SceneLoadBridge(tops_bridge=...)`. Each class keeps a single responsibility, and the relationship is testable end-to-end with mocks.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart TB
    subgraph SCENE ["Houdini scene lifecycle"]
        HIP["hou.hipFile<br/>events"]
    end
    subgraph PDG ["PDG cook lifecycle"]
        GC["pdg.GraphContext<br/>events"]
    end
    subgraph BRIDGE ["synapse.host.* (in-process)"]
        SLB["SceneLoadBridge<br/>scene_load_bridge.py"]
        TEB["TopsEventBridge<br/>tops_bridge.py"]
        SLB -- "composition<br/>(tops_bridge=...)" --> TEB
    end
    subgraph COG ["synapse.cognitive.*"]
        CB["perception_callback"]
    end
    HIP -- AfterLoad --> SLB
    GC -- "CookComplete<br/>WorkItemResult<br/>+5 more" --> TEB
    TEB --> CB
```

The end-to-end event flow when an artist opens a scene and cooks a TOP network:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569','actorBkg':'#1e293b','actorTextColor':'#f1f5f9','actorBorder':'#0f172a','signalColor':'#f59e0b','signalTextColor':'#f1f5f9','noteBkgColor':'#334155','noteTextColor':'#f1f5f9','sequenceNumberColor':'#f1f5f9','labelBoxBkgColor':'#1e293b','labelTextColor':'#f1f5f9','loopTextColor':'#f1f5f9'}}}%%
sequenceDiagram
    autonumber
    actor Artist
    participant Main as Main thread<br/>(Qt + hou.*)
    participant SLB as SceneLoadBridge
    participant TEB as TopsEventBridge
    participant Cook as Cook thread
    participant Agent as Agent perception

    Artist->>Main: File → Open scene.hip
    Main->>SLB: hou.hipFile event:<br/>BeforeLoad → BeforeClear →<br/>AfterClear → AfterLoad
    Note over SLB: Filter holds — only<br/>AfterLoad triggers warm
    SLB->>TEB: cool_all() (stale subs)
    SLB->>TEB: warm_all() (walk topnets)
    Note over SLB,TEB: per-topnet: register a pdg<br/>event handler (raw callable) against<br/>the live GraphContext
    Artist->>Main: cook TOP network
    Main->>Cook: dispatch graph cook
    Cook->>TEB: pdg.Event on a WORKER thread<br/>WorkItemStateChange
    Note over Cook,TEB: handler = pdg.* reads only;<br/>derive complete: currentState == CookedSuccess
    TEB->>Agent: TopsEvent via non-blocking enqueue
```

**State today:** scaffolded and tested in standalone mode (no live Houdini). The two bridges have **71 tests passing** between them — 47 across `tests/test_tops_bridge.py` (Spike 3.1 basic + hostile) and 24 across `tests/test_scene_load_bridge.py` (Spike 3.2 basic + hostile). Live cook integration — the *first* real `pdg.Event` reaching the agent's perception layer in graphical Houdini — lands at Mile 5 (Spike 3.3).

**Spike 3.3 prestage** (design-only — [`docs/sprint3/spike_3_3_recon.md`](docs/sprint3/spike_3_3_recon.md)): a `dir()`-over-docs recon plus one operator-authorized scratch cook **confirmed PDG events fire on a worker thread** and **caught four event-model bugs in the scaffolds before any live build** — `event.workItem` is phantom (payload silently empty); `workitem.complete` has no enum and must be derived from `WorkItemStateChange` + `currentState == CookedSuccess` (a *static* generator emits neither, so the gate demo needs a real processor); `pdg.Node` exposes `.name`, not `.path()`; and `pdg.PyEventHandler(callback)` has **no constructor**, so the scaffold's handler factory hard-crashes on the first `warm()` — the correct API registers a raw callable, and `addEventHandler` returns the wrapper. All four are documented-not-fixed; fixes land at Spike 3.3 M1.

### Portfolio thesis

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart TB
    subgraph SUB ["Cognitive substrate &mdash; USD + LIVRPS"]
        USD[("Session stages<br/>Agent Asset stages<br/>Turn history (append-only)<br/>Rollouts (sibling prims)")]
    end
    subgraph HOSTS ["DCC hosts (inside-out)"]
        direction LR
        SYN["SYNAPSE<br/>(Houdini) &mdash; shipping"]
        MON["Moneta<br/>(Nuke) &mdash; planned"]
        OCT["Octavius<br/>&mdash; planned"]
    end
    CB["Cognitive Bridge<br/>peer-discovery + handoff"]
    SYN --- SUB
    MON --- SUB
    OCT --- SUB
    CB --- SUB
    SYN <-. peer .-> CB
    MON <-. peer .-> CB
    OCT <-. peer .-> CB
```

Each host ships its own `synapse.host.*` layer. The cognitive substrate — USD stage layout, LIVRPS composition semantics, the Dispatcher contract, the append-only turn history — is shared. When all three are up, they coordinate through the Bridge via filesystem peer discovery.

---

## Install

**Two paths, one repo.** *Artists* — the **5-minute setup** below gets you chatting with Houdini, no command line beyond a copy-paste or two. *Developers* who want the editable install + test suite: see [`docs/getting-started/installation.md`](docs/getting-started/installation.md).

Tested on **Windows 11 + Houdini 21.0.671**. macOS / Linux are the same steps, different path separators.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    DL["1 &middot; Download<br/>the SYNAPSE folder"]:::step --> REG["2 &middot; Run the installer<br/>(once)"]:::step
    REG --> KEY["3 &middot; Paste your API key<br/>(double-click the .bat)"]:::step
    KEY --> OPEN["4 &middot; Restart Houdini,<br/>open the SYNAPSE panel"]:::step
    OPEN --> CHAT["Type 'make a box'<br/>&rarr; it builds"]:::done
    classDef step fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef done fill:#334155,stroke:#22c55e,color:#f1f5f9
```

### 1 · Get the files

On GitHub, click the green **Code ▸ Download ZIP** and unzip it somewhere stable — e.g. `C:\Users\<you>\SYNAPSE`. *(Prefer git? `git clone https://github.com/JosephOIbrahim/Synapse.git C:\Users\%USERNAME%\SYNAPSE`.)*

### 2 · Tell Houdini about it (run once)

From inside the SYNAPSE folder, run the installer — it writes one small file into your Houdini prefs so the panel shows up on launch:

```powershell
python scripts/install_synapse_package.py
```

No Python on your PATH? Use the copy that ships inside Houdini:

```powershell
& "C:\Program Files\Side Effects Software\Houdini 21.0.671\bin\hython.exe" scripts/install_synapse_package.py
```

*(Add `--dry-run` to preview without writing anything.)*

### 3 · Paste your Anthropic API key

SYNAPSE talks to Claude, so it needs a key — make one at **console.anthropic.com** (it starts with `sk-ant-`). Then just **double-click `set_anthropic_key.bat`** in the SYNAPSE folder, paste the key, and press Enter. It remembers it for you.

### 4 · Restart Houdini and open the panel

Fully quit and reopen Houdini. Then **New Pane Tab ▸ SYNAPSE** (the ➕ on any pane edge). Type **"make a box"** and watch it appear in your scene.

That's the whole loop. Everything SYNAPSE does is an ordinary Houdini action — **Ctrl+Z undoes it** — and it asks first before anything destructive.

<details>
<summary><strong>If something's not working</strong></summary>

- **SYNAPSE isn't in the Pane Tab menu** → Houdini loads packages only at launch; fully restart it, and confirm the installer reported success.
- **"No API key" / the panel won't connect** → re-run `set_anthropic_key.bat`, then **relaunch Houdini from scratch** — on Windows a freshly-set key only reaches apps started *after* you set it. To check, run in Houdini's Python Shell: `import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))` — it should print `True`.
- **`ModuleNotFoundError: No module named 'synapse'`** → the installer prints the path it wired; confirm it points at the repo's `python/` directory, and that you restarted Houdini.

</details>

<details>
<summary><strong>Portable / no-install setup</strong></summary>

Skip the installer — the shipped [`packages/synapse.json`](packages/synapse.json) derives every path from `$HOUDINI_PACKAGE_PATH`, so nothing is hard-coded. Add the repo's `packages/` dir to Houdini's package search path in your `houdini.env`:

```
HOUDINI_PACKAGE_DIR = "$HOUDINI_PACKAGE_DIR;C:/path/to/Synapse/packages"
```

Restart Houdini afterward. The optional `MONETA_SRC` var (auto-set by the installer when a sibling `../Moneta` exists) enables the Moneta memory backend; without it SYNAPSE uses the default JSONL store.

</details>

<details>
<summary><strong>For developers — API-key options + daemon verification</strong></summary>

**Set the key as a system env var** instead of the `.bat`, if you prefer:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Relaunch Houdini after `setx` — the value only reaches processes started after. When SideFX ships a secure-credentials API in a future Houdini release, SYNAPSE's auth resolver picks it up automatically; confirmed **not present** in 21.0.671 (`dir(hou)` exposes only `secureSelectionOption`).

**Boot the daemon directly** in Houdini's Python Shell:

```python
from synapse.host.daemon import SynapseDaemon

daemon = SynapseDaemon()
daemon.start()
print("running:", daemon.is_running)
daemon.stop()
```

Healthy → prints `running: True` and stops cleanly. Common errors:
- **`DaemonBootError: hou.isUIAvailable() returned False`** → you're in headless `hython`, not graphical Houdini. The daemon refuses to boot in PDG / render-farm contexts (Fork-Bomb prevention). For tests, pass `boot_gate=False`.
- **`DaemonBootError: No Anthropic API key available`** → the key didn't land; relaunch Houdini from a fresh shell.
- **`DaemonBootError: anthropic SDK is not installed`** → shouldn't happen (vendored at `python/synapse/_vendor/`, prepended to `sys.path` on `import synapse`); confirm the vendored tree is intact (`ls python/synapse/_vendor/anthropic/`).

</details>

---

## Current capability + roadmap

### What's shipping today

| Layer | State |
|---|---|
| **Artist copilot panel** (chat → in-Houdini build, Ctrl+K palette over 110 tools, live observability) | Shipping. Every mutation undo-wrapped + main-thread-safe (inline in the handlers); "make a box" → node verified in graphical Houdini 21.0.671 (2026-06-01). |
| Cognitive substrate (Dispatcher + `AgentToolError` + cognitive/host split) | Shipping. Zero-hou boundary enforced by lint. |
| Agent SDK loop (Anthropic, cancel-event-aware, serializable tool errors) | Shipping. Mocked end-to-end tests green. |
| Daemon lifecycle (boot gate, auth resolver, dialog suppression, bootstrap locks) | Shipping. Windows `WindowsSelectorEventLoopPolicy` + `PYTHONNOUSERSITE` + no-runtime-pip all baked. |
| `TurnHandle` async result envelope (Spike 2.4) | Shipping. `submit_turn` returns a handle immediately; `submit_turn_blocking` for headless / non-main-thread callers. Deadlock-pinned by 31 unit tests + regression class. |
| Vendored Anthropic SDK | Shipping. 15 MB at `python/synapse/_vendor/`, Python 3.11 / win\_amd64 ABI lock. |
| **Perception channel — `TopsEventBridge`** (Spike 3.1) | Scaffolded. 47 tests (basic + hostile), standalone only. **Spike 3.3 prestage recon (2026-05-30) caught 4 event-model bugs before any live build** — phantom `event.workItem`, underived `workitem.complete`, `pdg.Node.name`-not-`.path()`, and a **`pdg.PyEventHandler(callback)` no-constructor crash on first `warm()`**. Fixes land at Spike 3.3 M1. See `docs/sprint3/spike_3_3_recon.md`. |
| **Perception channel — `SceneLoadBridge`** (Spike 3.2) | Scaffolded. 24 tests (basic + hostile). Composes a `TopsEventBridge`; auto-warm on `hou.hipFile.AfterLoad`. Prestage confirmed the main-thread delivery and flagged the `AfterMerge` blind spot + a scene-clear dead-context teardown risk (recon doc §2). |
| **Tools ported through the Dispatcher** | **1** — `synapse_inspect_stage` (flat `/stage` AST). |
| **Tools still on the Sprint 2 WebSocket path** | **111** — registry tools working in production, awaiting port (104 → 108 with the v5.9.0 SCOUT→FORGE additions, → 111 with the Solaris Compose Tier below). (Plus 6 group-info knowledge tools that don't need porting — they serve local content without Houdini.) |
| **Provenance & audit** — Tier-0 Floor hook + agent.usd Ledger | Shipping (v5.11.0). Every *mutating* op on the live `/synapse` handler path leaves a durable provenance record (`FloorGate` via `registry.invoke` across all 3 handler sites; bounded FIFO rotation). The **agent.usd Ledger** gives curated verdicts a canonical home — per-record JSON files (source of truth) + a composed `agent.usd` read-projection; the markdown Ledger backfills **lossless** (29 parsed, 0 fields dropped, mutation-pinned by a source-vs-parse oracle). |
| **Autonomous-worker tool allowlist** (security) | Shipping (v5.11.0). The panel worker is filtered by policy — read-only + `inform`-gated tools allowed; `execute_python` / `execute_vex` / `delete_node` / render **denied** by default (fail-closed); `SYNAPSE_WORKER_TOOL_MODE=unrestricted` opt-out. Closes the unfiltered-tool-access gap a CTO review flagged. |
| **Autonomy task provenance** | Shipping (v5.11.0). `create_task` + verification wired into `autonomous_render`, closing the loop to the already-live `suspend_all_tasks` consumer (which iterated an always-empty tasks group). A liveness recon proved only 2 of 5 dormant `agent.usd` writers had a real emit point — the other 3 stay deferred rather than fake their activation. |
| **Self-healing bridge** (resilience) | Shipping (v5.11.0). The WS server publishes its real bound port to `~/.synapse/bridge.json`; every client resolves *that* (freshest-wins, `9999` fallback) so a stale-port collision can never strand the bridge. **Verified live end-to-end** — `ping`→`pong`, panel loads (all 3 faces, v5.11.0), and a box created *through* the bridge cooked to 8 points / 6 faces while the Floor hook recorded the mutation (`origin=handler, ok`). |

The port pattern is mechanical and documented in `docs/crucible_protocol.md` + the `spike(1)` commit message. Every legacy tool gets:

1. A pure-Python function under `synapse.cognitive.tools.<name>` (zero `hou` imports).
2. A schema dict (description + JSON Schema) registered alongside the function.
3. The WS adapter branch in `mcp_server.py` swapped from `synapse_inspect_stage`-style direct dispatch to `dispatcher.execute('<name>', kwargs)`.

### v5.11.0 — Two-tier provenance: the Floor hook + the agent.usd Ledger

Every action SYNAPSE takes is now recorded, on two tiers, on the path that actually runs. **Tier-0** is the **Floor hook**: a single `FloorGate` that every command-handler invocation routes through (`CommandHandlerRegistry.invoke()` across all three live sites — direct `handle`, batch sub-ops, and the autonomy adapter), writing one durable, atomic provenance record per *mutating* op (read-only ops are skipped) to `.synapse/provenance/` under a bounded FIFO cap. **Tier-1** is the **agent.usd Ledger**: the curated verdicts that used to live only in markdown now have a canonical home — one immutable `<kind>_<ts>_<sha8>.json` per record (the source of truth) composed into an `agent.usd` `/SYNAPSE/agent/ledger/` read-projection. The markdown Ledger backfills **losslessly** — a source-vs-parse oracle is mutation-pinned: drop the field catch-all and 33 tokens vanish, failing the test.

This is **audit, not admission control** — Tier-0 records what happened; it never gates. (The bridge's consent / `IntegrityBlock` layer is the `/mcp` audit path; finding §0.8 established it is *not* on the live `/synapse` transport — so the docs no longer claim it is.) Two adjacent landings shipped alongside: an **autonomous-worker tool allowlist** (the panel worker can no longer reach `execute_python` / `execute_vex` / destructive tools by default — fail-closed, env opt-out) and **autonomy task provenance** (`autonomous_render` now feeds the already-live `suspend_all_tasks` consumer, closing a real producer→consumer loop).

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart TB
    subgraph T0 ["Tier-0 &mdash; every mutating op (audit, never gates)"]
        direction TB
        WS["Live /synapse handler<br/>SynapseHandler.handle"] --> INV["registry.invoke<br/>handle · batch · autonomy"]
        INV --> GATE{"FloorGate.wrap<br/>read-only?"}
        GATE -- "read-only" --> SKIP["no record"]
        GATE -- "mutating" --> REC["provenance record<br/>op · digests · outcome · parent"]
        REC --> PDIR[".synapse/provenance/<br/>atomic write_report · FIFO cap"]
    end
    subgraph T1 ["Tier-1 &mdash; curated verdicts (the Ledger)"]
        direction TB
        VERD["verdict + verified_by<br/>(Confirmation · DeadEnd · DocConformance · ...)"] --> DEP["Ledger.deposit"]
        DEP --> FILES[".synapse/ledger/&lt;kind&gt;_&lt;ts&gt;_&lt;sha8&gt;.json<br/>source of truth"]
        FILES --> LUSD["agent.usd /SYNAPSE/agent/ledger/<br/>composed read-projection"]
        MD["docs/SCIENCE_HARNESS_LEDGER.md"] -. "lossless backfill (oracle-pinned)" .-> DEP
    end
```

**Honest by construction.** A 5-agent liveness recon checked every proposed emit point *before* wiring — and found 3 of the 5 dormant `agent.usd` writers had no live producer (the MOE router runs only in tests, agent handoffs don't exist on the live path, and the bridge's `IntegrityBlock` self-asserts its anchors). Those stay **deferred**, recorded in the RFC, rather than wired to dormant code to manufacture the *appearance* of activation.

### Self-healing bridge — verified end-to-end

The MCP/WS bridge had a recurring failure: a stale Houdini holding `:9999` with a dead server left the live session's WS server failing over to a port the clients couldn't find. The server *already* tracked its real bound port (`_actual_port`); the gap was that every client was hardcoded to 9999. The fix makes the port **discoverable** — on bind, the server atomically publishes `{host, port, pid, ts}` to a home-anchored sidecar (`~/.synapse/bridge.json`, `$SYNAPSE_BRIDGE_FILE` override); every client resolves *that*, freshest-writer-wins, with a hard fallback to `9999` / `$SYNAPSE_PORT` so a no-sidecar environment behaves byte-for-byte as before. A stale-port collision can never silently strand the bridge again.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    subgraph SRV ["Houdini &mdash; SynapseServer (on bind)"]
        direction TB
        BIND["bind: prefer 9999,<br/>fail over if taken"] --> PUB["publish_endpoint<br/>_actual_port, atomic write"]
    end
    PUB --> SIDE[("~/.synapse/bridge.json<br/>{host, port, pid, ts}")]
    subgraph CLI ["clients &mdash; MCP host · panel · dashboard"]
        direction TB
        RES["resolve_endpoint<br/>freshest-wins · 9999 fallback"] --> CONN["connect<br/>ws://host:port/synapse"]
    end
    SIDE -. "discoverable" .-> RES
    CONN --> OK["pong · panel loads · box cooks"]
```

**Proven live (2026-06-07).** End-to-end through the running bridge: `synapse_ping` → `{"pong":true}`; the panel built in-process (real `SynapsePanel`, all three faces `Direct · Work · Review`, v5.11.0); and a box created *via the bridge* cooked to **8 points / 6 faces / 1×1×1** — with the Floor hook's provenance record landing for each mutation (`create_node … origin=handler, outcome=ok`). The whole stack, confirmed in one live scene.

### v5.9.0 — SCOUT → FORGE: 7 verified capabilities

A read-only **SCOUT** recon cross-referenced the Houdini 21.0.671 capability surface against the live tool registry, surfaced 7 opportunities, and **V1-verified every one against the exact target build** (21.0.671 `hython`) before any code was written. A **FORGE** MOE agent team then built and unit-tested them, with **CRUCIBLE** adversarial review gating the merge. Registry **104 → 108 tools**:

- `houdini_set_payload_loadstate` — USD payload load/unload + activation
- `houdini_create_point_instancer` — `UsdGeom.PointInstancer` authoring
- `houdini_shot_render_ready` — shot-template composite orchestrator
- `cops_create_copnet` — modern Copernicus `copnet` (distinct from the legacy `cop2net` the existing COPs tools build on)
- `houdini_reference_usd` + `karma_visible`/`purpose`/`kind` — non-clobbering Karma-visibility metadata on import (completes the BL-008 advisory-only partial)
- `houdini_modify_usd_prim` + `instanceable`
- branch-aware, path-keyed upstream Karma-LOP discovery in the render walk

Plus bridge/panel hardening: read-only tool failures surface as JSON-RPC errors instead of success-with-`isError`, and the panel resolves the Anthropic key through the canonical auth layer with an actionable "set it + relaunch" message.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    S["SCOUT<br/>read-only recon<br/>RAG + codebase"] -->|7 opportunities<br/>V1-verified on 21.0.671| F["FORGE<br/>MOE agent team<br/>build + unit test"]
    F -->|diff| R["CRUCIBLE<br/>adversarial review"]
    R -->|fix-forward| F
    R -->|108 tools, green| P["PR 4<br/>shipped"]
    classDef scout fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef forge fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef cruc fill:#1e293b,stroke:#ef4444,color:#f1f5f9
    classDef gate fill:#334155,stroke:#22c55e,color:#f1f5f9
    class S scout
    class F forge
    class R cruc
    class P gate
```

Behavioral verification (Karma cook of `copnet`, EXR landing, USD editableStage round-trips) is deferred to a live 21.0.671 session.

### Solaris Compose Tier — 3 write/compose tools (PR #6)

The write/compose counterpart to the read-side inspector. Three MCP tools, every operation undo-wrapped + main-thread-safe, all `dir()`-confirmed-live on 21.0.671. Registry **108 → 111**:

- `synapse_solaris_shotsetup_karma_xpu` — builds a render-strongest department `sublayer` stack + camera + Karma `engine=xpu` render settings, with `synapse:*` provenance and an authored output path.
- `synapse_matlib_bind` — binds a MaterialX material to a prim set via `assignmaterial`, then verifies each binding with `ComputeBoundMaterial` and reports unmatched/unbound prims.
- `synapse_assess_render_ready` — read-only render-readiness report (rendersettings, camera, composition errors, materials bound, output path, AOVs, XPU compatibility), naming the offending prim per failed clause.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    SS["solaris_shotsetup_karma_xpu<br/>dept sublayer stack + camera<br/>Karma engine=xpu + provenance"]:::tool
    MB["matlib_bind<br/>MaterialX to prim set<br/>verify ComputeBoundMaterial"]:::tool
    AR["assess_render_ready<br/>read-only readiness report<br/>names the offending prim"]:::tool
    RENDER["render<br/>husk no-ops on Indie<br/>Karma flipbook verifies magenta"]:::gate
    BRIDGE["SynapseHandler<br/>undo + thread-safe + integrity"]:::bridge
    SS --> MB
    MB --> AR
    AR -->|greenlit| RENDER
    SS -.->|every op| BRIDGE
    MB -.-> BRIDGE
    AR -.-> BRIDGE
    classDef tool fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef gate fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef bridge fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
```

Five real bugs the SCOUT→FORGE discipline caught (the `usdrender` phantom, `sublayer` strongest-first ordering, `editableStage()`-outside-cook, the `productName` parm not authoring the prim, and an MRO name collision), plus the **BL-007 / BL-008 [REAL] close** — an end-to-end render confirm surfaced that **husk silently no-ops on Houdini Indie**, so the gold-standard EXR is license-blocked and the bound emissive material was verified via a Karma-interactive flipbook (magenta, not gray) instead. 49 standalone tests; see `forge/backlog/human_review.json` (BL-012…BL-017) and `scripts/verify_compose_render.py`.

---

### Memory substrate — Moneta vector engine (PR #14)

The inside-out thesis applied to memory. SYNAPSE's scene/decision memory carried two unreconciled stores (a JSONL entry store and a markdown scene-memory file), a metrics gauge wired to a dead accessor, and empty session stubs — a divergence *class*, not a bug list. **Moneta** — a vector-native memory engine (`deposit` / `query` / `signal_attention` / consolidation, with time-decay and durability) — is introduced behind the unchanged `MemoryStore` interface so that divergence becomes **structurally impossible**: there is one store, and `count()` reads the engine's live entity count.

It ships **shadow-first and flag-gated, default-off** (`SYNAPSE_MEMORY_BACKEND` = `jsonl` | `moneta` | `shadow`). Each SYNAPSE `Memory` is serialized whole into a Moneta deposit payload (byte-for-byte round-trip); a deterministic, dependency-free `HashEmbedder` (PYTHONHASHSEED-independent, swappable for a semantic model later) embeds the content; decision / show-tier / gate-source memories map to a `protected_floor` so pinned memories resist decay. Keyword search is **bit-identical** to the JSONL store (parity-by-construction); the shadow path dual-writes and diffs reads into a `ParityReport`, so cutover is justified by evidence, not hope.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart TB
    C["Callers &mdash; unchanged<br/>synapse_context / search / recall<br/>session tracker"] --> SM["SynapseMemory facade"]
    SM --> SEL{"SYNAPSE_MEMORY_BACKEND"}
    SEL -->|"jsonl &mdash; default"| JS["MemoryStore<br/>(JSONL, append-only)"]:::def
    SEL -->|shadow| SH["ShadowMemoryStore<br/>dual-write + ParityReport"]:::alt
    SEL -->|moneta| MB["MonetaBackedStore<br/>full Memory &rarr; payload"]:::alt
    SH -->|"authoritative read"| JS
    SH -.->|"mirror + diff"| MB
    MB --> ENG[("Moneta engine<br/>HashEmbedder &rarr; deposit/query<br/>decay &middot; consolidation &middot; protected_floor")]:::eng
    classDef def fill:#1e293b,stroke:#22c55e,color:#f1f5f9
    classDef alt fill:#1e293b,stroke:#8b5cf6,color:#f1f5f9
    classDef eng fill:#334155,stroke:#f59e0b,color:#f1f5f9
```

A four-agent **CRUCIBLE** fan-out attacked the backend and found two real defects — a protected-quota silent demotion and a corrupt-snapshot startup-killer — both fixed and pinned. A second ARCHITECT→FORGE→CRUCIBLE pass then closed the **FC4 single-writer gap by construction**: a serialization `RLock` makes the adapter thread-safe (the engine's swap-and-pop index can no longer be corrupted by concurrent deposit/iterate/prune), and because the adapter makes zero `hou.*` calls the lock is never held across the main-thread hop — so it can't deadlock the async server. Proven standalone by a concurrency stress suite; the destructive `run_sleep_pass` is now auditable (returns/logs exactly what it pruned). The production default-on flip is still staged (flag stays `jsonl`), but no longer blocked on live thread-safety verification. Full acceptance/falsifier status and the cutover procedure live in [`docs/MONETA_SYNAPSE_SHIP_REPORT.md`](docs/MONETA_SYNAPSE_SHIP_REPORT.md).

The memory store's bespoke `python/synapse/memory/evolution.py` (the charmander→charizard USD evolution) is superseded by Moneta's consolidation — it stays **dormant** under the `moneta` backend (pinned by `test_moneta_backend_never_fires_evolution`) and still fires under the default `jsonl`; physical removal is deferred to the cutover. (Distinct from `shared/evolution.py`, the MOE-orchestrator subsystem, which is unchanged.)

> **On the name "Moneta":** the vector-memory engine wired in here ([repo](https://github.com/JosephOIbrahim/Moneta)) is a Python library; it is a *distinct project* from the similarly-named "Moneta (Nuke)" entry in the Portfolio thesis above (a planned DCC host). They historically share a working name but are not the same codebase.

---

### Sprint 3 progress — Mile 4 of 6 closed (Mile 5 prestaged)

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    M1["Mile 1<br/>Spike 2.4<br/>deadlock close"]:::closed
    M2["Mile 2<br/>Spike 3.0<br/>PDG audit"]:::closed
    M3["Mile 3<br/>Spike 3.1<br/>TopsEventBridge"]:::closed
    M4["Mile 4<br/>Spike 3.2<br/>SceneLoadBridge"]:::closed
    M5["Mile 5<br/>Spike 3.3<br/>first event live<br/>recon prestaged"]:::prestaged
    M6["Mile 6<br/>Spike 3.4<br/>hostile crucible"]:::ahead
    M1 --> M2 --> M3 --> M4 --> M5 --> M6
    P["Spike 3.3 prestage - design-only<br/>4 scaffold bugs caught A-D<br/>handlers fire on a worker thread"]:::recon
    M5 -.-> P
    classDef closed fill:#1e293b,stroke:#22c55e,color:#f1f5f9
    classDef ahead fill:#334155,stroke:#94a3b8,color:#cbd5e1
    classDef prestaged fill:#3b2f1d,stroke:#f59e0b,color:#fde68a
    classDef recon fill:#0f172a,stroke:#f59e0b,color:#fbbf24
```

**Mile 1 — Spike 2.4 deadlock closure.** The live Crucible baseline at end of Sprint 3 Day 1 surfaced a deadlock at the daemon ↔ main-thread boundary: synchronous `submit_turn` parked Houdini's main thread on a result queue while the daemon thread's `hdefereval` dispatch waited for that same main thread to pump Qt events. Spike 2.4 closes it by changing `submit_turn` to return immediately with a `TurnHandle` — a `threading.Event`-backed Future analog. The caller decides when (and on which thread) to wait. Main thread stays free to pump Qt events; daemon thread keeps the agent loop; `hdefereval` lambdas execute because main is responsive.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569','actorBkg':'#1e293b','actorTextColor':'#f1f5f9','actorBorder':'#0f172a','signalColor':'#f59e0b','signalTextColor':'#f1f5f9','noteBkgColor':'#334155','noteTextColor':'#f1f5f9','sequenceNumberColor':'#f1f5f9','labelBoxBkgColor':'#1e293b','labelTextColor':'#f1f5f9','loopTextColor':'#f1f5f9'}}}%%
sequenceDiagram
    autonumber
    actor Caller
    participant Daemon as Daemon thread
    participant Main as Main thread<br/>(Qt + hou.*)
    participant H as TurnHandle

    Caller->>Daemon: submit_turn(prompt)
    Daemon-->>Caller: TurnHandle (immediate)
    Note over Caller,Main: Main thread free —<br/>Qt pump runs throughout

    Daemon->>Daemon: run_turn (agent loop)
    loop tool calls
        Daemon->>Main: hdefereval lambda
        Main-->>Daemon: tool result
    end
    Daemon->>H: _set_result(AgentTurnResult)

    Caller->>H: done() / wait() / result()
    H-->>Caller: AgentTurnResult
```

**Mile 2 — Spike 3.0 PDG API audit.** The `pdg` module surface in Houdini 21.0.671 has known divergences from prior versions and from external-LLM training data. Mile 2 ran `dir()` introspection against live Houdini, captured the empirical surface in `docs/sprint3/spike_3_0_pdg_api_audit.md`, and refuted six wrong references in the early sketch — every `hou.pdg.*` path missing, `hou.hipFile.addEventCallback` returning `None` (not a removable handle), `pdg.PyEventCallback` being the wrong name. Each of those would have crashed first contact with Houdini if Spike 3.1 had coded against the sketch verbatim.

**Mile 3 — Spike 3.1 `TopsEventBridge` (Phase A).** In-process PDG event bridge. `warm(top_node)` registers a `pdg.PyEventHandler` against the TOP network's live `pdg.GraphContext` (acquired via `top_node.getPDGGraphContext()`, never class-instantiated — that's for fresh graphs). Surfaces 7 audit-verified event types: `CookStart`, `CookComplete`, `CookError`, `CookWarning`, `WorkItemAdd`, `WorkItemStateChange`, `WorkItemResult`. Threading defensive: handler reads `pdg.*` properties only, no `hou.*` calls inside. 47 tests across basic happy paths and an 8-case hostile suite (handler leak, double-bridge independence, callback-raising-mid-event, topnet-deleted-mid-subscription, multi-event-type-no-loss).

**Mile 4 — Spike 3.2 `SceneLoadBridge` (Phase B).** Auto-warm wire from `hou.hipFile.AfterLoad` to `TopsEventBridge`. Composes (not inherits) — constructor takes a `TopsEventBridge` instance and orchestrates its `cool_all` / `warm_all` cycle on each scene load. Mile 4's empirical scene-load audit (`docs/sprint3/spike_3_2_scene_load_audit.md`) captured all four hipFile events firing on `MainThread`, so the AfterLoad handler is a direct synchronous call — no `hdefereval`. 24 tests across basic happy paths and a 10-case hostile suite. One fix-forward cycle during CRUCIBLE: case 6 (unsubscribe-during-handler) surfaced a real defect — `warm_all` kept iterating after `unsubscribe` returned, leaving stale subs. Reconcile step added at end of `_on_after_load`: if `_subscribed` flipped to `False` mid-handler, run `cool_all` again. The hostile test pinned the contract; the fix held it.

**Mile 5 (prestage) — Spike 3.3 `dir()` recon.** Before any build, a design-only prestage ran the dir()-over-docs discipline against live 21.0.671 and produced `docs/sprint3/spike_3_3_recon.md` — a 13-agent synthesis workflow + adversarial completeness review, then one operator-authorized scratch cook to resolve the single unknowable-from-`dir()` crux. It **resolved the thread-of-delivery question**: PDG event handlers fire on a **worker thread** (the exact opposite of `hou.hipFile`, which fires on main), so the perception handler must be `pdg.*`-only + non-blocking-enqueue or it reintroduces the Spike 2.4 deadlock. And it **caught four bugs in the already-scaffolded bridges** before they could reach a live cook: **A** — `event.workItem` is phantom, so payload is silently empty; **B** — there is no `WorkItemComplete` enum, so `workitem.complete` must be derived from `WorkItemStateChange` + `currentState == CookedSuccess` (and a *static* generator emits neither — the gate demo needs a real processor); **C** — `pdg.Node` has `.name`, not `.path()`; **D** — `pdg.PyEventHandler(callback)` has no constructor, so the scaffold's handler factory hard-crashes on the first `warm()` (the correct API is a raw callable passed to `addEventHandler`, which returns the wrapper). Zero production code was touched; build starts at M1.

**Workflow — the three-role pattern.** Phase A and Phase B both ran the same MOE shape internally:

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    A["ARCHITECT<br/>design only<br/>(spec contract)"] -->|design.md| F["FORGE<br/>implementation +<br/>basic tests"]
    F -->|system under test| C["CRUCIBLE<br/>hostile suite<br/>(adversarial posture)"]
    C -->|fix-forward| F
    C -->|all green| G["Phase Gate"]
    classDef arch fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef forge fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef cruc fill:#1e293b,stroke:#ef4444,color:#f1f5f9
    classDef gate fill:#334155,stroke:#22c55e,color:#f1f5f9
    class A arch
    class F forge
    class C cruc
    class G gate
```

ARCHITECT writes the design doc and never the code. FORGE implements against the spec and writes basic happy-path tests. CRUCIBLE writes hostile tests and never the implementation; when a hostile test surfaces a real defect, FORGE fixes the implementation rather than CRUCIBLE weakening the test (Commandment 7). Each role's authority is constitutionally restricted; phase boundaries gate the merge.

### Sprint 3 — load-bearing commits

```
87c4db9  Spike 3.2    SceneLoadBridge hostile suite (CRUCIBLE) + fix-forward
4cba649  Spike 3.2    SceneLoadBridge scaffold (FORGE)
ef7d5ae  Spike 3.2    SceneLoadBridge design (ARCHITECT)
9e4cc42  Spike 3.2    scene-load audit findings landed (Mile 4 audit)
a476386  Spike 3.2    scene-load API audit infrastructure
2f46590  CI repair    bump checkout/setup-python (Node.js 20 deprecation)
fcd1077  CI repair    gate test_live_capture body behind __main__
bb2713b  Spike 3.1    TopsEventBridge hostile suite (CRUCIBLE)
89da296  Spike 3.1    TopsEventBridge scaffold (FORGE)
2aa03d9  Spike 3.1    TopsEventBridge design (ARCHITECT)
07946dc  Spike 3.0    PDG API audit findings (Mile 2 audit)
6bf2f07  Spike 3.0    PDG API audit infrastructure
b1d3163  Spike 2.4    close daemon↔main-thread deadlock via TurnHandle
6e08dae  Spike 2.4    add TurnHandle (Future-shaped result envelope)
```

Sprint 2 Week 1 (`5e6fc0c`) shipped the first tool (`synapse_inspect_stage`) end-to-end through the still-outside-in WebSocket path. Sprint 3 built the inside-out substrate alongside it — one spike at a time, with an audit-first discipline (live `dir()` introspection in Houdini 21.0.671 before any code lands) and a human-in-the-loop Crucible protocol (`docs/crucible_protocol.md`) for the parts bash cannot drive. Tagged at `v5.5.0` (`4faaa3a`).

### Sprint 3 — what's next

```
Spike 3.3    First TOPS event surface live              [Mile 5 — needs GUI]
             workitem.complete → agent perception
             real .hip + real TOP cook through the bridge
Spike 3.4    Hostile TOPS Crucible                      [Mile 6]
             event flood, malformed events, cancellation
```

Mile 5 is the first time a real `pdg.Event` reaches the agent's perception layer through the two-bridge wiring in graphical Houdini. End-to-end timing target: under 50ms from `cookComplete` to `perception_callback` invocation (in-process should be sub-ms; budget is for safety margin). Mile 6 turns the heat up — event flood (10K events / 1s), malformed events (missing fields surface as typed parse errors), cancellation mid-cook with no orphaned callbacks.

Mile 5 cannot run from bash. It needs Joe at the GUI driving a real cook against the scaffolded bridges.

---

## Repository layout

```
python/synapse/
├── cognitive/                  # zero hou imports (lint-enforced)
│   ├── dispatcher.py           # Dispatcher + AgentToolError
│   ├── agent_loop.py           # Anthropic SDK turn runner
│   └── tools/                  # pure-Python tool implementations
├── host/                       # Houdini-specific (hou / hdefereval OK)
│   ├── daemon.py               # SynapseDaemon lifecycle
│   ├── main_thread_executor.py # tri-state GUI/headless/stock
│   ├── transport.py            # in-process execute_python
│   ├── dialog_suppression.py   # per-tool-call hou.ui guard
│   ├── auth.py                 # API key resolver (env var + hou.secure probe)
│   ├── turn_handle.py          # Spike 2.4 — Future-shaped submit_turn return
│   ├── tops_bridge.py          # Spike 3.1 — PDG event bridge (Phase A)
│   └── scene_load_bridge.py    # Spike 3.2 — auto-warm on AfterLoad (Phase B)
├── memory/                     # PR #14 — Moneta-backed memory substrate
│   ├── embedding.py            # deterministic HashEmbedder (Embedder protocol)
│   ├── moneta_runtime.py       # import-guarded Moneta access (pxr-free ephemeral)
│   ├── moneta_store.py         # MonetaBackedStore (MemoryStore-compatible)
│   ├── shadow_store.py         # dual-write + parity diff harness
│   ├── backfill.py             # one-time JSONL → Moneta backfill (backup-first)
│   └── store.py                # SynapseMemory + SYNAPSE_MEMORY_BACKEND selector
├── panel/                      # artist-facing copilot panel (Qt / PySide6)
│   ├── synapse_panel.py        # the docked panel — rail + 3 faces, state→face controller
│   ├── face_work.py            # Work face — cook-preview bucket grid + plan-with-progress + health
│   ├── face_review.py          # Review face — render-hero + verdict + credit/provenance + flags + gated commit
│   ├── claude_worker.py        # background QThread — streams Claude + tool loop
│   ├── tool_executor.py        # main-thread tool dispatch (→ SynapseHandler)
│   ├── bridge_adapter.py       # routes external-MCP mutations through LosslessExecutionBridge
│   ├── tool_palette.py         # Ctrl+K palette — two axes (verb × context) over the tool registry
│   ├── health_infographic.py   # observability (per-agent health + self-tuning loop), embedded in the Work face
│   └── designsystem/           # vendored tokens / qss / components (one source)
├── _vendor/                    # anthropic + deps, CP311 win_amd64
└── ...                         # Sprint 2 Week 1 + prior subsystems

tests/                          # 3168 local; ~70 are Moneta-gated (skip on a
                                # clean clone / CI without the moneta package)
docs/sprint3/                   # audits + design contracts + continuation
docs/crucible_protocol.md       # manual Crucible runbook
mcp_server.py                   # Sprint 2 WebSocket adapter (still shipping)
```

---

## License

MIT. See [LICENSE](LICENSE).
