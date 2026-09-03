"""BP4-CRUX USDKNOW T-D: independent per-row anchor verification.
Does NOT use the builder's checker. Own parsing, own assertions, both stdouts."""
import json, os, re, sys

SEED = "harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json"
BUILDER = "harness/notes/h22wl/bp4_usdknow/stdout.txt"
CRUX = "crux_usdknow_out/stdout.txt"
BP = "docs/intake/blueprint-h22-worldlabs-intent.md"
PROMOTABLE = {"VERIFIED-RUNTIME", "FIXTURE-VERIFIED"}

seed = json.load(open(SEED, encoding="utf-8"))
b = open(BUILDER, encoding="utf-8").read().split("\n")
c = open(CRUX, encoding="utf-8").read().split("\n")
bp = open(BP, encoding="utf-8").read().split("\n")

# blueprint heading index: "### 2.5 ..." -> line no
head = {}
for i, ln in enumerate(bp, 1):
    m = re.match(r"^#{2,4}\s+(\d+(?:\.\d+)*)\s", ln)
    if m:
        head.setdefault(m.group(1), (i, ln.strip()))

print("=" * 100)
print("T-D1  PROMOTABLE ROWS (independent check, builder stdout AND crux stdout)")
print("=" * 100)
print("{:<46} {:<17} {:<7} {:<11} {:<8} {:<8}".format(
    "row id", "tier", "anchor", "arc", "builder", "crux"))
prom_ok = prom_n = 0
fails = []
for r in seed["rows"]:
    tier = r["tier"]
    if tier not in PROMOTABLE:
        continue
    prom_n += 1
    rid, arc, ver, anc = r["id"], r["arc"], r["verify"], r["anchor"]
    m = re.fullmatch(r"stdout\.txt:(\d+)", anc.strip())
    if not m:
        fails.append((rid, "anchor not stdout.txt:N -> " + anc)); res_b = res_c = "BADANCH"
        print("{:<46} {:<17} {:<7} {:<11} {:<8} {:<8}".format(rid[:46], tier, anc[:7], arc, res_b, res_c))
        continue
    n = int(m.group(1))
    def judge(lines, label):
        if n < 1 or n > len(lines):
            return "RANGE"
        ln = lines[n - 1]
        if not ln.strip():
            return "BLANK"
        ok_arc = ("arc=" + arc) in ln
        ok_ver = ver in ln
        if ok_arc and ok_ver:
            return "PASS"
        miss = []
        if not ok_arc: miss.append("arc")
        if not ok_ver: miss.append("verify")
        fails.append((rid, "{} missing {} on line {}".format(label, "+".join(miss), n)))
        return "FAIL:" + "+".join(miss)
    rb, rc = judge(b, "builder"), judge(c, "crux")
    if rb == "PASS" and rc == "PASS":
        prom_ok += 1
    print("{:<46} {:<17} {:<7} {:<11} {:<8} {:<8}".format(rid[:46], tier, str(n), arc, rb, rc))
print("\npromotable: {}/{} PASS on BOTH stdouts".format(prom_ok, prom_n))
for rid, why in fails:
    print("  FAIL {}: {}".format(rid, why))

print()
print("=" * 100)
print("T-D2  DOC-ANCHORED ROWS (PROPOSED / DOC-STATED) -- does the cited section exist?")
print("=" * 100)
doc_ok = doc_n = 0
for r in seed["rows"]:
    tier = r["tier"]
    if tier in PROMOTABLE:
        continue
    doc_n += 1
    rid, anc = r["id"], r["anchor"]
    # pull every #<sec> fragment out of the anchor
    secs = re.findall(r"#(\d+(?:\.\d+)*)", anc)
    extras = re.findall(r"#\d+(?:\.\d+)*-([A-Za-z0-9.]+)", anc)
    if not secs:
        print("{:<42} {:<11} anchor={!r}\n    -> NO SECTION REF (prose/reasoning anchor)"
              .format(rid[:42], tier, anc))
        continue
    verdicts = []
    for s in secs:
        if s in head:
            verdicts.append("{} EXISTS (L{} {!r})".format(s, head[s][0], head[s][1][:52]))
        else:
            verdicts.append("{} MISSING".format(s))
    # extras like 'D2.7', 'property1', 'property3' -> grep the cited section body
    extra_v = []
    for e in extras:
        if not secs:
            continue
        sec = secs[0]
        if sec not in head:
            extra_v.append("{}: section {} missing".format(e, sec)); continue
        start = head[sec][0]
        # section body ends at next heading of same-or-higher level
        end = len(bp)
        for i in range(start, len(bp)):
            if re.match(r"^#{2,4}\s", bp[i]) and i + 1 > start:
                end = i; break
        body = "\n".join(bp[start:end])
        extra_v.append("{} {} in sec {} body".format(e, "FOUND" if e in body else "NOT FOUND", sec))
    allok = all("EXISTS" in v for v in verdicts) and all("NOT FOUND" not in v and "missing" not in v for v in extra_v)
    if allok:
        doc_ok += 1
    print("{:<42} {:<11} anchor={}".format(rid[:42], tier, anc))
    for v in verdicts: print("    section {}".format(v))
    for v in extra_v: print("    sub-ref {}".format(v))
    print("    -> {}".format("RESOLVES" if allok else "DOES NOT FULLY RESOLVE"))
print("\ndoc-anchored: {}/{} fully resolve".format(doc_ok, doc_n))
