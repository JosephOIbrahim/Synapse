"""HD1 scale claims (SPEC 5.3; design 8.4). Pure Python and numpy: no hou, no pxr, no network.

A scale is a claim with provenance, never a fact and never a default. These tests
check that no claim refuses metric output, that every enabled method records its
tier and method in the manifest's own vocabulary, that each method recovers
variant C's 0.4 m per unit, and that 1.0 is never assumed. The design's measured
figures ([M]) are printed on ``HD1-METRIC`` lines (run with -rP), never asserted.
"""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import importlib.util
import inspect
import json
import math
from pathlib import Path
import re
import sys

import pytest

np = pytest.importorskip("numpy")

from synapse.worldlabs.atlas_contracts import ContractError, unproject_metric  # noqa: E402
from synapse.worldlabs.physical import cloud as hd1_cloud  # noqa: E402
from synapse.worldlabs.physical import depth as hd1_depth  # noqa: E402
from synapse.worldlabs.physical import level as hd1_level  # noqa: E402
from synapse.worldlabs.physical import scale as hd1_scale  # noqa: E402
from synapse.worldlabs.physical.cloud import (  # noqa: E402
    floor_of,
    physical_cloud,
    unproject_raw,
    unproject_scaled,
)
from synapse.worldlabs.physical.depth import condition_depth  # noqa: E402
from synapse.worldlabs.physical.scale import (  # noqa: E402
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

_REPO = Path(__file__).resolve().parents[1]
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hd1_scene.py"
_SCHEMA = _REPO / "docs" / "intake" / "world_manifest.schema.json"
_PROBE = "tests/fixtures/hd1_scene.py#C"


def _load_fixture():
    """Load tests/fixtures/hd1_scene.py by path (design 2.9); a failed load is unregistered again."""
    mod = sys.modules.get("hd1_scene")
    if mod is None:
        spec = importlib.util.spec_from_file_location("hd1_scene", _FIXTURE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["hd1_scene"] = mod
        loaded = False
        try:
            spec.loader.exec_module(mod)
            loaded = True
        finally:
            if not loaded:
                sys.modules.pop("hd1_scene", None)
    return mod


hd1_scene = _load_fixture()

_GRIDS = [pytest.param((1280, 720), id="1280x720"), pytest.param((160, 90), id="160x90")]
_DESIGN_CAMERA_HEIGHT_SCALE_C = 0.400000000000000   # design 5.1 [M]: 1.5 / 3.750000000000


def _metric(**fields):
    print("HD1-METRIC", json.dumps(fields, sort_keys=True, allow_nan=False))


_CHAIN = {}


def _chain(name, grid):
    """(variant, depth mask, floor fit) for one fixture variant, computed once per module."""
    key = (name, tuple(grid))
    if key not in _CHAIN:
        v = hd1_scene.variant(name, *grid)
        mask = condition_depth(v.depth, v.confidence)
        _CHAIN[key] = (v, mask, floor_of(unproject_raw(v.frame, v.depth, mask.keep)))
    return _CHAIN[key]


def _schema_tiers():
    return json.loads(_SCHEMA.read_text(encoding="utf-8"))["$defs"]["tier"]["enum"]


def _claims_for(name, grid):
    """One claim per enabled method for one variant, built from its truth or its fit."""
    v, _, fit = _chain(name, grid)
    a, b, length = v.truth.reference_pair
    return {
        "asserted:fixture": asserted_fixture(v.truth.metres_per_unit, probe="tests/fixtures/hd1_scene.py#" + name),
        "derived:camera-height": from_camera_height(v.truth.declared_eye_height_m, fit,
                                                     probe="cloud.floor_of on " + v.frame.frame_id),
        "derived:reference-length": from_reference_length(a, b, length, probe="truth.reference_pair"),
    }


# --- design 8.4 ---------------------------------------------------------------------------

def test_no_claim_refuses_metric_output():
    claim = unknown_scale()
    assert claim.value is None and claim.tier == "unknown" and claim.method is None and claim.probe is None
    assert claim.known is False
    assert claim.provenanced_number() == {"value": None, "tier": "unknown", "method": None, "probe": None}
    v, mask, fit = _chain("C", (160, 90))
    with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
        require_metric(claim)
    with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
        apply_claim(v.frame, claim)
    with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
        physical_cloud(v.frame, v.depth, mask.keep, claim, fit)
    with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
        unproject_scaled(v.frame, v.depth, mask.keep)
    with pytest.raises(ContractError, match="^metric scale is unknown$"):
        unproject_metric(v.frame, v.depth.ravel().tolist())
    assert issubclass(ScaleRefused, ContractError) and issubclass(ScaleMethodNotEnabled, ContractError)


_SCALE_WORDS = re.compile(r"scale|metres|meters|mpu|unit", re.IGNORECASE)
_MODULES = {"depth": hd1_depth, "level": hd1_level, "scale": hd1_scale, "cloud": hd1_cloud}


def _is_one(node):
    return isinstance(node, ast.Constant) and type(node.value) in (int, float) and node.value == 1


def test_one_is_never_assumed():
    for name, module in _MODULES.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                args = node.args
                positional = args.posonlyargs + args.args
                pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
                pairs += [(arg, default) for arg, default in zip(args.kwonlyargs, args.kw_defaults)
                          if default is not None]
                for arg, default in pairs:
                    if _SCALE_WORDS.search(arg.arg):
                        assert not _is_one(default), (name, arg.arg)
        if name in ("scale", "cloud"):
            for node in ast.walk(tree):
                if isinstance(node, ast.IfExp):
                    assert not (_is_one(node.body) or _is_one(node.orelse)), (name, node.lineno)
                if isinstance(node, ast.BoolOp):
                    assert not any(_is_one(value) for value in node.values), (name, node.lineno)
        # The runtime defaults too, so a named constant equal to 1 cannot hide a default.
        for function_name, function in inspect.getmembers(module, inspect.isfunction):
            if function.__module__ != module.__name__:
                continue
            for parameter in inspect.signature(function).parameters.values():
                if _SCALE_WORDS.search(parameter.name) and parameter.default is not inspect.Parameter.empty:
                    assert parameter.default != 1, (name, function_name, parameter.name)
    # Variant A's truth is 1.0, and without a claim it refuses exactly as C does.
    for variant in ("A", "C"):
        v, mask, fit = _chain(variant, (160, 90))
        with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
            apply_claim(v.frame, unknown_scale())
        with pytest.raises(ScaleRefused, match="^metric scale is unknown$"):
            physical_cloud(v.frame, v.depth, mask.keep, unknown_scale(), fit)
        with pytest.raises(ScaleRefused):
            require_metric(1.0)


@pytest.mark.parametrize("method", sorted(METHOD_TIERS))
def test_each_method_records_tier_and_method(method):
    schema_tiers = _schema_tiers()
    assert list(TIERS) == schema_tiers
    claim = _claims_for("C", (160, 90))[method]
    number = claim.provenanced_number()
    assert set(number) == {"value", "tier", "method", "probe"}
    assert number["method"] == method and number["tier"] == METHOD_TIERS[method]
    assert number["tier"] in schema_tiers
    assert type(number["value"]) is float and number["value"] > 0.0
    assert isinstance(number["probe"], str) and number["probe"]
    record = claim.as_record()
    json.dumps(record, allow_nan=False)
    assert set(record) == {"value", "tier", "method", "probe", "inputs"}
    assert record["inputs"] and record["inputs"] == dict(claim.inputs)
    via_name = make_claim(method, **{
        "asserted:fixture": {"value": 0.4, "probe": _PROBE},
        "derived:camera-height": {"declared_eye_height_m": 1.5, "floor": _chain("C", (160, 90))[2]},
        "derived:reference-length": {"point_a": (0.0, 0.0, 0.0), "point_b": (2.5, 0.0, 0.0),
                                     "known_length_m": 1.0},
    }[method])
    assert via_name.method == method and via_name.tier == METHOD_TIERS[method]
    _metric(test="method_record", method=method, record=record)


@pytest.mark.parametrize("grid", _GRIDS)
def test_camera_height_scale_recovers_variant_C(grid):
    v, _, fit = _chain("C", grid)
    claim = from_camera_height(v.truth.declared_eye_height_m, fit)
    truth = v.truth.metres_per_unit
    relative = abs(claim.value - truth) / truth
    assert relative <= 1e-12
    assert dict(claim.inputs)["declared_eye_height_m"] == 1.5
    assert dict(claim.inputs)["camera_height_units"] == fit.camera_height
    assert dict(claim.inputs)["floor_seed"] == fit.seed
    _metric(test="scale_camera_height_C", grid=list(grid), value=claim.value, truth=truth,
            error=claim.value - truth, relative_error=relative, camera_height_units=fit.camera_height,
            design_figure_M=_DESIGN_CAMERA_HEIGHT_SCALE_C)


def test_reference_length_scale_recovers_variant_C():
    c = hd1_scene.variant("C", 160, 90)
    a, b, length = c.truth.reference_pair
    claim = from_reference_length(a, b, length)
    assert claim.value == pytest.approx(c.truth.metres_per_unit, rel=1e-12, abs=0.0)
    assert dict(claim.inputs) == {"known_length_m": 1.0, "measured_length_units": math.dist(a, b)}
    _metric(test="scale_reference_length_C", value=claim.value, truth=c.truth.metres_per_unit,
            error=claim.value - c.truth.metres_per_unit, measured_length_units=math.dist(a, b))


@pytest.mark.parametrize("grid", _GRIDS)
def test_scale_claims_on_C_per_method_beside_the_truth(grid):
    """Every enabled method on variant C, each beside the truth 0.4: printed, not judged."""
    v, _, _ = _chain("C", grid)
    truth = v.truth.metres_per_unit
    rows = {}
    for method, claim in _claims_for("C", grid).items():
        assert claim.method == method and claim.known
        rows[method] = {"value": claim.value, "tier": claim.tier, "error": claim.value - truth,
                        "relative_error": (claim.value - truth) / truth, "inputs": dict(claim.inputs)}
    rows["derived:moge2"] = {"value": None, "status": "not enabled (D-HD-05)"}
    _metric(test="scale_claims_C", grid=list(grid), truth=truth, claims=rows)


def test_reserved_moge2_raises_not_enabled():
    assert dict(RESERVED_METHODS) == {"derived:moge2": "D-HD-05"}
    for call in (lambda: make_claim("derived:moge2"),
                 lambda: make_claim("derived:moge2", depth=None),
                 lambda: from_metric_depth(),
                 lambda: from_metric_depth(None, reference=None)):
        with pytest.raises(ScaleMethodNotEnabled) as caught:
            call()
        assert "not enabled" in str(caught.value) and "D-HD-05" in str(caught.value)


def test_unknown_method_is_refused():
    for method in ("vendor:metadata", "derived:moge3", "", None, 1.0, ["derived:moge2"]):
        with pytest.raises(ContractError) as caught:
            make_claim(method)
        assert not isinstance(caught.value, ScaleMethodNotEnabled)
        assert str(caught.value) == "unknown scale method"


def test_bad_inputs_are_refused():
    _, _, fit = _chain("C", (160, 90))
    secret = 123.456789

    def refused(call, kind=ContractError):
        with pytest.raises(kind) as caught:
            call()
        assert "123.45" not in str(caught.value) and "nan" not in str(caught.value).lower()
        return caught.value

    for eye in (0, -1.0, float("nan"), float("inf"), True, None, "1.5", -secret):
        refused(lambda: from_camera_height(eye, fit))
    refused(lambda: from_camera_height(1.5, replace(fit, status="UNKNOWN")), ScaleRefused)
    refused(lambda: from_camera_height(1.5, replace(fit, camera_height=-secret)), ScaleRefused)
    refused(lambda: from_camera_height(1.5, replace(fit, camera_height=0.0)), ScaleRefused)
    refused(lambda: from_camera_height(1.5, replace(fit, camera_height=float("nan"))), ScaleRefused)
    refused(lambda: from_camera_height(1.5, {"status": "SUCCESS", "camera_height": 3.75}))
    refused(lambda: from_reference_length((1.0, 2.0, secret), (1.0, 2.0, secret), 1.0), ScaleRefused)
    for point in ((0.0, float("nan"), 0.0), (0.0, float("inf"), 0.0), (0.0, 0.0), (True, 0.0, 0.0), None):
        refused(lambda: from_reference_length(point, (1.0, 0.0, 0.0), 1.0))
    for length in (0.0, -secret, float("nan"), True, None):
        refused(lambda: from_reference_length((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), length))
    refused(lambda: from_reference_length((-1e308, 0.0, 0.0), (1e308, 0.0, 0.0), 1.0))
    for value in (0, 0.0, -secret, float("nan"), float("inf"), True, None, "0.4"):
        refused(lambda: asserted_fixture(value, probe=_PROBE))
    for probe in (None, "", 7, "x" * 257):
        refused(lambda: asserted_fixture(0.4, probe=probe))


def test_scale_applies_to_depth_and_camera_position_together():
    a, mask_a, _ = _chain("A", (160, 90))
    c, mask_c, _ = _chain("C", (160, 90))
    assert np.array_equal(mask_a.keep, mask_c.keep)
    scaled_a = unproject_scaled(apply_claim(a.frame, asserted_fixture(1.0, probe="truth A")), a.depth, mask_a.keep)
    scaled_c = unproject_scaled(apply_claim(c.frame, asserted_fixture(0.4, probe=_PROBE)), c.depth, mask_c.keep)
    assert np.array_equal(scaled_a.rows, scaled_c.rows) and np.array_equal(scaled_a.cols, scaled_c.cols)
    difference = float(np.max(np.abs(scaled_c.points_m - scaled_a.points_m)))
    camera = max(abs(x - y) for x, y in zip(scaled_c.camera_position_m, scaled_a.camera_position_m))
    depth = float(np.max(np.abs(scaled_c.depth_m - scaled_a.depth_m)))
    assert difference <= 1e-12 and camera <= 1e-12 and depth <= 1e-12
    # Review RVM-09 (2026-11-15): a check computed from scaled_c itself held whenever the line above
    # held, so it could never fail on its own; it is gone. The line above is the guard.
    _metric(test="scale_applies_together", max_point_difference_m=difference,
            max_camera_difference_m=camera, max_depth_difference_m=depth, points=int(scaled_a.rows.size))


def test_existing_frame_scale_is_never_overwritten():
    c = hd1_scene.variant("C", 160, 90)
    scaled = apply_claim(c.frame, asserted_fixture(0.4, probe=_PROBE))
    assert scaled.metres_per_unit == 0.4 and type(scaled.metres_per_unit) is float
    assert c.frame.metres_per_unit is None
    for claim in (asserted_fixture(0.4, probe=_PROBE), asserted_fixture(0.5, probe=_PROBE), unknown_scale()):
        with pytest.raises(ScaleRefused, match="never overwrites"):
            apply_claim(scaled, claim)
    assert scaled.metres_per_unit == 0.4
    with pytest.raises(ContractError):
        apply_claim(None, asserted_fixture(0.4, probe=_PROBE))


def test_claim_rejects_inconsistent_states():
    bad = [
        dict(value=0.4, tier="unknown", method=None, probe=None),
        dict(value=None, tier="unknown", method="asserted:fixture", probe=None),
        dict(value=0.4, tier="derived", method="asserted:fixture", probe=None),
        dict(value=0.4, tier="manual", method="derived:camera-height", probe=None),
        dict(value=0.4, tier="vendor", method=None, probe=None),
        dict(value=0.4, tier="probed", method="derived:camera-height", probe=None),
        dict(value=None, tier="derived", method="derived:camera-height", probe=None),
        dict(value=0.4, tier="SYNTHETIC", method="asserted:fixture", probe=None),
        dict(value=0.4, tier="derived", method="derived:unlisted", probe=None),
        dict(value=-0.4, tier="manual", method="asserted:fixture", probe=None),
        dict(value=True, tier="manual", method="asserted:fixture", probe=None),
        dict(value=0.4, tier="manual", method="asserted:fixture", probe=""),
        dict(value=0.4, tier="manual", method="asserted:fixture", probe=None, inputs=(("a", float("nan")),)),
        dict(value=0.4, tier="manual", method="asserted:fixture", probe=None, inputs=(("a", 1.0), ("a", 2.0))),
    ]
    for fields in bad:
        with pytest.raises(ContractError):
            ScaleClaim(**fields)
    with pytest.raises(ScaleMethodNotEnabled):
        ScaleClaim(0.4, "derived", "derived:moge2", None)
    good = ScaleClaim(np.float64(0.4), "manual", "asserted:fixture", None)
    assert type(good.value) is float and good.value == 0.4
    with pytest.raises(FrozenInstanceError):
        good.value = 1.0
