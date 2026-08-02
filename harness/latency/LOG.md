# LATENCY HARNESS — LOG

Append-only. Newest row last. The board reads the last row.

| date | tag | entry |
|---|---|---|
| 2026-08-02 | SCAFFOLD | Harness created. SPEC ladder L0-L5 + 8 predicates. verify.py honest at 0 PASS / 0 FAIL / 8 PENDING — nothing claimed, nothing broken. |
| 2026-08-02 | WHY | Opened on a contradiction, not a hunch: the 07-27 report's ledger says Houdini-side work is 1-70 ms and therefore "the 5%"; commit `98b556f` measured 6.9-7.7 s of Houdini-side stage serialization at 100k prims. Both survive only if the ledger is scale-scoped and says so nowhere. |
| 2026-08-02 | SELF-CATCH | P5's producer path was wrong on first run — it looked for `scripts/_benchmark_latency.py`; the benchmarks live at the repo root. Found by running the verifier, fixed in the verifier. The design doc names them without a directory, which is how the mistake was inherited. |
| 2026-08-02 | SCOUT | 20-agent read-only fan-out dispatched (run `wf_b9c32632-1fc`): 5 ground mappers, 9 hypothesis prospectors, 4 crucibles, 2 instrument designers. No worktrees, no writes — a second fan-out was live in `.claude/worktrees/wf_9aef52f3-c03-*` at dispatch time. |
| 2026-08-02 | HARVEST | Fan-out complete: 20/20 agents, 0 errors, 3.13M subagent tokens. LEDGER.md written; registry 9 -> 11 hypotheses (H10 gate-axis bypass + H11 unconsumed honesty fields), all adjudicated by 4 crucibles. Producer: wf_b9c32632-1fc journal.jsonl. |
| 2026-08-02 | HEADLINE | Contradiction RESOLVED: regime real+per-op, axis WRONG (authored array volume, not prims — 16,677x measured gate miss). The 07-27 report's #1 lever (extend declarative coverage) REFUTED by its own prospector, kill confirmed 3/4 crucibles: it would ADD a round-trip vs synapse_batch. |
| 2026-08-02 | DESIGNS | I1 scale-bench + I2 perf-ratchet designed, unbuilt (journal). I2's ruling: counted proxy, not wall-clock — CI has no pxr, a timer cannot gate this repo. Building them is the next wave. |
| 2026-08-02 | BUILD | Wave wf_006556ba-f9c: Lane A (cache breakpoint + usage producer, crucible SOUND-WITH-NITS) + Lane B (volume-gate re-key, crucible SOUND) both MERGED per R301. H10 -> L4 (measured ~55,000x on the repro, both machines). H4 fix landed, still unpriced -- the producer exists, the pricing awaits a real session. |
| 2026-08-02 | FOUND | Lane A's crucible surfaced a PRE-EXISTING panel defect while attacking: claude_worker's else-branch never appends the final end_turn assistant text to _messages -- multi-turn API history silently loses the assistant's last words. Not lane A's; queued to the panel session (R309/R204). |
