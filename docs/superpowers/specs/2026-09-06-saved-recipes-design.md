# Saved network recipes — milestone 3

Joe approved continuation through the roadmap milestone by milestone. This
milestone adds an artist-facing local library without changing the curated
RecipeSpec, BLOCKS, or memory-substrate authorities.

## Experience

A visible Recipes button opens a searchable library. Select sibling Solaris
nodes, enter a name, tags and optional notes, and Save selection. A recipe has
immutable numbered versions. Save new version explicitly targets a chosen
recipe; matching a name never silently overwrites another recipe.

Each version carries a native Houdini network clip and a USD metadata layer.
Intervening network dots travel with the selected nodes. Immediate item ports,
dot positions and pin state are read back, including nested dots and detached
external inputs. A section box travels only if every direct member belongs to
the selection or its required dots; other items are never pulled in by a box.
The metadata records the source build, scene, nodes, actual connections, clip
hash, and external dependencies. The library is local to this workstation;
capture, search and restore do not call a model or a cloud service. The location
is shown in the UI. These are saved networks, not independently render-qualified
curated recipes, and the UI must preserve that distinction.

Insert a copy creates a new empty Solaris subnet. It must not reuse, rearrange,
or change existing nodes or their display flag. Restoration verifies the clip
and build, reports missing types/dependencies, and reads back the imported graph.
External dependencies are listed and require explicit acknowledgement before
insertion; assets are not embedded or silently fetched. No cook, render, or
simulation is requested. Node loading itself may invoke normal Houdini behavior.
Acknowledgement covers the listed authored state, including explicitly UNRESOLVED
expressions. It never upgrades unknown dependency closure to verified portability
or render readiness. Inability to read an authored field, known missing fixed
files, missing types, build mismatch and corrupt packages refuse insertion.
Captured procedural references can remain unresolved without being evaluated.
Fixed source-context references are checked against the destination. Detached
external wires are described separately from unresolved expressions or file
references. A failed restore deletes only its
newly created subnet and verifies removal; residue is reported if cleanup fails.
Placement metadata must use canonical relative paths, finite coordinates and
owned items. Invalid metadata is refused before any scene mutation; failed
insertion restores and verifies the earlier root layout/display state.
An undo group is not claimed to be automatic rollback.

An explicit Keep selection at scene changes action arms only the named selected
nodes, with their session identities, name and tags. BeforeLoad/BeforeClear
captures a local revision before destruction; the pair is deduplicated. Closing
the panel also captures an armed selection and removes its callback. No modal
dialog runs in a scene-lifecycle callback. A nonmodal result states the source
scene and version or the actual failure. Deleted/replaced nodes fail visibly;
there is no path-only fallback to a different selection. New scenes disarm the
old watch. This is not crash recovery or a guarantee for process termination.
Each arm has a unique identity and records the original scene and node session
identities. Failure also disarms before any later callback can retry an uncertain
write. Both closeEvent and QObject destruction detach idempotently; a failed
unsubscribe leaves an inert callback and an observable error. Destruction never
calls a dead Qt widget. A local last-result receipt plus host status survives
panel closure; inability to persist the receipt is itself reported.
The observed capture scene is retained even after Save As; the originally armed
scene is a separate field. On receipt-write failure, a host-owned status and
process log remain available after the widget disappears. Permanent disk errors
still surface after bounded retries; the previous on-disk receipt is labeled as
a previous result when reopened.

## Alternatives and boundaries

Prompt recipes are easy to store but regenerate rather than restore authored
networks. A hand-built parameter serializer risks losing nested or animated
state. Native clips preserve Houdini's serialization and are the chosen format;
live round trips will establish the precise supported behavior. USD records
describe these local assets, without constructing a second Moneta/store owner.

The first implementation supports selected Solaris siblings and bounded nested
contents. Unsupported selections, oversized captures, unavailable USD/Houdini,
incomplete dependency inspection and corrupt packages are visible failures.
No global network tidy, new registered MCP write tool, external-library import,
substrate installation or changes to production deployment are included.

## Implementation plan

- `recipes/library.py`: pure metadata validation, atomic immutable versions,
  hash verification and search with explicit unreadable-entry problems.
- `host/saved_networks.py`: main-thread capture/restore, USD metadata codec,
  native clip round trip and observed dependency inventory.
- `host/recipe_watch.py`: lifecycle subscription, exact selection identity,
  deduplication, unsubscribe and nonmodal result delivery.
- `panel/saved_recipes.py`: local library UI, capture/version forms, dependency
  review, restore and opt-in watch controls using existing design tokens.
- `panel/designsystem/qss.py`: a scoped recipe extension and shared installer;
  the older stylesheet sections remain intact. The corresponding structure test
  checks each marked extension and its token-only styling.
- `panel/synapse_panel.py`: Recipes entry, local commands, watch cleanup and
  status messages. Existing model setup and task handling remain authoritative.
  `/saved-recipes` is intercepted before model preparation; the existing
  `/recipes` curated grammar is not repurposed.
- Pure regression tests, real Qt interactions and real Houdini composed probes.

## Qualification

Unchanged relevant baseline: 139 tests passed. Full-suite baseline remains the
network milestone's 7,616 passes, ten failures and 391 skips; nine failing checks
reproduce unchanged and one nested comparison is incomplete.

Watch new regressions fail before fixes. Exercise save → version → search →
restore twice, native nested state and nonzero ports, duplicate names, failed
capture, corrupt clips/manifests, missing dependencies, scene change dedup,
deleted/replaced selection, close/reopen, unavailable host and callback teardown.
Include competing version writers, failed publication between clip and metadata,
destruction without closeEvent, failed unsubscribe, and scoped restore cleanup.
Run independent composition review, focused and full suites, and a disposable
Houdini 22.0.400 GUI trial. Record limits without calling a focused pass a full
pass. Save the local checkpoint and evidence board, update the dashboard and
report before moving to model routing. Merge, release and production deployment
remain separate actions.
