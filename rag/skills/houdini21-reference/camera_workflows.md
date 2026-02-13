# Camera Workflows in Solaris

## Camera Types

| Type | Use Case | Notes |
|------|----------|-------|
| Standard perspective | Most shots | Focal length controls FOV |
| Orthographic | Technical/isometric views | No perspective distortion |
| Stereo rig | VR/3D stereo | Dual cameras with eye separation |

## Essential Parameters

| Parameter | USD Name | Default | Notes |
|-----------|----------|---------|-------|
| Focal length | `focalLength` | 50.0 | In mm. Lower = wider, higher = tighter |
| Horizontal aperture | `horizontalAperture` | 36.0 | Sensor width in mm (36 = full frame) |
| Vertical aperture | `verticalAperture` | 24.0 | Sensor height in mm |
| F-stop | `fStop` | 0.0 | 0 = no DOF. Lower = shallower DOF |
| Focus distance | `focusDistance` | 0.0 | In scene units. 0 = auto |
| Near clip | `clippingRange[0]` | 0.1 | Minimum render distance |
| Far clip | `clippingRange[1]` | 10000 | Maximum render distance |

## Focal Length Cheat Sheet

| Focal Length | Field of View | Best For |
|-------------|---------------|----------|
| 14-24mm | Ultra-wide | Environments, architecture, establishing shots |
| 24-35mm | Wide | Interior scenes, landscapes |
| 35-50mm | Normal | General purpose, natural perspective |
| 50-85mm | Portrait | Characters, product shots, close-ups |
| 85-135mm | Telephoto | Tight close-ups, compressed depth |
| 135-200mm+ | Long telephoto | Extreme compression, distant subjects |

## Depth of Field

### Setup

1. Set `fStop` to a non-zero value (e.g., 2.8, 5.6, 11)
2. Set `focusDistance` to the distance of your subject
3. Lower fStop = more blur (shallower DOF)

### Quick Reference

| Scenario | fStop | Notes |
|----------|-------|-------|
| Sharp everywhere | 0 (disabled) | Default, no DOF |
| Product shot | 2.0-4.0 | Shallow, subject isolated |
| Portrait | 2.8-5.6 | Moderate blur |
| Landscape | 8.0-16.0 | Nearly everything sharp |
| Miniature/tilt-shift | 1.4-2.0 | Extremely shallow |

### Bokeh

Bokeh shape is controlled by the aperture blade count. Karma uses circular bokeh by default. For polygonal bokeh (hexagonal, octagonal), render delegate settings may apply.

## Motion Blur

### Transform Motion Blur (Object-Level)

Captures position/rotation/scale changes between frames:
```
karma:object:xformsamples: 2    # Minimum for motion blur
```

### Deformation Motion Blur (Vertex-Level)

Captures per-vertex animation (cloth, muscle, waves):
```
karma:object:geosamples: 2      # Minimum for deformation blur
karma:object:geovelblur: 1      # Use velocity attribute if available
```

### Shutter Settings

| Setting | Value | Effect |
|---------|-------|--------|
| Shutter open: 0.0, close: 1.0 | Forward blur | Motion trails forward from position |
| Shutter open: -0.5, close: 0.5 | Centered blur | Symmetric around frame position |
| Shutter open: -1.0, close: 0.0 | Backward blur | Motion trails backward |

Centered blur (-0.5, 0.5) is most common for VFX.

## Camera Animation

### Keyframing in LOPs

Use the `Edit` LOP to animate camera transforms:
```python
# Create keyframes via Python
cam = stage.GetPrimAtPath("/World/cameras/render_cam")
xform = UsdGeom.Xformable(cam)
translate_op = xform.AddTranslateOp()

# Key at frame 1
translate_op.Set(Gf.Vec3d(0, 1, 10), Usd.TimeCode(1))
# Key at frame 100
translate_op.Set(Gf.Vec3d(5, 2, 5), Usd.TimeCode(100))
```

### Turntable Pattern

Standard orbit camera for asset review:
```python
# Orbit at radius 5, height 1.5, over 120 frames
import math
for frame in range(1, 121):
    angle = (frame / 120.0) * 2 * math.pi
    x = 5.0 * math.cos(angle)
    z = 5.0 * math.sin(angle)
    translate_op.Set(Gf.Vec3d(x, 1.5, z), Usd.TimeCode(frame))
```

### Look-At Constraint

Point camera at a target:
```python
from pxr import Gf

cam_pos = Gf.Vec3d(5, 3, 5)
target = Gf.Vec3d(0, 1, 0)
up = Gf.Vec3d(0, 1, 0)

# Compute rotation matrix
forward = (target - cam_pos).GetNormalized()
right = Gf.Cross(forward, up).GetNormalized()
new_up = Gf.Cross(right, forward)

# Build 4x4 matrix and extract rotation
```

In Houdini, use a `Look At` constraint LOP or the `constraintlookat` node.

## Multi-Camera Workflows

### Setting Up Multiple Cameras

```
/World/cameras/
    render_cam      (hero camera for final render)
    turntable_cam   (orbiting asset review)
    closeup_cam     (detail shot)
    wide_cam        (establishing shot)
```

### Switching Cameras for Render

On the `usdrender` ROP:
- `camera` parameter: Set to the USD prim path of the desired camera
- Example: `/World/cameras/closeup_cam`

### Batch Rendering All Cameras

Use TOPS/PDG to render all cameras:
1. Create a Wedge TOP with camera paths as attributes
2. Wire to a ROP Fetch TOP that reads the camera from the wedge attribute
3. Cook the TOP network — renders all cameras in parallel

## Composition Guidelines

### Rule of Thirds
Position key elements at the intersection of thirds grid lines. In Houdini, enable viewport guides: **Display > Composition Guides > Rule of Thirds**.

### Head Room
Leave space above the subject's head. Too little = cramped, too much = empty.

### Lead Room
When a character looks or moves in a direction, leave space in that direction.

### Framing Depth
Use foreground, midground, and background elements to create depth. Lower f-stop separates these layers with DOF.
