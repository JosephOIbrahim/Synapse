"""
Synapse Epoch-Based Tier Adaptation

Records tier outcomes during each epoch, aggregates success rates at
epoch boundaries, and adjusts confidence thresholds for new (unpinned)
inputs.

He2025 compliance:
- Fixed epoch SIZE (not time-based) — same as paper's fixed split-size
- sorted() before aggregation — order-independent
- kahan_sum() for float aggregation — stable across batch sizes
- round_float() on output — deterministic precision
- Pin staleness uses epoch ID (monotonic int), not wall-clock time
- No timestamps in any deterministic path
"""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..core.determinism import kahan_sum, round_float

logger = logging.getLogger("synapse.routing")

# Default epoch size — fixed window (not time-based) for stable tier adaptation
DEFAULT_EPOCH_SIZE = 100

# Thresholds for tier preference adjustment
LOW_SUCCESS_THRESHOLD = 0.5   # Below this, prefer next tier for new queries
HIGH_SUCCESS_THRESHOLD = 0.9  # Above this, prefer this tier more aggressively

# Number of epochs before a pin is considered stale
PIN_STALE_EPOCHS = 2


@dataclass
class TierEpoch:
    """A single epoch of tier outcome observations.

    Outcomes are collected during the epoch. At the epoch boundary
    (when is_complete is True), aggregate() returns Kahan-summed
    success rates per tier for threshold adjustment.
    """
    epoch_id: int
    epoch_size: int = DEFAULT_EPOCH_SIZE
    outcomes: List[Tuple[str, bool, float]] = field(default_factory=list)

    def record(self, tier: str, success: bool, latency_ms: float):
        """Record a single tier outcome."""
        self.outcomes.append((tier, success, latency_ms))

    @property
    def is_complete(self) -> bool:
        """Check if epoch has reached its fixed size."""
        return len(self.outcomes) >= self.epoch_size

    def aggregate(self) -> Dict[str, float]:
        """Kahan-summed success rates per tier. He2025 compliant.

        Returns dict mapping tier name to success rate [0.0, 1.0].
        """
        tier_outcomes: Dict[str, List[float]] = {}
        for tier, success, _ in sorted(self.outcomes):  # sorted for determinism
            tier_outcomes.setdefault(tier, []).append(1.0 if success else 0.0)
        return {
            tier: round_float(kahan_sum(vals) / len(vals))
            for tier, vals in sorted(tier_outcomes.items())
        }

    def aggregate_latency(self) -> Dict[str, float]:
        """Kahan-summed average latency per tier in ms."""
        tier_latencies: Dict[str, List[float]] = {}
        for tier, _, latency in sorted(self.outcomes):
            tier_latencies.setdefault(tier, []).append(latency)
        return {
            tier: round_float(kahan_sum(vals) / len(vals))
            for tier, vals in sorted(tier_latencies.items())
        }


@dataclass
class TierThresholds:
    """Adjusted confidence thresholds per tier.

    Higher threshold = tier needs more confidence to be selected
    for new (unpinned) inputs. Range [0.0, 1.0].
    """
    thresholds: Dict[str, float] = field(default_factory=dict)

    def get(self, tier: str, default: float = 0.5) -> float:
        return self.thresholds.get(tier, default)

    def adjust(self, success_rates: Dict[str, float]):
        """Adjust thresholds based on epoch success rates.

        Low success -> raise threshold (harder to select).
        High success -> lower threshold (easier to select).
        """
        for tier, rate in sorted(success_rates.items()):
            current = self.thresholds.get(tier, 0.5)
            if rate < LOW_SUCCESS_THRESHOLD:
                # Poor performance — raise threshold (prefer other tiers)
                self.thresholds[tier] = round_float(min(1.0, current + 0.1))
            elif rate > HIGH_SUCCESS_THRESHOLD:
                # Great performance — lower threshold (prefer this tier)
                self.thresholds[tier] = round_float(max(0.1, current - 0.05))
            # Moderate performance — no change


class EpochAdapter:
    """Manages epoch lifecycle and threshold adjustment.

    Thread-safe. One instance per TieredRouter.
    """

    def __init__(self, epoch_size: int = DEFAULT_EPOCH_SIZE):
        self._epoch_size = epoch_size
        self._current_epoch = TierEpoch(epoch_id=0, epoch_size=epoch_size)
        self._thresholds = TierThresholds()
        self._epoch_history: List[Dict[str, float]] = []  # past epoch aggregates
        self._lock = threading.Lock()

    @property
    def epoch_id(self) -> int:
        with self._lock:
            return self._current_epoch.epoch_id

    @property
    def thresholds(self) -> TierThresholds:
        with self._lock:
            return self._thresholds

    def record(self, tier: str, success: bool, latency_ms: float):
        """Record a tier outcome. If epoch is complete, rotate."""
        with self._lock:
            self._current_epoch.record(tier, success, latency_ms)
            if self._current_epoch.is_complete:
                self._rotate_epoch()

    def _rotate_epoch(self):
        """Complete current epoch and start a new one.

        Aggregates success rates, adjusts thresholds, archives.
        Must be called under lock.
        """
        rates = self._current_epoch.aggregate()
        self._epoch_history.append(rates)
        self._thresholds.adjust(rates)

        logger.info(
            "Epoch %d complete (%d outcomes). Success rates: %s",
            self._current_epoch.epoch_id,
            len(self._current_epoch.outcomes),
            rates,
        )

        # Start new epoch
        self._current_epoch = TierEpoch(
            epoch_id=self._current_epoch.epoch_id + 1,
            epoch_size=self._epoch_size,
        )

    def get_stale_pin_epoch(self) -> int:
        """Get the epoch ID below which pins are stale.

        Pins from epochs older than (current - PIN_STALE_EPOCHS)
        should be evicted.
        """
        with self._lock:
            return max(0, self._current_epoch.epoch_id - PIN_STALE_EPOCHS)

    def stats(self) -> Dict:
        """Return adaptation statistics."""
        with self._lock:
            return {
                "epoch_id": self._current_epoch.epoch_id,
                "epoch_progress": len(self._current_epoch.outcomes),
                "epoch_size": self._epoch_size,
                "thresholds": dict(sorted(self._thresholds.thresholds.items())),
                "history_epochs": len(self._epoch_history),
                "latest_rates": self._epoch_history[-1] if self._epoch_history else {},
            }
