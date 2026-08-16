# SYNAPSE User-Flow Map — panel to network, from lived evidence

> **Leg:** W6-JRNY (wave 6, flow 1/4) · **Band:** BUILD · **Status:** evidence-anchored, capped at the top 6 journeys.
> **Rule of this map:** no invented personas. Every journey step cites where a real seam or friction was **observed** (a live-seat log) or **coded** (a committed receipt / source line). A step without an anchor is a laundered persona — and this map is written to survive the crucible that hunts those.

---

## What this is

The path an artist actually walks from the **Synapse panel** to a **live Houdini network** — six canonical journeys, each broken into numbered steps. For every step this map records:

- **Seam class** — where the step lives in the loop: `input` · `execution` · `feedback` · `recovery`. Classified by the *failure-signature test*: what does a failure of this step's predicate look like?
- **Current friction** — the real snag, with a `file:line` / receipt / observation anchor.
- **One measurable predicate** — a single proposition a headless rig (W6-FLOWRIG) can assert per step.

It is the input to **W6-FLOWRIG**, which turns each predicate into a rig assertion and reports any predicate it cannot measure. Unmeasurable predicates are **refined, never dropped** (see *Refine protocol*).

**Adversarial pre-verification.** Before commit, three independent read-only reviewers attacked this map — each on two journeys, against the evidence files, hunting laundered anchors and unmeasurable predicates. Verdict: **0 laundered steps / 30** (no `anchor_supported=no`); the load-bearing undo-group literals were confirmed against live source. Their defects — one misquoted observation line, three seam mislabels, two friction↔predicate coherence gaps, and the J5.4 compound predicate — are folded in below.

---

## Evidence base (anchored sources + provenance)

| Source | What it is | Provenance |
|---|---|---|
| `harness/notes/h22/panel-observations-2026-08-16.md` | 7 lived-seat frictions, Joe's words, driver-recorded during the 2026-08-16 vNEXT ritual | This leg's designated `source.doc`. Driver-recorded seat log ("Untracked until Joe words it into a commit" — its own line 4); cited as observation evidence, not a shipped file. |
| `houdini/python_panels/synapse_panel.pypanel` | The panel loader + its `<help>` text (the intended first-node narration, engine picker, "/" palette, Connect) | Committed. |
| `houdini/toolbar/synapse.shelf` | The tool palette surface — 1 panel-launcher + 6 action tools | Committed. |
| `harness/notes/receipts/W5-ROPE.json` | The seat-walk receipt for the CURIOUS/EXPERT/ML switcher | Committed receipt. |
| `harness/notes/receipts/W5-PANEL.json` | Font floor, chat leading, token-tab spend | Committed receipt. |
| `harness/notes/receipts/W5-LIFE.json` | Close→reopen session survival + heartbeat ownership | Committed receipt. |
| `harness/notes/receipts/W5-SHELF.json` | Shelf icons + tooltips (obs 6/7 fix) | Committed receipt. |
| `harness/notes/receipts/W5-UNDO.json` | Undo grouping on the live node handlers | Committed receipt. |
| `CLAUDE.md` §1 / §1.8 | Runtime-verified undo-is-grouping-not-rollback; emergency-halt leaves partials undoable | Committed, VERIFIED-RUNTIME dated. |

**Observation line map** (fixed against the source): obs 1 = lines 6–9 · obs 2 = 10 · obs 3 (token counter dead) = **11** · obs 4 (font switcher) = 12–13 · obs 5 (chat leading) = 14 · obs 6 (shelf legibility) = **21–22** · obs 7 (shelf discoverability) = **23–25**.

**Anchor convention.** Where a line lives inside a peer-claimed source file this leg did not read line-by-line, the anchor is the **receipt that proved it** plus the function name (a receipt anchor is first-class evidence per the leg constitution). The function name is the durable anchor; a receipt's recorded line may drift from HEAD (e.g. W5-ROPE `:1015` → live `:1026`) — both are given where verified.

---

## Seam taxonomy

| Seam | The artist is… | Failure signature |
|---|---|---|
| **input** | telling Synapse what they want (open, pick engine, click a pill/tool, invoke a palette) | the request never forms, or forms wrong |
| **execution** | Synapse mutating the live scene (create/wire/set/compose/group) | a node/parm/profile does not change as asked |
| **feedback** | reading what happened (tokens, receipt, density, error dialog, transcript) | the artist can't tell what the tool did |
| **recovery** | getting back to safety after a fault (undo, close/reopen, halt, health-check) | the fault strands the artist or the scene |

---

## Measurement contract

Each predicate carries a measurability tag so FLOWRIG knows what a rig can reach:

- **`[headless]`** — a headless rig asserts it directly (a pytest already exists, or a static parse of a committed file).
- **`[headless-proxy]`** — the *true* friction is only visible on a live GUI seat; the predicate is a headless **stand-in** for the mechanism, and the visible half is recorded **UNKNOWN** (never a fake pass). Marked `†` in the index.
- **`gui_required→UNKNOWN`** — a step may also carry a *separate* gui-only observation recorded beside its headless predicate; it is UNKNOWN, never a predicate.

Per the leg constitution: **an unobtainable measurement renders UNKNOWN — never zero, never an estimate, never a pass.** A friction that is real but currently unobservable at the seat is labelled so inline.

---

## Journey 1 — First-node build (chat → one node in the network)

**Premise:** the "make a box" path the panel help promises (`synapse_panel.pypanel:64-70`).
**Seam arc:** input → feedback → feedback → execution → feedback → feedback.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | input | Open the Synapse panel from the shelf | The launcher tool references icon `SYNAPSE_synapse`, which has no committed PNG — the entry the artist needs first is the one blank icon on the shelf. `houdini/toolbar/synapse.shelf:13`; W5-SHELF spawn `W5-SHELF-PANEL-ICON` | **J1.1** `git ls-tree HEAD houdini/config/Icons/SYNAPSE_synapse.png` returns a blob. `[headless]` *(today: FAIL — absent)* |
| 2 | feedback | The panel loads; a load fault surfaces in-panel, not as a crash | A failed panel import must not take down Houdini's panel system — `onCreateInterface` catches it and returns a read-only error view. (Runtime bridge reachability — the help's "Connect" button, `pypanel:73-74` — is a separate, later concern, not measured here.) `synapse_panel.pypanel:47-57` | **J1.2** `onCreateInterface()` returns a `QWidget` error view rather than raising when the `synapse.panel` import fails (its own `except` imports Qt, so a Qt binding is assumed present). `[headless]` |
| 3 | feedback | Read the build conversation as Synapse works (the chat transcript) | Chat leading was too tight to read the build conversation. `panel-observations-2026-08-16.md:14` (obs 5); fixed by `chat_display.py::_apply_leading` (+0.75pt = 1.0px/line), W5-PANEL acceptance 2 | **J1.3** an inserted 12-line block's document height grows by 12px (176→188) with leading applied vs. stripped. `[headless]` (proven under hython 22.0.400) |
| 4 | execution | Synapse routes the request to a tool and creates the node (`houdini_create_node` → live handler) | On the live `/synapse` path the create handler wraps its mutation in one undo group — **grouping only, not rollback**. W5-UNDO acceptance 1; live `handlers_node.py:66` `hou.undos.group("synapse_node_create")`; `tests/test_node_undo_grouping.py` | **J1.4** the create handler enters exactly one `hou.undos.group` (`rec.groups == ['synapse_node_create']`). `[headless]` |
| 5 | feedback | The Token tab shows per-task spend on the selected model | At the live seat the per-task token counter is **dead**. `panel-observations-2026-08-16.md:11` (obs 3). Wiring delivered headless: `usage_sink.py` folds `provider.last_usage`; `face_token._refresh_usage`, W5-PANEL acceptance 3 | **J1.5 †** per-task spend == Σ `provider.last_usage` folded across the worker loop (None → UNKNOWN for a non-metering engine, never 0). `[headless-proxy]` — live-seat counter render is `gui_required→UNKNOWN` |
| 6 | feedback | The build leaves a receipt the artist can grab ("Last Result") | The receipt is a clipboard hop, not shown inline. `synapse_panel.pypanel:72` (receipt promise); `houdini/toolbar/synapse.shelf:69-74` | **J1.6** the `synapse_last_result` tool exposes a one-sentence `helpText` and a script calling `copy_last_result`. `[headless]` |

---

## Journey 2 — Multi-node rig (chat → many nodes wired as one operation)

**Premise:** the artist asks for a composite build — "set up a 3-point light rig" (`synapse_panel.pypanel:66-68`). The measured steps are the execution + recovery the ask triggers.
**Seam arc:** execution → execution → execution → recovery → feedback.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | execution | Synapse opens ONE grouped operation for the rig | A rig is many mutations; they collapse into one undoable operation only if the outer/nested grouping holds. W5-UNDO acceptance 1 (nested-group behavior) | **J2.1** a create nested under an outer `hou.undos.group` opens exactly one nested group and unwinds to depth 0 (`max_depth == 2`). `[headless]` |
| 2 | execution | Synapse creates the nodes and wires them | The connect handler wraps its own group (grouping only). W5-UNDO acceptance 1; live `handlers_node.py:174` `hou.undos.group("synapse_node_connect")` | **J2.2** the connect handler enters exactly one `hou.undos.group` (`rec.groups == ['synapse_node_connect']`). `[headless]` |
| 3 | execution | Synapse sets parameters on the rig nodes | `set_parm` was **unwrapped** at W5-UNDO — a rig's parm-sets fell outside the node undo group. `handlers.py:1091` (W5-UNDO F1, prior unwrapped state); closed by W5-UNDOB — the live wrap `hou.undos.group("synapse_set_parm")` is at `handlers.py:1145` (verified in source), noted in `CLAUDE.md` Identity | **J2.3** `_handle_set_parm` wraps its `parm.set`/`parm_tuple.set` in one `hou.undos.group`. `[headless]` *(confirms W5-UNDOB stayed closed)* |
| 4 | recovery | One Ctrl+Z, expecting the whole rig to vanish | Undo is grouping, not rollback: a **completed** op reverses in one Ctrl+Z, but a **failed** build orphans a partial network that survives until a deliberate undo. `CLAUDE.md` §1 (VERIFIED-RUNTIME 2026-07-25, orphaned Solaris partials); W5-UNDO acceptance 4 (UNKNOWN) | **J2.4 †** on a raised mutation the handler's `undos.group` still closes and the identical exception propagates (partial left, no auto-rollback). `[headless-proxy]` — one-Ctrl+Z-reverses-full-rig is `gui_required→UNKNOWN` |
| 5 | feedback | Confirm the rig ("Inspect Selection") | Verification is a clipboard hop into chat, not an inline scene diff. `houdini/toolbar/synapse.shelf:41-46` | **J2.5** the `synapse_inspect_selection` tool is present with a one-sentence `helpText` and a script calling `inspect_selection`. `[headless]` |

---

## Journey 3 — Error recovery (a build faults; the artist gets back to safety)

**Seam arc:** feedback → feedback → recovery → recovery → recovery.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | feedback | A shelf action throws → Houdini shows the error | Each shelf script catches and routes to a modal `hou.ui.displayMessage(severity=Error)` — informative, but a blocking dialog. `houdini/toolbar/synapse.shelf:19-23` (pattern, per tool) | **J3.1** all 7 shelf tool scripts wrap their body in `try/except` that calls `hou.ui.displayMessage(..., severity=...Error)`. `[headless]` |
| 2 | feedback | The panel itself fails to load | The fault is shown as read-only text, not a Houdini crash — but the artist must read a traceback. `synapse_panel.pypanel:54-56` (`setReadOnly(True)` + `traceback.format_exc()`) | **J3.2** the fallback view is `setReadOnly(True)` and its text contains the captured traceback. `[headless]` |
| 3 | recovery | A live build faults mid-operation | The nodes created before the fault **remain** in the network — recovery needs a deliberate undo, not an automatic one. W5-UNDO exception-path tests; `CLAUDE.md` §1 ("a partial network survives and the artist must undo it deliberately") | **J3.3** in the exception-path test, mutations fire at depth ≥1 before the raise and are **not** removed by the group close. `[headless]` |
| 4 | recovery | The artist closes the panel mid-thought | Close must not trip a false freeze escalation, yet a genuinely stalled main thread still must. W5-LIFE acceptance 2 (`detach_panel`; `tests/test_w5_life_heartbeat.py`) | **J3.4** a continuously-beaten runtime never escalates past the deadline; a stalled main thread does (RED/GREEN pair). `[headless]` |
| 5 | recovery | Diagnose the damaged scene ("Health Check") | The diagnosis is a clipboard report, not an in-panel triage view. `houdini/toolbar/synapse.shelf:83-88` | **J3.5** the `synapse_health_check` tool is present, its `helpText` names errors/warnings, and its script calls `health_check`. `[headless]` |

---

## Journey 4 — Mode switch (CURIOUS / EXPERT / ML)

**Premise:** the switcher the seat reported as inert (obs 1) — wiring is proven live; the **render** of the switch is the dead half.
**Seam arc:** input → execution → feedback → feedback.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | input | Click a profile pill (CURIOUS / EXPERT / ML) | Static-pinned wire, but historically only manually seat-accepted. `synapse_panel.py:1015` (pill.clicked → `_select_profile`; W5-ROPE finding 1; live `:1026`) | **J4.1** `pill.clicked` is wired to `_select_profile`. `[headless]` |
| 2 | execution | The selection composes and applies the rope profile | Correct and per-selection — the wiring is **not** the bug. `_select_profile` (`synapse_panel.py:499`) → `_recompose` (`:520`) → `compositor.compose` (`:566`); W5-ROPE acceptance 1 (`tests/test_rope_switcher_wires_profile.py`, 6 cases) | **J4.2** selecting each of CURIOUS/EXPERT/ML changes the active composed profile (density stamp airy/standard/tight, `_system_prompt_overlay`, persisted `SwitcherState.profile`), forward **and** back. `[headless]` |
| 3 | feedback | The density change should be visible (airy / standard / tight) | The seat's "does nothing": `compositor._repolish_tree` is dead — `import qtpy` (uninstalled → early return) **and** a premature `break` repolishes only the root, so density QSS descendant rules never reach child widgets; all three densities render identically. `panel-observations-2026-08-16.md:6-9` (obs 1); `compositor.py` `_repolish_tree` (W5-ROPE finding 2, `:184`; spawn target `:176`); spawn `W5-ROPE-DENSITY-REPAINT` | **J4.3 †** `_repolish_tree` repolishes the root **and every descendant** using the panel's own Qt binding, with no `qtpy` dependency. `[headless-proxy]` *(today: FAIL)* — visible seat density change is `gui_required→UNKNOWN` |
| 4 | feedback | Switch back (EXPERT → CURIOUS → EXPERT) restores folded readouts | `_apply_spec` applies `collapsed` one-way (`setMaximumHeight(0)`, never restored) → folded readouts never un-collapse on switch-back. **Moot at the seat today** — those readouts are already invisible (`activity_meter setVisible(False)`; `token_meter` has no text writer), so no seat can currently observe it; the code asymmetry is real and a density fix should address it. `compositor.py` `_apply_spec` (W5-ROPE finding 3, `:151`; spawn target `:146`) | **J4.4** `_apply_spec` collapsed/visible is two-way — a later profile that does not set collapse restores the widget. `[headless]` *(today: FAIL; code-asymmetry check, not a seat observation)* |

---

## Journey 5 — Palette tool use (the shelf palette + the "/" command palette)

**Premise:** the two palettes an artist reaches for: the **shelf** (7 tools) and the in-panel **"/" command palette**.
**Seam arc:** input → input → input → input → input.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | input | Scan the shelf to find a tool | Text-only labels, hard to read at a glance. `panel-observations-2026-08-16.md:21-22` (obs 6); fix: six distinct committed PNG icons, W5-SHELF acceptance 2 | **J5.1 †** the six action tools carry six distinct committed icon blobs (`git ls-tree HEAD houdini/config/Icons/` = 6 PNGs; `test_six_tools_have_distinct_icons`). `[headless]` — visible render is `gui_required→UNKNOWN` (W5-SHELF F1) |
| 2 | input | Hover to learn what a tool does | No indication of each tool's purpose. `panel-observations-2026-08-16.md:23-25` (obs 7); fix: one operator-sentence tooltip per tool, W5-SHELF acceptance 3; `synapse.shelf:28,42,56,70,84,98` | **J5.2** each of the six tools carries a one-sentence `helpText` ≥15 chars, sentence-terminated. `[headless]` |
| 3 | input | Click a tool (e.g. Inspect Scene) | The action tools deliver by copying to the OS clipboard (an extra hop — copy, then paste into chat); that hop works only if the clipboard helper resolves a Qt binding, so it is PySide6-first with the PySide2 fallback kept. `synapse.shelf:55-56`; `synapse_shelf.py:19` `_copy_to_clipboard`; W5-SHELF acceptance 1 | **J5.3** `_copy_to_clipboard` resolves PySide6 first with a PySide2 fallback kept (`check_shelf_current`, `harness/verify/checks.py:1989`, GREEN). `[headless]` |
| 4 | input | Inside the panel, browse tools via the "/" command palette | The help advertises the "/" palette but names **115** built-in tools, while the header registry count is **129** — a stale count invites "why can't I find it?" `synapse_panel.pypanel:75` vs `CLAUDE.md` header (129 MCP tools registered) | **J5.4** the pypanel help names the "/" command palette as the way to browse the built-in tools (substring present). `[headless]` · **Advisory (today: FAIL):** advertised `115` drifts from the `129`-tool header — a registry-count reconciliation for FLOWRIG if its rig can import the registry, else a doc-fix flag (see *Refine protocol*). |
| 5 | input | First-run: "Project Setup" wires memory folders + a handshake | The scene's memory scaffolding is a manual shelf click (Project Setup); the anchor shows the manual tool exists, not whether an automatic first-send path does. `synapse.shelf:27-32` | **J5.5** the `synapse_project_setup` tool is present, its `helpText` names memory folders + clipboard, and its script calls `project_setup`. `[headless]` |

---

## Journey 6 — Close → reopen continuity

**Premise:** the g5 lifecycle — the artist closes the panel and comes back expecting their conversation.
**Seam arc:** recovery → recovery → recovery → recovery → feedback.

| # | Seam | Artist step | Current friction — anchor | Measurable predicate |
|---|---|---|---|---|
| 1 | recovery | Close the panel (pane tab closed / layout change) | Chat history is `self._messages` on the QWidget — it **dies on close**; the per-send `ClaudeWorker` QThread is parented to the panel, not rebound. `synapse_panel.py:335` (W5-LIFE F1, receipt-recorded line; live `closeEvent` ~`:2578`); fix: `closeEvent` persists via `save_conversation()` and detaches (never `shutdown_freeze_chain`) | **J6.1** `closeEvent` persists the conversation via `save_conversation()` and uses `detach_panel` (source pins: `tests/test_panel_freeze_beat.py`, `tests/test_freeze_chain.py:211`). `[headless]` |
| 2 | recovery | Reopen — the loader flushes `sys.modules['synapse.*']` | The pypanel hot-reload flush resets any in-memory singleton, so the store had to be **disk-backed**. `synapse_panel.pypanel:36-38` (the flush); `session_store.py`, W5-LIFE F1 | **J6.2** the on-disk session data survives a simulated `sys.modules['synapse.*']` flush — save/restore round-trips across it (`tests/test_w5_life_session_survival.py`). *(The store module `synapse.server.session_store` is itself inside `synapse.*`; the flush-proof part is the disk data.)* `[headless]` |
| 3 | recovery | The reopened panel restores the conversation | Restore must be per-scene and fault-tolerant, not a global blob. W5-LIFE acceptance 3 (HIP-keyed; fresh-scene empty; corrupt/non-list tolerant; atomic write) | **J6.3** the save/restore round-trip is HIP-keyed, empty on a fresh scene, tolerant of corrupt/non-list data, and atomic. `[headless]` |
| 4 | recovery | The runtime stays alive across the close (so reopen can reconnect, not spawn a fresh chain) | The freeze beat had to move off the panel so a close doesn't tear down liveness. W5-LIFE acceptance 1 (`runtime_beat.py` `RUNTIME_BEAT_SOURCE`; panel-parented `QTimer` removed) | **J6.4** the freeze beat is owned by a process-lifetime service under `server/` and the panel-parented `QTimer` is gone (`checks.py --task R.2`, `runtime_owns_heartbeat.ok == true`). *(Proves the runtime stays alive; live reopen* reconnect *is W5-LIFE gui-UNKNOWN.)* `[headless]` |
| 5 | feedback | The artist **sees** the restored history | Restoring `self._messages` continues the **model's** conversation, but does **not** repaint the visible chat bubbles — the visible restore is deeper GUI wiring. W5-LIFE F3 / acceptance 3 (visible repaint UNKNOWN); spawn `W5-LIFE-S2` | **J6.5 †** the restored `self._messages` round-trips headlessly (next turn continues the session). `[headless-proxy]` — visible transcript repaint on reopen is `gui_required→UNKNOWN` |

---

## Predicate index for W6-FLOWRIG

Flat list, one per journey step. `[tag]` is the measurability class from the *Measurement contract*. `†` marks a `[headless-proxy]` predicate — the visible half is UNKNOWN by construction.

| ID | Predicate (one assertable proposition) | Tag |
|---|---|---|
| J1.1 | `SYNAPSE_synapse.png` icon blob exists under `houdini/config/Icons/` | `[headless]` |
| J1.2 | `onCreateInterface()` returns an error `QWidget` (never raises, Qt present) on panel import failure | `[headless]` |
| J1.3 | leaded 12-line chat block grows document height by 12px vs. stripped | `[headless]` |
| J1.4 | create handler enters exactly one `hou.undos.group` (`synapse_node_create`) | `[headless]` |
| J1.5 † | per-task token spend == Σ `provider.last_usage` (None→UNKNOWN, never 0) | `[headless-proxy]` |
| J1.6 | `synapse_last_result` tool has one-sentence helpText + `copy_last_result` script | `[headless]` |
| J2.1 | nested create opens one nested group, unwinds to 0 (`max_depth == 2`) | `[headless]` |
| J2.2 | connect handler enters exactly one `hou.undos.group` (`synapse_node_connect`) | `[headless]` |
| J2.3 | `_handle_set_parm` wraps its mutations in one `hou.undos.group` (`synapse_set_parm`) | `[headless]` |
| J2.4 † | exception-path group closes + identical exception propagates (partial left) | `[headless-proxy]` |
| J2.5 | `synapse_inspect_selection` tool present + helpText + `inspect_selection` script | `[headless]` |
| J3.1 | all 7 shelf scripts guard with `try/except` → `hou.ui.displayMessage(Error)` | `[headless]` |
| J3.2 | panel fallback view is read-only and contains the traceback text | `[headless]` |
| J3.3 | exception-path mutations fire at depth ≥1 and are not removed by group close | `[headless]` |
| J3.4 | beaten runtime never escalates; stalled main thread does (RED/GREEN pair) | `[headless]` |
| J3.5 | `synapse_health_check` tool present, helpText names errors/warnings, calls `health_check` | `[headless]` |
| J4.1 | `pill.clicked` wired to `_select_profile` | `[headless]` |
| J4.2 | each profile selection changes the active composed profile, forward and back | `[headless]` |
| J4.3 † | `_repolish_tree` reaches every descendant via the panel's Qt binding, no `qtpy` | `[headless-proxy]` |
| J4.4 | `_apply_spec` collapsed/visible is two-way (switch-back restores) | `[headless]` |
| J5.1 † | six distinct committed shelf icon blobs (visible render UNKNOWN) | `[headless]` |
| J5.2 | six one-sentence helpText tooltips (≥15 chars, sentence-terminated) | `[headless]` |
| J5.3 | `_copy_to_clipboard` PySide6-first with PySide2 fallback kept | `[headless]` |
| J5.4 | pypanel help names the "/" command palette (substring present) | `[headless]` *(+ 115≠129 advisory, today: FAIL)* |
| J5.5 | `synapse_project_setup` tool present + helpText + `project_setup` script | `[headless]` |
| J6.1 | `closeEvent` persists via `save_conversation()` + uses `detach_panel` | `[headless]` |
| J6.2 | on-disk session data survives a `sys.modules['synapse.*']` flush (round-trip) | `[headless]` |
| J6.3 | save/restore is HIP-keyed, fresh-scene empty, corrupt-tolerant, atomic | `[headless]` |
| J6.4 | freeze beat owned process-lifetime under `server/`; panel `QTimer` gone | `[headless]` |
| J6.5 † | restored `self._messages` round-trips headlessly (model continues) | `[headless-proxy]` |

**Counts:** 6 journeys · 30 steps · 30 predicates. **Unanchored / dropped: 0.** Headless-directly-assertable: **26**. Headless-proxy for a gui-only truth (visible half UNKNOWN): **4** — J1.5, J2.4, J4.3, J6.5. Steps additionally carrying a separate `gui_required→UNKNOWN` observation beside a headless predicate: shelf-icon render (J5.1), the 115-vs-129 tool-count advisory (J5.4).

---

## Refine protocol (bus round-trip with W6-FLOWRIG)

This list is published to the bus addressed to **W6-FLOWRIG**. The contract (target 3): when FLOWRIG reports a predicate **unmeasurable**, this leg **refines** it — never drops it silently.

Pre-flagged refine surface:

- **J5.4** — already split: the step predicate is the substring-only half (`"/" command palette` present in help, headless); the `115 == 129` reconciliation is a **standalone advisory** (today FAIL), not the step's predicate — because a count-vs-registry check needs the MCP registry imported, which may exceed FLOWRIG's headless rig. If the rig can import the registry it asserts the advisory too; if not, the advisory becomes a doc-fix flag.
- **The four `†` predicates** (J1.5, J2.4, J4.3, J6.5) — each carries a headless proxy so the rig has a measurable assertion for every step; the visible-only halves are recorded UNKNOWN, not dropped. If FLOWRIG finds a proxy still unreachable, the refinement is to weaken the proxy to a source-presence assertion, not to remove the step.
- **The "today: FAIL" predicates** (J1.1, J4.3, J4.4, J5.4 advisory) — these are *expected* to fail against the current tree; they encode the friction, not a regression. FLOWRIG asserts them as known-red so a later fix flips them green.

If FLOWRIG reports **no** unmeasurable predicate, the round-trip closes as an explicit **none-needed** on the bus thread.
