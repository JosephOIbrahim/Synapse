# Solaris v3 acceptance

**Start in this worktree's root.** Use an environment with pytest already installed.

```powershell
python scripts/solaris_v3_accept.py
```

The default is `pure`. It runs plain `python -m pytest` over these globs, expanding them without shell wildcard assumptions:

```text
tests/test_recipe_*.py
tests/test_worker_policy_demo*.py
tests/test_solaris_v3_*.py
```

A missing glob prints `NOT_RUN: no tests collected for <glob>`. A successful suite is **not** a product-gate pass.

## Pick a tier

| Tier | What it can prove | What must remain outside its claim |
|---|---|---|
| `pure` | Schema, policy, whole-request matching and dispatch refusal controls | Graph/USD, pixels, real panel interaction and artist state |
| `hython` | Reviewed graph/USD and bounded render controls on measured H22.0.400 | GUI undo, panel freshness and artist walk |
| `gui` | Nothing automatically; every row is `NOT_RUN` in this command | The artist walk is a human step |

```powershell
$env:SYNAPSE_HYTHON = 'C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe'
python scripts/solaris_v3_accept.py --tier all
```

`SYNAPSE_HYTHON` wins. A broken explicit pin never silently falls back. Without it, the runner reuses `.synapse/hytest.py` candidate discovery, filters to 22.0.400, and verifies the actual running build. It does not choose installed 22.0.429 because it is newer.

Only reviewed exact hython test bindings run. Until those tests and the golden HIP exist, that tier reports the reason for `NOT_RUN`.

```powershell
python scripts/solaris_v3_accept.py --tier pure --tier hython --timeout 600
python scripts/solaris_v3_accept.py --tier gui
```

The timeout is a finite process limit, **not** a measured render budget or cancellation guarantee. Hython controls must use the existing approved, bounded render job and establish its terminal state themselves. A runner timeout cannot supply that proof.

## Read the result

Each invocation writes an isolated `harness/solaris_v3/runs/<timestamp>/ledger.json`, per-tier logs, context and pytest observations. The ledger records reasons for every unresolved row.

The pytest process records the actual `synapse.__file__`, its containing checkout's commit, dirty-state/diff identity, untracked source hashes, Houdini build when applicable, command argument vector and loaded-module hashes. It also verifies the loaded plugin and each collected test module against the selected source. The `.pth` editable-install trap in `pyproject.toml` is checked **after** pytest applies its path configuration. A mismatched or mixed checkout refuses gate updates.

`GATES.json` changes only for a tier that actually executed tests. This run's ledger always starts with `NOT_RUN`; it never borrows an old pass. Historical rows for unselected/unavailable tiers stay in `GATES.json` with their original timestamps. They are not current-run evidence.

| Exit | Meaning |
|---|---|
| `0` | No executed check failed. Missing/skipped tiers may still be `NOT_RUN`. This is not permission to ship. |
| `1` | An executed suite/control failed. |
| `2` | Binding, configuration or runner infrastructure refused/failed. |

An exclusive lock under `runs/.acceptance.lock` protects ledger updates. A second writer refuses. After a crashed run, inspect the recorded PID and run before removing a stale lock; this command does not guess ownership.

## Promotion requires a reviewed binding

The initial `promotion_rule.bindings` is deliberately empty. No other stream's not-yet-present test name is invented. The integrator must review the **whole goalpost** and bind its actual controls before promotion.

`promotion_rule.bindings` maps each row ID to a nonempty list of exact pytest node IDs and intended paths:

```json
{
  "T4": [
    {
      "nodeid": "tests/test_worker_policy_demo_control.py::test_full_request_refused",
      "intended_path": "reviewed whole-request parser through final recipe dispatch"
    }
  ]
}
```

This is a **format example**, not a claim that this test exists. Configure every control needed for a goalpost, including its negative controls. Bindings are reviewed test definitions; the runner cannot determine whether an assertion is scientifically sufficient.

For each configured passing control, the pytest fixture `solaris_acceptance_evidence` provides a fresh `.directory`. Write the actual observation artifacts there, then call it with `(row_id, intended_path, [artifact_paths])`. It creates a run-specific receipt ID and hashes those files. It accepts no old/outside artifact path.

The runner requires every bound test to complete setup, call and teardown. Missing tests, skip, xfail/XPASS, wrong intended paths, missing receipts and changed artifacts cannot promote. A real failed assertion remains a failure even when another control skipped. Logs, command, receipt ID, actual commit/build/module and artifact hashes accompany every promoted row.

`G0`, `G2`, `G3`, `G5`, `G6`, `T11` and `T12` conservatively require GUI observation of the complete goalpost. Pure policy controls `T4`–`T6` do not certify `G2`'s real panel path. Hython covers the remaining automated scene rows. These tier assignments implement the stricter reading of blueprint pages 10–11.

## Pass rule — verbatim, blueprint page 11

> A test that was skipped, could not access its host, or did not exercise the intended path is NOT_RUN/UNKNOWN. It is never counted as a product pass.

## BENCH: collect measurements separately

```powershell
python harness/solaris_v3/bench.py
```

With no input, all seven metrics are `UNMEASURED`. Nothing cooks, renders or queries a GPU by default.

```powershell
python harness/solaris_v3/bench.py --samples path/to/measured-samples.json
```

The JSON input contains `conditions` (`frame`, integer `seed`, `engine`, `asset_set` mapping asset names to SHA-256 digests) and `samples`. Each sample names `metric`, numeric `value`, and `source` log/timer provenance. A `walk_completion_s` sample also requires Boolean `completed`; elapsed time alone is not completion.

| Metric | Measurement endpoint |
|---|---|
| `build_to_stage_s` | Request start → verified stage availability |
| `render_cold_s`, `render_warm_s` | Approved job start → terminal output validation; separate cold/warm repeats |
| `peak_memory_bytes` | Maximum observed process RSS during a repeat |
| `peak_vram_bytes` | Maximum observed selected GPU's used memory during a repeat |
| `cancellation_s` | Cancellation requested → confirmed terminal job state |
| `walk_completion_s` | Manual timer and explicit completion result |

The Python `Benchmark.measure` adapter accepts an already authorized, bounded operation callback. It records a duration only when that callback confirms its endpoint with `True`. Failed/incomplete jobs record no successful latency.

For sampled memory, call `memory_sample(pid, gpu_uuid)` across the measured interval and pass readings to `record_peaks`. It uses optional psutil and a bounded `nvidia-smi --query-gpu=uuid,memory.used` query. The existing `host/cache_host_probe.py` reports capacity (`memory.total`), which cannot establish a peak. Missing readings leave that metric unmeasured.

Peaks are **sampled peaks**: short spikes may be missed, and GPU usage includes other processes. Record sampling cadence/interval in the source log. An external cold-start protocol and golden asset identities still need host evidence; the scaffold cannot infer them.

Distributions contain `n`, minimum, median and empirical nearest-rank p95 (`ceil(0.95*n)`). A manual completion within fifteen minutes is reported separately from its time distribution. None of these numbers promotes a gate.

## September 4–13 window

Source: [blueprint page 12](../SOLARIS_RECIPES_H22_BLUEPRINT_V3.md#page-12). Dates are work windows, not achieved milestones. Row links point into the [gate ledger](../../harness/solaris_v3/GATES.json).

| Window | Work | Exit evidence | GATES rows |
|---|---|---|---|
| Sep 4–5 | Pin entry path. Joe builds the golden scene. Capture only that scope. | Saved HIP + scene/reference render + dependency record. | `G0`, `G1` |
| Sep 5–6 | Rebuild from captured spec; graph/USD checks; local edits and undo. | T1–T3 and failure recovery on H22.0.400. | `T1`, `T2`, `T3`, `T10`, `G1`, `G3` |
| Sep 7 | Demo dispatch fence; render approval; request/job identity. | T4–T7 and cancellation/retry controls. | `T4`, `T5`, `T6`, `T7`, `T10`, `T11`, `G2` |
| Sep 8 | Minimal card; freshness; image smoke; no stale-result cache. | T8–T12 and panel parity. | `T8`, `T9`, `T10`, `T11`, `T12`, `G4`, `G5` |
| Sep 9 | Two full owner rehearsals with reset between them. | Two recorded takes; pinned path has current evidence. | `G0`–`G6`, `T11`, `T12` |
| Sep 10–11 | Fix observed failures; invite a separate cold-walk tester if available. | Rerun touched controls; beta result reported separately. | Touched `T1`–`T12`, `G6` |
| Sep 12–13 | Freeze, dry run, record and ship. No new feature branch. | Pinned build/spec/profile; usable capture and recovery plan. | `G0`–`G6` with current receipts |

The swarm contract authorizes code-side work before golden capture. Golden qualification, owner rehearsals and the separate external-artist beta remain unrun until their evidence exists.
