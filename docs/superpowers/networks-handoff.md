# Networks you can trust — milestone 2

Repeated builds preserve arranged nodes and comments. New graphs can flow
vertically or horizontally; an explicit relayout applies that choice to the
reused nodes named in the request. Artist-owned references stay fixed.

The graph builder resolves the host's actual node versions and ports before
changing the scene. Preview and execution share a plan. Returned wires include
the observed source output and destination input; requested and actual display
state are reported separately. Conflicting slots, ambiguous node identities,
unrepresentable input gaps, and cycles through existing wiring are rejected.
Assembly accepts the same layout choice and rejects impossible ports in preview.

## Tryout

The separate Houdini 22.0.400 trial contains a 14-node look-development network
with 13 connections and three section boxes. Both layouts are saved locally:

- `checks/networks/gui/scene/SYNAPSE_network_vertical.hiplc`
- `checks/networks/gui/scene/SYNAPSE_network_horizontal.hiplc`

These paths are relative to the SYNAPSE_Refactor workspace. The vertical example
is open for visual feedback. The trial qualifies the real handlers, network
layout, and repeat behavior; it is not a new model conversation. The original
Houdini session and the first-session panel trial remain available. Product
changes are isolated on `ux/networks-20260906` and are not deployed over them.

## Evidence

- 252 focused checks passed.
- 19 composed network scenarios passed on real Houdini nodes.
- Independent review: 22 composed checks passed with stable source hashes.
- Visible trial: vertical → horizontal → repeat → vertical → repeat preserved
  the 13 connections and display output; repeated layouts reported unchanged.
- Seven broad live probes and both negative-control companions passed. The
  canonical strict runner remains failed because its unrelated G1 memory-write
  probe targets the original bridge and lacks a negative control; it was not run.
- Full suite: 7,616 passed, 10 failed, 391 skipped. The same ten failures were
  seen in the earlier milestone. Nine reproduce on unchanged source; the nested
  baseline comparison remains incomplete. No full-suite green claim is made.

Raw results, the exact independent command, source hashes, and test corrections
are under `checks/networks` and the milestone evidence board. Catalogs were
generated from 22.0.400, including measured ordered-input boundaries. Tests still
pointing to the historical 22.0.368 artifact were updated to the current artifact
without removing their checksum or byte-equality requirements.

## Limits and next milestone

This establishes bounded network construction and organization, not sustained
production stability, rendering correctness, model choice quality, or recovery
with undo disabled. Model-driven scene building was not part of this trial.
Recipes, tags and scene-exit capture are next, after Joe's feedback on this
milestone. Merge, publication and deployment remain separate actions.
