# Dormant spatial and substrate interfaces

These additive interfaces do not activate a provider, install a substrate, change a memory owner or authorize a scene operation. They are separate from release and Houdini qualification.

## Existing integrations

`synapse.worldlabs.client.WorldLabsClient` remains the connection owner for the existing Marble v1 read/list/PLY-export path. The existing importer and panel remain unchanged. The neutral spatial path/trail tools retain their existing registration; the three import-only spatial queries retain their existing status.

The observational LOOP already uses StagePort, LedgerPort, PortResult and LoopCoordinator for composition, a narrow forecast, settlement and feedback delivery. Its fixed Boolean handler observation is not a six-component RC+ξ gate. See [the existing LOOP documentation](MEMORY_LOOP_REPAIR.md).

## Atlas data boundary

`atlas_contracts.py` provides typed camera, posed-frame, asset, operation and provenance records. Camera intrinsics are pixel quantities; poses are camera-to-world with XYZW quaternions and explicit RUB/RDF axes. Successful bundles require unique ordered frame identities and one shared world frame; individual camera axes may differ. Metric unprojection requires an explicit positive scale. That scale is a synthetic caller assertion, not proof of calibration; unknown scale refuses metric output. Invalid source depths are masked, while nonfinite camera, rotation, translation or scaled output is rejected. Decoder row order is explicit instead of assuming that every EXR decoder behaves like Three.js. These choices follow the [camera guide](https://atlas-beta.worldlabs.ai/docs/cameras-and-posed-images).

`atlas.py` plans ordered synthetic pose requests and normalizes documented operation/camera fields from injected fixtures. Atlas v2 is kept distinct from the existing Marble v1 schema. A terminal result requires an explicit `done` value and exactly one response or error. See [operation semantics](https://atlas-beta.worldlabs.ai/docs/operations) and [the pose task](https://atlas-beta.worldlabs.ai/docs/images-to-posed-images).

Live submit, upload, resume and asset-read methods always raise `AtlasNotEnabled`. No HTTP executor, CLI dependency, auth probe or provider registration is added. Setting `SYNAPSE_ATLAS_LANE` does not activate this module or register tools. Proposed Atlas status/pose tools remain absent from dispatch. An existing connection does not establish beta task entitlement; that is distinct from credential validity in the [authentication documentation](https://atlas-beta.worldlabs.ai/docs/authentication).

The only runnable transport is explicit in-memory SYNTHETIC data. `SyntheticFixtureBinding` is created with the fixture, before parsing. It records the original request hash, ordered source frame identities, ordered output asset identities/content hashes, operation identity and shared world frame separately from the provider-shaped dictionary. Pending and terminal results must match that binding. Plain provider dictionaries are refused; the parser never manufactures a source request identity from the newly supplied plan. This is not an authenticated boundary against malicious Python fixture authors. A future live implementation needs a trusted persisted request-record owner, not an invented provider wire field.

Fixture asset hashes identify synthetic test tokens, not validated PNG/EXR files. The scaffold does not decode real media. Provenance contains ordered content hashes, frame identities, schema, task, API family and evidence tier, plus a canonical digest of all sanitized typed output frames. That digest covers camera intrinsics/pose/world frame, depth encoding, decoder rows and caller-asserted or unknown scale as well as asset references. It carries neither URLs nor credentials. Request binding establishes consistency, never owner approval. Real media dimensions, resource/magnitude limits and scale-calibration evidence remain prerequisites for any future activation.

## Substrate and future RC+ξ boundary

`rcxi_ports.py` borrows explicitly supplied existing ports through typing protocols. It neither constructs handles nor creates an outbox. An unconfigured adapter reports UNAVAILABLE; this is not an assertion that its substrate is absent from the host.

The borrowed result must have a recognized string status, a dictionary-or-absent payload, and a nonempty reason for every non-success. SUCCESS cannot carry an error and needs the operation-specific minimum shape: composition context; forecast digest or existing local sequence; settlement state and outcome. Invalid envelopes are BLOCKED, whereas an adapter execution exception is UNAVAILABLE. Existing non-success diagnostic dictionaries are preserved. Typed payload shapes do not establish that composition, durable authorship or settlement really occurred; the existing port remains the owner of that evidence.

SixMetrics and TelemetryObservation define a finite, identity-bound observation shape. Missing or mismatched observations cannot become success. Successful observation is data only and explicitly carries `authorizes_action: false`. The evaluator remains UNAVAILABLE: this scaffold implements no covariance calibration, tension decision, fuel enforcement, convergence seal or rollback. A real bounded gate must supply and test those mechanisms separately.

Tests use deterministic synthetic cameras and a hand-computed plane, exercise pending/success/error separation and disabled behavior, and demonstrate red failures when order or request binding is broken. None of these checks claims live Atlas, substrate installation or interactive Houdini acceptance.
