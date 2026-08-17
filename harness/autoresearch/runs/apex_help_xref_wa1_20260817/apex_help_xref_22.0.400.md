# APEX help-cache cross-reference — WA1-XREF (C3 referee)

*Generated 2026-08-17T16:46:00.541945+00:00*

## Runtime witness
- **Consumed:** yes — build `22.0.400`
- Artifact: `C:\Users\User\SYNAPSE\.claude\worktrees\wa1-truth\harness\autoresearch\runs\apex_basic_20260817_122650\apex_truth_22.0.400.json`

## Referee caveat (low-recall, encoded in the verdicts)
> The help cache is HIGH-PRECISION, LOW-RECALL: it holds only locally-browsed pages, not the full product surface. Absence from the cache is NO-EVIDENCE, never product-absence. A quarantine candidate is emitted ONLY when the runtime was actually consumed (runtime_consumed=true); otherwise the runtime column is UNKNOWN and no node is called absent.

## Sources
- Docs cache: `C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache` (config 22.0)
- Cache entries parsed: **25**
- Recipe names scanned: **24**

## Verdict tally

| verdict | count | meaning |
|---|---|---|
| `confirmed` | 17 | docs+runtime agree (membership) |
| `undocumented` | 27 | runtime present, docs absent (low-recall gap) |
| `quarantine-candidate` | 2 | docs present, runtime KNOWN-absent (deprecation/phantom) |
| `type-mismatch` | 0 | docs+runtime present but a port type differs |
| `runtime-unknown` | 9 | docs present, runtime UNKNOWN (apex_truth not yet consumed) |
| **unclassified** | **0** | must be 0 |

- Deprecated in docs: **1**
- Quarantine candidates (doc-present / runtime-absent): **2**

## Per-node rows

| surface | node | verdict | docs | runtime | recipes | docs anchor | runtime anchor |
|---|---|---|---|---|---|---|---|
| apex_callback | `Add<Float>` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[9]:apex_port_signature:Add<Float> |
| apex_callback | `Add<Matrix4>` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[8]:apex_port_signature:Add<Matrix4> |
| apex_callback | `component::MappedConstraints` | `quarantine-candidate` | present | absent | absent | nodes/apex/component--MappedConstraints-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `controlgadget::SnapXFormToAxes` | `quarantine-candidate` | present | absent | absent | nodes/apex/controlgadget--SnapXFormToAxes.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `geo::AddPacked` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[11]:apex_port_signature:geo::AddPacked |
| apex_callback | `geo::Lattice` | `confirmed` | present | present | absent | nodes/apex/geo--Lattice-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::AbstractControl` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[5]:apex_port_signature:rig::AbstractControl |
| apex_callback | `rig::CombineParmTransform` | `confirmed` | present | present | absent | nodes/apex/rig--CombineParmTransform-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::ControlSpline` | `confirmed` | present | present | absent | nodes/apex/rig--ControlSpline-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::ControlSplineFromArray` | `confirmed` | present | present | absent | nodes/apex/rig--ControlSplineFromArray-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::CurveIK` | `confirmed` | present | present | absent | nodes/apex/rig--CurveIK.json | apex_truth_22.0.400.json#entries[12]:apex_port_signature:rig::CurveIK |
| apex_callback | `rig::ExtractParmTransform` | `confirmed` | present | present | absent | nodes/apex/rig--ExtractParmTransform-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SampleSplineTransforms` | `confirmed` | present | present | absent | nodes/apex/rig--SampleSplineTransforms-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SampleSplineTransforms::2.0` | `confirmed` | present | present | absent | nodes/apex/rig--SampleSplineTransforms-2.0.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SampleSplineTransformsToArray` | `confirmed` | present | present | absent | nodes/apex/rig--SampleSplineTransformsToArray-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SampleSplineTransformsToArray::2.0` | `confirmed` | present | present | absent | nodes/apex/rig--SampleSplineTransformsToArray-2.0.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SplineInterpolateTransforms` | `confirmed` | present | present | absent | nodes/apex/rig--SplineInterpolateTransforms-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SplineInterpolateTransforms::2.0` | `confirmed` | present | present | absent | nodes/apex/rig--SplineInterpolateTransforms-2.0.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SplineInterpolateTransformsToArray` | `confirmed` | present | present | absent | nodes/apex/rig--SplineInterpolateTransformsToArray-.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `rig::SplineInterpolateTransformsToArray::2.0` | `confirmed` | present | present | absent | nodes/apex/rig--SplineInterpolateTransformsToArray-2.0.json | apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:* |
| apex_callback | `skel::AddJoint` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[10]:apex_port_signature:skel::AddJoint |
| apex_callback | `transform::Blend` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[6]:apex_port_signature:transform::Blend |
| apex_callback | `transform::LookAt` | `confirmed` | present | present | absent | nodes/apex/transform--LookAt-.json | apex_truth_22.0.400.json#entries[7]:apex_port_signature:transform::LookAt |
| lop_type | `apexsoprigbuilder` | `runtime-unknown` | present | unknown | absent | nodes/lop/apexsoprigbuilder.json | — |
| sop_type | `apex::apexscript` | `runtime-unknown` | present | unknown | absent | nodes/sop/apex--script.json | — |
| sop_type | `apex::autorigbuilder` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[14]:type_exists[*]:apex::autorigbuilder |
| sop_type | `apex::autorigcomponent` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[21]:type_exists[*]:apex::autorigcomponent |
| sop_type | `apex::autorigcomponent::2.0` | `runtime-unknown` | present | unknown | absent | nodes/sop/apex--autorigcomponent-2.0.json | — |
| sop_type | `apex::autorigcomponent::3.0` | `runtime-unknown` | present | unknown | absent | nodes/sop/apex--autorigcomponent.json | — |
| sop_type | `apex::buildfkgraph` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[15]:type_exists[*]:apex::buildfkgraph |
| sop_type | `apex::configurecontrols` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[22]:type_exists[*]:apex::configurecontrols |
| sop_type | `apex::configuregraph` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[20]:type_exists[*]:apex::configuregraph |
| sop_type | `apex::controlextract` | `confirmed` | present | present | absent | nodes/sop/apex--controlextract-.json | apex_truth_22.0.400.json#entries[23]:type_exists[*]:apex::controlextract |
| sop_type | `apex::controlextract::2.0` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[28]:type_exists[*]:apex::controlextract::2.0 |
| sop_type | `apex::graph` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[19]:type_exists[*]:apex::graph |
| sop_type | `apex::invokegraph` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[13]:type_exists[*]:apex::invokegraph |
| sop_type | `apex::layoutgraph` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[32]:type_exists[*]:apex::layoutgraph |
| sop_type | `apex::mapcharacter` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[24]:type_exists[*]:apex::mapcharacter |
| sop_type | `apex::mergegraph` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[31]:type_exists[*]:apex::mergegraph |
| sop_type | `apex::packcharacter` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[25]:type_exists[*]:apex::packcharacter |
| sop_type | `apex::rigpose` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[27]:type_exists[*]:apex::rigpose |
| sop_type | `apex::rigscriptcomponent` | `runtime-unknown` | present | unknown | absent | nodes/sop/apex--rigscriptcomponent.json | — |
| sop_type | `apex::sceneaddanimation` | `runtime-unknown` | present | unknown | absent | nodes/sop/apex--sceneaddanimation-.json | — |
| sop_type | `apex::sceneanimate` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[30]:type_exists[*]:apex::sceneanimate |
| sop_type | `apex::sceneinvoke` | `confirmed` | present | present | absent | nodes/sop/apex--sceneinvoke-.json | apex_truth_22.0.400.json#entries[26]:type_exists[*]:apex::sceneinvoke |
| sop_type | `apex::sceneinvoke::2.0` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[29]:type_exists[*]:apex::sceneinvoke::2.0 |
| sop_type | `bonegenerator` | `runtime-unknown` | absent | unknown | present | — | — |
| sop_type | `kinefx::blendtransforms` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[17]:type_exists[*]:kinefx::blendtransforms |
| sop_type | `kinefx::rigdoctor` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[18]:type_exists[*]:kinefx::rigdoctor |
| sop_type | `kinefx::twoboneik` | `undocumented` | absent | present | present | — | apex_truth_22.0.400.json#entries[16]:type_exists[*]:kinefx::twoboneik |
| sop_type | `kinefx::usdanimimport` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[33]:type_exists[*]:kinefx::usdanimimport |
| sop_type | `kinefx::usdcharacterimport` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[34]:type_exists[*]:kinefx::usdcharacterimport |
| sop_type | `kinefx::usdskinimport` | `undocumented` | absent | present | absent | — | apex_truth_22.0.400.json#entries[35]:type_exists[*]:kinefx::usdskinimport |
| sop_type | `null` | `runtime-unknown` | absent | unknown | present | — | — |
| sop_type | `skeleton` | `runtime-unknown` | absent | unknown | present | — | — |

## Quarantine candidates (both anchors required)

- `component::MappedConstraints` (apex_callback) — docs=`nodes/apex/component--MappedConstraints-.json` runtime=`apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:*` deprecated=False successor=None
- `controlgadget::SnapXFormToAxes` (apex_callback) — docs=`nodes/apex/controlgadget--SnapXFormToAxes.json` runtime=`apex_truth_22.0.400.json#entries[0]:apex_callback_catalog:*` deprecated=False successor=None

## Deprecations recorded in docs (runtime-independent)

- `rig::CurveIK` → successor `rig::SampleSplineTransforms` (since 20.0, `nodes/apex/rig--CurveIK.json`)
