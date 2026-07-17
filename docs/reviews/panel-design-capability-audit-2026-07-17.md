# SYNAPSE Panel — Design ↔ Capability Audit + Spacing Spec

**Date:** 2026-07-17
**Author:** SCRIBE (paper deliverable — report only; proposes no panel edits)
**Baseline:** git HEAD `dd5e163` (master, 2026-07-17 13:24) · panel root `python/synapse/panel/` · Qt/PySide 6.8.3 on Houdini 22.0.368

**Scope — two questions:**
1. **Is the panel's design 1:1 with SYNAPSE's current abilities?** (fidelity audit)
2. **The spacing update** Joe asked for — more air between model choices, and more room on the UI in general. (build-ready spec)

**Method:** three probes, every load-bearing claim carries `file:line` verified live this run.
- **SCOUT** — design-system + selector map (which token/widget governs what).
- **WARDEN** — G3 gate baseline (`audit_panel.py --strict`), spacing spec, guardrails.
- **CRUCIBLE** — the adversarial 1:1 gap verdict (binding on the fidelity section below).

> **What this report is not.** It authors no code. The spacing change in Part B is a greenlit *follow-up* — a panel-design-warden-gated build cycle, run separately. Nothing here touches the panel.

---

## Executive verdict

**The panel is an honest, well-built CHAT + TOOL-INVOCATION surface — and it under-serves the AUDIT surface that is SYNAPSE's actual thesis.** It is not 1:1. Graded: roughly **faithful on invocation** (the 5 engines, the 115-tool palette, bridge/corpus/attach/stop/font-scale all back real capability with no dead buttons and no invented tools), and **thin on supervision** — three shipped, load-bearing capabilities have no window into them, and one surface actively misrepresents a truth it cannot see. The largest gap class is **capability-without-UI** on RETINA render receipts, the IntegrityBlock/fidelity verdict, and the agent.usd provenance ledger. Compounding it, the **Review face presents a chat line as if it were a render receipt** — with a BL-007 "EXR not written" flag hardwired to fail. Net: the panel shows what it *did* (chat, tools) but not whether it was *true* (receipts, fidelity, provenance) — the exact inversion a supervisor UI must not have.

**The spacing ask is the clean, ship-today part.** "More space between model choices" is a **one-rung, token-honest, gate-safe** edit to a single QSS rule. "More space in general" splits: the menu surface is free; every vertical gap in the panel body is pinned by a 400px height floor (4px of slack) and needs a ruling from you before it can move; the horizontal gutters are an off-ramp taste call for the Design Director.

---

# PART A — Design ↔ Capability fidelity

## A.1 The fidelity matrix

Verdict legend: **FAITHFUL** (UI matches a real capability) · **CAPABILITY-WITHOUT-UI** (ability ships, no window) · **UI-WITHOUT-CAPABILITY** (button lies) · **MISLEADING** (UI implies an audit it isn't doing) · **DRIFT** (cosmetic/stale).

| SYNAPSE ability | Panel affordance | Verdict | Evidence (`file:line`) |
|---|---|---|---|
| Multi-engine LLM (5 providers) | Rail author-token → per-provider QMenu | **FAITHFUL** | `providers/registry.py:69` `PROVIDER_IDS=(claude,gemini,nemotron,ollama,custom)`; `synapse_panel.py:411,921` |
| 115 MCP tools | Ctrl+K / `/` command palette | **FAITHFUL** | `tool_palette.py:104` loads `_tool_registry.TOOL_DEFS`; live `len(TOOL_DEFS)=115` |
| Bridge lifecycle (hwebserver :9999) | Connect button → "Bridge ✓" | **FAITHFUL** | `synapse_panel.py:469,520` |
| RAG/scout corpus grounding | Corpus button → "Corpus ✓" | **FAITHFUL** | `synapse_panel.py:478,572` (`scout_ingest.activate`) |
| Cooperative worker abort | Stop (state-gated, "Stopping…") | **FAITHFUL** | `synapse_panel.py:440` |
| Multimodal context attach | Attach glyph + drag-drop | **FAITHFUL** | `synapse_panel.py:1334` |
| Content font-scale (artist reading size) | Aa "Larger/Default text" | **FAITHFUL** | `synapse_panel.py:1434`; `designsystem/tokens.py:322` |
| HumanGate consent (bridge path) | GateWidget auto-surfaces Review face | **FAITHFUL** (bridge) / see A.2.5 | `gate_widget.py:434` `HumanGate.get_instance()`; `synapse_panel.py:1396` |
| §16 agent-health telemetry | HealthInfographic in Work face | **FAITHFUL (partial)** | `synapse_panel.py:1279` `poll_agent_health()`; import `:53` |
| **RETINA render receipts** (t0.py, flagship) | **none** | **CAPABILITY-WITHOUT-UI** | grep `retina\|perception\|receipt` in `panel/` → **0 matches** |
| **IntegrityBlock / fidelity verdict** | **none in installed panel** | **CAPABILITY-WITHOUT-UI** | grep `session_integrity\|fidelity\|IntegrityBlock` in `synapse_panel.py` → **0 matches** |
| **agent.usd provenance ledger** | **none** (writers also dormant) | **CAPABILITY-WITHOUT-UI** | `memory/agent_state.py:329,403,512` are the only defs; **0 non-test callers** |
| Memory-evolution stage (charmander→charizard) | none (tools reachable via palette) | **CAPABILITY-WITHOUT-UI** | grep `evolve\|charmander\|charizard` in `synapse_panel.py` → 0 |
| **Review face "render receipt"** | verdict = first line of reply; BL-007 hardwired FAIL | **MISLEADING** | `synapse_panel.py:1120,1687`; `face_review.py:59` |
| Consent coverage (implied universal) | Gate UI draws no path distinction | **MISLEADING** | live `/synapse` path ungated per CLAUDE.md §1.2; `gate_widget.py:434` |
| Tool count label | comment "110 registry tools" | **DRIFT** | `tool_palette.py:102` says 110; actual `TOOL_DEFS=115` |

---

## A.2 Findings, ordered by severity

The supervisor's job is to answer three questions about any agent action: **what changed · did we get it · can we get back.** The capability-without-UI gaps below map onto exactly those three — which is why they matter more than their raw count suggests.

### A.2.1 — RETINA render receipts have zero panel surface · SEV 5

**Supervisor question: "did we get it?"** — the render receipt is *the* answer, and it is invisible.

`retina/t0.py` (shipped live v5.28.0, wired via `handlers_render.py` + `host/retina_sentinel_postframe.py`) emits structured pass/fail/inconclusive perception events with per-check detail and a sidecar JSONL. **Grep of `python/synapse/panel/` for `retina|perception|receipt` returns zero matches** — no widget consumes it. The real receipt sits one import away, unread, while the Review face runs its own degenerate substitute (see A.2.4). This is the flagship current capability, dark in the shipped UI.

### A.2.2 — IntegrityBlock / fidelity verdict never shown · SEV 4

**Supervisor question: "what changed?"** — the scene-hash delta and the fidelity score are recorded and then discarded to the UI.

`claude_worker.py:316-348` extracts the IntegrityBlock (fidelity, scene hashes, anchors) into `session_integrity.get_tracker()`, logging only a warning on `fidelity<1.0`. **`synapse_panel.py` has zero `session_integrity`/`fidelity`/`IntegrityBlock` references** — nothing in the installed faces panel reads the tracker. The only reader lives in the *non-installed* legacy `chat_panel.py`. CLAUDE.md's core guarantee — *"fidelity = 1.0 or stop"* — has no visible readout in the panel Joe actually runs.

### A.2.3 — agent.usd provenance ledger invisible (and dormant) · SEV 3

**Supervisor question: "can we get back?"** — provenance is the audit trail, and it is neither written nor shown.

Repo-wide, `log_routing_decision` / `log_handoff` / `log_integrity` have **only their definitions** (`memory/agent_state.py:329,403,512`) and test callers — **zero live production callers.** The panel reads none of agent.usd; `FaceReview.refresh_provenance` reads the panel-side MOERouter routing log instead (`face_review.py:444-459`). Softened to SEV 3 only because the ledger is itself partly dormant — there is little live data to show yet. The order of operations is: wire the writers, then build the window.

### A.2.4 — Review face presents a chat line as a render receipt · SEV 4 (MISLEADING)

This is worse than absence — it fills the audit vacuum with a **false positive-shaped surface.**

`_populate_review` (`synapse_panel.py:1120-1134`): the **verdict is the first line of the raw LLM reply**, truncated to 140 chars. `SIGNED` is the author/model token — which `face_review.py:324-327` itself states **never authors USD/customData** (display-only). Provenance is the panel-side router log, not agent.usd. And `detect_render_flags()` is called at `synapse_panel.py:1687` **with no output path**, so `bl007_flag('')` at `face_review.py:59` **always returns `("fail","EXR not written — BL-007")`.** The one surface that reads as a render receipt shows a near-hardcoded FAIL beside a chat-line "verdict" — it can false-negative a good render and implies an audit it is not performing.

### A.2.5 — Consent UI implies universal gating · SEV 2 (MISLEADING)

`GateWidget` binds the live `HumanGate.get_instance()` (`gate_widget.py:434`) and the panel auto-surfaces the consent face on any non-inform proposal (`synapse_panel.py:1396`). But per CLAUDE.md §1.2 / Safety-Rule-5, the **live `/synapse` handler path does not route through the bridge** and runs `execute_python`/`execute_vex` ungated (single-user-localhost auto-approve). Panel-initiated ops *do* go through the gated bridge adapter — but the UI draws no distinction, implying coverage the live/external path lacks. Low severity: architecturally documented, and the panel's own path is genuinely gated.

### A.2.6 — Memory-evolution stage not visualized · SEV 2

The §6 Pokémon evolution stage and §10 "Memory Stage" indicator have no panel surface. **Mitigated:** the 21 memory MCP tools are reachable as palette prompts (`tool_palette.py` over `TOOL_DEFS`) — only the *state readout* is missing, not the invocation.

### A.2.7 — Drift: "110" label vs 115 tools; vestigial model-menu path · SEV 1

`tool_palette.py:102` comment says "the 110 registry tools"; the live registry has **115** (verified). User-facing placeholder is dynamic (`len(self._rows)`), so impact is cosmetic. Separately, `_open_model_menu` (`synapse_panel.py:950`) anchors to `self._model_chip`, which is **never built** (getattr fallback) — dead vestigial path. Neither is user-visible; both are cleanup, not a lie.

---

## A.3 What's faithful — credit where due

The invocation surface is clean. No UI-without-capability lies were found beyond the vestigial `_model_chip` path (A.2.7).

- **Engine selector is 1:1 with real capability.** All 5 providers have non-stub implementations, constructed data-drivenly by `registry.py` `build_provider`; an unconfigured cloud/custom key surfaces an **honest error in chat** rather than a silent Claude swap.
- **Ctrl+K / `/` palette maps to the real tool surface** — the full 115-entry `TOOL_DEFS` plus command recipes and material/render galleries. No phantom tools invented.
- **Connect and Corpus back real lifecycle** — Connect force-starts the hwebserver bridge on :9999; Corpus activates `scout_ingest.activate`. Both idempotent, status-reported.
- **Stop, attach/drag-drop, and Aa content-scale are all real and honestly scoped** — Stop is a cooperative abort labeled "Stopping…", not a fake idle; Aa scales content only, chrome frozen so the panel never reflows.
- **The consent gate is real for the bridge-routed panel path** — `GateWidget` subscribes to the live `HumanGate` singleton (`gate_widget.py:434`); it is the one thing allowed to move the view, matching the documented consent posture.
- **§16 observability is partially surfaced** — the Work face embeds `HealthInfographic` fed by `poll_agent_health()` (`synapse_panel.py:1279`), so agent health *is* visible even though the full advisor stream is not.
- **The design-token system is accurate to the shipped panel** — `designsystem/qss.py` is the single applied stylesheet (`synapse_panel.py:256`); the 3-source accent split is real and test-pinned (do not unify); the installed `houdini/python_panels/synapse_panel.pypanel` genuinely loads `synapse.panel.synapse_panel.onCreateInterface`.

---

# PART B — The spacing update (build-ready spec)

Joe asked for two things. They land on very different parts of the system, and the honest answer is: **one is a clean one-line ship, the other is gated.**

## B.1 Current state — what governs spacing today

**The model choices are native Qt `QAction` rows inside a `QMenu`** — not a combobox, not buttons, not a custom widget list. The rail author-token (`synapse_panel.py:411`, a flat `QPushButton#DsAuthor`) opens `_open_author_menu` (`:921`), which builds one submenu per provider; `_fill_author_submenu` (`:903`) fills each with one checkable `QAction` per model row (`sub.addAction`). Because they are `QAction`s, **there is no widget `setSpacing` or item-height to set** — in Qt QSS, `QMenu::item` padding *is* the inter-choice separation mechanism.

**The single knob for "air between models" today:**

| What | Where | Value now |
|---|---|---|
| Space between model rows | `designsystem/qss.py:210` `QMenu::item { padding: … }` | `SPACE_XS`(4)px vertical · `SPACE_MD`(16)px horizontal |
| Inset around the whole list | `designsystem/qss.py:209` `QMenu { padding: … }` | `SPACE_XS`(4)px |
| The spacing ramp itself | `designsystem/tokens.py:329-333` | XS 4 · SM 8 · MD 16 · LG 24 · XL 40 |

**The load-bearing panel-EDGE whitespace is NOT on the ramp** — it is hardcoded "comp" literals, and editing `SPACE_*` will *not* move it:

| Surface | Where | Literal |
|---|---|---|
| Rail margins | `synapse_panel.py:391` | `26, 16, 26, 14` |
| Mode bar margins | `synapse_panel.py:692` | `26, 20, 26, 0` |
| Direct-face margins | `synapse_panel.py:727` | `26, 20, 26, 20` |
| Input internal padding | `designsystem/qss.py:160` | `14px 15px` |

> **The maintenance split to know:** `SPACE_*` drives menu/widget padding where the code uses it; the panel gutters are the scattered `26` literals. Two different levers. And note — **`styles.py` (821 lines) is legacy**: a `get_*_stylesheet` helper set with its own hardcoded paddings and **zero `QMenu` rules**, **not applied** to `synapse_panel` (which applies `designsystem/qss.py` at `:256`). Editing `styles.py` expecting a live change is a dead end.

## B.2 The spec

### (a) More space between model choices — SHIP-READY, one rung

Target: **`designsystem/qss.py:210`**, vertical padding only.

```
BEFORE:  QMenu::item { padding: {t.SPACE_XS}px {t.SPACE_MD}px; ... }   →  4px 16px
AFTER :  QMenu::item { padding: {t.SPACE_SM}px {t.SPACE_MD}px; ... }   →  8px 16px
```

- **Ramp step:** `SPACE_XS`(4) → `SPACE_SM`(8), one clean rung. Horizontal stays `SPACE_MD`(16) — already comfortable, and widening it wastes width on a 280px-min panel.
- **Effect:** each row's footprint grows ~+8px (row ~20px → ~28px), which **also clears the 26px comfort target for menu rows** — a real hit-area win.
- **Optional companion, same file:** `qss.py:209` `QMenu` container padding `SPACE_XS`→`SPACE_SM` (4→8) for symmetric top/bottom list inset. Popup-safe.
- **Scope, stated plainly:** `qss.py:210` is **global to every `QMenu`** in the panel (the engine/author menu, the `⋯` overflow menu, any right-click). That is *desirable* here — one consistent menu rhythm — but it is not scoped to only the model menu. Say it out loud.

### N-14 alignment

Blueprint start-line ruling **#8 — "panel touch-target sizing (after G2 real pixels)" — is UNRULED**, and this edit is adjacent to it. The menu bump advances the N-14 touch-target intent *for the menu surface* (rows clear 26px). Note the G3 touch-target WARN counts `QAbstractButton`s only, so `QAction`s don't move that number — this is a hit-area win the audit doesn't measure. That is a benefit, not a conflict.

### (b) More space on the UI in general — GATED, three levers

| Lever | What | Verdict |
|---|---|---|
| **1 — Vertical rhythm** (section gaps + input vertical padding) | direct-face 20→24, mode-bar top 20→24, input 14→16 | **BLOCKED at the floor — needs Joe's ruling** |
| **2 — Horizontal gutter** (the `26` literals) | widen left/right edge padding | **Human-owned taste call (off-ramp)** |
| **3 — Menus** (from part a) | `QMenu::item` padding | **Free — the one "general" surface with room** |

**Lever 1 is the sharp edge.** There are only **4px of vertical slack** at `PANEL_MIN_HEIGHT=400` (`tokens.py:396`): G3 reports `input not clipped: send bottom 396px / panel 400px`, and this is a **FAIL** (not a WARN) if tripped (`audit_panel.py:303`). The hard pytest gate `tests/panel/test_docking.py::test_usable_at_min_height` asserts composed `minimumSizeHint().height() <= 400`. **Any** panel-body vertical air (e.g. direct-face 20→24 = +8) trips **both** gates unless `PANEL_MIN_HEIGHT` is raised by the same delta (400→~408). Raising the min dock height is a **behavioral nudge, not pure presentation** — a design-vs-gate conflict. **This report does not resolve it. It is yours to rule** (it sits adjacent to unruled start-line #8). The forbidden move: never fix either gate by editing the test or the audit threshold.

**Lever 2 is a taste call.** The `26` gutters are vertical-clip-safe but content-squeezing on a 280px-min panel (26+26 = 52px = 18.6% of min width already). `26` is **off-ramp** — it sits between `SPACE_LG`(24) and `SPACE_XL`(40), so a bump is *not* a mechanical one-rung step. Do **not** naive-bump to XL(40) (→80px gutters, 29% of a 280px panel, content-starving). If you want more horizontal air: **tokenize the `26` to a single named `GUTTER` constant first** (kill the scattered magic number), then pick the value with the Design Director.

## B.3 Guardrails + acceptance test

The change **must** respect all of these (the (a) edit satisfies them by construction — it is padding-only):

1. **3-source accent gremlin — untouched.** The edits reference no color. The deliberate divergence — `designsystem/tokens.py:29` `SIGNAL=#8FB3D9` vs. `panel/tokens.py:39` fallback `#00D4FF` vs. the `~/.synapse/design/tokens.py` side-channel re-export, **pinned by `test_hda_panel`** per `panel/tokens.py:74-76** — stays exactly as-is. Do not "tidy" any color while in `qss.py`.
2. **WCAG contrast floors — spacing is contrast-neutral.** No color/size token moves, so A1 matrix + A3 seeded sweep read identical inputs. They stay green.
3. **Type floors — more air comes from padding, never smaller glyphs.** `SIZE_*` (`tokens.py:272-277`) untouched; BODY stays 12px ≥ floor.
4. **The vertical-clip floor — the (a) bump is safe** (a `QMenu` popup is outside both the 400px budget and `minimumSizeHint`). Only Lever-1 body edits engage it.
5. **Touch-target WARN must not grow.** The pre-existing `13 under 26px` WARN counts `QAbstractButton`s; `QAction`s aren't counted, so (a) is button-count-neutral.
6. **No capability change — pure presentation.** Same `QAction`s, same `registry.py` rows, same `_pick_engine_model` wiring; no model added/retired; no import from the dead `ui/` tree.

**Acceptance test (all must hold):**

```
QT_QPA_PLATFORM=offscreen "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" audit_panel.py --strict
  →  exit 0, 0 FAIL, touch-target WARN count ≤ 13
```
- Panel boots under hython-offscreen (G3 layer B builds it; `QApplication` must be a genuine PySide type — stock Python 3.14 on this box has no PySide).
- Seeded-contrast sweep green (G3 A3).
- **The real merge gate:** full `python -m pytest tests/` (NOT a panel-only subset — sibling PySide stubs leak module-globals and a subset lies), with `tests/panel/test_docking.py` and `test_hda_panel` both green.

> **G3 baseline (WARDEN's run, 2026-07-17):** real G3 under H22 hython-offscreen = **"pass · 1 WARN", exit 0.** The single WARN is the deferred N-14 territory: `interactive targets: 22 found, 13 under 26px`. Critical floor for any spacing change: `input not clipped: send bottom 396px / panel 400px` — 4px of slack, and a FAIL if tripped. The bar: the change keeps exit 0 and does not grow the 13/22 WARN.

---

# Prioritized upgrade path

Ordered by **what Joe asked** first, then by **supervisor-layer leverage.**

### 1. Ship the menu spacing (a) — do this now
Low-risk, pure-presentation, one ramp rung, gate-safe. Answers the actual request and delivers a free hit-area win on the menu surface.
**Spec of record:** Part B.2 (a) — `designsystem/qss.py:210`, `SPACE_XS`→`SPACE_SM` vertical.

### 2. Close the RETINA render-receipt gap — SEV 5, highest supervisor leverage
The flagship capability is dark. The data (`t0.py` structured events + sidecar JSONL) exists and is unconsumed one import away. Building this *and* fixing the misleading Review face (below) are the two SHOWSTOPPER items — the panel currently misrepresents render truth it cannot see.
**Spec of record:** RETINA blueprint (the render receipt, truth cycle ⑤) — memory `retina-blueprint.md`; wiring seam `handlers_render.py` + `host/retina_sentinel_postframe.py`.

### 3. Repair the Review face — SEV 4, MISLEADING
Stop the pseudo-receipt: the "verdict" is a chat line, the SIGNED credit is display-only, and BL-007 is hardwired to FAIL because no output path is threaded to `detect_render_flags()`. Thread the real output path (or gate the flag when unknown) and stop labeling a chat line as a verdict. Pairs naturally with #2.
**Spec of record:** this report A.2.4 → `synapse_panel.py:1120,1687` + `face_review.py:59`.

### 4. Surface IntegrityBlock/fidelity — SEV 4, "what changed?"
The data is recorded by `claude_worker.py:316-348` into `session_integrity.get_tracker()` and read by no installed widget. A small readout closes the core guarantee's visibility gap. Lower than #2/#3 because it is BOUNDED WEAKNESS (data pipe exists, only the widget is missing), not a misrepresentation.
**Spec of record:** this report A.2.2; CLAUDE.md §1.3 IntegrityBlock schema.

> The agent.usd provenance ledger (A.2.3) is deliberately *below* this cut: wire its dormant writers first (`memory/agent_state.py:329,403,512` have zero live callers), then build the window — there is little live data to show until then.

---

# How to verify + implement

**Re-run the G3 gate (the design authority for this panel):**
```
QT_QPA_PLATFORM=offscreen "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe" audit_panel.py --strict
```
Expect `pass · 1 WARN`, exit 0. Panel verify on this box is **hython-offscreen only** — stock Python 3.14 has no PySide, so layer B (the live build) and the v9 invariants silently SKIP under stock Python and you get a false "all green" on the token layers alone.

**The real merge gate is the full suite, not a subset:**
```
python -m pytest tests/
```
with `tests/panel/test_docking.py` and `test_hda_panel` green (subset runs lie — sibling PySide stubs leak module-globals).

**Implementation is a greenlit follow-up, not this report.** The spacing change (Part B) runs as a panel-design-warden-gated build cycle. This document authors no panel code and proposes no edits beyond the specified `qss.py:210` value — it is the spec and the audit, nothing more.

---

*Every load-bearing claim above was verified by direct Read/Grep against HEAD `dd5e163` this run. The `styles.py` line count (821), `TOOL_DEFS=115`, the zero-match greps (retina/perception/receipt in `panel/`; session_integrity/fidelity in `synapse_panel.py`; live callers of the agent.usd writers), and every cited `file:line` were read live — none copied from an upstream document.*
