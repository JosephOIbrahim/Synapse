# AUTHORITY report — 2026-09-04

**Implementation complete within the exclusive source write set; overall handoff
BLOCKED on commits and full-suite qualification.** New tests: **191 passed**
under `python -m pytest`. No live Houdini operation, merge, push, version edit or
ratification occurred. HEAD remains `83ec6330857b7305e5b9ee74e74e6d92d4155200`
on `bp5/solaris-authority`; changes are uncommitted because Git cannot create its
worktree index lock under the current filesystem permissions.

## Requirement to evidence

| Brief / blueprint | Implementation | Evidence / boundary |
|---|---|---|
| D1; p06, p13 S1/S2: demo final-dispatch fence | `worker_policy.py:135` accepts registered reads and only the named recipe proposal; rejects all generic mutation, group composites and unknown tools | `test_worker_policy_demo.py::DemoPolicyTests`: a generated direct policy test for every actual registry entry; no advertisement prerequisite |
| D1; p06: demo advertisement | `worker_policy.py:125` provides read tools + recipe schema, detached from the registry objects | `test_demo_provider_advertises_reads_and_recipe_exactly`; actual panel provider and registration changes are in HOOKUP, not applied |
| D1; p06: invalid mode/profile fail closed | `worker_policy.py:79` distinguishes absent settings from explicit invalid values, resolves conflicts to strict; accepts a trusted captured profile | Invalid-mode, profile-conflict, live environment-change and legacy-valid-mode controls; one contradictory legacy assertion documented below |
| D2; p06: typed bounded slots | `authority.py:63`, `:106`, `:168`: checks identities, keys, missing slots, types, bool collisions, finite numbers, bounds, enums and literal resolved field bindings | Numeric/color/enum/schema negative controls and immutable typed-binding tests in `test_recipe_authority.py` |
| D2/D4; p06: preserve permission | `authority.py:177`; handler computes max of declared, wrapped effect and render floor | Full permission-order matrix; relabeled render and CRITICAL wrapper controls |
| D2; p06: approval binding/recheck | `authority.py:182`, `:217`, `:229`, `:243`: validated exact scope + provenance, no path normalization/rounding/type coercion | Every bound field changed independently; missing, malformed and boolean scope controls. Immediate live job-start placement is an integration requirement |
| D2; p06: terminal hard stop | `authority.py:253`, `:259`; handler reserves the shared turn budget before dispatch/proposal | Sequential and concurrent mutation tests; reads remain possible; failed and pending terminal calls seal the turn |
| D3; p03/p06, T4: exact phrases | `phrases.py:25` fullmatches the entire normalized request, returns typed requests or Refusal only | Trailing/leading text and punctuation, ambiguity, finite float extraction, curated named colors and missing defaults controls |
| D4; p06: handler seams | `handlers_recipe.py:24`, `:28`, `:42`, `:96`: injected SpecLoader/ScopeProvider/Executor; fallback to BLOCKS loader when present | Prepared-operation dispatch, absent-adapter UNAVAILABLE, PENDING_HUMAN golden refusal, malformed payload and scope controls |
| D4/D5; T6: wrapper cannot approve | `handlers_recipe.py:63`, `:151`: consent payloads refused; APPROVE/CRITICAL return awaiting_approval with unapproved scope and no executor call | `test_t6_render_awaits_trusted_approval`, `test_t6_wrapper_cannot_self_approve`, independent malformed-scope test |
| D4; p09: request_id replay | `handlers_recipe.py:80`, `:123`: type-sensitive content identity, serialized in-flight claim, defensive cached outcomes | Sequential, overlapping and reentrant retry controls; failures cached as UNKNOWN; conflicting ID content refused |
| D4: hookup lines | `HOOKUP_AUTHORITY.md` | Exact mixin/registry/advertisement edits plus explicit host adapter, phrase and turn-boundary contracts. Protected files unchanged |
| D5; p11: prove the walls bite | `tests/test_recipe_authority_mutations.py` | Seven targeted in-memory source mutations produced assertion failures, zero harness errors; originals restored by patch contexts |

## Files changed

Modified: `python/synapse/panel/worker_policy.py`.

Added: `python/synapse/recipes/authority.py`, `python/synapse/recipes/phrases.py`,
`python/synapse/server/handlers_recipe.py`, `tests/test_worker_policy_demo.py`,
`tests/test_recipe_authority.py`, `tests/test_recipe_authority_review.py`,
`tests/test_recipe_authority_mutations.py`,
`harness/solaris_v3/STATUS_AUTHORITY.md`, this report and `HOOKUP_AUTHORITY.md`.

No changes to the frozen seam or prohibited files. `git diff --check` passed.
All four loaded implementation paths were verified to resolve inside this
worktree. An import-blocking probe imported all four while both `hou` and `pxr`
were unavailable; neither module was planted. No new code calls either API.

## Commands and observed counts

Commands ran in this worktree using Python 3.14.2. Before commands that import
the standalone tests or run the mutation producer, use:

```powershell
$env:PYTHONPATH = "$PWD/python;$PWD/tests"
$env:PYTHONDONTWRITEBYTECODE = '1'
```

| Command | Observed result |
|---|---|
| `python -m pytest tests/test_worker_policy_demo.py tests/test_recipe_authority.py tests/test_recipe_authority_review.py tests/test_recipe_authority_mutations.py -q -p no:cacheprovider` | **191 passed**, 0 failed, 0 skipped, 1 inherited vendor ABI warning; pytest 8.4.2; 1.15s |
| `python -m unittest test_worker_policy_demo test_recipe_authority test_recipe_authority_review -q` | **191 passed**, 0 failed; 0.178s |
| `python -m pytest tests/test_worker_tool_policy.py tests/test_phase0b_consent_posture.py -q -p no:cacheprovider` | **25 passed, 1 failed**; failure is the contradictory invalid-mode fallback assertion at `tests/test_worker_tool_policy.py:223`; consent-posture tests both pass |
| `python -m pytest tests -q -p no:cacheprovider` — required full-suite attempt, run once | **7,264 collected; 3 skipped; 5 collection errors; 0 tests executed**. Missing `websockets` prevented test execution. Exit 1, 9.41s |
| `python -m test_recipe_authority_mutations` | Seven mutations killed; 22 assertion/subtest failures across seven selected test methods; 0 errors; producer exits 0 only when every mutation is detected |
| `git diff --check` | Exit 0, no whitespace errors |

The full-suite collection errors were in `test_load.py`,
`test_passthrough_hygiene.py`, `test_port_wave_scene1.py`,
`test_websocket_cancel_inflight_known_defect.py` and
`test_websocket_cancel_reachable.py`. Each reported
`ModuleNotFoundError: No module named 'websockets'`.

At the first milestone `python -m pytest` itself was unavailable. It later became
available without this worker installing packages; the actual pytest runs above
supersede that early NOT_RUN status. The baseline document records 7,131
collected tests and a historical 6,942 green result, not comparable full-run
counts for this environment. **The baseline pass-count ratchet is UNKNOWN**;
collection counts cannot establish it. No tests were skipped or weakened to
manufacture a full-suite green.

The repository's existing pytest conftest supplies its legacy test environment;
this stream added no fake `hou`. The separate unittest and import-blocking
probes avoid relying on conftest for import safety.

The import-absence probe is reproducible after the environment setup above:

```powershell
@'
import importlib.abc
import sys
class NoSceneAPIs(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'hou', 'pxr'}:
            raise ModuleNotFoundError('authority import probe: ' + fullname)
sys.meta_path.insert(0, NoSceneAPIs())
from synapse.panel import worker_policy
from synapse.recipes import authority, phrases
from synapse.server import handlers_recipe
assert 'hou' not in sys.modules and 'pxr' not in sys.modules
print('All four authority modules imported with scene APIs unavailable.')
'@ | python -
```

### Mutation receipt

`tests/test_recipe_authority_mutations.py` is a reproducible producer, with these
in-memory mutations and resulting assertion failures:

| Mutation | Target control | Failure entries |
|---|---|---:|
| Force demo mode resolution to standard | T5 direct Solaris builder dispatch | 1 |
| Bypass slot validation refusals | Numeric bounds/type/NaN/inf controls | 9 |
| Truncate text at ` and ` before matching | T4 entire-request refusal | 1 |
| Always return true from approval recheck | Each bound scope field | 8 |
| Lower effective permission to INFORM | T6 no unapproved render dispatch | 1 |
| Treat all request contents as equal | Conflicting request_id content | 1 |
| Disable mutation budget consumption | Second action in a turn | 1 |

The initial mutation producer exposed three test-spy/diagnostic errors rather
than assertion failures. The T4 spy now accepts any escaped plan, and dedup/turn
tests assert refusal status before accessing its kind. The final producer above
has **zero errors** and every mutant is detected by an assertion.

## Independent review

An independent crucible wrote only `tests/test_recipe_authority_review.py`.
Its first ten-test run found two defects: Python's `True == 1` equality let an
invalid retry inherit a prior outcome, and punctuation-attached clauses had the
wrong refusal kind. Fixes added recursive type-sensitive identity and widened
only partial-match diagnostic boundaries. Full-match acceptance did not widen.
The independent rerun was **10 passed, 0 failed**, exit 0. Concurrent requests,
reentrancy, uncertain terminal failure, defensive copies and malformed scope
controls also passed. This review is pure-Python evidence, not live signoff.

## Stricter interpretations and unresolved conflicts

1. **Invalid mode vs legacy assertion.** The brief simultaneously demands strict
   fallback and unchanged existing tests. `test_unknown_env_value_falls_back_to_standard`
   explicitly demands a permitted create-node call for `bogus_mode`. Both cannot
   hold. The stricter explicit requirement wins: invalid/empty selections resolve
   to strict. The old test remains unchanged and red; the integrator must revise
   that conflicting assertion through its own authorized test ownership. Valid
   strict/standard/unrestricted behavior remains intact.
2. **No slot defaults in the frozen seam.** All declared slots are required.
   Named colors come from `presentation.named_colors`; phrase defaults come from
   `presentation.demo_slots[action_id]`. Missing mappings/defaults refuse rather
   than invent values. SPEC may need to populate or adapt these presentation keys.
3. **Proposal binding is not consent.** An awaiting response contains proposed
   `ApprovalScope` data, not an `ApprovalBinding` falsely attributed to a human.
   Without a trusted scope provider it contains `binding=None` plus the reason.
   Only the trusted confirmation path may call `bind_approval`.
4. **All four actions are terminal.** The per-turn budget is sealed before a
   prepared action, including an awaiting proposal or uncertain/failed execution.
   A new model-generated request ID does not reset it. Only a trusted user-turn
   boundary can provide a new budget.
5. **Dedup is handler-lifetime, not durable.** Identical retries receive prior
   outcomes without execution; changed content returns DUPLICATE_REQUEST. The
   handler retains outcomes without eviction for its lifetime. Durable render
   jobs, restart replay and pending-to-approved transitions belong to LIFECYCLE's
   host adapter. Never interpret the cache as fresh scene verification.
6. **Receipt location.** The swarm's exclusive ownership lists no writable `bus/`
   file and explicitly require STATUS/REPORT. The receipt is embedded below,
   instead of writing outside the exclusive set. The six stream worktrees and
   live processes were observed; this worker did not become a second conductor
   or write shared board state.

## Deferred/open with reasons

- **Commits: BLOCKED.** Every milestone attempted the required add/commit. Git
  reports `Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-authority/index.lock': Permission denied`.
  The metadata path is outside this sandbox's writable root; approvals are
  unavailable. No alternate index, Git directory or branch workaround was used.
  All source and status changes remain in this worktree for the orchestrator.
- **Full-suite pass/fail qualification: BLOCKED** by the collection dependency
  errors above, plus the separately measured policy-spec conflict. No full-suite
  green or unchanged pass-count claim is made.
- **Live panel/bridge, original-text interception, shared host-turn ownership,
  real BLOCKS executor, trusted UI approval and immediate render-start recheck:
  NOT_RUN.** Their hookups are outside the stream write set. `HOOKUP_AUTHORITY.md`
  names the exact registrations and required adapter responsibilities.
- **Golden rebuild/render: NOT_RUN.** No golden HIP was supplied. The injected
  miniature specs and recording executors are explicitly test-only. A spec with
  `golden_reference.status=PENDING_HUMAN` returns UNAVAILABLE before dispatch.
- **No contract changes requested.** Shared dataclasses and enums are unchanged;
  local adapters provide scope, prepared operations and presentation conventions.

## Durable handoff receipt

```json
{
  "leg": "solaris_v3:bp5:AUTHORITY",
  "verdict": "BLOCKED",
  "touched": [
    "python/synapse/panel/worker_policy.py:79",
    "python/synapse/recipes/authority.py:106",
    "python/synapse/recipes/phrases.py:25",
    "python/synapse/server/handlers_recipe.py:96",
    "tests/test_worker_policy_demo.py:1",
    "tests/test_recipe_authority.py:1",
    "tests/test_recipe_authority_review.py:1",
    "tests/test_recipe_authority_mutations.py:1",
    "docs/solaris_v3/HOOKUP_AUTHORITY.md:1",
    "docs/solaris_v3/REPORT_AUTHORITY.md:1",
    "harness/solaris_v3/STATUS_AUTHORITY.md:1"
  ],
  "commands": [
    "python -m pytest tests/test_worker_policy_demo.py tests/test_recipe_authority.py tests/test_recipe_authority_review.py tests/test_recipe_authority_mutations.py -q -p no:cacheprovider",
    "python -m pytest tests/test_worker_tool_policy.py tests/test_phase0b_consent_posture.py -q -p no:cacheprovider",
    "python -m pytest tests -q -p no:cacheprovider",
    "python -m test_recipe_authority_mutations",
    "git diff --check"
  ],
  "artifacts": [
    "docs/solaris_v3/REPORT_AUTHORITY.md",
    "docs/solaris_v3/HOOKUP_AUTHORITY.md",
    "harness/solaris_v3/STATUS_AUTHORITY.md",
    "tests/test_recipe_authority_mutations.py"
  ],
  "proved_it_bites": "Seven mutations detected by 22 assertion failures, zero mutation-harness errors; originals restored.",
  "could_not_verify": [
    "Full suite aborted during collection: missing websockets; baseline pass-count ratchet UNKNOWN.",
    "Legacy invalid-mode assertion contradicts the stricter brief and remains unchanged/red.",
    "Live panel, host-turn wiring, trusted approval UI and bounded render start are NOT_RUN.",
    "Golden HIP and real LIFECYCLE/SPEC adapters unavailable on this branch.",
    "Cross-process/restart deduplication belongs to the lifecycle job store and was not exercised.",
    "Commits blocked by worktree index.lock filesystem permissions."
  ],
  "needs_human": []
}
```
