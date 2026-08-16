import importlib.util, os, shutil, tempfile
STAGE=r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
spec=importlib.util.spec_from_file_location("cc",os.path.join(STAGE,"harness","verify","checks.py"))
c=importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
def run(wt): return c.check_runtime_owns_heartbeat({"wt":str(wt),"hython":"","mode":"A"})
d=os.path.join(tempfile.mkdtemp(prefix="beatinc_"),"wt")
shutil.copytree(os.path.join(STAGE,"python"),os.path.join(d,"python"))
rb=os.path.join(d,"python/synapse/server/runtime_beat.py"); s=open(rb,encoding="utf-8").read()
# 1. hollow the beat (as Form2)
s=s.replace("        from .freeze_chain import beat\n        beat()","        pass  # HOLLOW",1)
# 2. break the proof subprocess import: unguarded failing import at top (keeps # RUNTIME_BEAT_SOURCE marker)
s="import __nonexistent_module_xyz__  # forces proof subprocess import to raise -> ran=False\n"+s
open(rb,"w",encoding="utf-8").write(s)
assert "# RUNTIME_BEAT_SOURCE" in open(rb,encoding="utf-8").read()
r=run(d)
print("hollow beat + broken proof import -> check ok=%s" % r["ok"])
print("detail:", r["detail"][:160])
print("VERDICT:", "CONFIRMED false-green (INCONCLUSIVE fallback masks a hollow beat)" if r["ok"] is True else "gate held RED")
