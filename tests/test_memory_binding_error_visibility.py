"""R-031 — a failed Save As memory carry must be VISIBLE, not written to nothing.

THE DEFECT THESE PIN
--------------------
``memory_lifecycle._handle_event`` caught a failed ``ensure_current_memory`` and
wrote the reason to ``owner._memory_binding_error``. Nothing read that
attribute: ``synapse_memory_status`` and ``synapse_health`` reported a normal
store, so the artist saved, believed memory followed, and it did not. The most
concrete trigger is the one the R-033 incident left behind — duplicate memory
identities, which make ``_records`` refuse the whole carry.

Each test drives that failure with a REAL ``MemoryStore`` over a REAL duplicate
JSONL file (no MagicMock store, no ``hou``), then asserts the error is readable
on both health surfaces with the old and new project named, and that the next
memory call retries the carry.
"""

from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from synapse.host import memory_lifecycle as lifecycle
from synapse.memory import store as store_module
from synapse.memory.models import Memory, MemoryType
from synapse.server.handlers_memory import MemoryHandlerMixin


# ---------------------------------------------------------------------------
# A host seat: an unsaved scene being Save-As'd into a project whose carry
# fails. No ``hou`` — the lifecycle is driven through its own entry point.
# ---------------------------------------------------------------------------

def _write_jsonl(directory: Path, *, duplicate: bool) -> Memory:
    directory.mkdir(parents=True, exist_ok=True)
    record = Memory(content="Warm rim light stays", memory_type=MemoryType.DECISION)
    lines = [record.to_json()]
    if duplicate:
        conflicting = json.loads(record.to_json())
        conflicting["content"] = "Warm rim light stays (conflicting copy)"
        lines.append(json.dumps(conflicting, sort_keys=True))
    (directory / "memory.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return record


def _seat(tmp_path, monkeypatch, *, duplicate):
    monkeypatch.delenv("SYNAPSE_ENCRYPTION_KEY", raising=False)
    monkeypatch.delenv("SYNAPSE_MEMORY_BACKEND", raising=False)

    old_project = tmp_path / "untitled"
    old_store_dir = old_project / ".synapse"
    record = _write_jsonl(old_store_dir, duplicate=duplicate)
    store = store_module.MemoryStore(old_store_dir, background_load=False)
    old_binding = lifecycle.MemoryBinding(
        hip_path=str(tmp_path / "untitled.hip"), scene_dir=old_project,
        project_dir=old_project, unsaved=True, project_source="unsaved")
    owner = types.SimpleNamespace(
        storage_dir=old_store_dir, store=store, project_path=old_project,
        _memory_binding=old_binding)

    new_project = tmp_path / "show"
    new_hip = new_project / "shot.hip"
    new_binding = lifecycle.MemoryBinding(
        hip_path=str(new_hip), scene_dir=new_project, project_dir=new_project,
        unsaved=False, project_source="hip_directory")

    # The host globals the lifecycle reads. No worker thread, no hou.
    monkeypatch.setattr(store_module, "_global_synapse", owner)
    monkeypatch.setattr(store_module, "HOU_AVAILABLE", True)
    monkeypatch.setattr(store_module, "_read_on_main", lambda fn, **kwargs: fn())
    monkeypatch.setattr(lifecycle, "current_binding", lambda hou_module=None: new_binding)
    monkeypatch.setattr(lifecycle, "register_owner", lambda seat_owner: None)
    monkeypatch.setattr(lifecycle, "_refresh_bridge", lambda seat_owner: None)

    return types.SimpleNamespace(
        root=tmp_path, owner=owner, store=store, record=record,
        old_project=old_project, old_store_dir=old_store_dir,
        new_project=new_project, new_hip=new_hip, new_binding=new_binding)


@pytest.fixture
def failing_save(tmp_path, monkeypatch):
    """The Save As whose carry refuses: the source holds one identity twice."""
    return _seat(tmp_path, monkeypatch, duplicate=True)


@pytest.fixture
def clean_source(tmp_path, monkeypatch):
    """The same seat with a sound source, for the retry half of the predicate."""
    return _seat(tmp_path, monkeypatch, duplicate=False)


def _drive_failed_save(seat):
    with pytest.raises(RuntimeError, match="conflicting duplicate identity"):
        lifecycle.ensure_current_memory(cause="save")


# ---------------------------------------------------------------------------
# 1. The failure is recorded, and it names BOTH projects
# ---------------------------------------------------------------------------

def test_failed_save_records_the_error_and_both_projects(failing_save):
    seat = failing_save
    _drive_failed_save(seat)

    # The rebind did not publish: the old owner still serves.
    assert store_module._global_synapse is seat.owner

    report = lifecycle.pending_binding_report()
    assert report is not None, "the failed carry must survive the callback frame"
    assert report["status"] == "failed"
    assert report["cause"] == "save"
    assert "conflicting duplicate identity" in report["error"]
    assert report["old_project"] == str(seat.old_project)
    assert report["new_project"] == str(seat.new_project)
    assert report["hip_path"] == str(seat.new_hip)
    assert report["recovery"]


def test_a_successful_carry_reports_nothing_pending(clean_source):
    """The control: the same reader is silent when the carry worked."""
    assert lifecycle.pending_binding_report() is None
    seat = clean_source
    rebound = lifecycle.ensure_current_memory(cause="save")
    assert lifecycle._key(rebound.storage_dir) == lifecycle._key(
        seat.new_project / ".synapse")
    assert lifecycle.pending_binding_report() is None


# ---------------------------------------------------------------------------
# 2. synapse_memory_status reports it — even when the retry fails again
# ---------------------------------------------------------------------------

class _StatusHandler(MemoryHandlerMixin):
    """Just enough host for ``_handle_memory_status``: no hou, no marshal."""

    def __init__(self, bridge):
        self._bridge_obj = bridge

    @staticmethod
    def _scene_paths():
        return {"hip_path": "shot.hip", "hip_dir": "show",
                "job_path": "show", "job_root": "show"}

    def _memory_on_main(self, callback):
        # What production does: refresh_memory_owner() -> ensure_current_memory().
        # With a pending carry this RETRIES it on main before the read.
        lifecycle.ensure_current_memory()
        return callback(self._bridge_obj)


@pytest.fixture
def scene_status(monkeypatch):
    from synapse.memory import scene_memory

    monkeypatch.setattr(scene_memory, "get_memory_status",
                        lambda scene_dir, project_dir: {
                            "project": {"evolution": "none"},
                            "scene": {"evolution": "none"},
                            "agent": {"status": "idle"},
                        })


def test_memory_status_reports_the_pending_binding_error(
        failing_save, scene_status):
    seat = failing_save
    _drive_failed_save(seat)

    handler = _StatusHandler(types.SimpleNamespace(_synapse=seat.owner))
    status = handler._handle_memory_status({})

    assert status["binding"]["status"] == "failed"
    assert "conflicting duplicate identity" in status["binding"]["error"]
    assert status["binding"]["old_project"] == str(seat.old_project)
    assert status["binding"]["new_project"] == str(seat.new_project)

    # The retry inside the hop failed again: health must not read green, and
    # the reason must be the same one -- a generic "unknown" would hide the cause.
    assert status["health"]["status"] == "unknown"
    assert "conflicting duplicate identity" in status["health"]["reason"]


def test_memory_status_is_ok_when_no_carry_is_pending(clean_source, scene_status):
    handler = _StatusHandler(types.SimpleNamespace(_synapse=clean_source.owner))
    status = handler._handle_memory_status({})
    assert status["binding"]["status"] == "ok"
    assert status["binding"]["error"] is None


# ---------------------------------------------------------------------------
# 3. synapse_health reports it too
# ---------------------------------------------------------------------------

def test_get_health_reports_the_pending_binding_error(failing_save, monkeypatch):
    seat = failing_save
    _drive_failed_save(seat)

    from synapse.server import handlers as server_handlers
    from synapse.server import preflight_gate, write_plane

    # Keep the health call hermetic: the two heavyweight neighbours are stubbed
    # so this asserts the NEW field, not a disk probe.
    monkeypatch.setattr(write_plane, "write_plane_state", lambda: {"status": "ok"})
    monkeypatch.setattr(preflight_gate, "readiness",
                        lambda client_version=None: {"status": "ready"})

    health = server_handlers.SynapseHandler._handle_get_health(
        types.SimpleNamespace(), {})

    assert health["memory_binding"]["status"] == "failed"
    assert "conflicting duplicate identity" in health["memory_binding"]["error"]
    assert health["memory_binding"]["old_project"] == str(seat.old_project)
    assert health["memory_binding"]["new_project"] == str(seat.new_project)


def test_get_health_memory_binding_is_none_without_a_pending_carry(clean_source,
                                                                  monkeypatch):
    from synapse.server import handlers as server_handlers
    from synapse.server import preflight_gate, write_plane

    monkeypatch.setattr(write_plane, "write_plane_state", lambda: {"status": "ok"})
    monkeypatch.setattr(preflight_gate, "readiness",
                        lambda client_version=None: {"status": "ready"})

    health = server_handlers.SynapseHandler._handle_get_health(
        types.SimpleNamespace(), {})
    assert "memory_binding" in health
    assert health["memory_binding"] is None


# ---------------------------------------------------------------------------
# 4. The next memory call RETRIES the carry and clears the record
# ---------------------------------------------------------------------------

def test_next_memory_call_retries_the_failed_carry(clean_source, monkeypatch):
    seat = clean_source
    real_records = lifecycle._records
    source_reads = []

    def flaky(owner):
        # Only the SOURCE reads fail; the post-copy verification reads on the
        # replacement store must behave normally.
        if owner is seat.owner:
            source_reads.append(owner)
            if len(source_reads) == 1:
                raise RuntimeError("Source memory has duplicate identities")
        return real_records(owner)

    monkeypatch.setattr(lifecycle, "_records", flaky)

    with pytest.raises(RuntimeError, match="duplicate identities"):
        lifecycle.ensure_current_memory(cause="save")
    assert lifecycle.pending_binding_report() is not None

    # No explicit cause: the pending cause/hip is what tells this call to retry.
    rebound = lifecycle.ensure_current_memory()

    assert len(source_reads) == 2, "the failed carry was never retried"
    assert lifecycle._key(rebound.storage_dir) == lifecycle._key(
        seat.new_project / ".synapse")
    assert lifecycle.pending_binding_report() is None
    assert seat.record.id in {m.id for m in rebound.store.all()}
