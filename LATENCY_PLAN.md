# SYNAPSE Latency Plan

Rewritten Sat 10/3/2026 from measurements. The July plan described v4.2.1 on Houdini 21 and is in git history.

Every number below is measured unless it says projected. The source is the panel's own turn ledger,
`~/.synapse/usage/turns.jsonl` (111 rows, 94 with timings), read by `.scratch/freeze/turns2.py`.

## Where a turn's time goes

Last 7 days, 80 timed turns, almost all on `ollama / deepseek-v4.1-flash:cloud`.

| Measure | Value |
|---|---|
| Wall time per turn | median 17.8 s, p90 123 s, max 243 s |
| Share of wall time | model 64%, tools 36% |
| Model rounds per turn | median 4, max 25 |
| Input tokens per turn | median 138,000, max 2,300,000 |
| Turns with a prompt-cache read | 0 of 111 |

Saturday's run-through, on v5.93.0:

| Beat | Wall | Model | Tools | Rounds | Tool calls | Input tokens |
|---|---|---|---|---|---|---|
| 1, "How was this world scaled and grounded?" | 38 s | 10 s | 27 s | 5 | 12 | 125,509 |
| 2b, Scatter Instances | 96 s | 51 s | 45 s | 11 | 21 | 654,959 |
| 3, recall after relaunch | 11 s | 4 s | 7 s | 2 | 2 | 44,265 |
| 2c, `/spatial` (no model request) | about 6 s | 0 | - | 0 | 1 | 0 |

## Finding 1: every tool call pays a fixed 2 seconds

27 of the 30 tools with three or more samples have a median between 2.00 s and 3.3 s. `synapse_ping` is 2.00 s.
`synapse_solaris_build_graph`, which runs in-process, is 0.06 s.

The cause: `panel/tool_executor.py` opens a new `HTTPConnection("localhost", port)` for each call. On Windows
`localhost` resolves to `::1` first, the listener is IPv4-only, and the connect waits about 2 s before falling back.
Measured on this machine against `:9999`: `localhost` 2.01 s, `127.0.0.1` 0.009 s.

The fix is on branch `fix/tool-executor-loopback`: connect to `127.0.0.1` first, keep `localhost` as the fallback.

Projected, not yet measured in Houdini: Beat 1 from 38 s to about 14 s, Scatter from 96 s to about 54 s, recall from
11 s to about 7 s. Across the week it removes most of the 36% tool share.

## Finding 2: the model re-reads the whole prompt every round

A round sends about 25,000 to 60,000 input tokens, and no turn has ever had a cache read. Scatter's first token took
30.7 s. Two levers, neither built:

1. Send fewer tool schemas per turn. The panel agent is offered 99 tools. A routed subset per request is what the Jev
   panel route was written for; it is in shadow and reads `disabled`.
2. A provider with prompt caching for the fixed prefix. The Ollama cloud relay reports none.

## Finding 3: Scatter takes 11 rounds for a 2-call recipe

The recipe needs one knowledge lookup and one build call. The turn made 21 calls, 10 of them
`houdini_get_usd_attribute`, while the model looked for the world prim and the collider file. Resolving
`<WORLD_PRIM>` and `<COLLIDER_GLB>` in code before the model sees the recipe would cut the turn to 2 or 3 rounds.
Jev parked Scatter recipe changes until after the take (0.88).

## Smaller

- `synapse_memory_query`: median 17.0 s over 4 calls. Not on a demo beat.
- `synapse_context`: median 3.3 s, one call at 37.6 s.
- The test suite takes 7 min 16 s serially; `test_probe_timeout_is_fail` is 30 s of it, and pytest-xdist is not installed.

## Order

1. Merge the loopback fix and time Beat 1 once in the GUI.
2. After the take: pre-resolve recipe placeholders in code.
3. After the take: route the tool list per request, then measure input tokens per round again.
4. The model benchmark already queued for Oct 8 should record first-token time and cache reads per provider.

## What the zero-token paths show

`/spatial` answers in about 6 s and `/identify` makes no model call. For an ask the product can answer from the scene
alone, a local path is an order of magnitude faster than any agent turn above.
