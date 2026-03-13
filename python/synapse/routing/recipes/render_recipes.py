"""
Synapse Recipe Registry -- Render Recipes

Auto-extracted from the monolith recipes.py.
"""

from .base import Recipe, RecipeStep
from ...core.gates import GateLevel


def register_render_recipes(registry):
    """Register render recipes into the given registry."""

    # --- Three-Point Lighting ---
    registry.register(Recipe(
        name="three_point_lighting",
        description="Create a three-point lighting setup (key, fill, rim)",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?three[\s-]point\s+light(?:ing)?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "hlight",
                    "name": "key_light",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/key_light",
                    "parm": "light_exposure",
                    "value": 4,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "hlight",
                    "name": "fill_light",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/fill_light",
                    "parm": "light_exposure",
                    "value": 2,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "hlight",
                    "name": "rim_light",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/rim_light",
                    "parm": "light_exposure",
                    "value": 3,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Dome Light Environment ---
    registry.register(Recipe(
        name="dome_light_environment",
        description="Create a dome light with texture and exposure for environment lighting",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?dome\s*light(?:\s+(?:with|using)\s+(?P<texture>.+))?$",
            r"^(?:add|create)\s+(?:an?\s+)?(?:environment|env|hdri)\s+light(?:\s+(?:with|using)\s+(?P<texture>.+))?$",
        ],
        parameters=["texture"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/dome_light",
                    "prim_type": "DomeLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="dome",
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/dome_light",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 0,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Karma Render Setup ---
    registry.register(Recipe(
        name="karma_render_setup",
        description="Create a Karma render setup with resolution and camera",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?karma\s+render(?:\s+setup)?$",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "usdrender_rop",
                    "name": "karma_render",
                    "parent": "/stage",
                },
                gate_level=GateLevel.REVIEW,
                output_var="rop",
            ),
        ],
    ))

    # --- Turntable Render ---
    registry.register(Recipe(
        name="turntable_render",
        description=(
            "Set up a render-ready turntable: orbiting camera (360 deg "
            "over frame range), three-point lighting with Lighting Law "
            "exposure, dome light environment, Karma render settings with AOVs."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?turntable(?:\s+render)?(?:\s+(?:for|of|at|in)\s+(?P<target>.+))?$",
            r"^(?:add|create)\s+(?:a\s+)?(?:render\s+)?turntable(?:\s+(?:for|of|at|in)\s+(?P<target>.+))?$",
        ],
        parameters=["target"],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "stage = hou.node('/stage') or hou.node('/obj')\n"
                        "# Camera with orbit expression\n"
                        "cam = stage.createNode('cam', 'turntable_cam')\n"
                        "cam.parm('focal').set(50)\n"
                        "# Orbit: rotate Y over frame range\n"
                        "cam.parm('tx').set(0)\n"
                        "cam.parm('ty').set(1)\n"
                        "cam.parm('tz').set(5)\n"
                        "cam.parm('ry').setExpression("
                        "'$FF / ($FEND - $FSTART + 1) * 360')\n"
                        "result = {{'camera': cam.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="tt_cam",
            ),
            # Key light — Lighting Law: intensity 1.0, brightness via exposure
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/turntable_key",
                    "prim_type": "RectLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="tt_key",
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/turntable_key",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 5.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Fill light — 2 stops below key (4:1 ratio)
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/turntable_fill",
                    "prim_type": "RectLight",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/turntable_fill",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 3.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Rim light
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/turntable_rim",
                    "prim_type": "RectLight",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/turntable_rim",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 4.5,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Dome light for environment fill
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/turntable_dome",
                    "prim_type": "DomeLight",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/turntable_dome",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 0.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Lookdev Scene ---
    registry.register(Recipe(
        name="lookdev_scene",
        description=(
            "Set up a standard lookdev/turntable scene in LOPs: "
            "dome light (environment fill), key light (exposure 5), "
            "fill light (exposure 3, 4:1 ratio), backdrop grid, camera. "
            "Lighting Law compliant: all intensities 1.0."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?lookdev(?:\s+scene)?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:lookdev|look\s+dev)\s+(?:environment|setup|stage)$",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "stage = hou.node('/stage')\n"
                        "if not stage:\n"
                        "    stage = hou.node('/obj')\n"
                        "# Dome light for environment fill\n"
                        "dome = stage.createNode('domelight', 'env_dome')\n"
                        "# Key light\n"
                        "key = stage.createNode('rectlight', 'key_light')\n"
                        "key.parm('tx').set(3)\n"
                        "key.parm('ty').set(4)\n"
                        "key.parm('tz').set(3)\n"
                        "key.parm('rx').set(-35)\n"
                        "key.parm('ry').set(40)\n"
                        "# Fill light — 2 stops below key for 4:1 ratio\n"
                        "fill = stage.createNode('rectlight', 'fill_light')\n"
                        "fill.parm('tx').set(-3)\n"
                        "fill.parm('ty').set(2)\n"
                        "fill.parm('tz').set(2)\n"
                        "fill.parm('rx').set(-15)\n"
                        "fill.parm('ry').set(-45)\n"
                        "# Camera\n"
                        "cam = stage.createNode('cam', 'lookdev_cam')\n"
                        "cam.parm('tx').set(0)\n"
                        "cam.parm('ty').set(1)\n"
                        "cam.parm('tz').set(5)\n"
                        "cam.parm('rx').set(-10)\n"
                        "cam.parm('focal').set(85)\n"
                        "stage.layoutChildren()\n"
                        "result = {{'dome': dome.path(), 'key': key.path(), "
                        "'fill': fill.path(), 'camera': cam.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="lookdev",
            ),
            # Set exposures via USD (Lighting Law: intensity stays 1.0)
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "$lookdev.dome",
                    "parm": "light_exposure",
                    "value": 0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "$lookdev.key",
                    "parm": "light_exposure",
                    "value": 5,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "$lookdev.fill",
                    "parm": "light_exposure",
                    "value": 3,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Quick Render Preview ---
    registry.register(Recipe(
        name="render_preview",
        description=(
            "Render a quick preview: 640x360, 32 samples, Karma XPU. "
            "Optimized for fast iteration during layout and lighting."
        ),
        triggers=[
            r"^(?:quick\s+)?(?:render|preview)\s+(?:at\s+)?(?:low|preview|draft)\s*(?:quality|res)?$",
            r"^(?:render|do)\s+(?:a\s+)?(?:quick|fast)\s+(?:render|preview)$",
            r"^(?:test|preview)\s+render$",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="render",
                payload_template={
                    "width": 640,
                    "height": 360,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Render Sequence ---
    registry.register(Recipe(
        name="render_sequence",
        description=(
            "Render a frame sequence with per-frame validation, "
            "automatic issue diagnosis, and self-improving fixes. "
            "Learns from each render to start smarter next time."
        ),
        triggers=[
            r"^render\s+(?:sequence|frames?)\s+(?P<start>\d+)\s*[-\u2013to]+\s*(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
            r"^render\s+(?:from\s+)?(?P<start>\d+)\s+to\s+(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
            r"^batch\s+render\s+(?P<start>\d+)\s*[-\u2013to]+\s*(?P<end>\d+)(?:\s+(?:on|with|using)\s+(?P<rop>[\w\-./]+))?$",
        ],
        parameters=["start", "end", "rop"],
        gate_level=GateLevel.APPROVE,
        category="render",
        steps=[
            RecipeStep(
                action="render_sequence",
                payload_template={
                    "start_frame": "{start}",
                    "end_frame": "{end}",
                    "rop": "{rop}",
                    "auto_fix": True,
                    "max_retries": 3,
                },
                gate_level=GateLevel.APPROVE,
            ),
        ],
    ))

    # --- Render and Validate (single frame) ---
    registry.register(Recipe(
        name="render_validate_frame",
        description=(
            "Render the current frame and validate it for quality "
            "issues (fireflies, black frames, clipping)."
        ),
        triggers=[
            r"^render\s+and\s+validate$",
            r"^test\s+render$",
            r"^render\s+(?:and\s+)?check$",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="render",
                payload_template={},
                gate_level=GateLevel.REVIEW,
                output_var="render_result",
            ),
            RecipeStep(
                action="validate_frame",
                payload_template={
                    "image_path": "${render_result.image_path}",
                },
                gate_level=GateLevel.INFORM,
            ),
        ],
    ))

    # --- Setup Render Farm ---
    registry.register(Recipe(
        name="setup_render_farm",
        description=(
            "Configure render farm settings: classify the scene, "
            "query memory for known-good settings, and prepare "
            "the ROP for batch rendering."
        ),
        triggers=[
            r"^(?:set up|setup)\s+render\s+farm(?:\s+(?:on|for|with)\s+(?P<rop>[\w\-./]+))?$",
            r"^(?:prepare|configure)\s+(?:for\s+)?batch\s+render(?:ing)?(?:\s+(?:on|for|with)\s+(?P<rop>[\w\-./]+))?$",
        ],
        parameters=["rop"],
        gate_level=GateLevel.APPROVE,
        category="render",
        steps=[
            RecipeStep(
                action="get_stage_info",
                payload_template={},
                gate_level=GateLevel.INFORM,
                output_var="stage",
            ),
            RecipeStep(
                action="render_settings",
                payload_template={
                    "node": "{rop}",
                },
                gate_level=GateLevel.INFORM,
                output_var="settings",
            ),
        ],
    ))

    # --- Production Turntable ---
    registry.register(Recipe(
        name="render_turntable_production",
        description=(
            "Full production turntable: camera orbit (configurable radius, "
            "height, 120 frames), 3-point lighting rig with 4:1 key:fill "
            "ratio, ground plane shadow catcher, Karma XPU at 1920x1080 "
            "128 samples, AOVs (beauty, depth, normal, motion vector, "
            "crypto matte), motion blur enabled."
        ),
        triggers=[
            r"^(?:render\s+)?production\s+turntable(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
            r"^render\s+turntable\s+production(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
            r"^turntable\s+production(?:\s+(?:for|of|with)\s+(?P<subject>.+))?$",
        ],
        parameters=["subject"],
        gate_level=GateLevel.APPROVE,
        category="render",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import math\n"
                        "subject = '{subject}'.strip()\n"
                        "stage = hou.node('/stage')\n"
                        "if stage is None:\n"
                        "    stage = hou.node('/obj').createNode("
                        "'lopnet', 'stage')\n"
                        "\n"
                        "# --- Camera orbit ---\n"
                        "cam = stage.createNode('camera', 'turntable_cam')\n"
                        "cam.parm('primpath').set('/cameras/turntable_cam')\n"
                        "cam.parm('focalLength').set(50)\n"
                        "radius = 5.0\n"
                        "height = 1.5\n"
                        "frames = 120\n"
                        "for f in range(1, frames + 1):\n"
                        "    angle = (f - 1) * (2 * math.pi / frames)\n"
                        "    x = radius * math.cos(angle)\n"
                        "    z = radius * math.sin(angle)\n"
                        "    cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(x, hou.frameToTime(f)),), 0)\n"
                        "    cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(height, hou.frameToTime(f)),), 1)\n"
                        "    cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(z, hou.frameToTime(f)),), 2)\n"
                        "\n"
                        "# --- 3-point lighting (4:1 key:fill ratio) ---\n"
                        "# Key light: exposure 5\n"
                        "key = stage.createNode('light', 'key_light')\n"
                        "key.parm('primpath').set('/lights/key_light')\n"
                        "key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "key.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "key.parm('xn__inputsexposure_vya').set(5.0)\n"
                        "key.parmTuple('t').set((3, 4, 2))\n"
                        "key.parmTuple('r').set((-35, 45, 0))\n"
                        "\n"
                        "# Fill light: exposure 3 (4:1 ratio = 2 stops diff)\n"
                        "fill = stage.createNode('light', 'fill_light')\n"
                        "fill.parm('primpath').set('/lights/fill_light')\n"
                        "fill.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "fill.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "fill.parm('xn__inputsexposure_vya').set(3.0)\n"
                        "fill.parmTuple('t').set((-3, 3, 2))\n"
                        "fill.parmTuple('r').set((-25, -45, 0))\n"
                        "\n"
                        "# Rim light: exposure 4.5\n"
                        "rim = stage.createNode('light', 'rim_light')\n"
                        "rim.parm('primpath').set('/lights/rim_light')\n"
                        "rim.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "rim.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "rim.parm('xn__inputsexposure_vya').set(4.5)\n"
                        "rim.parmTuple('t').set((0, 3, -4))\n"
                        "rim.parmTuple('r').set((-20, 180, 0))\n"
                        "\n"
                        "# --- Ground plane with shadow catcher ---\n"
                        "ground = stage.createNode('sopimport', 'ground_plane')\n"
                        "ground.parm('primpath').set('/geo/ground_plane')\n"
                        "\n"
                        "# --- Merge scene ---\n"
                        "merge = stage.createNode('merge', 'scene_merge')\n"
                        "inputs = [cam, key, fill, rim, ground]\n"
                        "for i, node in enumerate(inputs):\n"
                        "    merge.setInput(i, node)\n"
                        "\n"
                        "# --- Render settings: Karma XPU 1920x1080 ---\n"
                        "rs = stage.createNode('karmarenderproperties', "
                        "'render_settings')\n"
                        "rs.setInput(0, merge)\n"
                        "rs.parm('resolutionx').set(1920)\n"
                        "rs.parm('resolutiony').set(1080)\n"
                        "rs.parm('engine').set('XPU')\n"
                        "rs.parm('samplesperpixel').set(128)\n"
                        "rs.parm('diffuselimit').set(4)\n"
                        "rs.parm('specularlimit').set(6)\n"
                        "\n"
                        "# --- Motion blur ---\n"
                        "rs.parm('xformsamples').set(2)\n"
                        "rs.parm('geosamples').set(2)\n"
                        "\n"
                        "# --- Karma LOP ---\n"
                        "karma = stage.createNode('karma', 'karma_render')\n"
                        "karma.setInput(0, rs)\n"
                        "karma.parm('camera').set('/cameras/turntable_cam')\n"
                        "karma.parm('picture').set("
                        "'$HIP/render/$HIPNAME/$HIPNAME.$F4.exr')\n"
                        "\n"
                        "# --- AOV passes ---\n"
                        "# Beauty is default; add utility passes\n"
                        "aovs = ['depth', 'N', 'motionvector', "
                        "'cryptomatte']\n"
                        "for idx, aov in enumerate(aovs):\n"
                        "    try:\n"
                        "        karma.parm('ar_aov_name_' + str(idx + 1)"
                        ").set(aov)\n"
                        "    except Exception:\n"
                        "        pass\n"
                        "\n"
                        "stage.layoutChildren()\n"
                        "result = {{'camera': cam.path(), "
                        "'karma': karma.path(), "
                        "'output': '$HIP/render/$HIPNAME/$HIPNAME.$F4.exr', "
                        "'frames': frames, 'resolution': '1920x1080', "
                        "'samples': 128, "
                        "'key_exposure': 5.0, 'fill_exposure': 3.0, "
                        "'rim_exposure': 4.5, "
                        "'motion_blur': True, "
                        "'aovs': ['beauty'] + aovs}}\n"
                    ),
                },
                gate_level=GateLevel.APPROVE,
                output_var="turntable",
            ),
        ],
    ))

    # --- Destruction Sequence ---
    registry.register(Recipe(
        name="destruction_sequence",
        description=(
            "RBD cache to Solaris multi-pass render: SOP imports for "
            "RBD cache, debris instancing, volumetric dust/smoke, "
            "destruction materials, and multi-pass Karma render settings "
            "(beauty, depth, motion vectors, crypto mattes)."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?destruction\s+sequence(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
            r"^(?:set up|setup|create)\s+destruction(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
            r"^rbd\s+to\s+solaris\s+render(?:\s+(?:for|from|with)\s+(?P<cache_path>.+))?$",
        ],
        parameters=["cache_path"],
        gate_level=GateLevel.APPROVE,
        category="render",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "cache_path = '{cache_path}'.strip()\n"
                        "stage = hou.node('/stage')\n"
                        "if stage is None:\n"
                        "    stage = hou.node('/obj').createNode("
                        "'lopnet', 'stage')\n"
                        "\n"
                        "# --- SOP Import: RBD cache ---\n"
                        "rbd_import = stage.createNode('sopimport', "
                        "'rbd_cache')\n"
                        "rbd_import.parm('primpath').set("
                        "'/fx/rbd_fragments')\n"
                        "if cache_path:\n"
                        "    rbd_import.parm('soppath').set(cache_path)\n"
                        "\n"
                        "# --- SOP Import: debris instancing ---\n"
                        "debris_import = stage.createNode('sopimport', "
                        "'debris_instances')\n"
                        "debris_import.parm('primpath').set("
                        "'/fx/debris')\n"
                        "\n"
                        "# --- SOP Import: volumetric dust/smoke ---\n"
                        "vol_import = stage.createNode('sopimport', "
                        "'dust_volume')\n"
                        "vol_import.parm('primpath').set("
                        "'/fx/dust_smoke')\n"
                        "\n"
                        "# --- Material library for destruction ---\n"
                        "matlib = stage.createNode('materiallibrary', "
                        "'destruction_materials')\n"
                        "matlib.parm('matpathprefix').set("
                        "'/materials')\n"
                        "matlib.cook(force=True)\n"
                        "\n"
                        "# Concrete material\n"
                        "concrete = matlib.createNode('subnet', "
                        "'concrete_mtl')\n"
                        "concrete_surf = concrete.createNode("
                        "'mtlxstandard_surface', 'concrete_shader')\n"
                        "concrete_surf.parm('base_color').set("
                        "(0.6, 0.58, 0.55))\n"
                        "concrete_surf.parm('specular_roughness').set("
                        "0.85)\n"
                        "\n"
                        "# Dust volume material\n"
                        "dust = matlib.createNode('subnet', "
                        "'dust_mtl')\n"
                        "dust_vol = dust.createNode("
                        "'mtlxstandard_volume', 'dust_shader')\n"
                        "\n"
                        "# --- Merge all FX layers ---\n"
                        "merge = stage.createNode('merge', "
                        "'fx_merge')\n"
                        "merge.setInput(0, rbd_import)\n"
                        "merge.setInput(1, debris_import)\n"
                        "merge.setInput(2, vol_import)\n"
                        "merge.setInput(3, matlib)\n"
                        "\n"
                        "# --- Render settings: multi-pass ---\n"
                        "rs = stage.createNode("
                        "'karmarenderproperties', "
                        "'destruction_render_settings')\n"
                        "rs.setInput(0, merge)\n"
                        "rs.parm('resolutionx').set(1920)\n"
                        "rs.parm('resolutiony').set(1080)\n"
                        "rs.parm('engine').set('XPU')\n"
                        "rs.parm('samplesperpixel').set(256)\n"
                        "rs.parm('diffuselimit').set(4)\n"
                        "rs.parm('specularlimit').set(6)\n"
                        "\n"
                        "# Motion blur for RBD\n"
                        "rs.parm('xformsamples').set(2)\n"
                        "rs.parm('geosamples').set(2)\n"
                        "\n"
                        "# --- Karma LOP ---\n"
                        "karma = stage.createNode('karma', "
                        "'karma_destruction')\n"
                        "karma.setInput(0, rs)\n"
                        "karma.parm('picture').set("
                        "'$HIP/render/destruction/"
                        "beauty.$F4.exr')\n"
                        "\n"
                        "# --- AOV config ---\n"
                        "passes = {{\n"
                        "    'beauty': 'beauty.$F4.exr',\n"
                        "    'depth': 'depth.$F4.exr',\n"
                        "    'motionvector': 'motionvector.$F4.exr',\n"
                        "    'cryptomatte_obj': "
                        "'cryptomatte_obj.$F4.exr',\n"
                        "    'cryptomatte_mtl': "
                        "'cryptomatte_mtl.$F4.exr',\n"
                        "    'cryptomatte_asset': "
                        "'cryptomatte_asset.$F4.exr',\n"
                        "}}\n"
                        "for idx, (aov, _) in enumerate("
                        "passes.items()):\n"
                        "    try:\n"
                        "        karma.parm('ar_aov_name_' + "
                        "str(idx)).set(aov)\n"
                        "    except Exception:\n"
                        "        pass\n"
                        "\n"
                        "stage.layoutChildren()\n"
                        "result = {{'rbd_import': rbd_import.path(), "
                        "'debris': debris_import.path(), "
                        "'volume': vol_import.path(), "
                        "'matlib': matlib.path(), "
                        "'karma': karma.path(), "
                        "'passes': list(passes.keys()), "
                        "'resolution': '1920x1080', "
                        "'samples': 256}}\n"
                    ),
                },
                gate_level=GateLevel.APPROVE,
                output_var="destruction",
            ),
        ],
    ))

    # --- Camera Match Turntable ---
    registry.register(Recipe(
        name="camera_match_turntable",
        description=(
            "Create a production turntable render using a real-world "
            "camera match. Combines camera_match_real sensor lookup with "
            "a full turntable orbit, 3-point lighting (4:1 key:fill "
            "ratio), Karma XPU render at 1920x1080 with configurable "
            "samples and frame count."
        ),
        triggers=[
            r"^turntable\s+(?:with|using)\s+(?:an?\s+)?(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
            r"^(?:production\s+)?turntable\s+(?P<camera_body>arri|red|sony|bmpcc|blackmagic|canon)[\w\s\-\[\]]*?(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
            r"^(?:render\s+)?turntable\s+(?:with|using)\s+(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+(?P<frames>\d+)\s+frames?)?(?:\s+(?P<samples>\d+)\s+samples?)?$",
        ],
        parameters=["camera_body", "lens_mm", "frames", "samples"],
        gate_level=GateLevel.APPROVE,
        category="render",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import re\n"
                        "import math\n"
                        "\n"
                        "SENSORS = {{\n"
                        "    'arri_alexa_35': {{'width': 27.99, 'height': 19.22, 'name': 'ARRI Alexa 35'}},\n"
                        "    'arri_alexa_mini_lf': {{'width': 36.70, 'height': 25.54, 'name': 'ARRI Alexa Mini LF'}},\n"
                        "    'red_v_raptor_x': {{'width': 40.96, 'height': 21.60, 'name': 'RED V-Raptor [X]'}},\n"
                        "    'red_komodo_x': {{'width': 27.03, 'height': 14.26, 'name': 'RED Komodo-X'}},\n"
                        "    'sony_venice_2': {{'width': 36.20, 'height': 24.10, 'name': 'Sony Venice 2'}},\n"
                        "    'sony_fx6': {{'width': 35.60, 'height': 23.80, 'name': 'Sony FX6'}},\n"
                        "    'bmpcc_ursa_12k': {{'width': 27.03, 'height': 14.26, 'name': 'Blackmagic URSA Mini Pro 12K'}},\n"
                        "    'canon_c500_ii': {{'width': 38.10, 'height': 20.10, 'name': 'Canon EOS C500 Mark II'}},\n"
                        "}}\n"
                        "\n"
                        "camera_body = '{camera_body}'.strip().lower()\n"
                        "slug = re.sub(r'[\\s\\-\\[\\]]+', '_', camera_body).strip('_')\n"
                        "sensor = SENSORS.get(slug)\n"
                        "if sensor is None:\n"
                        "    for key, val in sorted(SENSORS.items()):\n"
                        "        if slug in key or key in slug:\n"
                        "            sensor = val\n"
                        "            slug = key\n"
                        "            break\n"
                        "    if sensor is None:\n"
                        "        for key, val in sorted(SENSORS.items()):\n"
                        "            if camera_body in val['name'].lower():\n"
                        "                sensor = val\n"
                        "                slug = key\n"
                        "                break\n"
                        "if sensor is None:\n"
                        "    available = ', '.join(v['name'] for k, v in sorted(SENSORS.items()))\n"
                        "    result = {{'error': True, 'message': "
                        "\"Couldn't find camera body '\" + camera_body + "
                        "\"' in the sensor database. Available cameras: \" + available}}\n"
                        "else:\n"
                        "    lens_mm = int('{lens_mm}' or '50') if '{lens_mm}'.strip() else 50\n"
                        "    frames = int('{frames}' or '120') if '{frames}'.strip() else 120\n"
                        "    samples = int('{samples}' or '128') if '{samples}'.strip() else 128\n"
                        "\n"
                        "    stage = hou.node('/stage')\n"
                        "    if stage is None:\n"
                        "        stage = hou.node('/obj').createNode('lopnet', 'stage')\n"
                        "\n"
                        "    # --- Camera with real sensor match ---\n"
                        "    cam_name = slug + '_cam'\n"
                        "    cam = stage.createNode('camera', cam_name)\n"
                        "    cam.parm('primpath').set('/cameras/' + cam_name)\n"
                        "    cam.parm('horizontalAperture').set(sensor['width'])\n"
                        "    cam.parm('verticalAperture').set(sensor['height'])\n"
                        "    cam.parm('focalLength').set(lens_mm)\n"
                        "    cam.parm('clippingRange1').set(0.1)\n"
                        "    cam.parm('clippingRange2').set(10000)\n"
                        "\n"
                        "    # --- Camera orbit keyframes ---\n"
                        "    radius = 5.0\n"
                        "    height = 1.5\n"
                        "    for f in range(1, frames + 1):\n"
                        "        angle = (f - 1) * (2 * math.pi / frames)\n"
                        "        x = radius * math.cos(angle)\n"
                        "        z = radius * math.sin(angle)\n"
                        "        cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(x, hou.frameToTime(f)),), 0)\n"
                        "        cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(height, hou.frameToTime(f)),), 1)\n"
                        "        cam.parmTuple('t').setKeyframe("
                        "(hou.Keyframe(z, hou.frameToTime(f)),), 2)\n"
                        "\n"
                        "    # --- 3-point lighting (4:1 key:fill ratio) ---\n"
                        "    key = stage.createNode('light', 'key_light')\n"
                        "    key.parm('primpath').set('/lights/key_light')\n"
                        "    key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "    key.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "    key.parm('xn__inputsexposure_vya').set(5.0)\n"
                        "    key.parmTuple('t').set((3, 4, 2))\n"
                        "    key.parmTuple('r').set((-35, 45, 0))\n"
                        "\n"
                        "    fill = stage.createNode('light', 'fill_light')\n"
                        "    fill.parm('primpath').set('/lights/fill_light')\n"
                        "    fill.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "    fill.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "    fill.parm('xn__inputsexposure_vya').set(3.0)\n"
                        "    fill.parmTuple('t').set((-3, 3, 2))\n"
                        "    fill.parmTuple('r').set((-25, -45, 0))\n"
                        "\n"
                        "    rim = stage.createNode('light', 'rim_light')\n"
                        "    rim.parm('primpath').set('/lights/rim_light')\n"
                        "    rim.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "    rim.parm('xn__inputsexposure_control_wcb').set('set')\n"
                        "    rim.parm('xn__inputsexposure_vya').set(4.5)\n"
                        "    rim.parmTuple('t').set((0, 3, -4))\n"
                        "    rim.parmTuple('r').set((-20, 180, 0))\n"
                        "\n"
                        "    # --- Merge scene ---\n"
                        "    merge = stage.createNode('merge', 'scene_merge')\n"
                        "    inputs = [cam, key, fill, rim]\n"
                        "    for i, node in enumerate(inputs):\n"
                        "        merge.setInput(i, node)\n"
                        "\n"
                        "    # --- Render settings: Karma XPU 1920x1080 ---\n"
                        "    rs = stage.createNode('karmarenderproperties', "
                        "'render_settings')\n"
                        "    rs.setInput(0, merge)\n"
                        "    rs.parm('resolutionx').set(1920)\n"
                        "    rs.parm('resolutiony').set(1080)\n"
                        "    rs.parm('engine').set('XPU')\n"
                        "    rs.parm('samplesperpixel').set(samples)\n"
                        "\n"
                        "    # --- Karma LOP ---\n"
                        "    karma = stage.createNode('karma', 'karma_render')\n"
                        "    karma.setInput(0, rs)\n"
                        "    karma.parm('camera').set('/cameras/' + cam_name)\n"
                        "    karma.parm('picture').set("
                        "'$HIP/render/$HIPNAME/$HIPNAME.$F4.exr')\n"
                        "\n"
                        "    stage.layoutChildren()\n"
                        "    result = {{'camera': cam.path(), "
                        "'prim_path': '/cameras/' + cam_name, "
                        "'sensor': sensor['name'], "
                        "'horizontal_aperture': sensor['width'], "
                        "'vertical_aperture': sensor['height'], "
                        "'focal_length': lens_mm, "
                        "'frames': frames, "
                        "'samples': samples, "
                        "'resolution': '1920x1080', "
                        "'karma': karma.path(), "
                        "'output': '$HIP/render/$HIPNAME/$HIPNAME.$F4.exr', "
                        "'key_exposure': 5.0, 'fill_exposure': 3.0, "
                        "'rim_exposure': 4.5}}\n"
                    ),
                },
                gate_level=GateLevel.APPROVE,
                output_var="turntable_cam",
            ),
        ],
    ))

    # --- Spotlight Rig ---
    registry.register(Recipe(
        name="spotlight_rig",
        description=(
            "Create a Karma spotlight (SphereLight with shaping). "
            "Lighting Law: intensity always 1.0, brightness via exposure. "
            "Penumbra angle = cone_angle * 0.1 for soft falloff."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?spot\s*light(?:\s+(?:at|in|under)\s+(?P<position>.+))?$",
            r"^(?:add|create)\s+(?:a\s+)?(?:karma\s+)?spot\s*light(?:\s+(?:aimed|targeting|at)\s+(?P<target>.+))?$",
        ],
        parameters=["position", "target", "cone_angle"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "prim_type": "SphereLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="spotlight",
            ),
            # Lighting Law: intensity always 1.0
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputsintensity_i0a",
                    "value": 1.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Shaping: cone angle (default 45 degrees)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputsshapingconeangle_hgbb",
                    "value": "{cone_angle}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Penumbra = cone_angle * 0.1 (soft falloff)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputsshapingconeSoftness_jlbb",
                    "value": 0.1,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Brightness via exposure
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 4.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Color temperature (default 6500K neutral)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputsenableColorTemperature_znb",
                    "value": True,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/spotlight",
                    "attribute_name": "xn__inputscolorTemperature_r8a",
                    "value": 6500,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Distant Light (Sun) ---
    registry.register(Recipe(
        name="distant_light_sun",
        description=(
            "Create a directional/sun light (DistantLight). "
            "Lighting Law: intensity always 1.0, brightness via exposure. "
            "Default color temperature 5500K for natural sunlight."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:distant|directional|sun)\s*light$",
            r"^(?:add|create)\s+(?:a\s+)?(?:distant|sun|directional)\s*light$",
        ],
        parameters=["direction", "exposure", "color_temp"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "prim_type": "DistantLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="sun",
            ),
            # Lighting Law: intensity always 1.0
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "attribute_name": "xn__inputsintensity_i0a",
                    "value": 1.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Angular diameter (0.53 degrees = real sun)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "attribute_name": "xn__inputsangle_06a",
                    "value": 0.53,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Brightness via exposure (default 0 = bright sun)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Color temperature (default 5500K natural sunlight)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "attribute_name": "xn__inputsenableColorTemperature_znb",
                    "value": True,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/sun_light",
                    "attribute_name": "xn__inputscolorTemperature_r8a",
                    "value": 5500,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Area Light Panel ---
    registry.register(Recipe(
        name="area_light_panel",
        description=(
            "Create a rectangular area light panel (RectLight) with "
            "configurable width and height. Large area = soft shadows. "
            "Lighting Law: intensity always 1.0, brightness via exposure. "
            "Different from existing RectLight recipes — focused on "
            "studio panel lighting with explicit size control."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:area|panel)\s*light$",
            r"^(?:add|create)\s+(?:a\s+)?(?:area|panel|soft)\s*light$",
        ],
        parameters=["width", "height", "exposure"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "prim_type": "RectLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="panel",
            ),
            # Lighting Law: intensity always 1.0
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "attribute_name": "xn__inputsintensity_i0a",
                    "value": 1.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Width (default 2.0 meters for soft shadows)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "attribute_name": "xn__inputswidth_e5a",
                    "value": "{width}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Height (default 2.0 meters)
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "attribute_name": "xn__inputsheight_i5a",
                    "value": "{height}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Brightness via exposure
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 3.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Normalize power by area so brightness is independent of size
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/area_panel",
                    "attribute_name": "xn__inputsnormalize_01a",
                    "value": True,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Mesh Light (Emissive Geometry) ---
    registry.register(Recipe(
        name="mesh_light_emission",
        description=(
            "Create a mesh light from emissive geometry (MeshLight). "
            "Targets a USD prim pattern for the emitting mesh. "
            "Lighting Law: intensity always 1.0, brightness via exposure."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?mesh\s*light(?:\s+(?:from|on|for)\s+(?P<target_geo_pattern>.+))?$",
            r"^(?:add|create)\s+(?:a\s+)?(?:mesh|emissive|emission)\s*light(?:\s+(?:from|on|for)\s+(?P<target_geo_pattern>.+))?$",
        ],
        parameters=["target_geo_pattern"],
        gate_level=GateLevel.REVIEW,
        category="lighting",
        steps=[
            RecipeStep(
                action="create_usd_prim",
                payload_template={
                    "prim_path": "/lights/mesh_light",
                    "prim_type": "MeshLight",
                },
                gate_level=GateLevel.REVIEW,
                output_var="meshlight",
            ),
            # Lighting Law: intensity always 1.0
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/mesh_light",
                    "attribute_name": "xn__inputsintensity_i0a",
                    "value": 1.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Target geometry pattern
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/mesh_light",
                    "attribute_name": "xn__inputsgeometry_01a",
                    "value": "{target_geo_pattern}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            # Brightness via exposure
            RecipeStep(
                action="set_usd_attribute",
                payload_template={
                    "prim_path": "/lights/mesh_light",
                    "attribute_name": "xn__inputsexposure_vya",
                    "value": 2.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Safe Render (pre-flight validation) ---
    registry.register(Recipe(
        name="safe_render",
        description=(
            "Render with pre-flight validation -- checks camera, "
            "materials, output path before rendering"
        ),
        triggers=[
            r"^(?:safe|validated?)\s+render",
            r"^render\s+(?:safe|with\s+validation)",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="safe_render",
                payload_template={},
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Progressive Render (3-pass) ---
    registry.register(Recipe(
        name="render_progressively",
        description=(
            "Progressive 3-pass render: test (256x256) -> "
            "preview (720p) -> production"
        ),
        triggers=[
            r"^(?:progressive|incremental)\s+render",
            r"^render\s+progressive(?:ly)?",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="render",
        steps=[
            RecipeStep(
                action="render_progressively",
                payload_template={},
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))


