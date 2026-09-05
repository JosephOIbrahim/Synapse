"""Immutable run evidence and atomic, append-only JSONL persistence.

The default ledger follows loop.ports' repo-relative harness convention;
the copy-on-append protocol follows RecommendationHistory's .tmp + replace.
Unlike that history, existing bytes are never reserialized, pruned or repaired.
There are no host imports, scene observations, or success fallbacks here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import fields
from datetime import datetime, timezone
from enum import Enum
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .contracts import (
    ActionId, ApprovalBinding, CheckId, CheckResult, CheckStatus, OperationState,
    RecoveryVerdict, RunReceipt, TerminalVerdict, verdict_from_checks,
)


class _FrozenList(list):
    """JSON list with list equality, but no public mutation operations."""

    __slots__ = ()

    def __new__(cls, values=()):
        instance = list.__new__(cls)
        list.extend(instance, values)
        return instance

    def __init__(self, values=()):
        # Construction happens once in __new__; reinitialization is not an edit.
        pass

    def _immutable(self, *args, **kwargs):
        raise TypeError("receipt data is immutable")

    __setitem__ = __delitem__ = __iadd__ = __imul__ = _immutable
    append = clear = extend = insert = pop = remove = reverse = sort = _immutable


def freeze(value: Any) -> Any:
    """Detach JSON-shaped data recursively, preserving tuple/list identity."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return _FrozenList(freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(freeze(item) for item in value)
    return value


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise ValueError("evidence mapping keys must be strings")
        result = {key: _encode(item) for key, item in value.items()}
        # Escape reserved keys so artist evidence can contain them literally.
        return {"$mapping": result} if set(result) in ({"$tuple"}, {"$mapping"}) else result
    if isinstance(value, tuple):
        return {"$tuple": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("receipt data must contain finite JSON values or tuples")


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$tuple"}:
            if not isinstance(value["$tuple"], list):
                raise ValueError("invalid tuple encoding")
            return tuple(_decode(item) for item in value["$tuple"])
        if set(value) == {"$mapping"}:
            value = value["$mapping"]
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_decode(item) for item in value]
    return value


def timestamp(value: str) -> datetime:
    """Parse an aware ISO timestamp; never infer a timezone for evidence."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("evidence timestamps require a timezone")
    return parsed.astimezone(timezone.utc)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_receipt(receipt: RunReceipt) -> None:
    """Reject incomplete explanations and unsupported green claims.

    The frozen seam cannot validate its constructor; call this at every
    serialization boundary. Nonterminal evidence is allowed, but never VERIFIED.
    """
    for name, enum_type in (
        ("action_id", ActionId), ("operation_state", OperationState),
        ("verdict", TerminalVerdict), ("recovery", RecoveryVerdict),
    ):
        if not isinstance(getattr(receipt, name), enum_type):
            raise ValueError(f"{name} must be {enum_type.__name__}")
    for name in ("run_id", "request_id", "recipe_id", "recipe_version", "instance_id"):
        if not isinstance(getattr(receipt, name), str) or not getattr(receipt, name).strip():
            raise ValueError(f"{name} is required")
    if not isinstance(receipt.reason, str) or "\n" in receipt.reason or "\r" in receipt.reason:
        raise ValueError("reason must be one line")
    if receipt.verdict != TerminalVerdict.VERIFIED and not receipt.reason.strip():
        raise ValueError("reason is required when verdict is not VERIFIED")
    started = timestamp(receipt.started_at)
    completed = timestamp(receipt.completed_at) if receipt.completed_at is not None else None
    if completed is not None and completed < started:
        raise ValueError("completed_at precedes started_at")
    if receipt.operation_state == OperationState.TERMINAL and completed is None:
        raise ValueError("terminal receipt requires completed_at")
    if len({result.check for result in receipt.checks}) != len(receipt.checks):
        raise ValueError("duplicate check IDs")
    for result in receipt.checks:
        if not isinstance(result.check, CheckId) or not isinstance(result.status, CheckStatus):
            raise ValueError("check and status must be seam enums")
        if not isinstance(result.reason, str) or "\n" in result.reason or "\r" in result.reason:
            raise ValueError("check reason must be one line")
        if result.status != CheckStatus.PASS and not result.reason.strip():
            raise ValueError("non-PASS check requires a reason")
    if receipt.verdict == TerminalVerdict.VERIFIED:
        if receipt.recovery != RecoveryVerdict.NOT_NEEDED:
            raise ValueError("a recovered or uncertain operation cannot be VERIFIED")
        if receipt.operation_state != OperationState.TERMINAL or not receipt.fingerprint_after:
            raise ValueError("VERIFIED requires terminal post-state evidence")
        if verdict_from_checks(receipt.action_id, receipt.checks) != TerminalVerdict.VERIFIED:
            raise ValueError("VERIFIED requires all action predicates to pass")


def to_dict(receipt: RunReceipt) -> dict:
    """Lossless wire dictionary; seam enums use values, nested tuples use tags."""
    validate_receipt(receipt)
    result = {field.name: _encode(getattr(receipt, field.name))
              for field in fields(RunReceipt) if field.name not in ("checks", "approval")}
    result["checks"] = [
        {"check": check.check.value, "status": check.status.value,
         "reason": check.reason, "evidence": _encode(check.evidence)}
        for check in receipt.checks
    ]
    result["approval"] = None if receipt.approval is None else {
        field.name: (list(receipt.approval.resolution) if field.name == "resolution"
                     else _encode(getattr(receipt.approval, field.name)))
        for field in fields(ApprovalBinding)
    }
    return result


def from_dict(data: Mapping[str, Any]) -> RunReceipt:
    values = {key: _decode(value) for key, value in data.items()
              if key not in ("checks", "approval")}
    for key, enum_type in (("action_id", ActionId), ("operation_state", OperationState),
                           ("verdict", TerminalVerdict), ("recovery", RecoveryVerdict)):
        values[key] = enum_type(values[key])
    values["checks"] = tuple(
        CheckResult(CheckId(item["check"]), CheckStatus(item["status"]),
                    item["reason"], freeze(_decode(item["evidence"])))
        for item in data["checks"]
    )
    approval = data["approval"]
    values["approval"] = None if approval is None else ApprovalBinding(
        **{**approval, "resolution": tuple(approval["resolution"])})
    receipt = RunReceipt(**{key: freeze(value) for key, value in values.items()})
    validate_receipt(receipt)
    # Reject unsupported values even when this entry point did not come from JSON.
    to_dict(receipt)
    return receipt


def make_receipt(**fields: Any) -> RunReceipt:
    """Construct and detach verifier-supplied evidence; never observe the host."""
    return from_dict(to_dict(RunReceipt(**fields)))


def receipt_from_checks(**fields: Any) -> RunReceipt:
    """Derive an operation verdict from supplied checks, requiring failure reason."""
    fields["checks"] = tuple(fields["checks"])
    fields["verdict"] = verdict_from_checks(fields["action_id"], fields["checks"])
    return make_receipt(**fields)


def ledger_path() -> Path:
    """Local checkout default; optional SYNAPSE_RECIPE_LEDGER_DIR override."""
    override = os.environ.get("SYNAPSE_RECIPE_LEDGER_DIR")
    directory = Path(override).resolve() if override else (
        Path(__file__).resolve().parents[3] / "harness" / "solaris_v3" / "ledger")
    return directory / "receipts.jsonl"


class ReceiptStore:
    """One writer per path; contention fails closed instead of losing a line.

    An exclusive .lock file serializes processes as well as threads. A crash
    may leave it behind: only an operator who establishes owner death may
    remove it. File fsync precedes atomic replace; directory power-loss
    durability is platform/filesystem dependent. No edit/delete/repair API.
    """

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else ledger_path()

    @contextmanager
    def _writer(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = self.path.with_suffix(self.path.suffix + ".lock")
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink()

    def _read(self) -> tuple[bytes, tuple[RunReceipt, ...]]:
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return b"", ()
        if raw and not raw.endswith(b"\n"):
            raise ValueError("incomplete receipt ledger; refusing to repair history")
        receipts = tuple(from_dict(json.loads(line)) for line in raw.splitlines())
        if len({receipt.run_id for receipt in receipts}) != len(receipts):
            raise ValueError("duplicate run IDs in receipt ledger")
        return raw, receipts

    def read_all(self) -> tuple[RunReceipt, ...]:
        return self._read()[1]

    def append(self, receipt: RunReceipt) -> bool:
        """Append once, returning False for an exact retry; conflicts raise."""
        if receipt.operation_state != OperationState.TERMINAL:
            raise ValueError("only terminal runs enter the immutable receipt ledger")
        payload = to_dict(receipt)
        line = (json.dumps(payload, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        with self._writer():
            raw, receipts = self._read()
            for previous in receipts:
                if previous.run_id == receipt.run_id:
                    previous_line = (json.dumps(to_dict(previous), sort_keys=True,
                                                allow_nan=False) + "\n").encode("utf-8")
                    if previous_line == line:
                        return False
                    raise ValueError("run_id already records different immutable evidence")
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                with tmp.open("wb") as stream:
                    stream.write(raw)
                    stream.write(line)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(tmp, self.path)
            finally:
                tmp.unlink(missing_ok=True)
        return True
