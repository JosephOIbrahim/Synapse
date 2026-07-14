# H22 Phase-0 Reconciliation — `SYNAPSE_H22_DROP_HARNESS v1.0` vs. disk

**`docs/H22_PHASE0_RECONCILIATION.md`** · Repo: `C:\Users\User\SYNAPSE` · Branch `feat/h22-phase0-reconcile` · Authored 2026-07-14 against HEAD `68b1cba` (v5.23.0) / H21.0.671.

**Status: reconciliation record (MODE A paper).** Every load-bearing claim carries a `VERIFIED` (checked file:line this dispatch), `CORRECTED` (blueprint claim proven wrong), or `INFERENCE` (labelled judgment) tag per the blueprint's own truth contract (G-4). No H22 symbol is asserted; no gate is flipped.

---

## Why this document exists

The dispatched blueprint `SYNAPSE_H22_DROP_HARNESS v1.0` was authored **above the current disk reality.** Leg 0 already shipped ~90% of what its Phase 0 re-specifies — as complete, crucible-survived MODE-A **paper** (`docs/PREFLIGHT_GATE.md`, `docs/BENCHMARK_DESIGN.md`, `docs/PORT_WAVE_MANIFEST.md`, `docs/SCENE_GROUNDING_CONTRACT.md`) plus scaffolding (`harness/state/leg0_baselines.json`, `harness/state/wheel_cache/`, the `.claude/workflows/h22-*.js` orchestrators). In two places the blueprint **contradicts the tested gate**; in two more it re-opens a decision that is **already ruled**. Executing it literally would break the mode gate and manufacture make-work.

This record reconciles the blueprint to disk, so the build that follows touches only genuine gaps and leaves the three human gates (Gate 0.1, `drop.json`, merge-to-main) intact.

**Two operator rulings frame this run** (2026-07-14):
1. **Scope:** reconcile, then build only the real gaps.
2. **Mode gate:** keep the tested existence-gate; add a read-only Python guard — do not create a competing repo-root gate.

---

## The reconciliation table

| Task | Blueprint asks | On disk | Verdict | Action this run |
|---|---|---|---|---|
| **P0.1** | commit a `mode:"A"` `drop.json` at **repo root**; surface Gate 0.1 `DECISION-DUE` | gate is **existence-triggered** at `harness/state/drop.json` (`run.ts:62-63`); `.example` tracked, real file never committed; Gate 0.1 **already ruled Sidecar** (`gate-0.1-…md:83-91`) | **CONFLICT + STALE** | build a read-only `assert_mode_b()` Python guard on the *real* path; **no** repo-root file; **no** DECISION-DUE (nothing is due) |
| **P0.2** | new `SYNAPSE_U1_H22_RESWEEP.md` | flow already binding (drop-week step 4/10, `spec-U1`); probes are **emitter-seeded** so net-new families are invisible | **GENUINE-THIN-GAP** | author a thin re-sweep spec covering **only** the discovery-breadth delta |
| **P0.3** | add H22 nouns to `check_no_rigging_drift` + per-noun tests | that fn is an **allowlist** checker (`checks.py:324`); **no candidate-scan exists anywhere** | **GENUINE-GAP, mis-named target** | **extend** `check_no_rigging_drift` with a phrase-scan over `emitted_node_types.json` + tests |
| **P0.4** | `theme_source.py` adapter; route reads through it | `UIDark.hcs` read directly in `panel/designsystem/tokens.py`; no adapter | **GENUINE-GAP** | build the adapter (hcs live, qml stubbed), route tokens.py, snapshot + import tests |
| **P0.5** | scaffold a G6 benchmark harness now | `BENCHMARK_DESIGN.md` complete; meter **"does not execute until … a human merges it"** (:5); contract is **"extend, never rebuild"** the two existing scripts | **DESIGNED + GATED** | **do NOT build** — building now jumps its own merge-gate and violates extend-don't-rebuild |
| **P0.6** | Mile-5 perception baseline capture | source `TopsEventBridge.to_dict()` exists (`tops_bridge.py:131,209`); **no writer/envelope/empty-baseline** | **PARTIAL, genuine build** | build the timestamped baseline writer + fixed envelope + empty-baseline-headless + roundtrip test |
| **P0.7** | append IP evidentiary entry to the chain | **no evidentiary chain exists in-repo** (patents kept external) | **GAP + PLACEMENT** | **flag, do not self-author** — drafted entry below for operator placement + counsel |

---

## The two conflicts, resolved

### C-1 · The `drop.json` mode gate (P0.1)

`VERIFIED` (`run.ts:62-63`): `MODE` is `"B"` iff `harness/state/drop.json` **exists** — no `mode` field, at `harness/state/`, and `drop.json.example:9` states *"Never commit a real drop.json."* The blueprint's *"commit a `mode:"A"` template at repo root"* (§2, P0.1) would either land at the wrong path or, if placed at `harness/state/`, **flip run.ts to MODE B and arm the entire post-drop queue before H22 ships** — the exact inverse of its intent.

**Resolution (operator ruling 2):** keep run.ts's mechanism untouched; never write `harness/state/drop.json` (that is human gate #2). Add a read-only `assert_mode_b()` Python guard that (a) reads the **same** `harness/state/drop.json` existence, (b) validates the **real** schema numbers (`houdini_build`, `python`, `usd`, `pyside` per `drop.json.example`), and (c) raises under MODE A — for any Python task that runs outside run.ts. This is a non-conflicting adjunct, not a second gate.

### C-2 · The scope fence (P0.3)

`CORRECTED`: the blueprint names `check_no_rigging_drift` as a candidate-noun scanner. It is not. `VERIFIED` (`checks.py:324-344`): it reads `python/synapse/server/authoring_domains.json` and rejects **declared domains** whose set intersects `{apex,rig,rigging,kinefx,muscle,cfx}` (line 336, exact-token). `VERIFIED` (cartographer sweep): **no function anywhere** takes a candidate node-family string and admits/rejects it against scope nouns — `flywheel_review_wiring.classify_site`, `extract_emitted_node_types.scan_createnode_literals`, `rewire_assess.py`, `tool_filter.classify_tool` all lack a scope-noun axis.

**Resolution:** the genuine gap is to **add** a candidate-noun scan, housed as an **extension of** `check_no_rigging_drift` (its name is byte-frozen in `GUARDRAILS_FROZEN`, `test_r_track.py:30` + 3 siblings — a new check breaks four freezes). The extension scans `python/synapse/cognitive/tools/data/emitted_node_types.json` (`entries[].type_name` — the actual door an H22 node-type enters by, per blueprint G8) for multi-word rigging **phrases**, kept in a list **separate** from the single-token allowlist.

**Collision law (binding on the build):** match **phrases** with word boundaries, never bare tokens. `rig` poisons `rigid`/`bridge`/`trigger`; `splat` is **in-scope geometry** (blueprint G8) and must never be blanket-banned; `capture`/`deform`/`template`/`builder`/`script`/`transfer`/`sculpt` are all generic. Dead phrases only: `Rig Builder`, `Rig Template`, `biped retargeting`, `Mixamo retarget`, `APEX Script`, `ML Deformer`, `Muscle Transfer`, `ragdoll`, `splat rig`, `splat capture`, `Guide Deform`, `Short Sculpt`. A splat-**geometry** candidate must pass (positive test required).

---

## The two moot items

### M-1 · Gate 0.1 is already decided

`VERIFIED` (`gate-0.1-sidecar-vs-abi3.md:83-91`): **"DECISION — 2026-07-10 (human sanction): Sidecar"** — built in the first post-release cycle; drop-day contingency is re-vendor from the pre-cached `cp312/cp313` wheels at `harness/state/wheel_cache/`. P0.1's *"surface a DECISION-DUE, do not select"* is stale; writing a DECISION-DUE marker now would be **false** (G-4). The gate is ruled, not pending.

### M-2 · The G6 benchmark is designed and correctly gated

`VERIFIED` (`BENCHMARK_DESIGN.md:5,7,145`): the meter *"does not execute until this document survives adversarial review and a human merges it,"* execution is *"human-driven (Mile-5-adjacent),"* and the contract is *"extend `_benchmark_api.py`/`_benchmark_latency.py`, never rebuild."* P0.5's *"scaffold a new benchmark harness now"* would jump the merge-gate **and** rebuild what it must extend. Not built this run.

---

## Unverifiable dependency

`INFERENCE`: the blueprint's entire R1–R9 traceability cites `SYNAPSE_H22_ADJUDICATION_A1.md`, which **is not in the repo** (no `docs/intake/`, no matching file). The tasks are self-describing enough to execute by intent, but the R-number crosswalk cannot be verified against a source. Treated as advisory, not load-bearing.

---

## P0.7 — IP evidentiary entry: flagged, not self-authored

`VERIFIED`: no evidentiary chain exists in-repo (grep `patent|Filing|evidentiary|Cosmos|counsel` over `docs/` returns only the blueprint itself). Patent-adjacent evidence is a **guardrail domain** and is plainly kept outside this repo. The harness must **not self-adjudicate** patent matters (blueprint P0.7, §7). Drafted entry text, for the operator to place in the real chain and route to counsel:

> **2026-07-14 — H22 spherical-harmonics splat relighting (vendor motion).** H22 ships SH-splat relighting prototypes: lighting adjustment over a learned splat representation without a full light-transport simulation. Note as vendor motion in the *lighting-without-full-simulation* neighborhood. **Distinct mechanism from Filing 3 (Cosmos):** Cosmos predicts a rendered result via a world-foundation model with no ray tracing; SH-splat relighting evaluates a spherical-harmonics radiance basis over splats. Different representation, different inference path. `counsel-review-pending`. Cite the H22 keynote coverage. *(Placement + counsel ping are the operator's action, not the harness's.)*

---

## What this run builds (5 genuine items) — and what it will not

**Builds** (each on this branch, atomic commit, CRUCIBLE test, full suite green):
1. `assert_mode_b()` read-only guard on the real `harness/state/drop.json` path (+ test that it raises pre-drop).
2. `harness/notes/SYNAPSE_U1_H22_RESWEEP.md` — discovery-breadth delta only; feeds `flywheel_queue.json` as `ratified:false` (+ lint test: zero unqualified H22 symbol claims).
3. `check_no_rigging_drift` phrase-scan extension over `emitted_node_types.json` (+ one rejection test per dead phrase, + one positive splat-geometry test).
4. `theme_source.py` adapter — hcs backend byte-identical live, `qml_theme` stubbed `NotImplementedError`; `tokens.py` routed through it (+ snapshot + no-direct-`UIDark.hcs` import test).
5. Perception baseline capture writer over `TopsEventBridge` — fixed envelope, empty-baseline-headless (+ schema roundtrip test).

**Does not build, by design:** the repo-root `drop.json` (C-1), a Gate 0.1 DECISION-DUE (M-1), the G6 benchmark meter (M-2), the P0.7 patent record (guardrail). All Phase-1/2 work stays behind `assert_mode_b()` until the operator writes `harness/state/drop.json` on H22 drop day.
