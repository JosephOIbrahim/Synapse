# Local work notifications — milestone 5

Joe approved the ordered UX roadmap and continuing milestone by milestone,
including Houdini 22.0.400 testing. This design implements the notifications
portion of that scope. Source starts at the reviewed routing checkpoint 8fd3b9f1.

## Experience

An Events button opens a nonmodal local activity center. It shows observed job
state, node/model identity, a short explanation and a deliberate next action.
Unread attention is visible without moving the artist's current tab. Starts and
ordinary progress stay quiet. Completion, failure and meaningful connection
changes can alert; repeated polls cannot create duplicate notices.

The center offers All / Needs attention, Mark read, Clear finished and Watch
selected. A quiet control suppresses attention alerts, not the underlying
history. Optional desktop messages default off, use the native Qt notification
facility only when available, and say unavailable when the host lacks it. No
remote service, email, webhook, model request or cloud data transmission is added.
Desktop text is generic: no scene, node, model, file path or error detail leaves
the Events view. Opted-in native alerts may remain in the operating system's
notification history after Houdini closes; process-only retention describes the
Events journal, not that separate OS history.

History is bounded, in this Houdini process only, and clearly labeled that way.
Closing the panel stops its explicit watches; the source still records its own
running jobs. Reopening may show retained entries but never replay desktop alerts.
No disk log or new USD/memory owner is created. Production memory remains local.

## Chosen approach

Use a small process-local event journal with producer adapters at existing job
authority boundaries, plus explicitly selected native watches. The panel reads
snapshots and performs only UI actions. This provides actual outcomes without
asking a language model to infer what happened.

Alternatives considered: polling output directories cannot prove completion and
can mistake old files for new work; a general external notification service adds
setup, privacy and service dependencies without improving local event truth.
Existing render_farm broadcast and TOP monitor records are not a sufficient
authority: the broadcast has no discovered production connection, and monitor
registration can fail while its return still says monitoring.

## State and identity

`synapse.job_events` is pure Python, thread-safe, bounded and in memory. Each job
has an opaque unique ID, a source, category, immutable source scene/context when
known, node identity when known, timestamps, state and short bounded detail.
Entry payloads are detached copies. No keys, prompts, arbitrary tool result
objects, exceptions with tracebacks, or model response bodies enter this journal.
Revision and event sequence numbers let each consumer detect changes and drops.
The .pypanel loader removes synapse.* modules on reopen. The journal therefore
has one versioned process anchor outside that reload namespace, shared by old
workers and the newly loaded panel. It retains no QWidget, host node or callback.
Retention has a hard cap, including running entries; overflow is counted and
surfaced as observation loss, never an execution failure or fabricated outcome.

States distinguish running, completed, failed, cancelled, preview and unknown.
Completion means the observed operation returned successfully; it does not claim
render/file/cache validation unless its source actually performed it. Unknown
or conflicting outcomes require attention, and late/duplicate terminal events
cannot resurrect a job or manufacture another successful completion.

Only explicit lifecycle boundaries create automatic job IDs. Node paths alone
are not identity: native watches bind session IDs and scene generation. New
scenes, node deletion/replacement, teardown, missing starts and callback loss
must invalidate or narrow observations. Watching is read-only: it cannot cook,
render, save a HIP, or create a graph context as a side effect.
Close and QObject-destruction paths disable watches before removing callbacks.
Cleanup is idempotent; queued callbacks and failed-unsubscribe callbacks become
inert. Any Inspect node action revalidates generation and session ID, never a
path-only lookup into a replacement node. Destructor-only and failed-unsubscribe
teardown are required checks.

Automatic render jobs and native callbacks share an ID only through an exact
association established before execution. Otherwise they remain distinctly
labeled source observations; no path/time-window guess silently merges jobs.
Observers cannot alter execution, return values, exceptions or cancellation.

## Producers

1. `server/render_session.py`: observe real start, completion and exception of
   the off-main bounded render. A completion dict with error/cancel/preview
   status must be normalized honestly. Calling an operation is not output proof.
2. `server/handlers_render.py`: a separate observation around the existing inline
   render call preserves its current no-render-session invariant and threading.
3. `server/render_notify.py`: the final BatchReport is a terminal report-only
   source; it does not claim to observe a running batch. Preserve report files
   and API/return keys. Incomplete counts cannot say all frames succeeded, even
   when a cancelled batch lacks a cancellation flag. Batch and persistent-failure
   notices join the same quiet/default-off alert policy. Internal producers stop
   sending unconditional legacy toasts; a single atomic journal claim prevents
   duplicate desktop messages across multiple panels. The standalone send_toast
   utility remains callable, but these producers no longer invoke it directly.
4. `host/job_watch.py`: attach only supported, live-scouted ROP/TOP/selected cache
   observation APIs. Exact native signatures and H22 evidence will be appended
   before implementation of those hooks. Arbitrary SOP cook/range monitoring is
   unsupported until a real completion authority is found. A generic PostRender
   or CookComplete is not by itself proof of success or output validity.
5. Panel connection facts: record accepted metadata checks as Model checked,
   with location and a reminder that generation has not been tested. Observe
   bridge running/stopped transitions from its existing local state. This does
   not claim remote client health or silently ping/send content to a model.

The integration must handle a panel opening after a job started, a job finishing
after panel closure, duplicate callbacks, repeated runs at the same path, failures
then completion, unknown source outcomes, cleared scene and disconnected source.

## Files and boundaries

- New `python/synapse/job_events.py`: bounded state journal and conservative
  result classification; no Qt/HOM, persistence or external I/O.
- New `python/synapse/host/job_watch.py`: native observation and cleanup on the
  main thread; inject/expose a small host seam for independent testing.
- New `python/synapse/panel/notifications.py`: activity center, preferences,
  unread/quiet policy and optional native desktop adapter; queued/main-thread UI.
- Modify the three producer files above. Existing execution remains the owner.
- Modify `panel/synapse_panel.py`, `command_palette.py`, `settings.py` and shared
  design QSS as needed for Events/commands and validated notification preferences.
  Preserve project-rule authority and existing setup/worker lifecycle semantics.
- Add focused event/observer/UI tests and concise artist-facing documentation.

## Verification

Existing baseline: 96 checks pass across bounded renders, render notifications,
TOP bridge, panel render receipts and TOP cook errors. Test new lifecycle state
transitions, duplicate/late/out-of-order events, partial batch results, exception
preservation, retention/drop visibility, detached payloads and cleanup. Mutate
terminal classification and duplicate protection and preserve the failing runs.

Independent review attacks the actual composed producer/journal path and native
UI. Native H22 tests must prove watches do not cook on registration, callbacks
belong to exact nodes/scenes, actual small synthetic success/failure events arrive,
and teardown/repeated runs do not leak callbacks or produce false success.
Use an isolated Houdini process for live panel qualification. No production
render, scene replacement or cloud request is needed. Run the full suite and
report existing failures separately, with hashes and raw evidence.

Completion requires implementation, relevant tests, independent review, bounded
live host qualification, local checkpoint and dashboard/bus receipt. Sustained
farm operation and all desktop/OS configurations remain unqualified unless tested.
Merge, deployment and release remain separate user-authorized acts.

## H22 observation appendix

Native producer scripts and raw outputs are under
`checks/notifications/native-observation/{api-01,passive-02,tiny-03,terminal-04}`
in the parent workspace. They ran in disposable hython 22.0.400, Python 3.13.10.

- `hou.nodeEventType` has no general SOP post-cook event; passive cookCount and
  needsToCook cannot establish a simulation range or cancellation. Unsupported
  SOPs explain that boundary and direct the artist to a cache ROP or TOP network.
- `hou.RopNode.addRenderEventCallback(callback, run_before_script=False)` and
  removal by callback identity are real. PreRender/PreFrame/PostFrame/PostWrite/
  PostRender exist; there are no error/cancel event members. Script failures still
  emitted PostRender with errors() populated. A null ROP emitted no callbacks.
  Thus ROP error facts report failed; a clean PostRender reports activity ended
  with outcome unknown, not validated range/output success. PostWrite may be
  described as an observed write, not proof of the requested complete cache.
- `filecache::2.0.node('render')` passively resolved its delayed RopNode definition
  without changing cookCount. The one-frame Save to Disk probe produced the native
  sequence and a 915-byte empty-geometry cache only under disposable evidence.
- PDG addEventHandler returns PyEventHandler and removeEventHandler accepts it.
  Passive registration/removal changed no cook counts and emitted no events.
  CookComplete occurred for success and failure without CookError or item-state
  events. `NodeCooked.event.node.workItems` provided actual CookedSuccess or
  CookedFail, while CookComplete.event.node was None. Callbacks can be off-main.
  The adapter collects bounded pure-PDG terminal states from NodeCooked and requires
  its matching start. Missing/pending/mixed or lost observations are unknown.
  Explicit CookedCancel may establish cancellation; cancel requests alone cannot.
- Session IDs survive rename and disappear on deletion; a replacement at the same
  path has a different ID. Focus actions revalidate these IDs plus scene generation.

The existing TopsEventBridge assumes event.workItem, but actual tested pdg.Event
has workItemId/currentState/lastState and no workItem. The new watcher uses only
the verified payload surface; it does not silently revive that unused bridge.
No source currently supplies an exact automatic-render/native-watch lease, so
those observations stay distinctly labeled and never override one another.
Actual Escape cancellation and arbitrary third-party node callbacks remain
unqualified. Adapter-specific teardown and composed panel checks still must run.
