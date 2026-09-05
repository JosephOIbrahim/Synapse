# Solaris Recipes v3 — Integration report (bp5)

Orchestrator: Claude (Fable 5.1), 2026-09-04 20:35. Branch `bp5/solaris-integrate` = `bp5/solaris-v3-base` (24c8b7f0) + six worker branches merged `--no-ff` in the order spec, lifecycle, verify, authority, receipt, acceptance. No merge conflicts. Merge to master is Joe's word; nothing here was pushed.

## Wave result

Six Codex workers on `gpt-6-astra`, one per worktree, all completed. The sandbox could not write the worktree index, so every worker's tree was committed on its behalf by the orchestrator after it went terminal (commit bodies say so).

| Stream | Commit | Own evidence (from its REPORT) |
|---|---|---|
| SPEC | 1e64437b | 162 passed (63 new + 99 existing BLOCKS); 9 deliberate mutations each caught |
| LIFECYCLE | b1a10515 | in-memory fake-scene controls green; undo host driver deferred (symbols not in the H22 table) |
| VERIFY | f231d415 | verify + compose tests green; 4 headless-Houdini tests skipped with reason; tolerances doc |
| AUTHORITY | d06bd6d1 | 191 passed; 7 mutation controls; HOOKUP_AUTHORITY.md |
| RECEIPT | cdc8ec5a | 48 passed; 10 source mutations red; independent crucible PASS (headless scope); HOOKUP_RECEIPT.md |
| ACCEPTANCE | 0c3afa6e | 36 passed; skip-to-PASS and median-to-min mutations caught |

## Full suite on the integrated branch (orchestrator shell, Python 3.14.2, no hou)

```
python -m pytest tests -q -p no:cacheprovider
4 failed, 7407 passed, 198 skipped in 250.58s        (base: 1 failed, 6941 passed, 192 skipped)
```

+466 passing tests. The four failures, classified:

| Test | Class | Disposition |
|---|---|---|
| `tests/test_backfill.py::test_backup_is_taken_and_source_intact` | pre-existing at base | untouched |
| `tests/test_m3_env_conformance.py::test_every_source_env_read_is_documented` | new env vars undocumented (`SYNAPSE_RECIPE_LEDGER_DIR`, `SYNAPSE_WORKER_TOOL_PROFILE`) | **fixed on this branch**: rows added to `docs/studio/DEPLOYMENT.md`; test green |
| `tests/test_worker_tool_policy.py::test_unknown_env_value_falls_back_to_standard` | behaviour change | **needs Joe's ruling** (below) |
| `tests/test_pkg_bootstrap_invariant.py::test_r310_shapes_leave_no_runtime_divergence` | runs the R310 subset, which contains the test above | collapses into the ruling; goes green with it |

After the doc fix the branch stands at 3 failures, two of which are the same ruling.

## Ruling needed: unknown worker-tool mode

Base behaviour: an unknown `SYNAPSE_WORKER_TOOL_MODE` value fell back to `standard`. The AUTHORITY brief (written by the orchestrator from blueprint p06, "Unknown tools/actions and profile conflicts fail closed. Demo mode cannot silently fall through to an unrestricted environment setting") asked for fail-closed; the worker implemented unknown or conflicting values → `strict` and documented the conflict with the legacy test rather than weakening it.

Options:

1. **Accept fail-closed** (recommended). Update `test_unknown_env_value_falls_back_to_standard` to assert `strict`. Consistent with the 2026-08-18 DECIDE that the interactive worker may not self-authorize. Cost: a typo in the env var now yields a read-only worker instead of a standard one, which is visible and safe.
2. **Keep legacy fallback for MODE, fail closed only for `demo`/profile conflicts.** Smaller behaviour change; two code paths to reason about.
3. **Revert** to the base behaviour and drop the fail-closed rule from the brief.

Not applied from a tick. The test stays red until ruled.

## Acceptance command (ACCEPTANCE stream)

```
python scripts/solaris_v3_accept.py --tier pure
pure: PASS   hython: NOT_RUN (tier not selected)   gui: NOT_RUN (human steps)
G0–G6, T1–T12: all NOT_RUN
```

Rows are NOT_RUN by design: the runner's test-to-row binding map is empty until the integrator binds reviewed tests to rows. Candidates now exist for T4, T5, T6 (AUTHORITY tests), T7–T9 (VERIFY, pure tier parts), T10–T11 (LIFECYCLE in-memory controls), T12 (RECEIPT card tests). Binding them is a reviewed act, not a tick.

## Contract change requests

None. No stream asked to change `python/synapse/recipes/contracts.py`.

## Hookups awaiting Joe's word (not applied; larger than mechanical)

- **AUTHORITY** (`docs/solaris_v3/HOOKUP_AUTHORITY.md`): `RecipeHandlerMixin` into `SynapseHandler` + `reg.register("run_recipe", ...)`; a `TOOL_DEFS` tuple in `python/synapse/mcp/_tool_registry.py`; a constructor change to inject `recipe_executor` / `recipe_scope_provider`; a demo branch in `panel/tool_bridge.py`. Until wired, `run_recipe` is not reachable from either transport and demo mode advertises nothing new.
- **RECEIPT** (`docs/solaris_v3/HOOKUP_RECEIPT.md`): host-owned `RequestDedup`, `EvidenceTracker`, `ReceiptStore`; event adapters for scene_load/undo/redo/owned_edit/dependency_change; a `set_recipe_cards` display sink in `synapse_panel.py`. Freshness stays UNKNOWN by design until the adapters are proven on H22.

## What every stream deferred (same root cause)

Anything that needs the hand-built golden HIP: golden extraction and rebuild (T1), live USD predicates (P2–P4 on a real stage), image smoke (P5), H22 undo behaviour, render latency/VRAM. LIFECYCLE additionally refused to call `hou.undos.group/areEnabled/undoLabels/performUndo` because they are absent from the committed H22 symbol table; undo goes through an injected `TransactionBackend` until a live probe confirms the symbols. That probe is a `synapse_scout` call away and is the first thing to do once Houdini is open.

## Next actions, in order

1. Joe rules on the unknown-mode fallback (one line). The orchestrator updates the one test accordingly.
2. Joe builds and saves the golden sphere/ground scene on H22.0.400 (blueprint p12, first session).
3. Live probe of the four `hou.undos` symbols; LIFECYCLE backend bound.
4. Hookups applied under review; T4–T12 bindings added to the acceptance runner.
5. Merge word for `bp5/solaris-integrate`.
