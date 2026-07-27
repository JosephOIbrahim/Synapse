# v5.36.2 — two defects only a live run could find

*A patch. Both fixes came from ten minutes in the GUI on SideFX's own scene, after five days of headless verification found neither.*

---

## What broke, and why no test caught it

The first real GUI run of the shipped code was an explain of `karma_user_guide.hip` — SideFX's own documentation scene, 5,764 nodes across six contexts. **It did not crash**, which was the point of the exercise.

It surfaced two rendering defects instead. Both live in *where the eye lands* rather than in what a function returns, so no headless assertion could reach them.

### The authorship credit landed mid-table

SYNAPSE credits the model that produced a result. The v9 design attached that credit to the **first node chip** in a message — and on a structured answer, the first node path fell inside a markdown table cell:

```
| /stage/lights · signed GLM 5.2 | every light type |
```

It reads as a text bug, which is the opposite of what a credit is for.

Two docstrings described the feature differently — one said *"once at the head of a SYNAPSE group,"* the other said *"the first node chip carries the suffix."* The implementation followed the second. **The first is the better behaviour, and the standalone note that renders it already existed as a fallback.** Chips no longer claim it.

### Every bullet was dumped at the bottom

`_format_list_items` harvested every list item in the whole message with `findall()`, deleted them all with `sub("")`, and appended a single `<ul>` at the end.

The bullets survived. Their **position and grouping** did not.

Three bulleted sections collapsed into one undifferentiated list, and a bullet belonging to "Layer 2" rendered after the "Supporting Contexts" heading. **That is worse than no formatting** — SYNAPSE produced a genuinely good two-layer architectural read of someone else's scene, and the formatter threw the layers away.

Now it walks line by line and closes a `<ul>` when a run of list items ends.

---

## A correction that did not ship, and why it is here

A leg was dispatched to migrate 108 "stale" Houdini 21 references in the retrieval corpus to H22.

**It was wrong and was killed before it wrote anything.** The corpus *is* Houdini 21 documentation — H22 docs have not been converted yet. Every reference classified as stale was accurate, and the migration would have relabelled true content, making the corpus lie about its own provenance.

**The model was right and the reading of it was wrong.** SYNAPSE said *"SideFX ships with Houdini 21"* because it retrieved H21 documentation and reported its version accurately. That is the system being honest about its own knowledge.

`rag/skills/houdini21-reference` keeps its name. It is currently the most honest thing about it.

**The README now states the split plainly:** symbols and node types are H22 and verified against the running build; the prose corpus is H21 and labelled as such. Most consequential for Copernicus, which barely existed in H21.

---

## Also

**The README carries three diagrams now** — where the agent lives, what it knows and where that comes from, and the audited-vs-live paths. The middle one is new and is the one to read first.

**Known limitations are unchanged** and stated in full: no delta path, no `RopNode` cancel, the PDG rollback that has never executed, 41 deprecated node types, emergency halt unsurfaced, grounding at 18.3% LOP and 6.2% Copernicus.

---

## Verifying any of this

```
python harness/verify/version_agreement.py
python harness/verify/bom_audit.py
python harness/heats_status.py
```

Each fails on an unfixed tree. Both panel fixes carry controls asserting the property in both directions — the credit renders exactly once and not inline; bullets render between the heading they follow and the one that follows them.

**House rule:** no number enters a document without a producer path beside it.
