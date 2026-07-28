"""Make a long main-thread payload legible and escapable.

THE PROBLEM, IN THE CODEBASE'S OWN WORDS. ``main_thread.run_on_main`` fast path
2 says:

    "a long inline payload still freezes the GUI for its duration... NO bounding
     is applied here: the caller is the main thread, and there is no mechanism
     by which Python can interrupt it. Any 'timeout' on this path would be a
     lie. Pure observation."

Every clause of that is true of PURE PYTHON. It is not true of Houdini.

``hou.InterruptableOperation`` is Houdini's own cooperative interrupt - probed
present on 22.0.368, with ``updateProgress`` and ``updateLongProgress``. It
gives three things Python alone cannot:

    a progress bar, so the freeze is LEGIBLE rather than looking like a hang
    a Cancel, so the artist is not trapped
    Houdini pumping its own event loop inside the operation

SYNAPSE used it in ZERO files before this. That is the same shape as R73, where
the analysis nearly shipped "Houdini exposes no way to cancel a render" while
``rkill`` sat in the vendor's own reference.

WHAT THIS DOES NOT DO. It does not make anything faster, and it does not move
``hou.*`` off the main thread - nothing can, that is Houdini's threading model.
It changes a dead UI into a progress bar with an escape, which is most of what
"smoother" actually means to the person waiting.

Usage - wrap the long payload, not the whole handler:

    with long_operation("Cooking karmarendersettings1") as op:
        for i, item in enumerate(work):
            op.step(i / len(work), "frame %d" % i)   # raises on Cancel
            do_one(item)
"""

try:
    import hou
except ImportError:  # pragma: no cover - importable outside Houdini
    hou = None


class OperationCancelled(RuntimeError):
    """The artist pressed Cancel. Distinct from a failure - nothing broke."""


class _NullOperation:
    """No Houdini, or no UI. Every call is a no-op and nothing raises.

    Graceful degradation is a contract here: hython has no UI, and a handler
    wrapped in this must behave identically there.
    """

    def step(self, fraction=None, message=None):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _HoudiniOperation:
    """A live hou.InterruptableOperation with a cooperative cancel."""

    def __init__(self, title, long_progress=True):
        self._title = title
        self._long = long_progress
        self._op = None
        self._ctx = None

    def __enter__(self):
        self._op = hou.InterruptableOperation(
            self._title, open_interrupt_dialog=True)
        self._ctx = self._op.__enter__()
        return self

    def __exit__(self, *exc):
        try:
            return self._op.__exit__(*exc)
        finally:
            self._op = None

    def step(self, fraction=None, message=None):
        """Report progress and check for Cancel.

        Raises OperationCancelled if the artist pressed it. That is the whole
        point: without a call to this, the operation is still uninterruptible -
        Houdini's interrupt is COOPERATIVE, so a payload that never reports
        progress can never be cancelled.
        """
        if self._op is None:
            return
        try:
            if self._long:
                self._op.updateLongProgress(
                    percentage=fraction if fraction is not None else -1.0,
                    long_op_status=message or "")
            else:
                self._op.updateProgress(
                    fraction if fraction is not None else -1.0)
        except hou.OperationInterrupted:
            raise OperationCancelled(self._title)


def long_operation(title, long_progress=True):
    """A progress+cancel context for main-thread work, or a no-op without a UI.

    Never raises on construction. A handler that wraps its payload in this must
    behave identically in hython, where there is no UI to interrupt.
    """
    if hou is None:
        return _NullOperation()
    if not hasattr(hou, "InterruptableOperation"):
        return _NullOperation()
    try:
        if hasattr(hou, "isUIAvailable") and not hou.isUIAvailable():
            return _NullOperation()
    except Exception:
        return _NullOperation()
    return _HoudiniOperation(title, long_progress=long_progress)
