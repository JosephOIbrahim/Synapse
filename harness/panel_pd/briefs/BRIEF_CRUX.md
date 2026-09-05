# BRIEF — PD-CRUX (TRUST · referee · read-only)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§1, §3 all legs, §3 PD-CRUX, §4), `docs/panel_pd/COHERE_REFERENCE.md`, every `docs/panel_pd/REPORT_*.md` on this branch. Branch `pd/panel-integrate` = LEVER + CAMERA + SWEEP_A + SWEEP_B merged by the orchestrator. You have **no write grant** on code: your only outputs are `docs/panel_pd/CRUX_VERDICT.md` and `harness/panel_pd/runs/<date>/crux.json`. You did not build this and you are motivated to break it.

## Method
1. **Re-run every Accept in a fresh checkout.** Use `git archive HEAD | tar -x -C <scratch dir>` to get a clean tree, then run each leg's accept commands there (guard test, docking test, Expert pin, density rule, census script, sweep tests, full `python -m pytest tests -q -p no:cacheprovider`). Bind the run: assert `synapse.__file__` is inside the scratch tree (the editable `.pth` shadows scratch unless the test binds its own tree — confirm baseline-green first, then trust). Record commit, module path, runner command, counts.
2. **Mutations — each must turn a test red.** In the scratch tree only, one at a time, restoring between:
   - remove `rhythm.apply` from the recompose path;
   - set `density` to an unknown value;
   - re-add one untagged `setStyleSheet(` in a migrated file;
   - add one hex literal in a migrated file;
   - widen airy until 380 px docking fails.
   A mutation that stays green is a finding: the guard is not guarding.
3. **Audit the neighbours.** For every REPORT claim, look for the same bug-class in sibling files; for every exemption tag, decide if the reason holds; for every hex mapping, spot-check role rationale against the three-source cyan/blue trap.
4. **Crucible lines from the plan** per leg: `fontload.py` untouched; density rules carry margin only; standard emits no density block; `compositor.py` diff ≤ 20 lines; lifecycle/timer lines in `synapse_panel.py` untouched; `face_token` refresh path unchanged; a migrated widget whose look changed beyond gap/label/tag is BROKEN; any unmapped hex or added token is BROKEN; Voronoi/Cohere-palette/font-family imports are BROKEN.

## Output
`docs/panel_pd/CRUX_VERDICT.md`: verdict per leg `SOUND | SOUND-WITH-NITS | BROKEN` with `chain_broken_at`, each mutation with the test that went red (or the finding that none did), the neighbour findings, and the nits list for `harness/notes/panel_nits_pd.md`. `crux.json` mirrors it machine-readably. BROKEN does not ride; the orchestrator reads verdicts before any merge word reaches Joe.

STATUS → `harness/panel_pd/STATUS_CRUX.md` (this and the two outputs are your entire write set).
