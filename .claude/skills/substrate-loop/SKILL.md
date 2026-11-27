---
name: substrate-loop
description: Plan, launch and review a long unattended improvement run on one of SYNAPSE's memory substrates (Moneta, SALUS, Hanish, Octavius, the SALUS-Moneta shim), with a local Ollama model doing the iterations. Use for "/substrate-loop plan <target>", "/substrate-loop review", or when Joe asks to improve a substrate overnight without spending tokens.
---

# Substrate loop: conductor

You plan and you review. The local model does everything in between.
Read `harness/substrate_loop/CLAUDE.md` first; it is short.

## plan <target>

1. Read `harness/substrate_loop/targets.json` for the target's gates and frozen paths,
   and the target repo's own CLAUDE.md or blueprint. Skim; do not ingest the repo.
2. Pick ONE mission with a number the loop can measure (`ruff`, `mypy`,
   `pytest_failed`, or a `command` that prints a value). Smallest useful `focus`.
   Copy `missions/_template.json`; write it to `missions/<id>.json`.
3. Run `python harness/substrate_loop/loop.py doctor --mission <id>` and fix what it reports.
4. Show Joe the mission in a few sentences: objective, metric and its baseline if
   you measured it, focus, budget. Name the one judgment call in it. Wait for his go.

## launch

Tell Joe the one command, to run in his own terminal:
`python harness/substrate_loop/loop.py run --mission <id>`.
If he asks you to start it instead, run it as a background command and end your turn.
Never poll it.

## review

1. `python harness/substrate_loop/loop.py status`, then read the run's `REVIEW.md`.
2. For each kept commit, read the diff (`git -C <worktree> show <sha>`). Judge it:
   genuine, gaming the metric, or needs Joe's eyes. Check it against the
   substrate's locked decisions.
3. Write `REVIEW_VERDICT.md` next to `REVIEW.md`: one line per commit with your call and why.
4. Tell Joe the branch, the commits you would take, and anything that worried you.
   Never merge, push, rebase or cherry-pick. That is his, per commit.
