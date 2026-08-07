You are ORCHESTRATOR for CI0 — make master's CI honestly green. Read harness/AGENT_CONSTITUTION.md first; it binds you. Base off master (c4187d01), which is where the red check lives.

**WRITES CODE.** The GitHub Actions CI on master is red and has been since before the M5 merges (3fb5d45d was already failing the same job). This is not a BLOCKS regression — M5/M5b's own tests pass. This leg makes CI run what it CAN run, for real, and be explicit about what it cannot.

=== THE ONE RULING THAT GOVERNS THIS LEG (Joe, as CTO) ===

**HONESTY OVER A GREEN BADGE.** A green check that hides failures is WORSE than an honest red one. You may NOT reach green by weakening assertions, deleting tests, broadening excepts, or marking a genuinely-failing test as skip to silence it. Green means: every test that CAN run in the CI environment DID run and passed, and every test that cannot is skipped with a visible, specific reason a reader can audit. If you cannot reach honest green, ship the partial fix and report exactly what remains red and why. Law 6 and Commandment 7 are in force.

=== THREE FAILURES, ALREADY TRIAGED — TREAT THEM DIFFERENTLY ===

CI reports 3 failed / 5659 passed / 217 skipped on stock Python 3.14 (no pxr, no Houdini). The three are NOT one class:

**A — REAL ROT, investigate and fix (do NOT skip):**
  test_moneta_crucible.py::test_moneta_backend_never_fires_evolution
  test_pass7_per_agent_and_canonical.py::TestPokemonStageCanonicalPin::test_charmander_referenced_in_all_consumers
  Both fail on `cannot import name 'evolution' from synapse.memory` and a
  canonical-drift check naming python/synapse/memory/evolution.py — which DOES
  NOT EXIST on disk (0 refs in the package __init__). This is a real missing
  module or a real stale reference, unrelated to pxr. Determine which:
    - If evolution.py was deleted/renamed and consumers/tests still point at it,
      the tests are correctly catching drift — fix the references or restore the
      module so the canonical name resolves. 
    - If the tests reference a module that was intentionally removed, the TESTS
      are stale — update them to the current canonical source (this is a real
      fix, not a skip). Record which, with evidence, in the receipt.
  Do NOT mark these needs_houdini. They fail on logic/packaging, not environment.

**B — ENVIRONMENTAL, mark honestly:**
  test_moneta_integration.py::test_hard_exit_loses_the_deposit — depends on
  Moneta durability semantics and shows the pxr ModuleNotFoundError path. If
  and only if it genuinely requires a runtime absent in CI, mark it with the
  environment marker below and a reason. If it can be made hermetic with a
  stub, prefer that.

=== THE SPLIT ===

23 of 310 test files import hou or pxr directly (grep: `^\s*(import|from)\s+(hou|pxr)`). These cannot run on stock GitHub runners. Introduce ONE pytest marker — `needs_houdini` — registered in conftest.py (there is already a tests/conftest.py; extend it, do not replace). A test or module earns the marker ONLY if it truly imports hou/pxr or calls into a Houdini runtime. Auto-collect is fine (a conftest hook that marks modules importing hou/pxr), but the marker must be legible on each and its skip reason must name the missing dependency.

CI change (.github/workflows/ci.yml): the pytest step runs `-m "not needs_houdini"`. The skipped set must be VISIBLE in the run summary (use `-rs` so skips and reasons print), not silently deselected. Do not change the matrix or delete a leg to dodge a failure.

Local runs are unaffected: on a Houdini/hython interpreter the marker still collects and runs — `pytest tests/` with no `-m` filter runs everything, exactly as the receipts record. The marker gates CI, not the developer.

=== DO NOT ===

Touch python/synapse/blocks/ or the BLOCKS tests — they pass and are out of scope.
Weaken, xfail-to-hide, or delete any test to reach green.
Mark a logic/packaging failure (class A) as needs_houdini.
Merge or push — Gate C is human.

**If hou surprises you, probe with dir() before coding against it.**

=== ORACLE ===

  `pytest -m "not needs_houdini" tests/` green on stock Python 3.14 AND 3.11,
    locally reproduced (no pxr, no hou importable)
  the class-A rot actually fixed (evolution reference resolved), not skipped —
    with the receipt stating whether module or tests were the stale side
  `pytest tests/` with no filter still collects the full suite on a hou
    interpreter; the marker changes collection only under the CI filter
  every needs_houdini skip carries an auditable reason; `-rs` shows them
  .github/workflows/ci.yml runs the filtered set; no matrix leg removed
  receipt CI0.json: the three failures each classified with evidence and
    disposition (fixed / made-hermetic / honestly-skipped), the marker
    mechanism, the count moved from 3-failed to 0-failed-N-skipped, and the
    exact skipped count with the reason string
  a note for the operator: how to run the full suite locally vs what CI runs,
    so the two-worlds gap is documented, not folklore

=== STANDING ===

Master is red inherited, not broken by recent work. This leg makes the badge
tell the truth. Honest green, or an honest report of what is still red — never
a green that lies.
