# Harden SYNAPSE Solaris Wiring

Coordinated production-hardening pipeline for SYNAPSE's Solaris (LOP) network wiring and node
recognition on the pinned Houdini build. Drives ground-truth → design → integrate → adversarial
seam-gate → live-verify → land, halting at every human gate. Use when hardening, extending, or
auditing the Solaris builder, or before landing any change to `build_graph` / `assemble_chain` /
the wiring + recognition authorities.

## Why this exists (read once)

Across the hardening effort this pipeline was assembled by hand four times, and **every time the
isolated work went green and an independent adversary caught a real composed regression** — twice a
data-corruption bug that only appeared on the SECOND action (the rebuild, the second network, the
interaction with an existing feature). This skill codifies that loop so the lesson is structural,
not rediscovered. The load-bearing stage is D (the seam-gate); it is never skipped.

## The primitives it coordinates (mostly already in the repo)

- **Ground truth:** `scripts/harvest_lop_catalog.py`, `host/introspect_connectivity.py` (live catalog
  producers) → the committed `*_catalog_*.json` / `lop_solaris_knowledge_*.json`.
- **Gates (`harness/verify/checks.py`):** entry = `connectivity_catalog_fresh`, `lop_catalog_fresh`,
  `phantom_clean`; exit = `wiring_conformance`, `validator_catches_miswire`,
  `validator_lop_conformance`, `suite_baseline` (ratchet).
- **Agents:** `cartographer` (read-only mapper), `prospector` (candidates), `sidefx-cto` (vendor
  lens), and **`seam-hunter`** (the adversarial composition gate — this harness's own agent).
- **Live verify:** `scripts/run_live_probes.py` (the probe battery + negative-control discipline).

## The pipeline

Announce the arc before starting: dense build register through D; sea-level teach-down after land.

**ENTRY GATE — refuse on stale truth (un-skippable).**
Confirm you are on the pinned build (`harness/state/drop.json:houdini_build`; `synapse_ping` /
`houdini_scene_info` for a live session). Run the freshness gates; if the live catalog is stale or a
phantom leaked, STOP and regenerate (`harvest_lop_catalog.py`) before any design. A change grounded
on stale truth is the #1 failure class here.

**A. MAP (read-only, parallel).** Only when the change is not already scoped. Dispatch `cartographer`
(+ `prospector` / `sidefx-cto` as the change warrants) to map the current surface and live ground
truth into one gap ledger. Nothing is designed until this lands.

**B. SPEC (parallel design agents).** One agent per non-trivial item. Each GROUNDS every new `hou.*`
call live (phantom APIs are the top failure class) and returns an EXACT implementation contract —
precise hunks, tests, a live probe. Design only; agents do not edit.

**— HUMAN/CTO INTEGRATES —** Apply the contracts serially, reconciling shared-file overlaps the
parallel agents could not (this is the orchestrator's job, not an agent's). Validate each hunk's
anchor against the live code; the specs have been wrong before — grep for the risks they flag, and
for the ones they miss (e.g. live probes asserting old names).

**D. SEAM-GATE (adversarial — NEVER skip).** Dispatch `seam-hunter` on the integrated result. It
attacks the COMPOSED change on the live build (build→look→rebuild, second-network, round-trip
recognition, depth-vs-rank, arity, status coercion) and returns GO / NO-GO. On any blocker: fix,
then re-run D. Do not proceed to land on a NO-GO. This stage has caught a corruption bug every time.

**E. VERIFY.** `python scripts/run_live_probes.py --strict-companions` (whole battery + negative
controls) AND the full `pytest tests/` (green, above the `suite_baseline` floor — read at
merge-base, never lower a sprint's own bar). Add a live probe for the new behavior, with a
`*_fix_is_real` companion or an inline negative control.

**— HUMAN LAND GATE —** Branch, PR. `master` promotion is human (`harness/CLAUDE.md`); do not
self-merge unless explicitly and durably authorized. Then the sea-level teach-down.

## Hard rules

- **Entry gate refuses on stale truth.** No design on a stale catalog or a leaked phantom.
- **The seam-gate is un-skippable and independent.** The author of a change cannot objectively attack
  their own composition — proven four times. `seam-hunter` built none of it.
- **Isolated-green ≠ done.** A unit test and a build-once probe are necessary, not sufficient. The
  regression lives in the second action; the seam-gate and a build→rebuild probe are where it dies.
- **Live truth over priors.** Every `hou.*` / `pxr.*` / `pdg.*` call is verified on the running build
  before it ships. `exists_in_runtime` is the verdict, docs are a hint.
- **Ratchet advances only on a CI-observed floor.** `suite_baseline` is a CI-Linux count, not a local
  one — never bump it from a local run.
- **Only the human/CTO mutates and lands.** Every agent is read-only or design-only.

## Stop conditions

Stop and surface (do not push through): a stale/phantom entry gate that will not regenerate; a
seam-gate NO-GO you cannot resolve; a suite regression; or the human land gate. A clean stop with a
capsule beats a broken guess.
