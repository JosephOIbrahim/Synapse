# v5.50.0 — the knowledge layer stops guessing

Wave 4 (H22 retrieval repair): one session from recon report to shipped wave —
5 Opus 4.8 legs in worktrees, adversarial crucible, merge train, 80/80 integration green.

## What's in it

- **Retrieval repair** (`knowledge.py` +459): scout now *sees* the node corpus
  (previously zero rows reached it); node index keyed `(context, type)` with a
  disambiguation list for ambiguous bare types; a type-name intent test replaces
  the old 2-token bail-out, so sentence-shaped questions route to the node path
  or an honest not-found instead of stale H21 prose — **0/25 confident-wrong**
  on fresh adversarial probes; datasheets return **all** internal parm names +
  channels (12-label cap removed); similarity floor on the dense path; corpus
  build-stamp verified loudly at load.
- **Tool schema**: `knowledge_lookup` gains optional `context` and `k` — additive,
  back-compat held (171/161 census controls).
- **Freshness release gate + ingest ledger** (`checks.py`, `ingest_ledger.py`):
  served-corpus build stamp must match the ratified build, release-blocking;
  the per-context ingest ledger is single-writer by design.
- **helpdoc parameterized**: callers choose the help-archive build (`.368`/`.400`),
  loud SystemExit on a missing archive; no ingest path hardcodes a build.
- **Gate P fork packet** (`harness/notes/h22/crux-ruling.md`): the bookish-AST
  source ruling adversarially re-executed — regen reproduced to the integer
  (5,481 pages / 0 errors), one number corrected, four claims sharpened, and a
  staged-adoption advisory for the parser fork.
- **Harness hardening (CRX0)**: `_template.md` now mandates commit-before-receipt
  after a systemic receipt-sentinel race was caught, recorded, and repaired.

## Honest state — read before relying

- **Freshness gate is RED on purpose**: shipped corpus is `.368`, ratified build
  is `.400`. It stays red until the ING-DELTA re-ingest. That is the gate working.
- **P@1 0.755 vs the 0.98 campaign bar** on the hybrid scout — capped by node
  entries being absent from the dense semantic index (out-of-scope surface);
  the proven fix is held as spawn S1 for wave 5.
- **suite_baseline is RED on master** (R31 flat-baseline) — pre-existing,
  unrelated to this wave, queued for its own leg.

## Receipts

Every claim above traces to `harness/notes/receipts/W4-*.json`; the crucible
verdict `W4-CRUX.json` is the wave's truth document — all builder numbers were
independently re-run, none inherited. Blueprint: `harness/notes/h22/BLUEPRINT.md`.
