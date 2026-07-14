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
  <a href="tests"><img src="https://img.shields.io/badge/tests-4275%20passing-brightgreen.svg" alt="Tests"></a>
  <a href="CHANGELOG.md"><img src="https://img.shields.io/badge/changelog-v5.24.0-1e293b.svg" alt="Changelog"></a>
</p>

> ⚡ **TL;DR** — an AI panel *inside* Houdini: type **"make a box,"** get a real node. Every action is ordinary Houdini, so **Ctrl+Z** takes it back — and it's all recorded (receipts, not magic). Five engines, 115 tools. **Install ↓ in ~5 min.**

> 🧪 **The moat, in one line:** every other Houdini copilot reasons from docs and memory — SYNAPSE **probes the running Houdini and commits what it finds** (five truth catalogs and counting: wiring, Solaris context, capability, readiness, and now **live cook behavior**). Docs drift. Probes don't.

---

### ✦ The idea, in plain terms

SYNAPSE lives **inside** Houdini and turns plain English into real work:

- 🧠 **It works inside Houdini, not off to the side** — the assistant runs in Houdini itself, so there's no separate app to launch and nothing to wait on; it answers right where you're working.
- 🔁 **Your words become real nodes** — every request is just a normal Houdini action. Don't like it? **Ctrl+Z** takes it back.
- 🧾 **It keeps the receipts** — every change is undo-safe *and* recorded, so you can always see what it did and why. That's the differentiator — not magic, receipts.
- 🔌 **Pick your AI · 115 tools** — choose **Claude · Gemini · NVIDIA Nemotron · Ollama (local) · Custom** in the panel and switch whenever you like.
- 📜 **Free to use (MIT license)** ([LICENSE](LICENSE)) with **patent-pending methods** ([PATENTS](PATENTS)) — the license covers the code, not the patents.

---

### ✦ Map — you are here

| You want… | Read… |
|---|---|
| **The 30-second pitch** | *The idea, in plain terms* (above) + *What it is* |
| **What's new in v5.24.0** | *New in v5.24.0* — the H22 drop-harness reconciled + five Phase-0 hardening gaps |
| **How AI network-building stays safe** | *Propose → validate → build* |
| **To install it** | *Install — 5 minutes* |
| **The architecture** | *How it works — inside-out* |
| **Every release + per-tool detail** | [CHANGELOG.md](CHANGELOG.md) |

---

## ✦ What it is

A docked **SYNAPSE panel** inside Houdini. You type what you want — *"make a box"*, *"create a solaris network ending with rendersettings using karma xpu"* — and it **builds it in your live scene.** Chat in, real nodes out.

- ⚡ **In-process** — the agent runs in Houdini's own Python; tools are direct `hou.*` calls, not a slow round-trip bridge.
- ↩️ **Undo-safe** — everything it does is an ordinary Houdini action. **Ctrl+Z undoes it.** Every mutation leaves a provenance record.
- 🔌 **Multi-provider** — pick **Claude · Gemini · NVIDIA Nemotron · Ollama · Custom** right in the panel; swap engines mid-session.
- 🎬 **Built for the work** — SOPs, **Solaris / USD, Karma, COPs, PDG / TOPs, MaterialX** — 115 tools.

> ✅ *"make a box" → a real geo node, confirmed in graphical Houdini 21.0.671.*

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
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
    classDef artist fill:#334155,stroke:#f59e0b,color:#f1f5f9
    classDef panel fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef bridge fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef hou fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef side fill:#1e293b,stroke:#64748b,color:#cbd5e1
```

**The panel, briefly (v9.1):** a persistent rail (live state + a real **Stop**), one **CHAT** surface where the build review + **consent gate auto-surface** when a build needs approval — consent comes to you, then hands back on accept/revert — the **author token** (engine + model in one rail control), an **`Aa`** control that scales only what you *read*, a bundled **Space Grotesk / Space Mono** type system, a token-only meter, and a **`/`** command palette over every tool.

---

## ✦ New in v5.24.0 — the H22 drop-harness, reconciled

**A new drop-day blueprint arrived describing a fresh "Phase 0." It was authored above the code — most of it already shipped, and two of its steps would have broken the working gate. So it was reconciled, not run: mapped to reality, conflicts resolved, and only the genuinely-missing pieces built. No artist-facing behavior changed.**

- 🧭 **Reconciled, not executed** — a read-only sweep mapped every task to disk first ([the record](docs/H22_PHASE0_RECONCILIATION.md)). Two conflicts caught before any write: the blueprint's repo-root `drop.json` would have *false-armed* the H22 pipeline (the real gate keys on a file's **existence** at `harness/state/`), and it mis-named the scope guard. Both fixed the right way instead of the literal way.
- 🚦 **Five Phase-0 hardening gaps, each adversarially tested** — a read-only **mode guard** that refuses drop-day work until H22 actually ships; the **re-sweep spec** that catches brand-new H22 node families the existing probes can't see; the **scope fence** extended to H22 rigging names (splat *geometry* stays in, splat *rig* stays out); a **theme-source seam** so H22's Theme Editor swaps in behind one file; and the perception **"before photo"** for the post-drop diff.
- 🔒 **Honest about the gaps** — the three human gates stay human: the merge, the `drop.json` write on drop day, and the counsel placement of the IP note. **4,275 tests passing** (+48, zero failures) · **MODE A still holds**.

> *The last **product-feature** release is **v5.22.0** (in the table below). Houdini 22 ships **2026-07-15** — see [H22-ready before H22 ships](#-h22-ready-before-h22-ships).*

---

## ✦ H22-ready before H22 ships

**Houdini 22 lands mid-July. SYNAPSE meets it with a drop-day machine that's already proven.**

- 🎯 **Drop-day probe** — `scripts/h22_api_delta.py` diffs the running build's symbol table, node-type catalog, and punycode parm encodings against committed H21 baselines. Run against 21.0.671 the identity diff is **empty** — the machine is proven *before* the drop. *(First run against our own emitters, it caught **15 phantom spellings** — now purged.)*
- 📋 **Drop-day runbook** *(v5.22.0)* — [`docs/studio/DROP_DAY.md`](docs/studio/DROP_DAY.md): one page, ordered, human gates marked. Drop day is verification, not surgery.
- 🗂️ **Per-major symbol tables** — scout + doctor key on the running Houdini major; the H21 table is never overwritten by an H22 run.
- 🧪 **Dual-build test axis** — `SYNAPSE_TEST_HOUDINI_BUILD` points the suite at either build.
- 🤝 **APEX MCP boundary contract** — Houdini 22 ships a native APEX MCP. The ratified boundary ([`docs/SYNAPSE_H22_BOUNDARY.md`](docs/SYNAPSE_H22_BOUNDARY.md)): SYNAPSE **consumes it as a truth-contract provider** (observed-vs-claimed envelope, fail-loud) — it never competes with it. Coexistence rules: [`docs/MCP_COEXISTENCE.md`](docs/MCP_COEXISTENCE.md). SYNAPSE's lane stays the receipts: undo-safe mutations + recorded provenance.
- 🔒 **Multi-client hardening** — hash-guarded rollback that never pops a foreign (artist or other-client) undo block, plus `external_change_detected` attribution when someone else moved the scene.
- 🌀 **Cook-behavior diffs on day one** *(v5.21.0)* — the diagnostic-truth catalogs are **build-stamped and major-agnostic**: under H22 they go stale-loud and re-probe with zero code edits, so *how H22 changed cook behavior* becomes a diffable artifact instead of forum anecdotes.

**How the drop stays boring:** de-risk everything on H21 *now*, so drop day is verification, not surgery. One human write — the three version numbers into `drop.json` — arms the H22 pipeline; nothing before it can expand.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    A["MODE A · now (H21)<br/>de-risk: probe · flywheel · panel · clean-install<br/>+ Phase-0 hardening: mode guard · scope fence · theme seam · re-sweep spec"]:::hou -->|"assert_mode_b holds<br/>until a human writes drop.json<br/>python · usd · pyside"| G{{"Drop day"}}:::side
    G --> B["MODE B · H22<br/>pipeline arms — verify, not surgery"]:::panel
    classDef panel fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef hou fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef side fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
```

---

## ✦ The utility flywheel — probe-verified truth on a loop

**SYNAPSE improves itself on a loop: ground the AI's Houdini knowledge in probe-verified truth → review its own code against that truth → wire the truth into the live path.** Nothing enters the live path on memory alone — memory drifts; probes don't. Every cycle runs the same **EXPLORE → REVIEW → SCAFFOLD** contract; a human ratifies each new cycle; and where a catalog and a code comment disagree, **the catalog wins**.

**Three cycles have shipped — three kinds of truth** (with capability + readiness catalogs behind them):

- 🔌 **① Wiring truth — *how* nodes connect.** `host/introspect_connectivity.py` instantiates **282 node types** headless and records their real input/output counts + slot labels → a committed, integrity-checked catalog. `wire_by_label()` (`python/synapse/core/wiring.py`) then resolves inputs by **probed label, never remembered index** (fail-loud on an unknown label/type), and the validator's **slot-semantic checks (P3e)** reject an edge into an input the type doesn't have. *Receipts: the review sweep ran **141 sites, 0 critical**; the cycle fixed **2 known miswires** (swapped solver inputs).*
- 🧭 **② Solaris context truth — *what* the nodes are.** A corpus-authored, probe-cross-checked **LOP / Solaris knowledge catalog** teaches the validator the semantics wiring truth can't see. It **hard-rejects phantom LOP types** the model reaches for out of SOP habit — there is no `grid` or `plane` LOP (use a `cube`) — and **advises** when an `assignmaterial` has no material source upstream (a `materiallibrary`, *or* a `reference`/`sublayer` layer that already authors the materials). *Receipts: **20 checks, 0 critical**; the ordering rule was hardened from a hard error to an advisory after adversarial review caught it would false-reject valid reference/sublayer material graphs.*
- 🌀 **③ Diagnostic truth — what the scene *does* when poked** *(new in v5.21.0)*. Perturbation probes catalog live **dirty-propagation, recook triggers, and time-dependence** per context (SOP/LOP/COP/DOP) — the one truth class no external LLM can hold, because it only exists as live cook-state. *Receipts: the API probe caught the track's own spec citing **H18-era phantom spellings** (the cook surface lives on `hou.OpNode`, not `hou.Node`); the catalog's first run captured a real divergence — **a COP rewire dirties upstream nodes SOP semantics say it shouldn't**. Staged next on this catalog: `synapse_explain_recook` — ask "why did this recook?" and get an answer cited to a probe trial.*

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    EXP["EXPLORE<br/>probe-verified ground truth<br/>live probe · or probe-checked corpus"]:::hou -->|"committed, integrity-checked catalog"| REV["REVIEW<br/>sweep the code vs the catalog<br/>0 critical"]:::bridge
    REV -->|"findings → fixes"| SCAF["SCAFFOLD<br/>truth into the live path<br/>wire_by_label · validator P3e + LOP · test pins"]:::panel
    SCAF -->|"new truth classes"| NEXT["Queue<br/>human ratifies each new cycle"]:::side
    NEXT -->|"cycle N+1 · so far: ① wiring · ② Solaris context · ③ diagnostic (cook truth) · queued: H22 discovery re-sweep"| EXP
    classDef panel fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef bridge fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef hou fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef side fill:#1e293b,stroke:#64748b,color:#cbd5e1
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

It also wires **Solaris the way production expects** — live-probed against 21.0.671: the **Component Builder** pattern for assets, the proper **`rendersettings` → render** terminal, **layered** scene assembly, the real H21 light nodes (the per-shape light names don't exist), and the actual merge/sublayer strength rule (**higher input index wins**).

Verified end-to-end on **live Houdini 21.0.671** — build, single-undo revert, TOCTOU halt, and forced-failure rollback all pass.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    ASK["Artist<br/>'build a karma setup'"]:::artist --> PROP["Propose<br/>nodes + wires, on paper"]:::panel
    PROP --> VAL["Validate<br/>vs your live scene · vs the wiring catalog (P3e) · vs the Solaris knowledge catalog<br/>inputs · wire types · slot labels · phantom LOP types · material-source ordering · occupied inputs"]:::bridge
    VAL -->|"all clear · parked"| BUILD["Build — one undo group<br/>create → wire → read back"]:::hou
    VAL -.->|"something's off"| STOP["Stop · nothing touched"]:::side
    BUILD --> NODES[("Real nodes<br/>single Ctrl+Z reverts")]:::hou
    BUILD -.provenance.-> REC["agent.usd receipt<br/>decision · reasoning · revert"]:::side
    classDef artist fill:#334155,stroke:#f59e0b,color:#f1f5f9
    classDef panel fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef bridge fill:#1e293b,stroke:#f59e0b,color:#f1f5f9
    classDef hou fill:#334155,stroke:#22c55e,color:#f1f5f9
    classDef side fill:#1e293b,stroke:#64748b,color:#cbd5e1
```

---

## ✦ Earlier releases — the short version

**Each row is one release's headline; the full record lives in [CHANGELOG.md](CHANGELOG.md).**

| Release | Headline |
|---|---|
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

Tested on **Windows 11 + Houdini 21.0.671**. macOS / Linux: same steps, different slashes.

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
flowchart LR
    DL["1 · Download<br/>the SYNAPSE folder"]:::step --> REG["2 · Run the installer<br/>(once)"]:::step
    REG --> KEY["3 · Add your API key<br/>to the .env"]:::step
    KEY --> OPEN["4 · Restart Houdini,<br/>open the panel"]:::step
    OPEN --> CHAT["Type 'make a box'<br/>→ it builds"]:::done
    classDef step fill:#1e293b,stroke:#3b82f6,color:#f1f5f9
    classDef done fill:#334155,stroke:#22c55e,color:#f1f5f9
```

**1 · Get the files** *(~1 min)* — green **Code ▸ Download ZIP**, unzip somewhere stable (e.g. `C:\Users\<you>\SYNAPSE`).
*Prefer git?* `git clone https://github.com/JosephOIbrahim/Synapse.git`
> ✅ **You should see** a `SYNAPSE` folder containing `python/`, `scripts/`, and `README.md`.

**2 · Tell Houdini about it** *(~1 min, once):*

```powershell
python scripts/install_synapse_package.py
```

The installer **auto-detects your Houdini prefs directory** and writes a package file pointing at this repo (`--pref-dir` overrides, `--dry-run` previews).
*No Python on PATH? Use Houdini's:* `& "C:\Program Files\Side Effects Software\Houdini 21.0.671\bin\hython.exe" scripts/install_synapse_package.py`
> ✅ **You should see** a success line ending in the wired `python/` path — and **no** traceback.

**3 · Add your Claude key** *(~2 min)* — make one at **console.anthropic.com** (`sk-ant-…`), then put it in a **`.env` at the repo root** (gitignored, auto-loaded). This keeps the key **scoped to SYNAPSE** — it is *not* set as a system-wide `ANTHROPIC_API_KEY`, so it can't collide with or bill other Anthropic tools on your machine.
*Other engines* go in the same `.env`. **Ollama needs no key** (it's your local server), and **Custom** is configured right in the panel (base URL · model · key).

```
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=AIza...
NVIDIA_API_KEY=nvapi-...
```

**4 · Restart Houdini** *(~1 min)* → **New Pane Tab ▸ SYNAPSE** → type **"make a box."**
> ✅ **You should see** the **SYNAPSE** entry in the New Pane Tab menu, and *"make a box"* create a real geo node you can **Ctrl+Z**.

That's the whole loop — **start to chatting in ~5 minutes.** Everything is an ordinary Houdini action — **Ctrl+Z undoes it**.

<details>
<summary><strong>Troubleshooting</strong></summary>

| Symptom | Likely cause | Fix |
|---|---|---|
| **SYNAPSE isn't in the Pane Tab menu** | Houdini loads packages only at launch | Fully restart Houdini; confirm the installer reported success. |
| **"No API key" / won't connect** | The key line is missing from the repo-root `.env`, or Houdini was already open when you added it | Confirm the `ANTHROPIC_API_KEY` (and any `GEMINI_API_KEY` / `NVIDIA_API_KEY`) line in the `.env` at the repo root, then **relaunch Houdini from scratch** — the `.env` loads at startup. Verify in Houdini's Python Shell: `from synapse.host import auth; import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))` → `True`. |
| **`ModuleNotFoundError: No module named 'synapse'`** | The package path wasn't wired, or Houdini wasn't restarted | The installer prints the path it wired — confirm it points at the repo's `python/` directory, then restart Houdini. |
| **Panel loads but says it can't reach Houdini** | The in-process bridge server isn't up yet | Click **Connect** in the panel rail (one click force-starts it). |

</details>

---

## ✦ How it works — inside-out

Most AI-for-DCC tools run the agent in a **separate process** and reach in through a bridge — every call a round-trip, every tool a marshalling problem. **SYNAPSE inverts that:** the agent loop runs *inside* Houdini's own interpreter, dispatching tools as direct in-process calls against `hou`. The same pattern composes across the portfolio (a **Nuke** host, **Octavius**, the **Cognitive Bridge**).

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1e293b','primaryTextColor':'#f1f5f9','primaryBorderColor':'#0f172a','lineColor':'#f59e0b','secondaryColor':'#334155','tertiaryColor':'#475569'}}}%%
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

The `cognitive/` layer is **pure Python** (zero `hou` imports, lint-enforced); `host/` is the Houdini-specific layer that swaps per DCC. Every mutation is undo-wrapped, main-thread-safe, and leaves a provenance receipt.

**Deeper dive + the full per-version history:** **[CHANGELOG.md](CHANGELOG.md)**.

---

## ✦ Project status

**Shipping (v5.24.0):**

- 🎛️ **Artist panel v9.1** — five engines, undo-safe, 115 tools, a single **CHAT** surface where the review + consent gate auto-surface, live observability + latency instrumentation (WCAG/usability **G3-audited**).
- 🔨 **Propose → validate → build** — the full pipeline, gated on probed wiring truth.
- 🧾 **The honest envelope** — both roads into Houdini leave `IntegrityBlock` receipts: the audited `/mcp` bridge, and path-qualified, never-faked live-path records the self-tuning advisor can see.
- 🔬 **Evidence-based anchors** — the undo + main-thread integrity flags come from runtime evidence, not self-report (fidelity 1.0 = *verified*); composition validation covers `reference`, `payload`, `inherit`, and `specialize` arcs.
- 🔁 **Utility flywheel** — three ratified cycles (wiring · Solaris context · **diagnostic cook-truth**), self-improving on a human-ratified loop, with capability + readiness catalogs behind them.
- 🌀 **Diagnostic-truth catalogs** — live dirty-propagation / recook / time-dependence trials per context, golden-reproducible; the recook-explainer + callback-debugger handlers staged on them.
- 🟢 **Self-protecting harness** — full-suite green ratchet on every sprint, a posture-scoped red-driver, fix-is-real behavioral probes, and a **READY (solo posture)** studio-readiness verdict with the trade-offs named.
- 🚀 **H22 drop-day machine** — API-delta probe + dual-build test axis, proven empty against H21; cook-behavior diffs on day one.
- 🧭 **H22 drop-harness, reconciled** *(v5.24.0)* — the drop-day blueprint mapped to disk (not run literally), its two gate-breaking conflicts caught, and five Phase-0 hardening gaps landed — a read-only mode guard, the new-family re-sweep spec, the scope fence extended to H22 rigging names, a theme-source seam, and the perception "before photo." MODE A still holds; all three human gates intact.
- ⚙️ **In-process substrate** — two-tier provenance (audit write off the hot path), freeze-safety, bounded autonomy + a kill switch.
- 🎬 **Live-grounded Solaris / USD** parameter names + the ratified APEX-MCP coexistence boundary.

SYNAPSE is honest about its gaps — scaffolds self-report instead of faking success. The per-tool capability audit + full version record live in **[CHANGELOG.md](CHANGELOG.md)**.

---

## ✦ Dependencies

**Core — works standalone.** A clean clone runs without anything exotic. Memory persists to a plain **JSONL** file (the live default), and the **Anthropic SDK is vendored** into the repo (`python/synapse/_vendor/`) — no `pip install anthropic` required. Add a provider key and go.

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
│   └── tools/                  # pure-Python tool implementations + committed truth catalogs
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
│   ├── freeze_chain.py         # process-wide watchdog: 5s detect → 30s escalate → halt
│   ├── solaris_graph_templates.py  # one-call render-ready Solaris topologies
│   └── handlers*.py            # command handlers — inline undo, cross-client mutation lock
├── core/                       # canonical tables — timeouts.py (per-tool budgets) · wiring.py (wire_by_label vs the probed catalog)
└── _vendor/                    # anthropic + deps, CP311 win_amd64

host/                           # repo-root live-introspection probes (nodetypes · connectivity · runtime symbols · cook API · cook-truth perturbation trials)
scripts/                        # installer · h22_api_delta.py drop-day probe · flywheel_review_{wiring,lop}.py · mine_lop_knowledge.py
tests/                          # 4,275 passing (Moneta-gated tests skip on a clean clone)
harness/                        # the self-verifying loop — five tracks (H22 · v6 · context · studio · diagnostic), boundary guardrails, the full-suite green ratchet, the readiness verdict
docs/                           # installation · upgrade · boundary contract · coexistence · reviews
mcp_server.py                   # WebSocket adapter for external MCP clients
```

</details>

> **Security posture — local-first, single-user.** The MCP surface (`mcp_server.py` / the in-Houdini `hwebserver` `/mcp` handler in `python/synapse/mcp/server.py`) enforces Origin validation (DNS-rebinding protection) and supports Bearer-token auth, with `SYNAPSE_DEPLOY_MODE` defaulting to `local`. The design target is a single artist on localhost; a handler-layer consent gate is the documented prerequisite before any multi-user or studio deployment.

---

## License

**MIT** — see [LICENSE](LICENSE). Use, modify, and ship the source freely under copyright.

Certain methods are **patent-pending** (documented separately in [PATENTS](PATENTS)). The MIT grant covers **copyright, not patents** — the patent notice doesn't change the MIT terms, and MIT grants no license under any patent claims.
