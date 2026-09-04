# bp5 Solaris v3 -- suite baseline (ratchet floor)

Read at the base commit every stream branches from.

| item | value |
|---|---|
| base commit | 6e3dd963 (master, v5.62.0) |
| collected | 7131 tests (`python -m pytest tests -q --co`, Python 3.14.2, no hou) |
| last human-promoted green | 6942 green on 2026-09-03 (BP4 wave, capsule a632139c) |
| full-run pass/fail/skip at base | recorded by the orchestrator in `harness/solaris_v3/runs/baseline_6e3dd963.txt` when the background run completes |

Rule (SWARM_CONTRACT law 6): a stream may not reduce the pass count. Compare your full-run numbers against this file in your REPORT.
