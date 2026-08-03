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

### Relaunch-proof watch (use this from now on)

    double-click  harness\rope\watch.cmd

Windows terminal-restore can mangle a saved powershell command line into one
unfindable filename (error 0x80070002). The .cmd resolves its own folder, so
that failure class is dead. Also: the runner now refuses to start while a
Houdini process is alive -- close Houdini or pass --live-seat-ok consciously.

### 20-minute progress pushes

    double-click  harness\rope\notify.cmd

Every 20 min: a Windows toast + one digest line in its ticker window and in
harness\rope\PROGRESS.md (runner alive? · done this interval · gate · in
flight). First digest fires the moment you launch it. Read-only; close anytime.
For a full narrated read with receipts: ping Claude with anything at all.

### Design conformance (L5-11) -- staged, NOT auto-running

New panel UI (the L5-4 tab strip especially) is built structurally, not
designed. `python/synapse/panel/designsystem/` is the source of truth and its
own docstring records that an audit already found THREE divergent token
sources. L5-11 is a CONFORM-DO-NOT-INVENT pass, staged deliberately so it runs
with you at the desk:

    python harness\rope\merge_pending.py     (only when no runner is looping)
    python harness\rope\runner.py run --model claude-fable-5 --confirm-model --live-seat-ok --task L5-11

It machine-checks token conformance (no raw hex, no bare px) and ends at
needs_review, because visual judgement is not delegable.

### /remote-control (rc.cmd) -- steer from your phone

    double-click  harness\rope\rc.cmd        (or it may already be running)

Outbound only, two jobs:
1. BEACON -- pushes STATUS.md (gate + ledger + runner state) to branch
   rope/beacon every ~5 min. Read it anywhere:
   https://github.com/JosephOIbrahim/Synapse/blob/rope/beacon/STATUS.md
2. SENTINEL -- if the runner quota-paused with tasks pending, relaunches it
   automatically (max 6 times). Uses ledger evidence, not process guesswork.

It executes nothing FROM the repo -- no inbound command channel exists. If you
ever want one (edit a file on GitHub -> machine obeys), that's a deliberate
security decision to define together first, not a default.

### Token-limit mode: run the rope on YOUR local models (zero API tokens)

    $env:SYNAPSE_ROPE_ENGINE = "ollama"
    python harness\rope\runner.py run --model qwen2.5-coder:32b --confirm-model --live-seat-ok

Any model `ollama list` shows works as --model. Same accepts, same commits,
same ledger -- the judge doesn't care who edited. Honest scope: local models
handle small files well (docs, manifests, qss, tests); leave 2000-line
synapse_panel.py surgery for a frontier model when your limit resets.
Out-of-scope writes are refused by the executor itself.
Unset to return to Claude:   Remove-Item Env:SYNAPSE_ROPE_ENGINE

### PR the branch (review surface for integration)

    gh pr create --base master --head rope/gate-a --fill
    # no gh? open: https://github.com/JosephOIbrahim/Synapse/compare/master...rope/gate-a
