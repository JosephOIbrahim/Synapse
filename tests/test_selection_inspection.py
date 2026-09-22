"""Captured selection ownership; no Qt, Houdini, storage or model calls."""
from copy import deepcopy
import threading

import pytest

from synapse.panel.selection_inspection import InspectionController, inspection_request


def snapshot():
    return {
        "schema": "synapse-selection-v1", "selection_source": "live",
        "selected_count": 2, "observed_count": 2, "omitted_count": 0,
        "complete": True, "can_pin": True, "truncated": False,
        "identities": [{"path": "/stage/a", "session_id": 12},
                       {"path": "/stage/b", "session_id": 13}],
        "scene": {"session_token": "scene-1", "hip_path": "/project/work.hip",
                  "houdini_version": "22.0.400"},
        "topology_hash": "a" * 64,
        "nodes": [{"path": "/stage/a", "type": "null", "category": "Lop"},
                  {"path": "/stage/b", "type": "null", "category": "Lop"}],
        "wires": {"internal": [{"source": "/stage/a", "source_output": 2,
                                  "target": "/stage/b", "target_input": 3}],
                  "entering": [], "leaving": []}, "warnings": [],
    }


class Harness:
    def __init__(self):
        self.jobs, self.requests = [], []
        self.reply = snapshot()
        def scan(request, cancelled):
            self.requests.append(deepcopy(request))
            assert not cancelled()
            if isinstance(self.reply, Exception):
                raise self.reply
            return deepcopy(self.reply)
        self.controller = InspectionController(scanner=scan, launch=self.jobs.append)

    def finish(self):
        self.jobs.pop(0)()

    def ready(self):
        self.controller.open()
        self.finish()


def test_open_is_lazy_and_bounded_and_default_does_not_request_details():
    h = Harness()
    h.controller.open()
    for _ in range(8):
        h.controller.refresh()
    assert len(h.jobs) == 1 and h.requests == []
    h.finish()
    assert len(h.requests) == 1
    assert h.requests[0] == {"depth": 0, "include_parameters": False,
                             "include_geometry": False, "max_nodes": 200, "max_edges": 2000}
    assert h.controller.view()["status"] == "ready"


def test_pin_uses_exact_capture_and_unpin_explicitly_returns_to_live():
    h = Harness(); h.ready()
    h.controller.pin()
    h.controller.refresh(); h.finish()
    request = h.requests[-1]
    assert request["node_paths"] == ["/stage/a", "/stage/b"]
    assert request["expected_identities"] == snapshot()["identities"]
    assert request["expected_scene"] == {"session_token": "scene-1", "hip_path": "/project/work.hip"}
    assert request["expected_topology_hash"] == "a" * 64
    h.controller.unpin(); h.finish()
    assert "node_paths" not in h.requests[-1]


@pytest.mark.parametrize("change", ["identity", "scene", "topology", "failure"])
def test_prepare_revalidates_and_cannot_retarget_same_path_or_changed_scene(change):
    h = Harness(); h.ready()
    if change == "identity": h.reply["identities"][0]["session_id"] = 999
    if change == "scene": h.reply["scene"]["session_token"] = "new-scene"
    if change == "topology": h.reply["topology_hash"] = "b" * 64
    if change == "failure": h.reply = ValueError("SELECTION_STALE: captured node was replaced")
    h.controller.prepare("check_wiring")
    assert h.controller.take_prepared() is None
    h.finish()
    state = h.controller.view()
    assert state["status"] == "stale" and state["snapshot"] == snapshot()
    assert h.controller.take_prepared() is None


def test_prompt_contains_exact_ports_and_pin_limits_and_is_consumed_once():
    h = Harness(); h.ready()
    h.controller.prepare("check_wiring"); h.finish()
    prompt = h.controller.take_prepared()
    assert '"source_output": 2' in prompt and '"target_input": 3' in prompt
    assert '"session_id": 12' in prompt and ('"expected_topology_hash": "' + "a" * 64 + '"') in prompt
    assert "not an edit sandbox" in prompt and "current viewport selection" in prompt
    assert h.controller.take_prepared() is None


def test_close_drops_queued_and_inflight_results_then_reopen_is_new():
    h = Harness(); h.controller.open(); h.controller.close(); h.finish()
    assert h.requests == [] and h.controller.view()["status"] == "closed"
    h.controller.open(); h.finish()
    assert len(h.requests) == 1 and h.controller.view()["status"] == "ready"
    entered, release = threading.Event(), threading.Event()
    def scan(request, cancelled):
        entered.set(); release.wait(2)
        return snapshot()
    c = InspectionController(scanner=scan)
    c.open(); assert entered.wait(2)
    c.close(); release.set()
    assert c.view()["snapshot"] is None and c.take_prepared() is None


@pytest.mark.parametrize("field,value", [("can_pin", False), ("complete", False),
                                         ("identities", []), ("topology_hash", "")])
def test_partial_or_unidentified_capture_cannot_pin_or_prepare(field, value):
    h = Harness(); h.reply[field] = value; h.ready()
    with pytest.raises(ValueError): h.controller.pin()
    with pytest.raises(ValueError): h.controller.prepare("fix_selection")
    assert not h.jobs


def test_snapshot_and_request_are_detached_from_callers():
    h = Harness(); h.ready()
    copy = h.controller.view(); copy["snapshot"]["identities"].clear()
    assert len(h.controller.view()["snapshot"]["identities"]) == 2
    report = snapshot(); request = inspection_request(report)
    request["expected_identities"].clear()
    assert len(report["identities"]) == 2


def test_unknown_action_fails_before_any_host_request():
    h = Harness(); h.ready()
    with pytest.raises(KeyError): h.controller.prepare("execute_python")
    assert not h.jobs


def test_thread_start_failure_reports_unavailable_and_next_refresh_retries():
    calls = []
    def launch(fn):
        calls.append(fn)
        if len(calls) == 1:
            raise RuntimeError("thread start refused")
    c = InspectionController(scanner=lambda *a: snapshot(), launch=launch)
    c.open()
    assert c.view()["status"] == "unavailable" and "thread start refused" in c.view()["error"]
    c.refresh()
    assert len(calls) == 2
    calls[-1]()
    assert c.view()["status"] == "ready"


def test_reopen_preserves_explicit_pin_but_requires_new_validation():
    h = Harness(); h.ready(); h.controller.pin(); h.controller.close()
    h.controller.open()
    assert h.controller.view()["status"] == "loading"
    h.reply = ValueError("SELECTION_STALE: the pinned scene changed while closed")
    h.finish()
    assert "expected_identities" in h.requests[-1]
    assert h.controller.view()["pinned"] and h.controller.view()["status"] == "stale"


@pytest.mark.parametrize("field,value", [("topology_hash", "short"), ("topology_hash", "A" * 64),
    ("topology_hash", "g" * 64), ("session_token", 42), ("session_token", ""),
    ("hip_path", ""), ("hip_path", "   "), ("hip_path", None)])
def test_malformed_capture_cannot_be_reused(field, value):
    h = Harness()
    if field == "topology_hash": h.reply[field] = value
    else: h.reply["scene"][field] = value
    h.ready()
    with pytest.raises(ValueError): h.controller.pin()
    with pytest.raises(ValueError): h.controller.prepare("explain_selection")
    assert not h.jobs
