# BRIEF — PD-SWEEP-B (BUILD · mechanical sweep + the eight hex modules + legacy pair)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§1, §3 PD-SWEEP-B, §4), `docs/panel_pd/COHERE_REFERENCE.md`, `docs/PANEL_RHYTHM_SPEC.md` v2, `python/synapse/panel/designsystem/rhythm.py`, `designsystem/tokens.py`. Branch `pd/panel-sweep_b` (from `pd/panel-lever`). Your leg brief is **§3 PD-SWEEP-B**.

## Deliverables
1. `hda_views.py` · `tool_palette.py` · `command_palette.py` · `working_indicator.py`: the same migration as SWEEP-A (roles for spacing; objectName/role + QSS for inline styles, appended in your own fenced block `# --- SWEEP_B (...)` at the end of `designsystem/qss.py`, append-only).
2. The eight hex modules — `vex_tutor` · `apex_trace` · `apex_explainer` · `scene_doctor` · `performance_profiler` · `network_trace` · `cross_scene` · `message_formatter`: each hex → the nearest **existing** token by role (ink, muted, surface, signal, warm, hot). Check the mapping table in beside the diff: `docs/panel_pd/HEX_MAPPING_SWEEP_B.md` with columns `file · line · hex · token · role rationale`. No new tokens. Known trap: cyan/blue currently resolve from three sources — map by *role in context*, not by nearest RGB distance; say which source you chose and why.
3. Legacy pair: run `python .synapse/verify.py no-importers python/synapse/panel/tokens.py python/synapse/panel` (if that verifier is absent at this commit, do the import census with `rg`/AST and record the command). If only `styles.py` imports `tokens.py` and nothing imports `styles.py`, delete both; else keep them and record a `finding` in the REPORT with the importers.
4. Lower `harness/panel_pd/RESIDUAL.json` (only down). Tag true exemptions on the same line with `# rhythm-exempt: <why>`.

## Tests
`tests/test_panel_sweep_b*.py`: a test that every hex in the diff appears in the mapping table (parse the table; scan your files for 6-digit hex; assert zero unmapped and zero remaining in the migrated files); headless spacing checks for the four widget modules; the guard, docking, Expert pin, density rule all green.

## Accept (from the plan)
Census → 0 for these files; mapping table exists; `pytest -q` green. Crucible: any hex not in the mapping table is BROKEN; any token added is BROKEN.

REPORT → `docs/panel_pd/REPORT_SWEEP_B.md`; STATUS → `harness/panel_pd/STATUS_SWEEP_B.md`.
