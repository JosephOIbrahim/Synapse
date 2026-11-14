# CLAUDE.md: substrate loop (conductor conventions)

Short on purpose. Short = cached = cheap.

- **You conduct, the local model works.** Spend tokens on PLAN and REVIEW only.
  While `loop.py run` is going, do not poll it: end your turn. The run writes
  `runs/<id>/DONE` or `FAILED` last; read `REVIEW.md` then.
- **One mission at a time.** `loop.py` refuses a second live run (exit 4).
- **Never touch Houdini's lane.** The loop refuses to start while Houdini is
  running and pauses between iterations if it opens. Never work around it.
- **A green candidate is not an improvement.** Every kept commit passed every
  gate and moved the number. Read each diff for gaming before recommending it.
- **Promotion is Joe's, per commit.** Never merge, push, rebase or cherry-pick a
  loop branch. Report the branch and the commits you'd take.
- **Model names live in `tiers.json` only.** Swap models there, nowhere else.
- **`program.md` is Joe's.** If it is wrong, say so; do not edit it.
