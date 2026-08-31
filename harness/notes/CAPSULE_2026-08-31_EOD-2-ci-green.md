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
