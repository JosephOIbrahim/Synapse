"""Control for the list-position bug.

Observed live on a 2,727-node explain: sections rendered EMPTY and their bullets
appeared as one block at the bottom of the message.

_format_list_items harvests every list item in the whole message with findall,
deletes them all with sub(""), and appends a single <ul> at the end. Any message
with two bulleted sections has its structure destroyed - the bullets survive, the
order and the grouping do not.

This asserts the property that matters: a bullet must render BETWEEN the heading
it follows and the heading that follows it.
"""
import re, sys
sys.path.insert(0, 'python')

from synapse.panel.message_formatter import _format_list_items

MSG = "\n".join([
    "Layer 1: Shared Assets",
    "- Component Outputs: tetra, spiral, vase",
    "- Component Geometry: paired _geo sopcreate nodes",
    "",
    "Layer 2: Chapter Subnets",
    "- lights: every light type",
    "- motionblur: transformation blur",
    "",
    "Supporting Contexts",
    "- /obj standard object context",
])

out = _format_list_items(MSG)

def pos(s):
    return out.find(s)

l1, l2, sup = pos("Layer 1"), pos("Layer 2"), pos("Supporting Contexts")
comp, lights, obj = pos("Component Outputs"), pos("lights: every"), pos("/obj standard")

print("  Layer 1 at            :", l1)
print("  'Component Outputs' at:", comp, " -> after Layer 1:", comp > l1,
      "| before Layer 2:", comp < l2 if l2 >= 0 else "n/a")
print("  Layer 2 at            :", l2)
print("  'lights' at           :", lights, " -> between L2 and Supporting:",
      (lights > l2 and lights < sup) if (l2 >= 0 and sup >= 0) else "n/a")
print("  Supporting at         :", sup)
print("  '/obj' at             :", obj, " -> after Supporting:", obj > sup if sup >= 0 else "n/a")
print()
print("  <ul> count            :", out.count("<ul"), " (3 sections -> should be 3)")

ok = (l1 < comp < l2 < lights < sup < obj) and out.count("<ul") == 3
print()
print("RESULT:", "PASS" if ok else "FAIL - bullets are not in their sections")
sys.exit(0 if ok else 1)
