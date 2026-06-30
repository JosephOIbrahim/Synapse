# FORGE — Mile 2 (graph-synthesis)

ROLE: FORGE. Fill ONLY Mile 2 of the graph-synthesis blueprint, in the
`feat/graph-synth-mile2` worktree. Do not refactor unrelated files. Do not edit
`cognitive/graph_proposal.py` or `cognitive/interfaces.py` — FINAL contracts.

PREREQUISITE (you cannot start without these): the bench preflights are done —
§2.5 `dir()`-confirmed the `hou` connectivity symbols against live H21.0.671, and
§2.6 confirmed the scout existence surface. If either is missing, STOP and say so.

## Targets

1. `host/graph_oracle.py` — implement `IConnectivityOracle` via `hou.*`.
   - Use ONLY §2.5-confirmed symbols. Confirmed ABSENT, auto-quarantine: `hou.pdg.*`,
     `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick`. If a symbol you need
     isn't in `dir()`, STOP — do not write against priors or docs.
   - Graceful degradation: a false REJECT is cheaper than a false pass — EXCEPT
     `input_is_occupied`, which HALTS rather than degrades.

2. `cognitive/graph_validator.py` — implement the three gated phases:
   - `_phase3_connections`: 3a arity (all) · 3b type-compat (TYPED categories only —
     VOP/MAT/CHOP) · 3c slot-label advisory (goes in `advisories`, not `errors`) ·
     3d occupied-input guard (TARGET side, existing nodes; HALTS).
   - `_phase4_structural`: acyclicity (DAG) · NEW-vs-NEW friendly_name collision ·
     node_category ↔ network_type.
   - `_phase5_context`: parent exists/type · every EXISTING `scene_path` resolves
     (a resolve failure is a clean context error, never a crash) · NEW-vs-existing
     children name collision.
   - THEN flip `live_phases_enabled` to default `True` — but only once the five DoD
     tests are green.

3. `host/existence_adapter.py` — wire `ScoutExistenceAdapter` to the §2.6-confirmed
   scout surface (pass-through if scout returns a structured verdict; thin wrapper if
   it returns retrieval chunks).

## Done

- `tests/test_graph_oracle_mile2.py` green (RECONCILE its fixtures/assertions with
  spec §12 first — §12 is authoritative; the file is the starting target).
- Boundary green: `cognitive/*` still imports zero `hou`.
- Gate PASS:  `PYTHONPATH=python python harness/forge_evaluator_gate.py --mile 2`

Atomic commit on the Mile-2 branch. Halt for the Evaluator. Do NOT merge to main
(human gate).

## Note on what needs Houdini

The validator phases (P3-P5) are pure and testable on the mock oracle in the DoD
file — you can build and green most of this off-Houdini. Only `graph_oracle.py`
itself and an end-to-end pass require the live runtime.
