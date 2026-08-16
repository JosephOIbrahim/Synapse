import importlib.util, os, shutil, tempfile, pathlib, sys
STAGE = r"C:/Users/User/AppData/Local/Temp/claude/C--Users-User-SYNAPSE--claude-worktrees-w6-hcrx/b7cb3ce1-8197-4196-aea0-7176b9c8937b/scratchpad/w6combined"
spec = importlib.util.spec_from_file_location("cc", os.path.join(STAGE,"harness","verify","checks.py"))
checks = importlib.util.module_from_spec(spec); spec.loader.exec_module(checks)
def ctx(wt): return {"wt": str(wt), "hython": "", "mode": "A"}
def run(wt): return checks.check_provenance_not_bypassed(ctx(wt))

def real_copy():
    """Copy the REAL product provenance surface into a scratch tree."""
    d = tempfile.mkdtemp(prefix="prov_")
    for rel in ("python/synapse/server/handlers.py", "python/synapse/core/floor_gate.py"):
        src = os.path.join(STAGE, rel); dst = os.path.join(d, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(src): shutil.copy2(src, dst)
    # copy the whole server/ dir so leg-3 rglob sees the real side-door surface
    shutil.copytree(os.path.join(STAGE,"python/synapse/server"), os.path.join(d,"python/synapse/server"), dirs_exist_ok=True)
    return d

def patch(d, rel, old, new, required=True):
    p = os.path.join(d, rel); s = open(p, encoding="utf-8").read()
    if old not in s:
        if required: raise SystemExit("PATCH TARGET MISSING in %s: %r" % (rel, old[:60]))
        return False
    open(p,"w",encoding="utf-8").write(s.replace(old, new, 1)); return True

results = []
def record(tag, expect_red, res, note=""):
    red = (res["ok"] is False)
    status = "RED" if red else ("GREEN" if res["ok"] is True else "None")
    ok = (red == expect_red)
    results.append((tag, "expect "+("RED" if expect_red else "GREEN"), status, "PASS" if ok else "**MISS**", res["detail"][:150], note))

# 0. Baseline: clean real surface -> GREEN
d0 = real_copy(); record("baseline-clean-real-surface", False, run(d0))

# A. FRESH: gate CONSTRUCTED but wrap() bypassed in invoke (M1 built-connected-to-nothing shape)
dA = real_copy()
hp = os.path.join(dA,"python/synapse/server/handlers.py"); hs = open(hp,encoding="utf-8").read()
import re
# find the invoke() wrap call and neutralise ONLY the wrap delegation, keeping the FloorGate() construction
patched = False
if "self._floor_gate.wrap(" in hs:
    hs2 = hs.replace("self._floor_gate.wrap(", "self._DISABLED_wrap(", 1)  # keep construction, kill the ONLY wrap call
    open(hp,"w",encoding="utf-8").write(hs2); patched = True
record("A: gate-constructed-but-wrap-bypassed (M1)", True, run(dA), "patched=%s (FloorGate() kept, wrap call renamed)" % patched)

# A2. FRESH on REAL floor_gate.py: _record kept but write_report persist removed
dA2 = real_copy()
fp = os.path.join(dA2,"python/synapse/core/floor_gate.py"); fs = open(fp,encoding="utf-8").read()
had_wr = "write_report(" in fs
fs2 = re.sub(r"write_report\(", "no_persist_(", fs)
open(fp,"w",encoding="utf-8").write(fs2)
record("A2: real floor_gate write_report removed", True, run(dA2), "had write_report=%s" % had_wr)

# B1. HOLLOW-SPOT PROBE: TWO-LINE get-and-call side door under server/ (regex expects one-line)
dB1 = real_copy()
open(os.path.join(dB1,"python/synapse/server/sneaky_twoline.py"),"w",encoding="utf-8").write(
    "def go(self, cmd, payload):\n"
    "    h = self._registry.get(cmd)\n"     # get on its own line
    "    return h(payload)\n")               # call on the NEXT line -> regex (get(...) immediately-followed-by-'(') misses
record("B1: two-line get-and-call side door", True, run(dB1), "hollow-spot probe: regex expects one-line get(...)(")

# B2. HOLLOW-SPOT PROBE: dict-dispatch bound handler in a NON-handle method under server/
dB2 = real_copy()
open(os.path.join(dB2,"python/synapse/server/sneaky_dict.py"),"w",encoding="utf-8").write(
    "class SideDoor:\n"
    "    def run(self, cmd, payload):\n"
    "        return self._handlers[cmd].handle(payload)\n")  # not _registry.get, not in handle()
record("B2: dict-dispatch bound handler (non-handle)", True, run(dB2), "hollow-spot probe: neither leg-3a regex nor leg-3b handle()-scope")

# print
print("%-45s %-12s %-6s %-7s" % ("attack", "expectation", "got", "verdict"))
print("-"*95)
for tag, exp, got, verdict, detail, note in results:
    print("%-45s %-12s %-6s %-7s" % (tag, exp, got, verdict))
    if note: print("      note: %s" % note)
    print("      detail: %s" % detail)
print("-"*95)
misses = [r for r in results if r[3]!="PASS"]
print("Fresh fail-closed attacks (A, A2) that MUST go RED, and hollow-spot probes (B1,B2):")
for tag,exp,got,verdict,detail,note in results:
    print("  %-45s -> %s (%s)" % (tag, got, verdict))
