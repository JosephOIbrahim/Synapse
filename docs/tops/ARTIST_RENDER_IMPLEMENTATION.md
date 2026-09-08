# Artist render workspace implementation

The 7 September 2026 renderfarm blueprint guided this first implementation: rendering directly accessible in SYNAPSE with an executable, durable local TOPs path. The [8 September refactored blueprint](TRIAGE_FARM_BLUEPRINT.md) proposes the next comparison, final-render and remote-farm milestones while preserving the qualification recorded here.

## Artist experience

Open **Render** beside the existing local controls, through Commands, or with `/render`. This opens one modeless view and preserves the conversation draft. The view works while a model task is running and when no model is connected.

Select a saved Solaris output, frames and destination. **Prepare render** captures the exact request and prepares a separate render package in a headless Houdini process. Once the package is ready, **Render N frames** submits that prepared revision. A changed form needs a new preparation. Recent jobs remain visible after reopening. Cancelling is a request until execution confirms it stopped. Only verified outputs can be opened.

Ordinary rendering exposes the creative choices first. Detailed resolution, samples and farm configuration are secondary. Connection loss leaves the request visible and offers status recovery; it must never invite a blind duplicate submission.

## Execution boundaries

SYNAPSE owns request identity, durable records and presentation. TOPs owns the dependency graph. An isolated native Houdini process prepares and executes the local graph. HQueue is the intended remote scheduler; an absent or unqualified farm remains explicitly unavailable.

Preparation and submission are separate operations. The durable request is recorded before external work begins. All Houdini calls in the artist host use its main-thread dispatcher; dependency work, image decoding, polling and native graph execution stay outside the artist GUI.

The initial source is a saved HIP and an explicit Solaris output node. Unsaved changes are surfaced before preparation. No implementation action changes the artist's open scene. Render snapshots and output attempts have their own directories. Existing public render and TOPs tools retain compatibility.

## Exclusive implementation ownership

| Owner | Files |
| --- | --- |
| Core agent | `farm/models.py`, `store.py`, `service.py`, `verification.py`, package initializer and core tests |
| Native agent | `farm/backend.py`, `native_driver.py`, `package.py`, backend tests and disposable H22 probes |
| Artist flow agent | `panel/render_workspace.py`, `render_presenter.py` and dedicated tests |
| Root | Handler facade, canonical registry, tool group, protocol, role/gate/transport classification, panel entry points and composed verification |

## Shared interface

`FarmService(root, backend)` exposes capabilities, prepare, submit, list_jobs, get_job, refresh and cancel. Every job is a plain record with request ID, canonical digest, immutable plan, state, note, backend ID, verified frame keys and output records.

The native adapter provides capabilities, prepare, submit, poll and cancel. Preparation and submission return quickly after handing work to the owned process. Durable native receipts supply later observations. A completed task graph is insufficient: acceptance requires every expected frame and output, full image decoding and stable file identity.

## Completion evidence

- Meaningful pure tests for restart, duplicate intent, lost acknowledgement, source/digest changes, exact frames, failed validation and cancellation races.
- Native Houdini 22.0.400 parameter/API evidence and bounded renders using a disposable fixture.
- Genuine offscreen Qt interaction, narrow layout and text-size checks.
- Existing TOPs/render compatibility and the composed stock-Python suite, with baseline failures identified separately.
- An independent review of the integrated result before a deployment or release request.

Measured native results include a one-frame render, a twelve-frame animated render and an exact sparse frame set of 1, 3 and 5. The sparse run used the real journal and native backend, changed the disposable original HIP after preparation, then recreated the service with a deliberately lost submission acknowledgement. It recovered the existing render and verified all three outputs from the prepared revision. These are local 256-by-256, eight-sample Karma CPU results on Houdini 22.0.400.

Native cancellation was exercised after the first image appeared. The supervisor confirmed that its owned Windows process group had zero active processes and that retained process handles had signaled before publishing cancellation. Package texture tampering and pre-existing foreign output were refused. Closing the actual artist's Houdini application during a render was not exercised; new-service recovery and dialog close/destruction were tested separately.

The per-job thread and task limits do not impose a machine-wide queue or license budget across separate submissions. Add that resource admission layer before treating this local preview as a production farm controller.

## Current constraints

The source baseline is v5.67.1 at `87ce354a1aa04722fbfd2a8d308fb5eeb194455b`. The project chats establish one editable Solaris/Copernicus look, preserved artist changes and quiet, clear local controls as priorities.

TRIAGE FARM was located on 8 September in the separate `G:/KARMA_TRIAGE_FARM` project, loaded by `houdini22.0/python_panels/tops_farm.pypanel`. Its cheap-preview and look-review concept informs the new design; its code, panel and design are not a migration target. The [concept reference](TRIAGE_FARM_MIGRATION.md) retains the source findings. The [refactored blueprint](TRIAGE_FARM_BLUEPRINT.md) now brings a small local comparison and selected same-frame final into the plan after shared admission. The remote qualification requirements below remain necessary before enabling the farm.

Actual remote worker inventory, shared storage, service identities and concurrent licenses remain to be established. Local native qualification does not establish a two-machine farm. The current handlers explicitly refuse shared studio deployment because the existing shared transport key does not establish per-user job ownership. Deployment, release/version changes and live artist-session actions remain separate acts after implementation evidence is ready.

## Remote qualification requirements

Keep the artist's Prepare, Render, Recent renders and Cancel flow. Add a farm profile behind that same interface only when it can prove these conditions:

1. Two named workers and an HQueue controller use the qualified Houdini build, renderer and service identities. Set per-machine CPU, memory and renderer-slot budgets across jobs. Record actual simultaneous license checkout results.
2. The controller and both worker accounts can read the sealed scene, USD, textures and configuration and write their owned output attempts through the same shared storage paths. Keep the SQLite journal on controller-local disk.
3. The HQueue adapter durably binds the reviewed digest to the returned scheduler job identity. A disconnected submit recovers that identity or reports uncertainty; it never submits again to discover what happened.
4. A sparse animated frame set runs across both workers. Verify native task identity, complete decoded images and current output hashes before declaring success. Match the same scene against a local reference.
5. Stop a worker, interrupt the controller connection, exhaust a license and cancel during execution. Each outcome must remain observable and recoverable without duplicate work, unrelated process termination or false completion.
6. Add authenticated user/job ownership before enabling studio access. Verify that one artist cannot change or cancel another artist's jobs without the intended role.

Farm setup belongs in a separate configuration view. An artist choosing Render farm should see its availability and a useful reason when unavailable; controller addresses, account setup and license diagnostics should stay out of the normal render decision.
