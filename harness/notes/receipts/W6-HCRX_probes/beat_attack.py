import importlib.util, os, shutil, tempfile
STAGE = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
spec = importlib.util.spec_from_file_location("cc", os.path.join(STAGE,"harness","verify","checks.py"))
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
def ctx(wt): return {"wt": str(wt), "hython": "", "mode": "A"}
def run(wt): return checks.check_runtime_owns_heartbeat(ctx(wt))
results=[]
def rec(tag, expect_red, res, note=""):
    red = res["ok"] is False
    results.append((tag, "RED" if expect_red else "GREEN", "RED" if red else ("GREEN" if res["ok"] else "None"),
                    "PASS" if red==expect_red else "**MISS**", res["detail"][:170], note))

# 0. Baseline on the REAL combined tree — the behavioural proof runs for REAL (not stubbed)
rec("baseline-combined-real-behavioural-proof", False, run(STAGE), "runs _beat_behaviour_proof first-hand")

# Form 1 (structural): simulate ORIGINAL panel-parented wiring -> leg1 RED
d1 = tempfile.mkdtemp(prefix="beat1_")
os.makedirs(os.path.join(d1,"python/synapse/panel"), exist_ok=True)
open(os.path.join(d1,"python/synapse/panel/synapse_panel.py"),"w",encoding="utf-8").write(
    "class SynapsePanel:\n"
    "    def __init__(self):\n"
    "        self._freeze_timer = QTimer(self)\n"          # THE ORIGINAL DEFECT (R.2/P0.3)
    "        self._freeze_timer.setInterval(1000)\n")
rec("Form1: panel-parented QTimer (original defect)", True, run(d1), "structural leg1")

# Form 2 (BEHAVIOURAL): full package, marker+detach intact, but the beat HOLLOWED -> leg3 RED
d2 = os.path.join(tempfile.mkdtemp(prefix="beat2_"), "wt")
shutil.copytree(os.path.join(STAGE,"python"), os.path.join(d2,"python"))
rb = os.path.join(d2,"python/synapse/server/runtime_beat.py")
s = open(rb,encoding="utf-8").read()
assert "# RUNTIME_BEAT_SOURCE" in s
# hollow ONLY the beat feed; keep marker + ensure_beat_started + detach_panel intact
old = "        from .freeze_chain import beat\n        beat()"
assert old in s, "hollow target not found"
s2 = s.replace(old, "        pass  # HOLLOW BEAT: marker kept, chain no longer fed", 1)
open(rb,"w",encoding="utf-8").write(s2)
# confirm structural legs still pass (marker present, panel clean) so only the behaviour differs
still_marker = "# RUNTIME_BEAT_SOURCE" in open(rb,encoding="utf-8").read()
rec("Form2: hollow beat, marker kept (S3/F5 kill)", True, run(d2), "behavioural leg3; marker-still-present=%s" % still_marker)

print("%-48s %-7s %-6s %-8s" % ("attack","expect","got","verdict"))
print("-"*100)
for tag,exp,got,verdict,detail,note in results:
    print("%-48s %-7s %-6s %-8s" % (tag,exp,got,verdict))
    if note: print("      note: %s" % note)
    print("      detail: %s" % detail)
print("-"*100)
