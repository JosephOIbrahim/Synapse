"""Bounded local job observations; no Houdini, UI, persistence or model access.

The versioned anchor survives the panel loader's synapse.* module refresh.
Entries are observations, not proof that output files or pixels are valid.
"""
from __future__ import annotations

import copy
import sys
import threading
import time
import types
import uuid

_ANCHOR_NAME = "_synapse_job_events_v1"
_TERMINAL = frozenset({"completed", "failed", "cancelled", "preview", "unknown"})
_DEFAULT_POLICY = {"quiet": False, "desktop": False, "completions": True, "connections": True}


def _text(value, limit=400):
    # Never stringify an arbitrary object (including an exception/result).
    if type(value) is not str:
        return ""
    return " ".join("".join(c if c.isprintable() else " " for c in value[:limit]).split())


def _identity(value):
    if (type(value) is dict and set(value) == {"session_id", "generation"}
            and type(value["session_id"]) is int and 0 <= value["session_id"] < 2**63
            and type(value["generation"]) is str):
        return {"session_id": value["session_id"], "generation": _text(value["generation"], 128)}
    return None


def _fields(category, title, detail, state, source, node, scene, identity, context_id):
    return {"state": state, "category": _text(category, 40), "title": _text(title, 120),
            "detail": _text(detail), "source": _text(source, 120), "node": _text(node, 512),
            "scene": _text(scene, 1024), "identity": _identity(identity),
            "context_id": _text(context_id, 128)}


class JobJournal:
    """One locked authority; consumer snapshots never hold producer objects."""

    def __init__(self, max_entries=200):
        self._cap = max(1, min(200, max_entries)) if type(max_entries) is int else 200
        self._lock = threading.RLock()
        self._entries = {}
        self._meta = {}
        self._revision = self._sequence = self._dropped = 0
        self._instance_id = uuid.uuid4().hex
        self._policy = dict(_DEFAULT_POLICY)
        self._policy_initialized = False

    def _advance(self):
        self._revision += 1
        self._sequence += 1
        return self._sequence

    def _alert_allowed(self, entry):
        if self._policy["quiet"] or not self._policy["desktop"]:
            return False
        if entry["category"] == "connection":
            return self._policy["connections"]
        if entry["state"] in {"completed", "preview"}:
            return self._policy["completions"]
        return entry["state"] in {"failed", "unknown", "cancelled"}

    def _suppress_pending(self):
        for key, entry in self._entries.items():
            if not self._alert_allowed(entry):
                meta = self._meta[key]
                meta["claimed_sequence"] = meta["eligible_sequence"]

    def _make_room(self):
        if len(self._entries) < self._cap:
            return True
        for key, entry in self._entries.items():
            if entry["state"] != "running":
                del self._entries[key]
                del self._meta[key]
                self._dropped += 1
                return True
        self._dropped += 1
        self._advance()
        return False

    def _insert(self, category, title, *, source, state, detail="", node="", scene="",
                identity=None, context_id="", job_id=None, dedupe_key=None):
        if job_id is not None and (type(job_id) is not str or not job_id or len(job_id) > 128):
            return None
        key = job_id or uuid.uuid4().hex
        if key in self._entries:
            return key  # IDs never retarget or restart a retained job.
        if not self._make_room():
            return None
        sequence = self._advance()
        now = time.time()
        entry = {"id": key, "sequence": sequence, "change_sequence": sequence,
                 **_fields(category, title, detail, state, source, node, scene, identity, context_id),
                 "created_at": now, "updated_at": now,
                 "unread": state != "running"}
        self._entries[key] = entry
        eligible = state in _TERMINAL or entry["category"] == "connection"
        self._meta[key] = {"dedupe_key": dedupe_key, "conflicted": False,
                           "eligible_sequence": sequence if eligible else 0,
                           "claimed_sequence": sequence if eligible and not self._alert_allowed(entry) else 0}
        return key

    def start(self, category, title, *, source, node="", scene="", identity=None,
              context_id="", job_id=None):
        with self._lock:
            return self._insert(category, title, source=source, state="running", node=node,
                                scene=scene, identity=identity, context_id=context_id, job_id=job_id)

    def finish(self, job_id, state, detail=""):
        if type(job_id) is not str:
            return False
        if type(state) is str and state == "running":
            return False
        state = state if type(state) is str and state in _TERMINAL else "unknown"
        with self._lock:
            entry = self._entries.get(job_id)
            if entry is None:
                return False
            meta = self._meta[job_id]
            if entry["state"] != "running":
                if entry["state"] == state or meta["conflicted"]:
                    return False
                if entry["state"] not in _TERMINAL:
                    return False
                state = "unknown"
                detail = "Conflicting outcome reports; inspect the source job."
                meta["conflicted"] = True
            sequence = self._advance()
            entry.update(state=state, detail=_text(detail), updated_at=time.time(),
                         unread=True, change_sequence=sequence)
            meta["eligible_sequence"] = sequence
            # Publication under a suppressed policy is consumed immediately;
            # a later opt-in cannot replay it before a panel's first poll.
            if not self._alert_allowed(entry):
                meta["claimed_sequence"] = sequence
            return True

    def note(self, category, title, detail, *, state="info", source="", dedupe_key=None,
             node="", scene="", identity=None, context_id=""):
        state = state if type(state) is str and state in _TERMINAL | {"info"} else "unknown"
        # Dedupe metadata lives only as long as its bounded retained entry.
        key = _text(dedupe_key, 160) or None
        fields = _fields(category, title, detail, state, source, node, scene, identity, context_id)
        with self._lock:
            if key is not None:
                for entry_id in reversed(self._meta):
                    meta = self._meta[entry_id]
                    if meta["dedupe_key"] == key:
                        entry = self._entries[entry_id]
                        if fields["category"] == entry["category"] == "connection":
                            if any(entry[name] != value for name, value in fields.items()):
                                break  # Preserve each transition, comparing only the latest.
                        elif state in _TERMINAL and entry["state"] in _TERMINAL:
                            # A report ID is one terminal observation, never a new
                            # successful job after a failed or incomplete report.
                            self.finish(entry_id, state, detail)
                        return entry_id
            return self._insert(category, title, source=source, state=state, detail=detail,
                                node=node, scene=scene, identity=identity, context_id=context_id,
                                dedupe_key=key)

    def snapshot(self):
        with self._lock:
            entries = copy.deepcopy(list(self._entries.values()))
            return {"instance_id": self._instance_id, "revision": self._revision,
                    "sequence": self._sequence,
                    "oldest_sequence": min((e["sequence"] for e in entries), default=self._sequence + 1),
                    "entries": entries, "dropped": self._dropped}

    def mark_read(self, ids=None):
        with self._lock:
            selected = set(self._entries) if ids is None else {
                key for key in ids if type(key) is str
            } if type(ids) in (list, tuple, set, frozenset) else set()
            changed = [entry for key, entry in self._entries.items() if key in selected and entry["unread"]]
            if not changed:
                return False
            sequence = self._advance()
            for entry in changed:
                entry.update(unread=False, change_sequence=sequence)
            return True

    def clear_finished(self):
        with self._lock:
            keys = [key for key, entry in self._entries.items() if entry["state"] != "running"]
            for key in keys:
                del self._entries[key]
                del self._meta[key]
            if keys:
                self._advance()
            return len(keys)

    def get_policy(self):
        with self._lock:
            return dict(self._policy)

    def _set_policy(self, policy):
        if type(policy) is dict:
            valid = {key: value for key, value in policy.items()
                     if key in _DEFAULT_POLICY and type(value) is bool}
            if any(self._policy[key] != value for key, value in valid.items()):
                self._policy.update(valid)
                self._advance()
                # Muting or disabling consumes already pending alerts too,
                # even if no panel polls until after the next policy change.
                self._suppress_pending()
        self._policy_initialized = True
        return dict(self._policy)

    def set_policy(self, policy):
        with self._lock:
            return self._set_policy(policy)

    def initialize_policy(self, policy):
        with self._lock:
            return dict(self._policy) if self._policy_initialized else self._set_policy(policy)

    def claim_alerts(self, after_sequence):
        if type(after_sequence) is not int or after_sequence < 0:
            return []
        with self._lock:
            claimed = []
            for key, entry in self._entries.items():
                meta = self._meta[key]
                sequence = meta["eligible_sequence"]
                if sequence <= after_sequence or sequence <= meta["claimed_sequence"]:
                    continue
                # Claim even when suppressed: enabling later cannot replay it.
                meta["claimed_sequence"] = sequence
                if self._alert_allowed(entry):
                    claimed.append(copy.deepcopy(entry))
            return claimed


def get_journal():
    anchor = sys.modules.get(_ANCHOR_NAME)
    if anchor is None:
        candidate = types.ModuleType(_ANCHOR_NAME)
        candidate.journal = JobJournal()
        # A competing import can only see a fully initialized authority.
        anchor = sys.modules.setdefault(_ANCHOR_NAME, candidate)
    return anchor.journal


def classify_render_result(result):
    """Only known, primitive outcome fields; never retain a result or its text."""
    if type(result) is not dict:
        return "unknown", "The render returned no recognized outcome."
    raw_status = result.get("status")
    status = raw_status.strip().lower() if type(raw_status) is str else None
    if result.get("success") is False or any(
        result.get(key) is True
        or (type(result.get(key)) in (str, list, tuple, dict) and bool(result.get(key)))
        for key in ("error", "errors")
    ) or (type(status) is str and status in {"error", "failed", "failure", "blocked", "unavailable"}):
        return "failed", "The render reported a failure."
    malformed_flags = any(key in result and type(result[key]) is not bool
                          for key in ("success", "cancelled", "flipbook_fallback"))
    malformed_errors = any(result.get(key) is not None
                           and type(result[key]) not in (bool, str, list, tuple, dict)
                           for key in ("error", "errors"))
    if malformed_flags or malformed_errors:
        return "unknown", "The render returned malformed outcome fields; its final outcome is unconfirmed."
    if result.get("cancelled") is True or (type(status) is str and status in {"cancelled", "canceled"}):
        return "cancelled", "The render reported cancellation."
    if result.get("flipbook_fallback") is True or status == "preview":
        return "preview", "A viewport preview was produced; this is not a finished render."
    if raw_status is not None:
        if type(status) is str and status in {"done", "completed", "complete", "success", "succeeded", "ok", "rendered"}:
            return "completed", "The render operation returned successfully; output quality was not validated."
        return "unknown", "The render returned an unconfirmed outcome."
    if type(result.get("image_path")) is str and result["image_path"].strip():
        return "completed", "The render returned an image result; output quality was not validated."
    return "unknown", "The render returned no recognized outcome."


def observe_render_start(meta=None, *, job_id=None, source="render_session"):
    try:
        meta = meta if type(meta) is dict else {}
        return get_journal().start("render", "Render", source=source, node=meta.get("rop", ""),
                                   scene=meta.get("scene", ""), identity=meta.get("identity"),
                                   context_id=meta.get("context_id", ""), job_id=job_id)
    except Exception:
        return None


def observe_render_result(job_id, result):
    try:
        state, detail = classify_render_result(result)
        get_journal().finish(job_id, state, detail)
    except Exception:
        pass


def observe_render_exception(job_id, exc):
    try:
        cancelled = type(exc).__name__ in {"OperationCancelled", "OperationInterrupted", "CancelledError", "KeyboardInterrupt"}
        get_journal().finish(job_id, "cancelled" if cancelled else "failed",
                             "The render was interrupted." if cancelled else "The render raised an error; inspect its source result.")
    except Exception:
        pass


def observe_inline_render(callback, payload, *, node=""):
    job_id = observe_render_start({"rop": node}, source="render_inline")
    try:
        result = callback(payload)
    except BaseException as exc:
        observe_render_exception(job_id, exc)
        raise
    observe_render_result(job_id, result)
    return result


def observe_batch_report(report):
    """Observe the terminal report only: no invented start or cancellation."""
    try:
        total, passed, failed = report.total_frames, report.successful_frames, report.failed_frames
        if (any(type(n) is not int or n < 0 for n in (total, passed, failed))
                or total == 0 or passed + failed != total):
            state, detail = "unknown", "The batch report is incomplete; its final outcome is unconfirmed."
        elif failed:
            state, detail = "failed", f"The batch report records {failed} failed frame(s) out of {total}."
        elif report.settings_restore_error:
            state, detail = "unknown", "Frames were reported successful, but restoring render settings reported an error."
        else:
            state, detail = "completed", f"The batch report records {passed} successful frame(s)."
        return get_journal().note("render", "Render batch report", detail, state=state,
                                  source="render_batch_report", node=report.rop_path,
                                  dedupe_key="batch:" + report._notification_id)
    except Exception:
        return None
