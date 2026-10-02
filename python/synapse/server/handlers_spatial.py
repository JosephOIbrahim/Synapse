"""Synapse spatial handlers: the camera path read and its trail (D6, 10/1).

Two commands over ``synapse/spatial/path.py`` (pure numpy):

    get_spatial_path  read-only. The camera's move across frames and its
                      clearance to the scene, measured.
    spatial_trail     one build. The same read, drawn as a guide curve in a
                      Python Script LOP that SYNAPSE writes itself.

How time is read. A Camera LOP samples the current frame only (its
``sample_behavior`` defaults to ``single``), so the live stage holds one frame
of the move. A playhead loop would fill in the rest, but the house counts a
``hou.setFrame`` loop as mutating (handlers.py, the cops_temporal_analysis
note), and in the GUI it would recook and repaint every frame. So the read
evaluates the Camera LOP's own transform parms at every frame
(``evalAtFrame``: no playhead move, no cook) and confirms the result against
the composed stage at the current frame. ``stage_check`` carries that
comparison: how far apart the two are there, and whether they agree.

Where it says UNKNOWN instead of guessing:

    * no Camera LOP at or upstream of the node authors the camera, or more
      than one does (a switch between takes, say);
    * look-at is on at that Camera LOP (its rotation is not in its parms);
    * the camera already had a transform before that Camera LOP edited it;
    * a prim above the camera carries time-sampled transforms (its parent may
      be animated, and one frame of the stage cannot say how);
    * a node after the Camera LOP retimes the stage or changes the camera's
      transform ops;
    * the composed stage disagrees with that Camera LOP at the current frame,
      in position or in rotation (something after it also moves the camera).

The confirmation is at the current frame only, and the provenance says so:
a later node whose extra motion is exactly zero at that frame, and adds no
transform op of its own, is the case it cannot see. Scene geometry is read
where it is at the current frame; prims that move over the shot are counted
and named in ``not_measured``.

Probe receipt (10/1, hython 22.0.400, the demo scene): the parm route matched
the composed stage to 0.0 mm and 0.0 deg on all 120 frames, in 4 ms.

The trail reuses ``synapse_solaris_build_graph`` for the build: one Python
Script LOP spliced in above the node, display flag untouched, badge-checked,
under one undo group (``SYNAPSE: Draw camera path``). The handler reads the path
back from the stage afterwards, and a write that did not put it there is taken
back out before the error is raised. The model never writes or relays the code
or the coordinates; the handler generates both, and the only text that reaches
the code is a prim path the stage already holds.

Lane ``spatial``. Results carry prim and node paths only, never file paths
(D4), and name directions and distances, never objects.
"""
from __future__ import annotations

import logging
import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import hou
    HOU_AVAILABLE = True
except ImportError:
    hou = None  # type: ignore[assignment]
    HOU_AVAILABLE = False

from ..core.aliases import resolve_param
from ..core.errors import HoudiniUnavailableError, SynapseUserError
from ..spatial import path as spatial_path
from .handler_helpers import _safe_node_name, undo_receipt

logger = logging.getLogger(__name__)

CHECK_MM = 1.0             # parm route vs composed stage, at the current frame
CHECK_DEG = 0.05
MAX_SAMPLES = 1000         # frames sampled per read; above this the step widens
MAX_PAIRS = 150_000_000    # frames x points measured per read (about 2 s); above
                           # this the points are thinned, and the result says so
SPLAT_TYPE = "ParticleField3DGaussianSplat"
SPLAT_POSITIONS = "positions"
AGAINST = ("auto", "splats", "mesh", "none")
_NOTHING_FOUND = {"auto": "splats or mesh", "splats": "splats", "mesh": "mesh"}
PURPOSES = ("proxy", "guide", "default", "render")
TRAIL_PARENT = "/guides"
TRAIL_HEADER = "# SYNAPSE: camera path"
# The step's name in Houdini's Edit menu. The panel's bridge names its own outer
# group from this (bridge_adapter), so the label a result reports is the label
# the artist sees, whichever way the tool was reached.
TRAIL_UNDO = "SYNAPSE: Draw camera path"
RETIME_LOPS = ("timeshift",)      # a node of these types after the camera retimes the stage
_XFORM_MODE_PARM = "xn__xformOptransform_51a"
_FRAMES_RE = re.compile(
    r"\s*(-?\d+(?:\.\d+)?)(?:\s*-\s*(-?\d+(?:\.\d+)?)(?:\s*x\s*(\d+(?:\.\d+)?))?)?\s*")


def _provenance(method: str, tier: str = "measured") -> Dict[str, str]:
    return {"lane": "spatial", "method": method, "tier": tier}


def parse_frames(spec, start: float, end: float) -> List[float]:
    """Frames to sample: nothing (``start`` to ``end``), ``40``, ``"1-120"``
    or ``"1-120x5"``. Never more than MAX_SAMPLES; the step widens instead.
    The last frame of the range is always sampled."""
    if spec is None or str(spec).strip() == "":
        a, b, step = float(start), float(end), 1.0
    else:
        m = _FRAMES_RE.fullmatch(str(spec))
        if not m:
            raise SynapseUserError("frames must look like 40, 1-120 or 1-120x5, not %r" % (spec,))
        a = float(m.group(1))
        b = float(m.group(2)) if m.group(2) is not None else a
        step = float(m.group(3)) if m.group(3) is not None else 1.0
    if b < a:
        raise SynapseUserError("the frame range runs backwards: %s to %s"
                               % (spatial_path._fmt_frame(a), spatial_path._fmt_frame(b)))
    if step <= 0:
        raise SynapseUserError("the frame step must be positive: %s" % (spec,))
    count = int(math.floor((b - a) / step + 1e-9)) + 1
    if count > MAX_SAMPLES:
        step = (b - a) / (MAX_SAMPLES - 1)
        count = MAX_SAMPLES
    frames = [round(a + i * step, 6) for i in range(count)]
    if frames[-1] < b - 1e-6:
        if count < MAX_SAMPLES:
            frames.append(b)
        else:
            frames[-1] = b
    return frames


def _np(gf):
    import numpy as np
    return np.array([[gf[i][j] for j in range(4)] for i in range(4)], dtype=float)


def _stage_node(node_path: Optional[str]):
    """The LOP node whose stage is read. A LOP network's own path (``/stage``)
    means the node it displays, the same as leaving ``node`` out."""
    asked = str(node_path).strip() if node_path else ""
    node = hou.node(asked or "/stage")
    if node is not None and not hasattr(node, "stage"):
        shown = getattr(node, "displayNode", None)      # hou.LopNetwork has no stage() of its own
        if callable(shown):
            node = shown()
            if node is None:
                raise SynapseUserError("%s has no display node" % (asked or "/stage"),
                                       suggestion="Pass a LOP node path")
    if node is None or not hasattr(node, "stage"):
        raise SynapseUserError("No LOP node at %s" % (asked or "/stage"),
                               suggestion="Pass a Solaris node path, or leave node out "
                                          "to use /stage's display node")
    return node


def _render_camera(stage) -> Optional[str]:
    """The camera the render settings name, else the stage's first camera."""
    first = None
    for prim in stage.Traverse():
        type_name = prim.GetTypeName()
        if type_name == "RenderSettings":
            rel = prim.GetRelationship("camera")
            targets = rel.GetTargets() if rel else []
            if targets and stage.GetPrimAtPath(targets[0]).IsValid():
                return str(targets[0])
        elif type_name == "Camera" and first is None:
            first = str(prim.GetPath())
    return first


def _resolve_camera(stage, node, camera) -> Tuple[str, Any]:
    """A camera given as a prim path, a Camera LOP path, or a bare name.

    Returns ``(prim path, Camera LOP or None)``. A bare name must match one
    camera prim on the stage, or a Camera LOP beside ``node``."""
    from pxr import Sdf
    text = str(camera).strip()
    if text.startswith("/"):
        prim = stage.GetPrimAtPath(text) if Sdf.Path.IsValidPathString(text) else None
        if prim is not None and prim.IsValid():
            return str(prim.GetPath()), None
        candidate = hou.node(text)
    else:
        named = [str(p.GetPath()) for p in stage.Traverse()
                 if p.GetTypeName() == "Camera" and p.GetName() == text]
        if len(named) == 1:
            return named[0], None
        if len(named) > 1:
            raise SynapseUserError("%d cameras are named %s: %s" % (len(named), text, ", ".join(named[:5])),
                                   suggestion="Pass the full prim path of the one you mean")
        parent = node.parent()
        candidate = parent.node(text) if parent is not None and re.fullmatch(r"[A-Za-z0-9_]+", text) else None
    if not _is_camera_lop(candidate):
        raise SynapseUserError("No camera prim or Camera LOP at %s" % text,
                               suggestion="Pass a camera prim path such as /cameras/shot_cam, "
                                          "or leave camera out to use the render camera")
    return candidate.parm("primpath").evalAsString(), candidate


def _is_camera_lop(node) -> bool:
    return (node is not None and node.type().nameComponents()[2] == "camera"
            and node.parm("primpath") is not None)


def _camera_lops(node, prim_path: str) -> List[Any]:
    """Every live Camera LOP at or upstream of ``node`` that authors ``prim_path``.

    ``inputAncestors`` walks every branch, so two takes behind a switch both
    show up here; a bypassed node authors nothing and is left out."""
    return [candidate for candidate in [node] + list(node.inputAncestors())
            if _is_camera_lop(candidate) and not candidate.isBypassed()
            and candidate.parm("primpath").evalAsString() == prim_path]


def _xform_ops(prim) -> List[str]:
    from pxr import UsdGeom
    xformable = UsdGeom.Xformable(prim)
    if not xformable:
        return []
    ops = [str(op.GetOpName()) for op in xformable.GetOrderedXformOps()]
    return (["!resetXformStack!"] if xformable.GetResetXformStack() else []) + ops


def _unreadable(node, cam_node, cam_prim) -> Optional[str]:
    """Why this Camera LOP's parms cannot stand for the camera's move, or None.

    Each check is a way the per-frame parm read could differ from what the
    stage holds on frames other than the current one."""
    prim_path = str(cam_prim.GetPath())
    lookat = cam_node.parm("lookatenable")
    if lookat is not None and lookat.eval():
        return ("look-at is on at %s, so the camera's rotation is not in its transform parms"
                % cam_node.path())
    before = cam_node.input(0)
    before_stage = before.stage() if before is not None else None
    prior = before_stage.GetPrimAtPath(prim_path) if before_stage is not None else None
    if prior is not None and prior.IsValid() and _xform_ops(prior):
        return ("%s already had a transform before %s edited it, and the live stage holds "
                "only the current frame of the result" % (prim_path, cam_node.path()))
    animated = _animated_ancestor(cam_prim)
    if animated is not None:
        return ("%s, above the camera, carries an animated transform, and the live "
                "stage holds only the current frame of it" % animated)
    if node.path() != cam_node.path():
        for later in [node] + list(node.inputAncestors()):
            if later.path() == cam_node.path() or later.isBypassed():
                continue
            if not any(a.path() == cam_node.path() for a in later.inputAncestors()):
                continue
            if later.type().nameComponents()[2] in RETIME_LOPS:
                return "%s, after the Camera LOP, retimes the stage" % later.path()
        own_stage = cam_node.stage()
        own = own_stage.GetPrimAtPath(prim_path) if own_stage is not None else None
        if own is not None and own.IsValid() and _xform_ops(own) != _xform_ops(cam_prim):
            return ("something after %s changes the camera's transform ops (%s there, %s on "
                    "the stage)" % (cam_node.path(), len(_xform_ops(own)), len(_xform_ops(cam_prim))))
    return None


def _parm_local(cam_node, frame: float):
    import numpy as np

    def tup(name):
        return list(cam_node.parmTuple(name).evalAtFrame(frame))

    scale = cam_node.parm("scale").evalAtFrame(frame)
    values = {"translate": tup("t"), "rotate": tup("r"),
              "scale": [c * scale for c in tup("s")], "shear": tup("shear"),
              "pivot": tup("p"), "pivot_rotate": tup("pr")}
    xord = cam_node.parm("xOrd").evalAsStringAtFrame(frame)
    rord = cam_node.parm("rOrd").evalAsStringAtFrame(frame)
    return np.array(hou.hmath.buildTransform(values, xord, rord).asTuple(), dtype=float).reshape(4, 4)


def _rotation_deg(a, b) -> float:
    """The larger angle between two matrices' lens axes and between their up
    axes: the lens alone would miss a roll about it."""
    import numpy as np

    def angle(row):
        va = a[row, :3] / (np.linalg.norm(a[row, :3]) or 1.0)
        vb = b[row, :3] / (np.linalg.norm(b[row, :3]) or 1.0)
        return math.degrees(math.acos(max(-1.0, min(1.0, float(va @ vb)))))

    return max(angle(2), angle(1))


def _animated_ancestor(cam_prim) -> Optional[str]:
    """The nearest prim above the camera whose transform carries time samples.

    A LOP that authors an animated value at the current frame writes a time
    sample, and a static one writes a default, so a sample on a parent's
    transform means the parent may move across the shot. The live stage holds
    one frame of that, so the camera's world path cannot be read from it."""
    from pxr import UsdGeom
    prim = cam_prim.GetParent()
    while prim and prim.IsValid() and not prim.IsPseudoRoot():
        xformable = UsdGeom.Xformable(prim)
        if xformable:
            for op in xformable.GetOrderedXformOps():
                if op.GetAttr().GetNumTimeSamples() > 0:
                    return str(prim.GetPath())
        prim = prim.GetParent()
    return None


def _geometry(stage, now: float, against: str, skip: Tuple[str, ...], n_frames: int):
    """World-space points to measure against, with what they are.

    Returns ``(points, metric, measured, not_measured)``. Splat centres come
    first in ``auto``: they are dense, so the nearest one is a tight figure,
    while a mesh is measured at its vertices and a coarse mesh overstates the
    clearance. Point-instancer prototypes are not scene geometry and are left
    out; the instances themselves are not measured, and the result says so.
    """
    import numpy as np
    from pxr import Usd, UsdGeom

    if against == "none":
        return None, None, None, []
    xf = UsdGeom.XformCache(Usd.TimeCode(now))
    prototypes: List[str] = []
    found = {"splats": [], "mesh": [], "other": []}
    for prim in Usd.PrimRange(stage.GetPseudoRoot(), Usd.TraverseInstanceProxies()):
        type_name = prim.GetTypeName()
        if type_name == "PointInstancer":
            prototypes += [str(t) for t in UsdGeom.PointInstancer(prim).GetPrototypesRel().GetTargets()]
        elif type_name == SPLAT_TYPE:
            found["splats"].append(prim)
        elif type_name == "Mesh":
            found["mesh"].append(prim)
        elif prim.IsA(UsdGeom.Gprim):
            found["other"].append(prim)

    def under(path, roots):
        return any(path == r or path.startswith(r + "/") for r in roots)

    sampled: Dict[str, bool] = {}

    def moves(prim, attr) -> bool:
        """Time samples on the points, or on a transform at or above the prim."""
        if attr.GetNumTimeSamples() > 0:
            return True
        walk = prim
        while walk and walk.IsValid() and not walk.IsPseudoRoot():
            key = str(walk.GetPath())
            if key not in sampled:
                xformable = UsdGeom.Xformable(walk)
                sampled[key] = bool(xformable) and any(
                    op.GetAttr().GetNumTimeSamples() > 0 for op in xformable.GetOrderedXformOps())
            if sampled[key]:
                return True
            walk = walk.GetParent()
        return False

    def collect(kind):
        chunks, paths, moving = [], [], 0
        for prim in found[kind]:
            path = str(prim.GetPath())
            if under(path, skip) or under(path, prototypes):
                continue
            attr = (prim.GetAttribute(SPLAT_POSITIONS) if kind == "splats"
                    else UsdGeom.Mesh(prim).GetPointsAttr())
            value = attr.Get(Usd.TimeCode(now)) if attr else None
            if value is None or len(value) == 0:
                continue
            local = np.asarray(value, dtype=float).reshape(-1, 3)
            world = _np(xf.GetLocalToWorldTransform(prim))
            chunks.append(local @ world[:3, :3] + world[3, :3])
            paths.append(path)
            moving += 1 if moves(prim, attr) else 0
        return (np.concatenate(chunks) if chunks else None), paths, moving

    points, paths, kind, moving = None, [], None, 0
    for candidate in (("splats", "mesh") if against == "auto" else (against,)):
        points, paths, moving = collect(candidate)
        if points is not None:
            kind = candidate
            break
    not_measured: List[str] = []
    if moving:
        not_measured.append("the motion of %d measured prim%s (read where %s at frame %s)" % (
            moving, "" if moving == 1 else "s", "it is" if moving == 1 else "they are",
            spatial_path._fmt_frame(now)))
    shapes = [p for p in found["other"]
              if not under(str(p.GetPath()), skip) and not under(str(p.GetPath()), prototypes)]
    if shapes:
        not_measured.append("%d shape prim%s that %s not a mesh" % (
            len(shapes), "" if len(shapes) == 1 else "s", "is" if len(shapes) == 1 else "are"))
    if kind == "splats" and against == "auto":
        other = [p for p in found["mesh"]
                 if not under(str(p.GetPath()), skip) and not under(str(p.GetPath()), prototypes)]
        if other:
            not_measured.append("%d mesh prim%s (pass against=mesh)"
                                % (len(other), "" if len(other) == 1 else "s"))
    if prototypes:
        not_measured.append("point-instancer instances")
    if points is None:
        return None, None, None, not_measured
    measured = {"kind": kind, "prims": len(paths), "first": paths[:3], "points": int(len(points)),
                "at_frame": now}
    budget = max(1, MAX_PAIRS // max(1, n_frames))
    if len(points) > budget:
        stride = int(math.ceil(len(points) / budget))
        measured["thinned"] = "every %dth point measured, to stay inside the time budget" % stride
        points = points[::stride]
    metric = spatial_path.POINT_METRIC if kind == "splats" else spatial_path.MESH_METRIC
    return points, metric, measured, not_measured


def measure(node_path=None, camera=None, frames_spec=None, against="auto"):
    """The read. Returns (tool result, context for the trail). Main thread only."""
    import numpy as np
    from pxr import Usd, UsdGeom

    t0 = time.perf_counter()
    if against not in AGAINST:
        raise SynapseUserError("against must be one of: %s" % ", ".join(AGAINST))
    node = _stage_node(node_path)
    stage = node.stage()
    if stage is None:
        raise SynapseUserError("%s has no USD stage yet" % node.path(),
                               suggestion="It may need to cook, or its input may be in error")

    asked_node = None
    if camera is not None and str(camera).strip():
        prim_path, asked_node = _resolve_camera(stage, node, camera)
    else:
        prim_path = _render_camera(stage)
        if prim_path is None:
            raise SynapseUserError("The stage at %s has no camera" % node.path())
    cam_prim = stage.GetPrimAtPath(prim_path)
    if not cam_prim.IsValid():
        raise SynapseUserError("%s is not on the stage at %s" % (prim_path, node.path()))
    if cam_prim.GetTypeName() != "Camera":
        raise SynapseUserError("%s is a %s, not a camera" % (prim_path, cam_prim.GetTypeName() or "typeless prim"))
    lops = _camera_lops(node, prim_path)
    if asked_node is not None and not any(lop.path() == asked_node.path() for lop in lops):
        raise SynapseUserError(
            "%s is bypassed, or does not feed %s" % (asked_node.path(), node.path()),
            suggestion="Pass the camera's prim path, or the node whose stage should be read")
    cam_node = lops[0] if len(lops) == 1 else None

    now = float(hou.frame())
    frames = parse_frames(frames_spec, hou.hscriptExpression("$FSTART"),
                          hou.hscriptExpression("$FEND"))
    mpu = float(UsdGeom.GetStageMetersPerUnit(stage)) or 1.0
    up_index = 2 if str(UsdGeom.GetStageUpAxis(stage)).upper() == "Z" else 1

    move: Dict[str, Any]
    cam = None
    check = None
    if len(lops) > 1:
        move = {"status": spatial_path.STATUS_UNKNOWN,
                "reason": "%d Camera LOPs upstream of %s author %s (%s), and which one the "
                          "stage holds on each frame can't be read from here"
                          % (len(lops), node.path(), prim_path,
                             ", ".join(sorted(lop.path() for lop in lops)[:4]))}
    elif cam_node is None:
        move = {"status": spatial_path.STATUS_UNKNOWN,
                "reason": "no Camera LOP at or upstream of %s authors %s, so its move "
                          "can't be read without moving the playhead" % (node.path(), prim_path)}
    else:
        unreadable = _unreadable(node, cam_node, cam_prim)
        mode_parm = cam_node.parm(_XFORM_MODE_PARM)
        mode = mode_parm.evalAsString() if mode_parm is not None else ""
        parent = _np(UsdGeom.XformCache(Usd.TimeCode(now)).GetLocalToWorldTransform(cam_prim.GetParent()))

        def world(frame):
            local = _parm_local(cam_node, frame)
            return local if mode == "world" else local @ parent

        here = world(now)
        actual = _np(UsdGeom.Xformable(cam_prim).ComputeLocalToWorldTransform(Usd.TimeCode(now)))
        err_mm = float(np.linalg.norm(here[3, :3] - actual[3, :3])) * mpu * 1000.0
        err_deg = _rotation_deg(here, actual)
        # How far the composed stage is from the parm route at this one frame.
        # Named for what the numbers are: under UNKNOWN they are the mismatch.
        check = {"frame": now, "agrees": err_mm <= CHECK_MM and err_deg <= CHECK_DEG,
                 "position_off_mm": round(err_mm, 3), "rotation_off_deg": round(err_deg, 4)}
        if unreadable is not None:
            move = {"status": spatial_path.STATUS_UNKNOWN, "reason": unreadable}
        elif not check["agrees"]:
            move = {"status": spatial_path.STATUS_UNKNOWN,
                    "reason": "something after %s also moves the camera: at frame %s the stage "
                              "is %.1f mm and %.2f deg from the Camera LOP's own transform"
                              % (cam_node.path(), spatial_path._fmt_frame(now), err_mm, err_deg)}
        else:
            cam = spatial_path.camera_frames([world(f) for f in frames])
            move = spatial_path.summarize_move(frames, cam, up_index=up_index, meters_per_unit=mpu)

    clear = None
    if cam is not None and against != "none":
        points, metric, measured, not_measured = _geometry(
            stage, now, against, (TRAIL_PARENT, prim_path), len(frames))
        if points is None:
            clear = {"status": spatial_path.STATUS_UNKNOWN,
                     "reason": "no %s on the stage to measure against" % _NOTHING_FOUND[against]}
        else:
            clear = spatial_path.clearance(frames, cam, points, meters_per_unit=mpu, metric=metric)
            clear["measured"] = measured
        if not_measured:
            clear["not_measured"] = not_measured

    move_fields = dict(move.get("move", {}))
    move_fields.pop("class_thresholds", None)
    at = spatial_path._fmt_frame(now)
    if cam is not None:
        method = ("Camera LOP parms evaluated per frame (no playhead move); composed stage "
                  "confirmed at frame %s only; scene geometry read at that frame" % at)
    elif check is not None:
        method = ("Camera LOP parms compared with the composed stage at frame %s only; "
                  "no path was measured" % at)
    else:
        method = "the composed stage read at frame %s only; no path was measured" % at
    result = {
        "status": move.get("status"),
        "outcome": spatial_path.outcome_line(prim_path, move, clear),
        "camera": prim_path,
        "camera_node": cam_node.path() if cam_node is not None else None,
        "node": node.path(),
        # sampled is what was measured: nothing, when the move is UNKNOWN.
        "frames": {"start": frames[0], "end": frames[-1],
                   "sampled": len(frames) if cam is not None else 0},
        "move": move_fields or {"status": move.get("status"), "reason": move.get("reason")},
        "clearance": clear,
        "stage_check": check,
        "seconds": round(time.perf_counter() - t0, 3),
        "provenance": _provenance(method),
    }
    context = {"node": node, "cam": cam, "frames": frames, "mpu": mpu, "camera": prim_path}
    return result, context


def _is_trail(node) -> Optional[str]:
    """The code of ``node`` when it is a trail SYNAPSE wrote, else None."""
    if node is None or node.type().nameComponents()[2] != "pythonscript":
        return None
    parm = node.parm("python")
    text = parm.unexpandedString() if parm is not None else ""
    return text if text.startswith(TRAIL_HEADER) else None


def _trail_above(node, camera: str):
    """The trail SYNAPSE already wrote for this camera, anywhere upstream of
    ``node``. Trails for other cameras, and nodes an artist has since put
    between the trail and ``node``, are stepped over."""
    header = "%s of %s," % (TRAIL_HEADER, camera)
    for up in node.inputAncestors():
        text = _is_trail(up)
        if text is not None and text.startswith(header):
            return up
    return None


def _free_name(parent, base: str) -> str:
    name, n = base, 1
    while parent.node(name) is not None:
        n += 1
        name = "%s%d" % (base, n)
    return name


def _karma_purposes(stage) -> Optional[List[str]]:
    """The purposes the stage's render settings include; None with no settings."""
    from pxr import UsdRender
    prim = None
    named = stage.GetMetadata("renderSettingsPrimPath") if stage.HasAuthoredMetadata(
        "renderSettingsPrimPath") else None
    if named:
        prim = stage.GetPrimAtPath(named)
    if prim is None or not prim.IsValid():
        prim = next((p for p in stage.Traverse() if p.GetTypeName() == "RenderSettings"), None)
    if prim is None:
        return None
    value = UsdRender.Settings(prim).GetIncludedPurposesAttr().Get()
    return [str(v) for v in value] if value else ["default", "render"]


def _trail_on_stage(node, prim_path: str, purpose: str) -> Dict[str, Any]:
    """Read the trail back from the node's stage: what is there, not what was asked for."""
    from pxr import UsdGeom
    stage = node.stage()
    prim = stage.GetPrimAtPath(prim_path) if stage is not None else None
    ok = bool(prim is not None and prim.IsValid() and prim.GetTypeName() == "BasisCurves")
    purposes = _karma_purposes(stage) if stage is not None else None
    return {
        "prim": prim_path if ok else None,
        "points": len(UsdGeom.BasisCurves(prim).GetPointsAttr().Get() or []) if ok else None,
        "purpose": str(UsdGeom.Imageable(prim).ComputePurpose()) if ok else None,
        "karma_leaves_it_out": (purpose not in purposes) if purposes is not None else None,
    }


def _withdraw(parent, name: str, node, up, positions) -> bool:
    """Take a trail node that did not work back out: the node, the wire, and
    the places of the nodes the splice moved (``positions``, taken before it).

    ``name`` did not exist before this call, so a node by that name is this
    call's own. Returns whether there was anything to take out (build_graph may
    already have rolled its own build back). Never raises: the caller is about
    to raise the error that matters, and a failure here is logged."""
    try:
        trail = parent.node(name)
        if trail is None:
            return False
        current = node.input(0)
        if current is not None and current.path() == trail.path():
            node.setInput(0, up)
        trail.destroy()
        for child in parent.children():
            before = positions.get(child.path())
            if before is not None and child.position() != before:
                child.setPosition(before)
        return True
    except Exception as exc:  # noqa: BLE001 -- the original error is the one to report
        logger.warning("spatial_trail: could not take %s back out of %s: %s",
                       name, parent.path(), exc)
        return False


class SpatialHandlerMixin:
    """get_spatial_path (read) and spatial_trail (one build)."""

    def _handle_get_spatial_path(self, payload: Dict) -> Dict:
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        node_path = resolve_param(payload, "node", required=False)
        camera = payload.get("camera")
        frames = payload.get("frames")
        against = payload.get("against") or "auto"

        from .main_thread import run_on_main

        def _on_main():
            result, _context = measure(node_path, camera, frames, against)
            return result

        return run_on_main(_on_main, label="spatial:get_spatial_path")

    def _handle_spatial_trail(self, payload: Dict) -> Dict:
        if not HOU_AVAILABLE:
            raise HoudiniUnavailableError()
        node_path = resolve_param(payload, "node", required=False)
        camera = payload.get("camera")
        frames = payload.get("frames")
        purpose = payload.get("purpose") or "proxy"
        if purpose not in PURPOSES:
            raise SynapseUserError("purpose must be one of: %s" % ", ".join(PURPOSES))

        from .main_thread import run_on_main, _SLOW_TIMEOUT

        # One main-thread visit: measure, write, read back. Everything it
        # changes sits in one undo group, and a write that does not end with
        # the path on the stage is taken back out before the error is raised.
        # build_graph's own rollback cannot be relied on here: it undoes only
        # when its group reaches the undo stack, and under this group (or the
        # panel bridge's) it never does until the outer group closes.
        def _on_main():
            result, ctx = measure(node_path, camera, frames, "auto")
            if ctx["cam"] is None:
                raise SynapseUserError("No trail drawn: " + str(result["move"].get("reason")))
            node = ctx["node"]
            leaf = ctx["camera"].rsplit("/", 1)[-1] or "camera"
            prim_path = "%s/%s_path" % (TRAIL_PARENT, leaf)
            try:
                code = spatial_path.trail_code(prim_path, ctx["frames"], ctx["cam"],
                                               camera=ctx["camera"], meters_per_unit=ctx["mpu"],
                                               purpose=purpose)
            except ValueError as exc:       # one sample, or a prim name the code cannot carry
                raise SynapseUserError("No trail drawn: %s" % exc)
            errors_before = tuple(node.errors())

            def observed():
                """The stage read back, and any error the node did not have before."""
                seen = _trail_on_stage(node, prim_path, purpose)
                new_errors = [str(e) for e in node.errors() if e not in errors_before]
                if new_errors:
                    return seen, "%s reported an error with the trail above it: %s" % (
                        node.path(), "; ".join(new_errors[:2]))
                if not seen["prim"]:
                    return seen, "%s is not on the stage at %s" % (prim_path, node.path())
                return seen, None

            existing = _trail_above(node, ctx["camera"])
            if existing is not None:
                parm = existing.parm("python")
                before, hidden = parm.unexpandedString(), existing.isBypassed()
                if before == code and not hidden:
                    built = {"status": "unchanged", "node": existing.path()}
                    check, problem = observed()
                else:
                    with hou.undos.group(TRAIL_UNDO):
                        parm.set(code)
                        if hidden:                      # asked to see it: a bypassed trail draws nothing
                            existing.bypass(False)
                        check, problem = observed()
                        if problem:
                            parm.set(before)
                            if hidden:
                                existing.bypass(True)
                    built = {"status": "updated", "node": existing.path()}
                if problem:
                    raise SynapseUserError(
                        "The trail was not redrawn: " + problem,
                        suggestion="%s was left as it was" % existing.path())
            else:
                up = node.input(0)
                if up is None:
                    raise SynapseUserError(
                        "No trail drawn: %s has no input to splice the trail above" % node.path(),
                        suggestion="Pass the node the trail should sit above; "
                                   "the display flag is never moved")
                parent = node.parent()
                if up.parent() != parent:
                    raise SynapseUserError(
                        "No trail drawn: %s is wired from outside its own network" % node.path())
                name = _free_name(parent, _safe_node_name(leaf + "_path", "camera_path"))
                positions = {child.path(): child.position() for child in parent.children()}
                with hou.undos.group(TRAIL_UNDO):
                    try:
                        build = self._handle_solaris_build_graph({  # type: ignore[attr-defined]
                            "parent": parent.path(),
                            "nodes": [{"id": "up", "existing": True, "path": up.path()},
                                      {"id": "trail", "type": "pythonscript", "name": name,
                                       "parms": {"python": code}},
                                      {"id": "down", "existing": True, "path": node.path()}],
                            "connections": [{"from": "up", "to": "trail"},
                                            {"from": "trail", "to": "down", "input": 0,
                                             "insert": True}],
                            # One guide node is not a section of the network, and
                            # drawing sections sweeps the boxes earlier builds made.
                            "sections": False,
                        })
                        made = [entry.get("path") for entry in build.get("nodes_created", [])
                                if entry.get("id") == "trail"]
                        if not made or build.get("parms_missed"):
                            raise SynapseUserError(
                                "The trail was not drawn: the build did not write the trail's "
                                "node (%s)" % (build.get("parms_missed") or build.get("status")))
                        check, problem = observed()
                        if problem:
                            raise SynapseUserError("The trail was not drawn: " + problem)
                    except Exception:
                        _withdraw(parent, name, node, up, positions)
                        raise
                built = {"status": "created", "node": made[0]}
                if build.get("warnings"):
                    built["warnings"] = build["warnings"]

            result["trail"] = dict(built, **check)
            if built["status"] != "unchanged":
                # A write that fails is taken back out above, so the receipt says so.
                result.update(undo_receipt(TRAIL_UNDO, rolls_back_on_failure=True))
            verb = {"created": "Drew the path as", "updated": "Redrew the path as",
                    "unchanged": "The path is already drawn as"}[built["status"]]
            result["outcome"] += (" %s %s (%s purpose, %d points)%s."
                                  % (verb, prim_path, check["purpose"], check["points"],
                                     "; Karma's render settings leave it out"
                                     if check["karma_leaves_it_out"] else ""))
            return result

        return run_on_main(_on_main, timeout=_SLOW_TIMEOUT, label="spatial:spatial_trail")
