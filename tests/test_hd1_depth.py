"""HD1 depth conditioning (SPEC 4; design 8.2): each rule drops what it should.

Pure numpy: no Houdini, no OpenUSD and no network, so this runs on CI. The
rule tests build their own small arrays, with answers known by construction.
The variant tests (D's corruptions, clean A's edges and the HD-05 count) read
the analytic fixture tests/fixtures/hd1_scene.py. It is loaded by path inside
those tests only, so this module collects without it; a missing or broken
fixture fails those tests instead of skipping them.

Figures from design.md's in-memory re-derivation are printed beside the
measured value on HD1-METRIC lines and are never asserted: assertions come
from closed forms or from the fixture's truth record. Run with -rP to see them.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import math
from pathlib import Path
import sys

import pytest

np = pytest.importorskip("numpy")

from synapse.worldlabs.atlas_contracts import ContractError, mask_depth  # noqa: E402
from synapse.worldlabs.physical import depth as hd1_depth  # noqa: E402
from synapse.worldlabs.physical.depth import (  # noqa: E402
    CONFIDENCE_MIN,
    EDGE_REL_MAX,
    HALF_FLOAT_MAX,
    RULES,
    DepthMask,
    above_half_float_difference,
    condition_depth,
)

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hd1_scene.py"
_GRIDS = [pytest.param((1280, 720), id="1280x720"), pytest.param((160, 90), id="160x90")]

_DEPTH_ARRAY = "^decoded depth must be a non-empty 2-D array$"
_CONFIDENCE_ARRAY = "^decoded confidence must be a non-empty 2-D array$"
_CONFIDENCE_GRID = "^confidence must match the depth grid$"
_CONFIDENCE_RANGE = r"^confidence must be finite and normalised to \[0, 1\]$"
_CONFIDENCE_MIN_RANGE = r"^confidence_min must be a finite number in \[0, 1\]$"
_EDGE_REL_RANGE = "^edge_rel_max must be a finite number above 0$"

# design.md [M] figures (an in-memory re-derivation, 2026-11-14). Printed beside
# the measured value, never asserted: a difference is a finding, not an edit.
_DESIGN_D = {
    (1280, 720): {"flagged": {"invalid": 2048, "low_confidence": 5144, "edge": 2409},
                  "dropped": {"invalid": 2048, "low_confidence": 5144, "edge": 68},
                  "kept": 914340, "mixed": 779, "low_confidence_band": 5144},
    (160, 90): {"flagged": {"invalid": 32, "low_confidence": 664, "edge": 297},
                "dropped": {"invalid": 32, "low_confidence": 664, "edge": 0},
                "kept": 13704, "mixed": 97, "low_confidence_band": 664},
}
_DESIGN_CLEAN_A_EDGES = {(1280, 720): {"total": 1636, "floor": 456, "box": 817, "wall": 363},
                         (160, 90): {"total": 204, "floor": 58, "box": 101, "wall": 45}}
_DESIGN_HD05 = {(160, 90): 16, (1280, 720): 1024}


def _metric(**fields):
    print("HD1-METRIC", json.dumps(fields, sort_keys=True, allow_nan=False))


def _load_fixture():
    """Load tests/fixtures/hd1_scene.py by path, once per session (design 2.9).

    The module is registered before it executes, because dataclasses with
    postponed annotations look it up in sys.modules. A failed load is
    unregistered again, so no half-built module lingers for later tests.
    """
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


@pytest.fixture(scope="module")
def hd1_scene():
    """The analytic fixture, loaded only by the variant tests that ask for it."""
    return _load_fixture()


def _flat(mask_row):
    return set(int(i) for i in np.flatnonzero(mask_row))


def _label_boundary(labels):
    """True where a pixel has a 4-neighbour with a different truth label."""
    lab = np.asarray(labels)
    out = np.zeros(lab.shape, dtype=bool)
    step = lab[:-1, :] != lab[1:, :]
    out[:-1, :] |= step
    out[1:, :] |= step
    step = lab[:, :-1] != lab[:, 1:]
    out[:, :-1] |= step
    out[:, 1:] |= step
    return out


def _reference_rules(z, c, confidence_min, edge_rel_max):
    """The same three rules as a plain per-pixel loop over Python floats.

    A second implementation, written from SPEC 4 and design 3.1 and not from
    depth.py, with the attribution order spelled out by hand.
    """
    rows, cols = len(z), len(z[0])

    def valid(v):
        return math.isfinite(v) and v > 0.0 and v <= 65504.0

    invalid = [[not valid(z[r][k]) for k in range(cols)] for r in range(rows)]
    low = [[c is not None and c[r][k] < confidence_min for k in range(cols)] for r in range(rows)]
    edge = [[False] * cols for _ in range(rows)]
    for r in range(rows):
        for k in range(cols):
            for rr, kk in ((r + 1, k), (r, k + 1)):
                if rr < rows and kk < cols and not invalid[r][k] and not invalid[rr][kk]:
                    a, b = z[r][k], z[rr][kk]
                    if abs(a - b) > edge_rel_max * min(a, b):
                        edge[r][k] = True
                        edge[rr][kk] = True
    cells = [(r, k) for r in range(rows) for k in range(cols)]
    flagged = {"invalid": sum(invalid[r][k] for r, k in cells),
               "low_confidence": sum(low[r][k] for r, k in cells),
               "edge": sum(edge[r][k] for r, k in cells)}
    dropped = {"invalid": flagged["invalid"],
               "low_confidence": sum(low[r][k] and not invalid[r][k] for r, k in cells),
               "edge": sum(edge[r][k] and not invalid[r][k] and not low[r][k] for r, k in cells)}
    keep = [[not (invalid[r][k] or low[r][k] or edge[r][k]) for k in range(cols)] for r in range(rows)]
    return {"invalid": invalid, "low_confidence": low, "edge": edge, "keep": keep,
            "flagged": flagged, "dropped": dropped}


# --- design 8.2, tests 1-7: the rules on arrays built here -------------------------------

def test_validity_rule_drops_nonfinite_nonpositive_and_above_half_float():
    row = np.array([[1.0, np.nan, np.inf, -np.inf, 0.0, -1.0, 65504.0,
                     np.nextafter(65504.0, np.inf), 1e5, 2.0]])
    mask = condition_depth(row)
    assert HALF_FLOAT_MAX == 65504.0
    assert _flat(mask.invalid[0]) == {1, 2, 3, 4, 5, 7, 8}
    assert mask.flagged["invalid"] == 7
    assert mask.keep[0, 6], "65504.0 is at the ceiling, so it is valid and kept"
    # Every valid pixel here sits between invalid ones, so no edge pair exists.
    assert _flat(mask.keep[0]) == {0, 6, 9}
    assert mask.flagged == {"invalid": 7, "low_confidence": 0, "edge": 0}
    assert (mask.kept, mask.total) == (3, 10)
    assert condition_depth(np.array([[-0.0, 1.0]])).invalid[0].tolist() == [True, False]
    _metric(test="validity_row", flagged=mask.flagged, dropped=mask.dropped, kept=mask.kept,
            total=mask.total)


def test_confidence_rule_drops_below_threshold_and_is_optional():
    depth = np.full((3, 4), 2.0)
    without = condition_depth(depth)
    ones = condition_depth(depth, np.ones((3, 4)))
    assert without.confidence_supplied is False and ones.confidence_supplied is True
    assert without.flagged["low_confidence"] == 0 and not without.low_confidence.any()
    assert np.array_equal(without.keep, ones.keep) and without.keep.all()

    confidence = np.ones((3, 4))
    confidence[0, 0] = 0.5
    confidence[1, 1] = np.nextafter(0.5, 0.0)
    mask = condition_depth(depth, confidence)
    assert CONFIDENCE_MIN == 0.5
    assert mask.keep[0, 0], "0.5 is not below the threshold, so it is kept"
    assert not mask.keep[1, 1] and mask.low_confidence[1, 1]
    assert mask.flagged["low_confidence"] == 1 and mask.dropped["low_confidence"] == 1

    custom = np.full((3, 4), 0.7)
    custom[2, 3] = 0.69
    honoured = condition_depth(depth, custom, confidence_min=0.7)
    assert honoured.thresholds["confidence_min"] == 0.7
    assert _flat(honoured.low_confidence.ravel()) == {11}
    assert condition_depth(depth, custom).flagged["low_confidence"] == 0


@pytest.mark.parametrize("case", ["nan", "inf", "above-1", "negative", "uint8-255", "shape"])
def test_confidence_must_be_finite_and_normalised(case):
    depth = np.full((2, 3), 2.0)
    confidence = np.ones((2, 3))
    pattern = _CONFIDENCE_RANGE
    if case == "nan":
        confidence[1, 2] = np.nan
    elif case == "inf":
        confidence[1, 2] = np.inf
    elif case == "above-1":
        confidence[1, 2] = 1.5
    elif case == "negative":
        confidence[1, 2] = -0.1
    elif case == "uint8-255":
        confidence = np.full((2, 3), 255, dtype=np.uint8)
    else:
        confidence = np.ones((3, 2))
        pattern = _CONFIDENCE_GRID
    # An exact, fixed message: it cannot echo the offending value.
    with pytest.raises(ContractError, match=pattern):
        condition_depth(depth, confidence)


def test_edge_rule_is_a_strict_relative_jump():
    def edges(z, rel=None):
        z = np.asarray(z, dtype=np.float64)
        mask = condition_depth(z) if rel is None else condition_depth(z, edge_rel_max=rel)
        return mask.edge

    exact = 0.0625                       # binary-exact, so the boundary is exact too
    above = np.nextafter(1.0625, np.inf)
    for shape in ((1, 2), (2, 1)):       # horizontal and vertical pairs
        assert not edges(np.reshape([1.0, 1.0625], shape), exact).any()
        assert not edges(np.reshape([1.0625, 1.0], shape), exact).any()
        assert edges(np.reshape([1.0, above], shape), exact).all()
        assert edges(np.reshape([above, 1.0], shape), exact).all()
        assert edges(np.reshape([2.0, 3.0], shape), exact).all()
    ramp = 1.04 ** np.arange(40.0)       # 4% steps, under the default 5%
    assert EDGE_REL_MAX == 0.05
    assert not edges(ramp.reshape(1, -1)).any()
    assert not edges(ramp.reshape(-1, 1)).any()


def test_edge_rule_ignores_invalid_neighbours_and_never_wraps():
    assert not condition_depth(np.array([[2.0, np.nan, 2.0]])).edge.any()
    assert not condition_depth(np.array([[2.0, np.nan, 3.0]])).edge.any()
    assert not condition_depth(np.array([[2.0, 1e5]])).edge.any()
    # An invalid neighbour does not shield either: the valid pair still jumps.
    shielded = condition_depth(np.array([[np.nan, 2.0, 3.0]]))
    assert shielded.edge[0].tolist() == [False, True, True]

    ramp = 1.04 ** np.arange(20.0)       # last / first is about 2.1: a wrap would jump
    assert not condition_depth(ramp.reshape(1, -1)).edge.any()
    assert not condition_depth(ramp.reshape(-1, 1)).edge.any()
    plane = np.outer(1.02 ** np.arange(20.0), 1.02 ** np.arange(30.0))
    assert not condition_depth(plane).edge.any()

    # A low-confidence neighbour still counts for the edge rule.
    mask = condition_depth(np.array([[2.0, 3.0]]), np.array([[1.0, 0.0]]))
    assert mask.edge.all()
    assert mask.low_confidence[0].tolist() == [False, True]
    assert mask.dropped == {"invalid": 0, "low_confidence": 1, "edge": 1}


def test_nothing_is_filled_or_interpolated():
    depth = np.array([[1.0, np.nan, 3.0, 2.0], [np.inf, 2.0, 1e5, 2.1]])
    confidence = np.array([[1.0, 0.2, 1.0, 1.0], [1.0, 1.0, 0.0, 1.0]])
    depth_before, confidence_before = depth.copy(), confidence.copy()
    mask = condition_depth(depth, confidence)
    assert np.array_equal(depth, depth_before, equal_nan=True)
    assert np.array_equal(confidence, confidence_before)

    frozen_depth, frozen_confidence = depth_before.copy(), confidence_before.copy()
    frozen_depth.setflags(write=False)
    frozen_confidence.setflags(write=False)
    again = condition_depth(frozen_depth, frozen_confidence)
    assert np.array_equal(again.keep, mask.keep)

    names = {field.name for field in dataclasses.fields(DepthMask)}
    assert not any("depth" in name for name in names)
    assert not any("depth" in key for key in mask.as_dict())
    for array in (mask.keep, mask.invalid, mask.low_confidence, mask.edge):
        assert array.dtype == np.bool_ and array.shape == depth.shape
        assert not array.flags.writeable
        assert not np.shares_memory(array, depth)
    with pytest.raises(ValueError):
        mask.keep[0, 0] = True


def test_counts_are_independent_and_sequential():
    depth = np.array([[2.0, 2.0, 2.0, 2.0],
                      [2.0, np.nan, 3.0, 2.0],
                      [2.0, 2.0, 2.0, 2.0]])
    confidence = np.array([[1.0, 1.0, 1.0, 1.0],
                           [1.0, 0.0, 0.0, 1.0],
                           [1.0, 1.0, 1.0, 0.0]])
    mask = condition_depth(depth, confidence)
    assert RULES == ("invalid", "low_confidence", "edge")
    assert tuple(mask.flagged) == RULES and tuple(mask.dropped) == RULES
    # By construction: (1,1) is invalid and low; (1,2) is low and an edge; (2,3) is low;
    # the 3.0 at (1,2) jumps against (0,2), (2,2) and (1,3), and not across the NaN.
    assert mask.flagged == {"invalid": 1, "low_confidence": 3, "edge": 4}
    assert mask.dropped == {"invalid": 1, "low_confidence": 2, "edge": 3}
    assert (mask.kept, mask.total) == (6, 12)

    assert sum(mask.dropped.values()) == mask.total - mask.kept
    for rule in RULES:
        assert mask.flagged[rule] >= mask.dropped[rule]
        assert type(mask.flagged[rule]) is int and type(mask.dropped[rule]) is int
    assert type(mask.kept) is int and type(mask.total) is int

    # The attribution order is the RULES order, recomputed from the independent flags.
    claimed = np.zeros(depth.shape, dtype=bool)
    for rule in RULES:
        flag = getattr(mask, rule)
        assert mask.dropped[rule] == int(np.count_nonzero(flag & ~claimed))
        assert mask.flagged[rule] == int(np.count_nonzero(flag))
        claimed |= flag
    assert np.array_equal(mask.keep, ~claimed)
    _metric(test="counts_grid", flagged=mask.flagged, dropped=mask.dropped, kept=mask.kept,
            total=mask.total)


# --- additions beyond design 8.2, also on arrays built here ------------------------------

_BAD_DEPTH = [
    pytest.param(np.ones(4), id="1-D"),
    pytest.param(np.ones((2, 2, 1)), id="3-D"),
    pytest.param(np.ones((0, 3)), id="no-rows"),
    pytest.param(np.ones((3, 0)), id="no-columns"),
    pytest.param(np.float64(2.0), id="0-D"),
    pytest.param(np.ones((2, 2), dtype=bool), id="bool"),
    pytest.param(np.ones((2, 2), dtype=complex), id="complex"),
    pytest.param([[1.0, None]], id="object"),
    pytest.param([["1.0", "2.0"]], id="text"),
    pytest.param([[1.0, 2.0], [3.0]], id="ragged"),
    pytest.param(None, id="None"),
]


@pytest.mark.parametrize("value", _BAD_DEPTH)
def test_depth_must_be_a_non_empty_2d_real_array(value):
    with pytest.raises(ContractError, match=_DEPTH_ARRAY):
        condition_depth(value)
    with pytest.raises(ContractError, match=_DEPTH_ARRAY):
        above_half_float_difference(value)


@pytest.mark.parametrize("value", _BAD_DEPTH[:9])
def test_supplied_confidence_must_be_a_non_empty_2d_real_array(value):
    with pytest.raises(ContractError, match=_CONFIDENCE_ARRAY):
        condition_depth(np.full((2, 2), 2.0), value)


def test_any_real_dtype_is_read_as_float64():
    base = np.array([[2.0, 2.0], [2.0, 3.0]])
    reference = condition_depth(base)
    assert reference.flagged["edge"] == 3
    for value in ([[2, 2], [2, 3]], base.astype(np.int32), base.astype(np.uint16),
                  base.astype(np.float32), base.astype(np.float16)):
        mask = condition_depth(value)
        assert np.array_equal(mask.keep, reference.keep)
        assert mask.flagged == reference.flagged
    strided = np.full((6, 8), 2.0)[::2, ::3]
    assert condition_depth(strided).keep.all()
    eight_bit = condition_depth(base, np.array([[1, 0], [1, 1]], dtype=np.uint8))
    assert eight_bit.low_confidence.tolist() == [[False, True], [False, False]]


@pytest.mark.parametrize("kwargs, pattern", [
    pytest.param({"confidence_min": float("nan")}, _CONFIDENCE_MIN_RANGE, id="cmin-nan"),
    pytest.param({"confidence_min": float("inf")}, _CONFIDENCE_MIN_RANGE, id="cmin-inf"),
    pytest.param({"confidence_min": -0.1}, _CONFIDENCE_MIN_RANGE, id="cmin-negative"),
    pytest.param({"confidence_min": 1.5}, _CONFIDENCE_MIN_RANGE, id="cmin-above-1"),
    pytest.param({"confidence_min": True}, _CONFIDENCE_MIN_RANGE, id="cmin-bool"),
    pytest.param({"confidence_min": "0.5"}, _CONFIDENCE_MIN_RANGE, id="cmin-text"),
    pytest.param({"confidence_min": None}, _CONFIDENCE_MIN_RANGE, id="cmin-None"),
    pytest.param({"edge_rel_max": 0.0}, _EDGE_REL_RANGE, id="rel-zero"),
    pytest.param({"edge_rel_max": -0.05}, _EDGE_REL_RANGE, id="rel-negative"),
    pytest.param({"edge_rel_max": float("nan")}, _EDGE_REL_RANGE, id="rel-nan"),
    pytest.param({"edge_rel_max": float("inf")}, _EDGE_REL_RANGE, id="rel-inf"),
    pytest.param({"edge_rel_max": True}, _EDGE_REL_RANGE, id="rel-bool"),
    pytest.param({"edge_rel_max": None}, _EDGE_REL_RANGE, id="rel-None"),
])
def test_thresholds_must_be_finite_and_in_range(kwargs, pattern):
    with pytest.raises(ContractError, match=pattern):
        condition_depth(np.full((2, 2), 2.0), **kwargs)


def test_threshold_bounds_and_numpy_scalars_are_accepted():
    depth = np.full((2, 2), 2.0)
    confidence = np.array([[0.0, 0.5], [0.99, 1.0]])
    assert condition_depth(depth, confidence, confidence_min=0.0).flagged["low_confidence"] == 0
    assert condition_depth(depth, confidence, confidence_min=1).flagged["low_confidence"] == 3
    mask = condition_depth(depth, confidence, confidence_min=np.float64(0.5),
                           edge_rel_max=np.float32(0.0625))
    assert mask.thresholds == {"half_float_max": 65504.0, "confidence_min": 0.5, "edge_rel_max": 0.0625}
    assert all(type(value) is float for value in mask.thresholds.values())


@pytest.mark.parametrize("settings", [
    pytest.param({"confidence": True}, id="defaults"),
    pytest.param({"confidence": False}, id="no-confidence"),
    pytest.param({"confidence": True, "confidence_min": 0.25, "edge_rel_max": 0.07}, id="custom"),
])
def test_rules_match_a_plain_loop_reference(settings):
    rng = np.random.default_rng(20261115)
    # Neighbours differ by up to 9%, so each threshold splits the pairs into
    # jumps and non-jumps instead of flagging nearly every pixel.
    depth = rng.uniform(1.0, 1.09, size=(17, 23))
    depth[3, 4], depth[5, 6], depth[7, 8] = np.nan, np.inf, -np.inf
    depth[9, 10], depth[11, 12], depth[13, 14] = 0.0, -2.0, 1e5
    depth[2, 20], depth[15, 1] = np.nextafter(65504.0, np.inf), 65504.0
    confidence = rng.uniform(0.0, 1.0, size=(17, 23))
    confidence[0, :] = 0.5
    cmin = settings.get("confidence_min", CONFIDENCE_MIN)
    rel = settings.get("edge_rel_max", EDGE_REL_MAX)
    supplied = confidence if settings["confidence"] else None

    mask = condition_depth(depth, supplied, confidence_min=cmin, edge_rel_max=rel)
    ref = _reference_rules(depth.tolist(), None if supplied is None else supplied.tolist(), cmin, rel)
    for name in ("invalid", "low_confidence", "edge", "keep"):
        assert np.array_equal(getattr(mask, name), np.array(ref[name], dtype=bool)), name
    assert mask.flagged == ref["flagged"] and mask.dropped == ref["dropped"]
    assert mask.kept == sum(sum(row) for row in ref["keep"])
    _metric(test="loop_reference", settings=settings, flagged=mask.flagged,
            dropped=mask.dropped, kept=mask.kept, total=mask.total)


def test_as_dict_is_json_safe_and_carries_no_arrays():
    depth = np.array([[2.0, np.nan, 2.0], [2.0, 3.0, 2.0]])
    mask = condition_depth(depth, np.array([[1.0, 1.0, 0.1], [1.0, 1.0, 1.0]]))
    record = mask.as_dict()
    json.dumps(record, allow_nan=False)
    assert set(record) == {"status", "reason", "rules", "shape", "flagged", "dropped", "kept",
                           "total", "confidence_supplied", "thresholds"}
    assert record["status"] == "SUCCESS" and record["reason"] is None
    assert record["rules"] == list(RULES) and record["shape"] == [2, 3]
    assert record["flagged"] == mask.flagged and record["dropped"] == mask.dropped
    assert record["flagged"] is not mask.flagged
    assert record["confidence_supplied"] is True
    assert record["thresholds"] == {"half_float_max": HALF_FLOAT_MAX,
                                    "confidence_min": CONFIDENCE_MIN,
                                    "edge_rel_max": EDGE_REL_MAX}


def test_half_float_ceiling_difference_on_a_synthetic_row():
    row = np.array([[1.0, np.nan, np.inf, -np.inf, 0.0, -1.0, 65504.0,
                     np.nextafter(65504.0, np.inf), 1e5, 2.0]])
    contract_kept = sum(value is not None for value in mask_depth(row.ravel().tolist()))
    record = above_half_float_difference(row)
    json.dumps(record, allow_nan=False)
    assert set(record) == {"claim", "status", "reason", "half_float_max", "total", "contract_valid",
                           "hd1_valid", "kept_by_contract_dropped_by_hd1",
                           "kept_by_hd1_dropped_by_contract", "resolved"}
    assert (record["claim"], record["status"], record["resolved"]) == ("HD-05", "SUCCESS", False)
    # Closed form from the row: the contract keeps 0, 6, 7, 8 and 9; HD1 keeps 0, 6 and 9.
    assert contract_kept == 5
    assert record["contract_valid"] == contract_kept
    assert record["hd1_valid"] == 3
    assert record["hd1_valid"] == record["total"] - condition_depth(row).flagged["invalid"]
    assert record["kept_by_contract_dropped_by_hd1"] == 2
    assert record["kept_by_hd1_dropped_by_contract"] == 0
    _metric(test="ceiling_row", record=record)


def test_numpy_missing_reports_blocked_not_a_crash(monkeypatch):
    monkeypatch.setattr(hd1_depth, "NUMPY_AVAILABLE", False)
    monkeypatch.setattr(hd1_depth, "np", None)
    mask = hd1_depth.condition_depth([[1.0, 2.0]], [[1.0, 1.0]])
    assert mask.status == "BLOCKED" and "numpy" in mask.reason
    for name in ("keep", "invalid", "low_confidence", "edge", "flagged", "dropped", "kept", "total"):
        assert getattr(mask, name) is None, name
    assert mask.confidence_supplied is True
    record = mask.as_dict()
    json.dumps(record, allow_nan=False)
    assert record["status"] == "BLOCKED" and record["shape"] is None and record["kept"] is None

    hd05 = hd1_depth.above_half_float_difference([[1.0, 1e5]])
    json.dumps(hd05, allow_nan=False)
    assert hd05["status"] == "BLOCKED" and "numpy" in hd05["reason"]
    for key in ("total", "contract_valid", "hd1_valid", "kept_by_contract_dropped_by_hd1",
                "kept_by_hd1_dropped_by_contract"):
        assert hd05[key] is None, key
    # Bad thresholds still refuse: that check needs no numpy.
    with pytest.raises(ContractError, match=_EDGE_REL_RANGE):
        hd1_depth.condition_depth([[1.0]], edge_rel_max=float("nan"))


# --- design 8.2, tests 8-10: the analytic fixture (variants A and D) --------------------

@pytest.mark.parametrize("grid", _GRIDS)
def test_variant_D_each_rule_drops_what_it_should(hd1_scene, grid):
    variant = hd1_scene.variant("D", *grid)
    corruption = variant.truth.corruption
    mask = condition_depth(variant.depth, variant.confidence)
    assert np.array_equal(mask.invalid, corruption["nan"] | corruption["above_half_max"])
    assert np.array_equal(mask.low_confidence, corruption["low_confidence"])
    assert not (corruption["mixed"] & ~mask.edge).any(), "every mixed pixel is an edge"
    corrupted = (corruption["nan"] | corruption["above_half_max"] | corruption["mixed"]
                 | corruption["low_confidence"])
    assert not (mask.keep & corrupted).any()
    assert sum(mask.dropped.values()) == mask.total - mask.kept
    _metric(test="variant_D_rules", grid=list(grid),
            measured={"flagged": mask.flagged, "dropped": mask.dropped, "kept": mask.kept,
                      "mixed": int(corruption["mixed"].sum()),
                      "mixed_inside_low_confidence": int((corruption["mixed"]
                                                          & corruption["low_confidence"]).sum()),
                      "mixed_flagged_edge": int((corruption["mixed"] & mask.edge).sum()),
                      "low_confidence_band": int(corruption["low_confidence"].sum())},
            design_figure_M=_DESIGN_D[tuple(grid)])


@pytest.mark.parametrize("grid", _GRIDS)
def test_clean_A_edge_flags_sit_only_on_true_discontinuities(hd1_scene, grid):
    variant = hd1_scene.variant("A", *grid)
    mask = condition_depth(variant.depth, variant.confidence)
    boundary = _label_boundary(variant.labels)
    assert not (mask.edge & ~boundary).any(), "an edge flag away from any label boundary"
    labels = hd1_scene.LABELS
    box = np.isin(variant.labels, [labels["box_top"], labels["box_front"], labels["box_side"]])
    _metric(test="clean_A_edges", grid=list(grid),
            measured={"total": int(mask.edge.sum()),
                      "floor": int((mask.edge & (variant.labels == labels["floor"])).sum()),
                      "box": int((mask.edge & box).sum()),
                      "wall": int((mask.edge & (variant.labels == labels["wall"])).sum()),
                      "flagged": mask.flagged, "kept": mask.kept},
            design_figure_M=_DESIGN_CLEAN_A_EDGES[tuple(grid)])


def test_hd05_contract_keeps_what_hd1_drops(hd1_scene):
    small = hd1_scene.variant("D", 160, 90)
    above_small = int(small.truth.corruption["above_half_max"].sum())
    contract_count = sum(value is not None for value in mask_depth(small.depth.ravel().tolist()))
    mask = condition_depth(small.depth, small.confidence)
    hd1_count = mask.total - mask.flagged["invalid"]
    assert contract_count - hd1_count == above_small
    record_small = above_half_float_difference(small.depth)
    assert record_small["contract_valid"] == contract_count
    assert record_small["hd1_valid"] == hd1_count
    assert record_small["kept_by_contract_dropped_by_hd1"] == above_small
    assert record_small["kept_by_hd1_dropped_by_contract"] == 0

    large = hd1_scene.variant("D", 1280, 720)
    record_large = above_half_float_difference(large.depth)
    above_large = int(large.truth.corruption["above_half_max"].sum())
    assert record_large["kept_by_contract_dropped_by_hd1"] == above_large
    assert record_large["kept_by_hd1_dropped_by_contract"] == 0
    _metric(test="hd05_variant_D", grid=[160, 90], measured=record_small,
            truth_above_half_max=above_small, design_figure_M=_DESIGN_HD05[(160, 90)])
    _metric(test="hd05_variant_D", grid=[1280, 720], measured=record_large,
            truth_above_half_max=above_large, design_figure_M=_DESIGN_HD05[(1280, 720)])
