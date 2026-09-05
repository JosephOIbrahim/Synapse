# VERIFY stream report — 2026-09-04

**Verdict: code implemented; handoff BLOCKED on Git metadata permissions and
full-suite qualification. No live Solaris or golden-scene qualification.**

Branch: `bp5/solaris-verify`. Starting/current HEAD:
`83ec6330857b7305e5b9ee74e74e6d92d4155200`.
No commit succeeded. The worktree contains the deliverables as unstaged/new
files; do not treat the base SHA as the identity of these changes. Source
SHA-256 values below identify the tested files.

## Requirements and producer paths

| Requirement | Status and evidence |
|---|---|
| P1 graph, p08 / capture p05 | Implemented: `verify.py:162`, `HostObserver:634`. Exact owned IDs/paths/types/categories/parents, nested nodes, destination/source ports, flags, authored values and committed/current slots. BLOCKS observation supplements owned box evidence. |
| P2 USD, p08 | Implemented: `verify.py:206`. Expected active/defined typed prims, applied schemas, computed intended material binding, resolvable material surface shader; captured surface path/ID/context supported. |
| P3 readiness, p08 / S6-S7 p13 | Implemented: `verify.py:249`; extends `solaris_compose_tools.py:487` and `:694`. Explicit settings path, GetCameraRel, valid Camera, linked/authored products/vars/output, two authored lights, captured render-input ports and node identities. Legacy caller scope preserved. |
| P4 composition, p08 | Implemented: `verify.py:307`. Separate composition/node-error, asset-resolution and payload-state evidence; bounded stage traversal. |
| P5 image smoke, p08 / p05 | Implemented: `verify.py:333`, `:350`, `:415`. Terminal successful job, planned file, pre/post stat + digest, prior-artifact rejection, dimensions/channels, finite RGB, pinned-reference region coverage and mean color. No renderer is invoked. |
| P6 locality/recovery, p08 / p07 | Implemented: `verify.py:525`, `:552`. Complete field-digest snapshots, exact slot allowlist, unrelated state preservation, no resetting BUILD, terminal-state prerequisite and measured rollback residue. |
| T7, p11 | `tests/test_recipe_verify.py:172` and new assessor test `test_recipe_assessor_t7_camera_valid_but_render_branch_removed`. Removing branch fails with camera still valid; cached ready/pass claims cannot rescue it. |
| T8, p11 | `tests/test_recipe_verify.py:264`, `:273`, `:286`. Old file, copied old bytes with new stat identity, and a fresh nonblack wrong-color scene rejected separately. |
| T9, p11 | `tests/test_recipe_verify.py:163`. Stage unavailable => P2/P3 UNKNOWN with original diagnosis. |
| Hython real-path tests | Implemented in `tests/test_recipe_verify_hython.py`; four tests skip explicitly without resident real hou. Real H22 headless graph/USD/material/readiness/composition paths run when available; no GUI or render qualification claimed. |
| Candidate tolerances | `docs/solaris_v3/VERIFY_TOLERANCES.md` documents starting 64x64/1 sample, reference-derived half-open regions, luminance/coverage/color candidates, limitations and measurement protocol. |
| Milestone status/commits | Status appended in `harness/solaris_v3/STATUS_VERIFY.md`. Commit attempts blocked by `index.lock: Permission denied`; no branch/history workaround attempted. |

Full module paths for the abbreviated entries above:
`python/synapse/recipes/verify.py` and
`python/synapse/server/solaris_compose_tools.py`.

## Files changed

- `python/synapse/recipes/verify.py` (new)
- `python/synapse/server/solaris_compose_tools.py` (existing assessor extended)
- `tests/test_recipe_verify.py` (new pure-Python observation controls)
- `tests/test_recipe_verify_hython.py` (new clearly gated host adapters)
- `tests/test_solaris_compose_tools.py` (append-only test extension)
- `docs/solaris_v3/VERIFY_TOLERANCES.md`
- `docs/solaris_v3/REPORT_VERIFY.md`
- `harness/solaris_v3/STATUS_VERIFY.md`

No frozen contract, handler, MCP registration, panel, VERSION, CLAUDE.md, master
checkout or sibling-stream source was edited. Temporary test/profile data was
kept within this worktree.

## Validation

Interpreter: `C:/Python314/python.exe` (Python 3.14.2), pytest 8.4.2.
Actual imported module path is asserted by
`test_imported_checkout_is_this_worktree`. A fresh-process import test blocks
both hou and pxr via an import finder, verifies guarded import, and plants no
fake module. Actual local import measured hou unavailable and pxr available.

Focused command (after final code changes):

```text
python -m pytest tests/test_recipe_verify.py tests/test_recipe_verify_hython.py tests/test_solaris_compose_tools.py -q -p no:cacheprovider
102 passed, 4 skipped, 1 warning
```

That is 76 pure verifier tests + 26 compose tests passing; the latter include
the original 18 tests unchanged. Four headless host tests are NOT_RUN, not
product passes. The warning is the existing cp311/cp313 vendor versus Python
3.14 ABI warning.

The exact required full-suite command was attempted:

```text
python -m pytest tests -q -p no:cacheprovider
7140 items collected / 5 collection errors / 3 skipped; exit 2
```

Missing `websockets` prevents collection in test_load,
test_passthrough_hygiene, test_port_wave_scene1,
test_websocket_cancel_inflight_known_defect and
test_websocket_cancel_reachable. No pass/fail runtime count exists for that
interrupted run.

A supplementary complete traversal used
`--continue-on-collection-errors` without dropping failed tests:

```text
python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors
23 failed, 6874 passed, 263 skipped, 84 warnings, 5 errors in 177.04s
```

This earlier traversal preceded the last small verifier hardening changes.
The final source-bound traversal is recorded in the closing section below.
The failing inventory is retained there. Failures include unavailable
dependencies, OS process/ACL restrictions and Git dubious-ownership errors
under the isolated test profile. They were not suppressed or changed into skips.

The one full-suite failure entering the changed compose module,
`tests/test_m2_path_policy.py::test_compose_parms_keep_tokens`, was rerun
with the **original HEAD assessor file** temporarily restored, then the final
file restored immediately. It reproduced exactly:
`AttributeError: 'types.SimpleNamespace' object has no attribute 'ComposeError'`
at the existing `_resolve_layer_base` path (lines 165/232).
This is direct evidence that this failure is not introduced by the assessor
extension. Other out-of-scope failures were not exhaustively baseline-isolated.

Baseline comparison: `harness/solaris_v3/BASELINE.md` records 7,131 collected
and 6,942 last human-promoted green, with the complete base-run counts pending.
This environment's run does **not** demonstrate that floor. The ratchet is
UNKNOWN/BLOCKED; no gate or baseline number was edited or promoted.

Reproduction environment: run from this worktree with its `python` directory
first in PYTHONPATH, `PYTHONDONTWRITEBYTECODE=1`, and TEMP/TMP under
`.verify-test-tmp`. The full traversal also redirected USERPROFILE, APPDATA
and LOCALAPPDATA beneath that directory so tests could not write artist
profile state. PATH included C:/Python314, C:/Windows/System32 and
C:/Program Files/Git/cmd. The resulting Git ownership failures are recorded,
not normalized away. No substrate was installed. A temporary local pytest
bootstrap attempt failed with WinError 10013 (network denied); a subsequent
explicit test environment used the existing system pytest.

## Proved the checks can fail

All mutation files were restored immediately after each run. No mutant remains.

| Mutation / exact changed expression | Command suffix | Observed result |
|---|---|---|
| M1: in _Check._result, replace `CheckStatus.FAIL if failures else CheckStatus.PASS` with `CheckStatus.PASS` | `tests/test_recipe_verify.py -q -p no:cacheprovider` | 35 failed / 37 passed, exit 1 |
| M2: same expression replaced with `CheckStatus.FAIL` | same | 9 failed / 63 passed, exit 1 |
| M3: EvidenceUnavailable handler's UNKNOWN replaced with PASS | same | 24 failed / 48 passed, exit 1 |
| M4: assessor's `branch_ok = bool(expected) and not missing and branch.get("complete") is True` replaced with `branch_ok = True` | `tests/test_solaris_compose_tools.py -q -p no:cacheprovider` | 1 failed / 25 passed, exit 1; T7 catches it |

These counts identify the tests present at each mutation run. The final focused
run above reestablishes green after all additional tests and restored code.

Independent crucible: `/root/verify_crucible` did not build this code. It
demonstrated empty bound materials and insufficient pre-state coverage as
false-PASS paths; both were fixed. It verified the broken-branch failure with
a valid camera and reran its targeted tests: 17 passed / 55 deselected. Its
code-side verdict was GO with live qualification UNKNOWN. Its Menu/Toggle
normalization limitation was subsequently addressed and tested.
The platform cannot strip write tools from an individual spawned agent, so
this review was not claimed to be a technically fenced read-only execution.

## Deliberate strict readings and open qualifications

1. The frozen mapping receives an additive capture adapter at
   `golden_reference.verification`. Missing capture never becomes guessed
   expectations or a success fallback. This is code scaffolding awaiting the
   real golden scene under SWARM_CONTRACT decision 1.
2. P2 material resolution includes an actual surface source, not just a valid
   Material prim. The captured render context selects that source explicitly.
3. Legacy assessor callers retain legacy results; only explicit-path mode can
   supply recipe P3 evidence.
4. Loaded-payload qualification is strict: an unloaded payload fails P4 and is
   distinguished from a missing asset.
5. P5 checks file stat identity and content digest independently, and tests
   decoded reference regions rather than nonblack output. Region statistics
   are a smoke criterion, not proof against all possible wrong pictures.
6. P6 requires whole-scope semantic observations, including artist USD opinions;
   owned-only P1 data cannot establish locality. It requires measured terminal
   mutation state before accepting recovery.
7. Scalar animation/tuple-expression representations beyond the documented
   adapter are UNKNOWN. Their actual golden-scene use remains unqualified.
8. No actual H22 host, reference EXR, OIIO decoding, render job, undo/rollback,
   plugin compatibility, warm/cold timing, memory or GUI behavior was verified.
   Hython tests are ready but skipped here. No live-bridge claim or ping claim
   is made.
9. Full-suite qualification and commits remain blocked as described above.
   The implementation is not a completed/committed swarm leg.
10. No bus file is in VERIFY's exclusive write set. The requested stream status
    and this report carry the receipt instead; no shared board/bus was written.
    Worktree list and PID sweep were performed. CIM command-line access was
    denied; Get-Process supplied IDs. No existing local bus/STATUS_VERIFY was
    present at initial inspection. Other swarm worktrees are expected by the
    contract; no second writer to these VERIFY files was observed.

## Contract change requests and integration

No edit to `contracts.py` is requested. `VERIFY_TOLERANCES.md` defines the
additive golden-reference adapter and observer/context schema.

The integrator should call the public frozen seam, for each action's required
check, with trusted lifecycle context:

```python
from synapse.recipes.verify import VERIFIERS

results = tuple(
    VERIFIERS[check]().run(check, instance, spec, **trusted_context)
    for check in action_spec.required_checks
)
```

P1 uses action/validated slots; P1-P4 can use HostObserver or an injected trusted
ObservationReader. P5 needs terminal render_job, planned output_path and complete
prior_artifacts inventory. P6 needs full before/after snapshots, recovery, and
when applicable mutation_terminal plus rollback. Store returned evidence
verbatim. Keep operation failure separate from a clean recovery check.

The lifecycle/receipt handler is owned by another stream and is not present as
a stable integration anchor here; no guessed protected-handler patch is
provided. No MCP tools were added or removed.

## Commit blocker

Both staging and commit attempted the authorized bp5/solaris-verify branch:

```text
git add python/synapse/recipes/verify.py python/synapse/server/solaris_compose_tools.py tests/test_recipe_verify.py harness/solaris_v3/STATUS_VERIFY.md
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-verify/index.lock': Permission denied
```

The initial commit attempt also stopped at this lock. No permissions, ACLs,
Git refs or metadata were rewritten to evade the restriction. A commit with
subject `bp5(verify): implement and qualify Solaris recipe predicates` and
trailer `Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>` remains to
be made once metadata access works. Never merge or push this worker branch.

## Final source identities

| Path | SHA-256 |
|---|---|
| `python/synapse/recipes/verify.py` | `f744b110a3d2e605d23dafdee32510bc9bf20bba075569d13bf1c873bd1f32bc` |
| `python/synapse/server/solaris_compose_tools.py` | `2280b1c1311d3f9259b1299ef6e60cfbc927ab4228734988f90010e42779d4f2` |
| `tests/test_recipe_verify.py` | `9ea4c9c218a1ca9561f352535e75ebccd93e7c5c35b6423ae312375f2cd3dfc7` |
| `tests/test_recipe_verify_hython.py` | `6796cff6c7fd43f315ba803536dd58e6efd52c7a36902146676d8c67d45aa7c0` |
| `tests/test_solaris_compose_tools.py` | `f3e500cc77a3260e09366f7d9ac4b817542808a3f4e1fe6c5d4c93bd2a5fca1e` |

## Closing verification

Final source-bound command:

```text
python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors
20 failed, 6937 passed, 265 skipped, 84 warnings in 162.77s
exit 1; zero collection errors in this final run
```

All five source/test hashes above were checked unchanged after this run.
All VERIFY/compose tests passed in the composed run; the four dedicated
headless-Houdini tests skipped. The final 6,937 pass count is below the recorded
6,942 promoted floor, so full-suite qualification remains BLOCKED. The earlier
dependency collection errors did not recur; no successful dependency install
was performed by this worker.

Final failing test IDs (no assertions weakened):

```text
tests/test_d_track.py::test_tops_path_untouched_green_at_head
tests/test_decisions.py::test_the_aging_gate_can_fail
tests/test_harness_lock.py::test_second_acquire_is_refused
tests/test_harness_lock.py::test_acquire_records_the_base_commit
tests/test_harness_lock.py::test_live_lock_is_never_reaped
tests/test_harness_lock.py::test_undeterminable_liveness_is_treated_as_alive
tests/test_harness_lock.py::test_board_surfaces_a_running_leg
tests/test_m2_path_policy.py::test_compose_parms_keep_tokens
tests/test_perf_ratchet.py::TestAnchor::test_anchor_is_always_reported
tests/test_perf_ratchet.py::TestAnchor::test_run_gate_honest_end_to_end
tests/test_statusline.py::test_branch_read_without_git_matches_git
tests/test_statusline.py::test_registry_matches_git_worktree_list
tests/test_statusline.py::test_stamp_records_its_producer_and_commit
tests/test_statusline.py::test_head_sha_matches_git
tests/test_vendored_deps.py::TestVendorLayout::test_pycache_under_vendor_is_gitignored
tests/test_vendored_deps.py::TestVendorLayout::test_pyc_files_under_vendor_are_gitignored
tests/test_worktree_guard.py::test_orphan_directory_is_not_a_worktree
tests/test_worktree_guard.py::test_registered_worktree_passes
tests/test_worktree_guard.py::test_verify_reports_the_actual_harm
tests/test_write_plane_health.py::test_probe_bounded_on_real_acl_denied_dir
```

`git diff --check` passed. The original compose test file is preserved as an
exact prefix of its extended version. Protected-file diff was empty. The five
changed Python files parsed successfully with the standard-library AST parser.

Temporary test-data cleanup and final commit outcome are recorded below.

Cleanup completed: the resolved worktree-local .verify-test-tmp directory was
removed; .verify-test-deps was absent. Final staging again exited 128 with the
same index.lock permission error, so no subsequent commit was attempted on an
empty index. Only the eight declared deliverables remain modified/untracked.
Final source hashes matched the recorded test inputs.

### Closing receipt

```json
{
  "leg": "solaris_v3:verify:C4",
  "verdict": "BLOCKED",
  "touched": [
    "python/synapse/recipes/verify.py:162",
    "python/synapse/server/solaris_compose_tools.py:487",
    "tests/test_recipe_verify.py:163",
    "tests/test_recipe_verify_hython.py:110",
    "tests/test_solaris_compose_tools.py:187",
    "docs/solaris_v3/VERIFY_TOLERANCES.md:1",
    "docs/solaris_v3/REPORT_VERIFY.md:1",
    "harness/solaris_v3/STATUS_VERIFY.md:1"
  ],
  "commands": [
    "python -m pytest tests/test_recipe_verify.py tests/test_recipe_verify_hython.py tests/test_solaris_compose_tools.py -q -p no:cacheprovider",
    "python -m pytest tests -q -p no:cacheprovider",
    "python -m pytest tests -q -p no:cacheprovider --continue-on-collection-errors",
    "git diff --check",
    "git add -- python/synapse/recipes/verify.py python/synapse/server/solaris_compose_tools.py tests/test_recipe_verify.py tests/test_recipe_verify_hython.py tests/test_solaris_compose_tools.py docs/solaris_v3/VERIFY_TOLERANCES.md docs/solaris_v3/REPORT_VERIFY.md harness/solaris_v3/STATUS_VERIFY.md"
  ],
  "artifacts": [
    "docs/solaris_v3/REPORT_VERIFY.md",
    "docs/solaris_v3/VERIFY_TOLERANCES.md",
    "harness/solaris_v3/STATUS_VERIFY.md"
  ],
  "proved_it_bites": "M1 false PASS -> 35 failing controls; M2 false FAIL -> 9; M3 unavailable-as-PASS -> 24; M4 branch forced pass -> T7 fails. All mutants restored.",
  "could_not_verify": [
    "Live H22 graph/USD/EXR path and pinned golden capture (four hython tests skipped).",
    "Actual render job, reference-scene image tolerances, undo/recovery and performance.",
    "Full-suite floor: final 6937 passed, 20 failed, 265 skipped.",
    "Commit requirement: final git add exited 128 with index.lock Permission denied; no commit, unstaged worktree.",
    "Independent technical write-tool fencing and shared bus receipt (not in exclusive write set)."
  ],
  "needs_human": []
}
```
