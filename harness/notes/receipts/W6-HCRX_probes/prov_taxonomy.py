import importlib.util, os, shutil, tempfile, re
STAGE = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
spec = importlib.util.spec_from_file_location("cc", os.path.join(STAGE,"harness","verify","checks.py"))
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
def run(wt): return checks.check_provenance_not_bypassed({"wt": str(wt), "hython": "", "mode": "A"})
d = tempfile.mkdtemp(prefix="provtax_")
shutil.copytree(os.path.join(STAGE,"python/synapse/server"), os.path.join(d,"python/synapse/server"), dirs_exist_ok=True)
os.makedirs(os.path.join(d,"python/synapse/core"), exist_ok=True)
shutil.copy2(os.path.join(STAGE,"python/synapse/core/floor_gate.py"), os.path.join(d,"python/synapse/core/floor_gate.py"))
print("baseline (clean real surface):", run(d)["ok"])
hp = os.path.join(d,"python/synapse/server/handlers.py"); s = open(hp,encoding="utf-8").read()
# locate the frozenset literal for _READ_ONLY_COMMANDS and inject two mutating cmds
m = re.search(r"_READ_ONLY_COMMANDS\s*[:=].*?frozenset\(", s)
if not m:
    m = re.search(r"_READ_ONLY_COMMANDS\s*=\s*\{", s)
print("found _READ_ONLY_COMMANDS literal:", bool(m))
# inject after the first '{' or '(' following the name by adding two entries at the set's start
inj = re.sub(r"(_READ_ONLY_COMMANDS\s*[:=]\s*(?:frozenset\(\s*)?[\{\(])",
             r'\1"create_node", "set_parm", "connect_nodes", ', s, count=1)
changed = inj != s
open(hp,"w",encoding="utf-8").write(inj)
r = run(d)
print("MUTATING CMDS ADDED TO _READ_ONLY_COMMANDS (changed=%s) -> check ok=%s" % (changed, r["ok"]))
print("  detail:", r["detail"][:130])
print()
print("VERDICT:", "CONFIRMED FALSE-GREEN (taxonomy bypass real)" if (r["ok"] is True and changed) else "NOT reproduced")
