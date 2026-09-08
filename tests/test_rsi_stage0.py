"""Stage 0 data and storage controls. Fixtures here are SYNTHETIC unit data.

All writes use pytest's disposable directories. A separate native rehearsal
is required for qualification; these dictionaries never prove Houdini ran.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from synapse.memory import experience as ex
from synapse.memory import moneta_runtime as mr
from synapse.memory.embedding import HashEmbedder
from synapse.memory.models import Memory, MemoryType
from synapse.memory.moneta_store import MonetaBackedStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def report():
    return {
        "origin": "native_hython_rehearsal", "main_thread": True, "ui_available": False,
        "source_id": "synthetic-unit-001", "checked_at": "2026-09-08T17:00:00Z",
        "environment": {
            "houdini_build": "22.0.400", "synapse_version": "5.67.1",
            "implementation_sha256": hashlib.sha256(b"SYNTHETIC implementation").hexdigest(),
            "dependency_sha256": hashlib.sha256(b"SYNTHETIC dependency").hexdigest(),
            "producer": ex.PRODUCER, "checker": ex.CHECKER,
        },
        "request": {"template": ex.TASK, "parent": "/stage",
                    "template_params": {"name": "old_destination", "frequency": 4.0}},
        "result": {
            "status": "created", "template": ex.TASK, "dry_run": False,
            "resolution": [256, 256], "layout": "vertical",
            "verification": {
                "configuration": "verified", "usd": "verified", "geometry": "/World/plane",
                "material": "/Materials/mat", "binding": ["/Materials/mat"],
                "uv": "faceVarying st", "camera": "/camera", "render_settings": "/Render/settings",
                "texture_sources": {"base_color_file": "op:/stage/old/color{C}",
                                    "specular_roughness_file": "op:/stage/old/roughness{C}"},
                "texture_pixels": "not measured", "rendered_appearance": "not checked",
            },
        },
    }


@pytest.fixture
def record(report):
    return ex.make_experience(report, "SYNTHETIC unit fixture: fixed lookdev setup")


@pytest.fixture
def store(tmp_path):
    if not mr.moneta_available():
        pytest.skip("Moneta not installed: " + str(mr.import_error()))
    store = MonetaBackedStore.from_storage_dir(tmp_path / "memory", embedder=HashEmbedder(),
                                              dual_write_jsonl=False)
    yield store
    store.close()


@pytest.fixture
def adapter(store):
    return ex.ExperienceMemory(SimpleNamespace(store=store), enabled=True)


def test_source_key_is_stable_and_content_conflict_is_distinct(report):
    first = ex.make_experience(report, "First summary")
    second = ex.make_experience(report, "Changed summary")
    assert first["record_id"] == second["record_id"]
    assert first["record_sha256"] != second["record_sha256"]
    assert "name" not in first["procedure"]["parameters"]
    assert "parent" not in first["procedure"]


def test_noncanonical_timestamp_rejected(report):
    report["checked_at"] = "2026-9-8T17:0:0Z"
    with pytest.raises(ValueError, match="timestamp"):
        ex.make_experience(report, "Synthetic old date")


def test_newest_then_stable_identity_order(adapter, report):
    records = []
    for source, timestamp in (("older", "2026-09-08T17:00:00Z"),
                              ("newer-b", "2026-10-01T17:00:00Z"),
                              ("newer-a", "2026-10-01T17:00:00Z")):
        data = deepcopy(report)
        data.update(source_id=source, checked_at=timestamp)
        record = ex.make_experience(data, "Synthetic ordering")
        assert adapter.record(record)["status"] == "STORED"
        records.append(record)
    expected = min(records[1:], key=lambda r: r["record_id"])
    assert adapter.recall(ex.TASK, report["environment"], requested=True)["record_id"] == expected["record_id"]


def test_record_digest_protects_procedure(record):
    record["procedure"]["summary"] = "A different, still syntactically valid summary"
    assert ex.ExperienceMemory(enabled=True).record(record)["status"] == "INELIGIBLE"


@pytest.mark.parametrize("change", [
    lambda r: r.update(origin="chat"),
    lambda r: r.update(main_thread=False),
    lambda r: r.update(ui_available=True),
    lambda r: r["result"].update(dry_run=True),
    lambda r: r["result"].update(status="unknown"),
    lambda r: r["result"]["verification"].pop("geometry"),
    lambda r: r["result"]["verification"].update(usd="unknown"),
    lambda r: r["result"]["verification"].update(binding=["/wrong"]),
    lambda r: r["result"]["verification"].update(texture_pixels="verified"),
    lambda r: r["result"]["verification"].update(rendered_appearance="beautiful"),
    lambda r: r["environment"].pop("dependency_sha256"),
    lambda r: r["environment"].update(houdini_build="22.0.429"),
])
def test_incomplete_or_untrusted_reports_are_rejected(report, change):
    change(report)
    with pytest.raises((ValueError, TypeError)):
        ex.make_experience(report, "Synthetic")


def test_tampering_and_size_limit_rejected_without_storage(record):
    class ExplosiveOwner:
        @property
        def store(self):
            raise AssertionError("invalid records must not touch storage")

    adapter = ex.ExperienceMemory(ExplosiveOwner(), enabled=True)
    record["evidence"]["verification"]["camera"] = "/changed"
    assert adapter.record(record)["status"] == "INELIGIBLE"
    record["procedure"]["summary"] = "x" * (ex.MAX_BYTES + 1)
    assert adapter.record(record)["status"] == "INELIGIBLE"


def test_disabled_and_unrequested_paths_never_touch_owner():
    class ExplosiveOwner:
        @property
        def store(self):
            raise AssertionError("must not read storage")

    disabled = ex.ExperienceMemory(ExplosiveOwner())
    assert disabled.record(None)["status"] == "UNAVAILABLE"
    assert disabled.recall(None, None, requested=True)["status"] == "UNAVAILABLE"
    enabled = ex.ExperienceMemory(ExplosiveOwner(), enabled=True)
    assert enabled.recall(None, None)["status"] == "UNAVAILABLE"


def test_record_recall_and_exact_compatibility(adapter, record, monkeypatch, store):
    assert adapter.record(record)["status"] == "STORED"
    def forbidden(*args, **kwargs):
        raise AssertionError("recall invoked embedding, search, or a scene operation")
    monkeypatch.setattr(store._embedder, "embed", forbidden)
    monkeypatch.setattr(store, "search", forbidden)
    import hou
    monkeypatch.setattr(hou, "node", forbidden)
    hit = adapter.recall(ex.TASK, record["environment"], requested=True)
    assert hit["status"] == "HIT"
    assert hit["experience"] == record
    assert "not checked" in hit["explanation"]
    wrong = dict(record["environment"], synapse_version="5.67.2")
    assert adapter.recall(ex.TASK, wrong, requested=True)["status"] == "NO_MATCH"
    wrong = dict(record["environment"], dependency_sha256="0" * 64)
    assert adapter.recall(ex.TASK, wrong, requested=True)["status"] == "NO_MATCH"
    assert adapter.recall("scatter", record["environment"], requested=True)["status"] == "UNAVAILABLE"


def test_empty_store_is_a_complete_miss(adapter, record):
    assert adapter.recall(ex.TASK, record["environment"], requested=True) == {
        "status": "NO_MATCH", "reason": "No compatible checked experience", "complete": True}


def test_generic_ai_memory_cannot_claim_checked_experience(adapter, store, record):
    store.add(Memory(content=json.dumps(record, sort_keys=True), tags=[ex.NAMESPACE],
                     memory_type=MemoryType.FEEDBACK, source="ai"))
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "NO_MATCH"


def test_duplicate_and_conflicting_source_identity(adapter, store, report):
    first = ex.make_experience(report, "Synthetic first")
    changed = ex.make_experience(report, "Synthetic second")
    assert adapter.record(first)["status"] == "STORED"
    assert adapter.record(first)["status"] == "DUPLICATE"
    assert adapter.record(changed)["status"] == "INELIGIBLE"
    assert store.count() == 1


def test_real_snapshot_failure_and_lost_ack_retry(adapter, store, record, monkeypatch):
    durability = store._handle.durability
    def fail(_ecs):
        raise OSError("injected full disk")
    with monkeypatch.context() as patch:
        patch.setattr(durability, "snapshot_ecs", fail)
        assert adapter.record(record)["status"] == "UNAVAILABLE"
        assert adapter.record(record)["status"] == "UNAVAILABLE"
        assert store.count() == 1  # Failed acknowledgement is not rollback.
    assert adapter.record(record)["status"] == "DUPLICATE"
    assert store.count() == 1
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "HIT"


def test_legacy_add_still_logs_snapshot_failure(store, monkeypatch):
    def fail(_ecs):
        raise OSError("legacy best effort")
    with monkeypatch.context() as patch:
        patch.setattr(store._handle.durability, "snapshot_ecs", fail)
        assert store.add(Memory(content="ordinary note", id="legacy")) == "legacy"


def test_ephemeral_backend_never_reports_stored(record):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    store = MonetaBackedStore(mr.make_ephemeral(embedding_dim=256), HashEmbedder())
    try:
        adapter = ex.ExperienceMemory(SimpleNamespace(store=store), enabled=True)
        assert adapter.record(record)["status"] == "UNAVAILABLE"
        assert store.count() == 0
    finally:
        store.close()


def test_corrupt_payload_is_unavailable_not_a_miss(adapter, store, record):
    store._handle.deposit("not JSON", [0.0] * 256)
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "UNAVAILABLE"


@pytest.mark.parametrize("bad_tags", [ex.NAMESPACE, {ex.NAMESPACE: True}, [7], None])
def test_invalid_stored_tags_never_become_exact_matches(adapter, store, record, bad_tags):
    payload = Memory(id="bad-tags", content="Synthetic malformed data").to_dict()
    payload["tags"] = bad_tags
    store._handle.deposit(json.dumps(payload, sort_keys=True), [0.0] * 256)
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "UNAVAILABLE"


def test_empty_object_is_corrupt_not_an_empty_memory(adapter, store, record):
    store._handle.deposit("{}", [0.0] * 256)
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "UNAVAILABLE"
    assert adapter.record(record)["status"] == "UNAVAILABLE"


def test_missing_rows_snapshot_never_becomes_clean_miss(tmp_path):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    memory_dir = tmp_path / "damaged"
    (memory_dir / ".moneta").mkdir(parents=True)
    (memory_dir / ".moneta/snapshot.json").write_text('{"snapshot_version":1}', encoding="utf-8")
    for _ in range(2):
        store = MonetaBackedStore.from_storage_dir(memory_dir, HashEmbedder(), dual_write_jsonl=False)
        try:
            with pytest.raises(RuntimeError):
                store.get_by_tag_strict(ex.NAMESPACE)
        finally:
            store.close()


def test_partial_deposit_does_not_fallback_and_duplicate(adapter, store, record, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("index failure after ECS insert")
    with monkeypatch.context() as patch:
        patch.setattr(store._handle.vector_index, "upsert", fail)
        assert adapter.record(record)["status"] == "UNAVAILABLE"
    assert store.count() == 1
    assert adapter.record(record)["status"] == "UNAVAILABLE"
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "UNAVAILABLE"


def test_retry_repairs_real_jsonl_mirror_without_duplicate_lines(adapter, store, record, tmp_path, monkeypatch):
    from synapse.memory.store import MemoryStore
    net = MemoryStore(tmp_path / "mirror")
    store._jsonl_net = net
    try:
        def fail(_ecs):
            raise OSError("snapshot failed before mirror write")
        with monkeypatch.context() as patch:
            patch.setattr(store._handle.durability, "snapshot_ecs", fail)
            assert adapter.record(record)["status"] == "UNAVAILABLE"
        assert net.get(record["record_id"]) is None
        assert adapter.record(record)["status"] == "DUPLICATE"
        assert adapter.record(record)["status"] == "DUPLICATE"
        assert net.get(record["record_id"]).content == ex._json(record)
        assert len(net.memory_file.read_text(encoding="utf-8").splitlines()) == 1
    finally:
        net._shutdown_flush()


def test_candidate_bound_never_makes_false_miss(adapter, store, record):
    for i in range(ex.MAX_CANDIDATES + 1):
        store.add(Memory(id="candidate-" + str(i), content="ordinary feedback",
                         memory_type=MemoryType.FEEDBACK, tags=[ex.NAMESPACE]))
    response = adapter.recall(ex.TASK, record["environment"], requested=True)
    assert response["status"] == "UNAVAILABLE"
    assert "incomplete" in response["reason"]


def test_changed_stored_content_is_not_a_hit(adapter, store, record):
    assert adapter.record(record)["status"] == "STORED"
    memory = store.get(record["record_id"])
    damaged = deepcopy(record)
    damaged["evidence"]["verification"]["camera"] = "/tampered"
    memory.content = json.dumps(damaged, sort_keys=True)
    # Inject a corrupt row directly to model storage damage, not an authorized import.
    store._handle.deposit(memory.to_json(), [0.0] * 256)
    assert adapter.recall(ex.TASK, record["environment"], requested=True)["status"] == "UNAVAILABLE"


def test_fresh_process_recall_after_abrupt_exit(tmp_path, record):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    record_path = tmp_path / "synthetic-record.json"
    record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "python"), SYNAPSE_MEMORY_BACKEND="moneta")
    child = r'''
import json, os, sys
from synapse.memory.store import SynapseMemory
from synapse.memory.experience import ExperienceMemory, TASK
from synapse.memory.models import Memory
record = json.load(open(sys.argv[2], encoding="utf-8"))
owner = SynapseMemory(project_path=sys.argv[1])
adapter = ExperienceMemory(owner, enabled=True)
if sys.argv[3] == "record":
    owner.store.add(Memory(content="preceding ordinary deposit", id="preceding"))
    result = adapter.record(record)
else:
    result = adapter.recall(TASK, record["environment"], requested=True)
print(json.dumps(result, sort_keys=True), flush=True)
os._exit(0)
'''
    def run(mode):
        result = subprocess.run([sys.executable, "-c", child, str(project), str(record_path), mode],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout.strip().splitlines()[-1])
    assert run("recall")["status"] == "NO_MATCH"
    assert run("record")["status"] == "STORED"
    assert run("recall")["experience"] == record
    assert run("recall")["experience"] == record


def test_cli_disabled_does_not_open_nonexistent_inputs(tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "scripts/rsi_stage0.py"),
                             "--project-dir", str(tmp_path / "absent"), "recall",
                             "--environment", str(tmp_path / "missing.json")],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert "disabled" in json.loads(result.stdout)["reason"]
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("version", [None, 999, "1", True, 1.0])
def test_checked_factory_refuses_unknown_snapshot_version_untouched(tmp_path, version):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    store = MonetaBackedStore.from_storage_dir(tmp_path, HashEmbedder(), dual_write_jsonl=False)
    try:
        store.add(Memory(id="existing", content="existing ordinary memory"))
    finally:
        store.close()
    snapshot = tmp_path / ".moneta/snapshot.json"
    data = json.loads(snapshot.read_text(encoding="utf-8"))
    if version is None:
        del data["snapshot_version"]
    else:
        data["snapshot_version"] = version
    snapshot.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    before = snapshot.read_bytes()
    with pytest.raises(RuntimeError, match="snapshot format"):
        reopened = MonetaBackedStore.from_storage_dir(
            tmp_path, HashEmbedder(), dual_write_jsonl=False, require_compatible_snapshot=True)
        reopened.close()
    assert snapshot.read_bytes() == before


def test_cli_refuses_embedding_migration_without_embedding_or_rewrite(tmp_path, report, record, monkeypatch, capsys):
    if not mr.moneta_available():
        pytest.skip("Moneta unavailable")
    from synapse.memory.embedding import SemanticEmbedder
    project = tmp_path / "old-project"
    project.mkdir()
    store = MonetaBackedStore.from_storage_dir(project / ".synapse", HashEmbedder(dim=256),
                                              dual_write_jsonl=False)
    try:
        assert ex.ExperienceMemory(store, enabled=True).record(record)["status"] == "STORED"
    finally:
        store.close()
    snapshot = project / ".synapse/.moneta/snapshot.json"
    before = snapshot.read_bytes()
    report_path = tmp_path / "synthetic-report.json"
    report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("embed")
        raise AssertionError("Exact recall cannot re-embed existing storage")
    monkeypatch.setattr(SemanticEmbedder, "embed", forbidden)
    monkeypatch.setenv("SYNAPSE_MEMORY_BACKEND", "moneta")
    spec = importlib.util.spec_from_file_location("rsi_stage0_cli_under_test", ROOT / "scripts/rsi_stage0.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    code = cli.main(["--enable", "--project-dir", str(project), "recall", "--environment", str(report_path)])
    response = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert code == 2 and response["status"] == "UNAVAILABLE"
    assert "embedding dimension" in response["reason"]
    assert calls == []
    assert snapshot.read_bytes() == before
