# v5.65.1 — five things Joe saw in the first ten minutes

Patch release, same evening as v5.65.0. Joe opened the new panel in Houdini
22.0.400, looked for ten minutes, and named five things. All five landed within
two hours as a team wave (`design/joe-five`, merged `33c46028`): one spec with a
per-provider usage investigation, five forges in parallel worktrees, one
integrator, two referees (both SOUND-WITH-NITS, no repair round). Rulings:
`harness/cto/runs/2026-09-05/RULING_JOE_FIVE.md`. Reloaded and measured LIVE in
Joe's running Houdini afterwards.

## For artists

- **The model token is a status light.** `ollama/deepseek-v4-flash` in the top
  right is green while the engine is live, amber while a turn streams, grey
  when unreachable or unkeyed. Palette colours only. LIVE: grey before Connect,
  green (#6E8F72 sampled) after.
- **TOKEN counts tokens.** The face gains THIS TURN · SPEND (prompt, completion,
  total, context share) and a SESSION block. The cause of "it does nothing":
  only Anthropic's usage was ever parsed. Now Ollama and OpenAI-style endpoints
  (`stream_options.include_usage`), Gemini (`usageMetadata`) and Nemotron feed
  it from the provider's own receipt; where a provider reports nothing the face
  says so, never an estimate. Ollama verified live: prompt 11 / completion 4 on
  a four-token call, context window from `/api/show`.
- **Two speakers, two colours.** USER carries the accent, SYNAPSE the green, on
  the name label and the turn's leading rule; body text unchanged.
- **Profiles retired from the UI.** No Profile submenu, no pills, no density
  switch; the composed profile is expert. The machinery stays for when the
  difference is worth showing.
- **Air above the wordmark.** The rail's top inset is a grid step larger,
  through the rhythm role; wordmark top edge 8 → 16 px at 340 wide (LIVE: 16).

## Tests

Full suite on master `33c46028` (stock Python 3.14.2, no `hou`): **7613 passed,
0 failed, 357 skipped** (`harness/notes/h22/pytest_v5651_master.txt`). Panel tier
on Houdini 22.0.400 offscreen: `tests/panel` + docking **239 passed / 1 failed**
(the D1 render-view dead verb, pre-existing); G3 strict **pass, 0 WARN**.

## Not in this release

Speaker colours seen live in a real exchange (the reloaded panel had no
transcript yet; Joe's next turn is the check). The referees' nits: the token
cannot fall back to grey on bridge loss because nothing writes `disconnected`
after the first tick; direct-tool paths show the mark working while the token
stays green; a FLOW-rig probe still pins the retired profile pill. All three are
backlog, none blocks.

## Standing RC blockers — waiver carried

Unchanged from v5.65.0; nothing here touched their surfaces.
