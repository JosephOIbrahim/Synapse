# Observational memory LOOP

This repair connects the existing Moneta owner, a private Octavius context stage,
and Hanish forecast/evidence/settlement. It implements the observational first
slice of the temporal-cognition direction. It does not ratify a new architecture
or claim that multi-agent planning, predictive modeling, SALUS or recursive policy
improvement is complete.

The artist's existing action path and consent remain authoritative. Memory is
advisory. No remembered result automatically changes a network, a control, a
recipe, or the next action. A reference note is not a checked procedure.

## Data flow

1. On an artist-requested context lookup or eligible operation, the host borrows
   its existing Moneta owner on the main thread. A mismatched scene address or
   busy/unhealthy owner produces an explicit unavailable result.
2. Relation-filtered prior records provide bounded advisory context. Only named
   structural fields and recall identifiers enter an anonymous Octavius stage.
   SYNAPSE performs the allowlisting; Octavius performs composition. No production
   USD layer or arbitrary metadata enters that private stage. Agent formation
   and coordination ticks are not run in this slice.
3. Before dispatch, Hanish durably records a fixed 0.5 EXPOSED forecast of the
   narrow observable `synapse.handler_terminal_ok.v1`. SYNAPSE checks the persisted
   forecast digest and records the acknowledgement before yielding to the action.
4. The existing handler or panel bridge executes the requested operation. Hanish
   receives one immutable terminal observation for that attempt. Pending work,
   transport uncertainty and timeouts stay unknown; missing evidence is never
   converted to a failure. The 10-minute observation horizon is not an action
   timeout and never kills a host operation.
5. A Hanish outcome becomes an immutable, protected Moneta feedback capsule with
   its forecast digest, attempt identity, recall references and explicit limits.
   It can be recalled in a subsequent request. Hanish remains the outcome source;
   memory is not the evidence ledger.

## Recovery and ownership

Each project stores attempts and pending delivery pointers below `.synapse/loop`.
Every accepted transition is flushed and fsynced. The outbox retries delivery,
not the scene action. A stable memory identity gives exactly-once logical effect
after a lost acknowledgement or failed memory checkpoint. Recovery examines at
most four pending attempts on an explicit context request.

Recovery may reconcile a forecast that was already written when its ACK was
lost. It never creates a forecast after dispatch. An action that had no durable
forecast remains uninstrumented, with its pending history retained for diagnosis;
installing a substrate later cannot turn that history into a pre-action forecast.

The host owns memory handles. Ports borrow project/ledger owners without caching
or closing them. Workers carry JSON data only. Hanish and Octavius run as bounded
local subprocesses; neither imports the other or Moneta. Their work stays outside
Houdini's UI thread. Direct main-thread handler calls report uninstrumented rather
than waiting for a sidecar. The panel's worker brackets its existing main-thread
bridge call, so its regular mutation path can be observed without this extra UI
wait. Existing scene cook/render time still belongs to the original host action.

The explicit `rebind_project_memory` helper preserves and checks records before
publishing a replacement owner. It can carry an untitled scene's memory into its
first saved project. It never silently copies memory between unrelated projects.
Later scene-location mismatches refuse LOOP recall until the host is rebound.

## Configuration

Configuration is explicit and machine-local. No package is installed implicitly:

| Variable | Meaning |
|---|---|
| `SYNAPSE_LOOP_ENABLED=1` | Enable observational capture and requested LOOP context |
| `SYNAPSE_LOOP_PYTHON` | Absolute path to the matching Houdini USD Python executable |
| `SYNAPSE_HANISH_ROOT` | Qualified Hanish source root containing `hanish/` |
| `SYNAPSE_OCTAVIUS_ROOT` | Qualified Octavius root containing its current `src/stage/` API |

Missing or incompatible sources report unavailable. The worker uses isolated
Python so Octavius's generic `src` package cannot collide inside Houdini. Set the
enable flag to `0` to disengage. This flag does not grant scene-operation consent.
SALUS remains unavailable and must not be represented as allowing a path.

## Solaris reference intake

`docs/knowledge/rob_pieke_h22_solaris.json` contains eight reviewed reference notes
from the artist-supplied Rob Pieke transcript. `memory.source_knowledge` verifies
the source SHA-256 and exact excerpts before depositing notes through the borrowed
memory port. Repeating an intake does not duplicate notes. A changed source fails
validation. The notes preserve timestamps, artist choices and `LECTURE_CLAIM`
status; no node graph is executed and no model is trained by ingestion.

Example artist requests: “Recall Rob Pieke's Follow Parent Context workflow,”
“Explain the difference between Hydra and Husk procedurals,” or “Show the render
pass/settings/product relationship.” Runtime parameter names and resulting images
still require inspection and testing on the artist's running Houdini build.

## Qualification boundaries

Tests cover real-substrate composition, forecast-before-dispatch, HIT/MISS/unknown,
lost ACKs, failed delivery, reopen, a second action consuming recall, source hash
changes, owner borrowing and explicit scene rebind. The Hanish version qualified
here resolves captured event order; the adapter therefore supplies exactly one
terminal event per attempt and rejects conflicting retries. No generalized
out-of-order event guarantee or calibration benefit is claimed.
