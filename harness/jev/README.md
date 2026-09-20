# JEV guard seam

Typed guard nodes (TypeSafe's Jev / System One) on the BATTLEPLAN wave graph. Jev supplies
calibrated judgments; **code owns every decision**, and every judgment is ledgered so the
wave can grade the guard afterwards. A build-time instrument, like the crucible — never on
the product path. Full design: `harness/battleplan/notes/JEV_BLUEPRINT.md`.

## Files

- `questions.json` — the question graph. This file IS the prompt (guards → state fields,
  questions, policy thresholds). Tier NAMES come from `harness/rails_exec.json` at runtime.
- `jev_client.py` — key resolution, SDK call, fail-closed wrapper, ledger writer; the one
  place the harness talks to Jev.
- `jev_route.py` — JEV-ROUTE: mission → tier. `decide()` is the policy; `resolve_tier()` is
  the entry point `compile_wave.py` calls for a `"tier": "auto"` mission.
- `jev_screen.py` — JEV-SCREEN: builder receipt → one line in the CRUX brief
  (CLEAR | REFEREE | FLAG). Fail-closed verdict is REFEREE (full read).
- `ledger/` — append-only judgment ledger: `<wave>.route.jsonl`, `<wave>.screen.jsonl`.
- `tests/` — biting guard tests + a recorded SDK-shape fixture (`fixtures/route_answer.json`).

## Shadow commands (grade the guard before it goes live)

    python harness/jev/jev_route.py --wave bp4 --shadow   # Jev's tier beside the author's
    python harness/jev/jev_screen.py --wave bp4           # screen verdict beside CRUX's

## Env knobs

- `TYPESAFE_API_KEY` — the Jev API key. Read from the process env, else (Windows) from the
  HKCU\Environment registry scope so no shell restart is needed. Absent → fail closed.
- `SYNAPSE_JEV` — `off`/`0`/`false` disables Jev: `auto` missions behave as `reasoning` and
  the SDK is never imported. Default `on`.
- `model` (in `questions.json`) — the Jev model id. Default `jev-latest`.

## Invariants (the crucible checks these — verbatim from JEV_BLUEPRINT.md sec.4)

1. **rails_exec.json stays the only place a model is named.** Jev chooses among its
   tier names; it never emits a model string.
2. **A literal tier is byte-identical to today.** Only `"tier": "auto"` invokes Jev.
3. **Fail closed.** No key, no network, SDK error, malformed answer → the pre-Jev
   behaviour (`reasoning`; full CRUX read; no drift warning), and a `fallback` row in the ledger.
4. **Every call is ledgered.** `harness/jev/ledger/<wave>.route.jsonl`,
   `<wave>.screen.jsonl`: state hash, question ids, raw probabilities, decision, reason.
   UNKNOWN stays UNKNOWN: a fallback row never carries a fabricated probability.
5. **Jev is never on the product path.** Nothing under `panel/`, `synapse/`, or the
   package imports `harness/jev`. Jev is a build instrument, like the crucible.
6. **Questions are data.** `harness/jev/questions.json` is the whole "prompt". Editing a
   criterion is a text edit with a diff, not a code change.

## Helm guards (2026-09-20)

SHAPE, TEAM, EDGE and DRIFT - `jev_shape.py`, `jev_team.py`, `jev_edge.py`, `jev_drift.py`, templates in `workflows.json`. Card: `harness/battleplan/notes/JEV_HELM.md`. EDGE and DRIFT are inert unless `SYNAPSE_JEV_EDGE` / `SYNAPSE_JEV_DRIFT` are set.
