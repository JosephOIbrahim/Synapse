"""
Main-Thread Tool Executor -- Qt signal/slot bridge for Houdini panel.

The Claude API worker runs on a QThread and cannot call hou.* directly.
This module provides a ToolRequest + ToolExecutor pair that bridges the gap:

  1. Worker creates a ToolRequest (with a threading.Event)
  2. Worker emits a Qt signal carrying the request
  3. Qt's AutoConnection delivers the signal to ToolExecutor on the main thread
  4. ToolExecutor dispatches through SynapseHandler (which calls hou.*)
  5. ToolExecutor sets request.result/error and fires request.done
  6. Worker's request.done.wait() unblocks

All hou.* calls happen on the main thread. The worker never touches hou.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    from PySide6 import QtCore
except ImportError:
    from PySide2 import QtCore

from .tool_bridge import get_tool_dispatch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ToolRequest -- data object shared between worker thread and main thread
# ---------------------------------------------------------------------------

@dataclass
class ToolRequest:
    """Request object passed from worker thread to main-thread executor.

    The worker creates this, emits it via signal, then calls
    ``done.wait(timeout=30.0)`` to block until the executor finishes.

    Attributes:
        tool_use_id: The ``id`` from the Anthropic API tool_use content block.
        tool_name:   MCP tool name (e.g. ``"create_node"``).
        tool_input:  Tool arguments dict from the API.
        result:      Set by executor on success (response.data).
        error:       Set by executor on failure (error message string).
        done:        Threading event -- set by executor when processing is complete.
    """
    tool_use_id: str
    tool_name: str
    tool_input: dict
    result: Any = field(default=None, repr=False)
    error: Optional[str] = None
    done: threading.Event = field(default_factory=threading.Event, repr=False)


# ---------------------------------------------------------------------------
# ToolExecutor -- QObject living on the main thread
# ---------------------------------------------------------------------------

class ToolExecutor(QtCore.QObject):
    """Executes Synapse tool calls on Houdini's main thread.

    Created by the panel (which itself lives on the main thread).
    The worker thread connects its signal to :meth:`execute_tool`; Qt's
    ``AutoConnection`` ensures the slot runs on the main thread.

    Usage::

        executor = ToolExecutor()       # in panel setup (main thread)
        worker.tool_signal.connect(executor.execute_tool)

        # In worker thread:
        req = ToolRequest(tool_use_id="tu_abc", tool_name="create_node",
                          tool_input={"type": "geo", "path": "/obj"})
        worker.tool_signal.emit(req)
        req.done.wait(timeout=30.0)
        if req.error:
            ...  # handle error
        else:
            ...  # use req.result
    """

    def __init__(self, parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self._handler = None  # Lazy-loaded SynapseHandler

    # ------------------------------------------------------------------
    # Lazy handler initialisation
    # ------------------------------------------------------------------

    def _get_handler(self):
        """Lazy-load SynapseHandler to avoid importing hou at module level.

        Returns the cached handler instance, or None if the import fails
        (e.g. running outside Houdini).
        """
        if self._handler is not None:
            return self._handler

        try:
            from synapse.server.handlers import SynapseHandler
            self._handler = SynapseHandler()
            logger.debug("SynapseHandler initialised for ToolExecutor")
        except Exception:
            logger.exception("Failed to import/create SynapseHandler")
            # Leave self._handler as None so we retry next call
        return self._handler

    # ------------------------------------------------------------------
    # Main-thread slot
    # ------------------------------------------------------------------

    @QtCore.Slot(object)
    def execute_tool(self, request: ToolRequest) -> None:
        """Execute a tool request on the main thread.

        Connected to the worker's signal via Qt AutoConnection, which
        guarantees this runs on the thread that owns the ToolExecutor
        (the main thread).

        Args:
            request: The ToolRequest to process. On return, either
                ``request.result`` or ``request.error`` will be set,
                and ``request.done`` will be signalled.
        """
        try:
            # 1. Resolve tool name to (command_type, payload_builder)
            dispatch = get_tool_dispatch(request.tool_name)
            if dispatch is None:
                request.error = f"Unknown tool: {request.tool_name}"
                logger.warning("No dispatch for tool %r", request.tool_name)
                return

            cmd_type, payload_builder = dispatch

            # 2. Build payload from tool input
            payload = payload_builder(request.tool_input)

            # 3. Create SynapseCommand
            from synapse.core.protocol import SynapseCommand
            command = SynapseCommand(
                type=cmd_type,
                id=f"panel-{request.tool_name}-{int(time.time() * 1000)}",
                payload=payload,
            )

            # 4. Get handler (lazy init)
            handler = self._get_handler()
            if handler is None:
                request.error = (
                    "SynapseHandler unavailable -- "
                    "hou module may not be loaded yet"
                )
                return

            # 5. Dispatch
            response = handler.handle(command)

            # 6. Transfer result
            if response.success:
                request.result = response.data
            else:
                request.error = response.error or "Tool execution failed"

        except Exception as exc:
            logger.exception(
                "Unhandled exception executing tool %r", request.tool_name
            )
            request.error = f"Exception: {exc}"

        finally:
            # ALWAYS signal done -- the worker thread is blocking on this
            request.done.set()
