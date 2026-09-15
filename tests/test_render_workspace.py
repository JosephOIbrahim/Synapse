"""Artist render sequences, with no Qt, Houdini, model or actual render required."""
from copy import deepcopy
import json

import pytest

from synapse.panel.render_presenter import (
    FarmResponseError, RenderWorkspaceModel, decode_response, expected_frames,
    frame_text, inspection_frame_text, job_presentation, perform_farm_call,
    prepared_summary, verified_output_paths,
)


def model():
    ids = iter(("first-request", "second-request", "third-request"))
    result = RenderWorkspaceModel(request_id_factory=lambda: next(ids))
    result.edit({"source_hip": "C:/shots/scene.hiplc", "source_node": "/stage/OUT",
                 "frames": "1001-1005x2", "output_root": "C:/renders"})
    return result


def record(request_id="first-request", state="prepared", revision=2):
    frames = [1001, 1003, 1005]  # Independently enumerated from start 1001, end 1005, step 2.
    plan = {"source_hip": "C:/shots/scene.hiplc", "source_node": "/stage/OUT", "frames": frames,
            "output_root": "C:/renders", "profile_id": "local", "width": 256, "height": 256, "samples": 8}
    return {"request_id": request_id, "digest": "a" * 64, "state": state, "plan": plan,
            "note": "", "revision": revision, "verified_frames": [], "total_frames": len(frames),
            "outputs": [], "job_dir": "C:/renders/synapse_renders/" + request_id}


def completed():
    job = record(state="complete", revision=5)
    frames = [1001, 1003, 1005]
    job.update(verified=True, verified_frames=frames[:], verification={"verified": True, "frames": frames[:]})
    job["outputs"] = [{"frame": frame, "path": "C:/renders/synapse_renders/first-request/%s.exr" % frame,
                       "sha256": "b" * 64, "size": 41, "width": 256, "height": 256, "verified": True}
                      for frame in frames]
    return job


def test_prepare_review_and_submit_have_one_bound_identity():
    view = model()
    payload = view.begin_prepare()
    assert payload["request_id"] == "first-request"
    assert payload["frames"] == "1001-1005x2"
    assert not view.can_submit
    with pytest.raises(ValueError, match="Wait"):
        view.begin_prepare()
    view.receive_job(record(), request_id=payload["request_id"])
    assert view.can_submit
    assert "3 frames: 1001-1005x2" in prepared_summary(view.job)
    assert view.begin_submit() == {"request_id": "first-request", "digest": "a" * 64}
    with pytest.raises(ValueError, match="Prepare"):
        view.begin_submit()


@pytest.mark.parametrize("field,value", [
    ("frames", "1003"), ("source_node", "/stage/other"), ("source_hip", "C:/shots/new.hiplc"),
    ("output_root", "C:/different"), ("profile_id", "hqueue"), ("width", 512), ("height", 512), ("samples", 9),
])
def test_edit_after_prepare_invalidates_even_if_changed_back(field, value):
    view = model()
    view.begin_prepare()
    view.receive_job(record())
    original = view.form[field]
    view.edit({field: value})
    view.edit({field: original})
    assert not view.can_submit
    with pytest.raises(ValueError, match="Prepare"):
        view.begin_submit()
    assert view.begin_prepare()["request_id"] == "second-request"


def test_edit_during_preparation_does_not_bind_late_response_to_new_form():
    view = model()
    view.begin_prepare()
    view.edit({"frames": "1040"})
    view.receive_job(record())
    assert view.form["frames"] == "1040"
    assert not view.can_submit


def test_lost_submission_reply_is_reconciled_without_resubmitting():
    view = model()
    view.begin_prepare()
    view.receive_job(record())
    calls = []

    def transport(name, arguments):
        calls.append((name, arguments))
        if name == "synapse_farm_submit":
            raise RuntimeError("The connection closed after the server accepted the request.")
        return record(state="rendering", revision=3)

    payload = view.begin_submit()
    with pytest.raises(RuntimeError) as error:
        perform_farm_call("synapse_farm_submit", payload, transport)
    view.transport_failed("submit", str(error.value))
    assert view.job["state"] == "submission_uncertain"
    assert view.job["request_id"] == payload["request_id"]
    assert not view.can_submit
    assert "may have started" in job_presentation(view.job)["title"]
    with pytest.raises(ValueError):
        view.begin_prepare()
    response = perform_farm_call("synapse_farm_job", {"request_id": payload["request_id"]}, transport)
    view.receive_job(response, request_id=payload["request_id"])
    assert view.job["state"] == "rendering"
    assert [name for name, _ in calls] == ["synapse_farm_submit", "synapse_farm_job"]


def test_lost_prepare_reply_can_recover_prepared_record_for_explicit_submit():
    view = model()
    payload = view.begin_prepare()
    view.transport_failed("prepare", "No reply arrived.")
    assert view.job["state"] == "status_unavailable"
    view.receive_job(record(), request_id=payload["request_id"])
    assert view.can_submit
    assert view.pending is None  # Receiving the record did not itself submit.


def test_cancel_request_and_transport_loss_are_not_confirmed_cancellation():
    view = model()
    view.jobs["first-request"] = record(state="rendering", revision=3)
    view.select_job("first-request")
    assert view.begin_cancel() == {"request_id": "first-request"}
    view.transport_failed("cancel", "The reply was lost.")
    assert view.job["state"] == "cancel_requested"
    assert "Waiting" in job_presentation(view.job)["title"]
    assert not job_presentation(view.job)["can_cancel"]
    view.receive_job(record(state="cancelled", revision=4))
    assert view.job["state"] == "cancelled"
    assert not view.receive_job(completed())
    assert view.job["state"] == "cancelled"
    assert not job_presentation(view.job, observation_note=view.observation_note)["can_open"]


def test_old_snapshot_and_other_request_cannot_replace_selected_job():
    view = model()
    view.jobs["first-request"] = record(state="rendering", revision=8)
    view.select_job("first-request")
    assert not view.receive_job(record(state="prepared", revision=2))
    assert view.job["state"] == "rendering"
    with pytest.raises(FarmResponseError, match="different request"):
        view.receive_job(record(request_id="second-request"), request_id="first-request")
    assert view.job["request_id"] == "first-request"


def test_authoritative_output_invalidation_stays_failed_after_reselection():
    view = model()
    complete = completed()
    view.jobs[complete["request_id"]] = complete
    view.select_job(complete["request_id"])
    invalid = dict(complete, state="failed", error_code="output_changed", revision=complete["revision"] + 1,
                   verified=False, outputs=[], verified_frames=[], verification=None,
                   note="Previously verified images are missing or changed.")
    assert view.receive_job(invalid)
    assert view.job["state"] == "failed" and not verified_output_paths(view.job)
    view.new_render()
    view.select_job(complete["request_id"])
    assert view.job["state"] == "failed" and not job_presentation(view.job)["can_open"]
    assert not view.receive_job(complete)
    assert view.job["state"] == "failed"


def unreadable_outputs(complete):
    return dict(complete, state="status_unavailable", error_code="output_unavailable",
                output_recheck_pending=True, revision=complete["revision"] + 1,
                verified=False, outputs=[], verified_frames=[], verification=None,
                note="Previously verified images could not be read. Refresh to check them again.")


def test_verified_output_read_recovery_updates_the_selected_record():
    view = model()
    complete = completed()
    view.jobs[complete["request_id"]] = complete
    view.select_job(complete["request_id"])
    unavailable = unreadable_outputs(complete)
    assert view.receive_job(unavailable)
    presentation = job_presentation(view.job)
    assert not presentation["can_open"] and not presentation["can_cancel"]
    assert "running" not in presentation["title"].lower()
    assert presentation["poll"]
    restored = dict(complete, revision=unavailable["revision"] + 1, output_recheck_pending=False)
    assert view.receive_job(restored)
    assert job_presentation(view.job)["can_open"]
    assert not view.can_submit


@pytest.mark.parametrize("damage", ["digest", "plan", "job_dir", "pending", "revision", "outputs", "native_token"])
def test_read_failure_cannot_replace_verified_identity_or_expose_outputs(damage):
    view = model()
    complete = completed()
    view.jobs[complete["request_id"]] = complete
    view.select_job(complete["request_id"])
    unavailable = unreadable_outputs(complete)
    if damage == "digest":
        unavailable["digest"] = "c" * 64
    elif damage == "plan":
        unavailable["plan"] = dict(complete["plan"], samples=64)
    elif damage == "job_dir":
        unavailable["job_dir"] = "C:/other"
    elif damage == "pending":
        unavailable.pop("output_recheck_pending")
    elif damage == "revision":
        unavailable["revision"] = complete["revision"]
    elif damage == "native_token":
        unavailable["metadata"] = {"native_token": "different-owner"}
    else:
        unavailable["outputs"] = complete["outputs"]
    assert not view.receive_job(unavailable)
    assert not job_presentation(view.job, observation_note=view.observation_note)["can_open"]


@pytest.mark.parametrize("damage", ["digest", "plan", "job_dir", "revision", "outputs", "native_token", "cancelled", "pending"])
def test_restored_output_must_match_the_previously_verified_receipt(damage):
    view = model()
    complete = completed()
    view.jobs[complete["request_id"]] = complete
    view.select_job(complete["request_id"])
    unavailable = unreadable_outputs(complete)
    assert view.receive_job(unavailable)
    restored = deepcopy(complete)
    restored.update(revision=unavailable["revision"] + 1, output_recheck_pending=False)
    if damage == "digest":
        restored["digest"] = "c" * 64
    elif damage == "plan":
        restored["plan"]["samples"] = 64
    elif damage == "job_dir":
        restored["job_dir"] = "C:/other"
    elif damage == "revision":
        restored["revision"] = unavailable["revision"]
    elif damage == "outputs":
        restored["outputs"][0]["sha256"] = "c" * 64
    elif damage == "native_token":
        restored["metadata"] = {"native_token": "different-owner"}
    elif damage == "cancelled":
        restored["cancellation_requested"] = True
    else:
        restored["output_recheck_pending"] = True
    assert not view.receive_job(restored)
    assert not job_presentation(view.job, observation_note=view.observation_note)["can_open"]


def test_reopened_view_can_recover_the_same_unavailable_request():
    view = model()
    complete = completed()
    unavailable = unreadable_outputs(complete)
    view.jobs[complete["request_id"]] = unavailable
    view.select_job(complete["request_id"])
    restored = dict(complete, revision=unavailable["revision"] + 1, output_recheck_pending=False)
    assert view.receive_job(restored)
    assert job_presentation(view.job)["can_open"]


@pytest.mark.parametrize("state", ["rendering", "status_unavailable", "submission_uncertain"])
def test_unavailable_status_still_allows_explicit_stop_request(state):
    view = model()
    view.jobs["first-request"] = record(state=state)
    view.select_job("first-request")
    view.transport_failed("job", "The status reply could not be read.")
    assert job_presentation(view.job, observation_note=view.observation_note)["can_cancel"]
    assert view.begin_cancel() == {"request_id": "first-request"}
    assert view.job["state"] == "cancel_requested"
    assert not job_presentation(view.job)["can_cancel"]


def test_recent_prepared_record_restores_exact_plan_then_explicit_rerender_gets_new_id():
    view = model()
    view.jobs["older-request"] = record(request_id="older-request")
    view.select_job("older-request")
    assert view.can_submit
    assert view.form["frames"] == "1001-1005x2"
    view.new_render()
    assert not view.can_submit
    assert view.begin_prepare()["request_id"] != "older-request"
    assert "older-request" in view.jobs


def test_old_poll_reply_after_new_render_does_not_restore_old_selection():
    view = model()
    view.jobs["first-request"] = record(state="rendering", revision=3)
    view.select_job("first-request")
    view.new_render()
    assert not view.receive_job(record(state="verifying", revision=4), request_id="first-request")
    assert view.job is None
    assert view.jobs["first-request"]["state"] == "verifying"


def test_verified_complete_record_alone_enables_output():
    job = completed()
    paths = verified_output_paths(job)
    assert len(paths) == 3
    assert paths[0].endswith("1001.exr")
    presentation = job_presentation(job)
    assert presentation["can_open"]
    assert presentation["verified"] == presentation["total"] == 3
    assert presentation["title"] == "All 3 frames are ready."


@pytest.mark.parametrize("break_record", [
    lambda job: job.update(verified=False),
    lambda job: job["outputs"].append(dict(job["outputs"][0], path="C:/renders/duplicate.exr")),
    lambda job: job.update(verification=None),
    lambda job: job["verification"].update(verified=False),
    lambda job: job["verification"].update(frames=[]),
    lambda job: job["verification"].update(frames=[{}, 1003, 1005]),
    lambda job: job.update(verified_frames=[1001, 1001, 1005]),
    lambda job: job.update(total_frames=0),
    lambda job: job.update(outputs=[]),
    lambda job: job["outputs"].pop(),
    lambda job: job["outputs"][0].update(verified=False),
    lambda job: job["outputs"][0].update(path="relative.exr"),
    lambda job: job["outputs"][0].update(size=0),
    lambda job: job["outputs"][0].update(size=True),
    lambda job: job["outputs"][0].update(sha256="not-a-hash"),
    lambda job: job["outputs"][0].update(width=512),
    lambda job: job["outputs"][0].update(frame=True),
    lambda job: job["plan"].update(frames=[]),
    lambda job: job.update(plan=[]),
])
def test_corrupt_or_incomplete_evidence_never_becomes_a_complete_ui(break_record):
    job = completed()
    break_record(job)
    assert verified_output_paths(job) == []
    presentation = job_presentation(job)
    assert not presentation["can_open"]
    assert "ready" not in presentation["title"].lower()
    assert presentation["state"] == "status_unavailable"


@pytest.mark.parametrize("state", ["rendering", "verifying", "cancel_requested", "cancelled", "failed", "unknown"])
def test_later_files_do_not_enable_open_for_noncomplete_state(state):
    job = completed()
    job["state"] = state
    assert not verified_output_paths(job)
    assert not job_presentation(job)["can_open"]


def test_unreadable_status_and_observation_loss_are_never_idle_or_complete():
    view = model()
    view.jobs["first-request"] = completed()
    view.select_job("first-request")
    with pytest.raises(FarmResponseError):
        view.receive_job({"success": True, "data": {}})
    view.transport_failed("job", "No status response.")
    display = job_presentation(view.job, observation_note=view.observation_note)
    assert "unavailable" in display["title"].lower()
    assert not display["can_open"]
    assert display["verified"] == 3  # The last verified count is retained, not changed to zero.
    assert job_presentation({"state": "rendering", "plan": []})["total"] is None


@pytest.mark.parametrize("wrap", [
    lambda job: job,
    lambda job: {"success": True, "data": job},
    lambda job: {"structuredContent": job},
    lambda job: {"content": [{"type": "text", "text": json.dumps(job)}]},
    lambda job: {"content": [{"type": "text", "text": json.dumps({"data": job})}]},
])
def test_transport_unwraps_real_data_and_detaches_mutable_results(wrap):
    original = record()
    decoded = decode_response(wrap(original))
    decoded["plan"]["frames"].append(2000)
    assert original["plan"]["frames"] == [1001, 1003, 1005]


@pytest.mark.parametrize("response", [
    None, [], "not json", {"isError": True, "content": [{"type": "text", "text": "Permission denied"}]},
    {"success": False, "error": {"message": "Profile unavailable"}},
    {"content": [{"type": "text", "text": "one"}, {"type": "text", "text": "two"}]},
])
def test_transport_failure_does_not_claim_nothing_was_sent(response):
    with pytest.raises(FarmResponseError) as caught:
        perform_farm_call("synapse_farm_submit", {"request_id": "first-request"}, lambda *_: response)
    assert "nothing was" not in str(caught.value).lower()


def test_frame_syntax_roundtrips_the_service_parser_and_inspection_triple_is_distinct():
    from synapse.farm.models import parse_frames
    for frames in ([1001, 1003, 1005], [-3, -1, 1], [1, 2, 10], [0], [1001, 1004]):
        assert parse_frames(frame_text(frames)) == frames
    assert parse_frames(inspection_frame_text([1001, 1005, 2])) == [1001, 1003, 1005]
    assert inspection_frame_text([0, 0, 1]) == "0"


def test_form_and_job_payloads_are_copied_not_shared():
    view = model()
    payload = view.begin_prepare()
    payload["source_node"] = "/stage/wrong"
    assert view.form["source_node"] == "/stage/OUT"
    job = record()
    view.receive_job(job)
    job["plan"]["frames"].clear()
    assert expected_frames(view.job) == [1001, 1003, 1005]
