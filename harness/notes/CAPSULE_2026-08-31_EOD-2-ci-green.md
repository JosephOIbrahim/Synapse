# CAPSULE 2026-08-31 EOD-2 — CI green, seven loops closed, release staged & seat-blocked

Grounded against live repo ~22:55. Boot from this. Supersedes
CAPSULE_2026-08-31_EOD-gate0-closed.md where they differ (that capsule's
checklist is mostly discharged now — see below). Do not assert anything not
in this file.

## One-line state
master = origin = **26cbb8c8**, CI **GREEN** (confirmed by watched run
33447977484, exit 0, all six OS/Python jobs). Seven loops closed tonight with
receipts. Release v5.57.0 staged correct at adfe59e0, blocked only on the
operator seat. Demo round-trip still the one unmeasured link — Tuesday, camera.

## LATE ADDENDUM (~23:30) — v5.58.0 DRAFT staged, version bumped
Decision reversed from earlier option-A-only: Joe's word to give tonight its
OWN release. Done, DRAFT only:
- **Version bumped 5.57.0 → 5.58.0**, six surfaces CONFORM
  (`python scripts/sync_version.py --check` = PASS). Commit **fb99d46f**.
- **GitHub draft v5.58.0** created ("the night the loops closed honest"),
  target master, `isDraft:true`, **NO TAG CUT** (URL shows `untagged-`).
  Notes: harness/notes/RELEASE_v5.58.0.md — the BP1-wave + hardening span.
- **v5.57.0 draft UNTOUCHED** — still the store-owner work, its own release.
- **fb99d46f is one commit ahead of origin** — NOT pushed (per-act word).
  First action tomorrow if you want origin current before the seat walk.
- Publish v5.58.0 = `gh release edit v5.58.0 --draft=false` — AFTER the seat
  gates below, per-act word. Tag cuts at publish.

Net: TWO drafts now staged (v5.57.0 store work · v5.58.0 tonight), both
publish-blocked on the same operator seat. Pick which tags first at the rig.

## ADDENDUM 3 (~23:20) — ritual walked, R.R RED, publish NOT fired
- **Seat gates: ALL PASS by Joe's word** ("all pass"): g1 · g5 (build receipt
  PASS 22.0.400 ×3 surfaces) · g6 · Ctrl+Z (W5-UNDO-GUI receipt discharged) ·
  g9 (no segfault this walk).
- **drop.json WRITTEN** (harness/state/, untracked, BOM-free): values captured
  LIVE from .400 hython — 22.0.400 / py 3.13.10 / usd 0.26.5 / pyside 6.8.3.
  Joe author, Claude instrument, 2026-08-31T23:12:36Z.
- **R.R verify: FAIL** (harness/notes/h22/rr2.log). Ritual STOPPED per card —
  no partial release. Banked publish word VOIDED by red verdict. Two reds:
  1. `suite_baseline` — **1 NEW failure**, ratchet BROKEN (6832p/1f vs base 0).
     Test NOT yet named. Gate python is 3.14.2 w/ vendor tree INACTIVE (cp314
     no wheels) — ABI split is a candidate cause, not a finding yet.
     FIRST ACTION TOMORROW: `python -m pytest --lf -x -q` to name it.
  2. `release_readiness_review` — verdict RC. Blockers: mutation_fail_closed,
     hot_reload_gated, installer_host_targeted, ci_covers_shipping_surface
     (all four STANDING since v5.51 draft; v5.56.0 published over them) +
     `g3:pending-drop` (STALE — drop.json IS written; the check reads drop
     state from elsewhere or needs registration; investigate).
- **v5.58.0 remains DRAFT.** Publish path tomorrow: name+fix the 1 test →
  re-run _rr.ps1 → green → `gh release edit v5.58.0 --draft=false` (Joe word).
- **PANEL FLOAT — diagnosed, not fixed.** houdini/scripts/python/synapse_shelf.py
  :126-137 open_panel(): paneTabOfType(PythonPanel) → if None →
  createFloatingPaneTab. Every Ctrl+K without a docked tab spawns a float.
  Also hijacks ANY PythonPanel. Workaround (Joe, 30s): dock a Python Panel tab
  set to Synapse in main desktop + Save Current Desktop As (no .desk exists).
  Code fix (~15 lines, shipping, needs GUI verify): prefer tab whose
  activeInterface().name()=='synapse_panel' → else
  paneTabOfType(NetworkEditor).pane().createTab(PythonPanel) → float only if
  no panes. Demo-relevant (on-camera surface).

## One-line state (as of first EOD-2 write)

## What closed tonight (all pushed, all CI-green)
1. **Build call** — .400 owns demo week (CTO call, your word). assert_build_400
   v2 reads PASS on three surfaces; 8.3 short-path false-FAIL corrected (same
   class as BP1 G4). Probe: harness/notes/h22/assert_build_400.py.
2. **Ratified ×3** (your words, 86ec6b64): memory-recall-honesty ·
   harness-budget-rails · demo-round-trip. First two evidence-backed on origin
   and now binding. Third ratifies the **Tue 18:00 branch predicate ONLY** —
   its features stay passing:false, unmeasured until footage. Header says so.
3. **Worktree prune** — all 5 BP1 worktrees + 4 leg branches gone,
   merge-verified ancestors-of-master first. Remaining worktrees are deliberate:
   master, rope/beacon, mem/m1-handle-law, mem/m2-pgdrm.
4. **Probe-predicate fix** (2d3d916e) — G4 claim_id now read from
   payload.content JSON via _claim_id_of(); both call sites routed through it;
   AST-verified. This de-risks Tue: Gate 0 GUI half will read true, not
   false-fail on the same shape that fooled it this morning.
5. **Launch-path env bucket CLOSED** (eaa9cf76) — your `setx
   HOUDINI_PACKAGE_DIR=<repo>\packages` proved LIVE: fresh hython G1-G4 all
   pass, known_recalled=true, dropped all-zero, **bucket=none**. Receipt:
   silent_recall_hython.json. NOTE: fixes the 22.0.417 agent lane, **off the
   demo path** (demo is .400 GUI, loads from OneDrive, already passes).
6. **CI red→green** (26cbb8c8) — the S8 JSON gate
   (test_lint_all_harness_json_parses, R26) correctly caught four JSONL probe
   receipts wearing .json. Did NOT weaken the gate (it has a negative-control
   test forbidding that) — wrapped each receipt as single-object JSON
   {format,record_count,records[]}, every record preserved, paths/filenames
   unchanged so capsule + BP1_G4_FALSE_FAIL.md references stay intact. Watched
   to success.
7. **Release scope call** — v5.57.0 stays "the store stops having two owners,"
   target stays adfe59e0, draft NOT moved. One release per coherent scope; BP1
   + tonight ride a future tag. No-op on the release = the correct action.

## Your checklist — next chat opens here
- [ ] **Section B operator gates (your seat, ~25 min, the release gate):**
      g1 clean install (launch explicitly from ...\Houdini 22.0.400\bin) ·
      g5 lifecycle · g6 core smoke · g9 rollback. Mid-g5, paste:
      `exec(open(r'C:\Users\User\SYNAPSE\harness\notes\h22\assert_build_400.py').read())`
      — expect verdict PASS; that JSON is the seated build receipt.
      g9 last walk surfaced a real SideFX-side uninstall segfault (QIcon paint,
      zero SYNAPSE frames) — if it recurs, stop and receipt it; the gate works.
- [ ] **Ctrl+Z demo** — Tuesday (W5-UNDO-GUI + release marquee, counts twice).
- [ ] **drop.json** — your dictation, Claude types as instrument, or hand-edit.
- [ ] **verify** — R.R must read full green before tag.
- [ ] **Publish v5.57.0** — `gh release edit v5.57.0 --draft=false` (tag cuts at
      adfe59e0). Only after Section B + verify. Per-act word.
- [ ] **Demo round-trip (RED, Tue, camera):** deposit → close scene → reopen →
      recall SUCCESS payload.hit=true, ×2 both HIT. This is the Tue 18:00 branch
      predicate: two HITs → Sep 6 stands; no HIT → Sep 13.
- [ ] **Push** — one commit ahead after this capsule + backlog write.

## Standing open (unchanged unless above)
- mem/m2-pgdrm not merged · UNFINISHED_WORK_REVIEW_2026-08-20.md unreviewed
- LAUNCH_PATH_FIX option 1 done for env; the *durable* choice (repo as package
  source of truth) is now in effect — GUI/headless no longer split.
- dashboard_bp1.py stays modified+uncommitted on master (predates tonight).
- BASTION B1/B2/B3 = W2 · WA2 rungs = October · REACH+FLOW post-demo.

## Hardening backlog (see HARDENING_BACKLOG addendum in harness/notes/h22/)
Six BP1 nits · unguarded Backup-Branches push · scripted wave-teardown verb ·
stale RELEASE-DRAFT-vNEXT.md (v5.51-era text) · CRLF→LF on every commit tonight
(wants a .gitattributes normalize).

## Constitutional gates (always held)
merge words · push · tag/publish · drop.json · ratification — all per-act Joe
words. CTO standing authority for execution acts. One writer per surface.
No amends on master. Verdicts READ before merge words. Unmeasured renders
UNKNOWN, never zero. Never script an operator-seat gate to green.
