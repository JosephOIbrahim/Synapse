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


## Mile 3 - JEV-EDGE (built 2026-09-20; recommended mode: SHADOW)

    harness/jev/jev_edge.py                plan_edge() pure planner, repair_mission(), atomic apply(), dry run by default
    harness/orchestrate.ps1                ONE hook after Rails-Settle; inert unless SYNAPSE_JEV_EDGE = on | shadow
    harness/jev/tests/test_jev_edge.py     6 biting tests (pure planner, cap, no chains, dry run never raises)

    set SYNAPSE_JEV_EDGE=shadow            ledger what EDGE would do; write nothing   <- run BP8 like this
    set SYNAPSE_JEV_EDGE=on                FLAG inserts one repair leg into the live manifest

The orchestrator already re-reads its manifest every poll, so a dynamic edge is a bounded manifest
edit between polls. CLEAR / REFEREE -> continue (the screen line already sets CRUX's depth). FLAG ->
one repair leg, BASED ON THE FLAGGED LEG'S BRANCH, scoped to the flagged acceptance rows only; every
dependent of the flagged leg (CRUX) waits for it and its brief gains an 'Inserted leg' note. Bounds
are code: caps.max_inserted_legs (2) per wave, a repair never spawns a repair, one repair per leg,
referee/tidy receipts never rewrite the graph, a repair is charged through Rails-Charge like any leg,
any guard error -> continue.

Dry run on real BP4 receipts, 2026-09-20 (n=2):
- BP4-B7FIX (CRUX: sound)  -> REFEREE -> continue. Correct.
- BP4-RULINGS (CRUX: BROKEN) -> REFEREE -> continue. EDGE would NOT have inserted a repair.
  Jev smelled it - self_contradiction 0.69, crux_need 1.56, rows 0 and 1 weak - but row 0's
  does_not_support was 0.25 against a FLAG threshold of 0.60. So SCREEN did its job (it sent CRUX
  to a full read) and the FLAG trigger did not fire on the one known-BROKEN leg. JEV_BLUEPRINT.md
  sec.3.2 predicted a high-probability FLAG here; measured, it was not.
- The thresholds were NOT tuned on n=1. Candidate rule for Joe's ruling once more receipts exist:
  self_contradiction >= 0.6 AND crux_need >= 1.5 -> FLAG. Until then EDGE stays in shadow, and
  BP8's edge ledger (harness/jev/ledger/bp8.edge.jsonl) beside CRUX's verdicts is the evidence.

## Mile 4 - JEV-DRIFT (built 2026-09-20; SHADOW ONLY by construction)

    harness/jev/jev_drift.py               decide() pure policy, cadence, closed-leg guards, replay CLI; no bus writer exists
    harness/orchestrate.ps1                ONE hook after Drift-Check; inert unless SYNAPSE_JEV_DRIFT = shadow
    harness/jev/tests/test_jev_drift.py    7 biting tests (incl. one that fails if this file ever gains a bus.post)

    set SYNAPSE_JEV_DRIFT=shadow                                                     <- run BP8 like this
    python harness/jev/jev_drift.py --wave bp7 --bus-root <main>\harness\battleplan\bus --ignore-closed   (replay a finished wave)

harness/battleplan/drift.py (regex, zero model) KEEPS the refocus/halt authority and the rails keep
the hard stop. JEV-DRIFT answers only what a regex cannot - retrying the same step, claiming files
outside `touches` - and ledgers what it WOULD have warned: looping >= 0.80 AND advancing <= 0.20 on
two judgments in a row. A missing answer is UNKNOWN, never 0. Cadence is code: a leg is judged only
after 3+ new bus events and never once closed, so cost follows bus traffic, not poll frequency.
State is capped at 12 events x 400 chars.

Replay of the real BP7 bus, 2026-09-20 (4 legs judged; TRANSPORT had < 3 events once its DONE was stripped):
    MEMORY advancing 0.89 looping 0.11 · ROUTER 0.77 / 0.20 · SYNTH 0.84 / 0.12 · PANEL 0.52 / 0.71
No would-warn on any leg. The regex drift.py, live, posted 2 refocus + 1 HALT to BP7-PANEL - the leg
that went on to land a valid receipt (verdict UNKNOWN, e0fdcca2). On this one case the semantic read
("half advancing, somewhat repetitive, not a loop") fits the outcome better than the halt did. n=1:
recorded, not a ruling. If BP8's drift ledger keeps disagreeing with drift.py's halts, THAT is the
evidence for loosening the regex or handing the warning to Jev.

## SCREEN graded against CRUX, zero new Jev calls (2026-09-20, during BP8)

    python harness/jev/jev_grade.py        replays ledgered raw answers under candidate policies vs CRUX verdicts

BP4, six legs with both a screen answer and a CRUX verdict (1 BROKEN, 5 SOUND-WITH-NITS):

    policy                  BROKEN->FLAG  BROKEN->CLEAR(miss)  SOUND->CLEAR  SOUND->REFEREE
    current                     0               0                 0              5
    flag-on-contradiction       1               0                 0              5
    clear-conf-0.7              0               0                 1              4

Reading: the CURRENT policy is safe (no miss) but inert - REFEREE on every real receipt, so CRUX
always does a full read and the screen line has saved the referee nothing yet. Two candidate rules,
each a one-line text diff in questions.json, each with zero misses on this set:
  (a) FLAG when self_contradiction >= 0.6 AND crux_need >= 1.5  - catches the one BROKEN leg (RULINGS).
      This is the rule EDGE would need to ever insert a repair.
  (b) clear_min_support_confidence 0.8 -> 0.7                    - lets one SOUND-WITH-NITS leg CLEAR.
n=6. Joe's ruling, after BP8's two verdicts join the set: adopt (a), (b), both, or wait for n>=12.

## Docs read (2026-09-20 13:56, on Joe's word) - what changed and what was confirmed

Read: confidence.md, primitives/score.md, model-jaggedness/jev-1.13.md (reviewed 2026-09-17),
cookbooks/citation_check.md, llms.txt index.

CONFIRMED, no change needed:
- Score = probability-weighted mean over 0-indexed levels ("0x0.0 + 1x0.70 + 2x0.30 = 1.30"). Every
  Score threshold in questions.json (novelty 1.5, crux_need 0.5, breadth bands, parallelizable bands)
  reads that number correctly. Levels must describe concrete situations, not degrees - ours do.
- Confidence is a concentration statistic of the distribution, formula unspecified, "you are never
  locked into our definition". jev_client's max(probs) stand-in is a fair reading. Docs' own example
  floors: 0.5 general, 0.9 high-stakes; ours are 0.6 (route/shape/team) and 0.8 (screen clear).
- citation_check cookbook is SCREEN's exact shape: one Choice per claim/evidence pair, supports /
  contradicts / says_nothing, AUTO_ACCEPT 0.8. Ours adds `partial` and `claims_unknown` (UNKNOWN is
  a first-class answer here) and uses the same 0.8.
- "P(noul) != 1 - P(not noul)": DRIFT already asks advancing and looping as two Nouls and requires
  both, never derives one from the other.

CHANGED (jev_screen.py + tests/test_jev_screen_count.py, 5 tests):
- Jaggedness page: "Jev is not a calculator ... does not count reliably"; workaround "move
  arithmetic, counting ... to code". SCREEN rule 2 delegated the expected-vs-reported count
  comparison to Jev. That is the BP4-RULINGS miss: 22 expected, 21 reported, CRUX BROKEN, Jev put
  0.25 on does_not_support. count_mismatch_rows() now does it in code: '<n> <count-noun>' in the
  evidence that matches no count named in the mission note or predicates -> FLAG on that row, code
  reason first, Jev's reason kept beside it. Proven on the real a62267f9 receipt; BP8's two green
  receipts do not trip it. Turn caps and line windows are not count nouns.
- Consequence for the SCREEN ruling above: candidate (a) is no longer needed to catch RULINGS - the
  code check catches it with no threshold change. (a) stays listed only as a Jev-side backstop.

NOTED, no change yet:
- "Accuracy falls as the state grows with content unrelated to the decision": DRIFT is capped at
  12 events x 400 chars; SCREEN sends only named mission/receipt fields. Keep it that way.
- "The model doesn't treat state as hostile": receipts are written by builder agents. SCREEN can
  be gamed by evidence prose; CRUX exists for exactly that. Never let SCREEN CLEAR replace CRUX.
- SHAPE's `breadth` Score asks "how many pieces" - a counting question. Its levels are situations
  (One / Few / Many), the docs-recommended form, and leg_count() plus `--legs` keep the actual
  number in code. Watch it; if breadth drifts on real objectives, split it into Nouls.

## Open rulings

1. ~~Fifth template `fix-crux`~~ - added 2026-09-20.
2. SCREEN policy: the code count check now covers RULINGS; ruling narrows to (b) clear-conf 0.7 or keep collecting.
3. `probe-only` legs carry `tier: none`, which is not a rails tier. Either rails gains a no-model
   entry or probe-only waves run outside the orchestrator.

## Miles

    M1  SHAPE guard + shadow                                            done
    M2  TEAM guard + `team` field + compile hook + shadow                   done
    M3  EDGE guard + orchestrator hook, behind a flag; max 2 inserted legs      built, SHADOW until BP8 evidence
    M4  DRIFT guard + orchestrator hook                                         built, shadow only by construction
    M5  first real wave on the helm: BP8, the BP7 verdict's three fixes (skeleton ready, not armed)
