# SPEC report — 2026-09-04

Code-side deliverables are implemented. **The stream is not fully done:** milestone commits are denied by the worktree Git metadata permissions, and the full pytest run stops during collection because `websockets` is unavailable. The focused SPEC + existing BLOCKS run passes **162 tests**. Golden qualification remains **BLOCKED / NOT_RUN**.

This report describes only `bp5/solaris-spec`, based on `83ec6330`. No merge, push, tag, release, live Houdini operation, or new host emulation was performed.

## Requirement → status

| Requirement | Blueprint | Status and producer |
|---|---|---|
| One owned hero/ground/material/light/camera/Karma/render/output topology | p03, p04, p13 S5 | Implemented as a **contract-only design**, not a captured golden. `fixtures/solaris.spine.json` declares 14 nodes: 10 outer LOPs and 4 nested VOPs, with 11 connections. Ground uses catalog type `plane`. `tests/test_recipe_spec.py::SpecTests.test_each_required_subgraph_is_required` removes each role independently. |
| Exact types, typed parameters, parents, flags, positions | p04 | `recipes/spec.py::_nodes_and_wires`, `_validate_parm`; exact catalog membership, typed/finite values, multiparm templates, parent scope and duplicate identity checks. No `hou`/`pxr` calls. |
| Two material definitions and binding targets | p03–05 | Catalog-declared `mtlxstandard_surface` + `mtlxsurfacematerial` pairs, nested beneath `materials`, with explicit assignments to hero/ground prim paths. Structural binding equality checked by `_baseline`. USD material resolution is **NOT_RUN**. |
| VOP port identities captured, never guessed | p04–05 | Every VOP records all input/output names, indices and types from the instantiated `Vop.json` wire signature. Connections retain both indices and names. `catalog_ports` rejects unavailable signatures; controls reject missing names, wrong indices and incompatible types. |
| Build and catalog compatibility | p04–05 | Frozen `SUPPORTED_BUILD`; SHA256 of actual LOP bytes in `RecipeSpec.catalog_digest`; VOP bytes separately pinned in presentation. Tests compute SHA256 independently and modify the bytes read by the validator. |
| Required golden record | p04–05 | Exact requested `PENDING_HUMAN` record with three null artifacts. `load_recipe_spec` returns `LoadedRecipeSpec`, a `RecipeSpec` subclass, with `.availability == Availability.BLOCKED` and a reason. Missing key rejects. |
| Four actions, slots, checks, scopes, permissions, phrases | p03–04, p06 | Frozen `ActionSpec`/`SlotSchema`, `REQUIRED_CHECKS`, `DEMO_PHRASES`; render requires APPROVE. Validator rejects weaker permission, other engine, missing checks, wrong target, nonfinite bounds and unbounded presets. |
| Existing v1 behavior | p04 | Existing function bodies remain unchanged. New functions are appended to `blocks/fixtures.py`. Both existing BLOCKS test files pass. A separate control compares the v1 file and five API outputs against base commit `83ec6330`. |
| Outer graph adapter | p04 | `spec_to_fixture_v1` emits the existing node/wire/ownership/display vocabulary, sorted for creation. Nested data remains in `recipe_subgraphs`. It is explicitly a contract-only planning projection, not a complete scene. Expressions that v1 cannot preserve are refused. |
| Separate semantic/layout identities | p05 | `canon.semantic_digest` and `layout_digest`; moves affect only layout; each authored semantic dimension changes semantic identity. No rounding or expression evaluation. |
| Existing c3 reuse, explicit stage context | p05 | `canon` imports `synapse.blocks.canonical`; no copied c3 rule list. Stage context records version, frame/time, load rules, ordered layers, resolver and dependency identities. Actual stage context is **NOT_RUN** in the fixture. |
| Negative controls and mutation evidence | p11 | 63 SPEC tests; nine deliberately disabled guards/digests each produce exactly one assertion failure, then normal code passes again. Producer: `python tests/test_recipe_spec.py --prove-mutations`. |
| Full suite and ratchet | swarm contract §6 | Required full command attempted once: 7135 collected, 0 executed passes/failures, 3 collection skips, 5 collection errors. All five errors are missing `websockets`; no baseline pass-floor claim can be made. |
| Milestone commits | swarm contract §7/§9 | **BLOCKED.** `git add` and `git commit` cannot create the existing worktree index lock. Status updates are written; zero commits created. |

## Files changed

- `fixtures/solaris.spine.json` — complete schema-v2 contract design and honest catalog/design/golden provenance.
- `python/synapse/blocks/fixtures.py:257` — separate `load_recipe_spec` and validation facade, preserving v1 implementations.
- `python/synapse/recipes/spec.py:27` — parser, immutable seam-compatible view, catalog validation, availability and outer adapter.
- `python/synapse/recipes/canon.py:82` — graph/layout identity; stage context and c3 reuse.
- `tests/test_recipe_spec.py:44` — 47 schema/API tests and opt-in mutation producer.
- `tests/test_recipe_spec_canon.py:30` — 16 identity/stage/import tests.
- `harness/solaris_v3/STATUS_SPEC.md` and this report.

No frozen-seam or forbidden source file was edited. No catalog or rulebook surface was edited. The v1 fixture is unchanged. Scope verification: `git status --short` and `git diff --check`.

## Verification evidence

All commands run from this worktree. Python resolves to `C:\Python314\python.exe` (3.14.2). Pytest was initially missing, then became available during this session without a dependency installation by this worker. Earlier NOT_RUN status lines record that actual earlier state.

Focused required command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests/test_recipe_spec.py tests/test_recipe_spec_canon.py tests/test_blocks_reconciler.py tests/test_blocks_seam.py -q -p no:cacheprovider
```

Output: `162 passed, 1 warning in 6.28s` (63 SPEC + 99 existing BLOCKS). The warning is the repository's existing vendored-SDK ABI warning on Python 3.14. The source import guard control runs a fresh Python subprocess, loads the complete recipe, and asserts neither `hou` nor `pxr` was imported. The pre-existing suite conftest installs its own host fake; this worker added none and the SPEC tests require none.

Independent stdlib execution, before pytest became usable:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path (Get-Location) 'python')
python -m unittest discover -s tests -p 'test_recipe_spec*.py' -q
python tests/test_recipe_spec.py --prove-mutations
```

Output: `Ran 62 tests in 4.991s / OK`. The mutation producer reports all nine `caught: true`, each `tests: 1`, `failures: 1`, `errors: 0`:

1. Ignore supported-build guard.
2. Ignore actual LOP byte digest.
3. Ignore pending-golden honesty.
4. Ignore VOP wire identity.
5. Ignore material-binding target equality.
6. Ignore material prim-path validity.
7. Ignore required render topology.
8. Return a constant semantic digest.
9. Return a constant layout digest.

These are deliberately red controls, not failures in the restored implementation. Patches exist only inside scoped in-memory mock contexts; production files remain intact. Malformed-input controls recompute the graph hashes so the specific structural wall, rather than a stale digest, must reject them.

Full suite command, run once (before the final material-path tightening and its additional passing control):

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider
```

Output:

```text
collected 7135 items / 5 errors / 3 skipped
Interrupted: 5 errors during collection
3 skipped, 1 warning, 5 errors in 10.04s
ModuleNotFoundError: No module named 'websockets'
```

Affected collectors: `test_load.py`, `test_passthrough_hygiene.py`, `test_port_wave_scene1.py`, `test_websocket_cancel_inflight_known_defect.py`, `test_websocket_cancel_reachable.py`. Their import failures precede execution and do not involve a SPEC source file. Full-run counts: **pass 0, test-fail 0, skip 3, collection-error 5**; execution of the full population is NOT_RUN. `BASELINE.md` records 7131 collected and the last human-promoted 6942 green, not a completed current-environment baseline. The ratchet is **UNKNOWN**, not met or regressed by inference.

Observed contract digests (not golden graph/render evidence):

| Identity | SHA256 |
|---|---|
| Actual `Lop.json` bytes | `1b0c813933374e2f61b1f3ba906c9ee91e3e27319920ca146841ad4e71e33d40` |
| Actual `Vop.json` bytes | `f3912e8a68527a76259b3514c018f3897f71decc52e44b17bb0f6831ad310cf4` |
| Authored graph design | `8f2f9082c812f6b2f6ee0f4a254e30db7a873a42b4c96c1777ac4d188a899cfe` |
| Layout design | `b1646f8f3c864fe37cf82b3912c7321267e43e349b7f07f1431332cc5f1f3b7f` |

Producer: load `fixtures.load_recipe_spec('solaris.spine')` and read the corresponding fields. Catalog digest tests recompute from file bytes; embedded catalog `blake2b` is deliberately not used as the full-file identity.

## Strict choices and limits

- **No inferred qualification.** A structurally valid `PENDING_HUMAN` record is BLOCKED. A future `CAPTURED` record is EXPERIMENTAL; this pure schema module never promotes itself to READY. Host qualification requires the separate golden capture/rebuild/USD/render evidence. This is not a ratification flip.
- **Resolution uses an enum of typed tuples.** The frozen `SlotSchema` has no int2 type, and the catalog records `resolution` as a two-component tuple without component names. The schema therefore binds `resolution` to `render_settings.resolution` with `64x64`, `128x128`, `256x256`, and exact int2 values in `presentation.resolution_presets`. No `resolutionx/y` names were guessed. A trusted consumer resolves the enum through that map before applying the tuple.
- **Conservative design bounds.** CPU only; samples 1–64; exposure −10..10; hero color components 0..1; bounded resolution presets. These are curated limits and defaults, not measured render budgets. CPU selection, geometry dimensions, camera/light transforms and topology require Joe's golden scene comparison.
- **One selected topology.** Required roles, the outer chain, two nested material wires and the explicit KRS-to-render branch are validated. This module is not a general capture/export framework. Material output nodes have no required scalar parameters; their nonempty definitions are the required shader node, catalog-identified surface connection, material flag and binding target.
- **Existing c3 ownership.** `harness/blocks/invariants_m5.py` already imports `blocks/canonical.py`. `canon` imports that authority too, including its private substitution-order helper instead of duplicating it. Stage text uses c3's existing documented filters. Authored graph strings never receive those broad line filters, so dates, anonymous-looking artist text and expressions remain meaningful. Graph path normalization touches only parameters explicitly typed `path`, only caller-supplied approved c3 tokens, and only path-prefix boundaries. Source text of both canonicalizer modules is hashed with LF normalization.
- **Outer adapter fidelity.** v1 wire format has no source-output field or nested parents. The adapter refuses nonzero outer source outputs and outer expressions, retains all nested records separately, and marks the projection `recipe_contract_only=True`. Passing only that projection to a reconciler cannot prove material completion. `load_fixture('solaris.spine')` does not silently flatten v2; it fails before mutation. The new registry must use `load_recipe_spec`.
- **No bus outside ownership.** The latest task's exclusive write set permits STATUS and REPORT, not `bus/` or main-tree artifacts. This report embeds the durable receipt below. No shared STATE/bus was written. Worktrees and process IDs were inspected; detailed CIM command lines were denied, and the local board has no bus directory. No same-board ownership claim was inferred from unrelated live swarm processes.

## Deferred/open and integration handoff

1. Joe's golden HIP, reference render and closed dependency record are absent. Golden extraction, fresh-scene reconstruction, composed-USD predicates, actual Karma delegate behavior, rendered pixels, latency and memory are **NOT_RUN**. Keep the blocked card visible.
2. LIFECYCLE must consume the immutable spec and the outer adapter inside its existing BLOCKS transaction, apply the retained nested subgraphs through its owned host executor, and verify them. It must not call the legacy name loader as if this were a v1 complete scene or report success from the projection alone. This SPEC stream adds no writer/reconciler.
3. Trusted render planning must use `presentation.resolution_presets[validated_resolution]`, the pinned engine and samples, and replace the contract picture default with an approved run-specific destination. The contract default grants no render or export permission.
4. READY promotion belongs to independent host qualification/registry integration. The schema loader provides `.availability`, `.availability_reason`, and `validate_recipe_spec(spec) -> Availability` while returning the frozen seam type. No public handler registration or frozen-file hookup is needed for these imports alone; the integrator must connect the registry/lifecycle calls in its owned wiring pass.
5. Full-suite execution must be repeated in an environment with the repository dependencies, including `websockets`. No tests/assertions or collector skips were weakened to hide the missing dependency.
6. Independent crucible/integrator review remains pending. This worker did not self-certify a human gate or add agents beyond the assigned six-worker organization.
7. Commits remain blocked. Attempts to stage and commit with the required subject/trailer failed with: `fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-spec/index.lock': Permission denied`. The sandbox permits this worktree's files but not its existing shared Git metadata path. No alternate Git database, index, branch, or master checkout was used to bypass that boundary.

**Contract change requests:** none. Resolution presets and the derived availability view fit the frozen seam through SPEC-owned presentation data and a subclass. A future first-class tuple slot or READY qualification model can be designed by the integrator; neither is silently added here.

## Receipt

```json
{
  "leg": "solaris_v3:C1:SPEC",
  "verdict": "BLOCKED",
  "touched": [
    "fixtures/solaris.spine.json:1",
    "python/synapse/blocks/fixtures.py:257",
    "python/synapse/recipes/spec.py:27",
    "python/synapse/recipes/canon.py:82",
    "tests/test_recipe_spec.py:44",
    "tests/test_recipe_spec_canon.py:30",
    "harness/solaris_v3/STATUS_SPEC.md:1",
    "docs/solaris_v3/REPORT_SPEC.md:1"
  ],
  "commands": [
    "python -m pytest tests/test_recipe_spec.py tests/test_recipe_spec_canon.py tests/test_blocks_reconciler.py tests/test_blocks_seam.py -q -p no:cacheprovider",
    "python -m pytest tests -q -p no:cacheprovider",
    "python -m unittest discover -s tests -p 'test_recipe_spec*.py' -q",
    "python tests/test_recipe_spec.py --prove-mutations",
    "git diff --check",
    "git status --short"
  ],
  "artifacts": ["docs/solaris_v3/REPORT_SPEC.md", "harness/solaris_v3/STATUS_SPEC.md"],
  "proved_it_bites": "Nine scoped code mutations (build, Lop digest, pending golden, VOP identity, binding equality, prim-path validity, topology, semantic/layout digest) each yielded exactly one assertion failure; restored code passed 162 focused pytest tests.",
  "could_not_verify": [
    "Golden capture/rebuild, live Houdini/USD/MaterialX/render behavior and dependency closure: NOT_RUN",
    "Full-suite ratchet: collection blocked by missing websockets, 5 errors and 3 skips",
    "Independent crucible/integration review: pending",
    "Milestone/final commits and clean committed worktree: denied index.lock write permission"
  ],
  "needs_human": []
}
```
