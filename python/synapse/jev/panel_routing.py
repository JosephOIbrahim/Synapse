"""Optional shadow measurements; never changes a generator or its inputs.

No Qt/hou, waits, tool calls, consent grants or live scene reads. The accepted
task scope crosses threads explicitly. All publication is input-free evidence.
"""
from __future__ import annotations

import copy
import re
import sys
import threading
import time
import types

from . import adapter
from .panel_questions import QUESTIONS, VERSION

MAX_REQUEST_CHARS = 4096
_PRIVATE = re.compile(
    r"```|-----BEGIN|\b(?:password|passwd|secret|token|api[ _-]?key|authorization|bearer)\b"
    r"|\b(?:sk|tsk)[_-][A-Za-z0-9_-]{8,}|\b(?:hou|pxr|pdg)\s*\."
    r"|(?:^|\n)\s*(?:from\s+\w+\s+import|import\s+\w+|def\s+\w+|class\s+\w+)"
    r"|[{}]", re.I)
_candidate = types.ModuleType("_synapse_jev_shadow_v1")
_candidate.slot = threading.BoundedSemaphore(1)
_JOBS = sys.modules.setdefault(_candidate.__name__, _candidate)
del _candidate


def project_request(messages, network_kind="unknown"):
    """Take only this task's latest plain-text artist request, never history.

    Oversized, multimodal, recognizable code/credential-bearing requests are
    skipped rather than truncated into an apparently complete interpretation.
    No heuristic can recognize every secret in free text; the separate sharing
    permission therefore explicitly covers the artist's latest request.
    """
    if not messages or not isinstance(messages[-1], dict) or messages[-1].get("role") != "user":
        return None, "no_artist_request"
    text = messages[-1].get("content")
    if not isinstance(text, str):
        return None, "non_text_request"
    # The panel can prefix dropped-node paths. They are not routing evidence.
    if text.startswith("[Context: ") and "]\n" in text:
        text = text.split("]\n", 1)[1]
    if not text.strip():
        return None, "empty_request"
    if len(text) > MAX_REQUEST_CHARS:
        return None, "request_too_large"
    if _PRIVATE.search(text) or any(ord(c) < 32 and c not in "\n\t" for c in text):
        return None, "private_or_code_request"
    context = network_kind if network_kind in ("solaris", "materialx", "sop") else "unknown"
    return {"artist_request": text.strip(), "context": {"network_kind": context}}, None


class ShadowJob:
    """A snapshot-only handle. Intentionally has no wait/join/result API."""
    def __init__(self, scope, provider, model):
        self._lock = threading.Lock()
        self._receipt = {"task_id": scope.task_id, "mode": "shadow", "question_version": VERSION,
                         "generator": {"provider": provider, "model": model},
                         "behavior_changed": False, "status": "pending"}

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._receipt)

    def _publish(self, **fields):
        with self._lock:
            self._receipt.update(fields)


def start_shadow(messages, *, scope, provider, model, should_abort, mode=None):
    """Start at most one measurement; return immediately without joining it."""
    job = ShadowJob(scope, provider, model)
    use_saved_mode = mode is None
    if mode is None:
        from synapse.panel.settings import load_settings
        mode = load_settings().get("jev_routing_mode", "off")
    if mode != "shadow" or not adapter.enabled(opt_in=True):
        job._publish(status="disabled", reason="off")
        return job
    state, reason = project_request(messages)
    if reason:
        job._publish(status="unavailable", reason=reason)
        return job
    if should_abort() or not scope.active:
        job._publish(status="discarded", reason="task_ended")
        return job
    if not _JOBS.slot.acquire(blocking=False):
        job._publish(status="unavailable", reason="busy")
        return job

    def measurement_ended():
        if should_abort() or not scope.active or not adapter.enabled(opt_in=True):
            return True
        if use_saved_mode:
            from synapse.panel.settings import load_settings
            return load_settings().get("jev_routing_mode", "off") != "shadow"
        return False

    def measure():
        started = time.perf_counter()
        transport = {}
        try:
            answer = adapter.judge(state, QUESTIONS, lane="panel-route-transport", mode="shadow",
                                   model=adapter.DEFAULT_MODEL, scope=scope,
                                   should_abort=measurement_ended, opt_in=True, receipt=transport)
            if measurement_ended():
                job._publish(status="discarded", reason="task_or_measurement_ended")
            elif answer is None:
                job._publish(status="unavailable", reason=transport.get("reason", "unavailable"))
            else:
                # Revalidate at consumption too; this is not an activation threshold.
                clean = adapter._validated(answer, QUESTIONS)
                job._publish(status="measured", judgments=clean["answers"],
                             reported_model=clean["model"])
        except Exception as exc:
            job._publish(status="unavailable", reason=type(exc).__name__)
        finally:
            job._publish(elapsed_ms=round((time.perf_counter() - started) * 1000., 3),
                         request_hash=transport.get("request_hash"))
            adapter._ledger("panel-routing", job.snapshot())
            _JOBS.slot.release()

    try:
        threading.Thread(target=measure, name="synapse-jev-shadow", daemon=True).start()
    except Exception:
        _JOBS.slot.release()
        job._publish(status="unavailable", reason="thread_start")
    return job
