"""Detached native TOPs backend. Public methods perform no HOM/Qt/model calls."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time
import uuid

from .package import (QUALIFIED_BUILD, atomic_json, isolated_environment,
                      owned_path, process_identity, read_json, validate_local_plan)


class NativeTopsBackend:
    """Build-pinned Karma CPU profile with durable, independently owned processes."""

    def __init__(self, hfs=None):
        self.hfs = Path(hfs or os.environ.get("SYNAPSE_FARM_HFS") or
                        "C:/Program Files/Side Effects Software/Houdini 22.0.400")
        self.driver = Path(__file__).with_name("native_driver.py")
        self._children = {}

    @staticmethod
    def _cancel_requested(plan, job_dir):
        marker = Path(job_dir) / "cancel-request.json"
        if not marker.is_file():
            return False
        cancel = read_json(marker)
        return (cancel.get("request_id") == plan["request_id"] and
                cancel.get("plan_digest") == plan["digest"])

    def _reap_children(self):
        for pid, child in tuple(self._children.items()):
            if child.poll() is not None:
                self._children.pop(pid, None)

    def capabilities(self):
        required = [self.hfs / "bin/hython.exe", self.hfs / "bin/husk.exe",
                    self.hfs / "python313/python.exe",
                    self.hfs / "houdini/python3.13libs/pdgjob/topcook.py"]
        missing = [str(path) for path in required if not path.is_file()]
        available = os.name == "nt" and not missing
        local_reason = ("Houdini {} files found. Preparation checks the runtime, license, "
                        "and portable scene. Karma CPU; per job: 2 threads, 1 task at a time; "
                        "120 frames, 2048 pixels, 128 samples maximum; 60 seconds per frame.").format(QUALIFIED_BUILD)
        if not available:
            local_reason = "This local profile needs the qualified Windows Houdini {} installation.".format(QUALIFIED_BUILD)
        return {"build": QUALIFIED_BUILD, "profiles": [
            {"id": "local", "label": "This computer", "available": available,
             "reason": local_reason, "missing": missing, "qualification": "bounded_preview",
             "limits": {"max_frames": 120, "max_width": 2048, "max_height": 2048,
                        "max_samples": 128, "frame_timeout_seconds": 60,
                        "threads": 2, "concurrent_tasks": 1}},
            {"id": "hqueue", "label": "Render farm", "available": False,
             "reason": "HQueue server, workers, shared storage and license concurrency have not been configured and qualified. No farm submission is available."}],
            "license_entitlement": "checked when a detached process starts; farm concurrency unknown"}

    def _launch(self, phase, plan, job_dir, record=None):
        self._reap_children()
        try:
            validate_local_plan(plan)
            if not self.capabilities()["profiles"][0]["available"]:
                raise ValueError(self.capabilities()["profiles"][0]["reason"])
        except ValueError as exc:
            return {"state": "failed", "note": str(exc), "verified_frames": [], "outputs": []}
        root = Path(job_dir).resolve()
        if self._cancel_requested(plan, root):
            return {"state": "cancelled", "note": "This request was cancelled before process admission.",
                    "verified_frames": [], "outputs": []}
        token = uuid.uuid4().hex
        operation = root / "native" / token
        operation.mkdir(parents=True, exist_ok=False)
        phase_timeout = min(3600, 90 + len(plan["frames"]) * (12 if phase == "prepare" else 65))
        prior = (record or {}).get("metadata", {})
        config = {"phase": phase, "plan": plan, "token": token,
                  "job_dir": str(root), "hfs": str(self.hfs),
                  "timeout_seconds": phase_timeout,
                  "manifest_digest": prior.get("package_digest")}
        atomic_json(operation / "config.json", config)
        env = isolated_environment(self.hfs, operation / "runtime")
        command = [str(self.hfs / "python313/python.exe"), "-B", str(self.driver),
                   "supervise", str(operation / "config.json")]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            with (operation / "supervisor.stdout.log").open("wb") as out, (operation / "supervisor.stderr.log").open("wb") as err:
                child = subprocess.Popen(command, cwd=str(operation), env=env,
                                         stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                                         creationflags=creationflags, close_fds=True)
            self._children[child.pid] = child
        except Exception as exc:
            return {"state": "failed", "note": "The detached process could not start: " + str(exc),
                    "verified_frames": [], "outputs": []}
        try:
            identity = process_identity(child.pid)
        except Exception:
            # Popen already admitted a process. Preserve its token and receipts;
            # identity lookup failure must never turn into an absent launch.
            identity = None
        metadata = dict(prior)
        metadata.update({"native_token": token, "native_phase": phase,
                         "native_operation": str(operation.relative_to(root)).replace("\\", "/"),
                         "supervisor": identity or {"pid": child.pid, "alive": None},
                         "started_at": time.time(), "timeout_seconds": phase_timeout})
        return {"state": "preparing" if phase == "prepare" else "rendering",
                "note": "Preparing the frozen scene and visible TOP graph." if phase == "prepare" else "Rendering the frozen TOP graph in a separate process.",
                "backend_id": "local:{}:{}".format(child.pid, token),
                "verified_frames": [], "outputs": [], "total_frames": len(plan["frames"]),
                "metadata": metadata}

    def prepare(self, plan, job_dir):
        return self._launch("prepare", plan, job_dir)

    def submit(self, plan, job_dir, record):
        if not record.get("metadata", {}).get("package_digest"):
            return {"state": "failed", "note": "The frozen package is not ready for submission.",
                    "verified_frames": [], "outputs": []}
        return self._launch("render", plan, job_dir, record)

    def _recover_metadata(self, plan, job_dir, record):
        meta = dict(record.get("metadata", {}))
        rendering = record.get("submission_attempted") or record.get("state") in (
            "rendering", "verifying", "submitting", "submission_uncertain", "complete")
        if record.get("state") in ("cancel_requested", "status_unavailable", "cancelled", "failed"):
            rendering = rendering or meta.get("native_phase") == "render"
        phase = "render" if rendering else "prepare"

        def matches(config, operation):
            saved = config["plan"]
            if (saved.get("request_id") != plan["request_id"] or
                    saved.get("digest") != plan["digest"] or config.get("phase") != phase or
                    config.get("token") != operation.name or
                    Path(config["job_dir"]).resolve() != Path(job_dir).resolve()):
                return False
            validate_local_plan(saved)
            return True

        # A lost submit acknowledgment commonly leaves the old prepare metadata
        # in the journal. Reuse it only when it identifies the current phase.
        if (meta.get("native_operation") and meta.get("native_token") and
                meta.get("native_phase") == phase):
            try:
                operation = self._operation(job_dir, {"metadata": meta})
                if matches(read_json(operation / "config.json"), operation):
                    return meta
            except (OSError, ValueError, KeyError, TypeError):
                pass
        native = Path(job_dir) / "native"
        candidates = []
        if native.is_dir() and not native.is_symlink():
            for operation in native.iterdir():
                if operation.is_symlink() or not operation.is_dir():
                    continue
                try:
                    config = read_json(operation / "config.json")
                    if not matches(config, operation):
                        continue
                    try:
                        owner = read_json(operation / "supervisor.json")
                    except (OSError, ValueError):
                        owner = None
                    candidates.append((operation, config, owner))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        if len(candidates) != 1:
            raise ValueError("Native launch recovery is ambiguous or has no durable process admission. No job will be relaunched.")
        operation, config, owner = candidates[0]
        if (not owner or owner.get("token") != config["token"] or
                owner.get("plan_digest") != plan["digest"] or not isinstance(owner.get("identity"), dict)):
            raise ValueError("The possible native launch has no durable process admission. No job will be relaunched.")
        meta.update({"native_operation": str(operation.relative_to(Path(job_dir))).replace("\\", "/"),
                     "native_token": config["token"], "native_phase": config["phase"],
                     "supervisor": owner["identity"], "timeout_seconds": config["timeout_seconds"],
                     "started_at": owner.get("started_at"), "recovered_from_native_receipt": True})
        if config.get("manifest_digest"):
            meta["package_digest"] = config["manifest_digest"]
        return meta

    def _operation(self, job_dir, record):
        meta = record.get("metadata", {})
        relative = meta.get("native_operation")
        token = meta.get("native_token")
        if not relative or not token:
            raise ValueError("The saved native process identity is unavailable.")
        path = owned_path(job_dir, relative)
        if path.name != token or path.parent.name != "native":
            raise ValueError("The native operation identity is invalid.")
        return path

    def poll(self, plan, job_dir, record):
        self._reap_children()
        try:
            meta = self._recover_metadata(plan, job_dir, record)
            operation = self._operation(job_dir, {"metadata": meta})
        except ValueError as exc:
            return {"state": "status_unavailable", "note": str(exc), "verified_frames": []}
        status_path = operation / "status.json"
        if status_path.is_file():
            status = read_json(status_path)
            if (status.get("token") != meta["native_token"] or
                    status.get("plan_digest") != plan["digest"]):
                raise ValueError("The native receipt belongs to another request.")
            if status.get("state") in ("prepared", "complete", "failed", "cancelled", "status_unavailable"):
                meta.update(status.get("metadata", {}))
                result = {k: status[k] for k in ("state", "note", "verified_frames", "outputs", "verification") if k in status}
                if (status.get("state") != "status_unavailable" and
                        self._cancel_requested(plan, job_dir)):
                    # The supervisor publishes terminal receipts only after its
                    # worker exits and its owned descendant group is closed.
                    # A late cancel therefore converges without accepting a
                    # completion that raced the core's cancellation fence.
                    result = {"state": "cancelled", "note": "The owned processes have stopped and this request is cancelled.",
                              "verified_frames": [], "outputs": []}
                result["metadata"] = meta
                result["backend_id"] = "local:{}:{}".format(meta.get("supervisor", {}).get("pid"), meta["native_token"])
                return result
        supervisor = meta.get("supervisor", {})
        current = process_identity(supervisor.get("pid", -1))
        same = current and current.get("alive") and current.get("birth") == supervisor.get("birth")
        if not same:
            return {"state": "status_unavailable", "note": "The detached controller is unavailable without a final receipt. Outputs remain unverified; this request will not be resubmitted automatically.",
                    "verified_frames": [], "metadata": meta}
        state = "cancel_requested" if (operation / "cancel.json").exists() else (
            "preparing" if meta["native_phase"] == "prepare" else "rendering")
        return {"state": state, "note": "Cancellation requested; waiting for the owned processes to stop." if state == "cancel_requested" else (
                    "Preparing the frozen scene and visible TOP graph." if state == "preparing" else "Rendering the frozen TOP graph."),
                "verified_frames": [], "metadata": meta}

    def cancel(self, plan, job_dir, record):
        pkg_cancel = {"request_id": plan["request_id"], "plan_digest": plan["digest"]}
        atomic_json(Path(job_dir) / "cancel-request.json", pkg_cancel)
        try:
            meta = self._recover_metadata(plan, job_dir, record)
        except ValueError:
            return {"state": "cancel_requested", "cancellation_delivered": True,
                    "note": "The stop request was delivered; process admission could not be confirmed.",
                    "verified_frames": record.get("verified_frames", []), "metadata": record.get("metadata", {})}
        record = dict(record, metadata=meta)
        operation = self._operation(job_dir, record)
        atomic_json(operation / "cancel.json", {"token": meta["native_token"],
                                                "plan_digest": plan["digest"]})
        status = self.poll(plan, job_dir, record)
        if status.get("state") == "cancelled":
            return dict(status, cancellation_delivered=True)
        return {"state": "cancel_requested", "cancellation_delivered": True,
                "note": "Cancellation requested for this render's owned processes.",
                "verified_frames": record.get("verified_frames", []), "metadata": record.get("metadata", {})}
