"""Real Hanish worker contract; the optional dependency is never replaced by a fake."""
from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from synapse.loop import hanish_worker as worker

CREATED = "2026-09-08T00:00:00+00:00"
ARRIVED = "2026-09-08T00:00:01+00:00"
HORIZON = "2026-09-08T00:01:00+00:00"
AFTER = "2026-09-08T00:01:01+00:00"


@pytest.fixture(autouse=True)
def real_hanish(monkeypatch):
    selected = os.environ.get("SYNAPSE_TEST_HANISH_ROOT")
    original_module_names = {name for name in sys.modules
                             if name == "hanish" or name.startswith("hanish.")}
    if selected:
        root = Path(selected).resolve()
        if not (root / "hanish" / "__init__.py").is_file():
            pytest.fail("SYNAPSE_TEST_HANISH_ROOT does not contain the real Hanish package")
        # Other suites may already have imported a different installed version.
        # Restore their modules after this test; do not leak our source choice.
        for name in tuple(sys.modules):
            if name == "hanish" or name.startswith("hanish."):
                monkeypatch.delitem(sys.modules, name)
        monkeypatch.syspath_prepend(str(root))
        importlib.invalidate_caches()
    package = pytest.importorskip("hanish", reason="real optional Hanish package is not on the test path")
    if selected and Path(package.__file__).resolve().parent.parent != root:
        pytest.fail("The selected Hanish source was not imported")
    try:
        worker._api()
    except (ImportError, AttributeError) as exc:
        if selected:
            pytest.fail(f"Selected real Hanish source lacks the worker's required public API: {exc}")
        pytest.skip(f"Discovered Hanish lacks the required v0.2 public API: {exc}")
    monkeypatch.setattr(worker, "utc_now", lambda: ARRIVED)
    yield
    if selected:
        for name in tuple(sys.modules):
            if (name == "hanish" or name.startswith("hanish.")) and name not in original_module_names:
                sys.modules.pop(name, None)


@pytest.fixture
def request_data(tmp_path):
    return {
        "action": "author", "ledger_dir": str(tmp_path / "ledger"),
        "attempt": {"id": "attempt-1", "operation": "create_node", "created_at": CREATED,
                    "horizon": HORIZON, "context_sha256": "c" * 64},
    }


def settle_request(request, ack, value=True, *, at=ARRIVED):
    return {**copy.deepcopy(request), "action": "settle",
            "forecast_digest": ack["payload"]["forecast_digest"],
            "terminal": {"value": value, "arrived_at": at, "result_sha256": "d" * 64}}


def test_author_ack_binds_exact_durable_forecast(request_data, monkeypatch):
    import hanish.past.ledger as ledger
    original = ledger.os.fsync
    calls = []

    def fsync(fd):
        calls.append(fd)
        return original(fd)

    monkeypatch.setattr(ledger.os, "fsync", fsync)
    reply = worker.handle(request_data)
    assert reply["status"] == "SUCCESS", reply
    rows = (Path(request_data["ledger_dir"]) / "forecasts.jsonl").read_text().splitlines()
    assert len(rows) == 1 and calls
    row = json.loads(rows[0])
    serialized = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    independently_measured = "sha256:" + hashlib.sha256(serialized.encode()).hexdigest()
    assert reply["payload"]["forecast_digest"] == independently_measured
    assert reply["payload"]["durable_ack"]["forecast_digest"] == independently_measured
    assert row["probability"] == 0.5
    assert row["exposure"] == "EXPOSED"
    assert row["authored_by"] == "synapse-fixed-baseline-v1"
    assert row["resolution"]["observable"] == "synapse.handler_terminal_ok.v1"
    assert row["claim"] == "The synchronous handler returns without an explicit failure"
    assert not (Path(request_data["ledger_dir"]) / "evidence.jsonl").read_text().strip()


def test_repeated_author_is_exactly_idempotent_after_reopen(request_data):
    first = worker.handle(request_data)
    path = Path(request_data["ledger_dir"]) / "forecasts.jsonl"
    before = path.read_bytes()
    second = worker.handle(copy.deepcopy(request_data))
    assert second == first
    assert path.read_bytes() == before


def test_optional_input_digest_is_immutable_and_validated(request_data):
    request_data["attempt"]["input_sha256"] = "a" * 64
    ack = worker.handle(request_data)
    assert ack["status"] == "SUCCESS", ack
    row = json.loads((Path(request_data["ledger_dir"]) / "forecasts.jsonl").read_text())
    assert json.loads(row["world_commitment"])["attempt"]["input_sha256"] == "a" * 64
    request_data["attempt"]["input_sha256"] = "b" * 64
    assert worker.handle(request_data)["status"] == "BLOCKED"
    request_data["attempt"]["input_sha256"] = "invalid"
    assert worker.handle(request_data)["status"] == "BLOCKED"


@pytest.mark.parametrize("field,value", [
    ("operation", "delete_node"), ("context_sha256", "e" * 64),
    ("created_at", "2026-09-08T00:00:00.001+00:00"),
    ("horizon", "2026-09-08T00:02:00+00:00"),
])
def test_same_attempt_cannot_rewrite_commitment(request_data, field, value):
    assert worker.handle(request_data)["status"] == "SUCCESS"
    changed = copy.deepcopy(request_data)
    changed["attempt"][field] = value
    assert worker.handle(changed)["status"] == "BLOCKED"
    rows = (Path(request_data["ledger_dir"]) / "forecasts.jsonl").read_text().splitlines()
    assert len(rows) == 1


@pytest.mark.parametrize("value,verdict", [(True, "HIT"), (False, "MISS")])
def test_real_terminal_settles_and_persists_after_worker_reopen(request_data, value, verdict):
    ack = worker.handle(request_data)
    request = settle_request(request_data, ack, value)
    result = worker.handle(request)
    assert result["status"] == "SUCCESS", result
    outcome = result["payload"]["outcome"]
    assert outcome["terminal"] == "RESOLVED"
    assert outcome["verdict"] == verdict and outcome["observed"] is value
    assert outcome["calibration_eligible"] is False and outcome["brier"] == 0.25
    before = {p.name: p.read_bytes() for p in Path(request_data["ledger_dir"]).glob("*.jsonl")}
    repeated = worker.handle(request)
    assert repeated["payload"]["outcome"] == outcome
    assert {p.name: p.read_bytes() for p in Path(request_data["ledger_dir"]).glob("*.jsonl")} == before


def test_missing_forecast_never_backfilled(request_data):
    request_data["action"] = "settle"
    request_data["forecast_digest"] = "sha256:" + "a" * 64
    request_data["terminal"] = {"value": True, "arrived_at": ARRIVED, "result_sha256": "d" * 64}
    result = worker.handle(request_data)
    assert result["status"] == "UNAVAILABLE"
    assert result["payload"]["state"] == "UNINSTRUMENTED"
    assert not Path(request_data["ledger_dir"]).exists()


def test_author_cannot_receive_known_terminal_evidence(request_data):
    request_data["terminal"] = {"value": True, "arrived_at": ARRIVED, "result_sha256": "d" * 64}
    assert worker.handle(request_data)["status"] == "BLOCKED"
    assert not Path(request_data["ledger_dir"]).exists()


def test_missing_attempt_in_existing_ledger_never_authored(request_data):
    ack = worker.handle(request_data)
    request = settle_request(request_data, ack)
    request["attempt"]["id"] = "different"
    result = worker.handle(request)
    assert result["status"] == "UNAVAILABLE"
    assert len((Path(request_data["ledger_dir"]) / "forecasts.jsonl").read_text().splitlines()) == 1


@pytest.mark.parametrize("digest", [None, "sha256:" + "f" * 64])
def test_settle_requires_matching_forecast_digest(request_data, digest):
    ack = worker.handle(request_data)
    request = settle_request(request_data, ack)
    request["forecast_digest"] = digest
    result = worker.handle(request)
    assert result["status"] == "BLOCKED", result
    assert not (Path(request_data["ledger_dir"]) / "evidence.jsonl").read_text().strip()


def test_unknown_pending_then_unresolvable_never_sealed_or_scored(request_data, monkeypatch):
    ack = worker.handle(request_data)
    pending = worker.handle(settle_request(request_data, ack, None))
    assert pending["status"] == "UNAVAILABLE"
    assert pending["payload"]["state"] == "PENDING"
    monkeypatch.setattr(worker, "utc_now", lambda: AFTER)
    # Same stored arrival time: elapsed worker time must still close the horizon.
    unresolved = worker.handle(settle_request(request_data, ack, None))
    assert unresolved["status"] == "SUCCESS", unresolved
    outcome = unresolved["payload"]["outcome"]
    assert outcome["terminal"] == "UNRESOLVABLE"
    assert outcome["verdict"] is None and outcome["brier"] is None
    assert outcome["observed"] is None and outcome["calibration_eligible"] is False
    assert not (Path(request_data["ledger_dir"]) / "evidence.jsonl").read_text().strip()


def test_first_terminal_cannot_be_rescored_by_changed_retry(request_data):
    ack = worker.handle(request_data)
    first = worker.handle(settle_request(request_data, ack, False))
    before = {p.name: p.read_bytes() for p in Path(request_data["ledger_dir"]).glob("*.jsonl")}
    refused = worker.handle(settle_request(request_data, ack, True))
    assert refused["status"] == "BLOCKED"
    assert {p.name: p.read_bytes() for p in Path(request_data["ledger_dir"]).glob("*.jsonl")} == before
    again = worker.handle(settle_request(request_data, ack, False))
    assert again["payload"]["outcome"] == first["payload"]["outcome"]


def test_reusing_event_with_changed_result_digest_is_blocked(request_data):
    ack = worker.handle(request_data)
    request = settle_request(request_data, ack)
    assert worker.handle(request)["status"] == "SUCCESS"
    request["terminal"]["result_sha256"] = "e" * 64
    assert worker.handle(request)["status"] == "BLOCKED"


@pytest.mark.parametrize("invalid", [0, 1, "true", [], {}])
def test_terminal_type_is_strict_bool(request_data, invalid):
    ack = worker.handle(request_data)
    reply = worker.handle(settle_request(request_data, ack, invalid))
    assert reply["status"] == "BLOCKED"
    assert not (Path(request_data["ledger_dir"]) / "evidence.jsonl").read_text().strip()


def test_pre_forecast_evidence_is_refused(request_data):
    ack = worker.handle(request_data)
    reply = worker.handle(settle_request(request_data, ack, True, at=CREATED))
    assert reply["status"] == "BLOCKED"


def test_capture_failure_cannot_turn_green(request_data, monkeypatch):
    import hanish
    ack = worker.handle(request_data)
    monkeypatch.setattr(hanish.Substrate, "capture", lambda self, event: False)
    result = worker.handle(settle_request(request_data, ack))
    assert result["status"] == "UNAVAILABLE"
    assert not (Path(request_data["ledger_dir"]) / "outcomes.jsonl").read_text().strip()


def test_process_error_counter_cannot_turn_green(request_data, monkeypatch):
    import hanish
    ack = worker.handle(request_data)

    def broken_process(self, at=None):
        self.process_errors += 1
        return []

    monkeypatch.setattr(hanish.Substrate, "process", broken_process)
    assert worker.handle(settle_request(request_data, ack))["status"] == "BLOCKED"


def test_corrupt_forecast_is_refused_without_repair_or_append(request_data):
    assert worker.handle(request_data)["status"] == "SUCCESS"
    path = Path(request_data["ledger_dir"]) / "forecasts.jsonl"
    path.write_bytes(path.read_bytes() + b'{"torn":')
    before = path.read_bytes()
    assert worker.handle(request_data)["status"] == "BLOCKED"
    assert path.read_bytes() == before


def test_status_does_not_initialize_an_empty_ledger(request_data):
    result = worker.handle({"action": "status", "ledger_dir": request_data["ledger_dir"]})
    assert result["status"] == "SUCCESS" and result["payload"]["initialized"] is False
    assert not Path(request_data["ledger_dir"]).exists()


def test_status_reconciles_exact_lost_ack_without_authoring(request_data):
    first = worker.handle(request_data)
    path = Path(request_data["ledger_dir"]) / "forecasts.jsonl"
    before = path.read_bytes()
    recovered = worker.handle({**request_data, "action": "status"})
    assert recovered["status"] == "SUCCESS"
    assert recovered["payload"]["durable_ack"] == first["payload"]["durable_ack"]
    assert path.read_bytes() == before
    mismatch = copy.deepcopy(request_data)
    mismatch["action"] = "status"
    mismatch["attempt"]["input_sha256"] = "f" * 64
    assert worker.handle(mismatch)["status"] == "BLOCKED"
    assert path.read_bytes() == before


def test_status_of_missing_attempt_never_authors(request_data):
    result = worker.handle({**request_data, "action": "status"})
    assert result["status"] == "UNAVAILABLE"
    assert not Path(request_data["ledger_dir"]).exists()


def test_missing_dependency_has_an_honest_unavailable_envelope(request_data, monkeypatch):
    def unavailable():
        raise ModuleNotFoundError("hanish")
    monkeypatch.setattr(worker, "_api", unavailable)
    result = worker.handle(request_data)
    assert result["status"] == "UNAVAILABLE"
    assert "hanish" in result["error_message"]
    assert not Path(request_data["ledger_dir"]).exists()
