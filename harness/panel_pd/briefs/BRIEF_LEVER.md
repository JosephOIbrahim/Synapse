# BRIEF — PD-LEVER (BUILD · designsystem + compositor + tests)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§1, §3 PD-LEVER, §4), `docs/panel_pd/COHERE_REFERENCE.md`, `docs/PANEL_RHYTHM_SPEC.md` (v1, note its §5 honesty ledger), the CENSUS outputs on this branch (`docs/PANEL_REGION_MAP.md`, `harness/panel_pd/runs/*/rhythm_census.json`, `docs/panel_pd/REPORT_CENSUS.md`). Branch `pd/panel-lever` (from `pd/panel-census`). Your leg brief is **§3 PD-LEVER**; this file adds grounding and deltas.

## Deliverables

**Session A — spec.** `docs/PANEL_RHYTHM_SPEC.md` **v2**: the §4 role table with px per density, the five component patterns (label, row, tag, card, parm_row), the region map from CENSUS, the docking bound. There is no `/design` command in this runtime — author by hand from §4; same output, same accept. Keep v1's §5 honesty ledger and extend it.

**Session B — build.**
- `python/synapse/panel/designsystem/rhythm.py`: `ROLE_GAPS` (role → base px from `tokens.SPACE_GRID`), `apply(root, density)` walks widgets carrying the `rhythm_role` Qt dynamic property, sets `layout().setSpacing(tokens.gap(base, density))` and fixed `setContentsMargins` per role; idempotent; unknown role → standard, logged once. Importable without a QApplication at module top-level.
- `compositor.py`: call `rhythm.apply` after `_repolish_tree` at compose and in the recompose path — one property, two appliers, one call site each. **Diff ≤ 20 lines.**
- `designsystem/qss.py`: generic role rules keyed on `[rhythm_role="label"]`, `"tag"`, `"row"`, `#DsCard` bands, `"parm_row"` per §4. Density blocks carry **margin only**. Standard emits no density block. Use the BP4-PANELFONT type-floor constant and weight tokens (`git show 81f3fb08 --stat` to find them) — never a literal size.
- `tests/test_panel_rhythm_owner.py` — the guard: fails on any `setStyleSheet(`, `setSpacing(`, `setContentsMargins(`, or 6-digit hex in `python/synapse/panel/` outside `designsystem/` lacking a `# rhythm-exempt: <why>` tag on the same line; the allowed residual is a checked-in number (`harness/panel_pd/RESIDUAL.json`) that may only go down. Seed it with the CENSUS totals so the guard is green at the current residual and any new untagged site turns it red.
- `tests/test_panel_rhythm_docking.py` — every region at 380 px width in airy/standard/tight ≥ `.synapse/contracts/docking-minimums.yaml`; runs headless (`QT_QPA_PLATFORM=offscreen`, `SYNAPSE_REDUCED_MOTION=1`), skips with reason if PySide is absent.

## Accept (from the plan)
`rhythm.apply` changes layout spacing per role per density (headless test; negative control: role removed → spacing unchanged); guard test green at the current residual; docking test green; Expert pin (`tests/test_rope_expert_pin.py`) green; density rule (`tests/test_bp2_paneldesign_density.py`) green; zero new hex. Crucible will check: `fontload.py` untouched; no density-keyed rule carries colour/font/size/radius/border; `compositor.py` diff ≤ 20 lines.

REPORT → `docs/panel_pd/REPORT_LEVER.md`; STATUS → `harness/panel_pd/STATUS_LEVER.md`.
