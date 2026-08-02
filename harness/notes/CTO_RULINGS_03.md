# CTO RULINGS 03 — LATENCY WAVE + RESIDUALS

**Ruled** 2026-08-02 · **Authority** Joe: "you are CTO make the call. pre-approved"
**Scope** the latency registry (harness/latency/REGISTRY.json, post-harvest), the
in-flight build wave `wf_006556ba-f9c`, and the open residuals from today's G1 work.
Decisions, not proposals. Executors named. The two standing fences hold: no agent
edits `flywheel_queue.json` / `harness/state/DECISIONS.md`, and `VERSION` stays human.

---

## R301 — Standing merge policy for adversarially-verified waves

Today's precedent is now policy. Crucible says MERGE → merge. MERGE-WITH-FOLLOWUP →
the followup lands BEFORE the push, not "close behind" (the fc1c9e1 precedent: master
never carries a known regression window). BROKEN → one loop-back built from the
crucible's own prescription (the 68ab53e precedent: the 43-hour-spin repair), then
re-attack; a second BROKEN parks the lane with its commit pinned on a
`*-DO-NOT-MERGE` ref. No lane merges on its own green report — the report is input,
the crucible is the gate, the suite summary LINE (never an exit code) is the floor.
**Executor: standing — applies to wf_006556ba-f9c the moment it lands.**

## R302 — The shared T4 instrument comes before any T4 fix

C4 rank 6: non-saturating timing buckets on `_verify_composition` and
`_infer_stage_touch` (bridge.py has exactly two perf_counter calls today, and every
existing histogram saturates at 4000–5000 ms — useless in the T4 regime). One lane,
plus C4 rank 7's two one-line hython probes, plus H3's free-half (cache the
`_stage_exceeds` verdict in the per-op thread-local; assign `composition_valid`,
which has ZERO assignment sites today). This single lane prices H1, H2, and H3
simultaneously and is the precondition R309/H3-gating cite.
**Executor: LANE + crucible, next wave after wf_006556ba-f9c merges.**

## R303 — H6 probe now, H6 fix deferred

The rank-3 probe (un-stub `_handle_message` in a scratch copy of
`tests/test_websocket_cancel_reachable.py` — the stub at :157 is what hid the
defect) rides in the R302 lane: offline, decisive, cheap. The fix-half (control-plane
lane + data-plane worker, C4 rank 10) is DEFERRED: highest effort on the board, and
its seconds are artist-currency (cancel latency), not throughput.
**Reopen condition: the probe confirms + one real cancel-pain instance on the live seat.**

## R304 — The perf ratchet (I2) is RATIFIED to build; arming stays gated

Build exactly the I2 design (wf_b9c32632-1fc journal): counted proxy — full-stage
traversals / prims-visited per op — never wall-clock (CI has no pxr; a timer cannot
gate this repo). `tests/perf_counters.py` + `harness/verify/perf_ratchet.py` +
baseline JSON, floor read at merge-base per house ratchet discipline. The P6 ARMING
flip happens only after the ratchet's own regression proofs survive a crucible, and
records `human_armed_by: Joe (pre-approved batch, 2026-08-02)` — the pre-approval is
the human act; the crucible-pass is the condition it was given on.
**Executor: LANE + crucible, may run parallel to R302 (disjoint files).**

## R305 — I1 scale bench DEFERRED behind I2

The ratchet pins a win we already hold; the bench maps wins we do not yet have.
Sequence capital accordingly. **Reopen condition: I2 merged.**

## R306 — H11 (unconsumed honesty fields): surfacing YES, fidelity mutation NO

The recorded-but-read-by-nothing fields (`stage_hash_mode`, `stage_hash_full_fidelity`,
`composition_checks_reduced`) get CONSUMERS: surface reduced-mode counts in
`operation_stats()` / the session tracker, and stop `panel/session_integrity.py:66`
discarding the `no_change` blind-spot case (count it, labeled, don't hide it).
Explicitly OUT: making these fields lower `fidelity` — the fidelity=1.0-or-stop rule
is load-bearing across the whole doc surface, and a change there is a contract
amendment requiring its own ratification, not a rider.
**Executor: LANE + crucible, after R302.**

## R307 — The tops→websocket order dependence gets an owner

Pre-existing (baseline-reproduced at 4c76cc5, logged in .claude/g1_acceptance.md),
and this session proved the class also bites new tests (the m-group/package-attr
incident). A suite whose green depends on ordering erodes every floor read on it.
One forensic lane: identify the residue `test_tops.py` / `test_tops_assembly.py`
leave behind, fix at the PERPETRATOR (never by hardening the victim alone), pin with
a test that runs the pair in the failing order.
**Executor: LANE + crucible, after wf_006556ba-f9c merges (suite must be quiet first).**

## R308 — The stray audit.py stash: preserved as a ref, dropped as a stash

The uncommitted `log()` threading of `duration_ms`/state-hashes (zero callers,
dataclass half committed at 843d6a8) moves to branch `stray/audit-log-threading`
and the stash is dropped — same preservation pattern as the G1b DO-NOT-MERGE ref.
A stash is invisible inventory; a ref is auditable. If the C4-rank-6 instrument
lane (R302) wants those fields, it revives the branch; otherwise it dies of natural
causes in the branch list. **Executor: INLINE, now.**

## R309 — H8 (perceived latency) queued to the panel track

Zero measured wall-clock by its own adjudication; its currency is felt-time with
its own acceptance test. It joins R204 (panel IntegrityBlock readout) in the next
panel session under panel discipline (hython-offscreen verification, full-suite
gate). Not built tonight, deliberately — panel work in a non-panel session is how
regressions slip. **Executor: queued, panel session.**

---

**Sequence:** wf_006556ba-f9c merge (R301) → R302+R304 parallel wave → R306, R307 →
I1 (R305) → panel session (R309 + R204). H3's gating-half stays behind its probe
(C4 rank 9 — the one T4 item that can create a new integrity blind spot).

## R310 — The module-planting class: finish the kill (surfaced by R307, 2026-08-02)

Lane O fixed the canonical idiom (synthetic namespace package planted into sys.modules
WITHOUT parent-attribute binding) at 25 perpetrator files and pinned the pair-order
reproduction. Two residues it correctly left out of scope:
- ~20 further sites plant dotted modules via spec_from_file_location in OTHER shapes
  (e.g. spec_from_file_location("synapse.server.rbac", ...)). Same class, different
  costume. **Ruling: LANE + crucible, low priority — sweep the remaining shapes with
  the same fix-at-perpetrator discipline, one commit, pinned the same way.**
- tests/test_m3_logs_doctor.py flaked 2/6 full-suite runs at Lane O's HEAD, a
  DIFFERENT test each time, in a file the lane never touched. Unattributed, recorded
  honestly. **Ruling: OWN IT before it erodes a floor read — one forensic pass:
  reproduce under -p no:randomly repetition, attribute (timer race / tmp collision /
  ordering), fix at cause or file the skip-with-ticket. Never waive it silently.**
