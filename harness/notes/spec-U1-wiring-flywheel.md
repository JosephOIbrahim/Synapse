# Spec U.1 — Utility Flywheel, Cycle 1: Network-Wiring Truth

**Status:** ratified (this build) · **Layer:** utility · **Mode:** A (runs now on H21.0.671)
**Task id:** `U.1` in `harness/tasks.json` · **Queue:** `harness/state/flywheel_queue.json`

## Why this cycle exists

Yesterday's delta probe surfaced the pattern: SYNAPSE emits `setInput(index, ...)` wiring
from *remembered* input indices, and memory drifts. The two known-true regression seeds
(both fixed on the release train, both previously miswired):

- `vellumsolver` inputs are **0 = Vellum Geometry / 1 = Constraint Geometry / 2 = Collision Geometry**
- `rbdbulletsolver` constraint geometry goes to **input 1** (not 2)

Wiring truth is probeable the exact same way node-type truth was
(`host/introspect_nodetypes.py`): instantiate headless, read the live surface, commit the
catalog, gate the code against it. This cycle turns that one-off fix into a flywheel.

## The cycle contract (EXPLORE → REVIEW → SCAFFOLD)

Each utility cycle runs the same three phases; each phase produces committed artifacts the
next phase consumes. Nothing enters the live path on memory alone.

1. **EXPLORE — probe truth.** `host/introspect_connectivity.py` (zero-`synapse`-import,
   `hou` inside functions, mirrors the nodetype probe) instantiates every SYNAPSE-emitted
   node type PLUS all Sop types matching `solver|merge|switch|blend`, and records per
   resolved (category, type): `min_inputs`, `max_inputs`, ordered `input_labels`
   (instance-level `hou.Node.inputLabels()` — type-level labels are PHANTOM in 21.0.671),
   `output_count`, `output_labels`. Output:
   `harness/notes/verified_connectivity_21.0.671.json` (schema `verified_connectivity/v2`),
   deterministic (second run byte-identical; no wall-clock stamp), v1 keys the probe cannot
   re-derive folded in under `v1_preserved` with provenance markers.

2. **REVIEW — diff + deposit + queue-append.** `scripts/flywheel_review_wiring.py`
   (pure python + the catalog) sweeps `python/synapse/**` for `setInput(`/`insertInput(`
   call sites, resolves each receiver's node type (createNode assignment or created-name
   registry), and classifies: literal index within catalog `max_inputs`? does a nearby
   comment/label claim match the catalog label at that index? Emits
   `.claude/flywheel_u1_findings.json` + `.md` (severity-ranked: CRITICAL = provable
   miswire, INFO = unresolvable/dynamic). Verified finding classes are deposited to the
   Ledger via `synapse.science.deposit.LedgerDeposit` (Confirmation for clean classes,
   DeadEnd for confirmed miswire classes; live build stamp when `hou` is present;
   `--deposit` opt-in so the check verb doesn't re-deposit every sprint). New probeable
   truth classes the sweep surfaces are appended to the queue as evidence-linked U.2+
   candidates (status `candidate`, `ratified: false`).

3. **SCAFFOLD — wire into the live path + pin.**
   - `python/synapse/core/wiring.py` — `wire_by_label(node, label, source, catalog=None)`:
     resolves the input index from the packaged catalog
     (`python/synapse/cognitive/tools/data/connectivity_21.json`, the scout symbol-table
     pattern: per-major committed authority + blake2b integrity), case-insensitive exact
     label match, `WiringError` fail-loud on unknown label/type, index fallback ONLY with
     explicit `allow_index=True`. Adopted at the `vellumsolver` + `rbdbulletsolver` sites
     in `routing/planner.py` (behavior-identical).
   - `cognitive/graph_validator.py` P3: when the catalog knows the type, the validator
     rejects an edge into an index ≥ `max_inputs` and (when the proposal names a target
     input label) a label that resolves to a different index — additive, never weakens
     the oracle-backed checks.
   - `tests/test_wiring_flywheel.py` pins: catalog determinism, the `wire_by_label` unit
     matrix, and the three golden miswire fixtures (vellumsolver constraint→2/collision→1
     swap, rbdbulletsolver constraint→2, out-of-range index) REJECTED while the corrected
     forms pass.
   - `harness/verify/checks.py` verbs: `connectivity_catalog_fresh`,
     `wiring_conformance`, `validator_catches_miswire` (ADAPT-marker style).

## Anti-runaway anchors

- **Human ratifies new cycle classes.** The queue's `ratified` flag is flipped by a human
  only. An unratified candidate is a proposal, never a work order — no agent may start
  building U.N+1 because the queue mentions it.
- **Evidence-linked queue entries only.** Every queue entry carries `evidence` (artifact
  paths — probe outputs, findings files, test pins). An entry without evidence is invalid
  and must be rejected at review.
- **Guardrails every sprint.** The cross-cutting guardrails in `harness/tasks.json`
  (`scout_no_apex_corpus`, `no_rigging_drift`, `provenance_not_bypassed`) run on every
  U-cycle sprint exactly as on every other task; a utility cycle never gets a guardrail
  waiver.
- **Probe truth > pinned constants** (standing harness convention): where the catalog and
  a code comment disagree, the catalog wins; the code and its comment are the bug.

## Exit gate for U.1

Full `python -m pytest tests/ -q` green (modulo pre-existing release-train failures,
reported as a delta) AND `harness/verify/checks.py --task U.1` PASS.
