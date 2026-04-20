"""Suppress ``hou.ui.*`` modal dialogs around agent tool calls.

Agent tools run on a background thread marshaled to Houdini's main
thread via ``hdefereval``. If a tool body calls ``hou.ui.displayMessage``
(or any other blocking modal) the dialog opens and WAITS for a user
click. The agent thread cannot click. Deadlock.

This module provides a narrowly-scoped context manager,
``suppress_modal_dialogs()``, that patches the blocking ``hou.ui``
methods to raise ``ModalDialogSuppressedError`` instead. The error
propagates up to the Dispatcher's exception boundary and is wrapped as
``AgentToolError`` — the LLM sees the suppressed dialog as structured
data and can self-correct.

Why a context manager rather than a daemon-lifetime patch
---------------------------------------------------------
The Crucible test runs hostile co-tenancy: the **artist is also
clicking** while the agent runs. A lifetime-scoped global patch would
kill the artist's own UI. A per-tool-call context manager patches only
during the narrow window of a single main-thread dispatch, then
restores cleanly. The artist's dialogs outside that window work as
normal.

Thread safety note
------------------
``hou.ui`` patches are global (attributes on the ``hou.ui`` module).
During the patched window, **any** caller — agent thread, main thread,
another thread — sees the raisers. Because the context is entered on
the main-thread dispatch path and released before returning control,
the window is small (single tool call). Overlapping tool dispatches
would corrupt the restore state; Dispatcher serializes its executor,
so this cannot happen in practice.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any, Iterator, List

logger = logging.getLogger(__name__)


class ModalDialogSuppressedError(RuntimeError):
    """A ``hou.ui`` modal dialog was invoked during suppression window.

    Raised in place of the blocking modal. The Dispatcher's exception
    boundary catches it and wraps as ``AgentToolError(error_type=
    "ModalDialogSuppressedError")`` so the LLM sees the attempted
    dialog as ordinary tool output.

    Attributes:
        method_name: The ``hou.ui`` method that was called
            (e.g. ``"displayMessage"``).
        args: Positional args the tool passed to it.
        kwargs: Keyword args the tool passed to it.
    """

    def __init__(
        self,
        method_name: str,
        args: tuple,
        kwargs: dict,
    ):
        super().__init__(
            f"hou.ui.{method_name} was invoked inside a suppressed-dialog "
            f"window. Modal dialogs block the main thread waiting for "
            f"user input the agent cannot provide."
        )
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs


# Blocking hou.ui methods. Complete-ish list for H21.0.631.  Additions
# are safe — we patch only names that actually exist on the live module.
SUPPRESSED_METHODS: List[str] = [
    "displayMessage",
    "displayConfirmation",
    "displayFileDependencyDialog",
    "selectFromList",
    "selectFromTree",
    "selectFile",
    "selectNode",
    "readInput",
    "readMultiInput",
]


def _make_raiser(method_name: str):
    """Build a closure that raises ModalDialogSuppressedError when called."""

    def _raiser(*args: Any, **kwargs: Any) -> Any:
        raise ModalDialogSuppressedError(method_name, args, kwargs)

    _raiser.__name__ = f"_suppressed_{method_name}"
    _raiser.__doc__ = (
        f"Raises ModalDialogSuppressedError in place of the original "
        f"hou.ui.{method_name}. Installed by suppress_modal_dialogs()."
    )
    return _raiser


@contextmanager
def suppress_modal_dialogs() -> Iterator[None]:
    """Patch blocking ``hou.ui.*`` methods for the duration of the block.

    Outside Houdini — ``hou`` unimportable — this is a no-op so the
    same code path works in tests and stock Python.

    Safe to nest: inner enter patches over already-patched methods,
    inner exit restores to the inner's originals (which are the outer
    patches), and the outer exit restores to the true originals.
    """
    try:
        import hou  # type: ignore[import-not-found]
    except ImportError:
        yield
        return

    hou_ui = getattr(hou, "ui", None)
    if hou_ui is None:
        logger.debug("hou.ui not available; dialog suppression is a no-op")
        yield
        return

    originals: dict = {}
    for method_name in SUPPRESSED_METHODS:
        original = getattr(hou_ui, method_name, None)
        if original is None:
            continue
        originals[method_name] = original
        setattr(hou_ui, method_name, _make_raiser(method_name))

    logger.debug(
        "suppress_modal_dialogs: patched %d hou.ui methods",
        len(originals),
    )

    try:
        yield
    finally:
        for method_name, original in originals.items():
            setattr(hou_ui, method_name, original)
        logger.debug(
            "suppress_modal_dialogs: restored %d hou.ui methods",
            len(originals),
        )
