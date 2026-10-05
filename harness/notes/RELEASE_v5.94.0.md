# Release preparation: v5.94.0

Publish fourteen commits on top of v5.93.3 (tag `v5.93.3` on `bca7079c`). Joe's words, 2026-10-04: at about
13:40, "CTO, use recommendations, go" (the hardening cards onto local master); at about 17:00, "execute all the
tasks including the post-demo tasks. They are all in the timeframe"; at about 18:55, "Push, merge, codex"; at
about 19:30, "Codex now. Post-Codex we commit, git push, git release."

| Commit | What it does |
|---|---|
| `24dfed6f` | H-1, H-4. `execute_python` returns a falsy measured result; the `SYNAPSE_AUTO_MEMORY` switch. |
| `abe62a3f` | The switch's row in the deployment table. |
| `9a3ee1df` | H-5. A store past 2,000 records can bind, load and adopt; the budget applies to one migration. |
| `d9f5a7d4` | H-2. `execute_vex` class table matches the attribwrangle menu. |
| `3e8a9630` | H-3. An error reply carries the failing request's id. |
| `62bed8be` | The catalog ratchet for call sites (test only), baseline 24. |
| `cc267fdf` | B1. Four tools return `parms_missed`. |
| `55cd43cb` | B2. Memory handlers raise on an error result; the bridge does not finalize a failed handler. |
| `be740842` | B3. Housekeeping rows opt-in; the freeze chain stands down on BeforeQuit. |
| `a8a495e1` | B4. Honest COP tool claims; the render-comp recipe checks first; the string-code ratchet, baseline 18. |
| `973a159f` | A2. Turn budgets on time and input tokens. |
| `7d75d685` | The panel prompt names `synapse_project_setup` for scene-memory questions. |
| `d5a28449` | Codex. The Scatter resolver, the recipe path on `build_graph`, fixed-parameter enforcement and readback. |
| `15eb3951` | Enforcement narrowed to the recipe's own node (`is_recipe_scatter`). |

## Evidence

- **The suite.** The CI command on `15eb3951`, Windows, Python 3.14, home folder on scratch and no `SYNAPSE_*`
  variables (`.token-saver/merge-20261004/full.log`): 10,917 passed, 430 skipped, 183 deselected, 5 xfailed,
  0 failed. Earlier the same day: 10,836 on `cc267fdf`, 10,862 on `be740842`, 10,872 on `973a159f`. Not re-run on
  the release tree: the release commit changes version strings and documents only, and CI runs on it before the
  tag is pushed.
- **Scatter before.** Houdini 22.0.400 on `3e8a9630`, computer use, typed, deepseek-v4.1-flash:cloud, in
  `rc3_scatter20_look.hiplc` (a copy of the demo scene, never saved). Turn ledger row 18:30:36: 8 rounds, 17
  calls, 146.0 s, 410,258 input tokens. The build call carried `maxangle` 45; `protoIndices` read back 763.
- **Scatter after.** Houdini relaunched by Joe at 20:34 on `15eb3951`, same scene copy, same request. Turn ledger
  row 20:37:32: 3 rounds, 3 calls, 71,807 input tokens. The calls: `synapse_knowledge_lookup`,
  `synapse_solaris_build_graph` with `recipe` and `dry_run` (RESOLVED, five bindings with sources), then the build
  (`scatter_parameter_corrections` empty, `parms_missed` empty). The reply states `maxangle` 20 and a 0.06 m
  prototype, and says it did not read an instance count.
- **Memory before the prompt change.** Houdini relaunched by Joe at 19:31 on `973a159f`, `rc3_demo.hiplc`, asked
  only. Ledger rows 19:36:35 and 19:37:35: `synapse_recall` and `synapse_search` only; neither reply gave the
  doorway assumption or the offset. Row 19:38:26, asked for `synapse_project_setup` by name: the full record.
- **Memory after.** The 20:34 session, row 20:36:42: one `synapse_project_setup` call; the reply gives 2.1362,
  2.10 m, 1.2897 m and -0.016 m, and repeats "763 instances" from the older Scatter note.
- **The watchdog.** The 19:31 Houdini (B3 loaded) was closed from its main window at 20:11:17. `synapse.log`
  carries "Watchdog stopped" at that second. No "SUSTAINED FREEZE" line follows.
- **Rebind.** In both evening sessions the pane was connected before the scene opened. Each rebind loaded 2,026
  records and logged "Moneta init with use_real_usd=True failed" once.

## Decisions

- **Released before Tuesday's rehearsal, on Joe's word.** Jev, asked per card whether merging before the take
  was more likely to prevent an on-camera problem than cause one: B4 0.67, A2 0.65, B3 0.47, B2 0.45, B1 0.42
  (`.token-saver/merge-20261004/jev-ledger/`). Nothing reached 0.8, so the calls were Joe's, and he made them.
- **v5.94.0, not v5.93.4.** A default changes (housekeeping rows), and a tool gains an argument.
- **No reply cache for retried commands.** Recipes and the parser derive the command id from the payload.
- **The TOPs render tool is untouched.** `tests/test_d_track.py` quarantines it.
- **Codex's lane.** Codex wrote `d5a28449` in its own worktree on Joe's go, relayed by Claude. Claude gave the
  scope for `handlers_solaris_graph.py` and the existing `build_graph` registry entry, reviewed the diff, and
  narrowed the enforcement in `15eb3951`. That narrowing edits Codex's file: a message asking Codex to do it did
  not send.
- **JEV.** For the notes, 13 claims from the validation section were checked in one request
  (`harness/jev/ledger/v5.94.0.release.notes.jsonl`): 8 came back supported and 5 partial, none unsupported.
  The two highest unsupported probabilities were 0.42, on "one GUI run apiece", and 0.29, on the real-USD
  fallback sentence. Both went to a direct read and both were reworded after the ledgered request: the first now
  says "after the changes", since the memory question was also asked three times before the prompt change, and
  the second no longer says "recall worked" of a session whose answer came from project setup.

## Not in this release

- **Three resolver runs from a fresh launch.** One was run.
- **An instance count at 20 degrees in the GUI.**
- **The 20-degree decision in the scene's notes.** Joe's line is still not recorded; the notes say 45 and 763.
- **Guarded mutation, the panel layout, the many-parameters tool, releasing the store's USD layer on close.**
- **A full rehearsal on this build.** Tuesday.
- **A Windows Setup.**
