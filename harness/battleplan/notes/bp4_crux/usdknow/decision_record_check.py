"""BP4-CRUX USDKNOW T-E: decision-record coverage + citation sweep (independent)."""
import re, sys

DR = "docs/reviews/bp4-usd-composition-worldlabs.md"
B = "harness/notes/h22wl/bp4_usdknow/stdout.txt"
C = "crux_usdknow_out/stdout.txt"

dr = open(DR, encoding="utf-8").read().split("\n")
b = open(B, encoding="utf-8").read().split("\n")
c = open(C, encoding="utf-8").read().split("\n")

# --- split the record into ### sections
secs = {}
order = []
cur = None
for i, ln in enumerate(dr, 1):
    m = re.match(r"^##(#?)\s+(\S+)\s+(.*)$", ln)
    if m:
        cur = m.group(2).rstrip(".")
        secs[cur] = {"title": ln.strip(), "start": i, "body": []}
        order.append(cur)
        continue
    if cur:
        secs[cur]["body"].append(ln)
for k in secs:
    secs[k]["text"] = "\n".join(secs[k]["body"])

T1 = [
    ("2.1", "payload for splat + collider"),
    ("2.2", "purpose render / proxy"),
    ("2.3", "variantSet splatTier full|low"),
    ("2.4", "variantSet physics none|collision"),
    ("2.5", "kind = component"),
    ("2.6", "customData:worldlabs provenance"),
    ("2.7", "instanceable yes/no"),
    ("2.8", "where metric/ground/chirality transforms live"),
]

def cite_ok(n, lines):
    if n < 1 or n > len(lines): return "RANGE"
    return "OK" if lines[n-1].strip() else "BLANK"

print("=" * 118)
print("T-E1  DECISION RECORD COVERAGE (8 T1 choices + section 3)")
print("=" * 118)
print("{:<5} {:<38} {:<7} {:<7} {:<9} {:<26} {}".format(
    "sec", "choice", "arc?", "LIVRPS", "failure?", "tier", "anchors resolve?"))
covered = 0
rows_out = []
for sec, label in T1:
    if sec not in secs:
        print("{:<5} {:<38} SECTION MISSING".format(sec, label)); continue
    t = secs[sec]["text"]
    title = secs[sec]["title"]
    arc = bool(re.search(r"arc\s*=\s*\*\*", title)) or bool(re.search(r"\*\*Chosen", t))
    arcname = re.search(r"arc\s*=\s*\*\*([a-z ]+)\*\*", title)
    arcname = arcname.group(1).strip() if arcname else "-"
    livrps = ("LIVRPS reason" in t)
    # why-not-each-neighbour: count 'not X' bullets or an explicit 'why not'
    neigh = len(re.findall(r"^\s*-\s+\*\*not ", t, re.M)) + len(re.findall(r"why not", t, re.I))
    failure = ("Failure prevented" in t)
    tierm = re.findall(r"\*\*Tier:\*\*\s*\**([A-Z-]+)", t)
    if not tierm:
        tierm = re.findall(r"\*\*Tier:\*\*\s*(?:\*\*)?([A-Z][A-Z-]+)", t)
    tiers = ",".join(sorted(set(tierm))) or "-"
    # every stdout citation inside this section
    cites = [int(x) for x in re.findall(r"stdout\.txt:(\d+)", t)]
    rng = re.findall(r"stdout\.txt:(\d+)-(\d+)", t)
    resolved = all(cite_ok(n, b) == "OK" and cite_ok(n, c) == "OK" for n in cites)
    docanch = ("blueprint §" in t) or ("blueprint sec" in t)
    anchtxt = "{} stdout cites, all resolve={}".format(len(cites), resolved) if cites else \
              ("doc anchor only" if docanch else "NO ANCHOR")
    ok = arc and livrps and neigh >= 1 and failure and tiers != "-" and (resolved if cites else docanch)
    if ok: covered += 1
    print("{:<5} {:<38} {:<7} {:<7} {:<9} {:<26} {}".format(
        sec, label[:38], arcname[:7], "yes({})".format(neigh) if livrps else "NO",
        "yes" if failure else "NO", tiers[:26], anchtxt))
    rows_out.append({"section": sec, "choice": label, "arc": arcname,
                     "livrps_why_not_neighbours": bool(livrps and neigh >= 1),
                     "failure_prevented": failure, "tier": tiers,
                     "anchor": anchtxt, "complete": ok})
print("\ncovered: {}/8".format(covered))

print("\n--- section 3 (blueprint sec.4 / demo) ---")
if "3" in secs:
    t3 = secs["3"]["text"]
    print("  title:", secs["3"]["title"])
    print("  states 'adds no composition arc':", "no composition arc" in secs["3"]["title"] or "authors nothing upstream" in t3)
    print("  cites demo beats:", "Beat 3" in t3, "| fallback F-1:", "Fallback F-1" in t3)
    print("  ties back to 2.1/2.2/2.5/2.8:", all(s in t3 for s in ("§2.1", "§2.2", "§2.5", "§2.8")))
else:
    print("  SECTION 3 MISSING")

print()
print("=" * 118)
print("T-E2  EVERY stdout.txt:N CITATION IN THE DECISION RECORD (unchecked by the committed gate)")
print("=" * 118)
allc = []
for i, ln in enumerate(dr, 1):
    for m in re.finditer(r"stdout\.txt:(\d+)(?:-(\d+))?", ln):
        s = int(m.group(1)); e = int(m.group(2)) if m.group(2) else s
        for n in range(s, e + 1):
            allc.append((i, n))
bad = 0
seen = set()
for drline, n in allc:
    rb, rc = cite_ok(n, b), cite_ok(n, c)
    same = (b[n-1] == c[n-1]) if (rb == "OK" and rc == "OK") else False
    tag = "ok" if (rb == "OK" and rc == "OK" and same) else "PROBLEM"
    if tag == "PROBLEM": bad += 1
    key = n
    if key not in seen:
        seen.add(key)
        print("  DR:L{:<4} -> stdout:{:<4} builder={:<6} crux={:<6} same_text={:<5} {}".format(
            drline, n, rb, rc, str(same), b[n-1].strip()[:62] if rb == "OK" else ""))
print("\ndistinct stdout lines cited by the decision record: {} ; problems: {}".format(len(seen), bad))
print("total citation occurrences (ranges expanded): {}".format(len(allc)))
