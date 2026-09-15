"""Pure presentation and request binding for the artist Render workspace.

The farm service owns execution and verification. This module owns only an
editable form, its exact prepared binding, and conservative display decisions.
It imports no Qt, Houdini, storage owner, or model provider.
"""
from __future__ import annotations

from copy import deepcopy
import json
import ntpath
import os
import re
import uuid


STATES = frozenset((
    "preparing", "prepared", "submitting", "submission_uncertain", "rendering",
    "verifying", "complete", "failed", "cancel_requested", "cancelled",
    "status_unavailable",
))
ACTIVE_STATES = frozenset(("preparing", "submitting", "rendering", "verifying"))
POLL_STATES = ACTIVE_STATES | {"submission_uncertain", "cancel_requested", "status_unavailable"}
FORM_KEYS = ("source_hip", "source_node", "frames", "output_root", "profile_id", "width", "height", "samples")
DEFAULT_FORM = {
    "source_hip": "", "source_node": "", "frames": "1", "output_root": "",
    "profile_id": "local", "width": 256, "height": 256, "samples": 8,
}
_SHA256 = re.compile(r"^[a-fA-F0-9]{64}$")


class FarmResponseError(RuntimeError):
    """A missing, failed or unreadable tool response; never a job outcome."""


def decode_response(value):
    """Accept plain handler data and normal MCP envelopes, never fake success."""
    for _ in range(6):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError) as exc:
                raise FarmResponseError("The render service returned an unreadable response.") from exc
            continue
        if not isinstance(value, dict):
            raise FarmResponseError("The render service could not be reached or did not return a record.")
        if value.get("isError") is True or value.get("success") is False or value.get("status") == "error":
            error = value.get("error") or value.get("message") or value.get("content")
            if isinstance(error, dict):
                error = error.get("message") or error.get("error")
            if isinstance(error, list):
                error = " ".join(str(item.get("text", "")) for item in error if isinstance(item, dict))
            raise FarmResponseError(str(error or "The render service refused this request.")[:2000])
        if "structuredContent" in value and value["structuredContent"] is not None:
            value = value["structuredContent"]
            continue
        if isinstance(value.get("data"), dict):
            value = value["data"]
            continue
        if "content" in value and isinstance(value["content"], list):
            texts = [item.get("text") for item in value["content"]
                     if isinstance(item, dict) and item.get("type") == "text" and item.get("text")]
            if len(texts) != 1:
                raise FarmResponseError("The render service returned an unreadable response.")
            value = texts[0]
            continue
        if value.get("error") and not value.get("request_id"):
            raise FarmResponseError(str(value["error"])[:2000])
        return deepcopy(value)
    raise FarmResponseError("The render service response had too many wrappers.")


def perform_farm_call(tool_name, arguments, transport):
    """Injectable, model-free tool call, used by the background Qt worker."""
    return decode_response(transport(tool_name, deepcopy(arguments)))


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def expected_frames(job):
    plan = job.get("plan") if isinstance(job, dict) else None
    frames = plan.get("frames") if isinstance(plan, dict) else None
    if (not isinstance(frames, list) or not frames or
            any(not isinstance(frame, int) or isinstance(frame, bool) for frame in frames) or
            len(set(frames)) != len(frames)):
        return None
    return frames


def verified_output_paths(job):
    """Expose files only for a complete, internally consistent verified record."""
    if not isinstance(job, dict) or job.get("state") != "complete" or job.get("verified") is not True:
        return []
    expected = expected_frames(job)
    verification = job.get("verification") or {}
    if not expected or not isinstance(verification, dict) or verification.get("verified") is not True:
        return []
    for frames in (job.get("verified_frames"), verification.get("frames")):
        if (not isinstance(frames, list) or len(frames) != len(expected) or
                any(type(frame) is not int for frame in frames) or set(frames) != set(expected)):
            return []
    if job.get("total_frames") != len(expected):
        return []
    outputs = job.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != len(expected):
        return []
    covered, paths = set(), []
    plan = job.get("plan") or {}
    for output in outputs:
        if not isinstance(output, dict):
            return []
        path, frame = output.get("path"), output.get("frame")
        if (output.get("verified") is not True or frame not in expected or
                not isinstance(frame, int) or isinstance(frame, bool) or
                not isinstance(path, str) or not path or any(ord(char) < 32 for char in path) or
                not (os.path.isabs(path) or ntpath.isabs(path)) or
                not _SHA256.fullmatch(str(output.get("sha256", ""))) or
                not _positive_int(output.get("size")) or
                not _positive_int(output.get("width")) or not _positive_int(output.get("height")) or
                output.get("width") != plan.get("width") or output.get("height") != plan.get("height")):
            return []
        covered.add(frame)
        paths.append(path)
    if covered != set(expected) or len(paths) != len(set(paths)):
        return []
    return paths


def frame_text(frames):
    if isinstance(frames, str):
        return frames
    if not isinstance(frames, (list, tuple)) or not frames:
        return ""
    if len(frames) >= 3 and all(isinstance(f, int) and not isinstance(f, bool) for f in frames):
        step = frames[1] - frames[0]
        if step > 0 and all(b - a == step for a, b in zip(frames, frames[1:])):
            return "%d-%d%s" % (frames[0], frames[-1], "x%d" % step if step != 1 else "")
    return ", ".join(str(frame) for frame in frames)


def inspection_frame_text(frames):
    """Inspect returns a start/end/step triple, unlike a prepared frame list."""
    if isinstance(frames, (list, tuple)) and len(frames) == 3:
        start, end, step = frames
        if all(isinstance(f, int) and not isinstance(f, bool) for f in frames) and step > 0 and end >= start:
            return str(start) if start == end else "%d-%d%s" % (start, end, "x%d" % step if step != 1 else "")
    return frame_text(frames)


def form_from_plan(plan):
    form = dict(DEFAULT_FORM)
    if isinstance(plan, dict):
        form.update({key: deepcopy(plan[key]) for key in FORM_KEYS if key in plan})
    form["frames"] = frame_text(form["frames"])
    return form


def form_signature(form):
    return json.dumps({key: form.get(key) for key in FORM_KEYS}, sort_keys=True, separators=(",", ":"))


def prepared_summary(job):
    frames = expected_frames(job)
    if not frames:
        return "The service has not returned an exact frame selection."
    plan = job["plan"]
    metadata = job.get("metadata") or {}
    destination = metadata.get("output_directory") if isinstance(metadata, dict) else None
    if not destination and job.get("job_dir"):
        paths = ntpath if ntpath.splitdrive(job["job_dir"])[0] or "\\" in job["job_dir"] else os.path
        destination = paths.join(job["job_dir"], "outputs")
    return ("%d frame%s: %s\nSource: %s\nDestination: %s\n%s × %s · %s samples · %s" % (
        len(frames), "" if len(frames) == 1 else "s", frame_text(frames),
        plan.get("source_node", "Unknown"), destination or plan.get("output_root", "Unknown"),
        plan.get("width", 0), plan.get("height", 0), plan.get("samples", "Unknown"),
        "This computer" if plan.get("profile_id") == "local" else plan.get("profile_id", "Unknown")))


def job_presentation(job, *, observation_note=""):
    if not job:
        return {"state": "draft", "title": "Choose the render, then prepare it.", "note": observation_note,
                "verified": None, "total": None, "can_cancel": False, "can_open": False, "poll": False}
    if not isinstance(job, dict):
        job = {"state": "status_unavailable", "note": "The render record is unreadable."}
    state = job.get("state")
    if state not in STATES:
        state = "status_unavailable"
    expected = expected_frames(job)
    total = len(expected) if expected else (job.get("total_frames") if _positive_int(job.get("total_frames")) else None)
    verified = job.get("verified_frames")
    count = None
    if (expected and isinstance(verified, list) and
            all(isinstance(f, int) and not isinstance(f, bool) for f in verified) and
            len(verified) == len(set(verified)) and set(verified).issubset(set(expected))):
        count = len(verified)
    titles = {
        "preparing": "Preparing the scene and textures…", "prepared": "Prepared. Check the exact render below.",
        "submitting": "Sending this render…", "submission_uncertain": "The render may have started. Check its status.",
        "rendering": "Rendering…", "verifying": "Checking the rendered images…",
        "complete": "All %s frames are ready." % total, "failed": "This render needs attention.",
        "cancel_requested": "Cancellation requested. Waiting for the work to stop.",
        "cancelled": "Render cancelled.", "status_unavailable": "Status unavailable. The render may still be running.",
    }
    can_open = bool(verified_output_paths(job))
    if state == "complete" and not can_open:
        state = "status_unavailable"
        title = "The completion record is missing verified output evidence."
    else:
        title = titles[state]
    output_recheck = (job.get("state") == "status_unavailable" and
                      job.get("output_recheck_pending") is True and
                      job.get("error_code") == "output_unavailable")
    if observation_note:
        title = "Status unavailable. The render may still be running."
    if output_recheck:
        title = "The rendered images could not be checked. Refresh to check them again."
    return {"state": state, "title": title, "note": observation_note or str(job.get("note") or ""),
            "verified": count, "total": total,
            "can_cancel": not output_recheck and bool(job.get("request_id")) and job.get("state") in (
                ACTIVE_STATES | {"prepared", "submission_uncertain", "status_unavailable"}),
            "can_open": can_open and not observation_note, "poll": state in POLL_STATES or bool(observation_note)}


class RenderWorkspaceModel:
    """An explicit prepare/edit/submit state machine with no execution side effects."""

    def __init__(self, *, request_id_factory=None):
        self.form = dict(DEFAULT_FORM)
        self.job = None
        self.jobs = {}
        self.pending = None
        self.observation_note = ""
        self.form_revision = 0
        self._binding = None
        self._verified_before_recheck = {}
        self._new_id = request_id_factory or (lambda: uuid.uuid4().hex)

    def edit(self, values):
        updated = dict(self.form)
        updated.update({key: deepcopy(value) for key, value in values.items() if key in FORM_KEYS})
        if updated != self.form:
            self.form = updated
            self.form_revision += 1
            self._binding = None
        return self.form

    @property
    def can_submit(self):
        return bool(not self.pending and not self.observation_note and self.job and
                    self.job.get("state") == "prepared" and self.job.get("digest") and
                    expected_frames(self.job) and self._binding == (
                        self.job.get("request_id"), self.job.get("digest"), form_signature(self.form)))

    def begin_prepare(self):
        if self.pending:
            raise ValueError("Wait for the current render request.")
        if self.job and self.job.get("state") in POLL_STATES:
            raise ValueError("Check this request or choose New render before preparing another.")
        if not all(str(self.form.get(key) or "").strip() for key in ("source_hip", "source_node", "frames", "output_root")):
            raise ValueError("Choose a saved scene, source, frames and destination first.")
        payload = deepcopy(self.form)
        payload["request_id"] = self._new_id()
        self.pending = "prepare"
        self.observation_note = ""
        self._binding = (payload["request_id"], None, form_signature(self.form))
        self.job = {"request_id": payload["request_id"], "state": "preparing", "plan": deepcopy(self.form)}
        self.jobs[payload["request_id"]] = deepcopy(self.job)
        return payload

    def begin_submit(self):
        if not self.can_submit:
            raise ValueError("Prepare the current settings before rendering.")
        payload = {"request_id": self.job["request_id"], "digest": self.job["digest"]}
        self.pending = "submit"
        self.job = dict(self.job, state="submitting")
        return payload

    def begin_cancel(self):
        if self.pending or not job_presentation(self.job, observation_note=self.observation_note)["can_cancel"]:
            raise ValueError("This render cannot be cancelled from its current state.")
        self.pending = "cancel"
        self.job = dict(self.job, state="cancel_requested")
        return {"request_id": self.job["request_id"]}

    def receive_job(self, response, *, request_id=None):
        job = decode_response(response)
        rid = job.get("request_id")
        if not isinstance(rid, str) or not rid or job.get("state") not in STATES:
            raise FarmResponseError("The render service did not return a readable job record.")
        if request_id is not None and rid != request_id:
            raise FarmResponseError("The render service returned a different request. Check this request's status.")
        previous = self.jobs.get(rid) or {}
        old_revision, new_revision = previous.get("revision"), job.get("revision")
        if (isinstance(old_revision, int) and isinstance(new_revision, int) and new_revision < old_revision):
            return False
        output_invalidated = (previous.get("state") == "complete" and job["state"] == "failed" and
                              job.get("error_code") == "output_changed" and
                              type(old_revision) is int and type(new_revision) is int and new_revision > old_revision and
                              job.get("verified") is False and job.get("outputs") == [] and job.get("verified_frames") == [])
        newer = type(old_revision) is int and type(new_revision) is int and new_revision > old_revision
        same_identity = all(job.get(key) == previous.get(key) for key in (
            "request_id", "digest", "plan", "job_dir", "backend_id"))
        metadata, old_metadata = job.get("metadata") or {}, previous.get("metadata") or {}
        same_identity = same_identity and isinstance(metadata, dict) and isinstance(old_metadata, dict)
        for key in ("native_token", "native_phase"):
            same_identity = same_identity and metadata.get(key) == old_metadata.get(key)
        output_unavailable = (previous.get("state") == "complete" and
                              job["state"] == "status_unavailable" and
                              job.get("error_code") == "output_unavailable" and
                              job.get("output_recheck_pending") is True and newer and same_identity and
                              job.get("verified") is False and job.get("outputs") == [] and
                              job.get("verified_frames") == [] and job.get("verification") is None)
        recovering = (previous.get("state") == "status_unavailable" and
                      previous.get("output_recheck_pending") is True)
        recovery_conflict = False
        if recovering and job["state"] == "complete":
            anchor = self._verified_before_recheck.get(rid)
            recovery_conflict = (not newer or not same_identity or
                                 job.get("output_recheck_pending") is not False or
                                 job.get("cancellation_requested") is True or not verified_output_paths(job) or
                                 (anchor is not None and any(job.get(key) != anchor.get(key) for key in (
                                     "outputs", "verified_frames", "verification"))))
        elif recovering:
            empty = (job.get("verified") is False and job.get("outputs") == [] and
                     job.get("verified_frames") == [] and job.get("verification") is None)
            expected = ((job["state"] == "status_unavailable" and
                         job.get("output_recheck_pending") is True and job.get("error_code") == "output_unavailable") or
                        (job["state"] == "failed" and job.get("error_code") == "output_changed") or
                        (job["state"] in {"cancel_requested", "cancelled"} and job.get("cancellation_requested") is True))
            recovery_conflict = (not same_identity or not empty or not expected or
                                 type(old_revision) is not int or type(new_revision) is not int or new_revision < old_revision)
        if (previous.get("state") in {"complete", "cancelled", "failed"} and
                job["state"] != previous["state"] and not output_invalidated and not output_unavailable) or recovery_conflict:
            if self.job and self.job.get("request_id") == rid:
                self.pending = None
                self.observation_note = "The render service returned a conflicting terminal state. Check this request's status."
            return False
        if output_unavailable:
            self._verified_before_recheck[rid] = deepcopy(previous)
        elif recovering and job["state"] in {"complete", "failed", "cancelled"}:
            self._verified_before_recheck.pop(rid, None)
        self.jobs[rid] = deepcopy(job)
        if not self.job or self.job.get("request_id") != rid:
            return False
        self.pending = None
        self.observation_note = ""
        self.job = deepcopy(job)
        if job["state"] == "prepared" and self._binding and self._binding[0] == rid:
            if self._binding[2] == form_signature(self.form):
                # The service resolves frame syntax and paths; display that exact plan.
                self.form = form_from_plan(job.get("plan"))
                self._binding = (rid, job.get("digest"), form_signature(self.form))
        return True

    def transport_failed(self, action, message):
        self.pending = None
        note = str(message or "The render service could not be reached.")[:2000]
        if self.job and action in ("prepare", "submit", "cancel"):
            state = {"prepare": "status_unavailable", "submit": "submission_uncertain", "cancel": "cancel_requested"}[action]
            self.job = dict(self.job, state=state, note=note)
            self.jobs[self.job["request_id"]] = deepcopy(self.job)
            # Keep the binding so a later query can recover a definitely
            # prepared request. Only an explicit user submit can launch it.
        else:
            self.observation_note = note

    def select_job(self, request_id):
        if self.pending:
            raise ValueError("Wait for the current render request before changing jobs.")
        job = deepcopy(self.jobs[request_id])
        self.job = job
        self.form = form_from_plan(job.get("plan"))
        self.form_revision += 1
        self.observation_note = ""
        self._binding = ((request_id, job.get("digest"), form_signature(self.form))
                         if job.get("state") == "prepared" else None)
        return job

    def new_render(self):
        if self.pending:
            raise ValueError("Wait for the current render request.")
        self.job = None
        self._binding = None
        self.observation_note = ""
        self.form_revision += 1
