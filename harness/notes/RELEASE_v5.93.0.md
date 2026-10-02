# Release preparation: v5.93.0

Publish three commits on top of v5.92.1 (tag `v5.92.1` on `c5da7d6a`). Joe's words, 2026-10-02. For this release,
the two later commits and their push: "Commit, git push & git release". He said it in answer to a stated
recommendation: the panel check first, then both commits, then one release carrying the tools, the receipt fix and
the row of three. For the first commit's push that morning: "is evewrything built committed ? then git push and
git release". For building the row of three before the freeze: "B - Row of three".

| Commit | What it does |
|---|---|
| `95fb0af5` | The camera path, measured and drawn: `synapse_spatial_path` (read-only) and `synapse_spatial_trail` (one build) over the new core `python/synapse/spatial/path.py`, the handlers in `server/handlers_spatial.py`, and the wiring (registry 137 -> 139, RBAC, bridge tier, the worker's builder allowlist, timeout, tool group, one prompt paragraph). build_graph gains an internal `sections` flag. It is `45979990`, the benched commit, replayed onto the v5.92.1 release commit; the replayed tree is `84827d79`. Pushed 10/2 at 07:47; CI run 37002955441 passed on all six jobs. |
| `fb8736b1` | The receipt credit (`panel/synapse_panel.py`): `trail` and `assemble` join `_MUTATORS`, so a turn that ran `synapse_spatial_trail` or `synapse_solaris_assemble_chain` earns a receipt and REVERT. `tests/panel/test_turn_receipt_credit.py` pins every tool on the worker's builder allowlist against the list. It closes finding (1) of the first GUI test. |
| `45210b3c` | The row of three (R-10 to R-12, arrangement B). The footer's last row is Identify, Spatial, Render, and Identify leaves the rail (`panel/inset_footer.py`). A click on Spatial, or `/spatial`, runs `synapse_spatial_trail` through the panel's own executor on a worker thread, with no model request (`panel/spatial_action.py`, new; `panel/synapse_panel.py`; `panel/command_palette.py`). The answer is the tool's sentence, signed. A click that changed the scene leaves a one-change receipt with REVERT. A click during a task, or a second click while the first is reading, is refused. The click enters the model's history as one pair. README, `docs/status.md` and `docs/tops/RENDER_WORKSPACE.md` say where the controls are. Both later commits were pushed 10/2 at 14:37; CI run 37048729409: passed on all six jobs. |

Rulings behind it, ratified by Joe on 10/1 with "Use recommendations" (`claude/SPATIAL_BLUEPRINT.md`): R-5 lifts
rule D-1 for exactly these two tools; R-6 makes the trail host-made guide geometry, written by the handler; R-7
keeps Oct 7 to a scene that is already there; R-8 adds D6 to the done table; R-9 freezes D5 at three recipes.

Rulings behind the row of three, from one Jev request on 10/2 at 10:10 (`.token-saver/legs/orchestrate_fri_panel.json`):
R-10 proposes one row of three with a slash twin, the label being Joe's call; R-11 makes a click panel-local, with
no model call (1.00 at confidence 0.99); R-12 parks the control for the demo (need 0.32) and leaves building it
before the freeze to Joe, whose "B - Row of three" was that word.

## Evidence

- **Mile 0, the probe.** `.token-saver/spatial/spatial_probe.json` (probe_spatial.py, 10/1 20:21, hython 22.0.400,
  a copy of rc3_demo.hiplc, sha256 unchanged). The Camera LOP's parms, evaluated per frame without moving the
  playhead, against the stage cooked per frame: 0.0 mm and 0.0 deg at the worst of 120 frames; the parm read took
  0.004 s and the per-frame cook 0.92 s. Gates P1 (parms match the stage, read under 3 s, arc recovered), P2
  (clearance matches an independent computation) and P3 (the trail cooks clean) all true. The probe's collider
  sub-step raised (a PackedGeometry has no positionAt); the collider was measured later through the tool.
  `probe_camlop.json` holds the Camera LOP facts: the transform-mode menu, `lookatenable`, `sample_behavior` single.
- **The read and the trail, live.** `.token-saver/spatial/live_spatial.json` (live_spatial.py, 10/1 21:59, final
  code): 17 steps, 0 errors, the demo hip's sha256 unchanged. The read: arc, radius 6.00 m, 20.0 deg, 2.094 m of
  travel, height 1.29 m; nearest splat centre 1.04 m, left, frame 1, 500,000 points; 0.671 s; 1,452 characters;
  stage_check agrees at frames 1 and 60 with 0.0 mm and 0.0 deg; scene, frame and undo stack unchanged.
  `node: "/stage"` reads the display node. UNKNOWN with an extra transform op downstream: sampled 0, clearance
  null, stage_check off by 200.0 mm, the trail refused with nothing built and no undo entry. The trail: created,
  144 points, proxy, display flag unmoved; again: unchanged; `1-120x5`: updated, 31 points; two undos restore the
  start; a forced failed write is withdrawn. With the collider referenced: nearest mesh vertex 1.287 m, below,
  frame 1, 24,643 vertices.
- **Under the panel's undo wrapping.** `.token-saver/spatial/live_nested.json` (live_nested.py, 10/1 22:10): under
  an outer undo group and through `execute_through_bridge` with the production path forced on, the trail is one
  undo entry (fidelity 1.0) and one undo removes it; a forced failed write is withdrawn there too.
- **Karma and the trail's purpose, rendered.** `.token-saver/spatial/render_purpose_check.json`
  (render_purpose_check.py, 10/1 22:20; husk, Karma CPU, 320 x 180, 16 samples, a check camera looking at the path,
  the world hidden). No trail against the proxy trail: hoiiotool --diff PASS. No trail against the same trail at
  purpose default: 3,744 pixels (6.5%) differ, max error 1.0. Verdict EXCLUDED, with a control that can fail.
- **Through the panel worker.** `.token-saver/spatial/bench_spatial_f1.json`, `_f2.json`, `_f3.json`
  (bench_spatial.py, 10/1 21:55-21:58, final code, deepseek-v4.1-flash:cloud, the bridge's production path forced):
  four requests, three repeats, 12 of 12. Trail 3.8 / 3.0 / 3.3 s, read 3.0 / 2.7 / 2.6 s, each one tool call in
  two rounds; UNKNOWN 4.2 / 3.9 / 6.4 s, the third with two further read-only calls; after a Scatter build 2.7 /
  2.5 / 3.2 s with the section boxes unchanged. No vendor name in any reply or tool result.
  `bench_spatial_s1.json`, `_s2.json`, `_s3.json` (22:30): the run sheet's own prompt, on the plain scene and after
  a Scatter build, 6 of 6 in one trail call each, 2.8 to 4.8 s; one passed `node: "/stage"`. The earlier
  `bench_spatial_r1..r3.json` (21:42-21:45) are the run that found the two things fixed before the commit: all
  three UNKNOWN replies read the stage check's mismatch as a position, and one trail turn passed `node: "/stage"`
  and was refused.
- **Review.** One Fable pass on the wiring diff before the commit. Its must-fix (the trail's build redrew another
  build's section boxes) and its false-SUCCESS classes are fixed and pinned by tests.
- **Tests.** The six spatial and build_graph files under hython 22.0.400: 185 passed. The main checkout with the
  spatial commit, the CI command, Windows, Python 3.14: 10,707 passed, 426 skipped, 176 deselected, 5 xfailed,
  0 failed (`.token-saver/spatial/suite_ci.log`). With the two later commits: 10,735 passed, 426 skipped, 176 deselected,
  5 xfailed, 0 failed, in 486 s (`.token-saver/b3/suite_ci.log`). Release tree: 10,734 passed, 427 skipped, 176 deselected, 5 xfailed, 0 failed, in 429 s
  (`.token-saver/release/pytest_release_tree_v5930.log`). A first run of the same tree, started from a tool whose
  environment hides Python's user site, skipped 32 more tests (Pillow, opencv, filelock, transformers): 10,702
  passed, 459 skipped, 0 failed (`pytest_release_tree_v5930.userbase.log`). `harness/jev/tests` on the release
  tree: 88 passed. `sync_version.py --check` and
  `harness/notes/readme_check.py`: both PASS.
- **The spatial commit: the transfer.** The work was written in a cloud clone and typed onto the workstation. The committed tree is
  byte-identical to the tested one: `git write-tree` gave `00c0b9fdd5db882473318968e0b0346feddc8b7f` on both.
- **GUI, the first test.** `.token-saver/receipts/d6_gui.json` (10/2, 10:51-11:02; recorded as `2026-10-02 10-51-30.mp4`, 654.7 s, 3840 x 2160;
  Houdini 22.0.400 with the panel on `95fb0af5`; deepseek-v4.1-flash:cloud; driven by Claude through computer use on
  Joe's "go", Joe hands-off; the demo hip's sha256 unchanged). Turn 1, the run sheet's prompt: one
  `synapse_spatial_trail` call (0.713 s), no permission prompt, the tool's numbers in the reply, one node between
  `demo_cam` and `demo_settings`, display flag unmoved. Edit > Undo ("Undo SYNAPSE: synapse_spatial_trail: {}")
  removed the curve and its node in one step, twice. With the viewport on Houdini VK and no camera the curve showed,
  with its ticks and its colour ramp; through `demo_cam` it starts at the lens and is out of frame; Karma XPU in a free
  view was not tried. Findings: (1) no turn receipt and no REVERT control after a trail turn, because
  `_turn_evidence` credits tools by keyword (`_MUTATORS`) and `synapse_spatial_trail` matches none; (2) the same
  prompt after the undo made two calls (`synapse_spatial_path`, then `houdini_query_prims`, which failed for want of
  a node path) and the reply said the trail was still in the scene, which it was not; "Redraw the path." then redrew
  it in one call; (3) the integrity record read `delta_hash: no_change` with equal scene hashes across both builds,
  as in the forced-bridge run. Jev on the replies (1 request, 3,513 / 269 tokens, `DDD.testrun.jsonl` leg D6-gui):
  reply 1 states the move 0.98, the clearance 0.98, drawn and how to reverse 0.96, invents 0.16; reply 2's claim
  supported 0.12; reply 3 invents 0.65, with no reason given, and read against its tool result nothing in reply 3
  contradicts it. Not tested in this test: REVERT (there was no control; the second check clicked it), Ctrl+Z as a keystroke, the order after a
  Scatter build, clearance against the collider, voice, and Joe at the panel.
- **The row of three: the transfer.** Both later commits were written in a cloud clone and moved to the workstation
  as two patches (`.token-saver/b3/0001_fix_receipt_credit.patch`, sha256 `faa1640e...`; `0002_feat_row_of_three.patch`,
  sha256 `94fa8440...`). The trees are identical in the cloud and on the workstation: `820b58d9...` after the fix
  and `78e342b9...` after the feature (`apply_b3.py`, `commit_b3.ps1`). After the push the cloud clone fetched the
  two commits and read the same two trees.
- **The row of three: tests.** `.token-saver/receipts/b3_build.json`. New: `tests/test_spatial_action.py` (7),
  `tests/panel/test_spatial_button.py` (15), `tests/panel/test_turn_receipt_credit.py` (6).
  `tests/native_render_workspace.py` under hython 22.0.400: passed, 6 checks, 5 layouts. The panel tests under
  hython, with three test jobs sharing the machine: 580 passed and 33 failed, against 547 and 34 on `95fb0af5`. The
  three tests that differed were re-run alone, three times each: 9 of 9 passed on the build, and
  `test_narrow_empty_invitation_and_busy_actions_never_paint_clipped` failed 3 of 3 on the base. The panel tests on
  real Qt (PySide6 6.8.3, offscreen, Linux): 564 passed and 12 failed, against 529 and 15; no new failure. The CI
  command under Python 3.11 on Linux: 10,414 passed and 1 failed (`test_project_dir_sanitization`, which fails only
  in that sandbox).
- **The row of three: the real widgets, offscreen.** `click_real_panel.py`, run once after the build and not a test
  in the repo: the real `SynapsePanel` on PySide6 6.8.3, with the tool call and Houdini's undo stack stubbed, at
  640 x 900 and 340 x 760. The real Spatial, REVERT and Send controls were clicked: one tool call, no model worker,
  the answer with its not-measured line and its undo line, the signature, `1 CHANGE`, REVERT restoring the stubbed
  undo stack, `/spatial` through Send, and both refusals. Measured (`measure_narrow.py`): the footer is 126 px at
  640 wide and 171 px at 340 wide, on the base and on the build. At 2.25x text on a 341-wide dock the footer's
  content is 202 px longer and scrolls inside the same 81 px.
- **GUI, the second check.** `b3_build.json`, `gui_check` (10/2, 14:12-14:21; recorded as
  `2026-10-02 14-15-08.mp4`, 349.0 s, 3840 x 2160; Houdini 22.0.400 with the panel on the working tree whose tree
  id is `78e342b9...`, the tree later committed as `45210b3c`; driven by Claude through computer use on Joe's
  "continue", Joe hands-off; the demo hip's sha256 unchanged). Every step passed: the layout; Identify from the
  footer; a Spatial click at 14:16:16 (the tool's sentence, the signature, `1 CHANGE` and REVERT, `demo_cam_path`
  between `demo_cam` and `demo_settings`, 1,317 ms in the tool, no worker send in the log); REVERT, twice;
  Edit > Undo, one step; REVERT refused on a receipt already undone by hand, with nothing changed; `/spatial`; a
  click during a running task, refused; an empty scene and a scene with one Sphere LOP, each answered with the
  tool's reason and no receipt. One model turn in the whole check, the question in the busy step, answered from
  the click's line in the history with no tool call. A first attempt at 12:36 saw only white windows: the monitor
  was switched to another machine, so the workstation had no display. Not seen: the tooltips, the path in the
  viewport, a 340-wide dock, the Ctrl+Z keys, a receipt after a spoken turn that draws the path, and Joe at the
  panel. Found: the receipt stays after a hand undo; the empty-scene reason ends in a hint written for a model; the
  memory store logs a failed start and a retry on each scene change.
- **Jev on the build's decisions.** One request, 10 questions (1,703 / 291 tokens, 326 ms;
  `.token-saver/legs/build_b_jev.json`; ledger `DDD.design.jsonl`, leg FRI-build-B). Applied by code: the answer is
  a SYNAPSE message (0.90), the click is not echoed (0.88), a click during a task is refused (0.89), the tooltip
  says what the artist gets (0.87), the command row's title (0.89). Under the gate and decided for Joe: one row at
  340 wide (0.70 at confidence 0.41) and the click entering the model's history (0.65 at confidence 0.30).
  Overruled by code: "the rail change is in frame" at 0.40, because Identify does leave the rail.
- **Prepared in a worktree.** The release tree was built in `.claude/worktrees/rel-v5930` (branch
  `release/v5.93.0`) on `45210b3c`, after that commit was pushed. The same mechanical edits were made in a cloud
  clone, and the eight edited files are blob-identical there. The CI command ran on
  that tree under Python 3.11 on Linux: 10,414 passed, 756 skipped, 50 deselected, 3 xfailed and 1 failed
  (`test_project_dir_sanitization`, which fails only in that sandbox and passed in GitHub's Ubuntu jobs on
  `45210b3c`). `harness/jev/tests` there: 87 passed, 1 skipped.
- **Jev.** Jev checked the 46 claims in the release notes' validation section in four requests, each against the
  receipts its claims rest on (`.token-saver/release/jev_notes_v5930.py`; the guard's own check stops at 20
  claims). 44 came back partial and 2 not a claim. None came back unsupported and none went unanswered. The 44
  partial ones went to a direct read against the receipts, and all 44 stood as written. Tokens in / out per
  request: 11,481 / 228, 8,249 / 273, 11,658 / 639, 14,393 / 961; 1544 ms in all. Ledger: `harness/jev/ledger/v5.93.0.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.93.0.** Two new tools: the minor version moves.
- **Splats first.** With splats on the stage, `against: auto` measures splat centres and lists mesh prims as left
  out. The blueprint said mesh first; the demo world's visible surface is the splats, and its collider is not on
  the stage until a Scatter build references it.
- **The worker may call the trail.** It joins the builder allowlist on the argument that already holds for
  build_graph: one undo-grouped call of inform-level primitives, and its schema carries no code.
- **Two result changes after the first bench.** `stage_check` replaced `confirmed_against_stage`, and a LOP
  network's path is accepted as its display node.
- **Wording left as it is.** The provenance sentence and the `robust_min_m` field were each misread once by the
  model in nine replies. Both are parked, not changed, so the release is the code that was benched.
- **One release for three commits.** Joe's "Commit, git push & git release" answered a stated recommendation: one
  v5.93.0 carrying the two tools, the receipt fix and the row of three. The drafts written for the tools alone were
  widened, and the limit "No turn receipt after the trail" came out.
- **A keyword, not the principled fix.** The receipt still credits tools by name. Two keywords close the gap for the
  build tools and a test pins them. Crediting from the undo stack is parked.
- **Three calls made for Joe, each changeable.** The label is `Spatial` (Jev split it: `Spatial` 0.49,
  `Read the shot` 0.47). At 340 wide the three stay on one row. A click enters the model's history as one
  ask-and-answer pair.
- **The click runs off the Qt thread.** The blueprint said the main thread. Waiting for the main thread from the Qt
  thread is the deadlock the executor's off-main path exists to avoid, so the click runs on a worker thread and the
  executor marshals the tool onto the main thread.
- **Released before Joe's own look.** The blueprint's done list for the row of three ends in one GUI check by Joe.
  That check has not happened. The recorded check was driven by Claude, and the notes say so.

## Not in this release

`describe`, `classify` and `frustum` (still unregistered); footage-in; a trail that follows the camera; removing a
failed build's nodes inside the panel's undo step; clearance to surfaces; cameras that no Camera LOP authors; a receipt credited from
the undo stack; clearing a receipt after a hand undo; an artist's wording for the empty-scene reason; the
conversation at half the panel on a narrow dock.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.
