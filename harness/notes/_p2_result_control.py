"""Control for P2 — the result surface now has a producer.

P1's census measured it: set_credit / set_flags / set_paths / set_render /
show_result had ZERO product callers. The panel could render a result it never
populated, and set_credit's one caller passed a ROUTED row that its DECISION
filter drops — "a credit it could never earn".

This asserts both directions:
  POSITIVE  a turn that did things produces credit, flags and paths
  NEGATIVE  a turn that did nothing produces nothing - no invented decision

and that a FAILED tool becomes a flag rather than a credit (Law 3: report what
happened, not what was attempted).
"""
import sys, types
sys.path.insert(0, "python")

# Exercise the real method against a stand-in that carries only the state it
# reads. Importing the panel needs Qt; the logic under test does not.
from synapse.panel import synapse_panel as sp

Panel = sp.SynapsePanel
stub = types.SimpleNamespace()
stub._MUTATORS = Panel._MUTATORS
evidence = Panel._turn_evidence.__get__(stub, Panel)

print("=" * 70)
print("NEGATIVE CONTROL - a turn that did nothing")
print("=" * 70)
stub._turn_tools = []
c, f, p = evidence()
ok_neg = (c, f, p) == ([], [], [])
print("  credit=%s flags=%s paths=%s" % (c, f, p))
print("  ->", "PASS - nothing invented" if ok_neg else "FAIL")

print()
print("=" * 70)
print("POSITIVE CONTROL - a turn that built something")
print("=" * 70)
stub._turn_tools = [
    ("houdini_create_node", "ok", "created /stage/karmarendersettings1"),
    ("houdini_assign_material", "ok", "bound /materials/Dark_Glass to /stage/geo1"),
    ("synapse_inspect_node", "ok", "read /stage/geo1"),
    ("houdini_render", "failed", "EXR not written"),
]
c, f, p = evidence()
print("  CREDIT (DECISION rows):")
for row in c:
    print("    ", row)
print("  FLAGS:")
for row in f:
    print("    ", row)
print("  PATHS:", p)

names = [r[1] for r in c]
ok_mut = "houdini_create_node" in names and "houdini_assign_material" in names
ok_read = "synapse_inspect_node" not in names          # a read is not a decision
ok_fail = "houdini_render" not in names                 # a failure is not a credit
ok_flag = any(s == "fail" and "houdini_render" in t for s, t in f)
ok_path = "/stage/karmarendersettings1" in p and "/materials/Dark_Glass" in p

print()
print("  mutations credited      :", ok_mut)
print("  a READ is not credited  :", ok_read)
print("  a FAILURE is not credited:", ok_fail)
print("  the failure IS a flag   :", ok_flag)
print("  paths extracted         :", ok_path)

allok = ok_neg and ok_mut and ok_read and ok_fail and ok_flag and ok_path
print()
print("RESULT:", "PASS" if allok else "FAIL")
sys.exit(0 if allok else 1)
