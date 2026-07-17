# SPEC — SYNAPSE Proof Leg (harness-architect execution contract)

| | |
|---|---|
| **Governing doc** | `docs/SYNAPSE_H22_PROOF_LEG_BLUEPRINT.md` v1.0 — commit it **with this SPEC, before any dispatch** (F3). |
| **Frozen sub-specs of record** | `docs/SYNAPSE_COPERNICUS_EXPANSION.md` (C.4/C.3/C.10) · `docs/SYNAPSE_RETINA_BLUEPRINT.md` + `docs/reviews/retina-reconciliation-2026-07-16.md` (M1b/M2/M3) · `docs/PORT_WAVE_MANIFEST.md` (waves). This SPEC **points**; it never re-specifies them. |
| **Baseline pins (verify, don't trust)** | v5.28.0 · HEAD `72de5f1` · H22.0.368 (py 3.13.10 / USD 0.26.5 / PySide 6.8.3) · floor 4275/0/87 |
| **Mode / posture** | MODE B · solo · per-cycle human merge |
| **Date** | 2026-07-17 |

**Mission (one line):** discharge the blueprint's Miles 1–5 — kill the two silent-wrong twins, run the live session, ship C.4→C.3→C.10 and RETINA M1b→M2→M3 — landing the Dark_Glass scoped-delta demo with every claim probe-backed and every merge human.

---

## Step 0 — GROUNDING PASS (mandatory, read-only, before ANY dispatch)

The blueprint was authored off-repo. First act: re-derive every load-bearing pin against the live tree and runtime. Output: `docs/reviews/proof-leg-grounding-<date>.md`. **Any mismatch = STOP, report, await ruling.** Checklist:

1. `git rev-parse HEAD` / `git tag` — confirm `72de5f1` = `v5.28.0` (or record the newer truth and diff it against the blueprint's §1).
2. `harness/state/flywheel_queue.json` — confirm `C.4-H22-scaffold-rebuild` / `C.3-H22-neural-cops` / `C.10-H22-terrain-exposure` `ratified:true`; RETINA `M1b`/`M2` entries and their flags; every pool item `ratified:false`.
3. `harness/verify/suite_baseline.json` + one full `python -m pytest tests/` (stock python, the CI command) — record the live count vs floor 4275/0/87. Floor advances are **human-promoted only**; record, never promote.
4. `harness/state/drop.json` — fields + **tracked status** (was untracked at the ABI verdict; commit is the human's call — report, don't commit).
5. `docs/PORT_WAVE_MANIFEST.md` — OD-1/2/3 ruling block state; merged-wave set vs the postmortem's recorded list (`scene-1/W.3/W.5/W.7+W.8/W.1b/W.4/U.1`).
6. Bridge state (`ws://localhost:9999/synapse` reachable?) · `/obj` children (debris `_recon_planes2` / `_w4assay_net` present?) · panel install (`hconfig -xa`).
7. RETINA M1b tail commit `0039026` — open or closed.
8. `$SHFS/houdini/nodes/cop/` — SAM2/MoGe-2 model presence (arms or skips the C.3 models-present tests).
9. Memory/substrate analyst section — delivered yet? (Blueprint start-line #11.)
10. Blueprint start-line rulings 1–12 — which are ruled? **Dispatch nothing whose gate is unruled.**

---

## Dispatch table

> **Ladder PL** (proof-leg) — miles **1–6**. Cite cross-doc as **`PL-M<n>`**; the rulebook's ladder is **RBK** (miles 0–5), a different plan. Convention: CLAUDE.md → "Mile / ladder citation".

> Roles: **gatewarden** admits · **ARCHITECT** designs (paper only — mostly discharged already) · **FORGE** builds in an isolated worktree · **ASSAYER** live-verifies every emitted symbol on the running build · **CRUCIBLE** attacks what it didn't build (never weakens; Commandment 7 + thresholds) · **SCRIBE** persists artifacts with file:line anchors · **human merges**. Cycle IDs below are proposals; the queue's own IDs win.

| Mile | Cycle | Scope (spec of record) | Gate to dispatch | Merge-ready when |
|---|---|---|---|---|
| 1 | **C-U5** (`U.5-H22-context-fold`) | Blueprint §G1a: `lop_knowledge.py` major-aware resolver (mirror `wiring.py:_pkg_catalog_path`) + hython context re-probe → `lop_solaris_knowledge_22.json` (roles/USD types/key parms/ordering/`known_absent`; renamed instancers in; stale per-shape lights out) + fail-loud on missing per-major file | ratify | resolver test-pinned like `wiring.py`'s · catalog hash-stamped · `graph_validator` phase-5 exercised against the new catalog · suite ≥ floor · live lift queued for S-LIVE |
| 1 | **C-MTLX** (`MTLX-volume-fix`) | Blueprint §G1b: probe `mtlxvolume`/`mtlxvolumematerial` on 22.0.368 → swap `render_recipes.py:701` → repoint/drop `MTLX_STANDARD_VOLUME` (`mtlx_types.py:25,33`) | ratify | substitute probe-verified before emission · conformance fixture updated · suite ≥ floor · note in commit: standalone-before-usd-2, goldens later capture fixed truth |
| 2 | **S-LIVE** (session, not a code cycle) | Blueprint §G2 checklist 1–7 verbatim; artifacts → `harness/notes/` (probes, hash-stamped catalog regen) + `docs/reviews/h22-live-session-2026-XX-XX.md` (verdict flips, lifts, panel G2, SOP parm artifact) | start-line ruling #7 · **Joe at GUI** · bridge up | every checklist item has an artifact or an explicit DEFERRED line · zero scene residue (`/obj`,`/stage` clean, hip untouched) · provisional→VERIFIED-LIVE flips tabulated |
| 3 | **C.4 → C.3 → C.10** | `SYNAPSE_COPERNICUS_EXPANSION.md` **verbatim** — its DoD tables, honesty contracts, tests, and sequencing rules are the contract | OD-A/B/C/D ruled · W.4-merge precondition already SATISFIED (re-confirm at grounding) · P-1/P-2 discharged for the deliverables that need them | per the spec's own cycle gates · human merge per cycle · Joe-side parallel: Download Models (GUI, elevation likely) |
| 4 | **RETINA-M1b** then **RETINA-M2** | RETINA §9 + reconciliation: M1b tail (`0039026`) → M2 worker venv (`opencv-python-headless==5.0.0.93` abi3; 4.13 fallback) + OIIO/OCIO ingest (protected `OCIO` env) + T1 kit + verdict events; consume the committed perception catalog — uncataloged symbols stay INFERENCE, never coded against | M1b: ratified follow-up · M2: start-line #12 flip | M1b closed first · zero-cv2 pin stays green (host-side) · crucible hostile pass (flood/malform/cancel per RETINA §8) · suite ≥ floor |
| 5 | **RETINA-M3** | RETINA §5/§9: scoped-delta end-to-end on Dark_Glass; PROOF line in the receipt; consent-gate verdict | **Joe at GUI** | the demo sentence is literally demonstrable · receipt carries DECISION·VIA·PROOF · human merge |
| 6 | **WAVES + M4/M5 + CTO-05 + W-6** | Manifest order scene-2→…→memory-2 under blueprint §G5 coupling · RETINA M4 (paired w/ expansion) · M5 counters (= G6's number) · CTO-05 class fix · W-6 corpus reseed (blueprint §G7 contents) | per-wave/per-cycle ratify+merge · memory waves additionally gated on start-line #11 (owed analyst section) | each per its spec · **leg DoD does not owe Mile 6's tail** (see Definition of Done) |

**Parallelism:** Mile 1 ∥ Mile 2 (different surfaces). C.4 FORGE unit work may start pre-S-LIVE (honest-deferred envelopes are designed for it) but **no merge-ready claim** for C-cycle deliverables that P-1/P-2 gate until S-LIVE lands them. Mile 4 does not block on Mile 3.

---

## Non-negotiables (the guardrails; violations = STOP)

1. **Three standing human gates:** merge-to-main (per cycle, per wave) · `drop.json`-class mode triggers · architecture rulings (sidecar remains the ruled durable path, first post-release cycle — untouched by this SPEC). No agent merges, ratifies, promotes the floor, or edits the blueprint.
2. **`ratified:false` is the resting state.** Deposits go to the queue; humans flip.
3. **Phantom discipline, extended:** every `hou.*`/`pdg.*`/`pxr.*` symbol against the committed H22 table; every **node-type string and parm name** against a probe quote or the connectivity catalog — enforced by per-cycle conformance fixtures (the expansion's DoD-1 pattern). If a live-verified symbol is missing from the table, **re-introspect the table, never allowlist**.
4. **Commandment 7 + thresholds:** no test weakened, no threshold loosened to green a verdict; fix-forward only. CRUCIBLE never edits implementation; FORGE never edits hostile tests.
5. **Fake-residency trap:** unit fakes patch **handler-module globals**, never `sys.modules` plants; any fake `hou` under hython must provide `isUIAvailable()`.
6. **No golden performs a real render** (manifest hard rule) · **ports never change behavior** · numeric receipts get tolerance-based hython fixtures, never mock-`hou` equality goldens.
7. **Panel rules:** hython-offscreen only for boots (never stock python); full-suite is the gate, never a panel subset; the 3-source accent is pinned — no naive unification; changes route through `panel-design-warden`.
8. **Probe politeness:** SCENE_BUSY respected; scratch nodes destroyed in `finally`; hip never saved; read-only bash for verification.
9. **Auth guardrail:** `SYNAPSE_ANTHROPIC_KEY` only; `ANTHROPIC_API_KEY` is never set or documented; `OCIO` and `WS_PORT` preserved in any env work.
10. **Intake discipline:** external docs → one adjudication page max (§10); inline pastes without a tracked artifact path → adjudication-only. No blueprint self-revision; escalate to the human.
11. **Disclosure:** repo-committed paper stays at the RETINA blueprint's public-safe altitude — no mechanism claims, no thresholds-as-shipped, no filing specifics. CIP-queued material is referenced by name only.
12. **Truth contract:** VERIFIED/CORRECTED/INFERENCE labels with file:line anchors on every load-bearing claim; results never claim what wasn't observed; runtime > repo > paper.

---

## Artifact contract

- Probes/catalogs → `harness/notes/` (dated, hash-stamped where catalog-shaped; both files byte-coherent when packaged).
- Reviews/session records/grounding → `docs/reviews/` (h22-* naming continues).
- Deposits → `harness/state/flywheel_queue.json` (`ratified:false`).
- Every dispatch report ends with the compressed summary block (SCOUTMASTER-consumable) — no output is trusted without one.
- Commits: atomic, race-safe push (fetch+rebase, max 3, halt on conflict); worktree isolation for FORGE.

## Escalation & stop conditions

STOP and surface to Joe on: grounding-pass mismatch · any unruled gate reached · a probe refuting a frozen-spec assumption (amend the spec via its own rule, never silently) · suite below floor · CRUCIBLE sev-≥2 · any temptation to touch a non-goal · anything smelling like the fake-memo class (adjudicate, don't execute).

## Leg Definition of Done

1. Miles 1–5 human-merged: twins dead (context twin major-aware + live-lifted; mtlx phantom gone), S-LIVE artifacts landed with provisional stamps lifted, C.4→C.3→C.10 merged per their spec, RETINA M1b+M2 merged, **M3 demo demonstrated and merged** (the receipt carries PROOF).
2. From Mile 6, only the items that *gated* 1 are owed (e.g. nothing); the wave/M4/M5/CTO-05/W-6 tail is **sequenced in the queue with correct coupling notes**, not completed.
3. Suite ≥ floor at every merge; zero unratified behavior changes; start-line rulings either ruled or explicitly parked by Joe.
4. A closing SCRIBE report maps blueprint §3 → outcome per gap, honest about anything DEFERRED — the coverage-honesty pattern, applied to the leg itself.

---

*This SPEC is paper. It mutates nothing. harness-architect executes it top-down: grounding pass → start-line audit → Mile 1. Where this SPEC and the live runtime, the repo, or a frozen sub-spec disagree — the runtime, then the repo, then the sub-spec win, in that order.*
