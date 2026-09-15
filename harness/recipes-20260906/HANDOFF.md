# Saved networks — milestone 3

Recipes now opens a local library from the panel or `/saved-recipes`. Select
Solaris sibling nodes, name the network, add tags and notes, and save it. Each
version contains a native Houdini clip and USD metadata on this workstation.
The existing `/recipes` command retains its separate curated-recipe purpose.

Search by name or tag, inspect the dependencies, and insert a new copy in a
separate subnet. Positions, connections, connection dots and wholly owned
section boxes are preserved and read back. Existing scene layout stays fixed.
Missing known files or node types, changed clip bytes, a different Houdini build,
and malformed placement records refuse insertion before changing the scene.
Unknown expression dependencies remain visible and require acknowledgment.
External assets are referenced; they are not copied into the recipe.

“Keep at next scene change” watches the exact selected node identities for one
capture before leaving the scene or closing the panel. Save As provenance uses
the actual outgoing scene. The watch disarms before capture and reports failures;
it does not promise crash recovery. A failed secondary status record cannot hide
a successful primary capture. Capture and restore use Houdini's main thread.

The library defaults to `~/.synapse/recipes`; `SYNAPSE_RECIPE_DIR` overrides it.
No model request or cloud transmission is needed for this workflow.

## Qualification

Evidence is in the SYNAPSE_Refactor workspace under `checks/recipes` and the
local `harness/recipes-20260906` board. The source is isolated on
`ux/recipes-20260906`; it is not deployed over the artist's installation.

- 188 focused checks passed, including 49 new regression checks.
- 19 composed scenarios passed in Houdini 22.0.400.
- Independent review passed 60 additional native scenarios, 36 persistence and
  Qt checks, and eight final integration checks.
- The separate live GUI trial passed 15 control and host checks: local entry,
  save, search, acknowledgment, two inserts, versioning, actual scene callbacks,
  Save As, scaled controls, and failure reporting without a surviving notifier.
- Full suite: 7,665 passed, 10 failed, 391 skipped. The ten failing names match
  the prior milestone. Nine were reproduced on unchanged source; one nested
  baseline comparison remains incomplete. This is not a full-suite pass.

The original failing probes are preserved. Disabling placement validation made
16 of its 17 regressions fail. Reviews also exposed and corrected metadata
publication, concurrent status writes, dependency detail, typography, dot wiring,
and placement ownership defects. The shared stylesheet guard retains its original
checks and now covers a separate recipe block; its earlier blocks are unchanged.

The live GUI's `statusMessage()` returned `severityType.Message` after explicit
Warning and Error calls while correctly prefixing their displayed messages.
`gui/status-probe.json` records native controls; `gui/status-qualified.json`
compares failure delivery with the measured native Warning behavior. Product
source was unchanged when the incorrect enum-equality probe was corrected.

## Tryout and limits

The synthetic scene is `checks/recipes/gui/scene/SYNAPSE_recipe_trial.hiplc`.
Actual Qt renders are `gui/save-selection.png` and `gui/library-final.png`.
The GUI test harness exercised real controls and real Houdini operations.
Computer Use did not reliably target the floating panel, so successful manual
mouse and keyboard interaction is not claimed.

Production scenes, arbitrary HDA callbacks, rendering, sustained use, crash
durability and cross-build portability remain unqualified. Local captures are
authored work, not a ratified curated RecipeSpec or a new memory-store authority.
The next milestone is production-aware model routing, followed by useful job
notifications and panel finesse. Joe authorized continuation after each report.
