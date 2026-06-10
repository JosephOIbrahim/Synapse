# SYNAPSE PANEL — BUILD HARNESS · the Pentagram pass

> **Race:** translate the locked v3 design (rail + three faces, the work as hero) into the live Qt panel.
> **Distance:** ~7 spikes after the start line. **Start line is already crossed** — the harness runner boots and loads the full panel (verified).
> **One truth, taped to the mirror:** *the work is the product; the panel's only job is to make it trustworthy enough to walk away from.*

---

## 0 · What this is (and is not)

This is a **re-layout**, not a rewrite. Every widget already exists — `ChatDisplay`, `GateWidget`, `ClaudeWorker`, `ToolExecutor`, `HealthInfographic`, the design system. The work is rewriting `synapse_panel.py`'s `_build_ui` order, adding a **state→face controller**, and three design moves: the **mark-as-status**, **speaker-by-type** chat, and the **render-as-hero** Review.

**Panel-layer only.** Nothing here touches USD substrate conventions. **Michael Gold's zones stay untouched — no RFC needed for any of this.** If a spike ever wants to reach into substrate, that's a halt (see §5).

---

## 1 · Hard invariants (the constitution)

1. **Compose, don't rewrite.** Reuse the proven runtime. The legacy 3032-line monolith is dead; do not resurrect inline widgets that already exist as modules.
2. **PySide6, PySide2 fallback.** Every widget import stays optional and wrapped — *graceful degradation is a runtime contract.* The panel must instantiate even when a dependency is absent.
3. **The six properties stay visible.** termination · observability · bounded cost (the **rail**) · durability · provenance · reversibility (the **faces**). A spike that hides one fails its gate.
4. **Three verification gates, all required before a spike is "done":**
   - **G1 — boots (functionality):** `python run_panel.py --smoke` exits 0, the face renders in the window.
   - **G2 — Houdini 21.0.671 (functionality, live):** loads via the `.pypanel` hot-reload, renders in the real host. *Live verification supersedes "looks right in Qt."*
   - **G3 — readable + usable:** `python audit_panel.py --strict` exits 0 — no essential text under 3:1 contrast, no body under 13px, interactive targets ≥ 26px, the mile's faces/states present. *Run it in hython for the real check: the panel inherits Houdini's font, so size + contrast must be verified in-host, not just in Qt.*
5. **Design fidelity gate.** Each face is checked side-by-side against `synapse_panel_pentagram_v3.html`. Drift is a defect.
6. **Atomic commits, one per spike.** Marathon-marker messages (`mile N/7 — <what landed>`). Race-safe push: fetch + rebase, max 3 attempts, **halt on merge conflict.**
7. **No phantom APIs.** If a Qt/`hou` call isn't confirmed present on the build, probe it (`dir()`/`hasattr`) before relying on it. Confirmed-absent → quarantine, don't re-litigate.

### The three dimensions (what each gate proves)

| Dimension | Gate | The question | Floor |
|---|---|---|---|
| **Functionality** | G1 + G2 | Does it build, boot, and run in the host? | smoke exits 0 · loads in 21.0.671 |
| **Usability** | G3 | Can you operate it — targets reachable, every state legible, primary action obvious, faces switch? | targets ≥ 26px · empty/loading/error all styled (no raw JSON dumped to chat) |
| **Readability** | G3 | Can you *read* it the way the comp reads? | essential text ≥ 3:1 (body ≥ 4.5:1) · body ≥ 13px · a real type hierarchy |

Smoke proves *boots*. G3 proves *readable + usable*. A mile is not done until all three are green. `audit_panel.py` is the G3 tool — it reads your real `tokens.py`, so it audits the **system**, not a screenshot.

---

## 2 · Roles (sequential, one session — MOE)

- **ARCHITECT** — *design is locked.* The comps + this harness are the spec. ARCHITECT only re-opens if a spike exposes a real design gap → **halt + surface to Joe**, don't improvise a new direction.
- **FORGE** — implements the current spike. Carries momentum down the spike list; no scope expansion mid-spike.
- **CRUCIBLE** — adversarial verification against both gates. **Fix-forward only. Never weakens a test to make it pass.**

---

## 3 · The runner (Spike 0 — DONE, verified)

```
python run_panel.py            # open the panel in a window  (runner lives at REPO ROOT)
python run_panel.py --smoke    # offscreen build + verify, exits 0/1
```

- Edit any `synapse.panel.*` module → **press F5** in the window → hot-reload. No Houdini restart.
- `harness/hou_stub.py` feeds fake scene state (`/stage · 1 selected · f1`) so the panel renders alive.
- **Build every spike against this loop.** Drop into Houdini only at each spike's G2.
- Confirmed at start: all eight optional components load; the full layout renders. Chat needs a key; live telemetry needs the bridge — neither blocks design work.

---

## 4 · The spikes (the marathon)

> Each spike: **goal · files · gate · commit.** Continuous flow — only stop at a gate or a halt trigger.

**Mile 1 — The rail.** ✅ **DONE — verified live in Houdini 21.0.671.** Rail + mark-as-status; Send/Stop size to text; action pills +2pt.
- **Goal:** collapse header + footer + observability into one persistent top strip. Move `Stop` up into it. Condense `HealthInfographic` to a quiet meter + mono numerics + cost.
- **Files:** `synapse_panel.py` (`_build_header`/`_build_footer` → `_build_rail`), `designsystem/components.py` (new **MarkDot** — the ◖ that fills by state), `tokens.py` (mark + muted-semantic stops).
- **Gate:** G1 — rail renders, mark animates on `working`, `Stop` reachable. G2 — same in Houdini.
- **Commit:** `mile 1/7 — persistent rail + mark-as-status`

**Mile 2 — Faces + switcher.** ◀ **YOU ARE HERE.**
- **Goal:** extend the existing `Pill` + `QStackedWidget` (today `[Chat][Build HDA]`) to `[Direct][Work][Review]`. Add the **state→face controller**: idle→Direct, working→Work, gate-raised/done→Review. Pills are manual override. **Never yank away from Direct while the input has focus.** Build HDA demotes into Direct / ⌘K.
- **Files:** `synapse_panel.py` (`_build_mode_bar`, `_set_mode` → `_set_face`, wire to `_set_busy`/`_on_tool_status`/gate signals).
- **Gate:** G1 — switches manually + auto on simulated state changes. G2.
- **Commit:** `mile 2/7 — three faces + state-driven switching`

**Mile 3 — Direct, recomposed.**
- **Goal:** **kill the chat bubbles.** Speakers told apart by type + a single hairline rule on the human voice. Agent results appear as **artifact chips** (node refs as things, not sentences). Verb actions become type-set, not pills. Taut, goal-framed microcopy.
- **Files:** `chat_display.py`, `message_formatter.py`, `synapse_panel.py` (`_build_act`, `_build_input`).
- **Gate:** G1 — a scripted conversation renders correctly. G2.
- **Commit:** `mile 3/7 — speaker-by-type chat, results as artifacts`

**Mile 4 — Work face.**
- **Goal:** promote activity + `HealthInfographic` + live tool status (`_on_tool_status`) + a **cook preview** (bucket grid) + plan-with-progress. Reuse `routing_log` / `network_trace`.
- **Files:** new `panel/face_work.py`, wired into the stack.
- **Gate:** G1 — a simulated `working` state shows Work alive. G2.
- **Commit:** `mile 4/7 — Work face (the walk-away glance)`

**Mile 5 — Review face (the payoff).**
- **Goal:** **the render is the hero** (the work supplies the color). Taut benefit verdict. **Credit/provenance block** (named authorship — `apex_trace`/`routing_log`). `GateWidget` with the graduated `GATE_LEVELS` (`INFORM/REVIEW` flow, `APPROVE/CRITICAL` block + timeout). Quality flags via `render_preflight`/`scene_doctor` — **BL-007 / BL-008 detection lands here.** Diff + accept/revert.
- **Files:** new `panel/face_review.py`, a render-thumbnail surface, wire `gate_widget` + preflight.
- **Gate:** G1 — simulated `done` shows render + credit + gate + flags. G2.
- **Commit:** `mile 5/7 — Review face: render-hero, provenance, gated commit`

**Mile 6 — ⌘K on two axes.**
- **Goal:** reorganize the palette on **verb × context** (build/fix/explain/optimize/render × SOP/LOP/COP/Karma/USD) — self-identify two ways.
- **Files:** `tool_palette.py`, `command_palette.py`, `tool_filter.py`.
- **Gate:** G1 — palette opens, both axes navigable. G2.
- **Commit:** `mile 6/7 — two-axis command palette`

**Mile 7 — Design pass (the finish line).**
- **Goal:** recede the chrome, apply muted-semantic tokens, set the type roles, tune the negative-space rhythm, final QSS. Production type decision (Söhne / Diatype / GT America) vs the comp's Space Grotesk/Mono.
- **Files:** `designsystem/qss.py`, `tokens.py`, `styles.py`.
- **Gate:** G1 + G2 + **fidelity gate** against the v3 comp, all three faces.
- **Commit:** `mile 7/7 — design pass, fidelity locked`

---

## 5 · Halt and surface (stop, tell Joe, don't improvise)

- A spike exposes a **design gap** the comps don't answer.
- A Qt/`hou` API needed for a spike is **absent on 21.0.671** (quarantine it; surface the workaround choice).
- A change would touch **USD substrate** → Michael Gold's RFC zone.
- A gate **can't pass fix-forward** without weakening a test.
- **PySide6 vs PySide2 divergence** changes behavior between gates.
- Merge conflict on push.

---

## 6 · Definition of done

Per spike: **G1 green · G2 green · G3 green (`audit_panel.py --strict`) · matches comp · six properties intact · tests added or green.**
Overall: the three faces live in Houdini 21.0.671, the rail never leaves the screen, and a walk-away → come-back cycle reads as trustworthy without you touching the transcript.

---

## 7 · Capsule (paste-forward for the next session)

```
+== PANEL REDESIGN — BUILD ==============================+
| WHERE WE ARE:        Mile 1 done — rail LIVE in Houdini |
| MILE MARKER:         0 of 7 (start line crossed)       |
| WHAT I WAS THINKING: v3 design locked; re-layout only  |
| NEXT ACTION:         Mile 2 — faces + state→face switch |
| BLOCKERS:            none                              |
| ENERGY REQUIRED:     coding (3) — momentum from design |
| IDEAS PARKED:        production type (Söhne/Diatype/GT) |
+========================================================+
```
