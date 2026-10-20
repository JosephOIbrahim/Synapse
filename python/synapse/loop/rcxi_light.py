"""Synthetic-only light-gate components. No live adapter, I/O or registration.

See docs/RCXI_LIGHT_OFFLINE_CONTRACT.md. The fixture ledger is volatile; it
does not establish external custody, host measurement or crash-safe recovery.
"""
from __future__ import annotations

import logging as _boundary_logging
_boundary_log = _boundary_logging.getLogger(__name__)

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
import re

from .ports import PortResult
from .rcxi_ports import SixMetrics

METRIC_ORDER = ("task_loss", "execution_ms", "peak_memory_mb", "complexity_delta", "state_entropy", "invariant_violation")
_TOKEN = re.compile(r"[A-Za-z0-9_:-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ValueError("invalid opaque identity")
    return value


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite numeric value required")
    return float(value)


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def metric_vector(metrics):
    if not isinstance(metrics, SixMetrics):
        raise ValueError("typed six-component metrics required")
    return tuple(getattr(metrics, name) for name in METRIC_ORDER)


def histogram_entropy_ev(values, bin_width):
    width = _number(bin_width)
    if width <= 0:
        raise ValueError("positive exposure histogram width required")
    counts = {}
    for value in values:
        bucket = math.floor(_number(value) / width)
        counts[bucket] = counts.get(bucket, 0) + 1
    if not counts:
        raise ValueError("complete nonempty light set required")
    size = sum(counts.values())
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def synthetic_sample_covariance(samples, diagonal_regularization):
    """Unbiased sample covariance plus explicit positive synthetic ridge.

    This estimates no production threshold, population or metric semantics.
    """
    rows = tuple(metric_vector(sample) for sample in samples)
    ridge = tuple(_number(value) for value in diagonal_regularization)
    if len(rows) < 2 or len(ridge) != 6 or any(value <= 0 for value in ridge):
        raise ValueError("two samples and six positive regularizers required")
    means = tuple(sum(row[i] for row in rows) / len(rows) for i in range(6))
    return tuple(tuple(sum((row[i] - means[i]) * (row[j] - means[j]) for row in rows) / (len(rows) - 1)
                       + (ridge[i] if i == j else 0.0) for j in range(6)) for i in range(6))


def _cholesky(covariance):
    rows = tuple(tuple(_number(value) for value in row) for row in covariance)
    if len(rows) != 6 or any(len(row) != 6 for row in rows):
        raise ValueError("six-by-six covariance required")
    if any(not math.isclose(rows[i][j], rows[j][i], rel_tol=1e-12, abs_tol=1e-12)
           for i in range(6) for j in range(6)):
        raise ValueError("symmetric covariance required")
    lower = [[0.0] * 6 for _ in range(6)]
    for i in range(6):
        for j in range(i + 1):
            residual = (rows[i][j] + rows[j][i]) / 2 - sum(lower[i][k] * lower[j][k] for k in range(j))
            if i == j:
                if residual <= 0 or not math.isfinite(residual):
                    raise ValueError("positive-definite calibrated covariance required")
                lower[i][j] = math.sqrt(residual)
            else:
                lower[i][j] = residual / lower[j][j]
    return tuple(tuple(row) for row in lower)


@dataclass(frozen=True)
class SyntheticCalibrationProfile:
    profile_id: str
    covariance: tuple[tuple[float, ...], ...]
    loss_weight: float
    tension_limit: float
    loss_tolerance: float
    histogram_width_ev: float
    minimum_exposure: float
    maximum_exposure: float
    max_attempts: int
    max_measured_execution_ms: float
    no_progress_limit: int
    progress_epsilon: float
    evidence_tier: str = field(default="SYNTHETIC", init=False)

    def __post_init__(self):
        _token(self.profile_id)
        covariance = tuple(tuple(_number(value) for value in row) for row in self.covariance)
        _cholesky(covariance)
        object.__setattr__(self, "covariance", covariance)
        for name in ("loss_weight", "tension_limit", "loss_tolerance", "histogram_width_ev", "minimum_exposure",
                     "maximum_exposure", "max_measured_execution_ms", "progress_epsilon"):
            object.__setattr__(self, name, _number(getattr(self, name)))
        if any(getattr(self, name) < 0 for name in ("loss_weight", "tension_limit", "loss_tolerance", "progress_epsilon")):
            raise ValueError("negative decision choices are invalid")
        if self.histogram_width_ev <= 0 or self.max_measured_execution_ms <= 0 or self.minimum_exposure >= self.maximum_exposure:
            raise ValueError("positive budgets and ordered exposure bounds required")
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 64:
            raise ValueError("fixture attempt cap must be between one and 64")
        if type(self.no_progress_limit) is not int or not 1 <= self.no_progress_limit <= 64:
            raise ValueError("explicit bounded no-progress limit required")

    @property
    def sha256(self):
        return _digest(asdict(self))


def tension(forecast, observed, profile):
    predicted, actual = metric_vector(forecast), metric_vector(observed)
    lower = _cholesky(profile.covariance)
    solved = []
    for i in range(6):
        solved.append((actual[i] - predicted[i] - sum(lower[i][j] * solved[j] for j in range(i))) / lower[i][i])
    result = math.hypot(*solved) + profile.loss_weight * observed.task_loss
    if not math.isfinite(result):
        raise ValueError("unmeasurable tension")
    return result


@dataclass(frozen=True)
class LightRequest:
    instance_id: str
    expected_revision: int
    key_light_binding: str
    target_exposure: float

    def __post_init__(self):
        _token(self.instance_id)
        _token(self.key_light_binding)
        if type(self.expected_revision) is not int or self.expected_revision < 0:
            raise ValueError("nonnegative instance revision required")
        object.__setattr__(self, "target_exposure", _number(self.target_exposure))

    @property
    def sha256(self):
        return _digest({"action": "solaris.iterate.light", "field": "exposure", **asdict(self)})


@dataclass(frozen=True)
class SyntheticLightSnapshot:
    instance_id: str
    revision: int
    light_values: tuple[tuple[str, float], ...]
    node_count: int
    edge_count: int
    outside_sha256: str
    foreign_epoch: int | None
    undo_tracking_known: bool
    undo_enabled: bool
    latest_owner: str | None
    evidence_tier: str = field(default="SYNTHETIC", init=False)

    def __post_init__(self):
        _token(self.instance_id)
        for name in ("revision", "node_count", "edge_count"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError("known nonnegative snapshot counts required")
        values = tuple((_token(binding), _number(value)) for binding, value in self.light_values)
        if not values or len({binding for binding, _ in values}) != len(values):
            raise ValueError("complete unique fixture light set required")
        object.__setattr__(self, "light_values", values)
        if not isinstance(self.outside_sha256, str) or not _SHA.fullmatch(self.outside_sha256):
            raise ValueError("outside fixture-state digest required")
        if self.foreign_epoch is not None and (type(self.foreign_epoch) is not int or self.foreign_epoch < 0):
            raise ValueError("invalid foreign-edit epoch")
        if type(self.undo_tracking_known) is not bool or type(self.undo_enabled) is not bool:
            raise ValueError("explicit tracking and undo evidence required")
        if self.latest_owner is not None:
            _token(self.latest_owner)

    @property
    def sha256(self):
        return _digest(asdict(self))

    def exposure(self, binding):
        values = dict(self.light_values)
        if binding not in values:
            raise ValueError("captured key-light binding unavailable")
        return values[binding]


@dataclass(frozen=True)
class SyntheticMeasurement:
    after: SyntheticLightSnapshot
    execution_ms: float
    peak_memory_mb: float

    def __post_init__(self):
        if not isinstance(self.after, SyntheticLightSnapshot):
            raise ValueError("complete typed fixture snapshot required")
        for name in ("execution_ms", "peak_memory_mb"):
            value = _number(getattr(self, name))
            if value < 0:
                raise ValueError("nonnegative measured costs required")
            object.__setattr__(self, name, value)


def _loss(value, target):
    return abs(value - target) / max(1.0, abs(target))


def observed_metrics(request, before, measurement, attempt_id, profile):
    after = measurement.after
    before_values, after_values = dict(before.light_values), dict(after.light_values)
    violation = int(
        after.instance_id != before.instance_id or after.revision != before.revision + 1
        or before_values.keys() != after_values.keys()
        or any(after_values.get(key) != value for key, value in before_values.items() if key != request.key_light_binding)
        or after.node_count != before.node_count or after.edge_count != before.edge_count
        or after.outside_sha256 != before.outside_sha256
        or after.foreign_epoch is None or after.foreign_epoch != before.foreign_epoch
        or not after.undo_tracking_known or not after.undo_enabled or after.latest_owner != attempt_id
        or not profile.minimum_exposure <= after.exposure(request.key_light_binding) <= profile.maximum_exposure)
    return SixMetrics(_loss(after.exposure(request.key_light_binding), request.target_exposure),
                      measurement.execution_ms, measurement.peak_memory_mb,
                      after.node_count + after.edge_count - before.node_count - before.edge_count,
                      histogram_entropy_ev(after_values.values(), profile.histogram_width_ev), violation)


@dataclass(frozen=True)
class SyntheticForecastAck:
    attempt_id: str
    sha256: str
    durability: str = field(default="VOLATILE_SYNTHETIC", init=False)


class SyntheticForecastLedger:
    """In-memory fixture journal only. No durable or external trust claim."""
    evidence_tier = "SYNTHETIC"

    def __init__(self):
        self._records = {}

    def seal(self, record):
        identity = record["attempt_id"]
        if identity in self._records:
            raise ValueError("duplicate fixture forecast; replay refused")
        self._records[identity] = json.loads(json.dumps(record, sort_keys=True, allow_nan=False))
        return SyntheticForecastAck(identity, _digest(record))

    def verify(self, ack, record):
        if not isinstance(ack, SyntheticForecastAck) or ack.attempt_id != record["attempt_id"]:
            return False
        stored = self._records.get(ack.attempt_id)
        return stored is not None and _digest(stored) == ack.sha256 == _digest(record)


@dataclass(frozen=True)
class FixtureTrial:
    attempt_id: str
    decision: str
    metrics: SixMetrics | None
    tension: float | None


@dataclass(frozen=True)
class FixtureRunResult:
    verdict: str
    reason: str
    trials: tuple[FixtureTrial, ...]
    measured_execution_ms: float
    profile_sha256: str | None = None
    evidence_tier: str = field(default="SYNTHETIC", init=False)
    authorizes_live_action: bool = field(default=False, init=False)
    ledger_durability: str = field(default="VOLATILE_SYNTHETIC", init=False)
    live_validated: bool = field(default=False, init=False)


class SyntheticCancellation:
    """One-way fixture cancellation, not a host interruption mechanism."""
    def __init__(self):
        self._cancelled = False

    @property
    def cancelled(self):
        return self._cancelled

    def cancel(self):
        self._cancelled = True


class SyntheticLightGate:
    """Enforced fixture decisions; no configured/live Houdini entry point.

    Injected fixture objects are test dependencies, not an OS trust boundary.
    The mutator returns no evidence the controller will accept as measurement.
    """
    def __init__(self, *, mutator, observer, forecaster, ledger, profile, cancellation=None):
        self.mutator, self.observer, self.forecaster, self.ledger = mutator, observer, forecaster, ledger
        self.profile = profile
        self.cancellation = cancellation if cancellation is not None else SyntheticCancellation()

    def execute_live(self, *args, **kwargs):
        return PortResult.unavailable("Live RC+xi light integration is not implemented or qualified; no action dispatched.")

    def _recover(self, before, observed, attempt_id):
        try:
            current = self.observer.capture()
            if isinstance(current, SyntheticLightSnapshot) and current.sha256 == before.sha256:
                return True
            safe = (isinstance(current, SyntheticLightSnapshot) and current.sha256 == observed.sha256
                    and current.latest_owner == attempt_id and current.foreign_epoch is not None
                    and current.foreign_epoch == before.foreign_epoch and current.undo_tracking_known and current.undo_enabled)
            if not safe:
                return False
            self.mutator.rollback(before, attempt_id)
            restored = self.observer.capture()
            return isinstance(restored, SyntheticLightSnapshot) and restored.sha256 == before.sha256
        except Exception as _boundary_error:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light._recover', type(_boundary_error).__name__[:120])
            return False

    def run_fixture(self, request, run_id):
        trials, total_ms = [], 0.0
        profile_sha256 = None

        def result(verdict, reason):
            return FixtureRunResult(verdict, reason, tuple(trials), total_ms, profile_sha256)

        if not isinstance(request, LightRequest) or type(self.profile) is not SyntheticCalibrationProfile:
            return result("BLOCKED", "Typed fixture request/profile required.")
        try:
            run_profile = replace(self.profile)  # complete revalidated frozen copy; never reread policy for arithmetic
            profile_sha256 = run_profile.sha256
        except Exception as _boundary_error:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
            return result("BLOCKED", "Complete validated fixture profile required.")

        def policy_current():
            try:
                return (type(self.profile) is SyntheticCalibrationProfile and self.profile.sha256 == profile_sha256
                        and run_profile.sha256 == profile_sha256)
            except Exception as _boundary_error:
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.policy_current', type(_boundary_error).__name__[:120])
                return False

        if type(self.cancellation) is not SyntheticCancellation:
            return result("UNAVAILABLE", "Explicit synthetic cancellation state required.")
        if self.cancellation.cancelled:
            return result("FIXTURE_CANCELLED", "Cancelled before fixture dispatch.")
        if any(getattr(port, "evidence_tier", None) != "SYNTHETIC" for port in (
                self.mutator, self.observer, self.forecaster, self.ledger)) or self.mutator is self.observer:
            return result("UNAVAILABLE", "Separate explicit synthetic mutation/measurement/forecast/ledger fixtures required.")
        try:
            _token(run_id)
            if len(run_id) > 100:
                raise ValueError("run identity too long")
            before = self.observer.capture()
            if not policy_current():
                return result("BLOCKED", "Fixture policy changed before dispatch.")
            if not isinstance(before, SyntheticLightSnapshot) or before.instance_id != request.instance_id or before.revision != request.expected_revision:
                raise ValueError("stale fixture instance")
            if not before.undo_tracking_known or not before.undo_enabled or before.foreign_epoch is None:
                raise ValueError("unknown fixture ownership/tracking")
            if not run_profile.minimum_exposure <= request.target_exposure <= run_profile.maximum_exposure:
                raise ValueError("target outside explicit profile bounds")
            best_loss = _loss(before.exposure(request.key_light_binding), request.target_exposure)
        except Exception as _boundary_error:
            _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
            return result("UNAVAILABLE", "Complete in-scope prestate and tracking required; no mutation.")
        stagnant = 0
        for index in range(run_profile.max_attempts):
            attempt_id = run_id + ":" + str(index + 1)
            try:
                forecast = self.forecaster.predict(request, before, index + 1)
                metric_vector(forecast)
                if not policy_current():
                    raise ValueError("fixture policy changed before forecast custody")
                record = {"schema": "synapse.rcxi.light.synthetic.v1", "attempt_id": attempt_id,
                          "request_sha256": request.sha256, "profile_sha256": profile_sha256,
                          "prestate_sha256": before.sha256, "forecast": asdict(forecast), "evidence_tier": "SYNTHETIC"}
                ack = self.ledger.seal(record)
                if not self.ledger.verify(ack, record):
                    raise ValueError("unbound forecast acknowledgement")
                if self.observer.capture().sha256 != before.sha256:
                    raise ValueError("prestate changed before dispatch")
                if not policy_current():
                    raise ValueError("fixture policy changed before dispatch")
            except Exception as _boundary_error:
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
                return result("BLOCKED", "Forecast seal/identity/replay check failed before dispatch.")
            if self.cancellation.cancelled:
                return result("FIXTURE_CANCELLED", "Cancelled after forecast, before dispatch.")
            mutation_failed = False
            try:
                self.mutator.apply(request, attempt_id)  # ignore all mutator self-reports
            except Exception as _boundary_error:
                mutation_failed = True
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
            try:
                measured = self.observer.measure(before, request, attempt_id)
                if not isinstance(measured, SyntheticMeasurement):
                    raise ValueError("measurement unavailable")
                after = measured.after
                metrics = observed_metrics(request, before, measured, attempt_id, run_profile)
                xi = tension(forecast, metrics, run_profile)
                total_ms += measured.execution_ms
            except Exception as _boundary_error:
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
                trials.append(FixtureTrial(attempt_id, "MEASUREMENT_UNAVAILABLE", None, None))
                try:
                    after = self.observer.capture()
                    restored = isinstance(after, SyntheticLightSnapshot) and self._recover(before, after, attempt_id)
                except Exception as _boundary_error:
                    restored = False
                    _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
                verdict = "FIXTURE_CANCELLED" if restored and self.cancellation.cancelled else "FIXTURE_ROLLED_BACK" if restored else "FIXTURE_QUARANTINED"
                return result(verdict, "Incomplete measurement cannot converge.")
            try:
                bound = self.ledger.verify(ack, record)
            except Exception as _boundary_error:
                bound = False
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
            try:
                current = self.observer.capture()
                still_current = isinstance(current, SyntheticLightSnapshot) and current.sha256 == after.sha256
            except Exception as _boundary_error:
                still_current = False
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'rcxi_light.run_fixture', type(_boundary_error).__name__[:120])
            policy_bound = policy_current()
            if self.cancellation.cancelled or mutation_failed or not bound or not still_current or not policy_bound or metrics.invariant_violation or total_ms > run_profile.max_measured_execution_ms:
                reason = ("Cancelled after fixture dispatch." if self.cancellation.cancelled else "Mutation failed." if mutation_failed else "Forecast changed after dispatch." if not bound
                          else "State changed after observation." if not still_current else "Fixture policy changed after dispatch." if not policy_bound else "Invariant failed."
                          if metrics.invariant_violation else "Measured-work budget exhausted.")
                restored = self._recover(before, after, attempt_id)
                trials.append(FixtureTrial(attempt_id, "ROLLBACK" if restored else "QUARANTINE", metrics, xi))
                verdict = "FIXTURE_CANCELLED" if restored and self.cancellation.cancelled else "FIXTURE_ROLLED_BACK" if restored else "FIXTURE_QUARANTINED"
                return result(verdict, reason)
            if xi <= run_profile.tension_limit and metrics.task_loss <= run_profile.loss_tolerance:
                trials.append(FixtureTrial(attempt_id, "FIXTURE_CONVERGED", metrics, xi))
                return result("FIXTURE_CONVERGED", "Synthetic objective and tension met; not live authorization.")
            if metrics.task_loss < best_loss - run_profile.progress_epsilon:
                best_loss, stagnant = metrics.task_loss, 0
            else:
                stagnant += 1
            thrash = stagnant >= run_profile.no_progress_limit
            exhausted = index + 1 >= run_profile.max_attempts or total_ms >= run_profile.max_measured_execution_ms
            restored = self._recover(before, after, attempt_id)
            decision = "QUARANTINE" if not restored else "ROLLBACK" if thrash or exhausted else "FIXTURE_MORE_FUEL"
            trials.append(FixtureTrial(attempt_id, decision, metrics, xi))
            if not restored:
                return result("FIXTURE_QUARANTINED", "Fixture recovery not verified; no retry.")
            if thrash or exhausted:
                return result("FIXTURE_ROLLED_BACK", "Measured loss made no progress." if thrash else "Fixture fuel exhausted.")
        return result("UNAVAILABLE", "No fixture terminal decision.")
