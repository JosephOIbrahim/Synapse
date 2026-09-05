# Panel PD wave — Swarm Contract

**Plan:** `docs/PANEL_BATTLEPLAN_PD.md` (Joe, 2026-09-03). Scope: the Python panel's design. Nothing else.
**Reference notes:** `docs/panel_pd/COHERE_REFERENCE.md` — rules, not pixels.
**Base branch:** `pd/panel-base` (from master `6e3dd963`, v5.62.0). The plan was grounded at `26af4c68` (v5.61.0); one panel commit landed since — `81f3fb08` BP4-PANELFONT (type floor constant + weight tokens + pinning test). Respect it: the type floor is now a token, not a guess.

## Re-grounded census at the base commit (2026-09-04)

| owner | plan said | at 6e3dd963 |
|---|---|---|
| `setSpacing` / `setContentsMargins` outside `designsystem/` | 108 | **107** |
| inline `setStyleSheet(` outside `designsystem/` | 106 | **106** |
| 6-digit hex outside `designsystem/` | ~60 distinct | **135 raw sites** (distinct count is CENSUS's to state) |
| `# rhythm-exempt:` tags | — | 0 |
| `synapse_shelf.py` | listed under CAMERA | **does not exist** — CENSUS names the real shelf/ribbon owner |
| `docs/PANEL_REGION_MAP.md`, `harness/notes/panel_rhythm_census.py` | to be created | absent (CENSUS creates) |
| `.synapse/contracts/docking-minimums.yaml` | referenced | present |
| pinned tests | Expert pin, density rule | `tests/test_rope_expert_pin.py`, `tests/test_bp2_paneldesign_density.py`, `tests/test_bp2_paneltruth_density_repolish.py` |

## Agent setup (same as the Solaris wave)

Each leg is one Codex agent on `gpt-6-astra` in its own worktree, branched from the branch of the leg it depends on. No bus: the "bus" is (a) this contract, (b) `harness/panel_pd/STATUS_<LEG>.md` lines the orchestrator reads every ten minutes, (c) the previous leg's committed artifacts. The battleplan's tiering (Fable referees, Opus builds, Haiku sweeps) is replaced by gpt-6-astra for every leg; the caps in turns are advisory.

```
CENSUS (pd/panel-census, from pd/panel-base)
  └─ LEVER (pd/panel-lever, from pd/panel-census)
       ├─ CAMERA  (pd/panel-camera,  from pd/panel-lever)
       ├─ SWEEP_A (pd/panel-sweep_a, from pd/panel-lever)
       └─ SWEEP_B (pd/panel-sweep_b, from pd/panel-lever)
            └─ integrate: pd/panel-integrate = lever + camera + sweep_a + sweep_b (orchestrator merges; conflicts stop the chain)
                 └─ CRUX (read-only, on pd/panel-integrate)
```

## Exclusive write ownership (from the plan's `touches` lists)

| Leg | Exclusive write set |
|---|---|
| **CENSUS** | `harness/notes/panel_rhythm_census.py` · `docs/PANEL_REGION_MAP.md` · `harness/panel_pd/runs/<date>/rhythm_census.json` + `.md` |
| **LEVER** | `python/synapse/panel/designsystem/rhythm.py` (new) · `designsystem/qss.py` · `python/synapse/panel/compositor.py` (≤ 20-line diff) · `docs/PANEL_RHYTHM_SPEC.md` (v2) · `tests/test_panel_rhythm_owner.py` · `tests/test_panel_rhythm_docking.py` |
| **CAMERA** | `python/synapse/panel/synapse_panel.py` · `face_token.py` · `token_readout.py` · the real shelf/ribbon module CENSUS names · `chat_display.py` (T3 only) · the recall-card widget module (new, name it `recall_card.py`) · `design/rhythm_pd/{before,after}/` PNGs · `tests/test_panel_camera_rhythm*.py` |
| **SWEEP_A** | `chat_panel.py` · `face_review.py` · `gate_widget.py` · `context_bar.py` · `face_work.py` · `quick_actions.py` · `designsystem/qss.py` **append-only in a `# --- SWEEP_A` block** · `tests/test_panel_sweep_a*.py` |
| **SWEEP_B** | `hda_views.py` · `tool_palette.py` · `command_palette.py` · `working_indicator.py` · `vex_tutor` · `apex_trace` · `apex_explainer` · `scene_doctor` · `performance_profiler` · `network_trace` · `cross_scene` · `message_formatter` · legacy `panel/tokens.py` + `panel/styles.py` (delete only per the plan's rule) · `docs/panel_pd/HEX_MAPPING_SWEEP_B.md` · `designsystem/qss.py` **append-only in a `# --- SWEEP_B` block** · `tests/test_panel_sweep_b*.py` |
| **CRUX** | `docs/panel_pd/CRUX_VERDICT.md` · `harness/panel_pd/runs/<date>/crux.json` — **nothing else** (read-only leg; `--write` is not granted) |

Every leg also owns `harness/panel_pd/STATUS_<LEG>.md` (append a dated line per milestone, commit it) and `docs/panel_pd/REPORT_<LEG>.md`.

`qss.py` is the one shared file: LEVER writes the generic role rules; SWEEP_A and SWEEP_B append inside their own comment-fenced blocks at the end of the file so the three-way merge is clean. Never reorder or edit outside your block.

## Laws

1. **Worktree only.** Never write to `C:\Users\User\SYNAPSE`. Never use absolute repo paths in code.
2. **Zero new hex, zero new font family, zero new widget** except the recall card (plan §1-6). Tokens come from `designsystem/tokens.py`; the 4-pt ladder (`SPACE_GRID`, `gap()`, `ROW_MIN_H`, `RADIUS_CARD/ROUND`) is the vocabulary. `fontload.py` untouched.
3. **Density carries gaps only.** Density-keyed QSS never carries colour/font/size/radius/border; standard emits no density block (`tests/test_bp2_paneldesign_density.py` rule). Expert stays structurally pinned (`tests/test_rope_expert_pin.py`).
4. **Docking is a constraint.** Every region at 380 px in airy/standard/tight must satisfy `.synapse/contracts/docking-minimums.yaml`.
5. **Headless proves numbers; eyes sign off.** Run Qt tests with `QT_QPA_PLATFORM=offscreen` and `SYNAPSE_REDUCED_MOTION=1`. `panel_shot.py` PNGs are a diff instrument. GUI sign-off on H22.0.400 is Joe's, red gate; a leg never claims it.
6. **Lifecycle lines untouched.** Timer/lifecycle code in `synapse_panel.py` (W5L-LIFE), the `face_token` refresh-on-completion path, the shelf docked-open path, and `hou.*`-free worker code stay exactly as they are.
7. **Known trap:** cyan/blue tokens come from three sources (memory: panel redesign) — do not naively unify; map hex → nearest existing token by role and check the mapping table in.
8. **Tests before done.** Your tests green; the Expert pin green; the density rule green; then `python -m pytest tests -q -p no:cacheprovider` once, counts in your REPORT, never below the base (`harness/solaris_v3/BASELINE.md` on the Solaris base is the same commit; the orchestrator publishes full-run numbers in `harness/panel_pd/BASELINE.md`).
9. **Commits.** Subject prefix `pd(<leg>):`, trailer `Co-Authored-By: Codex (gpt-6-astra) <noreply@openai.com>`. Never merge, never push, never touch master or another leg's branch.
10. **Status cadence.** STATUS line + commit after every milestone.

## Definition of done (per leg)

The plan's **Accept** line for your leg (§3) is the definition. Your REPORT states each accept criterion with evidence (test name, census number, file path, PNG path), then files changed, tests/counts, deferred with reasons, and any nits for `harness/notes/panel_nits_pd.md` (write them into your REPORT; the orchestrator consolidates).
