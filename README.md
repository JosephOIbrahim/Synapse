<p align="center">
  <img src="assets/synapse_logo.png" alt="Synapse" width="400"/>
</p>

<h3 align="center"><strong>Talk to Houdini in plain English — it builds in your live scene.</strong></h3>

<p align="center"><em>An AI copilot that lives <strong>inside</strong> Houdini — say what you want and watch it build in your scene. Everything it makes is a normal Houdini action, so <strong>Ctrl+Z</strong> takes it back.</em></p>

<p align="center">
  <a href="https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml"><img src="https://github.com/JosephOIbrahim/Synapse/actions/workflows/ci.yml/badge.svg?branch=master" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License"></a>
  <a href="python/synapse/panel/synapse_panel.py"><img src="https://img.shields.io/badge/artist%20panel-chat%20%E2%86%92%20build-22c55e.svg" alt="Artist panel"></a>
  <a href="python/synapse/panel/providers"><img src="https://img.shields.io/badge/engines-Claude%20%C2%B7%20Gemini%20%C2%B7%20Nemotron%20%C2%B7%20Ollama%20%C2%B7%20Custom-8b5cf6.svg" alt="Engines"></a>
  <a href="tests"><img src="https://img.shields.io/badge/tests-4642%20passing-brightgreen.svg" alt="Tests"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-v5.33.0-1e293b.svg" alt="Changelog"></a>
</p>

> ⚡ **TL;DR** — an AI panel *inside* Houdini: type **"make a box,"** get a real node. Every action is ordinary Houdini, so **Ctrl+Z** takes it back — and it keeps receipts, not magic. Five engines, 115 tools. **Install ↓ in ~5 min.**

> 🧪 **The moat, in one line:** every other Houdini copilot reasons from docs and memory — SYNAPSE **probes the running Houdini and commits what it finds** (six truth catalogs and counting: wiring, Solaris context, capability, readiness, live cook behavior, and now **perception truth — the render receipt**). Docs drift. Probes don't.

---

### ✦ The idea, in plain terms

SYNAPSE lives **inside** Houdini and turns plain English into real work:

- 🧠 **It works inside Houdini, not off to the side** — the assistant runs in Houdini itself, so there's no separate app to launch and nothing to wait on; it answers right where you're working.
- 🔁 **Your words become real nodes** — every request is just a normal Houdini action. Don't like it? **Ctrl+Z** takes it back.
- 🧾 **It keeps the receipts** — changes are ordinary Houdini actions you can undo, and the audited `/mcp` path records a receipt for every one, so you can see what it did and why. That's the differentiator — not magic, receipts.
- 🔌 **Pick your AI · 115 tools** — choose **Claude · Gemini · NVIDIA Nemotron · Ollama (local) · Custom** in the panel and switch whenever you like.
- 📜 **Free to use (MIT license)** ([LICENSE](LICENSE)) with **patent-pending methods** ([PATENTS](PATENTS)) — the license covers the code, not the patents.

---

### ✦ Map — you are here

| You want… | Read… |
|---|---|
| **The 30-second pitch** | *The idea, in plain terms* (above) + *What it is* |
| **What's new in v5.33.0** | *New in v5.33.0* — the main thread never waits on itself: a whole class of permanent Houdini freeze removed, lint-enforced, live-verified |
| **What still holds the UI (and why)** | *The honest limits* — inside the v5.33.0 section |
| **What a render actually proves** | *The render receipt* |
| **How AI network-building stays safe** | *Propose → validate → build* |
| **To install it** | *Install — 5 minutes* |
| **The architecture** | *How it works — inside-out* |
| **Every release + per-tool detail** | [CHANGELOG.md](CHANGELOG.md) |

---

## ✦ What it is

A docked **SYNAPSE panel** inside Houdini. You type what you want — *"make a box"*, *"create a solaris network ending with rendersettings using karma xpu"* — and it **builds it in your live scene.** Chat in, real nodes out.

- ⚡ **In-process** — the agent runs in Houdini's own Python; tools are direct `hou.*` calls, not a slow round-trip bridge.
- ↩️ **Undo-safe** — everything it does is an ordinary Houdini action. **Ctrl+Z undoes it.** On the audited `/mcp` path every mutation leaves a provenance record; the live WebSocket path records observe-only envelopes.
- 🔌 **Multi-provider** — pick **Claude · Gemini · NVIDIA Nemotron · Ollama · Custom** right in the panel; swap engines mid-session.
- 🎬 **Built for the work** — SOPs, **Solaris / USD, Karma, COPs, PDG / TOPs, MaterialX** — 115 tools.

> ✅ *"make a box" → a real geo node, confirmed on graphical Houdini 22.0.368. (H21 code paths are retained and major-aware, but H21 is no longer installed here, so H22.0.368 is the only live-tested build.)*

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    ART["Artist<br/>'make a box'"]:::artist --> PANEL["SYNAPSE panel<br/>rail · CHAT · author token"]:::panel
    PANEL -->|"Claude · Gemini · Nemotron · Ollama · Custom"| LOOP["Agent loop<br/>chosen engine + 115 tools"]:::panel
    LOOP -->|"tool_use"| EXEC["Tool executor<br/>(main thread)"]:::panel
    EXEC --> BR["Handler<br/>undo-wrapped · integrity"]:::bridge
    BR -->|in-process call| HOU[("hou.*<br/>node created")]:::hou
    BR -.provenance.-> LEDGER["IntegrityBlock trail<br/>audited /mcp + live envelope"]:::side
    BR -.timing.-> METRICS["Latency metrics<br/>histograms → Prometheus"]:::side
    BR -.needs approval.-> GATE["Consent gate<br/>auto-surfaces in CHAT · accept / revert"]:::bridge
    GATE -.hands back.-> ART
    classDef artist fill:#DE8425,stroke:#7A4310,color:#1A1208
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef bridge fill:#EEA958,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

**The panel, briefly (v9.1):**

- **One CHAT surface** — the build review + **consent gate auto-surface** when a build needs approval. Consent comes to *you*, then hands back on accept/revert.
- **A persistent rail** — live state + a **Stop** that ends the agent loop. *It stops the next step; it cannot claw back a Houdini operation already running.*
- **The author token** — engine + model in one rail control.
- **`Aa`** scales only what you *read* · **`/`** opens a command palette over every tool · a token-only meter.
- Bundled **Space Grotesk / Space Mono** type system.

---

## ✦ New in v5.33.0 — the main thread never waits on itself

**One class of permanent Houdini freeze is gone: the main thread waiting on itself.** That specific class — not freezing in general — was **structurally removed** rather than made rarer, and a source lint keeps it from coming back. Everything still capable of holding the UI is listed under *The honest limits* below.

### The defect, in plain terms

Houdini has exactly **one** thread allowed to touch the scene: the main thread. Everything else has to hand work to it and wait.

The vendor helper SYNAPSE used for that handoff — `hdefereval.executeInMainThreadWithResult` — **never checks who is calling it.** Called from a background thread it works correctly. Called from the main thread, it puts work in a queue that *only the main thread can empty*, then parks the main thread waiting for that work.

**Houdini waits for itself, forever.** No error, no timeout, no recovery — you kill the process. This is vendor-level behavior on Houdini 22.0.368, and it happens **every time**, not as a race.

SYNAPSE reached that helper from the main thread by **two confirmed routes**.

### What the fix actually was

**Nothing new was built.** The codebase already had the right primitive — `server/main_thread.py::run_on_main`, which was immune from the start:

| Caller | What `run_on_main` does |
|---|---|
| **Off the main thread** | Posts the work **non-blocking**, then waits on a **per-call** result holder with a real timeout |
| **On the main thread** | Short-circuits to a **direct call** — never queues, so it can never wait on itself |

The fix was **deleting the nine call sites that bypassed it.** A line-scoped source lint (`tests/test_marshal_lint.py`) now fails the build if the unsafe helper reappears anywhere.

> 👻 **A finding inside the finding:** three of those nine called `hdefereval.executeInMainThread` — a function that **does not exist on H22.0.368**. Confirmed against the live runtime. They had been **failing silently**.

### Verified on a running Houdini, not a stub

Live session: **H22.0.368, PID 64396**, identity-probed *before* any repro was attempted, so the results can't be a stale-code false pass.

| Check | Result |
|---|---|
| `run_on_main` called **from the main thread** | **0.014 ms**, inline, returned — the identical shape used to park forever |
| `houdini_capture_viewport` over `/mcp` *(a confirmed pre-fix deadlock path)* | Returned **twice**; `Responding=True` throughout; bridge served the next turn |
| Deliberate **6-second** main-thread hold | Telemetry fired with exact attribution (`fast_path_2`, 6.0004 s vs a 5.0 s budget) · violations **0** · next turn served **22 µs** later |
| **~25-call soak** — 5 concurrent read-only, 4 concurrent mutating | Every call returned **its own** payload (no result swapping) · violations **0** · stack dumps **0** · **zero freezes** |

That last row closes a second, quieter bug: the vendor helper stored results in **module globals**, so two concurrent blocking handoffs could hand each other's results back — silently wrong data, no error. No SYNAPSE code path calls that helper any more, and the source lint keeps it out.

- 🟢 **4,642 tests passing · 0 failed · 100 skipped.** Against the **previous release** (v5.32.1, 4,571): **+71.** Against the **ratchet floor** (`harness/verify/suite_baseline.json`, 4,275): **+367.** Both figures are correct against their own baseline — neither is a bare delta. **Zero tests weakened:** two test files changed and both were flagged — one pinned the deliberately-removed primitive, and one had gone **vacuous** (passing while pinning nothing). Both re-anchored and proven able to fail.

### The honest limits — read this part

This release removed a *specific* failure: **the main thread waiting on itself.** It did not make Houdini un-freezable, and the following are still true:

- 🎬 **A render that runs on Houdini's main thread still holds the UI for its duration — and that is the panel path *and* `/mcp`, not the panel alone.**
  - **Panel** — the Qt slot *is* the main thread, so the render runs inline there.
  - **`/mcp`** — `mcp/server.py` marshals the whole dispatch onto the main thread first, so by the time the render handler runs it detects a main-thread caller and renders **inline too** (`python/synapse/server/handlers_render.py:517`, and the caller-path note at `:96-107`). **No session or token flow applies on `/mcp`** — the XPU foreground guard is the only protection there. Budget your `/mcp` renders accordingly.
  - **WS `/synapse`** — the one path that is off-main, and the only one that gets the bounded session flow (poll-based status, a 60s token cadence).
  - On the main thread a render can't be made invisible — only made to **finish**. What changed is real and it is the whole point: a **permanent, unrecoverable freeze became a stall bounded by the render's own duration, which completes.** Watch your cores or GPU to confirm it's doing real work.
- 🛑 **Cancel does not interrupt an operation that is already running.** The WebSocket loop reads messages **one at a time**, so your `cancel` queues up behind the very handler you're trying to cancel. Out-of-band only — `scripts/render_watch.ps1`, or kill the process. **This is the #1 known follow-up and it is not fixed.**
- 🐕 **The watchdog reports and degrades — it cannot un-wedge a stuck main thread.** Nothing running inside the process can. Its job is diagnosis plus graceful degradation, never rescue.
- ⏱️ **On `/mcp`, a long frame can report failure while the render keeps going** and writes its file. Check for the output before re-running, or you'll render it twice.

*Operator card (start/stop, healthy vs degraded turn signatures, the two env knobs, four failure modes with recovery): [`docs/sprint_freeze/OPERATOR_CARD.md`](docs/sprint_freeze/OPERATOR_CARD.md). The full evidence chain — every blocking wait mapped per thread, the gate log, the eight-item sign-off — is in [`docs/sprint_freeze/`](docs/sprint_freeze/).*

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart TB
    subgraph NOW ["Now — one marshal, run_on_main"]
        direction LR
        OFF["Off-main caller<br/>WS · server pool · worker"]:::panel -->|"posts, never blocks main"| POST["Non-blocking enqueue<br/>executeDeferred"]:::bridge
        POST --> MAIN1[("Main thread<br/>drains when idle<br/>runs hou.*")]:::hou
        MAIN1 -->|"per-call result holder<br/>bounded wait · timeout is real"| BACK["Caller resumes<br/>with its OWN payload"]:::panel
        ONMAIN["Main-thread caller"]:::artist -->|"fast path · thread identity checked"| DIRECT["Direct call — inline<br/>0.014 ms · nothing queued"]:::hou
    end
    subgraph GONE ["Removed — the 9 bypasses · lint-guarded"]
        direction LR
        LINT["Source lint<br/>this call can't come back"]:::bridge -.blocks.-> MB
        MB["Main thread"]:::artist -->|"executeInMainThreadWithResult<br/>NO caller-thread check"| QUEUE["Queue only MAIN can drain"]:::side
        QUEUE -.->|"main is now parked,<br/>so it never drains it"| MB
        MB -.-> DEAD["Permanent freeze<br/>no error · no timeout · kill the process"]:::side
    end
    NOW ~~~ GONE
    classDef artist fill:#DE8425,stroke:#7A4310,color:#1A1208
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef bridge fill:#EEA958,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

---

## ✦ The render receipt — proof, not a screenshot

**When SYNAPSE says it rendered your frame, it can show you why it believes that.** RETINA is the perception tier: a render doesn't count as done because the tool returned — it counts when the **file on disk** says so, and then when the **pixels that changed** are the ones that were supposed to change.

- 🎯 **T0 · file truth (live)** — did the render actually happen as declared? Products, resolution, AOVs, a completion sentinel written *after* the pixels, a fingerprint that round-trips.
- 🔍 **T1 · scoped delta (live)** — the change-mask intersected with the object-ID matte: did the change land **inside** the thing you asked about, and stay **out** of everything else.
- 🧾 **The receipt is tri-state** — pass · fail · **inconclusive**. It cannot fake green: no manifest reads "no receipt yet" in grey, never a green 100%.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    ASK["Artist<br/>'swap the crystal to Dark_Glass'"]:::artist --> BUILD["SYNAPSE builds it<br/>undo-safe · recorded"]:::panel
    BUILD --> RENDER["Karma render<br/>beauty + object-ID AOV"]:::panel
    RENDER -->|"EXR + .done sentinel<br/>(husk_postframe, +5ms after pixels)"| T0["T0 · file truth ✓ LIVE<br/>rendered? right res/AOVs?<br/>fingerprint round-trips?"]:::hou
    T0 -->|"pass / inconclusive"| T1["T1 · scoped-delta ✓ LIVE<br/>change-mask ∩ ID-matte<br/>containment + SSIM-outside"]:::hou
    T1 -->|"pass / fail / inconclusive"| REC["agent.usd receipt<br/>DECISION · VIA · PROOF"]:::side
    T1 -.next tiers.-> LADDER["T2 ONNX · T3 VLM<br/>cost-gated escalation"]:::side
    REC -.-> ART2["Artist<br/>proof, not a screenshot"]:::artist
    classDef artist fill:#DE8425,stroke:#7A4310,color:#1A1208
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

> *The full picture — the T1 metric kit, the scoped-delta primitives, the twins, the Rulebook, and the supervisor-layer seams that come next — lives in the **v5.29.0–v5.31.0 entries** of [CHANGELOG.md](CHANGELOG.md) and in `docs/SYNAPSE_RETINA_BLUEPRINT.md`.*

---

## ✦ H22 — running, verified, expanding

**Houdini 22 isn't a milestone SYNAPSE is approaching — it's the build SYNAPSE runs on, with the core transition proven live and the generative expansion spec'd next.**

- 🔬 **Verified against a running Houdini, not just headless** — the live-bridge reconfirm converted the whole drop cycle from provisional to confirmed on the real 22.0.368 interpreter: every merged fix, the memory integrity gate, the PDG event surface, the quarantine re-pins.
- 🧩 **The Solaris wiring layer is H22-native** — a major-aware connectivity catalog (mirroring the per-major symbol-table pattern) means `wire_by_label` and the graph validator resolve H22 truth on H22 and H21 truth on H21, so proposed networks validate against the build you're actually running.
- 📋 **The port-wave plan** ([`docs/PORT_WAVE_MANIFEST.md`](docs/PORT_WAVE_MANIFEST.md)) — all 115 registry tools mapped into 11 sub-waves, each gated: gatewarden admits → forge builds in an isolated worktree → an assayer probes every symbol against the live build → a hostile crucible pass hunts for behavior drift → a human merges. The pilot wave is merged; the rest are unblocked and sequenced.
- 🌋 **The Copernicus expansion, spec'd and ratified** ([`docs/SYNAPSE_COPERNICUS_EXPANSION.md`](docs/SYNAPSE_COPERNICUS_EXPANSION.md)) — the read/analysis and node-API layers are deep and live-verified; the generative frontier (scaffold rebuilds, heightfield/terrain emission, neural COP nodes with model/GPU preflight honesty) is now a live-probed build spec, the next cycle's work.
- 🤝 **APEX MCP boundary contract** — Houdini 22 keynote-announced a rigging-scoped first-party MCP preview (not shipped in 22.0). The ratified boundary ([`docs/SYNAPSE_H22_BOUNDARY.md`](docs/SYNAPSE_H22_BOUNDARY.md)) holds: SYNAPSE never competes with it; its differentiators — in-process perception, undo-wrapped mutation, provenance, substrate memory — remain unclaimed by anything SideFX shipped.
- 🌀 **Cook-behavior diffs, live** — the diagnostic-truth catalogs are build-stamped and major-agnostic; on H22 they re-probed with zero code edits, turning *how H22 changed cook behavior* into a diffable artifact instead of forum anecdotes.

**The discipline that got here:** nothing merged on any agent's self-report — forge builds, a hostile crucible pass attacks what it didn't build, and every cycle is post-merge suite-re-verified. When a "loud-error" fix was caught only ⅓-implemented, it looped to a Pass-3 rather than shipping. Receipts, not vibes — including the agent's own.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    DROP["Drop + drop-week<br/>9 runbook artifacts"]:::hou --> ROADMAP["CTO roadmap<br/>silent-break register"]:::panel
    ROADMAP --> FIX["Fix cycles<br/>forge → assay → crucible"]:::bridge
    FIX -->|"merged + suite-reverified"| MERGED[("master<br/>4,642 / 0")]:::hou
    MERGED --> LIVE["Live-bridge reconfirm<br/>32 verdicts → VERIFIED-LIVE"]:::bridge
    LIVE -->|"proven on running 22.0.368"| DEMO[("H22-native<br/>Solaris · COP · memory")]:::hou
    LIVE -.hostile pass finds a risk.-> NEXT["New fix cycle<br/>ratified · gated"]:::side
    NEXT -.-> FIX
    DEMO -.next.-> EXPAND["Copernicus expansion<br/>scaffold · terrain · neural (spec'd)"]:::side
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef bridge fill:#EEA958,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

---

## ✦ The utility flywheel — probe-verified truth on a loop

**SYNAPSE improves itself on a loop: ground the AI's Houdini knowledge in probe-verified truth → review its own code against that truth → wire the truth into the live path.** Nothing enters the live path on memory alone — memory drifts; probes don't. Every cycle runs the same **EXPLORE → REVIEW → SCAFFOLD** contract; a human ratifies each new cycle; and where a catalog and a code comment disagree, **the catalog wins**.

**Three cycles have shipped — three kinds of truth** (with capability + readiness catalogs behind them):

- 🔌 **① Wiring truth — *how* nodes connect.**
  - `host/introspect_connectivity.py` instantiates **282 node types** headless and records their real input/output counts + slot labels → a committed, integrity-checked catalog.
  - `wire_by_label()` (`python/synapse/core/wiring.py`) resolves inputs by **probed label, never remembered index** — fail-loud on an unknown label/type.
  - The validator's **slot-semantic checks (P3e)** reject an edge into an input the type doesn't have.
  - *Receipts: the review sweep ran **141 sites, 0 critical**; the cycle fixed **2 known miswires** (swapped solver inputs).*

- 🧭 **② Solaris context truth — *what* the nodes are.**
  - A corpus-authored, probe-cross-checked **LOP / Solaris knowledge catalog** teaches the validator the semantics wiring truth can't see.
  - It **hard-rejects phantom LOP types** the model reaches for out of SOP habit — there is no `grid` or `plane` LOP (use a `cube`).
  - It **advises** when an `assignmaterial` has no material source upstream (a `materiallibrary`, *or* a `reference`/`sublayer` layer that already authors the materials).
  - *Receipts: **20 checks, 0 critical**; the ordering rule was softened from a hard error to an advisory after adversarial review caught it would false-reject valid reference/sublayer material graphs.*

- 🌀 **③ Diagnostic truth — what the scene *does* when poked** *(new in v5.21.0)*.
  - Perturbation probes catalog live **dirty-propagation, recook triggers, and time-dependence** per context (SOP/LOP/COP/DOP) — the one truth class no external LLM can hold, because it only exists as live cook-state.
  - *Receipts: the API probe caught the track's own spec citing **H18-era phantom spellings** (the cook surface lives on `hou.OpNode`, not `hou.Node`); the catalog's first run captured a real divergence — **a COP rewire dirties upstream nodes SOP semantics say it shouldn't**.*
  - *Staged next: `synapse_explain_recook` — ask "why did this recook?" and get an answer cited to a probe trial.*

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    EXP["EXPLORE<br/>probe-verified ground truth<br/>live probe · or probe-checked corpus"]:::hou -->|"committed, integrity-checked catalog"| REV["REVIEW<br/>sweep the code vs the catalog<br/>0 critical"]:::bridge
    REV -->|"findings → fixes"| SCAF["SCAFFOLD<br/>truth into the live path<br/>wire_by_label · validator P3e + LOP · test pins"]:::panel
    SCAF -->|"new truth classes"| NEXT["Queue<br/>human ratifies each new cycle"]:::side
    NEXT -->|"cycle N+1 · so far: ① wiring · ② Solaris context · ③ diagnostic (cook truth) · ④ H22 discovery re-sweep (ran — 77 candidates) · queued: the port-wave fix cycles"| EXP
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef bridge fill:#EEA958,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

---

## ✦ Propose → validate → build — how AI network-building stays safe

**SYNAPSE never builds a network on the model's word alone.** Every plan is checked against your live scene *and* probed ground truth before a single node is created — and the build itself is one undo group.

- 📝 **Propose** — the model lays the whole network out first: every node, every wire, on paper.
- 🔎 **Validate against your live scene** — every input exists, every wire fits its input type, the parent network and every referenced node are really there, the plan is a DAG, and names don't collide. If a wire would land on an input you've *already* connected, validation **halts** — it never quietly severs your work.
- 📐 **Validate against probed truth (P3e)** — the wiring catalog rejects an edge into an input index the node type doesn't have, and a slot label that resolves to a different index. Memory doesn't get a vote; the probe does.
- 🧭 **Validate against Solaris knowledge** — a corpus-authored, probe-cross-checked catalog rejects **phantom LOP types** (there is no `grid`/`plane` LOP — use a `cube`) and flags a missing material source upstream of `assignmaterial`. Context the wiring truth can't see.
- 🔨 **Build — one undo group** — an unconditional TOCTOU re-validate first (a node deleted since propose halts with zero mutation), then create → set parms → wire → read back, all inside a single `hou.undos.group`. **One Ctrl+Z reverts the whole build.**
- 🛟 **Rollback on failure** — if the build trips mid-way, it destroys the partial nodes inside the undo group. Zero net mutation, a structured `FAILED` result, no orphan nodes.
- 🧾 **Receipts** — every build writes an `agent.usd` record: decision, reasoning, revert path.

It also wires **Solaris the way production expects** — the **Component Builder** pattern for assets, the proper **`rendersettings` → render** terminal, **layered** scene assembly, and the actual merge/sublayer strength rule (**higher input index wins**).

> 🕰️ **Historical note on that probe.** The production-wiring correction was *originally* live-probed on **21.0.671** — a build **no longer installed here**, so nothing in this release is verified against it. The Solaris knowledge catalog has since been **re-probed on 22.0.368 and made major-aware** (v5.29.0, C-U5): light names and the drifted `assignmaterial` parm resolve against the build you are actually running, and the stale H21 per-shape light entries were removed rather than carried forward.

Verified end-to-end on **live Houdini 22.0.368** (originally proven on 21.0.671) — build, single-undo revert, TOCTOU halt, and forced-failure rollback all pass; the wiring catalog is now major-aware, so validation resolves against whichever build you run.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    ASK["Artist<br/>'build a karma setup'"]:::artist --> PROP["Propose<br/>nodes + wires, on paper"]:::panel
    PROP --> VAL["Validate<br/>vs your live scene · vs the wiring catalog (P3e) · vs the Solaris knowledge catalog<br/>inputs · wire types · slot labels · phantom LOP types · material-source ordering · occupied inputs"]:::bridge
    VAL -->|"all clear · parked"| BUILD["Build — one undo group<br/>create → wire → read back"]:::hou
    VAL -.->|"something's off"| STOP["Stop · nothing touched"]:::side
    BUILD --> NODES[("Real nodes<br/>single Ctrl+Z reverts")]:::hou
    BUILD -.provenance.-> REC["agent.usd receipt<br/>decision · reasoning · revert"]:::side
    classDef artist fill:#DE8425,stroke:#7A4310,color:#1A1208
    classDef panel fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef bridge fill:#EEA958,stroke:#9C5A10,color:#1A1208
    classDef hou fill:#DE8425,stroke:#6B3A0C,color:#1A1208
    classDef side fill:#F2BC77,stroke:#B37A33,color:#1A1208
```

---

## ✦ Earlier releases — the short version

**Each row is one release's headline; the full record lives in [CHANGELOG.md](CHANGELOG.md).**

| Release | Headline |
|---|---|
| **v5.32.x** | **The render path is bounded** — every render tool used to funnel through one unbounded main-thread block. The WS path now renders through a bounded session flow (single-flight tokens, pollable status, a 60s cadence), and an XPU **foreground guard** refuses to launch a render inline against a cold OptiX shader cache — the condition that turned a bounded render into a multi-minute stall. Plus **BLACKBOX**: a session that dies silently leaves a capsule of everything in flight, and the next session detects it on startup; `render_watch.ps1` watches a stuck render from *outside* the process. (v5.32.1 reconciled the release metadata and refreshed the demo script to H22 reality.) |
| **v5.27.0** | **RETINA: the render receipt begins (M0)** — the governing blueprint for perception truth (truth cycle ⑤) committed and reconciled clean; a zero-cv2 host boundary pin *before* any perception code; two official-doc cross-references (HDK/HAPI) that caught a `.done`-sentinel design flaw on paper. A documentation-and-boundary foundation release. |
| **v5.26.0** | **H22 live-verified** — the whole transition proven against a *running* Houdini 22.0.368: 32 verdicts flipped provisional→verified-live, the memory integrity gate confirmed at fidelity 1.0 on the reorganized USD, and the last two silent breaks closed (Copernicus solver blocks + the major-aware wiring fold that makes Solaris network-building H22-native). A new `sidefx-cto` vendor-architect lens; an external "engineering memo" adjudicated-not-obeyed. |
| **v5.25.0** | **H22 has landed** — Houdini 22.0.368 dropped and SYNAPSE ran its own port machinery against it for the first time: the nine-step drop-week runbook complete, a three-lens CTO roadmap over 77 doc-scouted candidates, and the first two cycles merged (the Copernicus `planes()` silent-data-loss fix + the pilot Dispatcher port wave). H21 uninstalled; H22 the only live target. |
| **v5.24.0** | **The H22 drop-harness, reconciled** — a fresh drop-day blueprint arrived describing work that mostly already shipped; it was reconciled against reality (two gate-breaking conflicts caught before any write) rather than executed literally, and five genuinely-missing Phase-0 hardening gaps were built: a read-only mode guard, a new-family re-sweep spec, the scope fence extended to H22 rigging names, a theme-source seam, and the perception "before photo." No artist-facing behavior changed. |
| **v5.23.0** | **One Moneta · honest claims · the H22 blueprint harness** — the docs realigned to the code (Moneta *is* the memory substrate), the test badge dropped to its real green-floor, the local-first security posture stated plainly, and the H22 gap-closure blueprint got a one-command orchestrator that stops at every human gate. A documentation-integrity + H22-prep release; no product code changed. |
| **v5.22.0** | **The honest envelope + evidence-based anchors + the drop-day runbook** — receipts on *both* roads into Houdini (the audited `/mcp` bridge **and** the live panel path, recorded honestly, never faked); integrity flags now derived from runtime evidence instead of self-report (fidelity 1.0 = *verified*); composition validation extended to `payload` / `inherit` / `specialize` arcs; and the H22 drop compressed to one ordered, human-gated page. |
| **v5.21.0** | **Diagnostic truth + the self-protecting harness + the readiness verdict** — the scene interrogated live (dirty-propagation / recook / time-dependence cataloged per context — the truth class no external LLM can hold), the harness that guards its own green (full-suite ratchet, posture-scoped red-driver, fix-is-real probes), and an honest **READY (solo posture)** verdict with the trade-offs named instead of hidden. |
| **v5.20.0** | **H22 drop-day machine + utility flywheel + panel v9/v9.1** — the API-delta probe (proven empty on H21, caught 15 phantom spellings in our own emitters), the self-improving probe→review→wire loop, and the five-engine panel: **Claude · Gemini · NVIDIA Nemotron · Ollama · Custom**, the author token, one CHAT surface where **consent auto-surfaces** (v9.1), bundled Space Grotesk/Mono, a token-only meter. |
| **v5.19.0** | **The build half landed** — a validated proposal becomes real nodes under one undo group, with mid-build rollback. Plus the Solaris production-wiring correction (phantom per-shape lights purged, merge/sublayer strength rule live-probed). |
| **v5.18.0** | **Whole-graph validation** — every proposed node + wire checked against the live scene before anything is built; the occupied-input guard halts rather than sever artist wiring. |
| **v5.17.x** | **PDG cook-watcher fixed** (phantom event-handler idiom replaced with the real one) · **Solaris/USD parm names live-grounded** — silently-no-op'd light writes now land · **latency visibility** — the LLM turn is ~95% of each step, Houdini ops run 1–70 ms; the audit fsync moved off the hot path · license split so GitHub detects **pure MIT**. |
| **v5.16.0** | **Multi-provider selector** (first three engines) · prompt caching · one-call render-ready Solaris builds. |

---

## ✦ Install — 5 minutes

*Artists:* the steps below get you chatting — no command line beyond a copy-paste. *Developers* who want the editable install + test suite: [`docs/getting-started/installation.md`](docs/getting-started/installation.md).

Tested on **Windows 11 + Houdini 22.0.368** — the only build currently live-tested here. *(H21 code paths are retained and major-aware, but H21 is no longer installed on this machine.)* macOS / Linux: same steps, different slashes.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    DL["1 · Download<br/>the SYNAPSE folder"]:::step --> REG["2 · Run the installer<br/>(once)"]:::step
    REG --> KEY["3 · Add your API key<br/>to the .env"]:::step
    KEY --> OPEN["4 · Restart Houdini,<br/>open the panel"]:::step
    OPEN --> CHAT["Type 'make a box'<br/>→ it builds"]:::done
    classDef step fill:#E8963B,stroke:#9C5A10,color:#1A1208
    classDef done fill:#DE8425,stroke:#6B3A0C,color:#1A1208
```

**1 · Get the files** *(~1 min)* — green **Code ▸ Download ZIP**, unzip somewhere stable (e.g. `C:\Users\<you>\SYNAPSE`).
*Prefer git?* `git clone https://github.com/JosephOIbrahim/Synapse.git`
> ✅ **You should see** a `SYNAPSE` folder containing `python/`, `scripts/`, and `README.md`.

**2 · Tell Houdini about it** *(~1 min, once):*

```powershell
python scripts/install_synapse_package.py
```

The installer **auto-detects your Houdini prefs directory** and writes a package file pointing at this repo (`--pref-dir` overrides, `--dry-run` previews).
*No Python on PATH? Use Houdini's:* `& "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe" scripts/install_synapse_package.py` *(match your installed build/version.)*
> ✅ **You should see** a success line ending in the wired `python/` path — and **no** traceback.

**2b · Check it took** *(~10 sec — optional, but it's the whole install on one screen):*

```powershell
python scripts/install_synapse_package.py --verify
```

Read-only — it writes nothing, anywhere. It re-checks each condition from *state on disk*, so it still works long after the install output scrolled away.

> ✅ **You should see** every row `PASS` and a closing `All programmatic checks pass.`
> **If you see** a `FAIL` row, it names the fix — an unwired pref dir means re-run step 2 without `--dry-run`; a missing key means finish step 3.
> The three `MANUAL` rows are the checks nothing outside Houdini can honestly make (the menu entry, "make a box", the Connect button). They're never counted as passing — you confirm those yourself in step 4.

**3 · Add your Claude key** *(~2 min)* — make one at **console.anthropic.com** (`sk-ant-…`), then put it in a **`.env` at the repo root** (gitignored, auto-loaded). This keeps the key **scoped to SYNAPSE** — it is *not* set as a system-wide `ANTHROPIC_API_KEY`, so it can't collide with or bill other Anthropic tools on your machine.
*Other engines* go in the same `.env`. **Ollama needs no key** (it's your local server), and **Custom** is configured right in the panel (base URL · model · key).

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
NVIDIA_API_KEY=nvapi-...
```

**4 · Restart Houdini** *(~1 min)* → **New Pane Tab ▸ Synapse** → type **"make a box."**
> ✅ **You should see** the **Synapse** entry in the New Pane Tab menu *(title-case — scan for `Synapse`, not `SYNAPSE`)*, and *"make a box"* create a real geo node you can **Ctrl+Z**.

That's the whole loop — **start to chatting in ~5 minutes.** Everything is an ordinary Houdini action — **Ctrl+Z undoes it**.

<details>
<summary><strong>Troubleshooting</strong></summary>

| Symptom | Likely cause | Fix |
|---|---|---|
| **`Synapse` isn't in the Pane Tab menu** | Houdini loads packages only at launch | Fully restart Houdini, then run `python scripts/install_synapse_package.py --verify` — it confirms from disk which pref dirs are wired, so you don't need the original install output. |
| **"No API key" / won't connect** | The key line is missing from the repo-root `.env`, or Houdini was already open when you added it | Confirm the `ANTHROPIC_API_KEY` (and any `GEMINI_API_KEY` / `NVIDIA_API_KEY`) line in the `.env` at the repo root, then **relaunch Houdini from scratch** — the `.env` loads at startup. Fastest check: `--verify` (step 2b) reports the key as present or absent, and which source wins. To confirm it landed *inside* Houdini, in its Python Shell: `from synapse.host import auth; import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))` → `True`. |
| **`ModuleNotFoundError: No module named 'synapse'`** | The package path wasn't wired, or Houdini wasn't restarted | Run `--verify` (step 2b) — the `package file` row shows whether a pref dir points at this repo's `python/` directory. Fix, then restart Houdini. |
| **Panel loads but says it can't reach Houdini** | The bridge server isn't up — it never auto-starts | Click **Connect** in the panel **footer** strip (one click force-starts it; it then reads **Bridge ✓**). Only needed for external / MCP tools — ordinary chat runs in-process. |

</details>

---

## ✦ How it works — inside-out

Most AI-for-DCC tools run the agent in a **separate process** and reach in through a bridge — every call a round-trip, every tool a marshalling problem. **SYNAPSE inverts that:** the agent loop runs *inside* Houdini's own interpreter, dispatching tools as direct in-process calls against `hou`. The same pattern composes across the portfolio (a **Nuke** host, **Octavius**, the **Cognitive Bridge**).

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#E8963B','primaryTextColor':'#1A1208','primaryBorderColor':'#9C5A10','lineColor':'#7A4310','secondaryColor':'#EEA958','tertiaryColor':'#F2BC77','edgeLabelBackground':'#F2BC77','clusterBkg':'#F2BC77','clusterBorder':'#9C5A10'}}}%%
flowchart LR
    subgraph OUT ["Outside-in — the standard pattern"]
        direction LR
        A1["Agent process"] -.WebSocket / RPC.-> H1[("Houdini<br/>hou.*")]
    end
    subgraph IN ["Inside-out — SYNAPSE"]
        direction LR
        H2[("Houdini<br/>hou.*")]
        subgraph DAEMON ["Agent (in-process)"]
            A2["Agent loop"] --> D["Dispatcher"]
        end
        D -- in-process call --> H2
    end
    OUT ~~~ IN
```

The `cognitive/` layer is **pure Python** (zero `hou` imports, lint-enforced); `host/` is the Houdini-specific layer that swaps per DCC.

**The two roads in are not equally guarded — be precise about which one you're on:**

| Path | What it gets |
|---|---|
| **`/mcp` bridge** *(audited)* | The full anchor set — undo-wrapped, main-thread-safe, consent-gated, `IntegrityBlock` per operation |
| **Live `/synapse` handlers** *(RBAC-guarded)* | Main-thread-safe, and a path-qualified `IntegrityBlock` recorded honestly. **Undo-wrapping is partial** — the node create / set-parm / connect / delete handlers carry no `hou.undos.group`. `execute_python` / `execute_vex` run **ungated**. |

**Deeper dive + the full per-version history:** **[CHANGELOG.md](CHANGELOG.md)**.

---

## ✦ Project status

**Shipping (v5.33.0):**

- 🧵 **The marshal boundary** — the main thread never waits on itself: nine bypasses of the safe primitive deleted, a source lint keeping them out, live-verified on H22.0.368 across a ~25-call concurrent soak. *What it did **not** do: a render that runs on the main thread — the panel path **and** `/mcp` — still holds the UI while it runs, and cancel still can't interrupt an operation already running. Both stated plainly [above](#-new-in-v5330--the-main-thread-never-waits-on-itself).*
- 🎛️ **Artist panel v9.1** — five engines, undo-safe, 115 tools, a single **CHAT** surface where the review + consent gate auto-surface, live observability + latency instrumentation (WCAG/usability **G3-audited on H22's Qt 6.8.3**).
- 👁️ **RETINA — the render receipt (T0 live)** — the perception co-processor's first working tier: T0 file-truth verifies a render actually happened as declared (products, resolution, AOVs, completion sentinel, fingerprint), against a live-probed perception-truth catalog (truth cycle ⑤). The worker lives outside the Houdini process (zero `hou`, zero OpenCV in-host). The dead-`.done`-sentinel bug the crucible caught pre-merge is the receipt-honesty thesis proving itself.
- 🔬 **H22 live-verified** — the whole transition proven against a running Houdini 22.0.368: 32 verdicts flipped provisional→verified-live, the memory integrity gate confirmed at fidelity 1.0 on the reorganized USD, the PDG event surface and quarantine re-pins re-confirmed on the real interpreter.
- 🧩 **H22-native network building** — a major-aware connectivity catalog: `wire_by_label` + graph validator resolve H22 wiring on H22 and H21 wiring on H21, so proposed Solaris/COP networks validate against the build you're running (the demo-critical set-dressing path; verified live on H22.0.368, with H21 wiring from that build's last live probe — H21.0.671 is uninstalled and is not re-verified).
- 🔨 **Propose → validate → build** — the full pipeline, gated on probed wiring truth.
- 🧾 **The honest envelope** — both roads into Houdini leave `IntegrityBlock` receipts: the audited `/mcp` bridge, and path-qualified, never-faked live-path records the self-tuning advisor can see.
- 🔁 **Utility flywheel** — ratified cycles across wiring · Solaris context · diagnostic cook-truth · the H22 connectivity re-fold, self-improving on a human-ratified loop.
- 🟢 **Self-protecting harness** — full-suite green ratchet on every sprint (**4,642 / 0**, floor 4,275), a posture-scoped red-driver, fix-is-real behavioral probes, and forge-builds-crucible-attacks separation that caught a ⅓-implemented "loud-error" fix before it shipped.
- 🕵️ **Vendor-architect lens** — the `sidefx-cto` agent surfaces the non-obvious second-order changes a major brings; its first pass caught the memory-gate gap this release then closed live.
- 🌋 **Copernicus expansion, spec'd** — read/analysis + node-API layers deep and live-verified; the generative frontier (scaffold rebuilds, terrain emission, neural COP nodes with preflight honesty) is a live-probed build spec, next up.
- 🤝 **APEX MCP boundary held** — Houdini 22 keynote-announced a rigging-scoped MCP preview (not shipped); the ratified non-competing boundary stands unchanged.
- ⚙️ **In-process substrate** — two-tier provenance (audit write off the hot path), freeze **detection and degradation** (it reports and steps down; nothing in-process can un-wedge a parked main thread), bounded autonomy + a kill switch that stops the *next* step rather than one already running.

SYNAPSE is honest about its gaps — scaffolds self-report instead of faking success. The per-tool capability audit + full version record live in **[CHANGELOG.md](CHANGELOG.md)**.

---

## ✦ Dependencies

**Core — works standalone.** A clean clone runs without anything exotic:

- 💾 **Memory** persists to a plain **JSONL** file (the live default).
- 📦 **The Anthropic SDK is vendored** into the repo (`python/synapse/_vendor/`) — so **inside Houdini, no `pip install` is needed at all.**
- 🧬 **The vendored natives ship cp311 + cp313 win_amd64**, covering H22's embedded Python 3.13 and H20.5/21.x's 3.11.

Add a provider key and go.

**Two paths *do* need pip — neither is on the artist route:**

| Path | Needs |
|---|---|
| **External stdio MCP bridge** (`mcp_server.py`, run in your own Python) | `pip install mcp websockets` |
| **Developer test suite** | `pip install -e ".[dev]"` |

*Outside Houdini, on a Python with no matching vendored ABI, the vendor tree goes inactive and a real pip-installed SDK is used instead (`synapse._VENDOR_ABI_RISK` reports this).*

**Optional — Moneta.** Moneta is a private, encrypted memory substrate (repo `JosephOIbrahim/Moneta`). It's **built but default-OFF** — JSONL stays the default until you opt in:

- Flip it with the **`SYNAPSE_MEMORY_BACKEND`** env var → `moneta` (Moneta-backed) or `shadow` (JSONL primary + Moneta dual-write for parity). Any unknown value — or Moneta not being importable — **falls back to `jsonl` with a warning**, so the flag can never break startup.
- The package isn't bundled. CI checks it out via the **`MONETA_DEPLOY_KEY`** secret: when that secret is configured ~70 Moneta-gated tests run; when it's absent those steps and tests skip and **CI stays green**. Wiring details in [`docs/MONETA_FOLLOWUPS.md`](docs/MONETA_FOLLOWUPS.md).

---

## ✦ Repository layout

<details>
<summary><strong>Show the tree</strong></summary>

```
python/synapse/
├── cognitive/                  # zero hou imports (lint-enforced)
│   ├── dispatcher.py           # Dispatcher + AgentToolError
│   ├── agent_loop.py           # Anthropic SDK turn runner
│   ├── graph_validator.py      # whole-graph validation (P3/P4/P5 + P3e slot semantics)
│   ├── tools/                  # pure-Python tool implementations + committed truth catalogs
│   └── ws_passthrough.py       # H22 port wave: legacy WS handler wrapped as an in-process Dispatcher tool (2 of 11 sub-waves merged)
├── host/                       # Houdini-specific (hou / hdefereval OK)
│   ├── daemon.py               # SynapseDaemon lifecycle
│   ├── auth.py                 # API key resolver (.env + env var + hou.secure probe)
│   ├── graph_builder.py        # build half — one undo group, TOCTOU re-check, rollback
│   ├── tops_bridge.py          # PDG event bridge (perception, Phase A)
│   └── scene_load_bridge.py    # auto-warm on AfterLoad (Phase B)
├── providers/apex_mcp.py       # H22 APEX MCP truth-contract envelope (boundary-ratified)
├── memory/                     # Moneta-backed memory substrate
├── panel/                      # artist-facing copilot panel (Qt / PySide6)
│   ├── providers/              # five engines — anthropic / gemini / nemotron / ollama / custom (raw http.client, no SDK)
│   ├── synapse_panel.py        # the docked panel — rail + author token, single CHAT surface (consent auto-surfaces), "/" palette, Connect, honest Stop
│   ├── claude_worker.py        # background QThread — streams the engine + tool loop
│   ├── tool_executor.py        # main-thread tool dispatch (per-tool timeouts)
│   └── designsystem/           # vendored tokens / qss / components + bundled Space Grotesk/Mono
├── server/                     # live transport + safety wiring
│   ├── main_thread.py          # THE marshal — off-main posts + bounded wait, on-main short-circuits to a direct call
│   ├── marshal_guard.py        # typed errors + inline-overrun telemetry for main-thread work
│   ├── freeze_chain.py         # process-wide watchdog: 5s detect → 30s escalate → halt (reports + degrades; cannot un-wedge main)
│   ├── solaris_graph_templates.py  # one-call render-ready Solaris topologies
│   └── handlers*.py            # command handlers — inline undo, cross-client mutation lock
├── core/                       # canonical tables — timeouts.py (per-tool budgets) · wiring.py (wire_by_label vs the probed catalog)
└── _vendor/                    # anthropic + deps — dual-ABI cp311 + cp313 win_amd64 (H22's py3.13 covered)

host/                           # repo-root live-introspection probes (nodetypes · connectivity · runtime symbols · cook API · cook-truth perturbation trials)
scripts/                        # installer · h22_api_delta.py drop-day probe · flywheel_review_{wiring,lop}.py · mine_lop_knowledge.py
tests/                          # 4,642 passing (Moneta-gated + Houdini-gated tests skip on a clean clone)
                                #   test_marshal_lint.py    bans the unsafe main-thread primitive repo-wide
                                #   test_marshal_hostile.py adversarial suite for the marshal boundary
harness/                        # the self-verifying loop — five tracks (H22 · v6 · context · studio · diagnostic), boundary guardrails, the full-suite green ratchet, the readiness verdict
docs/                           # installation · upgrade · boundary contract · coexistence · reviews
mcp_server.py                   # WebSocket adapter for external MCP clients
```

</details>

> **Security posture — local-first, single-user.** The MCP surface (`mcp_server.py` / the in-Houdini `hwebserver` `/mcp` handler in `python/synapse/mcp/server.py`) enforces Origin validation (DNS-rebinding protection) and supports Bearer-token auth, with `SYNAPSE_DEPLOY_MODE` defaulting to `local`. The design target is a single artist on localhost; a handler-layer consent gate is the documented prerequisite before any multi-user or studio deployment.
>
> **Be precise about the blast radius:**
>
> - **One server, one port.** The bridge serves **both** surfaces — WebSocket `/synapse` and HTTP `/mcp` — from **one** `hwebserver` on **one port (default 9999)**.
> - **They cannot be separated.** There is no configuration that publishes `/mcp` while keeping `/synapse` private.
> - **`execute_python` / `execute_vex` run ungated** on the live `/synapse` handler path.
>
> **Therefore: exposing that single port to an untrusted network exposes arbitrary code execution inside your Houdini. Keep it on localhost.** Full detail: [`docs/mcp/SETUP.md`](docs/mcp/SETUP.md#authentication).

---

## License

**MIT** — see [LICENSE](LICENSE). Use, modify, and ship the source freely under copyright.

Certain methods are **patent-pending** (documented separately in [PATENTS](PATENTS)). The MIT grant covers **copyright, not patents** — the patent notice doesn't change the MIT terms, and MIT grants no license under any patent claims.
