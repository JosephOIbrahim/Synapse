## Do not open this PR until PLAN Stop 4 decision #1 is answered MERGE

`harness/notes/closeout-2026-09-15/PLAN.md:133` — *"Do not start this stop until the §2.3 question is answered."* Decision #1 at `PLAN.md:465`: **MERGE** a kernel with zero producers and zero consumers, or **HOLD** on the CLAUDE.md §2.3 precedent (*"a production caller must exist first"*). No ruling is recorded anywhere under `harness/notes/closeout-2026-09-15/` or `harness/notes/first-principles-2026-09-15/` (grep for `decision #1|§2.3|ruling.*(MERGE|HOLD)|pgdrm.*(HOLD|MERGE)` returns only the question itself and the deck slide). **Ruling: ________ (MERGE / HOLD).** If HOLD, close this without merging; the branch is safe to leave (two new files, clean merge-tree, nothing master-side touched).

## What this branch is

The M2 PG-DRM kernel (`python/synapse/loop/pgdrm.py`, 409 lines) and its test file (`tests/test_pgdrm_kernel.py`, 693 lines), rebased onto master `329bd5b3` as `dabf9a68`, plus the crucible repair `63c06d2e` that sat uncommitted in `synapse-m2-pgdrm-wt` until the 2026-09-15 first-principles audit found it (AUDIT.md:41, P10 row). Master has no `pgdrm.py` and no `test_pgdrm_kernel.py`; both files are new; `git merge-tree --write-tree master HEAD` → `212ab4a3`, exit 0, no conflicts.

## Repair round (this pass)

The refuter blocked on the fix commit's message: `52b4b86f` said only "commit the M2 kernel repair that sat uncommitted in the worktree" and named neither defect nor the API-contract change. That commit is now **amended, message only**, to `63c06d2e`:

- subject `fix(pgdrm): REFUSE one-shot iterables; cover the str/Iterable guards the crucible left untested`
- body names **defect 1**: `_reiterable()` raises `TypeError` when `iter(x) is x` on `task_context_tokens`, `records`, and `MemoryRecord.tokens` — materializing does not repair it, refusal is the contract; and states the **CONTRACT CHANGE**: generators passed to `evaluate()`, `filter_records()` or `MemoryRecord(tokens=...)` now raise instead of answering differently per call (on e4730869: ALLOW then DROP with the same argument; `('a',)` kept then `()`; DROP then ALLOW for one record inside one call)
- body names **defect 2**: mutation X25 (delete the `str`/`Iterable` guard in `_token_set`) survived the whole suite; e4730869 lines 201 / 231 / 263 had no covering test; new tests pin X25 (`match="must be an iterable of str"`), X23 (`records` Iterable guard, `match="records must be an iterable"`), X17/X18 (`_reiterable` on tokens / records), X19 (`__post_init__`), and the `evaluate` MemoryRecord guard (line 263)
- ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`

Amend was permissible: `git ls-remote --heads origin rebase/m2-pgdrm` returned nothing — the branch was never pushed. Tree identity: `git rev-parse 'HEAD^{tree}'` = `git rev-parse '52b4b86f^{tree}'` = `1cc896a3`.

**Ref caveat.** `rebase/m2-pgdrm` is checked out in worktree `wf_4ef50c87-4e2-3`, so git refuses to check it out or force-move it from another worktree. The amended commit lives on the sibling ref **`rebase/m2-pgdrm-reworded` @ `63c06d2e`**; `rebase/m2-pgdrm` still points at `52b4b86f` (same tree, old message). On MERGE, a human either removes worktree `4e2-3` and runs `git branch -f rebase/m2-pgdrm 63c06d2e`, or pushes `63c06d2e:refs/heads/rebase/m2-pgdrm` directly. Do not push `52b4b86f` — origin is PUBLIC and the next reader inherits the message.

## Evidence

| check | command | result |
|---|---|---|
| builder tests | `python -m pytest tests/test_pgdrm_kernel.py -q -p no:cacheprovider` | 86 passed, 2 warnings, 0.47s |
| composed regression (refuter's file) | `python -m pytest tests/test_loop_contracts.py -q -p no:cacheprovider` | 20 passed, 2 warnings, 0.37s — `:183-184` still pins `MemoryPort().query_and_filter` UNAVAILABLE naming PG-DRM: nothing consumes this kernel yet |
| env | `env \| grep -E '^(MONETA_SRC\|PXR_PLUGINPATH_NAME)='` | unset; Python 3.14.2, pytest 8.4.2 |
| merge | `git merge-tree --write-tree master HEAD` | `212ab4a3`, exit 0 |
| scope | `git diff --name-only master...HEAD \| grep -nE '^(VERSION\|harness/state/\|\.claude/\|CLAUDE\.md\|README\.md\|python/synapse/core/gates\|python/synapse/server/)'` | no match (grep exit 1) |
| diff | `git diff --stat master...HEAD` | 2 files changed, 1102 insertions(+) |
| log | `git log master..HEAD --oneline` | `63c06d2e` fix, `dabf9a68` feat |
| claim audit | `git show 52b4b86f \| grep` for `_reiterable\|TypeError\|X23\|X25`; `git show dabf9a68:python/synapse/loop/pgdrm.py \| sed -n '201p;231p;263p'` | every statement in the new message maps to a line in the diff; 201 = `_token_set` str-guard raise, 231 = decay overflow branch, 263 = `evaluate` MemoryRecord-guard raise |

## Not checked

- Whether the +264 test lines cover e4730869 line 231 (the decay overflow branch `raw = 0.0 if (lam > 0.0 and age > 0.0) else 1.0`); the message cites the crucible's list of three, and claims tests only for 201 and 263.
- The 28-mutation harness (`harness/memory/runs/2026-08-22/m2fix_mutate_harness.py`, verdicts.json action step 7) was not re-run on the rebased tree.
- The full suite (`pytest tests/`) — forbidden in this round; runs serially on the parent's side and on CI.
- Whether a ruling exists outside this tree (the main checkout's uncommitted state, PR #82's roster, or Joe's head). Only `harness/notes/` in this worktree was searched.
- The post-merge bookkeeping in `PLAN.md:149` (`harness/memory/STATE.json` rungs.m2, `harness/memory/bus/memory_m2_pgdrm_kernel.json`) — out of scope and under `harness/state`-adjacent paths.

## Non-blocking nit for a follow-up (not this PR)

`Verdict` and `FilterResult` are `frozen=True` dataclasses carrying a mutable `detail: Dict` — `hash(verdict)` raises `TypeError` and `detail` is externally mutable; `evaluate` also re-runs `_token_set` on `record.tokens` that `__post_init__` already froze (harmless).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

## CTO ruling (pre-approved 2026-09-15; overrule by comment)

**HOLD — draft PR, do not merge.** Zero producers and zero consumers on master (`git grep pgdrm -- python` finds only the kernel); CLAUDE.md §2.3 retired the last mechanism that merged ahead of a caller. The rebased branch (`rebase/m2-pgdrm-reworded`, commit message corrected per the refuter) is preserved here so the M3 rung that would call it can land against it. Flip to ready when a caller exists.
