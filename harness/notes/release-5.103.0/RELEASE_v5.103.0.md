# Release record — v5.103.0

**Prepared 2026-11-18. Not yet committed, tagged, pushed or published.**

## Candidate

- Base: `origin/master` `2037c268c8a7cb48f86f694d8270b6b375cf4c69` (confirmed against
  `git ls-remote origin refs/heads/master` at preparation time; the remote had not
  moved).
- Content: the four SIM commits, fast-forwarded — no merge commit.
  `19b4c32b` SIM-P2, `5aeb105d` SIM-P3, `5b602450` SIM-P4, `ec121502` SIM-P5.
- Tree at `ec121502`, clean before and after the suite.

## Evidence

Fenced stock suite, `harness/githooks`-era runner `run-stock-tree.sh`, worktree
`C:/synapse-build/rel-51030`, run id `sim-rel51030`:

```
STOCK_START HEAD=ec121502… PY=Python 3.14.2
STOCK_DONE  HEAD_AFTER=ec121502… EXIT=0
TREE_STATE_AFTER clean
= 13028 passed, 727 skipped, 11 deselected, 10 xfailed in 599.88s (0:09:59) =
```

Baseline `v5.102.0` head `2037c268`: 12,940 passed, 0 failed, 727 skipped,
11 deselected, 10 xfailed.

Delta: **+88 passed, 0 failed, 0 skips added, removed or moved.** The 88 are the
five new `tests/test_sim_*.py` files.

Two earlier runs are recorded here and are **not** the evidence: a 3.12 run
(817 skipped — `cv2` absent, a machine difference) and a 3.14 run on the default
testpaths (271 more tests — the harness suites the baseline never collects). The
release line is the fenced 3.14 `tests/` run above.

## Diff

19 files, +2,554 / −16. One product-runtime file: `python/synapse/loop/light_gate.py`,
additive only. `harness2/compositor.py` and `harness/jev/jev_screen.py` gain
keyword-only parameters defaulting to `None`. `harness/sim/` is new and unimported
by the runtime; `tests/test_sim_isolation.py` asserts that.

## Gates

| Gate | State |
|---|---|
| Suite on the release tree | PASS — line above |
| Adversarial read of the diff | Done — limits recorded in `docs/releases/v5.103.0.md` |
| Version propagation | `sync_version.py --write` run; `canonical=5.103.0 verdict=PASS` |
| **Gate C — commit, push, tag, publish** | **OPEN — waiting for the owner's go** |

## Commands, for the gate

```text
# the release commit stages VERSION, which the pre-commit hook refuses without
# the owner's gate variable supplied for this one command
SYNAPSE_GATE_C=1 git commit -F <message>
git push origin release/v5.103.0:master        # after the go
python scripts/tag_release.py …                # annotate and tag on the CI-green commit
python scripts/release_ci_gate.py              # the four test (os, py) contexts must be green
```

Nothing above has been run.
