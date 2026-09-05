import json, sys, collections
for name in ("expert_340", "curious_340", "ml_340", "expert_280"):
    d = json.load(open("harness/design_review/2026-09-05/type_census_%s.json" % name, encoding="utf-8"))
    s, rows = d["summary"], [r for r in d["rows"] if "error" not in r and r["w"] > 0]
    print("\n########", name, "density", s["density"], "host", s["host_font"], "n(w>0) =", len(rows))
    hist = lambda k: dict(collections.Counter(str(r[k]) for r in rows).most_common())
    print("px      ", hist("px"))
    print("family  ", hist("family"))
    print("weight  ", hist("weight"))
    print("spacing ", dict(collections.Counter("%s:%s" % (r["spacing_type"], r["spacing"]) for r in rows).most_common()))
    print("caps    ", dict(collections.Counter(("AllUpper" if r["caps"] == 1 else ("literalUPPER" if r["text_upper"] and any(c.isalpha() for c in r["text"]) else "mixed")) for r in rows).most_common()))
    print("per-face px:", {f: sorted({r["px"] for r in rows if r["face"] == f}) for f in ("direct_chat", "direct_hda", "work", "token")})
    print("wordmark", {k: s["wordmark"][k] for k in ("w", "hint_w", "min_w", "px", "weight", "spacing")})
    clipped = [r for r in rows if r["hint_w"] > r["w"]]
    print("CLIPPED (w>0):", len(clipped))
    for r in clipped:
        print("   %-12s %-12s %-14s %-28r w=%3d hint=%3d px=%d sp=%s" % (r["face"], r["cls"], r["id"], r["text"], r["w"], r["hint_w"], r["px"], r["spacing"]))
    if name == "expert_340":
        print("-- 10px rows:")
        for r in rows:
            if r["px"] == 10: print("   %-12s %-12s %-14s %-28r fam=%s sp=%s" % (r["face"], r["cls"], r["id"], r["text"], r["family"], r["spacing"]))
        print("-- 14/15px rows:")
        for r in rows:
            if r["px"] >= 14: print("   %-12s %-12s %-14s %-28r fam=%s w=%s sp=%s" % (r["face"], r["cls"], r["id"], r["text"], r["family"], r["weight"], r["spacing"]))
        print("-- host-family (Courier) rows = widgets with NO family applied:")
        for r in rows:
            if r["family"] == "Courier": print("   %-12s %-12s %-14s %-28r px=%s" % (r["face"], r["cls"], r["id"], r["text"], r["px"]))
        print("-- weight 600/700 rows:")
        for r in rows:
            if r["weight"] >= 600: print("   %-12s %-12s %-14s %-28r px=%s w=%s" % (r["face"], r["cls"], r["id"], r["text"], r["px"], r["weight"]))
        print("-- spacing_type 1 (Absolute) rows:")
        for r in rows:
            if r["spacing_type"] == 1: print("   %-12s %-12s %-14s %-28r px=%s sp=%s" % (r["face"], r["cls"], r["id"], r["text"], r["px"], r["spacing"]))
        print("PROBES", json.dumps(s["probes"], indent=1))
