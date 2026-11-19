# Release record — v5.103.0

**Prepared 2026-11-18. This record describes the state at the commit that carries
it, before the tag and the release page exist.** The Gates table is authoritative
for that snapshot and for nothing later: the moment a tag and a page exist, the
Tag and Publish rows below are superseded, and the tag is the authority.

## Candidate

- Base: `origin/master` `2037c268c8a7cb48f86f694d8270b6b375cf4c69` (confirmed against
  `git ls-remote origin refs/heads/master` at preparation time; the remote had not
  moved).
- Content: the four SIM commits, fast-forwarded — no merge commit.
  `19b4c32b` SIM-P2, `5aeb105d` SIM-P3, `5b602450` SIM-P4, `ec121502` SIM-P5.
- Tree at `0bb06001`, clean before and after the suite. Every commit after
  `ec121502` is in the release range `ec121502..HEAD` — read it with
  `git log --oneline ec121502..HEAD` rather than a count here, because a count
  written into this file changes with the commit that writes it. The suite
  numbers below are the shipping tree's; the evidence paragraph names the commit
  that ran.

## Evidence

Fenced stock suite, `run-stock-tree.sh`, worktree `C:/synapse-build/rel-51030`,
run id `sim-rel51030-minors2`:

```
STOCK_START HEAD=0bb06001… PY=Python 3.14.2
STOCK_DONE  HEAD_BEFORE=0bb06001… HEAD_AFTER=0bb06001… EXIT=0
TREE_STATE_AFTER clean
= 13057 passed, 727 skipped, 11 deselected, 10 xfailed in 513.80s (0:08:33) =
```

Baseline `v5.102.0` head `2037c268`: 12,940 passed, 0 failed, 727 skipped,
11 deselected, 10 xfailed.

Delta: **+117 passed, 0 failed, 0 skips added, removed or moved.** The 117 are the
cases the five new `tests/test_sim_*.py` files collect (110 `def test_` functions
plus 7 extra cases from two parametrizations).

Two earlier runs are recorded here and are **not** the evidence: a 3.12 run
(817 skipped — `cv2` absent, a machine difference) and a 3.14 run on the default
testpaths. The release line is the fenced 3.14 `tests/` run above.

## Diff

**20 files, +2,985 / −19 over the code and test paths** —

```
git diff --shortstat 2037c268..HEAD -- python harness/sim harness/harness2 harness/jev harness/bench tests
```

The pathspec is deliberate. `harness/notes/` and `docs/` are outside this
pathspec, so this file and the release note cannot move the figure. What the
pathspec does still contain is documentation that lives inside the code tree —
`harness/sim/ledger/README.md` is one of the 20 files, and `harness/jev/README.md`
and vendored `python/**/*.md` are tracked too — so an edit to those would move
it. Measured with this pathspec the figure is identical at `0bb06001`, at
`78483670` and at HEAD.

Two product-runtime files: `python/synapse/loop/light_gate.py`, additive only,
and `python/synapse/__init__.py`, whose two lines are the version string. `harness2/compositor.py` and `harness/jev/jev_screen.py` gain
keyword-only parameters defaulting to `None`. `harness/sim/` is new and unimported
by the runtime; `tests/test_sim_isolation.py` asserts that.

## Gates

| Gate | State |
|---|---|
| Suite on the release tree | PASS — 13,057 / 0 / 727 on `0bb06001`, `run-stock-tree.sh`, EXIT=0, tree clean |
| CI | Run 44415007384 on `d7c5b679` (all six jobs `success`) and run 44408737718 on `f6974fdf` (six of six failed on the README pointers) are both in this branch's history — `d7c5b679` is `origin/master` and an ancestor of `release/v5.103.0`. No CI has run on any commit after `d7c5b679`; those are the commits this branch adds and they are unpushed. The run id for the tip is recorded here once the push produces one. |
| Version propagation | PASS — `sync_version.py --write`, `canonical=5.103.0 verdict=PASS` |
| **Adversarial read of the diff** | **FAIL — two blockers, thirteen material findings. The review is what `scripts/tag_release.py` requires; it returned FAIL, so no `CRUX-RECORD.json` with `passed: true` is committed here.** |
| **Tag, at this commit** | **BLOCKED by the gate, not by choice.** `scripts/tag_release.py` refuses with *no closure record for v5.103.0*. |
| Publish, at this commit | NOT RUN |
| Push to master, at this commit | RUN — `f6974fdf..d7c5b679` |

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
The commits are `e102e7a7` (six SIM contracts) and `63545262` (transfer and docs),
with `e277f802` closing the co-adoption blocker. The commits after `413aefb3`
carry the later reviews' fixes: `git log --oneline 413aefb3..HEAD`.

## Commands, as actually run

```text
SYNAPSE_GATE_C=1 git commit -F <message>          # f6974fdf release: v5.103.0
git commit -F <message>                           # e59c9420, d7c5b679  (README fixes)
SYNAPSE_GATE_C=1 git push origin release/v5.103.0:master   # f6974fdf, then d7c5b679
python scripts/tag_release.py …                   # REFUSED: no closure record for v5.103.0
```

The tag command is listed last because at the time of writing it was the one that
did not work — `scripts/tag_release.py` refuses without a committed
`CRUX-RECORD.json`, as it did then. Once a passing record is committed on top of
this tree, that command runs. A note that implies it works now would be the same
error that produced this release's first red CI run.
