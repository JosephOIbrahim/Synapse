# BP3-TIDY — House Cleaning Report

**Leg:** BP3-TIDY · branch `bp3/tidy` · 2026-09-03
**Dispatch order:** After BP3-CRUX (dependencies satisfied)
**Mission:** Read-only survey with pruning proposals for BP3 + BP2 worktrees; receipt order validation; UNKNOWN discipline audit; docs/ scratch census.

---

## T1: Worktree Census

**Survey scope:** All 22 worktrees from `git worktree list` as of 2026-09-03 16:59 UTC.
**Prune criterion:** merged into master AND clean (0 dirty files) AND (unusable OR older than BP2 merge) — MUST have all three.
**Finding:** NO prune candidates. Every unmerged worktree is intentional and active. BP2 and BP3 branches are not yet merged into master.

| Worktree Path | Branch | Merged | Usable | Dirty | Action | Reason |
|---|---|---|---|---|---|---|
| C:/Users/User/SYNAPSE | master | ✓ | ✓ | 43 files | KEEP | Main tree; working state normal |
| C:/Users/User/rope-beacon-wt | rope/beacon | ✗ | ✓ | 0 | KEEP | Unmerged; not a candidate |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-crux | bp2/crux | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-cruxb | bp2/cruxb | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-healthwire | bp2/healthwire | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-integration | bp2/integration | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-latency | bp2/latency | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-meter | bp2/meter | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-meterlive | bp2/meterlive | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-nits | bp2/nits | ✗ | ✓ | 0 | KEEP | BROKEN-carried (per brief); explicitly kept |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-paneldesign | bp2/paneldesign | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-paneltruth | bp2/paneltruth | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp2-store | bp2/store | ✗ | ✓ | 0 | KEEP | Unmerged BP2 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-corpus | bp3/corpus | ✗ | ✓ | 0 | KEEP | Unmerged BP3 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-crux | bp3/crux | ✗ | ✓ | 0 | KEEP | Unmerged BP3 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-panel | bp3/panel | ✗ | ✓ | 0 | KEEP | Unmerged BP3 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-probe | bp3/probe | ✗ | ✓ | 4 files | KEEP | Unmerged BP3 leg; dirty is acceptable (work in progress) |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-recon | bp3/recon | ✗ | ✓ | 0 | KEEP | Unmerged BP3 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-stubs | bp3/stubs | ✗ | ✓ | 0 | KEEP | Unmerged BP3 leg; active |
| C:/Users/User/SYNAPSE/.claude/worktrees/bp3-tidy | bp3/tidy | ✗ | ✓ | 0 | KEEP | Current mission worktree (self) |
| C:/Users/User/synapse-m1-handle-wt | mem/m1-handle-law | ✗ | ✓ | 0 | KEEP | Unmerged memory board leg; active |
| C:/Users/User/synapse-m2-pgdrm-wt | mem/m2-pgdrm | ✗ | ✓ | 2 files | KEEP | Unmerged memory board leg; active |

**Conclusion:** All worktrees pass the keep criterion. No `git worktree remove` or `git branch -d` commands are warranted.

---

## T2: Receipt Order Verification (BP3 Legs)

**Scope:** Six BP3 legs with receipts: BP3-CORPUS, BP3-CRUX, BP3-PANEL, BP3-PROBE, BP3-RECON, BP3-STUBS.
**Criteria (CRX0):** (a) Receipt's stated `product_head` sha exists on branch before receipt commit; (b) No `git add -A` footprint (only leg-related files in diff vs master).

| Leg | Receipt SHA | Product HEAD | SHA Found | Files Changed | Footprint Check | Result |
|---|---|---|---|---|---|---|
| BP3-CORPUS | d2529974 | ac2b9440 | ✓ | 5 (promotion docs, receipts, parms) | ✓ Clean | **PASS** |
| BP3-CRUX | 2d1d22c0 | ada0a7d7 | ✓ | 6 (mutations, verdicts, flag, receipts) | ✓ Clean | **PASS** |
| BP3-PANEL | 38449ec7 | 1276fed0 | ✓ | 3 (audit, qss.py, receipts) | ✓ Clean | **PASS** |
| BP3-PROBE | df15ec33 | d6c6d9b3 | ✓ | 8 (reviews, probes, receipts) | ✓ Clean | **PASS** |
| BP3-RECON | 1e5018d1 | 062669fe | ✓ | 2 (audit, receipts) | ✓ Clean | **PASS** |
| BP3-STUBS | bb669478 | cf61fba6 | ✓ | 4 (intake docs, stubs, receipts) | ✓ Clean | **PASS** |

**Conclusion:** All BP3 receipts meet CRX0 order criteria. Product heads verified in history; no unrelated files detected.

---

## T3: UNKNOWN Discipline Audit

**Scope:** BP3 review docs and receipts. Search for numeric zeros or 'pass' verdicts claimed on rows where probe status is BLOCKED or acceptance is gui_required.
**Rule (constitutional):** Unobtainable renders UNKNOWN, never zero or pass.

| Leg | Probe/Acceptance | Status | Verdict Claimed | Anchor | Check |
|---|---|---|---|---|---|
| BP3-PROBE | P-6 | BLOCKED | (not claimed—correctly recorded as BLOCKED) | stdout.txt:223-230 | ✓ **PASS** — no false pass on BLOCKED |
| BP3-PROBE | D2.1 (handedness) | — | UNKNOWN (gui_required) | stdout.txt:277 + review sec.5 | ✓ **PASS** — gui_required marked UNKNOWN, not pass |
| BP3-PROBE | G-1 (scatter source) | gui_required | UNKNOWN | stdout.txt:374-392 | ✓ **PASS** — gui_required marked UNKNOWN |
| BP3-CRUX | BP3-PROBE verdicts | — | "1 gui_required acceptance UNKNOWN" | receipt summary | ✓ **PASS** — correctly disclosed, not laundered |
| BP3-CORPUS | Promotion check | — | Pass/fail validation includes BLOCKED filter | bp3_promotion_check.py | ✓ **PASS** — rejects anchor lines inside BLOCKED blocks |
| BP3-PANEL | Before/after screenshots | gui_required | UNKNOWN (headless) | receipt | ✓ **PASS** — gui_required marked UNKNOWN |

**Conclusion:** Zero violations. All BLOCKED and gui_required acceptances correctly recorded as BLOCKED or UNKNOWN. No false passes on unobtainable measurements.

---

## T4: docs/ Scratch Census

**Scope:** Probe scratch files (cop_*, copnet_*, _apex_* families) at docs root.
**Summary:** 54 `.txt` files totaling 146 KB; dated 2026-07-21 (oldest) to 2026-08-17 (newest).

| Year-Month | File Count | Total Bytes | Oldest File | Newest File |
|---|---|---|---|---|
| 2026-07 | 5 | ~15 KB | cop_diag.txt (2026-07-21) | copnet_wiring_strategy.txt (2026-07-21) |
| 2026-08 | 49 | ~131 KB | cop_all.txt (2026-08-12) | _apex_full.txt (2026-08-17) |
| **TOTAL** | **54** | **~146 KB** | 2026-07-21 | 2026-08-17 |

**Proposed organization:** Create `docs/scratch/` with month-based subdirectories; move all scratch files out of docs root.

**Example git mv sequence (first five):**

```bash
# Create directories
mkdir -p docs/scratch/2026-07
mkdir -p docs/scratch/2026-08

# Move 2026-07 files
git mv docs/cop_diag.txt docs/scratch/2026-07/cop_diag.txt
git mv docs/cop_node_parms.txt docs/scratch/2026-07/cop_node_parms.txt
git mv docs/cop_node_parms_summary.txt docs/scratch/2026-07/cop_node_parms_summary.txt
git mv docs/copnet_map.txt docs/scratch/2026-07/copnet_map.txt
git mv docs/copnet_wiring_strategy.txt docs/scratch/2026-07/copnet_wiring_strategy.txt

# Move 2026-08 files (49 files — abbreviated, full list below)
git mv docs/cop_all.txt docs/scratch/2026-08/cop_all.txt
git mv docs/cop_candidates3_result.txt docs/scratch/2026-08/cop_candidates3_result.txt
# ... (47 more files)
```

**Complete file list for 2026-08 (49 files):**
- _apex_avail.txt, _apex_avail_final.txt, _apex_avail_ok.txt, _apex_collated.txt, _apex_final.txt
- _apex_full.txt, _apex_list.txt, _apex_ok.txt, _apex_probe.txt, _apex_probe_result.txt
- _apex_readback.txt, _apex_readback2.txt, _apex_result.txt, _apex_result2.txt, _apex_result_read.txt
- _readback_cop.txt, cop_all.txt, cop_candidates3_result.txt, cop_catname.txt, cop_catname_readback.txt
- cop_cats.txt, cop_cats2.txt, cop_create_read.txt, cop_found.txt, cop_probe.txt
- cop_types.txt, cop_types_list.txt, cop_types_read.txt, copnet_children.txt, copnet_diag.txt
- copnet_remaining.txt, copnet_types_actual.txt, copnet_types_avail.txt, copnet_types_avail2.txt, copnet_types_avail3.txt
- copnet_types_avail4.txt, copnet_types_clean.txt, copnet_types_final.txt, copnet_types_fresh.txt, copnet_types_list.txt
- copnet_types_now.txt, copnet_types_read.txt, copnet_types_readable.txt, copnet_types_report.txt, copnet_types_stage.txt
- copnet_types_stage_report.txt, copnet_types_v2.txt, copnet_types_v3.txt

**Conclusion:** All files are proposal-only. Joe or the CTO runs the git mv sequence when ready. These scratch files belong in `docs/scratch/` to keep docs root clean.

---

## Findings Summary

| Target | Status | Evidence |
|---|---|---|
| **T1** Worktree census | COMPLETE | 22 worktrees surveyed; 0 prune candidates |
| **T2** Receipt order (BP3) | COMPLETE | 6 legs verified; all pass CRX0 criteria |
| **T3** UNKNOWN discipline | COMPLETE | 6 acceptance rows audited; 0 violations |
| **T4** Scratch census | COMPLETE | 54 files, 146 KB, ready for `docs/scratch/` migration |
| **T5** This report | COMPLETE | All four tables published |

---

## Ruling

**Legal status:** Read-only survey complete. All proposals carry exact commands or evidence. No mutations applied to the working tree or master.

**For Joe/CTO:**
- **T1 (worktree):** No action needed; all worktrees are intentional.
- **T2 (receipts):** No action needed; BP3 receipt order is sound.
- **T3 (UNKNOWN):** No action needed; UNKNOWN discipline holds.
- **T4 (scratch):** Optional: Run the git mv sequence when ready to relocate probe scratch files to `docs/scratch/`.

---

**Report authored by:** BP3-TIDY (Claude Haiku 4.5)  
**Timestamp:** 2026-09-03 16:59 UTC  
**Branch:** `bp3/tidy`
