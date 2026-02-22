# Camera Workflows in Solaris

## Triggers
camera, focal length, depth of field, fStop, motion blur, aperture, sensor,
turntable, look at, camera animation, shutter, clipping, multi camera, DOF

## Context
Camera setup and animation in Houdini 21 Solaris for Karma rendering.
Covers camera creation, DOF, motion blur, turntable, multi-camera workflows,
and batch rendering with TOPS.

## Code

```python
# Create and configure a camera in Solaris
import hou

def create_solaris_camera(
    parent="/stage",
    name="render_cam",
    focal_length=50.0,
    sensor_width=36.0,
    near_clip=0.1,
    far_clip=10000.0,
    position=(0, 1.5, 5),
):
    """Create a camera LOP with standard settings.
    focalLength in mm: 14-24=ultra-wide, 24-35=wide, 35-50=normal,
    50-85=portrait, 85-135=telephoto, 135+=long tele.
    Sensor width 36mm = full frame (default)."""
    stage = hou.node(parent)
    if not stage:
        return

    cam = stage.createNode("camera", name)
    cam.parm("focalLength").set(focal_length)
    cam.parm("horizontalAperture").set(sensor_width)
    # Vertical aperture auto-calculated from aspect ratio
    cam.parm("verticalAperture").set(sensor_width * 9.0 / 16.0)  # 16:9

    # Clipping range
    cam.parm("clippingRange1").set(near_clip)
    cam.parm("clippingRange2").set(far_clip)

    # Position via edit node
    edit = stage.createNode("edit", f"{name}_xform")
    edit.setInput(0, cam)
    edit.parm("primpath").set(f"/cameras/{name}")
    edit.parm("tx").set(position[0])
    edit.parm("ty").set(position[1])
    edit.parm("tz").set(position[2])

    stage.layoutChildren()
    print(f"Camera created: /cameras/{name} (focal={focal_length}mm)")
    return cam, edit


# Focal length reference table
FOCAL_LENGTH_GUIDE = {
    "ultra_wide":    (14, 24, "Environments, architecture, establishing shots"),
    "wide":          (24, 35, "Interior scenes, landscapes"),
    "normal":        (35, 50, "General purpose, natural perspective"),
    "portrait":      (50, 85, "Characters, product shots, close-ups"),
    "telephoto":     (85, 135, "Tight close-ups, compressed depth"),
    "long_tele":     (135, 200, "Extreme compression, distant subjects"),
}

create_solaris_camera(focal_length=50, position=(0, 1.5, 5))
```

```python
# Depth of Field setup
import hou

def configure_dof(
    cam_node_path,
    f_stop=5.6,
    focus_distance=3.0,
):
    """Configure depth of field on a camera.
    fStop=0 disables DOF (default). Lower fStop = shallower DOF.
      Product shot: 2.0-4.0 (shallow, subject isolated)
      Portrait: 2.8-5.6 (moderate blur)
      Landscape: 8.0-16.0 (nearly everything sharp)
      Miniature/tilt-shift: 1.4-2.0 (extremely shallow)
    """
    node = hou.node(cam_node_path)
    if not node:
        return

    # Set via USD-encoded parm names on the camera prim
    # fStop: 0 = no DOF, non-zero enables it
    if node.parm("fStop"):
        node.parm("fStop").set(f_stop)
    if node.parm("focusDistance"):
        node.parm("focusDistance").set(focus_distance)

    print(f"DOF: fStop={f_stop}, focusDistance={focus_distance}")
    print(f"  Blur circle ~ 1/{f_stop:.0f} of sensor width")

configure_dof("/stage/render_cam", f_stop=2.8, focus_distance=3.0)
```

```python
# Motion blur configuration
import hou

def configure_motion_blur(
    karma_props_path,
    shutter_open=-0.5,
    shutter_close=0.5,
    xform_samples=2,
    geo_samples=2,
    vel_blur=True,
):
    """Configure motion blur on Karma render properties.
    Shutter settings:
      (0.0, 1.0)   = forward blur (trails forward from position)
      (-0.5, 0.5)   = centered blur (symmetric, MOST COMMON for VFX)
      (-1.0, 0.0)   = backward blur (trails backward)
    xform_samples: 2+ for transform motion blur (position/rotation/scale)
    geo_samples: 2+ for deformation blur (cloth, muscle, waves)
    """
    node = hou.node(karma_props_path)
    if not node:
        return

    # Shutter open/close
    if node.parm("karma_shutteropen"):
        node.parm("karma_shutteropen").set(shutter_open)
    if node.parm("karma_shutterclose"):
        node.parm("karma_shutterclose").set(shutter_close)

    # Transform motion blur samples
    if node.parm("karma_xformsamples"):
        node.parm("karma_xformsamples").set(xform_samples)

    # Deformation motion blur samples
    if node.parm("karma_geosamples"):
        node.parm("karma_geosamples").set(geo_samples)

    # Velocity-based blur (use v@v attribute if available)
    if vel_blur and node.parm("karma_geovelblur"):
        node.parm("karma_geovelblur").set(1)

    print(f"Motion blur: shutter=[{shutter_open}, {shutter_close}]")
    print(f"  xform samples={xform_samples}, geo samples={geo_samples}")

configure_motion_blur("/stage/karmarenderproperties1")
```

```python
# Turntable camera animation
import hou
import math

def create_turntable(
    parent="/stage",
    radius=5.0,
    height=1.5,
    frame_count=120,
    target=(0, 0, 0),
    name="turntable_cam",
    focal_length=50.0,
):
    """Create an orbiting turntable camera for asset review.
    Orbits around target at given radius over frame_count frames."""
    stage = hou.node(parent)
    if not stage:
        return

    cam = stage.createNode("camera", name)
    cam.parm("focalLength").set(focal_length)

    edit = stage.createNode("edit", f"{name}_orbit")
    edit.setInput(0, cam)
    edit.parm("primpath").set(f"/cameras/{name}")

    # Keyframe orbit: one revolution over frame_count frames
    for frame in range(1, frame_count + 1):
        angle = (frame / float(frame_count)) * 2.0 * math.pi
        x = target[0] + radius * math.cos(angle)
        z = target[2] + radius * math.sin(angle)

        kf_tx = hou.Keyframe(frame, x)
        kf_ty = hou.Keyframe(frame, height + target[1])
        kf_tz = hou.Keyframe(frame, z)
        edit.parm("tx").setKeyframe(kf_tx)
        edit.parm("ty").setKeyframe(kf_ty)
        edit.parm("tz").setKeyframe(kf_tz)

        # Look at target: compute rotation
        dx = target[0] - x
        dz = target[2] - z
        ry = -math.degrees(math.atan2(dx, dz))
        kf_ry = hou.Keyframe(frame, ry)
        edit.parm("ry").setKeyframe(kf_ry)

    stage.layoutChildren()
    print(f"Turntable: {frame_count} frames, radius={radius}, height={height}")
    return cam, edit


create_turntable(radius=5.0, height=1.5, frame_count=120)
```

```python
# Look-at constraint for camera
import hou

def setup_look_at(parent="/stage", cam_prim="/cameras/render_cam", target_prim="/World/hero"):
    """Point camera at a target prim using constraintlookat LOP."""
    stage = hou.node(parent)
    if not stage:
        return

    lookat = stage.createNode("constraintlookat", "cam_lookat")
    lookat.parm("primpath").set(cam_prim)
    lookat.parm("targetprimpath").set(target_prim)
    # Up axis = Y
    lookat.parm("upvectorx").set(0)
    lookat.parm("upvectory").set(1)
    lookat.parm("upvectorz").set(0)

    print(f"Look-at: {cam_prim} -> {target_prim}")
    return lookat

setup_look_at()
```

```python
# Multi-camera setup and batch rendering
import hou

def setup_multi_camera(parent="/stage"):
    """Create a multi-camera rig for production.
    /cameras/render_cam    -- hero camera for final render
    /cameras/turntable_cam -- orbiting asset review
    /cameras/closeup_cam   -- detail shot
    /cameras/wide_cam      -- establishing shot
    """
    stage = hou.node(parent)
    if not stage:
        return

    cameras = {
        "render_cam":    {"focal": 50, "pos": (0, 1.5, 5)},
        "closeup_cam":   {"focal": 85, "pos": (0, 1.2, 2)},
        "wide_cam":      {"focal": 24, "pos": (5, 3, 10)},
    }

    nodes = []
    last = None
    for name, cfg in cameras.items():
        cam = stage.createNode("camera", name)
        cam.parm("focalLength").set(cfg["focal"])
        if last:
            cam.setInput(0, last)
        last = cam

        edit = stage.createNode("edit", f"{name}_xform")
        edit.setInput(0, cam)
        edit.parm("primpath").set(f"/cameras/{name}")
        edit.parm("tx").set(cfg["pos"][0])
        edit.parm("ty").set(cfg["pos"][1])
        edit.parm("tz").set(cfg["pos"][2])
        last = edit
        nodes.append((cam, edit))

    stage.layoutChildren()
    print(f"Created {len(cameras)} cameras")
    return nodes


def switch_render_camera(rop_path, camera_prim):
    """Switch the render camera on a usdrender ROP.
    camera_prim must be USD prim path, NOT Houdini node path.
    Example: /cameras/closeup_cam (not /stage/closeup_cam)"""
    rop = hou.node(rop_path)
    if not rop:
        return
    rop.parm("camera").set(camera_prim)
    print(f"Render camera: {camera_prim}")


# Batch render all cameras via TOPS/PDG:
# 1. Wedge TOP with camera paths as work item attribute
# 2. ROP Fetch TOP reads camera from wedge attribute
# 3. Cook TOP network -- renders all cameras in parallel
setup_multi_camera()
switch_render_camera("/out/usdrender1", "/cameras/closeup_cam")
```

```python
# Camera animation via USD API
import hou
from pxr import UsdGeom, Gf, Usd

def animate_camera_usd(stage_node_path, cam_prim_path, keyframes):
    """Animate camera position via USD API.
    keyframes: list of (frame, (tx, ty, tz)) tuples.
    """
    node = hou.node(stage_node_path)
    if not node or not hasattr(node, 'editableStage'):
        return

    stage = node.editableStage()
    cam = stage.GetPrimAtPath(cam_prim_path)
    if not cam:
        print(f"Camera not found: {cam_prim_path}")
        return

    xform = UsdGeom.Xformable(cam)
    translate_op = xform.AddTranslateOp()

    for frame, (tx, ty, tz) in keyframes:
        translate_op.Set(Gf.Vec3d(tx, ty, tz), Usd.TimeCode(frame))

    print(f"Animated {cam_prim_path}: {len(keyframes)} keyframes")


# Example: dolly push from wide to close
animate_camera_usd("/stage/python1", "/cameras/render_cam", [
    (1,   (0, 1.5, 10)),   # Start: wide
    (48,  (0, 1.5, 5)),    # Mid: medium
    (96,  (0, 1.3, 2.5)),  # End: close-up
])
```

## Common Mistakes
- Using fStop=0 and expecting DOF -- fStop=0 DISABLES depth of field entirely
- Setting camera to Houdini node path instead of USD prim path -- Karma needs `/cameras/render_cam`
- Not enabling geo_samples for deformation blur -- only xform_samples captures rigid motion
- Shutter (-0.5, 0.5) centered blur is standard for VFX -- (0, 1) forward blur looks different
- Near clip too far (>1.0) -- clips geometry near camera; keep at 0.1 for most scenes
- Forgetting to set focusDistance when enabling DOF -- auto-focus (0) may focus on wrong object
- Using orthographic camera for Karma -- no perspective, no DOF, usually wrong for VFX renders
