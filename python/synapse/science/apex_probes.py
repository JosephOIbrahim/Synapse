"""APEX seed probes for the SYNAPSE science loop.

Each :class:`ProbeSpec` in :data:`APEX_SEED` encodes a *verifiable assumption*
the SYNAPSE codebase makes about Houdini's APEX surface. The science loop
(``loop.run_search``) walks these against a live, injected namespace (the
``apex`` module + ``hou``) via ``probe.probe`` to confirm which assumptions are
champions and which are dead ends — without re-walking what the registry knows.

APEX-TRUTH-BUILD: 22.0.400
RE-STAMPED 2026-08-17 — confirmed against the live H22.0.400 runtime
-------------------------------------------------------------------
The build string above is **read from the runtime**, never typed from memory:
``hou.applicationVersionString()`` == ``22.0.400`` observed under hython during
the WA1-TRUTH re-run (G1/G4+C1). The prior stamp named an **H21 build** (see git
history for the exact number) — a truth verified once (2026-06-02) and then
silently aged, which is precisely the stale-truth defect class this re-stamp
retires. The per-build evidence artifact
``harness/autoresearch/runs/<stamp>/apex_truth_22.0.400.json`` (mission
``apex_basic``) is the receipt; ``harness/verify/version_agreement.py`` now reds
if this stamp drifts from the freshest artifact.

What the H22.0.400 re-run confirmed (probe evidence, not recall):

  * All the corrected node-type seeds below are **present** on 22.0.400 — with
    one category-drift finding: ``kinefx::twoboneik`` and
    ``kinefx::blendtransforms`` are **Vop** category on this build, not Sop.
    They exist; the probe records the category so the drift is visible.
  * H22 additions confirmed and seeded: ``apex::rigpose`` (Rig Pose SOP, set
    driven keys), ``apex::controlextract::2.0``, ``apex::sceneinvoke::2.0``
    (the "APEX Scene Evaluate" alias), ``apex::sceneanimate``, and the
    fuse-graph utilities ``apex::mergegraph`` / ``apex::layoutgraph``. The
    UsdSkel renames are label-only: ``kinefx::usdanimimport`` /
    ``usdcharacterimport`` / ``usdskinimport`` now read "UsdSkel …" but the
    type names are unchanged.
  * Two blueprint phantoms falsified (recorded ``exists: False`` in the
    ``apex_basic`` mission evidence, not seeded — an absence guard is not a
    presence assumption): ``apex::configuregraph::2.0`` (Configure Graph
    "Effects" is a *mode* parm on ``apex::configuregraph``, not a ``::2.0`` node)
    and ``apex::fusegraph`` (the fuse-graph *utilities* are
    ``mergegraph``/``layoutgraph``; no literal ``fusegraph`` node exists).
  * The callback registry is enumerable at runtime:
    ``apex.callbackRegistry().callbackDefinitions()`` returns **2286** callbacks
    on 22.0.400; per-callback ports come from ``Registry.getSignature(name)``
    (types incl. ``VariadicArg<T>``, ``Matrix4``, ``Geometry``). The autoresearch
    ``apex_basic`` mission dumps that catalog into the evidence artifact.

HISTORY — the 2026-06-02 re-seed (against the then-current H21 catalog) killed
the fictional ``apex::rig::`` / ``apex::sop::`` / ``apex::autorig::`` namespaces
the recipes had *invented*. APEX node types are **flat** ``apex::<name>`` — there
is NO ``::rig::`` / ``::sop::`` / ``::autorig::`` middle segment; several rig
operators live under ``kinefx::``. Supersession map (fictional -> real), see
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
``apex_explainer.py``) must be migrated to these real names before they build
(that migration is WA1-RECIPE / blueprint G2, not this leg).

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
    # --- H22.0.400 additions (WA1-TRUTH re-run 2026-08-17; all Sop, confirmed) --
    ProbeSpec(
        surface="nodetypes.apex::rigpose",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 APEX Rig Pose SOP (set-driven keys). New in the H22 delta "
            "(blueprint sec.3); confirmed present on 22.0.400."
        ),
        rank=43,
    ),
    ProbeSpec(
        surface="nodetypes.apex::controlextract::2.0",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 Control Extract 2.0 — versioned successor to apex::controlextract "
            "(both present on 22.0.400)."
        ),
        rank=42,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sceneinvoke::2.0",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 Scene Invoke 2.0 — the 'APEX Scene Evaluate' alias of "
            "apex::sceneinvoke; confirmed present on 22.0.400."
        ),
        rank=41,
    ),
    ProbeSpec(
        surface="nodetypes.apex::sceneanimate",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 APEX Scene Animate SOP (the SOP-context animate; the LOP "
            "counterpart is the 'apexanimate' Hydra scene-index node)."
        ),
        rank=40,
    ),
    ProbeSpec(
        surface="nodetypes.apex::mergegraph",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 fuse-graph utility (APEX Merge Graph) on the APEX Graph SOP path. "
            "Supersedes the blueprint's shorthand 'fusegraph' — there is no literal "
            "apex::fusegraph node."
        ),
        rank=39,
    ),
    ProbeSpec(
        surface="nodetypes.apex::layoutgraph",
        kind="nodetype",
        expect="present",
        rationale=(
            "H22 fuse-graph utility (APEX Layout Graph); companion to "
            "apex::mergegraph in the graph-assembly path."
        ),
        rank=38,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::usdanimimport",
        kind="nodetype",
        expect="present",
        rationale=(
            "UsdSkel rename (blueprint sec.3): the TYPE name is stable; the H22 "
            "label is now 'UsdSkel Animation Import' (was 'USD Animation Import')."
        ),
        rank=37,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::usdcharacterimport",
        kind="nodetype",
        expect="present",
        rationale=(
            "UsdSkel rename: H22 label 'UsdSkel Character Import'; type name stable."
        ),
        rank=36,
    ),
    ProbeSpec(
        surface="nodetypes.kinefx::usdskinimport",
        kind="nodetype",
        expect="present",
        rationale=(
            "UsdSkel rename: H22 label 'UsdSkel Skin Import'; type name stable."
        ),
        rank=35,
    ),
    # NOTE — the two falsified blueprint phantoms (apex::configuregraph::2.0,
    # apex::fusegraph) are deliberately NOT seeded here: APEX_SEED is the set of
    # PRESENCE assumptions (each catalog-confirmed), and an absence guard is not an
    # emitted node type. Their falsification lives where it belongs — as live
    # exists=False evidence in the apex_basic mission's apex_truth artifact, and in
    # the RE-STAMPED note above. See harness/autoresearch/missions/apex_basic.json.
]
