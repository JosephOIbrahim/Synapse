# FORGE Spec — `execute_python` main-thread-block fix

**Status:** ARCHITECT → FORGE handoff. Implementable now. A BUILD (not a search — see `SYNAPSE_SCIENCE_HARNESS.md` §5, hypothesis space collapsed).
**Target:** `synapse.server.handlers._handle_execute_python` (the WS path).
**Eval signal:** `houdini_execute_python` returns instead of hanging when the main thread is occupied; pure-Python (no-`hou`) scripts complete regardless of main-thread state. Bug resolved.

---

## Problem (mechanism, confirmed)

`_handle_execute_python` (`python/synapse/server/handlers.py:~912`) compiles the script, then runs the **entire** body — pure file I/O included — on Houdini's main thread:

```
_handle_execute_python  →  run_on_main(_on_main, timeout=_SLOW_TIMEOUT)   # handlers.py
run_on_main             →  hdefereval.executeDeferred(_on_main)           # main_thread.py:105
                           done.wait(timeout=30.0)                        # _SLOW_TIMEOUT (main_thread.py:20)
```

When the main thread is blocked — a modal dialog, an active cook, or any long main-thread op — `executeDeferred` never fires, `done.wait` times out at 30s, and the call raises a generic "main thread didn't respond." `ping` survives because it never enters `run_on_main`. Three things compound it:

1. **Everything is marshaled**, even scripts that never touch `hou` (e.g. a file write). They inherit the main thread's blockability for zero benefit.
2. **No dialog suppression on this path.** `suppress_modal_dialogs()` (`host/dialog_suppression.py:105`) is composed around the **daemon** executor (`host/daemon.py:160`) but NOT around the WS `run_on_main` path — so a modal that pops *inside* the script can self-deadlock.
3. **`is_main_thread_stalled()`** (`main_thread.py:41`) already exists (2 consecutive timeouts → stalled) but `_handle_execute_python` doesn't consult it to fast-fail or fall back.

(Distinct from Spike 2.4, which is CLOSED — that was the daemon↔main deadlock fixed by `TurnHandle`. This is the WS-handler residual.)

---

## The fix — three parts

### Part 1 — pure-Python scripts skip the main thread
A script that references no `hou` symbol needs neither the main thread nor the undo group. Detect that and dispatch it **directly on the handler thread** (the same property `synapse_write_report` already relies on).

- **Detection:** AST-based, not substring. Parse the compiled source; walk for any `Name`/`Attribute` referencing `hou` or `hdefereval`, and any `Import`/`ImportFrom` of them. Substring `"hou" in code` is wrong (matches comments/strings/`thou`). Provide an explicit override: payload flag `requires_main_thread: bool` (default = inferred). If the AST check is uncertain (e.g. `exec`/`eval`/`__import__` dynamic calls), **fail safe → marshal to main** (treat as `hou`-touching).
- **Dispatch:** if no `hou` → run the compiled code directly on the handler thread (no `run_on_main`, no undo group — a pure-Python script has nothing scene-side to roll back). If `hou` → unchanged path (Part 2/3).

### Part 2 — dialog suppression on the WS path
Wrap the `_on_main` body (the `hou`-touching branch) in `suppress_modal_dialogs()`, matching what the daemon already does (`daemon.py:160`). A stray `hou.ui.*` modal then raises instead of blocking the main thread.

### Part 3 — fast-fail + clearer error
Before marshaling a `hou`-touching script, consult `is_main_thread_stalled()`: if already stalled, return a structured error immediately (don't wait 30s again). On timeout, the error message must name the likely cause: `"main thread blocked (modal dialog or active cook) — the call could not be dispatched within 30s"`, not a generic failure.

---

## Exact targets

| File | Symbol / line | Change |
|---|---|---|
| `python/synapse/server/handlers.py` | `_handle_execute_python` (~912) | AST no-`hou` detection + branch; wrap `hou` branch in `suppress_modal_dialogs`; consult `is_main_thread_stalled`; clearer timeout error |
| `python/synapse/server/main_thread.py` | `run_on_main` (66), `is_main_thread_stalled` (41), `_SLOW_TIMEOUT` (20) | reuse; possibly expose a `requires_main` fast-path helper |
| `python/synapse/host/dialog_suppression.py` | `suppress_modal_dialogs` (105) | reuse (import into the server path) |
| `python/synapse/host/daemon.py` | `:71`, `:160` | precedent to mirror, not edit |

A small AST helper (`_script_touches_hou(compiled_or_src) -> bool`) is the only genuinely new logic; everything else is composition of existing parts.

---

## Tests

**Standalone (no Houdini) — pin the routing decision, the highest-value regression:**
- `_script_touches_hou` truth table: `"open('x','w').write('y')"` → False; `"hou.node('/obj')"` → True; `"import hou"` → True; `"# hou comment"` / `"s='hou'"` → False; `"exec(code)"` / `"__import__('hou')"` → True (fail-safe).
- **Decisive regression (mirrors `test_write_report.py`):** monkeypatch `main_thread.run_on_main` to raise; a no-`hou` script through `_handle_execute_python` still succeeds (proves it bypassed the main thread); a `hou`-touching script DOES call `run_on_main` (so the marshaling path is preserved).
- `requires_main_thread=True` override forces marshaling even for a no-`hou` script.
- Stalled fast-fail: with `is_main_thread_stalled()` patched True, a `hou` script returns the structured "main blocked" error without a 30s wait.

**Houdini-gated (live 21.0.671, manual):**
- A pure-Python write completes while a modal dialog is open on the main thread.
- A `hou`-touching script still runs correctly with undo-group atomicity intact; a `hou.ui` modal inside it raises (suppressed) instead of hanging.

---

## Gates & invariants

- **`execute_python` is CRITICAL-gated** (`OPERATION_GATES["execute_python"] = "critical"`). This fix changes the *dispatch route*, not the gate. The CRITICAL gate must still wrap the call.
- **Do not weaken atomicity for `hou` scripts.** The undo-group + smart-rollback (`_ROLLBACK_ERRORS`) path is untouched for anything that touches `hou`. Only the no-`hou` branch skips it (correctly — nothing scene-side to roll back).
- **Fail safe on detection ambiguity** — uncertain → treat as `hou`-touching → marshal. A false "no-hou" that actually touches `hou` off-main would be a thread-safety bug; the AST check must err toward marshaling.
- **Halt-and-surface**, not silent fallback: a blocked main thread returns a clear structured error.

---

## Risks

- **HIGH-ish: it's the execution path.** A wrong no-`hou` classification that runs `hou` off the main thread is a correctness/thread-safety bug. Mitigation: fail-safe detection + the standalone truth-table test + the "hou script still marshals" regression.
- Live verification needs a Houdini session with a deliberately-blocked main thread (modal/cook) — manual, can't be automated headless.

## Definition of done
Standalone tests green (routing decision pinned, no-`hou` bypasses main, `hou` still marshals + atomic); the AST helper fail-safes on dynamic imports; manual live check confirms a write completes under a blocked main thread and `hou` scripts retain undo atomicity. Ships as its own PR; CRUCIBLE attacks the detection helper (try to get `hou` to run off-main).
