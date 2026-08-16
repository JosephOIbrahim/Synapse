"""usage_sink — the per-task token-spend receipt, folded across a turn's API calls.

WHY THIS EXISTS. ``AnthropicProvider`` publishes the four real Anthropic usage
fields on ``provider.last_usage`` after every ``stream()``
(providers/anthropic_provider.py), and until now nothing read them: the worker
called ``stream()`` and dropped the number, so the Token tab (face_token.py) showed
UNKNOWN forever — the "dead counter" Joe flagged on the live seat (W5-PANEL item 3).
This module is the one hop that carries that receipt from the worker's tool loop
to the Token tab, with no edit to the peer-claimed synapse_panel.py: the worker
writes, and FaceToken reads on its already-wired tab-open refresh.

THE UNIT IS A TASK, NOT A CALL. ``provider.last_usage`` is RESET to ``None`` at the
start of every ``stream()`` (anthropic_provider.py:176), so on a multi-tool-call
turn it holds only the LAST call's usage. Per-TASK spend is the SUM across the whole
tool loop, so the worker folds each call's ``last_usage`` in here.

HONESTY (R162 — the house rule this whole Token face is built around). A field the
API never reported stays ``None`` — "not measured" — and the tab renders it UNKNOWN,
never zero. A zero is a claim; only a zero the API actually reported (folded as an
``int``) is shown as ``0``. Nothing here is ever estimated. A non-Anthropic provider
(gemini/nemotron/ollama) never sets ``last_usage`` (base.py:42), so its task folds no
fields and every spend row stays UNKNOWN — correct, not a fake zero.

Pure Python: no Qt, no ``hou``. The worker writes from its background QThread and the
Token tab reads on the Qt main thread, so every mutation is under a lock.
"""

from __future__ import annotations

import threading

# The four real Anthropic usage fields, matching provider ``_USAGE_FIELDS``.
_FIELDS = (
    "input_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
    "output_tokens",
)


class UsageSink:
    """The latest task's per-field token totals, folded across its API calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self._begun = False
        self._model = None
        self._runs = 0
        # field -> summed int. A field ABSENT from this dict was never reported
        # by the API for this task, and must render UNKNOWN (never 0).
        self._totals = {}

    def begin_task(self, model=None):
        """Open a new task, discarding the previous one's totals.

        Called once at the top of the worker's conversation loop so the snapshot
        reports THIS task's spend, not a lifetime running total. ``model`` is the
        provider's ``model_identity`` — the SELECTED model that will do the spending.
        """
        with self._lock:
            self._begun = True
            self._model = model
            self._runs = 0
            self._totals = {}

    def add(self, usage):
        """Fold one API call's ``provider.last_usage`` into the current task.

        ``usage`` is a dict of Anthropic usage fields, or ``None``. ``None`` means the
        call reported no usage (a non-Anthropic provider, or a stream that failed/
        aborted before usage arrived): the run is still counted, but no field is
        invented. Only ``int`` values land — ``bool`` is an ``int`` subclass and must
        never be read as a token count (the same guard as the provider's
        ``_merge_usage`` and the C1 agent-loop meter).
        """
        with self._lock:
            if not self._begun:
                # A call before begin_task (defensive): open implicitly so a real
                # receipt is never dropped on the floor. Model stays unknown.
                self._begun = True
                self._runs = 0
                self._totals = {}
            self._runs += 1
            if not isinstance(usage, dict):
                return
            for field in _FIELDS:
                value = usage.get(field)
                if isinstance(value, int) and not isinstance(value, bool):
                    self._totals[field] = self._totals.get(field, 0) + value

    def snapshot(self):
        """The current task's spend, or ``None`` if no task has run.

        Every field is the summed total, or ``None`` if the API never reported it
        for this task (⇒ UNKNOWN in the UI, never zero). Keys are the Token tab's
        own vocabulary (``cache_read`` / ``cache_creation``), decoupled from the raw
        Anthropic field names so the display layer never learns the wire format.
        """
        with self._lock:
            if not self._begun:
                return None
            g = self._totals.get
            return {
                "model": self._model,
                "runs": self._runs,
                "input_tokens": g("input_tokens"),
                "output_tokens": g("output_tokens"),
                "cache_read": g("cache_read_input_tokens"),
                "cache_creation": g("cache_creation_input_tokens"),
            }

    def clear(self):
        """Drop all state (tests / teardown)."""
        with self._lock:
            self._begun = False
            self._model = None
            self._runs = 0
            self._totals = {}


# Process-wide singleton: the worker writes, the Token tab reads. It holds ONE
# task's spend at a time — the tab is a read-out of the LAST task, refreshed when
# the artist opens it (face_token.refresh_from_probe, already wired).
USAGE_SINK = UsageSink()
