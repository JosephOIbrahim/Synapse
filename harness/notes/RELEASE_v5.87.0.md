# Release preparation: v5.87.0

Publish two commits on top of v5.86.0 (tag `v5.86.0` on `0e67a740`; master was
`3610b63c`, the commit that records its assets). Joe's word, 2026-09-29: "Git
push, git release, bump release version". Before that he had said "use computer
use to implement the blueprint" for Level 1 (`claude/LEVEL1_BLUEPRINT.md`).

| Commit | What it does |
|---|---|
| `cff77508` | Level 1 M0: the panel recovers an expired session (F1a), `POST /mcp` answers the session gate with HTTP 400 or 404 (F1b), and the stdio bridge never re-sends a change that may have run (F2); 14 tests |
| `429cfec6` | Level 1 M1: one outcome vocabulary on `/mcp`, the WebSocket, the stdio bridge and the panel; `-32006` for a busy server; 20 tests |

## Evidence

- **Tests and mutation.** M0 adds 14 tests, and six mutants, one per fix and one
  per pin, each made one fail. M1 adds 20 tests, and seven mutants, one per
  piece, each made one fail.
- **Full suite on the release tree.** Windows, Python 3.14, Houdini-only tests
  deselected: 10,483 passed, 426 skipped, 119 deselected, 5 xfailed, 0 failed. Except ratchet: 1,360 broad and 983 silent, unchanged from v5.86.0.
- **Houdini ran the tree.** Joe restarted Houdini 22.0.400 at 19:04 on the M1
  tree. Its Python 3.13 bytecode for the M1 files was written at 19:04:29 to
  19:04:31 and matches each source's size and modification time.
- **Live checks, by computer use, 19:07 to 19:39.** On `/mcp`: no session header
  gave HTTP 400 with `refused/session.missing`, an unknown session gave 404 with
  `retryable/session.expired` and `dispatched: no`, a notification gave 202, and
  `tools/list` gave 137 tools. The panel's client, with its session id replaced
  by one the server never issued, received the 404 (seen by a spy on
  `_session_gone`), started a new session and answered `synapse_ping`. With
  `SYNAPSE_MCP_READ_ONLY=1` set in Houdini's environment behind a 150 s timer,
  `houdini_set_parm` was refused on `/mcp` (-32005, `refused/policy.read_only`)
  and through `mcp_server.send_command`; `tops_cancel_cook` passed the fence on
  both routes; `synapse_ping` answered; unset, the same write ran and failed on
  its missing node. The Identify button drew four bubbles and cleared them; with
  200 selected nodes, a 10 ms main-thread timer measured an 81 ms longest pause
  against 11 ms idle. Probes and results: `.token-saver/bp11/l1g1_probe.py`,
  `l1ro_check.py`, `l1id_setup.py` and their JSON results.
- **Jev.** Jev checked 12 claims from the notes against the code that could
  contradict them (citation-check pattern; supports at 0.8 or more stands).
  Seven stood. Five went to a direct code read: two stood as written (where the
  outcome travels on each route, and `-32007` is never sent), and three were
  tightened (the six outcomes are the six besides ok; on `/mcp` a tool failure
  reaches the client as -32603 rather than as an `isError` result; the stdio
  bridge's failure result is not flagged `isError`). Ledger:
  `harness/jev/ledger/v5.87.0.release.notes.jsonl`.
- **Advice.** An advisor model reviewed the approach before each phase and
  before this release.

## Decisions

- **Source release.** Joe did not ask for an installer this time, so no
  v5.87.0 Setup is built. The v5.86.0 Setup stays the download, and the README,
  the installation page and the status page say it lacks these changes.
- **5.87.0.** M1 is a feature, a new outcome vocabulary and a new error code, so
  the minor version moves.
- **Open, not decided.** R-5 to R-7 in `claude/LEVEL1_BLUEPRINT.md` v1.1, written
  by a second seat while M1 was being built. This release ships M1 as built, on
  v1.0's wire: outcomes in JSON-RPC error `data`, and the new codes `-32006` and
  `-32007`. If R-6 is adopted, moving tool failures into `isError` results
  changes this published contract.

## Incidents

- Opening Houdini through the computer-use launcher started a second Houdini
  (19:17). It was stopped within a minute, at its splash screen; Joe's session
  and port 9999 were untouched.
- Houdini 22's Python shell runs code off the main thread, so a `QTimer` made
  there never starts; the main-thread probe went through
  `hdefereval.executeInMainThreadWithResult`.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
