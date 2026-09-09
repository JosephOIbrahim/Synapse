# Demo repairs

This change addresses the failures recorded in the 9 September 2026 SYNAPSE demo.
It requires a fresh Houdini session using the repaired source; an already-running
panel continues to use its installed code.

## Organize an existing network

Ask SYNAPSE for a vertical or horizontal arrangement, clear sections with generous
spacing and restrained colors, or named asset groups. The supported tool is
`houdini_layout_network`. It takes existing node paths and explicit asset groups;
SYNAPSE should inspect the network before choosing the groups and labels.

The tool changes positions, colors, explanatory comments and network boxes. Node
names, parameters, connections and output flags remain intact. Existing artist
comments are retained. Undo and Redo use a concise action label. A request that
would disturb unselected items in an artist's box is refused before any changes.
The tool requires Undo to be enabled.

## Remember a decision at the intended scope

“Remember this for the project” should use `synapse_decide` with `scope=project`.
The default `scope=scene` records a shot decision. The result reports the actual
scope, tier, record ID and storage directory. A failed durable write reports
`recorded=false`; readable Markdown mirrors are supplementary and report their
own failures separately.

Unreadable or incomplete JSONL, conflicting record identities and encryption
failures refuse further writes while retaining the original bytes. Identical
duplicate records are safe to reopen. Recovery is explicit; a new decision does
not silently repair a damaged store by discarding its unreadable rows.

For a saved scene, the canonical store follows a meaningful configured Houdini
project directory (`JOB`) that contains the scene. Otherwise, the scene directory
acts as the local project. Saving an untitled scene carries its records into the
saved location. Save As retains original record identities and provenance; scene
lineage keeps inherited shot decisions discoverable. Opening another scene does
not copy the previous scene's memory. Pending outboxes and approvals stay in their
original locations. Original source records are retained.

Recall accepts multiword questions whose meaningful words occur in a different
order. `scope=project` selects project decisions; `scope=scene` selects the current
scene and its Save As lineage. The default `all` searches all tiers in the current
project store. Recall returns canonical record IDs, not Markdown line numbers.

The older `synapse_project_setup` context still reads one `claude/memory.md` per
HIP directory. HIP files in the same folder share that readable context. Explicit
scene filtering applies to canonical recall/search; it does not isolate that
legacy Markdown projection.

## Remaining qualification

Native H22.0.400 probes and automated tests are required for this change. They do
not establish that either recorded Houdini exit is fixed. The first exit involved
Qt WebEngine/accessibility processing; the second occurred after a journaled
recall dispatch whose returned payload was not preserved. Memory access and text
search serialization have been hardened against independently reproduced hazards.

The final demo still needs a fresh installed build, live visual review, model tool
selection verification and new footage for the repaired chapters. No release or
installer version is implied by this source change.
