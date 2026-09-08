"""Hanish shadow instrumentation, run only in the host's isolated worker.

No Houdini, Moneta, model client, source-path discovery or installation occurs
here. The host supplies a bounded attempt and loads the real Hanish package.
One attempt has exactly one terminal evidence coordinate. This restriction is
deliberate: Hanish 0.2.0 resolves capture order, not arbitrary source order.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

OBSERVABLE = "synapse.handler_terminal_ok.v1"
SOURCE = "synapse:handler"
CHANNEL = "handler-terminal-v1"
PRODUCER = "synapse-fixed-baseline-v1"
MAX_LEDGER_BYTES = 16 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_IDENTITY = re.compile(r"[A-Za-z0-9_.:-]{1,160}\Z")
_FILES = ("forecasts.jsonl", "evidence.jsonl", "outcomes.jsonl")


class _Blocked(ValueError):
    pass


def _result(status: str, payload=None, error=None) -> dict:
    return {"status": status, "payload": payload, "error_message": error}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _json_value(value: Any) -> Any:
    return json.loads(_canonical(value))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise _Blocked(f"{field} must be an aware ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise _Blocked(f"{field} must be an aware ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise _Blocked(f"{field} must be timezone-aware")
    return parsed


def _digest(value: Any, field: str) -> str:
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise _Blocked(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _attempt(value: Any) -> dict:
    if not isinstance(value, dict):
        raise _Blocked("attempt must be an object")
    attempt = {key: value.get(key) for key in
               ("id", "operation", "created_at", "horizon", "context_sha256")}
    if not isinstance(attempt["id"], str) or not _IDENTITY.fullmatch(attempt["id"]):
        raise _Blocked("attempt.id must be a bounded namespaced identity")
    operation = attempt["operation"]
    if not isinstance(operation, str) or not operation.strip() or len(operation) > 256:
        raise _Blocked("attempt.operation must be a nonempty bounded string")
    created = _timestamp(attempt["created_at"], "attempt.created_at")
    horizon = _timestamp(attempt["horizon"], "attempt.horizon")
    if created >= horizon:
        raise _Blocked("attempt.created_at must precede its horizon")
    _digest(attempt["context_sha256"], "attempt.context_sha256")
    if "input_sha256" in value:
        attempt["input_sha256"] = _digest(value["input_sha256"], "attempt.input_sha256")
    return attempt


def _records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    before = path.stat()
    if before.st_size > MAX_LEDGER_BYTES:
        raise OSError(f"Hanish ledger exceeds worker byte budget: {path.name}")
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise OSError(f"Hanish ledger changed during observation: {path.name}")
    if raw and not raw.endswith(b"\n"):
        raise _Blocked(f"Hanish ledger has an incomplete tail: {path.name}")
    rows = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise _Blocked(f"Hanish ledger is not valid JSON: {path.name}") from exc
        if not isinstance(row, dict):
            raise _Blocked(f"Hanish ledger record is not an object: {path.name}")
        rows.append(row)
    return rows


def _api():
    from hanish import Substrate
    from hanish.future.claims import (
        Comparator, EmissionSemantics, Exposure, Forecast, ObservableSpec,
        ResolutionSpec, WorldRefCapability, canonical_world_commitment, world_ref_for,
    )
    from hanish.past.events import CompletenessSeal, ObservationEvent
    return {
        "Substrate": Substrate, "Comparator": Comparator, "Exposure": Exposure,
        "Forecast": Forecast, "ResolutionSpec": ResolutionSpec,
        "WorldRefCapability": WorldRefCapability, "ObservationEvent": ObservationEvent,
        "CompletenessSeal": CompletenessSeal,
        "canonical_world_commitment": canonical_world_commitment,
        "world_ref_for": world_ref_for,
        "observables": {OBSERVABLE: ObservableSpec(
            OBSERVABLE, "bool", EmissionSemantics.TERMINAL, (SOURCE,),
        )},
    }


def _forecast(api: dict, attempt: dict):
    commitment = api["canonical_world_commitment"]({
        "_v": 1, "_kind": "world_commitment", "capability": "IDENTIFIABLE",
        "adapter": "synapse-hanish-shadow-v1", "attempt": attempt,
        "observable": OBSERVABLE, "source_ref": SOURCE, "channel_id": CHANNEL,
    })
    return api["Forecast"](
        subject_ref=f"synapse-attempt:{attempt['id']}",
        claim="The synchronous handler returns without an explicit failure",
        probability=0.5,
        resolution=api["ResolutionSpec"](
            OBSERVABLE, api["Comparator"].EQ, True, attempt["horizon"],
        ),
        exposure=api["Exposure"].EXPOSED,
        world_ref=api["world_ref_for"](commitment),
        world_ref_capability=api["WorldRefCapability"].IDENTIFIABLE,
        authored_by=PRODUCER, forecast_id=f"f_{attempt['id']}",
        created_at=attempt["created_at"], world_commitment=commitment,
    )


def _forecast_record(forecast) -> dict:
    return _json_value({**dataclasses.asdict(forecast), "_v": 2, "_kind": "forecast"})


def _verified_ack(substrate, root: Path, forecast, attempt: dict) -> dict:
    matches = [row for row in _records(root / "forecasts.jsonl")
               if row.get("_kind") == "forecast" and row.get("forecast_id") == forecast.forecast_id]
    if len(matches) != 1 or matches[0] != _forecast_record(forecast):
        raise _Blocked("Persisted forecast differs from the immutable attempt")
    measured = "sha256:" + hashlib.sha256(_canonical(matches[0]).encode("utf-8")).hexdigest()
    if substrate.forecast_digest(forecast.forecast_id) != measured:
        raise _Blocked("Hanish forecast digest does not match its persisted bytes")
    return {"forecast_id": forecast.forecast_id, "forecast_digest": measured,
            "attempt_id": attempt["id"], "context_sha256": attempt["context_sha256"]}


def _health(substrate, at: str) -> dict:
    health = substrate.status(at=at)
    capture = health.get("capture", {})
    for key in ("process_errors", "corrupted", "tail_loss", "identity_conflicts",
                "seal_conflicts", "outcome_conflicts"):
        if capture.get(key, 0):
            raise _Blocked(f"Hanish integrity counter is nonzero: {key}")
    return health


def _event(api, forecast, attempt: dict, terminal: dict):
    value = terminal.get("value")
    if type(value) is not bool:
        raise _Blocked("terminal.value must be a Boolean or null")
    arrived = _timestamp(terminal.get("arrived_at"), "terminal.arrived_at")
    if arrived <= _timestamp(attempt["created_at"], "attempt.created_at"):
        raise _Blocked("Terminal evidence must arrive after forecast authoring")
    result_digest = _digest(terminal.get("result_sha256"), "terminal.result_sha256")
    return api["ObservationEvent"](
        source_ref=SOURCE, event_id=f"synapse-terminal:{attempt['id']}:1",
        subject_ref=forecast.subject_ref, observable=OBSERVABLE, value=value,
        source_seq=1, epoch_ref=f"synapse-attempt-epoch:{attempt['id']}",
        arrived_at=terminal["arrived_at"], emitted_at=terminal["arrived_at"],
        metadata={"channel_id": CHANNEL, "result_sha256": result_digest},
    )


def _capture_terminal(api, substrate, root: Path, forecast, attempt: dict, terminal: dict):
    event = _event(api, forecast, attempt, terminal)
    event_payload = _json_value(dataclasses.asdict(event))
    observations = [row for row in _records(root / "evidence.jsonl")
                    if row.get("_kind") == "observation"
                    and row.get("subject_ref") == forecast.subject_ref]
    if observations:
        if len(observations) != 1 or {
            key: value for key, value in observations[0].items() if key not in ("_v", "_kind")
        } != event_payload:
            raise _Blocked("Attempt already has different terminal evidence; use a new attempt")
    elif not substrate.capture(event):
        raise OSError("Hanish did not durably accept terminal evidence")
    # Never emit this seal on the unknown/timeout path: a seal with no evidence
    # could turn absence into a MISS in the underlying terminal observable.
    seal = api["CompletenessSeal"](
        source_ref=SOURCE, epoch_ref=event.epoch_ref, final_source_seq=1,
        subject_ref=forecast.subject_ref, sealed_at=event.arrived_at,
    )
    if not substrate.capture(seal):
        raise OSError("Hanish did not durably accept the terminal completeness seal")


def handle(request: Any) -> dict:
    """Execute one author/settle/status request with an honest JSON envelope.

    ``settle`` requires the exact ``forecast_digest`` returned by ``author``.
    The host must persist that ACK before it dispatches the artist's action.
    This function cannot reconstruct that ordering after an action ran.
    """
    try:
        if not isinstance(request, dict):
            raise _Blocked("request must be an object")
        action = request.get("action")
        if action not in ("author", "settle", "status"):
            raise _Blocked("action must be author, settle or status")
        ledger_dir = request.get("ledger_dir")
        if not isinstance(ledger_dir, str) or not ledger_dir.strip():
            raise _Blocked("ledger_dir must name an explicit absolute directory")
        root = Path(ledger_dir)
        if not root.is_absolute():
            raise _Blocked("ledger_dir must be absolute")
        attempt = _attempt(request.get("attempt")) if action != "status" or "attempt" in request else None
        terminal = request.get("terminal")
        if terminal is not None and not isinstance(terminal, dict):
            raise _Blocked("terminal must be an object or null")
        if action == "author" and terminal is not None:
            raise _Blocked("Forecast authoring cannot receive terminal evidence")
        if terminal is not None and terminal.get("value") is not None and type(terminal.get("value")) is not bool:
            raise _Blocked("terminal.value must be a Boolean or null")
        # Expiry advances on retry; evidence arrival is a separate immutable
        # coordinate and must not freeze the clock of an unresolved attempt.
        at = utc_now()
        _timestamp(at, "worker clock")
        if terminal is not None:
            _timestamp(terminal.get("arrived_at"), "terminal.arrived_at")
        api = _api()
        if action == "settle" and not (root / "forecasts.jsonl").is_file():
            return _result("UNAVAILABLE", {"state": "UNINSTRUMENTED"},
                           "No durable forecast exists; settlement never authors one")
        if action == "status" and not (root / "forecasts.jsonl").is_file() and attempt is None:
            return _result("SUCCESS", {"backend": "hanish", "initialized": False, "health": None})
        if action == "status" and attempt is not None and not (root / "forecasts.jsonl").is_file():
            return _result("UNAVAILABLE", {"state": "UNINSTRUMENTED"}, "No durable forecast exists")
        for name in _FILES:
            _records(root / name)
        substrate = api["Substrate"](root, observables=api["observables"])
        _health(substrate, at)
        if action == "status" and attempt is None:
            return _result("SUCCESS", {"backend": "hanish", "initialized": True,
                                       "health": _health(substrate, at)})
        forecast = _forecast(api, attempt)
        existing = substrate.forecasts.get(forecast.forecast_id)
        if existing is None:
            if action != "author":
                return _result("UNAVAILABLE", {"state": "UNINSTRUMENTED"},
                               "Attempt has no durable forecast; settlement never authors one")
            substrate.author(forecast)
        ack = _verified_ack(substrate, root, forecast, attempt)
        payload = {**ack, "durable_ack": ack, "world_ref": forecast.world_ref,
                   "exposure": "EXPOSED", "calibration_eligible": False,
                   "probability": 0.5, "observable": OBSERVABLE}
        if action in ("author", "status"):
            return _result("SUCCESS", {**payload, "state": "FORECAST_PERSISTED"})
        if request.get("forecast_digest") != ack["forecast_digest"]:
            raise _Blocked("Settlement requires the matching durable forecast digest")
        if terminal is not None and terminal.get("value") is not None:
            _capture_terminal(api, substrate, root, forecast, attempt, terminal)
        substrate.process(at=at)
        health = _health(substrate, at)
        outcome = substrate.outcomes.get(forecast.forecast_id)
        if outcome is None:
            return _result("UNAVAILABLE", {**payload, "state": "PENDING", "health": health},
                           "No valid terminal evidence; forecast horizon has not closed")
        return _result("SUCCESS", {**payload, "state": outcome.terminal.value,
                                   "outcome": _json_value(dataclasses.asdict(outcome)),
                                   "health": health})
    except (ImportError, ModuleNotFoundError) as exc:
        return _result("UNAVAILABLE", error=f"Hanish package unavailable: {exc}")
    except (ValueError, TypeError, KeyError, UnicodeError) as exc:
        return _result("BLOCKED", error=f"Hanish request or integrity check failed: {exc}")
    except Exception as exc:
        return _result("UNAVAILABLE", error=f"Hanish worker failed: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    import sys
    try:
        request = json.loads(sys.stdin.read(1024 * 1024 + 1))
        response = handle(request)
    except Exception as exc:
        response = _result("BLOCKED", error=f"Invalid worker input: {type(exc).__name__}: {exc}")
    # stdout is the single JSON IPC response; diagnostics belong on stderr.
    sys.stdout.write(_canonical(response) + "\n")
