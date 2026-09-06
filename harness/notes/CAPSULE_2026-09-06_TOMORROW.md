# Capsule — for tomorrow-you (written 2026-09-05, 20:30)

```
+== PROJECT CAPSULE: SYNAPSE panel + CTO loop ==================================+
| WHERE WE ARE:        v5.65.1 published (tag 6d56212d, master 133eba49+fix).    |
|                      Three releases today: v5.64.0 (PD wave + CTO loop),       |
|                      v5.65.0 (direction B+C), v5.65.1 (Joe's five). All        |
|                      through scripts/tag_release.py, pushed, GitHub releases.  |
| MILE MARKER:         Design arc: 5 of ~6. Left: B11 verb rail collapse toward  |
|                      the 280 px dock contract; D-F type doctrine items.        |
| WHAT I WAS THINKING: Joe rules, the pins move with the ruling. Every landing   |
|                      is spec -> parallel forges -> integrator -> 2 referees ->  |
|                      CTO addendum -> live reload + grab in Joe's Houdini.      |
| NEXT ACTION:         "run the cto-orchestrator" - one crank. SWEEP re-runs     |
|                      every open predicate (B9, B11, D-F1..14, referee nits).   |
| BLOCKERS:            None on my side. Joe's: recipe vocabulary ruling; golden  |
|                      HIP for Solaris v3; eyes on one real chat turn (speaker   |
|                      colours + TOKEN numbers for ollama).                       |
| ENERGY REQUIRED:     Low to start (crank + read). Medium if B11 is taken.      |
| IDEAS PARKED:        token grey on bridge loss (no writer sets disconnected);  |
|                      direct-tool paths bypass _render_state; FLOW probe J4.1   |
|                      still pins the retired pill; macOS CI flake class         |
|                      (freeze-chain timing: f3 anchored 2026-09-05, m3 watched).|
+===============================================================================+
```

## Where things live

- Board: `harness/cto/board.html` (published artifact, same URL all day).
- Canvas: `harness/design_review/2026-09-05/` (Bierut review + rulings + live rows).
- Rulings: `harness/cto/runs/2026-09-05/RULING_*.md` (R3-01, DIRECTION_BC + addenda, JOE_FIVE).
- Backlog with closure predicates: `harness/cto/BACKLOG.json`; ledger `harness/cto/LEDGER.md`.
- Live evidence: `design/rhythm_pd/live/2026-09-05/{after,cold,j5}/` (grabs + JSON reports).
- Release notes: `harness/notes/RELEASE_v5.64.0.md`, `RELEASE_v5.65.0.md`, `RELEASE_v5.65.1.md`.

## Words that unlock things

- "run the cto-orchestrator" - the crank.
- "rule: recipes are <the 62 | Solaris v3 | recipe_book>" - unblocks recipe execution.
- "panel looks right" / "<what is off>" - after one real chat turn on v5.65.1.
- "release" - the ritual (commit receipts -> gate -> tag -> push -> gh release; never chain gh after the gate).

## Two things learned today worth keeping

1. `gh release create` mints a tag by itself when the gate refused - undone once, memory written.
2. Live reload in a running Houdini: purge `synapse.*` from sys.modules, `installFile`, then
   `setActiveInterface`; never sleep on the main thread from the bridge (freeze breaker).
