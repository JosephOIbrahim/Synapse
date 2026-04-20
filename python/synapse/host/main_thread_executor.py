"""Main-thread executor for Houdini (Sprint 3 Spike 1 + 2.1 bugfix).

Implements the ``main_thread_executor`` callable contract consumed by
``synapse.cognitive.dispatcher.Dispatcher``.

Runtime mode detection (three-state)
------------------------------------
Stock Python, graphical Houdini, and headless Houdini are three
distinct runtime contexts. Collapsing them to a binary
"hdefereval importable or not" produced a real bug (Spike 2.1):
the deferred ``test_inspect_live.py`` gate run under ``hython``
would raise ``RuntimeError`` with the message "use is_testing=True" —
wrong advice for a live-tool invocation — because the headless path
was misclassified.

The modes:

- ``stock``    — no ``hou`` at all. Raise ``RuntimeError``; caller
                  must use ``Dispatcher(is_testing=True)`` for
                  stock-Python / CI work.
- ``gui``      — ``hou`` present AND ``hou.isUIAvailable()`` True.
                  Marshal through
                  ``hdefereval.executeInMainThreadWithResult`` with
                  hard timeout — the Qt event loop is running, the
                  caller is typically on a background thread (agent
                  daemon or WS handler).
- ``headless`` — ``hou`` present AND ``hou.isUIAvailable()`` False.
                  No Qt event loop to marshal to. The caller IS on
                  the only Python thread — execute the tool body
                  synchronously on the calling thread.

``hou.isUIAvailable()`` is the same primitive the daemon boot gate
uses (``synapse.host.daemon.SynapseDaemon._check_boot_gate``). One
detection primitive, two call sites — symmetry keeps the host layer
coherent.

Design notes
------------
- ``hdefereval.executeInMainThreadWithResult`` is blocking. To impose
  a timeout in GUI mode, we dispatch from a worker thread and wait
  on an Event. Payload keeps executing after timeout; Python can't
  safely kill a thread mid-op. Spike 2 Phase 2 pairs this with
  ``threading.Event('cancel_requested')`` inside tool bodies so
  cooperative cancellation actually lands.
- Headless mode does NOT apply the timeout. The caller IS on the
  main thread; spawning a worker to enforce timeout would move tool
  execution off the main thread, which breaks Houdini API
  thread-safety. Tool bodies running in headless that need to bound
  themselves can wrap their own work.
- Testing path: ``synapse.cognitive.dispatcher.Dispatcher(
  is_testing=True)``. This module has no test-mode — it exists to
  touch ``hou`` and ``hdefereval``.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Dict, Optional

try:
    import hdefereval  # type: ignore[import-not-found]
    _HDEFEREVAL_AVAILABLE = True
except ImportError:
    hdefereval = None  # type: ignore[assignment]
    _HDEFEREVAL_AVAILABLE = False


DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS: float = 30.0
"""Spike 2 lock. Change in coordination with Crucible deadlock budget."""


class MainThreadTimeoutError(TimeoutError):
    """GUI-mode main-thread dispatch exceeded the timeout budget.

    Subclass of the stdlib ``TimeoutError`` so callers can catch
    either the specific class or the broader category. Only ever
    raised from the GUI-mode path — headless mode executes
    synchronously on the calling thread without a timeout wrapper.
    """


# -- Runtime mode detection -------------------------------------------------


RUNTIME_STOCK: str = "stock"
RUNTIME_GUI: str = "gui"
RUNTIME_HEADLESS: str = "headless"


def detect_runtime_mode() -> str:
    """Return ``RUNTIME_STOCK``, ``RUNTIME_GUI``, or ``RUNTIME_HEADLESS``.

    Detection rules:
      - No ``hou`` import  → stock.
      - ``hou`` but no ``isUIAvailable`` attr → raises; we don't
        guess against unsupported Houdini builds.
      - ``hou.isUIAvailable()`` True  → gui.
      - ``hou.isUIAvailable()`` False → headless.

    Called every ``main_thread_exec`` invocation rather than cached
    because ``hou.isUIAvailable()`` can legitimately change across
    a session (rare, but possible when UI is dynamically torn down).

    Raises:
        RuntimeError: ``hou`` is present but ``hou.isUIAvailable``
            is missing. We don't guess — file a bug instead.
    """
    try:
        import hou  # type: ignore[import-not-found]
    except ImportError:
        return RUNTIME_STOCK

    is_ui_available = getattr(hou, "isUIAvailable", None)
    if is_ui_available is None:
        raise RuntimeError(
            "hou is importable but hou.isUIAvailable is missing — this "
            "Houdini build pre-dates the API synapse.host relies on. "
            "File a bug with the Houdini version and hython launch mode."
        )
    return RUNTIME_GUI if is_ui_available() else RUNTIME_HEADLESS


# -- Execution paths --------------------------------------------------------


def _exec_gui(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
    effective_timeout: float,
) -> Dict[str, Any]:
    """GUI-mode execution: marshal to Houdini's main thread via hdefereval.

    The hdefereval call blocks the worker thread until the callable
    runs on the main thread. We wrap it so a stuck main-thread
    payload returns control to the caller after ``effective_timeout``.
    The main-thread work keeps running in the background — Python
    can't safely kill a thread mid-op.
    """
    if not _HDEFEREVAL_AVAILABLE:
        raise RuntimeError(
            "hou.isUIAvailable() returned True but hdefereval is not "
            "importable. This state is inconsistent — file a bug "
            "with the Houdini version, hython launch mode, and "
            "full sys.path."
        )

    result_holder: list[Any] = []
    error_holder: list[BaseException] = []
    done = threading.Event()

    def _dispatch_on_main() -> None:
        try:
            result = hdefereval.executeInMainThreadWithResult(
                lambda: fn(**kwargs)
            )
            result_holder.append(result)
        except BaseException as exc:  # noqa: BLE001 - propagate faithfully
            error_holder.append(exc)
        finally:
            done.set()

    worker = threading.Thread(
        target=_dispatch_on_main,
        name="synapse.host.main_thread_exec",
        daemon=True,
    )
    worker.start()

    if not done.wait(timeout=effective_timeout):
        raise MainThreadTimeoutError(
            f"Main-thread dispatch of {getattr(fn, '__name__', repr(fn))!r} "
            f"exceeded {effective_timeout:g}s timeout. The dispatched "
            f"callable may still be running on Houdini's main thread."
        )

    if error_holder:
        raise error_holder[0]
    return result_holder[0]


def _exec_headless(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Headless-mode execution: direct call on the calling thread.

    Headless hython runs on a single Python thread. There is no Qt
    event loop to marshal through, and no other thread that would be
    the "main" thread. Spawning a worker to enforce a timeout would
    move tool execution off the main thread, breaking Houdini API
    thread-safety. Tool bodies that need to bound themselves in
    headless must wrap their own timing.
    """
    return fn(**kwargs)


def main_thread_exec(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
    *,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """Execute ``fn(**kwargs)`` on Houdini's main thread when marshaling
    is needed; otherwise run it directly.

    Args:
        fn: Callable returning a JSON-serializable dict.
        kwargs: Keyword arguments passed to ``fn``.
        timeout: Hard timeout in seconds — honoured only in GUI mode
            (see module docstring). ``None`` uses
            ``DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS``.

    Returns:
        Whatever ``fn`` returned.

    Raises:
        RuntimeError: running in stock Python (no ``hou``), or in a
            Houdini build that lacks ``hou.isUIAvailable``, or in GUI
            mode where ``hdefereval`` is inexplicably unavailable.
        MainThreadTimeoutError: GUI-mode dispatch took longer than
            ``timeout`` seconds.
        BaseException: any exception ``fn`` raised propagates through.
    """
    mode = detect_runtime_mode()

    if mode == RUNTIME_STOCK:
        raise RuntimeError(
            "main_thread_exec requires a Houdini process "
            "(hython graphical or headless). For stock-Python / CI "
            "test work, construct Dispatcher(is_testing=True) to "
            "bypass host-thread marshaling entirely."
        )

    if mode == RUNTIME_HEADLESS:
        return _exec_headless(fn, kwargs)

    # GUI mode.
    effective_timeout: float = (
        timeout if timeout is not None
        else DEFAULT_MAIN_THREAD_TIMEOUT_SECONDS
    )
    return _exec_gui(fn, kwargs, effective_timeout)
