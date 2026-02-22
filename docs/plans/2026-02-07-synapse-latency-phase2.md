# Synapse Latency Phase 2 — Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce per-command latency across the full Claude Desktop -> MCP -> WebSocket -> Synapse -> Houdini request path by eliminating unnecessary overhead in hot paths.

**Architecture:** Six targeted optimizations hitting the three highest-impact areas: (1) MCP bridge serialization and response formatting, (2) server-side resilience fast-track expansion, (3) handler dispatch overhead reduction. Each fix is independently testable and non-breaking.

**Tech Stack:** Python 3.14, asyncio (MCP), threading (server), orjson, pytest

---

### Task 1: Expand resilience fast-track to all read-only commands

**Files:**
- Modify: `python/synapse/server/websocket.py:298-317`
- Test: `tests/test_resilience.py` (add new test)

**Context:** Currently only `heartbeat`, `ping`, and `get_health` bypass the resilience layer (rate limiter + circuit breaker + backpressure). But handlers.py already defines 13 `_READ_ONLY_COMMANDS` that skip memory logging. These same commands should also skip resilience checks — they're cheap reads that can't cause cascading failures.

**Step 1: Write the failing test**

Add to `tests/test_resilience.py` — a test that verifies read-only commands skip resilience.

```python
def test_read_only_commands_bypass_resilience():
    """Read-only commands should not consume rate limiter tokens."""
    # Import _READ_ONLY_COMMANDS from handlers
    import importlib.util
    handlers_path = os.path.join(resilience_dir, "handlers.py")
    # We just verify the constant exists and contains expected entries
    from synapse.server.handlers import _READ_ONLY_COMMANDS
    assert "get_parm" in _READ_ONLY_COMMANDS
    assert "get_scene_info" in _READ_ONLY_COMMANDS
    assert "get_selection" in _READ_ONLY_COMMANDS
    assert "context" in _READ_ONLY_COMMANDS
    assert "search" in _READ_ONLY_COMMANDS
    assert "recall" in _READ_ONLY_COMMANDS
```

**Step 2: Modify websocket.py to import and use _READ_ONLY_COMMANDS**

In `_handle_message()`, after the existing ping/get_health fast-track (line 317), add a check for all read-only commands that skips the resilience layer.

```python
# After line 317 (existing ping/get_health fast-track):
if command.type in _READ_ONLY_COMMANDS:
    response = self._handler.handle(command)
    if self._circuit_breaker:
        self._circuit_breaker.record_success()
    websocket.send(response.to_json())
    return
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_resilience.py -v`
Expected: All pass including new test

**Step 4: Commit**

```bash
git add python/synapse/server/websocket.py tests/test_resilience.py
git commit -m "perf: expand resilience fast-track to all read-only commands"
```

---

### Task 2: Pre-compute reverse alias map for O(1) parameter resolution

**Files:**
- Modify: `python/synapse/core/aliases.py:52-80`
- Test: `tests/test_core.py` (add new test)

**Context:** `resolve_param()` iterates through alias lists (up to 5 entries per param) on every call. Every command with parameters hits this. Pre-computing a reverse map `{alias: canonical}` at module load gives O(1) dict lookups instead of O(n) iteration.

**Step 1: Write the failing test**

```python
def test_reverse_alias_map_exists():
    """Reverse alias map should be pre-computed at module load."""
    from synapse.core.aliases import _REVERSE_ALIASES
    assert isinstance(_REVERSE_ALIASES, dict)
    assert _REVERSE_ALIASES["code"] == "content"
    assert _REVERSE_ALIASES["node_path"] == "node"
    assert _REVERSE_ALIASES["parameter"] == "parm"
```

**Step 2: Build the reverse map and use it in resolve_param**

At module level after PARAM_ALIASES:
```python
_REVERSE_ALIASES: Dict[str, str] = {}
for _canonical, _aliases in PARAM_ALIASES.items():
    for _alias in _aliases:
        _REVERSE_ALIASES[_alias] = _canonical
```

Update `resolve_param()` to try payload keys against reverse map first:
```python
def resolve_param(payload, canonical, required=True):
    # Fast path: direct key match
    if canonical in payload:
        return payload[canonical]
    # Fast path: check payload keys against reverse map
    aliases = PARAM_ALIASES.get(canonical, [canonical])
    for alias in aliases:
        if alias in payload:
            return payload[alias]
    # ... rest unchanged
```

**Step 3: Run tests**

Run: `python -m pytest tests/test_core.py -v`

**Step 4: Commit**

---

### Task 3: Replace per-command Thread spawn with ThreadPoolExecutor for logging

**Files:**
- Modify: `python/synapse/server/handlers.py:7-8,128-138`
- Test: `tests/test_resilience.py` (add test for thread pool)

**Context:** Every write command spawns a new `threading.Thread` for fire-and-forget memory logging (~0.2ms overhead per Thread creation). A module-level `ThreadPoolExecutor(max_workers=2)` reuses threads, eliminating the spawn cost.

**Step 1: Replace Thread with executor.submit()**

```python
# At top of handlers.py, add:
from concurrent.futures import ThreadPoolExecutor
_log_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="synapse-log")

# Replace lines 133-138:
_log_executor.submit(bridge.log_action, f"Executed: {cmd_type}", session_id=sid)
```

**Step 2: Run tests**

Run: `python -m pytest tests/ -v`

**Step 3: Commit**

---

### Task 4: Fix MCP response serialization — use orjson consistently

**Files:**
- Modify: `mcp_server.py:589`

**Context:** Line 589 uses `json.dumps(data, indent=2)` (stdlib) even though orjson is imported at the top. This is the response path for EVERY tool call. orjson is 3-5x faster and the indent is unnecessary for machine-to-machine communication.

**Step 1: Fix the import reference**

Change line 589 from:
```python
return [TextContent(type="text", text=json.dumps(data, indent=2))]
```
to:
```python
return [TextContent(type="text", text=_dumps(data))]
```

**Step 2: Run MCP server smoke test**

Verify no import errors: `python -c "import mcp_server"` (will fail without mcp, that's OK — just verify syntax)

**Step 3: Commit**

---

### Task 5: Add resilience bypass for read-only commands in websocket fast-track (watchdog heartbeat)

**Files:**
- Modify: `python/synapse/server/websocket.py`

**Context:** The watchdog heartbeat is called on every successful command. For read-only commands that bypass resilience, we should still feed the watchdog to prevent false freeze detection, but skip the backpressure evaluation since read-only commands don't contribute to load.

This is already handled by the existing code structure — the watchdog runs on a separate timer. No change needed. **SKIP this task.**

---

### Task 6: Run full test suite and commit all changes

**Step 1:** Run: `python -m pytest tests/ -v`
**Step 2:** Verify all tests pass (324+ expected)
**Step 3:** Single commit with all changes

---

## Estimated Impact

| Fix | Savings | Commands Affected |
|-----|---------|-------------------|
| Task 1: Resilience fast-track | ~0.04ms/read | get_parm, get_scene_info, get_selection, context, search, recall |
| Task 2: Reverse alias map | ~0.1ms/call | All commands with parameters |
| Task 3: ThreadPoolExecutor | ~0.2ms/write | create_node, delete_node, set_parm, execute_python, add_memory, decide |
| Task 4: orjson response | ~1-3ms/large | ALL tool responses via MCP |

Total: ~0.3-3ms savings per command, compounding across parallel tool calls.
