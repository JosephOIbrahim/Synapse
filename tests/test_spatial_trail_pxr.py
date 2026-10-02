"""The trail's generated code, executed against a real USD stage (D6).

``synapse.spatial.path.trail_code`` writes the Python Script LOP's code. Here
that code runs as the LOP would run it, with ``hou.pwd().editableStage()``
standing in for the node's stage, and the prim it authors is read back. Needs
OpenUSD, so it is ``needs_houdini`` on stock CI runners (tests/conftest.py).
"""
from __future__ import annotations

import math
import os
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("pxr")
np = pytest.importorskip("numpy")

from pxr import Usd, UsdGeom  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.spatial import path as sp  # noqa: E402
from test_spatial_path import FRAMES, _demo_arc  # noqa: E402


def _run(code):
    stage = Usd.Stage.CreateInMemory()
    fake_hou = SimpleNamespace(pwd=lambda: SimpleNamespace(editableStage=lambda: stage))
    exec(compile(code, "<trail>", "exec"), {"hou": fake_hou})
    return stage


def test_the_trail_is_one_linear_curve_through_every_sample_plus_aim_ticks():
    cam = sp.camera_frames(_demo_arc())
    stage = _run(sp.trail_code("/guides/demo_cam_path", FRAMES, cam, camera="/cameras/demo_cam"))
    prim = stage.GetPrimAtPath("/guides/demo_cam_path")
    assert prim.IsValid() and prim.GetTypeName() == "BasisCurves"
    assert stage.GetPrimAtPath("/guides").GetTypeName() == "Scope"
    curves = UsdGeom.BasisCurves(prim)
    counts = list(curves.GetCurveVertexCountsAttr().Get())
    assert counts[0] == 120 and counts[1:] == [2] * 12        # a tick every 10th frame
    pts = np.asarray(curves.GetPointsAttr().Get(), dtype=float)
    assert len(pts) == sum(counts)
    assert np.allclose(pts[:120], cam["position"], atol=1e-4)
    assert curves.GetTypeAttr().Get() == UsdGeom.Tokens.linear
    assert UsdGeom.Imageable(prim).GetPurposeAttr().Get() == UsdGeom.Tokens.proxy


def test_the_trail_carries_its_frames_and_a_first_to_last_colour_ramp():
    cam = sp.camera_frames(_demo_arc())
    stage = _run(sp.trail_code("/guides/p", FRAMES, cam))
    curves = UsdGeom.BasisCurves(stage.GetPrimAtPath("/guides/p"))
    frames = list(UsdGeom.PrimvarsAPI(curves.GetPrim()).GetPrimvar("camera_frame").Get())
    assert frames[0] == 1.0 and frames[119] == 120.0
    colours = curves.GetDisplayColorPrimvar().Get()
    assert len(colours) == len(frames)
    assert tuple(round(c, 3) for c in colours[0]) == sp.TRAIL_START_RGB
    assert tuple(round(c, 3) for c in colours[119]) == sp.TRAIL_END_RGB


def test_the_trail_has_an_extent_and_writes_no_custom_data():
    cam = sp.camera_frames(_demo_arc())
    stage = _run(sp.trail_code("/guides/p", FRAMES, cam))
    prim = stage.GetPrimAtPath("/guides/p")
    extent = UsdGeom.BasisCurves(prim).GetExtentAttr().Get()
    pts = np.asarray(UsdGeom.BasisCurves(prim).GetPointsAttr().Get(), dtype=float)
    assert np.all(np.asarray(extent[0]) <= pts.min(axis=0) + 1e-6)
    assert np.all(np.asarray(extent[1]) >= pts.max(axis=0) - 1e-6)
    assert not prim.HasAuthoredMetadata("customData")


def test_stage_units_scale_the_width_and_the_ticks():
    mats = [np.asarray(m) for m in _demo_arc()]
    for m in mats:
        m[3, :3] *= 100.0                       # centimetres
    cam = sp.camera_frames(mats)
    stage = _run(sp.trail_code("/guides/p", FRAMES, cam, meters_per_unit=0.01))
    curves = UsdGeom.BasisCurves(stage.GetPrimAtPath("/guides/p"))
    assert list(curves.GetWidthsAttr().Get()) == [pytest.approx(2.0)]   # 2 cm
    pts = np.asarray(curves.GetPointsAttr().Get(), dtype=float)
    tick = np.linalg.norm(pts[121] - pts[120])
    assert tick == pytest.approx(50.0, abs=1e-2)                          # 0.5 m
    assert not math.isnan(tick)
