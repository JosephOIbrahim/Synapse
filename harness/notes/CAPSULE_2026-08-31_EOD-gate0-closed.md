# CAPSULE 2026-08-31 EOD — Gate 0 closed, release staged, wave awaiting verdicts

Grounded against live repo ~17:50. Boot from this. Do not assert anything not
in this file. Supersedes CAPSULE_2026-08-31_BP1-battle-plan.md where they differ.

## Where we are

- master 2767564c = origin/master at push time. This capsule's own commit sits
  on top (ahead 1, rides the next push — no push word banked).
- Wave BP1 live. Flag NOT landed at last check (~17:45). Orchestrator pid 25656
  alive. CRUX RUNNING ~5h; interim receipt: 8/8 self-authored mutations vs
  HONESTY ports.py applied cleanly + all reddened, 0 escapes, baseline green
  before and after (BP1-CRUX_mutations.json in crux worktree).
- Legs TRIAGE / RAILS / HONESTY: receipts green (2x green_with_findings),
  each ahead 2 on its branch. Nothing merged. Nothing ratified.
- Four powershell hosts are wave machinery, children of 25656:
  15212 = CRUX (LIVE — never kill), 55036/67816/50664 = closed-leg shells.
  Deliberately left alive; wave sweeps itself at close.

## What this session proved (all receipted)

1. GUI half of Gate 0, measured on the MAIN THREAD via
   hdefereval.executeDeferred: G1 env / G2 plugin / G3 layer all pass.
   G4 printed fail — then the rawdump autopsy proved it a PROBE-SIDE FALSE
   NEGATIVE: gate4 checks payload.claim_id; the real contract carries claim_id
   inside payload.content (a JSON string). The deposit round-tripped
   perfectly: deposit SUCCESS -> cortex_root.usda authored -> raw fetch
   returned it -> filter passed it -> query returned it. Recall is HEALTHY
   in the GUI. bucket=recall is superseded.
   Evidence on master AND origin (commit 2767564c):
   harness/battleplan/runs/2026-08-31/silent_recall_gui.json (immutable
   receipt, superseded in interpretation), silent_recall_gui.shell-vantage.json
   (pre-deferred run), rawdump_store_swjv252n/ (preserved store incl. the USD
   text with the claim in it), notes/BP1_G4_FALSE_FAIL.md (correction of
   record + corrected _claim_id_of predicate), notes/probe_recall_rawdump.py.

2. Thread law confirmed: the Houdini Python Shell executes OFF-main
   (Dummy-6); MemoryPort's main-thread guard refused correctly. The deferred
   route is THE route for GUI probes. Guard exonerated.

3. Build split (new finding): GUI = 22.0.400, hython = 22.0.417. Two
   installs on the machine. Docs say .400; the GUI aligns with docs.
   Pick one build to own the week.

4. hython half unchanged: bucket=env, launch-path defect, fix is
   LAUNCH_PATH_FIX.md (Joe hands). Off the demo path.

5. v5.57.0 GitHub release exists as a DRAFT (target adfe59e0, notes from
   RELEASE-DRAFT-vNEXT.md). NOT published, NO tag cut. Reason, from the
   release commit's own text + OPERATORS-CARD-release-ritual.md: section B
   gates outstanding — g1 clean install, g5 lifecycle, g6 smoke, g9 rollback,
   Ctrl+Z demo (= W5-UNDO-GUI, already Tuesday), drop.json (Joe-only).
   Joe's call on record: ride Tuesday. Publish = one word + one command.

6. DC housecleaning: zero DC sessions open; nothing killed.

## Joe's checklist — next chat opens here

- [ ] Flag: Test-Path harness/notes/h22/BP1_CRUX_LANDED.flag, or
      python harness\battleplan\dashboard_bp1.py --once
- [ ] Read CRUX verdicts per leg: SOUND merge-ready / SOUND-WITH-NITS merge
      with noted items / BROKEN that leg does not ride.
- [ ] Merge words, per-act: bp1/triage · bp1/rails · bp1/honesty · bp1/crux.
- [ ] Section B gates, your hands: g1 · g5 · g6 · g9 · Ctrl+Z (Tue session)
      · drop.json (you dictate, Claude types, or hand-edit).
- [ ] Publish v5.57.0: gh release edit v5.57.0 --draft=false
      (tag cuts at adfe59e0 on publish). Only after section B.
- [ ] Push (per-act word) — carries this capsule + any merge commits.
- [ ] Ratify three contracts, one word each: memory-recall-honesty ·
      harness-budget-rails · demo-round-trip.
- [ ] LAUNCH_PATH_FIX.md — execute one option (agent-lane env).
- [ ] Probe predicate fix post-merge: corrected _claim_id_of lives in
      BP1_G4_FALSE_FAIL.md. One small commit on whatever surface you name.
- [ ] Build call: own .400 or .417 for demo week.
- [ ] Tue 18:00 branch decision. Demo beat is UNBLOCKED; the ONLY unmeasured
      link is cross-session recall (close -> reopen -> remember) = the
      demo-round-trip contract, red tier, GUI, your hands on camera.

## Standing open items (unchanged unless listed above)

- mem/m2-pgdrm not merged · UNFINISHED_WORK_REVIEW_2026-08-20.md unreviewed
- REACH + FLOW post-demo · BASTION B1/B2/B3 = W2 · WA2 rungs = October
- Three modified files on master predate this session, untouched:
  dashboard_bp1.py, m2fix_suite_branch.txt, rope/STATE.json

## Constitutional gates (always held)

merge words · push · tag/publish · drop.json writes · contract ratification —
all per-act Joe words. CTO standing authority for execution acts. One writer
per surface. No amends on master. CRUX before merge. Verdicts READ before
merge words fire. Unmeasured renders UNKNOWN.
