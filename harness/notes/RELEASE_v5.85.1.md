# Release preparation: v5.85.1

Publish three commits on top of v5.85.0 (`8a90e5e5`). Joe's word: "Go"
(2026-09-28), after the seat proposed shipping them together.

| Commit | What it does |
|---|---|
| `914f995e` | Claude Fable 5.1, Opus 5.5 and Sonnet 5.5 in the model picker; the default stays `claude-sonnet-4-6` |
| `4e04daba` | `/mcp` and the WebSocket Origin check read headers case-insensitively; `tests/test_mcp_header_case.py` |
| `692d25a6` | `docs/mcp/SETUP.md`: the Claude Code steps verified live |

## Evidence

- **The bug.** On 2026-09-28, `claude mcp get synapse` reported the server as
  connected, with the tools fetch failing on "Missing Mcp-Session-Id header". A probe
  against the running server listed the tools with `Mcp-Session-Id` and got JSON-RPC
  error -32004 with `mcp-session-id`.
- **The fix, live.** After the fix and a Houdini restart (pid 59320), both spellings
  listed the tools, and `claude mcp get synapse` reported the server as connected.
- **Mutation.** With the old `server.py`, `tests/test_mcp_header_case.py` fails 2 of 8.
- **Live read test.** Claude Code 2.1.284 on Joe's Max plan (model
  `claude-sonnet-5-5`) loaded 137 tools. It answered 22.0.400, `untitled.hip` and
  0 selected using only allowlisted read tools, with 0 permission denials, and the
  answers matched the screen.
- **Models.** A live `GET /v1/models` listed all three
  (`harness/notes/econ/V3_probe_live.bp11-models-0928.json`). A completion smoke
  through the panel's provider was refused for credit on the only available key, so
  the default does not move.
- **Tests.** The targeted run passed 460 with 12 skipped. The `tests/` suite passed on
  Windows with Python 3.14, and `harness/jev/tests` passed 77. A bare `pytest` run
  collects `tests/` and `harness/jev/tests` into one process. In that run,
  `test_jev_edge::test_repair_mission_is_scoped_to_flagged_rows_and_valid` fails from
  a cross-suite leak. It passes alone and in CI's separate step. This is a BP12 item.

This record does not claim that the later CI, push or publication steps have
completed. They are checked after publication.
