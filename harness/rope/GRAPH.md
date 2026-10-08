# rope graph · operator card

`runner.py` walks one list, one session at a time, in the tree Houdini serves.

`graph.py` walks a graph, several sessions at a time, in a worktree of its own.

It is the same rope. The checks, the scoped revert and the executor command are imported from `runner.py`, not copied.

## What it does

1. **Map.** It reads the repo's own import graph. Each area of `python/synapse` is a node, plus the entry points outside it.
2. **Scout.** One read-only session per slice of the map. A scout returns candidates: a file, a line, the quoted line, the smallest fix, and how a program would prove it.
3. **Route.** Code vetoes first: fenced paths, the exam, and any candidate whose quoted line is not in the file. Then `harness/jev/jev_sweep.py` asks Jev where each survivor goes.
4. **Fix.** One session per file, each in its own slot worktree. A fixer may edit its card's files and run `python -m pytest`. Nothing else.

   Every prompt the graph writes (scout, fixer, referee) carries `GIT_RULES`: never `git stash`, because stash refs live in the shared `.git` and every worktree sees them. Two lanes swapped patches that way on 2026-10-07. The safe way to run old code is `git archive <rev> python | tar -x -C <scratch>` with `PYTHONPATH` on the scratch copy. A plain `git show <rev>:<path>` breaks package imports. Pinned by `tests/test_rope_graph_nostash.py`.
5. **Gate.** Checks decide. Keep is one scoped commit. Fail is a scoped restore. A fix that removes a logger call is refused (`dropped_log`) unless the same line was added in a declared file or the card quotes the call's message. Every fix also runs the four ratchets: catalog conformance, recipe-string conformance, the D-track TOPs quarantine, and the broad-except ratchet. A fix that breaks one of these composed gates is discarded, even when no judging test names its module.
6. **Referee.** A read-only session reads the kept commits. A drop is a `git revert`, never a rewrite.

## The three laws

1. **The cap is counted here and nowhere else.** A session is counted before it starts, so a crash cannot beat the cap.
2. **A fix may only declare files outside the fences and outside the exam.** The refusal is code, in `refuse_item`.
3. **The loop never edits its own exam.** Existing tests, fixtures, the catalog and this harness are read-only to every worker. No model keeps or discards a change.

## What Jev decides, and what it does not

Jev routes a candidate: `fix_now`, `needs_houdini`, `propose_only`, `not_a_defect`. It scores value. It picks the fixer's tier by name.

Doubt rounds down on the route and up on the tier. With no Jev answer, the route is `propose_only`: an outage produces a list, not edits.

Jev never keeps a change. The questions and thresholds are `guards.sweep` in `harness/jev/questions.json`.

## Run it

Run it from a worktree, never from the checkout Houdini loads.

```
python harness/rope/graph.py map
python harness/rope/graph.py init   --run RUN --slots SLOTS --cap 50 --minutes 60
python harness/rope/graph.py tick   --run RUN --kinds scout --loop 15
python harness/rope/graph.py route  --run RUN
python harness/rope/graph.py add    --run RUN RUN/fix_items.json
python harness/rope/graph.py tick   --run RUN --kinds fix --loop 15
python harness/rope/graph.py review --run RUN
python harness/rope/graph.py tick   --run RUN --kinds review --loop 15
python harness/rope/graph.py status --run RUN
```

`route` writes `candidates.json` and `fix_items.json` and adds nothing. Read them, then `add`. That pause is deliberate.

`RUN/seeds.json` is optional. It holds candidates from any other finder, in the scout's format. They pass the same vetoes and the same route.

A fix's new test is named `tests/test_graph_<run folder>_<candidate id>.py`. If that path is tracked in git or already on disk, a number is added until it is free. Seed ids repeat from run to run, so the id alone once named a test an earlier run had committed, and the item was refused as the exam.

## What you will see

Each tick prints one line:

```
11:42:07  sessions 23/50  clock 31m left  |  fix 2 kept 1 discarded 3 running  |  scout 22 done
```

`RUN/results.tsv` has rope's columns, one row per session, with the real token count.

`RUN/<id>.prompt.txt`, `.out`, `.err` and `.result.json` are the full record of each session.

## Models

A tier name goes in and a model string comes out. The table is `harness/rails_exec.json`.

Scouts run on `mechanical`. Fixers run on the tier Jev picked. The referee runs on `referee`.

`--models reasoning=sonnet` overrides one tier for one run. `SYNAPSE_ROPE_ENGINE=ollama` swaps the engine, as it does for rope.

## When it stops

- **`cap reached`.** The 51st session is refused. Raise `--cap` on a new run.
- **`clock ran out`.** No new session starts. Sessions already running are still gated.
- **`quota`.** A session reported a usage limit. The loop stops and is never retried.
- **A slot is `retired`.** A worker left it dirty in a way a scoped restore could not undo. It is not reused. Look at it.

## When Houdini is running

`init` refuses, as rope does. Rope refuses because it edits the tree Houdini serves.

A graph run in its own worktree does not. Pass `--live-seat-ok "<why it is safe>"`. The reason is written to the ledger as the first row.

Workers start with `harness/rope/no-mcp.json` and `harness/rope/graph-worker.json`. They attach to no MCP server and fire no session hooks, so they never touch the live bridge.

## Held lightly

- The import graph of this repo is close to one knot. Transitive reach is the same for almost every area, so work is ordered by direct importers.
- The gate proves tests pass. It does not prove behaviour inside Houdini. That is why `needs_houdini` candidates are listed and never fixed here.
- `dropped_log` reads the diff one line at a time. A logger call split over several lines, with its message on a continuation line, is not seen. `print(` is not checked.
- `dropped_log` counts a logger line pasted into the fix's own new test as moved. A fix can delete a production log call and launder it that way. Closing it means moving the pin `test_a_log_line_moved_to_another_declared_file_is_kept`, which is the owner's call.
- `tests_for` picks judging tests by module name. A module no test names is judged only by its new test and the four ratchets.
- The ratchets assume the integration root is green. `test_except_ratchet.py` scans the whole tree against `tests/fixtures/except_ratchet_baseline.json`. If the root is already red on any ratchet, every fix is discarded with a `fail` that has nothing to do with the fix. That is a dead gate. Not closed yet. The follow-up is a check in `cmd_init` that runs the ratchets once on the untouched root and refuses the session if any is red, pinned by a failing-today test that plants a red ratchet.
