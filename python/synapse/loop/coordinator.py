"""Synapse-owned observational LOOP with a durable, idempotent delivery outbox.

Forecasts are EXPOSED instrumentation. Recalled outcomes are advisory; nothing
here chooses, executes, repairs or approves an artist's scene operation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from .context import sanitize_context
from .ports import LedgerPort, PortResult, StagePort


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def append(path, record):
    """Publish one complete event; retain legacy bytes and interrupted writes.

    A process exit during an append must not poison every later recovery. New
    events are fsynced separately before their atomic publication. Unpublished
    .part files remain evidence, but are never interpreted as terminal events.
    """
    directory = path.with_name(path.name + ".d")
    identity = uuid.uuid4().hex
    temporary = directory / (identity + ".part")
    published = directory / (identity + ".json")
    create(temporary, record)
    os.replace(temporary, published)


def read_journal(path):
    """Read complete legacy lines and atomically published events.

    A legacy final line without its newline is uncommitted, even if its JSON
    happens to parse. Keep those bytes untouched. Corruption in a committed
    line or published event is not an interruption and must fail visibly.
    """
    events = []
    if path.exists():
        raw = path.read_bytes()
        complete = raw[:raw.rfind(b"\n") + 1]
        events.extend(json.loads(line.decode("utf-8")) for line in complete.splitlines())
    directory = path.with_name(path.name + ".d")
    for entry in sorted(directory.glob("*.json")):
        events.append(json.loads(entry.read_text(encoding="utf-8")))
    if any(not isinstance(event, dict) or not isinstance(event.get("event"), str)
           for event in events):
        raise ValueError("Invalid committed outbox event")
    return events


def create(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(canonical(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class LoopCoordinator:
    def __init__(self, root, worker, deposit):
        self.root = Path(root).resolve()
        self.worker = worker
        self.deposit = deposit  # host callback; never a worker's memory handle

    def context(self, context):
        clean = sanitize_context(context)
        composed = StagePort(worker=self.worker, context=clean).compose_sanitized_stage("host_context")
        if composed.status == "SUCCESS":
            return composed
        # Return only the smaller true source, explicitly without Octavius.
        return PortResult(composed.status, {"context": clean, "source": "local_host_context",
            "sanitization": "allowlisted_local_fields", "octavius_composed": False},
            composed.error_message)

    def begin(self, operation, context, relation_keys, input_sha256):
        if not re.fullmatch(r"[A-Za-z0-9_:-]{1,80}", operation):
            raise ValueError("Invalid operation identity")
        composed = self.context(context)
        now = datetime.now(timezone.utc)
        attempt = {"id": uuid.uuid4().hex, "operation": operation,
            "created_at": now.isoformat(), "horizon": (now + timedelta(minutes=10)).isoformat(),
            "context_sha256": digest(composed.payload["context"]),
            "input_sha256": input_sha256}
        folder = self.root / "attempts" / attempt["id"]
        record = {"schema": 1, "attempt": attempt, "context": composed._asdict(),
                  "relation_keys": list(relation_keys)}
        create(folder / "request.json", record)
        create(self.root / "pending" / (attempt["id"] + ".json"), {"id": attempt["id"]})
        ledger = LedgerPort(folder / "hanish", worker=self.worker, attempt=attempt)
        result = ledger.author_precommit("The synchronous handler returns without an explicit failure", 0.5,
                                        attempt["context_sha256"])
        append(folder / "journal.jsonl", {"event": "forecast_ack", "result": result._asdict()})
        # Durable marker before giving control back to the host. Recovery may
        # reconcile an existing forecast but NEVER author one after this point.
        append(folder / "journal.jsonl", {"event": "dispatch_started", "at": utc_now()})
        return record

    def finish(self, record, value, result_sha256):
        if value is not None and type(value) is not bool:
            raise ValueError("Only a measured Boolean or unknown is admissible")
        folder = self.root / "attempts" / record["attempt"]["id"]
        terminal = {"value": value, "arrived_at": utc_now(), "result_sha256": result_sha256}
        append(folder / "journal.jsonl", {"event": "terminal", "terminal": terminal})
        return self._deliver(record)

    def _deliver(self, record):
        attempt = record["attempt"]
        if not re.fullmatch(r"[a-f0-9]{32}", attempt["id"]):
            return PortResult.blocked("Invalid outbox attempt identity")
        folder = self.root / "attempts" / attempt["id"]
        events = read_journal(folder / "journal.jsonl")
        terminal_events = [e["terminal"] for e in events if e["event"] == "terminal"]
        if len(terminal_events) > 1 and any(t != terminal_events[0] for t in terminal_events[1:]):
            return PortResult.blocked("Conflicting terminal observations in outbox")
        ack = next((e["result"] for e in events if e["event"] == "forecast_ack"), None)
        if not ack or ack["status"] != "SUCCESS":
            # Recover only the forecast already on disk after a lost ACK. A
            # missing forecast stays uninstrumented; no post-action backfill.
            recovered = self.worker({"action": "status", "ledger_dir": str(folder / "hanish"), "attempt": attempt})
            if recovered.status != "SUCCESS":
                return recovered
            ack = recovered._asdict()
        forecast_digest = (ack.get("payload") or {}).get("forecast_digest")
        if not forecast_digest:
            return PortResult.unavailable("No digest-bound forecast acknowledgement")
        ledger = LedgerPort(folder / "hanish", worker=self.worker, attempt=attempt,
            forecast_digest=forecast_digest, terminal=terminal_events[0] if terminal_events else None)
        result = ledger.settle(attempt["id"])
        if result.status != "SUCCESS":
            return result
        outcome = (result.payload or {}).get("outcome")
        if not outcome:
            return PortResult.unavailable("Hanish has no settled outcome yet")
        # Keep the source outcome, its identity and limits in the capsule.
        body = {"schema": "synapse.loop.outcome.v1", "attempt": attempt,
            "forecast_digest": forecast_digest, "outcome": outcome,
            "recall_refs": record["context"]["payload"]["context"].get("recall_refs", []),
            "limits": "EXPOSED handler observation; not an artistic, geometry, render or calibration verdict"}
        from ..memory.models import Memory, MemoryType, MemoryTier
        verdict = outcome.get("verdict") or outcome.get("terminal") or "UNRESOLVABLE"
        capsule = Memory(id="loop_" + attempt["id"], content=canonical(body),
            summary=f"{attempt['operation']}: {verdict} (observed handler outcome; artistic quality unjudged)",
            created_at=attempt["created_at"], updated_at=attempt["created_at"],
            memory_type=MemoryType.FEEDBACK, tier=MemoryTier.SHOW,
            source="auto", agent_id="synapse-loop-observer-v1",
            node_paths=record["relation_keys"], tags=["synapse_loop_outcome", attempt["operation"]])
        deposited = self.deposit(capsule.to_dict())
        append(folder / "journal.jsonl", {"event": "delivery", "result": deposited._asdict()})
        if deposited.status == "SUCCESS":
            (self.root / "pending" / (attempt["id"] + ".json")).unlink(missing_ok=True)
            return PortResult.ok({"attempt_id": attempt["id"], "forecast_digest": forecast_digest,
                "outcome": outcome, "memory": deposited.payload,
                "context": record["context"], "mode": "observe_only"})
        return deposited

    def recover(self, limit=4):
        """Bounded retry of pending deliveries, without redispatching an action."""
        pending = self.root / "pending"
        if not pending.exists():
            return []
        results = []
        # Only pending pointers live here; delivered attempts retain their
        # immutable history elsewhere without slowing every later lookup.
        pointers = sorted(pending.glob("*.json"), key=lambda p: p.stat().st_mtime_ns)
        for pointer in pointers[:limit]:
            try:
                attempt_id = pointer.stem
                if not re.fullmatch(r"[a-f0-9]{32}", attempt_id):
                    raise ValueError("Invalid pending pointer")
                record = json.loads((self.root / "attempts" / attempt_id / "request.json").read_text(encoding="utf-8"))
                if record["attempt"]["id"] != attempt_id:
                    raise ValueError("Pending pointer differs from attempt")
                results.append(self._deliver(record)._asdict())
            except Exception as exc:
                results.append(PortResult.unavailable(f"Outbox recovery failed: {exc}")._asdict())
            finally:
                if pointer.exists():
                    # Queue pointers are mutable scheduling state; all attempt
                    # and evidence records remain append-only. Rotate failures
                    # so missing-substrate attempts cannot starve later work.
                    pointer.touch()
        return results
