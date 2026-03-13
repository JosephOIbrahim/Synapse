"""
Synapse Recipe Registry -- Scene Recipes

Auto-extracted from the monolith recipes.py.
"""

from .base import Recipe, RecipeStep
from ...core.gates import GateLevel


def register_scene_recipes(registry):
    """Register scene recipes into the given registry."""

    # --- Scatter & Copy ---
    registry.register(Recipe(
        name="scatter_copy",
        description="Scatter source points onto target geometry using copy-to-points",
        triggers=[
            r"^scatter\s+(?P<source>[\w\-./]+)\s+(?:on(?:to)?|over)\s+(?P<target>[\w\-./]+)$",
        ],
        parameters=["source", "target"],
        gate_level=GateLevel.REVIEW,
        category="geometry",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "scatter",
                    "name": "scatter1",
                    "parent": "{target}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "copytopoints",
                    "name": "copytopoints1",
                    "parent": "{target}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="connect_nodes",
                payload_template={
                    "source": "{source}",
                    "target": "{target}/copytopoints1",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Null Controller ---
    registry.register(Recipe(
        name="null_controller",
        description="Create a null node as a controller with display flag",
        triggers=[
            r"^create\s+(?:a\s+)?(?:null\s+)?controller(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="utility",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "null",
                    "name": "controller",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/controller",
                    "parm": "controltype",
                    "value": 1,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Color Correction Setup (COPs) ---
    registry.register(Recipe(
        name="color_correction_setup",
        description="Create a color correction chain (color_correct -> grade -> null merge point)",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?color\s+correct(?:ion)?(?:\s+(?:chain|setup|stack))?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="compositing",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "colorcorrect",
                    "name": "color_correct1",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/color_correct1",
                    "parm": "saturation",
                    "value": 1.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "grade",
                    "name": "grade1",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="connect_nodes",
                payload_template={
                    "source": "{parent}/color_correct1",
                    "target": "{parent}/grade1",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Camera Rig ---
    registry.register(Recipe(
        name="camera_rig",
        description="Create a camera with focal length and position",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?camera(?:\s+(?:at|in)\s+(?P<parent>.+))?$",
            r"^(?:add)\s+(?:a\s+)?(?:render\s+)?camera(?:\s+(?:at|in)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="camera",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "cam",
                    "name": "render_cam",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
                output_var="cam",
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "{parent}/render_cam",
                    "parm": "focal",
                    "value": 50,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Material Quick Setup ---
    registry.register(Recipe(
        name="material_quick_setup",
        description="Create a MaterialX standard surface material and assign it",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:quick\s+)?material\s+(?:named?\s+)?(?P<name>\w+)$",
        ],
        parameters=["name"],
        gate_level=GateLevel.REVIEW,
        category="materials",
        steps=[
            RecipeStep(
                action="create_material",
                payload_template={
                    "name": "{name}",
                    "base_color": [0.8, 0.8, 0.8],
                    "roughness": 0.4,
                },
                gate_level=GateLevel.REVIEW,
                output_var="mat",
            ),
        ],
    ))

    # --- Terrain with Erosion ---
    registry.register(Recipe(
        name="terrain_environment",
        description=(
            "Create a heightfield terrain with noise shaping and "
            "hydraulic/thermal erosion for environment work."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?terrain(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?heightfield(?:\s+terrain)?(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:add|build)\s+(?:a\s+)?(?:terrain|landscape|environment\s+ground)(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="environment",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Heightfield base\n"
                        "hf = parent.createNode('heightfield', 'terrain_base')\n"
                        "hf.parm('sizex').set(500)\n"
                        "hf.parm('sizey').set(500)\n"
                        "hf.parm('gridspacing').set(1.0)\n"
                        "# Noise for shape\n"
                        "noise = parent.createNode('heightfield_noise', "
                        "'terrain_noise')\n"
                        "noise.parm('height').set(80)\n"
                        "noise.parm('noisefreq').set(0.005)\n"
                        "noise.parm('octaves').set(6)\n"
                        "noise.setInput(0, hf, 0)\n"
                        "# Hydraulic erosion\n"
                        "erode = parent.createNode('heightfield_erode', "
                        "'erosion')\n"
                        "erode.parm('iterations').set(50)\n"
                        "erode.setInput(0, noise, 0)\n"
                        "# Output null\n"
                        "out = parent.createNode('null', 'TERRAIN_OUT')\n"
                        "out.setInput(0, erode, 0)\n"
                        "out.setDisplayFlag(True)\n"
                        "out.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': out.path(), 'erosion': erode.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="terrain",
            ),
        ],
    ))

    # --- VEX Debug Wrangle ---
    registry.register(Recipe(
        name="vex_debug_wrangle",
        description=(
            "Debug a VEX wrangle node: inspect inputs, check for "
            "errors, read attribute state, and suggest fixes."
        ),
        triggers=[
            r"^(?:debug|diagnose|check|inspect)\s+(?:the\s+)?(?:vex|wrangle|attribwrangle)(?:\s+(?:on|at|node)?\s*(?P<node>.+))?$",
            r"^what(?:'s| is)\s+wrong\s+with\s+(?:the\s+)?(?:vex|wrangle)(?:\s+(?:on|at)?\s*(?P<node>.+))?$",
            r"^fix\s+(?:the\s+)?(?:vex|wrangle)\s+(?:on|at)\s+(?P<node>.+)$",
        ],
        parameters=["node"],
        gate_level=GateLevel.REVIEW,
        category="utility",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import json\n"
                        "node_path = '{node}'.strip()\n"
                        "# Find wrangle node\n"
                        "node = None\n"
                        "if node_path:\n"
                        "    node = hou.node(node_path)\n"
                        "if node is None:\n"
                        "    # Try to find selected wrangle\n"
                        "    sel = hou.selectedNodes()\n"
                        "    for s in sel:\n"
                        "        if 'wrangle' in s.type().name():\n"
                        "            node = s\n"
                        "            break\n"
                        "if node is None:\n"
                        "    result = {{'error': 'No wrangle node found "
                        "-- select one or provide a path'}}\n"
                        "else:\n"
                        "    info = {{'node': node.path(), "
                        "'type': node.type().name()}}\n"
                        "    # Get snippet\n"
                        "    snip_parm = node.parm('snippet') or "
                        "node.parm('code')\n"
                        "    if snip_parm:\n"
                        "        info['snippet'] = snip_parm.eval()\n"
                        "    # Get run-over class\n"
                        "    class_parm = node.parm('class')\n"
                        "    if class_parm:\n"
                        "        class_map = {{0: 'Detail', 1: 'Points', "
                        "2: 'Vertices', 3: 'Primitives'}}\n"
                        "        info['run_over'] = class_map.get("
                        "class_parm.eval(), 'unknown')\n"
                        "    # Check errors\n"
                        "    try:\n"
                        "        errs = node.errors()\n"
                        "        if errs:\n"
                        "            info['errors'] = list(errs)\n"
                        "    except Exception:\n"
                        "        pass\n"
                        "    try:\n"
                        "        warns = node.warnings()\n"
                        "        if warns:\n"
                        "            info['warnings'] = list(warns)\n"
                        "    except Exception:\n"
                        "        pass\n"
                        "    # Input geometry info\n"
                        "    inputs = []\n"
                        "    for i in range(4):\n"
                        "        inp = node.input(i)\n"
                        "        if inp:\n"
                        "            geo = inp.geometry()\n"
                        "            if geo:\n"
                        "                attrs = [a.name() for a in "
                        "geo.pointAttribs()]\n"
                        "                inputs.append({{'index': i, "
                        "'node': inp.path(), 'points': "
                        "len(geo.points()), 'attributes': attrs}})\n"
                        "    info['inputs'] = inputs\n"
                        "    result = info\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="debug",
            ),
        ],
    ))

    # --- Material Assign ---
    registry.register(Recipe(
        name="material_assign",
        description=(
            "Assign a material to geometry prims on the USD stage."
        ),
        triggers=[
            r"^assign\s+(?:material\s+)?(?P<material>[\w/]+)\s+to\s+(?P<target>.+)$",
            r"^(?:bind|apply)\s+material\s+(?P<material>[\w/]+)\s+(?:to|on)\s+(?P<target>.+)$",
        ],
        parameters=["material", "target"],
        gate_level=GateLevel.REVIEW,
        category="materials",
        steps=[
            RecipeStep(
                action="assign_material",
                payload_template={
                    "material_path": "{material}",
                    "prim_pattern": "{target}",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- VEX Noise Deformer ---
    registry.register(Recipe(
        name="vex_noise_deformer",
        description=(
            "Create a wrangle that deforms geometry with layered "
            "noise displacement along normals. Standard fBm pattern."
        ),
        triggers=[
            r"^(?:create|make|add)\s+(?:a\s+)?noise\s+(?:deform(?:er|ation)?|displacement)(?:\s+(?:on|to|at|in)\s+(?P<parent>.+))?$",
            r"^(?:create|make|add)\s+(?:a\s+)?(?:vex\s+)?(?:fbm|fractal)\s+(?:noise|deform)(?:\s+(?:on|to|at|in)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="geometry",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"  # noqa: E501
                        "parent_path = '{parent}'.strip()\n"
                        "parent = hou.node(parent_path) if parent_path "
                        "else None\n"
                        "if parent is None:\n"
                        "    sel = hou.selectedNodes()\n"
                        "    if sel:\n"
                        "        parent = sel[0].parent() if "
                        "sel[0].type().category() == "
                        "hou.sopNodeTypeCategory() else sel[0]\n"
                        "    else:\n"
                        "        parent = hou.node('/obj').createNode("
                        "'geo', 'noise_deform')\n"
                        "        parent.moveToGoodPosition()\n"
                        "wrangle = parent.createNode('attribwrangle', "
                        "'noise_deform')\n"
                        "wrangle.parm('snippet').set("
                        "'// fBm Noise Displacement\\n"
                        "float n = 0;\\n"
                        "float amp = chf(\"amplitude\");\\n"
                        "float freq = chf(\"frequency\");\\n"
                        "int octaves = chi(\"octaves\");\\n"
                        "float a = 1.0;\\n"
                        "float f = freq;\\n"
                        "for (int i = 0; i < octaves; i++) {{\\n"
                        "    n += snoise(@P * f + @Time * "
                        "chf(\"speed\")) * a;\\n"
                        "    f *= 2.0;\\n"
                        "    a *= 0.5;\\n"
                        "}}\\n"
                        "@P += @N * n * amp;\\n')\n"
                        "# Create channel references\n"
                        "ptg = wrangle.parmTemplateGroup()\n"
                        "ptg.append(hou.FloatParmTemplate("
                        "'amplitude', 'Amplitude', 1, "
                        "default_value=(0.5,)))\n"
                        "ptg.append(hou.FloatParmTemplate("
                        "'frequency', 'Frequency', 1, "
                        "default_value=(2.0,)))\n"
                        "ptg.append(hou.IntParmTemplate("
                        "'octaves', 'Octaves', 1, "
                        "default_value=(4,), min=1, max=8))\n"
                        "ptg.append(hou.FloatParmTemplate("
                        "'speed', 'Animation Speed', 1, "
                        "default_value=(0.5,)))\n"
                        "wrangle.setParmTemplateGroup(ptg)\n"
                        "# Wire to last selected or first input\n"
                        "sel = hou.selectedNodes()\n"
                        "if sel and sel[0].parent() == parent:\n"
                        "    wrangle.setInput(0, sel[0])\n"
                        "wrangle.setDisplayFlag(True)\n"
                        "wrangle.setRenderFlag(True)\n"
                        "wrangle.moveToGoodPosition()\n"
                        "result = {{'node': wrangle.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="deformer",
            ),
        ],
    ))

    # --- Verify Installation ---
    registry.register(Recipe(
        name="verify_installation",
        description=(
            "Compare source and deployed file checksums to "
            "detect installation drift"
        ),
        triggers=[
            r"^verify\s+(?:install(?:ation)?|deployment|sync)",
            r"^check\s+(?:install|drift|sync)",
        ],
        parameters=[],
        gate_level=GateLevel.INFORM,
        category="utility",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import os\n"
                        "import hashlib\n"
                        "import json\n"
                        "\n"
                        "def _file_hash(path):\n"
                        "    try:\n"
                        "        with open(path, 'rb') as f:\n"
                        "            return hashlib.sha256(f.read()).hexdigest()\n"
                        "    except (OSError, IOError):\n"
                        "        return None\n"
                        "\n"
                        "home = os.path.expanduser('~')\n"
                        "source_dir = os.path.join(home, '.synapse', 'houdini')\n"
                        "deploy_dir = os.path.join(home, 'houdini21.0')\n"
                        "\n"
                        "file_map = {\n"
                        "    'python_panels/synapse_panel.pypanel': "
                        "'python_panels/synapse_panel.pypanel',\n"
                        "    'toolbar/synapse.shelf': "
                        "'toolbar/synapse.shelf',\n"
                        "    'scripts/python/synapse_shelf.py': "
                        "'scripts/python/synapse_shelf.py',\n"
                        "}\n"
                        "\n"
                        "drift = []\n"
                        "missing = []\n"
                        "synced = []\n"
                        "\n"
                        "for src_rel, dst_rel in sorted(file_map.items()):\n"
                        "    src_path = os.path.join(source_dir, src_rel)\n"
                        "    dst_path = os.path.join(deploy_dir, dst_rel)\n"
                        "    src_hash = _file_hash(src_path)\n"
                        "    dst_hash = _file_hash(dst_path)\n"
                        "    if src_hash is None:\n"
                        "        missing.append({'file': src_rel, "
                        "'issue': 'source missing'})\n"
                        "    elif dst_hash is None:\n"
                        "        missing.append({'file': dst_rel, "
                        "'issue': 'not deployed'})\n"
                        "    elif src_hash != dst_hash:\n"
                        "        drift.append({'file': src_rel, "
                        "'source_hash': src_hash[:12], "
                        "'deployed_hash': dst_hash[:12]})\n"
                        "    else:\n"
                        "        synced.append(src_rel)\n"
                        "\n"
                        "result = json.dumps({'synced': len(synced), "
                        "'drift': drift, 'missing': missing"
                        "}, sort_keys=True)\n"
                        "if drift:\n"
                        "    result = json.dumps({'synced': len(synced), "
                        "'drift': drift, 'missing': missing, "
                        "'suggestion': "
                        "'Run: python ~/.synapse/install.py --verify'"
                        "}, sort_keys=True)\n"
                        "print(result)\n"
                    ),
                },
                gate_level=GateLevel.INFORM,
            ),
        ],
    ))


