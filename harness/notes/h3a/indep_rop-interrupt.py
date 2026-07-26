# ASSAYER independent probe -- H3a leg. Throwaway. No imports from h3a_probe.py.
import sys

print("=== PROBE START ===")

try:
    import hou
except Exception as e:
    print("IMPORT_FAIL: %r" % (e,))
    sys.exit(2)

print("BUILD: %s" % hou.applicationVersionString())
print("BUILD_TUPLE: %r" % (hou.applicationVersion(),))
print("PYTHON: %s" % sys.version.replace("\n", " "))
print("EXECUTABLE: %s" % sys.executable)

# ---------------- CONTROLS ----------------
pos = hasattr(hou, "node")
neg1 = hasattr(hou, "zzz_indep_control_must_not_exist")
neg2 = hasattr(hou, "lopNetworks")
print("CONTROL_POS hasattr(hou,'node') = %r  (expect True)" % pos)
print("CONTROL_NEG1 hasattr(hou,'zzz_indep_control_must_not_exist') = %r  (expect False)" % neg1)
print("CONTROL_NEG2 hasattr(hou,'lopNetworks') = %r  (expect False)" % neg2)
controls_ok = (pos is True) and (neg1 is False) and (neg2 is False)
print("CONTROLS_OK = %r" % controls_ok)

# ---------------- TARGET SYMBOL ----------------
print("--- TARGET: hou.RopNode.render ---")
seg1 = hasattr(hou, "RopNode")
print("hasattr(hou,'RopNode') = %r" % seg1)
print("'RopNode' in dir(hou) = %r" % ("RopNode" in dir(hou)))
if seg1:
    RN = hou.RopNode
    print("repr(hou.RopNode) = %r" % (RN,))
    seg2 = hasattr(RN, "render")
    print("hasattr(hou.RopNode,'render') = %r" % seg2)
    print("'render' in dir(hou.RopNode) = %r" % ("render" in dir(RN)))
    if seg2:
        r = getattr(RN, "render")
        print("repr(hou.RopNode.render) = %r" % (r,))
        print("type(hou.RopNode.render) = %r" % (type(r),))
        d = getattr(r, "__doc__", None)
        print("doc(hou.RopNode.render) = %r" % (d,))
    print("EXISTS hou.RopNode.render = %r" % (seg1 and seg2,))
else:
    print("EXISTS hou.RopNode.render = False  (segment 'RopNode' absent)")

# ---------------- RELATED NAMES ON hou.RopNode ----------------
print("--- RELATED NAMES ON hou.RopNode ---")
KEYS = ("render", "cancel", "abort", "interrupt", "kill", "stop", "cook", "background")
if seg1:
    names = sorted(dir(hou.RopNode))
    print("LEN_DIR_RopNode = %d" % len(names))
    hits = [n for n in names if any(k in n.lower() for k in KEYS)]
    for n in hits:
        print("RELATED %s" % n)
    print("RELATED_COUNT = %d" % len(hits))
else:
    print("RELATED_COUNT = 0")

# ---------------- EIGHT MODULE-LEVEL NAMES ----------------
print("--- MODULE-LEVEL CHECKS ---")
EIGHT = [
    "InterruptableOperation",
    "updateProgressAndCheckForInterrupt",
    "OperationInterrupted",
    "interruptRender",
    "abortRender",
    "killRender",
    "setUpdateMode",
    "updateModeSetting",
]
hou_dir = dir(hou)
for nm in EIGHT:
    ha = hasattr(hou, nm)
    ind = nm in hou_dir
    print("MOD hou.%s hasattr=%r in_dir=%r -> %s" % (nm, ha, ind, "EXISTS" if ha else "ABSENT"))

print("=== PROBE END ===")
