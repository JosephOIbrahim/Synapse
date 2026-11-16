"""HD1 scale claims with provenance (SPEC 5.3).

A scale is a claim, never a fact (principle H3). Each claim is the world
manifest's ``provenancedNumber`` (``{value, tier, method, probe}``, tier from
``$defs/tier``) plus the inputs it was derived from. Pure Python: no numpy, no
hou, no pxr and no I/O; importing this module registers nothing.

    unknown_scale()                             value None, tier "unknown"
    asserted_fixture(value, probe=...)          "asserted:fixture", tier manual
    from_camera_height(eye_m, floor)            "derived:camera-height"
    from_reference_length(a, b, length_m)       "derived:reference-length"
    from_metric_depth(...)                      "derived:moge2": reserved (D-HD-05)
    make_claim(method, **kwargs)                dispatch by method name
    require_metric(claim)                       the value, or ScaleRefused
    apply_claim(frame, claim)                   the frame with metres_per_unit set

Rules. With no claim the value is None and the tier is ``unknown``, and metric
output is refused: there is never a default of 1.0, and no parameter or
fallback here supplies one. A scale applies to depth and camera position
together, because the contract multiplies the translated point. A frame that
already carries ``metres_per_unit`` is never overwritten. The reserved method
raises ScaleMethodNotEnabled; an unknown method raises ContractError. Both
refusal classes are ContractError subclasses, and no message echoes an input
value.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import numbers
from types import MappingProxyType
from typing import Any, Dict, Optional, Tuple

from ..atlas_contracts import ContractError, PosedRGBDFrame
from .level import STATUS_SUCCESS, FloorFit

TIERS = ("vendor", "derived", "probed", "manual", "unknown")   # world_manifest.schema.json $defs.tier.enum
METHOD_TIERS = MappingProxyType({
    "asserted:fixture": "manual",
    "derived:camera-height": "derived",
    "derived:reference-length": "derived",
})
RESERVED_METHODS = MappingProxyType({"derived:moge2": "D-HD-05"})
PROBE_MAX_CHARS = 256

_RESERVED_MESSAGE = "derived:moge2 is reserved and not enabled (D-HD-05)"


class ScaleRefused(ContractError):
    """Metric output refused: the scale is unknown, or the evidence cannot support a claim."""


class ScaleMethodNotEnabled(ContractError):
    """A reserved scale method name: named, and not enabled."""


def _real(value, message: str) -> float:
    """A finite real number as a Python float; bool, text and None are refused."""
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ContractError(message)
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(message)
    return number


def _positive(value, message: str) -> float:
    number = _real(value, message)
    if not number > 0.0:
        raise ContractError(message)
    return number


def _probe(value, *, required: bool) -> Optional[str]:
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value or len(value) > PROBE_MAX_CHARS:
        raise ContractError("probe must be a non-empty string of 256 characters or fewer")
    return value


def _point(value) -> Tuple[float, float, float]:
    message = "reference points must be three finite numbers"
    try:
        items = tuple(value)
    except TypeError:
        raise ContractError(message) from None
    if len(items) != 3:
        raise ContractError(message)
    return tuple(_real(item, message) for item in items)


def _inputs(value) -> Tuple[Tuple[str, Any], ...]:
    message = "inputs must be (name, number or text) pairs with unique names"
    try:
        pairs = tuple(tuple(pair) for pair in value)
    except TypeError:
        raise ContractError(message) from None
    names = set()
    for pair in pairs:
        if len(pair) != 2 or not isinstance(pair[0], str) or not pair[0] or pair[0] in names:
            raise ContractError(message)
        names.add(pair[0])
        item = pair[1]
        if item is None or type(item) is str or type(item) is int:
            continue
        if type(item) is not float or not math.isfinite(item):
            raise ContractError(message)
    return pairs


@dataclass(frozen=True)
class ScaleClaim:
    """One scale claim: the manifest's provenancedNumber plus the inputs it came from.

    tier ``unknown`` if and only if value and method are None. Otherwise the
    value is a finite Python float above 0, the method is an enabled method and
    the tier is that method's tier. ``probe`` is None or a short string.
    ``inputs`` is a tuple of (name, value) pairs: recorded, and not part of the
    provenancedNumber.
    """

    value: Optional[float]
    tier: str
    method: Optional[str]
    probe: Optional[str]
    inputs: Tuple[Tuple[str, Any], ...] = ()

    def __post_init__(self):
        if not isinstance(self.tier, str) or self.tier not in TIERS:
            raise ContractError("scale tier must be one of the manifest tiers")
        if isinstance(self.method, str) and self.method in RESERVED_METHODS:
            raise ScaleMethodNotEnabled(_RESERVED_MESSAGE)
        object.__setattr__(self, "probe", _probe(self.probe, required=False))
        object.__setattr__(self, "inputs", _inputs(self.inputs))
        if self.tier == "unknown":
            if self.value is not None or self.method is not None:
                raise ContractError("an unknown scale carries no value and no method")
            return
        if self.value is None:
            raise ContractError("a known scale tier requires a value")
        object.__setattr__(self, "value", _positive(self.value, "scale value must be a finite number above 0"))
        if not isinstance(self.method, str) or self.method not in METHOD_TIERS:
            raise ContractError("scale method is not an enabled method")
        if METHOD_TIERS[self.method] != self.tier:
            raise ContractError("scale tier does not match its method")

    @property
    def known(self) -> bool:
        return self.value is not None

    def provenanced_number(self) -> Dict[str, Any]:
        """Exactly the manifest's provenancedNumber keys: value, tier, method, probe."""
        return {"value": self.value, "tier": self.tier, "method": self.method, "probe": self.probe}

    def as_record(self) -> Dict[str, Any]:
        """The provenancedNumber plus ``inputs`` as a dict; JSON-safe."""
        record = self.provenanced_number()
        record["inputs"] = dict(self.inputs)
        return record


def unknown_scale() -> ScaleClaim:
    """No claim: value None, tier unknown, method None, probe None."""
    return ScaleClaim(None, "unknown", None, None)


def asserted_fixture(value, *, probe) -> ScaleClaim:
    """The fixture's own truth, asserted (tier manual). ``probe`` names where it comes from."""
    scale = _positive(value, "asserted scale must be a finite number above 0")
    return ScaleClaim(scale, METHOD_TIERS["asserted:fixture"], "asserted:fixture",
                      _probe(probe, required=True), (("asserted_metres_per_unit", scale),))


def from_camera_height(declared_eye_height_m, floor: FloorFit, *, probe=None) -> ScaleClaim:
    """``declared_eye_height_m / floor.camera_height`` (tier derived).

    Refuses an eye height that is not a finite number above 0, a floor that is
    not SUCCESS, and a camera that is not above the fitted floor.
    """
    eye = _positive(declared_eye_height_m, "declared eye height must be a finite number above 0")
    probe = _probe(probe, required=False)
    if not isinstance(floor, FloorFit):
        raise ContractError("a FloorFit is required")
    if floor.status != STATUS_SUCCESS:
        raise ScaleRefused("floor is not SUCCESS: no camera-height scale")
    height = floor.camera_height
    if isinstance(height, bool) or not isinstance(height, numbers.Real) or not math.isfinite(float(height)):
        raise ScaleRefused("camera height is not a finite number: no camera-height scale")
    height = float(height)
    if not height > 0.0:
        raise ScaleRefused("camera is not above the fitted floor: no camera-height scale")
    value = eye / height
    if not (math.isfinite(value) and value > 0.0):
        raise ScaleRefused("camera-height scale is not a finite number above 0")
    return ScaleClaim(value, METHOD_TIERS["derived:camera-height"], "derived:camera-height", probe,
                      (("declared_eye_height_m", eye), ("camera_height_units", height),
                       ("floor_seed", int(floor.seed))))


def from_reference_length(point_a, point_b, known_length_m, *, probe=None) -> ScaleClaim:
    """``known_length_m / |b - a|`` for two raw-frame points (tier derived).

    Generalises the parent blueprint's doorway heuristic. Refuses non-finite
    points, coincident points and a length that is not above 0.
    """
    a = _point(point_a)
    b = _point(point_b)
    length = _positive(known_length_m, "known length must be a finite number above 0")
    probe = _probe(probe, required=False)
    measured = math.dist(a, b)
    if not math.isfinite(measured):
        raise ContractError("reference points are too far apart to measure")
    if not measured > 0.0:
        raise ScaleRefused("reference points coincide: no reference-length scale")
    value = length / measured
    if not (math.isfinite(value) and value > 0.0):
        raise ScaleRefused("reference-length scale is not a finite number above 0")
    return ScaleClaim(value, METHOD_TIERS["derived:reference-length"], "derived:reference-length", probe,
                      (("known_length_m", length), ("measured_length_units", measured)))


def from_metric_depth(*args, **kwargs):
    """``derived:moge2``: the name is reserved and not enabled (D-HD-05)."""
    raise ScaleMethodNotEnabled(_RESERVED_MESSAGE)


_BUILDERS = MappingProxyType({
    "asserted:fixture": asserted_fixture,
    "derived:camera-height": from_camera_height,
    "derived:reference-length": from_reference_length,
})


def make_claim(method, **kwargs) -> ScaleClaim:
    """Build a claim by method name: enabled -> its builder; reserved -> ScaleMethodNotEnabled;
    anything else -> ContractError."""
    if not isinstance(method, str):
        raise ContractError("unknown scale method")
    if method in RESERVED_METHODS:
        raise ScaleMethodNotEnabled(_RESERVED_MESSAGE)
    builder = _BUILDERS.get(method)
    if builder is None:
        raise ContractError("unknown scale method")
    return builder(**kwargs)


def require_metric(claim) -> float:
    """The claim's metres per unit, or ScaleRefused. Never a default."""
    if not isinstance(claim, ScaleClaim):
        raise ScaleRefused("a scale claim is required")
    if claim.value is None:
        raise ScaleRefused("metric scale is unknown")
    return claim.value


def apply_claim(frame, claim) -> PosedRGBDFrame:
    """``replace(frame, metres_per_unit=claim value)``, which re-runs the contract's checks.

    Refuses a frame that already carries a scale (HD1 never overwrites one) and
    an unknown claim (ScaleRefused).
    """
    if not isinstance(frame, PosedRGBDFrame):
        raise ContractError("a PosedRGBDFrame is required")
    if frame.metres_per_unit is not None:
        raise ScaleRefused("the frame already carries a scale: HD1 never overwrites one")
    return replace(frame, metres_per_unit=require_metric(claim))
