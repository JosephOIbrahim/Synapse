"""Main-thread scene binding for the existing process memory authority.

This module owns context and a HIP callback, never a second store registry.
Only immutable memory records travel on Save As; outboxes and permissions stay
at their original addresses. The old store is retained on disk.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import sys
import threading
import uuid

_LOG = logging.getLogger(__name__)
_callback = None
_callback_hou = None
_loading = False
_unsaved_base = None
_MAX_RECORDS = 2000
_MAX_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class MemoryBinding:
    hip_path: str
    scene_dir: Path
    project_dir: Path
    unsaved: bool
    project_source: str


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


def current_binding(hou_module=None):
    """Read host context on main; choose an existing containing JOB or HIP."""
    from synapse.memory import store as module
    hou = hou_module if hou_module is not None else module.hou
    hip_path = str(hou.hipFile.path())
    unsaved = module.hip_is_unsaved(hip_path, hou)
    if unsaved:
        base = Path(_unsaved_base or module._safe_unsaved_base()).resolve()
        return MemoryBinding(hip_path, base, base, True, "unsaved")
    scene = Path(hip_path).resolve().parent
    raw = hou.getenv("JOB", "") if callable(getattr(hou, "getenv", None)) else ""
    # Embedded as well as whole-component tokens must not become disk paths.
    candidate = module._expand_and_validate(raw) if isinstance(raw, str) and raw.strip() else None
    source = "hip_directory"
    if candidate is not None and not re.search(r"\$[\w{]|%[^%]+%", str(candidate)):
        candidate = candidate.resolve()
        hfs = hou.getenv("HFS", "") if callable(getattr(hou, "getenv", None)) else ""
        install = Path(hfs).resolve() if isinstance(hfs, str) and hfs else None
        in_install = install is not None and candidate.is_relative_to(install)
        if (candidate.is_dir() and candidate != Path(candidate.anchor)
                and scene.is_relative_to(candidate) and not in_install):
            if not os.access(candidate, os.W_OK):
                raise RuntimeError(f"Configured project memory directory is not writable: {candidate}")
            return MemoryBinding(hip_path, scene, candidate, False, "job")
    return MemoryBinding(hip_path, scene, scene, False, source)


def _on_main(fn):
    from synapse.memory import store as module
    return module._read_on_main(fn, label="memory:lifecycle")


def _require_main():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Memory lifecycle requires the host main thread")


def register_owner(owner):
    """Called after host initialization; repeated panel opens add no callback."""
    global _callback, _callback_hou
    from synapse.memory import store as module
    if getattr(owner, "_memory_binding", None) is None or not module.HOU_AVAILABLE:
        return
    hou = module.hou
    if _callback is not None and _callback_hou is hou:
        return
    if _callback is not None and _callback_hou is not None:
        _callback_hou.hipFile.removeEventCallback(_callback)
    _callback = _handle_event
    hou.hipFile.addEventCallback(_callback)
    _callback_hou = hou


def _handle_event(event):
    global _loading, _unsaved_base
    from synapse.memory import store as module
    events = module.hou.hipFileEventType
    cause = None
    if event == events.BeforeLoad:
        _loading = True
    elif event == events.AfterLoad:
        _loading = False
        cause = "load"
    elif event == events.AfterSave:
        cause = "save"
    elif event == events.AfterClear and not _loading:
        # New File must not inherit an old session from the shared untitled root.
        _unsaved_base = module._safe_unsaved_base() / "sessions" / uuid.uuid4().hex
        cause = "clear"
    if cause is not None:
        try:
            ensure_current_memory(cause=cause)
        except Exception as exc:
            owner = module._global_synapse
            if owner is not None:
                owner._memory_binding_error = str(exc)
                owner._memory_pending_cause = cause
                owner._memory_pending_hip = str(module.hou.hipFile.path())
            _LOG.error("Memory %s binding failed; memory requests must retry or report unavailable: %s", cause, exc)


def _validate_jsonl(owner):
    """Legacy permissive reads must not authorize a lossy source rewrite."""
    from synapse.memory import store as module
    if not isinstance(owner.store, module.MemoryStore):
        return
    path = owner.store.memory_file
    if not path.exists():
        return
    if path.stat().st_size > _MAX_BYTES:
        raise RuntimeError("JSONL source exceeds the bounded migration read budget")
    crypto = module._get_crypto()
    seen = {}
    try:
        with path.open(encoding="utf-8") as stream:
            for number, raw in enumerate(stream, 1):
                line = raw.strip()
                if not line:
                    continue
                if crypto:
                    line = crypto.decrypt_line(line)
                data = json.loads(line)
                required = ("id", "created_at", "content", "memory_type")
                if (not isinstance(data, dict)
                        or any(not isinstance(data.get(key), str) for key in required)
                        or not data["id"] or not data["created_at"]):
                    raise ValueError(f"incomplete record on line {number}")
                # Validate enum/field decoding without inventing missing identity.
                module.Memory.from_dict(data)
                canonical = json.dumps(data, sort_keys=True)
                previous = seen.get(data["id"])
                if previous is not None and previous != canonical:
                    raise ValueError(f"conflicting duplicate identity on line {number}")
                seen[data["id"]] = canonical
    except Exception as exc:
        raise RuntimeError(f"Cannot migrate or rewrite incomplete JSONL source {path}: {exc}") from exc


def _records(owner):
    backend = owner.store
    strict = getattr(backend, "_iter_memories", None)
    if callable(strict):
        backend._require_durable()
        records = strict(strict=True)
    else:
        _validate_jsonl(owner)
        records = backend.all()
        if getattr(backend, "_degraded_load", False):
            raise RuntimeError("Cannot migrate a degraded memory store")
    if len(records) > _MAX_RECORDS or sum(len(m.to_json().encode("utf-8")) for m in records) > _MAX_BYTES:
        raise RuntimeError("Memory migration exceeds the bounded record/byte budget")
    ids = [m.id for m in records]
    if len(ids) != len(set(ids)):
        raise RuntimeError("Source memory has duplicate identities")
    return records


def _persist(owner):
    backend = owner.store
    if hasattr(backend, "_require_durable"):
        backend.save(require_durable=True)
    else:
        _validate_jsonl(owner)
        backend.flush()
        backend.save()


def _release(owner):
    closer = getattr(owner.store, "close", None)
    if callable(closer):
        closer()
    else:
        try:
            _validate_jsonl(owner)
        except Exception:
            owner.store._flusher_running = False
            raise
        owner.store._shutdown_flush()
        owner.store.save()


def _open(base):
    from synapse.memory import store as module
    owner = module.SynapseMemory(project_path=str(base))
    requested = os.environ.get("SYNAPSE_MEMORY_BACKEND", "jsonl").strip().lower()
    if requested == "moneta" and not hasattr(owner.store, "_require_durable"):
        _release(owner)
        raise RuntimeError("Project memory replacement did not open the requested Moneta backend")
    return owner


def _copy_records(destination, records):
    existing = {m.id: m.to_json() for m in _records(destination)}
    for record in records:
        if record.id in existing and existing[record.id] != record.to_json():
            raise RuntimeError(f"Destination has conflicting memory identity: {record.id}")
    for record in records:
        if record.id not in existing:
            add = getattr(destination.store, "add_durable_if_absent", destination.store.add)
            add(record)
    _persist(destination)
    actual = {m.id: m.to_json() for m in _records(destination)}
    if any(actual.get(record.id) != record.to_json() for record in records):
        raise RuntimeError("Migrated memory readback differs")


def _lineage(owner):
    path = Path(owner.storage_dir) / "scene_lineage.json"
    if not path.exists():
        return {}
    if path.stat().st_size > 1024 * 1024:
        raise RuntimeError("Scene memory lineage exceeds the read budget")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("scenes"), dict):
        raise RuntimeError("Invalid scene memory lineage")
    for hip, sources in value["scenes"].items():
        if not isinstance(hip, str) or not isinstance(sources, list) or any(not isinstance(p, str) for p in sources):
            raise RuntimeError("Invalid scene memory lineage entry")
    return value["scenes"]


def scene_hip_paths(owner, hip_path=None):
    """Provenance paths inherited by this HIP across Save As, also after restart."""
    binding = getattr(owner, "_memory_binding", None)
    hip = hip_path or (binding.hip_path if binding else "")
    if not hip:
        return set()
    key = _key(hip)
    return {_key(p) for p in _lineage(owner).get(key, [])} | {key}


def _save_lineage(owner, hip_path, sources):
    from synapse.cognitive.tools.write_report import write_report
    value = _lineage(owner)
    key = _key(hip_path)
    updated = sorted({_key(p) for p in sources} | {_key(p) for p in value.get(key, [])} | {key})
    if value.get(key) == updated:
        return
    value[key] = updated
    if len(value) > 4096 or len(updated) > 256:
        raise RuntimeError("Scene memory lineage exceeds the supported bound")
    serialized = json.dumps({"schema": 1, "scenes": value}, sort_keys=True)
    if len(serialized.encode("utf-8")) > 1024 * 1024:
        raise RuntimeError("Scene memory lineage exceeds the byte budget")
    write_report("scene_lineage.json", serialized,
                 base_dir=str(owner.storage_dir), backups=1)


def _refresh_bridge(owner):
    tracker = sys.modules.get("synapse.session.tracker")
    bridge = getattr(tracker, "_bridge", None)
    if bridge is not None:
        from synapse.memory.markdown import MarkdownSync
        bridge._synapse = owner
        bridge._markdown_sync = MarkdownSync(owner.storage_dir)
        bridge.invalidate_context_cache()


def rebind_owner(project_path, *, records=None, binding=None, inherited_hips=None):
    """Verified destination reopen before publishing; no directory-tree copy."""
    _require_main()
    from synapse.memory import store as module
    target = Path(project_path).resolve()
    if target.is_file() or target.suffix.lower() in {".hip", ".hiplc", ".hipnc"}:
        target = target.parent
    with module._GLOBAL_LOCK:
        old = module._global_synapse
        if old is None:
            raise RuntimeError("The host has not initialized memory")
        if _key(target / ".synapse") == _key(old.storage_dir):
            return {"status": "UNCHANGED", "storage_dir": str(old.storage_dir)}
        carried = list(records or [])
        if (len(carried) > _MAX_RECORDS
                or sum(len(m.to_json().encode("utf-8")) for m in carried) > _MAX_BYTES):
            raise RuntimeError("Memory migration exceeds the bounded record/byte budget")
        _persist(old)
        replacement = _open(target)
        try:
            _copy_records(replacement, carried)
            if binding is not None and inherited_hips:
                _save_lineage(replacement, binding.hip_path, inherited_hips)
            # Verification must read persisted bytes, not just the deposit cache.
            _release(replacement)
            replacement = _open(target)
            verified = {m.id: m.to_json() for m in _records(replacement)}
            if any(verified.get(m.id) != m.to_json() for m in carried):
                raise RuntimeError("Reopened migrated memory differs")
            _release(old)
        except Exception:
            _release(replacement)
            raise
        if binding is not None:
            replacement._memory_binding = binding
        module._global_synapse = replacement
        _refresh_bridge(replacement)
        return {"status": "REBOUND", "source": str(old.storage_dir),
                "storage_dir": str(replacement.storage_dir),
                "carried_records": len(carried), "verified_records": len(verified),
                "snapshot_copied": False,
                "records_sha256": hashlib.sha256(json.dumps(
                    {m.id: m.to_json() for m in carried}, sort_keys=True).encode()).hexdigest()}


def _adopt_scene_store(owner, binding):
    """Only this saved scene's legacy directory, never a cross-scene scan."""
    from synapse.memory import store as module
    source = binding.scene_dir / ".synapse"
    if binding.unsaved or _key(source) == _key(owner.storage_dir) or not source.is_dir():
        return
    adopted = getattr(owner, "_memory_adopted", set())
    if _key(source) in adopted:
        return
    if not (source / ".moneta" / "snapshot.json").exists() and not (source / "memory.jsonl").exists():
        return
    # A temporary, main-thread source reader has one different storage URI.
    # JSONL-only legacy sources must not be accidentally opened as empty Moneta.
    if not (source / ".moneta" / "snapshot.json").exists():
        from types import SimpleNamespace
        legacy = SimpleNamespace(storage_dir=source,
            store=module.MemoryStore(source, background_load=False))
    else:
        if not hasattr(owner.store, "_require_durable"):
            raise RuntimeError("This legacy scene uses Moneta; select Moneta to adopt its canonical records")
        legacy = _open(binding.scene_dir)
    try:
        records = _records(legacy)
        _copy_records(owner, records)
    finally:
        _release(legacy)
    owner._memory_adopted = adopted | {_key(source)}


def ensure_current_memory(*, cause=None):
    """Host request entry point. Call inside main-thread handler dispatch."""
    def sync():
        _require_main()
        from synapse.memory import store as module
        owner = module.get_synapse_memory()
        if not module.HOU_AVAILABLE:
            return owner
        binding = current_binding()
        previous = getattr(owner, "_memory_binding", None)
        effective_cause = cause
        if (effective_cause is None
                and getattr(owner, "_memory_pending_hip", None) == binding.hip_path):
            effective_cause = getattr(owner, "_memory_pending_cause", None)
        inherited = set()
        records = []
        if effective_cause == "save" and previous is not None:
            inherited = scene_hip_paths(owner, previous.hip_path)
            if previous.unsaved:
                records = _records(owner)
            elif _key(previous.project_dir) != _key(binding.project_dir):
                from synapse.memory.models import MemoryTier
                records = [m for m in _records(owner)
                           if m.tier != MemoryTier.SHOW and m.hip_file and _key(m.hip_file) in inherited]
        if _key(owner.storage_dir) != _key(binding.project_dir / ".synapse"):
            rebind_owner(binding.project_dir, records=records, binding=binding, inherited_hips=inherited)
            owner = module._global_synapse
        elif effective_cause == "save":
            _persist(owner)
            if inherited:
                _save_lineage(owner, binding.hip_path, inherited)
        owner._memory_binding = binding
        _adopt_scene_store(owner, binding)
        owner._memory_binding_error = None
        owner._memory_pending_cause = None
        owner._memory_pending_hip = None
        register_owner(owner)
        if previous != binding:
            _refresh_bridge(owner)
        return owner
    return _on_main(sync)
