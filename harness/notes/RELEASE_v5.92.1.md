# Release preparation: v5.92.1

Publish two commits on top of v5.92.0 (tag `v5.92.0` on `5c319d52`). Joe's word, 2026-10-02: "is evewrything built
committed ? then git push and git release". The release tree was prepared the night before and held at its
commit, because the release commit touches `VERSION`, which Gate C fences.

| Commit | What it does |
|---|---|
| `a624cc2a` | The round cap ends a turn in words (panel/claude_worker.py): a wrap-up directive on the last tool round, in the system prompt only, with the history untouched; a tool requested on that round is never run; the turn closes with a fixed line that is kept in the history; the usage ledger adds `wrap_up: answered \| closed` beside `outcome: cap_hit` |
| `b48c0b22` | build_graph's failure message is written after its rollback attempt (server/handlers_solaris_graph.py): "build rolled back" only when performUndo ran; otherwise "build failed and was NOT rolled back", its nodes still in the network, one Ctrl+Z or REVERT to remove them |

## Evidence

- **The round limit, forced.** `.token-saver/pack/bench3_capforced_4.json`, `bench3_capforced_6.json`,
  `bench3_capforced_9.json` (bench_cap_forced.py over bench3.py, 10/1 20:31-20:32) and the usage ledger rows in
  `.token-saver/spatial/cap_forced_turns.jsonl`. Cap 4: 4 rounds, 7 tool calls, 9.1 s, stop_reason end_turn,
  cap_hit/answered, nothing built. Cap 6: 6 rounds, 12 tool calls, 18.7 s, stop_reason tool_use, cap_hit/closed,
  the scatter's four nodes already built, the reply ends with the closing line. Cap 9: 8 rounds, 14 tool calls,
  14.7 s, completed.
- **Three repeats on the fix.** `.token-saver/pack/bench3_capfix_r1.json`, `bench3_capfix_r2.json`,
  `bench3_capfix_r3.json` (10/1 20:23-20:26): 9 of 9 built; scatter 17.5 / 47.6 / 39.2 s, 531 instances each;
  blocker 6.6 / 5.5 / 6.1 s, light:filters -> KarmaBlockerLightFilter each; passes 14.2 / 13.1 / 6.4 s, two
  RenderPass prims each; at most 14 of 25 rounds; display demo_settings; finished replies. Run 2's scatter left a
  warning on hide_collider ("Local variable 'protoprimname' not found."); there were no other badges.
- **The rollback message.** `.token-saver/spatial/live_nested.json` (live_nested.py, 10/1 22:10, hython 22.0.400,
  a copy of rc3_demo.hiplc; the demo hip's sha256 unchanged). No outer undo group: "build rolled back", node gone,
  0 undos to clean. Under an outer `hou.undos.group`: "build failed and was NOT rolled back", the node left wired
  in, the display node with no stage, 1 undo cleans. Through `execute_through_bridge` with the bridge's production
  path forced on: the same. The before state, the old text beside a node that stayed, was seen with the same script
  ahead of the fix and is recorded in b48c0b22's commit message; that run's JSON was overwritten by the later runs.
- **Tests.** tests/test_worker_round_cap.py 8 passed; tests/test_solaris_graph_oncamera.py
  TestBadgeFailureSaysWhatHappened 4 passed. Release tree, the CI command (`-m 'not needs_houdini'`), Windows,
  Python 3.14, after the release edits: 10,628 passed, 427 skipped, 120 deselected, 5 xfailed, 0 failed
  (`.token-saver/release/pytest_release_tree_v5921.log`). One skip is the worktree's own: a test in
  tests/test_cap_cost_basis.py reads a local run ledger that exists only in the main checkout, where it passes.
  The main checkout with the spatial commit on top, same command: 10,707 passed, 426 skipped, 176 deselected,
  5 xfailed, 0 failed (`.token-saver/spatial/suite_ci.log`). `sync_version.py --check` PASS;
  `harness/notes/readme_check.py` PASS.
- **Jev.** Jev checked the 16 claims in the release notes' validation section against the two commits since
  v5.92.0, the code diffs, the new tests and the receipts above (`.token-saver/release/jev_notes_v5921.py`). All
  16 came back partial and none unsupported (unsupported at most 0.09), so each went to a direct read against the
  receipts. All 16 stood as written. Ledger: `harness/jev/ledger/v5.92.1.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.92.1.** Two fixes, no new tool: the patch version moves.
- **The message fix rides with the cap fix.** It corrects a sentence v5.92.0 ships that is false inside the panel.
- **Message only.** Taking a failed build's nodes back out from inside the panel's undo step is not attempted
  here. What stays in the network is what stayed before.
- **Prepared in a worktree.** The release tree was built in `.claude/worktrees/rel-v5921` (branch
  `release/v5.92.1` on `b48c0b22`), so the main checkout stayed on `d6/overnight` with the spatial work.

## Not in this release

The spatial tools (`synapse_spatial_path`, `synapse_spatial_trail`), which follow in v5.93.0; removing a failed
build's nodes inside the panel's undo step; the other handlers that call `performUndo` on failure, unprobed inside
the panel; the closing line naming what the turn already changed; the Scatter recipe's 'protoprimname' warning; a
GUI run of either fix.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.
