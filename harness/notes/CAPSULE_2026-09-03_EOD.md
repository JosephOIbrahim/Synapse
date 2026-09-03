# CAPSULE 2026-09-03 EOD - wave BP3 (H22 Solaris + World Labs blueprint execution)

Boot from this file. Master is at c6c4fb86 + this capsule commit. Nothing merged, nothing pushed to master, nothing ratified.

## Position
- Wave BP3 BOARD COMPLETE 17:08:42. 7 legs done with receipts on their branches, BP3-SPATIAL held.
- Orchestrator pid in harness/notes/h22/orchestrator-bp3.pid is in idle watch (rails run orch_20260903-151611, cap 7, 3 used). Close its window or leave it; it dispatches nothing until a manifest row changes.
- Two rails ledgers for this wave: orch_20260903-142939 (run 1, 5 turns, died 15:04:35) and orch_20260903-151611 (run 2, relaunched with cap continuity). Metered so far: ~102.8M tokens in, ~1.5M out across 6 Opus legs; CRUX (Fable 5) and TIDY (Haiku) settle in run 2's ledger.
- Branches (all pushed by the orchestrator's Backup-Branches, NOT by a human word): bp3/recon 1e5018d1, bp3/panel 38449ec7, bp3/probe df15ec33, bp3/stubs bb669478, bp3/corpus d2529974, bp3/crux b4d8b7b0, bp3/tidy e3475d30.

## Verdicts (BP3-CRUX, harness/battleplan/notes/BP3-CRUX_verdicts.md on bp3/crux)
- RECON SOUND-WITH-NITS, PROBE SOUND-WITH-NITS, PANEL SOUND-WITH-NITS, CORPUS SOUND, STUBS SOUND. 0 BROKEN. 10 mutations (BP3-CRUX_mutations.json). 3 spawns held by CRUX.
- CRUX did NOT audit TIDY (runs after). CTO audited TIDY: T1 "Merged" column is ? (git branch not on the read-only allow list); the report's "not yet merged" sentence is UNKNOWN promoted to claim and is contradicted (9 bp2/* branches ARE merged). Recorded in BP3-TIDY.json cto_findings. No prune proposals stand.

## Truths landed (read the review docs before ruling)
- docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md (bp3/probe): 22 probes in 6.5 s on 22.0.400; P-6 BLOCKED; component built via SOP-side USD Create Component (exists on 22.0.400); native gsplat tools present (R-4 clear); collider 46,993 tris (WL-EX-03 REFUTED); app exports carry no scale/ground metadata (BLU-04 TRUE); B-6 usdc 19.8 MB; husk --pass confirmed.
- D2.4 FAIL is CONFOUNDED: B-7 EXR black with 6 "no render camera" errors = probe wiring defect (camera LOP created after render settings, never assigned). R-1 must read UNKNOWN, not triggered. Fix the probe, re-run B-7 before any claim about Karma XPU and splats.
- docs/reviews/bp3-h22-promotion-proposal.md (bp3/corpus): 8 promotions proposed (7 VERIFIED-RUNTIME + WL-EX-02 FIXTURE-VERIFIED), ratified:false, checker bp3_promotion_check.py exit 0 and reddens all 3 mutations. harness/notes/scatterinstances_parms_22.0.400.json: 138 rows (167-vs-138 counting caveat noted).
- docs/intake/h22-tool-candidates-2026-09-03.md (bp3/stubs): 3 stubs + 2 recipe proposals, impl none. BP3_lane_spatial.diff applies clean, UNAPPLIED; lane contract path in the diff says schemas/ and must read docs/intake/ before apply (STUBS ruling).
- harness/battleplan/notes/BP3_PANEL_AUDIT.md (bp3/panel): tokens 8.5/10, adoption 3.5/10 (492 literal px, 168 off-palette hex across 34 modules). 5 subs in designsystem/qss.py, stylesheet byte-identical at 5 scales, tests 123p/25s before and after. Spawns BP3-INLINE-HEX, BP3-STYLES-MIGRATE (+2) held.

## Rulings banked (22) - human + CTO words, none given yet
- RECON 3: M-1 schema home (CTO: docs/intake stays until a second schema exists); M-2 pin SYNAPSE_HYTHON=22.0.400 (CTO: yes, now; a 22.0.429 is on the box); D-DEP-03 hou for spatial tools (CTO: match existing).
- PANEL 1: narrow scope reading accepted, spawns stay held past demo (CTO: accept).
- PROBE 5, CORPUS 7, STUBS 2, CRUX 1, TIDY 3 (TIDY-R1..R3 written by CTO, see receipt). Read each receipt's for_ruling; PROBE's must be re-read against the D2.4 confounding above.

## Next session (fresh, reasoning-tier) - in order
1. Read verdicts + the five for_ruling lists cold. Rule the 22. Record rulings in harness/notes/CTO_RULINGS_*.md per house pattern.
2. Merge words, one per leg, dependency order: recon, stubs, probe, corpus, panel, crux, tidy. Squash or merge per house rule; no amends on master.
3. Fix B-7 (assign camera to render settings) and re-run B-7 only, before promoting any R-1 / D2.4 claim.
4. Flip BP3-SPATIAL held->ready in build_manifest_bp3.py HELD dict, recompile (compile_wave bp3 -> make_control bp3 -> build_manifest_bp3), re-arm on Joe's word.
5. Push master on Joe's word (Gate C pattern).
6. Hardening items from this wave (new wave, not now): orchestrator died once in Drift-Check path after a leg settled + another launched (15:04:35, no stderr); Backup-Branches pushes leg branches without a word; readonly-settings.json deny list beats its own scoped allow (git -C is the leak; Haiku legs stop); mission-authoring rule: never tell a leg to write anything AFTER its receipt (W5H).
7. Optional: drop the dossier + coffee notes into docs/intake/ (CORPUS worked from blueprint pointers; RECON dossier_in_repo=false).

## Held queue unchanged from 2026-09-01
BP2-NITS2 (fresh session), METER-DEDUPE / METERLIVE-SOFTCLOSE spawns, UNKNOWN back-settle. Untouched by BP3.

## Not done / not mine
- Dirty REACH/flow-conductor work on master (pre-existing, uncommitted) - left exactly as found.
- My malformed bus line for BP3-CRUX release at 17:03:01 (to: posted, raw msg) - append-only, left in place.
- Dry-run ledger orch_20260903-142231 left open (2 turns, no dispatch) - preflight receipt.
