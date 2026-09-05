# SYNAPSE / Solaris Recipes x H22 -- Blueprint v3.0

> Source: SYNAPSE_Solaris_Blueprint_v3.docx (Joe, 04 September 2026). Converted verbatim for the bp5 swarm; tables flattened to one cell per line. STATUS in the source: design proposal, not implemented.


SYNAPSE  /  DESIGN HANDOFF
SOLARIS RECIPES× H22
Blueprint v3.0 — refactored from first principles
04 September 2026  •  Demo target: 13 September 2026
Decision  Ship one complete, repeatable Solaris scene with bounded edits, explicit render approval, and evidence that describes the current scene.
The model interprets the request. A versioned recipe defines the permitted structure. The host authorizes and applies the change. Separate checks establish what actually exists and what actually renders.
What this document changes
Reuses the existing fixture/reconciliation foundation; no third recipe engine.
Separates build, edit, render, recovery and evidence freshness into explicit contracts.
Protects artist edits and existing consent gates; “recipe-only” is not a permission bypass.
Read by need
Need
Pages
Architecture and scope
2–4
Golden capture, authorization and recovery
5–7
Predicates, card truth and acceptance tests
8–11
Implementation order and September 13 decision
12
Evidence and change record
13–14

STATUS: design proposal, not implemented. Based on the v2 blueprint and the earlier review pinned to commit 2b9f9e0. No Houdini execution, current-head audit or gate promotion was performed while authoring these documents.

## Page 02

Start with the invariant, not the tool
The failure to prevent is simple: a plausible partial scene is reported as complete, then a later instruction changes more than the artist intended. Neither better prose nor a longer node catalog defines when to stop.
Five first principles
Intent is not permission. A request for a scene does not authorize arbitrary code, an expensive render, or an export to any path.
Structure needs an owner. The recipe defines the graph and editable fields. The model cannot invent topology, parameter names or recovery actions.
A graph is not its output. Nodes and wires, composed USD, and rendered pixels answer different questions. Each needs its own evidence.
Change must be local. A valid iteration edits only declared fields on the expected recipe instance. It does not repair or reset the surrounding scene.
Evidence expires. A successful earlier run is history, not proof about a modified scene. Unknown, stale and broken are different conditions.
What the earlier review established
The pinned planner recognized requested features that its scene builder omitted. The main panel used ClaudeWorker, so a router-only fence missed the relevant execution path. Existing BLOCKS fixtures already supplied useful reconciliation machinery. A full H22.0.400 LOP catalog existed. The B-7 CRUX receipt attributed the decisive render fix to topology, not camera binding alone. [S1–S6]
What remains unproven  The exact source of surplus nodes in an actual demo session still requires tool/node provenance. The revised runner, capture/rebuild fidelity, render bounds and clean recovery require fresh tests. Do not promote a design claim because the document is complete.

## Page 03

Freeze one artist loop
The September 13 baseline is one owned Solaris instance: hero sphere, ground plane, two real MaterialX materials with valid bindings, dome and key light, camera, Karma render settings, render branch and display output.
Operation
Allowed change
Completion
BUILDsolaris.spine
Create one captured topology in a clean owned scope.
Graph + USD verified.
LIGHTsolaris.iterate.light
Exposure on the captured key light only.
Field delta + USD verified.
MATERIALsolaris.iterate.material
Hero base-color input only.
Shader delta + binding verified.
RENDERsolaris.render.karma
Bounded settings/output through existing approval.
Current output + smoke checks verified.

Deliberate September 13 limits
Pin one Houdini build, one Karma engine and one hero topology from the successful hand-built scene. Do not promise both CPU/XPU or sphere/cube until each has its own evidence.
Start with exact demo phrases and typed panel controls. Phrase matching must consume the entire request; an unsupported trailing clause must not disappear.
Off-list or ambiguous changes stop before mutation: clarify or refuse, with a supported alternative.
No fog, fluid simulation, arbitrary asset ingestion, general recipe capture UI or world-ingest ending on the baseline path.
Scope recommendation  Move world ingest after the September 13 demo. This is intentionally stricter than v2’s late optional branch. Reopening it is a new Joe go/no-go decision and requires requalification of the base take.
A literal phrase demo proves deterministic orchestration. It does not demonstrate broad natural-language understanding. State that distinction on camera.

## Page 04

One specification, three separate objects
A single source of truth does not mean one file must contain every runtime fact. Keep three objects with different owners and lifetimes.
Object
Owner
Contains
RecipeSpecimmutable version
Curated authoring + registry
Topology, actions, slot bounds, predicates, presentation, compatibility.
RecipeInstancescene-local identity
Host runtime
Owned node IDs, instance ID, committed slot values, graph revision, authored baseline.
RunReceiptimmutable evidence
Verifier
Request/run IDs, observed checks, approval provenance, mutation outcome, render evidence.

Canonical location and reuse
Proposed schema v2 lives in fixtures/solaris.spine.json; it is not a supported API today. Extend blocks/fixtures.py with backward-compatible loading and adapters for the panel and routing. Actions reference one graph. Keep existing fixtures and non-demo profiles unchanged.
Use BLOCKS as the ownership/reconciliation base. Factor reusable DAG validation, wiring and layout helpers from handlers_solaris_graph.py only where needed. Do not nest public handlers or run two independent reconcilers over the same instance. [S3, S4]
Minimum schema contract
Version, recipe ID, supported build, catalog and canonicalizer digests; a required golden-reference record.
Node records: ID, parent ID, category, exact resolved type, typed parameters, flags and position. Include every nested shader/output node.
Connections: source ID/output index and destination ID/input index. VOP port identities are captured and validated, never guessed.
Actions: slot schemas, exact field bindings, required evidence, effect scope and permission category.
No executable placeholders  Missing subgraphs, unresolved type aliases and empty required material definitions reject publication. The blueprint supplies a contract, not a pretend runnable graph.

## Page 05

Capture artist truth, then reconstruct it
A hand-built golden scene is the behavioral reference. It is not automatically a portable recipe. Extraction succeeds only when the captured specification rebuilds the relevant behavior in a fresh scene.
Capture protocol
Select the owned scope. Record the outer graph, all nested MaterialX networks, binding targets, render branch and declared dependencies. Preserve the source HIP.
Record meaningful state. Capture nondefault authored values, expressions and explicitly pinned defaults that affect behavior. “Different from default” alone is not proof of artistic intent.
Close dependencies. Inventory textures, HDAs, USD references and resolver context. Record asset versions/content digests; do not package outside assets or absolute machine paths implicitly.
Pin compatibility. Verify exact LOP/VOP types and parameter interfaces against the running build and required plugins. A catalog entry proves availability, not correct wiring or behavior.
Rebuild and compare. Recreate in an empty test scene, compare normalized graph/state, evaluate USD predicates and run the approved render test.
Canonicalization is part of the contract
Separate semantic identity from layout. The semantic graph digest includes node types, parents, ports, parameters, expressions and flags; a layout digest covers positions. Stage canonicalization records its version, frame/time, load rules, relevant layers and resolver/dependency identity. Normalize only known volatile identifiers and approved path tokens; never erase meaningful differences to force matching.
Use exact equality for deterministic authored state after documented normalization. Use declared tolerances for render comparisons; stochastic pixels are not expected to be byte-identical.
Smallest useful extractor  Support this selected network and its MaterialX subgraphs first. A general-purpose Houdini-to-recipe exporter is outside the demo scope.

## Page 06

Put authority on the path that executes
The reviewed main panel runs through SynapsePanel → ClaudeWorker → tool executor. The demo restriction must apply to both tool advertisement and final dispatch. Hiding a tool description is not authorization. [S1, S2]
Proposed interface — not implemented
run_recipe(recipe_id, action_id, instance_id,
           slots, expected_revision, request_id)
The model can provide declared IDs and slot values. Trusted code resolves types, parameter targets and required permissions. Node paths, arbitrary code, output roots and consent flags are not model-selected capabilities.
A restrictive demo mode
Advertise registered read tools and the recipe proposal interface. Deny generic builders, assemble-all, arbitrary setters and code execution at dispatch.
Evaluate the selected action’s effective permission. A recipe wrapper must retain the render/export review or approval requirement; it cannot relabel a gated effect as an ordinary build.
For render, prepare the plan and let the existing trusted confirmation/native UI authorize that exact scope. Bind authorization to instance revision, engine, resolution, samples and output destination. Recheck it immediately before starting.
Unknown tools/actions and profile conflicts fail closed. Demo mode cannot silently fall through to an unrestricted environment setting or a legacy writer.
Intent and slot validation
Validate every requested slot: key, type, finite numeric value, bounds and enum. Use typed bindings, not Python-string interpolation. In this release, exact phrases map deterministically to actions; unfamiliar requests clarify or refuse before reaching a writer.
Hard stop; no extra authority  A terminal action ends mutation for that turn. No follow-on tool writes. A new change needs a new request. Recipe execution never grants blanket permission to render, export or delete.

## Page 07

A build is a transaction; a render is a job
Do not hold a graph transaction open around a potentially slow render. A correct stage can remain useful when rendering fails. Failure recovery should restore only what this run changed, not erase valid artist work.
Build and edit lifecycle
Preflight outside mutation; then acquire exclusive ownership of the instance mutation window. Re-read the expected revision and required dependencies immediately before writing.
Record pre-state and open one verified undo group. Apply only the prepared operation set. Re-observe nodes and USD; commit a receipt once the mutation is terminal.
On a confirmed mutation failure, roll back only this transaction, once. Compare against pre-state. Invoke global performUndo only when this transaction is provably the latest undo item and no unrelated edit intervened.
If recovery is uncertain, stop new writes and show residual changes. A UI timeout does not mean a main-thread task stopped; never race an in-flight operation with undo or retry.
Idempotence without resetting the artist
BUILD on an unchanged owned instance is a measured no-op. If its authored state has diverged from the last committed instance, return STALE/CONFLICT and preserve it. Do not silently reapply defaults, replace same-named artist nodes, or repair unrelated wires. An approved LIGHT or MATERIAL action updates the instance’s committed state so the next action remains valid.
Render lifecycle
After explicit approval, use the existing bounded render path with a run-specific output location. Track cancellation/termination, logs and file identity. A render failure does not automatically undo BUILD. Restore temporary render overrides through a separate bounded operation, or report remaining changes. Generated files are external effects; Ctrl+Z is not their rollback.
Recovery verdict  Record NOT_NEEDED, RESTORED, RESIDUE or UNKNOWN separately from the operation result. A clean rollback is still a failed build, not a successful scene.

## Page 08

Define proof by operation
“Done” is operation-specific. BUILD does not claim pixels. RENDER requires fresh stage readiness and image evidence. No required predicate is skipped into a green result.
Check
Evidence
Required for
P1 · Graph
Owned IDs/types/parents, nested shaders, ports, flags and bound parameter values.
Build; edit scope
P2 · USD
Live stage; active/defined expected prims; schema/type, material resolution and intended bindings.
Build; edits; render
P3 · Render readiness
Named RenderSettings camera relationship, valid Camera, products/vars/output, two authored lights and explicit render-input branch.
Render; golden qualification
P4 · Composition
Composition errors and relevant node errors; missing assets/load state checked separately.
Build; edits; render
P5 · Image smoke
Terminal job, fresh output file, expected dimensions/channels, readable finite RGB and expected visible content.
Render
P6 · Locality/recovery
Allowed field delta, preservation of unrelated artist state, measured rollback when needed.
Build; edits; failures

Important USD details
Resolve the intended RenderSettings prim explicitly; do not inspect whichever happens to be first. Read its camera as a relationship using UsdRender.Settings.GetCameraRel(), not winning_layer(), which is an attribute helper. Extend the existing stage assessor rather than duplicate its checks. [S7]
A tiny render is a smoke test, not a beauty verdict
Start qualification at 64×64 and one sample, then measure whether that is sufficient on the pinned scene/engine. Non-black alone can pass a wrong picture. Check the expected hero/ground region or a reference-derived coverage/color criterion with documented tolerances. Include fresh-file identity so a prior EXR cannot pass. Thirty seconds is a candidate budget, not a measured guarantee.
B-7 motivates checking the KRS-to-render branch as well as camera binding. Its recorded cause is evidence from that case, not a universal explanation of black renders. [S6]

## Page 09

The card observes; it does not certify itself
The registry defines the offer. The receipt records the run. Freshness determines whether that receipt still applies to this scene.
Dimension
Values
Meaning
Availability
READY / BLOCKED / EXPERIMENTAL
Compatibility and qualification of the recipe definition.
Operation state
PENDING / RUNNING / AWAITING_APPROVAL / TERMINAL
What is happening now; not a correctness verdict.
Terminal verdict
VERIFIED / REFUSED / BROKEN / UNKNOWN / CANCELLED
What this completed attempt demonstrated.
Evidence freshness
CURRENT / STALE / UNKNOWN
Whether past evidence still describes this scene.

One receipt, sufficient context
Record run/request IDs; recipe/action and instance revisions; code, build, engine and dependency identity; validated slots; trusted approval; timestamps; check results/reasons; pre/post fingerprints; render-job evidence; recovery outcome.
Invalidation
Scene load, undo/redo, relevant edits and dependency changes invalidate affected evidence. Recheck before each action; cheap periodic checks may supplement events. Do not hash the full stage every UI frame. Incomplete change tracking means UNKNOWN freshness.
Cache the plan, not the outcome
Cache compiled specs by digest, never live verdicts. A new request re-observes the scene. Deduplicate transport retries by request_id and job state: a lost response must not start a second render.
Minimum card  Recipe/action and scope; graph/USD/render evidence; freshness; approval/recovery; one reason and next action. Keep blocked cards visible with reasons. Unavailable is not nonexistent.

## Page 10

GATE / CAPABILITY / BENCH
Keep the vocabulary, but do not confuse a target gate with a measured status. All new v3 acceptance rows begin NOT_RUN. Only evidence produced by the bound code and host can promote them.
GATE — conditions required to ship the path
Gate
Goalpost
G0 · Real entry path
Panel phrase → action → dispatch → owned node provenance.
G1 · Compatible recipe
Build/catalog/dependencies agree; reconstructed golden graph passes.
G2 · Authority
Generic writers denied; render approval retained at final dispatch.
G3 · Local change
Artist state preserved; conflicts refuse; rollback/cancel measured.
G4 · Current evidence
Graph + USD + approved render proof; cache and stale-file controls pass.
G5 · Honest surface
Registry/card parity; blocked reason; stale evidence visibly invalidated.
G6 · Artist walk
Two owner rehearsals for demo; separate external-artist beta test.

CAPABILITY — build only what serves those gates
C1: targeted golden capture and schema extension; C2: one registry/instance adapter over BLOCKS.
C3: constrained dispatch, action-specific approval and terminal job tracking; C4: scoped graph/USD/image verification.
C5: current-scene receipts and minimal card; C6: one repeatable acceptance command using existing test infrastructure.
BENCH — measurements, not magic constants
Measure build-to-stage latency, render cold/warm latency, peak memory/VRAM, cancellation time and fifteen-minute walk completion. Pin frame, seed, engine and asset set. Report distributions across repeats where possible. Do not infer render success from cook duration or claim a latency/VRAM target was met without measurement.

## Page 11

Test the ways it can lie
Positive tests prove one path works. Negative controls prove a check notices the failure it claims to detect. Every claimed wall needs at least one deliberate attempt to cross it.
Test
Expected observation
T1 · Golden rebuild, twice
Same canonical semantic state; second apply is observed no-op.
T2 · Changed artist state
Rebuild refuses conflict; unrelated node and authored opinion survive.
T3 · Blue → red; key exposure
Only allowlisted shader/light fields change; bindings/topology stable.
T4 · Add fog / trailing clause
Full request rejected or clarified before any mutation dispatch.
T5 · Direct generic tool call
Dispatch denies it even when advertisement/filter is bypassed.
T6 · Render without approval
No render/export starts; wrapper cannot authorize itself.
T7 · Broken render branch
Topology check fails; camera binding alone cannot pass readiness.
T8 · Old EXR / wrong image
Fresh-file and scene-content checks reject stale or irrelevant pixels.
T9 · Stage unavailable
UNKNOWN, no success fallback; diagnosis retained.
T10 · Failure / timeout / cancel
Terminal state established before rollback/retry; residue measured.
T11 · Reset then repeat prompt
New request rebuilds; lost-response retry does not duplicate effects.
T12 · Undo, reload, dependency edit
Card evidence goes stale/unknown; reapproval when scope changes.

Bind each test to the actual imported checkout, not only PYTHONPATH. Record commit, loaded module path, Houdini build, runner command, logs and artifact hashes. Pure-Python tests cover schema/policy/matching; hython covers graph/USD; GUI covers undo, panel freshness and the artist walk. [S6]
Pass rule  A test that was skipped, could not access its host, or did not exercise the intended path is NOT_RUN/UNKNOWN. It is never counted as a product pass.

## Page 12

Sequence by exit condition
Keep September 13 as the target, not a promise that compresses missing work. Use the next observable exit condition to decide what happens today.
Window
Work
Exit evidence
Sep 4–5
Pin entry path. Joe builds the golden scene. Capture only that scope.
Saved HIP + scene/reference render + dependency record.
Sep 5–6
Rebuild from captured spec; graph/USD checks; local edits and undo.
T1–T3 and failure recovery on H22.0.400.
Sep 7
Demo dispatch fence; render approval; request/job identity.
T4–T7 and cancellation/retry controls.
Sep 8
Minimal card; freshness; image smoke; no stale-result cache.
T8–T12 and panel parity.
Sep 9
Two full owner rehearsals with reset between them.
Two recorded takes; pinned path has current evidence.
Sep 10–11
Fix observed failures; invite a separate cold-walk tester if available.
Rerun touched controls; beta result reported separately.
Sep 12–13
Freeze, dry run, record and ship. No new feature branch.
Pinned build/spec/profile; usable capture and recovery plan.

Stop rules
No agent wave before the golden scene reconstructs. A later panel-only leg/review may be commissioned, but this document authorizes no delegation or repository changes.
If the base path slips, cut features—not consent, freshness or failure reporting. World ingest stays post-demo.
If a safety/correctness gate remains open, show a labeled prerecorded result or postpone the live segment. Never relabel a partial run as completed.
First session  Open H22.0.400. Build and save the exact sphere/ground scene by hand. Verify both materials, both lights, camera, render branch and one image. That is the next concrete artifact—not another general framework.

## Page 13

Evidence ledger — pinned, not evergreen
Repository findings below are anchored to the earlier inspection at commit 2b9f9e0 (v5.62.0), not a new live-runtime qualification. Links resolve to that exact commit. Proposed fields, tools and gates elsewhere in this document are v3 design, not existing features.
S1  Actual panel path. _start_worker constructs ClaudeWorker with worker-policy enforcement enabled.
python/synapse/panel/synapse_panel.py
S2  Worker policy. Standard mode permits generic Solaris composite builders; a demo restriction must be stricter.
python/synapse/panel/worker_policy.py
S3  Fixture foundation. Existing owned-scope reconciliation; reuse does not establish new subgraph or rollback guarantees.
python/synapse/blocks/runtime.py
S4  Solaris DAG handler. Explicit connection validation and rollback attempts; no automatic proof of transactional safety.
python/synapse/server/handlers_solaris_graph.py
S5  H22.0.400 type catalog. 222 entries in the prior review; plane present, grid absent, deprecated render aliases identified.
rag/catalog/h22.0.400/Lop.json
S6  B-7 CRUX receipt. Recorded negative controls challenge the camera/light-only story and identify the render-input topology change.
harness/notes/receipts/BP4-CRUX.json
S7  Stage assessment. Existing camera relationship and stage assessment logic to extend.
python/synapse/server/solaris_compose_tools.py
S8  Planner and cache behavior. Planner acceptance stops the cascade; response-cache handling needs current-scene safeguards.
python/synapse/routing/router.py
Additional starting points: routing/planner.py; blocks/fixtures.py; fixtures/solaris.basic.json; server/handlers.py; server/foreground_guard.py. Earlier source: SOLARIS_RECIPES_H22_BLUEPRINT_V2.md, created September 4, 2026.
Governance gap  The earlier review found references to BETA_DONE.md but not that file in the pinned public tree. Treat the fifteen-minute external-artist walk as Joe’s supplied requirement until its authoritative artifact is resolved. Do not claim all beta obligations are satisfied from one walk.

## Page 14

What changed from v2
v2 tension
v3 resolution
One “done” test mixed build, render and rollback.
Action-specific predicates; recovery reported separately.
Recipe wrapper could hide render/export permission.
Effective permissions preserved and approved at dispatch.
Repeatability could reset the artist’s edits.
Instance revision and conflict refusal; committed slots evolve.
One object mixed capability with scene truth.
RecipeSpec, RecipeInstance and immutable RunReceipt.
Illustrative graph looked almost executable.
Contract-only schema; captured ports/subgraphs required before publication.
Empty/stale output could resemble a passing smoke test.
Fresh output identity and reference-derived content checks.
Timeout implied rollback was safe to start.
Establish terminal mutation state before recovery/retry.
Spatial work could return late in the schedule.
Post-demo by default; reopening is an explicit scope decision.

Ratify these four decisions
Scope: one golden topology and one qualified engine; bounded color/exposure edits; world ingest deferred.
Architecture: fixture-backed recipe specification, BLOCKS-owned instance, one constrained action path and independent verifiers.
Authority: preserve existing approval, native artist control and unrelated scene state. No arbitrary repair.
Claims: two owner takes qualify a demo; an external artist tests the cold path; neither equals general Solaris intelligence.
Public claim, after qualification  SYNAPSE turns a supported request into a tested Solaris build, makes bounded edits, asks for required render approval, and reports evidence from the current scene.
This refactor changes the engineering plan and its acceptance criteria. It does not modify the repository, install a runner, execute Houdini, or certify the September 13 build.
