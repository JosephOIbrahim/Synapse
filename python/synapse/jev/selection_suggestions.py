"""Optional semantic ranking for local selection-action prompt preparation.

The public API has no wait/result/join method, provider choice, tool list or
scene-data argument. Failures keep every fixed action in deterministic order.
An artist still chooses a local template and separately sends it to the selected
generator. Exact TypeSafe permission is checked by the existing fenced adapter
and again before a cached ranking can be consumed.
"""
from __future__ import annotations

import copy
import hashlib
import re
import sys
import threading
import time
import types

from . import adapter
from .panel_routing import project_request
from .selection_actions import ACTIONS, VERSION, questions

# No paths are needed to judge these public action descriptions. Skip the
# request, rather than redact it into an apparently complete interpretation.
_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\|(?:^|[\s\"'`(])/(?:obj|stage|mat|shop|out|top|img|ch|tasks)(?:/|\b)|(?:^|[\s\"'`(])(?:~/|/(?:[^\s/]+/)+))", re.I)
_candidate = types.ModuleType("_synapse_jev_suggestions_v1")
_candidate.slot = threading.BoundedSemaphore(1)
_JOBS = sys.modules.setdefault(_candidate.__name__, _candidate)
del _candidate


def _default(generation_key, *, status="unavailable", reason="not_requested"):
    return {"generation_key": generation_key, "status": status, "source": "default",
            "reason": reason, "question_version": VERSION,
            "ordered_actions": [{"id": action.id, "score": None} for action in ACTIONS]}


def _project(latest_text):
    state, reason = project_request([{"role": "user", "content": latest_text}])
    if reason:
        return None, reason
    if _PATH.search(state["artist_request"]):
        return None, "private_or_scene_request"
    # The old routing projection has an unknown network-kind field. Ranking
    # needs only the latest text; no scene-derived categories are accepted.
    return {"artist_request": state["artist_request"]}, None


def _cancelled(record):
    try:
        return (record.cancelled.is_set() or not record.scope.active
                or (record.grant is not None and not record.grant.active)
                or not adapter.enabled(opt_in=True) or bool(record.should_abort()))
    except Exception:
        return True


def _permission(record):
    """Local observation only: no grant minting, network or generic consent."""
    if _cancelled(record):
        return False
    try:
        from synapse import model_access as access
        key = adapter.resolve_key()
        if not key:
            return False
        access.require_access(adapter.connection_spec(), key=key, grant=record.grant,
                              scope=record.scope)
        return not _cancelled(record)
    except Exception:
        return False


class _Request:
    def __init__(self, identity, generation_key, scope, grant, should_abort):
        self.identity = identity
        self.generation_key = generation_key
        self.scope = scope
        self.grant = grant
        self.should_abort = should_abort or (lambda: False)
        self.cancelled = threading.Event()
        self.view = _default(generation_key, status="pending", reason=None)


class SuggestionService:
    """One retained request/result per caller; one active service job globally.

    Reuse the same accepted scope/grant for unchanged input within a suggestion
    lifecycle. The caller increments ``generation_key`` when its local input or
    observed selection changes, discards stale reads, and calls ``cancel`` on
    close, Stop, or preference changes. The service never mutates that scope.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._current = None
        self._generation = -1

    def request(self, latest_text, *, generation_key, scope, grant=None,
                enabled=False, should_abort=None):
        """Return immediately. Same input reuses a pending/completed ranking.

        A terminal fallback is not automatically retried for the same key.
        After failure/cancel, a new explicit request with a higher generation
        key may retry, including with the same still-authorized scope/input.
        """
        if type(generation_key) is not int or not 0 <= generation_key < 2 ** 63:
            return _default(None, status="discarded", reason="invalid_generation")
        state, reason = _project(latest_text)
        digest = hashlib.sha256(state["artist_request"].encode()).digest() if state else None
        identity = (digest, id(scope), id(grant), bool(enabled))
        with self._lock:
            if generation_key < self._generation:
                return _default(generation_key, status="discarded", reason="stale_generation")
            prior = self._current
            same_input = prior is not None and prior.identity == identity
            reusable = same_input and (generation_key == self._generation or (
                prior.view["status"] in ("pending", "ranked") and not prior.cancelled.is_set()))
            if reusable:
                self._generation = generation_key
                prior.generation_key = generation_key
                prior.should_abort = should_abort or (lambda: False)
                prior.view["generation_key"] = generation_key
                record = prior
                start = False
            else:
                if prior is not None:
                    prior.cancelled.set()
                self._generation = generation_key
                record = _Request(identity, generation_key, scope, grant, should_abort)
                self._current = record
                start = False
                if not enabled or not adapter.enabled(opt_in=True):
                    record.view = _default(generation_key, status="disabled", reason="off")
                elif reason:
                    record.view = _default(generation_key, reason=reason)
                elif _cancelled(record):
                    record.view = _default(generation_key, status="discarded", reason="cancelled")
                elif not _JOBS.slot.acquire(blocking=False):
                    record.view = _default(generation_key, reason="busy")
                else:
                    start = True
        if start:
            try:
                threading.Thread(target=self._rank, args=(record, state),
                                 name="synapse-jev-suggestions", daemon=True).start()
            except Exception:
                _JOBS.slot.release()
                self._publish(record, _default(generation_key, reason="thread_start"))
        return self.snapshot(generation_key)

    def snapshot(self, generation_key):
        """Copy current typed data; stale/cancelled/revoked rankings fall back."""
        if type(generation_key) is not int or not 0 <= generation_key < 2 ** 63:
            return _default(None, status="discarded", reason="invalid_generation")
        with self._lock:
            record = self._current
            if record is None or generation_key != self._generation:
                return _default(generation_key, status="discarded", reason="stale_generation")
            view = copy.deepcopy(record.view)
        if view["status"] in ("pending", "ranked") and _cancelled(record):
            record.cancelled.set()
            view = _default(generation_key, status="discarded", reason="cancelled")
            self._publish(record, view)
        elif view["source"] == "jev" and not _permission(record):
            record.cancelled.set()
            view = _default(generation_key, status="discarded", reason="permission_or_scope")
            self._publish(record, view)
        with self._lock:
            if record is not self._current or generation_key != self._generation:
                return _default(generation_key, status="discarded", reason="stale_generation")
            return copy.deepcopy(view)

    def cancel(self):
        """Invalidate publication immediately; never wait or revoke a shared task."""
        with self._lock:
            record = self._current
            if record is not None:
                record.cancelled.set()
                record.view = _default(self._generation, status="discarded", reason="cancelled")

    def _publish(self, record, view):
        with self._lock:
            if record is self._current:
                if record.cancelled.is_set() and view["source"] == "jev":
                    view = _default(self._generation, status="discarded", reason="cancelled")
                view["generation_key"] = self._generation
                record.view = view

    def _rank(self, record, state):
        started = time.perf_counter()
        transport = {}
        view = _default(record.generation_key, reason="unavailable")
        try:
            batch = questions()
            result = adapter.judge(state, batch, lane="selection-action-transport", mode="on",
                model=adapter.DEFAULT_MODEL, scope=record.scope, grant=record.grant,
                should_abort=lambda: _cancelled(record), opt_in=True, receipt=transport)
            if _cancelled(record):
                view = _default(record.generation_key, status="discarded", reason="cancelled")
            elif result is None:
                # Only fixed reason values enter this layer's UI/receipt.
                reason = transport.get("reason")
                if reason not in {"off", "busy", "deadline", "no_key", "permission_or_scope",
                                  "request_too_large", "invalid_request"}:
                    reason = "unavailable"
                view = _default(record.generation_key, reason=reason)
            elif not _permission(record):
                view = _default(record.generation_key, status="discarded", reason="permission_or_scope")
            else:
                checked = adapter._validated(result, batch)
                # Stable sort keeps the public order for equal scores. No
                # confidence threshold hides an action or authorizes a tool.
                ranked = sorted(ACTIONS, key=lambda item: -checked["answers"][item.id]["score"])
                view = {"generation_key": record.generation_key, "status": "ranked", "source": "jev",
                        "reason": None, "question_version": VERSION,
                        "ordered_actions": [{"id": item.id, "score": checked["answers"][item.id]["score"]}
                                            for item in ranked]}
        except Exception:
            view = _default(record.generation_key, reason="invalid_response")
        finally:
            if _cancelled(record):
                view = _default(record.generation_key, status="discarded", reason="cancelled")
            self._publish(record, view)
            # No input text, paths, scope identity, caller key or raw service
            # response. Scores/IDs have been validated against the fixed batch.
            try:
                adapter._ledger("selection-actions", {
                    "question_version": VERSION, "status": view["status"], "source": view["source"],
                    "reason": view["reason"], "ordered_actions": view["ordered_actions"],
                    "elapsed_ms": round((time.perf_counter() - started) * 1000., 3),
                })
            finally:
                _JOBS.slot.release()
