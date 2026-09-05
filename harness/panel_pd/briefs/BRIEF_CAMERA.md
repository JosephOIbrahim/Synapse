# BRIEF — PD-CAMERA (BUILD · the five camera regions + the recall card)

Read, in order: `docs/panel_pd/SWARM_CONTRACT.md`, `docs/PANEL_BATTLEPLAN_PD.md` (§1, §3 PD-CAMERA, §4), `docs/panel_pd/COHERE_REFERENCE.md`, `docs/PANEL_RHYTHM_SPEC.md` v2 and `docs/PANEL_REGION_MAP.md` (both on this branch from LEVER/CENSUS), `python/synapse/panel/designsystem/rhythm.py`. Branch `pd/panel-camera` (from `pd/panel-lever`). Your leg brief is **§3 PD-CAMERA** T1–T6; this file adds grounding and deltas.

## Grounding
- The plan's `synapse_shelf.py` does not exist; the shelf/ribbon/header owner is the module `docs/PANEL_REGION_MAP.md` names. That module is in your write set; nothing else outside the contract list.
- Roles and gaps come **only** from `rhythm_role` + `designsystem/`; every `setSpacing(28)`, `setSpacing(24)`, `setSpacing(18)` the plan cites is zeroed by giving the owning widget a role, never by hand-tuning a different number.
- T3 chat transcript: `chat_display.py` is token-clean today; reply leading +0.75 pt is the W5L-PANEL T2 rule and must be expressed through the type tokens (BP4-PANELFONT), not a literal.
- T4 recall card: the **one** greenfield widget (plan §1-6). New module `python/synapse/panel/recall_card.py`, three bands from `#DsCard`; header "what I remember"; body = the deposit; footer = text action left, status pill right from `STATUS ∈ SUCCESS|UNAVAILABLE|BLOCKED` + `payload.hit` → `HIT / NO HIT / UNAVAILABLE / BLOCKED`; `HOT_SOFT` only for BLOCKED; UNKNOWN as text. It displays an existing recall result (find the recall result shape in `python/synapse/panel/` and `python/synapse/server/handlers_memory.py`); it adds no capability.
- T5 TOKEN face → `rhythm_role="parm_row"` rows with objectNames; UNKNOWN as text in the value column, never a bar at zero.
- T6 header/ribbon → one row, label style; the `?` glyph opens docs; the docked-open path is landed — do not touch it.
- Lifecycle/timer lines in `synapse_panel.py` (W5L-LIFE) and the `face_token` refresh-on-completion path stay byte-identical: prove it with `git diff` hunks in your REPORT.

## Screenshots
Run `hython harness/notes/panel_shot.py --help` first. Before PNGs must come from the **untouched** tree: take them at your branch's first commit (before any edit) into `design/rhythm_pd/before/`, then after into `design/rhythm_pd/after/`, per profile (Curious/Expert/ML), with `QT_QPA_PLATFORM=offscreen` and `SYNAPSE_REDUCED_MOTION=1`. If no hython is bound (`SYNAPSE_HYTHON` unset and the hytest shim finds none), record NOT_RUN with the exact reason in the REPORT — never fabricate PNGs.

## Accept (from the plan)
Census for your files → 0 / 0 / 0 (run `harness/notes/panel_rhythm_census.py`); before/after PNGs per profile committed (or NOT_RUN stated); docking test green at 380 px; Expert pin green; density rule green; guard test green with the residual lowered. GUI sign-off is Joe's red gate — list your nits for him in the REPORT.

REPORT → `docs/panel_pd/REPORT_CAMERA.md`; STATUS → `harness/panel_pd/STATUS_CAMERA.md`.
