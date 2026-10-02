"""The spatial handlers over a real USD stage, with a stand-in ``hou`` (D6).

``handlers_spatial.measure`` reads a Camera LOP's parms per frame and confirms
them against the composed stage; ``_handle_spatial_trail`` hands a generated
Python Script LOP to build_graph. Here the stage is real OpenUSD and the
network is a small stand-in: each node is a function that authors onto the
stage, the Camera LOP samples the current frame only (as Houdini's does), and
a Python Script node runs its code the way the LOP would. So the handler's own
logic is exercised end to end: what it recovers, where it says UNKNOWN, and
exactly what it asks build_graph to do.

The stand-in is bound to the handler module only (``hs.hou``); the resident
``sys.modules['hou']`` is never replaced. Needs OpenUSD, so this module is
``needs_houdini`` on stock CI runners (tests/conftest.py). The same handlers
ran against Houdini 22.0.400 on the demo scene; that receipt is on the
done-day card.
"""
from __future__ import annotations

import json
import math
import os
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

pytest.importorskip("pxr")
np = pytest.importorskip("numpy")

from pxr import Gf, Sdf, Usd, UsdGeom, UsdRender  # noqa: E402

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "python"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from synapse.core.errors import SynapseUserError  # noqa: E402
from synapse.server import handlers_spatial as hs  # noqa: E402
from synapse.spatial import path as sp  # noqa: E402

CAM = "/cameras/demo_cam"
SPLAT = "/World/lane/points_0"


# --------------------------------------------------------------------------- #
#  The stand-in network                                                       #
# --------------------------------------------------------------------------- #
def _rot(axis, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
    if axis == "y":
        return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])
    return np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])


def _build_transform(values, xord="srt", rord="xyz"):
    assert xord == "srt" and rord == "xyz"
    r = values["rotate"]
    m = np.eye(4)
    m[:3, :3] = np.diag(values["scale"]) @ _rot("x", r[0]) @ _rot("y", r[1]) @ _rot("z", r[2])
    m[3, :3] = values["translate"]
    return SimpleNamespace(asTuple=lambda: tuple(m.flatten()))


def _ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def _arc_angle(f):
    return -10.0 + 20.0 * _ease((f - 1) / 119.0)


def _arc_t(f):
    a = math.radians(_arc_angle(f))
    return (6.0 * math.sin(a), 1.29, -6.0 + 6.0 * math.cos(a))


class Parm:
    def __init__(self, value, world):
        self._v, self._world = value, world

    def _at(self, f):
        return self._v(f) if callable(self._v) else self._v

    def evalAtFrame(self, f):
        return self._at(f)

    evalAsStringAtFrame = evalAtFrame

    def evalAsString(self):
        return self._at(self._world.now)

    unexpandedString = eval = evalAsString

    def set(self, value):
        self._v = value


class Node:
    def __init__(self, world, name, kind, parms=None, author=None, up=None, branches=()):
        self._world, self._name, self._kind, self._author, self._up = world, name, kind, author, up
        self._branches = list(branches)        # wired in, not cooked: the other inputs of a switch
        self._bypassed = False
        self._parms = {k: Parm(v, world) for k, v in (parms or {}).items()}
        self._pos = (0.0, -float(len(world.nodes)))
        world.nodes[name] = self

    def isBypassed(self):
        return self._bypassed

    def bypass(self, on):
        self._bypassed = bool(on)

    def position(self):
        return self._pos

    def setPosition(self, pos):
        self._pos = pos

    def path(self):
        return "/stage/" + self._name

    def name(self):
        return self._name

    def type(self):
        return SimpleNamespace(nameComponents=lambda: ("", "", self._kind, ""))

    def parent(self):
        return self._world

    def parm(self, name):
        return self._parms.get(name)

    parmTuple = parm

    def input(self, index):
        return self._up if index == 0 else None

    def setInput(self, index, node):
        assert index == 0
        self._up = node

    def destroy(self):
        del self._world.nodes[self._name]

    def errors(self):
        """An error on this node when a Python Script above it is marked bad."""
        return tuple("Invalid source %s" % n.path() for n in self._chain()
                     if n._kind == "pythonscript" and "# breaks downstream" in
                     n._parms["python"].unexpandedString())

    def _chain(self):
        out, node = [], self._up
        while node is not None:
            out.append(node)
            node = node._up
        return out

    def inputAncestors(self):
        """Every upstream node on every branch, as hou's does."""
        out = []
        for node in ([self._up] if self._up is not None else []) + self._branches:
            for found in [node] + node.inputAncestors():
                if found not in out:
                    out.append(found)
        return out

    def stage(self):
        stage = Usd.Stage.CreateInMemory()
        UsdGeom.SetStageMetersPerUnit(stage, self._world.mpu)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
        for node in reversed([self] + self._chain()):
            if not node._bypassed:
                node._cook(stage)
        return stage

    def _cook(self, stage):
        if self._kind == "pythonscript":
            fake = SimpleNamespace(pwd=lambda: SimpleNamespace(editableStage=lambda: stage))
            exec(compile(self._parms["python"].unexpandedString(), self._name, "exec"), {"hou": fake})
        elif self._kind == "camera":
            self._cook_camera(stage)
        elif self._author is not None:
            self._author(stage)

    def _cook_camera(self, stage):
        """Author the camera at the current frame only, as a time sample."""
        now = self._world.now
        prim_path = self._parms["primpath"].evalAsString()
        parent_path = prim_path.rsplit("/", 1)[0]
        if not stage.GetPrimAtPath(parent_path).IsValid():
            UsdGeom.Xform.Define(stage, parent_path)
        cam = UsdGeom.Camera.Define(stage, prim_path)
        # Worked out here, not through the handler's own reader: the handler's
        # check against the stage is then a real comparison, not an echo.
        size = self._parms["scale"].evalAtFrame(now)
        local = np.array(_build_transform({
            "translate": self._parms["t"].evalAtFrame(now), "rotate": self._parms["r"].evalAtFrame(now),
            "scale": [c * size for c in self._parms["s"].evalAtFrame(now)]}).asTuple()).reshape(4, 4)
        if self._parms["xn__xformOptransform_51a"].evalAsString() == "world":
            parent = np.array(UsdGeom.XformCache(Usd.TimeCode(now)).GetLocalToWorldTransform(
                stage.GetPrimAtPath(parent_path))).reshape(4, 4)
            local = local @ np.linalg.inv(parent)
        cam.MakeMatrixXform().Set(Gf.Matrix4d(local.tolist()), Usd.TimeCode(now))


class World:
    """/stage: the network, the playhead and the stand-in hou module."""

    def __init__(self, mpu=1.0):
        self.nodes, self.display, self.now, self.mpu = {}, None, 1.0, mpu
        self.undo_labels = []

    def path(self):
        return "/stage"

    def node(self, name):
        return self.nodes.get(name)

    def children(self):
        return list(self.nodes.values())

    def displayNode(self):
        return self.display

    def hou(self):
        @contextmanager
        def group(label):
            self.undo_labels.append(label)
            yield

        def node(path):
            if path == "/stage":
                return self
            return self.nodes.get(path[len("/stage/"):]) if path.startswith("/stage/") else None

        return SimpleNamespace(
            node=node, frame=lambda: self.now,
            hscriptExpression=lambda e: {"$FSTART": 1.0, "$FEND": 120.0}[e],
            hmath=SimpleNamespace(buildTransform=_build_transform),
            undos=SimpleNamespace(group=group))


def _camera_parms(t=_arc_t, r=lambda f: (0.0, _arc_angle(f), 0.0), mode="xformcommonapi", prim=CAM):
    return {"primpath": prim, "t": t, "r": r, "s": (1.0, 1.0, 1.0), "shear": (0.0, 0.0, 0.0),
            "p": (0.0, 0.0, 0.0), "pr": (0.0, 0.0, 0.0), "scale": 1.0,
            "xOrd": "srt", "rOrd": "xyz", "xn__xformOptransform_51a": mode}


def _near_point(frame=64, up=0.8):
    x, y, z = _arc_t(frame)
    return (x, y + up, z)


def _splats(points, scale=2.0):
    """A splat-typed prim under a scaled parent: its positions are local."""
    def author(stage):
        xform = UsdGeom.Xform.Define(stage, "/World/lane")
        xform.AddScaleOp().Set(Gf.Vec3f(scale, scale, scale))
        prim = stage.DefinePrim(SPLAT, hs.SPLAT_TYPE)
        prim.CreateAttribute(hs.SPLAT_POSITIONS, Sdf.ValueTypeNames.Point3fArray).Set(
            [Gf.Vec3f(*(c / scale for c in p)) for p in points])
    return author


def _wall(n=400, x=30.0):
    rng = np.random.default_rng(7)
    return [(x, float(a), float(b)) for a, b in zip(rng.uniform(0, 3, n), rng.uniform(-12, 1, n))]


def _settings(stage):
    settings = UsdRender.Settings.Define(stage, "/Render/demo_settings")
    settings.CreateCameraRel().SetTargets([Sdf.Path(CAM)])


@pytest.fixture
def world(monkeypatch):
    w = World()
    monkeypatch.setattr(hs, "hou", w.hou())
    monkeypatch.setattr(hs, "HOU_AVAILABLE", True)
    return w


def _demo(world, points=None, between=None, cam_parms=None, before=None):
    """world -> [before] -> demo_cam -> [between] -> demo_settings (displayed)."""
    pts = (_wall() + [_near_point()]) if points is None else points
    tip = Node(world, "lane", "sublayer", author=_splats(pts) if pts else None)
    if before is not None:
        tip = Node(world, "rig", "editproperties", author=before, up=tip)
    tip = Node(world, "demo_cam", "camera", parms=cam_parms or _camera_parms(), up=tip)
    if between is not None:
        tip = Node(world, "after_cam", "editproperties", author=between, up=tip)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=tip)
    return world.display


# --------------------------------------------------------------------------- #
#  The read                                                                   #
# --------------------------------------------------------------------------- #
def test_the_read_recovers_the_demo_arc_and_its_clearance(world):
    _demo(world)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["status"] == "SUCCESS"
    assert r["camera"] == CAM and r["camera_node"] == "/stage/demo_cam"
    assert r["node"] == "/stage/demo_settings"
    assert r["frames"] == {"start": 1.0, "end": 120.0, "sampled": 120}
    m = r["move"]
    assert m["class"] == "arc" and m["class_tier"] == "derived" and "class_thresholds" not in m
    assert m["radius_m"] == pytest.approx(6.0, abs=0.01)
    assert m["orbit_deg"] == pytest.approx(20.0, abs=0.1)
    assert m["height_m"] == [pytest.approx(1.29, abs=1e-3)] * 2 and m["faces_centre"] is True
    c = r["clearance"]
    assert c["status"] == "SUCCESS" and c["metric"] == sp.POINT_METRIC
    assert c["min_m"] == pytest.approx(0.8, abs=2e-3) and c["frame"] == 64.0 and c["side"] == "above"
    assert c["measured"] == {"kind": "splats", "prims": 1, "first": [SPLAT], "points": 401, "at_frame": 1.0}
    assert "not_measured" not in c
    assert r["stage_check"] == {"frame": 1.0, "agrees": True, "position_off_mm": 0.0, "rotation_off_deg": 0.0}
    assert r["provenance"]["lane"] == "spatial" and r["provenance"]["tier"] == "measured"
    assert "confirmed at frame 1 only; scene geometry read at that frame" in r["provenance"]["method"]
    assert r["outcome"].startswith("demo_cam: an arc of radius 6.00 m through 20.0 deg")
    assert "the nearest splat centre comes to 0.80 m, above the lens, at frame 64" in r["outcome"]


def test_the_result_is_short_and_carries_no_file_path(world):
    """D4, and the roster's budget: prim and node paths only, about 1,500 characters."""
    _demo(world)
    text = json.dumps(hs.SpatialHandlerMixin()._handle_get_spatial_path({}))
    assert len(text) < 1800, len(text)
    for token in ("\\\\", ":/", ".hip", ".usd", ".ply", ".glb"):
        assert token not in text


def test_the_read_never_moves_the_playhead_or_opens_an_undo_group(world):
    _demo(world)
    world.now = 37.0
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({"frames": "1-120x7"})
    assert world.now == 37.0 and world.undo_labels == []
    assert r["stage_check"]["frame"] == 37.0
    assert r["frames"]["sampled"] == 18 and r["frames"]["end"] == 120.0


def test_a_camera_no_camera_lop_authors_is_unknown(world):
    def camera(stage):
        UsdGeom.Camera.Define(stage, CAM).AddTranslateOp().Set(Gf.Vec3d(0, 1.29, 0))

    tip = Node(world, "lane", "sublayer", author=_splats(_wall()))
    tip = Node(world, "file_cam", "reference", author=camera, up=tip)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=tip)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["status"] == "UNKNOWN" and r["camera_node"] is None and r["clearance"] is None
    assert "no Camera LOP" in r["move"]["reason"]
    assert "its move is UNKNOWN" in r["outcome"]
    assert r["stage_check"] is None and r["frames"]["sampled"] == 0     # nothing compared, nothing sampled
    assert r["provenance"]["method"] == "the composed stage read at frame 1 only; no path was measured"


def test_a_camera_something_else_also_moves_is_unknown(world):
    def nudge(stage):
        cam = UsdGeom.Xformable(stage.GetPrimAtPath(CAM))
        op = cam.GetOrderedXformOps()[0]
        m = np.array(op.Get(Usd.TimeCode(world.now))).reshape(4, 4)
        m[3, 0] += 0.05
        op.Set(Gf.Matrix4d(m.tolist()), Usd.TimeCode(world.now))

    _demo(world, between=nudge)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["status"] == "UNKNOWN" and r["clearance"] is None
    assert "something after /stage/demo_cam also moves the camera" in r["move"]["reason"]
    # The numbers are the mismatch, and nothing in the result reads as measured.
    assert r["stage_check"]["agrees"] is False
    assert r["stage_check"]["position_off_mm"] == pytest.approx(50.0, abs=0.01)
    assert r["frames"] == {"start": 1.0, "end": 120.0, "sampled": 0}
    assert r["provenance"]["method"] == ("Camera LOP parms compared with the composed stage at "
                                         "frame 1 only; no path was measured")
    assert "confirmed" not in json.dumps(r)


def test_an_animated_parent_makes_the_path_unknown(world):
    def rig(stage):
        UsdGeom.Xform.Define(stage, "/cameras").AddTranslateOp().Set(Gf.Vec3d(0, 0, 0), Usd.TimeCode(world.now))

    _demo(world, before=rig)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["status"] == "UNKNOWN"
    assert r["move"]["reason"].startswith("/cameras, above the camera, carries an animated transform")


def test_a_static_parent_transform_is_carried_into_the_path(world):
    def rig(stage):
        UsdGeom.Xform.Define(stage, "/cameras").AddTranslateOp().Set(Gf.Vec3d(0, 0.5, 0))

    _demo(world, before=rig)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({"against": "none"})
    assert r["status"] == "SUCCESS" and r["clearance"] is None
    assert r["move"]["height_m"] == [pytest.approx(1.79, abs=1e-3)] * 2
    assert r["stage_check"]["agrees"] is True and r["stage_check"]["position_off_mm"] == 0.0


def test_a_world_space_camera_lop_ignores_its_parent(world):
    def rig(stage):
        UsdGeom.Xform.Define(stage, "/cameras").AddTranslateOp().Set(Gf.Vec3d(0, 0.5, 0))

    _demo(world, before=rig, cam_parms=_camera_parms(mode="world"))
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({"against": "none"})
    assert r["status"] == "SUCCESS"
    assert r["move"]["height_m"] == [pytest.approx(1.29, abs=1e-3)] * 2


def test_stage_units_become_metres(world):
    world.mpu = 0.01
    cm = lambda f: tuple(100.0 * c for c in _arc_t(f))            # noqa: E731
    pts = [tuple(100.0 * c for c in p) for p in _wall() + [_near_point()]]
    _demo(world, points=pts, cam_parms=_camera_parms(t=cm))
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["move"]["radius_m"] == pytest.approx(6.0, abs=0.01)
    assert r["clearance"]["min_m"] == pytest.approx(0.8, abs=2e-3)


@pytest.mark.parametrize("camera", [CAM, "demo_cam", "/stage/demo_cam", " demo_cam "])
def test_the_camera_can_be_named_three_ways(world, camera):
    _demo(world)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({"camera": camera})
    assert r["camera"] == CAM and r["status"] == "SUCCESS"


@pytest.mark.parametrize("camera, says", [
    ("/cameras/nope", "No camera prim or Camera LOP"), ("nope", "No camera prim or Camera LOP"),
    ("/World/lane", "not a camera"), ("/cameras/x\nimport os", "No camera prim or Camera LOP"),
])
def test_a_camera_that_is_not_there_is_a_user_error(world, camera, says):
    _demo(world)
    with pytest.raises(SynapseUserError, match=says):
        hs.SpatialHandlerMixin()._handle_get_spatial_path({"camera": camera})


def test_two_cameras_with_one_name_ask_which(world):
    def twin(stage):
        UsdGeom.Camera.Define(stage, "/layout/demo_cam")

    _demo(world, between=twin)
    with pytest.raises(SynapseUserError, match="2 cameras are named demo_cam"):
        hs.SpatialHandlerMixin()._handle_get_spatial_path({"camera": "demo_cam"})


def test_bad_inputs_are_user_errors(world):
    _demo(world)
    mixin = hs.SpatialHandlerMixin()
    with pytest.raises(SynapseUserError, match="against must be one of"):
        mixin._handle_get_spatial_path({"against": "everything"})
    with pytest.raises(SynapseUserError, match="No LOP node"):
        mixin._handle_get_spatial_path({"node": "/stage/nope"})
    with pytest.raises(SynapseUserError, match="frames must look like"):
        mixin._handle_get_spatial_path({"frames": "all of them"})


def test_a_lop_network_path_means_the_node_it_displays(world):
    """/stage is a network, with no stage of its own. Naming it is the same as
    leaving node out: the read, and the trail's splice, use its display node."""
    _demo(world)
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({"node": "/stage"})
    assert r["status"] == "SUCCESS" and r["node"] == "/stage/demo_settings"
    assert r["move"] == hs.SpatialHandlerMixin()._handle_get_spatial_path({})["move"]
    handler = Handler(world)
    drawn = handler._handle_spatial_trail({"node": " /stage "})
    assert handler.builds[0]["nodes"][2] == {"id": "down", "existing": True, "path": "/stage/demo_settings"}
    assert drawn["trail"]["status"] == "created"
    world.display = None
    with pytest.raises(SynapseUserError, match="/stage has no display node"):
        hs.SpatialHandlerMixin()._handle_get_spatial_path({"node": "/stage"})
    with pytest.raises(SynapseUserError, match="/stage has no display node"):
        hs.SpatialHandlerMixin()._handle_get_spatial_path({})


# --------------------------------------------------------------------------- #
#  Where one frame of the stage cannot vouch for the other frames             #
# --------------------------------------------------------------------------- #
def _read(**payload):
    return hs.SpatialHandlerMixin()._handle_get_spatial_path(payload)


def test_two_camera_lops_for_one_camera_are_unknown(world):
    """Two takes behind a switch: which one the stage holds per frame is not
    something the parms of either can say."""
    lane = Node(world, "lane", "sublayer", author=_splats(_wall()))
    take_a = Node(world, "take_a", "camera", parms=_camera_parms(), up=lane)
    take_b = Node(world, "take_b", "camera", parms=_camera_parms(r=(0.0, 0.0, 0.0)), up=lane)
    switch = Node(world, "takes", "switch", up=take_a, branches=[take_b])
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=switch)
    r = _read()
    assert r["status"] == "UNKNOWN" and r["camera_node"] is None and r["clearance"] is None
    assert r["move"]["reason"].startswith("2 Camera LOPs upstream of /stage/demo_settings author " + CAM)
    assert "/stage/take_a, /stage/take_b" in r["move"]["reason"]


def test_a_bypassed_camera_lop_is_not_the_camera(world):
    lane = Node(world, "lane", "sublayer", author=_splats(_wall() + [_near_point()]))
    old = Node(world, "old_cam", "camera", parms=_camera_parms(t=(9.0, 9.0, 9.0), r=(0.0, 0.0, 0.0)), up=lane)
    old.bypass(True)
    cam = Node(world, "demo_cam", "camera", parms=_camera_parms(), up=old)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=cam)
    r = _read()
    assert r["status"] == "SUCCESS" and r["camera_node"] == "/stage/demo_cam"
    assert r["move"]["class"] == "arc"
    with pytest.raises(SynapseUserError, match="/stage/old_cam is bypassed, or does not feed"):
        _read(camera="/stage/old_cam")


def test_a_camera_lop_that_does_not_feed_the_node_is_refused(world):
    _demo(world)
    Node(world, "elsewhere", "camera", parms=_camera_parms())           # same prim path, not wired in
    with pytest.raises(SynapseUserError, match="/stage/elsewhere is bypassed, or does not feed /stage/demo_settings"):
        _read(camera="/stage/elsewhere")


def test_look_at_makes_the_path_unknown(world):
    _demo(world, cam_parms=dict(_camera_parms(), lookatenable=1))
    r = _read()
    assert r["status"] == "UNKNOWN"
    assert r["move"]["reason"] == ("look-at is on at /stage/demo_cam, so the camera's rotation is "
                                   "not in its transform parms")


def test_a_camera_that_already_had_a_transform_is_unknown(world):
    """A Camera LOP editing a referenced, animated camera writes one sample at
    the current frame; the file's other frames are hidden from the live stage."""
    def referenced(stage):
        op = UsdGeom.Camera.Define(stage, CAM).AddTranslateOp()
        for f in (1, 60, 120):
            op.Set(Gf.Vec3d(0.0, 1.29, -0.1 * f), Usd.TimeCode(f))

    _demo(world, before=referenced)
    r = _read()
    assert r["status"] == "UNKNOWN"
    assert r["move"]["reason"].startswith(CAM + " already had a transform before /stage/demo_cam edited it")


def test_a_later_transform_op_that_is_zero_now_is_still_unknown(world):
    """A shake keyed from frame 40 adds nothing at frame 1, so the stage agrees
    with the parms there. The extra op on the camera gives it away."""
    def shake(stage):
        UsdGeom.Xformable(stage.GetPrimAtPath(CAM)).AddTranslateOp(opSuffix="shake").Set(
            Gf.Vec3d(0.0, 0.0, 0.0), Usd.TimeCode(world.now))

    _demo(world, between=shake)
    r = _read()
    assert r["status"] == "UNKNOWN" and r["clearance"] is None
    assert r["stage_check"]["agrees"] is True                           # the one-frame check alone would pass
    assert r["move"]["reason"] == ("something after /stage/demo_cam changes the camera's transform ops "
                                   "(1 there, 2 on the stage)")


def test_a_retime_after_the_camera_is_unknown(world):
    lane = Node(world, "lane", "sublayer", author=_splats(_wall()))
    cam = Node(world, "demo_cam", "camera", parms=_camera_parms(), up=lane)
    shift = Node(world, "slowmo", "timeshift", up=cam)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=shift)
    r = _read()
    assert r["status"] == "UNKNOWN"
    assert r["move"]["reason"] == "/stage/slowmo, after the Camera LOP, retimes the stage"
    shift.bypass(True)
    assert _read()["status"] == "SUCCESS"


def test_a_roll_about_the_lens_is_caught_by_the_check(world):
    """The lens axis alone cannot see a roll; left and right would swap."""
    def roll(stage):
        op = UsdGeom.Xformable(stage.GetPrimAtPath(CAM)).GetOrderedXformOps()[0]
        m = np.array(op.Get(Usd.TimeCode(world.now))).reshape(4, 4)
        m[:3, :3] = _rot("z", 30.0) @ m[:3, :3]
        op.Set(Gf.Matrix4d(m.tolist()), Usd.TimeCode(world.now))

    _demo(world, between=roll)
    r = _read()
    assert r["status"] == "UNKNOWN" and "also moves the camera" in r["move"]["reason"]
    assert r["stage_check"]["agrees"] is False and r["stage_check"]["position_off_mm"] == 0.0
    assert r["stage_check"]["rotation_off_deg"] == pytest.approx(30.0, abs=1e-3)


def test_too_few_frames_measure_without_naming_the_move(world):
    _demo(world)
    one = _read(frames="40")
    assert one["status"] == "SUCCESS" and one["move"]["class"] is None
    assert one["outcome"].startswith("demo_cam: one sample, at frame 40, at a stage height of 1.29 m")
    assert one["clearance"]["status"] == "SUCCESS"                      # one frame still has a clearance
    with pytest.raises(SynapseUserError, match="at least two camera samples"):
        Handler(world)._handle_spatial_trail({"frames": "40"})


# --------------------------------------------------------------------------- #
#  What clearance is measured against                                         #
# --------------------------------------------------------------------------- #
def _mesh(path, points):
    def author(stage):
        mesh = UsdGeom.Mesh.Define(stage, path)
        mesh.CreatePointsAttr([Gf.Vec3f(*p) for p in points])
    return author


def test_no_geometry_makes_clearance_unknown_not_zero(world):
    _demo(world, points=[])
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["status"] == "SUCCESS"
    assert r["clearance"] == {"status": "UNKNOWN", "reason": "no splats or mesh on the stage to measure against"}
    assert "clearance is UNKNOWN (no splats or mesh on the stage to measure against)" in r["outcome"]
    mesh = hs.SpatialHandlerMixin()._handle_get_spatial_path({"against": "mesh"})["clearance"]
    assert mesh["reason"] == "no mesh on the stage to measure against"


def test_auto_prefers_splats_and_says_what_it_left_out(world):
    x, y, z = _arc_t(30)
    _demo(world, between=_mesh("/World/collider", [(x, y - 0.3, z), (40, 0, 0), (41, 0, 0)]))
    mixin = hs.SpatialHandlerMixin()
    auto = mixin._handle_get_spatial_path({})["clearance"]
    assert auto["measured"]["kind"] == "splats" and auto["min_m"] == pytest.approx(0.8, abs=2e-3)
    assert auto["not_measured"] == ["1 mesh prim (pass against=mesh)"]
    mesh = mixin._handle_get_spatial_path({"against": "mesh"})["clearance"]
    assert mesh["metric"] == sp.MESH_METRIC and mesh["measured"]["first"] == ["/World/collider"]
    assert mesh["min_m"] == pytest.approx(0.3, abs=2e-3) and mesh["frame"] == 30.0 and mesh["side"] == "below"


def test_with_no_splats_auto_measures_mesh_vertices_and_skips_prototypes(world):
    """A point instancer's prototype sits wherever it was modelled, often at the
    origin. It is not scene geometry, so it is never what the lens came close to."""
    x, y, z = _arc_t(90)

    def scatter(stage):
        _mesh("/World/collider", [(x, y - 0.6, z), (40, 0, 0)])(stage)
        _mesh("/prototypes/rock_a", [(x, y, z), (x, y + 0.01, z)])(stage)      # on the lens, if it counted
        instancer = UsdGeom.PointInstancer.Define(stage, "/World/rocks")
        instancer.CreatePrototypesRel().SetTargets([Sdf.Path("/prototypes/rock_a")])

    _demo(world, points=[], between=scatter)
    c = hs.SpatialHandlerMixin()._handle_get_spatial_path({})["clearance"]
    assert c["measured"] == {"kind": "mesh", "prims": 1, "first": ["/World/collider"], "points": 2,
                             "at_frame": 1.0}
    assert c["min_m"] == pytest.approx(0.6, abs=2e-3) and c["metric"] == sp.MESH_METRIC
    assert c["not_measured"] == ["point-instancer instances"]


def test_asking_for_splats_when_there_are_none_is_unknown(world):
    _demo(world, points=[], between=_mesh("/World/collider", [(0, 0, 0), (1, 0, 0)]))
    c = _read(against="splats")["clearance"]
    assert c == {"status": "UNKNOWN", "reason": "no splats on the stage to measure against"}


def test_geometry_that_moves_is_measured_where_it_is_now_and_says_so(world):
    def crane_arm(stage):
        xform = UsdGeom.Xform.Define(stage, "/World/arm")
        xform.AddTranslateOp().Set(Gf.Vec3d(0, 0, 0), Usd.TimeCode(world.now))     # animated: one sample, now
        UsdGeom.Mesh.Define(stage, "/World/arm/geo").CreatePointsAttr([Gf.Vec3f(0, 3, -3)])
        UsdGeom.Sphere.Define(stage, "/World/ball")
        UsdGeom.Cube.Define(stage, "/World/crate")

    _demo(world, points=[], between=crane_arm)
    c = _read()["clearance"]
    assert c["measured"]["kind"] == "mesh" and c["measured"]["at_frame"] == 1.0
    assert c["not_measured"] == ["the motion of 1 measured prim (read where it is at frame 1)",
                                 "2 shape prims that are not a mesh"]


def test_past_the_budget_the_points_are_thinned_and_the_result_says_so(world, monkeypatch):
    monkeypatch.setattr(hs, "MAX_PAIRS", 120 * 100)
    _demo(world)
    c = hs.SpatialHandlerMixin()._handle_get_spatial_path({})["clearance"]
    assert c["measured"]["points"] == 401 and c["point_count"] == 81           # every 5th of 401
    assert c["measured"]["thinned"].startswith("every 5th point measured")


# --------------------------------------------------------------------------- #
#  The trail                                                                  #
# --------------------------------------------------------------------------- #
class Handler(hs.SpatialHandlerMixin):
    """The mixin with build_graph standing in: it records the request and
    splices the node the way an insert between two existing nodes does."""

    def __init__(self, world, parms_missed=None, code=None, fail_after_build=None):
        self.world, self.builds, self.parms_missed = world, [], parms_missed or []
        self.code, self.fail_after_build = code, fail_after_build

    def _handle_solaris_build_graph(self, payload):
        self.builds.append(payload)
        spec = {n["id"]: n for n in payload["nodes"]}
        up, down = hs.hou.node(spec["up"]["path"]), hs.hou.node(spec["down"]["path"])
        parms = dict(spec["trail"]["parms"])
        if self.code is not None:
            parms["python"] = self.code
        trail = Node(self.world, spec["trail"]["name"], spec["trail"]["type"], parms=parms, up=up)
        down.setInput(0, trail)
        down.setPosition((down.position()[0], down.position()[1] - 1.5))      # the inline splice's shift
        if self.fail_after_build is not None:
            raise self.fail_after_build       # the node is in, and nothing rolled it back
        return {"status": "created", "nodes_created": [{"id": "trail", "path": trail.path()}],
                "parms_missed": self.parms_missed, "warnings": []}


def test_the_trail_is_one_build_graph_splice_above_the_display_node(world):
    display = _demo(world)
    handler = Handler(world)
    r = handler._handle_spatial_trail({})
    assert len(handler.builds) == 1
    build = handler.builds[0]
    assert build["parent"] == "/stage" and "display_node" not in build and "template" not in build
    assert build["nodes"][0] == {"id": "up", "existing": True, "path": "/stage/demo_cam"}
    assert build["nodes"][2] == {"id": "down", "existing": True, "path": "/stage/demo_settings"}
    trail = build["nodes"][1]
    assert trail["type"] == "pythonscript" and trail["name"] == "demo_cam_path"
    assert set(trail["parms"]) == {"python"}
    assert build["connections"] == [{"from": "up", "to": "trail"},
                                    {"from": "trail", "to": "down", "input": 0, "insert": True}]
    assert world.display is display                                   # the flag did not move
    assert display.input(0).path() == "/stage/demo_cam_path"

    t = r["trail"]
    assert t["status"] == "created" and t["node"] == "/stage/demo_cam_path"
    assert t["prim"] == "/guides/demo_cam_path" and t["purpose"] == "proxy"
    assert t["points"] == 120 + 2 * 12 and t["karma_leaves_it_out"] is True
    assert build["sections"] is False                                 # earlier builds' boxes are left alone
    assert world.undo_labels == ["SYNAPSE: Draw camera path"]            # one group around the build
    assert r["undo"]["label"] == "SYNAPSE: Draw camera path"
    assert r["undo"]["artist"] == "One Ctrl+Z reverses: Draw camera path"
    assert r["undo"]["rolls_back_on_failure"] is True                 # a failed write is taken back out
    assert r["status"] == "SUCCESS" and r["move"]["class"] == "arc"
    assert r["outcome"].endswith("Drew the path as /guides/demo_cam_path (proxy purpose, 144 points); "
                                 "Karma's render settings leave it out.")


def test_the_trails_code_is_the_hosts_own(world):
    """What reaches the node is exactly trail_code over the measured frames.
    Anything else in the request is ignored: there is no input for code."""
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({"code": "import os", "python": "import os", "points": [[0, 0, 0]]})
    code = handler.builds[0]["nodes"][1]["parms"]["python"]
    frames = [float(f) for f in range(1, 121)]
    mats = [np.array(_build_transform({"translate": _arc_t(f), "rotate": (0.0, _arc_angle(f), 0.0),
                                       "scale": (1.0, 1.0, 1.0)}).asTuple()).reshape(4, 4) for f in frames]
    assert code == sp.trail_code("/guides/demo_cam_path", frames, sp.camera_frames(mats), camera=CAM)
    assert code.startswith(hs.TRAIL_HEADER + " of " + CAM + ", frames 1-120.") and "import os" not in code


def test_asking_again_changes_nothing_and_a_new_move_redraws_in_one_undo(world):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    again = handler._handle_spatial_trail({})
    assert len(handler.builds) == 1 and world.undo_labels == ["SYNAPSE: Draw camera path"]
    assert again["trail"]["status"] == "unchanged" and "undo" not in again
    assert "The path is already drawn as /guides/demo_cam_path" in again["outcome"]

    world.nodes["demo_cam"].parm("t").set(lambda f: (0.0, 1.29, -8.0 * (f - 1) / 119.0))
    world.nodes["demo_cam"].parm("r").set((0.0, 0.0, 0.0))
    moved = handler._handle_spatial_trail({})
    assert len(handler.builds) == 1 and world.undo_labels == ["SYNAPSE: Draw camera path"] * 2
    assert moved["trail"]["status"] == "updated" and moved["trail"]["node"] == "/stage/demo_cam_path"
    assert moved["undo"]["label"] == "SYNAPSE: Draw camera path"
    assert moved["move"]["class"] == "dolly" and "Redrew the path" in moved["outcome"]
    stage = world.display.stage()
    pts = UsdGeom.BasisCurves(stage.GetPrimAtPath("/guides/demo_cam_path")).GetPointsAttr().Get()
    assert tuple(pts[119]) == pytest.approx((0.0, 1.29, -8.0), abs=1e-4)


def test_a_drawn_trail_does_not_change_what_the_read_measures(world):
    _demo(world)
    handler = Handler(world)
    before = handler._handle_get_spatial_path({})["clearance"]
    handler._handle_spatial_trail({})
    after = handler._handle_get_spatial_path({})["clearance"]
    assert after == before


def test_a_second_camera_gets_its_own_trail(world):
    second = _camera_parms(t=lambda f: (3.0, 2.0, 0.1 * f), r=(0.0, 0.0, 0.0), prim="/cameras/wide")
    tip = Node(world, "lane", "sublayer", author=_splats(_wall()))
    tip = Node(world, "demo_cam", "camera", parms=_camera_parms(), up=tip)
    tip = Node(world, "wide", "camera", parms=second, up=tip)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=tip)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    wide = handler._handle_spatial_trail({"camera": "/cameras/wide"})
    assert len(handler.builds) == 2
    assert wide["trail"]["node"] == "/stage/wide_path" and wide["trail"]["prim"] == "/guides/wide_path"
    assert handler._handle_spatial_trail({})["trail"]["status"] == "unchanged"       # demo_cam's is still found
    assert handler._handle_spatial_trail({"camera": "wide"})["trail"]["status"] == "unchanged"
    assert len(handler.builds) == 2
    stage = world.display.stage()
    assert stage.GetPrimAtPath("/guides/demo_cam_path").IsValid()
    assert stage.GetPrimAtPath("/guides/wide_path").IsValid()


def test_a_node_that_already_has_the_name_is_never_reused(world):
    _demo(world)
    Node(world, "demo_cam_path", "null")                 # the artist's, elsewhere in the network
    handler = Handler(world)
    r = handler._handle_spatial_trail({})
    assert handler.builds[0]["nodes"][1]["name"] == "demo_cam_path2"
    assert r["trail"]["node"] == "/stage/demo_cam_path2"


def test_the_default_purpose_is_not_left_out_by_karma(world):
    _demo(world)
    r = Handler(world)._handle_spatial_trail({"purpose": "default"})
    assert r["trail"]["purpose"] == "default" and r["trail"]["karma_leaves_it_out"] is False
    assert r["outcome"].endswith("(default purpose, 144 points).")


def test_nothing_is_built_when_the_trail_cannot_be_drawn(world):
    _demo(world)
    handler = Handler(world)
    with pytest.raises(SynapseUserError, match="purpose must be one of"):
        handler._handle_spatial_trail({"purpose": "invisible"})
    with pytest.raises(SynapseUserError, match="has no camera"):
        handler._handle_spatial_trail({"node": "/stage/lane"})        # upstream of the camera
    assert handler.builds == [] and world.undo_labels == []


def test_a_node_with_no_input_has_nowhere_to_splice_the_trail(world):
    """The trail goes above a node and never takes the display flag, so a
    first node (here the Camera LOP itself) is refused, not worked around."""
    world.display = Node(world, "demo_cam", "camera", parms=_camera_parms())
    handler = Handler(world)
    with pytest.raises(SynapseUserError, match="has no input to splice the trail above"):
        handler._handle_spatial_trail({})
    assert handler.builds == [] and world.undo_labels == []


def test_an_unknown_move_draws_no_trail(world):
    def nudge(stage):
        op = UsdGeom.Xformable(stage.GetPrimAtPath(CAM)).GetOrderedXformOps()[0]
        m = np.array(op.Get(Usd.TimeCode(world.now))).reshape(4, 4)
        m[3, 1] += 0.2
        op.Set(Gf.Matrix4d(m.tolist()), Usd.TimeCode(world.now))

    _demo(world, between=nudge)
    handler = Handler(world)
    with pytest.raises(SynapseUserError, match="No trail drawn: something after /stage/demo_cam"):
        handler._handle_spatial_trail({})
    assert handler.builds == []


def _assert_withdrawn(world):
    assert "demo_cam_path" not in world.nodes
    assert world.display.input(0).path() == "/stage/demo_cam"
    assert world.display.position() == (0.0, -2.0)            # moved back to where it was
    assert not world.display.stage().GetPrimAtPath("/guides").IsValid()


def test_a_build_that_did_not_write_the_code_is_withdrawn(world):
    _demo(world)
    handler = Handler(world, parms_missed=[{"node": "/stage/demo_cam_path", "parm": "python"}])
    with pytest.raises(SynapseUserError, match="The trail was not drawn"):
        handler._handle_spatial_trail({})
    _assert_withdrawn(world)


def test_a_node_whose_code_draws_nothing_is_withdrawn(world):
    """The handler reads the stage back. A node that is in the network without
    the path on the stage is not a trail, so it does not stay."""
    _demo(world)
    handler = Handler(world, code="# nothing here\n")
    with pytest.raises(SynapseUserError, match="/guides/demo_cam_path is not on the stage"):
        handler._handle_spatial_trail({})
    _assert_withdrawn(world)


def test_a_trail_that_puts_an_error_on_the_node_below_is_withdrawn(world):
    _demo(world)
    code = sp.trail_code("/guides/demo_cam_path", [1.0, 2.0],
                         sp.camera_frames([np.eye(4), np.eye(4)])) + "# breaks downstream\n"
    handler = Handler(world, code=code)
    with pytest.raises(SynapseUserError, match="/stage/demo_settings reported an error with the trail above"):
        handler._handle_spatial_trail({})
    _assert_withdrawn(world)


def test_a_build_that_raises_with_its_node_still_in_is_withdrawn(world):
    """Under another undo group (this handler's, or the panel bridge's)
    build_graph's own rollback does not run, so the handler takes the node out."""
    _demo(world)
    handler = Handler(world, fail_after_build=SynapseUserError("build rolled back -- an error badge"))
    with pytest.raises(SynapseUserError, match="an error badge"):
        handler._handle_spatial_trail({})
    _assert_withdrawn(world)


def test_a_redraw_that_fails_puts_the_old_path_back(world, monkeypatch):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    before = world.nodes["demo_cam_path"].parm("python").unexpandedString()
    world.nodes["demo_cam"].parm("t").set(lambda f: (0.0, 1.29, -8.0 * (f - 1) / 119.0))
    monkeypatch.setattr(hs, "_trail_on_stage", lambda node, prim, purpose: {
        "prim": None, "points": None, "purpose": None, "karma_leaves_it_out": None})
    with pytest.raises(SynapseUserError, match="The trail was not redrawn"):
        handler._handle_spatial_trail({})
    assert world.nodes["demo_cam_path"].parm("python").unexpandedString() == before


def test_the_trail_is_found_again_after_the_artist_wires_a_node_below_it(world):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    trail = world.nodes["demo_cam_path"]
    grade = Node(world, "artist_grade", "editproperties", up=trail)
    world.display.setInput(0, grade)
    again = handler._handle_spatial_trail({})
    assert len(handler.builds) == 1 and again["trail"]["status"] == "unchanged"
    assert again["trail"]["node"] == "/stage/demo_cam_path"


def test_a_bypassed_trail_is_switched_back_on_when_asked_for_again(world):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    world.nodes["demo_cam_path"].bypass(True)
    assert not world.display.stage().GetPrimAtPath("/guides/demo_cam_path").IsValid()
    again = handler._handle_spatial_trail({})
    assert again["trail"]["status"] == "updated" and len(handler.builds) == 1
    assert world.nodes["demo_cam_path"].isBypassed() is False
    assert world.undo_labels == ["SYNAPSE: Draw camera path"] * 2
    assert world.display.stage().GetPrimAtPath("/guides/demo_cam_path").IsValid()


def test_an_artists_own_guides_prim_keeps_its_type(world):
    def guides(stage):
        UsdGeom.Xform.Define(stage, "/guides")

    _demo(world, before=guides)
    Handler(world)._handle_spatial_trail({})
    stage = world.display.stage()
    assert stage.GetPrimAtPath("/guides").GetTypeName() == "Xform"
    assert stage.GetPrimAtPath("/guides/demo_cam_path").IsValid()


# --------------------------------------------------------------------------- #
#  The read says whether the path is drawn                                    #
# --------------------------------------------------------------------------- #
ABSENT = " Its path is not drawn on this stage."
DRAWN = " Its path is drawn on this stage as /guides/demo_cam_path (144 points)."


def _undo_by_hand(world, name="demo_cam_path"):
    """What Edit > Undo does to a drawn trail: the node and its wire go."""
    trail = world.nodes[name]
    for node in list(world.nodes.values()):
        if node.input(0) is trail:
            node.setInput(0, trail.input(0))
    trail.destroy()


def test_the_read_says_not_drawn_then_drawn_then_not_drawn_after_an_undo(world):
    """TRAILPRESENT (the recorded D6 test, 2026-10-02). Asked again after the
    path was undone, the model called the read, which said nothing about a
    path, and answered from its own history that the path was still there. The
    read now says what the stage holds, both ways, in the sentence the model is
    told to relay."""
    _demo(world)
    handler = Handler(world)
    before = handler._handle_get_spatial_path({})
    assert before["trail"] == {"status": "absent"}
    assert before["outcome"].endswith("at frame 64 (a stray point: the 10th nearest is 28.96 m)." + ABSENT)

    handler._handle_spatial_trail({})
    drawn = handler._handle_get_spatial_path({})
    assert drawn["trail"] == {"status": "drawn", "node": "/stage/demo_cam_path",
                              "prim": "/guides/demo_cam_path", "points": 144}
    assert drawn["outcome"].endswith(DRAWN) and ABSENT not in drawn["outcome"]
    assert drawn["move"] == before["move"] and drawn["clearance"] == before["clearance"]

    _undo_by_hand(world)
    gone = handler._handle_get_spatial_path({})
    assert gone["trail"] == {"status": "absent"}                      # the finding: this said nothing
    assert gone["outcome"] == before["outcome"]
    # Three reads opened no undo group and wrote nothing: one group, the trail's.
    assert world.undo_labels == ["SYNAPSE: Draw camera path"]


def test_the_read_with_a_path_drawn_still_fits_the_budget_and_names_no_file(world):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    text = json.dumps(handler._handle_get_spatial_path({}))
    assert len(text) < 1800, len(text)
    for token in ("\\\\", ":/", ".hip", ".usd", ".ply", ".glb"):
        assert token not in text


def test_a_bypassed_trail_is_not_drawn_and_the_read_says_which_node(world):
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    world.nodes["demo_cam_path"].bypass(True)
    r = handler._handle_get_spatial_path({})
    assert r["trail"] == {"status": "bypassed", "node": "/stage/demo_cam_path"}
    assert r["outcome"].endswith(" Its path is not drawn on this stage: /stage/demo_cam_path is bypassed.")
    assert world.nodes["demo_cam_path"].isBypassed() is True          # a read switches nothing back on


def test_a_curve_of_the_artists_own_at_that_path_is_not_called_synapses(world):
    """The prim alone is not the evidence. A curve an artist authored at
    /guides/demo_cam_path, with no trail node of SYNAPSE's above the node, is
    theirs, and the read does not claim it."""
    def own_curve(stage):
        curve = UsdGeom.BasisCurves.Define(stage, "/guides/demo_cam_path")
        curve.CreatePointsAttr([Gf.Vec3f(0, 0, 0), Gf.Vec3f(1, 0, 0)])

    _demo(world, before=own_curve)
    assert world.display.stage().GetPrimAtPath("/guides/demo_cam_path").GetTypeName() == "BasisCurves"
    r = hs.SpatialHandlerMixin()._handle_get_spatial_path({})
    assert r["trail"] == {"status": "absent"} and r["outcome"].endswith(ABSENT)


def test_the_read_answers_for_the_stage_and_the_camera_it_read(world):
    """A trail sits above the display node. Read at a node above the trail, the
    stage there does not hold it. And each camera's path is its own."""
    second = _camera_parms(t=lambda f: (3.0, 2.0, 0.1 * f), r=(0.0, 0.0, 0.0), prim="/cameras/wide")
    tip = Node(world, "lane", "sublayer", author=_splats(_wall()))
    tip = Node(world, "demo_cam", "camera", parms=_camera_parms(), up=tip)
    tip = Node(world, "wide", "camera", parms=second, up=tip)
    world.display = Node(world, "demo_settings", "karmarendersettings", author=_settings, up=tip)
    handler = Handler(world)
    handler._handle_spatial_trail({})                                 # demo_cam's path only
    assert handler._handle_get_spatial_path({})["trail"]["status"] == "drawn"
    assert handler._handle_get_spatial_path({"camera": "/cameras/wide"})["trail"] == {"status": "absent"}
    above = handler._handle_get_spatial_path({"node": "/stage/wide", "camera": CAM})
    assert above["node"] == "/stage/wide" and above["trail"] == {"status": "absent"}
    # Read at the trail's own node, the stage there holds it.
    at_trail = handler._handle_get_spatial_path({"node": "/stage/demo_cam_path", "camera": CAM})
    assert at_trail["trail"]["status"] == "drawn" and at_trail["trail"]["node"] == "/stage/demo_cam_path"


def test_a_path_drawn_before_the_move_became_unreadable_is_still_reported(world):
    """The drawn path is a snapshot. Look-at switched on afterwards makes the
    move UNKNOWN, and the curve drawn earlier is still on the stage."""
    _demo(world)
    handler = Handler(world)
    handler._handle_spatial_trail({})
    world.nodes["demo_cam"]._parms["lookatenable"] = Parm(1, world)
    r = handler._handle_get_spatial_path({})
    assert r["status"] == sp.STATUS_UNKNOWN and "its move is UNKNOWN (look-at is on" in r["outcome"]
    assert r["trail"]["status"] == "drawn" and r["outcome"].endswith(DRAWN)


def test_the_trail_tools_own_result_is_worded_as_it_was(world):
    """The read's sentence about the path belongs to the read. The trail says
    what it did, in the words it had."""
    _demo(world)
    handler = Handler(world)
    drawn = handler._handle_spatial_trail({})
    assert "on this stage" not in drawn["outcome"]
    assert drawn["outcome"].endswith("Drew the path as /guides/demo_cam_path (proxy purpose, 144 points); "
                                     "Karma's render settings leave it out.")
    assert set(drawn["trail"]) == {"status", "node", "prim", "points", "purpose", "karma_leaves_it_out"}
