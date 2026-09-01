# CAPSULE 2026-09-01 — BOOT: v5.58.0 PUBLISHED. Demo week mile 2/8.

Grounded ~00:05 2026-09-01 against live repo + GitHub. Boot from THIS file.
Supersedes CAPSULE_2026-08-31_EOD-2-ci-green.md and all four of its addendums
(kept for provenance; do not boot from them). Do not assert anything not here.

## One-line state
**v5.58.0 is Latest** ("the night the loops closed honest"), published
2026-08-31T23:47Z, tag → **8c01a066**, CI green on that head, R.R suite
6833/0, g3 green (first time ever), published under **Joe's recorded waiver**
over four standing RC blockers (named below, on the release body). Local
master **f75c94cd** = 1 docs commit ahead of origin (waiver line in notes) —
rides a push word. v5.57.0 still a Draft. Today = **Tue, demo-week mile 2/8**.

## The 2026-08-31 session, compressed (all on origin unless noted)
- BP1 wave: 4 legs merged SOUND-WITH-NITS, 84/84 sweep, torn down, pruned.
- Build call: **22.0.400 owns demo week.** assert_build_400 v2 (8.3 short-path
  false-FAIL corrected). Five builds share one prefs dir; probe is enforcement.
- Ratified ×3 (Joe words): memory-recall-honesty · harness-budget-rails ·
  demo-round-trip (**predicate only** — features stay passing:false).
- Probe predicate fix: G4 claim_id read from payload.content (BP1_G4 autopsy).
- Launch-path env bucket CLOSED: `setx HOUDINI_PACKAGE_DIR=<repo>\packages`;
  hython G1–G4 pass, bucket=none. (22.0.417 agent lane, off demo path.)
- CI red→green ×2: S8 JSON gate caught (a) four JSONL receipts as .json →
  wrapped as records[] envelope, gate kept strict; (b) BOM in VERSION from my
  `Set-Content -Encoding utf8` during the bump → rewritten via python io.
- Version 5.57.0 → 5.58.0, six surfaces CONFORM (scripts/sync_version.py).
- **Seat gates ALL PASS by Joe's hands:** g1 · g5 (build receipt PASS ×3
  surfaces) · g6 · Ctrl+Z (W5-UNDO-GUI receipt DISCHARGED) · g9 (no segfault).
- drop.json written (Joe author, Claude instrument), live .400 values.
- R.R findings: `_rr.ps1` runs **Mode A** where g3 is pending-drop BY
  CONSTRUCTION; Mode B reads the drop. checks.py:2367 read key `houdini` while
  the human drop schema uses `houdini_build` → g3 had NEVER been green. Fixed
  (accept either). Mode B now: blockers = the four standing only.
- v5.58.0 published over those four with waiver recorded in Joe's name.
- Panel float DIAGNOSED, not fixed (below).

## Joe's checklist — next chat opens here
- [ ] **push** — f75c94cd (docs, waiver line). One word.
- [ ] **DEMO ROUND-TRIP (RED, camera) — THE Tuesday beat, last unmeasured link.**
      .400 GUI, your hands: deposit → close scene → reopen → recall SUCCESS
      payload.hit=true, ×2 both HIT. Contract: .synapse/contracts/
      demo-round-trip.yaml (ratified as predicate; no agent flips features).
      **Tue 18:00 branch:** two HITs → demo-ready Sun Sep 6 stands; no HIT →
      Sep 13, week rolls to beta-W1. Every take is footage — stamp it.
      NOTE: roadmap (Aug 30) put on-camera recall on Wed; the contract (Aug 31,
      ratified) sets the Tue 18:00 predicate. Contract is newer → governs.
- [ ] **Panel float fix** — demo-relevant, it's on camera.
      houdini/scripts/python/synapse_shelf.py:126–137 open_panel():
      paneTabOfType(PythonPanel) → None → createFloatingPaneTab. Every Ctrl+K
      without a docked tab spawns a float; also hijacks ANY PythonPanel.
      Fix (~15 lines, shipping, GUI-verify): prefer tab whose
      activeInterface().name()=='synapse_panel' → else
      paneTabOfType(NetworkEditor).pane().createTab(PythonPanel) → float only
      if no panes. Workaround now (30s): dock a Python Panel tab set to Synapse
      in main desktop + Windows→Desktop→Save Current Desktop As (no .desk
      file exists at all today, so nothing persists until you save one).
- [ ] **Loop part 1** (roadmap Tue mile): ports wired, full turn closes clean.
      Gate 0 already proved in-session deposit+recall in the GUI; today's
      round-trip is the cross-session half. Check docs/BATTLEPLAN.md §4/§5 for
      the exact V0.0 slice — state beyond that is UNKNOWN to this capsule.
- [ ] **v5.57.0 draft** — decide: publish (store scope, tag at adfe59e0, older
      than v5.58.0's head — legal, just non-Latest) or delete/fold. Your call.
- [ ] `_rr.ps1` → pass `--mode B` for release verifies (one-line hygiene).
- [ ] Wed prep: OpenMontage footage bank from today's takes.

## Four standing RC blockers — now HEAD of hardening backlog
mutation_fail_closed · hot_reload_gated · installer_host_targeted ·
ci_covers_shipping_surface. Red since v5.51 draft; v5.56.0 and v5.58.0 both
published over them under recorded waivers. Precedent is not permission —
every further release re-signs or fixes. See harness/notes/h22/HARDENING_BACKLOG.md
(also: six BP1 nits · Backup-Branches push · teardown verb · stale
RELEASE-DRAFT-vNEXT.md · .gitattributes CRLF · JSONL-receipt recurrence).

## Standing open (unchanged)
mem/m2-pgdrm not merged · UNFINISHED_WORK_REVIEW_2026-08-20.md unreviewed ·
dashboard_bp1.py + m2fix_suite_branch.txt modified, uncommitted on master ·
BASTION B1/B2/B3 = W2 · WA2 rungs = Oct · REACH+FLOW post-demo · APEX H22
blueprint phases 1–7 parked post-demo.

## Findings ledger — what the reds actually were
| Red | Kind | Truth |
|---|---|---|
| G4 recall (morning) | instrument | claim_id lives in payload.content |
| assert_build_400 v1 | instrument | HFS came back 8.3 short path |
| g3 pending-drop | instrument | Mode A never reads drop; key `houdini` vs `houdini_build` |
| S8 JSONL as .json | **real** | receipts mis-extensioned; gate correct |
| S8 BOM in VERSION | **real, mine** | Set-Content utf8 on PS5.1; gate correct |
Rule reaffirmed: autopsy the gauge before believing the engine — but the
gauge was right twice, and both times it was my write.

## Driver hygiene (mine, don't repeat)
- Never `Set-Content -Encoding utf8` for repo files → BOM. Use python io.
- Never inline `gh run watch` → DC 4-min ceiling. Detach + poll ≤200s windows.
- Watch CI on every code-touching push before declaring anything green.
- R.R for release = `--mode B`.

## Constitutional gates (always held)
merge words · push · tag/publish · drop.json · ratification · waivers — per-act
Joe words, spelled out, never inferred from a tired typo. CTO standing
authority for execution acts. One writer per surface. No amends on master.
Verdicts READ before words fire. Unmeasured renders UNKNOWN, never zero. Never
script an operator-seat gate to green. Relayed approval is not consent.
