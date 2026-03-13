"""
Synapse Recipe Registry -- Fx Recipes

Auto-extracted from the monolith recipes.py.
"""

from .base import Recipe, RecipeStep
from ...core.gates import GateLevel


def register_fx_recipes(registry):
    """Register fx recipes into the given registry."""

    # --- Pyro Source Setup ---
    registry.register(Recipe(
        name="pyro_source_setup",
        description="Create a pyro source setup with scatter and attribute wrangle",
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?pyro\s+source(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "scatter",
                    "name": "pyro_scatter",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="create_node",
                payload_template={
                    "type": "attribwrangle",
                    "name": "pyro_source_attrs",
                    "parent": "{parent}",
                },
                gate_level=GateLevel.REVIEW,
            ),
            RecipeStep(
                action="connect_nodes",
                payload_template={
                    "source": "{parent}/pyro_scatter",
                    "target": "{parent}/pyro_source_attrs",
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))

    # --- Vellum Cloth Simulation ---
    registry.register(Recipe(
        name="vellum_cloth_sim",
        description=(
            "Set up a complete Vellum cloth simulation: "
            "vellumcloth configure -> vellumsolver -> filecache. "
            "Configures stretch/bend stiffness, substeps, and collision."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:vellum\s+)?cloth\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:add|create)\s+(?:a\s+)?vellum\s+cloth(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Create Vellum cloth configure\n"
                        "cloth = parent.createNode('vellumcloth', 'vellum_cloth')\n"
                        "cloth.parm('stretchstiffness').set(10000)\n"
                        "cloth.parm('bendstiffness').set(0.001)\n"
                        "cloth.parm('thickness').set(0.01)\n"
                        "# Create Vellum solver\n"
                        "solver = parent.createNode('vellumsolver', 'vellum_solver')\n"
                        "solver.parm('substeps').set(5)\n"
                        "# Wire: cloth geo output -> solver input 1\n"
                        "solver.setInput(0, cloth, 0)\n"
                        "# Wire: cloth constraints output -> solver input 2\n"
                        "solver.setInput(2, cloth, 1)\n"
                        "# File cache for sim output\n"
                        "cache = parent.createNode('filecache', 'cloth_cache')\n"
                        "cache.parm('file').set('$HIP/cache/cloth.$F4.bgeo.sc')\n"
                        "cache.setInput(0, solver, 0)\n"
                        "cache.setDisplayFlag(True)\n"
                        "cache.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': cache.path(), 'solver': solver.path(), "
                        "'cloth': cloth.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="cloth_sim",
            ),
        ],
    ))

    # --- RBD Destruction ---
    registry.register(Recipe(
        name="rbd_destruction",
        description=(
            "Set up an RBD destruction pipeline: "
            "rbdmaterialfracture -> assemble -> rbdconstraintsfromrules -> "
            "rbdconstraintproperties (glue) -> rigidsolver -> filecache."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:rbd\s+)?destruction(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:rbd\s+)?fracture\s+(?:sim|simulation|pipeline)(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:destroy|fracture|break)\s+(?P<parent>[\w\-./]+)$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Fracture\n"
                        "frac = parent.createNode('rbdmaterialfracture', 'fracture')\n"
                        "frac.parm('numpieces').set(50)\n"
                        "# Assemble into packed prims\n"
                        "asm = parent.createNode('assemble', 'assemble')\n"
                        "asm.parm('create_packed').set(True)\n"
                        "asm.setInput(0, frac, 0)\n"
                        "# Constraints from proximity\n"
                        "cons = parent.createNode('rbdconstraintsfromrules', 'constraints')\n"
                        "cons.setInput(0, asm, 0)\n"
                        "# Glue constraint properties\n"
                        "props = parent.createNode('rbdconstraintproperties', 'glue_props')\n"
                        "props.parm('type').set(0)  # Glue\n"
                        "props.parm('strength').set(500)\n"
                        "props.setInput(0, cons, 0)\n"
                        "# Rigid body solver\n"
                        "solver = parent.createNode('rigidsolver', 'rbd_solver')\n"
                        "solver.setInput(0, asm, 0)\n"
                        "solver.setInput(2, props, 0)\n"
                        "# Cache\n"
                        "cache = parent.createNode('filecache', 'rbd_cache')\n"
                        "cache.parm('file').set('$HIP/cache/rbd.$F4.bgeo.sc')\n"
                        "cache.setInput(0, solver, 0)\n"
                        "cache.setDisplayFlag(True)\n"
                        "cache.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': cache.path(), 'solver': solver.path(), "
                        "'fracture': frac.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="rbd",
            ),
        ],
    ))

    # --- Ocean Setup ---
    registry.register(Recipe(
        name="ocean_setup",
        description=(
            "Set up an ocean: oceanspectrum -> oceanevaluate for "
            "displaced surface. Configurable wind speed and chop."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:an?\s+)?ocean(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:add|create)\s+(?:an?\s+)?ocean\s+(?:surface|sim|fx)(?:\s+(?:at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Ocean spectrum — wave frequency data\n"
                        "spec = parent.createNode('oceanspectrum', 'ocean_spectrum')\n"
                        "spec.parm('speed').set(15)  # wind m/s\n"
                        "spec.parm('chop').set(0.7)\n"
                        "spec.parm('gridsize').set(6)  # 2^6 = 64 resolution\n"
                        "spec.parm('depth').set(200)\n"
                        "# Ocean evaluate — displaced geometry\n"
                        "evl = parent.createNode('oceanevaluate', 'ocean_evaluate')\n"
                        "evl.setInput(0, spec, 0)\n"
                        "# Output null\n"
                        "out = parent.createNode('null', 'OCEAN_OUT')\n"
                        "out.setInput(0, evl, 0)\n"
                        "out.setDisplayFlag(True)\n"
                        "out.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': out.path(), 'spectrum': spec.path(), "
                        "'evaluate': evl.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="ocean",
            ),
        ],
    ))

    # --- Full Pyro Fire Simulation ---
    registry.register(Recipe(
        name="pyro_fire_sim",
        description=(
            "Set up a complete pyro fire simulation: scatter source points "
            "-> attribwrangle (density/temperature/flame/velocity) -> "
            "volumerasterizeattributes -> pyrosolver -> filecache."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:pyro\s+)?fire\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:full\s+)?pyro\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Scatter source points\n"
                        "scatter = parent.createNode('scatter', 'pyro_source_pts')\n"
                        "scatter.parm('npts').set(5000)\n"
                        "# Emission attributes wrangle\n"
                        "wrangle = parent.createNode('attribwrangle', 'emission_attrs')\n"
                        "wrangle.parm('snippet').set("
                        "'f@density = 1;\\n"
                        "f@temperature = 2;\\n"
                        "f@flame = 1;\\n"
                        "v@v = set(0, 2 + rand(@ptnum)*0.5, 0);\\n"
                        "f@pscale = 0.05;')\n"
                        "wrangle.setInput(0, scatter, 0)\n"
                        "# Rasterize to volumes\n"
                        "rast = parent.createNode('volumerasterizeattributes', "
                        "'rasterize')\n"
                        "rast.parm('attributes').set('density temperature flame')\n"
                        "rast.setInput(0, wrangle, 0)\n"
                        "# Pyro solver\n"
                        "solver = parent.createNode('pyrosolver', 'pyro_solver')\n"
                        "solver.parm('divsize').set(0.05)\n"
                        "solver.parm('tempcooling').set(0.6)\n"
                        "solver.parm('dissipation').set(0.1)\n"
                        "solver.setInput(0, rast, 0)\n"
                        "# Cache\n"
                        "cache = parent.createNode('filecache', 'pyro_cache')\n"
                        "cache.parm('file').set('$HIP/cache/pyro.$F4.bgeo.sc')\n"
                        "cache.setInput(0, solver, 0)\n"
                        "cache.setDisplayFlag(True)\n"
                        "cache.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': cache.path(), 'solver': solver.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="pyro",
            ),
        ],
    ))

    # --- Vellum Hair / Wire Simulation ---
    registry.register(Recipe(
        name="vellum_wire_sim",
        description=(
            "Set up Vellum hair/wire simulation for cables, ropes, or "
            "strands: vellumhair configure -> vellumsolver -> filecache."
        ),
        triggers=[
            r"^(?:set up|setup|create)\s+(?:a\s+)?(?:vellum\s+)?(?:wire|cable|rope|hair)\s+sim(?:ulation)?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
            r"^(?:add|sim(?:ulate)?)\s+(?:a\s+)?(?:vellum\s+)?(?:wire|cable|rope|hair)s?(?:\s+(?:on|for|at|in|under)\s+(?P<parent>.+))?$",
        ],
        parameters=["parent"],
        gate_level=GateLevel.REVIEW,
        category="fx",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "parent = hou.node('{parent}') or hou.node('/obj')\n"
                        "# Vellum hair configure (used for wires/cables)\n"
                        "hair = parent.createNode('vellumhair', 'vellum_wire')\n"
                        "hair.parm('stretchstiffness').set(50000)\n"
                        "hair.parm('bendstiffness').set(1.0)\n"
                        "# Vellum solver\n"
                        "solver = parent.createNode('vellumsolver', 'wire_solver')\n"
                        "solver.parm('substeps').set(3)\n"
                        "solver.setInput(0, hair, 0)\n"
                        "solver.setInput(2, hair, 1)\n"
                        "# Cache\n"
                        "cache = parent.createNode('filecache', 'wire_cache')\n"
                        "cache.parm('file').set('$HIP/cache/wires.$F4.bgeo.sc')\n"
                        "cache.setInput(0, solver, 0)\n"
                        "cache.setDisplayFlag(True)\n"
                        "cache.setRenderFlag(True)\n"
                        "parent.layoutChildren()\n"
                        "result = {{'node': cache.path(), 'solver': solver.path()}}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
                output_var="wire_sim",
            ),
        ],
    ))

    # --- DOP Network Setup ---
    registry.register(Recipe(
        name="dop_network_setup",
        description=(
            "Create a properly wired DOP network with solver, "
            "object, and merge nodes"
        ),
        triggers=[
            r"^(?:set\s*up|create|build)\s+(?:a\s+)?dop\s+(?:network|sim)",
            r"^(?:simulation|dynamics)\s+setup",
        ],
        parameters=[],
        gate_level=GateLevel.REVIEW,
        category="sim",
        steps=[
            RecipeStep(
                action="execute_python",
                payload_template={
                    "code": (
                        "import hou\n"
                        "\n"
                        "# Create DOP network\n"
                        "obj = hou.node('/obj')\n"
                        "dopnet = obj.createNode('dopnet', 'simulation')\n"
                        "\n"
                        "# Create gravity force\n"
                        "gravity = dopnet.createNode('gravity', 'gravity_force')\n"
                        "\n"
                        "# Create RBD solver\n"
                        "solver = dopnet.createNode('rigidbodysolver', 'rbd_solver')\n"
                        "\n"
                        "# Create RBD packed object\n"
                        "rbd_obj = dopnet.createNode('rbdpackedobject', 'rbd_object')\n"
                        "\n"
                        "# Create merge to wire forces into solver "
                        "(DOP convention: merge, not direct wires)\n"
                        "merge = dopnet.createNode('merge', 'force_merge')\n"
                        "merge.setInput(0, gravity)\n"
                        "\n"
                        "# Wire: object + merged forces -> solver\n"
                        "solver.setInput(0, merge)\n"
                        "solver.setInput(1, rbd_obj)\n"
                        "\n"
                        "# Create output null\n"
                        "out = dopnet.createNode('output', 'OUT')\n"
                        "out.setInput(0, solver)\n"
                        "out.setDisplayFlag(True)\n"
                        "out.setRenderFlag(True)\n"
                        "\n"
                        "# Layout\n"
                        "dopnet.layoutChildren()\n"
                        "\n"
                        "result = {'dopnet': dopnet.path(), "
                        "'solver': solver.path(), "
                        "'object': rbd_obj.path(), "
                        "'gravity': gravity.path(), "
                        "'output': out.path()}\n"
                    ),
                },
                gate_level=GateLevel.REVIEW,
            ),
        ],
    ))


