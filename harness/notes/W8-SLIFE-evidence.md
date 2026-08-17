# W8-SLIFE — lifecycle scout evidence (runtime/session lifetime vs UI, undo, threads, recovery)

Leg: **W8-SLIFE** · band TRUTH · branch `wave8/slife` · read-only recon.
Source: `harness/bastion/PROGRAM.md` anchor `B1-LIFECYCLE`.

Every claim below is first-hand: personally read at the cited `file:line`, then
adversarially re-verified by an independent read pass. All anchors are relative
to the `wave8/slife` worktree. Method: 4-target scout fan-out + per-target
adversarial verify, then a personal confirmation read of every P1 anchor.

**Headline:** the lifecycle story is fundamentally SOUND. The R.2 / g5 /
W7-SESSCOPE work (2026-08-16) fixed the headline crashes — a panel-parented
freeze heartbeat that false-froze a healthy runtime on close, and a chat lost on
reopen. **No confirmed P0.** Two P0 *candidates* exist but are each gated on an
UNKNOWN (a parallel HTTP transport's live status; an orphan-timer's GC timing).
The rest are hardening (P1) and polish (P2).

---

## Target 1 — objects whose lifetime is parented to a UI surface + SESSCOPE

### What SESSCOPE actually covers (and what it does not)
`W7-SESSCOPE` = `python/synapse/server/session_store.py`. It is a disk-backed
store of **exactly one thing: the Anthropic-format conversation transcript** —
HIP-keyed (`$HIP/claude/conversation.json`), atomic (`.tmp`+`os.replace`),
boot-token stamped via an owner sidecar, parked-to-`previous` on a new Houdini
boot (`load_conversation_scoped` → `same_boot`/`empty`/`previous_parked`;
`restore_previous_conversation` is the one-call undo). `session_store.py:233`.

It survives widget death AND the pypanel module flush **precisely because it
lives outside `synapse.*`, on disk** (`session_store.py:15`). It has **no** API
that stops a QTimer, quits a QThread, or disconnects a signal. **SESSCOPE
restores the chat, full stop** — it does not know about a single timer, thread,
heartbeat, gate registration, or integrity tracker.

Robustness bonus (first-hand): the transcript is saved on **every completed
turn** in `_on_done` (`synapse_panel.py:2354`) as well as on close
(`:2650`) — so restore survives even if Houdini destroys the panel without
calling `closeEvent`. That same fragility is why the timer/thread/gate teardown
(which lives ONLY in `closeEvent`) is the unreliable half.

### The installed panel has a closeEvent-only teardown that stops nothing
Installed panel = `houdini/python_panels/synapse_panel.pypanel` →
`synapse.panel.synapse_panel.SynapsePanel`. Its **only** lifecycle hook is
`closeEvent` (`synapse_panel.py:2620`); there is no
`onDestroyInterface`/`onDeactivateInterface`. `closeEvent` does exactly three
things: `hou.ui.removeSelectionCallback` (correct dangling-ref guard),
`runtime_beat.detach_panel()` (deliberate — see below), and
`session_store.save_conversation`. It does **not** stop `_ctx_timer`/
`_health_timer`, does **not** `quit()`/`wait()` the `ClaudeWorker` or
`DirectToolCall` QThreads, does **not** disconnect any signal, and does **not**
unregister the `GateWidget` from the `HumanGate` singleton.

NOTE: `chat_panel.py`'s `SynapseChatPanel` has the *clean* teardown
(`onDestroyInterface` stops both timers + `bridge.stop`, `chat_panel.py:283`) —
but it is loaded only by `python/synapse/panel/synapse_chat.pypanel`, which is
NOT under `houdini/python_panels/`. That exemplary lifecycle is effectively dead
code; the shipping panel does not have it.

### The freeze heartbeat is (mostly) fixed — but the module flush reopens it
R.2 relocated the 1 s main-thread freeze beat off the panel widget
(`self._freeze_timer = QTimer(self)`) to a **parentless, process-lifetime**
`QTimer()` owned by `python/synapse/server/runtime_beat.py:152`. `closeEvent`
→ `detach_panel()` LEAVES it running so the Watchdog never false-freezes a
healthy runtime the artist merely closed. This is the correct fix and it holds
**across close-without-reopen**.

BUT the pypanel loader deletes every `synapse.*` module on each panel creation
(`synapse_panel.pypanel:36-38`), and `synapse.server.runtime_beat` matches. On
**reopen** the module is re-imported fresh with `_timer = None`, so
`ensure_beat_started`'s idempotency guard `if _timer is not None: return True`
(`runtime_beat.py:139`) sees `None` and arms a **second** parentless `QTimer`;
the first is orphaned. The "process-lifetime" invariant is broken across the
reopen boundary → a double-beat or a heartbeat gap. Whether the orphaned first
timer keeps firing (double-beat) or is GC-stopped (gap) is **UNKNOWN** (PyQt
C++ QTimer lifetime under module-global GC is nondeterministic and not statically
observable). Same class of hazard also applies to
`telemetry_dump.start_periodic_flush` (started `synapse_panel.py:456`,
module-singleton reset by the flush).

### UI-parented object inventory (all first-hand)
| Object | Owner / lifetime | Anchor | Close teardown | Severity |
|---|---|---|---|---|
| Freeze beat (1 s) | parentless module timer, process-lifetime | `runtime_beat.py:152` | detach (not stop); **double-arms on reopen** | **P1** |
| `ClaudeWorker` (QThread) | `parent=self` | `synapse_panel.py:2287` | none (abort only on Stop, `:2413`) → destroyed-while-running | **P1** |
| `GateWidget` → `HumanGate` cbs | process singleton strong-ref list | `gate_widget.py:549` / `core/gates.py:262` | none → dangling callback into deleted widget | **P1** |
| `_ctx_timer` (2 s) | `QTimer(self)` | `synapse_panel.py:433` | not stopped; spawns off-main daemon per tick | P2 |
| `_health_timer` (4 s) | `QTimer(self)` | `synapse_panel.py:441` | not stopped | P2 |
| `telemetry_dump` flush thread | module-singleton daemon | `synapse_panel.py:456` | not stopped; double-starts on reopen | P2 |
| `DirectToolCall` (QThread) | `parent=self` | `synapse_panel.py:2008` | not waited (short calls) | P2 |
| `session_integrity._tracker` | in-memory module singleton | `session_integrity.py:236` | reset by flush → integrity strip blank while chat full | P2 |
| async formatter thread | daemon, off by default | `async_format.py:109` | `shutdown()` never called by closeEvent | P2 |
| gate proposal-card timers | children of card | `gate_widget.py:259` | self-terminating; die with card | info |
| `_typing_timer` | `QTimer(self)` | `chat_display.py:110` | stopped on typing end | info |

**UNKNOWN:** whether Houdini invokes `closeEvent` on the embedded panel at all
vs. silently deleting the widget — if skipped, none of the (already partial)
teardown runs, while the transcript still survives via the per-turn save.

---

## Target 2 — undo contract (one-Ctrl+Z coverage)

Contract = wrap mutations in `hou.undos.group(...)` so one Ctrl+Z reverses the
whole op. Per `CLAUDE.md:44` this is **grouping only, not rollback** — a partial
network survives on the exception path (Solaris build paths are the exception:
they `performUndo`-rollback). The `g7`/W5-UNDO/W5-UNDOB seed (node trio +
set_parm + set_keyframe) is confirmed accurate and now **vastly exceeded**.

**~53 of ~59 mutating paths are COVERED** (first-hand): node create/delete/
connect (`handlers_node.py:66/144/174`), set_parm/batch/execute_python
(`handlers.py:1142/1014/1296`, execute_python only on the `atomic` branch),
render/set_keyframe/configure_render_passes (`handlers_render.py:672/1167/2017`),
all 10 USD/LOP handlers (`handlers_usd.py`), all 17 COPs handlers
(`handlers_cops.py`), 3 material handlers, hda_create/hda_package, all 4 Solaris
files, graph-synth via `host/graph_builder.py:131`, solaris_tools via
`mcp/tool_impls/solaris/*`, TOPS `render_sequence.py:182`, and the /mcp bridge on
both sync (`shared/bridge.py:1818`) and async (`:1954`) paths.

### UNCOVERED node-creating / mutating holes (the ceiling above the seed)
| Path | Anchor | Severity | Note |
|---|---|---|---|
| `execute_vex` (geo+attribwrangle under `cook_sandwich`, no group) | `handlers.py:1411` | **P1** | comment at `:1396` admits "no undo group of its own" |
| tops `multi_shot` (topnet/generator/ropfetch/partition/encode) | `render_sequence.py:402` | **P1** | 5 createNodes = 5 undo entries |
| tops `setup_wedge` (wedge node + multiparm) | `wedge.py:121` | **P1** | ungrouped create |
| `render_settings` (ROP/Karma `p.set`) | `handlers_render.py:1228` | **P1** | same class W5-UNDOB wrapped for set_parm, left unwrapped |
| `api_adapter.py` `/api` transport (create/delete/set_parm/execute_python) | `api_adapter.py:215/248/310` | **P1** | **ZERO** undos.group in the whole file — P0 IF routed live (status UNKNOWN) |
| tops `configure_scheduler` (`parm.set`) | `cook.py:192` | P2 | low artist-visibility |
| `hda_promote_parm` / `hda_set_help` (HDA-def edits) | `handlers_hda.py:122/246` | P2/info | may be no-op for `hou.undos`; adjudicate the asymmetry vs wrapped hda handlers |

**`api_adapter.py` is the sharpest hole:** an entire parallel hwebserver
`@apiFunction("synapse")` HTTP transport that mutates the scene with no undo
grouping anywhere. `CLAUDE.md:34` says the live WS path calls `handlers.py`
directly (which wrap), so this appears to be an alternate/experimental transport
— but its live/dead status cannot be resolved by static read. **If ever routed,
it is a total undo-contract bypass (P0).** Flagged for adjudication.

**UNKNOWN (gui_required):** live artist-visible one-Ctrl+Z reversal for EVERY
path (covered or not). Both W5 receipts record this UNKNOWN; static audit and the
recorder tests prove only that the group is *entered* around the mutation, not
that a single Ctrl+Z reverses the built op in a GUI session. House rule:
unobtainable-headless renders UNKNOWN, never a pass.

---

## Target 3 — Qt thread discipline / main-thread marshaling

Marshaling core = `python/synapse/server/main_thread.py:run_on_main`, three arms:
- **fast-path-1** reentrant (`:389`, `_tls.on_main` → inline `fn()`).
- **fast-path-2** caller-already-on-main (`:399`, `ident==_MAIN_THREAD_ID` →
  inline `fn()`, **unbounded** — a long payload freezes the GUI for its whole
  duration; the accepted residual, fully instrumented at `:416-437`, F4 register
  at `:406`).
- **off-main worker arm** (`import hdefereval:443`, `executeDeferred(_on_main):514`,
  `Event.wait(timeout)`, C4 abandoned-flag zombie-kill `:465-467`, F3 pending
  registry `:509`, F4 in-flight register `:476`). This is the ONLY marshal by
  which an off-main thread reaches `hou`.

**Every transport self-marshals:** legacy WS `handlers.py` `_handle_*` wrap
`hou.*` in `run_on_main`; the hwebserver `/mcp` apiFunction adapter marshals via
`_on_main_thread` → `run_on_main` (`api_adapter.py:156`); all TOPS sites via
`_run_in_main_thread_pdg` (`handlers_tops/_common.py:82`). The panel
`ClaudeWorker` QThread reaches `hou` via `run_on_main`'s deferred arm
(`tool_executor.py:565`), NOT Qt AutoConnection (the legacy `tool_requested`
@Slot path has zero emitters + an h7 inline guard). The bridge is a
**defense-in-depth detector**: it records `main_thread_executed = _on_main_thread()`
(`shared/bridge.py:1801`) and hard-rejects a mutation that ran off-main
(`:800-802`), so a forgotten marshal fails its fidelity check rather than
silently corrupting the scene. Cross-thread telemetry reads (`_in_flight`,
`*_stats()`, `cancel_pending_dispatches`) are single-writer-lock-free or
lock-guarded — no torn reads found.

### Deliberate off-main `hou` touches (not accidental)
| Site | Anchor | Severity | Note |
|---|---|---|---|
| WS-path halt `hou.node('/obj').allSubChildren()` + `cancelCook()` from the freeze-timer thread | `emergency_live.py:126` | **P1** | deliberate — the main thread it would marshal onto is the frozen one it is breaking; residual hou-thread-safety risk (graph traversal off-main under active mutation). On record. |
| disconnect hook `hou.hipFile.path()`/`getenv()` on the server daemon thread | `websocket.py:605` | P2 | read-only, fallback transport, unmarshaled — consistency gap |

**No accidental off-main *mutating* `hou` was found.** Doc-debt (P2):
`_common.py:82` docstring claims it wraps the banned `executeInMainThreadWithResult`
but routes `run_on_main`; stale `main_thread.py:240` fast-path-2 pointers in
`marshal_guard.py:16` + `claude_worker.py:406` (actual line is `:399`).

---

## Target 4 — crash recovery (observe, never assert)

Headless read-only recon; a true hard-kill survival test is process/GUI-level, so
timing-dependent survival is UNKNOWN.

### Survives a hard kill (disk-backed, up to last write)
- **Conversation transcript** — atomic `.tmp`+`os.replace` (`session_store.py:103`);
  survives to the last `save_conversation`. Loss window = the current in-flight
  turn (per-turn save at `_on_done`, first-hand). On restart the boot token
  differs → transcript is **parked to `previous`, not auto-reattached**
  (`session_store.py:170`); recovery is `restore_previous_conversation`.
- **Session journal** — append-per-event, per-event open/close, NO fsync
  (`session_journal.py:145`). Survives a process kill; power-loss tail not
  guaranteed.
- **agent.usd provenance IS live during a build** (contradicts a blanket
  "writers dormant" reading): `log_decision` build receipts
  (`graph_synth_runtime.py:121`) + `create_task`/`update_task_status` for
  autonomous_render. Each writer ends in **in-place `stage.GetRootLayer().Save()`**
  (`agent_state.py:594`) — NOT the repo's atomic `.tmp`+`os.replace` idiom → a
  kill mid-Save risks a **corrupt agent.usd** (USD-writer atomicity is
  version-dependent, not observable headless). The other 3 writers
  (routing/handoff/integrity) are genuinely dormant.
- **WS-path emergency halt** → `emergency_halt_<UTC>.json`, atomic rename, no
  fsync (`emergency_live.py:171`).
- **freeze_dump_*.json** — **plain non-atomic** `open(target,"wb").write(blob)`,
  no tmp/flush/fsync/replace (`telemetry_dump.py:312`). NOTE: the scout first
  claimed this was the *most* crash-durable artifact (fsync+replace); the
  adversarial verify **REFUTED** it — that fsync path is the `periodic`
  telemetry branch; the freeze dump falls through to the plain write. It is the
  **least** atomic write of the set.

### Lost on a hard kill (in-memory only)
- Houdini's undo stack (`hou.undos.group`) — process-memory; dies with the
  process. Grouping protects one Ctrl+Z *in session*, says nothing about crash
  survival.
- **No auto HIP-save in the mutation path** (first-hand grep across
  `python/synapse`: the only `hipFile.save` hit is a `$HIP`-resolution comment
  in `solaris_compose_tools.py:99`). A half-built network survives ONLY if the
  artist manually saved → most likely LOST; true survival is UNKNOWN without a
  live kill test.
- /mcp `EmergencyProtocol.trigger_emergency_halt` writes NOTHING to disk —
  returns the report dict (`shared/bridge.py:2941`).
- Moneta memory: deposit is in-memory; periodic 30 s snapshot (atomic);
  `atexit`=clean-exit only; WAL inert → hard kill loses ≤30 s
  (`moneta_store.py:170`). **Default backend is `jsonl`** (`store.py:982`),
  buffered + atexit-flush → a hard kill bypasses atexit and loses the unflushed
  buffer (window UNKNOWN).

### Recovery tooling (reconstruction, not durability)
`scripts/blackbox_recover.py` reconstructs from Claude Code's own transcript
`.jsonl` (external `~/.claude/projects`, survive the kill); detects tail-orphaned
tool calls as death evidence, writes a capsule. Does NOT recover SYNAPSE
in-memory state.

---

## Provenance
- Recon: 4-target Explore fan-out + per-target adversarial Explore verify
  (8 agents, 0 errors). Verify refuted 1 finding (freeze_dump durability) and
  corrected several off-by-one anchors — recorded above as corrected.
- Every P1 anchor was personally re-opened and confirmed before landing in the
  receipt. UNKNOWNs are recorded as UNKNOWN, never zero, never estimate.
