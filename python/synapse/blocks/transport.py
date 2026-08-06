"""BLOCKS transport -- how a caller outside the Houdini process reaches in.

Identical contract to the Inspector's transport (``synapse.inspector.transport``),
and it REUSES that module's ``wrap_script_base64`` rather than carrying a second
copy of the base64/exec wrapper:

    def execute_python(code: str, *, timeout: Optional[float] = None) -> str

The registry is separate from the Inspector's on purpose. mcp_server builds one
Dispatcher singleton per tool family, each with its own closure over the asyncio
loop; sharing one global transport would mean whichever family happened to boot
first silently owned the other's plumbing.

Pure Python. No ``hou``.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional, Protocol

from synapse.inspector.transport import wrap_script_base64

__all__ = [
    "TransportFn",
    "TransportNotConfiguredError",
    "configure_transport",
    "get_transport",
    "is_transport_configured",
    "reset_transport",
    "wrap_script_base64",
]


class TransportNotConfiguredError(RuntimeError):
    """No transport has been registered for the BLOCKS tools."""


class TransportFn(Protocol):
    def __call__(self, code: str, *, timeout: Optional[float] = None) -> str:
        ...


_lock = threading.RLock()
_configured: Optional[TransportFn] = None


def configure_transport(fn: Callable[..., str]) -> None:
    """Register the transport. Call once at application startup."""
    if not callable(fn):
        raise TypeError(
            "configure_transport requires a callable, got %s" % type(fn).__name__
        )
    global _configured
    with _lock:
        _configured = fn


def reset_transport() -> None:
    """Unregister the transport. For test isolation."""
    global _configured
    with _lock:
        _configured = None


def get_transport() -> TransportFn:
    with _lock:
        fn = _configured
    if fn is None:
        raise TransportNotConfiguredError(
            "No BLOCKS transport registered. Call "
            "synapse.blocks.transport.configure_transport(fn) at startup, or "
            "pass execute_python_fn explicitly."
        )
    return fn


def is_transport_configured() -> bool:
    with _lock:
        return _configured is not None
