"""usage_sink — the token-spend receipt: per TASK, and folded across the SESSION.

WHY THIS EXISTS. Every provider adapter publishes the API's own usage report on
``provider.last_usage`` after ``stream()`` — Anthropic since W5-PANEL item 3;
Ollama / Custom / Nemotron via the OpenAI ``usage`` chunk and Gemini via
``usageMetadata`` since J2 (RULING_JOE_FIVE.md, 2026-09-05) — and the worker
folds it in here after every call. This module is the one hop that carries that
receipt from the worker's tool loop to the Token tab: the worker writes, and
FaceToken reads on its tab-open / task-done refresh (token_readout).

TWO UNITS. A TASK is one artist message through the whole tool loop:
``provider.last_usage`` is RESET at the start of every ``stream()``, so per-task
spend is the SUM across the loop's calls (``begin_task`` opens one, ``add`` folds
one call). The SESSION (J2) is every task since ``clear()``: ``begin_task`` never
resets it, and it is also kept per (provider, model) so a session that changed
engines can still be priced honestly (providers/model_facts.session_cost).

HONESTY (R162 — the house rule this whole Token face is built around). A field
the API never reported stays ``None`` — "not measured" — and the tab renders it
UNKNOWN, never zero. A zero is a claim; only a zero the API actually reported
(folded as an ``int``) is shown as ``0``. Nothing here is ever estimated. A
provider that reports nothing folds no fields and the face says "not reported
by <provider>" — correct, not a fake zero. The context window is likewise the
provider's own figure or ``None`` (``set_context_window``), and ``last_prompt``
— the context the model actually held on its LAST call — is only ever the sum
of that call's reported prompt-side fields.

Pure Python: no Qt, no ``hou``. The worker writes from its background QThread and
the Token tab reads on the Qt main thread, so every mutation is under a lock.
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

# The prompt side of a call: what the model held in context.
_PROMPT_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")

# Wire field -> the Token tab's own vocabulary (``cache_read`` / ``cache_creation``),
# decoupled from the raw Anthropic names so the display layer never learns the
# wire format.
_KEYS = (
    ("input_tokens", "input_tokens"),
    ("output_tokens", "output_tokens"),
    ("cache_read_input_tokens", "cache_read"),
    ("cache_creation_input_tokens", "cache_creation"),
)


def _is_count(value):
    """Only ``int`` values land — ``bool`` is an ``int`` subclass and must never
    be read as a token count (the provider ``_merge_usage`` / C1 guard)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _view(totals):
    """Wire-keyed totals -> the tab's vocabulary; an absent field is ``None``."""
    g = totals.get
    return {dst: g(src) for src, dst in _KEYS}


class UsageSink:
    """The latest task's per-field token totals (folded across its API calls),
    plus the session's running totals since ``clear()``."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset_all()

    def _reset_all(self):
        self._begun = False
        self._reset_task(None, None)
        self._session_totals = {}
        self._session_runs = 0
        self._session_tasks = 0
        self._session_by_model = {}      # (provider, model) -> {field: int}

    def _reset_task(self, model, provider):
        self._model = model
        self._reported_models = []
        self._provider = provider
        self._runs = 0
        # field -> summed int. A field ABSENT from this dict was never reported
        # by the API for this task, and must render UNKNOWN (never 0).
        self._totals = {}
        self._last_prompt = None
        self._context_window = None
        self._context_source = None

    def _open_task(self, model, provider):
        self._begun = True
        self._reset_task(model, provider)
        self._session_tasks += 1
        self._session_by_model.setdefault((provider, model), {})

    def begin_task(self, model=None, provider=None):
        """Open a new task, discarding the previous one's TASK totals.

        Called once at the top of the worker's conversation loop so the snapshot
        reports THIS task's spend, not a lifetime running total. ``model`` is the
        provider's ``model_identity`` — the SELECTED model that will do the
        spending; ``provider`` its ``id`` (J2), which is what the face names in
        "not reported by <provider>" and what model_facts prices by. The SESSION
        accumulators are NOT reset here — only ``clear()`` does that. The context
        window starts unknown for every task (a new task may be a new model).
        """
        with self._lock:
            self._open_task(model, provider)

    def add(self, usage):
        """Fold one API call's ``provider.last_usage`` into the current task.

        ``usage`` is a dict of Anthropic-shaped usage fields, or ``None``. ``None``
        means the call reported no usage (a provider that does not report, or a
        stream that failed / aborted before usage arrived): the run is still
        counted, but no field is invented. The same fold lands on the session
        totals and on the session's (provider, model) part. ``last_prompt`` is
        THIS call's prompt side (input + cache read + cache creation) — the
        context the model actually held — or ``None`` when it reported none.
        """
        with self._lock:
            if not self._begun:
                # A call before begin_task (defensive): open implicitly so a real
                # receipt is never dropped on the floor. Model stays unknown.
                self._open_task(None, None)
            self._runs += 1
            self._session_runs += 1
            if not isinstance(usage, dict):
                self._last_prompt = None
                return
            part = self._session_by_model.setdefault((self._provider, self._model), {})
            prompt = None
            for field in _FIELDS:
                value = usage.get(field)
                if not _is_count(value):
                    continue
                self._totals[field] = self._totals.get(field, 0) + value
                self._session_totals[field] = self._session_totals.get(field, 0) + value
                part[field] = part.get(field, 0) + value
                if field in _PROMPT_FIELDS:
                    prompt = (prompt or 0) + value
            self._last_prompt = prompt

    def set_reported_model(self, model):
        """Keep API-reported identity separate from the requested alias."""
        if not isinstance(model, str) or not model or len(model) > 256 or any(ord(c) < 32 for c in model):
            return
        with self._lock:
            if model not in self._reported_models:
                self._reported_models.append(model)

    def set_context_window(self, window, source=None):
        """Record the model's context window for the current task (J2): the
        provider's OWN figure (``provider.context_window()``) and where it came
        from, or ``None`` = "not reported by <provider>". Only an int > 0 lands."""
        with self._lock:
            if _is_count(window) and window > 0:
                self._context_window = window
                self._context_source = source
            else:
                self._context_window = None
                self._context_source = None

    def snapshot(self):
        """The current task's spend, or ``None`` if no task has run.

        Every task field is the summed total, or ``None`` if the API never
        reported it for this task (⇒ UNKNOWN in the UI, never zero). Keys are the
        Token tab's own vocabulary. J2 adds ``provider``, ``context_window`` /
        ``context_source``, ``last_prompt`` and ``session`` — the sums since
        ``clear()`` plus ``runs`` (API calls), ``tasks`` and ``by_model`` (one
        part per (provider, model) that spent, for honest session pricing).
        """
        with self._lock:
            if not self._begun:
                return None
            snap = {"model": self._model, "runs": self._runs}
            snap.update(_view(self._totals))
            snap.update({
                "provider": self._provider,
                "reported_models": list(self._reported_models),
                "context_window": self._context_window,
                "context_source": self._context_source,
                "last_prompt": self._last_prompt,
            })
            session = _view(self._session_totals)
            session.update({
                "runs": self._session_runs,
                "tasks": self._session_tasks,
                "by_model": [
                    dict({"provider": pid, "model": model}, **_view(totals))
                    for (pid, model), totals in self._session_by_model.items()
                ],
            })
            snap["session"] = session
            return snap

    def clear(self):
        """Drop all state — task AND session (tests / teardown)."""
        with self._lock:
            self._reset_all()


# Process-wide singleton: the worker writes, the Token tab reads. The TASK half
# is the LAST task's receipt (begin_task discards the previous one); the SESSION
# half runs until clear(). Refreshed on tab-open (face_token.refresh_from_probe)
# and on task completion (synapse_panel._on_done -> token_readout).
USAGE_SINK = UsageSink()
