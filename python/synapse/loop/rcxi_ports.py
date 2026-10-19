"""Typed, inert seams beside the existing observational LOOP.

This module does not activate substrates, acquire memory handles, persist
claims, authorize actions, evaluate xi or replay mutations. Existing StagePort,
LedgerPort and LoopCoordinator remain the owners of their current behavior.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Protocol, TypedDict

from .ports import PortResult, STATUS

_IDENTITY = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class StageComposition(Protocol):
    def compose_sanitized_stage(self, stage_identifier: str) -> PortResult: ...


class ForecastLedger(Protocol):
    def author_precommit(self, claim_predicate: str, probability: float, world_ref: str) -> PortResult: ...
    def settle(self, turn_id: str) -> PortResult: ...


class CompositionPayload(TypedDict):
    context: dict


class DigestForecastPayload(TypedDict):
    forecast_digest: str


class SequenceForecastPayload(TypedDict):
    seq: int


class SettlementPayload(TypedDict):
    state: str
    outcome: dict


def _payload_matches(payload, operation):
    """Minimum operation-specific shape, never proof that an effect occurred.

    Existing owner metadata/diagnostics are retained; this facade does not
    sanitize a stage, author a ledger record, or certify durable settlement.
    """
    if operation == "compose":
        return isinstance(payload.get("context"), dict)
    if operation == "forecast":
        digest, seq = payload.get("forecast_digest"), payload.get("seq")
        return ((isinstance(digest, str) and _DIGEST.fullmatch(digest) is not None)
                or (type(seq) is int and seq > 0))
    if operation == "settle":
        return (isinstance(payload.get("state"), str) and bool(payload["state"].strip())
                and isinstance(payload.get("outcome"), dict))
    return False


def _checked(result, operation):
    if not isinstance(result, PortResult) or type(result.status) is not str or result.status not in STATUS:
        return PortResult.blocked("Adapter returned an invalid PortResult.")
    if result.payload is not None and not isinstance(result.payload, dict):
        return PortResult.blocked("Adapter returned an invalid payload shape.")
    if result.status == "SUCCESS":
        if result.error_message is not None or not isinstance(result.payload, dict):
            return PortResult.blocked("Adapter success requires a payload and no error.")
        if not _payload_matches(result.payload, operation):
            return PortResult.blocked("Adapter success lacks the operation-specific payload.")
    elif not isinstance(result.error_message, str) or not result.error_message.strip():
        return PortResult.blocked("Adapter non-success requires an explicit reason.")
    return result


@dataclass(frozen=True)
class SubstrateSeams:
    """Borrow explicitly supplied existing ports; do not create new owners.

    Missing adapters are unconfigured, not proof that a substrate is absent
    from this machine. The existing coordinator still owns its durable outbox.
    This facade does not change the fixed Boolean observational forecast into
    a six-component RC+xi forecast.
    """
    stage: StageComposition | None = None
    ledger: ForecastLedger | None = None

    def compose_sanitized_stage(self, stage_identifier):
        if self.stage is None:
            return PortResult.unavailable("Octavius composition adapter not configured; no operation performed.")
        try:
            result = self.stage.compose_sanitized_stage(stage_identifier)
        except Exception as exc:
            return PortResult.unavailable("Composition observation failed: " + type(exc).__name__)
        return _checked(result, "compose")

    def author_precommit(self, claim_predicate, probability, world_ref):
        if self.ledger is None:
            return PortResult.unavailable("Hanish ledger adapter not configured; no forecast authored by this facade.")
        try:
            result = self.ledger.author_precommit(claim_predicate, probability, world_ref)
        except Exception as exc:
            return PortResult.unavailable("Forecast observation failed: " + type(exc).__name__)
        return _checked(result, "forecast")

    def settle(self, turn_id):
        if self.ledger is None:
            return PortResult.unavailable("Hanish ledger adapter not configured; no settlement performed.")
        try:
            result = self.ledger.settle(turn_id)
        except Exception as exc:
            return PortResult.unavailable("Settlement observation failed: " + type(exc).__name__)
        return _checked(result, "settle")


@dataclass(frozen=True)
class SixMetrics:
    task_loss: float
    execution_ms: float
    peak_memory_mb: float
    complexity_delta: int
    state_entropy: float
    invariant_violation: int

    def __post_init__(self):
        for name in ("task_loss", "execution_ms", "peak_memory_mb", "state_entropy"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("all measured nonnegative metric values must be finite")
            object.__setattr__(self, name, float(value))
        if type(self.complexity_delta) is not int:
            raise ValueError("graph complexity delta must be an integer")
        if type(self.invariant_violation) is not int or self.invariant_violation not in (0, 1):
            raise ValueError("invariant violation must be measured as zero or one")


@dataclass(frozen=True)
class TelemetryObservation:
    attempt_id: str
    input_sha256: str
    profile_id: str
    metrics: SixMetrics
    evidence_tier: str

    def __post_init__(self):
        if not isinstance(self.attempt_id, str) or not _IDENTITY.fullmatch(self.attempt_id):
            raise ValueError("invalid observation attempt identity")
        if not isinstance(self.input_sha256, str) or not _DIGEST.fullmatch(self.input_sha256):
            raise ValueError("invalid observation request digest")
        if not isinstance(self.profile_id, str) or not _IDENTITY.fullmatch(self.profile_id):
            raise ValueError("explicit versioned measurement profile required")
        if not isinstance(self.metrics, SixMetrics) or self.evidence_tier not in {"SYNTHETIC", "HOST_MEASURED"}:
            raise ValueError("typed measurement and explicit evidence tier required")


class TelemetryProvider(Protocol):
    def observe(self, attempt_id: str, input_sha256: str) -> TelemetryObservation: ...


@dataclass(frozen=True)
class RcxiObservationPort:
    """Data-only future boundary. A measurement is never an allow decision."""
    provider: TelemetryProvider | None = None

    def observe(self, attempt_id, input_sha256):
        if self.provider is None:
            return PortResult.unavailable("Six-component observation provider not configured; gate must remain closed.")
        try:
            observation = self.provider.observe(attempt_id, input_sha256)
        except Exception as exc:
            return PortResult.unavailable("Six-component observation failed: " + type(exc).__name__)
        if not isinstance(observation, TelemetryObservation):
            return PortResult.blocked("Observer returned no typed six-component measurement.")
        if observation.attempt_id != attempt_id or observation.input_sha256 != input_sha256:
            return PortResult.blocked("Observation identity differs from the requested attempt.")
        return PortResult.ok({"observation": asdict(observation), "authorizes_action": False,
                              "limits": "Observation only; no covariance calibration, xi verdict, seal, fuel or rollback authority."})

    def evaluate(self, *args, **kwargs):
        return PortResult.unavailable("RC+xi evaluator is not implemented by this scaffold; no action authorized.")
