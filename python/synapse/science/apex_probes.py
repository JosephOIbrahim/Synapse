"""APEX seed probes for the SYNAPSE science loop.

Each :class:`ProbeSpec` in :data:`APEX_SEED` encodes a *verifiable assumption*
the SYNAPSE codebase ALREADY makes about Houdini 21.0.671's APEX surface.
The science loop (``loop.run_search``) walks these against a live, injected
namespace (the ``apex`` module + ``hou``) via ``probe.probe`` to confirm which
assumptions are champions and which are dead ends — without re-walking
anything the registry already knows.

Provenance — every claim below is derived from existing code, not invented:

* ``python/synapse/panel/apex_recipes.py``
    - Node types assumed buildable via ``houdini_create_node``:
      ``apex::rig::fkfull``, ``apex::rig::ikfull``, ``apex::rig::blendtransform``,
      ``apex::rig::controlshapes``, ``apex::rig::parentconstraint``,
      ``apex::autorig::build``, ``apex::sop::graphdefaults``,
      ``apex::sop::fromkinefx``, plus ``rig_doctor`` / ``invoke`` /
      ``apex_editgraph`` SOPs.
* ``python/synapse/panel/apex_explainer.py``
    - ``_APEX_TYPE_PATTERNS`` assumes the autorig building-block SOPs
      ``apex::sop::TransformObject``, ``apex::sop::FK``, ``apex::sop::IK``,
      ``apex::sop::invoke``, ``apex::sop::apexedit``.
    - The whole module assumes APEX graphs are inspectable geometry executed by
      an Invoke SOP (graph-as-geometry mental model). At the Python-API level
      that surfaces as the ``apex`` module exposing a graph type with node
      mutation (``addNode``) and serialization — the natural API mirror of the
      "build/edit graph then invoke" workflow the recipes describe.

These are seeds, not exhaustive coverage. ``kind`` distinguishes a plain
attribute lookup (``"attr"``) from something we expect to be invoked
(``"call"``) or a graph constructed (``"construct"``). ``expect`` records the
codebase's prior belief; the loop's job is to confirm or falsify it.
"""

from __future__ import annotations

from .probe import ProbeSpec

# NOTE on surface convention:
#   For node-type assumptions the surface is the SOP/APEX type STRING the
#   recipes feed to houdini_create_node. The probe namespace is expected to
#   expose a node-type catalog (e.g. injected as namespace["nodetypes"], a dict
#   keyed by type name) so a dotted lookup like "nodetypes.apex::rig::fkfull"
#   resolves to a truthy entry when the type exists in this Houdini build.
#   For pure Python APEX-module assumptions the surface is a dotted attribute
#   path against namespace["apex"].

APEX_SEED: list[ProbeSpec] = [
    # --- Python-level APEX module surface (highest value: gates everything) ---
    ProbeSpec(
        surface="apex.Graph",
        kind="attr",
        expect="present",
        rationale=(
            "apex_explainer's graph-as-geometry model assumes a first-class "
            "APEX graph type at the Python layer; recipes build/edit graphs "
            "before Invoke evaluates them."
        ),
        rank=100,
    ),
    ProbeSpec(
        surface="apex.Graph.addNode",
        kind="call",
        expect="unknown",
        rationale=(
            "apex_editgraph / 'add nodes for your deformation logic' "
            "(simple_deformer recipe) assumes the graph is mutable by adding "
            "nodes; addNode is the canonical APEX Graph mutator. Exact "
            "signature unverified on 21.0.671."
        ),
        rank=90,
    ),
    # --- Node-type catalog assumptions from apex_recipes.py ---
    ProbeSpec(
        surface="nodetypes.apex::rig::fkfull",
        kind="attr",
        expect="present",
        rationale=(
            "fk_chain / fk_ik_blend / control_shapes recipes all build "
            "apex::rig::fkfull as the FK setup node."
        ),
        rank=80,
    ),
    ProbeSpec(
        surface="nodetypes.apex::rig::ikfull",
        kind="attr",
        expect="present",
        rationale=(
            "ik_chain / fk_ik_blend recipes build apex::rig::ikfull for the "
            "IK solver with end effector + pole vector."
        ),
        rank=78,
    ),
    ProbeSpec(
        surface="nodetypes.apex::rig::blendtransform",
        kind="attr",
        expect="present",
        rationale=(
            "fk_ik_blend recipe blends FK/IK via apex::rig::blendtransform; "
            "KINEFX_MIGRATION_GUIDE maps Skeleton Blend -> this node."
        ),
        rank=70,
    ),
    ProbeSpec(
        surface="nodetypes.apex::autorig::build",
        kind="attr",
        expect="unknown",
        rationale=(
            "autorig_biped recipe assumes apex::autorig::build generates a "
            "full production rig from a named skeleton. Namespacing "
            "(autorig vs rig) is the least certain of the recipe types."
        ),
        rank=65,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sop::graphdefaults",
        kind="attr",
        expect="present",
        rationale=(
            "simple_deformer recipe + its tips explicitly prefer "
            "apex::sop::graphdefaults to seed a base APEX graph rather than "
            "building from scratch."
        ),
        rank=60,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sop::fromkinefx",
        kind="attr",
        expect="present",
        rationale=(
            "kinefx_to_apex recipe + migration guide assume "
            "apex::sop::fromkinefx converts KineFX skeleton data into APEX "
            "format (skeleton only, not rig logic)."
        ),
        rank=55,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sop::invoke",
        kind="attr",
        expect="unknown",
        rationale=(
            "apex_explainer maps 'invoke' to both bare 'invoke' and "
            "'apex::sop::invoke'; the Invoke SOP is the 'run program' bridge "
            "from APEX graph to SOP geometry. Which type string is canonical "
            "on 21.0.671 is unverified."
        ),
        rank=50,
    ),
    ProbeSpec(
        surface="nodetypes.rig_doctor",
        kind="attr",
        expect="present",
        rationale=(
            "Multiple recipes (fk_chain, autorig_biped, kinefx_to_apex) and "
            "their tips treat rig_doctor as the mandatory pre-APEX skeleton "
            "validator."
        ),
        rank=45,
    ),
    # --- Autorig building-block SOPs assumed by apex_explainer patterns ---
    ProbeSpec(
        surface="nodetypes.apex::sop::transformobject",
        kind="attr",
        expect="unknown",
        rationale=(
            "_APEX_TYPE_PATTERNS lists apex::sop::transformobject as an "
            "autorig building block ('creates a transform control'). Casing "
            "and existence on 21.0.671 unverified."
        ),
        rank=40,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sop::apexedit",
        kind="attr",
        expect="unknown",
        rationale=(
            "apex_explainer classifies apex::sop::apexedit / apexedit as the "
            "APEX network editor; simple_deformer uses apex_editgraph for the "
            "same 'edit the graph' role. Confirms which edit-graph type is real."
        ),
        rank=35,
    ),
]
