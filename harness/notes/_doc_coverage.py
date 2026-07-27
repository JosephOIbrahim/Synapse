"""Can local docs lift LOP and COP grounding? Measure coverage, do not guess.

Grounding is D2 union D3. D2 is semantic - what a node is FOR, its parms, its
intent. That is exactly what authored documentation supplies. D3 is behavioural
and only probes can supply it.

So the question is precise: for how many of the 218 LOP and 384 Cop types does
the shipped reference carry a page, and how substantial is it?

A page that exists but is a stub is not grounding. Measure size too.
"""
import zipfile, os, json, statistics

Z = r"C:\Program Files\Side Effects Software\Houdini 22.0.368\houdini\help\nodes.zip"

with zipfile.ZipFile(Z) as z:
    infos = [i for i in z.infolist() if not i.is_dir()]
    print("entries:", len(infos))

    by_ctx = {}
    for i in infos:
        parts = i.filename.split("/")
        if len(parts) >= 2:
            by_ctx.setdefault(parts[0], []).append(i)
    print("\nCONTEXTS:")
    for c, items in sorted(by_ctx.items(), key=lambda x: -len(x[1]))[:14]:
        sizes = [x.file_size for x in items]
        print("  %-14s %4d pages   median %5d B   total %6.1f KB"
              % (c, len(items), int(statistics.median(sizes)), sum(sizes) / 1024))

# Compare against the live catalogues this project already probed
for cat, ctxkeys in (("h22_lop_catalog_live_22.0.368.json", ("lop",)),
                     ("h22_cop_catalog_live_22.0.368.json", ("cop", "cop2"))):
    p = os.path.join("harness", "notes", cat)
    if not os.path.exists(p):
        print("\n%s NOT FOUND - cannot compare" % cat)
        continue
    d = json.load(open(p, encoding="utf-8", errors="replace"))
    # find the type-name list whatever its shape
    names = []
    def harvest(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("types", "node_types", "entries", "catalog") and isinstance(v, (list, dict)):
                    if isinstance(v, dict):
                        names.extend(v.keys())
                    else:
                        for e in v:
                            if isinstance(e, str):
                                names.append(e)
                            elif isinstance(e, dict):
                                for kk in ("name", "type", "type_name", "node_type"):
                                    if kk in e:
                                        names.append(e[kk]); break
                else:
                    harvest(v)
        elif isinstance(o, list):
            for v in o:
                harvest(v)
    harvest(d)
    names = sorted(set(n.split("::")[-1].lower() for n in names if isinstance(n, str)))
    print("\n%s -> %d live types" % (cat.split("_")[1].upper(), len(names)))
    if not names:
        continue
    with zipfile.ZipFile(Z) as z:
        have = set()
        for ck in ctxkeys:
            for i in z.infolist():
                if i.filename.startswith(ck + "/") and i.file_size > 0:
                    base = os.path.splitext(os.path.basename(i.filename))[0].lower()
                    have.add(base)
        hit = [n for n in names if n in have]
        print("  pages present : %d / %d  = %.0f%%" % (len(hit), len(names), 100 * len(hit) / len(names)))
        missing = [n for n in names if n not in have]
        print("  missing sample:", missing[:10])
