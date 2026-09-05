# BRIEF — PD-CENSUS (TRUTH · probe)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§0, §1, §3 PD-CENSUS, §4), `docs/panel_pd/COHERE_REFERENCE.md`. Branch `pd/panel-census`; the worktree is the current directory. Your leg brief is **§3 PD-CENSUS** of the plan; this file only adds grounding and deltas.

## Deliverables (the plan's T1 + T2, grounded)

1. `harness/notes/panel_rhythm_census.py` — pure Python (AST + regex), source-only, no `hou`, no Qt, runs in stock CI. Per file under `python/synapse/panel/` (excluding `designsystem/`): `setSpacing`/`setContentsMargins` sites **with values**, inline `setStyleSheet(` sites, foreign hex (both raw sites and distinct values), objectNames present, `# rhythm-exempt:` tags. Per camera region: reachability (named? styled inline? layout-owned?). Emits `harness/panel_pd/runs/<YYYY-MM-DD>/rhythm_census.json` and `.md`. Make it a CLI with `--json <path>` and `--md <path>` and exit code 0 always (it reports; the guard test in LEVER enforces).
2. `docs/PANEL_REGION_MAP.md` — every visible region → widget ids → `file:line` of its spacing owners → target role from the plan's §4 table. Camera regions first, in the order seen: profile tab strip · header/ribbon · chat transcript · verb rail · recall result · TOKEN face. The plan lists `synapse_shelf.py` as a CAMERA file; **it does not exist** at this commit — find the real owner of the shelf/ribbon/header (grep `shelf`, `ribbon`, `header`, `DsHeader` across `python/synapse/panel/`) and name it explicitly in the region map, because CAMERA's write set is defined by your answer.
3. Reproduce the plan's totals and state the deltas as findings (the contract already re-grounded 107 / 106 / 135 raw hex sites / 0 exempt at this commit; the plan said 108 / 106 / ~60 distinct / 24 `Ds*` names). A mismatch is a finding, not a fail. Also count widgets with a `Ds*` objectName and the density-keyed QSS rules that exist today.
4. A small pure-Python test `tests/test_panel_rhythm_census.py` that runs the script against a fixture snippet and checks the counters (positive + one negative control per counter).

## Accept (from the plan)
Census JSON with totals; region map lists all six camera regions with owners. REPORT to `docs/panel_pd/REPORT_CENSUS.md`; STATUS lines to `harness/panel_pd/STATUS_CENSUS.md`.
