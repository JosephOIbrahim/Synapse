# RECEIPT stream report — 2026-09-04

Overall disposition: **BLOCKED on Git metadata permissions; code implemented.**
The RECEIPT pytest controls pass. The full-suite attempt stopped at collection
because `websockets` was missing. No live-Houdini qualification is claimed.

Worktree: `C:/Users/User/SYNAPSE/.claude/worktrees/bp5-solaris-receipt`.
Branch: `bp5/solaris-receipt`. Base/remaining HEAD:
`83ec6330857b7305e5b9ee74e74e6d92d4155200`.

## Requirement → result

| Brief / blueprint reference | Status and producer |
|---|---|
| D1; p04/p09 complete receipt context | Implemented through frozen `RunReceipt` seam; `receipt.py:105` validator and `:187` construction helpers. No seam edit. |
| D1; exact round-trip, enums as values | `receipt.py:148`/`:166`; nested tuple tags preserve tuple versus list identity and escape colliding mapping keys. `test_recipe_receipt.py:41` includes exact JSON round-trip controls. |
| D1; reason on every non-VERIFIED result | `validate_receipt`; checks also require a non-PASS reason. Missing predicates cannot certify VERIFIED; recovery remains separate. |
| D1; immutable append-only ledger | `ReceiptStore` at `receipt.py:207`; existing byte prefix retained, file fsync, sibling `.tmp`, atomic replace, cross-process exclusive `.lock`. Same-run retry compares canonical JSON bytes, distinguishing `1`, `1.0`, and `true`. Conflicting or truncated history fails closed. |
| D2; p09 freshness and T12 | `EvidenceTracker` at `freshness.py:39`; current observed fingerprint AND continuous tracking since completion required. Scene load/undo/redo/owned/dependency edits invalidate. Gaps and missing observations remain UNKNOWN. |
| D2; no full-stage hash per frame | `freshness.py` module/hook docstrings; injected scoped observation, two-second default / one-second minimum enforced on periodic hooks, including failures. No stage hashing or host calls in these modules. |
| D3; p09 minimum card and visible blocked offers | `make_card` at `card.py:68`; registry offer, scope, six per-check evidence records, four independent dimensions, approval/recovery, one reason/next action. BLOCKED without reason rejects; missing evidence is NOT_RUN. |
| D3; scope change reapproval | `ApprovalScope` at `card.py:25`; exact six-field binding plus current instance revision; no authority granted by rendering. In-flight job stays RUNNING while next changed scope requires approval. |
| D3; p09/S8 cache plan only | `SpecCache` at `card.py:164`; full compiled-spec digest, declarative-type whitelist, nested outcome rejection, detached data. Negative control uses independently computed VALID digest so a digest mismatch cannot mask a broken outcome guard. |
| D3; T11 request/job dedup | `RequestDedup` at `card.py:201`; atomic claim before effect, pending/approval/running/terminal retries observe same job, payload reuse refuses, exception retains RUNNING, render receipt must match tracked job. |
| D4; pure plain/rich text | `panel/recipe_card.py:59` and `:77`; HTML escaped, STATUS/SURFACE/TYPE_ROLES/SPACE_SM supplied from existing vendored tokens. No top-level or lazy Qt/host import. Stale VERIFIED history is labelled and never green. |
| D4; panel and router hookup | `HOOKUP_RECEIPT.md` supplies exact unapplied unified diffs and host adapter sequence. Both diffs pass `git apply --check` with UTF-8 byte input. |
| D5; T12, cache, retry and negative controls | `test_recipe_card.py`, `test_recipe_receipt.py`, independent `test_recipe_card_review.py`, and rerunnable mutation script `test_recipe_card_mutations.py`. Final verification record below. |

## Files changed

New product files: `python/synapse/recipes/receipt.py`, `freshness.py`, `card.py`,
and `python/synapse/panel/recipe_card.py`.

New tests: `tests/test_recipe_receipt.py`, `tests/test_recipe_card.py`,
`tests/test_recipe_card_review.py`, `tests/test_recipe_card_mutations.py`.

New handoff/evidence: `docs/solaris_v3/HOOKUP_RECEIPT.md`, this report, and
`harness/solaris_v3/STATUS_RECEIPT.md`. Git status shows these new files only;
`git diff --name-only` shows no modifications of existing tracked files.

## Verification and provenance

Python: `C:/Python314/python.exe`, 3.14.2. Final pytest observed: 8.4.2. Tests
resolve `synapse` from this worktree via repository pytest configuration. The
isolated import control additionally asserts the loaded receipt module path,
no `hou`, no `pxr`, and no Qt modules in a fresh process. No fake `hou` was added
by this stream; existing full-suite conftest behavior was not modified.

Initial `python -m pytest tests/test_recipe_receipt.py -q -p no:cacheprovider`
failed before collection: `No module named pytest`. Python 3.11 also lacked
pytest; the installed 3.13 launcher was denied execution. Later the same default
Python could import pytest. This worker performed no installation. Early
milestones used the same unittest-based controls with the standard-library
runner and recorded their actual results in STATUS.

Full-suite command, run once:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests -q -p no:cacheprovider
```

Observed: **7113 collected, 0 test cases executed, 0 passed, 0 assertion
failures, 3 collection skips, 5 collection errors**, interrupted during
collection after 11.66 seconds. All five errors are
`ModuleNotFoundError: No module named 'websockets'`:

- `tests/test_load.py:18`
- `tests/test_passthrough_hygiene.py:41` → `mcp_server.py:46`
- `tests/test_port_wave_scene1.py:36` → `mcp_server.py:46`
- `tests/test_websocket_cancel_inflight_known_defect.py:33`
- `tests/test_websocket_cancel_reachable.py:31`

The pass-count ratchet is **UNKNOWN**, not green: `BASELINE.md` records 7131
collected and 6942 historically green, but no completed base full-run counts in
this worktree. A collection interruption cannot establish preservation of that
floor. These errors originate outside this stream's write set; no unrelated
assertion was weakened or file changed to hide them.

### Independent crucible

The `/root/receipt_crucible` reviewer wrote only
`tests/test_recipe_card_review.py`; the builder fixed product code. Observed red
before fixes: four initial failures (nested receipt list reinitialization,
compiled-cache digest drift, wrong/missing tracked render-job IDs), then two
additional failures (boolean/integer same-run collision, backdated tracking
reconnect). The reviewer also challenged the periodic-observation failure then
reconnect sequence. Findings and final disposition are recorded in the final
verification appendix.

### Deliberate mutation evidence

Command: `python -B tests/test_recipe_card_mutations.py`.
It changes product source in isolated child module namespaces before importing
the control, without editing repository source or creating a fake host. An
import error does not count as detecting a mutation. Every accepted mutation
produced an assertion failure; the script exits zero only when all controls
actually go red.

| Deliberate break | Observed failure |
|---|---|
| Remove reason validator | ValueError not raised, eight verdict/blank-reason cases |
| Replace atomic publish with direct write | Injected replacement failure no longer reached |
| Make evidence mappings mutable | TypeError not raised |
| Compare every fingerprint as equal | CURRENT instead of STALE |
| Ignore all invalidating events | CURRENT instead of STALE for all five events |
| Ignore incomplete coverage | CURRENT instead of UNKNOWN |
| Remove periodic throttle | Observation ran during enforced interval |
| Bypass approval-scope comparison | Missing AWAITING_APPROVAL for all six scope fields |
| Bypass spec outcome validation | Four poisoned compiled specs incorrectly admitted |
| Return an execution permit on retry | Eight permits instead of one |

## Stricter choices and limits

- The frozen seam is untouched. `make_receipt`/`from_dict` provide detached
  read-only nested snapshots; serialization/store entry points validate even
  directly constructed seam instances. Raw `RunReceipt(...)` remains only
  shallowly frozen because its class is outside this stream's write set.
- Only terminal runs enter the durable receipt ledger. In-flight state belongs
  to the job registry; there is no attempt to edit a persisted line later.
- Invalidation at the exact completion timestamp counts as stale. Naive/missing
  or future completion times cannot become CURRENT. Reconnection never moves
  the known coverage boundary backward. Known invalidations may yield STALE
  despite incomplete tracking; incomplete tracking can never yield CURRENT.
- A full compiled-spec digest includes layout/build/presentation as well as
  semantic graph identity. Metadata values that are live terminal verdicts or
  outcome fields are conservatively rejected, even if offered as presentation.
- Approval comparison in a card is descriptive only. Host authority still owns
  the action permission and final consent check.
- Spec cache is process-local; RequestDedup is host-lifetime transport dedup.
  Host restart recovery requires durable pending-job reconciliation, explicitly
  deferred to the lifecycle/host adapter. Reset/undo must not discard dedup.
- JSONL append is copy-on-append and reads the history for duplicate validation;
  it is intentionally not a high-volume database. Lock contention fails closed;
  a crashed writer's lock is not auto-cleared. File fsync is verified, but
  power-loss directory durability depends on the platform/filesystem.
- Live H22 event coverage, golden HIP reconstruction, actual fingerprints,
  render termination/files, Qt appearance and transport delivery are NOT_RUN.
  No `hou.*`/`pxr.*` symbol is called or introduced in product modules.
- The later swarm contract's exclusive write set overrides the generic AGENTS
  main-tree artifact/bus convention. This report and STATUS carry the receipt;
  no `bus/`, other stream board, or master-tree file was written. Worktree/PID
  sweep found expected other workers; process-commandline inspection was denied.
- Brainstorming/feature skills' additional design-approval loops were superseded
  by the user's supplied design and explicit autonomous implementation order.
  Independent crucible work follows AGENTS §5; it is not a new ownership stream.

## Contract changes, hookups, and outstanding completion work

Contract change requests: **none**. The list/tuple wire tags and approval-scope
adapter live in owned modules; no shared seam field changed. See
`HOOKUP_RECEIPT.md` for the panel/router diffs and explicit host ownership steps.

Every milestone attempted an authorized branch commit, using the requested
`bp5(receipt):` subject and
`Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>` trailer. Every attempt
failed at `git add`/`git commit` with:

```text
fatal: Unable to create 'C:/Users/User/SYNAPSE/.git/worktrees/bp5-solaris-receipt/index.lock': Permission denied
```

The current sandbox permits worktree-file writes but not shared Git metadata.
No approval escalation is available in this session. No Git metadata was
relocated or permission check bypassed. Thus **no commit was created and the
worktree is not clean**; the completion contract is not satisfied. The
orchestrator must commit these reviewed files on this branch in an authorized
environment and rerun the full suite with its dependencies available. Merge,
push, master, VERSION, deployed files and live GUI were not touched.


## Final verification appendix

Final builder AND independent crucible command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest tests/test_recipe_receipt.py tests/test_recipe_card.py tests/test_recipe_card_mutations.py tests/test_recipe_card_review.py -q -p no:cacheprovider
```

Both observed **48 passed, 0 failed, 0 skipped**, with one existing Python 3.14 /
vendored cp311+cp313 ABI warning. Builder elapsed test time: 0.73 seconds.
The full-suite collection failure recorded above preceded the eight additional
crucible controls; it is not represented as a final full-suite green.

Independent disposition: **PASS for reviewed headless scope**, no remaining
concrete findings. The final periodic-failure -> reconnect regression first
produced `CURRENT` instead of `UNKNOWN`; the failure path now advances the same
coverage watermark as every explicit tracking gap. All eight crucible controls
were seen red before fixes or under a deliberate retry-permit mutation.
Producer: `tests/test_recipe_card_review.py` (reviewer authored only that file).

Final mutation replay: `python -B tests/test_recipe_card_mutations.py` returned
zero and emitted ten `RED_OBSERVED` records on the final product code.
Headless import/provenance, same-run immutability, real thread contention, and
scoped reapproval controls are included in the 48-test result. Neither that
result nor the crucible disposition is a live-render or GUI claim.

Hookup applicability was verified without applying either patch by extracting
each `diff` block and passing UTF-8 bytes to `git apply --check -`. Byte input
avoids Windows text-pipe newline conversion; both returned zero. Runtime hookup
is still deferred to integration.

### Source artifact SHA-256

These hashes bind the verification handoff to the uncommitted files; HEAD alone
cannot identify this work while the Git index remains inaccessible.

| File | SHA-256 |
|---|---|
| `python/synapse/recipes/receipt.py` | `ec02e92ce70766d877be5b8396552c13be17c4c9bb5c805c90c4238e3957528f` |
| `python/synapse/recipes/freshness.py` | `30a649abf574b1b5208751a9023a1f5fe2f0038f9e64d3ddbbcbce07e8016984` |
| `python/synapse/recipes/card.py` | `be8d61cb28aee880e96f89df41e42bada1b0d1cc095bb3b416dccb0bf350d223` |
| `python/synapse/panel/recipe_card.py` | `9943cbf805015e9b9dac8a764d779095cb1795b2a7f40dc5d6590df2a5b494bf` |
| `tests/test_recipe_receipt.py` | `1581042cadf49cf2b78ec6e87012b4c6dcd22a341b908214999b1053e6ca2552` |
| `tests/test_recipe_card.py` | `095c083247869476175054ef0caf5e00604017b1292e57127c0e8a41cc8cd724` |
| `tests/test_recipe_card_mutations.py` | `dadb8eb9e3b4793263b906d742d767857ecfe624ae51287ce642bd1fdc9dac94` |
| `tests/test_recipe_card_review.py` | `a01230b50c1aab77c4fa53d34b17307af433f42271e87f21f774444fb20bfbfc` |
| `docs/solaris_v3/HOOKUP_RECEIPT.md` | `c323524a0e9e953bce9cc0bbdedc951a10c17d16d4da43cb32518f319a82f058` |

### Durable stream receipt

```json
{
  "artifacts": [
    "docs/solaris_v3/REPORT_RECEIPT.md",
    "docs/solaris_v3/HOOKUP_RECEIPT.md",
    "harness/solaris_v3/STATUS_RECEIPT.md"
  ],
  "blocked_by": [
    "Git index.lock creation is denied outside writable root; approval escalation is unavailable."
  ],
  "branch": "bp5/solaris-receipt",
  "commands": [
    "python -m pytest tests/test_recipe_receipt.py tests/test_recipe_card.py tests/test_recipe_card_mutations.py tests/test_recipe_card_review.py -q -p no:cacheprovider",
    "python -B tests/test_recipe_card_mutations.py",
    "python -m pytest tests -q -p no:cacheprovider",
    "git status --short",
    "git diff --name-only"
  ],
  "could_not_verify": [
    "Full-suite pass floor: five collection errors from missing websockets; 3 collection skips, no test bodies executed.",
    "Commits/clean worktree: shared Git index writes denied by sandbox.",
    "H22 golden scene, event/fingerprint adapters, renderer jobs/files, live Qt surface, and applied router/panel integration.",
    "Dedup across host restarts and filesystem power-loss directory durability."
  ],
  "head": "83ec6330857b7305e5b9ee74e74e6d92d4155200",
  "leg": "solaris_v3:bp5:RECEIPT",
  "needs_human": [],
  "next_owner": "Integrator: commit reviewed RECEIPT files on this branch, install no substrate on this worker's behalf, apply reviewed hookup under authorized integration, rerun full suite in established test environment.",
  "proved_it_bites": "Ten source mutations observed red; eight independent crucible controls observed red before fixes or under retry-permit mutation; final targeted pytest 48 passed.",
  "recorded_at": "2026-09-04T20:16:26.851236-04:00",
  "touched": [
    "python/synapse/recipes/receipt.py:1",
    "python/synapse/recipes/freshness.py:1",
    "python/synapse/recipes/card.py:1",
    "python/synapse/panel/recipe_card.py:1",
    "tests/test_recipe_receipt.py:1",
    "tests/test_recipe_card.py:1",
    "tests/test_recipe_card_mutations.py:1",
    "tests/test_recipe_card_review.py:1",
    "docs/solaris_v3/HOOKUP_RECEIPT.md:1"
  ],
  "verdict": "BLOCKED"
}
```
