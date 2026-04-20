# Crucible Protocol — Spike 2 Phase 2

**Purpose:** prove the embedded SYNAPSE daemon survives hostile
co-tenancy — the artist and the agent operating on the same
Houdini scene at the same time.

**What this is:** a manual runbook. The "Hit ESC" step is literally a
keyboard press. The agent's infrastructure (daemon, dispatcher,
agent loop, tool registry) is fully automated and tested in
`tests/test_agent_loop.py` and `tests/test_host_layer.py` — what
this runbook covers is the **human-in-the-loop observation** the
automated tests cannot reach.

**Commit context:** carried alongside the Phase 2 scaffolding
commit. Runs AGAINST commit `HEAD`.

---

## Pass rubric (from `SPRINT3_EXECUTE.md`)

| Tier | Behaviour |
|---|---|
| **Baseline** | No segfault. Houdini stays alive. |
| **Full** | Agent catches `hou.ObjectWasDeleted`, the Dispatcher wraps it as `AgentToolError`, the agent_loop serializes it into the next turn's `tool_result`, and the LLM rewrites its approach visibly in the conversation. |
| **Partial** | Catches the exception but the conversation doesn't show a clear recovery pivot — needs a Spike 2.5 iteration on error-message structuring. |
| **FAIL** | Silent retry on a stale pointer (same dead path dispatched twice in a row), or segfault. |

---

## Preconditions

1. Houdini 21.0.631 graphical session running.
2. The SYNAPSE package is importable from Houdini's Python —
   `python/synapse/` is on the Houdini `$PYTHONPATH` (it is, via
   the package config referenced in `PYTHONPATH` env in Spike 0
   diagnostic).
3. `hou.secure.password('synapse_anthropic')` set OR
   `ANTHROPIC_API_KEY` in env. Spike 0 / daemon boot resolves
   either.
4. `anthropic` package installed in hython's site-packages. Spike 0
   established this via the sys.path-stripping launcher.
5. `pyproject.toml` Windows Credential Manager: `hou.secure.
   setPassword('synapse_anthropic', 'sk-ant-...')` was called at
   least once from Houdini's Python shell (or env var set).

---

## Test scene

Use `tests/fixtures/inspector_week1_flat.hip` — it has 8 known
LOP nodes under `/stage` (matching the Sprint 2 Week 1 golden
fixture). The scene is small enough that node paths are trivially
referenceable in a prompt.

---

## Setup (run once in Houdini Python shell)

```python
import sys
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")

from synapse.host.daemon import SynapseDaemon

daemon = SynapseDaemon()  # boot_gate=True by default; runs because UI is up
daemon.start()
print("daemon running:", daemon.is_running)
```

Expected: `daemon running: True`. If boot fails:

- `DaemonBootError: hou.isUIAvailable() returned False` → you're in
  hython headless, not graphical Houdini. Don't force `boot_gate=
  False` — the whole point of the test is GUI co-tenancy.
- `DaemonBootError: No Anthropic API key` → fix precondition #3.
- `DaemonBootError: anthropic SDK is not installed` → fix
  precondition #4.

Then load the fixture scene:

```python
import hou
hou.hipFile.clear(suppress_save_prompt=True)
hou.hipFile.load(r"C:\Users\User\SYNAPSE\tests\fixtures\inspector_week1_flat.hip",
                 suppress_save_prompt=True)
```

---

## Protocol

### Turn 1 — establish baseline

Issue this prompt via `daemon.submit_turn`:

```python
result = daemon.submit_turn(
    user_prompt=(
        "Inspect /stage using synapse_inspect_stage. List every node "
        "by name and hou_path. Pay particular attention to the node "
        "whose hou_path is '/stage/xf' — report its usd_prim_paths."
    ),
    system=(
        "You are a SYNAPSE agent inside Houdini. You have one tool: "
        "synapse_inspect_stage. Call it to answer the user's question."
    ),
    wait_timeout=60.0,
)
print(result.status)
print(result.iterations)
print(result.tool_calls_made)
```

**Expected:**
- `status == "complete"`.
- `iterations >= 2` (one for tool_use, one for final text).
- `tool_calls_made == 1`.
- Final assistant message includes `/stage/xf` with `usd_prim_paths`
  containing `/geo`.

If the baseline turn fails, stop and debug before running the
hostile turn — the Crucible setup itself isn't working.

### Turn 2 — the Crucible

**Step-by-step. Timing matters.**

1. In the Houdini Python shell, type (but do NOT execute yet) this
   call:
   ```python
   result = daemon.submit_turn(
       user_prompt=(
           "Re-inspect /stage. Look again at /stage/xf specifically — "
           "what are its inputs and outputs? Follow up with a second "
           "call to synapse_inspect_stage to confirm."
       ),
       system="You are a SYNAPSE agent inside Houdini.",
       wait_timeout=90.0,
   )
   ```

2. Have the Houdini Network Editor open on `/stage`. Have
   `/stage/xf` visible.

3. **Press Enter to execute.** The `submit_turn` call blocks; the
   agent loop is now running on the daemon thread.

4. Watch for the first "yielding to network I/O" moment — the
   daemon thread is sitting on `client.messages.create()` for the
   first response. This is the 2-5 second window after you hit
   Enter.

5. **During that window**, in the Houdini UI:
   - **Right-click `/stage/xf` in the Network Editor → Delete.**
   - **Drag the playbar scrubber left-to-right across a few frames**
     (forces geometry cooks downstream).

6. Wait for the call to return.

7. **Observe `result`:**
   ```python
   print(result.status)
   print(f"iterations: {result.iterations}")
   print(f"tool_calls_made: {result.tool_calls_made}")
   print(f"tool_errors: {len(result.tool_errors)}")
   for err in result.tool_errors:
       print(f"  - {err.error_type}: {err.error_message[:120]}")
   # Inspect the conversation
   import json
   for msg in result.messages[-3:]:
       print(json.dumps(msg, indent=2)[:500])
   ```

### Optional — the ESC path

Start a third turn and trigger `daemon.cancel()` while the agent
is yielding. The result should come back with
`status == "cancelled"` and `tool_calls_made` reflecting only the
tools that dispatched before the cancel fired.

```python
import threading, time
def _esc():
    time.sleep(3)
    daemon.cancel()
threading.Thread(target=_esc, daemon=True).start()

result = daemon.submit_turn(
    user_prompt="Call synapse_inspect_stage twice. Take your time.",
    wait_timeout=30.0,
)
print(result.status)  # expected: "cancelled"
```

---

## Decoding the outcome

### Full pass

- `result.status == "complete"`.
- Exactly one `tool_errors` entry whose `error_type` is
  `ObjectWasDeleted` (or `AttributeError`, `ReferenceError` — the
  exact exception depends on Houdini's internals).
- The final assistant message acknowledges the node is gone and
  pivots — either "/stage/xf appears to have been deleted"
  verbatim, or a rewritten approach that doesn't try to touch
  `/stage/xf` again.
- **Crucially:** `result.messages` shows the `AgentToolError`
  envelope serialized into the `tool_result.content` of the
  follow-up turn. Search for `"agent_tool_error": true` in the
  message body.

### Partial pass

- `status == "complete"` but the final assistant message is vague
  or blames the user ("I couldn't find /stage/xf, please check
  your input"). The agent saw the error but didn't articulate
  recovery. Raise as a Spike 2.5 need — the error envelope needs
  additional context so the LLM can reason about it.

### FAIL

- Segfault: Houdini died. File the crash dump path + the exact
  sequence of clicks. Access-violation cross-reference: check
  whether the Windows Event Log / crash dump mentions
  `_pytest\capture.py` or similar stacks to the one observed
  during the deferred `test_inspect_live.py` run (Spike 2.1
  observation). If yes → we have a pattern.
- Silent retry: same dead path dispatched twice in the same
  `tool_calls_made` count without intervening re-inspect.
  `test_no_silent_retry_on_dead_node` asserts this at unit level
  but if the live path violates it, the Dispatcher or agent_loop
  regressed.

---

## Cleanup

```python
daemon.stop()
print("daemon stopped:", not daemon.is_running)
```

---

## What this covers that the unit tests don't

The unit tests verify the agent loop's **logical** handling of a
dead-node error — with a synthesized `_FakeObjectWasDeleted`
exception in a mocked Anthropic conversation. What they
**cannot** cover:

1. The real `hou.ObjectWasDeleted` exception type emitted from
   real Houdini C++ internals when a LOP node is destroyed
   mid-cook.
2. Qt event loop interactions between the daemon thread's
   hdefereval call and the UI's scrub / delete events.
3. Access violations in the Python / C++ boundary — specifically
   the `_pytest\capture.py`-style AV observed during the Spike
   2.1 deferred-gate run, which we're now watching for as a
   potential second data point.

The Crucible IS the live test for these. The unit tests constrain
what the agent code does GIVEN correctly-shaped inputs; the
Crucible confirms that Houdini's runtime produces the shape of
inputs we expected when it does something hostile.
