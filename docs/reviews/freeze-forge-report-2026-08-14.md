# Freeze-Relief Forge — Verification Report (2026-08-14)

Verifier: independent pass over `fix/ui-freeze-relief` in
`C:/Users/User/SYNAPSE/.claude/worktrees/freeze-relief`, against the amended
spec `docs/reviews/ui-freeze-fix-spec-2026-08-14.md`. No fixes applied —
verify only.

**Verdict: SHIPPED — all six legs conform to spec; focused tests 339 passed /
0 failed. Two stated deviations (one deliberate tightening, one spec-sanctioned
risk) itemized below.**

---

## 1. Commit discipline

12 commits on `master..HEAD`, oldest first:

| Commit | Leg | Subject (abridged) |
|---|---|---|
| d625ee61 | F4 | instrument honesty — in-flight main-thread register + labels |
| 737db251 | F2 | retry cascade circuit-breaker (register-rooted) |
| d318ab7a | F3 | emergency net wiring |
| e12b82a1 | F1 | update-mode sandwich + run-by-Joe probe gate |
| d27baf43 | F6.1 | scene-gather record_stall=False |
| b28bfea6 | F6.2 | query_prims \_walk visit-counter bound (25k) |
| b89027be | F6.3 | reference_usd 30s budget owned by core/timeouts |
| e9c75cf8 | F6.4 | houdini_capture_viewport into \_KNOWN_SLOW_TOOLS |
| 8e6055ab | F6.5 | WS \_handle_inspect_scene marshal → timeout_for 30s |
| 22ecfea6 | F6.6 | read-only reconciliation counts re-derived live + test_f6_hygiene.py |
| 11debc8d | (test) | re-pin 8 USD fake run_on_main lambdas for F4's label= kwarg |
| 48667545 | F5a | render-offload probe only (no behavior change) |

Checks pass:

- **One-per-fix discipline holds.** F1–F4 land as one commit each; F6 lands as
  six commits, one per hygiene item; F5a is probe-only as re-scoped. Sequencing
  matches the spec forge order (F4 → F2 → F3 → F1 → F6 → F5a), including the
  load-bearing F4-before-F2 dependency.
- **No pushes.** `fix/ui-freeze-relief` does not exist on
  `origin` (only `finish/freeze-attribution` does). Reflog shows local commits
  only.
- **Nothing outside the worktree.** All commits are inside
  `C:/Users/User/SYNAPSE/.claude/worktrees/freeze-relief`.
- Untracked evidence in the worktree: `docs/reviews/crucible-full.json`,
  `docs/reviews/freeze-recon-full.json`, and the spec itself — inputs to the
  forge, left untracked; decision on whether to commit them is Joe's.
- The test re-pin commit (11debc8d) is honest in its message: F4 added
  `label=` kwargs to handlers_usd.py call sites and 48 USD-fake tests broke on
  the unexpected keyword; re-pinned forward, contract unchanged. Disclosed
  repair, not a hidden spec change.

## 2. Per-fix conformance

### F2 — retry circuit-breaker — CONFORM (one tightening, see Deviations)

`panel/retry_breaker.py` (pure decision half) + `claude_worker.py` wiring.

- Consults **`current_main_thread_holder()`**, never `stall_state()` — the
  crucible FATAL is landed. `claude_worker._check_retry_breaker` imports the
  register directly; the module docstring states the re-root reasoning.
- Abandons keyed by `(tool_name, canonical-json input)`; counted on both
  abandon shapes (MCP RuntimeError "STILL be running inside Houdini" and
  worker-level wait-budget timeout); success clears the counter.
- Sentence matches the spec form: *"Houdini is busy — a {label} operation has
  held the UI for {elapsed}s. Try again when it finishes."* — elapsed computed
  from the register's `start_ts`, `slowest_label` demoted.
- Threshold is 2 consecutive abandons, as specified.

### F1 — update-mode sandwich — CONFORM

`server/update_mode.py` (new) + call sites.

- Snapshot → `Manual` → yield → **`finally:` restore the pre-sandwich mode** →
  explicit **`hou.ui.triggerUpdate()`** (vendor-documented mechanism; the
  "restore re-cooks" claim is carried as UNVERIFIED in the module, not relied
  on). Restore failure is logged LOUD and counted
  (`restore_failures`), triggerUpdate still attempted.
- **Flag-gated, dev-default-OFF**: `SYNAPSE_COOK_SANDWICH`; passthrough no-op
  when off, headless (`hou.isUIAvailable()` False), or `hou` absent. Restore
  is the snapshot, not a constant (nested-payload probe item (d) honored).
- Call sites: `execute_python` (inside the undo group on the atomic path —
  probe item (c) nesting), `execute_vex`, `solaris_build_graph` (with
  `note_estimate(len+1)` A/B hint).
- **`batch_commands` untouched** — excluded per the sandwich-scope-≤-op-scope
  invariant, and pinned by `test_callers_do_not_wrap_batch_commands`.
- Instrumented A/B readout: sandwich histogram + collapsed-cook estimates
  surface in `doctor.py`'s `_check_main_thread` under `"cook_sandwiches"`.

### F3 — emergency net — CONFORM

- **Never-construct invariant intact**: `freeze_chain.py` contains no breaker
  constructor — only `register_transport_breaker`/`unregister_transport_breaker`
  slots. The breaker is constructed in `hwebserver_adapter.start_hwebserver`
  (startup) and registered for the chain to read; unregistered on stop and on
  startup-failure unwind.
- `session_report` caller fix landed as scoped: `_peek_active_bridge` now
  duck-type-validates `callable(session_report)` before handing the object to
  `EmergencyProtocol` — the session-tracker `SynapseBridge` no longer reaches
  the halt; no new attribute implementation.
- **WS-path halt never waits on the main thread** (`server/emergency_live.py`):
  reads F4's register (lock-free), flips C4 abandoned flags via
  `main_thread.cancel_pending_dispatches` (lock+bool only), cancels PDG
  contexts from the halt thread, writes a bounded
  `emergency_halt_<UTC>.json` (atomic tmp+replace, pruned to newest 5).
  Deliberately does NOT re-fire a freeze dump (protects the bounded
  newest-5 freeze evidence and the "one escalation = one sustained_freeze
  dump" pin). See Deviations for the PDG-sweep thread note.
- The F3 companion mechanism — `main_thread.py`'s pending-dispatch registry —
  registers before `executeDeferred` and deregisters in `finally`, so the halt
  only reaches dispatches a caller still awaits.

### F4 — instrument honesty — CONFORM

- Register on **both dispatch paths**: fast path 2 sets `(label, start_ts)`
  before `fn()` and restores in `finally` (save/restore for nesteds);
  deferred `_on_main` sets it after the C4 abandoned-check passes and clears
  in `finally` — deferred zombie renders are named mid-flight.
- `current_main_thread_holder() → (label, start_ts) | None` is the public
  read; single-writer (main-thread-only) discipline documented.
- Labels added across handlers_usd, handlers_cops, api_adapter,
  live_metrics, integrity_envelope, probe_main_thread, et al.
- Freeze dump (`telemetry_dump.py`) now samples the live holder with `held_s`
  age — the "651ms doctor vs 179s in-flight execute_python" inversion is
  closed.
- The 5–6s detector-stickiness blind spot is correctly left probe-first /
  UNKNOWN, as the spec demands.

### F6 — hygiene bundle — CONFORM (all six items)

1. `live_metrics.py` scene-gather `record_stall=False`, with the
   crucible-accepted mitigation stated in code (F4 register still observes).
2. `query_prims` `_walk` visit bound (25,000 visits) added; `truncated` now
   covers both caps.
3. `reference_usd` 30s budget **owned by `core/timeouts.SLOW_COMMANDS`**, the
   marshal reads `timeout_for("reference_usd")` — transport and marshal agree;
   the no-new-zombie-window reasoning is stated inline (crucible item-3 note).
4. `houdini_capture_viewport` added to `_KNOWN_SLOW_TOOLS`.
5. WS `_handle_inspect_scene` marshal raised to `timeout_for('inspect_scene')`
   = 30s.
6. Counts **re-derived at forge time**, not copied from the spec: transport
   registry 40, bridge set 36, divergence 4 (cops_temporal_analysis,
   synapse_propose_graph, **synapse_render_processes**, synapse_validate_frame);
   `tool_bridge.py` header corrected 102→124. `tests/test_f6_hygiene.py` pins
   membership so the sets cannot silently re-diverge.

### F5 — CONFORM (re-scoped to probe-only)

`harness/notes/probe_render_offload.py` (463 lines) +
`docs/reviews/render-offload-f5a-design-gate.md`. Zero production behavior
change — no default flip, no `_handle_render` contract touch, the
`render_progressively` 256px escape hatch untouched. F5b stays gated behind
Joe's sign-off, per spec.

### Guardrail surfaces — CLEAN

Diff-wide grep: no modifications to consent-gate wiring, RBAC, C5, or the
`_READ_ONLY_COMMANDS` **set**. The only `_READ_ONLY_COMMANDS` hits are three
new read-only uses in hwebserver_adapter (import + membership checks for the
F3 breaker gate — read-only commands correctly bypass the breaker during a
freeze, mirroring the websocket path). `mcp/server.py`'s `_READ_ONLY_TOOLS`
touch is a comment-only count refresh.

## 3. Test results

Command (from the worktree):

```
python -m pytest tests/ -q -k "main_thread or retry or freeze or update_mode or consent or bridge"
```

Result — verbatim:

```
======== 339 passed, 5 skipped, 6128 deselected, 38 warnings in 29.72s ========
```

(84 further tests in 7 modules deselected by the standing
`-m 'not needs_houdini'` marker — they require a live Houdini runtime.)

Includes the new pin suites: `test_main_thread_holder.py` (265 lines),
`test_retry_breaker.py` (262), `test_f3_emergency_net.py` (353),
`test_update_mode_sandwich.py` (226), `test_f6_hygiene.py` (132).

The full suite beyond the `-k` filter was not part of this verify charter;
recommend one full `pytest tests/` pass before merge.

## 4. Deviations from spec

1. **F2 breaker requires a live holder (deliberate tightening).** Spec text:
   "After 2 consecutive abandoned attempts of the same command, stop
   retrying." Implementation: the breaker opens only when the count ≥ 2 **and**
   `current_main_thread_holder()` returns a holder right now; an idle main
   thread resets the history and lets the retry through. Stricter and safer
   than the letter of the spec (a stale count can't fast-fail after the hold
   cleared), and consistent with the spec's own anchoring on the register's
   live state — but it is a behavioral superset Joe should ratify.
2. **F3 WS-path halt calls `hou.node("/obj").allSubChildren()` from the halt
   thread.** The spec explicitly sanctioned PDG cancel "from THIS thread, not
   marshalled," and the sweep is fully try/excepted — but be aware: calling
   `hou` off the main thread is generally unsafe in Houdini, and this path
   fires exactly when the main thread is frozen. Spec-endorsed, not
   live-probed. The probe-first live session below is the right place to
   watch it.
3. Cosmetic: `integrity_envelope.py`'s new `label=` kwarg landed with odd
   continuation indent; parses fine, tests pass. Not worth a churn commit.

## 5. Handoff — live verification for Joe

**Step 0 — the two probe gates (run first, on H22.0.400, before any F1/F5
claims):**

- **0a. F1 probe** — run `harness/notes/probe_update_mode_sandwich.py` inside
  H22's Script Editor / hython+GUI session. Establishes: (a) symbols exist on
  22.0.400; (b) Manual→mutate→restore+`triggerUpdate()` = exactly one
  consolidated cook (cookCount deltas on a probe chain); (c) sandwich inside an
  open undo group does not swallow artist edits; (d) nested `setUpdateMode`
  payloads restore to the pre-sandwich mode. **Pass = F1 stays behind the
  flag and gets enabled; fail = F1 descoped with the probe evidence.**
- **0b. F5a probe** — run `harness/notes/probe_render_offload.py`. Establishes
  husk-on-Indie ground truth and what `node.render()` does under a
  background-mode Karma ROP; reconciles the contradictory in-tree evidence.
  Result decides whether F5b gets designed at all. Nothing in F5 changes
  behavior today.

**Step 1 — the live session protocol (after probes):**

1. Start H22 + panel, run a normal panel session (build a component, render).
   Keep the sandwich flag OFF for a baseline pass, then set
   `SYNAPSE_COOK_SANDWICH=1` (restart) for the A/B pass.
2. Trigger a deliberately long `execute_python` (e.g. a 100-node build flood).
3. Expected with the flag on: one consolidated cook instead of a cook storm;
   the sandwich histogram (via doctor `"cook_sandwiches"`) shows the shortened
   hold; if a hold still occurs, the panel says **what** holds the UI and
   **for how long** instead of piling retries.
4. Take a freeze dump during any hold — it now names the in-flight holder for
   **both** the inline (fast path 2) and deferred zombie classes.
5. Kill-switch drill: fire `synapse_emergency_halt` with no `/mcp` bridge
   live — expect the WS-path halt to act (pending-dispatch abandon, PDG
   cancel, bounded `emergency_halt_<UTC>.json` state write, panel notification
   via the breaker fast-fail sentence) **without waiting on the frozen main
   thread**, and the dump to record the in-flight holder.
6. Retry drill: let the panel re-issue the same timed-out command — after 2
   consecutive abandons with a live holder, expect the breaker sentence
   naming the holder and the hold's age.
