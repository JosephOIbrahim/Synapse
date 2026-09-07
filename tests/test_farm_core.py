"""Pure journal/acceptance tests. Fake decoder receipts do not test image decoding."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from pathlib import Path
import threading

import pytest

from synapse.farm import FarmError, FarmService, canonical_plan, parse_frames
from synapse.farm.models import MAX_FRAMES


class Backend:
    def __init__(self):
        self.calls = {name: 0 for name in ("capabilities", "prepare", "submit", "poll", "cancel")}
        self.on_prepare = self.on_submit = self.on_poll = self.on_cancel = None

    def capabilities(self):
        self.calls["capabilities"] += 1
        return {"available": True, "profiles": [{"id": "local", "available": True},
                {"id": "hqueue", "available": False, "reason": "HQueue is not configured."}]}

    def prepare(self, plan, job_dir):
        self.calls["prepare"] += 1
        return self.on_prepare(plan, job_dir) if self.on_prepare else {"state": "prepared", "note": "Ready."}

    def submit(self, plan, job_dir, record):
        self.calls["submit"] += 1
        return self.on_submit(plan, job_dir, record) if self.on_submit else {"state": "rendering", "backend_id": "worker-42"}

    def poll(self, plan, job_dir, record):
        self.calls["poll"] += 1
        return self.on_poll(plan, job_dir, record) if self.on_poll else {"state": "rendering"}

    def cancel(self, plan, job_dir, record):
        self.calls["cancel"] += 1
        return self.on_cancel(plan, job_dir, record) if self.on_cancel else {"state": "cancelled"}


@pytest.fixture
def rig(tmp_path):
    scene = tmp_path / "saved.hiplc"
    scene.write_bytes(b"standalone saved-scene fixture; the backend owns HIP parsing")
    payload = {"request_id": "render-1001", "source_hip": str(scene),
               "source_node": "/stage/OUT", "frames": "1001-1005x2,1010",
               "output_root": str(tmp_path / "output")}
    backend = Backend()
    service = FarmService(tmp_path / "journal", backend)
    return service, backend, payload


def complete_receipt(plan, job_dir):
    """Synthetic decoder evidence used only to exercise the core byte boundary."""
    output_dir = job_dir / "frames"
    output_dir.mkdir(exist_ok=True)
    outputs = []
    for frame in plan["frames"]:
        path = output_dir / f"frame.{frame}.exr"
        raw = f"synthetic decoded image fixture for frame {frame}".encode()
        path.write_bytes(raw)
        outputs.append({"frame": frame, "path": str(path),
                        "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
                        "width": plan["width"], "height": plan["height"], "verified": True})
    return {"state": "complete", "verified_frames": list(plan["frames"]),
            "verification": {"verified": True, "frames": list(plan["frames"])},
            "outputs": outputs}


def start(rig):
    service, backend, payload = rig
    prepared = service.prepare(payload)
    return service.submit(prepared["request_id"], prepared["digest"])


def unavailable(*args):
    raise TimeoutError("The process may have started; acknowledgement was lost.")


def test_sparse_frame_ranges_are_exact_and_canonical():
    # Hand expansion: 1001, 1003, 1005; disjoint 1010; overlap adds no new frame.
    assert parse_frames("1001-1005x2,1010,1003") == [1001, 1003, 1005, 1010]
    assert parse_frames("-3-3x2") == [-3, -1, 1, 3]
    assert parse_frames([4, 1, 4]) == [1, 4]


@pytest.mark.parametrize("frames", [[], [True], [1.2], "", "3-1", "1-3x0", "1,", "1-1000000", "9" * 5000, [1] * (MAX_FRAMES + 1)])
def test_frame_selection_is_bounded(frames):
    with pytest.raises(FarmError):
        parse_frames(frames)


@pytest.mark.parametrize("field,value", [
    ("request_id", "../escape"), ("request_id", "CON"), ("request_id", "A" * 65),
    ("source_hip", "relative.hip"), ("source_node", "stage/OUT"),
    ("source_node", "/stage/../OUT"), ("output_root", "relative"),
    ("width", True), ("height", 0), ("samples", 65537), ("arbitrary_command", "launch")])
def test_plan_refuses_unsafe_or_unreviewable_scope(rig, field, value):
    service, backend, payload = rig
    with pytest.raises(FarmError):
        service.prepare(dict(payload, **{field: value}))
    assert service.list_jobs() == []
    assert backend.calls["prepare"] == 0


def test_missing_or_empty_saved_scene_cannot_be_prepared(rig):
    service, backend, payload = rig
    Path(payload["source_hip"]).write_bytes(b"")
    with pytest.raises(FarmError, match="missing, empty or changing"):
        service.prepare(payload)
    assert backend.calls["prepare"] == 0


def test_immutable_plan_digest_covers_source_bytes_and_render_scope(rig):
    _, _, payload = rig
    original = canonical_plan(payload)
    equivalent = canonical_plan(dict(payload, frames=[1010, 1001, 1005, 1003]))
    assert original["digest"] == equivalent["digest"]
    assert original["digest"] != canonical_plan(dict(payload, samples=9))["digest"]
    Path(payload["source_hip"]).write_bytes(b"different saved scene")
    assert original["digest"] != canonical_plan(payload)["digest"]


def test_prepare_is_durable_and_idempotent_after_service_reopen(rig):
    service, backend, payload = rig
    first = service.prepare(payload)
    assert first["state"] == "prepared"
    assert not first["submission_attempted"]
    reopened = FarmService(service.store.root, backend)
    assert reopened.prepare(payload) == first
    assert reopened.get_job(first["request_id"]) == first
    assert reopened.list_jobs() == [first]
    assert backend.calls["prepare"] == 1
    assert backend.calls["submit"] == 0
    assert backend.calls["poll"] == 0


def test_same_request_id_with_changed_plan_conflicts_without_work(rig):
    service, backend, payload = rig
    first = service.prepare(payload)
    with pytest.raises(FarmError) as error:
        service.prepare(dict(payload, width=512))
    assert error.value.code == "request_conflict"
    assert service.get_job(first["request_id"]) == first
    assert backend.calls["prepare"] == 1


def test_intentional_new_request_gets_separate_owned_output_directory(rig):
    service, backend, payload = rig
    first = service.prepare(payload)
    second = service.prepare(dict(payload, request_id="intentional-rerender"))
    assert first["job_dir"] != second["job_dir"]
    assert first["digest"] != second["digest"]
    assert backend.calls["prepare"] == 2


def test_preexisting_output_directory_is_not_consumed_as_a_new_job(rig):
    service, backend, payload = rig
    folder = Path(payload["output_root"]) / "synapse_renders" / payload["request_id"]
    folder.mkdir(parents=True)
    stale = folder / "keep.exr"
    stale.write_bytes(b"existing artist data")
    record = service.prepare(payload)
    assert record["state"] == "failed"
    assert backend.calls["prepare"] == 0
    assert stale.read_bytes() == b"existing artist data"


def test_admission_is_persisted_before_prepare_or_submit(rig):
    service, backend, payload = rig
    def preparing(plan, folder):
        seen = FarmService(service.store.root, backend).get_job(plan["request_id"])
        assert seen["state"] == "preparing"
        assert folder.is_dir()
        return {"state": "prepared"}
    def submitting(plan, folder, record):
        seen = FarmService(service.store.root, backend).get_job(plan["request_id"])
        assert seen["state"] == "submitting"
        assert seen["submission_attempted"] is True
        return {"state": "rendering"}
    backend.on_prepare, backend.on_submit = preparing, submitting
    assert start(rig)["state"] == "rendering"


def test_unfinished_preparation_cannot_submit(rig):
    service, backend, payload = rig
    backend.on_prepare = lambda *args: {"state": "preparing"}
    prepared = service.prepare(payload)
    with pytest.raises(FarmError) as error:
        service.submit(prepared["request_id"], prepared["digest"])
    assert error.value.code == "invalid_state"
    backend.on_poll = lambda *args: {"state": "prepared"}
    assert service.refresh(prepared["request_id"])["state"] == "prepared"
    assert backend.calls["submit"] == 0


def test_submit_requires_exact_review_digest(rig):
    service, backend, payload = rig
    prepared = service.prepare(payload)
    with pytest.raises(FarmError) as error:
        service.submit(prepared["request_id"], "0" * 64)
    assert error.value.code == "digest_mismatch"
    assert service.get_job(prepared["request_id"])["state"] == "prepared"
    assert backend.calls["submit"] == 0


def test_lost_prepare_acknowledgement_is_not_retried_after_reopen(rig):
    service, backend, payload = rig
    backend.on_prepare = unavailable
    uncertain = service.prepare(payload)
    assert uncertain["state"] == "status_unavailable"
    reopened = FarmService(service.store.root, backend)
    assert reopened.prepare(payload) == uncertain
    assert backend.calls["prepare"] == 1


def test_lost_submit_acknowledgement_never_launches_twice_after_reopen(rig):
    service, backend, payload = rig
    backend.on_submit = unavailable
    uncertain = start(rig)
    assert uncertain["state"] == "submission_uncertain"
    reopened = FarmService(service.store.root, backend)
    assert reopened.submit(uncertain["request_id"], uncertain["digest"]) == uncertain
    # The stale preparation receipt does not grant permission for a second launch.
    backend.on_poll = lambda *args: {"state": "prepared"}
    observed = reopened.refresh(uncertain["request_id"])
    assert observed["state"] == "submission_uncertain"
    assert reopened.submit(observed["request_id"], observed["digest"]) == observed
    assert backend.calls["submit"] == 1
    assert backend.calls["poll"] == 1


def test_successful_repeat_submit_returns_existing_job(rig):
    service, backend, _ = rig
    first = start(rig)
    assert service.submit(first["request_id"], first["digest"]) == first
    assert backend.calls["submit"] == 1


def test_reads_do_not_probe_or_resume_uncertain_execution(rig):
    service, backend, _ = rig
    backend.on_submit = unavailable
    first = start(rig)
    before = dict(backend.calls)
    reopened = FarmService(service.store.root, backend)
    assert reopened.get_job(first["request_id"]) == first
    assert reopened.list_jobs() == [first]
    assert backend.calls == before


def test_verified_complete_requires_every_actual_output(rig):
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    done = service.refresh(first["request_id"])
    assert done["state"] == "complete"
    assert done["verified"] is True
    assert done["verified_frames"] == [1001, 1003, 1005, 1010]
    assert [image["frame"] for image in done["outputs"]] == [1001, 1003, 1005, 1010]
    reopened = FarmService(service.store.root, backend)
    assert reopened.get_job(done["request_id"]) == done


@pytest.mark.parametrize("change", ["modified", "deleted"])
def test_refresh_invalidates_completed_outputs_that_changed_after_acceptance(rig, change):
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    done = service.refresh(first["request_id"])
    assert done["state"] == "complete"
    path = Path(done["outputs"][0]["path"])
    if change == "modified":
        path.write_bytes(b"changed after the original acceptance")
    else:
        path.unlink()
    before = dict(backend.calls)
    reopened = FarmService(service.store.root, backend)
    rejected = reopened.refresh(done["request_id"])
    assert rejected["state"] == "failed"
    assert rejected["error_code"] == "output_changed"
    assert not rejected["verified"]
    assert rejected["verified_frames"] == []
    assert rejected["outputs"] == []
    assert reopened.submit(done["request_id"], done["digest"]) == rejected
    assert backend.calls == before


def test_refresh_of_unchanged_complete_outputs_never_starts_backend_work(rig):
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    done = service.refresh(first["request_id"])
    before = dict(backend.calls)
    assert service.refresh(done["request_id"]) == done
    assert backend.calls == before


@pytest.mark.parametrize("damage", ["no_evidence", "validator_false", "missing_frame", "extra_frame", "duplicate_frame", "wrong_dimensions", "changed_bytes", "missing_file", "empty_file", "wrong_hash", "unverified_image", "outside_job"])
def test_false_completion_is_failed_closed(rig, damage, tmp_path):
    service, backend, _ = rig
    first = start(rig)
    def false_complete(plan, folder, record):
        result = complete_receipt(plan, folder)
        output = result["outputs"][0]
        if damage == "no_evidence":
            result.pop("verification")
        elif damage == "validator_false":
            result["verification"]["verified"] = False
        elif damage == "missing_frame":
            result["verified_frames"].pop()
            result["outputs"].pop()
        elif damage == "extra_frame":
            result["verified_frames"].append(1011)
        elif damage == "duplicate_frame":
            result["outputs"][1]["frame"] = output["frame"]
        elif damage == "wrong_dimensions":
            output["width"] += 1
        elif damage == "changed_bytes":
            Path(output["path"]).write_bytes(b"replacement after image decoding")
        elif damage == "missing_file":
            Path(output["path"]).unlink()
        elif damage == "empty_file":
            Path(output["path"]).write_bytes(b"")
        elif damage == "wrong_hash":
            output["sha256"] = "0" * 64
        elif damage == "unverified_image":
            output["verified"] = False
        elif damage == "outside_job":
            outside = tmp_path / "unowned.exr"
            outside.write_bytes(Path(output["path"]).read_bytes())
            output["path"] = str(outside)
        return result
    backend.on_poll = false_complete
    rejected = service.refresh(first["request_id"])
    assert rejected["state"] == "failed"
    assert rejected["error_code"] == "verification_failed"
    assert rejected["verified"] is False
    assert rejected["verified_frames"] == []
    assert rejected["outputs"] == []


def test_validator_exception_with_existing_files_is_not_success(rig):
    service, backend, _ = rig
    first = start(rig)
    complete_receipt(first["plan"], Path(first["job_dir"]))
    def validator_crashes(*args):
        raise RuntimeError("image decoder failed")
    backend.on_poll = validator_crashes
    observed = service.refresh(first["request_id"])
    assert observed["state"] == "status_unavailable"
    assert not observed["verified"]
    assert observed["outputs"] == []


def test_backend_cook_progress_does_not_claim_verified_images(rig):
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda plan, *args: {"state": "verifying", "verified_frames": plan["frames"], "metadata": {"cooked_frames": 4}}
    observed = service.refresh(first["request_id"])
    assert observed["verified_frames"] == []
    assert observed["metadata"]["cooked_frames"] == 4


def test_backend_may_not_mutate_reviewed_plan_through_arguments(rig):
    service, backend, payload = rig
    expected = canonical_plan(payload)
    def mutates_input(plan, folder):
        plan["frames"].append(9000)
        plan["width"] = 7
        return {"state": "prepared", "plan": plan, "digest": "fabricated"}
    backend.on_prepare = mutates_input
    observed = service.prepare(payload)
    assert observed["plan"] == expected
    assert observed["digest"] == expected["digest"]


def test_completion_before_submission_is_rejected(rig):
    service, backend, payload = rig
    backend.on_prepare = complete_receipt
    record = service.prepare(payload)
    assert record["state"] == "failed"
    assert record["error_code"] == "unexpected_completion"
    assert not record["verified"]


def test_cancel_is_durable_and_fences_late_completion(rig):
    service, backend, _ = rig
    first = start(rig)
    def stopping(plan, folder, record):
        seen = FarmService(service.store.root, backend).get_job(plan["request_id"])
        assert seen["state"] == "cancel_requested"
        assert seen["cancellation_requested"] is True
        return complete_receipt(plan, folder)
    backend.on_cancel = stopping
    stopped = service.cancel(first["request_id"])
    assert stopped["state"] == "cancel_requested"
    reopened = FarmService(service.store.root, backend)
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    late = reopened.refresh(first["request_id"])
    assert late["state"] == "cancel_requested"
    assert not late["verified"]
    assert late["outputs"] == []
    backend.on_poll = lambda *args: {"state": "cancelled"}
    assert reopened.refresh(first["request_id"])["state"] == "cancelled"
    assert reopened.submit(first["request_id"], first["digest"])["state"] == "cancelled"
    assert backend.calls["submit"] == 1


def test_failed_cancel_acknowledgement_remains_an_acceptance_fence(rig):
    service, backend, _ = rig
    first = start(rig)
    backend.on_cancel = unavailable
    assert service.cancel(first["request_id"])["state"] == "cancel_requested"
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    assert service.refresh(first["request_id"])["state"] == "cancel_requested"
    assert backend.calls["cancel"] == 1


def test_backend_observed_cancellation_also_fences_late_completion(rig):
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda *args: {"state": "cancel_requested"}
    assert service.refresh(first["request_id"])["cancellation_requested"] is True
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    assert service.refresh(first["request_id"])["state"] == "cancel_requested"


def test_cancel_between_admission_and_dispatch_prevents_backend_launch(rig, monkeypatch):
    service, backend, payload = rig
    prepared = service.prepare(payload)
    update = service.store.update
    def stop_after_admission(request_id, change):
        record = update(request_id, change)
        if record["state"] == "submitting":
            service.cancel(request_id)
        return record
    monkeypatch.setattr(service.store, "update", stop_after_admission)
    stopped = service.submit(prepared["request_id"], prepared["digest"])
    assert stopped["state"] == "cancelled"
    assert backend.calls["submit"] == 0


def test_concurrent_prepare_admits_only_one_backend_call(rig):
    service, backend, payload = rig
    entered, release = threading.Event(), threading.Event()
    def slow_prepare(*args):
        entered.set()
        assert release.wait(5)
        return {"state": "prepared"}
    backend.on_prepare = slow_prepare
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.prepare, payload)
        try:
            assert entered.wait(5)
            other = FarmService(service.store.root, backend)
            duplicate = pool.submit(other.prepare, payload).result(timeout=3)
            assert duplicate["state"] == "preparing"
            assert backend.calls["prepare"] == 1
        finally:
            release.set()
        assert first.result(timeout=3)["state"] == "prepared"


def test_cancel_during_slow_submission_holds_no_database_lock(rig):
    service, backend, payload = rig
    prepared = service.prepare(payload)
    entered, release = threading.Event(), threading.Event()
    def slow_submit(plan, folder, record):
        entered.set()
        assert release.wait(5)
        return complete_receipt(plan, folder)
    backend.on_submit = slow_submit
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.submit, prepared["request_id"], prepared["digest"])
        try:
            assert entered.wait(5)
            other = FarmService(service.store.root, backend)
            stopped = pool.submit(other.cancel, prepared["request_id"]).result(timeout=3)
            assert stopped["state"] == "cancelled"
            assert service.list_jobs()[0]["state"] == "cancelled"
        finally:
            release.set()
        assert first.result(timeout=3)["state"] == "cancelled"
    assert service.get_job(prepared["request_id"])["outputs"] == []


@pytest.mark.parametrize("phase", ["prepare", "submit"])
def test_late_active_phase_cancel_acknowledgement_converges(rig, phase):
    service, backend, payload = rig
    prepared = service.prepare(payload) if phase == "submit" else None
    entered, release = threading.Event(), threading.Event()
    def delayed_ack(*args):
        entered.set()
        assert release.wait(5)
        return {"state": "cancelled"}
    backend.on_cancel = lambda *args: {"state": "cancel_requested"}
    setattr(backend, "on_" + phase, delayed_ack)
    with ThreadPoolExecutor(max_workers=2) as pool:
        running = (pool.submit(service.submit, prepared["request_id"], prepared["digest"])
                   if prepared else pool.submit(service.prepare, payload))
        try:
            assert entered.wait(5)
            assert service.cancel(payload["request_id"])["state"] == "cancel_requested"
        finally:
            release.set()
        assert running.result(timeout=3)["state"] == "cancelled"
    assert not service.get_job(payload["request_id"])["verified"]


def test_old_preparation_cancel_ack_cannot_confirm_a_submitted_render_stopped(rig):
    service, backend, payload = rig
    entered, release = threading.Event(), threading.Event()
    def delayed_preparation(*args):
        entered.set()
        assert release.wait(5)
        return {"state": "cancelled"}
    backend.on_prepare = delayed_preparation
    backend.on_cancel = lambda *args: {"state": "cancel_requested"}
    backend.on_poll = lambda *args: {"state": "prepared"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        preparing = pool.submit(service.prepare, payload)
        try:
            assert entered.wait(5)
            ready = service.refresh(payload["request_id"])
            assert service.submit(ready["request_id"], ready["digest"])["state"] == "rendering"
            assert service.cancel(ready["request_id"])["state"] == "cancel_requested"
        finally:
            release.set()
        assert preparing.result(timeout=3)["state"] == "cancel_requested"
    assert service.get_job(payload["request_id"])["cancellation_requested"] is True


def test_cancel_during_output_verification_fences_the_receipt(rig, monkeypatch):
    import synapse.farm.service as service_module
    service, backend, _ = rig
    first = start(rig)
    backend.on_poll = lambda plan, folder, record: complete_receipt(plan, folder)
    verify = service_module.verify_completion
    entered, release = threading.Event(), threading.Event()
    def slow_verify(*args):
        entered.set()
        assert release.wait(5)
        return verify(*args)
    monkeypatch.setattr(service_module, "verify_completion", slow_verify)
    with ThreadPoolExecutor(max_workers=2) as pool:
        checking = pool.submit(service.refresh, first["request_id"])
        try:
            assert entered.wait(5)
            stopped = pool.submit(service.cancel, first["request_id"]).result(timeout=3)
            assert stopped["state"] == "cancelled"
        finally:
            release.set()
        assert checking.result(timeout=3)["state"] == "cancelled"
    assert not service.get_job(first["request_id"])["verified"]


def test_capabilities_preserve_honest_unavailable_profile(rig):
    service, backend, _ = rig
    result = service.capabilities()
    hqueue = next(profile for profile in result["profiles"] if profile["id"] == "hqueue")
    assert hqueue == {"id": "hqueue", "available": False, "reason": "HQueue is not configured."}
    assert backend.calls["prepare"] == 0


@pytest.mark.parametrize("limit", [0, 201, True, "20"])
def test_read_limits_are_bounded(rig, limit):
    with pytest.raises(FarmError):
        rig[0].list_jobs(limit)


def test_missing_request_has_explicit_shape(rig):
    with pytest.raises(FarmError) as error:
        rig[0].get_job("not-found")
    assert error.value.code == "job_not_found"
