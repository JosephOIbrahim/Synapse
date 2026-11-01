# SUBSTRATE LOOP: Operator's Card

Long, unattended improvement runs on the memory substrates SYNAPSE stands on
(Moneta, SALUS, Hanish, Octavius, the SALUS-Moneta shim). **Claude plans and
reviews. A local Ollama model does every iteration.** So a run can go for hours
without touching your Claude budget.

```
Claude (your session)   PLAN: write one mission  ──►  REVIEW: read REVIEW.md, pick commits
                               │                              ▲
loop.py (plain Python)         ▼                              │
   Houdini check → local model proposes → scope + anti-gaming → substrate gates
   → SYNAPSE's own tests against the candidate → metric → KEEP (commit) / discard
```

---

## Run it

```powershell
# 0 · once: pull the worker model (19 GB, fits the 4090)
ollama pull qwen3-coder:30b

# 1 · open Claude Code in the SYNAPSE repo and ask for a plan
claude
> /substrate-loop plan salus        # Claude writes a mission and runs doctor

# 2 · start the run in its own terminal (closing Claude Code won't stop it)
python harness\substrate_loop\loop.py run --mission salus_lint

# 3 · come back whenever
python harness\substrate_loop\loop.py status

# 4 · when DONE is written, back in Claude Code
> /substrate-loop review
```

Stop early at any time with `python harness\substrate_loop\loop.py stop`. The
run finishes its current iteration and writes its review packet. Delete
`runs\STOP` before the next run.

Repos are expected next to the SYNAPSE checkout. If they live elsewhere, set
`SUBSTRATE_ROOT` to the folder that holds them.

---

## What you'll see

`runs\<mission>_<stamp>\` holds everything one run made:

- `state.json`, the heartbeat: status, iteration, kept, best, Houdini pauses
- `ledger.tsv`, one row per iteration: KEEP, discard, no_gain, rejected, worker_error
- `REVIEW.md`, written at the end: why it stopped, the metric's path, every kept commit
- `wt\`, a git worktree on branch `substrate-loop/<mission>/<stamp>` holding the kept commits
- `DONE` or `FAILED`, written last

Your substrate checkout and its main branch are never touched. Nothing is pushed.

---

## The rules it enforces

**Houdini.** It refuses to start while Houdini, hython, husk, hbatch or mantra
is running (`houdini_guard.py`). Between iterations it checks again. With
`"on_houdini": "pause"` it unloads the model from the GPU, waits, and resumes
when Houdini closes. With `"stop"` it ends the run cleanly. If the process list
can't be read, it treats that as running. An iteration already in flight
finishes first, so a pause can lag by one iteration.

**Keep only real gains.** Every gate must pass before and after, and the
mission's number must get strictly better. A tie is discarded.

**No gaming.** Frozen paths (tests, specs, verify gates) can't be edited. Added
`# noqa`, `# type: ignore`, skips and xfails are rejected before any gate runs.

**SYNAPSE still works.** Moneta and Hanish candidates also run SYNAPSE's own
integration tests, and the loop proves those tests imported the candidate, not
an installed copy.

**Stop rules.** Iteration cap, wall-clock cap, no-progress streak, consecutive
worker errors, the STOP file, and (when Claude is used mid-run) a dollar cap.

---

## Swap the model

Everything lives in `tiers.json`. A mission picks a tier with `"worker_tier"`.

| Tier | What runs each iteration | Claude tokens |
|---|---|---|
| `worker` (default) | the loop calls Ollama directly; the model returns edit blocks | none |
| `worker_claude_code` | Claude Code itself, pointed at Ollama, edits the files | none |
| `worker_haiku` | the same Claude Code worker on Haiku, for when a local model stalls | yes, capped |

The `worker_claude_code` tier needs Ollama started with a bigger window:
`$env:OLLAMA_CONTEXT_LENGTH=65536; ollama serve`. Run `ollama ps` and check the
PROCESSOR column says 100% GPU; if it spills to CPU, drop back to 32768.

---

## When it breaks

**`REFUSED: Houdini check: running ...`** Close Houdini. Background license
services (hserver, sesinetd) are ignored on purpose.

**`REFUSED: baseline is red at gate ...`** The substrate fails its own tests
before the loop touched it. Fix that first, or write a `pytest_failed` mission
that targets that suite (see `missions\_template.json`).

**`ollama is not answering`** Start it with `ollama serve`.

**`another run is live`** One mission at a time. If that process is gone, the
next run clears the lock itself.

**Lots of `no_gain` or `rejected` rows** The model is circling. Narrow the
mission's `focus`, or switch `worker_tier` for one run.

---

## Where it lives

```
harness\substrate_loop\
├── loop.py            # the runner: doctor · run · status · stop
├── workers.py         # lean Ollama worker, Claude Code worker, optional reviewer
├── houdini_guard.py   # fail-closed process check
├── metrics.py         # ruff · mypy · pytest_failed · command
├── targets.json       # the substrates, their gates, frozen paths, SYNAPSE downstream tests
├── tiers.json         # model names live HERE only
├── program.md         # the rules every worker reads (yours to edit)
├── missions\          # one JSON per mission; _template.json documents every field
├── tests\             # self-tests with a fake worker: python -m pytest harness\substrate_loop\tests
└── runs\              # git-ignored run output
```
