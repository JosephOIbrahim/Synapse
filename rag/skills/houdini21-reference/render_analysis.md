# Render Analysis Guide

## Triggers
render analysis, exposure analysis, noise, fireflies, lighting check, material quality,
composition, stop math, denoiser, convergence, render iteration, lookdev

## Context
Analyzing renders for production quality: exposure/stop math, noise diagnosis,
lighting composition, material quality checks. All code is Houdini Python.

## Code

```python
# Exposure analysis and adjustment via Synapse
import hou

def analyze_exposure(karma_props_path, lights=None):
    """Analyze and adjust lighting exposure.
    All adjustments use exposure (stops), never intensity.
    Stop math: +1 stop = 2x brighter, -1 stop = 0.5x brightness."""
    node = hou.node(karma_props_path)
    if not node:
        return

    # Stop math reference
    STOP_MATH = {
        "+1 stop": "2x brighter",
        "-1 stop": "0.5x brightness",
        "+2 stops": "4x brighter",
        "-2 stops": "0.25x brightness",
        "+0.5 stop": "~1.4x brighter",
    }

    if lights is None:
        lights = {
            "key":  "/stage/key_light",
            "fill": "/stage/fill_light",
            "rim":  "/stage/rim_light",
            "dome": "/stage/dome_light",
        }

    report = {}
    for role, path in lights.items():
        light = hou.node(path)
        if not light:
            continue
        exposure = light.evalParm("xn__inputsexposure_vya") if light.parm("xn__inputsexposure_vya") else 0
        intensity = light.evalParm("xn__inputsintensity_i0a") if light.parm("xn__inputsintensity_i0a") else 1.0
        report[role] = {"exposure": exposure, "intensity": intensity, "path": path}

        # Flag violations
        if intensity > 1.0:
            print(f"  WARNING: {role} intensity={intensity} > 1.0 (violates Lighting Law)")

    # Key:fill ratio analysis
    if "key" in report and "fill" in report:
        key_exp = report["key"]["exposure"]
        fill_exp = report["fill"]["exposure"]
        ratio = 2 ** (key_exp - fill_exp)
        print(f"Key:fill ratio: {ratio:.1f}:1 ({key_exp - fill_exp:.1f} stops difference)")

    return report


def adjust_light_exposure(light_path, delta_stops):
    """Adjust a light's exposure by delta stops.
    +1 = double brightness, -1 = halve brightness."""
    light = hou.node(light_path)
    if not light:
        return
    parm = light.parm("xn__inputsexposure_vya")
    if parm:
        current = parm.eval()
        parm.set(current + delta_stops)
        print(f"Exposure: {current:.1f} -> {current + delta_stops:.1f} ({'+' if delta_stops > 0 else ''}{delta_stops} stops)")

# Too dark overall: increase key light by 1 stop
adjust_light_exposure("/stage/key_light", 1.0)

# Fill too weak: increase fill by 0.5 stops
adjust_light_exposure("/stage/fill_light", 0.5)
```

```python
# Noise analysis and sample settings
import hou

NOISE_TYPES = {
    "general":  {"fix": "Increase max samples (128 -> 256)", "parm": "karma:global:pathtracedsamples"},
    "shadow":   {"fix": "Increase min samples, use variance oracle", "parm": "karma:global:minpathtracedsamples"},
    "specular": {"fix": "Enable clamping, increase specular bounces", "parm": "karma:global:reflectlimit"},
    "volume":   {"fix": "Increase volume step rate (0.5 -> 1.0)", "parm": "karma:global:volumesteprate"},
    "caustic":  {"fix": "Enable caustics with higher samples, or disable caustics", "parm": None},
}

QUALITY_PRESETS = {
    "preview": {
        "karma:global:pathtracedsamples": 32,
        "karma:global:pixeloracle": "uniform",
    },
    "lookdev": {
        "karma:global:pathtracedsamples": 64,
        "karma:global:minpathtracedsamples": 4,
        "karma:global:pixeloracle": "variance",
        "karma:global:convergencethreshold": 0.01,
    },
    "production": {
        "karma:global:pathtracedsamples": 256,
        "karma:global:minpathtracedsamples": 16,
        "karma:global:pixeloracle": "variance",
        "karma:global:convergencethreshold": 0.005,
    },
}


def diagnose_noise(karma_props_path):
    """Diagnose noise issues from render settings."""
    node = hou.node(karma_props_path)
    if not node:
        return []
    issues = []
    samples = node.evalParm("karma:global:pathtracedsamples") if node.parm("karma:global:pathtracedsamples") else 0
    if samples < 64:
        issues.append(f"Low max samples ({samples}) -- increase to 128+ for clean result")
    min_samples = node.evalParm("karma:global:minpathtracedsamples") if node.parm("karma:global:minpathtracedsamples") else 0
    if min_samples < 4:
        issues.append(f"Low min samples ({min_samples}) -- increase to 4+ to reduce shadow noise")
    oracle = node.evalParm("karma:global:pixeloracle") if node.parm("karma:global:pixeloracle") else ""
    if oracle != "variance":
        issues.append(f"Pixel oracle is '{oracle}' -- use 'variance' for adaptive sampling")
    threshold = node.evalParm("karma:global:convergencethreshold") if node.parm("karma:global:convergencethreshold") else 0
    if threshold > 0.01:
        issues.append(f"High convergence threshold ({threshold}) -- lower to 0.005 for production")

    for issue in issues:
        print(f"  - {issue}")
    return issues


def apply_quality_preset(karma_props_path, preset_name):
    """Apply a quality preset for noise reduction."""
    node = hou.node(karma_props_path)
    if not node:
        return
    preset = QUALITY_PRESETS.get(preset_name)
    if not preset:
        return
    for parm_name, value in preset.items():
        p = node.parm(parm_name)
        if p:
            p.set(value)
    print(f"Applied '{preset_name}' preset")

diagnose_noise("/stage/karmarenderproperties1")
apply_quality_preset("/stage/karmarenderproperties1", "lookdev")
```

```python
# Material quality validation
import hou

MATERIAL_ISSUES = {
    "fireflies":    {"check": "roughness < 0.001", "fix": "Set roughness minimum 0.001"},
    "plastic_look": {"check": "uniform roughness", "fix": "Add roughness variation via texture"},
    "black_metal":  {"check": "metal with no env light", "fix": "Add dome light for reflections"},
    "bad_metalness":{"check": "metalness between 0.3-0.7", "fix": "Use 0.0 (dielectric) or 1.0 (metal)"},
}


def check_material_quality(material_path):
    """Check material for common quality issues."""
    node = hou.node(material_path)
    if not node:
        return []
    issues = []

    # Check roughness
    roughness_parm = node.parm("roughness")
    if roughness_parm:
        roughness = roughness_parm.eval()
        if roughness == 0.0:
            issues.append("Roughness is exactly 0.0 -- causes fireflies. Use 0.001 minimum.")
        elif roughness < 0.001:
            issues.append(f"Roughness {roughness} is very low -- may cause fireflies.")

    # Check metalness
    metalness_parm = node.parm("metalness")
    if metalness_parm:
        metalness = metalness_parm.eval()
        if 0.3 < metalness < 0.7:
            issues.append(f"Metalness {metalness} is in 0.3-0.7 range (physically incorrect). Use 0.0 or 1.0.")

    for issue in issues:
        print(f"  - {issue}")
    return issues
```

```python
# Lighting composition analysis
import hou
import math

LIGHTING_SCENARIOS = {
    "product_beauty": {"key_fill_ratio": 2.0, "env_exposure": 1.0, "mood": "Clean, inviting"},
    "broadcast":      {"key_fill_ratio": 3.0, "env_exposure": 1.0, "mood": "Professional, clear"},
    "dramatic":       {"key_fill_ratio": 4.0, "env_exposure": 0.0, "mood": "Moody, cinematic"},
    "horror_noir":    {"key_fill_ratio": 8.0, "env_exposure": -1.0, "mood": "Dark, tense"},
    "overcast":       {"key_fill_ratio": 1.5, "env_exposure": 2.0, "mood": "Soft, natural"},
}


def setup_lighting_scenario(scenario_name, key_path, fill_path, dome_path, key_base_exposure=5.0):
    """Configure lights for a specific scenario.
    key_base_exposure: absolute exposure for key light."""
    scenario = LIGHTING_SCENARIOS.get(scenario_name)
    if not scenario:
        print(f"Unknown scenario. Available: {list(LIGHTING_SCENARIOS.keys())}")
        return

    ratio = scenario["key_fill_ratio"]
    fill_offset = math.log2(ratio)  # Stops below key

    key = hou.node(key_path)
    fill = hou.node(fill_path)
    dome = hou.node(dome_path)

    if key and key.parm("xn__inputsexposure_vya"):
        key.parm("xn__inputsexposure_vya").set(key_base_exposure)
    if fill and fill.parm("xn__inputsexposure_vya"):
        fill.parm("xn__inputsexposure_vya").set(key_base_exposure - fill_offset)
    if dome and dome.parm("xn__inputsexposure_vya"):
        dome.parm("xn__inputsexposure_vya").set(scenario["env_exposure"])

    print(f"Scenario '{scenario_name}': {scenario['mood']}")
    print(f"  Key: {key_base_exposure}, Fill: {key_base_exposure - fill_offset:.1f} ({ratio}:1 ratio)")
    print(f"  Environment: {scenario['env_exposure']}")


setup_lighting_scenario("dramatic", "/stage/key_light", "/stage/fill_light", "/stage/dome_light")
```

```python
# Progressive render iteration workflow
import hou

ITERATION_STAGES = {
    "blocking": {
        "description": "Layout and composition check",
        "width": 640, "height": 360,
        "samples": 16, "oracle": "uniform",
        "check": ["composition", "lighting direction", "overall exposure"],
    },
    "lookdev": {
        "description": "Material and color check",
        "width": 1280, "height": 720,
        "samples": 64, "oracle": "variance",
        "check": ["material quality", "noise", "color accuracy"],
    },
    "final": {
        "description": "Production quality",
        "width": 1920, "height": 1080,
        "samples": 256, "oracle": "variance",
        "check": ["no clipping", "no noise", "no artifacts", "AOVs present"],
    },
}


def configure_iteration_stage(rop_path, karma_props_path, stage_name):
    """Set up render for a specific iteration stage."""
    stage = ITERATION_STAGES.get(stage_name)
    if not stage:
        return

    rop = hou.node(rop_path)
    props = hou.node(karma_props_path)
    if not rop or not props:
        return

    # Resolution
    rop.parm("override_res").set("specific")
    rop.parm("res_user1").set(stage["width"])
    rop.parm("res_user2").set(stage["height"])

    # Samples
    if props.parm("karma:global:pathtracedsamples"):
        props.parm("karma:global:pathtracedsamples").set(stage["samples"])
    if props.parm("karma:global:pixeloracle"):
        props.parm("karma:global:pixeloracle").set(stage["oracle"])

    # Enable denoiser only for lookdev+
    if props.parm("karma:global:enabledenoise"):
        props.parm("karma:global:enabledenoise").set(1 if stage_name != "blocking" else 0)

    print(f"Stage '{stage_name}': {stage['description']}")
    print(f"  Resolution: {stage['width']}x{stage['height']}, Samples: {stage['samples']}")
    print(f"  Check: {', '.join(stage['check'])}")


configure_iteration_stage("/out/karma_render", "/stage/karmarenderproperties1", "lookdev")
```

## Common Mistakes
- Setting light intensity > 1.0 -- violates Lighting Law; use exposure for brightness
- Roughness exactly 0.0 -- causes fireflies; use 0.001 minimum
- Metalness in 0.3-0.7 range -- physically incorrect; use 0.0 (dielectric) or 1.0 (metal)
- Low samples (16) with heavy denoiser -- produces smearing; use 64+ base samples
- Jumping to production quality -- iterate at low resolution first, scale up incrementally
- Pixel oracle set to "uniform" for production -- use "variance" for adaptive sampling
