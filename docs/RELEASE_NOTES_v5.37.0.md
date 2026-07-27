# v5.37.0 — the panel, connected

*Six panel changes, each with a control demonstrated failing before it was trusted. Five of the six close a gap between something the panel could already do and something an artist could actually reach.*

---

## The result surface had no producer

`set_credit`, `set_flags`, `set_paths`, `set_render` and `show_result` had **zero product callers.** The panel could render a result it never populated — and `set_credit`'s single caller passed a `ROUTED` row, which its own `DECISION` filter drops. **A credit it could never earn.**

`_on_tool_status` already fired for every tool with name, phase and detail, and threw the terminal results away. It now accumulates them per turn, and the review face credits what the turn actually did:

```
DECISION   houdini_create_node        created /stage/karmarendersettings1
DECISION   houdini_assign_material    bound /materials/Dark_Glass to /stage/geo1
FLAGS      ok · ok · ok · fail — houdini_render, EXR not written
PATHS      /stage/karmarendersettings1 · /materials/Dark_Glass · /stage/geo1
```

**Law 3 throughout.** A mutation that succeeded gets a decision row. A read gets nothing — it decided nothing. A failure becomes a flag, never a credit. An empty turn produces nothing rather than an invented decision.

Setters with product callers: **3 → 6.**

---

## 41 recipes were reachable and undiscoverable

The command palette showed 21 recipes from `panel/recipe_book`. `RecipeRegistry` held **62** more, including cinema-camera sets — and they fire on regexes matched against free text, so the capability existed and **nothing told an artist the words.**

The trigger patterns now yield the sentence you would type. Palette entries: **95 → 157.**

---

## The chat used a third of its width

The document was capped at a fixed **492px**. In an 1830px pane that left 73% empty.

The principle was right and stays — prose past ~90 characters a line gets harder to track. The unit was wrong: **pixels do not scale with the size control**, so raising the text size *shrank* the measure in characters. It is measured from the live font now and holds ~95 characters at every step.

---

## The size control was unusable by design

One `Aa` button cycling **five hidden steps**, with a tooltip as the only feedback. The options were invisible, the live state was invisible, and finding a size meant clicking until it looked right and then overshooting.

Three targets now, each labelled **A** and drawn at the size it sets — small, medium, large. The live one is bright.

---

## The wordmark, and a rule that cited a source saying otherwise

The v9 rule read: *"hierarchy comes from tracking and position, **never** from weight,"* citing Cohere.

Reading the source it cites: **"Cohere Text has three weights (bold, reg, light) plus italics."** Bold is one of three shipped weights, and the wordmark is *"carefully crafted using the Cohere typeface"* — a designed lockup, not tracked-out body text.

**An interpretation had hardened into a prohibition, and the prohibition justified itself by pointing at a source that contradicts it.** That is this release's own defect pattern, occurring in a design rule rather than in code.

The mark is weight 700 at 0.16em tracking in `TEXT_BRIGHT`, size unchanged. Weight alone would not have done it — bold with 4px tracking reads heavy *and* sparse. Solidity is weight plus density.

---

## And the action row can breathe

`EXPLAIN / FIX / OPTIMIZE / BUILD HDA` had 4px inside each pill and 4px outside the row. Now 7 and 6 — **8px → 13px per side.** Horizontal deliberately untouched: the crowding was vertical, and widening the pills would have changed the row's wrap point for no reason.

---

## The shape of it

**Five of the six were connections, not additions.** A surface that could render what nothing sent it. Recipes reachable by words nobody could guess. A measure in a unit that could not scale. A control whose state was invisible. A rule quoting a source that disagreed.

None of them were missing features.

---

## Verifying any of this

```
harness/notes/_p2_result_control.py        credit/flags/paths, both directions
harness/notes/_measure_control.py          the measure holds across size steps
harness/notes/_sizecontrol_control.py      three targets, live one marked
harness/notes/_wordmark_control.py         heavier AND denser AND brighter
harness/notes/_quickactions_control.py     more vertical, horizontal untouched
```

Each was demonstrated failing before its pass was trusted. Suite: 5,031 passed, 0 failed.
