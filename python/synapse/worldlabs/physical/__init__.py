"""HD1 physical frame: one posed RGBD frame towards metric, level, collidable geometry.

Pure modules only: no hou, no pxr and no I/O. Importing this package has no
side effects and registers nothing; it only re-exports names.

    depth   validity, confidence and edge masks (SPEC 4)
    level   floor fit, levelling rotation, ground offset (SPEC 5.1, 5.2)
    scale   scale claims with provenance; refusal when unknown (SPEC 5.3)
    cloud   numpy unprojection, stride cap, point footprint (SPEC 6)

Each module keeps its own numpy guard and status strings; reach those as
``depth.NUMPY_AVAILABLE`` and so on. They are not re-exported here, so the
modules never clash.
"""
from __future__ import annotations

from .depth import (
    CONFIDENCE_MIN,
    EDGE_REL_MAX,
    HALF_FLOAT_MAX,
    RULES,
    DepthMask,
    above_half_float_difference,
    condition_depth,
)
from .level import (
    FLOOR_INLIER_REL,
    FLOOR_ITERATIONS,
    FLOOR_MAX_TILT_DEG,
    FLOOR_MIN_INLIER_FRACTION,
    FLOOR_REFINE_PASSES,
    FLOOR_ROWS_FRACTION,
    FLOOR_SEED,
    FloorFit,
    PhysicalBlocked,
    fit_floor,
    ground_offset,
    normal_angle_deg,
    quaternion_angle_deg,
    rotation_matrix,
    smallest_rotation_to_up,
)
from .scale import (
    METHOD_TIERS,
    RESERVED_METHODS,
    TIERS,
    ScaleClaim,
    ScaleMethodNotEnabled,
    ScaleRefused,
    apply_claim,
    asserted_fixture,
    from_camera_height,
    from_metric_depth,
    from_reference_length,
    make_claim,
    require_metric,
    unknown_scale,
)
from .cloud import (
    FOOTPRINT_K,
    POINT_CAP,
    PhysicalCloud,
    RawCloud,
    ScaledCloud,
    choose_stride,
    floor_of,
    footprint_radius,
    half_pixel_delta,
    physical_cloud,
    unproject_raw,
    unproject_scaled,
)

__all__ = [
    # depth (SPEC 4)
    "CONFIDENCE_MIN",
    "EDGE_REL_MAX",
    "HALF_FLOAT_MAX",
    "RULES",
    "DepthMask",
    "above_half_float_difference",
    "condition_depth",
    # level (SPEC 5.1, 5.2)
    "FLOOR_INLIER_REL",
    "FLOOR_ITERATIONS",
    "FLOOR_MAX_TILT_DEG",
    "FLOOR_MIN_INLIER_FRACTION",
    "FLOOR_REFINE_PASSES",
    "FLOOR_ROWS_FRACTION",
    "FLOOR_SEED",
    "FloorFit",
    "PhysicalBlocked",
    "fit_floor",
    "ground_offset",
    "normal_angle_deg",
    "quaternion_angle_deg",
    "rotation_matrix",
    "smallest_rotation_to_up",
    # scale (SPEC 5.3)
    "METHOD_TIERS",
    "RESERVED_METHODS",
    "TIERS",
    "ScaleClaim",
    "ScaleMethodNotEnabled",
    "ScaleRefused",
    "apply_claim",
    "asserted_fixture",
    "from_camera_height",
    "from_metric_depth",
    "from_reference_length",
    "make_claim",
    "require_metric",
    "unknown_scale",
    # cloud (SPEC 6)
    "FOOTPRINT_K",
    "POINT_CAP",
    "PhysicalCloud",
    "RawCloud",
    "ScaledCloud",
    "choose_stride",
    "floor_of",
    "footprint_radius",
    "half_pixel_delta",
    "physical_cloud",
    "unproject_raw",
    "unproject_scaled",
]
