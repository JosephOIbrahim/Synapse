# Release preparation: v5.93.3

Publish one commit on top of v5.93.2 (tag `v5.93.2` on `860c4b0f`). Joe's words, 2026-10-03, from his phone: at
about 16:10, "Close Houdini via Hython or Hou and try to fix the scatter"; at about 16:20, "merge";
then "commit, git push, git release".

| Commit | What it does |
|---|---|
| `c13b1d7c` | SCATTERANGLE. `routing/solaris_recipes.py`: the Scatter Instances recipe's `maxangle` goes from 45 to 20, and its notes name `enablecameramaskfar` and `cameramaskfar`. `tests/test_scatter_recipe_mask.py` (3 tests). |

## Evidence

- **The measure.** `.scratch/freeze/hy_scatter2.py`, hython 22.0.400, `rc3_demo.hiplc`, the recipe's payload built
  with `hou`, nothing saved. Ground is the tenth-percentile instance height in each 2 m bin of z; an instance is
  off the lane when it sits more than 0.35 m above that. The lane's tenth percentile runs from -0.03 m near the
  camera to 1.25 m at z -46 (`.scratch/freeze/an_pos.py`).
- **The variants** (`hy_scatter2_out.log`, on v5.93.2's recipe with one parameter changed at a time): 45 degrees
  763 instances and 73 off the lane, 5 within 26 m, worst 6.33 m; 30 degrees 731 and 34; 20 degrees 758 and 12,
  none within 26 m, worst 2.13 m; 20 degrees with sharpness 1, 769 and 26; a 26 m far plane alone 407 and 7; far
  plane with 30 degrees 410 and 0; far plane with 20 degrees 469 and 0, worst 0.18 m; a 20 m far plane with 20
  degrees 367 and 0; ambient occlusion 887 and 88.
- **The branch's recipe** (`hy_branch_out.log`, the payload from `c13b1d7c`): 758 instances, 12 off the lane, none
  within 26 m, worst 2.16 m. No missing parameter, no node error or warning.
- **v5.93.2 in the GUI.** Houdini 22.0.400 relaunched on `860c4b0f` at 15:21, computer use, typed,
  deepseek-v4.1-flash:cloud. Saved, not reviewed: `2026-10-03 15-32-30.mp4`. From the turn ledger and the panel's
  conversation (`.scratch/freeze/runthrough2.py`): Beat 1 at 15:32:57 in 22.6 s with 8 calls; Scatter at 15:33:36
  in 25.9 s with 18 calls, the build call carrying `enabledirection` 1 and `maxangle` 45, 763 instances; a recall
  at 15:35:03 in 6.4 s. Slowest tool call 0.90 s. At 15:38, off the recording, a turn asked to call
  `synapse_recall` for heightfield terrain replied that one knowledge reference came back, and no card showed
  under it. The four recorded turns did not call `synapse_recall`.
- **The suite.** The CI command on `c13b1d7c`, Windows, Python 3.14 (`.scratch/freeze/pytest_scatter_angle.log`):
  10,782 passed, 428 skipped, 183 deselected, 5 xfailed, 0 failed. Not re-run on the release tree: the release commit changes version strings and documents only,
  and CI runs on it before the tag is pushed.

## Decisions

- **20 degrees, without the far plane.** The far plane gets to zero off the lane and cuts the count from 758 to
  469, and its distance is a property of the scene. It is named in the recipe's notes and left to the scene.
- **Merged and released before the take, on Joe's word.** Jev read "park until after the take" at 0.88 for the
  first mask at about 12:20. Joe's "merge" came after a message that named that read.
- **No agent bench.** The bench opens the live memory store, which waits on Joe's word.
- **v5.93.3, not v5.94.0.** One parameter and a note.
- **JEV.** No Jev request was made for the choice of angle; the measurements above decided it. For the notes, Jev checked the 11 claims in the validation section in one request (`harness/jev/ledger/v5.93.3.release.notes.jsonl`): 10 came back partial and 1 not a claim, none unsupported, with the highest unsupported probability 0.32, on the closing sentence about inherited limits. They went to a direct read against the receipts. Two sentences were reworded before the ledgered request: the three headless runs that carried the 45-degree mask ran on the recipe before v5.93.2 was cut, not on v5.93.2, and the new memory row is reported as a row count and a recital, since what wrote it was not traced. All then stood. The first request's row is kept outside the tree as `jev_notes_v5933.firstpass.jsonl`.

## Not in this release

- **A GUI check of the 20-degree mask.** Houdini is closed, on Joe's word.
- **The scatter records in the memory store,** now four, and the bridge rows. Removing them needs Joe's word.
- **Whatever writes a decision record after a Scatter build.**
- **The far plane as a recipe default.**
- **A Windows Setup.**
