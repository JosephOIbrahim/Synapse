"""S1 scout: build the tool -> command_type -> handler cross-reference.

Read-only. Emits scratchpad/inventory_raw.json.
"""
import ast
import json
import os
import re
import sys

REPO = r"C:\Users\User\SYNAPSE"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "s1_artifacts", "registry_xref.json")

sys.path.insert(0, os.path.join(REPO, "python"))
from synapse.mcp import _tool_registry as R  # noqa: E402

tools = []
for name, cmd, builder, desc, schema, ro, destr, idemp in R.TOOL_DEFS:
    tools.append({
        "tool": name,
        "cmd": cmd,
        "desc": desc,
        "read_only": ro,
        "destructive": destr,
        "idempotent": idemp,
        "payload_builder": getattr(builder, "__qualname__", str(builder)),
    })

# ---- handler registrations -------------------------------------------------
SERVER = os.path.join(REPO, "python", "synapse", "server")
reg_re = re.compile(r"""\.register\(\s*["']([\w.]+)["']\s*,\s*([\w.\[\]"']+)""")

registrations = {}   # cmd -> [ {file, line, target} ]
py_files = []
for root, _dirs, files in os.walk(SERVER):
    if "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            py_files.append(os.path.join(root, f))

for path in py_files:
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            m = reg_re.search(line)
            if m:
                cmd, target = m.group(1), m.group(2)
                registrations.setdefault(cmd, []).append({
                    "file": os.path.relpath(path, REPO).replace("\\", "/"),
                    "line": i,
                    "target": target,
                })

# ---- resolve handler function definitions ---------------------------------
# map "method name" -> file:line of its def, across the whole server package
defs = {}   # simple name -> [ (file, line) ]
for path in py_files:
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except Exception:
        continue
    rel = os.path.relpath(path, REPO).replace("\\", "/")
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, []).append({
                "file": rel, "line": node.lineno,
                "end": getattr(node, "end_lineno", None),
            })

# also scan the whole python/synapse tree for handler defs that live elsewhere
SYN = os.path.join(REPO, "python", "synapse")
for root, _dirs, files in os.walk(SYN):
    if "__pycache__" in root or "_vendor" in root:
        continue
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        if path in py_files:
            continue
        try:
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
        except Exception:
            continue
        rel = os.path.relpath(path, REPO).replace("\\", "/")
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, []).append({
                    "file": rel, "line": node.lineno,
                    "end": getattr(node, "end_lineno", None),
                })

for t in tools:
    regs = registrations.get(t["cmd"], [])
    t["registrations"] = regs
    impls = []
    for r in regs:
        simple = r["target"].split(".")[-1].strip("'\"")
        for d in defs.get(simple, []):
            impls.append({"name": simple, **d})
    t["impls"] = impls
    t["reachable_static"] = bool(regs)

unmatched_cmds = sorted(set(registrations) - {t["cmd"] for t in tools})

payload = {
    "tool_count": len(tools),
    "registered_cmds": len(registrations),
    "tools": tools,
    "handler_cmds_with_no_tool": unmatched_cmds,
    "pending_tool_names": R.PENDING_TOOL_NAMES,
}
with open(OUT, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=1)

missing = [t["tool"] for t in tools if not t["reachable_static"]]
print("tools:", len(tools))
print("distinct cmd_types in tools:", len({t['cmd'] for t in tools}))
print("registered cmds:", len(registrations))
print("TOOLS WITH NO HANDLER REGISTRATION:", missing)
print("handler cmds with no tool:", len(unmatched_cmds))
print("wrote", OUT)
