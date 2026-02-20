# Camera Sensor Database for USD/Solaris

## Triggers
camera sensor, aperture, horizontal aperture, vertical aperture, focal length,
arri alexa, red, sony venice, blackmagic, canon, crop factor, fov, gate fit,
sensor size, usd camera

## Context
Production camera bodies mapped to USD camera parameters for accurate FOV matching
in Houdini 21 Solaris. All code is Houdini Python and USD API.

## Code

```python
# Camera sensor database: real camera bodies to USD parameters
import hou

CAMERA_SENSORS = {
    "arri_alexa_35": {
        "sensor_mm": (27.99, 19.22),
        "max_res": (4608, 3164),
        "format": "Super 35",
        "color_science": "ARRI LogC4 / Wide Gamut 4",
        "dynamic_range": 17,
        "gate_fit": "horizontal",
        "common_primes": [18, 25, 32, 40, 50, 65, 75, 100],
    },
    "arri_alexa_mini_lf": {
        "sensor_mm": (36.70, 25.54),
        "max_res": (4448, 3096),
        "format": "Large Format",
        "color_science": "ARRI LogC3 / Wide Gamut 3",
        "dynamic_range": 14,
        "gate_fit": "horizontal",
        "common_primes": [25, 29, 35, 40, 47, 58, 75, 95, 125],
    },
    "red_v_raptor_x": {
        "sensor_mm": (40.96, 21.60),
        "max_res": (8192, 4320),
        "format": "VV (VistaVision+)",
        "color_science": "REDWideGamutRGB / Log3G10",
        "dynamic_range": 17,
        "gate_fit": "horizontal",
        "common_primes": [24, 35, 50, 85, 100],
    },
    "red_komodo_x": {
        "sensor_mm": (27.03, 14.26),
        "max_res": (6144, 3240),
        "format": "Super 35",
        "color_science": "REDWideGamutRGB / Log3G10",
        "dynamic_range": 16.5,
        "gate_fit": "horizontal",
        "common_primes": [24, 35, 50, 85],
    },
    "sony_venice_2": {
        "sensor_mm": (36.20, 24.10),
        "max_res": (8640, 5760),
        "format": "Full Frame",
        "color_science": "S-Log3 / S-Gamut3.Cine",
        "dynamic_range": 16,
        "gate_fit": "horizontal",
        "common_primes": [25, 35, 50, 75, 100, 135],
    },
    "sony_fx6": {
        "sensor_mm": (36.00, 24.00),
        "max_res": (4264, 2408),
        "format": "Full Frame",
        "color_science": "S-Log3 / S-Gamut3.Cine",
        "dynamic_range": 15,
        "gate_fit": "fill",  # Photo-style E-mount lenses
        "common_primes": [24, 35, 50, 85, 135],
    },
    "bmd_ursa_12k": {
        "sensor_mm": (27.03, 14.25),
        "max_res": (12288, 6480),
        "format": "Super 35",
        "color_science": "Blackmagic Film Gen 5 / Wide Gamut Gen 5",
        "dynamic_range": 14,
        "gate_fit": "horizontal",
        "common_primes": [25, 35, 50, 85, 100],
    },
    "canon_c500_ii": {
        "sensor_mm": (38.10, 20.10),
        "max_res": (5952, 3140),
        "format": "Full Frame (17:9)",
        "color_science": "Canon Log 2 / Cinema Gamut",
        "dynamic_range": 15,
        "gate_fit": "horizontal",
        "common_primes": [24, 35, 50, 85, 100, 135],
    },
}


def apply_camera_sensor(cam_node_path, camera_name, focal_length=50):
    """Apply real camera sensor dimensions to a Solaris camera LOP.
    Sets horizontalAperture, verticalAperture, and focalLength."""
    cam = hou.node(cam_node_path)
    if not cam:
        return

    sensor = CAMERA_SENSORS.get(camera_name)
    if not sensor:
        print(f"Unknown camera. Available: {list(CAMERA_SENSORS.keys())}")
        return

    h_aperture, v_aperture = sensor["sensor_mm"]
    cam.parm("horizontalAperture").set(h_aperture)
    cam.parm("verticalAperture").set(v_aperture)
    cam.parm("focalLength").set(focal_length)

    print(f"Camera: {camera_name} ({sensor['format']})")
    print(f"  Sensor: {h_aperture} x {v_aperture} mm")
    print(f"  Focal length: {focal_length}mm")
    print(f"  Gate fit: {sensor['gate_fit']}")
    print(f"  Common primes: {sensor['common_primes']}")
    return sensor


apply_camera_sensor("/stage/camera1", "arri_alexa_35", focal_length=50)
```

```python
# FOV calculation and crop factor reference
import hou
import math

def calculate_fov(h_aperture, focal_length):
    """Calculate horizontal field of view in degrees.
    HFOV = 2 * atan(horizontalAperture / (2 * focalLength))"""
    hfov_rad = 2.0 * math.atan(h_aperture / (2.0 * focal_length))
    return math.degrees(hfov_rad)


def calculate_crop_factor(h_aperture, reference=36.0):
    """Calculate crop factor relative to full frame (36mm).
    Crop factor = reference_width / sensor_width."""
    return reference / h_aperture


def calculate_equivalent_focal_length(focal_length, h_aperture, reference=36.0):
    """Full-frame equivalent focal length.
    A 50mm on S35 (27mm) ≈ 67mm on full frame."""
    crop = calculate_crop_factor(h_aperture, reference)
    return focal_length * crop


def fov_comparison(focal_length=50):
    """Compare FOV across all camera sensors at a given focal length."""
    print(f"FOV comparison at {focal_length}mm:")
    print(f"{'Camera':<25} {'Sensor W':>10} {'HFOV':>8} {'Crop':>6} {'FF Equiv':>10}")
    print("-" * 65)
    for name, sensor in sorted(CAMERA_SENSORS.items(),
                                key=lambda x: x[1]["sensor_mm"][0]):
        h = sensor["sensor_mm"][0]
        fov = calculate_fov(h, focal_length)
        crop = calculate_crop_factor(h)
        equiv = calculate_equivalent_focal_length(focal_length, h)
        print(f"{name:<25} {h:>8.2f}mm {fov:>6.1f}° {crop:>5.2f}x {equiv:>7.0f}mm")


fov_comparison(50)
```

```python
# Set up camera matching a specific real-world camera body
import hou

def create_matched_camera(stage_path, camera_name, focal_length,
                          cam_prim_path="/cameras/render_cam"):
    """Create a Solaris camera LOP matching a real camera body."""
    stage = hou.node(stage_path)
    if not stage:
        return

    sensor = CAMERA_SENSORS.get(camera_name)
    if not sensor:
        return

    cam = stage.createNode("camera", "render_cam")
    h_aperture, v_aperture = sensor["sensor_mm"]

    cam.parm("primpath").set(cam_prim_path)
    cam.parm("horizontalAperture").set(h_aperture)
    cam.parm("verticalAperture").set(v_aperture)
    cam.parm("focalLength").set(focal_length)
    cam.parm("fStop").set(0)  # Disable DOF by default

    # Set resolution to match camera max res aspect ratio
    max_w, max_h = sensor["max_res"]
    aspect = max_w / max_h
    print(f"Matched camera: {camera_name}")
    print(f"  Sensor: {h_aperture} x {v_aperture}mm ({sensor['format']})")
    print(f"  Lens: {focal_length}mm")
    print(f"  Native aspect: {aspect:.3f} ({max_w}x{max_h})")
    print(f"  Gate fit: {sensor['gate_fit']}")
    return cam


create_matched_camera("/stage", "sony_venice_2", focal_length=35)
```

```python
# USD API: set camera sensor parameters directly
from pxr import UsdGeom, Gf

def set_camera_sensor_usd(stage, cam_prim_path, camera_name, focal_length=50):
    """Set camera sensor via USD API (no hou dependency)."""
    cam_prim = stage.GetPrimAtPath(cam_prim_path)
    if not cam_prim:
        return
    cam = UsdGeom.Camera(cam_prim)

    sensor = CAMERA_SENSORS.get(camera_name)
    if not sensor:
        return

    h_aperture, v_aperture = sensor["sensor_mm"]
    cam.GetHorizontalApertureAttr().Set(h_aperture)
    cam.GetVerticalApertureAttr().Set(v_aperture)
    cam.GetFocalLengthAttr().Set(float(focal_length))
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.1, 10000.0))

    print(f"USD camera: {cam_prim_path}")
    print(f"  Sensor: {h_aperture} x {v_aperture}mm ({sensor['format']})")
    print(f"  Focal: {focal_length}mm")


# Usage with an open USD stage:
# set_camera_sensor_usd(stage, "/cameras/render_cam", "arri_alexa_35", 50)
```

```python
# Gate fit mode reference and configuration
import hou

GATE_FIT_MODES = {
    "horizontal": "Matches horizontal FOV to sensor width. Standard for cinema/anamorphic.",
    "vertical":   "Matches vertical FOV. Rarely used.",
    "fill":       "Fits entire sensor gate inside render resolution. No cropping.",
    "overscan":   "Renders larger than gate for VFX edge data.",
}

# USD camera parameter mapping (NO xn__ encoding for cameras)
USD_CAMERA_PARMS = {
    "focalLength":              ("float", "Lens focal length in mm"),
    "horizontalAperture":       ("float", "Sensor width in mm"),
    "verticalAperture":         ("float", "Sensor height in mm"),
    "fStop":                    ("float", "Aperture f-number (0 = no DOF)"),
    "focusDistance":            ("float", "Focus distance in scene units"),
    "clippingRange":            ("vec2",  "Near/far clip planes"),
    "projection":               ("token", "perspective or orthographic"),
    "horizontalApertureOffset": ("float", "Lens shift horizontal (mm)"),
    "verticalApertureOffset":   ("float", "Lens shift vertical (mm)"),
}

# Unlike lights (inputs:intensity -> xn__inputsintensity_i0a),
# camera parms use plain USD names directly as Houdini parm names.

for parm, (ptype, desc) in USD_CAMERA_PARMS.items():
    print(f"  {parm} ({ptype}): {desc}")
```

## Common Mistakes
- Using light-style xn__ encoding for camera parms -- cameras use plain USD attribute names
- Not matching sensor dimensions to real camera -- produces wrong FOV
- Larger sensor = wider FOV at same focal length -- a 50mm on S35 ≈ 67mm on full frame
- Gate fit mismatch -- cinema cameras use horizontal, photo-style cameras (FX6) use fill
- Setting fStop=0 unintentionally -- disables DOF entirely (use fStop >= 1.4 for DOF)
- Using Houdini node path for camera in Karma -- must use USD prim path (/cameras/render_cam)
