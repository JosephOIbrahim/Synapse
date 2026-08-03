# ROPE HARNESS · OPERATOR CARD

**What this is.** GATE A of the release blueprint, run karpathy/autoresearch-
style: Python orchestrates and verifies (zero tokens), one fresh headless
Claude session edits per task, git keeps or discards, results.tsv logs.

## Run it

    cd C:\Users\User\SYNAPSE
    python harness\rope\runner.py status
    python harness\rope\runner.py run --model <MODEL> --confirm-model

Overnight = that second command. It loops until nothing is eligible.
Add `--max 1` to watch a single task first (recommended for run one).
`--allow-dirty` if tracked files are intentionally dirty.

## While it runs / after

    python harness\rope\runner.py gate                    # GREEN or what's open
    type harness\rope\results.tsv                         # the ledger
    git log --oneline -15                                 # one commit per task

## Your two tasks (agents can't do these)

    python harness\rope\runner.py human L3-2 --done "video embedded"
    python harness\rope\runner.py human L3-5 --done "Apprentice row filled"

## Manual sign-offs (Qt/seat checks)

    python harness\rope\runner.py verify L5-4 --passed
    python harness\rope\runner.py verify L5-10 --passed

## When it breaks

- **Task blocked (2 strikes):** read `results.tsv` note + `last_run.log` tail;
  fix by hand or re-open: edit STATE.json status -> "pending", attempts -> 0.
- **claude CLI errors on flags:** set SYNAPSE_ROPE_FLAGS env to match your
  `claude --help` (default: --permission-mode acceptEdits).
- **Stop it:** Ctrl+C. State is on disk; re-run resumes exactly where it was.

## Where it lives

- harness\rope\ -> program.md (the org file — edit THIS to tune agents),
  STATE.json (task DB), runner.py, results.tsv (untracked), OPERATOR_CARD.md
- .claude\agents\rope-executor.md (Mode 2 subagent)
- Branch: rope/gate-a · one commit per verified task · your untracked files
  are never touched (reset --hard only, no git clean, ever)

## Watch it live

    powershell -ExecutionPolicy Bypass -File harness\rope\watch.ps1

Live dashboard in its own window: runner alive? · gate · non-pending tasks ·
ledger tail · the current agent's output · stderr if any. Refreshes every 5s.
Closing the window never stops the marathon -- it's a separate process.
