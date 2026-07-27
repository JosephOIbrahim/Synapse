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


# --- what's new, top level -------------------------------------------------
d = json.load(open(os.path.join(C, "news", "22", "index.json"), encoding="utf-8", errors="replace"))
txt = " ".join(" ".join(flat(d, [])).split())
print("=" * 72)
print("WHAT'S NEW IN HOUDINI 22 - the index")
print("=" * 72)
print(txt[:1500])
print()

# --- copernicus: the only dedicated page -----------------------------------
d = json.load(open(os.path.join(C, "news", "22", "copernicus.json"), encoding="utf-8", errors="replace"))
txt = " ".join(" ".join(flat(d, [])).split())
print("=" * 72)
print("COPERNICUS - 45KB, the only dedicated what's-new page")
print("=" * 72)
print(txt[:2600])
