# Synapse Latency Plan

## Current Architecture (v4.2.1)

```
Claude Desktop ──[stdio/JSON-RPC]──> mcp_server.py ──[async WebSocket]──> SynapseServer ──[sync handler]──> hou module
                                    (Python process)                    (daemon thread)                    (main thread*)

* Most hou.* calls are thread-safe in Houdini 21, but some (editableStage, cook) require main thread
```

## End-to-End Request Timeline (measured)

```
                                    create_node (typical)
────────────────────────────────────────────────────────────
MCP: JSON-RPC parse + dispatch         ~1ms
MCP: _get_connection()                 ~0ms (cached) / ~50-5200ms (first connect*)
MCP: json.dumps(command)               <1ms
MCP: ws.send + ws.recv                 ~2-10ms (localhost)
SRV: SynapseCommand.from_json          <1ms
SRV: resilience checks                 ~0.25ms (3 lock acquisitions)
SRV: handler lookup                    <0.1ms
HDL: hou.node(parent)                  ~1-5ms
HDL: createNode()                      ~5-20ms
HDL: moveToGoodPosition()              ~2-10ms
HDL: bridge.log_action() → JSONL       ~5-15ms ← SYNC I/O ON EVERY COMMAND
SRV: json.dumps(response)              <1ms
MCP: json.loads(response)              <1ms
────────────────────────────────────────────────────────────
TOTAL (subsequent):                    ~20-65ms
TOTAL (first connect):                 ~70-5250ms

* First connect = TCP handshake + consume connection_context (loads memory, queries hou.*)
```

## Identified Bottlenecks (ranked by impact)

### P0: Critical

| # | Bottleneck | Where | Impact | Fix |
|---|-----------|-------|--------|-----|
| 1 | **Connection context on every connect** | websocket.py:253-262 + mcp_server.py:68-81 | +50-200ms first connect, +5s timeout risk | Skip for MCP (stateless), cache for panels |
| 2 | **Circuit breaker never recovers from watchdog freeze** | websocket.py:390-392 | Blocks ALL commands until server restart | **FIXED (Fix 14)** — `_on_recover` now calls `cb.reset()` |
| 3 | **Ping/health blocked by resilience** | websocket.py:318-353 | Health probes fail when circuit open | **FIXED (Fix 15)** — bypass for ping, get_health |

### P1: High

| # | Bottleneck | Where | Impact | Fix |
|---|-----------|-------|--------|-----|
| 4 | **Sync memory logging on every command** | handlers.py:118-124 | +5-15ms per command (JSONL append) | Async queue + batch flush |
| 5 | **Session creation on every connection** | websocket.py:237-242 | +5-20ms per connect | Lazy-create on first mutation |
| 6 | **Full memory scan on search/recall** | tracker.py:366-508 | +10-100ms per search | In-memory index or SQLite |

### P2: Medium

| # | Bottleneck | Where | Impact | Fix |
|---|-----------|-------|--------|-----|
| 7 | **MCP reconnect on any error** | mcp_server.py:115-119 | Drops connection, re-pays context cost | Smarter retry (don't clear on transient) |
| 8 | **Redundant bridge.log_action in handler** | handlers.py:119 + per-handler logs | Double logging (handle + specific) | Remove generic log, keep specific |
| 9 | **No connection pooling in MCP** | mcp_server.py:46-92 | Single connection, serial requests | Connection pool (but MCP is serial anyway) |

### P3: Low (nice to have)

| # | Bottleneck | Where | Impact | Fix |
|---|-----------|-------|--------|-----|
| 10 | **Unused queue classes** | queue.py | Cognitive overhead, not perf | Document as "future async" or remove |
| 11 | **Thread-per-connection model** | websocket sync server | Fine for 1-3 clients | Only matters at scale |

---

## Phase 1: Quick Wins (1-2 hours)

### 1A. Skip connection_context for MCP clients
The MCP server is stateless — it doesn't use the context. Detect via a protocol flag or skip the recv.

**Option A (server-side):** Add `X-Synapse-Client: mcp` header or initial message
**Option B (client-side):** Already done — mcp_server.py:68-81 consumes and discards it
**Verdict:** Server-side is better. Don't generate what you'll discard.

```python
# websocket.py: _handle_client — add client_type detection
# If first message is {"type": "init", "client_type": "mcp"}, skip context
# Otherwise send context (panel clients use it)
```

### 1B. Lazy session creation
Don't create session until first non-ping command. Ping/health are stateless.

### 1C. Skip memory logging for read-only operations
`get_parm`, `get_scene_info`, `get_selection`, `get_stage_info`, `get_usd_attribute` — these don't modify state. No need to log them.

**Estimated savings:** 50-200ms on connect, 5-15ms per read command.

---

## Phase 2: Async Memory (half day)

### 2A. Async memory write queue
Replace synchronous `self._synapse.add(...)` calls with a queue + batch flush:

```python
class AsyncMemoryWriter:
    def __init__(self, synapse: SynapseMemory, flush_interval: float = 5.0):
        self._queue = queue.Queue()
        self._thread = threading.Thread(target=self._flush_loop, daemon=True)

    def enqueue(self, content, memory_type, tags, **kwargs):
        self._queue.put((content, memory_type, tags, kwargs))

    def _flush_loop(self):
        while True:
            batch = []
            # Drain queue
            try:
                while True:
                    batch.append(self._queue.get_nowait())
            except queue.Empty:
                pass
            # Batch write
            for item in batch:
                self._synapse.add(*item[:3], **item[3])
            time.sleep(self._flush_interval)
```

### 2B. Memory index for search
Replace full JSONL scan with an in-memory inverted index built on load.

**Estimated savings:** 5-15ms per write command, 10-100ms per search.

---

## Phase 3: Architecture — hwebserver Migration (1-2 days)

### The Opportunity

Houdini 21 ships `hwebserver` — a C++ multi-threaded HTTP/WebSocket server built into the process. Key properties:

- **Native C++ server** — no Python overhead for connection handling
- **Multi-threaded** with global lock + GIL acquisition per handler
- **Non-blocking in graphical session** — `hwebserver.run(port)` returns immediately
- **ONE global server** per Houdini instance
- **Handlers run with hou access** — no thread-dispatch needed for most operations
- **`hwebserver.WebSocket`** class for native WebSocket support
- **`hwebserver.apiFunction`** decorator for JSON API endpoints

### What It Eliminates

| Current Layer | With hwebserver | Savings |
|--------------|----------------|---------|
| `websockets` Python package | Native C++ | ~2-5ms per message |
| Daemon thread for server | Built-in non-blocking | Thread overhead |
| `haio.py` concerns | No asyncio at all | Complexity |
| Watchdog | Unnecessary (server IS Houdini) | Entire subsystem |
| Circuit breaker freeze detection | Server can't freeze separately | Simplification |
| Thread pool dispatching | Handlers run with GIL | Thread sync overhead |
| Port binding/retry logic | Single `hwebserver.run(port)` | Startup complexity |

### What It Preserves

- WebSocket wire protocol (SynapseCommand/Response JSON)
- All handler logic (unchanged)
- MCP server (still connects via WebSocket)
- Memory system (unchanged)
- Session tracking (unchanged)
- Rate limiter (still useful)
- Backpressure (still useful)

### Migration Strategy

**Step 1: Dual-stack** — Add `hwebserver_adapter.py` alongside existing `websocket.py`. Both implement same interface. Feature flag: `SYNAPSE_SERVER_BACKEND=hwebserver|websockets`.

**Step 2: Handler adapter** — `hwebserver.apiFunction` handlers call into existing `SynapseHandler.handle()`. WebSocket class wraps `hwebserver.WebSocket`.

**Step 3: Deprecate** — Once stable, remove `websocket.py`, `websockets` dependency, watchdog freeze detection.

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| hwebserver is ONE per Houdini | Register Synapse endpoints under `/synapse/` prefix |
| Global lock per handler | Keep handlers fast, offload heavy work |
| Only available inside Houdini | Keep `websockets` fallback for testing without Houdini |
| Undocumented edge cases | RAG system at G:\HOUDINI21_RAG_SYSTEM has NO hwebserver usage — we'd be pioneers |

### Integration Test Results (2026-02-08)

**FINDING: hwebserver has a ~2s main-event-loop dispatch floor.**

All handlers route through Houdini's main event loop, adding ~2s per message regardless
of handler complexity. The websockets daemon-thread server avoids this for non-`hou.*` ops.

| Command | websockets | hwebserver | Winner |
|---------|-----------|-----------|--------|
| ping (warm) | **0.2ms** | 2070ms | websockets (10,000x) |
| get_scene_info | **2.0ms** | 0.66ms | hwebserver (3x) |
| context (memory) | **0.9ms** | 2059ms | websockets (2,300x) |
| create_node | 2531ms | **2082ms** | hwebserver (1.2x) |
| delete_node | 4179ms | **4.6ms** | hwebserver (908x) |

**Conclusion:** For the MCP workload (many reads/pings + occasional mutations),
websockets is the better default. hwebserver only wins for `hou.*` mutations that
happen to hit the right event loop tick.

**Decision:** Keep websockets as primary transport. hwebserver adapter preserved
for future use if SideFX improves dispatch latency or for mutation-heavy workflows.
Phase 3 migration is **DEFERRED** — not abandoned.

### RAG System Cross-Reference

Searched `G:\HOUDINI21_RAG_SYSTEM` — **zero references to hwebserver**. The old system uses raw `socket.socket` HTTP/1.1 with connection pooling (3 pre-warmed sockets, keep-alive). This means we have no existing patterns to draw from — hwebserver migration would be greenfield.

---

## Phase 4: MCP Optimization (optional)

### 4A. Skip connection_context consumption in MCP
If server implements Phase 1A (no context for MCP), the MCP client no longer needs the recv+discard.

### 4B. Connection health ping
Replace `await _ws_connection.ping()` (WebSocket protocol ping) with application-level heartbeat tracking.

---

## Priority Matrix

```
            HIGH IMPACT                    LOW IMPACT
EASY   ┌─────────────────────┐    ┌────────────────────────┐
       │ 1A. Skip MCP context │    │ 1C. Skip read logging  │
       │ 1B. Lazy session     │    │ 10. Remove dead queues │
       │ Fix 14 (DONE)        │    │                        │
       │ Fix 15 (DONE)        │    │                        │
       └─────────────────────┘    └────────────────────────┘
HARD   ┌─────────────────────┐    ┌────────────────────────┐
       │ 3. hwebserver        │    │ 6. Memory index        │
       │ 2A. Async memory     │    │ 9. Connection pool     │
       └─────────────────────┘    └────────────────────────┘
```

## Recommended Order

1. ~~**Now**: Fix 14 + 15 — circuit breaker recovery + health bypass~~ **DONE**
2. ~~**Next session**: Phase 1 quick wins — skip MCP context, lazy session, skip read logs~~ **DONE**
3. ~~**When needed**: Phase 2A async memory write queue~~ **DONE** (MemoryStore._write_buffer + _flush_loop)
4. ~~**When needed**: Phase 2B in-memory search index~~ **DONE** (search() now queries _index to narrow candidates)
5. ~~**Next**: Phase 3 hwebserver integration test~~ **TESTED (2026-02-08)** — ~2s event loop floor makes it slower for reads; websockets stays primary. See test results below.

## Metrics to Track

Once implemented, instrument these:
- `request_latency_ms` per command type (P50, P95, P99)
- `connection_setup_ms` (first connect vs reconnect)
- `memory_write_ms` (before/after async queue)
- `circuit_breaker_trips` per hour
- `watchdog_false_positives` per session (should be 0 after hwebserver)
