# Release preparation: v5.93.1

Publish five commits on top of v5.93.0 (tag `v5.93.0` on `58214dc5`). Joe's words, 2026-10-02. For the build, at
about 15:35: "lets implement to ones we did add from this morning and today more broadly now!", read as the ones
we did not add. For the commits, the push and this release, at about 18:10: "commit, push, release". He said it
in answer to a narrower recommendation: commit and push now, and release after Monday's attempt and his own
look. His word chose the release now. At about 18:35: "ok. lets proceed with your recommendations then and focus
on getting demo-ready".

| Commit | What it does |
|---|---|
| `1bad31b6` | TESTSPILL. `tests/conftest.py` sets `SYNAPSE_LOG_DIR` and `SYNAPSE_BRIDGE_FILE` at import to a folder made for the session, as defaults, and removes it at exit. `tests/native_render_workspace.py` sets the same two beside its output before any synapse import. `tests/test_session_scratch.py` is new (4). |
| `c7f730e4` | SPATIALHINT. `panel/spatial_action.py::error_text` drops a trailing " -- Pass ..." suggestion and shows the tool's reason word for word. `tests/test_spatial_action.py` gains 3. |
| `58881fb8` | UNDOLABEL. `TRAIL_UNDO` is `SYNAPSE: Draw camera path` (`server/handlers_spatial.py`), and `panel/bridge_adapter.py` takes the trail's operation summary from it, so the bridge's outer undo group and the tool's result carry one name. Every other tool keeps its summary. `tests/test_spatial_tools.py` gains 2; the label pins move in three test files. |
| `a01fed73` | TRAILPRESENT. `synapse_spatial_path`'s result gains `trail` (`drawn`, `absent`, `bypassed`, with node, prim and points) and its sentence says so (`server/handlers_spatial.py`). The tool's description gains one clause, 333 to 382 characters (`mcp/_tool_registry.py`). `tests/test_spatial_handlers_pxr.py` gains 7. |
| `0f6ca57b` | STALERECEIPT. The panel's context read carries Houdini's undo labels (`panel/ws_bridge.py`), `turn_revert.turn_gone` compares them with the turn's, and `_retire_stale_receipt` hides the receipt when the turn is no longer on the stack (`panel/synapse_panel.py`, `panel/turn_revert.py`). `send_chat` strips the labels. `tests/test_stale_receipt.py` is new (31); `tests/panel/test_bc_wave.py` gains one on real Qt. |

All five were pushed 10/2 at 18:30. CI run 37072834064: passed on all six jobs.

## Evidence

- **The transfer and the commits.** The five fixes were written in a cloud clone and moved to the workstation as
  five patches, one per finding (`.token-saver/m1/0001_testspill.patch` to `0005_stalereceipt.patch`, 159
  checksummed lines, every sha256 matched). Each patch's tree is the same in the cloud and on the workstation:
  `3106f609`, `668d328a`, `1e2fe8f1`, `323dc2b2`, `f6b5c5d3`. `commit_m1.ps1` proved the five trees in a
  temporary index, then made the commits in `.claude/worktrees/m1-fixes` on `fix/friday-findings`, each checked
  against its staged files and its tree. `push_m1.ps1` pushed master with Gate C set for that one command. After
  the push the cloud clone fetched master and read tree `f6b5c5d3`. One preflight line of `commit_m1.ps1`
  errored on an empty branch name, which is what a detached worktree gives; the script went on and every tree
  matched.
- **Live in hython.** `.token-saver/m1/live_m1.json` (live_m1.py, 10/2 16:59, hython 22.0.400, a copy of
  rc3_demo.hiplc with the worktree's code and the bridge's production path forced on; the demo hip's sha256
  unchanged). The undo history gained one entry, `SYNAPSE: Draw camera path`, equal to the label in the tool's
  result. The read: drawn, 144 points, 1,633 characters; after `performUndo`, absent, 1,520; after a redo,
  drawn; with the node bypassed, named and still bypassed, 1,588; 0.70 to 0.78 s per read. The real panel,
  offscreen: a click showed "1 CHANGE"; a tick kept it; "Change Selection" on top kept it; after two undos the
  next tick hid it; REVERT refused in its old words; a redo left it hidden; a fresh click and REVERT reverted.
  The empty scene: the tool's "/stage has no display node -- Pass a LOP node path", the panel's "Spatial:
  /stage has no display node". `undoLabels()`: 0.004, 0.04 and 0.12 ms at 101, 1,001 and 3,001 entries. An
  earlier run (`live_m1_run1.json`, 16:57) saved the same results and then crashed hython on the way out,
  because the script ended on `os._exit(0)` after creating Qt; `compare_live.py` shows the two runs agree apart
  from timings.
- **Through the panel worker.** `.token-saver/m1/bench_m1_base1.json`, `_base2`, `_w1`, `_w2`, `_w3`, `_base3`,
  `_base4` (bench_m1.py, 10/2 17:00-17:07, deepseek-v4.1-flash:cloud through Ollama, zero Claude tokens): eleven
  conversations, nineteen turns. Asked directly after an undo whether the path is still drawn: the fix, one
  call to the read, right; v5.93.0 twice, 4 and 6 calls with 3 and 4 errors, right. Asked the run sheet's words
  again after an undo: the fix, three runs: read then redraw, saying it had gone; a redraw, saying nothing had
  changed; no tool call, saying it was already drawn, which was false. v5.93.0 twice: a redraw in 1 call, and
  a redraw after 7 calls. The read, UNKNOWN and draw cases, once each on the fix: one call each. A first
  attempt at 17:00 refused the six worktree conversations before they reached the model
  (`bench_m1_log.txt`): a worktree has no project rules. The second attempt set `SYNAPSE_MODEL_POLICY` to
  Joe's existing rules file. No rule was written.
- **Tests.** Linux, Python 3.11, the five fixes: 10,454 passed, 757 skipped, 50 deselected, 3 xfailed and 1
  failed (`test_project_dir_sanitization`, which fails only in that sandbox); v5.93.0 there was 10,414. The
  USD-backed spatial tests under Python 3.13 with pxr: 70 passed, 7 skipped. The workstation, Python 3.14, the
  CI command, on the worktree with the five patches: 10,774 passed, 428 skipped, 183 deselected, 5 xfailed, 0
  failed, in 437 s (`.token-saver/m1/suite_ci.log`); `harness/jev/tests` there: 88 passed. Release tree:
  10,774 passed, 428 skipped, 183 deselected, 5 xfailed, 0 failed, in 459 s
  (`.token-saver/release/pytest_release_tree_v5931.log`); `harness/jev/tests` on the release tree: 88 passed. `sync_version.py --check` and `harness/notes/readme_check.py`: both PASS.
- **The panel tests under hython.** `.token-saver/m1/panel_work.txt` (10/2 17:10-17:20): 587 passed and 32
  failed, against 580 and 33 on v5.93.0's tree (`.token-saver/b3/panel_work.txt`). Every one of the 32 is among
  the 33; the one that passed this time is
  `tests/panel/test_ollama_discovery.py::test_closing_parent_during_discovery_never_calls_deleted_qt`. Six of
  the seven more passes are this release's new tests. A second set (`extra_work.txt` against `extra_base.txt`):
  369 passed and 13 failed, against 327 and the same 13 by name; the 42 more passes are the new tests (31, 4
  and 7). On real Qt in the Linux sandbox: 530 passed and 25 failed, against 495 and the same 25 by name. That
  run's selection is not the one in v5.93.0's notes, so its counts do not compare with theirs.
- **The render workspace's check.** `tests/native_render_workspace.py` under hython 22.0.400 on the worktree
  (10/2 18:22, `.token-saver/m1/rw_out_182221/native-receipt.json`): passed, 6 checks, 5 layouts, in 6 s. Joe's
  Houdini was open: its sidecar `~/.synapse/bridge.json` had the same sha256 before and after, the memory
  store's snapshot was not rewritten, and no halt or freeze file appeared. The run left no sidecar of its own
  behind, so it shows the live one untouched and does not show where the check's own would have gone.
- **TESTSPILL, measured.** After a full run on each machine: no new halt or freeze file in the log folder,
  `synapse.log` and `bridge.json` untouched, and the session's folder gone at exit. The audit log grew by
  47,028 bytes in the sandbox and 47,344 on the workstation; it has no folder override.
- **What the checks did on Joe's machine.** Loading the demo scene sets `$JOB` back to the home folder it was
  saved with, and a scene under `$JOB` binds the memory store there. Nine hython processes of these checks,
  between 16:57 and 17:07, opened `~/.synapse/.moneta` while Joe's Houdini held it and re-saved its snapshot
  (17:01:13, then 17:07:33); `wal.log` was refused by his session's lock. Checked afterwards: 1,558 records,
  the newest from 15:14:55, his own session's last write; no record with bench text. Not checked: an id-by-id
  comparison. The snapshot was written again at 18:10:40, two seconds before his Houdini relaunched, which is
  his old session saving on its way out; that reading rests on the times. At 18:32 the record the take's
  Beats 1 and 3 depend on, `ddd-rc4-9e121f`, was in the snapshot (read-only check). The check scripts now set
  `$JOB` to their own folder after each load.
- **Jev.** Three requests on the day's decisions, each one request (`.token-saver/legs/orchestrate_fri_more.json`
  at 15:37, `orchestrate_fri_coordinate.json` at 17:15, `orchestrate_fri_demoready.json` at 18:37; ledger
  `DDD.orchestrate.jsonl`). Used here: five commits, one per finding, 0.85 at confidence 0.77. On the release's
  timing Jev leaned to a release after Monday's attempt, 0.55 against 0.37 at confidence 0.32, which made it
  Joe's, and his word was to release. On the notes: Jev checked the 20 claims in their validation
  section in one request, against the five commits, the test counts and the receipts
  (`.token-saver/release/jev_notes_v5931.py`; 14,590 tokens in, 913 out, 440 ms). 19 came back partial and 1
  supported. None came back unsupported (0.18 at most) and none went unanswered. The 19 partial ones went to a
  direct read against the receipts, and all 19 stood as written. One number in the evidence Jev was given was
  wrong: the script counted 4 added test functions in `tests/test_spatial_action.py`, where the file gained 3
  (10 collected against 7). The notes say 3. Ledger: `harness/jev/ledger/v5.93.1.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.93.1.** Five fixes, no new tool: the patch version moves.
- **Five commits, one per finding.** Any one can be reverted alone during the freeze week.
- **Released before any GUI look.** None of the five has been seen in the Houdini GUI. The notes say so in their
  first limit. Joe's two-line look (the step's name in Edit > Undo, and the receipt going after a hand undo) is
  still his.
- **The take's build is not decided here.** Joe's checkout (`d6/overnight`) and his Houdini stay on v5.93.0.
  Loading this release means a fast-forward and a relaunch, and that is his word. Jev on which build Monday's
  first attempt runs on: stay on v5.93.0 0.47, v5.93.1 tonight 0.28, v5.93.1 Monday morning 0.25, at
  confidence 0.21.
- **UNDOLABEL changes one tool's summary only.** The summary is also a consent card's description, so the
  other tools keep theirs.
- **The receipt only hides.** The turn's record stays, so REVERT's own refusal still speaks. A redo does not
  bring the receipt back.
- **A correction.** The commit message of `a01fed73` says v5.93.0 answered the direct question in "4 and 6 calls
  with 2 and 3 errors". The receipts show 3 and 4 errors. The public notes carry the receipts' numbers, and the
  commit stays as pushed.

## Not in this release

A fix for the model answering from its history after an undo; a folder override for the audit log; a fix for
two processes on one memory store; names in words for the other tools' undo steps; a GUI look at any of the
five; the chat-side flag for the World Labs import, which Joe met at the panel at 18:13 and which waits for
after Oct 7 on his word; ghost frusta and the rest of the onion skin; arrangement C of the panel.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.
