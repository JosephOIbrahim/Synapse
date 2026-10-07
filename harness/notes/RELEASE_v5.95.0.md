# RELEASE v5.95.0 · 2026-10-06 evening

## Joe's words, in order

- "use the synapse harness to execute an hour of production hardening across the SYNAPSE repo. Use up to 30 subagents (talking to each other) with graph engineering and a design team to tighten the panel design based on pentagram design studio principles and https://www.pentagram.com/work/cohere. Think deeply about recursively improving SYNAPSE during this time period. Use JEV for decisions and routing."
- "use dynamic workflows with agents as well"
- "after hour 1 do another 1 hour loop. Then commit, git push, git release all the updates."
- "add one more hour loop where you do the same loop you just did but one more time. JEV for decisions and routing."

## Shape of each hour

Each hour was one Workflow-tool run plus one rope graph run (`harness/rope/graph.py`), capped at 30 agents: 16 workflow agents and 14 graph sessions.

1. **Seed.** Three finders, each aimed at one defect class, then one refuter. Seeds replace broad scouts: in v5.94.3's run, 33 scout sessions found one small real fix.
2. **Route.** `graph.py route` vetoes by rule, then asks Jev (`guards.sweep`). The operator reads every routed card before `add`.
3. **Fix.** One headless session per file, in a slot worktree, kept only by the gate.
4. **Referee.** A Fable 5.1 session reads every kept commit.
5. **Design and harness lanes.** Agents in their own worktrees. Jev picks the move to build. A reviewer that did not write the change attacks it.

## What each hour fed the next

| Hour | Lesson | Became |
|---|---|---|
| v5.94.3 run | a reviewer kept a fix that dropped a debug line | the dropped-log gate (`ea6288f0`) |
| 2 | seed ids reused, so 3 fixes refused as exam edits | free test paths (`8b50f772`), used in hour 4 |
| 3 | a repair outside the graph broke the TOPs quarantine and the except ratchet; only the full suite caught it | every fix runs four ratchets (`e45bb510`); the repair was reverted (`77134d3a`) |
| 3 | evidence quoted as a bare `if p:` is vetoed as too short | finders told to quote a distinctive line of 12+ characters |

## Decisions made by the operator

- **Base:** origin's master at v5.94.3 (`ed9504c3`). The seat checkout stayed on `40ef16f9` and was never written to.
- **Held, owner's call:** the planner's default model id; three tools that read arguments and ignore them (COPs batch cook, HDA promote, component builder); the `dirtyAllTasks` keyword.
- **Held, needs an existing test changed:** two `hou.expandString` sites; `NetworkBox.addNode`; the unconditional rollbacks in `matlib_bind`, `shotsetup_karma_xpu` and `hda_package`.
- **Held, quarantine:** the TOPs live-monitor repair, on branch `tops/hour3-20261006`.
- **Held, narrows a gate:** design commit `7e46da26` on `design/hour3-20261006`, which changes what `audit_panel.py` measures.
- **Refused by its own probe:** design move T5. Qt honours span letter-spacing. It is ruling R3-B in `docs/design/PANEL_TIGHTEN_2026-10-06.md`.

## Where the evidence lives (on the build machine, not in the repository)

`Downloads\synapse_night_loop\hour{2,3,4}-20261006\`: each run's `run\results.tsv` ledger, every session's prompt and reply, the Jev ledgers, the workflow results, design proofs with their producers, and the suite logs and JUnit files (`hour2-20261006\baseline.xml`, `integrate-*.xml`, `release.xml`).

## Jev's check of the notes

One request to Jev (`guard="release.notes"`, ledger `harness/jev/ledger/v5.95.0.release.notes.jsonl`) asked, for each of 42 claims in `docs/releases/v5.95.0.md`, whether the receipts support it. Answers: 12 supported, 22 partial, 8 unsupported.

All eight unsupported claims were then checked by a direct read of the release tree, and each holds: `hip_crawler.py:81` reads `hou.text.expandString`; the palette comment reads "the panel rows"; `render_settings` still writes overrides behind `if p:`; `render_progressively` still loops over the three sample parms; `matlib_bind` and `hda_package` still call `performUndo()` on any failure; two `hou.expandString` calls and `box.addNode` remain; the design note exists; no Setup was built. The receipts lacked them because the commit log sent to Jev was cut at 24,000 characters and the held items were not in it. No sentence was reworded.
