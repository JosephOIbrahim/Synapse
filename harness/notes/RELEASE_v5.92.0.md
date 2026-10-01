# Release preparation: v5.92.0

Publish four commits on top of v5.91.0 (tag `v5.91.0` on `ef9ac022`). Joe's word, 2026-10-01: "Yes and git
release (bump the number)", after the four commits were made and pushed on his earlier words ("Yes! Absolutely";
"Push after push, hint first, the commit"; "Yes").

| Commit | What it does |
|---|---|
| `7f0b898a` | Round-3 camera polish: REVERT undoes only SYNAPSE's own turn (panel/turn_revert.py), framing outside undo, label-aware inline spacing, narration paragraphs, prompt rules (inspect once, say you cannot see, state values set) |
| `7cc1e427` | Pieke pack: routing/solaris_recipes.py (three verified one-call recipes), KnowledgeIndex serves them for the artist's words, prompt names the types; get_usd_attribute reads at the current frame |
| `ce280144` | CI fix for 7cc1e427: emitted_node_types.json regenerated; the frame read's silent except removed (except ratchet) |
| `af30580c` | Type hint: core/type_suggest.py; houdini_create_node and build_graph name the closest real types; build_graph no longer points at synapse_scout |

## Evidence

- **Baseline, v5.91.0 plus the then-uncommitted round 3.** `.token-saver/pack/bench3.json` (bench3.py: the
  panel worker built as the panel builds it, enforce_worker_policy=True, deepseek-v4.1-flash:cloud, hython on a
  fresh copy of rc3_demo.hiplc per request). Scatter 123.3 s, no PointInstancer, ended at stop_reason=length;
  blocker 32.4 s, 15 failed houdini_create_node calls; passes 165.4 s, two usdrender ROPs in /out and a prune,
  0 RenderPass prims. Round 3 (12:46-12:49) was in the working tree for this baseline and for every later run.
- **Three repeats on the release code.** `.token-saver/pack/bench3_rep1.json`, `bench3_rep2.json`,
  `bench3_rep3.json` (14:44-14:47): 9 of 9 built; scatter 28.0 / 28.2 / 33.6 s, 531 instances each; blocker
  18.3 / 8.6 / 18.1 s, light:filters -> KarmaBlockerLightFilter each; passes 13.5 / 11.7 / 10.7 s, two RenderPass
  prims each; display demo_settings, clean badges, finished replies (bench3_reps_check.py). These ran before
  af30580c; the type hint does not touch the recipe path.
- **Recipes through the real tool.** `.token-saver/pack/recipes_proof.json` (recipes_proof.py,
  worker._execute_tool_block): three builds, parms_missed [], badges clean; scatter 531 instances, collider mesh
  ComputeVisibility invisible; blocker light:filters -> KarmaBlockerLightFilter; passes /Render/Passes/beauty and
  /Render/Passes/isolate including /World/cobblestone_lane and /lights.
- **Current-frame read.** `.token-saver/pack/probe_vis.py` output: visibility time samples [1.0]; Get() default
  'inherited'; Get(frame 1) 'invisible'; mesh computed 'invisible'.
- **Type hint.** `.token-saver/pack/probe_hint.py` (217 Lop types, about 3 ms per query) and
  `probe_hint_tool.py` (worker tool path: karmablocker -> karmablockerlightfilter first; gobo -> look-up sentence;
  build_graph lightfilter -> closest real types, nothing created; stage unchanged).
- **Tests.** tests/test_solaris_recipes.py 22 passed; tests/test_type_suggest.py 17 passed. Full `tests/` suite,
  Windows, Python 3.14, on af30580c's tree: 10,681 passed, 482 skipped, 5 xfailed, 0 failed
  (`.token-saver/pack/suite_typehint3.log`). CI on 7cc1e427 (run 36909916600) failed 2 of 10,541 (the emitted
  types artifact and the except ratchet); ce280144 fixes both. Release tree, the CI command
  (`-m 'not needs_houdini'`), after the release edits: 10,617 passed, 426 skipped, 120 deselected, 5 xfailed,
  0 failed (`.token-saver/release/pytest_release_tree_v5920.log`). `sync_version.py --check` PASS;
  `harness/notes/readme_check.py` PASS.

- **Jev.** Jev checked the 15 claims in the release notes' validation section against the commits since
  v5.91.0, the code diffs, the new tests and the receipts above (`.token-saver/release/jev_notes_v5920.py`).
  All 15 came back partial and none unsupported (unsupported at most 0.05), so each went to a direct read. Two
  were tightened: the baseline now says round 3 was already in the working tree, and the repeat line no longer
  claims the collider was invisible in each repeat (the repeat bench did not check it; the recipe proof did).
  The rest stood. Ledger: `harness/jev/ledger/v5.92.0.release.notes.jsonl`.

## Decisions

- **Source release.** No installer was asked for; the v5.86.0 Setup stays the download.
- **5.92.0.** New recipes, a new knowledge path and new tool-error content: the minor version moves.
- **Two commits for the panel and the pack.** Round 3 was written before the pack and had not been reviewed;
  it was read before its commit and committed first, so the pack carries none of it.

## Not in this release

The 25-round cap ending a turn mid-sentence; the response-token-limit stop (avoided, not fixed); the prompt's
conditional synapse_scout mention; houdini_stage_info called without a node; the other in-lane Pieke workflows
(W1, W2, W4, W5, W7, W8, W9); the model benchmark; a recorded GUI run of a Pieke request.

This record does not claim that the later CI, push or publication steps have completed. They are checked after
publication.
