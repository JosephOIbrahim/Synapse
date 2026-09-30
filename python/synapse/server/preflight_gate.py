"""The Houdini side of the preflight, and the gate every transport runs (Level 1, R-5).

``core/preflight.py`` holds the checks and stays pure. This module gives it the one hop onto
Houdini's main thread, measures free disk and RAM for ``synapse_health``, and runs the gate for
the transports: ``POST /mcp`` (``mcp/server.py``) and the two WebSocket servers that the stdio
bridge reaches (``server/hwebserver_adapter.py`` and ``server/websocket.py``).

The gate applies to the calls read-only mode refuses (``read_only_mode.is_change``); reads and
stop controls always pass. It runs before a session's first change, and again after any
retryable or unrecoverable outcome on that session. The session is the MCP session on
``/mcp`` and the connection on a WebSocket; each keeps a ``preflight_due`` flag. A refusal feeds
neither the circuit breaker nor the stall detector: the hop's 250 ms budget is not a stall.

A process without Houdini has no hop, so the gate does not apply there: every test interpreter,
whose stand-in ``hou`` (tests/conftest.py) is not Houdini, and the standalone WebSocket server.
Production SYNAPSE always runs in Houdini.
"""
from __future__ import annotations

import os
import shutil
import sys
import types
from typing import Any, Callable, Dict, Optional

from ..core import preflight as _preflight


def _houdini():
    """The ``hou`` module of a running Houdini, or None.

    It is read from ``sys.modules`` when asked, never imported here: Houdini loads ``hou``
    before SYNAPSE runs. The real module is a file on disk; the stand-in the test suite plants
    is a bare module with no ``__file__``, so it is never taken for Houdini.
    """
    module = sys.modules.get("hou")
    if isinstance(module, types.ModuleType) and getattr(module, "__file__", None):
        return module
    return None


def _facts(hou) -> Dict[str, Any]:
    """Checks 3 and 4, read on Houdini's main thread."""
    return {
        "loading": bool(hou.hipFile.isLoadingHipFile()),
        "undo_enabled": bool(hou.undos.areEnabled()),
        "hip_path": hou.hipFile.path(),
    }


def _make_hop(hou) -> Callable[[float], Dict[str, Any]]:
    def hop(timeout_s: float) -> Dict[str, Any]:
        from .main_thread import MainThreadTimeout, run_on_main

        try:
            # record_stall/record_wait off: a busy moment seen by the preflight must not flip
            # the transports into fast-failing real commands, nor skew the dispatch-wait
            # histogram.
            return run_on_main(lambda: _facts(hou), timeout=timeout_s, record_stall=False,
                               record_wait=False, label="preflight")
        except MainThreadTimeout as exc:
            raise TimeoutError(str(exc)) from exc
        except ImportError:
            # hython has no UI event loop to defer onto (no hdefereval); its calling thread is
            # the only one, so the facts are read here.
            return _facts(hou)
        except hou.Error as exc:
            raise _preflight.ProbeError(str(exc)) from exc

    return hop


def houdini_hop() -> Optional[Callable[[float], Dict[str, Any]]]:
    """The preflight's hop onto Houdini's main thread, or None without Houdini in this process."""
    hou = _houdini()
    return None if hou is None else _make_hop(hou)


def server_version() -> Optional[str]:
    """The SYNAPSE release this Houdini runs."""
    import synapse

    return getattr(synapse, "__version__", None)


def _free_bytes(path: str) -> Optional[int]:
    """Free bytes on the volume holding *path*, or of its nearest existing parent."""
    probe = os.path.abspath(path)
    while not os.path.exists(probe):
        parent = os.path.dirname(probe)
        if parent == probe:
            return None
        probe = parent
    try:
        return int(shutil.disk_usage(probe).free)
    except OSError:
        return None


def _ram_available() -> Optional[int]:
    try:
        import psutil
    except ImportError:
        return None
    try:
        return int(psutil.virtual_memory().available)
    except (psutil.Error, OSError, RuntimeError, AttributeError, ValueError):
        return None


def measure_resources(hip_path: Optional[str]) -> Dict[str, Any]:
    """Check 7: free disk for the scene's folder and its cache root, and available RAM.

    The cache root is ``$HIP/cache``, the show config's default. A figure that could not be
    measured is None, never an assumed value (cache blueprint law 5).
    """
    hip_dir = os.path.dirname(hip_path) if hip_path else None
    cache_root = os.path.join(hip_dir, "cache") if hip_dir else None
    return {
        "hip_dir": hip_dir,
        "hip_free_bytes": _free_bytes(hip_dir) if hip_dir else None,
        "cache_root": cache_root,
        "cache_free_bytes": _free_bytes(cache_root) if cache_root else None,
        "ram_available_bytes": _ram_available(),
    }


def readiness(client_version: Optional[str] = None) -> Dict[str, Any]:
    """The readiness section of synapse_health (checks 1 to 7)."""
    from ..mcp import read_only_mode

    return _preflight.readiness(houdini_hop(), client_version=client_version,
                                server_version=server_version(),
                                read_only=read_only_mode.enabled(),
                                resources=measure_resources)


def admit(holder: Any, tool_name: Optional[str],
          client_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The outcome refusing *tool_name* before it is sent, or None when it may be sent.

    *holder* is the session (``/mcp``) or the connection (WebSocket); its ``preflight_due``
    attribute says whether the next change must be checked, and defaults to True. A ready
    preflight clears it; ``note`` sets it again.
    """
    from ..mcp import read_only_mode

    if not tool_name or not read_only_mode.is_change(tool_name):
        return None
    hop = houdini_hop()
    if hop is None:
        return None
    if not getattr(holder, "preflight_due", True):
        return None
    refused = _preflight.gate(hop, client_version=client_version, server_version=server_version())
    if refused is None:
        holder.preflight_due = False
        return None
    return refused.to_dict()


def note(holder: Any, outcome: Any) -> None:
    """After a call: a retryable or unrecoverable outcome makes the next change check again."""
    if _preflight.is_trouble(outcome):
        holder.preflight_due = True
        _preflight.invalidate()


def response_outcome(response: Any) -> Optional[Dict[str, Any]]:
    """The outcome a WebSocket response carries, as its wire form would say it."""
    if getattr(response, "success", True):
        return None
    from ..core.outcomes import with_failure_outcome

    data = with_failure_outcome(getattr(response, "data", None), getattr(response, "error", None))
    return data.get("outcome") if isinstance(data, dict) else None
