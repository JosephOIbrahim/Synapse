"""Host seam for the opt-in, observation-only Moneta/Octavius/Hanish LOOP."""
from __future__ import annotations

import logging
import json
import os
from pathlib import Path
import re
import sys
import threading

from synapse.loop.coordinator import LoopCoordinator, digest
from synapse.loop.ports import MemoryPort, PortResult
from synapse.loop.subprocess_port import SubstrateWorker

_LOG = logging.getLogger(__name__)
OBSERVED_COMMANDS = frozenset({
    "create_node", "delete_node", "connect_nodes", "set_parm", "execute_python",
    "execute_vex", "build_template", "set_usd_attribute", "set_usd_primvar",
    "create_usd_prim", "modify_usd_prim", "knowledge_intake",
})


def enabled():
    return os.environ.get("SYNAPSE_LOOP_ENABLED") == "1"


def _on_main(fn):
    from synapse.server.main_thread import run_on_main
    return run_on_main(fn, timeout=3.0, label="memory_loop:owner")


def _owned(fn, expected_path=None):
    """Borrow only an existing owner, under the owner's established locks."""
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("The LOOP memory seam requires the main thread")
    from synapse.memory import store as module
    if not module._GLOBAL_LOCK.acquire(blocking=False):
        raise RuntimeError("Project memory is busy")
    try:
        owner = module._global_synapse
        if owner is None:
            raise RuntimeError("Project memory has not been initialized by the host")
        if expected_path and Path(owner.storage_dir).resolve() != Path(expected_path).resolve():
            raise RuntimeError("The memory owner changed; delivery remains in its original outbox")
        port = MemoryPort.from_owner(owner)
        if port.handle is None:
            raise RuntimeError(port._bind_error or "Moneta memory is unavailable")
        if not owner.store._lock.acquire(blocking=False):
            raise RuntimeError("Project memory backend is busy")
        try:
            owner.store._require_durable()
            return fn(owner, port)
        finally:
            owner.store._lock.release()
    finally:
        module._GLOBAL_LOCK.release()


def _snapshot(query=""):
    import hou
    def read(owner, port):
        resolved = owner._resolve_project_path(None).resolve()
        base = resolved.parent if resolved.is_file() else resolved
        if (base / ".synapse").resolve() != Path(owner.storage_dir).resolve():
            raise RuntimeError("Project memory belongs to another scene location; host rebind required")
        selection = [node.path() for node in hou.selectedNodes()][:32]
        stage = hou.node("/stage")
        nodes = [{"path": node.path(), "type": node.type().name()}
                 for node in (stage.children()[:64] if stage is not None else ())]
        relation_keys = sorted(set(["/stage"] + selection))
        recalled = port.query_and_filter(relation_keys, [])
        if recalled.status != "SUCCESS":
            raise RuntimeError(recalled.error_message)
        candidates = recalled.payload.get("filtered_memories", [])
        words = set(re.findall(r"[a-z0-9_]+", query.lower()))
        memories = []
        for candidate in candidates:
            record = candidate.get("payload", {})
            content = record.get("content", "")
            summary = record.get("summary", "")
            score = len(words & set(re.findall(r"[a-z0-9_]+", (content + " " + summary).lower())))
            if words and not score:
                continue
            memories.append({"id": record.get("id"), "summary": summary[:400],
                "content": content[:3500], "source": record.get("source"),
                "created_at": record.get("created_at", ""), "score": score,
                "advisory": True})
        memories.sort(key=lambda value: (value["score"], value["created_at"]), reverse=True)
        memories = memories[:6]
        context = {"selection": selection, "nodes": nodes, "frame": hou.frame(),
            "houdini_build": hou.applicationVersionString(),
            "recall_refs": [m["id"] for m in memories if m["id"]]}
        return {"context": context, "memories": memories, "relation_keys": relation_keys,
                "storage_dir": str(Path(owner.storage_dir).resolve())}
    return _owned(read)


def coordinator(storage_dir):
    def deposit(capsule):
        try:
            return _on_main(lambda: _owned(lambda owner, port: port.deposit_capsule(capsule), storage_dir))
        except Exception as exc:
            return PortResult.unavailable(str(exc))
    return LoopCoordinator(Path(storage_dir) / "loop", SubstrateWorker(), deposit)


def context_for_request(query=""):
    """Explicit memory-context request: recover pending work, then recall it."""
    if not enabled():
        return PortResult.unavailable("Memory LOOP observation is disabled")._asdict()
    if threading.current_thread() is threading.main_thread():
        return PortResult.unavailable("Request LOOP context from the host worker; no sidecar wait on the UI thread")._asdict()
    try:
        snapshot = _on_main(lambda: _snapshot(query))
        loop = coordinator(snapshot["storage_dir"])
        recovery = loop.recover()
        if recovery:
            snapshot = _on_main(lambda: _snapshot(query))
        stage = loop.context(snapshot["context"])
        return {"status": stage.status, "mode": "observe_only", "stage": stage._asdict(),
            "memories": snapshot["memories"], "recovery": recovery,
            "error_message": stage.error_message,
            "limits": "Context composition only; no multi-agent planning, policy learning or automatic scene edits"}
    except Exception as exc:
        return PortResult.unavailable(str(exc))._asdict()


def terminal_value(result):
    """A narrow handler result, never an artistic or render-success oracle."""
    if not isinstance(result, dict):
        return None
    status = str(result.get("status", "")).lower()
    if status in {"queued", "pending", "running", "cancelled", "canceled", "proposal"}:
        return None
    if result.get("executed") is False or result.get("pending") is True:
        return None
    if result.get("success") is False or result.get("error") or status in {"failed", "error", "blocked"}:
        return False
    return True


def _mcp_payload(result):
    """Only a decoded handler payload is terminal evidence, never its wrapper."""
    from synapse.core.tool_results import unpack_tool_result
    try:
        data, is_error = unpack_tool_result(result)
    except (ValueError, TypeError, RuntimeError):
        return None
    # Unstructured/multi-block envelopes and transport-level errors do not
    # supply a typed handler outcome. They may hide a timeout or pending work.
    return None if is_error or data is result else data


def _attach(result, receipt, response, mcp=False):
    if mcp:
        data = _mcp_payload(result)
        if not isinstance(data, dict):
            return result
        updated = dict(data, memory_loop=receipt._asdict())
        result = dict(result)
        if "structuredContent" in result:
            result["structuredContent"] = updated
        content = result.get("content")
        if (isinstance(content, list) and len(content) == 1
                and isinstance(content[0], dict) and content[0].get("type") == "text"):
            result["content"] = [dict(content[0], text=json.dumps(updated, allow_nan=False))]
        return result
    if response:
        if result.data is None or isinstance(result.data, dict):
            result.data = dict(result.data or {}, memory_loop=receipt._asdict())
        else:
            _LOG.info("LOOP receipt retained in outbox history; scalar response shape preserved")
    elif isinstance(result, dict):
        result = dict(result, memory_loop=receipt._asdict())
    return result


def observe_operation(operation, payload, dispatch, *, response=False, mcp=False):
    """Capture before/after the existing authorized dispatch, without gating it."""
    if not enabled() or operation not in OBSERVED_COMMANDS:
        return dispatch()
    if threading.current_thread() is threading.main_thread():
        return _attach(dispatch(), PortResult.unavailable(
            "Main-thread dispatch was not instrumented; sidecar work requires a host worker"), response, mcp)
    loop = record = None
    try:
        snapshot = _on_main(lambda: _snapshot(operation))
        loop = coordinator(snapshot["storage_dir"])
        record = loop.begin(operation, snapshot["context"], snapshot["relation_keys"], digest(payload))
    except Exception as exc:
        _LOG.warning("LOOP precommit unavailable; operation remains uninstrumented: %s", exc)
    try:
        result = dispatch()
    except Exception as exc:
        if loop is not None and record is not None:
            try:
                # A timeout says nothing about whether the host eventually ran.
                from synapse.server.main_thread import MainThreadTimeout
                value = None if isinstance(exc, (TimeoutError, MainThreadTimeout)) else False
                loop.finish(record, value, digest({"exception_type": type(exc).__name__}))
            except Exception:
                _LOG.exception("LOOP exception evidence remains pending")
        raise
    if loop is not None and record is not None:
        try:
            data = _mcp_payload(result) if mcp else result.data if response else result
            # A transport-level error can hide a timeout. Without typed evidence
            # it is unknown; it must not become a confident failure observation.
            value = None if response and not result.success else terminal_value(data)
            receipt = loop.finish(record, value, digest(data))
            result = _attach(result, receipt, response, mcp)
        except Exception as exc:
            _LOG.warning("LOOP outcome remains pending: %s", exc)
            result = _attach(result, PortResult.unavailable(str(exc)), response, mcp)
    else:
        result = _attach(result, PortResult.unavailable("No pre-action forecast acknowledgement"), response, mcp)
    return result


def rebind_project_memory(project_path, *, carry_records=False):
    """Explicit host migration; preserve the old store and verify before publishing.

    Used for the untitled-to-saved repair. Copying records is never implicit on
    loading an unrelated scene. No panel or worker constructs a memory owner.
    """
    def migrate(owner, port):
        from synapse.memory import store as module
        from synapse.memory.moneta_store import MonetaBackedStore
        target_base = Path(project_path).resolve()
        if target_base.is_file():
            target_base = target_base.parent
        if target_base / ".synapse" == Path(owner.storage_dir).resolve():
            return {"status": "UNCHANGED", "storage_dir": str(owner.storage_dir)}
        records = owner.store._iter_memories(strict=True) if carry_records else []
        if len(records) > 2000:
            raise RuntimeError("Migration exceeds the bounded live record limit")
        owner.store.save(require_durable=True)
        destination = target_base / ".synapse"
        copied_snapshot = False
        if carry_records and not destination.exists():
            # A fresh saved scene can reuse the durable snapshot/vectors. Avoid
            # re-embedding and checkpointing every record on the UI thread.
            import shutil
            source = Path(owner.storage_dir).resolve()
            if destination.is_relative_to(source):
                raise RuntimeError("Memory destination cannot be inside its source")
            files = [p for p in source.rglob("*") if p.is_file()]
            if len(files) > 512 or sum(p.stat().st_size for p in files) > 64 * 1024 * 1024:
                raise RuntimeError("Memory snapshot exceeds the live migration byte budget")
            shutil.copytree(source, destination)
            copied_snapshot = True
        replacement = module.SynapseMemory(project_path=str(target_base))
        try:
            if not isinstance(replacement.store, MonetaBackedStore):
                raise RuntimeError("Replacement memory did not open Moneta")
            replacement.store._require_durable()
            existing = {m.id: m.to_json() for m in replacement.store._iter_memories(strict=True)}
            for memory in records:
                if memory.id in existing and existing[memory.id] != memory.to_json():
                    raise RuntimeError("Destination has a conflicting memory identity")
            for memory in records:
                if memory.id not in existing:
                    replacement.store.add_durable_if_absent(memory)
            verified = {m.id: m.to_json() for m in replacement.store._iter_memories(strict=True)}
            if any(verified.get(m.id) != m.to_json() for m in records):
                raise RuntimeError("Migrated memory readback differs")
        except Exception:
            closer = getattr(replacement.store, "close", None)
            if callable(closer):
                closer()
            raise
        old_path = str(owner.storage_dir)
        owner.store.close()
        module._global_synapse = replacement
        tracker = sys.modules.get("synapse.session.tracker")
        bridge = getattr(tracker, "_bridge", None)
        if bridge is not None:
            bridge._init_synapse()
            bridge.invalidate_context_cache()
        return {"status": "REBOUND", "source": old_path, "storage_dir": str(replacement.storage_dir),
                "carried_records": len(records), "verified_records": len(verified),
                "snapshot_copied": copied_snapshot,
                "records_sha256": digest({m.id: m.to_json() for m in records})}
    return _on_main(lambda: _owned(migrate))
