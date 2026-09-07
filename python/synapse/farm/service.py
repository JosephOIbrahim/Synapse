"""Durable artist-reviewed requests, with an explicitly uncertain launch seam."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import uuid

from .models import (FarmError, canonical_json, canonical_plan, get_constants,
                     validate_request_id)
from .store import FarmStore, now
from .verification import verify_completion

_TERMINAL = {"complete", "failed", "cancelled"}
_BACKEND_STATES = {"preparing", "prepared", "rendering", "verifying", "complete",
                   "failed", "cancel_requested", "cancelled", "status_unavailable"}
_MAX_RECEIPT_BYTES = 2 * 1024 * 1024


def _public(record: dict) -> dict:
    return deepcopy({key: value for key, value in record.items()
                     if not key.startswith("_")})


class FarmService:
    """One controller journal and a backend that owns detached execution.

    Backend calls and file verification run outside all journal locks. A durable
    admission flag, not a transient status or in-memory object, prevents repeat
    submission after restart or lost acknowledgement. Operation tokens prevent
    late observations from replacing a newer decision, especially cancellation.
    No public read starts, resumes or retries a render.
    """

    def __init__(self, root, backend):
        self.store = FarmStore(root)
        self.backend = backend

    def capabilities(self) -> dict:
        try:
            result = self.backend.capabilities()
            if type(result) is not dict:
                raise TypeError("Backend capabilities must be an object")
            result = deepcopy(result)
            canonical_json(result)
        except Exception as exc:
            result = {"available": False, "status": "unavailable",
                      "note": f"Render capabilities are unavailable ({type(exc).__name__})."}
        result["limits"] = get_constants()
        return result

    def prepare(self, payload: dict) -> dict:
        plan = canonical_plan(payload)
        request_id = plan["request_id"]
        job_dir = Path(plan["output_root"]) / "synapse_renders" / request_id
        stamp, token = now(), uuid.uuid4().hex
        record = {"request_id": request_id, "digest": plan["digest"],
                  "plan": plan, "job_dir": str(job_dir), "state": "preparing",
                  "note": "Preparing a frozen scene and TOPs render plan.",
                  "backend_id": None, "verified_frames": [],
                  "total_frames": len(plan["frames"]), "outputs": [],
                  "verified": False, "verification": None, "metadata": {},
                  "submission_attempted": False, "cancellation_requested": False,
                  "created_at": stamp, "updated_at": stamp, "revision": 1,
                  "_operation": token, "_phase": "prepare"}
        record, created = self.store.reserve(record)
        if not created:
            return _public(record)
        try:
            # A new request never consumes a pre-existing output/cache directory.
            parent = job_dir.parent
            if parent.is_symlink() or getattr(parent, "is_junction", lambda: False)():
                raise OSError("Render request parent is a filesystem link")
            job_dir.mkdir(parents=True, exist_ok=False)
            if not job_dir.resolve().is_relative_to(Path(plan["output_root"])):
                raise OSError("Render folder escaped its output root")
        except OSError as exc:
            return self._record_exception(request_id, token, "prepare",
                FarmError("output_unavailable", "The new render folder could not be created. Choose a writable output folder and a new request ID."))
        current = self.store.get(request_id)
        if current["cancellation_requested"] or current["state"] in _TERMINAL:
            return _public(current)
        try:
            result = self.backend.prepare(deepcopy(plan), job_dir)
        except Exception as exc:
            return self._record_exception(request_id, token, "prepare", exc)
        return self._record_result(request_id, token, "prepare", result)

    def submit(self, request_id: str, digest: str) -> dict:
        request_id = validate_request_id(request_id)
        token = uuid.uuid4().hex
        def admit(record):
            if type(digest) is not str or digest != record["digest"]:
                raise FarmError("digest_mismatch", "The reviewed render plan changed. Prepare and review the current plan before rendering.")
            if record["submission_attempted"] or record["cancellation_requested"]:
                return None
            if record["state"] != "prepared":
                raise FarmError("invalid_state", "This render plan is not ready to submit. Refresh its preparation status first.")
            record.update(state="submitting", note="Submitting the reviewed render plan.",
                          submission_attempted=True, submitted_at=now(),
                          _operation=token, _phase="submit")
            return record
        record = self.store.update(request_id, admit)
        if record.get("_operation") != token:
            return _public(record)
        current = self.store.get(request_id)
        if current["cancellation_requested"] or current["state"] in _TERMINAL:
            return _public(current)
        try:
            result = self.backend.submit(deepcopy(record["plan"]),
                                         Path(record["job_dir"]), _public(record))
        except Exception as exc:
            return self._record_exception(request_id, token, "submit", exc)
        return self._record_result(request_id, token, "submit", result)

    def get_job(self, request_id: str) -> dict:
        record = self.store.get(validate_request_id(request_id))
        if record is None:
            raise FarmError("job_not_found", "This render request is not in the farm journal.")
        return _public(record)

    def list_jobs(self, limit: int = 20) -> list[dict]:
        return [_public(record) for record in self.store.list(limit)]

    def refresh(self, request_id: str) -> dict:
        request_id, token = validate_request_id(request_id), uuid.uuid4().hex
        def observe(record):
            if record["state"] in _TERMINAL or record["state"] == "prepared":
                return None
            record["_operation"] = token
            return record
        record = self.store.update(request_id, observe)
        if record.get("_operation") != token:
            if record["state"] == "complete":
                return self._recheck_complete(record)
            return _public(record)
        try:
            result = self.backend.poll(deepcopy(record["plan"]),
                                       Path(record["job_dir"]), _public(record))
        except Exception as exc:
            return self._record_exception(request_id, token, "poll", exc)
        return self._record_result(request_id, token, "poll", result)

    def _recheck_complete(self, observed: dict) -> dict:
        """A fresh observation may invalidate a previously accepted output set."""
        try:
            verify_completion(observed["plan"], Path(observed["job_dir"]), observed)
        except Exception as exc:
            def invalidate(record):
                if (record["state"] != "complete" or record["revision"] != observed["revision"]
                        or record["cancellation_requested"]):
                    return None
                record["_last_verified_receipt"] = {
                    "outputs": record["outputs"], "verification": record["verification"],
                    "verified_frames": record["verified_frames"], "updated_at": record["updated_at"]}
                record.update(state="failed", error_code="output_changed", verified=False,
                              outputs=[], verified_frames=[], verification=None,
                              note="Previously verified images are missing, changed or could not be read. This render will not be resubmitted automatically.")
                return record
            return _public(self.store.update(observed["request_id"], invalidate))
        return _public(self.store.get(observed["request_id"]))

    def cancel(self, request_id: str) -> dict:
        request_id, token = validate_request_id(request_id), uuid.uuid4().hex
        def fence(record):
            if record["state"] in _TERMINAL or record["cancellation_requested"]:
                return None
            record.update(state="cancel_requested", cancellation_requested=True,
                          note="Stopping this render; waiting for the backend to confirm.",
                          verified=False, verification=None, verified_frames=[], outputs=[],
                          _operation=token)
            return record
        record = self.store.update(request_id, fence)
        if record.get("_operation") != token:
            return _public(record)
        try:
            result = self.backend.cancel(deepcopy(record["plan"]),
                                         Path(record["job_dir"]), _public(record))
        except Exception as exc:
            return self._record_exception(request_id, token, "cancel", exc)
        return self._record_result(request_id, token, "cancel", result)

    def _record_exception(self, request_id, token, action, exc):
        def apply(record):
            if record.get("_operation") != token or record["state"] in _TERMINAL:
                return None
            if record["cancellation_requested"]:
                record.update(state="cancel_requested",
                              note=f"Stop was requested; backend confirmation is unavailable ({type(exc).__name__}).")
            elif isinstance(exc, FarmError):
                record.update(state="failed", note=exc.message, error_code=exc.code)
            elif action == "submit":
                record.update(state="submission_uncertain",
                              note=f"Submission acknowledgement is unavailable ({type(exc).__name__}). Refresh status; this request will not be submitted twice.")
            else:
                record.update(state="status_unavailable",
                              note=f"Render status is unavailable ({type(exc).__name__}). Refresh to check the existing request.")
            return record
        return _public(self.store.update(request_id, apply))

    def _record_result(self, request_id, token, action, result):
        current = self.store.get(request_id)
        if current.get("_operation") != token and type(result) is dict and result.get("state") == "cancelled":
            # A cancel request supersedes an in-flight launch token. Its late
            # cancellation acknowledgement still proves that active phase stopped.
            # A former preparation cannot certify a subsequently admitted render.
            same_phase = ((action == "prepare" and not current["submission_attempted"])
                          or (action == "submit" and current["submission_attempted"])
                          or action == "cancel")
            if same_phase and current["cancellation_requested"] and current["state"] == "cancel_requested":
                def confirm(record):
                    if (record["cancellation_requested"] and record["state"] == "cancel_requested"
                            and record["submission_attempted"] == current["submission_attempted"]):
                        record.update(state="cancelled", note="The backend confirmed this render request has stopped.",
                                      outputs=[], verified_frames=[], verified=False, verification=None)
                        return record
                    return None
                return _public(self.store.update(request_id, confirm))
        if current.get("_operation") != token or current["state"] in _TERMINAL:
            return _public(current)
        try:
            if type(result) is not dict or len(canonical_json(result).encode("utf-8")) > _MAX_RECEIPT_BYTES:
                raise TypeError("Backend receipt must be a bounded object")
            result = deepcopy(result)
            state = result.get("state")
            if state not in _BACKEND_STATES:
                raise TypeError("Backend returned an unrecognized state")
            note = result.get("note", "")
            if type(note) is not str or type(result.get("metadata", {})) is not dict:
                raise TypeError("Backend note and metadata must be plain values")
            backend_id = result.get("backend_id")
            if backend_id is not None and (type(backend_id) is not str or len(backend_id) > 1024):
                raise TypeError("Backend ID must be a bounded string")
            outputs = []
            if state == "complete" and not current["cancellation_requested"]:
                if not current["submission_attempted"]:
                    raise FarmError("unexpected_completion", "The backend reported output completion before this plan was submitted.")
                outputs = verify_completion(current["plan"], Path(current["job_dir"]), result)
        except Exception as exc:
            return self._record_exception(request_id, token, action, exc)

        def apply(record):
            if record.get("_operation") != token or record["state"] in _TERMINAL:
                return None
            if backend_id is not None:
                record["backend_id"] = backend_id
            record["metadata"].update(result.get("metadata", {}))
            # Cancellation is a permanent acceptance fence, including late success.
            if state in {"cancel_requested", "cancelled"}:
                record["cancellation_requested"] = True
            if record["cancellation_requested"]:
                record["state"] = "cancelled" if state == "cancelled" else "cancel_requested"
                record["note"] = note[:2000] if state == "cancelled" else "Stop was requested; waiting for the backend to confirm it has stopped."
                record.update(verified=False, verification=None, outputs=[], verified_frames=[])
                return record
            if record["submission_attempted"] and state in {"prepared", "preparing"}:
                record.update(state="submission_uncertain",
                              note="The backend has not confirmed the submitted render. This request will not be submitted again automatically.")
                return record
            if not record["submission_attempted"] and state in {"rendering", "verifying"}:
                record.update(state="failed", error_code="unexpected_execution",
                              note="The backend started rendering before the prepared plan was submitted.")
                return record
            record["state"], record["note"] = state, note[:2000]
            if state == "complete":
                record.update(outputs=outputs, verified=True,
                              verified_frames=list(record["plan"]["frames"]),
                              verification={"verified": True, "frames": list(record["plan"]["frames"])})
            # Progress is not output verification. Only the final verified set
            # advances verified_frames; raw task progress can remain in metadata.
            return record
        return _public(self.store.update(request_id, apply))
