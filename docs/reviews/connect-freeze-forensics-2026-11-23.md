# Freeze forensics: the Connect freeze of 2026-11-22

> Copied into the repository on 2026-11-23 from the read-only forensics of the same day. Local machine paths are replaced by descriptions; nothing else is changed. Code citations are to tag v5.104.1, so later line numbers differ. The fix that followed (remediation 1 below) is in `python/synapse/mcp/server.py` `_handle_initialize`.

**Verdict in one line.** The cause is **not identified**. Two causes still stand, both **OPEN**. Two are **REFUTED**. None is confirmed, because no freeze dump in the record has a stack.

**What is confirmed** is the structural defect that turns any slow step into a full hang. Every MCP `initialize` runs `synapse_project_setup` on Houdini's main thread. Nothing reads the result, and once that work starts nothing can stop it.

Scope and sources:

- **Code:** a git archive of tag v5.104.1. Paths below are relative to the repository root at that tag.
- **Evidence:** copies of the seat's logs, freeze dumps and Windows event exports. They stay on the seat and are not in this repository. `L<n>` is a line number in the seat's `synapse.log`.
- **Times:** given in Z. The seat runs on UTC-5, so 17:49Z is 12:49 local.
- **Method:** read-only throughout. No Houdini, hython or git was run, and no code was changed.

---

## 1. What happened

**The bad start: 2026-11-22, pid 25020, v5.104.0, untitled scene, the seat's first start with auth on**

| Time (Z) | Event | Source |
|---|---|---|
| 17:49:17.974 | Server up on `ws://127.0.0.1:9999/synapse`. These are the last lines logged before the hold. | L33388-33390 |
| ~17:49:17.984 | Last main-thread heartbeat. There were 3 in total. | derived from the dump: ts minus `last_heartbeat_ago` |
| ~17:49:18.737 | `run_on_main` posted with label `mcp:initialize:project_setup` and a 10 s budget | derived: timeout #1 minus 10 s |
| **17:49:18.857** | **The payload starts on the main thread and never returns** | `freeze_dump_20261122_174947.json` `main_thread_holder.start_ts` |
| 17:49:23.952 | FREEZE DETECTED (6.0 s) | L33391-33392 |
| 17:49:28.737 | Timeout #1. The initialize caller gives up, but the payload has already started. | L33393 |
| 17:49:43.739 | The panel's `synapse_doctor` call fails with `MCPOutcomeUnknown` | L33395 onward |
| 17:49:47.988 | SUSTAINED FREEZE. The breaker opens and the dump is written (held_s 29.135). | L33438-33441 |
| 17:49:47.996 | 2 pending dispatches abandoned | L33442 |
| 17:50:20.842 | Timeout #7. This is the last line the process logged. | L33447 |
| **17:50:26** | **Windows Application Hang 1002 and AppHangB1.** Houdini is closed after a hold of about 67-68 s. | `windows-app-events-20261122.txt` |

**What set it off.** The panel's MCP client sends `initialize` lazily, on its first tools/call (`python/synapse/panel/tool_executor.py:331-347`). The timing and the 17:49:43 traceback place that first call at the Doctor button (`python/synapse/panel/doctor_dialog.py:121`). The Doctor runs on a QThread, and its own 10 s marshals then chained timeouts #2-#7 behind the hold.

**Missing log lines.** After 17:49:17.974 there is no `Seeded memory.md`, no `Initialized agent.usd` and no `Scene structure ready`. Every good untitled start logs all three. On the 18:27Z good start they came at 18:27:37.400-.460, 1.9 s after server up.

**The good relaunch: 18:27Z, pid 67416, same install.** It was started the way the Start-menu shortcut starts Houdini, with the stack recorder armed. `project_setup` took about 2 s. No stack dump was written (`stack-67416.log` has only the arm and tick lines).

**The headless control** (`project-setup-probe.txt`) took 0.29 s and 0.19 s. It forced `HIP` and `JOB` to a local scratch scene folder of the v5.104.0 release build, and `HOUDINI_TEMP_DIR` to a folder inside it (line 1 of the probe output), and it dispatched on hython's main thread directly. **It never exercised the GUI's `$JOB`, the GUI's launch context, or the hwebserver-to-hdefereval path.**

---

## 2. Ranked causes

### How the window is bounded (what all causes share)

The call path in v5.104.1 runs in this order:

1. `python/synapse/mcp/server.py:598-610`: `run_on_main(_preload_project_context, timeout=10.0, label="mcp:initialize:project_setup")`.
2. `dispatch_tool`, then `execute_through_bridge`, then the bridge's `_execute_houdini`. In `shared/bridge.py`: `scene_hash_before` at :1943, `_undo_evidence_snapshot` at :1947-1949, `hou.undos.group` at :1950, `operation.fn` at :1951, `scene_hash_after` at :1953.
3. `_handle_project_setup` (`python/synapse/server/handlers_memory.py:305-312`).
4. `_scene_paths` (`handlers_memory.py:135-171`).
5. `ensure_scene_structure` (`python/synapse/memory/scene_memory.py:346-405`).

Three pieces of evidence bound where the hold sits:

- **The 11-22 dump: the hold began after `bridge.py:1943`.** It records `scene_hash.count=1` (0.080 ms), `stage_touch.count=1` (0.002 ms) and `composition.count=0`. The before-hash finished and the after-hash never ran.
- **The 11-22 log: the hold began before `seed_scene_md` finished.** There is no `Seeded memory.md` (`scene_memory.py:442`).
- **The 11-08 dump points into the `_scene_paths` main-thread body.** Its holder is `memory:_scene_paths`, held 29.247 s. That body is `handlers_memory.py:150-169`: `hou.hipFile.path`, `resolve_hip_dir`, `hou.getenv("JOB")`, `resolve_job_dir`.

**Why the two labels differ.** A nested `run_on_main` inside a deferred payload takes fast path 1 (`python/synapse/server/main_thread.py:496-497`) and never relabels the holder. So on 11-22 the outer label covers every inner step.

**Why the hold is unbounded.** Two rules in `main_thread.py`:

- The `abandoned` flag is checked only before `fn()` runs (:584-587). The finally block states that "an already-started payload remains free to finish" (:674).
- The inline path says outright "NO bounding is applied here" (:528-530).

---

### Standing cause 1: H1 (narrowed). A fixed `$JOB` under OneDrive blocks the single `isdir` stat

**Status: OPEN.** It survived attack, but only in narrowed form.

**Mechanism.** `_scene_paths._on_main` reads the raw `hou.getenv("JOB", hip_dir)` (`handlers_memory.py:166`) and calls `resolve_job_dir` (:167). That leads to `_resolve_memory_parent`, whose first filesystem touch is `os.path.isdir(<JOB>/claude)` (`scene_memory.py:265`).

If `$JOB` is a fixed path inside the OneDrive sync root, and the cloud-files provider is connected but not answering, that stat can wait in the kernel on the main thread. Nothing in SYNAPSE bounds that wait.

For an unsaved scene, this stat is the only filesystem call in the 11-08 holder window that can reach storage outside the machine. The rest resolves under Houdini's local temp folder (`houdini_temp` in the user's local temp directory), as the good-start log lines show.

**What the attack removed.** The original H1 also blamed the `mkstemp`/`close`/`unlink` probe (`_can_create_under`, `scene_memory.py:202-229`) and a `$JOB` taken from the launch folder. Both legs are dead:

- **The probe leg never runs on this seat.** `grep -ci relocat synapse.log` returns **0** across 33,498 lines. No untitled start since early October has logged `Seeded project.md`; the last five seeds, L28596-L32865, are all saved scenes on `D:` or OneDrive. So `<JOB>/claude` existed on every logged start, and `:265` short-circuited before `_can_create_under` (:271) could run.
- **`$JOB` does not follow the launch folder.** On 11-16 a process was launched from the Codex app folder: its HIP was in WindowsApps (L33118, 16:45:05 local, from `session_store`, which is keyed on the HIP dir). That process ran `project_setup` with no relocation and no `project.md` seed. A `$JOB` taken from that folder would have failed `mkstemp` and warned (`scene_memory.py:244`, :276).

**Against what is left:**

- A stat on an existing, fully downloaded folder normally needs no callback to the cloud-files provider.
- The 18:27Z good start, 38 minutes later, would have hit the same fixed `$JOB`. The two starts may have differed in launch context, but the 17:49Z launch method is not recorded.
- OneDrive's state at 17:49Z is unknown: `onedrive-events-20261122.txt` is 0 bytes. It was found not running on 11-23.
- The roughly 60 s provider timeout is unverified recollection.

**Closing probe:**

- **First, a cheap read-only check:** find where `$JOB` is set on the seat (houdini.env in the OneDrive prefs folder, the user env, or the machine env), and whether that path is inside the user's OneDrive folder. If `$JOB` is local, H1 is effectively closed without a launch.
- **Then a live check:** a cold GUI launch with the stack recorder armed. H1 is **supported** only if the main-thread stack's innermost frame is `genericpath.isdir` called from `scene_memory.py:265`, with `$JOB` under OneDrive. **A main-thread stack anywhere else refutes it.**

---

### Standing cause 2: H3. HOM contention with another thread at a later `hou.*` call

**Status: OPEN.** It survived attack but cannot be falsified on the current evidence.

**Mechanism.** The payload makes several `hou.*` calls on main after the before-hash:

- `hou.undos.areEnabled` / `undoLabels` (`shared/bridge.py:351-381`, via :1947-1949)
- entering `hou.undos.group` (:1950)
- `hou.hipFile.path` (`handlers_memory.py:151`)
- `hou.hipFile.isNewFile` (`python/synapse/memory/store.py:1457`)
- `hou.text.expandString` (`scene_memory.py:167`)
- `hou.getenv` (`handlers_memory.py:166`)

H3 says one of those calls blocked because another thread held Houdini's HOM lock while that thread waited on something the main thread owns.

**What the attack narrowed.** The 11-22 dump shows the payload's first HOM call finished: `hou.node` inside `_compute_scene_hash` (`bridge.py:1122`, called from :1943). So "the first HOM read blocked" is wrong. A block, if there was one, came at a later call.

**For it:**

- The shape is real in this GUI. On 11-22 the halt thread logged `Abandoned 2` (L33442), then entered a bare off-main `hou.node('/obj').allSubChildren()` (`python/synapse/server/emergency_live.py:126`). It never logged the `LIVE-PATH EMERGENCY HALT` line that should follow. An off-main HOM caller stayed stuck while main was held.
- **One new reading, from a code comment in the archive** (`python/synapse/mcp/server.py:574-586`, R-001). Before R-001, the bridge's undo group and R1 scene hash ran on the calling hwebserver worker. That was a bare off-main `hou.*` call, and only the handler's `_scene_paths` was marshalled to main. If v5.97.6 still ran that path, then on **11-08** SYNAPSE itself had an off-main HOM caller, holding an open undo group, while main ran `_scene_paths`. That fits the 11-08 dump's slow `scene_hash` of 337.5 ms against 0.08 ms on 11-22.
- **Caveat on that reading:** this is inferred from the comment. The v5.97.6 source is not in this archive. On 11-22 (v5.104.0) the envelope runs on main, so the comment does not identify a partner thread for 11-22.

**Against it:**

- No off-main `hou.*` caller at startup is identified in v5.104.1:
  - `live_metrics` marshals (`python/synapse/server/live_metrics.py:274-287`).
  - The panel context gather marshals (`python/synapse/panel/ws_bridge.py:130-178`).
  - `emergency_live.py:126` fires 30 s into the hold, so it is a result, not the trigger.
- For H3 to hold, a foreign thread would have to win the lock in the microseconds between two main-thread HOM calls.
- The blocked halt thread shows only that main blocks off-main callers. Every hypothesis predicts that, and 11-06 (a class B stall with no holder) showed the same delayed halt lines (L32499-32505).

**Closing probe.** A cold GUI launch with an all-threads stack dump that lands about 10 s into the hold. It has to come before the 30 s halt adds its own off-main `hou.node` call. The existing recorder dumps every Python thread every 10 s.

- **H3 is confirmed only if both hold:** the main frame sits on one of the HOM lines above, **and** a different thread (not the freeze-chain timer) is inside `hou.*` in the 10 s dump.
- **H3 is refuted** if the main frame is in `os`/`genericpath`/`tempfile` under `scene_memory.py`, or if no other thread is in `hou.*` at 10 s.
- A freeze with `$JOB` pinned to a fresh local folder also counts for H3 and against H1.

---

### Refuted: H2. `$JOB` is an unreachable network path

**Killing line.** The variable H2 depends on, a `$JOB` inherited from the launching process, does not change between launches. The 11-16 Codex-launched process (HIP in WindowsApps, L33118) resolved project memory twice under one session uuid, with no relocation warning and no `project.md` seed. So `isdir(<JOB>/claude)` was True there.

Across all 33,498 log lines every `project.md` path is on `C:` or `D:`. No UNC or other network path appears anywhere.

**Residual:** a fixed `$JOB` on a mapped drive that happened to be offline at 17:49Z is unevidenced. It would also predict a finite SMB timeout followed by a logged relocation, which is not the 68 s hang with no return that was observed.

### Refuted: H4. Python import-lock deadlock on a first cold import

**Killing line.** The import chain is already loaded before the payload starts:

- `python/synapse/server/hwebserver_adapter.py:66` imports `session.tracker`.
- `tracker.py:21-24` imports `memory.store`, `models` and `native_panic`.
- `hwebserver_adapter` logged at L33390 before the payload began.

The probe also ran an AST scan of every `.py` under `python/synapse` for module-level marshals or `hou.*` calls. It found **0** non-trivial hits, so no module can hold an import lock while it waits on main. Even if one did, `run_on_main`'s 10 s timeout would unwind the import and release the lock. That cannot explain a 67 s hold.

---

### Count

| Verdict | Count | Causes |
|---|---|---|
| CONFIRMED | 0 | none |
| OPEN (standing after attack) | 2 | H1 (narrowed), H3 |
| REFUTED | 2 | H2 (by attack), H4 (by probe) |

---

## 3. How this relates to the 11-08 dump and the others

**Class A: a startup `project_setup` hold.** Seen on 11-08 (v5.97.6) and 11-22 (v5.104.0). It is the only class with a named holder.

- **Shared fingerprint:** a fresh GUI process with an untitled scene and 3-5 heartbeats; the hold starts 0.9-1.8 s after server up; `scene_hash.count=1`, `stage_touch.count=1`, `composition.count=0`; the 10 s timeout fires on a payload that has already started; no recovery and no `Watchdog stopped` line.
- **The trigger time is normal.** Good starts log their first `scene_memory` line 1.8-6.7 s after server up, so 0.9 s and 1.8 s are not unusual. Only the failure to return is.
- **Not caused by** auth (11-08 ran with auth off, L32518), the bind address (the 18:27Z good start used the same `127.0.0.1` with auth on), or the `PXR_PLUGINPATH`/Moneta fault (present on the good start too).
- **One difference between the two incidents:** on 11-08 the bridge envelope probably ran off-main (the R-001 comment, see H3). On 11-22 everything ran on main. So the two may not share a single root cause, even though both hold inside `_scene_paths`.
- **Hit rate:** 2 of about 10 logged starts since 11-08.

**Class B: in-session stalls with no holder.** 11-06 (v5.97.6, a 15 h session) and both 11-16 dumps (v5.100.0, a saved scene with 470 nodes).

- The holder register is null, so no SYNAPSE payload owned the main thread.
- The stalls ran 10-72 s, and most recovered on their own. SYNAPSE was a queued victim here, with dispatch waits up to 20 s and 104 s.
- The 8.9 s, 8.4 s and 7.8 s stalls at 18:54-18:55Z in the good 11-22 session are a small member of this class (L33482-33496).
- **This class is out of scope for this verdict.**

**Missing from the evidence:** `freeze_dump_20261106_133811.json` is named at L32486 but was not supplied.

---

## 4. Remediation ticket

Ranked by leverage. **No code was changed.** Owners follow the CLAUDE.md agent roster.

**1. Take `project_setup` off the MCP `initialize` path.** Highest leverage: it removes the class A trigger whatever the root cause turns out to be.

- **Owner:** SUBSTRATE. **File:** `python/synapse/mcp/server.py:598-623`.
- **Why it is safe:** the preload's only output is `session.project_context` (:621). Nothing in the tree reads it; the only other reference is the slot at `python/synapse/mcp/session.py:51`. `initialize` also swallows every failure (:622-623), so a 10 s timeout looks like a successful handshake.
- **The test that would pin it:** extend `tests/test_mcp_initialize_main_thread.py` so that `initialize` makes zero `run_on_main` calls and does not dispatch `synapse_project_setup`, and so that a `project_setup` stub that hangs cannot delay the handshake.
- **Limit:** the server's own instructions tell clients to "START EVERY SESSION: Call synapse_project_setup" (:646). The same window can therefore still open on the first `tools/call`. Fix 2 is what closes it there.

**2. Keep filesystem work off the main thread in `_scene_paths`.** This addresses H1.

- **Owner:** SUBSTRATE for the handler, CONDUCTOR for `memory/`. **Files:** `python/synapse/server/handlers_memory.py:150-171` and `python/synapse/memory/scene_memory.py:247-319`.
- **The change:** only `hou.hipFile.path`, `isNewFile`, `expandString` and `getenv` need main. Return the raw strings from main, then run `resolve_hip_dir`/`resolve_job_dir` (isdir, mkstemp) on the calling thread with a bounded wait. Apply the same split to `ensure_scene_structure`'s makedirs and seeds when they run under the bridge.
- **The test that would pin it:** patch `os.path.isdir` in `_resolve_memory_parent` with a stub that records its thread. Assert that it never runs while `_tls.on_main` is set, and that a stub that sleeps 60 s does not hold the main-thread marshal.

**3. Make the holder register name the inner step.** This addresses every open cause.

- **Owner:** SUBSTRATE. **File:** `python/synapse/server/main_thread.py:496-497` (fast path 1).
- **The change:** on a nested `run_on_main`, save `_in_flight`, set it to the inner label, then restore it. The 11-22 dump would then have read `memory:_scene_paths`, as the 11-08 dump did. Optional: a step breadcrumb inside `_scene_paths` and the bridge envelope.
- **The test that would pin it:** inside a deferred payload labelled `outer`, a nested call labelled `inner` reports `current_main_thread_holder()` as `inner` while it runs and `outer` after it returns.

**4. Stop the freeze chain making a bare off-main `hou.*` call.** This one compounds a hang; it does not cause it.

- **Owner:** SUBSTRATE. **File:** `python/synapse/server/emergency_live.py:118-137`.
- **The problem:** `_cancel_pdg_contexts` calls `hou.node("/obj").allSubChildren()` from the timer thread while main is known to be held. On 11-22 the halt never logged its completion line.
- **The change:** skip the sweep while a holder is registered, or defer it until main recovers.
- **The test that would pin it:** with a holder registered, the halt makes no `hou.*` call and still logs its completion line.

**5. Lower-leverage hygiene.**

- `cancel_pending_dispatches` flips flags but does not wake the waiters. The 17:49:38 caller still timed out at 17:49:48 (L33443).
- The `/mcp` server's own `synapse-mcp` breaker (`python/synapse/mcp/server.py:423-429`) is never registered with the freeze chain.
- **Owner:** SUBSTRATE. **Test:** after `cancel_pending_dispatches`, a queued waiter returns at once rather than at its timeout.

**H3 has no fix direction** until its partner thread is identified. Fix 3 and a stack dump are what would identify it.

---

## 5. What is still unknown

1. **The bad process's launch context.** How Houdini was started at 12:49 local on 11-22, its working directory, its parent process, and its `$JOB`/`$HIP`. None of it was recorded.
2. **Where `$JOB` is set on the seat,** and whether that path is under OneDrive. That one read-only check decides H1 cheaply.
3. **OneDrive's state** at 17:49Z on 11-22 and 17:51Z on 11-08. The OneDrive event file is 0 bytes.
4. **The stack.** No dump in the record has one. That is the single missing piece of evidence.
5. **The v5.97.6 source.** It is not in the archive, so "the same `_scene_paths` body" and "the envelope ran off-main on 11-08" are inferred, the second from the R-001 comment.
6. **Whether v5.104.1 changed this path.** It was checked against `CHANGELOG.md` lines 5-22 only (the PXR_PLUGINPATH join, the MCP auth text frame, the collider, World Labs). No diff was possible without git.
7. **Recovery.** Whether 11-22 would have recovered given more time. The 11-06 class B stalls recovered at 71.6 s and 72.4 s; Windows closed Houdini at about 68 s.
8. **The 18:27Z trigger.** What triggered `project_setup` on the good start is not recorded; the log shows no Doctor line before it.
9. **The cloud-files provider timeout** (about 60 s) is unverified.
10. **A missing dump:** `freeze_dump_20261106_133811.json` was not supplied.
11. **The recorder's own effect.** It was armed only on the good run, so whether it changed the startup timing cannot be ruled out.
