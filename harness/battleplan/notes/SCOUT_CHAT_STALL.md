# SCOUT — chat stalls after the first turn

2026-09-20 · source doc for wave BP7 (scouts + SYNTH). Symptom as reported by Joe: SYNAPSE
answers the first message, then stops responding to inquiries once engaged in conversation.

## First principles

Turn 1 works, turn N does not. The request path is therefore intact; what breaks is state
that ACCUMULATES or is LEFT BEHIND between turns. Along the message path there are six
places that carry state across turns. One hypothesis per place, one scout per hypothesis
that Jev ranks plausible. Scouts are read-only TRUTH legs: they gather evidence, they do
not fix. SYNTH reads all scout receipts through the Jev screen line and writes the verdict.

## Evidence on disk (2026-09-20, pre-wave)

- No runtime logs under logs/, harness/notes/h22, or the H22 prefs dir in the last 7 days:
  scouts must reproduce or read code, not tail a log.
- `panel/chat_panel.py::_send_message` gates on `bridge.connected` only (FR-1, a752ca5b,
  2026-09-15). `_waiting_for_response` and the typing indicator are set on send and cleared
  only in `_on_response`; nothing times them out.
- `server/handlers.py:227` classifies `route_chat` READ-ONLY: it bypasses the C5 mutation
  lock and the WS resilience layer's mutating path.
- `_handle_route_chat` caches `TieredRouter` on the handler for the process lifetime and
  calls `_repoint_router_memory(owner)` every turn; `resolve_param(payload, "content")`
  while the panel sends `{"message": ...}` (aliases.py presumably maps it - VERIFY).
- Memory store: ae34ed96 (2026-09-17) fixed a duplicate deposit that DEGRADED the store;
  5.75.2 added `MemoryStore.health()` because a store could be refusing writes silently.
- 30 s slow-op timeout on the live `/synapse` path (harness/CLAUDE.md, Identity).

## Hypotheses (state carried across turns)

H1 panel-state   The panel believes it is still waiting: `_waiting_for_response` / typing
                 indicator never cleared because the reply to turn 1 did not arrive as a
                 `route_chat` response (different command name, error filtered, or a
                 proposal card left the input in a settled-pending state). Sends still go
                 out; the artist sees a spinner and no answer.
H2 transport     The socket drops after the first reply (server-side close on slow-op
                 timeout, or reconnect loop not restoring `connected`); FR-1 then refuses
                 every later send with BRIDGE_DOWN_LINE. Artist reads "not responding".
H3 lock          Turn 1 executed commands (recipe / undo group / render) that hold the C5
                 mutation lock or an open undo group; turn 2's follow-on commands queue
                 behind it. route_chat itself returns, but nothing it proposes lands.
H4 router        The cached TieredRouter carries state (cache, planner, LLM tier) that
                 makes turn 2 block past the 30 s timeout or raise inside `route()`; the
                 error response is swallowed or filtered on the panel side.
H5 sidecar       The brain's out-of-process interpreter (sidecar) or its stdio pipe
                 deadlocks after the first response (buffer full, thread not draining).
H6 memory        `_repoint_router_memory(owner)` on turn 2 hits a degraded store
                 (refusing writes / health UNKNOWN) and blocks or raises inside the
                 memory tier before the LLM tier is reached.

## Verdict shape (SYNTH)

One paragraph per surviving hypothesis: CONFIRMED / REFUTED / UNKNOWN, with the scout's
anchor. Then the single most likely cause, the reproduction Joe can run in the GUI in
under two minutes, and the smallest fix shape. UNKNOWN is a legal verdict.
