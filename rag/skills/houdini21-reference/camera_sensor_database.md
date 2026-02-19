# Camera Sensor Database for USD/Solaris

Production camera bodies mapped to USD camera parameters for accurate FOV matching in Houdini 21 Solaris. Setting `horizontalAperture` and `verticalAperture` to match a real sensor ensures virtual lenses produce the same field of view as the physical camera.

## Sensor Quick Reference

| Camera | Sensor (mm) | Max Resolution | USD horizontalAperture | USD verticalAperture | Format |
|--------|-------------|----------------|----------------------|---------------------|--------|
| ARRI Alexa 35 | 27.99 x 19.22 | 4608 x 3164 | 27.99 | 19.22 | Super 35 |
| ARRI Alexa Mini LF | 36.70 x 25.54 | 4448 x 3096 | 36.70 | 25.54 | Large Format |
| RED V-Raptor [X] | 40.96 x 21.60 | 8192 x 4320 | 40.96 | 21.60 | VV (VistaVision+) |
| RED Komodo-X | 27.03 x 14.26 | 6144 x 3240 | 27.03 | 14.26 | Super 35 |
| Sony Venice 2 | 36.20 x 24.10 | 8640 x 5760 | 36.20 | 24.10 | Full Frame |
| Sony FX6 | 36.00 x 24.00 | 4264 x 2408 | 36.00 | 24.00 | Full Frame |
| Blackmagic URSA Mini Pro 12K | 27.03 x 14.25 | 12288 x 6480 | 27.03 | 14.25 | Super 35 |
| Canon EOS C500 Mark II | 38.10 x 20.10 | 5952 x 3140 | 38.10 | 20.10 | Full Frame (17:9) |

---

## ARRI Alexa 35

- **Sensor**: ALEV 4 CMOS, 27.99 x 19.22 mm (Super 35)
- **Max Resolution**: 4608 x 3164 (4.6K)
- **USD horizontalAperture**: 27.99
- **USD verticalAperture**: 19.22
- **Native ISO**: 200 - 6400 (EI range), base sensitivity adjustable
- **Dynamic Range**: 17 stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: LPL (ARRI), PL (with adapter)
- **Color Science**: ARRI LogC4 / ARRI Wide Gamut 4
- **Common Primes**: 18, 25, 32, 40, 50, 65, 75, 100 mm (ARRI Signature Prime S35)
- **Notes**: Flagship ARRI Super 35 sensor. ARRI Textures extended metadata system. Supports anamorphic desqueeze (1.3x, 1.5x, 2x). LogC4 is a new encoding curve -- not backward-compatible with LogC3.

## ARRI Alexa Mini LF

- **Sensor**: ALEV 3 A2X CMOS, 36.70 x 25.54 mm (Large Format)
- **Max Resolution**: 4448 x 3096 (4.5K)
- **USD horizontalAperture**: 36.70
- **USD verticalAperture**: 25.54
- **Native ISO**: 200 - 3200 (EI range), dual base 800
- **Dynamic Range**: 14+ stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: LPL (ARRI), PL (with LPL-PL adapter)
- **Color Science**: ARRI LogC3 / ARRI Wide Gamut 3
- **Common Primes**: 25, 29, 35, 40, 47, 58, 75, 95, 125 mm (ARRI Signature Primes LF)
- **Notes**: Large format sensor in compact body. Same sensor as full-size ALEXA LF. 44.71 mm image circle. Requires LF-class lenses to cover full sensor area. Open Gate mode uses full 36.70 x 25.54 mm area.

## RED V-Raptor [X]

- **Sensor**: RED CMOS, 40.96 x 21.60 mm (VV / VistaVision+)
- **Max Resolution**: 8192 x 4320 (8K)
- **USD horizontalAperture**: 40.96
- **USD verticalAperture**: 21.60
- **Native ISO**: 250 - 12800, dual base 800 / 2000
- **Dynamic Range**: 17+ stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: Canon RF (native), PL (with adapter)
- **Color Science**: REDWideGamutRGB / Log3G10
- **Common Primes**: 24, 35, 50, 85, 100 mm (various PL/RF mount cinema primes)
- **Notes**: VV sensor is wider than standard full frame (40.96 vs 36 mm). 46.31 mm diagonal requires large-format lenses for full coverage. Sensor crops available for S35 (approx 27 x 14.25 mm) at 6K. REDCODE RAW at up to 8K 120fps.

## RED Komodo-X

- **Sensor**: RED Global Shutter CMOS, 27.03 x 14.26 mm (Super 35)
- **Max Resolution**: 6144 x 3240 (6K)
- **USD horizontalAperture**: 27.03
- **USD verticalAperture**: 14.26
- **Native ISO**: 250 - 12800, dual base 800 / 2000
- **Dynamic Range**: 16.5+ stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: Canon RF (native)
- **Color Science**: REDWideGamutRGB / Log3G10
- **Common Primes**: 24, 35, 50, 85 mm (Canon RF or PL with adapter)
- **Notes**: Global shutter sensor -- no rolling shutter artifacts. Compact body (129 x 101 x 95 mm). Same S35 sensor dimensions as URSA Mini Pro 12K. REDCODE RAW at 6K up to 40fps, 4K up to 120fps. Global shutter ideal for VFX (clean motion, no wobble).

## Sony Venice 2

- **Sensor**: Full-Frame CMOS, 36.20 x 24.10 mm (Full Frame)
- **Max Resolution**: 8640 x 5760 (8.6K)
- **USD horizontalAperture**: 36.20
- **USD verticalAperture**: 24.10
- **Native ISO**: Dual base 500 / 2500
- **Dynamic Range**: 16+ stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: PL (native), E-mount (with adapter)
- **Color Science**: S-Log3 / S-Gamut3.Cine (or S-Gamut3)
- **Common Primes**: 25, 35, 50, 75, 100, 135 mm (Zeiss Supreme Primes, ARRI Signature Primes)
- **Notes**: Interchangeable sensor block (8.6K or 6K available). 8.6K sensor shoots up to 60fps full-frame. Built-in 8-step ND filter system. X-OCN internal recording. 6K sensor option: 6048 x 4032, same 36 x 24 mm body. PL mount is industry standard for cine primes.

## Sony FX6

- **Sensor**: Full-Frame back-illuminated CMOS, 36.00 x 24.00 mm (Full Frame)
- **Max Resolution**: 4264 x 2408 (approx 10.2 MP effective)
- **USD horizontalAperture**: 36.00
- **USD verticalAperture**: 24.00
- **Native ISO**: Dual base 800 / 12800
- **Dynamic Range**: 15+ stops
- **Gate Fit**: Fill (photo-style full-frame lenses)
- **Lens Mount**: Sony E-mount
- **Color Science**: S-Log3 / S-Gamut3.Cine (or S-Gamut3)
- **Common Primes**: 24, 35, 50, 85, 135 mm (Sony G Master, Sigma Art)
- **Notes**: Lightweight run-and-gun cinema camera. E-mount gives access to extensive Sony/Sigma/Tamron photo and cine lens ecosystem. Electronic variable ND filter built in. Fast Hybrid AF with 627 phase-detection points. Outputs UHD 4K (3840 x 2160) in most recording modes. Gate fit recommendation is "fill" since E-mount photo lenses assume full-frame coverage.

## Blackmagic URSA Mini Pro 12K

- **Sensor**: Super 35 CMOS, 27.03 x 14.25 mm (Super 35)
- **Max Resolution**: 12288 x 6480 (12K)
- **USD horizontalAperture**: 27.03
- **USD verticalAperture**: 14.25
- **Native ISO**: 800 (fixed base)
- **Dynamic Range**: 14 stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: PL (interchangeable to EF or F)
- **Color Science**: Blackmagic Film Gen 5 / Blackmagic Wide Gamut Gen 5
- **Common Primes**: 25, 35, 50, 85, 100 mm (PL cinema primes)
- **Notes**: 80 MP per frame at 12K. Records Blackmagic RAW. 60fps at 12K, 120fps at 8K, 240fps at 4K Super 16 crop. Interchangeable lens mount system supports PL, EF, and F. Sensor pitch matches RED Komodo-X S35 dimensions. Ideal for heavy reframe/crop workflows.

## Canon EOS C500 Mark II

- **Sensor**: Full-Frame CMOS, 38.10 x 20.10 mm (Full Frame, 17:9 aspect)
- **Max Resolution**: 5952 x 3140 (5.9K)
- **USD horizontalAperture**: 38.10
- **USD verticalAperture**: 20.10
- **Native ISO**: Dual base 800 / 3200 (Cinema Gamut), or 400 / 1600 (BT.709)
- **Dynamic Range**: 15+ stops
- **Gate Fit**: Horizontal (cinema standard)
- **Lens Mount**: EF (native), PL (with optional module)
- **Color Science**: Canon Log 2 (or Canon Log 3) / Cinema Gamut
- **Common Primes**: 24, 35, 50, 85, 100, 135 mm (Canon CN-E Primes, Sigma Cine)
- **Notes**: Wider-than-standard full frame (38.1 mm vs typical 36 mm). 17:9 native aspect ratio. Cinema RAW Light internal recording. Dual Pixel CMOS AF with Canon EF/RF lenses (RF via adapter). Supports Super 35 crop mode (approx 24.6 x 13.0 mm). Modular design with optional EVF, handle, expansion units.

---

## Gate Fit Mode Guide

| Gate Fit | When to Use | Behavior |
|----------|-------------|----------|
| Horizontal | Cinema cameras (most entries above) | Matches horizontal FOV to `horizontalAperture`. Vertical may crop/extend. Standard for anamorphic and widescreen. |
| Vertical | Rarely used | Matches vertical FOV. Horizontal may crop/extend. |
| Fill | Photo-style cameras (FX6 with photo lenses) | Fits the entire sensor gate inside the render resolution. No cropping, may letterbox/pillarbox. |
| Overscan | VFX plates needing padding | Render slightly larger than the gate to provide edge data for comp. |

Set gate fit on the Karma render settings or on the camera LOP directly. Default in Houdini is horizontal.

---

## USD Camera Parameter Encoding in Houdini 21

Camera parameters in Houdini 21 Solaris do **not** use the `xn__` prefix encoding that light parameters use. Camera attributes use their plain USD names as Houdini parameter names.

| USD Attribute | Houdini Parameter | Type | Notes |
|---------------|------------------|------|-------|
| `focalLength` | `focalLength` | float | Lens focal length in mm |
| `horizontalAperture` | `horizontalAperture` | float | Sensor width in mm (set to match camera body) |
| `verticalAperture` | `verticalAperture` | float | Sensor height in mm (set to match camera body) |
| `fStop` | `fStop` | float | Aperture f-number (0 = no DOF) |
| `focusDistance` | `focusDistance` | float | Focus distance in scene units |
| `clippingRange` | `clippingRange` | vec2 | Near/far clip planes |
| `projection` | `projection` | token | `perspective` or `orthographic` |
| `horizontalApertureOffset` | `horizontalApertureOffset` | float | Lens shift horizontal (mm) |
| `verticalApertureOffset` | `verticalApertureOffset` | float | Lens shift vertical (mm) |

Unlike light parameters (e.g., `inputs:intensity` -> `xn__inputsintensity_i0a`), camera parameters are direct USD attributes on `UsdGeomCamera` and map to Houdini parms without encoding.

### Setting Camera Aperture via Python

```python
# Match a specific camera body in a Solaris camera LOP
cam_node = hou.node("/stage/camera1")

# Example: ARRI Alexa 35 sensor
cam_node.parm("horizontalAperture").set(27.99)
cam_node.parm("verticalAperture").set(19.22)
cam_node.parm("focalLength").set(50)  # 50mm prime

# Example: RED V-Raptor [X] VV sensor
cam_node.parm("horizontalAperture").set(40.96)
cam_node.parm("verticalAperture").set(21.60)
cam_node.parm("focalLength").set(35)  # 35mm prime
```

### Setting Camera Aperture via USD API

```python
from pxr import UsdGeom

cam = UsdGeom.Camera(stage.GetPrimAtPath("/cameras/render_cam"))
cam.GetHorizontalApertureAttr().Set(27.99)   # ARRI Alexa 35
cam.GetVerticalApertureAttr().Set(19.22)
cam.GetFocalLengthAttr().Set(50.0)
```

---

## FOV Calculation Reference

Field of view is determined by sensor size and focal length:

```
Horizontal FOV = 2 * atan(horizontalAperture / (2 * focalLength))  [radians]
Vertical FOV   = 2 * atan(verticalAperture / (2 * focalLength))    [radians]
```

### Example: 50mm Lens Across Sensor Sizes

| Camera | Sensor Width (mm) | HFOV at 50mm |
|--------|-------------------|-------------|
| RED Komodo-X | 27.03 | 30.2 deg |
| ARRI Alexa 35 | 27.99 | 31.3 deg |
| BMD URSA 12K | 27.03 | 30.2 deg |
| Sony FX6 | 36.00 | 39.6 deg |
| Sony Venice 2 | 36.20 | 39.8 deg |
| ARRI Alexa Mini LF | 36.70 | 40.3 deg |
| Canon C500 II | 38.10 | 41.6 deg |
| RED V-Raptor [X] | 40.96 | 44.4 deg |

Larger sensors produce wider FOV at the same focal length. A 50mm lens on a S35 sensor (27 mm) matches roughly the FOV of a 75mm lens on a VV sensor (41 mm).

---

## Crop Factor Reference

Crop factor relative to standard full frame (36 x 24 mm):

| Camera | Sensor Width | Crop Factor | 50mm Equivalent |
|--------|-------------|-------------|-----------------|
| RED Komodo-X | 27.03 mm | 1.33x | 67mm |
| ARRI Alexa 35 | 27.99 mm | 1.29x | 64mm |
| BMD URSA 12K | 27.03 mm | 1.33x | 67mm |
| Sony FX6 | 36.00 mm | 1.00x | 50mm |
| Sony Venice 2 | 36.20 mm | 0.99x | 50mm |
| ARRI Alexa Mini LF | 36.70 mm | 0.98x | 49mm |
| Canon C500 II | 38.10 mm | 0.94x | 47mm |
| RED V-Raptor [X] | 40.96 mm | 0.88x | 44mm |
