# CAPSULE 2026-09-03 EOD - wave BP3 shipped as v5.61.0

Boot from this file. Master = 26af4c68 (release commit) + this capsule. Tag v5.61.0 at ad589fe5, published 21:27Z, Latest. Everything below is on master and on origin.

## What happened today, in order
1. Blueprint v0.3 (docs/intake/blueprint-h22-worldlabs-intent.md), probes (harness/probes/synapse_blueprint_probes.py), manifest schema (docs/intake/world_manifest.schema.json) landed. Three intents on independent layers; demo only references.
2. Wave BP3 authored in the battleplan schema (harness/battleplan/missions/BP3-*.json, prompts, build_manifest_bp3.py, arm_bp3.ps1). Dry-run preflight kept as ledger orch_20260903-142231. Armed on Joe's word 14:29.
3. Seven legs done by 17:08: RECON, PANEL, PROBE, STUBS, CORPUS (Opus 4.8), CRUX (Fable 5, five parallel audit lanes), TIDY (Haiku). BP3-SPATIAL held. Verdicts: RECON/PROBE/PANEL SOUND-WITH-NITS, CORPUS/STUBS SOUND, 0 BROKEN, 10 mutations.
4. Joe read BP3-CRUX_verdicts.md (surfaced in chat) and said `merge 1-7`. Seven --no-ff merges 22437d4e..5edbd5ee. Pushed 485aa425 on Joe's word.
5. Release ritual per the 09-01 capsule: VERSION 5.61.0, six surfaces CONFORM, RELEASE_v5.61.0.md, checks.py --task R.R --mode B (same eight red as 09-01, no regression), gh release --draft, Joe: waiver + publish, triple check green. Release commit 26af4c68.
6. README: dated "Right now" block, "Wave BP3, one picture" section + intent-layer mermaid, knowledge diagram gained the intake branch. Repo description updated; topics swapped python/ai-assistant -> gaussian-splatting/multi-agent.

## Truths now on master (anchors in docs/reviews/bp3-h22-worldlabs-probes-2026-09-03.md)
- 22 probes on hython 22.0.400 in 6.5 s; 21 RAN, P-6 BLOCKED (OpNode has no .stage); crucible re-run identical.
- SOP-side USD Create Component exists on 22.0.400; component built through it (sop_component).
- Gaussian-splat tooling native on the build (R-4 clear).
- World Labs collider 46,993 tris - WL-EX-03 refuted by fixture. App exports carry no scale/ground metadata - BLU-04 true. husk --pass confirmed. B-6 usdc 19.8 MB.
- D2.4 black EXR is a PROBE BUG (camera created after render settings, never assigned; husk: Total Lights 0, camera-name mismatch). R-1 = UNKNOWN. Not a Karma verdict.
- Panel audit: tokens 8.5/10, adoption 3.5/10 (492 px, 168 hex, 34 modules). 5 subs in qss.py, stylesheet byte-identical at 5 scales, tests 123p/25s.
- Corpus: 138-row scatterinstances parm seed (22.0.400); 8 promotions PROPOSED, ratified:false, checker bp3_promotion_check.py bites.
- Stubs: 3 tool signatures (impl none), lane diff unapplied (contract path says schemas/, must read docs/intake/ before apply), example manifest validates.
- Env: five hythons installed; 22.0.429 passes the hytest usability gate -> pin SYNAPSE_HYTHON=22.0.400 (demonstrated, not inferred). H22 prefs = OneDrive redirect. Deep-path fresh clone loses _vendor/anthropic without core.longpaths.

## Open - next session (fresh, reasoning tier), in order
1. Rule the 22 banked items cold (RECON 3, PANEL 1, PROBE 5, CORPUS 7, STUBS 2, CRUX 1, TIDY 3). CTO recommendations already in receipts / in the 17:00 chat: M-1 schema stays docs/intake; M-2 pin hython 22.0.400 now; D-DEP-03 hou; PANEL narrow scope accepted, spawns held; TIDY-R1 T1 merged status = UNKNOWN. Record in harness/notes/CTO_RULINGS_*.md per house pattern.
2. Fix B-7 in synapse_blueprint_probes.py: assign the camera prim to the render settings (and add a light) BEFORE rop.render; re-run B-7 only; then and only then decide R-1 / D2.4.
3. Flip BP3-SPATIAL: HELD dict in build_manifest_bp3.py -> ready; compile_wave bp3 -> make_control bp3 -> build_manifest_bp3; re-arm on Joe's word (Mile 2: three read-only spatial tools, unregistered, timed < 5 s).
4. Optional: drop dossier + coffee notes into docs/intake/ (RECON dossier_in_repo=false; CORPUS worked from blueprint pointers).
5. Seven held spawns (PANEL 4: BP3-INLINE-HEX, BP3-STYLES-MIGRATE, +2; CRUX 3: qss hex-authority pin, timer-interval pin, +1) - post-demo.

## Hardening wave (new wave, not now)
- orchestrate.ps1 died once at 15:04:35 in the Drift-Check path (leg just settled + leg just launched); no stderr. Instrument Drift-Check / Get-LastProgress.
- Backup-Branches pushes leg branches with no human word (named item, observed again).
- readonly-settings.json: deny Bash(git add:*)/Bash(git commit:*) beats the scoped allow; git -C is the leak; Haiku legs stop at the fence. Fix: drop the two blanket denies, keep push/merge/checkout/reset denied, add Bash(git branch --merged:*) to allow.
- Mission-authoring rule: never instruct a leg to write anything AFTER its receipt (W5H held CRUX at closing).
- R.R phantom check still keyed to the 21.0.671 symbol table; vendored wheels inactive on Python 3.14 (both warnings, both known since 09-01).
- Windows long-path clone hazard for audit lanes: git config core.longpaths true.

## Housekeeping done 17:35
- Orchestrator (pid 63884, idle watch) stopped. R.R verify finished on its own 17:27. No leg windows. %TEMP%\orch_BP3-*.ps1 removed. All CTO helper scripts removed after use.
- 22 worktrees KEPT (unusable-only prune standard; TIDY census has merged status UNKNOWN - re-census with git branch allowed before any prune).
- Left untracked on purpose: harness/notes/h22/orchestrator-bp3.{pid,err}, rr_v5610.err (logs are ignored). Dry-run ledger orch_20260903-142231 left open as preflight receipt.
- Not mine, untouched: the pre-existing dirty REACH/flow-conductor files on master.
- Bus: my malformed BP3-CRUX release line 17:03:01 (to: posted) stays; append-only.

## Held queue unchanged from 2026-09-01
BP2-NITS2 (fresh session), METER-DEDUPE / METERLIVE-SOFTCLOSE spawns, UNKNOWN back-settle.

## Metered (real, from rails ledgers)
Opus legs: ~102.8M in / ~1.5M out / ~115 min. CRUX + TIDY in ledger_orch_20260903-151611.json. Session cost on the chat side was dominated by moving 63 KB of blueprint/probes across the DC bridge - next time, drop from the Studio panel.
