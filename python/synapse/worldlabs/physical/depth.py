"""HD1 depth conditioning: validity, confidence and edges (SPEC 4).

Pure numpy over one decoded depth buffer. No hou, no pxr and no I/O, mirroring
spatial/path.py; importing this module registers nothing.

    condition_depth(depth, confidence=None)   the three rules: one keep mask,
                                              per-rule flags and counts
    above_half_float_difference(depth)        claim HD-05, measured: what the
                                              landed contract keeps and HD1
                                              drops

The rules. Each is an independent (H, W) bool flag in the input buffer's own
row order:

    invalid         not finite, not above 0, or above 65504 (the half-float
                    ceiling)
    low_confidence  below confidence_min, and only where a confidence array is
                    supplied. That array must be finite and in [0, 1]: a NaN
                    would compare as a silent keep, and an un-normalised 8-bit
                    array would keep everything, so both are refused.
    edge            a 4-neighbour pair whose depths differ by more than
                    edge_rel_max of the nearer one (strict, by multiplication);
                    both pixels of the pair are flagged. Only pairs of two
                    valid depths count, so an invalid pixel neither flags nor
                    shields its neighbours. Borders have fewer neighbours and
                    nothing wraps around. A low-confidence neighbour still
                    counts, which keeps the rules independent.

``flagged`` counts each rule on its own; rules may overlap. ``dropped`` gives
each dropped pixel to the first rule in RULES that flags it, so its counts sum
to total - kept. The mask never fills, interpolates or clips, and no depth
value comes back.

Without numpy both functions report BLOCKED with a reason, as spatial/path.py
does, and every array and count is None rather than a zero that would read as
measured. Error messages are public-safe: they never echo an input value.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numbers
from typing import Any, Dict, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - numpy is a dev extra; without it the rules report BLOCKED
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

from ..atlas_contracts import ContractError, mask_depth

STATUS_SUCCESS = "SUCCESS"
STATUS_BLOCKED = "BLOCKED"

HALF_FLOAT_MAX = 65504.0    # SPEC 4: the half-float ceiling; at or below it is valid
CONFIDENCE_MIN = 0.5        # SPEC 4 proposal (D-1's to rule); strictly below it drops
EDGE_REL_MAX = 0.05         # SPEC 4 proposal (D-1's to rule); strictly above it is an edge
RULES = ("invalid", "low_confidence", "edge")   # attribution order for ``dropped``

_BLOCKED_REASON = "depth conditioning requires numpy"
_DEPTH_ARRAY = "decoded depth must be a non-empty 2-D array"
_CONFIDENCE_ARRAY = "decoded confidence must be a non-empty 2-D array"
_CONFIDENCE_GRID = "confidence must match the depth grid"
_CONFIDENCE_RANGE = "confidence must be finite and normalised to [0, 1]"
_CONFIDENCE_MIN_RANGE = "confidence_min must be a finite number in [0, 1]"
_EDGE_REL_RANGE = "edge_rel_max must be a finite number above 0"
_REAL_KINDS = "iuf"         # signed and unsigned integers, floats; bool, complex, text and objects refuse


@dataclass(frozen=True, eq=False)
class DepthMask:
    """The three rules' flags and counts for one decoded depth buffer.

    ``keep``, ``invalid``, ``low_confidence`` and ``edge`` are (H, W) bool
    arrays, read-only, in the same row order as the input buffer. ``flagged``
    and ``dropped`` are ``{rule: count}`` in RULES order, as Python ints.
    ``thresholds`` records ``half_float_max``, ``confidence_min`` and
    ``edge_rel_max`` as Python floats. There is no depth field.

    ``status`` is SUCCESS, or BLOCKED without numpy; when BLOCKED, ``reason``
    says why and every array and count is None.
    """

    keep: Optional[np.ndarray]
    invalid: Optional[np.ndarray]
    low_confidence: Optional[np.ndarray]
    edge: Optional[np.ndarray]
    flagged: Optional[Dict[str, int]]
    dropped: Optional[Dict[str, int]]
    kept: Optional[int]
    total: Optional[int]
    confidence_supplied: bool
    thresholds: Optional[Dict[str, float]]
    status: str = STATUS_SUCCESS
    reason: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """JSON-safe record: status, rules, shape, counts and thresholds; no arrays."""
        return {
            "status": self.status,
            "reason": self.reason,
            "rules": list(RULES),
            "shape": None if self.keep is None else [int(n) for n in self.keep.shape],
            "flagged": None if self.flagged is None else dict(self.flagged),
            "dropped": None if self.dropped is None else dict(self.dropped),
            "kept": self.kept,
            "total": self.total,
            "confidence_supplied": bool(self.confidence_supplied),
            "thresholds": None if self.thresholds is None else dict(self.thresholds),
        }


def _real_number(value, message: str) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ContractError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(message)
    return number


def _thresholds(confidence_min, edge_rel_max) -> Dict[str, float]:
    cmin = _real_number(confidence_min, _CONFIDENCE_MIN_RANGE)
    if not 0.0 <= cmin <= 1.0:
        raise ContractError(_CONFIDENCE_MIN_RANGE)
    rel = _real_number(edge_rel_max, _EDGE_REL_RANGE)
    if not rel > 0.0:
        raise ContractError(_EDGE_REL_RANGE)
    return {"half_float_max": HALF_FLOAT_MAX, "confidence_min": cmin, "edge_rel_max": rel}


def _real_2d(value, message: str):
    """A non-empty 2-D array of real numbers as float64; the input is never written."""
    try:
        array = np.asarray(value)
    except (TypeError, ValueError, OverflowError):
        raise ContractError(message) from None
    if array.dtype.kind not in _REAL_KINDS or array.ndim != 2 or array.size == 0:
        raise ContractError(message)
    return np.asarray(array, dtype=np.float64)


def _valid(z):
    with np.errstate(invalid="ignore"):
        return np.isfinite(z) & (z > 0.0) & (z <= HALF_FLOAT_MAX)


def _edges(z, valid, rel: float):
    # Invalid pixels take no part in any pair. The placeholder only keeps NaN
    # and inf out of the arithmetic; every pair it touches is masked out.
    safe = np.where(valid, z, 0.0)
    edge = np.zeros(z.shape, dtype=bool)
    a, b = safe[:-1, :], safe[1:, :]
    jump = valid[:-1, :] & valid[1:, :] & (np.abs(a - b) > rel * np.minimum(a, b))
    edge[:-1, :] |= jump
    edge[1:, :] |= jump
    a, b = safe[:, :-1], safe[:, 1:]
    jump = valid[:, :-1] & valid[:, 1:] & (np.abs(a - b) > rel * np.minimum(a, b))
    edge[:, :-1] |= jump
    edge[:, 1:] |= jump
    return edge


def condition_depth(depth, confidence=None, *, confidence_min=CONFIDENCE_MIN,
                    edge_rel_max=EDGE_REL_MAX) -> DepthMask:
    """Apply the validity, confidence and edge rules to one decoded depth buffer.

    ``depth`` is an (H, W) array of real numbers in raw units; it is read and
    never written. ``confidence`` is optional; when given it must have the same
    shape and be finite and in [0, 1]. Returns a DepthMask; nothing is filled.
    """
    thresholds = _thresholds(confidence_min, edge_rel_max)
    supplied = confidence is not None
    if not NUMPY_AVAILABLE:
        return DepthMask(None, None, None, None, None, None, None, None, supplied, thresholds,
                         status=STATUS_BLOCKED, reason=_BLOCKED_REASON)
    z = _real_2d(depth, _DEPTH_ARRAY)
    invalid = ~_valid(z)
    if supplied:
        c = _real_2d(confidence, _CONFIDENCE_ARRAY)
        if c.shape != z.shape:
            raise ContractError(_CONFIDENCE_GRID)
        if not (np.isfinite(c).all() and (c >= 0.0).all() and (c <= 1.0).all()):
            raise ContractError(_CONFIDENCE_RANGE)
        low_confidence = c < thresholds["confidence_min"]
    else:
        low_confidence = np.zeros(z.shape, dtype=bool)
    edge = _edges(z, ~invalid, thresholds["edge_rel_max"])

    flags = {"invalid": invalid, "low_confidence": low_confidence, "edge": edge}
    claimed = np.zeros(z.shape, dtype=bool)
    dropped: Dict[str, int] = {}
    for rule in RULES:
        dropped[rule] = int(np.count_nonzero(flags[rule] & ~claimed))
        claimed |= flags[rule]
    keep = ~claimed
    for array in (keep, invalid, low_confidence, edge):
        array.setflags(write=False)
    return DepthMask(
        keep=keep,
        invalid=invalid,
        low_confidence=low_confidence,
        edge=edge,
        flagged={rule: int(np.count_nonzero(flags[rule])) for rule in RULES},
        dropped=dropped,
        kept=int(np.count_nonzero(keep)),
        total=int(z.size),
        confidence_supplied=supplied,
        thresholds=thresholds,
    )


def above_half_float_difference(depth) -> Dict[str, Any]:
    """Claim HD-05, measured on one buffer; reported, never resolved.

    The landed contract's ``mask_depth`` keeps every finite depth above 0. HD1's
    validity rule also drops depths above 65504. This calls the contract's own
    ``mask_depth``, so ``contract_valid`` follows the landed code, and counts
    the pixels each rule keeps that the other drops. ``hd1_valid`` is the
    validity rule alone: no confidence and no edges.
    """
    record: Dict[str, Any] = {
        "claim": "HD-05",
        "status": STATUS_SUCCESS,
        "reason": None,
        "half_float_max": HALF_FLOAT_MAX,
        "total": None,
        "contract_valid": None,
        "hd1_valid": None,
        "kept_by_contract_dropped_by_hd1": None,
        "kept_by_hd1_dropped_by_contract": None,
        "resolved": False,
    }
    if not NUMPY_AVAILABLE:
        record.update(status=STATUS_BLOCKED, reason=_BLOCKED_REASON)
        return record
    z = _real_2d(depth, _DEPTH_ARRAY)
    contract = np.fromiter((value is not None for value in mask_depth(z.ravel().tolist())),
                           dtype=bool, count=z.size)
    hd1 = _valid(z).ravel()
    record.update(
        total=int(z.size),
        contract_valid=int(np.count_nonzero(contract)),
        hd1_valid=int(np.count_nonzero(hd1)),
        kept_by_contract_dropped_by_hd1=int(np.count_nonzero(contract & ~hd1)),
        kept_by_hd1_dropped_by_contract=int(np.count_nonzero(hd1 & ~contract)),
    )
    return record
