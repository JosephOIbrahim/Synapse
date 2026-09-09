"""Interrupted legacy outbox recovery with an explicit recording substrate.

No real ledger or memory store is opened. The fixture independently models an
already-authored forecast; recovery is forbidden from authoring or dispatching.
"""
import json
from pathlib import Path

import pytest

from synapse.loop.coordinator import LoopCoordinator, canonical, create, digest
from synapse.loop.ports import PortResult


@pytest.fixture
def legacy(tmp_path):
    attempt = {"id": "a" * 32, "operation": "create_node",
        "created_at": "2020-01-01T00:00:00+00:00", "horizon": "2020-01-01T00:10:00+00:00",
        "context_sha256": digest({}), "input_sha256": digest({"type": "null"})}
    record = {"schema": 1, "attempt": attempt, "context": {"payload": {"context": {}}},
        "relation_keys": ["/stage"]}
    folder = tmp_path / "attempts" / attempt["id"]
    create(folder / "request.json", record)
    create(tmp_path / "pending" / (attempt["id"] + ".json"), {"id": attempt["id"]})
    calls, capsules = [], {}
    available = [True]

    def worker(request):
        calls.append(request)
        assert request["action"] in {"status", "settle"}, "recovery reauthored or replayed"
        if not available[0]:
            return PortResult.unavailable("Recording substrate absent")
        if request["action"] == "status":
            return PortResult.ok({"forecast_digest": "b" * 64})
        assert request["forecast_digest"] == "b" * 64
        terminal = request.get("terminal")
        value = terminal.get("value") if terminal else None
        verdict = "UNRESOLVABLE" if value is None else "HIT" if value else "MISS"
        return PortResult.ok({"outcome": {"verdict": verdict, "recording_double": True}})

    def deposit(capsule):
        if capsule["id"] in capsules:
            assert capsules[capsule["id"]] == capsule
        capsules[capsule["id"]] = capsule
        return PortResult.ok({"id": capsule["id"], "recording_double": True})

    return tmp_path, folder, record, worker, deposit, calls, capsules, available


@pytest.mark.parametrize("tail", [None, b'{"event":"terminal","terminal":',
    b'{"event":"terminal","note":"\xe2\x82',
    b'{"event":"terminal","terminal":{"value":true}}'])
def test_missing_or_uncommitted_tail_recovers_unknown_without_reauthoring(legacy, tail):
    root, folder, record, worker, deposit, calls, capsules, _ = legacy
    journal = folder / "journal.jsonl"
    if tail is not None:
        journal.write_bytes(tail)
    loop = LoopCoordinator(root, worker, deposit)
    result = loop.recover()
    assert result[0]["status"] == "SUCCESS", result
    assert result[0]["payload"]["outcome"]["verdict"] == "UNRESOLVABLE"
    assert [request["action"] for request in calls] == ["status", "settle"]
    assert calls[-1].get("terminal") is None
    assert len(capsules) == 1
    assert LoopCoordinator(root, worker, deposit).recover() == []
    if tail is not None:
        assert journal.read_bytes() == tail, "damaged source evidence was rewritten"


def test_complete_terminal_survives_torn_delivery_and_reopened_retry(legacy):
    root, folder, _, worker, deposit, calls, capsules, _ = legacy
    terminal = {"value": True, "arrived_at": "2020-01-01T00:00:01+00:00", "result_sha256": "c" * 64}
    source = (canonical({"event": "terminal", "terminal": terminal}) + "\n").encode() + b'{"event":"delivery"'
    (folder / "journal.jsonl").write_bytes(source)
    first = LoopCoordinator(root, worker, lambda capsule: PortResult.unavailable("deposit busy"))
    assert first.recover()[0]["status"] == "UNAVAILABLE"
    second = LoopCoordinator(root, worker, deposit)
    result = second.recover()[0]
    assert result["status"] == "SUCCESS", result
    assert result["payload"]["outcome"]["verdict"] == "HIT"
    assert all(request.get("terminal") == terminal for request in calls if request["action"] == "settle")
    assert (folder / "journal.jsonl").read_bytes() == source
    assert len(capsules) == 1 and second.recover() == []


def test_complete_corruption_is_not_silently_discarded(legacy):
    root, folder, _, worker, deposit, calls, capsules, _ = legacy
    source = b'{"event":"terminal",BROKEN}\n'
    (folder / "journal.jsonl").write_bytes(source)
    result = LoopCoordinator(root, worker, deposit).recover()[0]
    assert result["status"] in {"BLOCKED", "UNAVAILABLE"}
    assert not calls and not capsules
    assert (folder / "journal.jsonl").read_bytes() == source


def test_absent_forecast_remains_pending_then_reconciles_existing_forecast(legacy):
    root, _, _, worker, deposit, calls, capsules, available = legacy
    available[0] = False
    loop = LoopCoordinator(root, worker, deposit)
    assert loop.recover()[0]["status"] == "UNAVAILABLE"
    assert [request["action"] for request in calls] == ["status"]
    assert not capsules
    available[0] = True
    assert LoopCoordinator(root, worker, deposit).recover()[0]["status"] == "SUCCESS"
    assert all(request["action"] != "author" for request in calls)


def test_conflicting_complete_terminals_are_refused(legacy):
    root, folder, _, worker, deposit, calls, capsules, _ = legacy
    entries = [{"event": "terminal", "terminal": {"value": value,
        "arrived_at": "2020-01-01T00:00:01+00:00", "result_sha256": "c" * 64}}
        for value in (True, False)]
    (folder / "journal.jsonl").write_text("".join(canonical(item) + "\n" for item in entries), encoding="utf-8")
    assert LoopCoordinator(root, worker, deposit).recover()[0]["status"] == "BLOCKED"
    assert not calls and not capsules


def test_interrupted_event_publication_retains_bytes_without_admitting_terminal(legacy, monkeypatch):
    import synapse.loop.coordinator as module
    root, folder, record, worker, deposit, calls, _, _ = legacy
    original = module.os.replace
    def interrupt(source, target):
        assert Path(source).suffix == ".part"
        raise OSError("interrupted before atomic publication")
    monkeypatch.setattr(module.os, "replace", interrupt)
    with pytest.raises(OSError, match="before atomic"):
        LoopCoordinator(root, worker, deposit).finish(record, True, "c" * 64)
    leftovers = {path: path.read_bytes() for path in folder.glob("journal.jsonl.d/*.part")}
    assert len(leftovers) == 1
    assert json.loads(next(iter(leftovers.values())))["terminal"]["value"] is True
    monkeypatch.setattr(module.os, "replace", original)
    recovered = LoopCoordinator(root, worker, deposit).recover()[0]
    assert recovered["status"] == "SUCCESS"
    assert recovered["payload"]["outcome"]["verdict"] == "UNRESOLVABLE"
    assert all(request.get("terminal") is None for request in calls if request["action"] == "settle")
    assert all(path.read_bytes() == data for path, data in leftovers.items())


def test_event_is_flushed_before_atomic_publication(tmp_path, monkeypatch):
    import synapse.loop.coordinator as module
    actual_sync, actual_replace = module.os.fsync, module.os.replace
    transitions = []
    def sync(fd):
        actual_sync(fd)
        transitions.append("fsync")
    def publish(source, target):
        assert transitions == ["fsync"]
        assert json.loads(Path(source).read_text()) == {"event": "probe"}
        assert not Path(target).exists()
        actual_replace(source, target)
        transitions.append("published")
    monkeypatch.setattr(module.os, "fsync", sync)
    monkeypatch.setattr(module.os, "replace", publish)
    journal = tmp_path / "journal.jsonl"
    module.append(journal, {"event": "probe"})
    assert transitions == ["fsync", "published"]
    assert module.read_journal(journal) == [{"event": "probe"}]
