# VERIFY measurement contract and candidate tolerances

Status: code-side candidates, **not golden-scene qualification**. No pinned HIP or
reference EXR was supplied to this stream. The swarm contract explicitly defers
that capture. A passing synthetic test does not promote a recipe or a gate.

## Evidence boundary

The six classes in `python/synapse/recipes/verify.py` implement the frozen
`Verifier.run(check, instance, spec, **context)` seam. They return detached,
JSON-safe `CheckResult.evidence` mappings. They never call a writer, trigger
a render, load a payload, repair a graph, or undo a transaction.

Default P1-P4 observations use `HostObserver`. Every Houdini read runs through
`run_on_main`; the stage is read from a captured owned LOP ID. A missing host,
unreadable stage, missing expectation, incomplete observation, or timeout returns
UNKNOWN with its diagnosis. A wrong verifier/check dispatch returns NOT_RUN.

`observation=...` and an injected `ObservationReader` are trusted host/testing
interfaces. Do not expose them as model-selected request fields. An injected
`complete=True` declares the producer's coverage; it is not something this
module can establish from an arbitrary dictionary.

## Additive capture adapter (no frozen-contract edits)

Populate `spec.golden_reference["verification"]` from the selected scene:

| Key | Captured meaning |
|---|---|
| `stage_node_id` | An ID in `instance.owned_node_ids`, naming the intended read-only LOP stage. |
| `expected_prims` | Nonempty records with absolute USD `path`, exact `type`, and optional applied `schemas`. |
| `expected_prims[].material` | Intended computed-bound material path. Material must be active/defined and resolve a surface shader with a nonempty shader ID. |
| `expected_prims[].render_context` | Captured material surface context, e.g. `mtlx`; omitted means the universal context, not a search through contexts. |
| `expected_prims[].surface_shader`, `shader_id` | Optional exact surface path/ID checks against the capture. |
| `render_settings_path` | Absolute path of the intended RenderSettings prim, never a first-prim fallback. |
| `render_input_connections` | Nonempty subset of `spec.connections` covering the complete captured render-input branch, including source/destination port indices. |
| `image` | The pinned image/reference requirements below. |

The captured node records include all nested shader/output nodes, exact type and
category, parent ID, authored parameter values/expressions, meaningful flags and
optional `input_names`/`output_names`. P1 compares committed slot values
plus this action's supplied validated slots. Declared float/color3 slot values
are normalized to authored floating-point values before comparing field digests;
ambiguous slot keys across actions are rejected. Layout positions do not participate.

Host parameter capture supports raw scalar values, raw constant tuples, and
`{"type": ..., "value": ...}` wrappers for float/int/string, Menu/enum,
Toggle/bool and float3/color3. Scalar expressions include value, expression and
language. Uncaptured keyframe animation and animated tuples return UNKNOWN;
golden capture must qualify or extend those representations before using them.
BLOCKS `runtime.observe` supplies supplemental outer-box evidence when a
network box is supplied. It does not cover nested shaders or source-output ports;
the host adapter reads those explicitly.

## P3 assessor compatibility

`_assess_stage` and `assess_render_ready` gain optional
`render_settings_path` and `render_input_branch` arguments. Omitting the
path preserves the legacy scope and verdict. An explicit path, including an
empty one, enters strict mode. Legacy readiness does not qualify recipe P3.

Strict mode requires a single camera relationship target resolving to an
active/defined UsdGeom.Camera, products connected to these settings, authored
output names, connected ordered RenderVars with authored sourceName/dataType,
at least two active/defined authored LightAPI prims, and the captured branch's
actual source/destination ports. The new clauses are `products_authored`,
`two_authored_lights`, `render_input_branch`, `traversal_complete`;
the resolved settings path and camera targets are retained in details.
P3 separately checks observed branch node type/category/parent/flags/path against
the spec and instance. A correctly bound camera cannot conceal a broken branch.

The assessor branch argument is a trusted observation record:
`{"expected": [connection records], "observed": [connection records], "complete": true}`.
HostObserver produces it from fresh graph reads; do not accept a model's boolean.

## P4 composition and dependencies

Composition errors, owned-node errors, missing assets, and payload load state are
separate evidence channels. Dependency resolution uses
`UsdUtils.ComputeAllDependencies` on used layers under the stage resolver
context. Unloaded payloads fail qualification; they are reported independently
of missing assets. No payload is loaded to make a predicate pass. Traversal
limits cause UNKNOWN in the verifier, with the limit diagnosis.

## P5 qualification candidates

Start with a **64 x 64 image and one sample**. These are starting settings to
measure, not a latency or quality guarantee. The `image` record contains:

| Key | Meaning / candidate default |
|---|---|
| `reference_path` | Captured reference image file readable in the host environment. Resolve approved path tokens before calling the verifier. |
| `reference_sha256` | Measured digest of that reference's bytes. A changed reference is UNKNOWN. |
| `resolution` | [width, height]; candidate [64, 64]. |
| `samples` | Candidate 1, matched against the terminal job record. |
| `channels` | Exact ordered channels, candidate [R, G, B]; RGB must be present. Capture RGBA explicitly if that is the actual product. |
| `regions` | Named hero and ground regions selected from the reference, each with integer `bounds=[x0,y0,x1,y1]`. Bounds are half-open, in unflipped decoded pixel coordinates. No guessed default regions. |
| `luminance_threshold` | Candidate 0.01 in the reference's linear RGB units. |
| `coverage_tolerance` | Candidate 0.10 absolute fraction (ten percentage points). |
| `mean_rgb_tolerance` | Candidate 0.05 absolute linear value, per RGB channel. |

For each region, derive the reference measurements from the pinned reference
pixels at verification time. A pixel is visible when
`0.2126 R + 0.7152 G + 0.0722 B > luminance_threshold`.
Coverage is the visible-pixel count divided by region area; mean RGB is the
arithmetic mean of all RGB samples in the region.

Both regions must satisfy:

1. Absolute coverage difference from the reference <= coverage_tolerance.
2. Maximum per-channel absolute mean difference <= mean_rgb_tolerance.
3. Reference coverage > coverage_tolerance, preventing an empty/dark reference
   region from qualifying a missing subject.

These are smoke criteria. They can reject nonblack wrong-color/missing-subject
images; they do not prove perceptual equivalence or detect every image with the
same regional statistics. Do not describe P5 as a beauty or exact-scene oracle.
Reference capture must select meaningful, distinct hero/ground regions and
measure repeated same-scene variation before these defaults are accepted.

The trusted context requires:

- `render_job`: `terminal=True`, `state=SUCCEEDED` or `COMPLETED`,
  `exit_code=0`, measured `started_ns` (epoch nanoseconds), output_path,
  resolution, samples, and the lifecycle job's provenance fields.
- `output_path`: the trusted planned output, matching the job.
- `prior_artifacts`: every previous output identity in receipt context; an
  explicit empty list means the first run. Missing history is UNKNOWN.

A file identity includes resolved path, device, inode, mtime_ns, size, SHA-256.
Output must be nonempty, have mtime >= job start, differ in the inode/mtime/size
tuple from every prior artifact, and have a digest unequal to every prior
artifact's digest. The tuple is an identity: equal size alone does not mean
staleness, and a changed timestamp does not rescue copied old bytes.
File identity is checked before/after hashing and again after image reads.
A changing file is UNKNOWN. No filesystem timestamp tolerance is silently added.

The default decoder uses the repo's OpenImageIO read_image pattern
(`python/synapse/autonomy/evaluator.py:116`), with header dimension/channel
checks before allocating pixels. OIIO is optional and is never installed by
the verifier. Missing OIIO is UNKNOWN; unreadable/invalid image data fails P5.
All RGB values must be readable and finite. Injected decoders are test/host
adapters, not an authorization interface.

Measure on the pinned HIP/build/engine/frame/seed/asset set:
same-scene repeats, cold/warm outputs, controlled missing hero/ground,
wrong-color and unrelated-scene images, channel ordering, and filesystem
timestamp resolution. Record false accepts/rejects and measured tolerances.
Thirty seconds remains an unmeasured budget candidate; no timing claim is made.

## P6 complete semantic scope and recovery

The lifecycle host supplies `before` and `after` field-digest snapshots,
`action`, validated `slots`, and the separate `RecoveryVerdict`.
Use `semantic_snapshot(nodes, connections, scope=..., complete=True)` only
after observing the entire relevant scope, including unrelated artist nodes
and USD authored opinions. Include owned nodes' actual `path` fields. P1's
owned-only, declared-parameter observation is **not** a whole-scene P6 snapshot.

The adapter canonicalizer is `verify-fields-v1`: JSON-sorted authored values
produce SHA-256 per field and an aggregate hash over the field map. It excludes
only node `id` (the map key) and layout `position`; expressions, flags,
types, parents, paths and ports remain meaningful. Field components escape
tilde/slash using JSON-pointer rules to avoid aliases. Preserve arbitrary artist
USD opinions as additional semantic records, rather than dropping them during
adaptation. C1's canonicalizer may feed this projection through a host adapter;
no sibling module's private functions are imported.

Edit pre-state must include the captured fields and connections. Changed fields
must be exactly within this action's supplied slot bindings, and successful
post-state must contain the requested values. A no-op is allowed only when the
requested values are already observed. BUILD can add only captured owned state,
with its expected values; it cannot reset existing fields.

If recovery happened, also provide `mutation_terminal=True` and a complete
`rollback` snapshot of the same scope. P6 measures exact rollback residue
against pre-state and retains the list. UNKNOWN recovery remains UNKNOWN.
A P6 PASS for clean recovery is **not** a successful operation. Lifecycle must
keep the failed operation verdict separate when creating its RunReceipt.

## Limits awaiting measurement

No golden scene, live H22 host path, real EXR read, render job, actual undo or
rollback, latency distribution, plugin compatibility, or UI behavior was
qualified by synthetic tests. The headless tests are separately gated in
`tests/test_recipe_verify_hython.py`; a skip is NOT_RUN evidence.
