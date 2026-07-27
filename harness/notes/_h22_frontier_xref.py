"""Cross-reference H22's NEW Copernicus nodes against what SYNAPSE grounds.

The what's-new index lists 18 areas. Copernicus is the one with a dedicated
45KB page, and S0 established H22 shipped no agent surface - so the frontier
question is not "what AI did SideFX add" but "what did SideFX add that an
assistant must understand".

This measures the gap directly rather than asserting it.
"""
import json, os, re, glob

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


# --- 1. the NEW cop node types named in the what's-new page ---------------
txt = " ".join(flat(json.load(open(os.path.join(C, "news", "22", "copernicus.json"),
                                  encoding="utf-8", errors="replace")), []))
new_cops = sorted(set(re.findall(r"/nodes//cop/([a-z0-9_]+)", txt)))
print("NEW Copernicus nodes named in What's New :", len(new_cops))
print("  sample:", ", ".join(new_cops[:10]))
print()

# --- 2. every cop page that exists in the shipped node reference -----------
cop_dir = os.path.join(C, "nodes", "cop")
all_cops = []
if os.path.isdir(cop_dir):
    all_cops = sorted(f[:-5] for f in os.listdir(cop_dir) if f.endswith(".json"))
print("Copernicus node pages in the reference  :", len(all_cops))
print()

# --- 3. what SYNAPSE grounds ----------------------------------------------
grounded = set()
for p in glob.glob("harness/notes/h22_cop_catalog*.json") + \
         glob.glob("harness/notes/h22_doc_grounding_corpus.json"):
    try:
        blob = open(p, encoding="utf-8", errors="replace").read()
    except Exception:
        continue
    for n in all_cops:
        if '"%s"' % n in blob or "/cop/%s" % n in blob:
            grounded.add(n)

known_new = [n for n in new_cops if n in grounded]
print("SYNAPSE grounds, of the NEW nodes        : %d / %d  (%.0f%%)"
      % (len(known_new), len(new_cops), 100.0 * len(known_new) / max(len(new_cops), 1)))
print("SYNAPSE grounds, of ALL cop pages        : %d / %d  (%.0f%%)"
      % (len(grounded), len(all_cops), 100.0 * len(grounded) / max(len(all_cops), 1)))
print()
missing = [n for n in new_cops if n not in grounded]
print("NEW and ungrounded (%d):" % len(missing))
for n in missing[:22]:
    print("   ", n)
