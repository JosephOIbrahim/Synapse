# Release preparation: v5.94.3

Publish the hour loop of 2026-10-06 on top of v5.94.2 (tag `v5.94.2` on `40ef16f9`): eleven small repairs, two
one-line corrections to them, and rope's graph mode. Joe's words, 2026-10-06, in order: "setup synapse for an hour
today of recursive general improvement. Connect to Claude code and the synapse repo and basically look for synapse
details we can fine tune in a loop for an hour."; "use subagents during the hour to touch as many aspects of
synapse as you can capping agents at 50 subagents. Use graph engineering and modify the synapse harness to work
with this request."; "use JEV for routing and decisions"; "give me 30min updates during this operation"; after the
hour's report, sent at 12:30pm, "Commit, git push , git release"; and during the release, "Outline in a list the
miles".

| Commit | Card | What changed |
|---|---|---|
| `0b36c434` | harness | `harness/rope/graph.py`, `GRAPH.md`, `graph-worker.json`, `harness/jev/jev_sweep.py`, `guards.sweep` in `questions.json`, 25 tests. |
| `24e777bb` | harness | A scout is told its turn budget and may carry a brief. |
| `e08d32a8` | F02 | `server/handlers_memory.py`: a module logger. |
| `4f0aee14` | F08 | `mcp_server.py`: `import concurrent.futures` at module level. |
| `ea29c048` | F09 | `panel/synapse_panel.py`: two tooltips. |
| `af362faf` | F12 | `component_builder.py`: the unknown-purpose message lists the purposes, sorted. |
| `3d3cf023` | operator | Restores a space F08 dropped. |
| `72f27796` | H01 | `tests/test_help_page_honest.py`. A test only. |
| `8ef02dd9` | U01 | `scripts/sync_version.py`: the `help_page` surface. |
| `0282cb64` | K01 | `synapse/hooks/synapse_hooks_houdini.py`: `InputChanged` becomes `InputRewired` (HOM-2). |
| `131ad244` | K02 | `shared/bridge.py`: `rollback_incomplete` on the sentinel-hash branch when the undo raised (HOM-22). |
| `d587d26b` | K03 | `server/handlers.py`, `server/handlers_render.py`: the undo-label guard (HOM-13). |
| `52cdaa09` | K05 | `panel/cross_scene.py`, `server/solaris_compose_tools.py`: `hou.text.expandString` (HOM-6, two of five sites). |
| `d4ae6a18` | D01 | `docs/help/events.md`, `commands.md`, `panel_docking.md`. |
| `41020b05` | operator | Restores a debug line K03 dropped. |

The release commit on top is version strings and documents.

## Evidence

- **The remote before anything was pushed.** `git ls-remote origin` at 1:46pm: `refs/heads/master` at `40ef16f9`,
  no `loop/*` branch, no `v5.94.3` tag. The repository is public.
- **The branch push.** `loop/hour-20261006` at `41020b05` went up at 1:59pm as a new branch. Its 15 commits touch
  no Gate C path, and the pre-push hook passed with no override set.
- **The hour.** 49 sessions through `graph.py` and one smoke test, against a cap of 50, in 28 minutes: 33 scout
  sessions (31 on Haiku, 2 on Sonnet), 13 fixer sessions on Sonnet (11 kept, 2 changed nothing) and 3 referee
  sessions on Sonnet. Jev answered 61 calls with no fallback. The ledger and every prompt and reply are in
  `C:\Users\User\Downloads\synapse_night_loop\hour-20261006\run\`, outside the repository.
- **Each kept card's checks.** Its new test file exists, and one pytest run passes over the two catalog
  conformance tests, four or five existing test files chosen for the modules it touches, and the new file, with
  `-m "not needs_houdini"`. Before that run the gate checks that only the card's declared files changed and that
  each changed Python file parses.
- **The suite, three times on Windows.** Python 3.14.2, the CI command, home folder on scratch, no `SYNAPSE_*`
  variables. At `40ef16f9` before the hour: 10,923 passed, 430 skipped, 186 deselected, 5 xfailed, 0 failed. At
  `41020b05`: 10,965 passed with the same other counts; a set-diff of test ids between the two junit files shows
  0 newly failing, 42 added, 0 removed. On the release branch's working tree (`rel\full_rel.log`): 10,965 passed,
  430 skipped, 186 deselected, 5 xfailed, 0 failed, in 8 minutes 37 seconds, then `harness/jev/tests`, 97 passed.
  That run had the nine modified release files and a draft of the notes; this note and the Jev ledger row came
  after it. With those in place, the README receipt, version conformance, tool-count and help-page tests and
  `harness/jev/tests` were run again on 3.14.
- **Each repair's tests on v5.94.2's tree** (`rel\base_check.log`). The eleven files, 26 tests, copied onto a
  worktree at `40ef16f9` and run one file at a time: 19 failed, 7 passed. Per file: seed_1 1 failed; seed_2 2
  failed; seed_4 2 failed; s08_1 1 failed; help_page_honest 4 passed; sync_version_help_page 2 failed; hom2 1
  failed, 1 passed; hom22 1 failed, 1 passed; hom13 4 failed; hom6 2 failed, 1 passed; help_pages_older 3 failed.
- **Linux.** A fresh clone of the pushed branch at `41020b05` in Claude's cloud workspace. Python 3.11.17:
  `compileall` clean on the changed trees; CI step 1, 10,643 passed, 763 skipped, 50 deselected, 3 xfailed, 0
  failed, in 5 minutes 36 seconds; CI step 2, 97 passed; CI step 3, 14 passed and 27 skipped without the engine.
  Python 3.13.16: the twelve new test files and `harness/jev/tests`, 139 passed.
- **Python 3.11 on Windows.** 3.11.15, the venv at `.token-saver\bp11\ci_dry\py311`, on the release tree: sixteen
  files (README receipt, version conformance, tool count, egress docs and the twelve new test files), 95 passed;
  `harness/jev/tests`, 97 passed. pytest's `pythonpath = ["python"]` puts the worktree's package first; that
  venv's own installed `synapse` is an old tree.
- **The symbol table.** `h22_symbol_table.json`, introspected from 22.0.400, 36,472 symbols: it lists
  `hou.nodeEventType.InputRewired`, `hou.text.expandString`, `hou.undos.undoLabels` and `hou.undos.performUndo`.
  No entry contains `InputChanged`.
- **Read in the source for the notes.** `_ROLLBACK_ERRORS` in `handlers.py` decides when `execute_python` rolls
  back, and it does so only in atomic mode. `_is_sentinel_hash` is true for an empty hash, the no-node marker and
  the no-hou fallback. `_register_single_node` wraps `addEventCallback` in `except Exception: pass`. A search of
  every file type finds the hooks module named only by itself, its new test, harness notes and one review
  document. `valid_purposes` is `{"render", "proxy", "simproxy"}`. `mcp_server.py` line 338 annotates
  `_DISPATCH_EXECUTOR` with a string that names `concurrent.futures`. The help page has 20 `says` spans, and
  `2 CHANGES` is the one on the test's allowlist.
- **Twelve arguments assigned and never read.** An AST check on `41020b05`: `component_builder.py` `execute()`
  lines 248, 249, 250 and 253; `create_variants.py` `plan()` line 79; `handlers_cops.py`
  `_handle_cops_batch_cook()` lines 2097 and 2098; `handlers_hda.py` `_handle_hda_promote_parm()` line 149;
  `routing/planner.py` lines 275, 360, 534 and 589. Line 327 of `handlers_hda.py` reads `definition.sections()`
  into a name nothing uses, which is dead code and not an argument.
- **The seat.** The main checkout `C:\Users\User\SYNAPSE` was fingerprinted before and after the hour: `master`
  at `40ef16f9`, 169 pending lines, the same listing hash. A walk at 2:25pm read the write time of all 353,958
  files in it outside `.git` (`rel\sweep2.txt`). Three were written after 10:50am, all inside the live session's
  own `.synapse` folder: its health history, which Houdini appends to through the day, and two provenance records
  stamped 11:04am, half an hour before the loop's first session. Nothing else was written. Two old pytest-cache
  folders under `.claude\worktrees` could not be read. Houdini 22.0.400 ran throughout as one process and was not
  touched.

## Decisions

- **Released on Joe's word, the day before the take.** The take is Wed 10/7 at 11:00. The rule since the pin is no
  code changes until the take. His instruction puts this release on GitHub; it does not move the take build.
- **The seat stays pinned.** `master` on origin moves by a push from `release/v5.94.3` in the hour loop's
  worktree, `git push origin release/v5.94.3:refs/heads/master`, fast-forward only. The main checkout's own
  `master` is not moved, so it reads 17 commits behind `origin/master` until Joe pulls after the take. Houdini
  loads files, and those files are still v5.94.2.
- **The Oct 4 review asked for three of these after the take.** HOM-13: "do not change before Oct 7". HOM-22:
  "Post-take". HOM-6: "Fix must wait: zero take benefit, nonzero risk". Those rulings protect the build that is
  recorded, and that build does not change. Anyone who pulls `master` into the seat before the take changes it.
- **The whole branch.** The hour's report listed "take the branch, or pick from it" as Joe's call and named K03
  as the one to read first. His answer was the three release words, read here as the whole branch.
- **v5.94.3, a patch.** Repairs and a harness mode. No new capability for the artist.
- **No pull request.** CI runs on pull requests and on pushes to `master`. Joe asked for a push and a release, so
  the Linux pass ran in Claude's cloud workspace from the pushed branch, CI's six jobs run on the push to
  `master`, and the tag waits for them.
- **The tag follows CI.** An annotated tag with the title, as for the last three releases.
  `scripts/tag_release.py --check-only` is run on the release commit as the gate before the push.
- **VERSION was written by a script, under the gate.** `scripts/sync_version.py --write` propagates VERSION and
  does not write it. `rel\set_version.py` wrote `5.94.3`, utf-8 with a line feed and no BOM, and refused unless
  the file held `5.94.2`. The Gate C override is set for the commit and for the push to `master`, each time for
  one command, and removed after.
- **The README's recipe pointer stays on v5.94.1.** Those are still the last notes that record what was seen in
  Houdini.
- **Two numbers in the hour's report were wrong.** It said thirteen ignored arguments; there are twelve, and the
  thirteenth item is the dead read at `handlers_hda.py` line 327. It said two of four `hou.expandString` calls
  were moved; the review lists five sites, the card listed four, and three remain. The notes use the right
  numbers, and the project's hour-loop page is corrected.
- **One evidence line in the release commit was wrong, and the commit after it corrects it.** `f5f00ae6` said a
  sweep at 12:19pm had read all 197,315 files in the checkout and found none written after 10:50am. That sweep
  had stopped without a word at a folder it could not read, having covered about half of the files, and it never
  reached `.synapse`. The seat line above comes from a second walk that counts its errors. The wrong line also
  went to Joe in the hour's report and is corrected there. The correction is the seventeenth commit, so the notes
  and the changelog now say seventeen; the Jev request below checked the sentence when it said sixteen.
- **JEV.** For the notes, 37 claims were checked in one request
  (`harness/jev/ledger/v5.94.3.release.notes.jsonl`): 31 came back supported and 6 partial, none unsupported. Each
  partial went to a direct read, and two more sentences were tightened on the same pass. Reworded after the
  request: "closes two of them and narrows two" now names the two it closes; the `sync_version.py` sentence
  quotes the script's own line instead of "not by hand"; the three tests that pass on v5.94.2's tree are
  described as what they are, a collector check, a symbol-table check and one pin, where the draft said all three
  pin behaviour; "a second session" became "three more sessions", and "restored by hand" became the session
  running the hour, because no person's hand was involved; the rollback limit now says the old code's cost rests
  on the project's own note about empty undo groups; the hooks docstring describes loading from Houdini's Python
  Shell, where the draft said a startup script. Also tightened: `execute_python` rolls back on coding errors and
  not on every exception; "ten Python files of the product", with the release tool and the version strings named
  beside them. The weakest supported claims were the ten-file count and the test counts (0.49 each), both
  re-counted from the diff and the logs.

## Not in this release

- **Anything seen in Houdini.** No session was opened. The first Houdini evidence for these repairs is still to
  come.
- **`NetworkBox.addItem`** (HOM-18), and the three remaining `hou.expandString` sites.
- **The twelve ignored arguments,** and the dead read at `handlers_hda.py` line 327.
- **The panel-path rollback** (BRIDGE-7), and the label inspection HOM-10 asks for on the bridge's sentinel
  branch. The docstring of `_guarded_rollback` still calls that branch "exactly the pre-H2 behavior"; after K02
  it can also record `rollback_incomplete`.
- **`docs/help/health_row.md`,** and the help page opened from the panel.
- **A hardcoded path in the hooks module's docstring.**
- **Moving the take seat.** Joe's, after the take: `git -C C:\Users\User\SYNAPSE merge --ff-only origin/master`,
  with the 169 pending lines looked at first.
- **The hour's scaffolding.** Seven worktrees, the session logs and the remote branch `loop/hour-20261006` stay
  until Joe removes them.
- **The houseclean branch, and a Windows Setup.**
