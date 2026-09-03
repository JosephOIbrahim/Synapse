"""Split the 174 panel-wide literal-typography hits into TRULY hardcoded vs
%-interpolated (token-fed) — fairness pass so the crux does not overcount."""
import os, re, sys
ROOT = sys.argv[1]
PANEL = os.path.join(ROOT, "python", "synapse", "panel")
LIT = re.compile(r"font-(?:size|weight|family)\s*:\s*(?!\{)[^\s;\n]")
def strip(s): return re.sub(r"/\*.*?\*/", "", s, flags=re.DOTALL)
hard, interp = [], []
for dp, _dn, fn in os.walk(PANEL):
    for f in sorted(fn):
        if not f.endswith(".py"): continue
        p = os.path.join(dp, f); rel = os.path.relpath(p, ROOT).replace("\\","/")
        body = strip(open(p, encoding="utf-8").read())
        for m in LIT.finditer(body):
            ln = body[:m.start()].count("\n") + 1
            seg = body[m.start():].split(";",1)[0].split("\n",1)[0].strip()
            val = seg.split(":",1)[1].strip() if ":" in seg else seg
            (interp if val.startswith("%") else hard).append((rel, ln, seg[:70]))
print("TRULY HARDCODED (value is a literal) =", len(hard))
print("%-INTERPOLATED (token-fed at runtime) =", len(interp))
print("TOTAL =", len(hard)+len(interp))
print()
print("--- %-interpolated, per file ---")
c={}
for r,_l,_s in interp: c[r]=c.get(r,0)+1
for r,n in sorted(c.items(), key=lambda x:-x[1]): print(f"{n:5d}  {r}")
print()
print("--- TRULY HARDCODED per file (top 20) ---")
c={}
for r,_l,_s in hard: c[r]=c.get(r,0)+1
for r,n in sorted(c.items(), key=lambda x:-x[1])[:20]: print(f"{n:5d}  {r}")
print()
print("--- 12 sample truly-hardcoded rows ---")
for r,l,s in hard[:12]: print(f"   {r}:{l}: {s}")
