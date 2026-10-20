"""Measured-population arithmetic and a bounded pure local LIGHT referee.

Profiles record supplied measurement provenance. The host controller must own
their actual acquisition and current-context binding; a dataclass/tag is not
an authentication or hostile-Python boundary. No host/store handle enters the
referee thread, and no remote evaluator or model is called.
"""
from __future__ import annotations

import logging as _boundary_logging
_boundary_log = _boundary_logging.getLogger(__name__)

from dataclasses import asdict, dataclass, field, replace
import math
import queue
import re
import threading

from .light_custody import digest
from .rcxi_ports import SixMetrics
from .rcxi_light import _cholesky, metric_vector, tension


class ProfileUnavailable(RuntimeError):
    pass


class HoldoutOutsideTraining(ProfileUnavailable):
    """Measured data outside this fitted population; never an allow decision."""


@dataclass(frozen=True)
class MeasuredLightProfile:
    profile_id: str
    origin: str
    process_pid: int
    context_sha256: str
    samples_sha256: str
    covariance: tuple[tuple[float, ...], ...]
    resolutions: tuple[float, ...]
    forecast: SixMetrics
    tension_limit: float
    loss_weight: float
    loss_tolerance: float
    histogram_width_ev: float
    minimum_exposure: float
    maximum_exposure: float
    max_attempts: int
    max_execution_ms: float
    max_wall_ms: float
    no_progress_limit: int
    progress_epsilon: float
    referee_timeout_seconds: float
    training_samples: int
    holdout_samples: int
    memory_model: str
    mean_peak_growth_mb: float
    memory_baselines_sha256: str
    threshold_method: str = field(default="TRAINING_ENVELOPE_WITH_INDEPENDENT_HELDOUT_VALIDATION", init=False)

    def __post_init__(self):
        if not isinstance(self.profile_id, str) or not re.fullmatch(r"[A-Za-z0-9_:-]{1,128}", self.profile_id):
            raise ProfileUnavailable("Explicit versioned profile identity required")
        if self.origin not in {"HEADLESS_H22_MEASURED", "UNIT_SYNTHETIC_ARITHMETIC"}:
            raise ProfileUnavailable("Explicit measurement provenance required")
        if (self.memory_model not in {"CONDITIONAL_LIFETIME_PEAK", "ABSOLUTE_UNIT_ARITHMETIC"}
                or self.origin == "HEADLESS_H22_MEASURED" and self.memory_model != "CONDITIONAL_LIFETIME_PEAK"
                or type(self.mean_peak_growth_mb) not in (int, float) or not math.isfinite(self.mean_peak_growth_mb)
                or self.mean_peak_growth_mb < 0 or not re.fullmatch(r"[0-9a-f]{64}", self.memory_baselines_sha256)):
            raise ProfileUnavailable("Explicit measured peak-baseline model/binding required")
        if type(self.process_pid) is not int or self.process_pid <= 0:
            raise ProfileUnavailable("Measured process identity required")
        if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in (self.context_sha256, self.samples_sha256)):
            raise ProfileUnavailable("Context and actual sample digests required")
        if (type(self.covariance) not in (tuple, list) or len(self.covariance) != 6
                or any(type(row) not in (tuple, list) or len(row) != 6 for row in self.covariance)
                or any(type(value) not in (int, float) or not math.isfinite(value) for row in self.covariance for value in row)):
            raise ProfileUnavailable("Six-by-six finite numeric covariance required")
        covariance = tuple(tuple(float(value) for value in row) for row in self.covariance)
        _cholesky(covariance)
        object.__setattr__(self, "covariance", covariance)
        if type(self.resolutions) not in (tuple, list) or any(type(value) not in (int, float) for value in self.resolutions):
            raise ProfileUnavailable("Explicit numeric resolutions required")
        resolutions = tuple(float(value) for value in self.resolutions)
        if len(resolutions) != 6 or any(not math.isfinite(value) or value <= 0 for value in resolutions):
            raise ProfileUnavailable("Six explicit positive measurement/structural resolutions required")
        object.__setattr__(self, "resolutions", resolutions)
        if type(self.forecast) is not SixMetrics:
            raise ProfileUnavailable("Typed six-value forecast required")
        object.__setattr__(self, "forecast", replace(self.forecast))
        for field in ("tension_limit", "loss_weight", "loss_tolerance", "histogram_width_ev", "minimum_exposure", "maximum_exposure",
                      "max_execution_ms", "max_wall_ms", "progress_epsilon", "referee_timeout_seconds"):
            value = getattr(self, field)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ProfileUnavailable("Finite explicit profile choice required: " + field)
            object.__setattr__(self, field, float(value))
        if (self.tension_limit < 0 or self.loss_weight < 0 or self.loss_tolerance <= 0
                or self.histogram_width_ev <= 0 or self.minimum_exposure >= self.maximum_exposure
                or not 0 < self.max_execution_ms <= 60_000 or not 0 < self.max_wall_ms <= 60_000
                or self.progress_epsilon < 0 or not 0 < self.referee_timeout_seconds <= 2):
            raise ProfileUnavailable("Invalid explicit decision choices or bounded fuel")
        if (type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 4
                or type(self.no_progress_limit) is not int or not 1 <= self.no_progress_limit <= 4
                or type(self.training_samples) is not int or self.training_samples < 2
                or type(self.holdout_samples) is not int or self.holdout_samples < 1):
            raise ProfileUnavailable("Explicit finite attempt and measured sample counts required")

    @property
    def sha256(self):
        return digest({"schema": "synapse.light.measured-profile.v2", **asdict(self)})

    def forecast_for(self, measured_pretrial_peak_mb):
        """Condition lifetime-peak prediction on the actual current process peak.

        The observed metric remains absolute process-lifetime peak MB. Its
        covariance models innovations around the measured pre-trial baseline,
        so deterministic process growth does not become an unexplained drift.
        """
        if type(measured_pretrial_peak_mb) not in (int, float) or not math.isfinite(measured_pretrial_peak_mb) or measured_pretrial_peak_mb < 0:
            raise ProfileUnavailable("Actual finite pre-trial peak required")
        if self.memory_model == "ABSOLUTE_UNIT_ARITHMETIC":
            return replace(self.forecast)
        return replace(self.forecast, peak_memory_mb=measured_pretrial_peak_mb + self.mean_peak_growth_mb)


def fit_observed_profile(*, training, holdout, resolutions, profile_id, origin, process_pid, context_sha256,
                         loss_weight, loss_tolerance, histogram_width_ev, minimum_exposure, maximum_exposure,
                         max_attempts, max_execution_ms, max_wall_ms, no_progress_limit, progress_epsilon,
                         referee_timeout_seconds, memory_baselines=None):
    """Unbiased six-dimensional sample covariance plus explicit diagonal ridge.

    Cost resolutions come from actual clock/kernel units. Structurally fixed
    graph/entropy/invariant dimensions still participate, with their explicit
    discrete resolution and separate hard invariants. Threshold is fixed from
    the training envelope BEFORE independent held-out validation. A validation
    outlier refuses the profile; it can never widen its own acceptance limit.
    This is not a statistical coverage guarantee for future/artist workloads.
    """
    if len(training) < 2 or not holdout:
        raise ProfileUnavailable("Separate measured training and holdout populations required")
    rows = tuple(replace(row) if type(row) is SixMetrics else (_ for _ in ()).throw(ProfileUnavailable("Typed observed sample required"))
                 for row in (*training, *holdout))
    if any(row.invariant_violation or row.complexity_delta or row.task_loss > loss_tolerance for row in rows):
        raise ProfileUnavailable("Unclean/unsupported calibration sample cannot calibrate acceptance")
    regularizers = tuple(float(value) for value in resolutions)
    if len(regularizers) != 6 or any(not math.isfinite(value) or value <= 0 for value in regularizers):
        raise ProfileUnavailable("Explicit positive regularization resolutions required")
    if memory_baselines is None:
        if origin != "UNIT_SYNTHETIC_ARITHMETIC":
            raise ProfileUnavailable("Actual headless calibration requires every pre-trial process peak")
        baselines = (0.0,) * len(rows)
        memory_model = "ABSOLUTE_UNIT_ARITHMETIC"
    else:
        if (type(memory_baselines) not in (list, tuple) or len(memory_baselines) != len(rows)
                or any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
                       or value > row.peak_memory_mb for value, row in zip(memory_baselines, rows))):
            raise ProfileUnavailable("Measured monotonic pre-trial lifetime peaks required")
        baselines = tuple(float(value) for value in memory_baselines)
        memory_model = "CONDITIONAL_LIFETIME_PEAK"
    innovations = tuple(replace(row, peak_memory_mb=row.peak_memory_mb - baseline) for row, baseline in zip(rows, baselines))
    train = tuple(metric_vector(row) for row in innovations[:len(training)])
    count = len(train)
    means = tuple(sum(row[index] for row in train) / count for index in range(6))
    covariance = tuple(tuple(sum((row[i] - means[i]) * (row[j] - means[j]) for row in train) / (count - 1)
                             + (regularizers[i] ** 2 if i == j else 0.0)
                             for j in range(6)) for i in range(6))
    reference_peak = sum(row.peak_memory_mb for row in rows[:count]) / count
    predicted = SixMetrics(means[0], means[1], reference_peak, 0, means[4], 0)
    profile = MeasuredLightProfile(profile_id, origin, process_pid, context_sha256,
                                   digest([asdict(row) for row in rows]), covariance, regularizers,
                                   predicted, 0.0, loss_weight, loss_tolerance, histogram_width_ev,
                                   minimum_exposure, maximum_exposure, max_attempts, max_execution_ms,
                                   max_wall_ms, no_progress_limit, progress_epsilon, referee_timeout_seconds,
                                   count, len(holdout), memory_model,
                                   means[2] if memory_model == "CONDITIONAL_LIFETIME_PEAK" else 0.0,
                                   digest(list(baselines)))
    training_scores = tuple(tension(profile.forecast_for(baseline), row, profile) for baseline, row in zip(baselines[:count], rows[:count]))
    limit = math.nextafter(max(training_scores), math.inf)
    holdout_scores = tuple(tension(profile.forecast_for(baseline), row, profile) for baseline, row in zip(baselines[count:], rows[count:]))
    if any(score > limit for score in holdout_scores):
        raise HoldoutOutsideTraining("Independent calibration holdout exceeds the pre-fixed training envelope; profile unavailable")
    return replace(profile, tension_limit=limit)


@dataclass(frozen=True)
class RefereeDecision:
    accepted: bool
    tension: float
    worker_thread: int
    profile_sha256: str
    forecast_sha256: str
    observed_sha256: str


class LocalLightReferee:
    """Bounded six-value arithmetic, no arbitrary evaluator callback/service."""
    def evaluate(self, forecast, observed, profile):
        if type(forecast) is not SixMetrics or type(observed) is not SixMetrics or type(profile) is not MeasuredLightProfile:
            raise ProfileUnavailable("Typed detached forecast/observation/profile required")
        forecast, observed, profile = replace(forecast), replace(observed), replace(profile)
        output = queue.Queue(maxsize=1)
        def compute():
            try:
                xi = tension(forecast, observed, profile)
                accepted = observed.invariant_violation == 0 and observed.task_loss <= profile.loss_tolerance and xi <= profile.tension_limit
                output.put(RefereeDecision(accepted, xi, threading.get_ident(), profile.sha256,
                                           digest(asdict(forecast)), digest(asdict(observed))))
            except Exception as exc:
                _boundary_log.warning("Bounded LIGHT boundary %s caught %s", 'light_profile.compute', type(exc).__name__[:120])
                output.put(ProfileUnavailable("Local arithmetic unavailable: " + type(exc).__name__))
        worker = threading.Thread(target=compute, name="synapse-light-referee", daemon=True)
        worker.start()
        worker.join(profile.referee_timeout_seconds)
        if worker.is_alive():
            raise ProfileUnavailable("Local referee deadline exceeded; no decision")
        try:
            result = output.get_nowait()
        except queue.Empty as exc:
            raise ProfileUnavailable("Local referee produced no decision") from exc
        if type(result) is not RefereeDecision:
            raise ProfileUnavailable(str(result))
        if (result.worker_thread == threading.get_ident() or result.profile_sha256 != profile.sha256
                or result.forecast_sha256 != digest(asdict(forecast)) or result.observed_sha256 != digest(asdict(observed))):
            raise ProfileUnavailable("Local referee identity/measurement binding failed")
        return result
