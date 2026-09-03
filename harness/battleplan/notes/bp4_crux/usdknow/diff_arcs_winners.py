"""BP4-CRUX USDKNOW: normalize + diff builder stdout vs crux stdout, section by section."""
import re, sys, difflib

B = sys.argv[1]  # builder
C = sys.argv[2]  # crux

def load(p):
    return open(p, encoding="utf-8").read().split("\n")

def norm(ln):
    s = ln
    s = re.sub(r"anon:[0-9A-Fa-f]+:", "anon:<ID>:", s)
    s = re.sub(r"bp4_livrps_[A-Za-z0-9_]+", "bp4_livrps_<TMP>", s)
    # absolute usdc path in either slash flavour
    s = s.replace("\\", "/")
    s = re.sub(r"[A-Za-z]:/[^ ,]*b6_wl_component\.usdc", "<USDC>", s)
    s = re.sub(r"[A-Za-z]:/Users/[^ ]*?/Temp/", "<TMP>/", s)
    return s.rstrip()

bl, cl = load(B), load(C)
nb, nc = [norm(x) for x in bl], [norm(x) for x in cl]

def report(label, pred):
    """pred(line)->bool selects lines; compares the selected sequences."""
    bs = [(i+1, s) for i, s in enumerate(nb) if pred(s)]
    cs = [(i+1, s) for i, s in enumerate(nc) if pred(s)]
    same_text = [s for _, s in bs] == [s for _, s in cs]
    same_lineno = [i for i, _ in bs] == [i for i, _ in cs]
    print("\n### {}  (builder {} lines / crux {} lines)".format(label, len(bs), len(cs)))
    if same_text and same_lineno:
        print("VERDICT: identical (same text AND same line numbers)")
    elif same_text:
        print("VERDICT: text identical, LINE NUMBERS DIFFER")
        print("  builder linenos:", [i for i, _ in bs])
        print("  crux    linenos:", [i for i, _ in cs])
    else:
        print("VERDICT: DIFFERENT")
        for d in difflib.unified_diff([s for _, s in bs], [s for _, s in cs],
                                      "builder", "crux", lineterm="", n=1):
            print("  " + d)
    return same_text and same_lineno

results = {}
# (i) per-prim table rows: indented lines starting with a '/' path, inside part A
results["per_prim_table"] = report(
    "(i) per-prim table rows",
    lambda s: s.startswith("  /") and "|" in s)
# (ii) every [BP4-EV:...] line
results["ev_lines"] = report(
    "(ii) [BP4-EV:...] evidence lines",
    lambda s: s.lstrip().startswith("[BP4-EV:"))
# (iii) prim counts lines
results["payload_counts"] = report(
    "(iii) prim counts / reference prim counts / composed arcs",
    lambda s: ("prim counts:" in s) or ("composed arcs on" in s) or ("payload target:" in s))
# (iv) arc order strong->weak
results["arc_order"] = report(
    "(iv) arc order strong->weak",
    lambda s: "arc order strong->weak:" in s or "composed /Test.intensity" in s)
# (v) C.1 / C.2 result lines
results["c1_c2"] = report(
    "(v) C.1/C.2 result lines",
    lambda s: ("spot1.intensity" in s) or ("deep-dive L138 claims" in s)
              or ("/Obj inherits" in s) or ("'first added = strongest'" in s))
# bonus: P-0 build pin
results["build_pin"] = report(
    "(bonus) P-0 build pin + part A header facts",
    lambda s: s.startswith("  USD:") or s.startswith("  Houdini:")
              or s.startswith("  pref_dir(") or s.startswith("  bytes:")
              or s.startswith("  defaultPrim:") or s.startswith("  root prims:"))
# whole-file normalized diff
print("\n### WHOLE-FILE normalized diff")
wd = list(difflib.unified_diff(nb, nc, "builder", "crux", lineterm="", n=0))
if not wd:
    print("VERDICT: whole normalized file IDENTICAL ({} lines each)".format(len(nb)))
    results["whole_file"] = True
else:
    print("VERDICT: DIFFERENT ({} diff lines)".format(len(wd)))
    for d in wd:
        print("  " + d)
    results["whole_file"] = False

print("\n### SUMMARY")
for k, v in results.items():
    print("  {:20} {}".format(k, "identical" if v else "DIFFERENT"))
