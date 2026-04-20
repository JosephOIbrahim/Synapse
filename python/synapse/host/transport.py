"""In-process synchronous ``execute_python`` transport (Sprint 3 Spike 2 P1).

Closes the deferred Sprint-2 Week-1 gate: test_inspect_live.py's
``SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE`` can now point at
``synapse.host.transport`` to route Inspector calls through the
host-layer main-thread executor instead of through an external
WebSocket.

Contract
--------
Matches ``synapse.inspector.transport.TransportFn``:

    def execute_python(code: str, *, timeout: Optional[float] = None) -> str:
        '''Runs code in Houdini's runtime, returns captured stdout.'''

Behaviour
---------
1. The compiled code runs on Houdini's main thread via
   ``synapse.host.main_thread_exec`` (Spike 1). Timeout kwarg is
   honoured; exceeds-budget raises ``MainThreadTimeoutError``.
2. stdout is redirected into a fresh ``io.StringIO`` inside the
   main-thread payload — per-call isolation, no shared buffer.
3. Exceptions from the executed code propagate up to the caller;
   at the Dispatcher exception boundary they are wrapped as
   ``AgentToolError`` — not here.

This module IS a host-layer import (touches ``hou`` transitively via
``main_thread_exec``). It lives in ``synapse.host.*`` and never imports
``hou`` directly — transitive deps are the executor's problem.
"""

from __future__ import annotations

import contextlib
import io
from typing import Any, Dict, Optional

from synapse.host.main_thread_executor import main_thread_exec


def _run_with_stdout_capture(code: str) -> Dict[str, Any]:
    """Runs on Houdini's main thread (inside main_thread_exec).

    Compiles ``code``, executes it with stdout redirected to a local
    ``io.StringIO``, returns the captured output. Per-call isolation
    is guaranteed: every invocation constructs its own buffer here
    inside the main-thread payload.
    """
    buffer = io.StringIO()
    compiled = compile(code, "<synapse.host.transport>", "exec")
    namespace: Dict[str, Any] = {"__builtins__": __builtins__}
    with contextlib.redirect_stdout(buffer):
        exec(compiled, namespace)  # noqa: S102 — DCC scripting pattern
    return {"stdout": buffer.getvalue()}


def execute_python(code: str, *, timeout: Optional[float] = None) -> str:
    """Execute Python code on Houdini's main thread; return stdout.

    Args:
        code: Python source to run in Houdini.
        timeout: Per-call timeout in seconds. ``None`` → executor
            default (30s, per Spike 2 Crucible lock).

    Returns:
        Captured stdout (string) from the executed code.

    Raises:
        MainThreadTimeoutError: dispatch exceeded ``timeout``.
        RuntimeError: not running inside Houdini (no hdefereval).
        BaseException: whatever ``code`` itself raised.
    """
    result = main_thread_exec(
        _run_with_stdout_capture,
        {"code": code},
        timeout=timeout,
    )
    return result.get("stdout", "") or ""
