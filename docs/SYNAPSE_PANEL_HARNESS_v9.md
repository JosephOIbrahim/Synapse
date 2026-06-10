# SYNAPSE PANEL — BUILD HARNESS · the v9 pass

> **Race:** translate the locked v9 concept — two tabs, the work signed, the chrome receded — into the live Qt panel.
> **Distance:** 7 spikes. **The start line is already crossed:** `audit_panel.py` boots the full panel offscreen and all components load.
> **One truth, taped to the mirror:** *the model is the author; the panel's only job is to make the decision trustworthy enough to walk away from. The render is Houdini's job, not the panel's.*
> **Visual source of truth:** `synapse_panel_pentagram_v9.html`. The build matches it; it does not reinterpret it.

---

## 0 · What this is — and is not

This is a **re-layout, not a rewrite.** Every widget already exists: `ChatDisplay`, `GateWidget`, `ClaudeWorker`, `ToolExecutor`, `MarkDat`, the design system, `context_bar.py`. The work is reordering `_build_ui`, collapsing the tab set, composing two faces, and the type pass. **Do not resurrect inline widgets that already exist as modules.** The legacy monolith is dead; leave it dead.

**Panel-layer only.** Nothing here authors USD or touches substrate. **Michael Gold's zones need no RFC for any spike in this harness.** If a spike ever reaches toward substrate, that is a halt (§4).

**In scope:** tab set 3→2 · the two faces composed per v9 · rail additions (author, Stop, context) · the same-pane law enforced · the type pass.

**Out of scope — deliberately carved out:**
- **The `customData` write.** The SIGNED line *displays* the author. It does **not** write `customData:synapse:signed_by` to `/stage` — that is substrate authoring and crosses Gold's schema. Display ships here; the write is a separate, RFC-gated unit.
- **BL-007 / BL-008** — separate bugs, not this race.
- **The full ⌘K palette** — its own mile. The comp shows only the entry hint; build the hint, not the palette.

**Definition of done:** the live Qt panel matches v9 — two tabs, same pane, signed *display*, the type pass applied — `audit_panel.py` is green on every gate plus the new assertions, and a continuity capsule is emitted. The `customData` write is absent by design.

---

## 1 · Hard invariants — the constitution

1. **Compose, don't rewrite.** Reuse the proven runtime. No new monolith, no re-inlining.
2. **PySide6, PySide2 fallback.** Every optional widget import stays wrapped; **graceful degradation is a runtime contract**, not a nice-to-have.
3. **Panel-layer only.** No USD / `customData` authoring. The SIGNED line is a label, not a write.
4. **Live introspection gates every new `hou.*`.** `dir()` / `hasattr` against the runtime (V1) **before** any call. Phantom APIs are a primary failure class. Confirmed-absent, auto-quarantined, no re-litigation: `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`.
5. **The same-pane law.** Faces swap via the **existing `QStackedWidget`**. **Zero** pane / floating-panel creation. State persists across switches. **No auto-switch** — tabs move only on user click; the rail mark signals a ready result. The panel never leaves its pane and the pane never spawns another.
6. **Never weaken the audit.** Thresholds do not relax to pass — fix the code. (CRUCIBLE Commandment 7.)
7. **Atomic commits, race-safe push.** One coherent change per commit; fetch + rebase on non-fast-forward (§8).
8. **The five calls are locked.** Settled below — do not relitigate mid-race.

**The five locked calls:**
1. **Tabs → underline** (QSS `border-bottom` on a baseline track; retires the live pill).
2. **Field inset → Houdini's editable grey** (`--ground` darker).
3. **Fonts → bundle + `QFontDatabase` load**; build-mismatch flag if a family is absent — **never silent-fallback**.
4. **Stop → rail, working-state only** (visible while the mark sweeps, hidden otherwise).
5. **Selection context → a quiet line under the rail** (`/obj · N selected · f1`), updates on selection change.

---

## 2 · Roles — MOE, sequential in one session

- **ARCHITECT** — reads the code, plans the per-spike diff, **mutates nothing**. Produces the change list.
- **FORGE** — implements the diff. Reuses existing widgets; writes the minimum new code.
- **CRUCIBLE** — adversarial. Runs the audit + probes, hunts the failure, **fix-forward**.

Rotate per spike: **ARCHITECT frames → FORGE builds → CRUCIBLE verifies → commit.** CRUCIBLE is a standing lens, not a final phase — it runs at every gate.

Claude Code runs with `--dangerously-skip-permissions`; the halt triggers (§4) are the rails.

---

## 3 · Verification ladder — every API touch

- **V0** — doc / RAG citation. Houdini 21 RAG at `G:\HOUDINI21_RAG_SYSTEM\`, or SideFX docs.
- **V1** — live `dir()` / `hasattr` probe via the bridge at `ws://localhost:9999`; fallback to **hython 21.0.631** with a **build-mismatch flag** (671 graphical vs 631 headless have separate site-packages). **No V1, no call.**

---

## 4 · Halt-and-surface triggers

Stop, write a capsule (§7), surface to Joe — do not push through:

- A pane / floating-panel **spawn** or a panel **move** on any handler (Spike 1).
- Any reach into **USD / substrate** authoring.
- A **font family absent** from `QFontDatabase` after the load attempt.
- An **audit regression** — any gate goes red.
- A **non-fast-forward** that will not rebase cleanly (merge conflict).
- A **`hou.*` call not present in `dir()`** (phantom API).

---

## 5 · The spikes — the race

Each spike: **GOAL · TOUCHES · METHOD · GATE · HALT.**

### Spike 0 · Verified runner — *start line, already crossed*
- **GOAL** — confirm the line still holds before anyone runs.
- **METHOD** — run `audit_panel.py` offscreen (`QT_QPA_PLATFORM=offscreen`); confirm all components load and capture the **green pre-change baseline**.
- **GATE** — panel boots; baseline audit captured.

### Spike 1 · Same-pane probe — *the relay handoff that shapes the rest*
- **GOAL** — prove the panel root never leaves itself; find any pane-spawn **before** wiring anything.
- **TOUCHES** — new `probe_same_pane.py` (or an `audit_panel.py` extension); **read-only** scan of the panel package.
- **METHOD** —
  1. AST / grep scan for `createFloatingPanel`, `pane.createTab`, `setCurrentTab`, or any pane mutation on **button and face handlers**.
  2. Offscreen runtime: switch tabs, fire every button, **assert the parent pane is unchanged and no panes were created.**
  3. The **"open in render view" pointer** may *focus* an existing Render View pane — it must **never create** a pane or **move** the SYNAPSE panel.
- **GATE** — zero spawns/moves on handlers; faces switch by `QStackedWidget` index only; the assertion is added to the audit.
- **HALT** — a spawn/move on any non-pointer path → surface the `file:line` and the call. **This is the one result that can change the plan; surface it as a capsule before proceeding to Spike 2.**

### Spike 2 · Tab set 3→2
- **GOAL** — collapse Direct / Work / Review → **Direct / Work**; Review's synthesis folds into Work.
- **TOUCHES** — `synapse_panel.py` (`_build_ui`, the switcher), the `QStackedWidget` pages.
- **METHOD** — remove the Review page; the Work page gains a sub-state (cook / done). Reuse the verdict, credit, and `GateWidget` from the old Review. Apply the **underline** tab style (call 1).
- **GATE** — two tabs render; Work holds both sub-states; audit green; the no-pane-spawn assertion still passes.

### Spike 3 · Work face — cook → synthesis
- **GOAL** — the Work face transitions cook-progress into the signed verdict, on one surface.
- **TOUCHES** — the Work page; reuse the progress/bucket widget + `GateWidget`.
- **METHOD** — a sub-`QStackedWidget` (or show/hide) inside Work: **cooking** → progress + cookline; **done** → verdict + credit (`DECISION` / `SIGNED`, **display only**) + status dots + Accept / Revert / Commit (existing `GateWidget` handlers). Simplified synthesis; `VIA` and paths behind an expandable detail. Cook→done is a **content update within the tab**, not a tab switch; the rail mark moves working→done.
- **GATE** — both sub-states render; gate buttons wired; the SIGNED line is **display-only**.
- **HALT** — any attempt to author `customData` (invariant 3).

### Spike 4 · Direct face — input + speaker-by-type
- **GOAL** — a roomy multi-line prompt; conversation told apart by type, not bubbles.
- **TOUCHES** — the Direct page; reuse `ChatDisplay`; the composer.
- **METHOD** — multi-line input with a generous `minimumHeight`, Send anchored bottom-right; speaker-by-type via `ChatDisplay`; the signed-author note on results; the **⌘K entry hint** (hint only — palette is OUT).
- **GATE** — input is multi-line and roomy; conversation renders by type; audit green.

### Spike 5 · Rail — author, Stop, context
- **GOAL** — the rail carries the signature, a state-gated Stop, and selection context.
- **TOUCHES** — the rail widget; `context_bar.py`; `MarkDat`.
- **METHOD** — author token (`opus-4.5`, **display**, leading the cost cluster it answers for); **Stop** visible only when state = working (mark sweeping), wired to the existing stop; selection-context line under the rail (`/obj · N selected · f1`) from the selection/frame API, updated on a selection-change callback. **V1-probe the selection API before use.**
- **GATE** — author shows; Stop appears/hides with state; context updates on selection; `MarkDat` states (idle / working / done) intact.
- **HALT** — selection/frame API not in `dir()` → V0 + V1 before any call.

### Spike 6 · Type pass
- **GOAL** — the v8/v9 typography, faithfully, in Qt.
- **TOUCHES** — `designsystem/fonts/` (new `.ttf`), `designsystem/tokens.py` (tracking map + font factory), `designsystem/qss.py` (greys, underline tabs, field inset).
- **METHOD** —
  - **Bundle** Space Grotesk (400/500/700) + Space Mono (400/700) `.ttf`. Load via `QFontDatabase.addApplicationFont` at init; **verify both families registered** → else raise the build-mismatch flag, fall back to a documented family, and log.
  - **Tracking lives on `QFont`, not QSS** — QSS has no `letter-spacing`. Add a font factory in `tokens.py`: role → `QFont(family, size)` with `setLetterSpacing(QFont.AbsoluteSpacing, em × px)`. Roles and em values:
    | role | em | applies to |
    |---|---|---|
    | BRAND | +0.16 | wordmark |
    | LABEL | +0.15 | tabs, section + action labels |
    | LABEL_SM | +0.12 | credit keys, tiny labels |
    | DATA | +0.03 | author, meter, paths, cookline, chip, mini |
    | DISPLAY | −0.015 | verdict |
    | BODY | 0 | conversation, prompt |

    AbsoluteSpacing px = `em × role_px`, DPI-adjusted via `hou.qt.inchesToPixels` where it matters. Kerning is on by default on `QFont` — leave it.
  - **Greys:** the audited hex tokens stay the **source of truth** (they passed). Move `--ground` to Houdini's editable-field grey (call 2). CRUCIBLE **samples `hou.qt.color()`** to confirm the tokens haven't drifted from the live theme — a cross-check, **not** a replacement (invariant 6).
  - **Underline tabs** (call 1) via QSS `border-bottom` on a baseline track. Expect hairlines to round toward 1px on-device — accept slightly heavier rules.
- **GATE** — audit green (contrast + type-scale floor); `QFontDatabase` reports both families present, or the flag is raised; tracking applied per role.
- **HALT** — fonts absent after the load attempt.

### Spike 7 · CRUCIBLE + audit green — *the finish line*
- **GOAL** — everything proven together.
- **METHOD** — run `audit_panel.py` G3 (WCAG contrast matrix, type-scale floor, widget-tree walk for target sizes + face presence) **plus the new assertions**: no-pane-spawn, no-auto-switch, **state-persistence across tab switches**, mark-as-status correctness, reduced-motion honored. Adversarial sweep on the Work cook→done transition.
- **GATE** — every gate green. Emit the continuity capsule.

---

## 6 · Tracking map — the type spec, as code

Compact reference (full detail in Spike 6):

- **Mechanism:** `QFont.setLetterSpacing(QFont.AbsoluteSpacing, em × px)` per role, set on the role's font in `tokens.py`. **Never** in QSS.
- **Scale (em):** BRAND +0.16 · LABEL +0.15 · LABEL_SM +0.12 · DATA +0.03 · DISPLAY −0.015 · BODY 0.
- **Kerning:** on (QFont default). **Balanced rag** has no Qt equivalent — display lines wrap greedily; hand-tune the verdict measure if a line breaks badly.

---

## 7 · Continuity capsule — emit at every halt and every finish

```
WHERE WE ARE — <spike + sub-state>
MILE MARKER  — <n of 7>
BLOCKERS     — <halt reason, or none>
NEXT ACTION  — <the single next move>
```

---

## 8 · Commit / push protocol

- **Atomic commits** per spike (or per coherent sub-step). **Marathon mile markers** in the message — e.g. `panel v9 · mile 3/7 · Work face cook→synthesis`.
- **Race-safe push:** on non-fast-forward, `fetch` + `rebase`; **max 3 attempts**; **halt on merge conflict** and surface.
- **Branch:** `master`.

---

## 9 · First move

ARCHITECT reads `synapse_panel.py`, the `designsystem/`, and `audit_panel.py`. Then run **Spike 0** (confirm boot) and **Spike 1** (the probe) **before any mutation.** Surface the Spike 1 result as a capsule. Only then take Spike 2.

*Probe before fixes — the only action whose outcome changes the plan runs first.*
