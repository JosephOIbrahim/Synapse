"""Scope, provenance and acknowledgement regressions from the captured demo."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from synapse.memory import models, scene_memory, store
from synapse.memory.models import Memory, MemoryTier, MemoryType
from synapse.mcp._tool_registry import TOOL_DISPATCH, TOOL_JSON
from synapse.session import tracker


@pytest.fixture
def bridge(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "HOU_AVAILABLE", False)
    monkeypatch.setattr(tracker, "HOU_AVAILABLE", False)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    memory = store.SynapseMemory(str(tmp_path))
    obj = tracker.SynapseBridge.__new__(tracker.SynapseBridge)
    obj._synapse = memory
    obj._markdown_sync = None
    obj._context_cache = None
    yield obj
    memory.save()


def test_explicit_scope_survives_tool_payload_and_defaults_to_scene():
    schema = TOOL_JSON["synapse_decide"]["inputSchema"]["properties"]
    assert set(schema["scope"]["enum"]) == {"scene", "project"}
    _, build = TOOL_DISPATCH["synapse_decide"]
    payload = build({"decision": "Warm coral", "scope": "project", "tags": ["look"]})
    assert payload["scope"] == "project" and payload["tags"] == ["look"]
    assert "scope" not in build({"decision": "Local adjustment"})


def test_decision_tier_and_scope_receipt_persist_before_acknowledgement(bridge):
    result = bridge.handle_memory_decide({
        "decision": "Approved warm coral look", "reasoning": "Chosen during the demo",
        "scope": "project",
    })
    # Reopen immediately: do not explicitly save here and accidentally test
    # a different durability boundary than the artist's success receipt.
    reopened = store.SynapseMemory(str(bridge._synapse.project_path))
    records = reopened.recall("coral look")
    assert len(records) == 1 and records[0].id == result["id"]
    assert records[0].tier is MemoryTier.SHOW
    assert result["scope"] == "project" and result["tier"] == "show"
    assert Path(result["storage_dir"]) == bridge._synapse.storage_dir


def test_project_recall_filters_scene_decisions(bridge):
    project = bridge.handle_memory_decide({"decision": "Coral product palette", "scope": "project"})
    local = bridge.handle_memory_decide({"decision": "Coral sphere placement", "scope": "scene"})
    recalled = bridge.handle_memory_recall({"query": "coral", "scope": "project"})
    assert [r["id"] for r in recalled["matches"]] == [project["id"]]
    assert set(recalled["matches"][0]) == {"id", "summary", "content", "date"}
    assert bridge._synapse.store.get(local["id"]).tier is MemoryTier.SHOT


@pytest.mark.parametrize("method, key", [("handle_memory_recall", "matches"), ("handle_memory_search", "results")])
def test_scene_queries_exclude_siblings_and_retain_save_as_lineage(bridge, method, key):
    from synapse.host.memory_lifecycle import _save_lineage
    memory = bridge._synapse
    scene_a = memory.project_path / "a.hip"
    scene_b = memory.project_path / "b.hip"
    saved_as = memory.project_path / "a_saved_as.hip"
    memory._memory_binding = SimpleNamespace(hip_path=str(saved_as))
    _save_lineage(memory, str(saved_as), {str(scene_a.resolve())})
    for identity, hip in [("current", scene_a), ("sibling", scene_b)]:
        memory.store.add(Memory(id=identity, content="Approved coral look " + identity,
            memory_type=MemoryType.DECISION, tier=MemoryTier.SHOT, hip_file=str(hip)))
    result = getattr(bridge, method)({"query": "coral look", "scope": "scene"})
    assert [row["id"] for row in result[key]] == ["current"]


@pytest.mark.parametrize("scope", ["studio", "both", "", 4])
def test_invalid_decision_scope_never_writes(bridge, scope):
    before = bridge._synapse.store.count()
    result = bridge.handle_memory_decide({"decision": "Should not store", "scope": scope})
    assert result.get("recorded") is False and result.get("error")
    assert bridge._synapse.store.count() == before


def test_same_job_and_hip_mirror_uses_explicit_project_directory(bridge, monkeypatch):
    base = bridge._synapse.project_path
    paths = {"scene_dir": str(base / "claude"), "project_dir": str(base / "claude")}
    Path(paths["scene_dir"]).mkdir()
    (base / "claude" / "memory.md").write_text("Scene\n", encoding="utf-8")
    (base / "claude" / "project.md").write_text("Project\n", encoding="utf-8")
    monkeypatch.setattr(tracker, "HOU_AVAILABLE", True)
    monkeypatch.setattr(tracker, "hou", SimpleNamespace(
        hipFile=SimpleNamespace(path=lambda: str(base / "demo.hip")),
        getenv=lambda *a: str(base),
    ))
    monkeypatch.setattr(scene_memory, "ensure_scene_structure", lambda *args: paths)
    result = bridge.handle_memory_decide({"decision": "Keep coral", "scope": "project"})
    project_text = (base / "claude" / "project.md").read_text(encoding="utf-8")
    assert "Keep coral" in project_text and result["id"] in project_text
    assert "Keep coral" not in (base / "claude" / "memory.md").read_text(encoding="utf-8")


def test_failed_durable_write_never_returns_recorded_true(bridge, monkeypatch):
    def failed_save():
        raise OSError("Injected disk full")
    with monkeypatch.context() as patch:
        patch.setattr(bridge._synapse.store, "save", failed_save)
        result = bridge.handle_memory_decide({"decision": "Unsettled decision"})
        assert result.get("recorded") is False
        assert "disk full" in result["error"]


def test_same_second_decisions_at_different_scopes_keep_both_records(bridge, monkeypatch):
    monkeypatch.setattr(models.time, "strftime", lambda *args: "2026-09-09T20:00:00Z")
    project = bridge.handle_memory_decide({"decision": "Use warm coral", "scope": "project"})
    scene = bridge.handle_memory_decide({"decision": "Use warm coral", "scope": "scene"})
    assert project["recorded"] and scene["recorded"] and project["id"] != scene["id"]
    hits = bridge.handle_memory_recall({"query": "warm coral", "scope": "project"})
    assert [m["id"] for m in hits["matches"]] == [project["id"]]


def test_failed_second_scope_write_does_not_evict_durable_record(bridge, monkeypatch):
    monkeypatch.setattr(models.time, "strftime", lambda *args: "2026-09-09T20:00:00Z")
    project = bridge.handle_memory_decide({"decision": "Use warm coral", "scope": "project"})
    before = bridge._synapse.store.get(project["id"]).to_json()
    with monkeypatch.context() as patch:
        patch.setattr(bridge._synapse.store, "save", lambda: (_ for _ in ()).throw(OSError("disk full")))
        failed = bridge.handle_memory_decide({"decision": "Use warm coral", "scope": "scene"})
    assert failed["recorded"] is False
    assert bridge._synapse.store.get(project["id"]).to_json() == before


def test_checked_jsonl_identity_collision_keeps_existing_record(bridge):
    backend = bridge._synapse.store
    original = Memory(id="shared-id", content="Artist's existing decision")
    backend.add_durable_if_absent(original)
    with pytest.raises(ValueError, match="identity"):
        backend.add_durable_if_absent(Memory(id="shared-id", content="Different data"))
    assert backend.get("shared-id").to_json() == original.to_json()


@pytest.mark.parametrize("damage", ["malformed", "conflicting_id", "missing_identity", "invalid_utf8"])
def test_decision_refuses_incomplete_source_without_changing_bytes(tmp_path, monkeypatch, damage):
    monkeypatch.setattr(store, "HOU_AVAILABLE", False)
    monkeypatch.setattr(tracker, "HOU_AVAILABLE", False)
    monkeypatch.setattr(store, "_get_crypto", lambda: None)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "jsonl")
    directory = tmp_path / ".synapse"
    directory.mkdir()
    original = Memory(id="prior", content="Artist's durable coral decision")
    extra = {
        "malformed": b"{unfinished record",
        "conflicting_id": Memory(id="prior", content="Conflicting replacement").to_json().encode(),
        "missing_identity": b'{"content": "Decision without identity"}',
        "invalid_utf8": b"\xff\xfe",
    }[damage]
    before = original.to_json().encode() + b"\n" + extra + b"\n"
    path = directory / "memory.jsonl"
    path.write_bytes(before)
    owner = store.SynapseMemory(str(tmp_path))
    obj = tracker.SynapseBridge.__new__(tracker.SynapseBridge)
    obj._synapse, obj._markdown_sync, obj._context_cache = owner, None, None
    try:
        result = obj.handle_memory_decide({"decision": "New demo look", "scope": "project"})
        assert result["recorded"] is False and result["error"]
        with pytest.raises(RuntimeError, match="DEGRADED"):
            owner.store.save()
        owner.store.flush()
        assert path.read_bytes() == before
        assert not any(m.content == "New demo look" for m in owner.store.all())
    finally:
        owner.store._shutdown_flush()


def test_identical_jsonl_duplicate_remains_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "_get_crypto", lambda: None)
    original = Memory(id="prior", content="Artist's durable coral decision")
    (tmp_path / "memory.jsonl").write_text((original.to_json() + "\n") * 2, encoding="utf-8")
    backend = store.MemoryStore(tmp_path, background_load=False)
    try:
        backend.add_durable_if_absent(Memory(id="new", content="New decision"))
        assert {m.id for m in backend.all()} == {"prior", "new"}
        assert len((tmp_path / "memory.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    finally:
        backend._shutdown_flush()
