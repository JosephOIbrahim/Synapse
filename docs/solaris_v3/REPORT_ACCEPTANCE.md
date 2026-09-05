# ACCEPTANCE report — 2026-09-04

**Implementation complete; completion contract BLOCKED by Git permissions and the full-suite environment.** All 40 ACCEPTANCE tests pass under plain `python -m pytest`. Every product gate remains `NOT_RUN`. No commit, merge or push occurred.

Evidence: [final acceptance ledger](../../harness/solaris_v3/runs/20260905T001306.845967Z-20617ffd/ledger.json), [validation receipt with artifact hashes](../../harness/solaris_v3/runs/acceptance-validation/receipt.json), [targeted test log](../../harness/solaris_v3/runs/acceptance-validation/targeted.log).

## Requirements → status

| Requirement | Blueprint | Status and producer |
|---|---|---|
| G0–G6 and T1–T12 ledger, initial `NOT_RUN`, promotion rule and schema control | p10–11 | Implemented: `harness/solaris_v3/GATES.json`; `scripts/solaris_v3_accept.py:161`; `test_gate_schema_and_independent_page_coverage` parses the blueprint's labels and checks goalposts. |
| One command: pure globs, absent-glob reasons, bound hython, human GUI step | p10 C6, p11 | Implemented: `scripts/solaris_v3_accept.py:422`; actual `--tier all` run passed its pure suite and left all 19 product rows `NOT_RUN`. |
| Actual imported checkout/commit/build, commands, logs and hashes | p11 | Implemented: `scripts/solaris_v3_accept.py:82`, `:102`, `:500`; actual pytest process validates package, plugin and collected test-module paths, hashes selected/loaded sources, detects mixed checkout and changes during execution. |
| Only executed tiers update; skip/wrong-path never promotes; nonzero failure exit | p10–11 | Implemented: `scripts/solaris_v3_accept.py:314`, `:327`, `:381`, `:392`; skip, missing receipt, wrong path, stale artifact, empty collection, second-run invalidation and failure controls pass. |
| BENCH latency, cold/warm render, sampled RSS/VRAM, cancellation and manual walk | p10 | Implemented scaffolding: `harness/solaris_v3/bench.py:30`, `:44`, `:134`; seven metrics default `UNMEASURED`. No real performance measurement claimed. |
| Repeat distributions and pinned conditions | p10 | Implemented: immutable copies of frame/seed/engine/asset digests; independently hand-computed distribution test; minimum/median/nearest-rank p95/n. |
| Runner tests | p11 | Implemented: 40 passed, 0 failed, 0 skipped; includes real subprocess pytest evidence and wrong-checkout refusal. |
| Run guide, verbatim pass rule, Sep 4–13 windows with gate references | p11–12 | Implemented: `docs/solaris_v3/ACCEPTANCE.md`. |
| Full suite once and baseline comparison | Swarm law 6 | Attempted; stopped at collection with unavailable `websockets`. Regression/pass floor remains **UNKNOWN**. Details below. |
| Milestone status + atomic commits | Swarm law 7/9 | STATUS updated. Commits **BLOCKED**: Git cannot create `C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-acceptance/index.lock` outside this worktree's writable sandbox. |

## Files changed

- `scripts/solaris_v3_accept.py`
- `harness/solaris_v3/GATES.json`
- `harness/solaris_v3/bench.py`
- `tests/test_solaris_v3_acceptance_runner.py`
- `tests/test_solaris_v3_acceptance_bench.py`
- `docs/solaris_v3/ACCEPTANCE.md`
- `harness/solaris_v3/STATUS_ACCEPTANCE.md`
- `docs/solaris_v3/REPORT_ACCEPTANCE.md`

Generated evidence stays under the brief's mandated `harness/solaris_v3/runs/` in this worktree. No source files outside the exclusive ACCEPTANCE set were edited. `git status --short` lists only these files and that evidence directory.

## Validation

| Command | Result | Evidence |
|---|---|---|
| `python -m pytest tests/test_solaris_v3_acceptance_bench.py tests/test_solaris_v3_acceptance_runner.py -q -p no:cacheprovider` | **40 passed**, 0 failed, 0 skipped; one pre-existing vendored-SDK ABI warning | `runs/acceptance-validation/targeted.log` |
| `python -m pytest tests -q -p no:cacheprovider` | **7109 collected; 0 passed, 0 failed, 3 skipped, 5 collection errors; exit 2** | `runs/acceptance-validation/full-suite.log` |
| `python scripts/solaris_v3_accept.py --tier all` | Exit 0; pure **40 tests passed**; **19 product rows NOT_RUN**; two absent globs reported | `runs/20260905T001306.845967Z-20617ffd/ledger.json` |
| Headless `Benchmark().report()` | All seven metrics `UNMEASURED` | `runs/acceptance-validation/bench-default.json` |
| AST parse + import of both new modules under plain Python | Valid Python; neither imports `hou` nor `pxr` at module import | Re-run `python -B -c "from scripts import solaris_v3_accept; from harness.solaris_v3 import bench; import sys; assert 'hou' not in sys.modules and 'pxr' not in sys.modules"` |

Paths in the table are relative to `harness/solaris_v3/` unless a complete command is shown. PowerShell-captured logs use its text encoding; artifact hashes cover their exact bytes.

The full-suite collection errors are existing files: `test_load.py`, `test_passthrough_hygiene.py`, `test_port_wave_scene1.py`, `test_websocket_cancel_inflight_known_defect.py`, and `test_websocket_cancel_reachable.py`. Each failed with `ModuleNotFoundError: No module named 'websockets'`; none reached test execution. Assertions were not weakened and those modules were not edited.

`BASELINE.md` records 7131 collected and the last human-promoted 6942 green; its full-run baseline is pending. This run did not establish a comparable pass count. A collection interruption cannot establish either regression freedom or a reduction in passing behavior. Restore the existing suite dependencies and rerun the full suite before integration qualification.

Pytest was initially unavailable in the shared stock-Python environment, then became available as pytest 8.4.2 without an install by ACCEPTANCE. The subsequent successful targeted tests supersede the initial failed launch. The H22.0.400 probe still could not import pytest; its log is retained.

The final run bound `synapse` to this worktree's `python/synapse/__init__.py` at HEAD `83ec6330857b7305e5b9ee74e74e6d92d4155200`. Because new files could not be committed, it honestly records `dirty: true` and their source hashes. That HEAD is the inherited base, **not a claim that the implementation is committed**.

## Negative controls and independent review

`python harness/solaris_v3/runs/acceptance-validation/mutation_check.py skip` replaces the actual `phase_status` function in an isolated replay process so skipped phases return `PASS`. `test_skipped_phase_never_promotes_even_with_evidence` fails all three phase subcontrols; exit 1. See `mutation-skip.log`.

The same replay with `median` replaces `statistics.median(values)` with the minimum. The hand-computed distribution control fails; exit 1. See `mutation-median.log`. Source files were unchanged during the concurrent full-suite attempt.

Independent crucible `/root/acceptance_crucible` found and re-reviewed five issues: lock acquisition order, empty provenance accepted by schema validators, empty collection overwriting history, mutable benchmark pins, and unchecked loaded test/plugin paths. All were corrected; final review reported no outstanding findings. Review probes did not run a host or write files. The collaboration interface cannot enforce a restricted tool list, so this is an independent review, not a claim of a tool-fenced read-only agent.

## Strict choices, deferrals and gaps

**No guessed product bindings.** The initial binding map is empty because sibling stream tests are absent on this branch. The runner executes available suites and records them separately. The integrator must review and register exact node IDs plus intended execution paths, and those controls must emit fresh observation artifacts. A suite's aggregate success cannot qualify a row.

**Complete goalposts determine tiers.** `G0/G2/G3/G5/G6/T11/T12` conservatively require GUI evidence; `T4/T5/T6` permit pure dispatch-policy evidence without certifying the real panel gate. Remaining rows require hython. GUI rows are always `NOT_RUN` in this command. The runner does not automate or certify artist walks.

**Pinned host discovery.** Reuse `.synapse/hytest.py` discovery, but filter its normally newest-first candidates to 22.0.400. An explicit `SYNAPSE_HYTHON` is never silently replaced. Actual host qualification is deferred: pytest is absent in that interpreter and no golden HIP or reviewed hython bindings exist here. The sole new `hou` call is `applicationVersionString`, confirmed in the 22.0.400 symbol table and absent from `phantoms.json`, dispatched through `run_on_main`.

**Measured benchmarks require actual inputs.** Missing conditions, incomplete callbacks and missing memory samples cannot produce measured rows. The existing GPU helper reports total capacity, so the scaffold uses the same bounded `nvidia-smi` approach with `memory.used` and an explicit GPU UUID. Sampled peaks can miss spikes and device VRAM includes other processes. Cold/warm preparation, real stage/output completion, consent, cancellation termination and manual-timer provenance remain the host/control producer's responsibility.

**Gate persistence versus current-run truth.** Unrun tiers retain historical `GATES.json` rows. Every new ledger resets to `NOT_RUN`, so that history cannot become a current-run pass. A newly executed skipped control clears that tier's old pass. Empty collection does not overwrite historical evidence.

**Scope conflicts resolved in favor of this brief.** No shared `bus/` was written: it is outside ACCEPTANCE ownership. The durable receipt is in the requested run directory and linked from STATUS/REPORT. No artifacts were placed in master's checkout. The generic skills' design-approval pauses were superseded by the user's explicit autonomous implementation instruction and approved blueprint/brief.

## Contract changes and integrator hookup

**Contract change requests: none.** No edits to the frozen seam or protected integration files are needed.

**Hookup lines: none.** The command and pytest plugin are self-contained. Integration work is configuration/evidence: review and add exact `promotion_rule.bindings`, supply qualifying controls and golden artifacts, restore the test environments, and rerun acceptance. GUI qualification remains the human workflow.

## Commit handoff

Both milestone staging attempts failed with the same sandbox denial before a commit could be created. No metadata permissions were changed and no alternate checkout was used. Intended subject: `bp5(acceptance): implement evidence-bound gate runner and measurements`.

Once the authorized environment can write this branch's Git metadata, stage the eight owned files and review the generated evidence, then commit on **bp5/solaris-acceptance** with:

```text
bp5(acceptance): complete gate runner, benchmark scaffold and validation report

Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>
```

Until that succeeds and the full-suite floor is measured, this report is **BLOCKED**, not DONE.
