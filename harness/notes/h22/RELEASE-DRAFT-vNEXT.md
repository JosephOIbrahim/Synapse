# RELEASE DRAFT - vNEXT (v5.51.0 proposed - number is Joe's call at ritual)
# Status: DRAFT. Tag + GitHub Release happen ONLY via the release ritual (g-receipts + drop.json are Joe's).
# Updated 2026-08-16: post-W5L merge train (5 legs), R1 flip, shelf icon. Ritual HALTED at g5; resumes on this build.

## Headline
Close the tab, keep the session. Undo everything. A panel that stops lying about spend.

## For artists
- **Closing the SYNAPSE panel no longer kills the runtime** - heartbeat moved off the panel into
  the runtime (P0.3 fixed, W5-LIFE). Close the tab mid-operation: work finishes, session and chat
  history are there when you reopen. (g5 re-run on this build confirms live.)
- **Ctrl+Z reverses everything SYNAPSE builds** - named undo groups wrap creation, deletion,
  wiring, parms, keyframes.
- **Font scale respects the host** - floor equals Houdini's UI font; the Aa cycle and "Larger text"
  can never shrink below it (R1 wired live today, 4c1134d8).
- **Token tab tells the truth** - spend traces to real API usage receipts; unmetered engines read
  UNKNOWN, never a fake 0. Chat leading +0.75pt, proven effective not inert.
- **Shelf grown up** - six distinct committed icons + one-sentence tooltips per tool; panel-open
  tool has its icon (2dd6bab6). Visual render = live-seat check at relaunch.
- Type-name retrieval P@1 1.0 (603/603) on a corpus stamped fresh at 22.0.400.

## For the harness
- **First fully-clean wave**: 4/4 legs' receipts are their own closing commits, zero operator
  rescues (W5-LCRUX mandate table). Commit-before-receipt is now lived, not just codified.
- Substrate fold in flight: per-build **Schema Catalog** (386 Cop types, APEX registries) and
  **gated_set() parm API** legs DONE; **Cook-Verify measures** running; all three merge only on
  the W5-WCRUX verdict - not in this tag unless merged before ritual resume.
- suite_baseline ratchet holds through the 5-leg train (6508/0); hosted CI green on push.

## Honest state (ships declared, not hidden)
- 4 machine gates still RED: mutation_fail_closed, hot_reload_gated, installer_host_targeted,
  ci_covers_shipping_surface. Shipping red-declared per v5.50.0 precedent.
- G3 pending-drop: h22 symbol table not regenerated since Aug 9 (drop.json is Joe-only).
- provenance guardrail warn-only/unwired (standing hardening debt).
- gui_required UNKNOWNs close only at Joe's live seat: g5 re-run, icon render, font floor feel.

## Ritual checklist (resume point: g5 on THIS build)
g5 lifecycle re-run (Joe's hands) . g6-g9 . W5-UNDO-GUI live Ctrl+Z receipt (doubles as marquee
demo) . drop.json (Joe-only write) . version bump across six surfaces . R.R Mode A . tag .
GitHub Release.


---

## Addendum - 2026-08-16 late session (merged to master, CI green)

**Panel parity proven.** An adversarial crucible independently re-executed both parity probes under real hython 22.0.400: all 90 panel modules load byte-identical from the repo, zero shadow installs, all seven icons + shelf resolve in-repo, and the pypanel exec/flush path genuinely re-imports fresh (import-masking ruled out). The live GUI seat was observed running 22.0.400 during the probe window.

**Hardening wave (W6).** The failure-class ledger (`harness/HARDENING-SPEC.md`) mined every receipt and ruling into eight seeded classes plus newly-mined ones; four builders then moved the worst classes from prose to enforced gates, each proven RED-able on its original defect by the crucible:
- Injection class killed: `Sanitize-SQ` + adversarial-name parser matrix (41 tests; 17 fresh payloads, zero reached a code position)
- Provenance now **fail-closed** in task verdicts (was warn-only by construction since June)
- Heartbeat gate reads **behavior**, not a source grep - panel death, beat survives
- Orchestrator `done` now requires receipt == branch HEAD **and** a bus RELEASE (the CRX0 class, structurally closed)
- Composed tree: 6572 passed / 0 failed, ratchet +67, zero regressions

One operator close-pass per R135 (recorded openly in the W6-HCRX verdict): the GATE leg's own receipt commit + two missing RELEASE lines - the wave's thesis caught live on its own authors.

**User-flow wave (W6f).** Six evidence-anchored journeys mapped (zero invented personas under audit), a hython journey rig measuring every step, and two pinned panel fixes proven green-to-red under revert simulation. Three adversarial journeys survived first-hand, including panel-close mid-journey - the P0.3 fix under attack.

**Honest-state correction to the list above:** `provenance_not_bypassed` is no longer unwired - it is WIRED and fail-closed as of this addendum. Cook-verify substrate (W5-MEASURES/WCRUX) still in flight; will ride the next update.
