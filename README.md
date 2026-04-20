<p align="center">
  <img src="assets/synapse_logo.png" alt="Synapse" width="400"/>
</p>

<h3 align="center"><strong>Inside-out agent substrate for Houdini.</strong></h3>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="python/synapse/cognitive/dispatcher.py"><img src="https://img.shields.io/badge/dispatcher-Strangler%20Fig-1e293b.svg" alt="Dispatcher"></a>
  <a href="python/synapse/host/daemon.py"><img src="https://img.shields.io/badge/daemon-in--process-f59e0b.svg" alt="Daemon"></a>
  <a href="tests"><img src="https://img.shields.io/badge/tests-2700%20passing-brightgreen.svg" alt="Tests"></a>
</p>

---

## The thesis: outside-in → inside-out

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

Tested on **Windows 11 + Houdini 21.0.671**. Linux / macOS paths are the same shape, different separators.

### 1. Clone into a known path

```powershell
git clone https://github.com/JosephOIbrahim/Synapse.git C:\Users\%USERNAME%\SYNAPSE
cd C:\Users\%USERNAME%\SYNAPSE
```

**You're good if:** `git log -1 --oneline` shows the latest commit on `master`.
**If you see** `fatal: destination path already exists`: pick a different destination or remove the existing folder first.

### 2. Register the package with Houdini

Create `%USERPROFILE%\houdini21.0\packages\Synapse.json`:

```json
{
    "env": [
        { "PYTHONPATH": "C:/Users/YOUR_USERNAME/SYNAPSE/python" }
    ]
}
```

Replace `YOUR_USERNAME` with your actual Windows username (forward slashes in the path, not backslashes).

**You're good if:** launching Houdini and running `import synapse; print(synapse.__version__)` in the Python Shell prints a version string.
**If you see** `ModuleNotFoundError: No module named 'synapse'`: double-check the `PYTHONPATH` value in the `.json` points at the `python/` directory, not the repo root.

### 3. Set the API key

**Current primary — env var.** Set `ANTHROPIC_API_KEY` in your system environment (not just a terminal session — Houdini launches don't inherit shell-scoped vars on Windows):

```powershell
setx ANTHROPIC_API_KEY "sk-ant-..."
```

Launch a fresh Houdini after running `setx` — the new value only reaches processes started after.

**Forward-compat — `hou.secure`.** When SideFX ships a secure-credentials API in a future Houdini release, SYNAPSE's auth resolver picks it up automatically. Confirmed **not present** in Houdini 21.0.671 (`dir(hou)` only exposes `secureSelectionOption`). No action needed today.

**You're good if:** in Houdini's Python Shell, `import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))` prints `True`.
**If you see** `False`: the variable didn't land in this Houdini's environment. Close Houdini, re-open from a fresh shell, try again.

### 4. Verify the daemon boots

In Houdini's Python Shell:

```python
from synapse.host.daemon import SynapseDaemon

daemon = SynapseDaemon()
daemon.start()
print("running:", daemon.is_running)
daemon.stop()
```

**You're good if:** prints `running: True` and stops cleanly.
**If you see** `DaemonBootError: hou.isUIAvailable() returned False`: you're in headless `hython`, not graphical Houdini. The daemon refuses to boot in PDG / render-farm contexts (Fork Bomb prevention). For tests, pass `boot_gate=False`.
**If you see** `DaemonBootError: No Anthropic API key available`: step 3 didn't take. Re-launch Houdini from a fresh shell.
**If you see** `DaemonBootError: anthropic SDK is not installed`: this shouldn't happen — the SDK is vendored at `python/synapse/_vendor/` and prepended to `sys.path` on `import synapse`. If it does, confirm the vendored tree is intact on disk (`ls python/synapse/_vendor/anthropic/`).

---

## Current capability + roadmap

### What's shipping today

| Layer | State |
|---|---|
| Cognitive substrate (Dispatcher + `AgentToolError` + cognitive/host split) | Shipping. Zero-hou boundary enforced by lint. |
| Agent SDK loop (Anthropic, cancel-event-aware, serializable tool errors) | Shipping. Mocked end-to-end tests green. |
| Daemon lifecycle (boot gate, auth resolver, dialog suppression, bootstrap locks) | Shipping. Windows `WindowsSelectorEventLoopPolicy` + `PYTHONNOUSERSITE` + no-runtime-pip all baked. |
| Vendored Anthropic SDK | Shipping. 15 MB at `python/synapse/_vendor/`, Python 3.11 / win\_amd64 ABI lock. |
| **Tools ported through the Dispatcher** | **1** — `synapse_inspect_stage` (flat `/stage` AST). |
| **Tools still on the Sprint 2 WebSocket path** | **~103** — working in production, awaiting port. |

The port pattern is mechanical and documented in `docs/crucible_protocol.md` + the `spike(1)` commit message. Every legacy tool gets:

1. A pure-Python function under `synapse.cognitive.tools.<name>` (zero `hou` imports).
2. A schema dict (description + JSON Schema) registered alongside the function.
3. The WS adapter branch in `mcp_server.py` swapped from `synapse_inspect_stage`-style direct dispatch to `dispatcher.execute('<name>', kwargs)`.

### Known architectural gap — Spike 2.4

The live Crucible baseline surfaced a deadlock at the daemon ↔ main-thread boundary:

```
main thread:   submit_turn → result_queue.get() [BLOCKED on Python queue]
daemon thread: Dispatcher → main_thread_exec
               → hdefereval waits for main thread Qt pump
               → main thread blocked on result_queue.get()
result:        30s MainThreadTimeoutError per tool call
```

This was masked by `TransportNotConfiguredError` fast-failing in 80789fe; Spike 2.3 wired the transport and unmasked the real issue. Matches the "CI Event Loop Desync" hazard from the Gemini Deep Think Round 3 production audit. Three remediation options identified, scoped for Spike 2.4:

1. **Non-blocking `submit_turn`** returning a `Future`; caller pumps Qt explicitly between polls.
2. **Qt event pump during wait** — only viable if Houdini exposes an appropriate API (`hou.ui.processEvents()` is confirmed absent in 21.0.631).
3. **Agent loop off the daemon thread** — run on main thread directly; main thread stays responsive because Anthropic SDK calls yield via `asyncio`.

Each is 4–8 hours of work plus a real test surface. Not a one-line fix.

### Sprint 3 — commit tree

```
cce7b34  Revert       revert spike(2.3) — deadlock unmasked by transport fix
43ee77f  Spike 2.3    auto-wire transport (reverted, kept for 2.4 reference)
dce8834  Spike 2.2    vendor Anthropic SDK for cross-version portability
80789fe  Spike 2 P2   agent loop + submit_turn + Crucible runbook
ed6ace6  Spike 2.1    close deferred live-transport gate (tri-state executor)
c6d232b  Spike 2 P1   daemon scaffolding + bootstrap locks
516242f  Spike 1      Dispatcher extraction + inspect_stage port
b5a2ce3  Spike 1.0    Dispatcher test-mode bypass + cognitive boundary
e6f79f9  Spike 0      SDK import gate green (hython + anthropic round-trip)
```

Sprint 2 Week 1 (`5e6fc0c`) shipped the first tool (`synapse_inspect_stage`) end-to-end through the still-outside-in WebSocket path. Sprint 3 built the inside-out substrate alongside it, one spike at a time, with a human-in-the-loop Crucible protocol (`docs/crucible_protocol.md`) for the parts bash cannot drive.

---

## Repository layout

```
python/synapse/
├── cognitive/              # zero hou imports (lint-enforced)
│   ├── dispatcher.py       # Dispatcher + AgentToolError
│   ├── agent_loop.py       # Anthropic SDK turn runner
│   └── tools/              # pure-Python tool implementations
├── host/                   # Houdini-specific (hou / hdefereval OK)
│   ├── daemon.py           # SynapseDaemon lifecycle
│   ├── main_thread_executor.py  # tri-state GUI/headless/stock
│   ├── transport.py        # in-process execute_python
│   ├── dialog_suppression.py    # per-tool-call hou.ui guard
│   └── auth.py             # API key resolver (env var + hou.secure probe)
├── _vendor/                # anthropic + deps, CP311 win_amd64
└── ...                     # Sprint 2 Week 1 + prior subsystems

tests/                      # 2700 passing, 5 pre-existing failures
docs/crucible_protocol.md   # manual Crucible runbook
mcp_server.py               # Sprint 2 WebSocket adapter (still shipping)
```

---

## License

MIT. See [LICENSE](LICENSE).
