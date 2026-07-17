# Proof-Leg Grounding — Step-0 Pass

**Date:** 2026-07-17
**Baseline pins:** v5.28.0 = `72de5f1` · ABI 22.0.368 / py 3.13.10 / USD 0.26.5 / PySide 6.8.3 · suite floor 4275/0/87 (`harness/verify/suite_baseline.json`)
**Overall verdict: `CLEAN`**

This is a read-only grounding artifact. It assembles the Step-0 verdicts the orchestrator already produced; each row carries the file:line or command that produced it. No verdict was re-run in this pass. The gate rule: STOP only on a load-bearing MISMATCH. `RECORDED-DIFF` and `DEFERRED` are not stop conditions — every diff below is expected and explained.

---

## The 10-item grounding table

| # | item | blueprint pin | live-found | verdict | evidence |
|---|------|---------------|------------|---------|----------|
| 1 | HEAD / tag baseline | v5.28.0 = `72de5f1` (release baseline) | HEAD = `c108147`, advanced by exactly 4 docs/state-only commits above baseline (`c108147` blueprint v1.0+SPEC · `6934584` debt rulings · `6340507` HDK grounding · `2de573f` latency report) — all `docs/` or `docs+state`, zero source/harness-logic touched | RECORDED-DIFF | `git rev-parse HEAD`=`c10814772b85`; `git tag --points-at 72de5f1`=`v5.28.0`; `git log --oneline -10` |
| 2 | flywheel_queue ratified-flag audit | `harness/state/flywheel_queue.json` L223,233,404,467,478,489,500,511,523,534 + §8-pool falses L203–434 | Copernicus trio ratified:true (C.3 L223 · C.4 L233 · C.10 L404); M1b ratified:false (L511, expected open); entire §8 candidate pool ratified:false; 2 new probes ratified:true (L523, L534); RETINA M2–M5 ladder all ratified:true (L467/478/489/500) | RECORDED-DIFF | Read `harness/state/flywheel_queue.json` at cited lines |
| 3 | CI suite `python -m pytest tests/ -q` | floor 4275/0/87 | 4436 passed / 0 failed / 97 skipped in 102.13s; +161 over floor, 0 failures — healthy advance; floor NOT promoted (human-promoted only); PR-branch-CI guard `test_d_track.py::test_tops_path_untouched_green_at_head` did NOT fail | RECORDED-DIFF | summary line `4436 passed, 97 skipped, 553 warnings in 102.13s`; floor `harness/verify/suite_baseline.json` |
| 4 | drop.json ABI fields + tracked status | 22.0.368 / py 3.13.10 / USD 0.26.5 / PySide 6.8.3; report tracked (do NOT commit) | all four ABI fields match EXACTLY (dropped_at 2026-07-15T18:09:17Z); `?? harness/state/drop.json` still UNTRACKED, not staged, not committed (Joe's call) | VERIFIED-MATCH | Read `harness/state/drop.json` (4 version fields verbatim); `git status --short` → `?? harness/state/drop.json` |
| 5 | PORT_WAVE_MANIFEST OD-ruling + merged-wave set | `docs/PORT_WAVE_MANIFEST.md` L15–19 | OD-1/2/3 RULED 2026-07-16 (VERIFIED-MATCH, corroborated `a6d3d62`); all 7 prompt-named waves confirmed merged on master; W.1-H22-planes (`3cae9bd`) ALSO merged — actual merged set is a superset by one wave | RECORDED-DIFF | `docs/PORT_WAVE_MANIFEST.md` L15–19; git `3cae9bd,b5570f8,34f41f7,dab186d,f1cdb69,789c94c,9b36b4d,be27313,a6d3d62` |
| 6 | bridge / live | live sub-checks gated on G2 / Mile-2 (blueprint ruling #7) | `ws://localhost:9999/synapse` rejected HTTP 400 → bridge DOWN; `/obj` debris (`_recon_planes2` / `_w4assay_net`), panel G2 boot, `hconfig -xa` DEFERRED to Mile-2 Joe-at-GUI session | DEFERRED (not a mismatch) | orchestrator `synapse_ping` (live) |
| 7 | RETINA M1b tail (`0039026`) | expected OPEN (deposited, ratified:false, one-line T0 fix not built) | OPEN as expected — subject confirmed (`RETINA.M1 merged … + M1b sibling-honesty follow-up`, stat: flywheel_queue.json only +13/-2); entry `RETINA.M1b-t0-sibling-honesty` status=candidate, ratified=false; sev-2 one-line fix (`if not existing: res_pass = None` + fp equiv in `retina/t0.py`) deposited-not-built | VERIFIED-MATCH | `git show --stat 0039026`; `git show 0039026 -- harness/state/flywheel_queue.json`; live L504-513 |
| 8 | Copernicus neural models (SAM2 / MoGe-2) | SAM2 (`neural_*sam2`) / MoGe-2 (`neural_*moge2`) ONNX ABSENT; only `neural_cellularautomatacore` present | absence CONFIRMED — `$SHFS/houdini/nodes/cop/` resolves to a single child `neural_cellularautomatacore/`; no `neural_*sam2`, no `neural_*moge2`, no ONNX payload; H22.0.368 present under the SideFX dir | VERIFIED-MATCH | `ls -la '/c/Program Files/Side Effects Software/shfs/houdini/nodes/cop/'` (PROGRA~1 shortname identical) |
| 9 | *(pin not supplied to this dispatch)* | — | — | `[UNVERIFIED — no verdict for item 9 was passed to this scribing dispatch; would be verified by the orchestrator supplying its Step-0 result]` | n/a |
| 10 | Start-line ruling audit (§4 rulings 1-12) | all 12 start-line rulings resolved-or-carried | RULED: 1-6, 12 · UNRULED: 7,8,9,10,11 · memory_section_owed = TRUE · stop_worthy = FALSE | RECORDED-DIFF | see §"Start-line ruling audit" below |

**Item 9 note:** the orchestrator's brief enumerates ten grounding items (1-9 as pins, item 10 the ruling audit, item 6 the bridge line), but supplied pin verdicts for items 1,2,3,4,5,7,8 only. Item 9 has no backing verdict in this dispatch and is left `[UNVERIFIED]` rather than invented. It is not a MISMATCH — it is a missing input, and the OVERALL gate keys on mismatches, of which there are none.

---

## Start-line ruling audit (§4 rulings 1-12)

| # | ruling | RULED / UNRULED | disposition | evidence |
|---|--------|-----------------|-------------|----------|
| 1 | OD-A — port-manifest absorbs 3 new tools (115→118) | RULED | (a) — the 3 new tools join a cops-3 addendum wave; count 115→118 is test-forced, ships per-tool | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:14` (`RULED 2026-07-17 (Joe, harness-architect debt pass)`) |
| 2 | OD-B — native reaction-diffusion pair rides C.4 | RULED | (a) — RD rides C.4 as D4.5 (title expands 4→5 tools) | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:14` |
| 3 | OD-C — C.10 verb name | RULED | `cops_terrain_setup` — provisional name stands, no rename | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:14` |
| 4 | OD-D — C.4 subsumes W.4b(3)? | RULED | subsume — C.4 absorbs W.4b(3)'s dead `limit` cleanup (W.4b items 1-2 untouched) | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:14` |
| 5 | CHOP scope | RULED | (A) documented non-goal — CHOP (channels/motion) is a NON-GOAL; 11 byproduct catalog rows are not partial coverage; no queue entry | `harness/state/flywheel_queue.json:524` (M.DOP-recon note, sibling ruling, on master); corroborated branch postmortem `docs/reviews/h22-per-context-postmortem-2026-07-17.md:38` (branch-only, NOT merged) |
| 6 | DOP / MPM scope | RULED | (A) non-goal for NEW sim capability + one hard-bounded scoped recon (4 already-emitted SOP solvers + MPM wiring, one smoke cook each) then hard freeze; future C.0 excludes DOP | `harness/state/flywheel_queue.json:515-524` (M.DOP-recon-2026-07-17, ratified:true, master); corroborated branch postmortem `:40` |
| 7 | SCOUTMASTER `/obj/_recon_planes2` (+`_w4assay_net`) — debris or active? | UNRULED | no committed disposition; gated on a live/GUI session (SCENE_BUSY blocked all three expansion probe legs); Mile 2's literal first step | `docs/SYNAPSE_COPERNICUS_EXPANSION.md:88`; `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:81` (start-line ruling #7) |
| 8 | Panel touch-target sizing (after G2 real pixels) | UNRULED | no committed disposition; taste call requiring the human, gated "after G2 real pixels" — G2 not yet run | `docs/reviews/h22-cto-roadmap-2026-07-16.md:114` (N-14, P3); `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:154` |
| 9 | Public-surface policy (G9 drift) | UNRULED | no committed disposition; stale v5.5.0-era public README (incl. forbidden `setx ANTHROPIC_API_KEY`); refresh-cadence-vs-deliberate-freeze is Joe's ruling | `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:136`, `:155` |
| 10 | `hou._imagePlanes` private-API posture | UNRULED | no committed disposition; private `_imagePlanes` QUARANTINED from production emission as a holding default "pending SCOUTMASTER ruling" — quarantine is the safe hold, not the ruling | `docs/reviews/h22-cop-audit-verification.md:218`; `docs/reviews/h22-cto-roadmap-2026-07-16.md:169`; `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:156` |
| 11 | Commission the owed Memory/substrate analyst section | UNRULED | no committed disposition; the 2026-07-17 debt pass ratified only M.DOP-recon + M.OPENPBR-probe — no memory-commission queue entry; section body still "owed until the full section lands" | `harness/state/flywheel_queue.json:515` & `:527`; branch postmortem `:452-475`; `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:128` (§G8) |
| 12 | RETINA M2 ratification | RULED (with tension) | FLIP realized — `RETINA.M2` ratified:true — but flipped in the 2026-07-16 blanket "Administer this blueprint" batch, BEFORE M1b closed; `RETINA.M1b-t0-sibling-honesty` still ratified:false, out of the blueprint's carried "flip after M1b closes" order | `harness/state/flywheel_queue.json:467` (M2 ratified:true) vs `:511` (M1b ratified:false); `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md:158` |

**Dispatch-eligible now (gate ruled):** OD-A (r1), OD-B (r2), OD-C (r3), OD-D (r4), CHOP non-goal (r5), DOP/MPM scoped-recon-then-freeze (r6), RETINA M2 (r12).
**Blocked (unruled):** SCOUTMASTER `/obj` debris (r7), panel touch-target sizing (r8), public-surface / mirror policy (r9), `hou._imagePlanes` posture (r10), Memory/substrate section commission (r11).

---

## Recorded diffs (benign, not stop conditions)

- **Newer HEAD.** `c108147` sits +4 commits above the `v5.28.0` baseline `72de5f1`. All four (`c108147`, `6934584`, `6340507`, `2de573f`) are `docs/`- or `docs+state`-prefixed; zero source or harness-logic touched. Baseline integrity intact. — *item 1*
- **Two new ratified probes.** `M.DOP-recon-2026-07-17` (L523) and `M.OPENPBR-probe-2026-07-17` (L534) both read ratified:true — ratified by Joe this session, exactly as expected. — *item 2*
- **RETINA M2/M1b ordering nuance.** The entire RETINA M2–M5 ladder (L467/478/489/500) reads ratified:true from the 2026-07-16 batch ratification, while `RETINA.M1b-t0-sibling-honesty` (L511) remains ratified:false. This is out of the blueprint-#12 "flip after M1b closes" order but is committed, explained, and not stop-worthy — M2 was flipped before the M1b tail was deposited. — *items 2, 10 / ruling 12*
- **Copernicus neural models absent.** Only `neural_cellularautomatacore` is present under `$SHFS/houdini/nodes/cop/`; SAM2 and MoGe-2 ONNX payloads are absent — matches the Copernicus Leg B expectation, verified from the filesystem without a live Houdini env. — *item 8*
- **Merged-wave superset.** Every prompt-named port wave IS genuinely merged on master; `W.1-H22-planes` (`3cae9bd`) is also merged though absent from the prompt's enumeration. No claimed-merged wave is actually unmerged, so this is a one-short enumeration, not a load-bearing mismatch. — *item 5*
- **CI count advance.** 4436 passed vs floor 4275 (+161); skipped 87→97; 0 failed. Floor NOT promoted (human-promoted only). — *item 3*
- **drop.json still untracked.** ABI fields VERIFIED-MATCH; the file remains `?? harness/state/drop.json`, not staged, not committed — deliberately Joe's call. — *item 4*
- **Memory/substrate §4 section owed.** `memory_section_owed = TRUE`; the analyst section body is explicitly truncated/owed ("owed until the full section lands"), with no commission queue entry yet. — *ruling 11*

---

## Verdict

**`CLEAN`.** No ruling record that must exist is contradicted; the only divergences are RECORDED-DIFF (newer docs-only HEAD, healthy suite advance, expected new probes, M2/M1b ordering tension, absent neural models, one-short merged enumeration) and DEFERRED (live bridge down, gated to Mile-2 GUI). `stop_worthy = FALSE`.

Grounding clean; Mile-1 deposit (C-U5, C-MTLX ratified:false) authorized; FORGE awaits human ratify.

*Item 9's pin was not supplied to this dispatch and is carried `[UNVERIFIED]`; it is a missing input, not a mismatch, and does not gate the CLEAN verdict.*
