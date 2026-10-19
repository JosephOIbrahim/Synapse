"""Dormant Atlas seam. Existing WorldLabsClient remains the connection owner.

Only explicit in-memory SYNTHETIC fixtures can run. No HTTP executor, upload,
credential configuration, flag promotion or tool registration exists here.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
from typing import Mapping

from .client import WorldLabsError
from .atlas_contracts import (
    API_FAMILY, TASK, AssetRef, CameraIntrinsics, CameraPose, ContractError,
    PosedRGBDFrame, ProvenanceManifest, SpatialOperation, canonical, request_identity, sha256, token,
)


class AtlasNotEnabled(WorldLabsError):
    """Live Atlas execution is unavailable in this dormant scaffold."""


@dataclass(frozen=True)
class PosePlan:
    frames: tuple[tuple[str, AssetRef], ...]

    def __post_init__(self):
        object.__setattr__(self, "frames", tuple(tuple(row) for row in self.frames))
        request_identity(self.frames)

    @property
    def request_id(self):
        return request_identity(self.frames)


def plan_pose(frames):
    """Plan fixture identity only; a request digest is never owner approval."""
    return PosePlan(tuple(frames))


@dataclass(frozen=True)
class SyntheticFixtureBinding:
    """Authored with fixture data, independently of the plan passed to parse.

    This is synthetic test context, not a provider field or security boundary.
    A future live executor needs a trusted owner of persisted request records.
    """
    request_sha256: str
    frame_ids: tuple[str, ...]
    output_assets: tuple[tuple[AssetRef, AssetRef, AssetRef], ...]
    operation_id: str
    world_frame: str

    def __post_init__(self):
        sha256(self.request_sha256)
        token(self.operation_id)
        token(self.world_frame)
        if not self.operation_id.startswith("SYNTHETIC-"):
            raise ContractError("synthetic operation binding required")
        object.__setattr__(self, "frame_ids", tuple(self.frame_ids))
        object.__setattr__(self, "output_assets", tuple(tuple(row) for row in self.output_assets))
        if not self.frame_ids or len(set(self.frame_ids)) != len(self.frame_ids):
            raise ContractError("unique ordered source frame identities required")
        for identity in self.frame_ids:
            token(identity)
        if len(self.frame_ids) != len(self.output_assets):
            raise ContractError("bound output cardinality differs from source")
        for row in self.output_assets:
            if len(row) != 3 or any(not isinstance(asset, AssetRef) for asset in row):
                raise ContractError("typed ordered output asset binding required")


class SyntheticFixtureEnvelope(dict):
    """Mutable fixture operation plus separately fixed synthetic source binding."""
    __slots__ = ("_binding",)

    def __init__(self, binding, operation):
        if type(binding) is not SyntheticFixtureBinding or not isinstance(operation, dict):
            raise ContractError("explicit synthetic fixture binding required")
        super().__init__(deepcopy(operation))
        object.__setattr__(self, "_binding", binding)

    def __setattr__(self, name, value):
        raise AttributeError("fixture source binding is fixed")

    @property
    def binding(self):
        return self._binding

    def __deepcopy__(self, memo):
        return type(self)(self.binding, deepcopy(dict(self), memo))

    def with_operation(self, **changes):
        result = deepcopy(self)
        result.update(changes)
        return result


def parse_fixture_operation(payload, plan: PosePlan, assets: Mapping[str, AssetRef], *,
                            api_family=API_FAMILY, decoded_row_order="top_down"):
    """Normalize documented operation/camera fields from SYNTHETIC fixtures.

    Output content hashes come from supplied synthetic bytes, never invented
    from provider IDs or URLs. URLs, account data and provider error text are
    discarded. Real operation parsing/asset retrieval is not activated.
    """
    if api_family != API_FAMILY or type(payload) is not SyntheticFixtureEnvelope or type(plan) is not PosePlan:
        raise ContractError("Atlas v2 operation required; Marble v1 is separate")
    binding = payload.binding
    if (binding.request_sha256 != plan.request_id or binding.frame_ids != tuple(row[0] for row in plan.frames)
            or binding.operation_id != payload.get("id")):
        raise ContractError("fixture source identity differs from the requested operation")
    if not isinstance(payload.get("metadata"), dict) or payload["metadata"].get("task") != TASK:
        raise ContractError("operation task differs from the pose request")
    operation_id = payload.get("id")
    if type(payload.get("done")) is not bool:
        raise ContractError("explicit operation terminal flag required")
    response, error = payload.get("response"), payload.get("error")
    if not payload["done"]:
        if response is not None or error is not None:
            raise ContractError("pending operation carries terminal data")
        return SpatialOperation(operation_id, "PENDING", plan.request_id)
    if (response is None) == (error is None):
        raise ContractError("terminal operation requires exactly one response or error")
    if error is not None:
        return SpatialOperation(operation_id, "FAILED", plan.request_id, error_code="provider_error")
    if not isinstance(response, dict) or not isinstance(response.get("frames"), list):
        raise ContractError("complete ordered pose response required")
    if len(response["frames"]) != len(plan.frames):
        raise ContractError("response frame cardinality differs from input")
    result = []
    for frame_id, expected_assets, row in zip(binding.frame_ids, binding.output_assets, response["frames"]):
        try:
            camera = row["camera"]
            intrinsics = camera["intrinsics"]
            pose = camera["extrinsics"]
            refs = (row["imageAsset"], row["depth"]["depthAsset"], row["depth"]["confidenceAsset"])
            resolved = tuple(assets[ref["assetId"]] for ref in refs)
            if resolved != expected_assets or any(asset.asset_id != ref["assetId"] for asset, ref in zip(resolved, refs)):
                raise ContractError("asset identity differs from fixture bytes")
            result.append(PosedRGBDFrame(frame_id, *resolved,
                CameraIntrinsics(**intrinsics),
                CameraPose(pose["position"], pose["quaternion"], pose["coordinateSystem"], binding.world_frame),
                "linear_exr_half", decoded_row_order, metres_per_unit=None))
        except (KeyError, TypeError, AttributeError):
            raise ContractError("invalid or incomplete synthetic camera/asset bundle") from None
    return SpatialOperation(operation_id, "SUCCEEDED", plan.request_id, tuple(result))


class SyntheticFixtureTransport:
    """In-memory test data only. No callback, URL, socket or file transport."""

    def __init__(self, payload, assets):
        if type(payload) is not SyntheticFixtureEnvelope:
            raise ContractError("transport requires an independently bound synthetic fixture")
        self._payload = deepcopy(payload)
        self._assets = dict(assets)

    def run(self, plan):
        return parse_fixture_operation(deepcopy(self._payload), plan, self._assets)


class AtlasAdapter:
    """Borrow an existing WorldLabsClient; never construct/configure another."""

    def __init__(self, existing_client):
        self._existing_client = existing_client

    def status(self):
        return {"state": "DISABLED", "api_family": API_FAMILY, "live_validated": False,
                "reason": "Dormant scaffold; synthetic fixtures only; no registered Atlas tools."}

    def run_fixture(self, plan, transport):
        if type(transport) is not SyntheticFixtureTransport:
            raise AtlasNotEnabled("Only the explicit in-memory synthetic fixture transport is available.")
        return transport.run(plan)

    def submit(self, plan):
        raise AtlasNotEnabled("Atlas submission is disabled; no media, entitlement or cost approval is implied.")

    def upload(self, *args, **kwargs):
        raise AtlasNotEnabled("Atlas uploads are disabled.")

    def resume(self, *args, **kwargs):
        raise AtlasNotEnabled("Live Atlas operation reads are not enabled by this scaffold.")

    def read_asset(self, *args, **kwargs):
        raise AtlasNotEnabled("Live Atlas asset reads are not enabled by this scaffold.")


def provenance(plan: PosePlan, operation: SpatialOperation):
    if operation.phase != "SUCCEEDED" or operation.request_sha256 != plan.request_id or tuple(frame.frame_id for frame in operation.frames) != tuple(
            frame_id for frame_id, _ in plan.frames):
        raise ContractError("only a matching complete ordered result has output provenance")
    return ProvenanceManifest(
        tuple(frame_id for frame_id, _ in plan.frames),
        tuple(asset.content_sha256 for _, asset in plan.frames),
        tuple((frame.image.content_sha256, frame.depth.content_sha256, frame.confidence.content_sha256)
              for frame in operation.frames),
        plan.request_id,
        hashlib.sha256(canonical([asdict(frame) for frame in operation.frames]).encode("utf-8")).hexdigest(),
    )
