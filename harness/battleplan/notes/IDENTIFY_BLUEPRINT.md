# IDENTIFY BLUEPRINT - one click, every selected node explains itself

Status: v1.4 - 2026-09-29 - the overlay's G1 and G5 pass through the panel button (section 10). v1.3 built
help paths the way Houdini's help builds them, and What lines carry no help markup (BP12 item 3, section 11).
v1.2 made the bubble an overlay on the network editor (section 10). v1.1 shipped in v5.85.0 (section 9). v1.0
authored by the CTO seat on Joe's word.
Source of truth for BP11-IDCORE, BP11-IDSURF, BP11-SALIENCE and BP12 item 2. Update this card; don't multiply it.
Companion: `harness/battleplan/notes/BP11_CTO_PLAN.md` (scouting report, wave graph, budget, rulings).

## 0. One paragraph

The artist selects some nodes and clicks Identify, either the panel button or `/identify`.
Each selected node gets a short bubble beside it, drawn over the network editor, that says what the node
does, which of its changed parameters matter, and whether it is in trouble. Code builds every bubble from
exact sources, so there is no model call, no network call and no token cost. The bubbles are an overlay:
nothing is written to the scene. A second click, or `/identify off`, takes every bubble away.

## 1. What M0 proved (live probe, Houdini 22.0.400, 2026-09-28)

The probe built a seven-node SOP chain in `/obj/identify_probe`, selected it, and tried every
drawing path the H22 network editor offers. Producer scripts:
`C:\Users\User\Downloads\synapse_identify_probe.py`, `_probe2.py`, `_probe3.py`, `_probe4.py`, with reports
beside them. Evidence tier for every row below is PROBED unless marked otherwise.

- **The carrier works.** `node.setComment(text)` plus `node.setGenericFlag(hou.nodeFlag.DisplayComment, True)`
  draws the text under the node in every network editor looking at that network. It follows pan and zoom.
- **The flash banner works.** `NetworkEditor.flashMessage(None, text, seconds)` shows a fading line in the
  editor's upper left corner.
- **Custom shapes are not a carrier.** `setShapes()` with `NetworkShapeBox(..., screen_space=False)` draws in
  network space, but the editor's own event handling wipes it as soon as the mouse moves. `setOverlayShapes()`
  drew nothing. H22 ships no text shape (`NetworkShape`, `Box`, `Connection`, `Line`, `NodeShape` only).
- **Hover is a later door.** `setTooltip()` exists, but it only makes sense from the editor's event hook.
- **The facts are all there.** Per node the probe read `type().nameWithCategory()`, `type().description()`,
  `type().defaultHelpUrl()` (for example `operator:Sop/polybevel?version=3.0`), `errors()`, `warnings()` and the
  non-default parameters.
- **The raw parameter list is noisy.** PolyBevel reported six changed parameters, five of them ramp internals.
  Attribute Noise reported two folders. Filtering folders and `ramp\d+(pos|value|interp)` left PolyBevel with
  `offset` alone.
- **Long bubbles collide.** In a default layout a long comment overlaps the node below it (OBSERVED on screen).

## 2. The bubble (contract)

A bubble is drawn by `identify/overlay.py` from the fields `identify/bubble.py` builds. Its anatomy follows
option 1 on the `Identify Bubbles` canvas, and every colour, font, padding and radius is a design-system token.

1. **Header.** The SYNAPSE ring (WARM), the type label from `type().description()`, and the category tag
   (`SOP`, `LOP`, `OBJ` ...) at the top right in Space Mono.
2. **What.** The summary of the node type from the local SideFX library, found by the exact help path that
   Houdini's own help opens for the type (section 11). For an HDA with embedded help, that help's summary. When
   no exact row exists the bubble says `Not in the local SideFX library.` in a quiet ink; for now a page with no
   summary line says the same (section 11). A search-ranked hit is never used as a node's summary, because a
   near match on the wrong page is a phantom.
3. **Here.** For a LOP, `writes <first prim> (+N)` from the prims the node last modified, the path in SIGNAL
   Space Mono. For any other node, up to two changed parameters that matter, written as `Label value`.
4. **State.** Present only when non-empty: `error: ...` (ERROR), `warning: ...` (WARN), `bypassed`, `beta`.

Formatting rules: floats to three significant digits, a parameter driven by an expression or channel marked
`(expr)`. Text wraps inside the bubble instead of being cut at 56 characters; one field is bounded at 240
characters. A long title or path is shortened with an ellipsis.

The bubble is 300 px wide at a host scale of 1, scaled by the host font the way the panel scales itself. It
sits beside its node after two tail dots: on the right past the name label, or on the left, whichever side
has room, and it narrows to fit down to 200 px. A chip at the editor's top left reads
`Identify  N of M nodes`. When the network is zoomed out so far that nodes are shorter than half a text
line, each node gets a ring marker instead of a bubble.

The comment carrier of v1.1 is retired. Older versions appended the bubble text to the node comment below the
ASCII sentinel line `~ identify ~`; `identify/apply.py` now only removes such a block (section 3, rule 2).

## 3. Rules the code must keep (the crucible re-checks each one with its own mutation)

1. **Zero tokens by default.** The bubble path makes no model call and no network call. `/identify` is a
   panel-answered command: it is added to `PANEL_ANSWERED_COMMANDS` in `panel/command_palette.py`, so it can
   never reach the model.
2. **Nothing is written to the scene.** The overlay reads only. The one write left is the legacy cleanup:
   when an identified node carries an old Identify comment block, it is removed in one undo group named
   `SYNAPSE Identify cleanup`. A block is removed only when it has the exact shape Identify wrote: the last
   standalone sentinel line, one to three lines after it, none longer than 56 characters, and the first of
   them a What line Identify could have written for that node. Artist text is never lost (CRUX F4).
3. **Clearing is a click.** A second click on the same nodes, or `/identify off`, removes every bubble. A click
   on a different selection replaces them. Bubbles make no undo entry, because they change nothing.
4. **Nothing reaches disk.** There is nothing to strip, so the BeforeSave and AfterSave hooks are gone and no
   Identify module registers a hipFile callback (CRUX2 N5 closed by removal).
5. **Short main-thread holds.** Library lookups and bubble building run off the main thread. The main-thread
   steps are the facts read and the overlay draw. The overlay's tracking tick runs at 30 Hz while bubbles are
   shown and repaints only when a node, the zoom or the pane moved. The selection is capped at 60 bubbles, a
   starting value, and the chip says `60 of 214 nodes` when the cap applies.
6. **Exact sources or UNKNOWN.** Summaries come from an exact help-path row. An unknown type says so. No value
   is estimated.
7. **Reuse, don't fork.** Selection facts come from `server/introspection.inspect_selection`, the same
   pipeline the Selection Inspector uses (`panel/selection_inspection.py:68`). Identify adds no second walk of
   the selection.
8. **The Inspector stays read-only.** Its module docstring promises that it owns no Houdini objects
   (`panel/selection_inspector.py:1-4`). Identify adds no writer there. The Inspector may show the same bubble
   text as a read-only column.
9. **Tokens and one registry.** Every colour, font and size in the overlay comes from
   `panel/designsystem/tokens`, the overlay declares no colour of its own, and
   `tests/panel/test_token_authority.py` stays green. `/identify` is registered once, through
   `tool_palette._load_entries` (`panel/tool_palette.py:141`), per the "one registry, one name" rule in
   `panel/command_palette.py`.

## 4. Where it lives

    python/synapse/identify/__init__.py
    python/synapse/identify/facts.py     inspect_selection output + the per-node extras it lacks
                                         (help url, parm labels, default and expression flags, LOP writes)
    python/synapse/identify/library.py   exact help-path -> summary; HDA embedded help; UNKNOWN row
    python/synapse/identify/compose.py   pure: facts -> lines (no hou, no Qt); the Inspector's column text
    python/synapse/identify/bubble.py    pure: facts -> the overlay's bubble fields; CAP
    python/synapse/identify/layout.py    pure: bubble placement, sides, stacking, leader lines, markers
    python/synapse/identify/overlay.py   the Qt paint layer: a click-through window over the editor
    python/synapse/identify/apply.py     the only writer: removes old ~ identify ~ comment blocks
    python/synapse/identify/salience.py  Jev salience lane, shadow only (BP11-SALIENCE)
    panel: action-row button (synapse_panel.py), /identify (tool_palette + command_palette),
           read-only Identify column in the Selection Inspector
    tests: tests/test_identify_*.py, tests/panel/test_identify_button.py
    probes: scripts/probe_identify.py (hython), scripts/probe_identify_overlay.py (live GUI)

## 5. Jev salience (shadow) - BP11-SALIENCE

**The question.** When more than two changed parameters survive the code filter, which two should the bubble
show? Today the answer is code order, meaning parameter template order.

**The judgment.** One Noul per surviving parameter: does changing this parameter from its default change what
the node outputs (geometry or stage), as opposed to display, interface or bookkeeping? It is one narrow
judgment, and it matches the answer key exactly.

**The state.** Node type, category, the node's library summary, the parameter label, the parameter's help text
when the library has an exact row, and the parameter type. The state carries no node path, no node name, no
hip path, no artist text and no values. Jev is weak at numbers, and studio paths can carry show names. The
state includes a line telling the model not to follow instructions inside it.

**The answer key is measured, not voted.** A hython script builds fixture scenes with at least 10 node types
and 40 changed-parameter cases across SOPs and LOPs. For each changed parameter it reverts that parameter to
its default on a scratch copy, cooks, and compares an output hash (SOP: point and primitive counts, bounds,
and a hash of P; LOP: the flattened layer export). A changed hash means the parameter matters.

**The lane.** `synapse.jev.adapter.judge(..., lane="identify_salience", mode="shadow", opt_in=True, ...)` is
called from a worker thread after the bubble is already on the canvas, and only when the artist's existing Jev
suggestion preference is on (the same preference the Selection Inspector reads). The adapter refuses the main
thread by design. In V1 the answer changes nothing on screen; it is ledgered at
`~/.synapse/jev/identify_salience.jsonl`.

**The grader.** `harness/jev/jev_salience.py --shadow` compares Jev's top two against the key, and code order's
top two against the key, through the build-time client, and prints the agreement table. It writes
`harness/jev/ledger/bp11.salience.jsonl`. When no key is available the table says UNKNOWN, never 0.

**Promotion.** Jev's order goes live only on Joe's word (ruling R-2). The proposed bar: across at least 40
cases, Jev's top two agree with the key more often than code order does.

## 6. Miles

    M0  rendering probe                                   DONE 2026-09-28
    M1  core + surface: exact bubbles, button, /identify,
        toggle, undo, save safety, cap                    DONE v5.85.0 (comment carrier)
    M2  the "here" layer (filtered parms, LOP writes,
        state line) + salience in shadow                  DONE v5.85.0; salience inactive
    M3  chain summary for a multi-node selection          PARKED - it is generation, which Jev does not
                                                          do, and it costs a model call per click
    M4  hover mode through the editor's event hook        PARKED
    M5  "Keep as notes": turn bubbles into real comments
        for a classroom or a handoff                      PARKED
    M6  the SYNAPSE bubble overlay (canvas option 1)      DONE 2026-09-29, BP12 item 2 (section 10)

## 7. GUI gates (computer use by the seat; every leg marks these UNKNOWN)

    G1  the Identify button is in the panel's action row and styled by tokens
    G2  a node chain: one bubble beside each node and the chip
    G3  a second click clears every bubble; a pre-existing artist comment is untouched
    G4  a LOP chain: a bubble names the prims its node wrote
    G5  200 selected nodes: the panel stays responsive; the measured hold is written down
    G6  the scene hash is the same before and after show and clear
    G7  the bubbles follow a zoom in and out, and the wheel reaches the editor through the overlay

## 8. What Identify is not

It is not a docs browser, not a model call, and not a replacement for the Selection Inspector. It writes
nothing to the scene. The only write is removing an old Identify comment block that has the exact shape an
older version wrote.

## 9. Shipped in v5.85.0 (2026-09-28)

Identify shipped in v5.85.0 (tag `v5.85.0` on `8a90e5e5`, all six CI jobs green in run 36494157653, published at 18:56 and marked Latest: https://github.com/JosephOIbrahim/Synapse/releases/tag/v5.85.0). The live gates ran by computer use in Houdini 22.0.400.

    G1  pass  Identify sits in the panel's action row beside Connect and Doctor
    G2  pass  7 of 7 notes on the final code; PolyExtrude reads "Extrudes polygonal faces and edges."
    G3  pass  one Ctrl+Z cleared all 7; the artist comment survived show and clear
    G4  pass  gate_ball says "writes /ball" (pass-through LOPs say it too: known limit)
    G5  pass  60 of 200 notes, 1.2 s after the click cold and 53 ms warm; longest main-thread
              pause 80 ms against 55 ms idle (about 40 s before IDFIX)
    G6  pass  saved with 67 notes: 0 in the file, artist comment on disk, all 67 back in session

**What changed from this blueprint.** Rule 5's target held once IDFIX capped the selection before reading
facts and memoized the library lookup. Rule 4 needed IDFIX to arm the save hooks inside `show()`. Rule 6
needed two passes: IDFIX stripped a leading BOM and directive block, and IDFIX2 skips markup-only paragraphs
wherever they sit, which is the real corpus shape. The salience lane (section 5) ships inactive: the live
grade kept code order (9 of 10 against Jev's 8 of 10), so it is not called.

**Known limits, carried to BP12.** 39 of 4,606 node help pages still produce a summary with leftover
formatting (`= Title =` headings, `:warning:` tags on deprecated nodes, `[Image:]` links on six MaterialX
nodes, inline `**`). A standalone `~ identify ~` line in artist text reads as a note (F4). A library outage on
the first lookup of a type is cached until restart (CRUX2 N1). The notes are Houdini comment text; the
approved SYNAPSE bubble overlay (option 1 on the `Identify Bubbles` canvas) is the next visual step.

## 10. The overlay, BP12 item 2 (2026-09-29)

Joe approved option 1 on the `Identify Bubbles` canvas: a Qt overlay with the panel's tokens, and nothing
written to the scene. Commit `5d25069a`, local until Joe says to push.

**Why a window, not a widget.** A live probe on 22.0.400 found that Houdini draws its whole main window in
one native OpenGL surface (`RE_WindowDrawable`, a `QOpenGLWidget` with a native handle), so a plain child
widget would sit underneath it. The overlay is a frameless, see-through, click-through tool window owned by
the window that holds the network editor (`NetworkEditor.qtParentWindow()`), placed over the drawing area:
`qtScreenGeometry()` minus the toolbar above `screenBounds()`. Node anchors come from `posToScreen()`, whose y
axis points up from the editor's bottom edge. Name labels run about 0.07 to 0.11 network units per character
(probed with `networkItemsInBox`); the overlay uses 0.1.

**Live check (computer use, Houdini 22.0.400, UI scale 2.25, the `/stage/lookdev_xpu` network).**

    G2  pass  the chip and one bubble per visible node, beside its node, past its name
    G4  pass  SOP Import, Texture Material Library, Camera and Light say "writes <prim>"
    G6  pass  scene hash 17ef933cf91c37a5 before the first probe and after show and clear
    G7  pass  a three-step wheel zoom out and back: the wheel reached the editor through the overlay,
              and the bubbles followed both ways
    G3  pass  clear removed all 7 bubbles (through the overlay's own clear, not the panel button)
    G1, G5  UNKNOWN at first: the running session had the old panel code loaded, so the button path
              was not clicked live. Both passed later the same day, below.

Cost: a full layout pass took 0.1 to 0.25 ms for 7 nodes and an idle tick 0.08 ms.

**The button path, live (computer use, Houdini 22.0.400, 2026-09-29 19:27 to 19:39, an untitled scene).**
Houdini had been restarted on the current tree, so the panel ran the overlay code.

    G1  pass  box, PolyExtrude, Transform and Null, all four selected: one click on the panel's Identify
              button drew the chip "Identify 4 of 4 nodes" and one bubble beside each node with its
              library summary; a second click took every bubble and the chip away
    G5  pass  200 selected null SOPs: the chip read "60 of 200 nodes · zoom in to read", with 60 ring
              markers. A 10 ms timer on the main thread measured the longest pause at 81 ms, the next at
              78 ms and every other gap at 20 ms or less, against 11 ms idle (v5.85.0 measured 80 ms
              against 55 ms idle). A second click cleared the markers

The test networks were built and deleted with undo disabled, and `/obj` was empty again afterwards.

**For the next live probe.** In Houdini 22 the Python Shell runs code off the main thread (a thread named
`Dummy-12`), so a `QTimer` created there never starts. A probe that touches Qt goes through
`hdefereval.executeInMainThreadWithResult(fn, *args)`. The probe used here is
`.token-saver/bp11/l1id_setup.py`.

**What the live check changed.** At a 2.25 UI scale a 300 px bubble is 675 px, wider than the room beside a
node in a 1,249 px pane, so bubbles ran off the right edge. A bubble now takes the side with room and narrows
to fit, down to 200 px. In a crowded column, stacking pushed bubbles beside the wrong node; a bubble now takes
the side where it drifts least, and one that still drifts gets a leader line from its tail to its edge,
drawn under every bubble.

**Known limits.** In a narrow pane at high UI scale a crowded column still stacks downward with leader
lines, and the lowest bubbles can run past the bottom edge; centring a stack on its nodes is not built. The
tail dots use the canvas colours and are faint on the editor's background. The name estimate covers the
name, not the LOP info line under it, which a bubble can cover. The overlay can draw over a floating Houdini
window that sits above the editor (not tested). Bubbles show the facts from the click; they do not update
when a parameter changes afterwards.

## 11. Help paths and clean What lines, BP12 item 3 (2026-09-29)

**What was wrong.** The What line leaked help markup on 617 of the library's 4,606 node pages: wiki and
markdown headings, `:warning:` boxes, `[Image:]` links, bold and italic markers, and a stray title before a
byte-order mark. Separately, the lookup built help paths its own way. It missed every Object node, every ROP,
every Labs node and the network managers, because Houdini keeps those pages under `nodes/obj`, `nodes/out`,
`nodes/<context>/labs--<name>-<version>` and `nodes/manager`. HDA help also leaked its `"""` tooltip quotes.

**The lookup now mirrors Houdini.** `derive_help_keys` follows `houdinihelp.api.components_to_path` in
Houdini 22. The category picks its help folder from Houdini's `table_to_dir`, a `?namespace=` becomes a
`<namespace>--` prefix with colons written as `$`, and a `?version=` becomes a `-<version>` suffix. A type
without a namespace tries `nodes/manager/<name>` last, as Houdini does. A scoped type (`?scopeop=`) needs
`hou` to decode its scope, so it stays honestly unknown.

**The summary rules.** A page's summary is its triple-quoted tooltip when it has one, which is Houdini's own
tooltip rule. Otherwise it is the first prose paragraph before any section. The walk skips titles,
breadcrumbs, directives (with or without their colon), includes, pictures, note and warning boxes, lists,
tables, code, indented blocks and template placeholders. A section heading, an `@` marker or a parameter
term before any prose ends the search, so the line stays unknown rather than borrowing a sentence about a
part or a context of the node. Inline markup becomes plain words: a link keeps its label and a code span its
text. `library.RESIDUE` is the one pattern that says what counts as markup.

**Measured** with `scripts/sweep_identify_summaries.py` on library generation `6b2fc2d5` and the live type
list from Houdini 22.0.400:

| | before | after |
|---|---|---|
| Node pages with markup in the What line | 617 of 4,606 | 0 |
| Node types that reach a library page | 3,864 of 5,661 | 4,625 |
| Reached pages with markup in the What line | 119 of 3,668 | 0 of 4,322 |
| Reached pages with no summary line | 0 | 12 |
| HDA help texts with markup | 53 of 55 | 0 (the other 2 are template blanks, now unknown) |

**Jev check.** Jev judged the lines that changed, as a seat check outside the product; Identify still makes
no model call. The 257 cases were every changed or emptied line on a reached page, with 60 of the 303 Labs
pages because they share one shape, and every changed HDA help text. Jev rated 217 of the new lines as
describing their node, against 97 of the old ones. It flagged 29 lines. One was a real miss, a directive
written without its colon, now fixed and pinned by a test. Twenty-two are pages whose own summary points
elsewhere ("See the RSL texture() function in the RenderMan documentation."), and they stay as written.
Three are the pages' own first sentences, rated just under even odds (MtlX Plus: "Adds bg input to fg.").
The last three are Overview pages where Jev found a describing sentence further into the section; they stay
unknown under the strict rule. The run took 9 seconds and about 261,000 input and 33,000 output tokens.

**The 12 reached pages with no summary line** are Cloth Solver 2.0, FEM Solver, Draw Guides, Edit Context
Options, Geometry Clip Sequence, Load Layer for Editing, Value Clip, and the DOP, Object, ROP, SOP and TOP
network manager pages. Each page top opens on a Parameters, Overview, Tips or Related section.

**Parked as new BP12 items.**

- **Deprecated nodes.** A deprecated node's What line no longer carries the warning box. The right source is
  `hou.NodeType.deprecated()`, true for 314 types on the seat's machine, shown on the state line beside
  `bypassed`. It needs a fact, a state-line rule and a GUI check.
- **"No summary line" wording.** The 12 pages above show `Not in the local SideFX library.`, which is not
  accurate for them. A distinct line needs a bubble field and a GUI check.

**Re-run it.** `python scripts/sweep_identify_summaries.py` checks the configured library. Add
`--types <file>` with a list written inside Houdini by `scripts/probe_node_help_urls.py` to check the pages a
session's node types reach and its HDA help. The corpus-gated test
`test_no_node_page_what_line_carries_help_markup` runs the same check when `SYNAPSE_SIDEFX_CORPUS_ROOT` is set.
