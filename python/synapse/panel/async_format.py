"""Off-main formatting pipeline for the chat result path (W2-S2 / F4 design).

WHY THIS EXISTS
---------------
The panel result path formats a reply to HTML and inserts it into the chat
``QTextDocument`` entirely on Houdini's Qt main thread. The convergence seat of
BOTH result paths -- the streaming finalize (``end_stream``) and the non-streaming
direct append -- is ``ChatDisplay.append_synapse_message`` (FRZ probe 5). Two costs
live there, and they are separable:

  * ``format_synapse_message`` -- four regex passes + ``html.escape`` over the whole
    reply. PURE string work: zero Qt, zero ``hou`` (``message_formatter.py``).
  * ``insertHtml`` -- Qt rich-text re-layout, O(document). It touches ``QTextCursor``
    / ``QTextDocument`` and therefore MUST stay on the Qt thread.

The F4 design (the W1-MTFIX spawn that seeded this leg) moves the first off the Qt
thread and keeps the second on it: decide grouping on main (cheap), run the pure
formatter on a worker thread, hand a PRERENDERED HTML STRING back to main, insert
there.

WHAT THIS MODULE IS
-------------------
A single-consumer FIFO pipeline. ``submit(job)`` enqueues a job whose ``render()``
is the pure formatter call; ONE background daemon thread pulls jobs in submit order,
runs ``render()`` off the submitting thread, and makes each completed job available
-- again in submit order -- to a main-thread ``drain()``. Ordering is correct BY
CONSTRUCTION: a single serial consumer never starts job N+1 before job N is rendered,
so a burst of completions can only surface in submit order. There is no reordering
window to get wrong.

Qt is never imported here and no Qt object ever crosses to the worker: a job carries
plain data in and a plain HTML string out. The caller (``ChatDisplay``) owns the one
Qt hop -- a queued signal that wakes the main-thread ``drain``. That keeps this
module zero-Qt / zero-``hou`` and therefore unit-testable headless, on stock Python,
with no ``QApplication`` -- the tier that carries the load-bearing off-main + ordering
proof, exactly as the sibling result-telemetry module is testable without Qt.
"""

from __future__ import annotations

import collections
import threading
from queue import Queue
from typing import Any, Callable, List, Optional


class FormatJob:
    """One unit of deferred formatting.

    ``render`` is a pure, no-arg callable returning the HTML string (a bound
    ``format_synapse_message`` call). ``apply`` is the main-thread insert callback,
    invoked with THIS job when it is drained on main (it reads ``job.html``).
    ``html`` is filled by the worker; ``error`` captures a render exception so the
    worker thread can never die; ``thread_ident`` / ``thread_name`` record WHERE
    ``render()`` actually ran, which is the off-main proof. ``meta`` carries any
    caller label (e.g. an ordering index for tests).
    """

    __slots__ = ("render", "apply", "html", "error", "thread_ident",
                 "thread_name", "meta")

    def __init__(self,
                 render: Callable[[], str],
                 apply: Optional[Callable[["FormatJob"], None]] = None,
                 meta: Any = None) -> None:
        self.render = render
        self.apply = apply
        self.meta = meta
        self.html: Optional[str] = None
        self.error: Optional[BaseException] = None
        self.thread_ident: Optional[int] = None
        self.thread_name: Optional[str] = None


class OrderedAsyncFormatter:
    """FIFO single-consumer off-main formatter. Ordering is by construction.

    ``on_ready`` (optional) is called FROM THE WORKER THREAD each time a job finishes
    rendering; the caller uses it to marshal a ``drain()`` onto the main thread (in
    the panel that is a queued Qt signal). It must be cheap and must not touch Qt
    objects directly -- its only job is to wake the main thread.
    """

    def __init__(self,
                 on_ready: Optional[Callable[[], None]] = None,
                 name: str = "synapse-fmt") -> None:
        self._in: "Queue[Optional[FormatJob]]" = Queue()
        self._ready: "collections.deque[FormatJob]" = collections.deque()
        self._ready_lock = threading.Lock()
        self._on_ready = on_ready
        self._name = name
        self._thread: Optional[threading.Thread] = None
        self._alive = False
        # Pending = submitted-but-not-yet-rendered. Guards the idle Event with it so
        # a submit/complete race can't leave the Event wrongly set.
        self._pending = 0
        self._pending_lock = threading.Lock()
        self._idle = threading.Event()
        self._idle.set()

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the worker thread (idempotent). Lazy: a ChatDisplay that never
        appends a synapse message never spawns a thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._alive = True
        self._thread = threading.Thread(
            target=self._run, name=self._name, daemon=True)
        self._thread.start()

    def stop(self, join_timeout: float = 2.0) -> None:
        """Signal the worker to exit and join it. Safe to call more than once."""
        self._alive = False
        self._in.put(None)  # sentinel wakes a blocked get()
        t = self._thread
        if t is not None:
            t.join(join_timeout)
        self._thread = None

    # -- producer (main thread) ---------------------------------------------

    def submit(self, job: FormatJob) -> None:
        """Enqueue a job. Starts the worker lazily. Call on the main thread."""
        self.start()
        with self._pending_lock:
            self._pending += 1
            self._idle.clear()
        self._in.put(job)

    # -- consumer (worker thread) -------------------------------------------

    def _run(self) -> None:
        while True:
            job = self._in.get()
            if job is None:
                break
            job.thread_ident = threading.get_ident()
            job.thread_name = threading.current_thread().name
            try:
                job.html = job.render()
            except BaseException as exc:  # a formatter bug must not kill the thread
                job.error = exc
                job.html = ""
            with self._ready_lock:
                self._ready.append(job)
            with self._pending_lock:
                self._pending -= 1
                if self._pending == 0:
                    self._idle.set()
            cb = self._on_ready
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass  # a wake-up failure must never break the worker

    # -- drain (main thread) -------------------------------------------------

    def drain(self) -> List[FormatJob]:
        """Pop every completed job IN SUBMIT ORDER and run ``job.apply(job)``.

        Returns the drained jobs. Call on the main thread: ``job.apply`` is where
        ``insertHtml`` runs, and that is the only Qt work the result path still does
        on main.
        """
        drained: List[FormatJob] = []
        while True:
            with self._ready_lock:
                if not self._ready:
                    break
                job = self._ready.popleft()
            drained.append(job)
            if job.apply is not None:
                job.apply(job)
        return drained

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """Block until every submitted job has finished RENDERING (not necessarily
        drained/inserted). For tests and for the synchronous flush the panel does
        before a same-thread insert. Returns True if idle within the timeout."""
        return self._idle.wait(timeout)

    def pending(self) -> int:
        """Count of submitted-but-not-yet-rendered jobs (diagnostic)."""
        with self._pending_lock:
            return self._pending
