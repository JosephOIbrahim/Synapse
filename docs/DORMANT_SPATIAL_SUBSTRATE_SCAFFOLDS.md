# Dormant spatial and substrate interfaces

These additive interfaces do not activate a provider, install a substrate, change a memory owner or authorize a scene operation. They are separate from release and Houdini qualification.

## Existing integrations

`synapse.worldlabs.client.AtlasClient` (alias `WorldLabsClient`) is the connection owner: a read-only Atlas v2 client that lists and reads finished operations and downloads their SPZ splats. It cannot start a task. The Marble v1 path and the dormant `atlas.py` executor scaffold were removed on 2026-11-22, when World Labs became Atlas-only. See [World Labs import](architecture/overview.md#world-labs-import). The neutral spatial path/trail tools retain their existing registration; the three import-only spatial queries retain their existing status.

The observational LOOP already uses StagePort, LedgerPort, PortResult and LoopCoordinator for composition, a narrow forecast, settlement and feedback delivery. Its fixed Boolean handler observation is not a six-component RC+ξ gate. See [the existing LOOP documentation](MEMORY_LOOP_REPAIR.md).

## Atlas data boundary

`atlas_contracts.py` provides typed camera, posed-frame, asset, operation and provenance records. Camera intrinsics are pixel quantities; poses are camera-to-world with XYZW quaternions and explicit RUB/RDF axes. Successful bundles require unique ordered frame identities and one shared world frame; individual camera axes may differ. Metric unprojection requires an explicit positive scale. That scale is a synthetic caller assertion, not proof of calibration; unknown scale refuses metric output. Invalid source depths are masked, while nonfinite camera, rotation, translation or scaled output is rejected. Decoder row order is explicit instead of assuming that every EXR decoder behaves like Three.js. These choices follow the [camera guide](https://atlas-beta.worldlabs.ai/docs/cameras-and-posed-images).

The executor scaffold that sat beside these contracts (`atlas.py`: synthetic pose planning, fixture binding, a disabled adapter) was retired on 2026-11-22. The contracts stay because the HD1 physical-frame track builds on them; their tests are in `tests/test_atlas_contracts.py`.

## Substrate and future RC+ξ boundary

`rcxi_ports.py` borrows explicitly supplied existing ports through typing protocols. It neither constructs handles nor creates an outbox. An unconfigured adapter reports UNAVAILABLE; this is not an assertion that its substrate is absent from the host.

The borrowed result must have a recognized string status, a dictionary-or-absent payload, and a nonempty reason for every non-success. SUCCESS cannot carry an error and needs the operation-specific minimum shape: composition context; forecast digest or existing local sequence; settlement state and outcome. Invalid envelopes are BLOCKED, whereas an adapter execution exception is UNAVAILABLE. Existing non-success diagnostic dictionaries are preserved. Typed payload shapes do not establish that composition, durable authorship or settlement really occurred; the existing port remains the owner of that evidence.

SixMetrics and TelemetryObservation define a finite, identity-bound observation shape. Missing or mismatched observations cannot become success. Successful observation is data only and explicitly carries `authorizes_action: false`. The evaluator remains UNAVAILABLE: this scaffold implements no covariance calibration, tension decision, fuel enforcement, convergence seal or rollback. A real bounded gate must supply and test those mechanisms separately.

Tests use deterministic synthetic cameras and a hand-computed plane. None of these checks claims live Atlas, substrate installation or interactive Houdini acceptance.
