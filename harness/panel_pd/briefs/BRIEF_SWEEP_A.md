# BRIEF — PD-SWEEP-A (BUILD · six panel modules)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§1, §3 PD-SWEEP-A, §4), `docs/panel_pd/COHERE_REFERENCE.md`, `docs/PANEL_RHYTHM_SPEC.md` v2, `docs/PANEL_REGION_MAP.md`, `python/synapse/panel/designsystem/rhythm.py` and the role rules in `designsystem/qss.py`. Branch `pd/panel-sweep_a` (from `pd/panel-lever`). Your leg brief is **§3 PD-SWEEP-A**.

## Deliverables
Per file, in this order: `chat_panel.py` · `face_review.py` · `gate_widget.py` · `context_bar.py` · `face_work.py` · `quick_actions.py`.
- Every `setSpacing` / `setContentsMargins` → a `rhythm_role` on the owning widget (the compositor's `rhythm.apply` sets the numbers). Remove the imperative call.
- Every inline `setStyleSheet` → an objectName or role + a QSS rule appended to `designsystem/qss.py` **inside one comment-fenced block at the end of the file**: `# --- SWEEP_A (chat_panel.py)` … grouped by file. Append-only; never touch LEVER's rules or anything outside your block.
- Nothing changes structurally: same widgets, same hierarchy, same signals. A widget whose look changed beyond gap / label / tag treatment is BROKEN under CRUX.
- Where a site truly cannot map to a role without structural change, keep it and tag it on the same line: `# rhythm-exempt: <why>`; list every exemption in the REPORT. Lower `harness/panel_pd/RESIDUAL.json` accordingly (only down).

## Tests
`tests/test_panel_sweep_a*.py`: headless (`QT_QPA_PLATFORM=offscreen`, `SYNAPSE_REDUCED_MOTION=1`) instantiation of each migrated widget with a role → spacing equals `tokens.gap(base, density)` for the three densities; negative control: role removed → spacing unchanged. Run the guard (`tests/test_panel_rhythm_owner.py`), docking, Expert pin, density rule.

## Accept (from the plan)
Census for these six files → 0 / 0 / 0; `panel_shot.py` diff shows rhythm-only change (PNGs under `design/rhythm_pd/sweep_a/{before,after}/` if hython is bound, else NOT_RUN stated); Expert pin green.

REPORT → `docs/panel_pd/REPORT_SWEEP_A.md`; STATUS → `harness/panel_pd/STATUS_SWEEP_A.md`.
