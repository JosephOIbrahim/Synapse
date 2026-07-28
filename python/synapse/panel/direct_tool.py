"""Off-UI-thread single-tool dispatch for the panel (H3b).

WHY
---
Every artist control in ``synapse_panel.py`` today funnels back into
``_send()`` -- i.e. through a Claude turn. That is wrong for a *cancel*: the
whole point of stopping a cook or halting the pipeline is that it must work
while the agent loop is busy, and an LLM turn is exactly the thing that is
busy. ``_on_stop``'s own comment has said so since it was written:

    (Cancelling the in-flight tool itself -- tops_cancel_cook / render cancel
     -- must run off the UI thread against a live bridge; deferred ...)

This module is that missing half. It calls ONE named tool directly, with no
model in the loop, on a worker thread.

WHY OFF-THREAD IS NOT OPTIONAL
------------------------------
``tool_executor.try_mcp_tool_call`` documents its own contract:

    Safe to call from any thread (worker threads, background threads).
    NOT safe to call from the main thread (will deadlock with hdefereval).

A Qt menu action runs ON the main thread. Calling it inline would deadlock the
UI against the very marshal it needs, which is the same self-deadlock class
recorded for ``hdefereval`` blocking marshals. So the call goes to a QThread
and the result comes back by signal.

THE READER
----------
``extract_node_path`` recovers the target node from the tool-status ``detail``
string. That string is produced by ``claude_worker.py`` as
``json.dumps(tool_input)[:120]`` -- i.e. **truncated to 120 characters**, so it
is frequently not valid JSON. A reader that only tried ``json.loads`` would
return None on exactly the long payloads a real cook produces, and the cancel
control would look wired while silently never finding a target.

That is a reader blind spot of the R60 class, so the reader is a pure function
with its own paired controls in tests/test_h3b_panel_cancel.py: it is proved to
recover a path from truncated JSON, and proved to return None when there is
genuinely no node in the payload.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

try:  # PySide6 first, PySide2 fallback -- the panel's own idiom
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover
    try:
        from PySide2.QtCore import QThread, Signal
    except ImportError:  # pragma: no cover - headless import for tests
        QThread = object
        Signal = None


# Keys a tool payload may use for "the node this is about", in preference
# order. `node` is the canonical one _handle_tops_cancel_cook requires.
_NODE_KEYS = ("node", "node_path", "top_node", "topnet", "parent_path", "path")

# Fallback for TRUNCATED detail strings, which are not parseable JSON.
# Matches  "node": "/tasks/topnet1"  even when the closing brace was cut off.
_NODE_RE = re.compile(
    r'"(?:%s)"\s*:\s*"([^"]+)"' % "|".join(_NODE_KEYS)
)

# Last resort: any quoted absolute Houdini path in the fragment, for the case
# where truncation cut the key name off but left the value. Deliberately
# refuses FILE-looking paths -- a truncated payload can easily leave an output
# path visible while hiding the node key, and cancelling "a cook on
# /mnt/shots/a.exr" is a wrong target rather than a missing one.
_ANY_PATH_RE = re.compile(r'"(/[A-Za-z0-9_/:$-]+(?:\.[A-Za-z0-9_]+)?)"')


def _looks_like_a_file(path: str) -> bool:
    """True when the last segment carries an extension (e.g. a.exr, x.usd)."""
    tail = path.rsplit("/", 1)[-1]
    return "." in tail


def extract_node_path(detail: Optional[str]) -> Optional[str]:
    """Recover a node path from a (possibly truncated) tool-input fragment.

    Returns None when the payload genuinely carries no node -- that negative
    case is what makes this a check rather than a decoration.
    """
    if not detail:
        return None
    text = detail.strip()

    # 1. Whole, valid JSON -- the easy case.
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in _NODE_KEYS:
                val = parsed.get(key)
                if isinstance(val, str) and val.startswith("/"):
                    return val
            return None          # valid JSON, no node key: honest None
    except (ValueError, TypeError):
        pass

    # 2. Truncated fragment -- recover by key name.
    m = _NODE_RE.search(text)
    if m and m.group(1).startswith("/"):
        return m.group(1)

    # 3. Truncated fragment with the key itself cut off -- any absolute path
    #    that is not obviously a file on disk.
    for candidate in _ANY_PATH_RE.findall(text):
        if not _looks_like_a_file(candidate):
            return candidate
    return None


def is_cookish_tool(name: Optional[str]) -> bool:
    """Is this tool the kind whose in-flight work a cook-cancel can reach?

    Used only to decide whether the panel offers 'Cancel cook' as enabled.
    Deliberately conservative: TOPS/PDG cook entry points only.
    """
    if not name:
        return False
    n = name.lower()
    if n.startswith("synapse_"):
        n = n[len("synapse_"):]
    return n in {
        "tops_cook_node", "tops_batch_cook", "tops_cook_and_validate",
        "tops_generate_items", "tops_render_sequence", "tops_multi_shot",
        "cook_pdg_chain",
    }


class DirectToolCall(QThread):
    """Run ONE named SYNAPSE tool off the UI thread. No model in the loop.

    ``finished_ok(dict)`` on success, ``failed(str)`` on any error. Both are
    terminal and exactly one fires -- a control that can silently do neither is
    a control the artist cannot trust.
    """

    if Signal is not None:  # pragma: no branch
        finished_ok = Signal(object)
        failed = Signal(str)

    def __init__(self, tool_name: str, arguments: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._tool_name = tool_name
        self._arguments = dict(arguments or {})

    def run(self):  # pragma: no cover - exercised live in Houdini
        try:
            from synapse.panel.tool_executor import try_mcp_tool_call
        except Exception as exc:
            self.failed.emit("Tool transport unavailable: %s" % exc)
            return
        try:
            result = try_mcp_tool_call(self._tool_name, self._arguments)
        except Exception as exc:
            logger.warning("direct tool %s failed", self._tool_name,
                           exc_info=True)
            self.failed.emit(str(exc))
            return
        if result is None:
            # try_mcp_tool_call returns None when MCP is unreachable. Saying
            # "done" here would be the exact defect R18 names: an affordance
            # reporting a safety action it did not perform.
            self.failed.emit(
                "Couldn't reach the SYNAPSE server, so nothing was cancelled. "
                "Check the bridge is connected and try again."
            )
            return
        self.finished_ok.emit(result)
