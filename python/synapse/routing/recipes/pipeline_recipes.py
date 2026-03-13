"""
Synapse Recipe Registry -- Pipeline Recipes

Auto-extracted from the monolith recipes.py.
"""

from .base import Recipe, RecipeStep
from ...core.gates import GateLevel


def register_pipeline_recipes(registry):
    """Register pipeline recipes into the given registry."""

    # --- SOPImport Chain ---
    registry.register(Recipe(
        name="sopimport_chain",
        description="Create a SOP Import LOP to bring SOP geometry into the USD stage",
        triggers=[
            r"^(?:import|bring)\s+(?P<sop_path>[\w\-./]+)\s+(?:into|to)\s+(?:the\s+)?(?:usd\s+)?stage$",
        ],
        parameters=["sop_path"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "sopimport",
                    "name": "sopimport1",
                    "parent": "/stage",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "/stage/sopimport1",
                    "parm": "soppath",
                    "value": "{sop_path}",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Edit Transform ---
    registry.register(Recipe(
        name="edit_transform",
        description="Create an edit node for transforming USD prims",
        triggers=[
            r"^(?:edit|transform)\s+(?P<prim_path>[\w\-./]+)\s+(?:position|translate|move)$",
        ],
        parameters=["prim_path"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "edit",
                    "name": "edit_xform",
                    "parent": "/stage",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="set_parm",
                payload_template={
                    "node": "/stage/edit_xform",
                    "parm": "primpattern",
                    "value": "{prim_path}",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- File Cache ---
    registry.register(Recipe(
        name="file_cache",
        description=(
            "Add a file cache node to cache any SOP output to disk. "
            "Uses bgeo.sc format with frame padding."
        ),
        triggers=[
            r"^cache\s+(?P<source>[\w\-./]+)(?:\s+to\s+disk)?$",
            r"^(?:add|create)\s+(?:a\s+)?(?:file\s*)?cache\s+(?:for|on|after)\s+(?P<source>[\w\-./]+)$",
        ],
        parameters=["source"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "src = hou.node('{source}')\n"
                        "if not src:\n"
                        "    result = {{'error': 'Could not find node: {source}'}}\n"
                        "else:\n"
                        "    parent = src.parent()\n"
                        "    cache = parent.createNode('filecache', "
                        "src.name() + '_cache')\n"
                        "    cache.parm('file').set("
                        "'$HIP/cache/' + src.name() + '.$F4.bgeo.sc')\n"
                        "    cache.setInput(0, src, 0)\n"
                        "    cache.setDisplayFlag(True)\n"
                        "    cache.setRenderFlag(True)\n"
                        "    parent.layoutChildren()\n"
                        "    result = {{'node': cache.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="cached",
            ),
        ],
    ))

    # --- HDA Scaffold ---
    registry.register(Recipe(
        name="hda_scaffold",
        description=(
            "Scaffold a complete HDA: create subnet with IN/OUT nulls, "
            "create digital asset definition, add standard parameter "
            "interface, and save to $HIP/otls/."
        ),
        triggers=[
            r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)\s+(?:called|named)\s+(?P<name>[\w]+)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
            r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)\s+(?P<name>[\w]+)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
            r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:hda|digital asset|otl)(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
            r"^(?:new|setup)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
            r"^hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
        ],
        parameters=["name", "description"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import os\n"
                        "import re\n"
                        "# Parameters from trigger\n"
                        "raw_name = '{name}'.strip()\n"
                        "description = '{description}'.strip()\n"
                        "# Derive names\n"
                        "if not raw_name:\n"
                        "    raw_name = 'custom_tool'\n"
                        "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                        "raw_name.lower()).strip('_')\n"
                        "hda_label = raw_name.replace('_', ' ').title()\n"
                        "# Find parent context\n"
                        "sel = hou.selectedNodes()\n"
                        "if sel and sel[0].type().category() == "
                        "hou.sopNodeTypeCategory():\n"
                        "    parent = sel[0].parent()\n"
                        "elif sel:\n"
                        "    parent = sel[0]\n"
                        "else:\n"
                        "    obj = hou.node('/obj')\n"
                        "    parent = obj.createNode('geo', "
                        "hda_name + '_dev')\n"
                        "    parent.moveToGoodPosition()\n"
                        "# Create subnet structure\n"
                        "subnet = parent.createNode('subnet', hda_name)\n"
                        "input_null = subnet.createNode('null', 'IN')\n"
                        "input_null.setPosition(hou.Vector2(0, 0))\n"
                        "output_null = subnet.createNode('null', 'OUT')\n"
                        "output_null.setPosition(hou.Vector2(0, -3))\n"
                        "output_null.setInput(0, input_null)\n"
                        "output_null.setDisplayFlag(True)\n"
                        "output_null.setRenderFlag(True)\n"
                        "input_null.setInput(0, "
                        "subnet.indirectInputs()[0])\n"
                        "subnet.layoutChildren()\n"
                        "subnet.moveToGoodPosition()\n"
                        "# Create HDA definition\n"
                        "otls_dir = os.path.join("
                        "hou.getenv('HIP', ''), 'otls')\n"
                        "if not os.path.exists(otls_dir):\n"
                        "    os.makedirs(otls_dir)\n"
                        "hda_path = os.path.join(otls_dir, "
                        "hda_name + '.hda')\n"
                        "hda_node = subnet.createDigitalAsset(\n"
                        "    name=hda_name,\n"
                        "    hda_file_name=hda_path,\n"
                        "    description=hda_label,\n"
                        "    min_num_inputs=1,\n"
                        "    max_num_inputs=1,\n"
                        ")\n"
                        "# Configure HDA definition\n"
                        "definition = hda_node.type().definition()\n"
                        "help_text = '= ' + hda_label + ' =\\n\\n'\n"
                        "if description:\n"
                        "    help_text += description + '\\n\\n'\n"
                        "help_text += '== Parameters ==\\n\\n'\n"
                        "help_text += 'See parameter interface "
                        "for controls.\\n'\n"
                        "definition.setExtraFileOption("
                        "'Help', help_text)\n"
                        "definition.setIcon('SOP_subnet')\n"
                        "definition.setExtraFileOption("
                        "'CreatedBy', 'Synapse HDA Scaffold')\n"
                        "# Standard parameter interface\n"
                        "ptg = hda_node.parmTemplateGroup()\n"
                        "main_folder = hou.FolderParmTemplate(\n"
                        "    'main_folder', 'Main', "
                        "folder_type=hou.folderType.Tabs)\n"
                        "if description:\n"
                        "    main_folder.addParmTemplate(\n"
                        "        hou.LabelParmTemplate("
                        "'info_label', 'Purpose', "
                        "column_labels=[description]))\n"
                        "main_folder.addParmTemplate(\n"
                        "    hou.FloatParmTemplate("
                        "'blend', 'Blend', 1, "
                        "default_value=(1.0,),\n"
                        "        min=0.0, max=1.0, "
                        "min_is_strict=True, "
                        "max_is_strict=True))\n"
                        "main_folder.addParmTemplate(\n"
                        "    hou.ToggleParmTemplate("
                        "'enable', 'Enable', "
                        "default_value=True))\n"
                        "ptg.append(main_folder)\n"
                        "hda_node.setParmTemplateGroup(ptg)\n"
                        "# Save and select\n"
                        "definition.save(hda_path, hda_node)\n"
                        "hda_node.setSelected(True, "
                        "clear_all_selected=True)\n"
                        "hda_node.setDisplayFlag(True)\n"
                        "hda_node.setRenderFlag(True)\n"
                        "result = {{\n"
                        "    'node': hda_node.path(),\n"
                        "    'hda_file': hda_path,\n"
                        "    'hda_name': hda_name,\n"
                        "    'hda_label': hda_label,\n"
                        "    'definition': 'Sop/' + hda_name,\n"
                        "    'description': description "
                        "or '(none provided)',\n"
                        "}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="hda",
            ),
        ],
    ))

    # --- LOP HDA Scaffold ---
    registry.register(Recipe(
        name="lop_hda_scaffold",
        description=(
            "Scaffold a Solaris (LOP) HDA: create subnet in /stage with "
            "stage passthrough, edit properties and configure primitive "
            "nodes, convert to HDA, promote primpath, and save to "
            "$HIP/otls/synapse/."
        ),
        triggers=[
            r"^(?:create|make|build|scaffold)\s+(?:an?\s+)?(?:solaris|lop|usd)\s+(?:hda|digital asset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?:for|that|to|which)\s+(?P<description>.+))?$",
            r"^(?:create|make|build)\s+(?:an?\s+)?(?:lop|solaris|usd)\s+(?:hda|digital asset)\s+(?P<name>[\w]+)(?:\s+(?P<description>.+))?$",
            r"^(?:new|setup)\s+(?:lop|solaris)\s+(?:hda|digital asset)(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
            r"^(?:lop|solaris)\s+hda\s+scaffold(?:\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
            r"^build\s+(?:an?\s+)?usd\s+digital\s+asset(?:\s+(?:called|named)\s+(?P<name>[\w]+))?(?:\s+(?P<description>.+))?$",
        ],
        parameters=["name", "description"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import os\n"
                        "import re\n"
                        "# Parameters from trigger\n"
                        "raw_name = '{name}'.strip()\n"
                        "description = '{description}'.strip()\n"
                        "if not raw_name:\n"
                        "    raw_name = 'custom_lop_tool'\n"
                        "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                        "raw_name.lower()).strip('_')\n"
                        "hda_label = raw_name.replace('_', ' ').title()\n"
                        "# Find or create /stage context\n"
                        "stage = hou.node('/stage')\n"
                        "if not stage:\n"
                        "    stage = hou.node('/obj')\n"
                        "# Create LOP subnet\n"
                        "subnet = stage.createNode('subnet', hda_name)\n"
                        "# Wire subnet indirect input for stage passthrough\n"
                        "indirect = subnet.indirectInputs()[0]\n"
                        "# Create internal nodes\n"
                        "edit_props = subnet.createNode("
                        "'editproperties::2.0', 'edit_properties')\n"
                        "edit_props.setInput(0, indirect)\n"
                        "config_prim = subnet.createNode("
                        "'configureprimitive', 'configure_prim')\n"
                        "config_prim.setInput(0, edit_props)\n"
                        "config_prim.setDisplayFlag(True)\n"
                        "subnet.layoutChildren()\n"
                        "subnet.moveToGoodPosition()\n"
                        "# Create HDA definition\n"
                        "otls_dir = os.path.join("
                        "hou.getenv('HIP', ''), 'otls', 'synapse')\n"
                        "os.makedirs(otls_dir, exist_ok=True)\n"
                        "hda_path = os.path.join(otls_dir, "
                        "hda_name + '.hda')\n"
                        "hda_node = subnet.createDigitalAsset(\n"
                        "    name=hda_name,\n"
                        "    hda_file_name=hda_path,\n"
                        "    description=hda_label,\n"
                        "    min_num_inputs=1,\n"
                        "    max_num_inputs=1,\n"
                        ")\n"
                        "# Set LOP category\n"
                        "definition = hda_node.type().definition()\n"
                        "import time as _time\n"
                        "definition.setExtraInfo(\n"
                        "    'author=synapse;version=1.0.0;'\n"
                        "    'created=' + _time.strftime("
                        "'%Y-%m-%d %H:%M:%S'))\n"
                        "# Promote primpath from edit_properties\n"
                        "ptg = hda_node.parmTemplateGroup()\n"
                        "ep_node = hda_node.node('edit_properties')\n"
                        "if ep_node:\n"
                        "    pp = ep_node.parm('primpath')\n"
                        "    if pp:\n"
                        "        tpl = pp.parmTemplate().clone()\n"
                        "        tpl.setName('primpath')\n"
                        "        tpl.setLabel('Prim Path')\n"
                        "        ptg.append(tpl)\n"
                        "        hda_node.setParmTemplateGroup(ptg)\n"
                        "# Help text\n"
                        "help_text = '= ' + hda_label + ' =\\n\\n'\n"
                        "if description:\n"
                        "    help_text += description + '\\n\\n'\n"
                        "help_text += '#type: node\\n'\n"
                        "help_text += '#context: Lop\\n'\n"
                        "definition.addSection('HelpText', help_text)\n"
                        "# Save and select\n"
                        "definition.save(hda_path, hda_node)\n"
                        "hda_node.setSelected(True, "
                        "clear_all_selected=True)\n"
                        "hda_node.setDisplayFlag(True)\n"
                        "result = {{\n"
                        "    'node': hda_node.path(),\n"
                        "    'hda_file': hda_path,\n"
                        "    'hda_name': hda_name,\n"
                        "    'hda_label': hda_label,\n"
                        "    'definition': 'Lop/' + hda_name,\n"
                        "    'description': description "
                        "or '(none provided)',\n"
                        "}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="lop_hda",
            ),
        ],
    ))

    # --- Karma Quality HDA ---
    registry.register(Recipe(
        name="karma_quality_hda",
        description=(
            "Create a Karma render quality preset HDA with draft/medium/final "
            "quality tiers, resolution control, and HScript-switched pixel samples."
        ),
        triggers=[
            r"^(?:create|make|build)\s+(?:a\s+)?karma\s+quality\s+(?:hda|digital asset|preset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?$",
            r"^(?:create|make|build)\s+(?:a\s+)?render\s+quality\s+(?:hda|digital asset|preset)(?:\s+(?:called|named)\s+(?P<name>[\w]+))?$",
            r"^(?:build|make)\s+(?:a\s+)?render\s+(?:settings|quality)\s+(?:hda|preset)(?:\s+(?P<name>[\w]+))?$",
            r"^karma\s+(?:quality|preset)\s+hda(?:\s+(?P<name>[\w]+))?$",
        ],
        parameters=["name"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import os\n"
                        "import re\n"
                        "import time as _time\n"
                        "raw_name = '{name}'.strip()\n"
                        "if not raw_name:\n"
                        "    raw_name = 'karma_quality'\n"
                        "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                        "raw_name.lower()).strip('_')\n"
                        "hda_label = raw_name.replace('_', ' ').title()\n"
                        "# Create in /stage\n"
                        "stage = hou.node('/stage')\n"
                        "if not stage:\n"
                        "    stage = hou.node('/obj')\n"
                        "subnet = stage.createNode('subnet', hda_name)\n"
                        "indirect = subnet.indirectInputs()[0]\n"
                        "# Karma render properties\n"
                        "karma_props = subnet.createNode("
                        "'karmarenderproperties', 'karma_props')\n"
                        "karma_props.setInput(0, indirect)\n"
                        "# Pixel samples switched by quality tier\n"
                        "# 0=draft(16), 1=medium(64), 2=final(256)\n"
                        "karma_props.parm('karma:global:pathtracedsamples'"
                        ").setExpression(\n"
                        "    'if(ch(\"../quality_tier\")==0, 16, "
                        "if(ch(\"../quality_tier\")==1, 64, 256))',\n"
                        "    hou.exprLanguage.Hscript)\n"
                        "# Resolution via edit properties\n"
                        "edit_res = subnet.createNode("
                        "'editproperties::2.0', 'resolution')\n"
                        "edit_res.setInput(0, karma_props)\n"
                        "edit_res.setDisplayFlag(True)\n"
                        "subnet.layoutChildren()\n"
                        "subnet.moveToGoodPosition()\n"
                        "# Create HDA\n"
                        "otls_dir = os.path.join("
                        "hou.getenv('HIP', ''), 'otls', 'synapse')\n"
                        "os.makedirs(otls_dir, exist_ok=True)\n"
                        "hda_path = os.path.join(otls_dir, "
                        "hda_name + '.hda')\n"
                        "hda_node = subnet.createDigitalAsset(\n"
                        "    name=hda_name,\n"
                        "    hda_file_name=hda_path,\n"
                        "    description=hda_label,\n"
                        "    min_num_inputs=1,\n"
                        "    max_num_inputs=1,\n"
                        ")\n"
                        "definition = hda_node.type().definition()\n"
                        "definition.setExtraInfo(\n"
                        "    'author=synapse;version=1.0.0;'\n"
                        "    'created=' + _time.strftime("
                        "'%Y-%m-%d %H:%M:%S'))\n"
                        "# Add quality_tier menu parameter\n"
                        "ptg = hda_node.parmTemplateGroup()\n"
                        "quality_menu = hou.MenuParmTemplate(\n"
                        "    'quality_tier', 'Quality Tier',\n"
                        "    menu_items=['0', '1', '2'],\n"
                        "    menu_labels=['Draft (16 spp)', "
                        "'Medium (64 spp)', 'Final (256 spp)'],\n"
                        "    default_value=0)\n"
                        "ptg.append(quality_menu)\n"
                        "# Promote resolution\n"
                        "res_node = hda_node.node('resolution')\n"
                        "if res_node:\n"
                        "    rp = res_node.parm('primpath')\n"
                        "    if rp:\n"
                        "        tpl = rp.parmTemplate().clone()\n"
                        "        tpl.setName('res_primpath')\n"
                        "        tpl.setLabel('Render Prim')\n"
                        "        ptg.append(tpl)\n"
                        "hda_node.setParmTemplateGroup(ptg)\n"
                        "# Help text\n"
                        "help_text = ('= ' + hda_label + ' =\\n\\n'\n"
                        "    'Karma render quality preset with three '\n"
                        "    'tiers: Draft (16 spp), Medium (64 spp), '\n"
                        "    'Final (256 spp).\\n\\n'\n"
                        "    '@parameters\\n\\n'\n"
                        "    'quality_tier:\\n'\n"
                        "    '    Select render quality level.\\n')\n"
                        "definition.addSection('HelpText', help_text)\n"
                        "definition.save(hda_path, hda_node)\n"
                        "hda_node.setSelected(True, "
                        "clear_all_selected=True)\n"
                        "hda_node.setDisplayFlag(True)\n"
                        "result = {{\n"
                        "    'node': hda_node.path(),\n"
                        "    'hda_file': hda_path,\n"
                        "    'hda_name': hda_name,\n"
                        "    'hda_label': hda_label,\n"
                        "    'definition': 'Lop/' + hda_name,\n"
                        "}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="karma_hda",
            ),
        ],
    ))

    # --- HDA Generate (Content from Description) ---
    registry.register(Recipe(
        name="hda_generate",
        description=(
            "Generate a functional HDA from a natural-language description. "
            "Matches keywords to pre-built VEX templates (scatter, deformer, "
            "color, mask, extrude) and populates the HDA with working code "
            "and parameter interface."
        ),
        triggers=[
            r"^generate\s+(?:an?\s+)?(?:hda|digital asset|tool)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
            r"^generate\s+(?:an?\s+)?(?P<name>[\w]+)\s+(?:hda|digital asset|tool)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
            r"^generate\s+(?:an?\s+)?(?:hda|digital asset|tool)\s+(?:called|named)\s+(?P<name>[\w]+)\s+(?:that|to|for|which)\s+(?P<description>.+)$",
            r"^hda\s+generate\s+(?P<description>.+)$",
        ],
        parameters=["name", "description"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import os\n"
                        "import re\n"
                        "raw_name = '{name}'.strip()\n"
                        "description = '{description}'.strip()\n"
                        "desc = description.lower()\n"
                        "\n"
                        "# --- Match description to template ---\n"
                        "template = 'generic'\n"
                        "vex_code = ''\n"
                        "parms = []\n"
                        "\n"
                        "if any(w in desc for w in "
                        "['scatter', 'distribute', 'sprinkle', "
                        "'random point']):\n"
                        "    template = 'scatter'\n"
                        "    if not raw_name: raw_name = 'point_scatter'\n"
                        "    vex_code = ("
                        "'// Point removal by noise threshold\\n'"
                        "'float density = chf(\"density\");\\n'"
                        "'float seed = chf(\"seed\");\\n'"
                        "'float n = noise(@P * density + "
                        "set(seed, seed*0.7, seed*1.3));\\n'"
                        "'if (n < chf(\"cutoff\"))\\n'"
                        "'    removepoint(0, @ptnum);\\n')\n"
                        "    parms = [\n"
                        "        ('density', 'Density', 'float', 5.0),\n"
                        "        ('cutoff', 'Cutoff', 'float', 0.5),\n"
                        "        ('seed', 'Seed', 'float', 0.0),\n"
                        "    ]\n"
                        "\n"
                        "elif any(w in desc for w in "
                        "['deform', 'bend', 'twist', 'wave', "
                        "'displace']):\n"
                        "    template = 'deformer'\n"
                        "    if not raw_name: raw_name = 'deformer'\n"
                        "    vex_code = ("
                        "'// fBm noise deformation\\n'"
                        "'float amp = chf(\"amplitude\");\\n'"
                        "'float freq = chf(\"frequency\");\\n'"
                        "'int oct = chi(\"octaves\");\\n'"
                        "'float n = 0, a = 1.0, f = freq;\\n'"
                        "'for (int i = 0; i < oct; i++) {{\\n'"
                        "'    n += snoise(@P * f + @Time * "
                        "chf(\"speed\")) * a;\\n'"
                        "'    f *= 2.0; a *= 0.5;\\n'"
                        "'}}\\n'"
                        "'@P += @N * n * amp * chf(\"blend\");\\n')\n"
                        "    parms = [\n"
                        "        ('amplitude', 'Amplitude', "
                        "'float', 0.5),\n"
                        "        ('frequency', 'Frequency', "
                        "'float', 2.0),\n"
                        "        ('octaves', 'Octaves', 'int', 4),\n"
                        "        ('speed', 'Speed', 'float', 0.0),\n"
                        "        ('blend', 'Blend', 'float', 1.0),\n"
                        "    ]\n"
                        "\n"
                        "elif any(w in desc for w in "
                        "['color', 'paint', 'gradient', 'ramp', "
                        "'visualize']):\n"
                        "    template = 'color'\n"
                        "    if not raw_name: raw_name = 'color_tool'\n"
                        "    vex_code = ("
                        "'// Color by height gradient\\n'"
                        "'vector bmin, bmax;\\n'"
                        "'getbbox(0, bmin, bmax);\\n'"
                        "'int axis = chi(\"axis\");\\n'"
                        "'float t = fit(@P[axis], bmin[axis], "
                        "bmax[axis], 0, 1);\\n'"
                        "'vector ca = chv(\"color_a\");\\n'"
                        "'vector cb = chv(\"color_b\");\\n'"
                        "'@Cd = lerp(ca, cb, "
                        "chramp(\"gradient\", t));\\n')\n"
                        "    parms = [\n"
                        "        ('axis', 'Axis (0=X 1=Y 2=Z)', "
                        "'int', 1),\n"
                        "        ('color_a', 'Color A', "
                        "'vector', (0, 0, 1)),\n"
                        "        ('color_b', 'Color B', "
                        "'vector', (1, 0, 0)),\n"
                        "    ]\n"
                        "\n"
                        "elif any(w in desc for w in "
                        "['mask', 'group', 'select', 'filter', "
                        "'isolate']):\n"
                        "    template = 'mask'\n"
                        "    if not raw_name: raw_name = 'mask_tool'\n"
                        "    vex_code = ("
                        "'// Proximity-based point mask\\n'"
                        "'vector center = chv(\"center\");\\n'"
                        "'float rad = chf(\"radius\");\\n'"
                        "'float d = distance(@P, center);\\n'"
                        "'f@mask = 1.0 - smooth(rad * 0.5, "
                        "rad, d);\\n'"
                        "'if (chi(\"invert\")) "
                        "f@mask = 1.0 - f@mask;\\n'"
                        "'if (f@mask > chf(\"threshold\"))\\n'"
                        "'    setpointgroup(0, \"masked\", "
                        "@ptnum, 1);\\n')\n"
                        "    parms = [\n"
                        "        ('center', 'Center', "
                        "'vector', (0, 0, 0)),\n"
                        "        ('radius', 'Radius', "
                        "'float', 1.0),\n"
                        "        ('threshold', 'Threshold', "
                        "'float', 0.5),\n"
                        "        ('invert', 'Invert', "
                        "'toggle', False),\n"
                        "    ]\n"
                        "\n"
                        "elif any(w in desc for w in "
                        "['extrude', 'push', 'inflate', "
                        "'thicken', 'offset']):\n"
                        "    template = 'extrude'\n"
                        "    if not raw_name: "
                        "raw_name = 'extrude_tool'\n"
                        "    vex_code = ("
                        "'// Push along normals with noise\\n'"
                        "'float dist = chf(\"distance\");\\n'"
                        "'float namt = chf(\"noise_amount\");\\n'"
                        "'float n = 0;\\n'"
                        "'if (namt > 0)\\n'"
                        "'    n = snoise(@P * chf(\"noise_freq\"))"
                        " * namt;\\n'"
                        "'@P += @N * (dist + n) * "
                        "chf(\"blend\");\\n')\n"
                        "    parms = [\n"
                        "        ('distance', 'Distance', "
                        "'float', 0.1),\n"
                        "        ('noise_amount', 'Noise Amount', "
                        "'float', 0.0),\n"
                        "        ('noise_freq', 'Noise Frequency', "
                        "'float', 2.0),\n"
                        "        ('blend', 'Blend', "
                        "'float', 1.0),\n"
                        "    ]\n"
                        "\n"
                        "else:\n"
                        "    if not raw_name: "
                        "raw_name = 'custom_tool'\n"
                        "    vex_code = ("
                        "'// Custom tool: ' + description + '\\n'"
                        "'float blend = chf(\"blend\");\\n'"
                        "'// @P += @N * blend;\\n')\n"
                        "    parms = [\n"
                        "        ('blend', 'Blend', "
                        "'float', 1.0),\n"
                        "    ]\n"
                        "\n"
                        "# --- Derive names ---\n"
                        "hda_name = re.sub(r'[^a-z0-9_]', '_', "
                        "raw_name.lower()).strip('_')\n"
                        "hda_label = raw_name.replace('_', "
                        "' ').title()\n"
                        "\n"
                        "# --- Find parent context ---\n"
                        "sel = hou.selectedNodes()\n"
                        "if sel and sel[0].type().category() == "
                        "hou.sopNodeTypeCategory():\n"
                        "    parent = sel[0].parent()\n"
                        "elif sel:\n"
                        "    parent = sel[0]\n"
                        "else:\n"
                        "    obj = hou.node('/obj')\n"
                        "    parent = obj.createNode('geo', "
                        "hda_name + '_dev')\n"
                        "    parent.moveToGoodPosition()\n"
                        "\n"
                        "# --- Create subnet with content ---\n"
                        "subnet = parent.createNode("
                        "'subnet', hda_name)\n"
                        "input_null = subnet.createNode("
                        "'null', 'IN')\n"
                        "input_null.setPosition("
                        "hou.Vector2(0, 0))\n"
                        "wrangle = subnet.createNode("
                        "'attribwrangle', template + '_wrangle')\n"
                        "wrangle.parm('snippet').set(vex_code)\n"
                        "wrangle.setPosition("
                        "hou.Vector2(0, -2))\n"
                        "wrangle.setInput(0, input_null)\n"
                        "output_null = subnet.createNode("
                        "'null', 'OUT')\n"
                        "output_null.setPosition("
                        "hou.Vector2(0, -4))\n"
                        "output_null.setInput(0, wrangle)\n"
                        "output_null.setDisplayFlag(True)\n"
                        "output_null.setRenderFlag(True)\n"
                        "input_null.setInput(0, "
                        "subnet.indirectInputs()[0])\n"
                        "subnet.layoutChildren()\n"
                        "subnet.moveToGoodPosition()\n"
                        "\n"
                        "# --- Create HDA definition ---\n"
                        "otls_dir = os.path.join("
                        "hou.getenv('HIP', ''), 'otls')\n"
                        "if not os.path.exists(otls_dir):\n"
                        "    os.makedirs(otls_dir)\n"
                        "hda_path = os.path.join(otls_dir, "
                        "hda_name + '.hda')\n"
                        "hda_node = subnet.createDigitalAsset(\n"
                        "    name=hda_name,\n"
                        "    hda_file_name=hda_path,\n"
                        "    description=hda_label,\n"
                        "    min_num_inputs=1,\n"
                        "    max_num_inputs=1,\n"
                        ")\n"
                        "definition = hda_node.type().definition()\n"
                        "ht = '= ' + hda_label + ' =\\n\\n'\n"
                        "ht += 'Template: ' + template + '\\n\\n'\n"
                        "if description:\n"
                        "    ht += description + '\\n\\n'\n"
                        "ht += '== Parameters ==\\n\\n'\n"
                        "ht += 'See parameter interface.\\n'\n"
                        "definition.setExtraFileOption('Help', ht)\n"
                        "definition.setIcon('SOP_subnet')\n"
                        "definition.setExtraFileOption("
                        "'CreatedBy', 'Synapse HDA Generate')\n"
                        "\n"
                        "# --- Build parameter interface ---\n"
                        "ptg = hda_node.parmTemplateGroup()\n"
                        "mf = hou.FolderParmTemplate(\n"
                        "    'main_folder', 'Main', "
                        "folder_type=hou.folderType.Tabs)\n"
                        "for pd in parms:\n"
                        "    pn, pl, pt = pd[0], pd[1], pd[2]\n"
                        "    pv = pd[3]\n"
                        "    if pt == 'float':\n"
                        "        mf.addParmTemplate("
                        "hou.FloatParmTemplate("
                        "pn, pl, 1, default_value=(pv,)))\n"
                        "    elif pt == 'int':\n"
                        "        mf.addParmTemplate("
                        "hou.IntParmTemplate("
                        "pn, pl, 1, default_value=(pv,)))\n"
                        "    elif pt == 'vector':\n"
                        "        mf.addParmTemplate("
                        "hou.FloatParmTemplate("
                        "pn, pl, 3, default_value=pv))\n"
                        "    elif pt == 'toggle':\n"
                        "        mf.addParmTemplate("
                        "hou.ToggleParmTemplate("
                        "pn, pl, default_value=bool(pv)))\n"
                        "    elif pt == 'string':\n"
                        "        mf.addParmTemplate("
                        "hou.StringParmTemplate("
                        "pn, pl, 1, default_value=(pv,)))\n"
                        "ptg.append(mf)\n"
                        "hda_node.setParmTemplateGroup(ptg)\n"
                        "definition.save(hda_path, hda_node)\n"
                        "hda_node.setSelected(True, "
                        "clear_all_selected=True)\n"
                        "hda_node.setDisplayFlag(True)\n"
                        "hda_node.setRenderFlag(True)\n"
                        "result = {{\n"
                        "    'node': hda_node.path(),\n"
                        "    'hda_file': hda_path,\n"
                        "    'hda_name': hda_name,\n"
                        "    'hda_label': hda_label,\n"
                        "    'template': template,\n"
                        "    'definition': 'Sop/' + hda_name,\n"
                        "    'description': description "
                        "or '(none provided)',\n"
                        "    'vex_lines': len("
                        "vex_code.split('\\n')),\n"
                        "    'parameters': len(parms),\n"
                        "}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="hda",
            ),
        ],
    ))

    # --- Character Cloth Setup ---
    registry.register(Recipe(
        name="character_cloth_setup",
        description=(
            "Solaris character with cloth pipeline: sublayer LOP for "
            "character USD reference, materiallibrary with skin/cloth/hair "
            "MaterialX subnets, SOP Import for Vellum cloth cache, "
            "subdivision + displacement on render geometry settings, "
            "purpose tagging (render vs proxy)."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+character\s+cloth(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?character\s+with\s+cloth(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
            r"^character\s+cloth\s+setup(?:\s+(?:for|on|at|in)\s+(?P<char_path>.+))?$",
        ],
        parameters=["char_path"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "char_path = '{char_path}'.strip()\n"
                        "stage = hou.node('/stage')\n"
                        "if stage is None:\n"
                        "    stage = hou.node('/obj').createNode("
                        "'lopnet', 'stage')\n"
                        "\n"
                        "# --- Sublayer for character USD reference ---\n"
                        "sublayer = stage.createNode('sublayer', "
                        "'char_reference')\n"
                        "if char_path:\n"
                        "    sublayer.parm('filepath1').set(char_path)\n"
                        "\n"
                        "# --- Material Library: skin, cloth, hair ---\n"
                        "matlib = stage.createNode('materiallibrary', "
                        "'char_materials')\n"
                        "matlib.setInput(0, sublayer)\n"
                        "matlib.parm('matpathprefix').set("
                        "'/materials')\n"
                        "matlib.cook(force=True)\n"
                        "\n"
                        "# Skin MaterialX subnet\n"
                        "skin = matlib.createNode('subnet', 'skin_mtl')\n"
                        "skin_surf = skin.createNode("
                        "'mtlxstandard_surface', 'skin_shader')\n"
                        "skin_surf.parm('base_color').set("
                        "(0.8, 0.6, 0.5))\n"
                        "skin_surf.parm('specular_roughness').set(0.4)\n"
                        "skin_surf.parm('subsurface').set(0.3)\n"
                        "skin_out = skin.createNode("
                        "'subnetconnector', 'surface_output')\n"
                        "skin_out.setInput(0, skin_surf)\n"
                        "\n"
                        "# Cloth MaterialX subnet\n"
                        "cloth = matlib.createNode('subnet', 'cloth_mtl')\n"
                        "cloth_surf = cloth.createNode("
                        "'mtlxstandard_surface', 'cloth_shader')\n"
                        "cloth_surf.parm('base_color').set("
                        "(0.3, 0.3, 0.35))\n"
                        "cloth_surf.parm('specular_roughness').set(0.7)\n"
                        "cloth_surf.parm('sheen').set(0.5)\n"
                        "cloth_out = cloth.createNode("
                        "'subnetconnector', 'surface_output')\n"
                        "cloth_out.setInput(0, cloth_surf)\n"
                        "\n"
                        "# Hair MaterialX subnet\n"
                        "hair = matlib.createNode('subnet', 'hair_mtl')\n"
                        "hair_surf = hair.createNode("
                        "'mtlxstandard_surface', 'hair_shader')\n"
                        "hair_surf.parm('base_color').set("
                        "(0.15, 0.1, 0.08))\n"
                        "hair_surf.parm('specular_roughness').set(0.35)\n"
                        "hair_out = hair.createNode("
                        "'subnetconnector', 'surface_output')\n"
                        "hair_out.setInput(0, hair_surf)\n"
                        "\n"
                        "# --- SOP Import for Vellum cloth cache ---\n"
                        "cloth_import = stage.createNode('sopimport', "
                        "'cloth_cache_import')\n"
                        "cloth_import.parm('primpath').set("
                        "'/characters/cloth_sim')\n"
                        "cloth_import.setInput(0, matlib)\n"
                        "\n"
                        "# --- Render Geometry Settings: "
                        "subdivision + displacement ---\n"
                        "rendergeo = stage.createNode("
                        "'rendergeometrysettings', 'char_render_geo')\n"
                        "rendergeo.setInput(0, cloth_import)\n"
                        "rendergeo.parm('primpattern').set("
                        "'/characters/**')\n"
                        "try:\n"
                        "    rendergeo.parm("
                        "'xn__karmasubdivisionmesh_control_kfb'"
                        ").set('set')\n"
                        "    rendergeo.parm("
                        "'xn__karmasubdivisionmesh_beb'"
                        ").set(True)\n"
                        "except Exception:\n"
                        "    pass\n"
                        "\n"
                        "# --- Purpose tagging ---\n"
                        "configure = stage.createNode("
                        "'configureprimitive', 'purpose_tags')\n"
                        "configure.setInput(0, rendergeo)\n"
                        "configure.parm('primpattern').set("
                        "'/characters/**')\n"
                        "try:\n"
                        "    configure.parm('purpose').set('render')\n"
                        "except Exception:\n"
                        "    pass\n"
                        "\n"
                        "stage.layoutChildren()\n"
                        "result = {{'sublayer': sublayer.path(), "
                        "'matlib': matlib.path(), "
                        "'materials': ['skin_mtl', 'cloth_mtl', "
                        "'hair_mtl'], "
                        "'cloth_import': cloth_import.path(), "
                        "'render_geo': rendergeo.path(), "
                        "'purpose_config': configure.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="char_setup",
            ),
        ],
    ))

    # --- Multi-Shot Composition ---
    registry.register(Recipe(
        name="multi_shot_composition",
        description=(
            "Shot-based USD layer composition: sublayer chain for "
            "base assets and shot overrides, per-shot camera prim, "
            "per-shot lighting overrides as stronger opinion layer, "
            "and render layer management."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+multi\s*shot\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?shot\s+based\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
            r"^multi\s+shot\s+composition(?:\s+(?:for|called|named)\s+(?P<shot_name>.+))?$",
        ],
        parameters=["shot_name"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "shot_name = '{shot_name}'.strip() or 'shot_010'\n"
                        "stage = hou.node('/stage')\n"
                        "if stage is None:\n"
                        "    stage = hou.node('/obj').createNode("
                        "'lopnet', 'stage')\n"
                        "\n"
                        "# --- Base asset sublayer ---\n"
                        "base_layer = stage.createNode('sublayer', "
                        "'base_assets')\n"
                        "base_layer.parm('filepath1').set("
                        "'$HIP/usd/assets.usda')\n"
                        "\n"
                        "# --- Shot overrides sublayer "
                        "(stronger opinion) ---\n"
                        "shot_layer = stage.createNode('sublayer', "
                        "shot_name + '_overrides')\n"
                        "shot_layer.setInput(0, base_layer)\n"
                        "shot_layer.parm('filepath1').set("
                        "'$HIP/usd/' + shot_name + '_overrides.usda')\n"
                        "\n"
                        "# --- Per-shot camera ---\n"
                        "cam = stage.createNode('camera', "
                        "shot_name + '_cam')\n"
                        "cam.parm('primpath').set("
                        "'/cameras/' + shot_name + '_cam')\n"
                        "cam.parm('focalLength').set(35)\n"
                        "cam.setInput(0, shot_layer)\n"
                        "\n"
                        "# --- Per-shot lighting overrides ---\n"
                        "light_layer = stage.createNode('sublayer', "
                        "shot_name + '_lighting')\n"
                        "light_layer.setInput(0, cam)\n"
                        "\n"
                        "# Key light override for this shot\n"
                        "key = stage.createNode('light', "
                        "shot_name + '_key')\n"
                        "key.parm('primpath').set("
                        "'/lights/' + shot_name + '_key')\n"
                        "key.parm('xn__inputsintensity_i0a').set(1.0)\n"
                        "key.parm("
                        "'xn__inputsexposure_control_wcb').set('set')\n"
                        "key.parm('xn__inputsexposure_vya').set(5.0)\n"
                        "\n"
                        "# Merge lighting into shot layer\n"
                        "light_merge = stage.createNode('merge', "
                        "shot_name + '_light_merge')\n"
                        "light_merge.setInput(0, light_layer)\n"
                        "light_merge.setInput(1, key)\n"
                        "\n"
                        "# --- Render layer management ---\n"
                        "rs = stage.createNode("
                        "'karmarenderproperties', "
                        "shot_name + '_render_settings')\n"
                        "rs.setInput(0, light_merge)\n"
                        "rs.parm('resolutionx').set(1920)\n"
                        "rs.parm('resolutiony').set(1080)\n"
                        "\n"
                        "karma = stage.createNode('karma', "
                        "shot_name + '_karma')\n"
                        "karma.setInput(0, rs)\n"
                        "karma.parm('camera').set("
                        "'/cameras/' + shot_name + '_cam')\n"
                        "karma.parm('picture').set("
                        "'$HIP/render/' + shot_name + "
                        "'/' + shot_name + '.$F4.exr')\n"
                        "\n"
                        "stage.layoutChildren()\n"
                        "result = {{'shot': shot_name, "
                        "'base_layer': base_layer.path(), "
                        "'shot_overrides': shot_layer.path(), "
                        "'camera': cam.path(), "
                        "'camera_prim': '/cameras/' + shot_name + '_cam', "
                        "'lighting': light_merge.path(), "
                        "'karma': karma.path(), "
                        "'output': '$HIP/render/' + shot_name + "
                        "'/' + shot_name + '.$F4.exr'}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="shot_comp",
            ),
        ],
    ))

    # --- Multi-Shot Render (TOPS pipeline) ---
    registry.register(Recipe(
        name="multi_shot_render",
        description=(
            "Multi-shot render pipeline via TOPS/PDG: creates per-shot "
            "work items from a shot list, configures camera and frame "
            "range per shot, renders via ropfetch, partitions results "
            "by shot name, and optionally encodes per-shot movies."
        ),
        triggers=[
            r"^(?:render|batch render)\s+(?:all\s+)?shots?\s+(?P<shots>.+?)(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
            r"^multi[- ]?shot\s+render(?:\s+(?P<shots>.+?))?(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
            r"^render\s+all\s+shots?(?:\s+(?P<shots>.+?))?(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
            r"^batch\s+render\s+shots?\s+(?P<shots>.+?)(?:\s+frames?\s+(?P<frame_range>\d+-\d+))?$",
        ],
        parameters=["shots", "frame_range"],
        gate_level=GateLevel.APPROVE,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou, json\n"
                        "shots_str = '{shots}'.strip()\n"
                        "frame_range_str = '{frame_range}'.strip()\n"
                        "\n"
                        "# Parse shot names\n"
                        "shot_names = [s.strip() for s in shots_str.split(',') if s.strip()]\n"
                        "if not shot_names:\n"
                        "    shot_names = ['sq010_sh010', 'sq010_sh020', 'sq010_sh030']\n"
                        "\n"
                        "# Parse frame range\n"
                        "frame_start, frame_end = 1001, 1048\n"
                        "if frame_range_str and '-' in frame_range_str:\n"
                        "    parts = frame_range_str.split('-')\n"
                        "    frame_start, frame_end = int(parts[0]), int(parts[1])\n"
                        "\n"
                        "# Build shot definitions for tops_multi_shot\n"
                        "shot_defs = []\n"
                        "for name in shot_names:\n"
                        "    shot_defs.append({{\n"
                        "        'name': name,\n"
                        "        'frame_start': frame_start,\n"
                        "        'frame_end': frame_end,\n"
                        "        'camera': '/cameras/' + name + '_cam',\n"
                        "    }})\n"
                        "\n"
                        "result = {{\n"
                        "    'shot_count': len(shot_defs),\n"
                        "    'shots': shot_defs,\n"
                        "    'frame_range': '{{}}-{{}}'.format(frame_start, frame_end),\n"
                        "}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="shot_list",
            ),
            RecipeStep(
                action="tops_multi_shot",
                payload_template={
                    "shots": "$shot_list.shots",
                    "output_dir": "$HIP/render",
                    "renderer": "karma_xpu",
                    "camera_pattern": "/cameras/{{shot}}_cam",
                },
                gate_level=GateLevel.APPROVE,
                output_var="multi_shot_job",
            ),
        ],
    ))

    # --- Copernicus Render Comp ---
    registry.register(Recipe(
        name="copernicus_render_comp",
        description=(
            "Render pass compositing via Copernicus GPU nodes: "
            "load beauty EXR and utility AOVs as file COPs, "
            "grade (exposure/contrast), tonemap, and output "
            "composited result."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?copernicus\s+render\s+comp(?:osite|ositing)?(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?render\s+comp(?:osite|ositing)?(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
            r"^composite\s+render\s+passes(?:\s+(?:for|from|with)\s+(?P<exr_path>.+))?$",
        ],
        parameters=["exr_path"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "exr_path = '{exr_path}'.strip()\n"
                        "if not exr_path:\n"
                        "    exr_path = '$HIP/render/$HIPNAME/"
                        "$HIPNAME.$F4.exr'\n"
                        "\n"
                        "# --- Create COP network ---\n"
                        "root = hou.node('/stage') or hou.node('/out')\n"
                        "cop = root.createNode('cop2net', "
                        "'render_comp')\n"
                        "\n"
                        "# --- File COP: beauty pass ---\n"
                        "beauty_file = cop.createNode('file', "
                        "'beauty_input')\n"
                        "beauty_file.parm('filename1').set(exr_path)\n"
                        "\n"
                        "# --- File COP: depth AOV ---\n"
                        "depth_path = exr_path.replace("
                        "'$HIPNAME.$F4', 'depth.$F4')\n"
                        "depth_file = cop.createNode('file', "
                        "'depth_input')\n"
                        "depth_file.parm('filename1').set(depth_path)\n"
                        "\n"
                        "# --- File COP: normal AOV ---\n"
                        "normal_path = exr_path.replace("
                        "'$HIPNAME.$F4', 'N.$F4')\n"
                        "normal_file = cop.createNode('file', "
                        "'normal_input')\n"
                        "normal_file.parm('filename1').set("
                        "normal_path)\n"
                        "\n"
                        "# --- Grade node: exposure/contrast ---\n"
                        "grade = cop.createNode('colorcorrect', "
                        "'grade')\n"
                        "grade.setInput(0, beauty_file)\n"
                        "try:\n"
                        "    grade.parm('gamma').set(1.0)\n"
                        "    grade.parm('gain').set(1.0)\n"
                        "except Exception:\n"
                        "    pass\n"
                        "\n"
                        "# --- Tonemap node ---\n"
                        "tonemap = cop.createNode('tonemap', "
                        "'tonemap')\n"
                        "tonemap.setInput(0, grade)\n"
                        "\n"
                        "# --- ROP Composite Output ---\n"
                        "rop_out = cop.createNode('rop_comp', "
                        "'comp_output')\n"
                        "rop_out.setInput(0, tonemap)\n"
                        "output_path = exr_path.replace("
                        "'$HIPNAME.$F4', 'comp.$F4')\n"
                        "rop_out.parm('copoutput').set(output_path)\n"
                        "\n"
                        "cop.layoutChildren()\n"
                        "result = {{'cop_net': cop.path(), "
                        "'beauty': beauty_file.path(), "
                        "'depth': depth_file.path(), "
                        "'normal': normal_file.path(), "
                        "'grade': grade.path(), "
                        "'tonemap': tonemap.path(), "
                        "'output': rop_out.path(), "
                        "'output_path': output_path}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="comp_setup",
            ),
        ],
    ))

    # --- Copernicus Procedural Texture ---
    registry.register(Recipe(
        name="copernicus_procedural_texture",
        description="Generate a procedural noise texture in Copernicus (perlin/worley/simplex)",
        triggers=[
            r"^(?:create|make|generate)\s+(?:a\s+)?(?:copernicus\s+)?procedural\s+(?:noise\s+)?texture(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+(?:noise|procedural)\s+texture(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_procedural_texture",
                payload_template={
                    "parent": "{parent}",
                    "noise_type": "perlin",
                    "frequency": 1.0,
                    "octaves": 4,
                    "resolution": [1024, 1024],
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Pixel Sort ---
    registry.register(Recipe(
        name="copernicus_pixel_sort",
        description="Apply pixel sorting effect in Copernicus (motion design)",
        triggers=[
            r"^(?:create|apply|make)\s+(?:a\s+)?(?:copernicus\s+)?pixel\s+sort(?:ing)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+pixel\s+sort(?:ing)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_pixel_sort",
                payload_template={
                    "parent": "{parent}",
                    "sort_by": "luminance",
                    "direction": "vertical",
                    "threshold_low": 0.2,
                    "threshold_high": 0.8,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Reaction-Diffusion ---
    registry.register(Recipe(
        name="copernicus_reaction_diffusion",
        description="Create a Gray-Scott reaction-diffusion simulation in Copernicus",
        triggers=[
            r"^(?:create|make|set up|setup)\s+(?:a\s+)?(?:copernicus\s+)?reaction[\s-]diffusion(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+(?:gray[\s-]scott\s+)?reaction[\s-]diffusion(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+r[\s-]?d\s+(?:sim(?:ulation)?)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_reaction_diffusion",
                payload_template={
                    "parent": "{parent}",
                    "feed_rate": 0.055,
                    "kill_rate": 0.062,
                    "iterations": 100,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Growth ---
    registry.register(Recipe(
        name="copernicus_growth",
        description="Create a DLA-style growth propagation solver in Copernicus",
        triggers=[
            r"^(?:create|make|set up|setup)\s+(?:a\s+)?(?:copernicus\s+)?growth(?:\s+propagation)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+growth(?:\s+propagation)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+dla(?:\s+growth)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_growth_propagation",
                payload_template={
                    "parent": "{parent}",
                    "iterations": 20,
                    "growth_rate": 0.5,
                    "blur_amount": 1.0,
                    "threshold": 0.5,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Stylize ---
    registry.register(Recipe(
        name="copernicus_stylize",
        description="Apply NPR stylization effects in Copernicus (toon, risograph, posterize)",
        triggers=[
            r"^(?:create|apply|make)\s+(?:a\s+)?(?:copernicus\s+)?(?:toon|risograph|posterize|edge[\s_]detect)(?:\s+effect)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+(?:stylize|npr|toon|risograph)(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_stylize",
                payload_template={
                    "parent": "{parent}",
                    "style_type": "toon",
                    "levels": 6,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Wetmap ---
    registry.register(Recipe(
        name="copernicus_wetmap",
        description="Create a wetmap effect with temporal decay in Copernicus",
        triggers=[
            r"^(?:create|make|set up|setup)\s+(?:a\s+)?(?:copernicus\s+)?wetmap(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+wetmap(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_wetmap",
                payload_template={
                    "parent": "{parent}",
                    "decay": 0.95,
                    "blur": 2.0,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Bake Textures ---
    registry.register(Recipe(
        name="copernicus_bake_textures",
        description="Set up UV texture baking in Copernicus (normal, AO, curvature maps)",
        triggers=[
            r"^(?:create|set up|setup)\s+(?:a\s+)?(?:copernicus\s+)?(?:texture\s+)?bak(?:e|ing)(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+bak(?:e|ing)(?:\s+textures?)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_bake_textures",
                payload_template={
                    "parent": "{parent}",
                    "map_types": ["normal", "ao"],
                    "resolution": [2048, 2048],
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Stamp Scatter ---
    registry.register(Recipe(
        name="copernicus_stamp_scatter",
        description="Scatter stamp images with randomized transforms in Copernicus",
        triggers=[
            r"^(?:create|make|set up|setup)\s+(?:a\s+)?(?:copernicus\s+)?stamp\s+scatter(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
            r"^(?:copernicus|cops?)\s+stamp(?:\s+scatter)?(?:\s+(?:in|at|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_stamp_scatter",
                payload_template={
                    "parent": "{parent}",
                    "count": 50,
                    "seed": 42,
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Copernicus Batch Process ---
    registry.register(Recipe(
        name="copernicus_batch_process",
        description="Batch-process multiple COP nodes in Copernicus",
        triggers=[
            r"^(?:copernicus|cops?)\s+batch\s+(?:cook|process)(?:\s+(?P<node_list>.+))?$",
            r"^batch\s+cook\s+cops?(?:\s+(?P<node_list>.+))?$",
        ],
        parameters=["node_list"],
        gate_level=GateLevel.REVIEW,
        category="copernicus",
        steps=[
            RecipeStep(
                action="cops_batch_cook",
                payload_template={
                    "nodes": ["{node_list}"],
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Camera Match Real ---
    registry.register(Recipe(
        name="camera_match_real",
        description=(
            "Create a USD camera prim that matches a real-world cinema "
            "camera body. Looks up sensor dimensions from a built-in "
            "database of 8 cameras (ARRI Alexa 35, ARRI Alexa Mini LF, "
            "RED V-Raptor [X], RED Komodo-X, Sony Venice 2, Sony FX6, "
            "Blackmagic URSA Mini Pro 12K, Canon EOS C500 Mark II). "
            "Sets horizontalAperture, verticalAperture, focalLength, "
            "clippingRange, and optional fStop/focusDistance overrides."
        ),
        triggers=[
            r"^(?:match|set up|setup|create)\s+(?:an?\s+)?(?:arri|red|sony|bmpcc|blackmagic|canon)\s*(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
            r"^camera\s+(?:match|like)\s+(?:an?\s+)?(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
            r"^(?:set up|setup|create)\s+(?:an?\s+)?camera\s+(?:match(?:ing)?|like)\s+(?P<camera_body>[\w\s\-\[\]]+?)(?:\s+(?:with|at)\s+(?P<lens_mm>\d+)\s*mm)?(?:\s+f/?(?P<f_stop>[\d.]+))?(?:\s+(?:focus|fd)\s+(?P<focus_distance>[\d.]+))?$",
        ],
        parameters=["camera_body", "lens_mm", "f_stop", "focus_distance"],
        gate_level=GateLevel.REVIEW,
        category="pipeline",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "import re\n"
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
                        "# Normalize body name to match sensor keys\n"
                        "slug = re.sub(r'[\\s\\-\\[\\]]+', '_', camera_body).strip('_')\n"
                        "# Try direct match first, then fuzzy prefix match\n"
                        "sensor = SENSORS.get(slug)\n"
                        "if sensor is None:\n"
                        "    for key, val in sorted(SENSORS.items()):\n"
                        "        if slug in key or key in slug:\n"
                        "            sensor = val\n"
                        "            slug = key\n"
                        "            break\n"
                        "    # Try matching against display names\n"
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
                        "    f_stop_str = '{f_stop}'.strip()\n"
                        "    focus_str = '{focus_distance}'.strip()\n"
                        "\n"
                        "    stage = hou.node('/stage')\n"
                        "    if stage is None:\n"
                        "        stage = hou.node('/obj').createNode('lopnet', 'stage')\n"
                        "\n"
                        "    cam_name = slug + '_cam'\n"
                        "    cam = stage.createNode('camera', cam_name)\n"
                        "    cam.parm('primpath').set('/cameras/' + cam_name)\n"
                        "    cam.parm('horizontalAperture').set(sensor['width'])\n"
                        "    cam.parm('verticalAperture').set(sensor['height'])\n"
                        "    cam.parm('focalLength').set(lens_mm)\n"
                        "    cam.parm('clippingRange1').set(0.1)\n"
                        "    cam.parm('clippingRange2').set(10000)\n"
                        "\n"
                        "    if f_stop_str:\n"
                        "        cam.parm('fStop').set(float(f_stop_str))\n"
                        "    if focus_str:\n"
                        "        cam.parm('focusDistance').set(float(focus_str))\n"
                        "\n"
                        "    stage.layoutChildren()\n"
                        "    result = {{'camera': cam.path(), "
                        "'prim_path': '/cameras/' + cam_name, "
                        "'sensor': sensor['name'], "
                        "'horizontal_aperture': sensor['width'], "
                        "'vertical_aperture': sensor['height'], "
                        "'focal_length': lens_mm, "
                        "'clipping_range': [0.1, 10000]}}\n"
                        "    if f_stop_str:\n"
                        "        result['f_stop'] = float(f_stop_str)\n"
                        "    if focus_str:\n"
                        "        result['focus_distance'] = float(focus_str)\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="camera",
            ),
        ],
    ))


