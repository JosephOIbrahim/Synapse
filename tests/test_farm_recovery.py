"""Independent failure-sequence probes. Never launches Houdini or a render."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import sys

import pytest

WORKTREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKTREE / "python"))
from synapse.farm import backend as native_module
from synapse.farm import package
from synapse.farm.backend import NativeTopsBackend
from synapse.farm.service import FarmService
from synapse.farm import verification
from synapse.farm.models import FarmError
from synapse.farm.native_driver import _cancelled


class ReceiptBackend:
    def prepare(self, plan, job_dir):
        return {"state": "prepared", "metadata": {"package_digest": "review-fixture"}}

    def submit(self, plan, job_dir, record):
        return {"state": "rendering"}


@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("This review must never launch a subprocess")
    monkeypatch.setattr(native_module.subprocess, "Popen", prohibited)


def admitted_render(tmp_path, monkeypatch):
    scene = tmp_path / "fixture.hiplc"
    scene.write_bytes(b"Synthetic scene identity; never parsed by Houdini")
    journal = tmp_path / "journal"
    service = FarmService(journal, ReceiptBackend())
    prepared = service.prepare({"request_id": "cancel-delivery", "source_hip": str(scene),
        "source_node": "/stage/OUT", "frames": [1, 2], "output_root": str(tmp_path / "output")})
    record = service.submit(prepared["request_id"], prepared["digest"])
    root = Path(record["job_dir"])
    operation = root / "native" / "review-token"
    operation.mkdir(parents=True)
    package.atomic_json(operation / "config.json", {"phase": "render", "token": "review-token",
        "plan": record["plan"], "job_dir": str(root), "timeout_seconds": 60})
    identity = {"pid": 2147483000, "birth": "synthetic-review-only", "alive": True}
    package.atomic_json(operation / "supervisor.json", {"token": "review-token",
        "plan_digest": record["digest"], "identity": identity})
    monkeypatch.setattr(native_module, "process_identity", lambda pid: dict(identity))
    service.backend = NativeTopsBackend()
    return service, record, root


def test_cancel_retry_delivers_after_transient_marker_failure(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    real_atomic = native_module.atomic_json
    calls = []

    def one_transient_error(path, value):
        calls.append(str(path))
        if len(calls) == 1:
            raise OSError("Simulated output share outage before cancellation marker delivery")
        return real_atomic(path, value)

    monkeypatch.setattr(native_module, "atomic_json", one_transient_error)
    first = service.cancel(record["request_id"])
    assert first["state"] == "cancel_requested"
    assert not (root / "cancel-request.json").exists()
    # The output directory is writable again. Restart the authority, observe,
    # and explicitly request cancellation again; no execution is relaunched.
    reopened = FarmService(service.store.root, NativeTopsBackend())
    observed = reopened.refresh(record["request_id"])
    repeated = reopened.cancel(record["request_id"])
    operation = root / "native/review-token"
    supervisor_observes_cancel = _cancelled(operation, package.read_json(operation / "config.json"))
    evidence = {"initial": first["state"], "after_reopen_poll": observed["state"],
        "repeated_cancel": repeated["state"], "marker_write_attempts": len(calls),
        "request_marker_exists": (root / "cancel-request.json").exists(),
        "operation_marker_exists": (root / "native/review-token/cancel.json").exists(),
        "supervisor_observes_cancel": supervisor_observes_cancel}
    (tmp_path / "cancel-delivery-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert (root / "cancel-request.json").exists(), evidence
    assert supervisor_observes_cancel is True
    assert observed["cancellation_delivery_pending"] is False
    assert repeated["cancellation_requested"] is True
    writes_after_delivery = len(calls)
    assert reopened.refresh(record["request_id"])["state"] == "cancel_requested"
    assert len(calls) == writes_after_delivery  # Delivery acknowledged; only observe the worker now.


def test_direct_native_cancel_can_deliver_the_marker(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    result = service.backend.cancel(record["plan"], root, record)
    assert result["state"] == "cancel_requested"
    assert (root / "cancel-request.json").is_file()
    assert (root / "native/review-token/cancel.json").is_file()
    operation = root / "native/review-token"
    assert _cancelled(operation, package.read_json(operation / "config.json")) is True


def test_lost_cancel_ack_after_delivery_is_observable(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    real_cancel = service.backend.cancel

    def lose_reply(*args):
        real_cancel(*args)
        raise TimeoutError("Simulated lost acknowledgement after marker delivery")

    monkeypatch.setattr(service.backend, "cancel", lose_reply)
    assert service.cancel(record["request_id"])["state"] == "cancel_requested"
    assert (root / "cancel-request.json").is_file()
    operation = root / "native/review-token"
    package.atomic_json(operation / "status.json", {"state": "cancelled", "token": "review-token",
        "plan_digest": record["digest"], "metadata": {"owned_processes_stopped": True}})
    reopened = FarmService(service.store.root, NativeTopsBackend())
    assert reopened.refresh(record["request_id"])["state"] == "cancelled"


def test_cancel_before_prepare_dispatch_can_confirm_no_worker(tmp_path, monkeypatch):
    scene = tmp_path / "fixture.hiplc"
    scene.write_bytes(b"Synthetic fixture; no Houdini parsing")
    service = FarmService(tmp_path / "journal", NativeTopsBackend())
    payload = {"request_id": "cancel-before-prepare", "source_hip": str(scene),
        "source_node": "/stage/OUT", "frames": [1], "output_root": str(tmp_path / "out")}
    reserve = service.store.reserve

    def cancel_immediately_after_reservation(record):
        result = reserve(record)
        service.cancel(record["request_id"])
        return result

    monkeypatch.setattr(service.store, "reserve", cancel_immediately_after_reservation)
    first = service.prepare(payload)
    root = Path(first["job_dir"])
    assert (root / "cancel-request.json").is_file()
    assert not (root / "native").exists()
    reopened = FarmService(service.store.root, NativeTopsBackend())
    observed = reopened.refresh(payload["request_id"])
    assert observed["state"] == "cancelled", {"initial": first["state"], "after_reopen": observed["state"],
        "note": observed["note"], "native_operation_exists": (root / "native").exists()}


def test_cancel_before_submit_dispatch_can_confirm_no_worker(tmp_path, monkeypatch):
    scene = tmp_path / "fixture.hiplc"
    scene.write_bytes(b"Synthetic fixture; no Houdini parsing")
    service = FarmService(tmp_path / "journal", ReceiptBackend())
    prepared = service.prepare({"request_id": "cancel-before-submit", "source_hip": str(scene),
        "source_node": "/stage/OUT", "frames": [1], "output_root": str(tmp_path / "out")})
    root = Path(prepared["job_dir"])
    operation = root / "native" / "prepared-token"
    operation.mkdir(parents=True)
    package.atomic_json(operation / "config.json", {"phase": "prepare", "token": "prepared-token",
        "plan": prepared["plan"], "job_dir": str(root), "timeout_seconds": 60})
    package.atomic_json(operation / "supervisor.json", {"token": "prepared-token",
        "plan_digest": prepared["digest"], "identity": {"pid": 2147483000, "birth": "synthetic", "alive": False}})
    package.atomic_json(operation / "status.json", {"state": "prepared", "token": "prepared-token",
        "plan_digest": prepared["digest"], "metadata": {"owned_processes_stopped": True}})
    service.backend = NativeTopsBackend()
    update = service.store.update
    cancelled = False

    def cancel_immediately_after_submit_admission(request_id, change):
        nonlocal cancelled
        record = update(request_id, change)
        if record["state"] == "submitting" and not cancelled:
            cancelled = True
            service.cancel(request_id)
        return record

    monkeypatch.setattr(service.store, "update", cancel_immediately_after_submit_admission)
    first = service.submit(prepared["request_id"], prepared["digest"])
    assert not any(package.read_json(path).get("phase") == "render" for path in root.glob("native/*/config.json"))
    reopened = FarmService(service.store.root, NativeTopsBackend())
    observed = reopened.refresh(prepared["request_id"])
    assert observed["state"] == "cancelled", {"initial": first["state"], "after_reopen": observed["state"], "note": observed["note"]}


def test_restart_delivers_cancel_after_crash_between_fence_and_dispatch(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    update = service.store.update

    class SimulatedHostCrash(BaseException):
        pass

    def commit_then_crash(request_id, change):
        result = update(request_id, change)
        if result["cancellation_requested"]:
            raise SimulatedHostCrash()
        return result

    monkeypatch.setattr(service.store, "update", commit_then_crash)
    with pytest.raises(SimulatedHostCrash):
        service.cancel(record["request_id"])
    reopened = FarmService(service.store.root, NativeTopsBackend())
    assert reopened.get_job(record["request_id"])["cancellation_requested"] is True
    reopened.refresh(record["request_id"])
    reopened.cancel(record["request_id"])
    assert (root / "cancel-request.json").exists(), "Committed stop intent was never delivered after reopen or explicit retry"


def test_restart_redelivers_after_marker_write_before_acknowledgement(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    real_cancel = service.backend.cancel

    class SimulatedHostCrash(BaseException):
        pass

    def deliver_then_crash(*args):
        result = real_cancel(*args)
        assert result["cancellation_delivered"] is True
        raise SimulatedHostCrash()

    monkeypatch.setattr(service.backend, "cancel", deliver_then_crash)
    with pytest.raises(SimulatedHostCrash):
        service.cancel(record["request_id"])
    marker_before = package.read_json(root / "cancel-request.json")
    config_before = package.read_json(root / "native/review-token/config.json")
    reopened = FarmService(service.store.root, NativeTopsBackend())
    assert reopened.get_job(record["request_id"])["cancellation_delivery_pending"] is True
    recovered = reopened.refresh(record["request_id"])
    assert recovered["state"] == "cancel_requested"  # Delivery does not prove worker termination.
    assert recovered["cancellation_delivery_pending"] is False
    assert recovered["outputs"] == [] and recovered["verified"] is False
    assert package.read_json(root / "cancel-request.json") == marker_before
    assert package.read_json(root / "native/review-token/config.json") == config_before
    assert len(list(root.glob("native/*/config.json"))) == 1


def test_legacy_stop_fence_without_delivery_field_is_retryable(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    def legacy_stop(value):
        value.update(state="cancel_requested", cancellation_requested=True)
        value.pop("cancellation_delivery_pending", None)
        return value
    service.store.update(record["request_id"], legacy_stop)
    reopened = FarmService(service.store.root, NativeTopsBackend())
    recovered = reopened.refresh(record["request_id"])
    assert (root / "cancel-request.json").is_file()
    assert recovered["state"] == "cancel_requested"
    assert recovered["cancellation_delivery_pending"] is False


def test_missing_admission_receipts_alone_cannot_certify_no_dispatch(tmp_path):
    scene = tmp_path / "fixture.hiplc"
    scene.write_bytes(b"fixture")
    service = FarmService(tmp_path / "journal", ReceiptBackend())
    prepared = service.prepare({"request_id": "lost-owner", "source_hip": str(scene),
        "source_node": "/stage/OUT", "frames": [1], "output_root": str(tmp_path / "out")})
    service.submit(prepared["request_id"], prepared["digest"])
    service.backend = NativeTopsBackend()
    cancelled = service.cancel(prepared["request_id"])
    assert cancelled["state"] == "cancel_requested"
    assert cancelled["cancellation_delivery_pending"] is False
    assert service.refresh(prepared["request_id"])["state"] == "cancel_requested"
    assert service.store.get(prepared["request_id"]).get("_dispatch_skipped") is None


def completed_render(tmp_path, monkeypatch):
    service, record, root = admitted_render(tmp_path, monkeypatch)
    outputs = []
    for frame in record["plan"]["frames"]:
        path = root / (str(frame) + ".exr")
        raw = ("Synthetic verified byte fixture " + str(frame)).encode()
        path.write_bytes(raw)
        outputs.append({"frame": frame, "path": str(path), "verified": True,
            "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
            "width": record["plan"]["width"], "height": record["plan"]["height"]})
    receipt = {"state": "complete", "outputs": outputs,
        "verified_frames": record["plan"]["frames"],
        "verification": {"verified": True, "frames": record["plan"]["frames"]}}
    monkeypatch.setattr(service.backend, "poll", lambda *args: receipt)
    complete = service.refresh(record["request_id"])
    assert complete["state"] == "complete"
    return service, complete, root


def test_verified_job_recovers_after_transient_output_read_denial(tmp_path, monkeypatch):
    service, record, root = completed_render(tmp_path, monkeypatch)
    outputs = record["outputs"]
    real_identity = verification.file_identity
    reads = []

    def transient_denial(path):
        reads.append(str(path))
        raise FarmError("invalid_file", "A required file could not be read.")

    monkeypatch.setattr(verification, "file_identity", transient_denial)
    interrupted = service.refresh(record["request_id"])
    assert interrupted["state"] == "status_unavailable"
    assert interrupted["output_recheck_pending"] is True
    assert interrupted["outputs"] == [] and interrupted["verified"] is False
    original = service.store.get(record["request_id"])["_last_verified_receipt"]
    assert original["outputs"] == record["outputs"]
    assert original["digest"] == record["digest"]
    assert original["metadata"] == record["metadata"]
    assert service.refresh(record["request_id"])["state"] == "status_unavailable"
    assert service.store.get(record["request_id"])["_last_verified_receipt"] == original
    monkeypatch.setattr(verification, "file_identity", real_identity)
    def backend_forbidden(*args):
        pytest.fail("Rechecking an accepted output receipt must not call the backend")
    for method in ("prepare", "submit", "poll", "cancel"):
        monkeypatch.setattr(service.backend, method, backend_forbidden)
    # Independently establish that every actual file is still byte-for-byte intact.
    assert all(real_identity(Path(output["path"]))["sha256"] == output["sha256"] for output in outputs)
    reopened = FarmService(service.store.root, service.backend)
    recovered = reopened.refresh(record["request_id"])
    original_payload = {key: record["plan"][key] for key in (
        "request_id", "source_hip", "source_node", "frames", "output_root",
        "profile_id", "width", "height", "samples")}
    public_methods = {
        "prepare_same_intent": reopened.prepare(original_payload)["state"],
        "submit_same_intent": reopened.submit(record["request_id"], record["digest"])["state"],
        "cancel": reopened.cancel(record["request_id"])["state"],
        "get_job": reopened.get_job(record["request_id"])["state"],
        "list_jobs": reopened.list_jobs()[0]["state"],
        "refresh": recovered["state"],
    }
    assert "_last_verified_receipt" not in recovered
    evidence = {"during_denial": interrupted["state"], "error_code": interrupted.get("error_code"),
        "after_read_access_restored": recovered["state"], "outputs_unchanged": True,
        "published_outputs": recovered["outputs"], "public_method_states": public_methods}
    (tmp_path / "transient-output-read-evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert recovered["state"] == "complete", evidence
    assert recovered["output_recheck_pending"] is False
    assert recovered["outputs"] == record["outputs"]
    assert recovered["digest"] == record["digest"]
    assert recovered["plan"] == record["plan"]
    assert recovered["metadata"] == record["metadata"]


@pytest.mark.parametrize("change", ["modified", "deleted", "empty"])
def test_unreadable_output_then_confirmed_damage_remains_failed(tmp_path, monkeypatch, change):
    service, complete, _ = completed_render(tmp_path, monkeypatch)
    real_identity = verification.file_identity
    def unavailable(path):
        raise PermissionError("simulated read denial")
    monkeypatch.setattr(verification, "file_identity", unavailable)
    assert service.refresh(complete["request_id"])["state"] == "status_unavailable"
    monkeypatch.setattr(verification, "file_identity", real_identity)
    path = Path(complete["outputs"][0]["path"])
    original_bytes = path.read_bytes()
    if change == "deleted":
        path.unlink()
    else:
        path.write_bytes(b"confirmed different bytes" if change == "modified" else b"")
    failed = service.refresh(complete["request_id"])
    assert failed["state"] == "failed" and failed["error_code"] == "output_changed"
    assert failed["output_recheck_pending"] is False
    path.write_bytes(original_bytes)
    assert service.refresh(complete["request_id"]) == failed
    assert service.submit(complete["request_id"], complete["digest"]) == failed


def test_cancel_while_rechecking_original_bytes_fences_the_result(tmp_path, monkeypatch):
    service, complete, _ = completed_render(tmp_path, monkeypatch)
    real_identity = verification.file_identity
    def unavailable(path):
        raise PermissionError("simulated read denial")
    monkeypatch.setattr(verification, "file_identity", unavailable)
    assert service.refresh(complete["request_id"])["state"] == "status_unavailable"
    def cancel_during_read(path):
        service.cancel(complete["request_id"])
        return real_identity(path)
    monkeypatch.setattr(verification, "file_identity", cancel_during_read)
    cancelled = service.refresh(complete["request_id"])
    assert cancelled["cancellation_requested"] is True
    assert cancelled["state"] == "cancel_requested"
    assert cancelled["output_recheck_pending"] is False
    assert cancelled["outputs"] == [] and cancelled["verified"] is False
    monkeypatch.setattr(service.backend, "poll", lambda *args: {"state": "cancelled"})
    assert service.refresh(complete["request_id"])["state"] == "cancelled"


def test_old_failed_output_record_is_not_implicitly_migrated(tmp_path, monkeypatch):
    service, complete, _ = completed_render(tmp_path, monkeypatch)
    def old_failure(record):
        record["_last_verified_receipt"] = {key: record[key] for key in (
            "outputs", "verification", "verified_frames", "updated_at")}
        record.update(state="failed", error_code="output_changed", outputs=[],
                      verified=False, verification=None, verified_frames=[])
        return record
    legacy = service.store.update(complete["request_id"], old_failure)
    reopened = FarmService(service.store.root, NativeTopsBackend())
    assert reopened.refresh(complete["request_id"])["state"] == "failed"
    assert reopened.store.get(complete["request_id"]) == legacy


@pytest.mark.parametrize("parent_error", [FileNotFoundError, PermissionError])
def test_unreachable_output_directory_is_not_confirmed_image_deletion(tmp_path, monkeypatch, parent_error):
    service, complete, _ = completed_render(tmp_path, monkeypatch)
    output = Path(complete["outputs"][0]["path"])
    real_lstat, real_stat = Path.lstat, Path.stat
    def missing_file(path, *args, **kwargs):
        if path == output:
            raise FileNotFoundError("simulated unavailable share path")
        return real_lstat(path, *args, **kwargs)
    def unavailable_parent(path, *args, **kwargs):
        if path == output.parent:
            raise parent_error("simulated unavailable output directory")
        return real_stat(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", missing_file)
    monkeypatch.setattr(Path, "stat", unavailable_parent)
    unavailable = service.refresh(complete["request_id"])
    monkeypatch.setattr(Path, "lstat", real_lstat)
    monkeypatch.setattr(Path, "stat", real_stat)
    assert unavailable["state"] == "status_unavailable"
    assert unavailable["error_code"] == "output_unavailable"
    assert FarmService(service.store.root, NativeTopsBackend()).refresh(complete["request_id"])["state"] == "complete"
