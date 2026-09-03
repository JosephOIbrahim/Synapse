"""T-E corrected: count 'not <neighbour>' bullets with the record's ACTUAL bullet shapes."""
import re
DR = "docs/reviews/bp4-usd-composition-worldlabs.md"
dr = open(DR, encoding="utf-8").read().split("\n")
secs, cur = {}, None
for i, ln in enumerate(dr, 1):
    m = re.match(r"^###\s+(\S+)\s+(.*)$", ln)
    if m:
        cur = m.group(1).rstrip("."); secs[cur] = {"title": ln.strip(), "body": []}; continue
    if re.match(r"^##\s", ln): cur = None; continue
    if cur: secs[cur]["body"].append(ln)
for k in secs: secs[k]["text"] = "\n".join(secs[k]["body"])

T1 = [("2.1","payload for splat + collider"),("2.2","purpose render / proxy"),
      ("2.3","variantSet splatTier full|low"),("2.4","variantSet physics none|collision"),
      ("2.5","kind = component"),("2.6","customData:worldlabs provenance"),
      ("2.7","instanceable yes/no"),("2.8","metric/ground/chirality transform home")]

print("{:<5} {:<38} {:<10} {:<6} {:<8} {:<5} {}".format(
    "sec","choice","arc","neigh","failure","tier","neighbour phrases found"))
for sec, label in T1:
    t = secs[sec]["text"]; title = secs[sec]["title"]
    arcm = re.search(r"arc\s*=\s*\*\*([a-z ]+)\*\*", title)
    arc = arcm.group(1).strip() if arcm else "-"
    # every bullet that rejects an alternative, in any of the record's shapes
    phrases = re.findall(r"^\s*-\s+\*\*(?:not |why not |[a-z]+ not )([^*]+)\*\*", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(there is exactly \*\*one instance)", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(an instanceable prim becomes)", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(instance proxies complicate)", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(a payloaded file already in metric)", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(an `Xform` op is a)", t, re.M|re.I)
    phrases += re.findall(r"^\s*-\s+(the \*\*`applied` ledger)", t, re.M|re.I)
    livrps_hdr = "LIVRPS reason" in t
    failure = "Failure prevented" in t
    tierm = re.findall(r"\*\*Tier:\*\*\s*\**([A-Z][A-Z-]+)", t)
    tiers = "/".join(sorted(set(tierm))) or "-"
    print("{:<5} {:<38} {:<10} {:<6} {:<8} {:<5} {}".format(
        sec, label[:38], arc[:10], len(phrases), "yes" if failure else "NO",
        "y" if tiers!="-" else "N", "; ".join(p.strip()[:26] for p in phrases[:4])))
    if not livrps_hdr: print("      !! no 'LIVRPS reason' header")
