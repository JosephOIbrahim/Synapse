## What / why

Repair round for `salvage/bp2-nits` after the refuter blocked it. The two DONE stamps in `docs/MONETA_FOLLOWUPS.md` cited `tests/test_memory_models.py` for pins that file does not contain — exactly the evidence-path class this salvage exists to fix.

**Commit 64aed526 — `docs/MONETA_FOLLOWUPS.md` (3 citation fixes)**

- FU-2 status paragraph (was L87-90): `(verified in tests/test_memory_models.py MonetaBackedStore tests)` → `(pinned by tests/test_sleep_pass_gate.py::test_sleep_pass_constant_is_approve, ::test_tool_maps_to_sleep_pass_operation, ::test_rejecting_gate_blocks_the_prune)`.
- FU-2 status-table row: `test_memory_models.py (gate rejection blocks prune)` → `test_sleep_pass_gate.py::test_rejecting_gate_blocks_the_prune`.
- FU-1 status paragraph: `(... assertion in tests/test_memory_models.py)` → `(... assertion at tests/test_moneta_crucible.py:257; id-generation order pinned by tests/test_memory_models.py::test_defaulted_created_at_participates_in_id)`.
  - **One deliberate deviation from the refuter's prescribed text:** it said `:244`. Line 244 is the `def test_repeat_deposits_...` line; the `assert s.count() == len(s.all()) == 2` is at **257** (`grep -nE 'count\(\) *== *len' tests/test_moneta_crucible.py` → 257). I cited the assert line, since a line cite that lands on the wrong line is the same bug in miniature.

**Commit 84354f85 — `prove_bp2_meter_dryrun.ps1` (optional item, comment-only)**

Added a SCOPE header: the edited side is the working-tree `harness/orchestrate.ps1`, so the script is a true BP2-METER before/after proof only when run at `1c2b78fd`; `orchestrate.ps1` changed again at `882eec6b` (`git log --oneline 7fc09482..master -- harness/orchestrate.ps1` → 882eec6b, 1c2b78fd). Chose the header over re-pinning the edited side to `git show 1c2b78fd:...` because that would turn a working-tree proof into a fixed-history replay and change the script's behaviour; the header keeps it honest without executing anything new. Parser check: 0 errors. **Not executed.**

## Evidence

Refuter's claims re-verified before editing:
- `grep -cE MonetaBackedStore tests/test_memory_models.py` → `0`
- `grep -nE '^def test_' tests/test_memory_models.py` → only the 5 id-generation tests (L22/32/38/47/52)
- `grep -nE '^def test_' tests/test_sleep_pass_gate.py` → `test_sleep_pass_constant_is_approve` L35, `test_tool_maps_to_sleep_pass_operation` L43, `test_rejecting_gate_blocks_the_prune` L53
- `grep -nE 'test_memory_models\.py' docs/MONETA_FOLLOWUPS.md` after edit → one hit, L55, the correct `::test_defaulted_created_at_participates_in_id` cite

Tests (all serial, targeted files only, no full suite):
- refuter set 1: 29 passed
- builder set: 49 passed
- `test_sleep_pass_gate.py`: 7 passed
- refuter's required re-run (`test_sleep_pass_gate.py test_memory_models.py test_moneta_crucible.py`): **43 passed, 0 failed**

`git log salvage/bp2-nits..HEAD --oneline` → 84354f85, 64aed526. `git merge-base --is-ancestor salvage/bp2-nits HEAD` → rc=0 (strict fast-forward). Working tree clean after commit.

## The ruling the human must give

**The fixups live on `salvage/bp2-nits-repair` (HEAD 84354f85), not on `salvage/bp2-nits` itself.** `git checkout salvage/bp2-nits` and `git branch -f salvage/bp2-nits HEAD` were both refused: `fatal: cannot force update the branch 'salvage/bp2-nits' used by worktree at 'C:/Users/User/SYNAPSE/.claude/worktrees/wf_4ef50c87-4e2-5'`. I did not bypass with `update-ref` — that would leave worktree -5's index stale against its own HEAD and make its working tree look like it reverts these fixes. Two-commit fast-forward, so either:
1. once worktree `wf_4ef50c87-4e2-5` is released: `git branch -f salvage/bp2-nits salvage/bp2-nits-repair` and drop the repair branch, or
2. put `salvage/bp2-nits-repair` in the merge train in place of `salvage/bp2-nits` (same content plus the 2 fixups).

## What was NOT checked

- Full `pytest tests/` and the hython seat suite (law: parent/CI run those serially).
- `prove_bp2_meter_dryrun.ps1` was parse-checked, not executed.
- State of worktree `wf_4ef50c87-4e2-5` (git -C refused by isolation); left untouched.
- `docs/MONETA_FOLLOWUPS.md:23` still carries the pre-existing absolute path `C:\Users\User\SYNAPSE\tests\test_moneta_crucible.py` (on master, out of this branch's scope per the refuter — separate one-liner on a public repo).
- No rebase onto master 329bd5b3: master moved one commit past merge-base d8ebb74a (adds `harness/design_review/2026-09-14/RULINGS-OPEN.md`); `git diff --stat master..HEAD` therefore shows a spurious -585 for that file which is master content, not a branch change. Diff stats above use the merge-base.
- Tool count untouched; `tests/test_phase0c_doc1_toolcount.py` passed inside refuter set 1.

🤖 Generated with [Claude Code](https://claude.com/claude-code)