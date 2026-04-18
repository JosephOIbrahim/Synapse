"""SYNAPSE 2.0 Inspector — Transport layer.

Provides:
  - ``configure_transport(fn)``: register the WebSocket execute_python
    function once at application startup
  - ``wrap_script_base64(script)``: wrap a multi-line Python script as a
    single-line exec() call to bypass WebSocket multi-line parser
    constraints (Sprint 1 §6.3)

Thread safety
-------------
The configured transport is module-level mutable state. Access is
guarded by an RLock. ``configure_transport``, ``reset_transport``, and
``get_transport`` are all safe to call from multiple threads.

Transport function contract
---------------------------
A valid transport function has the signature:

    def execute_python(code: str, *, timeout: Optional[float] = None) -> str:
        '''Send Python source to Houdini via WebSocket, return stdout.

        Args:
            code: Python source to execute in Houdini's interpreter.
            timeout: Optional timeout in seconds.

        Returns:
            stdout captured from the Houdini-side execution.

        Raises:
            TransportError: transport layer failed
            TransportTimeoutError: operation exceeded timeout
        '''

The Inspector uses duck-typing on the timeout keyword: if the wrapped
transport doesn't accept ``timeout``, it's called without. This lets
the Inspector work against both modern (timeout-aware) and legacy
transport functions.

Security
--------
``wrap_script_base64`` is NOT a trust boundary. The script it wraps
is trusted code from the Inspector module, never user input. Do not
use this function to smuggle arbitrary user-controlled strings through
``exec()``.
"""

from __future__ import annotations

import base64
import logging
import threading
from typing import Callable, Optional, Protocol

from synapse.inspector.exceptions import TransportNotConfiguredError

logger = logging.getLogger(__name__)


class TransportFn(Protocol):
    """Protocol for a transport function.

    Modern implementations accept an optional ``timeout`` kwarg.
    Legacy implementations may omit it — the Inspector handles both.
    """

    def __call__(self, code: str, *, timeout: Optional[float] = None) -> str:
        ...


# Module-level mutable state guarded by the lock below.
_lock = threading.RLock()
_configured_transport: Optional[TransportFn] = None


def configure_transport(fn: Callable[..., str]) -> None:
    """Register the default transport function.

    Call once at application startup. Subsequent calls replace the
    registered function (useful for reconfiguration, but test code
    should prefer dependency injection via the ``execute_python_fn``
    parameter on Inspector functions).

    Args:
        fn: Callable that accepts a Python code string and returns the
            stdout as a string. May optionally accept ``timeout`` kwarg.

    Raises:
        TypeError: if fn is not callable.
    """
    if not callable(fn):
        raise TypeError(
            f"configure_transport requires a callable, got {type(fn).__name__}"
        )
    global _configured_transport
    with _lock:
        previous = _configured_transport
        _configured_transport = fn
    if previous is not None:
        logger.info("Transport reconfigured (previous registration replaced)")
    else:
        logger.debug("Transport configured")


def reset_transport() -> None:
    """Unregister the current transport.

    Primarily for test isolation. Production code should not need this.
    """
    global _configured_transport
    with _lock:
        _configured_transport = None
    logger.debug("Transport reset to unconfigured")


def get_transport() -> TransportFn:
    """Return the configured transport.

    Raises:
        TransportNotConfiguredError: no transport has been registered.
    """
    with _lock:
        fn = _configured_transport
    if fn is None:
        raise TransportNotConfiguredError(
            "No transport registered. Call configure_transport(fn) at "
            "application startup, or pass execute_python_fn explicitly."
        )
    return fn


def is_transport_configured() -> bool:
    """True if a transport is currently registered."""
    with _lock:
        return _configured_transport is not None


def wrap_script_base64(script: str) -> str:
    """Wrap a multi-line Python script as a single-line exec() call.

    This bypasses WebSocket multi-line parser constraints (Sprint 1 §6.3:
    "multi-line Python with dict literals fails over WebSocket") while
    preserving full original script semantics.

    The output is a single line in the form:

        exec(__import__('base64').b64decode('...').decode('utf-8'))

    Args:
        script: Multi-line Python source to wrap.

    Returns:
        Single-line exec() call containing the Base64-encoded script.

    Raises:
        TypeError: if script is not a str.

    Security note:
        This function is a transport-layer utility, not a trust boundary.
        The script should be compile-time constant Python from the
        Inspector module. Never pass unsanitized user input through here.
    """
    if not isinstance(script, str):
        raise TypeError(
            f"wrap_script_base64 requires str, got {type(script).__name__}"
        )
    encoded = base64.b64encode(script.encode("utf-8")).decode("ascii")
    return (
        f"exec(__import__('base64').b64decode('{encoded}').decode('utf-8'))"
    )
