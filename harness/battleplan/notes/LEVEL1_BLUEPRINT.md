# LEVEL 1 BLUEPRINT - every call runs, or stops with a reason an artist can act on

Status: v1.1 - 2026-09-29. v1.0 was authored by the CTO seat on Joe's word. v1.1 is a second seat's review of
every claim against the same commit, `0e67a740`, and of the transport rules against the MCP specification,
checked again by an independent verifier. M0 has since landed locally as `cff77508`, not yet pushed, and v1.1
records it.

**Update v1.2, 2026-09-29 20:17, CTO seat.** M0 and M1 shipped in v5.87.0 (release commit `fd225f6b`, CI run
36648579497), on Joe's word "Git push, git release, bump release version". M1 was built on v1.0's wire, before v1.1
was written: outcomes ride in JSON-RPC error `data` on `/mcp` and in `data` on the WebSocket, and M1 added
`-32006` (busy) and `-32007` (needs an artist, not sent yet). R-5 to R-7 are still proposed. Because M1 is now
published, adopting R-6 would change a published contract rather than a local commit. The live checks are in
section 8.

**Update v1.3, 2026-09-29 21:45, CTO seat.** Joe's "Continue" adopted R-5 and R-6; R-7 comes later as its own
milestone. Two local commits, not pushed. M1b (`3496737c`) moves every tool failure into a result flagged
`isError` on `/mcp` and on the stdio bridge, withdraws the published `-32006` and `-32007`, and sets the flag on
every stdio error path (M0+). M2 (`86faa156`) is the preflight inside `synapse_health`, with the gate on `/mcp` and
on both WebSocket servers. Section 7 records both, and section 3 notes what M2 built differently. Their live
checks wait for a Houdini restart on the new code.

**Update v1.4, 2026-09-30 09:05, CTO seat.** M0+, M1b and M2 shipped in v5.88.0 (release commit
`507153d4`, tag `v5.88.0`, CI run 36717537891), on Joe's word "Gut push, then Git release". One follow-up rode with
them: `90246aea` lets the farm controls through the readiness gate, as they already pass the stall gates. The
notes say that `-32006` and `-32007` were withdrawn one release after they shipped. The live checks for M1b and M2
have not run, because the Houdini session still runs v5.87.0's code.

Covers items 01 and 02 of the studio readiness order: **session preflight and error taxonomy** (T1b) and
**the cache guard** (T3c).
Source of truth for the Level 1 legs. Update this card; don't multiply it.
Companions: `claude/BP11_CTO_PLAN.md` (queue and rulings), the `Studio Readiness Priorities` canvas (the
order and Jev's scores), and `docs/SYNAPSE_RESOURCE_AWARE_CACHE_BLUEPRINT.md`, whose verdicts, laws and
feasibility maths the cache guard reuses rather than forks.

## What v1.1 changed

Most of v1.0 holds. The three M0 bugs are real, each sits exactly where v1.0 says, and the seat has fixed all
three in `cff77508`. These are the changes, most consequential first. The new choices they raise are R-5 to
R-7 in section 9; R-1 to R-4 stand as decided.

1. **The signal table mapped codes that are never sent.** `-32001`, `-32002` and `-32003` have no raise site
   anywhere. On `/mcp`, a failed tool, a stalled main thread, the rate limiter, an open breaker and a crash all
   arrive as `-32603` with free text. v1.1 adds that row, marks the three as unused, and marks the signals
   Level 1 creates as new (F5, section 2).
2. **Neither route flags a failed tool the way MCP specifies.** The stdio bridge returns every failure as a
   successful result, and `/mcp` turns every tool failure into a protocol error. MCP puts tool failures inside
   the result with `isError: true`, which clients should show the model. v1.1 adds F8, rewrites "On the wire"
   and proposes the result channel in place of v1.0's two new JSON-RPC codes (section 2, R-6).
3. **A change can land in a scene the caller never saw.** After Houdini restarts, the stdio bridge reconnects
   silently and an HTTP client starts a clean session, so an agent that keeps going works in a new process,
   perhaps with another file open. The same happens when someone opens another file mid-conversation. Houdini
   already keeps a per-process boot token and a hip-file hook. v1.1 builds a scene generation from them, and a
   change from a caller that has not seen the current scene is refused once with the open file named, a "you
   are here" (F9, check 8, rule 12).
4. **A batch walks past a transport gate.** `synapse_batch` dispatches its commands without `handle()`, so a
   gate that checks tool names sees only the batch. The batch already refuses farm commands, and v1.1 refuses
   guarded commands the same way (F10, section 4, rule 14).
5. **The guard's scope is a named list.** `is_cookish_tool` exists to enable the panel's Cancel cook button and
   names TOPs entry points only. v1.1 names the registry tools the guard covers, and a walk test catches new
   ones (F7, section 4).
6. **A simulation cannot be sampled into a range.** The cache blueprint forbids sampling a later frame without
   its preceding state, and says the first frame is not the largest. For a sim, a sample gives a floor, so the
   call still needs approval (section 4, M4).
7. **Smaller corrections.** The "Unknown session" stream more likely came from an HTTP client such as Claude
   Code than from the panel (F1b). The stdio connect does retry (F3). `version.match` must compare release
   versions, because the protocol strings already disagree (F11, check 5). Preflight extends `synapse_health`
   rather than adding a 138th tool (F12, R-5), and the gate runs it, not the client. Rule 9's budget holds on
   the ready path only. Approval is two calls because a wait would deadlock the panel (F4). The Python
   exclusion now cites the overview, which says it, rather than `SETUP.md`, which does not.

## 0. One paragraph

Today a SYNAPSE call can fail in several ways that all look the same. The bridge may be gone, or the session
may have expired. A rule may have refused the call, a cook may have failed, or the reply may have been lost
after the work ran. The caller sees free text and tries again.

Level 1 gives every call one of seven typed outcomes, and each outcome says what to do next. A cheap,
read-only preflight runs before any work that changes the scene. The cache guard stops a cook that would
write more than the disk can hold, or more than the artist's budget, until an artist says go.

Level 1 does not make calls succeed more often. It makes failures say what they are, and it stops the one
kind of call that can fill a disk.

## 1. What the code says today (read at `0e67a740`, 2026-09-29; re-checked line by line in v1.1)

Evidence tier is READ (from source) unless marked. Line numbers are at that commit. M0 (`cff77508`) has since
changed `mcp/server.py`, `mcp_server.py` and `panel/tool_executor.py`, so in those three files find a line by
its symbol. Module paths are under `python/synapse/`; `mcp_server.py`, `VERSION`, `README.md`, `docs/` and
`tests/` are at the repo root.

- **F1a. The panel never recovers an expired session (fixed in M0).** `panel/tool_executor.py:356` clears the
  session when the error code is `-32003`, with the comment `SESSION_INVALID`. But `-32003` is `COOK_ERROR`.
  `SESSION_INVALID` is `-32004` (`mcp/protocol.py:45-46`), and that is what the server sends for a missing or
  unknown session (`mcp/server.py:447-458`). The panel does drop its session when the port changes or a
  connection fails (`panel/tool_executor.py:218-220`, `:283-287`), but not when the server answers. Sessions
  expire after 30 minutes idle (`mcp/session.py:21`) and are swept whenever another client initializes
  (`mcp/session.py:76-78`), and the client's `reset()` has no callers. So a session that was swept, or lost to
  a server restart on the same port between two calls, stays stale. Every panel call then returns `Unknown
  session: <id>` until Houdini's Python restarts, because the client is a module-level singleton. `COOK_ERROR`
  has no raise site today, so the wrong check never fires at all.
- **F1b. External HTTP clients are never told to start again (fixed in M0, with 400 and 404).** `POST /mcp`
  answers an unknown session with HTTP 200 and a JSON-RPC error body (`_post_response`,
  `mcp/server.py:964-978`). The GET route answers the same case with HTTP 404 (`mcp/server.py:1062-1068`). The
  MCP Streamable HTTP transport says a server must answer a request that carries a terminated session id with
  404, and that a client receiving 404 must re-initialize (Session Management, rules 3 and 4, the same text in
  2025-06-18, which SYNAPSE negotiates, and in 2025-11-25; tier DOCS). A POST without the header also gets
  200, where the spec says it should get 400. A client that follows the spec therefore re-initializes after a
  GET but not after a POST.
- **Where the Unknown session stream most likely came from (v1.1).** Only the two HTTP routes produce that
  text (`mcp/server.py:457`, `:1066`); the stdio bridge cannot. Claude Code's documented connection is HTTP
  (`claude mcp add --transport http`, `docs/mcp/SETUP.md:65`). After Houdini restarts, or after its session is
  swept, every POST it sends gets 200 and `Unknown session`, and nothing tells it to start again. So for an
  external agent the likelier source is F1b, and F1a is the same failure inside the panel. M0 fixed both.
  Whether Claude Code re-initializes by itself once it gets a 404 is not yet observed (gate G8).
- **F2. The stdio bridge can send a scene change twice (fixed in M0).** `mcp_server.py` makes "one transparent
  retry on connection failure" (lines 392-451). The retry also runs when `ws.send` succeeded and the
  connection dropped while waiting for the reply. So a mutation that may already have run is sent again under
  the same command id, a per-process sequence number (`mcp_server.py:138-141`). The server keeps no
  de-duplication by command id; only recipes de-duplicate, by their own `request_id`
  (`server/handlers_recipe.py:102-105`). The panel's own client has the right rule: `MCPOutcomeUnknown`,
  possibly sent and the reply lost, is never re-sent. The stdio path did not. It is the path the repo's
  `.mcp.json` launches, and the documented alternative to HTTP for Claude Code. M0's
  `mcp/resend_policy.may_resend()` now sends a command again only if its bytes never left, or if it is a
  protocol command, a stop control or a tool read-only under both gating sets.
- **F3. A failure to connect is untyped.** On the stdio path, `_get_connection()` sits outside the retry's
  `try` (`mcp_server.py:393`). It does retry the connection itself, twice per candidate URL, 50 ms apart
  (`mcp_server.py:189-190`, `:344-367`). Then it raises a `ConnectionError` whose text is already plain and
  useful ("Houdini might not be running..."), and that text reaches the client with no type (F8).
- **F4. "Needs an artist" has no working channel.** Disk-writing tools raise the bridge gate to APPROVE
  (`panel/bridge_adapter.py:182-186`). But the production bridge approves without showing a card
  (`docs/architecture/overview.md:107`). The overview gives the reason: attaching the bridge's blocking
  approval poll to the GUI thread would deadlock the panel (`:111`), and that constraint shapes the approval
  design in section 4. The disk-writing set is four tools: farm prepare, submit and cancel, and the Karma XPU
  shot setup. The cook and render tools that write caches as a side effect are not in it.
- **F5. On `/mcp`, nearly every failure has the same code.** The HTTP server has a circuit breaker, which
  opens after 5 failures for 30 s, and a rate limiter (`mcp/server.py:375-389`, off with
  `SYNAPSE_RESILIENCE=0`). A stalled main thread (`:662-673`), the rate limiter (`:675-683`), an open breaker
  (`:685-693`), a failed tool (`:648-651`, `:797-809`) and an unhandled exception (`:468-473`) are all sent as
  `INTERNAL_ERROR -32603` with free text. Among tool-call failures, only a missing or unknown session
  (`-32004`) and read-only mode (`-32005`) have codes of their own; protocol errors keep the standard codes,
  such as `-32601` for an unknown method (`:494`) and `-32602` for a call without a tool name (`:592`). The
  breaker decides what counts as an infrastructure failure by looking for the words timeout, main thread,
  crashed or unresponsive in the error text (`:801`). The WebSocket route gates the same things in its own
  way, and its one structured field, `retry_after`, is flattened into prose by the stdio bridge
  (`mcp_server.py:465-466`).
- **F6. The cache advisor already speaks the right language, but only advises.** `cache_policy` defines the
  verdicts `insufficient_disk`, `measure_first`, `optimize_first` and `unknown` (`cache_policy/models.py:76-85`).
  It has feasibility maths on high estimates with a free-disk floor (`cache_policy/decision.py:329`), and the
  cache blueprint's law 4 says disk writes require explicit approval
  (`docs/SYNAPSE_RESOURCE_AWARE_CACHE_BLUEPRINT.md:198`). But `synapse_assess_cache` is off by default
  (`SYNAPSE_CACHE_ADVISOR_ENABLED`), and nothing calls it before a cook. Nothing stops a 200 GB sim.
- **F7. Where the risk actually sits.** The standard panel worker already refuses PDG cooking, rendering and
  arbitrary Python (`README.md:55`). An external MCP client is not under worker policy, and neither is a future
  worker that allows cooking. The guard therefore belongs in the transport, beside the read-only fence, where
  it covers every caller. `is_cookish_tool` (`panel/direct_tool.py:122-137`) is not the guard's scope. By its
  own docstring it only decides whether the panel's Cancel cook button is enabled, and it names TOPs and PDG
  entry points only, deliberately. Section 4 names the scope.
- **F8. Neither route flags a failed tool the way MCP specifies (v1.1).** MCP reports a tool's execution
  failures inside the result with `isError: true`, and says clients should show those to the model so it can
  correct itself. Protocol errors are for unknown tools, malformed requests and server errors, and clients may
  show them (specification 2025-11-25, Tools, Error Handling; tier DOCS). The stdio bridge never sets the flag.
  Every failure returns as text in a normal result (`mcp_server.py:1203-1211`, and the same shape in its other
  call paths), and the pinned SDK marks a returned list `isError=False` (`mcp` 1.26.0,
  `server/lowlevel/server.py:576`). To Claude Code, a refused connection, a timeout and a failed cook are
  successful calls whose text describes a failure. `/mcp` does the reverse, on purpose: it turns every
  `isError` result into a `-32603` protocol error (`mcp/server.py:586-588`). The pinned SDK accepts a returned
  `CallToolResult` (`server/lowlevel/server.py:540`), so the bridge can set the flag itself.
- **F9. Houdini knows when its scene changed, but no caller is told (v1.1).** `server/session_store.py:181-198`
  keeps a per-process boot token on `hou.session`, and the panel's conversation store uses it to tell a
  reattach from a new boot. Scene memory already registers a hip-file hook that sees every load, save and
  clear (`host/memory_lifecycle.py:111-131`). Nothing on the MCP side uses either, and `initialize` returns
  nothing that identifies the Houdini process or the open file (`mcp/server.py:500`). So a caller that
  re-initializes or reconnects after a restart, or keeps going after someone opens another file, cannot tell
  that the scene under it changed. The stdio bridge reconnects silently on the next call (`_get_connection`),
  so an agent that keeps going after a restart works in the new process as if nothing had happened.
- **F10. A batch passes a transport gate unseen (v1.1).** `synapse_batch` runs its commands through
  `registry.invoke()` directly and bypasses `handle()`, as its own comment records
  (`server/handlers.py:539-542`). A gate that checks the tool name sees only `synapse_batch`. The batch already
  refuses farm commands inside it (`server/handlers.py:991-993`), which is the pattern section 4 reuses.
- **F11. Version strings disagree, and none are compared (v1.1).** The stdio bridge stamps protocol `5.4.0` on
  every command (`mcp_server.py:188`), and the server answers `4.0.0` (`core/protocol.py:31`). The release is
  `5.86.0` (`VERSION`). The server knows it as `synapse.__version__` (`__init__.py:123`) and reports it in
  `initialize`, falling back to a stale `5.8.0` (`mcp/server.py:261-269`). The stdio bridge has no release
  version at all, and the panel introduces itself as `1.0.0` (`panel/tool_executor.py:308`).
- **F12. Three health tools already exist (v1.1).** `synapse_ping`; `synapse_health`, which returns liveness,
  whether `hou` is available, the protocol version and a write-plane state that can honestly be unknown
  (`server/handlers.py:919-935`); and `synapse_doctor`, for install and operations. `ping` and `get_health`
  bypass the WebSocket rate limiter (`server/hwebserver_adapter.py:219-224`). The HTTP route also already
  refuses a call while the main thread is stalled, after a probe of up to 2 s (`mcp/server.py:662-673`,
  `server/main_thread.py:379-406`).

## 2. The outcome taxonomy (contract)

Every tool call on every route ends in exactly one outcome. The routes are panel HTTP, external HTTP, and
stdio forwarded over the WebSocket.

| Outcome | What it means | Who acts next | Ran? | Automatic retry |
|---|---|---|---|---|
| `ok` | It ran and the result is attached. | nobody | yes | not needed |
| `refused` | A rule stopped it before dispatch: read-only mode, worker policy, a safety guard, a changed scene, or a disk that cannot hold the output. | the caller changes the request, or an artist changes the rule | no | no; the same call gets the same answer |
| `retryable` | Nothing ran, and the cause is passing: an expired session, a restarting bridge, the rate limiter, an open breaker. | the client, automatically | no | once, after the named wait |
| `unrecoverable` | Nothing can succeed until something outside the call changes: Houdini is not running, the server is not started, the port is wrong, the auth key does not match, the versions disagree. | the artist, with the named fix | no | no |
| `needs_artist` | The call would run, but a person must approve it first: a cook over the cache budget, or an unknown size over a long range. | the artist, in the panel | no | no; only after approval |
| `unknown_outcome` | It may have run. The reply was lost, invalid, or late. | the artist inspects the scene first | maybe | never |
| `failed` | It ran and failed: a cook error, a missing node, an exception. | the caller reads the error | yes | no |

**Fields.** Each outcome carries `outcome`; a stable `code` for software (`session.expired`,
`cache.over_budget`); a one-sentence `message`; a `next` action in plain words ("Click Connect", "Approve it in
the panel"); `dispatched` as `no`, `yes` or `maybe`; `retry_after_s` for `retryable`; `evidence`, the numbers
behind a refusal; and `scene`, the scene generation of the Houdini that answered (F9, check 8).

**On the wire (revised in v1.1; R-6 decides).** This replaces v1.0's proposal, which kept outcomes in JSON-RPC
errors and added two codes.

- A tool call's outcome travels inside the tool result, on every route. Every outcome except `ok` sets
  `isError: true`, as MCP specifies for tool failures (F8).
- The first text line reads `<outcome>: <message> Next: <next>`. The model sees the class and the action even
  when a client shows it nothing else. The full outcome object rides in `_meta["synapse/outcome"]` for
  software. It stays out of `structuredContent`, which a tool's future output schema would own. `_meta` also
  carries the scene generation on every result, `ok` included (check 8).
- The stdio bridge returns a `CallToolResult` with the flag set, instead of a bare list. WebSocket responses
  carry the object in `data.outcome`, and the bridge passes it through unchanged.
- JSON-RPC errors stay for protocol failures: bad JSON, an unknown method or tool, and sessions. An unknown
  session on `POST /mcp` answers HTTP 404, and a missing header answers 400 (F1b, done in M0).
- `-32005` keeps its code for now, because v5.86.0 documents it, and its message gains the outcome line.
  Moving it into the result belongs to R-6.
- v1.0 proposed `-32006` for a busy server and `-32007` for needs an artist. Both are tool outcomes, so under
  this proposal they are not needed.

**Signals, mapped (revised in v1.1).** Rows marked *new* are signals Level 1 creates; the rest exist today.
At `0e67a740` the stdio bridge could not tell a send that failed from a reply that was lost: both landed in
the same branches, and both were retried (`mcp_server.py:427-447`). M0's `resend_policy` now makes that
distinction.

| Signal | Outcome | Code |
|---|---|---|
| `SESSION_INVALID -32004` | `retryable`: the server refused before dispatch; re-initialize, then retry once (a retried change then meets check 8) | `session.expired` |
| *new:* a change from a session that has not seen the current scene: a new session, a restarted Houdini, another file opened | `refused` once; the message names the open file and what changed | `scene.changed` |
| `READ_ONLY_REFUSED -32005` | `refused` | `policy.read_only` |
| `INTERNAL_ERROR -32603` from a tool's `isError` result | `failed` | the tool's own, such as `scene.node_not_found` or `cook.error` |
| `INTERNAL_ERROR -32603` from the stall gate | `retryable` once, then `needs_artist`, because a probe cannot tell an open dialog from a long cook | `houdini.busy` |
| `INTERNAL_ERROR -32603` from the rate limiter or an open breaker | `retryable`, with the remaining time | `server.busy` |
| `INTERNAL_ERROR -32603` from an unhandled exception | `failed` if the handler raised it; `unknown_outcome` if it was raised after the handler returned | `server.internal` |
| `SAFETY_GUARD_REJECTION -32001`, `NODE_NOT_FOUND -32002`, `COOK_ERROR -32003` | defined but never sent; their meanings survive as the codes `policy.safety_guard`, `scene.node_not_found` and `cook.error` | none |
| worker policy refusal (panel) | `refused` | `policy.worker` |
| panel `MCPUnavailable` (not sent) | `retryable` once for a session or a connection; otherwise `unrecoverable` | `bridge.unreachable` |
| panel `MCPOutcomeUnknown` | `unknown_outcome` | `transport.reply_lost` |
| stdio connection refused, after its own retries | `unrecoverable` after a 2 s window | `houdini.not_reachable` |
| stdio send failed before any byte left (told apart since M0) | `retryable` | `transport.not_sent` |
| stdio connection lost after the send | `unknown_outcome` for a mutation; `retryable` for a read-only tool | `transport.reply_lost` |
| timeout | `unknown_outcome` for a mutation; `retryable` for a read-only tool | `transport.timeout` |
| WebSocket rate limit or breaker (`retry_after` in `data`) | `retryable`, with that wait | `server.busy` |
| farm `submission_uncertain` (`farm/service.py:254`) | `unknown_outcome`; reconcile by `request_id`, never resubmit | `farm.submission_uncertain` |
| *new:* a guarded command inside `synapse_batch` | `refused` | `policy.batch_guarded` |
| *new:* cache guard over budget, or size unknown | `needs_artist` | `cache.over_budget`, `cache.unknown_size` |
| *new:* cache guard: the disk cannot hold it | `refused` (approval cannot add disk) | `cache.insufficient_disk` |

## 3. The preflight (contract)

A preflight is a cheap, read-only check that runs before work that changes the scene.

**Where it lives (v1.1, proposed as R-5).** Preflight is the readiness section of `synapse_health`, not a new
tool. Health already answers liveness, `hou` and the protocol (F12), passes the read-only fence, and skips
the WebSocket rate limiter. Preflight adds the checks below and a result.

**When it runs.** The gate runs it for every caller, so an external client does not have to know it exists. It
runs before the first mutating call after `initialize`, and again after any `retryable` or `unrecoverable`
outcome. The panel worker also runs it before the first mutating call of a turn. Anyone can read it on demand
through `synapse_health`.

**The checks.** Each check returns PASS, FAIL or UNKNOWN. By the house rule, UNKNOWN blocks mutations.

1. `bridge.alive`: the server answers a protocol ping within 2 s.
2. `session.valid`: the caller's HTTP session is known to the server, or its WebSocket is authenticated.
3. `houdini.responsive`: the main thread answers within the marshal budget, so no modal dialog is up and no
   foreground cook holds it. This check reuses `server/main_thread.py` and `server/marshal_guard.py`, and calls
   `probe_main_thread` (`server/main_thread.py:406`) with a 250 ms timeout rather than the stall gate's 2 s. A
   probe cannot tell an open dialog from a long cook, so a first FAIL is `retryable` and a second in a row is
   `needs_artist`: "Houdini is not answering. Check for an open dialog or a running cook."
4. `scene.writable`: a scene is loaded, it is not mid-load, and undo is available. Scene memory's hip-file hook
   already tracks a load in progress (`host/memory_lifecycle.py:115-131`).
5. `version.match`: the release version is the same on both sides. The server already has it as
   `synapse.__version__` (F11). The stdio bridge has none today, so it gains one: it reads the `VERSION` file of
   its own checkout at start. A stale stdio process talking to a newer Houdini session is a common source of
   strange failures. The check does not compare the protocol strings, which already disagree (F11) and
   would fail every call. It applies to the stdio bridge only, because the panel runs in the same process
   and an external HTTP client has no SYNAPSE version.
6. `mode`: whether read-only mode is on. This is reported, not a failure.
7. `resources`: free disk on the volumes holding `$HIP` and the cache root, and available RAM. These are
   measured evidence for the cache guard. When a measurement is missing it stays unknown, and never becomes
   an assumed figure; the 64 GB assumption in `panel/render_preflight.py:615` is not reused.
8. `scene.same` (v1.1, proposed as R-7): the scene the caller is about to change is the one it last saw. The
   server keeps a scene generation: the boot token (F9) plus a counter that the existing hip-file hook
   advances on every load and clear. The server records the generation it last reported to each session, and
   every result carries it in `_meta`. A client that knows it, such as the panel or the stdio bridge after a
   reconnect, can send it back as `expect_scene`, and a match passes. A change from a session that has not
   seen the current generation is refused once (`scene.changed`), and the refusal is the "you are here": it
   names the open file and what changed, a restart, a load or a new file. The next call proceeds. Any earlier
   result in the session counts as seeing it, so an agent that reads before it writes, as `initialize` already
   instructs, never meets this refusal. It does not stop a careless agent. It makes sure the agent was told.

**The result** is `ready`, `degraded` (reads only) or `blocked`, together with the outcome of the check that
failed. An agent must not call a mutating tool after a `blocked` result. The panel shows the failing check and
its fix in one line.

**The cost.** When Houdini is ready, at most 50 ms of wall time and at most one main-thread hop of 5 ms. A busy
main thread answers UNKNOWN at the probe's 250 ms timeout, which blocks mutations. The result is cached for
10 s within a turn, and any `retryable` or `unrecoverable` outcome clears it.

**As built in M2 (v1.3).** `core/preflight.py` holds checks 1 to 7 and stays pure; `server/preflight_gate.py` gives
it one hop onto the main thread (`run_on_main` with a 250 ms budget, and `record_stall` and `record_wait` off, so a
miss never trips the stall detector). The gate checks the calls read-only mode refuses, except the farm controls, which
pass it as they pass the stall gates (`90246aea`, v1.4). It checks before a session's first change and again after a `retryable` or `unrecoverable` outcome, where the session is the MCP session or the
WebSocket connection. Only a ready answer is cached for 10 s; a failing check is always probed again. Checks 1 and 2
pass by construction inside the server, which answered on a live session. Check 4 reads
`hou.hipFile.isLoadingHipFile()` and `hou.undos.areEnabled()` (both verified in hython 22.0.400); undo off is
`unrecoverable` (`scene.undo_off`, fixed with `undoctrl on`). Check 5 compares `synapse.__version__`, which the
stdio bridge stamps on every command as `synapse_version`, and its fix names the side on the older release. Checks 6
and 7 are reported by `synapse_health` and never block; check 7 measures `$HIP` and `$HIP/cache` and stays off the
gate path. The result is `degraded` for undo off, a version mismatch or read-only mode, and `blocked` when the main
thread does not answer or a scene is loading. The panel worker's own run at the start of a turn is not built; the
session gate covers the panel.

## 4. The cache guard (contract)

**Scope (named in v1.1).** The guard covers calls, from any caller, that cook frames or write them. The list is
one named set, `GUARDED_TOOLS` in `cache_policy/guard.py`, and a registry walk test fails when a tool is left
unclassified. From the 137 tools at `0e67a740`:

- Cook: `tops_cook_node` (unless `generate_only`), `tops_batch_cook`, `tops_cook_and_validate`,
  `tops_resume_cook`, `houdini_wedge` and `cops_batch_cook`.
- Render: `tops_render_sequence`, `tops_multi_shot`, `synapse_render_sequence`, `synapse_safe_render`,
  `synapse_render_progressively`, `houdini_render`, which renders one frame, and
  `houdini_shot_render_ready`, which runs `safe_render` inside it unless `skip_render` is set.
- Farm: `synapse_farm_prepare`. The guard runs there, where the range and outputs are known, and an approval
  binds to the prepared digest that `synapse_farm_submit` already requires.
- `synapse_autonomous_render` plans its frame range inside the call, so the gate cannot see it before
  dispatch. It is either guarded at its own execute step, or it answers `needs_artist` until it is given a
  range. M3 picks one.
- Not covered, and listed in code with the reason, so the walk test sees them as placed:
  `tops_generate_items`, which does not cook; `cops_bake_textures`, a scaffold that writes nothing by its own
  description; `cops_temporal_analysis`, which cooks every frame of its range in memory but writes nothing
  (parked in section 11); `synapse_insert_cache`, which inserts a node; `synapse_solaris_shotsetup_karma_xpu`,
  which writes `.usd` layers rather than frames and is already gated as a disk writer (F4);
  `houdini_capture_viewport`, one image; the stop controls; and `houdini_execute_python` and
  `houdini_execute_vex`, which cannot be estimated. The standard worker already refuses those two, and external
  handlers run Python and VEX under their own rules (`docs/architecture/overview.md:111`). Every other registry
  tool is listed as not covered too, so a new tool fails the walk test until someone places it.
- Inside `synapse_batch`, a guarded command is `refused` (`policy.batch_guarded`), the way the batch already
  refuses farm commands (F10).

**The steps, all before dispatch:**

1. **Find the write.** For a TOP cook, the output paths of its File Cache and ROP nodes. For a render, the
   ROP's output path and frame range. For a bake, the node's file path and range. A target that cannot be
   found is `unknown`.
2. **Estimate.** Use the cache blueprint's estimation ladder (its 11.1): a matching cache manifest or files
   already on disk from the same signature, else an approved sample, else unknown. Take the HIGH estimate
   times the number of frames. A simulation is a stateful range (cache blueprint 11.2). It grows over time, a
   later frame cannot be sampled without cooking every frame before it, and the first frame is not the
   largest (10.3). So a sample of a simulation gives a floor, never a high estimate.
3. **Feasibility.** `required_free = high x safety multiplier + free-disk floor` (cache blueprint 10.3),
   against the measured free space on the target volume.
4. **Budget.** Per-artist settings: bytes per call, and frames that may run without approval. The defaults
   are decision R-1.
5. **Verdict to outcome.**
   - Fits the budget and the disk: `ok`. The estimate goes on the operation receipt.
   - The size is unknown and the range is over the frame threshold: `needs_artist` (`cache.unknown_size`).
     The message offers a measurement, or approval. For independent frames the measurement samples three
     spread frames, the first, the middle and the last. For a simulation it can only report a floor ("at
     least 40 GB"), so approval is still needed.
   - Over the budget, but the disk can hold it: `needs_artist` (`cache.over_budget`), with the numbers.
   - The disk cannot hold it: `refused` (`cache.insufficient_disk`), with the numbers. Approval cannot add
     disk space. A simulation whose floor alone exceeds the free space is refused the same way.

**Approval.** A `needs_artist` outcome carries a one-time `approval_id`. The id is bound to the tool name, a
hash of its arguments, and the frame range; for the farm it binds to the prepared digest. The artist approves
it on a card in the SYNAPSE panel. The caller then repeats the call with that id, and it runs exactly once.
Approval is two calls, never a wait: a blocking approval on the GUI thread would deadlock the panel (F4), so
the guard answers at once and the caller comes back with the id. An external client's own permission prompt
does not count as this approval, because that prompt can be set to always allow. A click in the panel's own
render controls shows the same card with the numbers, so an artist's own large render is confirmed rather
than blocked.

**Relationship with the advisor.** The guard is not the advisor. It reuses the pure estimation and
feasibility code in `cache_policy` (the cache blueprint's law 12 keeps it free of `hou` and Qt) and the same
verdict names. It never inserts a node, never bakes, and never deletes. It only gates.

## 5. Rules the code must keep (the crucible re-checks each one with its own mutation)

1. **One vocabulary.** Every route maps into the same seven outcomes through one module. A walk test visits
   every refusal and raise site in `mcp/server.py`, `server/websocket.py`, `server/hwebserver_adapter.py`,
   `server/handlers.py`, `panel/tool_executor.py` and `mcp_server.py`, and checks each maps to an outcome.
2. **Never retry what may have run.** An automatic retry is allowed only for `retryable`, whose definition
   requires `dispatched = no`. A test drops the connection after a mutation is sent on the stdio path and
   asserts it was sent once. This pins F2 (done in M0, `tests/test_level1_m0.py`).
3. **Constants, not literals.** The panel reads `SESSION_INVALID` from `mcp/protocol.py`. A test fails on any
   JSON-RPC code written as a literal outside `protocol.py`. This pins F1a (done in M0).
4. **The transport's own rules.** An unknown session on `POST /mcp` answers 404, a missing header answers 400,
   and the panel client re-initializes on 404 or `-32004` and retries once. This pins F1b (done in M0).
5. **UNKNOWN blocks.** A preflight check that cannot be observed returns UNKNOWN, and UNKNOWN blocks
   mutations.
6. **No guessed resources.** Missing RAM, disk or throughput evidence stays unknown (cache blueprint law 5).
7. **Stopping is never fenced.** Stop controls pass the preflight, the scene check and the cache guard, as they
   have passed the read-only fence since v5.86.0.
8. **Refusals happen before dispatch.** A refused or `needs_artist` call has `dispatched = no`. Tests prove it
   with a dispatch mock, the way `test_mcp_tools_call_is_refused_before_dispatch` does
   (`tests/test_mcp_read_only_mode.py:77`).
9. **Cheap.** When Houdini is ready, preflight stays under 50 ms, with at most 5 ms on the main thread. A busy
   main thread answers UNKNOWN at the 250 ms probe, and UNKNOWN blocks by rule 5. A guard estimate from
   last-known evidence stays under 20 ms. Any measurement is an explicit, separate call.
10. **Plain words.** Every outcome message is one sentence that names the next action. Codes are for
    software.
11. **Everything on the receipt.** The outcome, the preflight result and the guard's estimate go on the
    operation receipt. That prepares the audit trail (item 08).
12. **A changed scene is announced before it is changed (v1.1).** A change from a session that has not seen
    the current scene generation is refused once, with the open file named. Two tests: restart the fake host
    between two calls, and open another file between two calls. Both times the change is not dispatched, and
    the refusal names the file. This pins F9.
13. **The flag matches the outcome (v1.1).** Every outcome except `ok` sets `isError: true`, on both routes. A
    test drives each outcome through the stdio bridge and through `/mcp`, and checks the flag and the first
    text line. This pins F8.
14. **The scope is walked, batches included (v1.1).** Every registry tool is classified as guarded or not,
    and a new tool fails the test until it is. Each guarded tool is also sent inside `synapse_batch` and must
    be refused before anything cooks. This pins F7 and F10.

## 6. Where it lives

    python/synapse/core/outcomes.py         the seven outcomes, codes and messages; pure
    python/synapse/core/preflight.py        the checks, the result and its 10 s cache; hou behind a seam;
                                            reported through synapse_health (R-5)
    python/synapse/server/scene_generation.py
                                            the boot token (server/session_store.py) plus the counter the
                                            hip-file hook advances; check 8
    python/synapse/cache_policy/guard.py    pure: GUARDED_TOOLS; a call and its evidence in, a verdict out
    python/synapse/server/cache_guard.py    the hou side: write targets, ranges, sizes on disk, free space
    mcp/server.py, server/websocket.py,
    server/hwebserver_adapter.py            the gate: preflight, scene check and guard before dispatch, beside
                                            the read-only fence; 404 and 400 on POST; isError results
    server/handlers.py                      the batch refuses guarded commands, beside its farm refusal
    mcp/resend_policy.py                    M0: what the stdio bridge may send again
    panel/tool_executor.py                  M0: F1a, re-initialize and retry once; then reads the flag and outcome
    mcp_server.py                           M0: F2; then F3, CallToolResult with isError, expect_scene
    panel                                   the outcome line and the approval card
    tests: test_level1_m0.py (landed), test_outcomes_*.py, test_preflight.py, test_cache_guard.py,
           test_outcome_flag_both_routes.py, test_scene_changed.py, test_guard_scope_walk.py

## 7. Miles

    M0  shipped in v5.87.0 (cff77508): F1a (session code), F1b (400 and 404 on POST), F2 (no re-send after
        send); tests/test_level1_m0.py, 14 tests, six mutants caught
    M0+ (v1.1) F8's flag on each error return in the stdio bridge, M0's own "it may have run" message
        included. Shipped in v5.88.0 with M1b (3496737c): every stdio error path returns CallToolResult isError
    M1  outcomes module; every existing error on every route mapped; outcomes as isError results with the
        outcome line (R-6); the panel reads the flag and shows outcome + next
        Shipped in v5.87.0 as built on v1.0's wire (429cfec6): outcomes in JSON-RPC error data and in
        WebSocket data, the next step in the stdio and panel messages, -32006 for the limiter, the breaker
        and the stall gate; tests/test_level1_m1.py, 20 tests, seven mutants caught.
    M1b (R-6) shipped in v5.88.0 (3496737c): a failed tool call is a result flagged isError on /mcp and stdio,
        first line "<outcome>: <message> Next: <next>", the object in _meta["synapse/outcome"]; JSON-RPC
        errors only for protocol failures; -32006 and -32007 withdrawn; the panel raises the line and
        never re-sends. tests/test_level1_r6.py, 34 tests, fourteen mutants caught
    M2  preflight checks 1-7 inside synapse_health (R-5) and the gate on every route; the "no mutation
        after blocked" rule. Shipped in v5.88.0 (86faa156, and 90246aea for the farm controls):
        tests/test_level1_m2.py, 40 tests, twenty-four mutants caught.
        Check 8, the scene generation and the "announce a changed scene" rule move to M2b (R-7)
    M2b the scene check (R-7): scene generation, expect_scene, refuse a change once with the open file named
    M3  cache guard: the named scope and its walk test, the batch refusal, last-known estimate, disk
        feasibility, budget, needs_artist, approval id, panel card
    M4  measure first: three spread frames for independent ranges; a floor for simulations, which still asks
    M5  live gates in Houdini

M0 shipped in v5.87.0. M0+, M1b and M2 shipped in v5.88.0, whose notes say that -32006 and -32007 were
withdrawn one release after they shipped.

## 8. Gates (computer use by the seat; every leg marks these UNKNOWN)

    G1  restart Houdini's server with the panel open: the next panel call recovers with no panel restart
    G2  drop the WebSocket after Claude Code sends a mutation: it ran once; the client sees unknown_outcome
    G3  Houdini closed, Claude Code on the stdio bridge: every call comes back flagged as an error within
        2 s, with one unrecoverable line and its fix. Over HTTP no SYNAPSE is left to answer, so record what
        Claude Code shows. Whether the agent then stops is its own behavior: record it, don't promise it
    G4  a cook over the budget returns needs_artist; approving it in the panel lets exactly that call run once
    G5  a volume without room: refused with the numbers, and no bytes written
    G6  preflight on a 200-node scene: under 50 ms, main thread under 5 ms, measured and written down
    G7  Cancel cook and Emergency halt work while the preflight says blocked
    G8  Claude Code over HTTP, Houdini restarted: its next call gets 404; record whether it re-initializes by
        itself; its first change after that is refused once, naming the open file
    G9  a render sent inside synapse_batch is refused, and nothing cooks

**Live results, 2026-09-29 (Houdini 22.0.400 on the v5.87.0 code, computer use).**

    G1      PARTIAL  the recovery path passed: the panel's client, given a session id the server never
                     issued, got HTTP 404, started a new session, and its call answered. The server restart
                     itself was not run.
    also    PASS     /mcp: no session header gets 400 and an unknown session 404, each with its outcome and
                     next step; a notification gets 202. SYNAPSE_MCP_READ_ONLY refused a change on /mcp
                     (-32005) and through the stdio bridge's own transport, and the stop control passed on
                     both routes (BP12 item 25).
    G2-G9   not run  they need M2 to M4, a scripted connection drop, or a closed Houdini.

**v5.88.0, 2026-09-30.** M1b and M2 have not been checked live: the Houdini session still runs v5.87.0's code. The
Houdini calls the readiness check relies on were confirmed in hython 22.0.400, and the farm and readiness tests
passed there (80 passed, 1 skipped). A scripted check of the readiness refusals, the flagged results and the
version comparison waits for the restart.

## 9. Decisions for Joe

R-1 to R-4 are decided: Joe's word to implement the blueprint was taken as a yes to all four
(`claude/BP11_CTO_PLAN.md`, section 34). R-5 and R-6 are decided: Joe's "Continue" after the v5.87.0 report was
taken as a yes to both, with R-7 later as its own milestone (v1.3). R-7 is still proposed.

- **R-1. The budget.** 25 GB per call, and 10 frames of unknown size without approval.
- **R-2. On by default.** The guard is on by default, with `SYNAPSE_CACHE_GUARD=0` to turn it off. It exists
  to stop the one call that can fill a disk, so off by default would miss the point.
- **R-3. Where approval happens.** A card in the SYNAPSE panel, identified by an approval id. An external
  client's own permission prompt does not count.
- **R-4. Retry policy.** One automatic retry, for `retryable` only.
- **R-5. Where preflight lives (v1.1).** Inside `synapse_health`, as its readiness section, rather than as a
  new tool. Health already reports liveness, `hou` and a version, and it skips the rate limiter. It also
  passes the read-only fence, which `synapse_doctor` does not (checked by calling `refusal_for_tool` with
  read-only mode on). The count of 137 tools is stated in the README and the v5.86.0 notes.
- **R-6. Tool failures on `/mcp` (v1.1).** Move them from `-32603` protocol errors to `isError` results, as
  MCP specifies, and change the panel's client in the same commit, because today it treats a JSON-RPC error as
  the failure signal. `-32005` follows at the next contract change. The alternative is to keep `-32603` and put
  the outcome line in its message. That reaches the model, but leaves the spec's channel unused. Since v5.87.0,
  M1 is published on v1.0's wire, so adopting R-6 also withdraws the published `-32006` and `-32007`.
- **R-7. The scene check (v1.1).** Check 8 is on by default. It costs one refusal, naming the open file, the
  first time a session changes a scene it has not read, and after a restart or another file is opened.

## 10. Done means

- F1a, F1b and F2 are each pinned by a test that fails when the fix is reverted (done in M0), and so are F8,
  F9 and F10.
- The walk test maps every error on every route to exactly one outcome.
- G1 to G9 pass live, or are marked UNKNOWN with the reason.
- The full suite is green, and the except ratchet does not rise.

## 11. What Level 1 is not

It is not transactions or rollback, and it is not read-back verification; both are Level 2. It is not farm
submission, which is Level 4. It does not decide what to cache; the advisor still does that. It makes
failures say what they are, and it stops the one call that can fill a disk.

Parked for Level 2 (v1.1): reads can cook. Inspecting a node downstream of a simulation at a frame that is
not cached cooks the sim up to that frame, in memory, and `cops_temporal_analysis` force-cooks every frame of
its range (`server/handlers_cops.py:1962-1965`). The guard does not see either, because neither writes. That
risk is RAM and time rather than disk, and it belongs with frame-bounded reads.
