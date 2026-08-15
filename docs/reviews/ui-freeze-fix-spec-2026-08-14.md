# UI Freeze — First-Principles Fix Spec (2026-08-14)

*Synthesized from the 4-scout recon (wf_70e898fe-041: L1 state-diff, L2 surface,
L3 substrate, L4 logs — 528K subagent tokens, 196 tool calls, 0 errors).
Full evidence: freeze-recon archive + `~/.synapse/logs` mining.
Authority: Latency Ruling R2 — measured numbers only. Every fix below names
its measured target or says UNKNOWN.*

## The physical law (this bounds everything)

Houdini's main thread **is** the UI thread. Python code executing on it
cannot be preempted — no API cancels an in-flight `node.render()`
(crucible wording fix: `hou.IPRViewer.killRender` and the
`hou.InterruptableOperation`/`hou.OperationInterrupted` pair **do** exist
in the 35,908-symbol H22.0.400 table, but neither reaches an arbitrary
in-flight ROP render; the intended claim — no general cancel for an
in-flight `node.render()` — stands, and the blanket "absent" wording was
wrong), and no threading construct interrupts running Python. Deferred
dispatch and inline dispatch freeze the GUI for the **same** payload
duration; they differ only in transport behavior.

Therefore the goal "use Houdini while SYNAPSE processes" is achievable by
exactly four levers:

1. **Don't run it on main** — off-process offload (husk renders —
   **contested in-tree evidence**, probe-first: `handlers_render.py:336-338`
   says Indie can't load the Karma delegate (2026-07-17), the perception
   ledger says husk wrote real EXRs headless on Indie. Which invocation
   differs is UNKNOWN. Probed by F5a before any offload claim ships).
2. **Make it shorter** — the update-mode sandwich collapses N redundant
   auto-cooks into one consolidated cook (behavior **UNVERIFIED** — see F1
   probe requirement; symbol existence ≠ behavior).
3. **Don't compound it** — retry cascades and lock-queued mutations turn one
   hold into a multi-minute lockup.
4. **Survive it** — a safety net that actually exists on the live transport.

Chunking (pump UI between mutation fragments) stays **refuted**: an open
`hou.undos.group` swallows artist edits made between chunks into SYNAPSE's
undo entry. No design below reintroduces it.

## What actually froze Joe today (measured)

**2026-08-14 15:01:21 → 15:04:21 — 179.43s.**
Panel ClaudeWorker building `/stage/component_hero_chair` imperatively
(batch advisory → composition-validation AttributeError → `execute_python`
**inline** on main for 179.43s; `synapse.log:43493`; resilience confirms
"frozen for 180.6s", :43494). During the hold, 5 worker-thread
`execute_python` retries abandoned at 30s each (:43366-43473). Conversation
died at the 25-iteration cap with 36 tool calls. Freeze dump fired mid-hold
and **could not see its own freeze** — inline holds bypass the histogram.
**Same class, Aug 13:** 25.5s + 143.66s + 143.67s execute_python cascade;
seven 162-177s render zombie windows (19 min aggregate GUI death, detector
saw only 5-6s blips); six 6.0s Qt stalls from a 123K-char result document.

## The six fixes

### F1 — Update-mode sandwich (the hold-shortener; targets today's exact class)

New `python/synapse/server/update_mode.py`:

```python
@contextmanager
def cook_sandwich():
    """Manual-update sandwich: collapse auto-cook floods into one cook."""
```

- Snapshot `hou.updateModeSetting()`, set `hou.updateMode.Manual`, yield,
  `finally:` restore prior mode. Restore is then followed by an **explicit
  `hou.ui.triggerUpdate()`** — that is the vendor-documented update mechanism
  (vendor `hou.py:103374-103383`), NOT the assumption that restore itself
  re-cooks. Both assumptions ("restore triggers one consolidated cook",
  "`cook(force=True)` works under Manual") are **UNVERIFIED behavior**:
  vendor docstrings (`hou.py:118487-118500`) do not state them;
  `h3a_symbols.json:53-55` marks these symbols `candidate: true`,
  probe-pending. The pinned ledger evidence is introspected on **22.0.368**
  — one build off the 22.0.400 target; the "verified on 22.0.400" wording
  was an overclaim (crucible). Zero production call sites exist today —
  this is a NEW mechanism, not a behavior change to existing flows.
- **F1 probe (gate before forge):** a live script must establish, on
  22.0.400: (a) symbols present; (b) Manual→mutate→restore+
  `hou.ui.triggerUpdate()` produces exactly one downstream cook; (c) a
  `hou.undos.group` open across the sandwich does not swallow artist edits
  (no pumping — refuted class stays out); (d) nested payload
  `setUpdateMode` calls restore to the pre-sandwich mode, not to Manual's
  default. Probe script ships with the forge; results land in the
  verification protocol. If (b)/(c) fail, F1 is descope-and-report, not
  fix-forward.
- Apply to the measured cook-flood sites: `execute_python` / `execute_vex`
  inline payloads, Solaris build-graph chains
  (`handlers_solaris_graph.py:332-338`). **`batch_commands` is excluded
  from F1** (crucible): a batch runs N sub-ops under one undo group, and a
  sandwich wrapped around the batch would sit outside the per-op hash
  bracket that the bridge's R1 scene-hash + R7 Scene Integrity anchor read.
  The sandwich sits **inside the bridge's hash bracket** (hash-before →
  sandwich → op → restore+triggerUpdate → hash-after). Stated as the
  invariant: *sandwich scope ≤ bridge op scope*. Batch-level shortening is
  a separate later design, not this spec.
- Guards: GUI-session-only (`hou.isUIAvailable()`), try/finally restore is
  non-negotiable, mode is non-persisted session state (Houdini restart also
  recovers). No UI pumping inside the sandwich (refuted class).
- **Risk, stated:** while Manual is on, the viewport is stale during the
  build — UI responsive, scene frozen. Acceptable for bounded automation;
  restore fires one consolidated cook so the stale window ends with the
  correct scene.
- **Measurement requirement (R2):** none of this has a live win number
  (C1: "needs-live-measurement"). First ship = instrumented A/B: sandwich
  records collapsed-cook estimate + hold duration both ways in the
  panel/dev harness before it becomes default.

### F2 — Retry cascade circuit-breaker (the compounder-killer)

Today's 179s hold became a 3-minute lockup because the panel re-issued
`execute_python` 5× at 30s while zombies were running.

- Panel worker (`claude_worker`): before re-attempting a tool after a
  main-thread timeout, consult the **F4 in-flight register**
  (`current_main_thread_holder()` → `(label, start_ts)`), NOT
  `stall_state()`. **`stall_state()` is driven only by deferred-path
  `_record_timeout` (main_thread.py:401-405) — fast path 2 has no timeout
  by design, so the inline class (the 179.43s freeze) never moves the stall
  counter. F2 as originally written consulted an instrument that is blind
  to exactly the class it polices — crucible FATAL, now re-rooted.** After
  2 consecutive abandoned attempts of the same command, stop retrying and
  surface to the artist, computing the sentence from the register:
  *"Houdini is busy — a {label} operation has held the UI for
  {now − start_ts}s. Try again when it finishes."* (`stall_state()`'s
  `slowest_label` is historical and unaged — it cannot date the *current*
  hold; the register's `start_ts` can.) This converts an invisible pileup
  into one honest sentence.
- The WS stall gate already fast-fails new commands; the panel retry loop
  currently bypasses that judgment (retries are new tool-use iterations).
  Same information, one hop.
- **Hard dependency:** F2 ships after F4. If F4 does not land, F2 does not
  ship — a circuit-breaker reading a blind instrument is worse than none
  (it would fast-fail on stale deferred stalls while inline freezes pile
  up silently).

### F3 — Emergency net wiring (make the net exist)

All five on-disk freeze dumps show the net **inert**: "No live SynapseServer
breaker (hwebserver transport has no resilience layer)", "No ACTIVE bridge —
emergency halt skipped", and `AttributeError: SynapseBridge has no attribute
session_report` (Aug 13). Crucible correction up front: **part of this is
deliberate design, not defect** — `freeze_chain.py:201-204` explicitly
logs-and-proceeds when no transport breaker exists, and `:224` carries the
never-construct invariant ("NEVER construct; attribute reads only") to keep
the freeze handler from mutating state during the freeze it observes. And
`session_report` **already exists** at `shared/bridge.py:2841` and
`panel/ws_bridge.py:200` — so the Aug-13 AttributeError is a *caller* bug
(wrong class, or an instance constructed without it), not a missing
method. Three re-scoped work items:

1. **hwebserver breaker:** add an honest breaker for the hwebserver/panel
   transport so `freeze_chain` escalation has something to open, **without
   violating the never-construct invariant** — the breaker is constructed
   at transport startup and *registered* for `freeze_chain` to read, never
   created inside the freeze handler.
2. **session_report caller fix:** find the actual failing caller by
   file:line first (the AttributeError names the attribute, not the call
   site), then fix the caller to hit the existing attribute on the right
   class. No new attribute implementation.
3. **emergency_halt on the WS path:** design the no-`/mcp`-bridge case
   explicitly, with the deadlock shape analyzed: firing the emergency halt
   *while the main thread is frozen mid-op* means the halt's own
   marshalled work queues behind the very hold it is responding to. The
   safe shape is: the halt performs only what does not need the main
   thread (cancel PDG graph contexts via their own API, cancel pending
   *unstarted* dispatches under C4's abandoned flag, write state, notify
   the panel) and records the in-flight hold from the F4 register as
   evidence, rather than attempting main-thread mutation during an
   in-flight freeze. The halt *never* waits on the frozen main thread.

### F4 — Instrument honesty (see the biggest class)

- Inline holds (fast path 2) never reach `_record_main_thread_hold` — the
  instrument is blind to exactly the class that froze Joe twice this week.
  Add an in-flight register to `run_on_main` **and to the deferred
  `_on_main` path**. Fast path 2 (main_thread.py:315-348, ident-gated,
  single-writer-safe: writes happen only on the main thread by
  construction): `(label, start_ts)` on entry, clear on exit in `finally`.
  Deferred `_on_main` (:365-397): same register entry set when the C4
  abandoned-check passes and the payload starts, cleared in `finally` —
  this is what names the Aug-13 162-177s deferred zombie renders
  **mid-flight**, which otherwise stay invisible until they complete.
  One register, both dispatch paths; the exposed read is
  `current_main_thread_holder() → (label, start_ts) | None`. Freeze dumps
  then name the **current** holder instead of only the last completed one.
  Today's mid-freeze dump named a 651ms doctor while a 179s
  execute_python was in flight — that inversion is the defect.
- Label the unlabeled `run_on_main` call sites (all `handlers_cops`,
  `handlers_usd`, TOPS `_common.py:82`, etc.) — ~40 sites file as
  "unlabeled" today, so `slowest_label` can attribute a hold to nothing
  useful.
- Detector blind spot (seven 162-177s windows → 5-6s blips) stays
  **UNKNOWN / probe-first** — S4 probe governs, no fix licensed. The F4
  register is what makes that probe possible.

### F5 — Zombie-proof renders (killability via offload)

Seven renders zombie-ran 162-177s on main **after** their MCP callers were
told they failed — and no API can cancel an in-flight foreground render.
Husk background renders **are** killable (`synapse_render_stop`) — **on
build, OS, and delegate combinations that are verified**. The crucible ruled
the original F5 fatal twice: (1) `_handle_render`'s return contract is
synchronous file-on-return — a 15s output poll, then a GL flipbook
fallback on the main thread, then a false RuntimeError — so a naive
"default to background" flip manufactures flipbook freezes and silently
viewport-validated "renders" on every automation render over 15s; and
(2) the evidence is contested within the tree: `handlers_render.py:336-338`
carries "on Indie husk cannot load the Karma delegate, verified live
2026-07-17" while `harness/notes/perception_truth_22.0.368.json` records
husk writing real multi-part EXRs headless on Indie. Which invocation
differs is UNKNOWN. **`node.render()` under `soho_foreground=0` was never
probed** — the premise the flip rested on.

F5 is therefore **re-scoped to a probe, and only a probe**:

- **F5a (probe, ships with the forge):** a live script that establishes,
  on Joe's licensed H22.0.400: (a) whether husk launches and loads the
  Karma delegate headless from a SYNAPSE automation call (which build,
  which license, which invocation); (b) what `node.render()` does when
  dispatched under a *background*-mode Karma ROP from the SYNAPSE code
  path — return-immediately, raise, or queue; (c) the correct completion
  signal for automation renders (file-exists poll is the current contract —
  is it the right one, or is there a callback on the ROP).
- **F5b (design change, explicitly NOT in this forge):** any default flip
  of automation renders to background/husk. It is gated behind F5a's
  probe result **and** Joe's explicit sign-off, and its design must rework
  the `_handle_render` return contract (no GL flipbook fallback for
  automation-class renders; failure must surface as failure, never as a
  viewport-validated fake). None of that is implemented in this mission.
- **What the forge does ship for F5:** the probe script under
  `harness/notes/` or the dev harness, plus the *documentation* of the
  contested-evidence reconciliation; and `render_progressively`'s 256px
  foreground layout-pass escape hatch stays exactly as it is (crucible:
  that hatch only covers `render_progressively`; `safe_render`'s force-
  foreground path is unaffected by F5 because F5 changes no defaults).

### F6 — Hygiene bundle (already-catalogued, small, orthogonal)

From the L1 re-verified-open list:
1. `live_metrics.py:255` scene-gather: `record_stall=False` (2s telemetry
   currently counts toward fast-failing real commands — highest live-burn).
   Crucible-named risk, accepted with mitigation: if the 2s scene gather
   itself wedges the main thread, `record_stall=False` also hides *that* —
   acceptable because (a) the F4 in-flight register records the gather's
   hold regardless of the stall counter, so the observation survives on a
   different instrument, and (b) the alternative (telemetry fast-failing
   real commands) is the measured live-burn.
2. `handlers_usd.py:956-1018` `_walk`: visit-counter bound, not results-only
   (a limit=10 walk over 100k filter-rejecting prims walks all 100k on main).
3. `reference_usd`: 30s entry in `core/timeouts.py` + explicit timeout at
   `handlers_usd.py:905`. Crucible note: the abandonment window is
   governed by layered budgets (run_on_main default 10s at this call site
   today, `core/timeouts.py` budget, MCP transport) — the forge must state
   which layer owns the 30s and that the raise doesn't create a new
   transport-reported-failure-while-running window (the F5 zombie class
   pattern).
4. `houdini_capture_viewport` into `_KNOWN_SLOW_TOOLS`
   (`bridge_adapter.py:244-251`; already budgeted 30s).
5. WS-path `_handle_inspect_scene` marshal raised to match the /mcp 30s
   budget (`handlers.py:1511`).
6. `mcp/server.py:121-123` comment: **re-derive the counts at forge time
   from the live registry** — the three in-tree sources disagree (comment
   says 35 bridge / 3 divergent; recon found 39/35; spec said 40/36/4).
   The fix is a correct comment, not the spec's number.

## Sequencing (forge order, post-crucible)

| # | Fix | Why this order |
|---|---|---|
| 1 | F4 in-flight register + labels (both dispatch paths) | Observation first (Tier 0 doctrine): every later fix becomes attributable. F2 is now *hard-dependent* on F4's register — this ordering is load-bearing, not preference. |
| 2 | F2 retry circuit-breaker (register-rooted) | Kills the compounder with ~30 lines of panel logic, reading F4's `current_main_thread_holder()`. |
| 3 | F3 emergency net | The net must exist before F1 changes hold behavior. (Crucible: the *stated* dependency was decorative — the net doesn't guard the sandwich's stuck-Manual failure mode. Kept as risk preference; the real F1 gate is the probe in row 4.) |
| 4 | F1 sandwich **probe + implementation** (instrumented, dev-default-off) | The hold-shortener, gated by its own live probe on 22.0.400. Probe runs first inside the same fix; failed probe = descope-and-report, no half-ship. |
| 5 | F6 hygiene bundle | Independent one-liners (counts re-derived live for item 6), batch as one commit series. |
| 6 | F5a render-offload **probe only** | No behavior change. The probe result + contested-evidence reconciliation ships as the deliverable; F5b (any default flip) is out of scope pending probe + Joe's sign-off. |

## Explicitly NOT in this spec

- **Mid-hold preemption.** Impossible; no API exists. The spec deletes this
  expectation rather than pretending.
- **Chunking handlers with UI pumping.** Refuted (undo-swallow).
- **Off-main viewport capture.** No path exists (`sv.flipbook` is
  main-thread GL; `QWidget.grab()` returns black). Say none.
- **The 5–6s stickiness discriminator.** S4 probe-first; UNKNOWN until a
  human-at-GUI session runs the ready_diff negative-cache probe.

## Crucible disposition (two-lens adversarial pass, 2026-08-14)

Threading lens: 1 fatal / 6 major / 4 minor. Anchors/blast-radius lens:
2 fatal / 3 major / 7 minor. All dispositions applied inline above.

| Attack | Disposition |
|---|---|
| F2 consults blind `stall_state()` (FATAL, threading) | **Landed.** F2 re-rooted on F4's register; hard dependency stated. |
| F2's "held for Ns" not computable (major) | **Landed.** Register's `start_ts` computes it; `slowest_label` demoted. |
| F5 flip breaks file-on-return contract + detonates flipbook fallback (FATAL, anchors) | **Landed.** F5 re-scoped to probe-only (F5a); no default flip ships. |
| F5 foreground-semantics callers (render_progressively sync-validate) (FATAL, anchors) | **Landed.** Same re-scope; `node.render()`-under-background never probed — now probe item (b). |
| F1 "restore = one consolidated cook" / "force-cook under Manual" unverified (major, both lenses) | **Landed.** Downgraded to UNVERIFIED; F1 probe gate (a)-(d) added; `hou.ui.triggerUpdate()` adopted as the documented mechanism. |
| F1 sandwich vs. bridge hash bracket; batch_commands shape (major, anchors) | **Landed.** `batch_commands` excluded from F1; sandwich-scope ≤ op-scope invariant stated. |
| F4 register fast-path-only; deferred zombies invisible (major, threading) | **Landed.** Register extended to `_on_main` deferred path. |
| F3 recasts deliberate never-construct degrade as defect (major, threading) | **Landed.** F3.1 rewritten to construct-at-startup + register-for-read. |
| F3 `session_report` already exists (major, threading) | **Landed.** Re-scoped to caller-fix by file:line. |
| F3 halt-mid-freeze deadlock shape unanalyzed (major, threading) | **Landed.** Halt restricted to non-main-thread actions + register evidence read. |
| killRender/IPRViewer "absent" overclaim (minor) | **Landed.** Wording corrected in the physical-law preamble. |
| ".400 verified" cites .368-introspected ledger (minor, both lenses) | **Landed.** One-build overclaim corrected in F1. |
| F6 item 6 carries contested counts (minor, anchors) | **Landed.** Re-derive live at forge time. |
| F6 item 1 observability hole (minor, anchors) | **Landed.** Accepted with F4-register mitigation, stated. |
| F6 item 3 layered budgets unstated (minor, anchors) | **Landed.** Forge must name the owning layer. |
| F1 no-undo-swallow defense (minor, anchors) | **Spec survives.** Refutation targeted pumping; spec never pumps. No change. |
| F2 anchor surface clean; F3/F4/F6 gate/RBAC/C5-clean (anchors) | **Spec survives.** No consent-gate, classification, or mutation-lock drift. Verified unchanged. |
| Sequencing F3-before-F1 decorative (minor, anchors) | **Landed.** Real dependency (F1 probe) added; order kept as risk preference. |

**Not landed (spec stands as written):** chunking stays refuted; no
mid-hold preemption; no off-main viewport capture; S4 stickiness probe-first.

## Verification protocol (for Joe, after merge)

**Probe-gate first (both ship in the forge, run by Joe live on 22.0.400):**

0a. **F1 probe** — validates sandwich behavior: (a) symbols exist on
    22.0.400; (b) Manual→mutate→restore+`triggerUpdate()` = exactly one
    consolidated cook (count cooks via `cookCount` deltas on a probe chain);
    (c) sandwich inside an open undo group doesn't swallow artist edits;
    (d) nested `setUpdateMode` payloads restore correctly. Pass = F1 ships
    behind its flag; fail = F1 descoped with the probe evidence.
0b. **F5a probe** — establishes the husk-on-Indie and
    background-`node.render()` ground truth; reconciles the contradictory
    in-tree claims by naming the exact invocation that differs. Result
    lands in `harness/notes/` and decides whether F5b gets designed at all.

**Then the live session:**

1. Start H22 + panel, run a normal panel session (build a component, render).
2. Trigger a deliberately long `execute_python` (e.g. 100-node build flood).
3. Expected (if F1 probe passed and the flag is on): one consolidated cook
   instead of a cook storm; hold histogram shows the shortened hold labeled;
   if a hold still occurs, the panel says *what* holds the UI and *for how
   long* instead of silently piling retries.
4. Freeze dump during any hold now names the in-flight holder — inline
   (fast path 2) **and** deferred zombie classes both visible.
5. Kill-switch drill: fire `synapse_emergency_halt` with no `/mcp` bridge
   live — expect the WS-path halt to act (PDG cancel, dispatch cancel,
   state write, panel notify) without waiting on the frozen main thread,
   and the dump to record the in-flight holder.
