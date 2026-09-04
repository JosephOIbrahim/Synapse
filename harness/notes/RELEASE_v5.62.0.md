# v5.62.0 — the inspector found the light

Draft release notes. **Draft only — not published, no tag cut.** Publish is
gated on the release ritual (R.R verify) and Joe's re-signed waiver for the
four standing RC blockers. Every claim is receipt-backed on master (HEAD at
draft time `a632139c`). Where a claim needs eyes on a live Houdini it says
UNKNOWN, not green. Where the CTO seat got something wrong, it says so by name.

Scope: wave **BP4** — BP3's closing plus two new asks, executed as six builder
legs (INTAKE, RULINGS, B7FIX, SPATIAL, PANELFONT, USDKNOW), an adversarial
crucible (CRUX, **Fable 5.1**, six parallel audit lanes, 37 self-authored
mutations) and a house-cleaning census (TIDY). **Five builders SOUND-WITH-NITS,
one BROKEN (RULINGS — a missing row and a count line; carried, not shipped).**
Joe read the verdicts (`harness/battleplan/notes/BP4-CRUX_verdicts.md`) and said
`merge 1–6`, then `merge tidy`; seven `--no-ff` merges landed in dependency
order (12bf4600 → ff61508e). **Nothing in this release is ratified**: the USD
composition seed ships `ratified:false`, the spatial tools ship unregistered
behind a flag that defaults off, the font floor ships UNKNOWN and pinned.

## For artists

**Two things can move under your hands, and both are off or invisible by default.**
The panel's typography is now tokens (`python/synapse/panel/designsystem/tokens.py`):
one family, a five-step scale, weights, a floor. The floor is honest and
unmeasured — the H22 help cache states no default UI font size, so
`FONT_FLOOR_PX=10` pins to the smallest size the panel already shipped, and
nothing got smaller. The real Houdini default becomes a number the moment Joe
pastes `python/synapse/panel/scripts/probe_ui_font.py` into the 22.0.400 Python
shell; until then, screenshots are UNKNOWN. The crucible counted 166 typography
literals still outside the token module — this pass scoped itself to the design
system's authority, and says so.

The three spatial queries — describe, classify (floor / wall / ceiling by normal),
frustum — exist and pass 14/14 on the World Labs fixture, exactly reproduced by
the crucible. They are **not** registered: `SYNAPSE_SPATIAL_LANE=1` turns them
on, and the lane is `ratified:false` (rule D-1). The environment table in
`docs/studio/DEPLOYMENT.md` says the same thing.

## Under the hood

**The probe bug is fixed, and the story about it was wrong.** B-7 (Karma render
of the World Labs component) rendered black in BP3 because the camera was never
bound to the render settings. Bound now, with a light authored before
`rop.render` and a `--only <id>` flag on `harness/probes/synapse_blueprint_probes.py`.
D2.4 PASS and R-1 CLEAR reproduce on the crucible's own render. Then the
crucible ran controls the builder didn't: **Karma XPU 22.0.400 substitutes a
default distant light when the stage carries none**, so "no light → black" was
never a safe expectation on this build; the camera bind silenced husk's errors
without changing pixels; the composite rewiring is what restores lighting. The
splat still renders **uncoloured** — per-point SH colour is not shaded on the naive
USD (`shader_calls.surface=0`). That is a finding, not a fix.

**The fixture is not what the blueprint said.** `b6_wl_component.usdc`'s proxy
is a four-face auto-proxy from the SOP USD Create Component, not the 46,993-tri
collider — the collider lives in the GLB. BP3's S-2/S-3 spatial numbers were
computed on two packed prims and are degenerate; the authoritative per-face
numbers are in the SPATIAL leg's correction run (frustum 20,146 of 46,993).

**USD composition knowledge, tiered by evidence.** A LIVRPS decision record for
`/WL_<world_id>` (`docs/reviews/bp4-usd-composition-worldlabs.md`) and a rule seed
(`harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json`) where every
VERIFIED row anchors a hython 22.0.400 stdout line. Truths: purpose is authored
on the `/geo/proxy` and `/geo/render` scopes, the splat leaf authors none; the
splatTier / physics variant sets and `customData:worldlabs` are **not** in the SOP
build — PROPOSED, not FIXTURE-VERIFIED. The shipped skill text's claim that a
specialized prim loses to its base was **refuted at runtime**: a local opinion wins.
The seed's checker matches by substring and let three false assertions through
(crucible U-1); it is a held spawn.

**The budget rail bit, correctly.** Cap `12turns,105000000tokens`; the six
builders measured 105,897,811 on the rails meter (cache reads counted, same
basis as v5.61.0's 102.8M) and the rail halted dispatch at INTAKE's settle. CRUX
had already launched; TIDY ran later on a `2turns,25000000tokens` mini-cap and
came in at 8.79M. CRUX's own tokens are UNKNOWN in the ledger — rails refuses to
settle into a blocked ledger — and ≥ 41.8M by hand from its lead transcript.
Wave ≥ 154.8M in. Both ledgers ship in `harness/battleplan/runs/2026-09-03/`.

**Harness.** Referee tier is `claude-fable-5-1` (`harness/rails_exec.json`;
`runs/2026-09-03/preflight_bp4.json` proves every tier answers at `--effort max`
on Claude Code 2.1.259). `readonly-settings.json` no longer denies the scoped
`git add`/`git commit` it also allows — the contradiction that killed Haiku legs
at the fence in BP3. `make_control.py` says `max`, not the unlisted `ultracode`.
Three skill texts live under `harness/battleplan/notes/skills/` so legs read the
real thing.

**What the CTO seat got wrong, by name.** `status_bp4.py` shipped a BP2-era
hardcoded leg list (caught and fixed by the second seat, 2d26231f). An R135
in-place harvest of INTAKE was redundant — the leg had preserved its own product
— and its receipt stated, falsely, that no leg branch existed; the merge kept the
leg's receipt and demoted mine to a corrected addendum. Commit 60cc1a2b's message
claimed the ratchet was green while one test was still red (a `findstr failed`
chained into a commit); 36dc5ab9 corrects it. Two legs wrote copies of their
product into the main tree by absolute path; identical to the branch products,
deleted before merge, filed as hardening.

## Tests

Full suite at `36dc5ab9`: **6942 passed, 192 skipped, 0 failed** (4 m 38 s).
Three reds introduced by the wave were fixed on master before the tidy merge:
two tests pinning the old referee literal, a BOM in a receipt written by the
merge train, and the spatial flag missing from the env-var conformance table.

## Not in this release

RULINGS (BROKEN — `bp4/rulings` carried; the 22 cold rulings and five
ratifications are the next fresh session's first task). The two `.docx` sources
(still missing under `docs/intake/src/`; `dossier_in_repo = partial`). The font
floor as a measured number. Five held spawns from the crucible (timing pin,
registration pin, checker token boundary, `-k panel` gate, causal sentence).
Eighteen worktree prunes proposed by TIDY, none executed (unusable-only standard).

Handoff: `harness/notes/CAPSULE_2026-09-03_BP4.md`.
