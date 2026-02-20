# Lighting in Solaris

## Triggers

dome light, domelight, HDRI, environment light, area light, rect light, rectlight, distant light, distantlight, sphere light, spherelight, disk light, disklight, cylinder light, three point lighting, 3-point lighting, key light, fill light, rim light, back light, exposure, intensity, light intensity, light exposure, color temperature, kelvin, light linking, light categories, shadow, barn doors, IES, specular contribution, diffuse contribution, light visibility, spot light, cone angle, light shaping, light setup, studio lighting, product lighting, turntable lighting, outdoor lighting, interior lighting, portal light, light ratio, key fill ratio, stops, lighting law, xn__inputsintensity_i0a, xn__inputsexposure_vya, xn__inputscolor_kya

## Context

Solaris lights are USD prims created via LOP nodes. All light brightness is controlled by exposure (logarithmic, in stops) — intensity is ALWAYS locked at 1.0. Houdini encodes USD attribute names as `xn__`-prefixed parameter names; use the encoded names when setting parms directly via `hou.node().parm()`.

## Code

```python
import hou
import math

# ============================================================
# LIGHTING LAW — READ THIS FIRST
# ============================================================
# intensity is ALWAYS 1.0. NEVER set it above 1.0.
# Brightness is controlled by EXPOSURE (logarithmic, in stops).
# Final light contribution = intensity * color * 2^exposure
# Since intensity == 1.0 always, contribution = color * 2^exposure
#
# Key:fill ratios as stop differences:
#   1.5:1 ratio = 0.585 stops  (log2(1.5))  — flat, broadcast beauty
#   2:1   ratio = 1.0   stops  (log2(2))    — subtle, beauty
#   3:1   ratio = 1.585 stops  (log2(3))    — standard narrative
#   4:1   ratio = 2.0   stops  (log2(4))    — dramatic, moody
#   8:1   ratio = 3.0   stops  (log2(8))    — noir, extreme contrast
#  16:1   ratio = 4.0   stops  (log2(16))   — silhouette, low-key
#
# Formula: fill_exposure = key_exposure - log2(ratio)
KEY_EXPOSURE = 5.0
RATIO_3_TO_1 = math.log2(3)          # 1.585 stops
FILL_EXPOSURE_3_1 = KEY_EXPOSURE - RATIO_3_TO_1   # 3.415
FILL_EXPOSURE_4_1 = KEY_EXPOSURE - math.log2(4)   # 3.0
```

```python
import hou

# ============================================================
# COMPLETE ENCODED PARAMETER REFERENCE (Houdini 21 Solaris)
# ============================================================
# USD Attribute               Houdini Encoded Parm                  Notes
# inputs:intensity            xn__inputsintensity_i0a               ALWAYS 1.0 — never change
# inputs:exposure             xn__inputsexposure_vya                brightness in stops
# inputs:exposure (control)   xn__inputsexposure_control_wcb        set to "set" to enable
# inputs:color                xn__inputscolor_kya                   RGB via parmTuple
# inputs:diffuse              xn__inputsdiffuse_vya                 diffuse multiplier 0-1
# inputs:specular             xn__inputsspecular_01a                specular multiplier 0-1
# inputs:shadow:enable        xn__inputsshadowenable_2kb            bool — toggle shadows
# inputs:shadow:color         xn__inputsshadowcolor_o5a             vec3 — shadow tint
# inputs:normalize            xn__inputsnormalize_01a               bool — normalize by area
# inputs:texture:file         xn__inputstexturefile_i1a             HDRI path (DomeLight only)
# inputs:texture:format       xn__inputstextureformat_r1a           latlong / mirroredBall / angular
# inputs:enableColorTemperature xn__inputsenablecolortemperature_r5a bool
# inputs:colorTemperature     xn__inputscolortemperature_u5a        float Kelvin
# inputs:shaping:cone:angle   xn__inputsshapingconeangle_bobja      spot cone angle degrees
# inputs:shaping:cone:softness xn__inputsshapingconesoftness_brbja  edge falloff 0-1
# inputs:shaping:focus        xn__inputsshapingfocus_i5a            focus toward center


def _set_light_intensity_law(light_node):
    """Enforce Lighting Law: intensity always 1.0, brightness via exposure only."""
    light_node.parm("xn__inputsintensity_i0a").set(1.0)
    # Enable the exposure control so the value takes effect
    ctrl = light_node.parm("xn__inputsexposure_control_wcb")
    if ctrl:
        ctrl.set("set")
```

```python
import hou

# ============================================================
# DOME LIGHT — HDRI ENVIRONMENT
# ============================================================

def create_dome_light(stage_path="/stage", name="env_light",
                      hdri_path="", exposure=0.0, ry=0.0):
    """
    Create a DomeLight LOP with an HDRI texture.
    Position (tx/ty/tz) has no effect on DomeLights — only rotation matters.
    Two DomeLights double the ambient level; use only one per scene.
    """
    stage = hou.node(stage_path)
    dome = stage.createNode("domelight", name)

    # Lighting Law: intensity always 1.0
    dome.parm("xn__inputsintensity_i0a").set(1.0)

    # Brightness via exposure only (0.0 = baseline, 1x multiplier)
    dome.parm("xn__inputsexposure_control_wcb").set("set")
    dome.parm("xn__inputsexposure_vya").set(exposure)

    # HDRI texture — EXR preferred (full HDR range, no clipping)
    # JPEG/PNG work but clip at 1.0 — no HDR range
    if hdri_path:
        dome.parm("xn__inputstexturefile_i1a").set(hdri_path)

    # latlong = equirectangular (most common for HDRIs)
    # mirroredBall = chrome ball capture, angular = light probe
    dome.parm("xn__inputstextureformat_r1a").set("latlong")

    # Horizontal rotation — pan environment to reposition sun
    # ry by 15-30 degree increments during iteration to find optimal sun position
    dome.parm("ry").set(ry)

    return dome


# Example: studio HDRI at moderate exposure
dome = create_dome_light(
    hdri_path="D:/GreyscaleGorillaAssetLibrary/HDRIs/parking_lot_2k.exr",
    exposure=0.25,   # low exposure — HDRI provides its own brightness range
    ry=120.0         # rotate environment so sun hits from camera-left
)

# When combining HDRI with CG lights, lower dome exposure 1-2 stops
# to avoid overexposure — HDRI then acts as ambient fill only
dome.parm("xn__inputsexposure_vya").set(-1.0)

# Control HDRI contribution separately for diffuse vs. reflections
dome.parm("xn__inputsdiffuse_vya").set(0.3)    # dim diffuse fill
dome.parm("xn__inputsspecular_01a").set(1.0)   # full reflections from HDRI

# Built-in Houdini test HDRIs
hfs_hdri = "$HFS/houdini/pic/hdri/HDRIHaven_parking_lot_2k.exr"
dome.parm("xn__inputstexturefile_i1a").set(hfs_hdri)
```

```python
import hou

# ============================================================
# AREA LIGHT — RECTLIGHT (RECTANGULAR AREA)
# ============================================================

def create_rect_light(stage_path="/stage", name="rect_light",
                      exposure=4.0, tx=0.0, ty=3.0, tz=3.0,
                      rx=-45.0, ry=0.0, sx=2.0, sz=2.0,
                      shadows=True, normalize=True):
    """
    Create a RectLight LOP.
    Shadow softness is physically determined by light source size (sx, sz).
    Larger sx/sz = softer shadows. Smaller = sharper.
    normalize=True keeps intensity consistent as you resize.
    """
    stage = hou.node(stage_path)
    rect = stage.createNode("rectlight", name)

    # Lighting Law: intensity locked at 1.0
    rect.parm("xn__inputsintensity_i0a").set(1.0)
    rect.parm("xn__inputsexposure_control_wcb").set("set")
    rect.parm("xn__inputsexposure_vya").set(exposure)

    # Position and orientation
    rect.parm("tx").set(tx)
    rect.parm("ty").set(ty)
    rect.parm("tz").set(tz)
    rect.parm("rx").set(rx)
    rect.parm("ry").set(ry)

    # Physical size controls shadow softness
    rect.parm("sx").set(sx)   # width
    rect.parm("sz").set(sz)   # height

    # Normalize: True = resize without changing total energy output
    rect.parm("xn__inputsnormalize_01a").set(normalize)

    # Fill lights often look better without shadows (avoids double-shadow artifacts)
    rect.parm("xn__inputsshadowenable_2kb").set(shadows)

    return rect


# Soft key light: large area for wraparound illumination
key_rect = create_rect_light(
    name="key_rect",
    exposure=4.0,
    tx=-3.0, ty=4.0, tz=2.0,
    rx=-35.0, ry=-45.0,
    sx=3.0, sz=3.0    # large = soft shadows
)

# Sharp accent: small source for crisp highlights
accent = create_rect_light(
    name="accent",
    exposure=3.5,
    sx=0.2, sz=0.2,   # small = sharp shadows
    shadows=True
)
```

```python
import hou

# ============================================================
# DISTANT LIGHT — SUN / DIRECTIONAL
# ============================================================

def create_distant_light(stage_path="/stage", name="sun_light",
                         exposure=6.0, rx=-45.0, ry=-30.0,
                         color_temp_k=None):
    """
    Create a DistantLight LOP.
    DistantLight is infinitely far — position (tx/ty/tz) has no effect.
    Shadow softness is controlled by the light's angle parm (simulates sun disk size).
    angle=0 produces perfectly sharp shadows (looks CG); increase for realism.
    """
    stage = hou.node(stage_path)
    dist = stage.createNode("distantlight", name)

    # Lighting Law: intensity always 1.0
    dist.parm("xn__inputsintensity_i0a").set(1.0)
    dist.parm("xn__inputsexposure_control_wcb").set("set")
    dist.parm("xn__inputsexposure_vya").set(exposure)

    # Direction only — rx/ry control sun angle
    dist.parm("rx").set(rx)
    dist.parm("ry").set(ry)

    # Optional: color temperature instead of RGB
    # Guide: 3000K=warm tungsten, 5500K=noon daylight, 8000K=blue sky shade
    if color_temp_k is not None:
        dist.parm("xn__inputsenablecolortemperature_r5a").set(True)
        dist.parm("xn__inputscolortemperature_u5a").set(color_temp_k)

    return dist


# Noon sun: high angle, neutral white
noon_sun = create_distant_light(
    name="noon_sun",
    exposure=6.0,
    rx=-80.0,          # nearly vertical (high noon)
    ry=-30.0,
    color_temp_k=6000  # neutral daylight
)

# Golden hour sun: low angle, warm
golden_hour = create_distant_light(
    name="golden_hour_sun",
    exposure=4.0,
    rx=-10.0,          # very low on horizon
    ry=-30.0,
    color_temp_k=3500  # warm orange-gold
)

# Moonlight: barely above horizon, cool, dim
moonlight = create_distant_light(
    name="moonlight",
    exposure=0.0,      # very dim (1x multiplier)
    rx=-30.0,
    ry=0.0,
    color_temp_k=8000  # cool blue
)
```

```python
import hou
import math

# ============================================================
# THREE-POINT LIGHTING RIG
# ============================================================
# Key:fill ratio 3:1 = 1.585 stops difference (log2(3))
# Key:fill ratio 4:1 = 2.0   stops difference (log2(4))

def create_three_point_rig(stage_path="/stage",
                           key_exposure=5.0,
                           ratio=3.0,
                           scenario="narrative"):
    """
    Build a complete three-point lighting rig.
    Intensity is NEVER touched — all brightness via exposure.

    scenario presets:
      "beauty"    — 2:1 ratio, even and flattering
      "narrative" — 3:1 ratio, standard film
      "dramatic"  — 4:1 ratio, moody
      "noir"      — 8:1 ratio, extreme contrast
    """
    PRESETS = {
        #               key   ratio  rim_offset  env
        "beauty":     (4.0,  2.0,   -0.5,       1.0),
        "narrative":  (5.0,  3.0,   -0.5,       0.0),
        "dramatic":   (5.0,  4.0,   -0.5,       0.0),
        "noir":       (5.0,  8.0,   0.0,        -1.0),
    }
    if scenario in PRESETS:
        key_exposure, ratio, rim_offset, env_exposure = PRESETS[scenario]

    fill_exposure = key_exposure - math.log2(ratio)
    rim_exposure  = key_exposure + rim_offset   # typically 0.5 stops below key

    stage = hou.node(stage_path)

    # --- KEY LIGHT (DistantLight, camera left, high angle) ---
    key = stage.createNode("distantlight", "key_light")
    key.parm("xn__inputsintensity_i0a").set(1.0)       # Lighting Law
    key.parm("xn__inputsexposure_control_wcb").set("set")
    key.parm("xn__inputsexposure_vya").set(key_exposure)
    key.parm("rx").set(-35.0)   # downward angle
    key.parm("ry").set(-45.0)   # camera-left
    # Warm color temperature for natural key
    key.parm("xn__inputsenablecolortemperature_r5a").set(True)
    key.parm("xn__inputscolortemperature_u5a").set(5500)  # neutral daylight

    # --- FILL LIGHT (RectLight, camera right, soft) ---
    fill = stage.createNode("rectlight", "fill_light")
    fill.parm("xn__inputsintensity_i0a").set(1.0)      # Lighting Law
    fill.parm("xn__inputsexposure_control_wcb").set("set")
    fill.parm("xn__inputsexposure_vya").set(fill_exposure)
    fill.parm("rx").set(-20.0)
    fill.parm("ry").set(45.0)   # camera-right
    fill.parm("sx").set(3.0)    # large = very soft shadows
    fill.parm("sz").set(3.0)
    fill.parm("xn__inputsnormalize_01a").set(True)
    # Fill lights: disable shadows to avoid double-shadow artifacts
    fill.parm("xn__inputsshadowenable_2kb").set(False)

    # --- RIM / BACK LIGHT (DistantLight, behind subject) ---
    rim = stage.createNode("distantlight", "rim_light")
    rim.parm("xn__inputsintensity_i0a").set(1.0)       # Lighting Law
    rim.parm("xn__inputsexposure_control_wcb").set("set")
    rim.parm("xn__inputsexposure_vya").set(rim_exposure)
    rim.parm("rx").set(-30.0)
    rim.parm("ry").set(180.0)   # directly behind subject

    # --- ENVIRONMENT (DomeLight, ambient baseline) ---
    env = stage.createNode("domelight", "env_dome")
    env.parm("xn__inputsintensity_i0a").set(1.0)       # Lighting Law
    env.parm("xn__inputsexposure_control_wcb").set("set")
    env.parm("xn__inputsexposure_vya").set(
        -1.0 if scenario == "noir" else env_exposure
    )
    # Keep env as subtle fill only
    env.parm("xn__inputsdiffuse_vya").set(0.5)
    env.parm("xn__inputsspecular_01a").set(1.0)

    print(f"Three-point rig '{scenario}': "
          f"key={key_exposure:.2f} fill={fill_exposure:.2f} "
          f"rim={rim_exposure:.2f} ratio={ratio}:1")
    return key, fill, rim, env


# --- STANDARD SCENARIO EXPOSURE PRESETS ---
# Verify fill math: fill = key - log2(ratio)
# Product beauty:         key=4.0  fill=3.0   rim=3.5  env=1.0   (2:1)
# Broadcast/commercial:   key=5.0  fill=3.415 rim=4.5  env=1.0   (3:1)
# Dramatic narrative:     key=5.0  fill=3.0   rim=4.5  env=0.0   (4:1)
# Noir/low-key:           key=5.0  fill=2.0   rim=5.0  env=-1.0  (8:1)
# Overcast exterior:      key=3.0  fill=2.5   rim=--   env=2.0   (1.5:1)
# Character portrait:     key=4.0  fill=2.415 rim=3.5  env=0.5   (3:1)

key, fill, rim, env = create_three_point_rig(scenario="narrative")
```

```python
import hou

# ============================================================
# PRODUCT / TURNTABLE LIGHTING RIG
# ============================================================
# Even, flattering light with minimal harsh shadows.
# Key:fill ratio 2:1 or less for even coverage.
# Large RectLights (sx=5, sz=5) for soft wraparound illumination.

def create_product_rig(stage_path="/stage"):
    """
    Standard product lighting rig: top key + two side fills + rim + dome.
    Normalize ON so resizing area lights doesn't change total energy.
    Turntable: lights stay fixed, asset rotates on Y-axis animated Xform.
    """
    stage = hou.node(stage_path)

    def _rect(name, exposure, rx, ry, sx=3.0, sz=3.0, shadows=True):
        n = stage.createNode("rectlight", name)
        n.parm("xn__inputsintensity_i0a").set(1.0)    # Lighting Law
        n.parm("xn__inputsexposure_control_wcb").set("set")
        n.parm("xn__inputsexposure_vya").set(exposure)
        n.parm("rx").set(rx)
        n.parm("ry").set(ry)
        n.parm("sx").set(sx)
        n.parm("sz").set(sz)
        n.parm("xn__inputsnormalize_01a").set(True)  # consistent as resized
        n.parm("xn__inputsshadowenable_2kb").set(shadows)
        return n

    # Top/key: directly above, slightly forward
    top_key  = _rect("top_key",   exposure=4.0, rx=-70, ry=0,
                     sx=5.0, sz=5.0)

    # Side fills: symmetric, camera left and right — disable shadows
    side_a   = _rect("side_fill_a", exposure=3.0, rx=-15, ry=-90,
                     sx=4.0, sz=4.0, shadows=False)
    side_b   = _rect("side_fill_b", exposure=3.0, rx=-15, ry=90,
                     sx=4.0, sz=4.0, shadows=False)

    # Subtle rim from behind
    backdrop = _rect("backdrop_rim", exposure=2.5, rx=-10, ry=180,
                     sx=3.0, sz=3.0, shadows=False)

    # Ambient dome — low exposure, acts as fill only
    dome = stage.createNode("domelight", "env_dome")
    dome.parm("xn__inputsintensity_i0a").set(1.0)   # Lighting Law
    dome.parm("xn__inputsexposure_control_wcb").set("set")
    dome.parm("xn__inputsexposure_vya").set(1.0)
    dome.parm("xn__inputsdiffuse_vya").set(0.5)
    dome.parm("xn__inputsspecular_01a").set(1.0)

    return top_key, side_a, side_b, backdrop, dome

create_product_rig()
```

```python
import hou

# ============================================================
# OUTDOOR / NATURAL LIGHTING
# ============================================================

def create_outdoor_rig(stage_path="/stage", time_of_day="noon"):
    """
    Sun + sky + bounce rig for exterior scenes.
    Color temperature guide:
      1800-2000K  candlelight
      2700-3200K  tungsten / incandescent indoor warm
      3500-4500K  golden hour sun
      5500-6500K  daylight (noon)
      6500-7500K  overcast sky
      8000-10000K blue sky shade (cool fill in shadows)

    time_of_day presets:
      "dawn"         rx=-5,  exposure=3.0, color_temp=3000
      "morning"      rx=-25, exposure=5.0, color_temp=4500
      "noon"         rx=-80, exposure=6.0, color_temp=6000
      "golden_hour"  rx=-10, exposure=4.0, color_temp=3500
      "dusk"         rx=-3,  exposure=2.0, color_temp=2500
      "moonlight"    rx=-30, exposure=0.0, color_temp=8000
    """
    TIME_PRESETS = {
        #                rx     exp    sky_exp  kelvin
        "dawn":        (-5,   3.0,    0.5,    3000),
        "morning":     (-25,  5.0,    1.5,    4500),
        "noon":        (-80,  6.0,    2.0,    6000),
        "golden_hour": (-10,  4.0,    1.0,    3500),
        "dusk":        (-3,   2.0,    0.0,    2500),
        "moonlight":   (-30,  0.0,   -2.0,    8000),
    }

    rx, sun_exp, sky_exp, kelvin = TIME_PRESETS.get(time_of_day, TIME_PRESETS["noon"])

    stage = hou.node(stage_path)

    # --- SUN (DistantLight) ---
    sun = stage.createNode("distantlight", "sun")
    sun.parm("xn__inputsintensity_i0a").set(1.0)      # Lighting Law
    sun.parm("xn__inputsexposure_control_wcb").set("set")
    sun.parm("xn__inputsexposure_vya").set(sun_exp)
    sun.parm("rx").set(rx)
    sun.parm("ry").set(-30.0)
    sun.parm("xn__inputsenablecolortemperature_r5a").set(True)
    sun.parm("xn__inputscolortemperature_u5a").set(kelvin)

    # --- SKY (DomeLight — HDRI sky or solid blue fill) ---
    sky = stage.createNode("domelight", "sky_dome")
    sky.parm("xn__inputsintensity_i0a").set(1.0)      # Lighting Law
    sky.parm("xn__inputsexposure_control_wcb").set("set")
    sky.parm("xn__inputsexposure_vya").set(sky_exp)
    # Cool sky color for blue-sky scenarios
    sky.parmTuple("xn__inputscolor_kya").set((0.6, 0.75, 1.0))

    # --- GROUND BOUNCE (RectLight, pointing up from below) ---
    bounce = stage.createNode("rectlight", "ground_bounce")
    bounce.parm("xn__inputsintensity_i0a").set(1.0)   # Lighting Law
    bounce.parm("xn__inputsexposure_control_wcb").set("set")
    bounce.parm("xn__inputsexposure_vya").set(1.0)    # subtle bounce
    bounce.parm("rx").set(80.0)    # nearly flat, pointing upward
    bounce.parm("ry").set(180.0)
    bounce.parm("sx").set(6.0)     # large for soft diffuse bounce
    bounce.parm("sz").set(6.0)
    # Warm ground bounce (sun-heated ground)
    bounce.parm("xn__inputsenablecolortemperature_r5a").set(True)
    bounce.parm("xn__inputscolortemperature_u5a").set(4000)
    bounce.parm("xn__inputsshadowenable_2kb").set(False)   # no bounce shadows

    return sun, sky, bounce

sun, sky, bounce = create_outdoor_rig(time_of_day="golden_hour")
```

```python
import hou

# ============================================================
# INTERIOR LIGHTING WITH PORTAL LIGHTS
# ============================================================
# Portal lights help Karma sample outdoor light through small windows
# more efficiently. Without portals, tiny window openings cause heavy noise.

def create_interior_rig(stage_path="/stage",
                        window_positions=None):
    """
    Interior rig: window portals + practicals + ambient dome.
    window_positions: list of (tx, ty, tz, rx, ry, width, height) tuples.
    Practicals: SphereLight inside lamp geometry for realism.
    CylinderLights for tube fluorescent fixtures.
    Residential: 2700-3200K. Office: 4000-5000K.
    """
    stage = hou.node(stage_path)
    lights = []

    # --- WINDOW PORTAL LIGHTS (RectLight sized to match window opening) ---
    if window_positions:
        for i, (tx, ty, tz, rx, ry, w, h) in enumerate(window_positions):
            portal = stage.createNode("rectlight", f"window_portal_{i}")
            portal.parm("xn__inputsintensity_i0a").set(1.0)   # Lighting Law
            portal.parm("xn__inputsexposure_control_wcb").set("set")
            portal.parm("xn__inputsexposure_vya").set(4.0)    # match outdoor brightness
            portal.parm("tx").set(tx)
            portal.parm("ty").set(ty)
            portal.parm("tz").set(tz)
            portal.parm("rx").set(rx)
            portal.parm("ry").set(ry)
            portal.parm("sx").set(w)    # width matches window
            portal.parm("sz").set(h)    # height matches window
            portal.parm("xn__inputsnormalize_01a").set(True)
            lights.append(portal)
    else:
        # Default single window portal
        portal = stage.createNode("rectlight", "window_portal")
        portal.parm("xn__inputsintensity_i0a").set(1.0)
        portal.parm("xn__inputsexposure_control_wcb").set("set")
        portal.parm("xn__inputsexposure_vya").set(4.0)
        portal.parm("tx").set(0.0)
        portal.parm("ty").set(1.5)
        portal.parm("tz").set(-3.0)
        portal.parm("rx").set(0.0)
        portal.parm("ry").set(0.0)
        portal.parm("sx").set(1.2)
        portal.parm("sz").set(1.5)
        lights.append(portal)

    # --- TABLE LAMP PRACTICAL (SphereLight inside lamp geometry) ---
    lamp_a = stage.createNode("spherelight", "table_lamp_a")
    lamp_a.parm("xn__inputsintensity_i0a").set(1.0)   # Lighting Law
    lamp_a.parm("xn__inputsexposure_control_wcb").set("set")
    lamp_a.parm("xn__inputsexposure_vya").set(2.0)
    lamp_a.parm("tx").set(1.5)
    lamp_a.parm("ty").set(0.8)
    lamp_a.parm("tz").set(0.5)
    lamp_a.parm("xn__inputsenablecolortemperature_r5a").set(True)
    lamp_a.parm("xn__inputscolortemperature_u5a").set(2700)  # warm tungsten
    lights.append(lamp_a)

    # --- ACCENT LAMP PRACTICAL ---
    lamp_b = stage.createNode("spherelight", "table_lamp_b")
    lamp_b.parm("xn__inputsintensity_i0a").set(1.0)   # Lighting Law
    lamp_b.parm("xn__inputsexposure_control_wcb").set("set")
    lamp_b.parm("xn__inputsexposure_vya").set(1.5)
    lamp_b.parm("tx").set(-1.0)
    lamp_b.parm("ty").set(0.6)
    lamp_b.parm("tz").set(1.0)
    lamp_b.parm("xn__inputsenablecolortemperature_r5a").set(True)
    lamp_b.parm("xn__inputscolortemperature_u5a").set(2700)
    lights.append(lamp_b)

    # --- AMBIENT DOME — very low, just enough to prevent pure black ---
    # Exposure -1 to 0 keeps contrast; higher breaks the interior mood
    ambient = stage.createNode("domelight", "interior_ambient")
    ambient.parm("xn__inputsintensity_i0a").set(1.0)  # Lighting Law
    ambient.parm("xn__inputsexposure_control_wcb").set("set")
    ambient.parm("xn__inputsexposure_vya").set(-1.0)  # very subtle
    lights.append(ambient)

    return lights

create_interior_rig()
```

```python
import hou

# ============================================================
# COLOR TEMPERATURE SETUP
# ============================================================

def set_color_temperature(light_node, kelvin):
    """
    Switch a light to use Kelvin color temperature instead of RGB color.
    Useful for matching real-world sources and time-of-day accuracy.

    Color temperature reference:
      1800-2000K  candlelight / firelight
      2700-3200K  tungsten / incandescent (warm indoor)
      3500-4500K  golden hour / warm halogen
      5500-6500K  neutral daylight (noon sun)
      6500-7500K  overcast sky
      8000-10000K blue sky shade (cool shadow fill)
    """
    # Enable color temperature mode (overrides RGB color parm)
    light_node.parm("xn__inputsenablecolortemperature_r5a").set(True)
    light_node.parm("xn__inputscolortemperature_u5a").set(kelvin)


def set_rgb_color(light_node, r, g, b):
    """Set light color via RGB (0-1 range). Disables color temperature mode."""
    light_node.parm("xn__inputsenablecolortemperature_r5a").set(False)
    light_node.parmTuple("xn__inputscolor_kya").set((r, g, b))


# Examples
key = hou.node("/stage/key_light")
if key:
    set_color_temperature(key, 5500)    # neutral noon daylight key

fill = hou.node("/stage/fill_light")
if fill:
    set_color_temperature(fill, 6500)   # slightly cooler fill (sky bounce)
    # Or use a tinted RGB fill:
    # set_rgb_color(fill, 0.7, 0.85, 1.0)  # faint blue fill tint
```

```python
import hou

# ============================================================
# LIGHT SHAPING — SPOT / CONE + BARN DOORS
# ============================================================

def make_spot_light(stage_path="/stage", name="spot",
                    exposure=4.0, cone_angle=30.0, cone_softness=0.3):
    """
    Convert a SphereLight into a spot via shaping attributes.
    cone_angle: full cone angle in degrees (tighter = narrower beam)
    cone_softness: edge falloff 0=hard edge, 1=very soft edge
    """
    stage = hou.node(stage_path)
    spot = stage.createNode("spherelight", name)

    spot.parm("xn__inputsintensity_i0a").set(1.0)      # Lighting Law
    spot.parm("xn__inputsexposure_control_wcb").set("set")
    spot.parm("xn__inputsexposure_vya").set(exposure)

    # Shaping: cone angle and softness
    spot.parm("xn__inputsshapingconeangle_bobja").set(cone_angle)
    spot.parm("xn__inputsshapingconesoftness_brbja").set(cone_softness)

    # Optional: focus intensity toward cone center
    # spot.parm("xn__inputsshapingfocus_i5a").set(0.5)

    return spot


# Tight theatrical spot
theatre_spot = make_spot_light(name="theatre_spot",
                               exposure=5.0,
                               cone_angle=15.0,
                               cone_softness=0.1)   # hard edge

# Wide soft studio spot
studio_spot = make_spot_light(name="studio_spot",
                              exposure=3.5,
                              cone_angle=60.0,
                              cone_softness=0.6)    # soft falloff
```

```python
import hou

# ============================================================
# DIFFUSE / SPECULAR CONTRIBUTION SPLITTING
# ============================================================

def split_contribution(light_node, diffuse=1.0, specular=1.0):
    """
    Independently control a light's diffuse and specular contribution.
    Use cases:
      - diffuse=0, specular=1: specular-only eye highlight accent
      - diffuse=1, specular=0: diffuse-only fill (lifts shadows, no reflections)
      - diffuse=0.5, specular=1: half-strength diffuse, full specular
    """
    light_node.parm("xn__inputsdiffuse_vya").set(diffuse)
    light_node.parm("xn__inputsspecular_01a").set(specular)


# Art-direct specular eye-highlight light (does NOT shade the face)
eye_highlight = hou.node("/stage/eye_highlight")
if eye_highlight:
    split_contribution(eye_highlight, diffuse=0.0, specular=1.0)

# Diffuse-only fill (lifts dark areas without adding specular hotspots)
soft_fill = hou.node("/stage/soft_fill")
if soft_fill:
    split_contribution(soft_fill, diffuse=1.0, specular=0.0)
```

```python
import hou

# ============================================================
# SHADOW CONTROLS
# ============================================================

def configure_shadows(light_node, enabled=True, shadow_color=(0, 0, 0)):
    """
    Configure shadow casting on a light.
    Shadow softness = physical size of light source (larger = softer).
    Fill lights should have shadows disabled to avoid double-shadow artifacts.
    Shadow bias lives on the Karma render properties, not per-light.
    """
    light_node.parm("xn__inputsshadowenable_2kb").set(enabled)
    if shadow_color != (0, 0, 0):
        light_node.parmTuple("xn__inputsshadowcolor_o5a").set(shadow_color)


# Disable shadows on fill light (standard practice)
fill = hou.node("/stage/fill_light")
if fill:
    configure_shadows(fill, enabled=False)

# Soft shadows: make the source physically large
rect = hou.node("/stage/key_rect")
if rect:
    rect.parm("sx").set(5.0)   # large width  = soft shadows
    rect.parm("sz").set(5.0)   # large height = soft shadows

# Sharp shadows: small source
accent = hou.node("/stage/accent")
if accent:
    accent.parm("sx").set(0.1)
    accent.parm("sz").set(0.1)

# Tinted shadow (e.g., blue shadow for a cold key)
key = hou.node("/stage/key_light")
if key:
    configure_shadows(key, enabled=True, shadow_color=(0.1, 0.15, 0.3))
```

```python
import hou

# ============================================================
# LIGHT LINKING VIA COLLECTIONS (USD/Solaris)
# ============================================================
# Light linking controls which lights illuminate which objects.
# In USD, implemented through collection-based linking on light prims.
# LightLinker LOP provides an artist-friendly graph interface.

def create_light_link(stage_path="/stage",
                      light_prim_path="/lights/key_light",
                      geo_prim_path="/World/hero_character",
                      link_name="key_to_hero"):
    """
    Create a LightLinker LOP to restrict a light to specific geometry.
    The LightLinker node generates USD collection relationships on the light prim:
      collection:lightLink:includes  — geometry this light illuminates
      collection:lightLink:excludes  — geometry excluded from this light
    """
    stage = hou.node(stage_path)
    linker = stage.createNode("lightlinker", link_name)

    # Configure which light and which geometry
    # (LightLinker uses its own UI — set via parms or the node interface)
    # linker.parm("light1").set(light_prim_path)
    # linker.parm("geo1").set(geo_prim_path)

    return linker


# ---- Category-based linking (simpler) ----
# On the light LOP: assign a category tag string
key = hou.node("/stage/key_light")
if key:
    # Assign this light to the "hero_lights" category
    key.parm("lightcategories").set("hero_lights")

# On geometry LOP: specify which light categories affect it
# hero_geo = hou.node("/stage/hero_geo")
# hero_geo.parm("lightcategories").set("hero_lights")

# ---- Exclude key light from background geo ----
# Create a LightLinker and set up exclude relationship on background prims
# so the hero key doesn't spill onto the background set.
```

```python
import hou

# ============================================================
# EXPOSURE ADJUSTMENT WORKFLOW (correct order)
# ============================================================
# Step 1: Set key light exposure — anchors everything else
# Step 2: Adjust fill relative to key using ratio math
# Step 3: Set rim exposure by eye (typically 0.5–1.0 stops below key)
# Step 4: Adjust dome exposure last to control ambient level
# Step 5: NEVER touch intensity — always use exposure

import math

def adjust_rig_exposure(key_path, fill_path, rim_path, dome_path,
                        key_exposure, ratio=3.0, rim_offset=-0.5):
    """
    Adjust a complete rig's exposure values correctly.
    Never modifies intensity — only exposure parms.
    """
    fill_exposure = key_exposure - math.log2(ratio)
    rim_exposure  = key_exposure + rim_offset

    def _set_exp(node_path, exp_value):
        n = hou.node(node_path)
        if n:
            n.parm("xn__inputsexposure_control_wcb").set("set")
            n.parm("xn__inputsexposure_vya").set(exp_value)
            print(f"  {node_path} exposure = {exp_value:.3f}")

    print(f"Adjusting rig: key={key_exposure} fill={fill_exposure:.3f} "
          f"rim={rim_exposure:.3f} (ratio {ratio}:1)")
    _set_exp(key_path,  key_exposure)
    _set_exp(fill_path, fill_exposure)
    _set_exp(rim_path,  rim_exposure)
    # Dome last — set manually based on desired ambient level
    # _set_exp(dome_path, 0.0)  # call separately after reviewing a test render


# Lift entire rig brightness by 1 stop (double the light)
adjust_rig_exposure(
    key_path="/stage/key_light",
    fill_path="/stage/fill_light",
    rim_path="/stage/rim_light",
    dome_path="/stage/env_dome",
    key_exposure=6.0,   # was 5.0 — lifted by 1 stop
    ratio=3.0
)
```

## Common Mistakes

**Violating the Lighting Law (most critical)**
- Wrong: `node.parm("xn__inputsintensity_i0a").set(5.0)` — breaks energy conservation, causes fireflies and blown highlights
- Wrong: `node.parm("intensity").set(5.0)` — raw USD name does not work as a Houdini parm anyway
- Right: keep intensity at 1.0 always; set `xn__inputsexposure_vya` for brightness

**Wrong encoded parameter names**
- Wrong: `xn__inputsexposure_fya` — outdated/incorrect encoding
- Wrong: `inputs:exposure`, `light_exposure`, `exposure` (without Synapse alias resolution)
- Right: `xn__inputsexposure_vya` — verified for Houdini 21 Solaris lights

**Exposure is logarithmic — not linear**
- Exposure 10 is NOT twice as bright as exposure 5; it is 32x brighter (2^5 = 32)
- Negative exposure is valid: exposure -2 = 1/4 brightness (useful for moonlight, subtle fill)
- Exposure 0 does NOT turn a light off; it means 1x multiplier. Use `xn__inputsshadowenable_2kb = False` or disconnect the node to disable

**DomeLight mistakes**
- Position (`tx/ty/tz`) has NO effect on DomeLights — only rotation matters
- Two DomeLights in the same stage double the ambient level — use only one
- No texture file = uniform white environment (not black; will overexpose scenes)
- JPEG/PNG textures clip at 1.0 — no HDR range; use EXR or HDR format

**Area light normalization**
- When `xn__inputsnormalize_01a = False` (some types default to off), making the light bigger also makes it brighter
- Enable normalize on area lights for consistent behavior when resizing for shadow softness

**Missing exposure control enable**
- Setting `xn__inputsexposure_vya` without setting `xn__inputsexposure_control_wcb = "set"` may not take effect
- Always set the control parm first when using exposure overrides programmatically

**Fill light double shadows**
- Fill lights should almost always have `xn__inputsshadowenable_2kb = False`
- Two shadow-casting lights from different angles produce confusing crossed shadows

**Light not appearing in render**
- Check the light LOP is wired into the merge node that feeds render properties
- Check `xn__inputsdiffuse_vya` and `xn__inputsspecular_01a` are not both 0.0
- Check exposure is not extremely negative (e.g., -20 is effectively invisible)
- Check light linking collections are not accidentally excluding the target geometry
- Check the light prim is active (not muted in the LOP network)
