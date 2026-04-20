"""SYNAPSE Agent Daemon — Sprint 3 Spike 2 Phase 1 scaffolding.

The daemon is the in-process host of the Claude Agent SDK. It lives in
a background thread inside a graphical Houdini session and marshals
tool dispatches onto the main thread via
``synapse.host.main_thread_exec``. Phase 1 ships the lifecycle and the
full bootstrap chain (boot gate, auth, policy, suppression) with an
**empty agent loop** — the thread starts, signals ready, and waits on
the cancel event. Phase 2 populates the loop with actual Agent SDK
turns and runs the Crucible protocol against it.

Boot chain (in order)
---------------------
1. **Boot gate** — ``hou.isUIAvailable()`` must return True. In
   headless / PDG / render-farm-worker contexts it returns False and
   the daemon refuses to boot. This is the Render Farm Fork Bomb
   guard: TOPS scheduling N hython subprocesses each booting an agent
   would N× the API cost and blow file locks.
2. **Auth** — ``synapse.host.auth.get_anthropic_api_key()``
   (hou.secure → env var). If neither source has a key, boot halts
   with an explicit error.
3. **Event loop policy (Windows only)** —
   ``asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())``.
   Confirmed necessary in Spike 0: without it, httpx/anyio collides
   with the default ProactorEventLoop and raises
   ``APIConnectionError`` + ``NameError('closing_agens')``.
4. **User-site advisory** — ``sys.flags.no_user_site`` checked; warns
   if interpreter was started without ``-s`` / ``PYTHONNOUSERSITE=1``.
   The Spike 0 CP314/CP311 mismatch is unrecoverable from inside a
   running interpreter, so this is advisory — callers must set the
   env var at launch.
5. **Dispatcher** — built with the ``synapse_inspect_stage`` tool
   registered and a ``main_thread_executor`` that composes dialog
   suppression around ``main_thread_exec``. Per-tool-call suppression
   scope preserves the artist's own UI outside tool dispatches.
6. **Thread start** — daemon thread begins, signals ``started_event``,
   waits on ``cancel_event``. Phase 1 ends here; Phase 2 inserts the
   agent loop between signal-ready and cancel-wait.

Cancellation
------------
``cancel_event: threading.Event`` is the physical Stop button. The
agent loop (Phase 2) checks it before every API yield and before every
tool dispatch. Spike 2 Phase 1 exposes it; Phase 2 wires it into the
agent's cooperation points.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

from synapse.cognitive.agent_loop import (
    AgentTurnConfig,
    AgentTurnResult,
    STATUS_CANCELLED,
    STATUS_API_ERROR,
    run_turn,
)
from synapse.cognitive.dispatcher import Dispatcher
from synapse.cognitive.tools.inspect_stage import (
    INSPECT_STAGE_SCHEMA,
    inspect_stage,
)
from synapse.host.auth import get_anthropic_api_key
from synapse.host.dialog_suppression import suppress_modal_dialogs
from synapse.host.main_thread_executor import main_thread_exec

logger = logging.getLogger(__name__)


DEFAULT_START_TIMEOUT_SECONDS: float = 5.0
"""Max time to wait for the daemon thread to signal started_event."""

DEFAULT_STOP_TIMEOUT_SECONDS: float = 10.0
"""Max time to wait for the daemon thread to exit after cancel."""

_REQUEST_POLL_INTERVAL_SECONDS: float = 0.25
"""How often the daemon thread checks its request queue AND the
cancel event. Short enough that ``cancel()`` → exit latency is
bounded; long enough that idle loops don't peg a core."""


@dataclass
class _AgentRequest:
    """Internal envelope for a submit_turn request queued to the daemon.

    Kept private — callers use ``SynapseDaemon.submit_turn``.
    """

    user_prompt: str
    config: AgentTurnConfig
    result_queue: "queue.Queue[AgentTurnResult]"
    submitted_at: float = field(default_factory=lambda: 0.0)


class DaemonBootError(RuntimeError):
    """Boot failed before the daemon thread started.

    Distinct from runtime errors inside the daemon thread so callers
    can route on type — boot failures are recoverable (fix and retry),
    runtime failures may leave mutable state in the thread that
    needs cleanup.
    """


class SynapseDaemon:
    """In-process agent daemon.

    Phase 1 contract:
      - ``.start()`` runs the full bootstrap chain synchronously on
        the caller's thread, then spins up the daemon thread which
        immediately idles on ``cancel_event.wait()``.
      - ``.cancel()`` sets ``cancel_event`` — the agent loop cooperates.
      - ``.stop(timeout)`` cancels and joins.
      - ``.dispatcher`` exposes the Dispatcher for direct invocation
        from tests and from Phase 2's agent loop.
      - ``.cancel_event`` exposes the Event for Phase 2 check-in points.

    Reusable: ``start()`` / ``stop()`` can cycle repeatedly. State is
    cleared at each start.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        thread_name: str = "synapse.host.daemon",
        boot_gate: bool = True,
        main_thread_executor: Optional[
            Callable[[Callable, Dict[str, Any]], Dict[str, Any]]
        ] = None,
        anthropic_client_factory: Optional[Callable[[str], Any]] = None,
    ) -> None:
        """Construct the daemon (boot is deferred to ``start()``).

        Args:
            api_key: Optional override for the resolved API key. When
                ``None``, boot resolves via hou.secure → env var.
                Passing a value bypasses resolution — useful for tests
                and for explicit-credential launches.
            thread_name: Name assigned to the daemon ``threading.Thread``.
                Appears in debugger / thread inspection.
            boot_gate: When True (default), boot refuses unless
                ``hou.isUIAvailable()``. Tests and direct-hython
                experiments can pass ``False`` to skip.
            main_thread_executor: Optional override for the executor
                the Dispatcher uses. Default composes
                ``suppress_modal_dialogs()`` around
                ``main_thread_exec``. Tests can inject a pure-Python
                stub to exercise the daemon outside Houdini.
            anthropic_client_factory: Optional callable that accepts
                the resolved API key and returns a client object with
                a ``messages.create(...)`` method. Default imports
                ``anthropic.Anthropic`` at boot time. Tests inject a
                mock so no real API calls are made.
        """
        self._api_key_override = api_key
        self._thread_name = thread_name
        self._boot_gate_enabled = boot_gate
        self._custom_executor = main_thread_executor
        self._client_factory = anthropic_client_factory

        self._thread: Optional[threading.Thread] = None
        self._dispatcher: Optional[Dispatcher] = None
        self._anthropic_client: Optional[Any] = None
        self._request_queue: "queue.Queue[_AgentRequest]" = queue.Queue()
        self._cancel_event = threading.Event()
        self._started_event = threading.Event()
        self._exit_event = threading.Event()
        self._thread_error: Optional[BaseException] = None
        self._resolved_api_key: Optional[str] = None

    # -- Public surface --------------------------------------------------

    @property
    def cancel_event(self) -> threading.Event:
        """The cooperative cancel flag. Phase 2 checks it at yield points."""
        return self._cancel_event

    @property
    def started_event(self) -> threading.Event:
        """Set once the daemon thread is running. Useful for test sync."""
        return self._started_event

    @property
    def exit_event(self) -> threading.Event:
        """Set once the daemon thread has exited, success or failure."""
        return self._exit_event

    @property
    def dispatcher(self) -> Dispatcher:
        """The Dispatcher this daemon uses. Available after ``start()``.

        Raises:
            DaemonBootError: daemon has not been started yet.
        """
        if self._dispatcher is None:
            raise DaemonBootError(
                "Dispatcher not available — daemon has not been started"
            )
        return self._dispatcher

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def thread_error(self) -> Optional[BaseException]:
        """Exception the daemon thread raised (if any). None on clean exit."""
        return self._thread_error

    def start(self) -> None:
        """Run the boot chain and start the daemon thread.

        Raises:
            DaemonBootError: any boot-chain step failed. The daemon
                thread is not started; no cleanup required.
        """
        if self.is_running:
            raise DaemonBootError("Daemon already running; stop() it first")

        self._check_boot_gate()
        self._resolved_api_key = self._resolve_api_key()
        self._apply_event_loop_policy()
        self._warn_if_user_site_active()
        self._dispatcher = self._build_dispatcher()
        self._boot_inspector_transport()
        self._anthropic_client = self._build_anthropic_client()

        # Reset signals for a fresh run. The request queue is drained
        # so any stale submit_turn()s from a prior cycle don't fire.
        self._drain_request_queue()
        self._cancel_event.clear()
        self._started_event.clear()
        self._exit_event.clear()
        self._thread_error = None

        self._thread = threading.Thread(
            target=self._thread_main,
            name=self._thread_name,
            daemon=True,
        )
        self._thread.start()

        if not self._started_event.wait(timeout=DEFAULT_START_TIMEOUT_SECONDS):
            raise DaemonBootError(
                f"Daemon thread did not signal started within "
                f"{DEFAULT_START_TIMEOUT_SECONDS:g}s"
            )
        logger.info("SynapseDaemon started (thread: %r)", self._thread_name)

    def cancel(self) -> None:
        """Signal cooperative cancel. Idempotent.

        Safe to call from any thread. The daemon thread's cooperation
        points (Phase 2) pick it up within one yield-point of being set.
        """
        self._cancel_event.set()

    def stop(self, timeout: float = DEFAULT_STOP_TIMEOUT_SECONDS) -> None:
        """Cancel and join the daemon thread.

        Args:
            timeout: Join timeout in seconds. If the thread does not
                exit within this budget, a warning is logged and the
                method returns — Python cannot force-kill a thread.
        """
        self.cancel()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning(
                    "Daemon thread did not exit within %.1fs of stop()",
                    timeout,
                )
        self._thread = None

    # -- Boot chain steps ------------------------------------------------

    def _check_boot_gate(self) -> None:
        """Refuse boot unless ``hou.isUIAvailable()`` returns True.

        Render Farm Fork Bomb guard. PDG / TOPS workers spawn N hython
        subprocesses; each booting an agent multiplies API cost and
        produces file-lock contention. Headless hython returns False
        from ``hou.isUIAvailable()``; graphical Houdini returns True.
        """
        if not self._boot_gate_enabled:
            logger.debug("Boot gate bypassed (boot_gate=False)")
            return

        try:
            import hou  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DaemonBootError(
                "SynapseDaemon requires a running Houdini process. "
                "Pass boot_gate=False only if you know why."
            ) from exc

        is_ui_available = getattr(hou, "isUIAvailable", None)
        if is_ui_available is None:
            raise DaemonBootError(
                "hou.isUIAvailable is missing from this Houdini build — "
                "cannot verify the boot gate. Refusing to boot."
            )

        if not is_ui_available():
            raise DaemonBootError(
                "hou.isUIAvailable() returned False. SynapseDaemon will "
                "not boot in headless / PDG contexts (Render Farm Fork "
                "Bomb prevention). Pass boot_gate=False to override."
            )

    def _resolve_api_key(self) -> str:
        """Explicit override > hou.secure > env var.

        Raises:
            DaemonBootError: no source produced a usable key.
        """
        if self._api_key_override is not None:
            key = self._api_key_override.strip()
            if not key:
                raise DaemonBootError(
                    "Explicit api_key override was empty / whitespace"
                )
            return key

        resolved = get_anthropic_api_key()
        if resolved is None:
            raise DaemonBootError(
                "No Anthropic API key available. Set one via "
                "hou.secure.setPassword('synapse_anthropic', 'sk-ant-...') "
                "or export ANTHROPIC_API_KEY=sk-ant-... before launching."
            )
        return resolved

    def _apply_event_loop_policy(self) -> None:
        """Spike 0 bootstrap lock: selector policy on Windows.

        Without it, httpx/anyio raises APIConnectionError + NameError
        ('closing_agens') during async shutdown on Python 3.11 Windows
        because the default ProactorEventLoop mishandles stream cleanup.
        """
        if sys.platform == "win32":
            policy = asyncio.WindowsSelectorEventLoopPolicy()
            asyncio.set_event_loop_policy(policy)
            logger.info(
                "Event loop policy set to WindowsSelectorEventLoopPolicy"
            )

    def _warn_if_user_site_active(self) -> None:
        """Spike 0 bootstrap lock (advisory): user site should be disabled.

        Cannot be enforced from inside a running interpreter — the flag
        is read at startup. If unset, warn; downstream wrong-ABI imports
        will fail loudly at that point.
        """
        if not getattr(sys.flags, "no_user_site", False):
            logger.warning(
                "User site-packages enabled (PYTHONNOUSERSITE not set at "
                "interpreter launch). Spike 0 found CP314 pydantic_core "
                "binaries leaking from user site into CP311 hython. Start "
                "hython with -s flag or set PYTHONNOUSERSITE=1 before "
                "launching to isolate."
            )

    def _build_dispatcher(self) -> Dispatcher:
        """Construct the Dispatcher with host-layer executor + suppression.

        The executor composes ``suppress_modal_dialogs()`` around
        ``main_thread_exec`` so every tool dispatch gets a clean,
        narrowly-scoped dialog-suppression window.
        """
        executor = self._custom_executor or _default_executor
        return Dispatcher(
            tools={"synapse_inspect_stage": inspect_stage},
            schemas={"synapse_inspect_stage": INSPECT_STAGE_SCHEMA},
            main_thread_executor=executor,
        )

    def _build_anthropic_client(self) -> Any:
        """Construct the Anthropic client for the agent loop.

        Default: imports ``anthropic.Anthropic`` lazily so stock-Python
        test paths don't pay the import cost. Tests inject
        ``anthropic_client_factory`` to bypass the real SDK entirely.

        Raises:
            DaemonBootError: anthropic SDK is not installed and no
                factory was provided. Actionable because Spike 0's
                install recipe for hython's site-packages is
                ``hython -m pip install anthropic`` (with the
                sys.path-stripping launcher documented there).
        """
        if self._client_factory is not None:
            return self._client_factory(self._resolved_api_key or "")

        try:
            from anthropic import Anthropic  # type: ignore[import-not-found]
        except ImportError as exc:
            raise DaemonBootError(
                "anthropic SDK is not installed in this Python. "
                "See Spike 0's install recipe for hython; for stock-"
                "Python tests pass anthropic_client_factory explicitly."
            ) from exc
        return Anthropic(api_key=self._resolved_api_key)

    def _drain_request_queue(self) -> None:
        """Empty the request queue. Called on start() before the thread
        takes over, so stale requests from a prior cycle don't fire
        into the new agent loop."""
        try:
            while True:
                self._request_queue.get_nowait()
        except queue.Empty:
            pass

    def _boot_inspector_transport(self) -> None:
        """Wire the Inspector's global transport to the in-process executor.

        Sprint 2.3 bug fix: the ``inspect_stage`` cognitive tool calls
        ``synapse.inspector.synapse_inspect_stage`` internally, which
        dispatches through the Inspector's configured transport (a
        ``TransportFn`` registered via
        ``synapse.inspector.configure_transport``). Pre-2.3, the daemon
        never registered one — the first tool call raised
        ``TransportNotConfiguredError``. Baseline Crucible caught this.

        Idempotent: ``is_transport_configured()`` checked first. If
        something else already registered a transport (test fixture,
        external bootstrap, prior daemon cycle), leave that intact —
        the caller has a reason and we are not in the business of
        second-guessing it.

        Belt-and-suspenders: seeds the
        ``SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE`` env var when unset.
        That's the resolution path ``tests/test_inspect_live.py`` uses
        to find a transport when ``configure_transport`` wasn't called
        in the consumer process.
        """
        # Function-scope imports — cognitive layer is already loaded by
        # the time we get here (dispatcher was built above), but keeping
        # these local avoids polluting the module-level import graph.
        from synapse.inspector import (
            configure_transport,
            is_transport_configured,
        )
        from synapse.host import transport as _host_transport

        if is_transport_configured():
            logger.debug(
                "Inspector transport already configured — leaving intact"
            )
        else:
            configure_transport(_host_transport.execute_python)
            logger.info(
                "Inspector transport wired: synapse.host.transport.execute_python"
            )

        env_var = "SYNAPSE_INSPECTOR_LIVE_TRANSPORT_MODULE"
        if env_var not in os.environ:
            os.environ[env_var] = "synapse.host.transport"
            logger.debug("%s seeded to synapse.host.transport", env_var)

    # -- submit_turn -----------------------------------------------------

    def submit_turn(
        self,
        user_prompt: str,
        *,
        system: str = "",
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        max_iterations: Optional[int] = None,
        wait_timeout: Optional[float] = None,
    ) -> AgentTurnResult:
        """Submit a prompt to the agent loop; block until it returns.

        Blocks the caller's thread while the daemon thread runs the
        turn. Tool dispatches inside the turn go through the
        Dispatcher (and thus through the host-layer main-thread
        executor → hdefereval in GUI mode, direct exec in headless).

        Args:
            user_prompt: The user message kicking off the turn.
            system: Optional system prompt.
            model: Override the default model for this turn.
            max_tokens: Override per-response token ceiling.
            max_iterations: Override the cap on API round-trips.
            wait_timeout: How long to wait for the daemon thread to
                return a result. ``None`` = wait indefinitely. Tests
                should always pass a small finite timeout so stuck
                tests surface loudly.

        Returns:
            ``AgentTurnResult`` on normal completion.

        Raises:
            DaemonBootError: daemon is not running.
            TimeoutError: ``wait_timeout`` elapsed without a result.
                The request may still be pending or actively running
                on the daemon thread; use ``cancel()`` + ``stop()``
                to tear down if needed.
        """
        if not self.is_running:
            raise DaemonBootError(
                "submit_turn requires a running daemon — call start() first."
            )

        config = AgentTurnConfig(
            model=model or AgentTurnConfig.model,
            max_tokens=max_tokens if max_tokens is not None
                       else AgentTurnConfig.max_tokens,
            max_iterations=(max_iterations if max_iterations is not None
                            else AgentTurnConfig.max_iterations),
            system=system,
        )
        result_queue: "queue.Queue[AgentTurnResult]" = queue.Queue(maxsize=1)
        request = _AgentRequest(
            user_prompt=user_prompt,
            config=config,
            result_queue=result_queue,
        )
        self._request_queue.put(request)

        try:
            return result_queue.get(timeout=wait_timeout)
        except queue.Empty as exc:
            raise TimeoutError(
                f"submit_turn did not complete within {wait_timeout}s"
            ) from exc

    # -- Thread entry point ---------------------------------------------

    def _thread_main(self) -> None:
        """Daemon loop body.

        Phase 2 (Spike 2.2) shape:
          1. Signal ``started_event`` so ``start()`` unblocks.
          2. Loop: pull requests from ``_request_queue`` with a short
             timeout so cancel latency is bounded. Each request is
             a ``_AgentRequest`` carrying a user prompt, config, and
             a reply queue.
          3. For each request: run ``synapse.cognitive.agent_loop.run_turn``
             against the dispatcher + cancel event. Post the result
             back on the request's reply queue.
          4. Exit loop when ``cancel_event`` fires.

        Cancel semantics:
          - Between requests: cancel cuts the loop immediately.
          - During a request: the agent_loop itself checks
            ``cancel_event`` at every API yield and every tool
            dispatch and returns STATUS_CANCELLED. The daemon still
            posts that result back so callers aren't left waiting.
        """
        try:
            self._started_event.set()
            logger.info("Daemon thread entering request loop")
            while not self._cancel_event.is_set():
                try:
                    request = self._request_queue.get(
                        timeout=_REQUEST_POLL_INTERVAL_SECONDS,
                    )
                except queue.Empty:
                    continue
                self._process_request(request)
            logger.info("Daemon thread received cancel — exiting loop")
        except BaseException as exc:  # noqa: BLE001 — capture everything
            self._thread_error = exc
            logger.exception("Daemon thread raised")
        finally:
            self._exit_event.set()

    def _process_request(self, request: _AgentRequest) -> None:
        """Run one agent turn against the configured client + dispatcher.

        Never lets a turn failure take down the daemon thread. API
        errors and unexpected exceptions come back on the reply queue
        as ``AgentTurnResult`` values (with status STATUS_API_ERROR
        when the loop caught it, or a synthesized result when the
        failure escaped the loop itself).
        """
        assert self._dispatcher is not None
        assert self._anthropic_client is not None
        try:
            result = run_turn(
                self._anthropic_client,
                self._dispatcher,
                request.user_prompt,
                cancel_event=self._cancel_event,
                config=request.config,
            )
        except BaseException as exc:  # noqa: BLE001 — protect daemon thread
            logger.exception("run_turn raised outside its own guard")
            result = AgentTurnResult(
                status=STATUS_API_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )
        try:
            request.result_queue.put_nowait(result)
        except queue.Full:
            # Caller abandoned the request (e.g. timed out and moved
            # on). Nothing to do — the result is discarded.
            logger.debug("Dropping turn result — caller queue full")


def _default_executor(
    fn: Callable[..., Dict[str, Any]],
    kwargs: Dict[str, Any],
) -> Dict[str, Any]:
    """Production executor: dialog suppression + main-thread marshal.

    Every tool dispatch through this executor gets its own
    suppression window that opens on enter and closes before return —
    the artist's own UI work outside this narrow interval is untouched.
    """
    with suppress_modal_dialogs():
        return main_thread_exec(fn, kwargs)
