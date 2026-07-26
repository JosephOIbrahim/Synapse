"""Does ANY cancel path for a render exist in the H22 reference?

R58 and R72 confirmed hou.RopNode has no cancel method. The SideFX ask makes a
BROADER claim: Houdini exposes no way to cancel an in-flight render. Different
claims - only the narrow one was tested.

R50: ABSENT requires a positive control ON THE SAME CLASS. The class the ask
speaks about is the whole HOM surface plus the ROP node docs, not one class.

Both sources local, version-pinned to 22.0.368.
"""
import zipfile, json, os, re

Z = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\hom.zip"
CACHE = r"C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache"

VERB = re.compile(r"cancel|abort|interrupt|kill|terminate|halt", re.I)
RENDER = re.compile(r"render|rop|cook|karma|mantra|husk", re.I)

print("=" * 72)
print("A. HOM SURFACE - cancel-verb lines that ALSO mention rendering")
print("=" * 72)
with zipfile.ZipFile(Z) as z:
    names = [n for n in z.namelist() if n.endswith(".txt")]
    total, rel, seen = 0, [], set()
    for n in names:
        t = z.read(n).decode("utf-8", errors="replace")
        for m in VERB.finditer(t):
            total += 1
            ls = t.rfind("\n", 0, m.start()) + 1
            le = t.find("\n", m.end())
            line = t[ls:le if le > 0 else len(t)].strip()
            if RENDER.search(line):
                k = (n, line[:70])
                if k not in seen:
                    seen.add(k)
                    rel.append((n, line))
    print("  %d cancel-like mentions across %d of %d entries" %
          (total, len(set(n for n, _ in rel)) or 0, len(names)))
    print("  %d sit on a line that also mentions render/rop/cook/karma/husk:" % len(rel))
    for n, line in rel[:25]:
        print("   [%s] %s" % (n, line[:130]))

print()
print("=" * 72)
print("B. RENDER-ADJACENT NODE DOCS mentioning a cancel verb")
print("=" * 72)

def flat(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            flat(v, out)
    elif isinstance(o, list):
        for v in o:
            flat(v, out)
    return out

hits = 0
for root, _, files in os.walk(CACHE):
    if (os.sep + "nodes" + os.sep) not in (root + os.sep).lower():
        continue
    parent = os.path.basename(root).lower()
    for f in files:
        if not f.endswith(".json"):
            continue
        base = f[:-5].lower()
        if parent not in ("out", "rop", "lop", "top") and not RENDER.search(base):
            continue
        p = os.path.join(root, f)
        try:
            t = " ".join(flat(json.load(open(p, encoding="utf-8", errors="replace")), []))
        except Exception:
            continue
        m = VERB.search(t)
        if m:
            w = " ".join(t[max(0, m.start() - 100):m.start() + 160].split())
            print("   [%s/%s] %s" % (parent, base, w[:155]))
            hits += 1
print("  %d render-adjacent node docs mention a cancel verb" % hits)
