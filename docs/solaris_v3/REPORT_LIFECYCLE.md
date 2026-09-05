# LIFECYCLE report — 2026-09-04

**Code implemented and targeted tests green. Full-suite qualification and commits are BLOCKED.**

Branch: `bp5/solaris-lifecycle`; starting/current HEAD at report time:
`83ec6330857b7305e5b9ee74e74e6d92d4155200`. Changes remain in this worktree:
`C:/Users/User/SYNAPSE/.claude/worktrees/bp5-solaris-lifecycle`.
No merge, push, branch switch, release edit, substrate install, or live Houdini operation occurred.

## Requirement → implementation/evidence

| Requirement | Blueprint | Status and producer |
|---|---|---|
| Scene-local identity, owned IDs, revision, committed slots | p04, p07 | Implemented in `python/synapse/recipes/instance.py:117` (`InstanceLifecycle`), using the frozen `RecipeInstance` seam. Store keys identify the scene/box lifetime, not just a reusable path. Unknown existing metadata is never adopted. |
| BLOCKS-owned discovery and semantic fingerprint | p04, p05, p07; S3 | `instance.py:86` wraps `blocks.runtime.observe`. Complete capture and `Canonicalizer.semantic_digest(state, version=...)` are injected. Missing nested/expressions/ports capture raises `LifecycleUnavailable` with `UNAVAILABLE` reason. No import of SPEC's future canon module. |
| STALE/CONFLICT refusal and artist preservation | p07, T2 | `instance.py:169`, `:184`, `check_conflict`; `tests/test_recipe_instance.py`, `test_recipe_transaction.py::TransactionTests::test_t2_artist_change_conflicts_without_repair`. Caller revision, current identity, box lifetime, owned paths and authored baseline are checked. |
| Measured second BUILD no-op | p07, T1 | `transaction.py:234`; `test_t1_build_twice_is_measured_noop`. Reobserves fingerprint and full pre/post snapshot, preserves revision, performs zero additional applies/groups, never replays defaults. This is an in-memory golden-like control, not the missing golden HIP qualification. |
| Approved LIGHT/MATERIAL commits and rebaseline | p07 | `instance.py:207`; transaction validates exact declared slot bindings and exact parameter-leaf write scopes. The committed record joins the same undo group as graph mutations. `test_approved_edit_rebaselines_then_build_does_not_reset_it` exercises the second action. |
| Preflight, exclusive ownership, dependency/revision reread | p07 | `transaction.py:108`, `:135`. Process-local instance and stage/box ownership; nonblocking collision refusal; no timed ownership lease. Existing BUILD bypasses MUTATING for an observed no-op. |
| One evidence-derived undo group | p07; S4 | `TransactionBackend` supplies qualified undo evidence and group. Before/after enabled/label evidence follows the pattern inspected in `shared/bridge.py:305` and `:1645`; unknown evidence refuses before mutation. The bridge is not imported. |
| Terminal mutation before single recovery | p07, T10 | `transaction.py:356`. `await_terminal`, cooperative cancellation, queued-dispatch fencing, separate recovery; timeout never means stopped. Global undo requires our exact label at head, unchanged full post-state and a known unchanged foreign-edit epoch. |
| Recovery verdict separate from operation result | p07, T10 | `BuildResult`, `state_diff`, recovery controls. Clean rollback leaves the build failed/cancelled; unsafe undo produces measured RESIDUE and quarantines ownership. Missing observations produce UNKNOWN. Metadata is restored/verified too. |
| Render approval, final recheck, bounded existing route | p06, p07 | `render_job.py:28`, `:69`, `:167`. `ApprovalRechecker` injected; exact revision/engine/resolution/samples/output checked before preparation and immediately before start. Existing `foreground_guard.assess_foreground_render` and `_handle_render_bounded` reused, with force flags false. |
| Run output, cancellation, native termination, logs and file identity | p07, p09 | `RenderPlan.prepare` resolves a unique output before approval. `RenderResult`, `file_identity`, `RenderJob.poll` retain evidence. Native termination requires `RenderBackend.render_terminated(...) is True`; a Python return alone cannot certify a background ROP. Lost waits keep RUNNING. |
| Render override recovery independent of BUILD | p07, T10 | `render_job.py:383`; separate bounded restoration, once, only after native termination, matching post-state and unchanged foreign-edit epoch. No build undo interface exists on a RenderJob. Partial output files remain and are recorded, never deleted as “rollback”. |
| Request dedup and reset/new request semantics | p09, T11 | `TransactionRegistry` and `RenderJobRegistry`. Register before execution, bind original payload identity, retain terminal requests across scene resets; new request creates new run; changed payload under old ID refuses. |
| BLOCKS extract-only preservation | S3 | `python/synapse/blocks/runtime.py` unchanged: `observe` is already public, so no extraction was necessary. Its 99 existing tests pass. No second reconciler added. |
| Hython-only checks with honest absence | p11 | `tests/test_recipe_transaction_hython.py`: two tests skipped with NOT_RUN reason. They require isolated hython and an explicit golden-capture backend factory; collection never accesses the live GUI. |

## Files added

- `python/synapse/recipes/instance.py`
- `python/synapse/recipes/transaction.py`
- `python/synapse/recipes/render_job.py`
- `tests/test_recipe_instance.py` (8 controls)
- `tests/test_recipe_transaction.py` (14 controls)
- `tests/test_recipe_transaction_review.py` (5 independently authored adversarial controls)
- `tests/test_recipe_render_job.py` (16 controls)
- `tests/test_recipe_transaction_hython.py` (2 NOT_RUN host checks)
- `harness/solaris_v3/STATUS_LIFECYCLE.md`
- This report.

No frozen seam, handler, panel, runtime, VERSION, rulebook surface, or other stream file changed.

## Tests, commands and observed counts

Commands run from the worktree using Python 3.14.2. Bind imports explicitly:

```powershell
$env:PYTHONPATH = "$PWD/python;$PWD/tests"
$env:PYTHONDONTWRITEBYTECODE = '1'
python -m pytest tests/test_recipe_instance.py tests/test_recipe_transaction.py tests/test_recipe_transaction_review.py tests/test_recipe_render_job.py tests/test_recipe_transaction_hython.py tests/test_blocks_reconciler.py tests/test_blocks_seam.py -q -p no:cacheprovider
```

Observed: **144 collected; 142 passed, 0 failed, 2 skipped**, 1 pre-existing vendored-SDK ABI warning. Final targeted run: 1.33 seconds. Of the passes, 43 are new lifecycle controls and 99 are unchanged BLOCKS controls. The two skips are NOT_RUN host qualification, not product passes.

Full-suite command (run once):

```powershell
python -m pytest tests -q -p no:cacheprovider
```

Observed: **7,117 collected; 0 executed passes, 0 executed failures, 3 skips, 5 collection errors**; collection interrupted in 10.90 seconds. Every error was `ModuleNotFoundError: No module named 'websockets'` in existing modules:

- `tests/test_load.py:18`
- `tests/test_passthrough_hygiene.py:41` → `mcp_server.py:46`
- `tests/test_port_wave_scene1.py:36` → `mcp_server.py:46`
- `tests/test_websocket_cancel_inflight_known_defect.py:33`
- `tests/test_websocket_cancel_reachable.py:31`

No test was excluded or assertion weakened. The baseline file records 7,131 collected at base and a last human-promoted 6,942 green, without an available base full-run breakdown. **The full-suite ratchet comparison is UNKNOWN**, not a claim of matching or exceeding 6,942. Collection was prevented by this environment's absent dependency, not a changed lifecycle assertion.

Earlier in this session pytest was unavailable (`C:/Python314/python.exe: No module named pytest`); the shared `.hython_deps` copy was access-denied. The environment later exposed pytest 8.4.2 without an install/change by this worker. Status history preserves both facts. A standard-library fallback independently ran:

```powershell
python -m unittest test_recipe_instance test_recipe_transaction test_recipe_transaction_review test_recipe_render_job test_recipe_transaction_hython -v
```

Observed before the final late-output regression was added: 44 tests, **42 passed, 0 failed, 2 skipped**. All new tests remain pytest-compatible. They inject an in-memory scene/backend; they do not plant `hou`. The existing repository pytest conftest supplies its own pre-existing suite-wide double; the fallback run does not need that double.

Fresh-process imports of the three production modules resolved inside this worktree. `hou` was not in `sys.modules` after those imports. `git diff --check` reported no errors (the new files are untracked because staging is denied).

## Falsification and independent review

The independent crucible, which authored none of the production code, first produced four failing controls in `test_recipe_transaction_review.py`: graph/metadata split across undo entries, stale revision accepted after a 0→2→0 exposure round-trip, fingerprint crossing a reset/recreated instance, and cancellation during verification still committing. All four were fixed and independently rerun green.

A fifth independent control failed when a group-close error followed metadata save but left zero graph delta: recovery claimed RESTORED without restoring session metadata. That path now restores/verifies metadata before reporting recovery; the fifth control independently reran green.

The reviewer also challenged artist edits between render termination and restoration; the guarded restore preserves the artist edit and reports RESIDUE. A separate source-level finding that native background rendering can outlive a Python return led to mandatory native termination evidence and `test_python_return_without_native_termination_cannot_restore`.

Deliberate approval mutation (in a disposable interpreter; source file not modified):

```powershell
@'
import pytest
from synapse.recipes.render_job import RenderJob
RenderJob._check = lambda self: None
raise SystemExit(pytest.main(['tests/test_recipe_render_job.py::RenderJobTests::test_no_approval_means_no_render_or_overrides', '-q', '-p', 'no:cacheprovider']))
'@ | python -
```

Observed **1 failed**: `(renderer.starts, renderer.applies)` became `(1, 1)` rather than `(0, 0)`. The final unmutated selection subsequently returned 142 pass / 2 skip. This proves the approval control observes actual effects.

A final independent probe found that an absent output before native termination was prematurely classified as failure. `test_background_output_may_arrive_after_python_return` reproduced one pytest failure before the fix. File validation now occurs only after confirmed native termination; the final targeted suite includes the green regression. The full-suite collection attempt above preceded this last timing correction and could not execute tests.

Final independent review verdict: **GO for reviewed code-side controls**. `python -m unittest test_recipe_transaction_review test_recipe_render_job -v` independently passed 21 tests; its standalone delayed-output probe also returned terminal success with one render and one restore, while retaining UNKNOWN image verdict. No remaining concrete code-side blocker was found by that review; host qualification remains NOT_RUN.

## Deferred/open, stricter choices and integration contract

1. **Live qualification NOT_RUN.** No golden HIP, real nested capture, image reference, or qualified host backend was supplied. T1's real golden reconstruction, live USD, H22 undo behavior, render P5, cancellation latency and memory/VRAM remain unmeasured. The in-memory controls do not promote these gates.
2. **Undo host driver deferred pending evidence.** `rulebook/phantoms.json` contains an empty phantom list. The committed symbol table identifies build 22.0.400 but lacks `hou.undos.group`, `areEnabled`, `undoLabels` and `performUndo`. Existing bridge evidence is older H21 evidence. No new code calls those unconfirmed symbols; qualified undo operations must be injected through `TransactionBackend`. Missing proof refuses mutation. No live scouting/GUI call was made.
3. **Complete capture is required, not guessed.** `BlocksObserver(fixture, capture)` reuses the existing BLOCKS ownership read. A host capture must produce `ScopeObservation` with all nested authored state, owned ID paths, complete flag/reason, and stable scene/box lifetime. Incomplete capture is UNAVAILABLE. This preserves extract-only scope in BLOCKS.
4. **Host metadata needs correct undo semantics.** A persistent `InstanceStore.save` must be atomic and join the active transaction undo group. `after_undo` may restore session-only data or verify that HIP metadata was already undone; it must never issue another scene write. `MemoryInstanceStore` is session-only; missing records after reload refuse adoption. Persistent metadata/scene event hookup is not qualified here.
5. **Process-local concurrency and retry retention only.** Ownership protects both instance ID and initial-build stage/box; no cross-process lock is claimed. Registries retain requests across scene resets but not process restarts. Restart-safe dedup needs a durable host registry. RESIDUE/UNKNOWN keeps ownership reserved; remediation needs a separate host reset, never an automatic retry.
6. **Render bounds are existing bounds, not a hard native kill.** Reuse is the main-thread inline branch of `_handle_render_bounded`, whose foreground guard can reduce risk but cannot interrupt a native renderer. A qualified override driver must capture all affected settings, apply the exact approved scope, report foreign edits and prove native termination. Missing termination stays RUNNING/UNKNOWN, with no override restore. The default adapter reports cancellation unsupported instead of pretending to kill a render. Actual native cancellation driver and bounds remain NOT_RUN.
7. **Authority and canonicalization adapters.** No sibling module is imported. Adapt SPEC's canonicalizer to `semantic_digest(state, version=spec.canonicalizer)`; adapt AUTHORITY's recheck to `(ApprovalBinding, current RecipeInstance, RenderPlan) -> Refusal | None`. The caller supplies trusted validated slots, prepared BLOCKS operations, dependency identity and approved edit provenance. No frozen contract change is requested.
8. **Independent checks.** The host backend's `verify(action, instance)` delegates to VERIFY's independent checks; all required `CheckResult`s must PASS to commit. Successful render file identity deliberately leaves terminal verdict UNKNOWN until P5 and required stage checks are supplied to RECEIPT. A complete capture/foreign-edit tracker is required; those capabilities cannot be inferred from a return code.
9. **Bus restriction.** This stream's exclusive write set grants its status/report and named code/tests, not shared `bus/` or main-tree artifacts. The receipt below is embedded here instead of writing outside that set. Initial worktree/PID/status sweep found the expected six separate stream worktrees and no pre-existing LIFECYCLE status file; only this stream's status was written.

## Integrator hookup (no frozen-file edits made)

Bind one `InstanceLifecycle` per stage/spec with the SPEC fixture, `BlocksObserver`, complete capture, canonicalizer adapter and host metadata store. Discover existing identity; for a clean absent scope create a candidate with captured owned IDs. Do not adopt a same-named artist scope. The host operation compiler validates ownership/collisions and produces `PreparedOperation`s; no handler nesting or second reconciler is needed.

Use one process-level `TransactionRegistry`; register the original request payload before calling `BuildTransaction.execute()`. Pass actual dependencies and independent verifier results through the qualified backend. A nonterminal response is polled through `await_terminal`; after confirmed failure call `recover` once and publish operation plus recovery dimensions separately. Never release quarantined ownership merely because a UI timeout expired.

Prepare `RenderPlan` with a host-owned output root before obtaining exact approval. Use one process-level `RenderJobRegistry`, an AUTHORITY adapter, a live `current_instance` callback and `BoundedRenderAdapter(existing_handler, qualified_overrides_driver)`. Its dispatch uses `server.main_thread.run_on_main`. Keep the job alive when caller wait expires; poll native termination; create receipts from `RenderResult` and VERIFY's image/stage checks. No BUILD transaction remains open around render.

Specific handler hookup patches depend on AUTHORITY's not-yet-present dispatcher and qualified host driver. None is fabricated in forbidden `handlers.py`/`mcp_server.py`. The APIs above are the callable handoff; lack of the driver is an explicit integration blocker.

## Commit blocker and receipt

Milestone `git add`/`git commit` attempts all failed:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-lifecycle/index.lock': Permission denied
```

The sandbox permits writes only inside this worktree; linked Git metadata is outside it. Approval escalation is unavailable. The worker did not relocate or bypass that boundary. **No milestone or final commit exists; the completeness contract is not fully satisfied.** Once the worktree's Git metadata is writable, stage only the ten files above and use subject prefix `bp5(lifecycle):` with trailer `Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`.

```json
{
  "leg": "solaris_v3:bp5:lifecycle",
  "verdict": "BLOCKED",
  "touched": ["python/synapse/recipes/instance.py:117", "python/synapse/recipes/transaction.py:135", "python/synapse/recipes/render_job.py:167", "tests/test_recipe_instance.py:1", "tests/test_recipe_transaction.py:1", "tests/test_recipe_transaction_review.py:1", "tests/test_recipe_render_job.py:1", "tests/test_recipe_transaction_hython.py:1", "harness/solaris_v3/STATUS_LIFECYCLE.md:1", "docs/solaris_v3/REPORT_LIFECYCLE.md:1"],
  "commands": ["python -m pytest tests/test_recipe_instance.py tests/test_recipe_transaction.py tests/test_recipe_transaction_review.py tests/test_recipe_render_job.py tests/test_recipe_transaction_hython.py tests/test_blocks_reconciler.py tests/test_blocks_seam.py -q -p no:cacheprovider", "python -m pytest tests -q -p no:cacheprovider", "python -m unittest test_recipe_instance test_recipe_transaction test_recipe_transaction_review test_recipe_render_job test_recipe_transaction_hython -v", "git diff --check"],
  "artifacts": ["docs/solaris_v3/REPORT_LIFECYCLE.md", "harness/solaris_v3/STATUS_LIFECYCLE.md", "tests/test_recipe_transaction_review.py"],
  "proved_it_bites": "Five independent red-to-green lifecycle controls; bypassing RenderJob._check made the no-approval test fail with one render and one override application.",
  "could_not_verify": ["Full-suite pass count: five collection errors from absent websockets", "Golden HIP reconstruction, live USD/P5 and H22 native undo/termination/cancellation", "Cross-process ownership or process-restart dedup", "Live persistent metadata/capture/backend hookup", "Commits: linked Git metadata write denied"],
  "needs_human": []
}
```

## Final production-file identity

SHA-256, measured from this worktree after the last production edit:

- `python/synapse/recipes/instance.py`: `db16612ae2bf5817cf6745ee56e17a7f22baa727b3e32cae254d0b81267c544c`
- `python/synapse/recipes/transaction.py`: `55849da2f7930506599c6198f9cbd49d15607c54758ef7c21a6f2a98f74953d4`
- `python/synapse/recipes/render_job.py`: `73e56bc390a9fefbf589b3e5442c919100c5f3e1aa683a58308aba35be1aa9dc`
