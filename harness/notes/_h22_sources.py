import json, os, re

C = r"C:\Users\User\OneDrive\Documents\houdini22.0\config\Help\cache"


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


def load(*parts):
    p = os.path.join(C, *parts)
    if not os.path.exists(p):
        return None
    return " ".join(" ".join(flat(json.load(open(p, encoding="utf-8", errors="replace")), [])).split())


# --- solaris glossary: the vocabulary an assistant must speak -------------
g = load("solaris", "glossary.json")
if g:
    terms = re.findall(r"term\s+([A-Z][A-Za-z /-]{2,40})", g)
    seen = []
    for t in terms:
        t = t.strip()
        if t not in seen:
            seen.append(t)
    print("SOLARIS GLOSSARY  %d KB, ~%d distinct terms" % (len(g) / 1024, len(seen)))
    print("  ", ", ".join(seen[:26]))
    print()

# --- ml/train_solutions ---------------------------------------------------
d = os.path.join(C, "ml", "train_solutions")
if os.path.isdir(d):
    print("ML / TRAIN_SOLUTIONS")
    for fn in sorted(os.listdir(d)):
        t = load("ml", "train_solutions", fn) or ""
        print("   %-26s %5d chars" % (fn, len(t)))
        print("      ", t[:260])
    print()

# --- vex cop2 context -----------------------------------------------------
v = load("vex", "contexts", "cop2.json")
if v:
    fns = sorted(set(re.findall(r"\b([a-z][a-z0-9_]{3,})\s*\(", v)))
    print("VEX cop2 CONTEXT  %d KB, %d function-shaped tokens" % (len(v) / 1024, len(fns)))
    print("  ", ", ".join(fns[:20]))
    print()

# --- glsl -----------------------------------------------------------------
s = load("shade", "glsl.json")
if s:
    print("SHADE / GLSL      %d KB" % (len(s) / 1024))
    print("  ", s[:240])
    print()

# --- examples/nodes -------------------------------------------------------
e = os.path.join(C, "examples", "nodes")
if os.path.isdir(e):
    ctx = {}
    for root, _, files in os.walk(e):
        for f in files:
            k = os.path.basename(root)
            ctx[k] = ctx.get(k, 0) + 1
    print("EXAMPLES / NODES  by context:", dict(sorted(ctx.items(), key=lambda x: -x[1])[:8]))
