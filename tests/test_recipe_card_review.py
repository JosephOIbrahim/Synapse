"""Independent crucible regressions for immutable evidence and job correlation."""
from dataclasses import replace
from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from synapse.recipes.card import RequestDedup, SpecCache, spec_digest
from synapse.recipes.contracts import ActionId, EvidenceFreshness, OperationState, RunRecipeRequest
from synapse.recipes.receipt import ReceiptStore, from_dict, to_dict
from test_recipe_card import render_receipt, sample_instance, sample_spec, tracker
from test_recipe_receipt import sample_receipt


def test_receipt_nested_list_cannot_be_reinitialized():
    receipt = from_dict(to_dict(sample_receipt()))
    original = to_dict(receipt)
    channels = receipt.render_job["file"]["channels"]
    try:
        channels.__init__(["forged"])
    except (TypeError, AttributeError):
        pass
    assert to_dict(receipt) == original


def test_cached_list_reinitialization_cannot_change_digest():
    spec = replace(sample_spec(), nodes=({"id": "test-node", "values": [1]},))
    digest = spec_digest(spec)
    cache = SpecCache()
    cache.put(digest, spec)
    values = cache.get(digest).nodes[0]["values"]
    try:
        values.__init__([2])
    except (TypeError, AttributeError):
        pass
    assert spec_digest(cache.get(digest)) == digest


def running_render():
    request = RunRecipeRequest("solaris.spine", ActionId.RENDER.value,
                               "instance-1", {}, 1, "req-1")
    dedup = RequestDedup()
    assert dedup.claim(request).should_execute
    dedup.transition(request.request_id, OperationState.RUNNING, job_id="expected-job")
    return dedup, request


@pytest.mark.parametrize("render_job", [{"job_id": "different-job"}, {}])
def test_tracked_render_cannot_complete_with_unrelated_or_missing_job_identity(render_job):
    dedup, request = running_render()
    with pytest.raises(ValueError):
        dedup.transition(request.request_id, OperationState.TERMINAL,
                         receipt=replace(render_receipt(), render_job=render_job))
    retry = dedup.claim(request)
    assert not retry.should_execute
    assert retry.job.operation_state == OperationState.RUNNING
    assert retry.job.job_id == "expected-job"
    assert retry.job.receipt is None


def test_tracked_render_matching_receipt_survives_lost_response_retry():
    dedup, request = running_render()
    terminal = dedup.transition(request.request_id, OperationState.TERMINAL,
                               receipt=replace(render_receipt(), render_job={"job_id": "expected-job"}))
    retry = dedup.claim(request)
    assert not retry.should_execute
    assert retry.job == terminal
    assert retry.job.receipt.render_job["job_id"] == retry.job.job_id


def test_exact_retry_does_not_conflate_boolean_and_integer_evidence():
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
        store = ReceiptStore(Path(directory) / "receipts.jsonl")
        store.append(sample_receipt(render_job={"observed": 1}))
        original = store.path.read_bytes()
        with pytest.raises(ValueError):
            store.append(sample_receipt(render_job={"observed": True}))
        assert store.path.read_bytes() == original


def test_reconnect_cannot_backdate_away_a_known_tracking_gap():
    subject = tracker()
    subject.set_tracking(False, since="2026-09-04T12:00:02Z")
    subject.set_tracking(True, since="2026-09-04T11:00:00Z")
    assert subject.freshness(sample_receipt(), sample_instance()) == EvidenceFreshness.UNKNOWN


def test_periodic_observation_failure_cannot_be_erased_by_backdated_reconnect():
    subject = tracker()

    def fail_observation():
        raise RuntimeError("observation channel lost")

    with patch("synapse.recipes.freshness.utc_now", return_value="2026-09-04T12:00:02Z"):
        with pytest.raises(RuntimeError, match="observation channel lost"):
            subject.periodic_recheck(fail_observation)
    subject.set_tracking(True, since="2026-09-04T11:00:00Z")
    assert subject.freshness(sample_receipt(), sample_instance()) == EvidenceFreshness.UNKNOWN
