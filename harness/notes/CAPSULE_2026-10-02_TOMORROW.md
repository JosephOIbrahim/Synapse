# Capsule — for tomorrow-you (written 2026-10-01, about 16:10)

```
+== PROJECT CAPSULE: SYNAPSE, Demo Done Day (Wed 10/7 11:00) ===================+
| WHERE WE ARE:        v5.92.0 published and Latest (5c319d52, CI 6 of 6 green). |
|                      Pieke bar: Scatter Instances, Karma blocker and Render    |
|                      Passes build in one call, 9 of 9 headless runs (were 0    |
|                      of 3). Houdini relaunched 15:59 on rc3_demo.hiplc, so it  |
|                      runs v5.92.0; the Synapse pane is not added yet.          |
| MILE MARKER:         Pieke bar: mile 5 of ~8. Freeze: Tue 10/6 EOD. First take |
|                      attempt: Mon 10/5.                                        |
| WHAT I WAS THINKING: The drops were missing knowledge, not the model (Jev      |
|                      0.99). Recipes plus the type hint fixed them. Latency is  |
|                      model rounds, not tools (under 1 s of tool time a turn).  |
| NEXT ACTION:         Fix the 25-round cap that ends a reply mid-sentence, then  |
|                      rerun bench3 three times (.token-saver/pack/bench3.py).   |
| BLOCKERS:            Joe's: add the Synapse pane and Connect; eyes on REVERT,  |
|                      labels and narration in the GUI; is anything of yours in  |
|                      rc3/backup/rc3_demo_bak2.hiplc; pick the on-camera Pieke  |
|                      beat (Jev leaned Scatter, 0.63); OBS crop OK.             |
| ENERGY REQUIRED:     Low to start (one code fix plus a bench run). Medium for  |
|                      the next Pieke workflows.                                 |
| IDEAS PARKED:        roster trim (62k chars a round); the prompt's scout line; |
|                      stage_info with no node; 7 more in-lane workflows; model  |
|                      benchmark; Houdini dialogs open too small at this UI      |
|                      scale (Quit, Project rules); new windows capture white.   |
+===============================================================================+
```

## Where things live

- Bench: `.token-saver/pack/bench3.py` (the panel worker as the panel builds it, headless, fresh scene copy per
  request); receipts `bench3*.json`; summaries `bench3_summary.py`, `bench3_reps_check.py`.
- Recipes: `python/synapse/routing/solaris_recipes.py`; proof `.token-saver/pack/recipes_proof.json`.
- Type hint: `python/synapse/core/type_suggest.py`.
- Release: `docs/releases/v5.92.0.md`, `harness/notes/RELEASE_v5.92.0.md`, scripts in `.token-saver/release/`.
- Plan and run log: project doc `claude/DEMO_DONE_DAY_BLUEPRINT.md`; take steps `claude/TAKE_RUN_SHEET.md`.
- Jev routing for the next legs: `.token-saver/legs/jev_legs13.py` -> `pieke_baseline_route.json`.

## Words that unlock things

- "go" - the next fix (the 25-round cap), then the bench three times.
- "the beat is <scatter | blocker | passes>" - the on-camera Pieke request for the take.
- "push" / "release" - the ritual: full suite, commit, tag_release.py, push master, release_ci_gate.py, then
  push the tag and `gh release`.

## Three things learned today worth keeping

1. Run the full suite before any commit, not just the tests near the change. Two repo-wide guards (the
   emitted-types artifact and the except ratchet) turned CI red once today; ce280144 fixed it.
2. Configure Primitive writes visibility as a time sample. Read USD at the current frame, or an invisible prim
   reads `inherited` (fixed in get_usd_attribute).
3. Houdini's Quit dialog opens empty at this UI scale. To quit remotely: in the Python shell,
   `hou.hipFile.saveAsBackup()` and then `hou.exit(suppress_save_prompt=True)`. Never save over rc3_demo.hiplc
   (sha d3c86829).
