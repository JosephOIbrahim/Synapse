# Solaris Recipes v3 — Swarm Contract (bp5)

**Blueprint:** `docs/SOLARIS_RECIPES_H22_BLUEPRINT_V3.md` (Joe, 2026-09-04, demo target 2026-09-13).
**Frozen seam:** `python/synapse/recipes/contracts.py` — import from it, never edit it in a stream branch.
**Base branch:** `bp5/solaris-v3-base` (from master `6e3dd963`, v5.62.0). Every stream branches from it.

## Human decisions on record (2026-09-04, Joe)

1. The blueprint's stop rule ("no agent wave before the golden scene reconstructs") is **overridden for code-side streams only**. Golden-scene capture (blueprint p05 capture protocol against a real HIP) waits for Joe's hand-built scene. Anything that needs the golden HIP is scaffolded and reported **NOT_RUN**, never faked.
2. Six workers, one integrator pass at the end. Each worker is a Codex agent on `gpt-6-astra` in its own worktree.
3. Nothing merges to master from a worker. Merge is a human gate.

## Streams and exclusive write ownership

Read anything. Write only inside your list. Shared directories (`docs/solaris_v3/`, `harness/solaris_v3/`, `tests/`) are fine because file *names* are per stream.

| Stream | Capability | Exclusive write set |
|---|---|---|
| **SPEC** | C1 schema half | `fixtures/solaris.spine.json` · `python/synapse/blocks/fixtures.py` · `python/synapse/recipes/spec.py` · `python/synapse/recipes/canon.py` · `tests/test_recipe_spec*.py` |
| **AUTHORITY** | C3 dispatch fence | `python/synapse/panel/worker_policy.py` · `python/synapse/recipes/authority.py` · `python/synapse/recipes/phrases.py` · `python/synapse/server/handlers_recipe.py` · `tests/test_recipe_authority*.py` · `tests/test_worker_policy_demo*.py` |
| **VERIFY** | C4 predicates P1–P6 | `python/synapse/recipes/verify.py` · `python/synapse/server/solaris_compose_tools.py` · `tests/test_recipe_verify*.py` · `tests/test_solaris_compose_tools.py` (extend only) |
| **LIFECYCLE** | build transaction · render job · instance | `python/synapse/recipes/instance.py` · `python/synapse/recipes/transaction.py` · `python/synapse/recipes/render_job.py` · `python/synapse/blocks/runtime.py` (extract-only, behaviour-preserving) · `tests/test_recipe_instance*.py` · `tests/test_recipe_transaction*.py` · `tests/test_recipe_render_job*.py` |
| **RECEIPT** | C5 receipt · card · freshness · cache | `python/synapse/recipes/receipt.py` · `python/synapse/recipes/card.py` · `python/synapse/recipes/freshness.py` · `python/synapse/panel/recipe_card.py` · `tests/test_recipe_receipt*.py` · `tests/test_recipe_card*.py` |
| **ACCEPTANCE** | C6 one command · gate ledger · bench | `scripts/solaris_v3_accept.py` · `harness/solaris_v3/GATES.json` · `harness/solaris_v3/bench.py` · `tests/test_solaris_v3_acceptance*.py` · `docs/solaris_v3/ACCEPTANCE.md` |

Every stream also owns exactly these two files, named for itself:

- `harness/solaris_v3/STATUS_<STREAM>.md` — append a dated line after every milestone. This is the live dashboard source. Format: `- HH:MM  <milestone>  [tests: N pass / M fail]`.
- `docs/solaris_v3/REPORT_<STREAM>.md` — final report (template below).

Files nobody in a stream edits: `python/synapse/recipes/contracts.py`, `python/synapse/server/handlers.py`, `python/synapse/mcp_server.py`, `python/synapse/panel/synapse_panel.py`, `python/synapse/panel/claude_worker.py`, `CLAUDE.md`, `VERSION`, anything under `rulebook/surfaces/`. If your work needs a hookup line in one of those, write the exact patch into `docs/solaris_v3/HOOKUP_<STREAM>.md` for the integrator.

## The seam — how streams "talk" without talking

- All shared types live in `contracts.py`. Use them as-is. Adding an optional field with a default in your own module is fine; renaming/removing/retyping anything in the seam is not.
- Need a seam change? Write `docs/solaris_v3/CONTRACT_CHANGE_REQUESTS_<STREAM>.md` with the exact diff and why. Code against your proposed change locally **only through an adapter in your own module**, so the integrator can accept or reject the request without touching your code.
- Cross-stream calls go through the seam types, never through another stream's module internals. Example: VERIFY returns `CheckResult`; RECEIPT consumes `Sequence[CheckResult]` + `verdict_from_checks`; LIFECYCLE produces `RecipeInstance` and a `RecoveryVerdict`; AUTHORITY produces `RunRecipeRequest` or `Refusal`.
- If you must call something another stream is building, code against a `Protocol` in your module and inject it. Do not import a sibling module that does not exist on the base branch.

## Laws (every stream)

1. **Worktree only.** Work in the worktree path you were given. Never write to `C:\Users\User\SYNAPSE` (that is master's checkout). Never use absolute repo-root paths in code; use `blocks.fixtures.repo_root()` style resolution.
2. **No third recipe engine.** Extend `blocks/fixtures.py` + BLOCKS runtime. `synapse.loop.recipe` (THE LOOP v0.0) is a *different* contract — do not extend it, do not import it.
3. **Phantom-API guard.** Before any `hou.*` / `pxr.*` call you are not certain exists on H22.0.400: check `rulebook/phantoms.json` and `python/synapse/cognitive/tools/data/h22_symbol_table.json`. Known phantoms: `hou.updateGraphTick`, `hou.lopNetworks`, `hou.secure`, `hou.pdg.*`, `hdefereval.executeInMainThread` (non-Result variant). Camera relationship: `UsdRender.Settings.GetCameraRel()`, never `winning_layer()`.
4. **Import guards.** Every new module imports cleanly with no `hou` and no `pxr` (try/except → `*_AVAILABLE = False`). Pure-Python tests run under plain `python -m pytest`.
5. **Honest NOT_RUN.** A test that needs hython/GUI and cannot reach it reports NOT_RUN/UNKNOWN via `CheckStatus`, and is `pytest.skip`ped with the reason. Never plant a fake `hou` in `sys.modules` (documented trap: it corrupts the SWIG type map). Never copy an expectation from the blueprint into a test as its oracle — compute it.
6. **Tests before done.** Your own tests green under `python -m pytest tests/<your files> -q`. Then run the full suite once: `python -m pytest tests -q -p no:cacheprovider` and record pass/fail/skip counts in your REPORT. Baseline on base branch is recorded in `harness/solaris_v3/BASELINE.md` — you may not reduce the pass count. Fix regressions you caused; report ones you did not.
7. **Commits.** Atomic commits on your branch, subject prefixed `bp5(<stream>):`. Trailer: `Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`. Never merge, never rebase onto master, never push, never touch `master` or another stream's branch.
8. **Scope.** Only what the blueprint asks for your capability. No unrelated refactors. World ingest, fog, fluids, general capture UI, arbitrary asset ingest are out (blueprint p03).
9. **Status cadence.** Append to `STATUS_<STREAM>.md` after each milestone; commit it. The orchestrator reads it every ten minutes.

## Definition of done (per stream)

- Every blueprint requirement mapped to your capability is implemented, or explicitly deferred with a reason.
- REPORT written: (1) requirement → status table with blueprint page refs, (2) files changed, (3) tests run and counts, (4) deferred/open with reasoning, (5) contract change requests, (6) hookup lines for the integrator.
- Final commit made; worktree clean.

## Integrator pass (after all six)

Merges the six branches onto `bp5/solaris-v3-base`, applies accepted contract changes, applies HOOKUP patches into `handlers.py` / `mcp_server.py` / panel, runs the acceptance command, updates `GATES.json` with evidence only, and writes `docs/solaris_v3/INTEGRATION.md`. Merge to master stays a human gate.
