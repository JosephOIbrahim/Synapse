"""What did Houdini 22 actually add? Read SideFX's own release notes.

S0 established there is no LLM/agent/MCP surface in 22.0.368 - a proven absence.
This asks the complementary question: what DID move, so a report on "the
frontier" is grounded in the vendor's own account rather than in what we happen
to have built.
"""
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


for fn in sorted(os.listdir(os.path.join(C, "news", "22"))):
    p = os.path.join(C, "news", "22", fn)
    d = json.load(open(p, encoding="utf-8", errors="replace"))
    txt = " ".join(flat(d, []))
    print("=" * 74)
    print(fn, "|", len(txt), "chars")
    print("=" * 74)
    print("title:", str(d.get("title"))[:120])
    print()
    # The headings carry the shape of the release
    heads = re.findall(r"#+\s*([A-Z][^#\n]{4,70})", txt)
    seen = []
    for h in heads:
        h = h.strip()
        if h not in seen:
            seen.append(h)
    for h in seen[:40]:
        print("   ", h[:90])
    print()
