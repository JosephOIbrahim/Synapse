# Release record — v5.103.0

**Prepared 2026-11-18; committed and pushed, not tagged or published.** The Gates
table below is the authoritative state.

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
| Suite on the release tree | PASS — 13,028 / 0 / 727 on `d7c5b679`, `run-stock-tree.sh`, EXIT=0, tree clean |
| CI on the pushed head | PASS — run 44415007384, all six jobs `success`, including the four required contexts |
| Version propagation | PASS — `sync_version.py --write`, `canonical=5.103.0 verdict=PASS` |
| **Adversarial read of the diff** | **FAIL — two blockers, thirteen material findings. The review is what `scripts/tag_release.py` requires; it returned FAIL, so no `CRUX-RECORD.json` with `passed: true` is committed here.** |
| **Tag** | **BLOCKED by the gate, not by choice.** `scripts/tag_release.py` refuses with *no closure record for v5.103.0*. |
| Publish | NOT RUN |
| Push to master | RUN — `f6974fdf..d7c5b679` |

### The two blockers

1. `harness/harness2/compositor.py` co-adopted a SIM-refused candidate as a
   secondary: the adoption loop filtered strength, probe support, composability
   and file conflicts, and never consulted `sim_rejects`. The decision could
   read `adopted: [clean, refused]`, falsifying the plane's own headline claim.
   Fixed in this commit; pinned by two tests, one that a refused secondary is
   skipped and one that a clean secondary is still adopted.
2. This file's previous revision reported the adversarial read as "Done" and
   listed the tag command as the next step. Neither was true: the read FAILED
   and the tag is refused. Corrected here.

### The material findings, all fixed in this tree

SIM: cluster citation validated; `REPLACE` counted as retained; the duplicate
rule scoped to the edit; cluster filenames checked against content ids; atomic
cluster writes; torn-tail refusal. Transfer: `created_utc` compared as an instant;
`harness_changed` surfaces as `comparison_invalidated`. Docs: TAGS.md, the README
body, the install guide, the evidence-line wording and the CHANGELOG hook sentence.
The commits are `e102e7a7` (six SIM contracts) and `63545262` (transfer and docs).
A second independent review followed; its surviving findings are fixed in the
commit that carries this note.

## Commands, as actually run

```text
SYNAPSE_GATE_C=1 git commit -F <message>          # f6974fdf release: v5.103.0
git commit -F <message>                           # e59c9420, d7c5b679  (README fixes)
SYNAPSE_GATE_C=1 git push origin release/v5.103.0:master   # f6974fdf, then d7c5b679
python scripts/tag_release.py …                   # REFUSED: no closure record for v5.103.0
```

The tag command is listed last because it is the one that does not work yet, and
a note that implies otherwise is how this release acquired its first red CI run.
