# v5.42.0 — the receipts release

The front door works, the receipts stopped lying, and won latency is now pinned.

## The P0, closed on the live seat
- `memory_write` no longer dies with WinError 5 on a fresh unsaved scene — scene
  memory resolves a writable address, discovery still reads the raw `$JOB` root
  (G1a + followup), verified over raw WS against the captured cold-boot baseline
  (`scripts/live_probes/probe_g1_acceptance_ws.py`).
- `doctor`'s permanently-red install-stamp false alarm fixed for repo-direct
  installs (G1c).

## Four honest-receipt fixes — same family: a green light that couldn't say no
- `health` now carries `write_plane` (and its probe can no longer hang ~43 hours
  on an ACL-denied dir — one non-retrying syscall, pinned by a real icacls test).
- `composition_valid` carries a real verdict (it had ZERO assignment sites — an
  anchor that could never fail). Failed compositions now read fidelity 0.0.
- Ops that fail BEFORE validation record `composition_applicable=false` instead
  of inheriting "ran and passed" (K4).
- Reduced-mode hashing is now COUNTED: `operation_stats()` lifetime counters +
  the session tracker's `unobservable_deltas` (R306). Fidelity semantics
  deliberately untouched.

## Latency: measured, fixed, and pinned
- The agent loop stamps an incremental prompt-cache breakpoint each iteration
  (kills the O(K^2) re-prefill) and captures real usage via `last_usage` — the
  producer that can finally price it.
- The stage-hash gate re-keyed on AUTHORED ARRAY VOLUME: a 4-prim/2M-instance
  stage that slipped a 16,677x miss past the prim gate now takes the reduced
  path (~55,000x cheaper, measured on two machines).
- Non-saturating T4 phase timers (`synapse_composition_ms`,
  `synapse_stage_touch_ms`) — a 7 s event lands in a real bucket instead of
  vanishing at the old 4–5 s ceiling.
- One stage walk per op instead of two (`_stage_exceeds` per-op cache),
  independently confirmed by the perf ratchet's own counters.
- **The perf ratchet is ARMED**: counted-proxy floor, read at
  merge-base(origin/master) so a PR cannot gate against its own doctored floor,
  CI-runnable with zero pxr. Counts fall freely; rises need a human-promoted
  floor.
- **The scale bench** sweeps the axis: prims held at 4, the gate flips on
  volume alone between 500k and 1M authored elements. Offline tier emits
  COUNTS ONLY — enforced in code, not prose.
- Latency board: `harness/latency/` — 8 PASS / 0 FAIL / 0 PENDING.

## Suite hygiene
- The module-planting class (synthetic packages in `sys.modules` without
  parent-attribute binding) fixed at 26 files; `tests/pkgbootstrap.py` is the
  one sanctioned way to plant.
- Refuted and recorded so nobody re-litigates: extending declarative coverage
  (would ADD a round-trip), H1 topo-hash cost (cookCount never cooks), H2
  blast-radius cost (0.039 ms at N=500).

Suite at tag: 5540+ passed / 0 failed (main checkout). Producer paths for every
number: harness/latency/LEDGER.md + LOG.md.

---
RITUAL (human): edit VERSION -> 5.42.0, then:
  git commit -am "release: v5.42.0 — the receipts release" && SYNAPSE_GATE_C=1 git push origin master
  gh release create v5.42.0 --title "v5.42.0 — the receipts release" --notes-file .claude/release_v5420_notes.md
