import importlib.util, os, sys
STAGE = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
wt = sys.argv[1] if len(sys.argv)>1 else STAGE
spec = importlib.util.spec_from_file_location("cc", os.path.join(STAGE,"harness","verify","checks.py"))
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
ctx = {"wt": wt, "hython": "", "mode": "A"}
GUARDRAILS = ["scout_no_apex_corpus","no_rigging_drift","provenance_not_bypassed","phantom_clean","suite_baseline"]
print("guardrails on wt=%s" % wt)
print("%-26s %-7s %s" % ("guardrail","ok","detail(120)"))
print("-"*100)
violations=[]
for g in GUARDRAILS:
    fn = checks.DISPATCH.get(g)
    if fn is None: print("%-26s MISSING" % g); continue
    try:
        r = fn(ctx)
    except Exception as e:
        r = {"ok": None, "detail": "EXC %s: %s" % (type(e).__name__, str(e)[:80])}
    ok = r.get("ok")
    if ok is False: violations.append(g)
    print("%-26s %-7s %s" % (g, str(ok), (r.get("detail") or "")[:120]))
print("-"*100)
print("guardrail_violations (ok:False):", violations if violations else "NONE")
