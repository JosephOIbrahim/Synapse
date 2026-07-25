"""L2: locate the hou.PermissionError raised by import_megascans on 22.0.368."""
import sys, traceback, json
from pathlib import Path
_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "python"))
import hou
from synapse.validation.solaris import verify_wiring_common as common

net = hou.node("/stage").createNode("lopnet", "l2_mega")
tool = common.load_tool("import_megascans")
try:
    tool.execute({"parent": net.path(), "parent_path": net.path(),
                  "asset_name": "l2asset", "usdc_path": "$HIP/x.usdc"})
    print("NO ERROR")
except Exception:
    traceback.print_exc()

# is componentgeometry's interior editable at all?
g = net.createNode("componentgeometry", "probe")
print("PROBE isNetwork:", g.isNetwork(), "matchesDef:", g.matchesCurrentDefinition())
print("children:", [c.name() for c in g.children()])
try:
    g.createNode("null", "l2_probe_null")
    print("createNode inside componentgeometry: OK")
except Exception as e:
    print("createNode inside componentgeometry: FAILS ->", type(e).__name__, str(e)[:200])
try:
    inner = g.node("sopnet/geo")
    print("sopnet/geo:", inner)
    if inner:
        inner.createNode("null", "l2_ok")
        print("createNode inside sopnet/geo: OK")
except Exception as e:
    print("sopnet/geo path:", type(e).__name__, str(e)[:200])
