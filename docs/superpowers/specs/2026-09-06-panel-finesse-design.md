# M6: A panel that gets out of the way

Joe authorized the ordered UX roadmap and asked to continue milestone by
milestone, including live Houdini 22.0.400 testing. This closes the panel-finesse
scope already approved. The current identity, local USD memory language,
model-sharing rules and existing task execution remain the foundation.

## Measured starting point

The prior milestone is saved at 34f5f4c4. The first M6 baseline passes 69 checks
and skips 103 native-only checks. A live observation in the isolated M5 process
finds that /events and /saved-recipes rows carry their descriptions as the
payload, so a palette choice misses the local command handler. The prior M5
receipt tested the Events button and direct /events dispatch, not this composed
menu choice. Preserve that distinction and its raw evidence.

At actual chrome scale 2.25, requested widths of 360 or 560 became 862. The
initial investigation suspected the single footer row; the qualification
addendum below separates that layout from Houdini's containing window.
An unmatched search shows an empty list without explanation. Escape
already returns focus to the draft in the observed host; preserve and test it.

## Chosen approach

Refine these measured seams using native wrapping layouts and the shared style
owner. A wholesale visual redesign would add uncertainty without addressing
these failures. An overflow-only menu would hide the newly useful local views.
Keep Commands, Recipes and Events directly available instead.

1. Canonical command entries retain their command payload through ToolPalette.
   /events and /saved-recipes therefore reach the existing local handlers while
   busy, without a model request or consuming the draft. Other recipe/tool picks
   retain their existing prompt intent and permission path.
2. The keyboard hint gets its own wrapping line. Commands/Recipes/Events use
   native wrapping rows, retaining their order and existing button styles.
   Add accessible names to the composer and its image attachment button.
3. A command search with no matches displays a plain explanation and how to
   recover. Clearing the query or changing filters updates that feedback.
   Close the popup before emitting a chosen action so a new local dialog owns
   focus. Escape remains a dismissal, never a send. Reopening must not retain
   stale selections or accumulate hidden popup widgets.
   One gesture emits at most once; Enter on no matches emits nothing. A selected
   local dialog keeps focus, while Escape preserves and focuses the draft.
   Keep one popup per panel and reset its search/filters on each fresh opening.
4. Verify long replies/code, keyboard selection, repeated open/close, and
   short/narrow panes. Correct only defects exposed by these bounded checks.

## File plan

- panel/tool_palette.py: preserve command identity, visible empty-search state,
  close-before-emission, and bounded popup lifetime.
- panel/synapse_panel.py: wrapping footer, accessible controls, popup lifecycle
  integration and any measured final-row clipping correction.
- Shared design-system helpers only if native layouts cannot meet measured
  bounds; no new private colors, fonts, spacing values or ratchet exemptions.
- tests/test_panel_finesse.py: composed payload/draft regressions and meaningful
  native-independent checks. Native Qt/live producers live in checks/finesse.
- docs/help/commands.md and the M6 handoff: explain actual interaction and limits.

## Qualification

Independently review this spec, then attack the final source with real Qt on
Houdini's Python runtime. Measure scales 1/1.25 and the real 2.25. Check the
smallest attainable width honestly: requested width and actual width are both
recorded. The large-scale full-panel target is 560, with 360 explored separately;
native utility dialogs retain their prior independent qualification.

Exercise palette -> local dialog while idle and busy, no-match -> clear -> pick,
Escape -> type, repeated opening, draft preservation, long reply/code scrolling,
and short -> tall resize recovery. Capture evidence before and after; the
regressions must fail against the old source. Run the relevant baseline,
unchanged ownership checks, then one full regression after source stabilizes.
Keep the ten inherited full-suite failures and the incomplete baseline
comparison visible. Never call real model generation just to test a menu.

Save a reviewed local checkpoint and durable receipt before dashboard Verified.
Stop after all six scoped milestones are recorded, or at a concrete blocker or
a separate merge/release/deployment decision. No master/deployed-copy changes,
version edit, push, release, new substrate or production render is included.

## Qualification addendum: the native opening path

The default Houdini Python Panel creates a QuickStartBrowser whose containing
window already has an 862-pixel minimum, before SYNAPSE is loaded. Switching
interfaces afterwards retains that floor; hiding the toolbar or using the
official resize API does not remove it. The final SYNAPSE widget's minimum
hint is 555 at scale 2.25. Creating the window with the documented
python_panel_interface argument directly passes the actual 560-pixel target.
This is recorded in the M6 default/direct host comparison, not inferred from
the bounded Qt harness.

The product shelf used the same default-then-switch sequence for both docked
and floating creation. The measured correction therefore also includes
houdini/scripts/python/synapse_shelf.py and its behavioral tests. Select the
interface at creation, retain reuse of an existing tab and the preference for
docking, and preserve the existing floating size request. Houdini hides its
Python Panel toolbar when the interface is selected directly. Existing open
tabs are reused without changing their host geometry.
