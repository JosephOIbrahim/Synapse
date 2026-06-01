# RSI HARNESS — Session Capsule (DIGEST)

> Reuses the CONTINUATION / session-capsule format. Written at INGEST, replaced
> at each cycle boundary / session end.

```
+== RSI HARNESS CAPSULE ========================================+
| MODE:                SIMULATED TEAM (no launcher; master, in turn)   |
| WHERE WE ARE:        DELIBERATE ⇄ EXECUTE — Line R CLOSED at L2 (+L3) |
| MILE MARKER:         1/6 loops closed (L2+) · R done; O/S/F/E/C open  |
| WHAT I WAS THINKING: SPEC ratified. VERIFY-THE-AUDIT on R confirmed    |
|                      the dead _memory guard (survived 7 CRUCIBLE       |
|                      attacks, zero drift); ordering fork resolved      |
|                      "close-now-swap-later". Wired get_synapse_memory  |
|                      into _handle_render_sequence (1 line); 384 tests  |
|                      pass; eval proved L1/L2/L3 across 2 fresh procs.  |
| NEXT ACTION:         DELIBERATE on Line O (§16 observability) —        |
|                      VERIFY-THE-AUDIT: RecommendationHistory has 0     |
|                      non-test callers; wire the panel poll.            |
| BLOCKERS:            none open. (Carry: TOPS render path is a separate |
|                      follow-up to R, not part of the one-liner.)       |
| MONETA:              BUILT but default-OFF; jsonl is the live default. |
|                      Line C = flip SYNAPSE_MEMORY_BACKEND + wire       |
|                      deposit_fn (substrate already on master).         |
| ENERGY REQUIRED:     low — next one-liner (O) is the same shape as R.  |
| IDEAS PARKED:        (1) TOPS render-path learning (R follow-up).      |
|                      (2) real-APEX-name discovery for the 10 nodetype  |
|                          dead-ends (Line S DELIBERATE).                |
+===============================================================+
```

## Files seeded at INGEST (`docs/rsi/`)

| File | Logical layer | State |
|---|---|---|
| `RSI_PLAN.md` | PLAN — the six lines (definitions, ROI) | seeded |
| `SPEC.md` | SPEC — Outcome / Predicates / Scope / Falsification / Strategy | **RATIFIED 2026-06-01** |
| `RSI_CHAMPION.md` | CHAMPION — the loop-closure ratchet | **R closed (1/6)**; O/S/F/E/C dormant |
| `RSI_DEADENDS.md` | DEADENDS — protected-immutable tier | seeded, 12 records |
| `FORUM.md` | FORUM — proposals / critiques | **ACTIVE** — Line R DELIBERATE+EXECUTE logged |
| `RSI_CAPSULE.md` | DIGEST — this capsule | seeded |

Maps onto existing artifacts (not re-created): LOG/TRACE → git history;
LEDGER → `forge/corpus/`; the registry → `.synapse/science/apex_registry.jsonl`.

**STATUS: DELIBERATE ⇄ EXECUTE active.** Line R closed at L2 (+L3), 1/6. Next:
DELIBERATE on Line O (§16 observability). SIMULATED TEAM — one line at a time.
