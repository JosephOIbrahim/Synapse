# LATENCY HARNESS — LOG

Append-only. Newest row last. The board reads the last row.

| date | tag | entry |
|---|---|---|
| 2026-08-02 | SCAFFOLD | Harness created. SPEC ladder L0-L5 + 8 predicates. verify.py honest at 0 PASS / 0 FAIL / 8 PENDING — nothing claimed, nothing broken. |
| 2026-08-02 | WHY | Opened on a contradiction, not a hunch: the 07-27 report's ledger says Houdini-side work is 1-70 ms and therefore "the 5%"; commit `98b556f` measured 6.9-7.7 s of Houdini-side stage serialization at 100k prims. Both survive only if the ledger is scale-scoped and says so nowhere. |
| 2026-08-02 | SELF-CATCH | P5's producer path was wrong on first run — it looked for `scripts/_benchmark_latency.py`; the benchmarks live at the repo root. Found by running the verifier, fixed in the verifier. The design doc names them without a directory, which is how the mistake was inherited. |
| 2026-08-02 | SCOUT | 20-agent read-only fan-out dispatched (run `wf_b9c32632-1fc`): 5 ground mappers, 9 hypothesis prospectors, 4 crucibles, 2 instrument designers. No worktrees, no writes — a second fan-out was live in `.claude/worktrees/wf_9aef52f3-c03-*` at dispatch time. |
