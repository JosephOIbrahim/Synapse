# JEV HELM — Jev picks the graph, code builds it

Status: mile 1 of 5 landed on branch `bp8/helm` · 2026-09-20 · CTO seat (Fable 5.1) on Joe's word
Extends `JEV_BLUEPRINT.md`. All six invariants there still hold. Update this card; don't multiply it.

## One paragraph

Until now a person chose each wave's shape by hand. The helm makes that a judgment. Jev cannot
plan, so code lists the possible moves and Jev picks among them: which graph template fits an
objective (SHAPE, mile 1), how many subagents a leg may spawn (TEAM, mile 2), and which edge to
take after each receipt (EDGE, mile 3). Code owns every decision. Doubt never spends: an unsure
SHAPE returns `manual` (author by hand, as before), and an unsure TEAM rounds down to zero.

## Mile 1 — JEV-SHAPE (done)

    harness/jev/workflows.json             template catalog: solo, scout-synth, build-screen-crux, probe-only; caps
    harness/jev/questions.json             + guards.shape (shape Choice, cause_known, deterministic, breadth, policy)
    harness/jev/jev_shape.py               decide() policy, expand() skeletons, derive_shape(), shadow CLI
    harness/jev/shape_shadow_cases.json    past-wave objectives (answer key is computed, never hand-labelled)
    harness/jev/tests/test_jev_shape.py    11 biting tests, one per policy branch

Run it:

    python harness/jev/jev_shape.py --shadow
    python harness/jev/jev_shape.py --wave bp8 --objective "..." --expand

Policy: the Choice must clear 0.60 AND a second independent judgment must agree with it
(scout-synth needs cause unknown; build shapes need cause known; probe-only needs deterministic
>= 0.70; solo needs breadth <= 1.0). Any disagreement returns `manual`. `expand()` writes mission
skeletons to stdout or `--out`, never into `missions/`.

## Shadow result, 2026-09-20 (n=4, a smoke test, not a calibration)

bp3, bp4 -> build-screen-crux; bp6 -> solo; bp7 -> scout-synth. 4/4 against shapes derived from the
mission files. Caveat: the objectives were paraphrased after the fact by the seat that knew the
answers. Two criteria examples leaked BP6 and BP7 and were replaced before the recorded run.

Unseen objective (the H6 memory-store fix, bundled with a panel safety net): `manual`, shape
confidence 0.41. Jev split build-screen-crux 0.56 / solo 0.44 with cause_known 0.98 and breadth
0.92. Reading: the catalog had no shape for ONE fix that ships to artists. Joe's word
("execute this setup") -> fifth template `fix-crux` added. Re-run, still bundled: `manual` at
0.54 (crux 0.64 / fix-crux 0.35) - Jev was right, the objective held two deliverables. Scoped to
H6 alone: `fix-crux` @ 0.99.

## BP8 - the first wave shaped by the helm (skeleton only, NOT armed)

BP7-SYNTH landed (`harness/battleplan/notes/BP7_VERDICT.md`, branch bp7/synth @ 8d49e790) and
overruled the H6-first plan: H6 is confirmed only under a Save-As rebind the symptom does not
mention; the most likely chain is H4 -> H1 (router tier timeouts defined at router.py:124-125 but
never passed to guarded_create at :685,893; no panel watchdog). Objective rewritten from the
verdict's three named changes -> `build-screen-crux` @ 0.99, breadth 1.01 ("Few").

    harness/jev/bp8.skeleton.json    BUILD1 watchdog (panel) · BUILD2 tier timeouts (router+handlers)
                                     BUILD3 _adopt_scene_store (memory) · CRUX referee · TIDY mechanical

Bug caught on this run: the linear breadth map turned "Few" (1.01) into FOUR builders for THREE
named changes. leg_count() now uses level bands (One -> lo, Few -> lo+1, Many -> hi) and takes an
explicit author count (`--legs`), clamped to the template. Jev judges breadth; it does not count.
Regression test: test_few_means_three_not_four_regression.

Before arming: Joe's 2-minute GUI repro in BP7_VERDICT.md ("Reproduce in the GUI") decides whether
BUILD3 belongs in this wave. If the hang appears without a Save-As, H6 is not the symptom and
BUILD3 can wait. Notes, targets and acceptance for each skeleton are still to be authored.

## Mile 2 — JEV-TEAM (done 2026-09-20)

    harness/jev/jev_team.py                decide() 0/2/4 subagents, team_lines() brief section, shadow CLI
    harness/jev/questions.json             + guards.team (parallelizable Score, shared_files Noul, policy bands)
    harness/battleplan/mission_schema.py   OPTIONAL `team`: "auto" | {max_subagents 0..4, subagent_tier <rails tier>}
    harness/battleplan/compile_wave.py     resolves team:auto like tier:auto; Team section appended only when > 0
    harness/jev/tests/test_jev_team.py     9 biting tests incl. team-less leg compiles byte-identical

    python harness/jev/jev_team.py --wave bp8 --shadow

Doubt rounds DOWN: low confidence drops a band, writers that would share a file get zero, unknown
collision risk counts as a collision, any failure is zero. Referee and tidy legs always work alone.
The subagent tier is a code rule (`mechanical`), never Jev's choice.

Shadow over BP8 (4 legs) and BP4 (8 legs): ZERO subagents on all twelve. Reading, not a bug: your
missions are already cut one-piece-per-leg, so the wave graph IS the parallelism and a team inside
a leg would be paying twice. Closest calls: BP4-RULINGS (parallelizable 1.31 but confidence 0.23)
and BP4-PANELFONT (0.91, 22 modules, shared_files 0.68). The thresholds were NOT tuned to make
teams appear. Expect teams only on a deliberately wide leg (one scout over many modules).


## Open rulings

1. ~~Fifth template `fix-crux`~~ - added 2026-09-20.
2. `probe-only` legs carry `tier: none`, which is not a rails tier. Either rails gains a no-model
   entry or probe-only waves run outside the orchestrator.

## Miles

    M1  SHAPE guard + shadow                                            done
    M2  TEAM guard + `team` field + compile hook + shadow                   done
    M3  EDGE: recompile between legs on the SCREEN verdict, behind a flag; max 2 inserted legs
    M4  DRIFT wired to the orchestrator poll, shadow only
    M5  first real wave on the helm: BP8, the BP7 verdict's three fixes (skeleton ready, not armed)
