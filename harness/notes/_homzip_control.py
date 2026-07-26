"""Same control, against the SHIPPED hom.zip rather than the browsing cache.

The cache failed: 101 symbols, no RopNode, no TopNode - it holds only pages
someone opened. A symbol missing from it means "nobody looked", not
"undocumented", and conflating those is the exact defect H5 exists to prevent.

hom.zip ships with 22.0.368, so it is version-pinned by construction and needs
no network. If it reproduces both known answers it is a usable oracle.
"""
import zipfile, re, os

Z = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\hom.zip"

with zipfile.ZipFile(Z) as z:
    names = z.namelist()
    print("entries:", len(names))
    ext = {}
    for n in names:
        e = os.path.splitext(n)[1].lower()
        ext[e] = ext.get(e, 0) + 1
    print("extensions:", dict(sorted(ext.items(), key=lambda x: -x[1])[:6]))
    print()

    rop = [n for n in names if re.search(r"RopNode", n)]
    top = [n for n in names if re.search(r"TopNode", n)]
    print("RopNode entries:", rop[:4])
    print("TopNode entries:", top[:4])
    print()

    def read(entry):
        try:
            return z.read(entry).decode("utf-8", errors="replace")
        except Exception as e:
            return ""

    print("=" * 62)
    print("CONTROL 1  RopNode - expect NO cancel verb")
    print("=" * 62)
    if rop:
        t = read(rop[0])
        print("  entry:", rop[0], "|", len(t), "chars")
        hits = sorted(set(re.findall(r"\b(\w*(?:cancel|abort|interrupt|kill|terminate)\w*)\b", t, re.I)))
        print("  CANCEL-LIKE TOKENS:", hits if hits else "NONE  <- matches live probe")
        print("  has render:", bool(re.search(r"\brender\b", t)))
    else:
        print("  no RopNode entry")

    print()
    print("=" * 62)
    print("CONTROL 2  TopNode.dirtyAllTasks - expect DEPRECATED")
    print("=" * 62)
    if top:
        t = read(top[0])
        print("  entry:", top[0], "|", len(t), "chars")
        i = t.lower().find("dirtyalltasks")
        if i < 0:
            print("  dirtyAllTasks NOT MENTIONED")
        else:
            w = t[max(0, i - 200):i + 400]
            dep = "deprecat" in w.lower()
            print("  DEPRECATION NOTED:", dep, "<- matches runtime" if dep else "<- MISS")
            print("  ...", " ".join(w.split())[:300])

    print()
    print("=" * 62)
    print("DEPRECATION COVERAGE ACROSS THE WHOLE REFERENCE")
    print("=" * 62)
    dep = 0
    for n in names:
        if n.endswith("/"):
            continue
        if "deprecat" in read(n).lower():
            dep += 1
    print("  entries mentioning deprecation:", dep, "of", len(names))
