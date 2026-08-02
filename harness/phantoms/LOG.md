# PHANTOM SWEEP — LOG

*Append-only. Columns: date | line | attempt | predicates | fix-queue.*

| date | line | attempt | predicates | fix-queue |
|---|---|---|---|---|
| 2026-07-31 | FRAME | SPEC + orchestrator + workflow built (CTO, surgical pass) | — | harness armed, PROPOSED, awaiting idle start |
| 2026-07-31 | SWEEP | run 1 (orchestrator Agent fan-out — Workflow engine unavailable) | SW1 PASS (19/19 symbols assayed) / SW2 PASS-with-cap (154 of 179 classified, 25 recorded UNCLASSIFIED by group cap) / SW3 PASS (SWEEP-2026-07-31.md written) / SW4 PASS (zero sweep edits landed); crucible attack FAIL-then-PASS after in-scope re-verdict (initial citations were harness/state/*.jsonl out-of-surface + one already-held row) | 35 FIX (all corpus rag/** usdrender teaching); spec remains PROPOSED |
| 2026-07-31 | SWEEP | run 1 supplement | attack re-verdict over-ruled on MISSING-HITS: first attacker found 9 in-scope harness/notes/h3a/indep_*.py hits the inventory cap swallowed unrecorded (hand-grep verified by orchestrator); supplement classified all 9 KEEP (negative controls), zero new FIX; final totals 163/188 classified (128 KEEP / 35 FIX) with 25 UNCLASSIFIED recorded; ledger amended in place; SW2 now PASS-with-supplement | fix-queue unchanged: 35 (corpus usdrender) |
| 2026-07-31 | FIX-R1 | forge dispatched (Joe ratified all 6) after fix-verify found 0/6 plans sound as-written — corrected specs from 6 crucibles: substring trap (configure_usdrender_rop), uppercase banners, spurious :197 row, coverage gaps | 41 lines, 6 commits (c15e906..79d85d1); spec-attack SOUND; side-effects attack found residual corpus + karma :5 keyword policy | round 2 opened (Joe: "classify then fix") |
| 2026-07-31 | FIX-R2 | classify (8 legs) → forge → attack on residual corpus + karma :5 repair: 10 edits, 4 KEEPs (incl. render_farm:585), common_errors:66 MAP-VALUE corrected (query was resolving TO the phantom) | 14 commits total on fix/corpus-usdrender-rop; attack SOUND; GLOBAL PROOF: bare-usdrender = keyword dual-spellings + blueprint :42 warning only | claim now true: no corpus file teaches the usdrender node type; merge = Joe's gate; content_digest rebuild queued as follow-up |
