## What / why

One new file, `harness/notes/backlog/H-MATRIX-contract.md` (the `backlog/` directory did not exist; created). It records the contract `wip/panel-goalposts` wanted from `.synapse/hytest.py` so the idea survives the branch's archive-and-delete, without merging the salvage test.

Pointer: `harness/notes/closeout-2026-09-15/PLAN.md` row `wip/panel-goalposts` (OVERTURNED from ARCHIVE_DELETE to SPLIT_SALVAGE) and `harness/notes/first-principles-2026-09-15/AUDIT.md` row `wip/panel-goalposts` (PARK / RECORD, never merge as-is). The room's finding: `tests/panel/test_hython_matrix.py` asserts a `SYNAPSE_HYTHONS` parser master does not have, and its own docstring says it "FAILS NOW" — merging it is a guaranteed red against the 8869/0 floor.

The note contains:
1. The branch's module docstring quoted verbatim as the spec (the comma/semicolon `SYNAPSE_HYTHONS` matrix; pass iff all builds pass; unresolvable targeted build = hard error; unset = today's behaviour).
2. What `.synapse/hytest.py` does today on master — `:100` is the singular `os.environ.get("SYNAPSE_HYTHON")`; single-best resolution rules 1–4; entry points `_candidates` `:87`, `_candidates_with_reason` `:98`, `_usable` `:120`, `find_hython*` `:133/:144`, `main` `:148`; no per-build loop, no aggregation, no token-to-path resolver.
3. What a future implementation must satisfy — the four seams the test discovers by `getattr` (parser / resolver / per-build run / matrix driver) with their accepted names, signatures, and behaviours (both separators, whitespace and trailing-separator handling, run every build with no short-circuit, nonzero on any failure or any unresolvable target, module-level so `setattr` patching works), plus the compatibility constraints (`_candidates()` plain strings for `scripts/solaris_v3_accept.py`, stock-CPython only). Also flags one open design point the branch predates: rule 3 (symbol-table stamp, B10 2026-09-05) — a matrix must not let a pass on an unstamped build read as "verified".
4. Branch disposition: tip `c3a603240407df51918aebed1b41c6dbbce4a6d0` (2026-06-24), merge-base `2e8ddd3a`, 2 unapplied commits, 8 files / +1130; archive tag to create `archive/wip-panel-goalposts` at `c3a60324` (does not exist yet), with the PLAN.md:425–428 steps including the tag push the original verdict omitted. Origin push-delete stays PLAN ruling 6.

## Evidence

- `git checkout -b park/panel-goalposts master && git status --short --branch` → `Switched to a new branch 'park/panel-goalposts'` / `## park/panel-goalposts`
- `git log -1 --format='%H %ad %s' --date=short wip/panel-goalposts` → `c3a603240407df51918aebed1b41c6dbbce4a6d0 2026-06-24 test(panel): WIP goalposts — model-picker, ollama, hython-matrix, type-scale`
- `git rev-parse master` → `d8ebb74a7abbb719850e8616610c17bb4f0ce4d5`; `git merge-base master wip/panel-goalposts` → `2e8ddd3a6f94922dc2eed72e9574d205b5b470b1`; `git log --oneline master..wip/panel-goalposts` → 2 commits (`c3a60324`, `91fe5b1e`)
- `git show wip/panel-goalposts:tests/panel/test_hython_matrix.py | head -40` → docstring quoted verbatim in §1 of the note
- `grep -n 'def \|SYNAPSE_HYTHON' .synapse/hytest.py` → `100: pinned = os.environ.get("SYNAPSE_HYTHON")`, `102: yield pinned, "SYNAPSE_HYTHON pin"`, entry points at :87/:98/:120/:133/:144/:148
- `git grep -n SYNAPSE_HYTHONS master` → hits only inside `harness/notes/closeout-2026-09-15/*` and `first-principles-2026-09-15/*` (the closeout notes themselves); zero in code or tests. `git grep -n SYNAPSE_HYTHONS wip/panel-goalposts` → `tests/panel/test_hython_matrix.py:5, :9, :55, :82, :88`
- `git tag -l 'archive/*'` → 20 tags, none named `archive/wip-panel-goalposts`
- `git diff --stat master...wip/panel-goalposts` → `8 files changed, 1130 insertions(+)`
- `git commit -F msg.txt` → `[park/panel-goalposts 87d8d5c4] ... 1 file changed, 109 insertions(+)`; `git log master..HEAD --oneline` → 1 commit; `git status --short --branch` → `## park/panel-goalposts` (clean; the temporary msg.txt was removed before status)

## Ruling needed

none

## NOT checked

- No tests were run — the task named none. The branch's `test_hython_matrix.py` was not executed (it fails by design on master).
- No hython was spawned; master's resolver was not re-probed against the two installed 22.0.x builds (22.0.400 / 22.0.429).
- The archive tag was NOT created and no branch was deleted or pushed — those are the human's acts per the LAWS and PLAN.md:425–428.
- Whether `scripts/solaris_v3_accept.py:hython_candidates` is the only consumer of `_candidates()`'s plain-string shape.
- Tool count: not touched, not re-derived (out of scope for this branch).

🤖 Generated with [Claude Code](https://claude.com/claude-code)