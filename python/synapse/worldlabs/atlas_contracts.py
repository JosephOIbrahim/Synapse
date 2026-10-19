"""Pure dormant Atlas data contracts. No I/O, registration or credential access.

Marble v1 PLY import remains in the existing client/importer. These contracts
describe Atlas v2 camera bundles; they do not enable an Atlas API executor.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Iterable

SCHEMA_VERSION = "synapse.atlas.contracts.v1"
API_FAMILY = "atlas_v2"
TASK = "images2PosedRGBD"
_TOKEN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class ContractError(ValueError):
    """Public-safe contract error; input values must not be echoed."""


def token(value):
    if not isinstance(value, str) or not _TOKEN.fullmatch(value):
        raise ContractError("invalid opaque identity")
    return value


def sha256(value):
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ContractError("invalid content digest")
    return value


def finite(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ContractError("finite numeric value required")
    return float(value)


def vector(value, count):
    if not isinstance(value, (tuple, list)) or len(value) != count:
        raise ContractError("invalid vector shape")
    return tuple(finite(item) for item in value)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class AssetRef:
    asset_id: str
    content_sha256: str
    media_type: str
    evidence_tier: str = "SYNTHETIC"

    def __post_init__(self):
        token(self.asset_id)
        sha256(self.content_sha256)
        if self.media_type not in {"image/png", "image/jpeg", "image/x-exr"}:
            raise ContractError("unsupported asset format")
        if self.evidence_tier != "SYNTHETIC" or not self.asset_id.startswith("SYNTHETIC-"):
            raise ContractError("dormant fixtures require explicitly synthetic assets")


@dataclass(frozen=True)
class CameraIntrinsics:
    width: int
    height: int
    fx: float
    fy: float
    cx: float
    cy: float

    def __post_init__(self):
        if any(type(v) is not int or v <= 0 for v in (self.width, self.height)):
            raise ContractError("positive integer image dimensions required")
        for name in ("fx", "fy", "cx", "cy"):
            object.__setattr__(self, name, finite(getattr(self, name)))
        if self.fx <= 0 or self.fy <= 0:
            raise ContractError("positive pixel focal lengths required")


@dataclass(frozen=True)
class CameraPose:
    position: tuple[float, float, float]
    quaternion_xyzw: tuple[float, float, float, float]
    coordinate_system: str
    world_frame: str

    def __post_init__(self):
        object.__setattr__(self, "position", vector(self.position, 3))
        object.__setattr__(self, "quaternion_xyzw", vector(self.quaternion_xyzw, 4))
        if self.coordinate_system not in {"rub", "rdf"}:
            raise ContractError("explicit RUB or RDF camera axes required")
        token(self.world_frame)
        if not math.isclose(sum(v * v for v in self.quaternion_xyzw), 1.0, rel_tol=0, abs_tol=1e-6):
            raise ContractError("unit XYZW quaternion required; no implicit normalization")


@dataclass(frozen=True)
class PosedRGBDFrame:
    frame_id: str
    image: AssetRef
    depth: AssetRef
    confidence: AssetRef
    intrinsics: CameraIntrinsics
    pose: CameraPose
    depth_encoding: str
    decoded_row_order: str
    metres_per_unit: float | None = None

    def __post_init__(self):
        token(self.frame_id)
        if not isinstance(self.image, AssetRef) or self.image.media_type not in {"image/png", "image/jpeg"}:
            raise ContractError("RGB image reference required")
        if not isinstance(self.depth, AssetRef) or self.depth.media_type != "image/x-exr":
            raise ContractError("linear EXR depth reference required")
        if not isinstance(self.confidence, AssetRef) or self.confidence.media_type != "image/png":
            raise ContractError("PNG confidence reference required")
        if not isinstance(self.intrinsics, CameraIntrinsics) or not isinstance(self.pose, CameraPose):
            raise ContractError("typed camera bundle required")
        if self.depth_encoding != "linear_exr_half":
            raise ContractError("unsupported depth encoding")
        if self.decoded_row_order not in {"top_down", "bottom_up"}:
            raise ContractError("decoder row order must be explicit")
        if self.metres_per_unit is not None:
            scale = finite(self.metres_per_unit)
            if scale <= 0:
                raise ContractError("positive calibrated scale required")
            object.__setattr__(self, "metres_per_unit", scale)


@dataclass(frozen=True)
class SpatialOperation:
    operation_id: str
    phase: str
    request_sha256: str
    frames: tuple[PosedRGBDFrame, ...] = ()
    error_code: str | None = None
    api_family: str = API_FAMILY
    task: str = TASK
    evidence_tier: str = "SYNTHETIC"

    def __post_init__(self):
        token(self.operation_id)
        sha256(self.request_sha256)
        object.__setattr__(self, "frames", tuple(self.frames))
        if not self.operation_id.startswith("SYNTHETIC-") or self.evidence_tier != "SYNTHETIC":
            raise ContractError("no real operation identity is claimed by dormant fixtures")
        if self.api_family != API_FAMILY or self.task != TASK:
            raise ContractError("Atlas v2 pose operation required; Marble v1 is separate")
        if self.phase not in {"PENDING", "SUCCEEDED", "FAILED"}:
            raise ContractError("unknown operation phase")
        if self.phase == "SUCCEEDED":
            if not self.frames or any(not isinstance(frame, PosedRGBDFrame) for frame in self.frames) or self.error_code is not None:
                raise ContractError("successful operation requires complete camera bundles")
            if len({frame.frame_id for frame in self.frames}) != len(self.frames):
                raise ContractError("unique ordered output frame identities required")
            if len({frame.pose.world_frame for frame in self.frames}) != 1:
                raise ContractError("all output poses must share one world frame")
        elif self.frames:
            raise ContractError("non-successful operation cannot carry output frames")
        if self.phase == "FAILED" and self.error_code != "provider_error":
            raise ContractError("failure must carry a public-safe error code")
        if self.phase == "PENDING" and self.error_code is not None:
            raise ContractError("pending operation cannot carry a terminal error")


@dataclass(frozen=True)
class ProvenanceManifest:
    frame_ids: tuple[str, ...]
    input_sha256: tuple[str, ...]
    output_sha256: tuple[tuple[str, str, str], ...]
    request_sha256: str
    spatial_result_sha256: str
    schema_version: str = SCHEMA_VERSION
    provider: str = "worldlabs"
    api_family: str = API_FAMILY
    task: str = TASK
    evidence_tier: str = "SYNTHETIC"

    def __post_init__(self):
        sha256(self.request_sha256)
        sha256(self.spatial_result_sha256)
        object.__setattr__(self, "frame_ids", tuple(self.frame_ids))
        object.__setattr__(self, "input_sha256", tuple(self.input_sha256))
        object.__setattr__(self, "output_sha256", tuple(tuple(row) for row in self.output_sha256))
        if not self.frame_ids or len(set(self.frame_ids)) != len(self.frame_ids):
            raise ContractError("unique ordered frame identities required")
        if not (len(self.frame_ids) == len(self.input_sha256) == len(self.output_sha256)):
            raise ContractError("ordered input and output cardinality differs")
        for identity in self.frame_ids:
            token(identity)
        for value in self.input_sha256:
            sha256(value)
        for row in self.output_sha256:
            if len(row) != 3:
                raise ContractError("each output needs RGB, depth and confidence hashes")
            for value in row:
                sha256(value)
        if (self.schema_version, self.provider, self.api_family, self.task, self.evidence_tier) != (
                SCHEMA_VERSION, "worldlabs", API_FAMILY, TASK, "SYNTHETIC"):
            raise ContractError("unsupported provenance schema or evidence tier")

    def to_json(self):
        return canonical(asdict(self))


def mask_depth(values: Iterable[float]):
    """Mask invalid decoded linear depths; this function does not decode EXR."""
    result = []
    for value in values:
        if type(value) not in (int, float):
            raise ContractError("numeric decoded depths required")
        result.append(float(value) if math.isfinite(value) and value > 0 else None)
    return tuple(result)


def unproject_metric(frame: PosedRGBDFrame, decoded_depth):
    """Pure synthetic geometry check with explicit decoder rows and scale.

    Depth is optical-axis distance. Unknown scale refuses metric geometry.
    The row mapping applies to the supplied decoder buffer, not every EXR.
    """
    if frame.metres_per_unit is None:
        raise ContractError("metric scale is unknown")
    camera = frame.intrinsics
    depth = mask_depth(decoded_depth)
    if len(depth) != camera.width * camera.height:
        raise ContractError("depth buffer does not match the camera grid")
    qx, qy, qz, qw = frame.pose.quaternion_xyzw
    points = []
    for y in range(camera.height):
        source_y = y if frame.decoded_row_order == "top_down" else camera.height - 1 - y
        for x in range(camera.width):
            z = depth[source_y * camera.width + x]
            if z is None:
                points.append(None)
                continue
            vx, vy, vz = vector(((x - camera.cx) * z / camera.fx, (y - camera.cy) * z / camera.fy, z), 3)
            if frame.pose.coordinate_system == "rub":
                vy, vz = -vy, -vz
            # Unit-quaternion rotation: v + 2*w*(q_xyz x v) + 2*(q_xyz x (q_xyz x v)).
            tx, ty, tz = vector((2 * (qy * vz - qz * vy), 2 * (qz * vx - qx * vz), 2 * (qx * vy - qy * vx)), 3)
            rotated = vector((vx + qw * tx + qy * tz - qz * ty,
                       vy + qw * ty + qz * tx - qx * tz,
                       vz + qw * tz + qx * ty - qy * tx), 3)
            translated = vector(tuple(rotated[i] + frame.pose.position[i] for i in range(3)), 3)
            points.append(vector(tuple(value * frame.metres_per_unit for value in translated), 3))
    return tuple(points)


def request_identity(frames):
    """Preserve sequence order. Hash sorting would collapse distinct captures."""
    ordered = []
    for frame_id, image in frames:
        token(frame_id)
        if not isinstance(image, AssetRef) or image.media_type not in {"image/png", "image/jpeg"}:
            raise ContractError("typed synthetic image input required")
        ordered.append({"frame_id": frame_id, "image": asdict(image)})
    if not ordered or len({row["frame_id"] for row in ordered}) != len(ordered):
        raise ContractError("unique ordered inputs required")
    body = {"schema": SCHEMA_VERSION, "api_family": API_FAMILY, "task": TASK, "frames": ordered}
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()
