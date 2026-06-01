# SYNAPSE Panel — Redesign Brief

> First-principles redesign of the SYNAPSE Houdini panel. Design-led (the
> "Pentagram" bar: one point of view, ruthless restraint, every pixel earns its
> place), **1:1 with available functionality**, production-ready Python,
> artist-friendly, shipped public + installed locally.
>
> Grounded in a 5-lens read-only audit of the live repo (panels · functionality ·
> design · ship · runtime). Date: 2026-06-01.

---

## 1. The problem (what the audit found)

**Three competing panels, none of them whole.**

| Family | File | Status | Has | Lacks |
|---|---|---|---|---|
| **Legacy monolith** | `houdini/python_panels/synapse_panel.pypanel` (3032-line CDATA) | **the one that actually ships** (install.py + shelf) | rich features: slash commands, Ctrl+K palette, activity log, agent-health, image attach, direct-Claude streaming | **no gate UI** (consent shown only as passive log lines — a constitutional safety gap), untestable, unmaintainable |
| **Modular chat** | `python/synapse/panel/chat_panel.py` via `synapse_chat.pypanel` | **the only tested one** — but *not installed* | clean modules, the full **GateWidget**, HDA wizard, WS-bridge | functionally thinner: no palette, no activity, no agent-health, no image attach |
| **Orphaned admin** | `python/synapse/ui/panel.py` | registered by nothing | 5 memory/server tabs | unreachable; duplicates connection/health |

So the **shipped panel ≠ the tested panel ≠ a third orphan**, on two *incompatible* LLM architectures (panel-side `ClaudeWorker` vs server-side `route_chat`), with **two installers**, **three divergent design-token sources**, and an **orphaned custom icon set** that never renders.

**The 1:1 gap.** The server exposes **110 registry tools** (the "~108"), grouped into 6 cognitive domains. The panel today calls exactly **one** server command — `route_chat` — and lets the LLM pick tools. Direct artist affordances exist for ~3 domains (memory, HDA mode, 5 prompt-macro pills). **~0% direct UI** for: 21 COPs tools, 16 USD/Solaris, 9 render orchestrators, 18 TOPS/PDG, 4 materials, 10 scene/node ops, execution, batch, knowledge/recipes/metrics. *That invisibility is the whole reason this redesign exists.*

---

## 2. The decisions (the forks, resolved)

1. **ONE panel, ONE interface.** Collapse the three families into a single modular panel package with a **thin `.pypanel` loader** at `houdini/python_panels/` (the only auto-load location). One interface name. Update `install_synapse_package.py`, `synapse.shelf`, `synapse_shelf.open_panel()`, and `tests/test_design_system.py` **in lockstep**. Drop `ui/panel.py`; fold its memory-browse tabs into the Trust drawer (below). Retire the legacy `install.py` + clipboard shelf flow.

2. **Keep the proven chat runtime; close the safety gap.** Keep the **`ClaudeWorker` direct-stream + MCP-first/signal-fallback tool path** — it ships, it works, and it carries the rich feature set (lowest-risk foundation). **Wire `GateWidget` into it via `HumanGate` callbacks** so consent is a real, actionable surface — not passive log lines. (A full WS-`route_chat` migration is a deliberate *later* pass, explicitly out of scope here to bound risk.) All four bridge safety anchors already attach at `bridge_adapter`; we surface them.

3. **Registry-driven IA.** The 110-tool registry already annotates every tool `read_only / destructive / idempotent` and groups them into 6 domains. The capability surface is **generated from that metadata**, not hand-curated: `read_only` → instant quick actions; `destructive` → gated/confirm affordances keyed to the INFORM/REVIEW/APPROVE/CRITICAL taxonomy. The IA stays correct as tools are added.

4. **Vendor the design system.** Kill the 3-way token split and the un-shipped `~/.synapse/design` runtime dependency. **One token module + one component library + bundled icons (and fonts where licensable)** ride the package on `PYTHONPATH`/`HOUDINI_PATH`. Zero raw hex in widget code.

---

## 3. The design system (Pentagram pillars)

**Principle: monochrome restraint + one intelligent accent. Warmth through type and voice, not decoration.**

- **Color — one source, vendored.** A carbon ramp with explicit *surface-elevation* steps (`ground → panel → surface → raised → border`) so VOID/CARBON/GRAPHITE stop being used interchangeably, plus a single accent **SIGNAL** (cyan `#00D4FF`) for intelligence/connectivity, and a four-hue **status grammar** (FIRE `#FF6B35` / GROW `#00E676` / WARN `#FFAB00` / ERROR `#FF3D71`). A complete **interaction-state ramp** (hover / press / disabled / focus) as tokens — not the ad-hoc `#33DDFF`/`#484848` invented today. Base surface tuned near Houdini's window grey for a deliberate docked feel; a **high-contrast variant** for accessibility; accent text validated to **WCAG AA** at the smallest size (cyan body text currently fails — it becomes label/icon-only).
- **Type — roles, not sizes.** Sans (DM Sans) for conversation + buttons (warmth); mono (JetBrains Mono) reserved for **code / paths / data / labels** only — shedding the "terminal tool" feel. Define roles: `display · title · body · label · code · status`. Bundle the fonts via `QFontDatabase` at init, with guaranteed fallbacks (Segoe UI / Consolas). ONE user font-scale that drives **both** the QSS chrome and the chat HTML (today only chat scales).
- **Space — load-bearing.** The `4 / 8 / 16 / 24 / 40` scale pulled from tokens for *every* margin/padding. Defined vertical rhythm; chat honors a content max-measure (not a 40px hardcoded margin); reflow at `PANEL_MIN_WIDTH = 280`.
- **Components — a real library.** Tokenized `QWidget` subclasses consumed everywhere, replacing 314 inline-style occurrences and 21 hardcoded-hex files: `Button` (primary/secondary/ghost/danger) · `Pill` · `Card` · `Badge/Chip` · `StatusDot` (one status grammar, replacing the three vocabularies "Connected"/"Ready"/"Fidelity 1.0") · `ProgressBar` · role `Label`s. QSS generated from the one token table.
- **Icons — wire the orphan.** Render the existing custom mark family (synapse mark in header/tab, replacing `MISC_python`; inspect/execute/verify/document/profile on actions). Ship rasterized **PNG @1x/@2x** (Qt SVG is inconsistent in Houdini), SVG as progressive enhancement. Retire emoji memory tiers + Unicode status glyphs.
- **Motion — tokenized.** Qt QSS has no transition primitive; a small `QPropertyAnimation` helper with tokenized durations/easings (`fast 120ms / base 200ms / slow 320ms`, OutCubic) drives page fades, hover elevation, gate flash, and a typing indicator re-implemented as an overlay (not document mutation).
- **Voice — de-jargon (the synapse voice guide).** `HALT → Stop` *with* a confirm (matching CRITICAL's risk model); hide raw `ws://` URLs behind a status affordance; translate `Fidelity 1.0 / 0 violations` into plain reassurance; drop CHARMANDER/CHARMELEON/CHARIZARD from the artist surface (plain *memory: flat / structured / composed*). Gate cards keep their safety semantics but lose the high-anxiety pulsing-red-countdown styling.

---

## 4. Information architecture — three zones + two ribbons

The panel is, at root, **a conversation with a capable studio partner, plus direct access to its capabilities, plus the means to trust it.** Three zones:

- **CONVERSE** (dominant) — the agent chat. `ChatDisplay` as the single renderer (delete the legacy inline-HTML duplicate). Clickable node links, grouped messages, streaming, overlay typing indicator.
- **ACT** (the 1:1 surface) — deterministic, artist-initiated access to all 110 tools:
  - a **context-aware action row** above the input (network-type adaptive: SOP/LOP/COP/TOP… → the right verbs), unifying the three competing quick-action systems into one;
  - a **Ctrl+K command palette** over the full tool registry + recipes, grouped by the 6 domains, with `read_only`/`destructive` driving the affordance (instant vs gated).
- **TRUST** (collapsible drawer, auto-surfacing) — one safety/observability surface: **Gates** (consent cards, incl. INFORM/REVIEW which are suppressed today), **Integrity** (fidelity in plain words), **Activity** (a real tool-operation log from integrity blocks + the audit chain, distinct from the memory feed), **Health** (the advisor — *and the place RSI Line O's persisted `RecommendationHistory` lands*). Folds in the orphaned panel's memory-browse (Context/Log/Search).

Two quiet ribbons frame them: a **Context ribbon** (where am I — network · selection · frame · memory stage) and a **Connection/Stop** footer.

---

## 5. Layout

```
┌──────────────────────────────────────────────┐
│ ◖ SYNAPSE            ● ready            ⋯      │  Header: mark · StatusDot · overflow
├──────────────────────────────────────────────┤
│ /obj/geo1 › attribwrangle · 3 sel · f1001 · ▣ │  Context ribbon (quiet, mono, one line)
├──────────────────────────────────────────────┤
│                                                │
│   You    How do I fix these fireflies?        │
│                                                │  CONVERSE (dominant)
│   SYNAPSE  The /stage/karma1 samples are low   │  ChatDisplay — grouped, node-links,
│            — want me to bump them?  [node]     │  streaming, overlay typing dots
│                                                │
│   ┌─ Trust ─────────────────────────── ▾ ──┐  │  TRUST drawer (collapsed; auto-opens
│   │ ⚠ APPROVE  set_render_settings   2:00  │  │  on a gate that needs action). Gates +
│   │   pathtracedsamples 64 → 128          │  │  Integrity + Activity + Health.
│   │            [ Approve ]  [ Not now ]     │  │
│   └────────────────────────────────────────┘  │
├──────────────────────────────────────────────┤
│ [Explain] [Fix] [Optimize] [⌘K  more…]        │  ACT: context actions + palette
├──────────────────────────────────────────────┤
│  Ask SYNAPSE…                          ⌯  ▸   │  Input: grow, attach-image, send/stop
├──────────────────────────────────────────────┤
│ ● connected                         Stop ⏹    │  Footer: status · Stop (confirm)
└──────────────────────────────────────────────┘
```

---

## 6. The 1:1 map — every domain gets a discoverable, gate-respecting entry

Driven by the registry's `read_only/destructive` flags; surfaced via the palette + context actions; the agent can still do all of it conversationally.

| Domain | Tools | Affordance |
|---|---|---|
| Scene / nodes / params | 10 | inspect tree + node actions (create/connect/parm/keyframe), undo/redo |
| USD / Solaris assembly | 16 | the biggest invisible bucket — reference, assemble-chain, build-graph (4 templates), variants, collections, light-linking, instancer |
| Materials | 4 | preset picker (10 PBR presets) + MaterialX/textured + assign/read |
| Render / Karma | 9 | safe/progressive/sequence/autonomous render, AOV passes (12), validate-frame results, capture; **Indie-aware** (husk no-ops → steer to Karma flipbook) |
| TOPS / PDG | 18 | live job monitor (cook/cancel/diagnose/pipeline-status + event `monitor_stream`) |
| COPs / generative | 21 | an effects gallery (reaction-diffusion, growth, stylize, pixel-sort, wetmap, bake, slap-comp) |
| HDA authoring | 5 | keep/extend the Create-HDA wizard + expose list/promote/set-help |
| Memory & recall | 10 | context/search/recall/decide/add + actionable **Evolve** + gated Moneta sleep-pass |
| Gates & consent | (core) | global, always-available; shows INFORM/REVIEW too |
| Activity / audit | (core) | real operation log (integrity + audit hash-chain) |
| Connection & health | 2 | one unified status + live-metrics dashboard + Stop |

---

## 7. Runtime contracts to preserve (non-negotiable)

Main-thread `hou.*` invariant (worker QThread → Qt signal → main-thread `ToolExecutor`, or `hdefereval`); the Claude streaming + 25-iteration tool loop with `abort()`; **MCP-first, signal-fallback** tool exec with the `request.done` always-set rendezvous; `bridge_adapter` (4 safety anchors, read-only short-circuit, blast-radius); gate levels/timeouts (inform0/review0/approve120/critical300), timeout→auto-reject, CRITICAL confirm, thread-safe callback→Signal relay; graceful degradation everywhere; the module-flush hot-reload trick.

## 8. Build & ship plan

**BUILD** (modular, in `python/synapse/panel/`): (1) vendored `designsystem/` — one token module + QSS generator + component library + bundled icons; (2) the IA shell (header, context ribbon, converse, act, trust drawer, footer) as composed components; (3) registry-driven command palette + context actions; (4) port `GateWidget` onto the `ClaudeWorker` runtime via `HumanGate`; (5) the thin `.pypanel` loader at `houdini/python_panels/`. Keep PySide6-primary/PySide2-fallback; respect the Win11/PySide6 QFrame+no-QScrollArea constraints.

**VERIFY**: headless import/instantiate under `QT_QPA_PLATFORM=offscreen`; component snapshot/smoke tests; keep `tests/test_install_package.py` (7) + `tests/test_design_system.py` green (update the interface-name assertion); regression the existing `tests/test_chat_panel.py`.

**SHIP**: vendor tokens + icons onto the package path (eliminate `~/.synapse/design` + `install.py`); collapse to one interface name + update shelf/open_panel/installer/tests together; branch off `master`, push to `origin` (`github.com/JosephOIbrahim/Synapse`), PR per the #20 precedent; reinstall locally via `scripts/install_synapse_package.py` (points at the repo → live on Houdini restart).

**Done when:** one production-ready, artist-friendly panel — gates present, 110 tools reachable, one design system — is on `origin/master` and loads in local Houdini 21.
