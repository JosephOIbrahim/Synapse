"""APEX seed probes for the SYNAPSE science loop.

Each :class:`ProbeSpec` in :data:`APEX_SEED` encodes a *verifiable assumption*
the SYNAPSE codebase makes about Houdini 21.0.671's APEX surface. The science
loop (``loop.run_search``) walks these against a live, injected namespace (the
``apex`` module + ``hou``) via ``probe.probe`` to confirm which assumptions are
champions and which are dead ends — without re-walking what the registry knows.

RE-SEEDED 2026-06-02 — corrected against the live H21.0.671 catalog
------------------------------------------------------------------
The original seeds carried node-type strings the recipes *invented* — an
``apex::rig::``/``apex::sop::``/``apex::autorig::`` namespacing that does **not
exist**. A second-seed harness run + a read-only catalog dump (5811 types) +
a 3-lens adversarial reconcile established the real surface:

  * APEX node types are **flat** ``apex::<name>`` — there is NO ``::rig::`` /
    ``::sop::`` / ``::autorig::`` middle segment.
  * Several rig operators live under ``kinefx::``, not ``apex::``.

These seeds now carry the **real** names (each confirmed present in the
catalog). Supersession map (fictional -> real), see
``docs/SCIENCE_apex_verify_run_2026-06-02.md``:

    apex::rig::fkfull        -> apex::buildfkgraph
    apex::rig::ikfull        -> kinefx::twoboneik   (+ solveik/fullbodyik)
    apex::rig::blendtransform-> kinefx::blendtransforms
    apex::autorig::build     -> apex::autorigbuilder (+ apex::autorigcomponent)
    apex::sop::invoke        -> apex::invokegraph    (+ apex::sceneinvoke)
    apex::sop::graphdefaults -> apex::graph          (the base graph itself)
    apex::sop::apexedit      -> apex::configuregraph (edit via apex.Graph API)
    apex::sop::transformobject-> apex::configurecontrols / controlextract
    apex::sop::fromkinefx    -> apex::mapcharacter / packcharacter (diffuse)
    rig_doctor               -> kinefx::rigdoctor

NOTE — type-existence is confirmed; node SIGNATURES / role-fit are a separate
verification (catalog membership != does-the-intended-job). The recipes that
still reference the fictional names (``python/synapse/panel/apex_recipes.py``,
``apex_explainer.py``) must be migrated to these real names before they build.

``kind`` distinguishes a plain attribute lookup (``"attr"``) from something
invoked (``"call"``), a graph constructed (``"construct"``), or a Houdini node
type looked up by NAME in a catalog (``"nodetype"`` — required because type
names contain "::" and are not getattr-resolvable). ``expect`` records the
prior belief; the loop's job is to confirm or falsify it.
"""

from __future__ import annotations

from .probe import ProbeSpec

# NOTE on surface convention:
#   For node-type assumptions (kind="nodetype") the surface is the SOP/APEX
#   type STRING carrying a "nodetypes." routing prefix. The probe namespace is
#   expected to expose a node-type catalog as namespace["nodetypes"] — a dict
#   keyed by full type name. probe() strips the prefix and does a MEMBERSHIP
#   test ("apex::invokegraph" in catalog), NOT getattr.
#   For pure Python APEX-module assumptions (kind="attr"/"call") the surface is
#   a dotted attribute path against namespace["apex"].

APEX_SEED: list[ProbeSpec] = [
    # --- Python-level APEX module surface (highest value: gates everything) ---
    ProbeSpec(
        surface="apex.Graph",
        kind="attr",
        expect="present",
        rationale=(
            "apex_explainer's graph-as-geometry model assumes a first-class "
            "APEX graph type at the Python layer; recipes build/edit graphs "
            "before Invoke evaluates them. CONFIRMED on two seeds."
        ),
        rank=100,
    ),
    ProbeSpec(
        surface="apex.Graph.addNode",
        kind="call",
        expect="present",
        rationale=(
            "apex_editgraph / 'add nodes for your deformation logic' "
            "(simple_deformer) assumes the graph is mutable via addNode — the "
            "canonical APEX Graph mutator. CONFIRMED present on two seeds; "
            "exact call signature still unverified."
        ),
        rank=90,
    ),
    # --- Real APEX/KineFX node types (re-seeded 2026-06-02; all catalog-present) ---
    ProbeSpec(
        surface="nodetypes.apex::invokegraph",
        kind="nodetype",
        expect="present",
        rationale=(
            "Run-program bridge: APEX graph -> SOP geometry. Supersedes the "
            "fictional apex::sop::invoke. Variants: apex::sceneinvoke, "
            "sopinvokegraph. Gates every recipe that evaluates a graph."
        ),
        rank=85,
    ),
    ProbeSpec(
        surface="nodetypes.apex::autorigbuilder",
        kind="nodetype",
        expect="present",
        rationale=(
            "Generates a full production rig from a named skeleton "
            "(autorig_biped recipe). Supersedes fictional apex::autorig::build; "
            "assembles apex::autorigcomponent parts."
        ),
        rank=80,
    ),
    ProbeSpec(
        surface="nodetypes.apex::buildfkgraph",
        kind="nodetype",
        expect="present",
        rationale=(
            "FK setup as an APEX graph build (fk_chain / fk_ik_blend / "
            "control_shapes recipes). Supersedes fictional apex::rig::fkfull."
        ),
        rank=78,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::twoboneik",
        kind="nodetype",
        expect="present",
        rationale=(
            "Limb IK solver with end effector + pole vector (ik_chain / "
            "fk_ik_blend). Supersedes fictional apex::rig::ikfull — IK lives "
            "under kinefx::, not apex:: (siblings: solveik/fullbodyik/ikchains)."
        ),
        rank=76,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::blendtransforms",
        kind="nodetype",
        expect="present",
        rationale=(
            "Blends FK/IK transform sets (fk_ik_blend). Supersedes fictional "
            "apex::rig::blendtransform; kinefx::skeletonblend is the migration "
            "guide's Skeleton-Blend alternate."
        ),
        rank=74,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::rigdoctor",
        kind="nodetype",
        expect="present",
        rationale=(
            "Mandatory pre-APEX skeleton validator (fk_chain, autorig_biped, "
            "kinefx_to_apex). Supersedes the bare 'rig_doctor' string — the "
            "validator is kinefx-namespaced. Strongest of the corrected names."
        ),
        rank=72,
    ),
    ProbeSpec(
        surface="nodetypes.apex::graph",
        kind="nodetype",
        expect="present",
        rationale=(
            "The base APEX graph node — seed a graph rather than build from "
            "scratch (simple_deformer). Supersedes fictional "
            "apex::sop::graphdefaults (no dedicated 'defaults' node exists)."
        ),
        rank=70,
    ),
    ProbeSpec(
        surface="nodetypes.apex::configuregraph",
        kind="nodetype",
        expect="present",
        rationale=(
            "Configure/edit an APEX graph. Supersedes fictional "
            "apex::sop::apexedit; the edit capability is the apex.Graph API "
            "(champion) plus configuregraph/layoutgraph/mergegraph."
        ),
        rank=65,
    ),
    ProbeSpec(
        surface="nodetypes.apex::autorigcomponent",
        kind="nodetype",
        expect="present",
        rationale=(
            "Per-part autorig building blocks assembled by apex::autorigbuilder "
            "(::2.0/::3.0 variants exist). Recipe-relevant for component rigs."
        ),
        rank=60,
    ),
    ProbeSpec(
        surface="nodetypes.apex::configurecontrols",
        kind="nodetype",
        expect="present",
        rationale=(
            "Authors APEX controls into a graph — the node side of "
            "'creates a transform control'. Supersedes fictional "
            "apex::sop::transformobject (control = apex.TransformControl)."
        ),
        rank=55,
    ),
    ProbeSpec(
        surface="nodetypes.apex::controlextract",
        kind="nodetype",
        expect="present",
        rationale=(
            "Extracts controls from a rig — companion to configurecontrols in "
            "the transform-control authoring path."
        ),
        rank=50,
    ),
    ProbeSpec(
        surface="nodetypes.apex::mapcharacter",
        kind="nodetype",
        expect="present",
        rationale=(
            "Ingests a (kinefx) character/skeleton into APEX. Supersedes "
            "fictional apex::sop::fromkinefx — KineFX & APEX share the "
            "point-skeleton, so 'convert' is diffuse via mapcharacter/"
            "packcharacter + apex.findSkeletonJoints."
        ),
        rank=48,
    ),
    ProbeSpec(
        surface="nodetypes.apex::packcharacter",
        kind="nodetype",
        expect="present",
        rationale=(
            "Packs an APEX character — companion to mapcharacter in the "
            "KineFX->APEX ingestion path."
        ),
        rank=46,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sceneinvoke",
        kind="nodetype",
        expect="present",
        rationale=(
            "Scene-level invoke variant of apex::invokegraph (::2.0 exists). "
            "Recipe-relevant for character-scene evaluation."
        ),
        rank=44,
    ),
]
