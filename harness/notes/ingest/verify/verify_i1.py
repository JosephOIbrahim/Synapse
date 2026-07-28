"""Independent verification of leg I1 against the ORACLE block in harness/prompts/i1.md.

Reads the COMMITTED blob (R127), never the worktree file. Recomputes every published
number from the entries themselves and compares. Exit 1 on any disagreement.
"""
import json
import subprocess
import sys
import hashlib
from collections import Counter, defaultdict

REPO = "C:/Users/User/SYNAPSE/.claude/worktrees/i1-ingest"
CORPUS = "harness/notes/ingest/h22_node_corpus.json"
RECEIPT = "harness/notes/receipts/I1.json"
fails = []
notes = []


def show(path):
    r = subprocess.run(["git", "-C", REPO, "show", "HEAD:" + path], capture_output=True)
    if r.returncode != 0:
        raise SystemExit("cannot read committed %s" % path)
    return r.stdout


def chk(label, got, want):
    ok = got == want
    print("%-58s %-24s %s" % (label, repr(got)[:24], "OK" if ok else "DISAGREE want=%r" % (want,)))
    if not ok:
        fails.append((label, got, want))
    return ok


corpus_blob = show(CORPUS)
receipt_blob = show(RECEIPT)
C = json.loads(corpus_blob)
R = json.loads(receipt_blob)
E = C["entries"]

print("=" * 96)
print("A. every entry tiered VERIFIED-DOC, with build, source path, floor verdict")
print("=" * 96)
chk("entries in committed corpus", len(E), R["oracle"]["entries"])
chk("every entry tier == VERIFIED-DOC", sorted({e.get("tier") for e in E}), ["VERIFIED-DOC"])
chk("every entry build == 22.0.368", sorted({e.get("build") for e in E}), ["22.0.368"])
chk("every entry has non-empty source path",
    all(isinstance(e.get("source"), str) and e["source"].strip() for e in E), True)
chk("every entry source_archive == nodes.zip",
    sorted({e.get("source_archive") for e in E}), ["nodes.zip"])
chk("every entry has floor.clears bool",
    all(isinstance(e.get("floor", {}).get("clears"), bool) for e in E), True)
chk("every entry has floor.rung", all(bool(e.get("floor", {}).get("rung")) for e in E), True)
chk("every entry has floor.known_thin bool",
    all(isinstance(e.get("floor", {}).get("known_thin"), bool) for e in E), True)
chk("floor verdict total (clears XOR known_thin)",
    all(e["floor"]["clears"] != e["floor"]["known_thin"] for e in E), True)
chk("every entry has producer path", all(bool(e.get("producer")) for e in E), True)
chk("source path prefixed by its context",
    all(e["source"].startswith(e["context"] + "/") for e in E), True)

print()
print("=" * 96)
print("B. counts per context as integers: exists / clears-floor / ingested")
print("=" * 96)
mine = defaultdict(Counter)
for e in E:
    c = e["context"]
    mine[c]["exists"] += 1
    mine[c]["ingested"] += 1
    if e["floor"]["clears"]:
        mine[c]["clears_floor"] += 1
    else:
        mine[c]["known_thin"] += 1
pub = C["counts"]
for ctx in ("cop", "lop", "cop2"):
    for field in ("exists", "clears_floor", "ingested", "known_thin"):
        got = mine[ctx][field]
        chk("recomputed %s.%s" % (ctx, field), got, pub[ctx][field])
        chk("  receipt agrees %s.%s" % (ctx, field),
            R["oracle"]["counts_per_context"][ctx][field], got)
    chk("  %s counts are ints" % ctx,
        all(isinstance(pub[ctx][f], int)
            for f in ("exists", "clears_floor", "ingested", "known_thin")), True)
    chk("  %s catalogue_total_live" % ctx, pub[ctx]["catalogue_total_live"],
        C["catalogue_totals_live"][ctx])
chk("contexts present", sorted(mine.keys()), ["cop", "cop2", "lop"])
chk("brief catalogue totals cop/cop2/lop",
    [C["catalogue_totals_live"]["cop"], C["catalogue_totals_live"]["cop2"],
     C["catalogue_totals_live"]["lop"]], [384, 169, 218])

print()
print("=" * 96)
print("C. the 161: ingested / need a probe / named")
print("=" * 96)
named = [e for e in E if e.get("in_named_copernicus_set")]
nc = C["named_copernicus"]
chk("entries flagged in_named_copernicus_set", len(named), nc["ingested"])
chk("  of those, clear the floor", sum(1 for e in named if e["floor"]["clears"]), nc["clears_floor"])
need = sorted(e["stem"] for e in named if not e["floor"]["clears"])
chk("  need a runtime probe (count)", len(need), nc["known_thin_need_a_runtime_probe"])
chk("  need a runtime probe (named)", need, sorted(nc["known_thin_named"]))
chk("receipt agrees the_161.ingested", R["oracle"]["the_161"]["ingested"], len(named))
chk("receipt agrees the_161.clears_floor", R["oracle"]["the_161"]["clears_floor"], nc["clears_floor"])
chk("receipt agrees need_a_probe named",
    sorted(R["oracle"]["the_161"]["need_a_runtime_probe_named"]), need)
chk("all named-set entries are cop context", sorted({e["context"] for e in named}), ["cop"])

print()
print("=" * 96)
print("D. 20-node cross-check vs the LIVE runtime")
print("=" * 96)
xc = C["crosscheck_20"]
nodes = xc["nodes"]
chk("nodes probed", len(nodes), 20)
chk("all instantiated ok", sorted({n["status"] for n in nodes}), ["ok"])
lab_doc = sum(n["documented_params"] for n in nodes)
lab_agree = sum(n["label_agreement"] for n in nodes)
nm_doc = sum(n["documented_internal_names"] for n in nodes)
nm_agree = sum(n["internal_name_agreement"] for n in nodes)
chk("recomputed documented labels", lab_doc, R["oracle"]["crosscheck_20"]["documented_labels"])
chk("recomputed label agreement", lab_agree, R["oracle"]["crosscheck_20"]["label_agreement"])
chk("recomputed documented internal names", nm_doc,
    R["oracle"]["crosscheck_20"]["documented_internal_names"])
chk("recomputed internal-name agreement", nm_agree,
    R["oracle"]["crosscheck_20"]["internal_name_agreement"])
chk("label pct", round(100.0 * lab_agree / lab_doc, 1),
    R["oracle"]["crosscheck_20"]["label_agreement_pct"])
chk("internal-name pct", round(100.0 * nm_agree / nm_doc, 1),
    R["oracle"]["crosscheck_20"]["internal_name_agreement_pct"])
chk("label beats internal name (R97)", lab_agree / lab_doc > nm_agree / nm_doc, True)
notes.append("crosscheck contexts: %s" % dict(Counter(n["context"] for n in nodes)))

print()
print("=" * 96)
print("E. doc and probe axes never summed")
print("=" * 96)
chk("every entry carries a separate runtime block",
    all(isinstance(e.get("runtime"), dict) for e in E), True)
chk("runtime blocks tiered VERIFIED-RUNTIME",
    sorted({e["runtime"].get("tier") for e in E}), ["VERIFIED-RUNTIME"])
chk("entry tier stays DOC when runtime present",
    all(e["tier"] == "VERIFIED-DOC" for e in E if e["runtime"].get("live_type_exists")), True)
chk("deprecation records both sides",
    all("agreement" in e["deprecation"] and "sources" in e["deprecation"] for e in E), True)
dep = Counter(e["deprecation"]["agreement"] for e in E)
print("     deprecation union:", dict(dep))
ronly = sorted(e["context"] + "/" + e["stem"] for e in E
               if e["deprecation"]["agreement"] == "runtime_only")
print("     runtime-only (doc silent):", ronly)
notes.append("deprecation %s runtime_only=%s" % (dict(dep), ronly))

print()
print("=" * 96)
print("F. NO change to rag/, emission corpus, or product")
print("=" * 96)
base = R["base_commit"]
head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
names = subprocess.run(["git", "-C", REPO, "diff", "--name-only", base, head],
                       capture_output=True, text=True).stdout.split()
print("     files changed %s..%s : %d" % (base, head[:7], len(names)))
print("     dirs:", sorted({"/".join(n.split("/")[:3]) for n in names}))
chk("no rag/ file changed", [n for n in names if n.startswith("rag/")], [])
chk("all changes under harness/notes/{ingest,receipts}",
    sorted({n for n in names if not (n.startswith("harness/notes/ingest/")
                                     or n.startswith("harness/notes/receipts/"))}), [])
chk("no python/ product file changed", [n for n in names if n.startswith("python/")], [])
chk("no panel/ or shared/ file changed",
    [n for n in names if n.startswith("panel/") or n.startswith("shared/")], [])

print()
print("=" * 96)
print("G. receipt/v1 conformance")
print("=" * 96)
chk("schema", R.get("schema"), "receipt/v1")
chk("leg", R.get("leg"), "I1")
chk("has model", bool(R.get("model")), True)
chk("has settings_profile", bool(R.get("settings_profile")), True)
chk("has for_ruling", isinstance(R.get("for_ruling"), list) and len(R["for_ruling"]) > 0, True)
chk("has resume_token", isinstance(R.get("resume_token"), dict), True)
s = R.get("summary", "")
for ctx in ("cop", "lop", "cop2"):
    chk("clears-floor int for %s in summary" % ctx, str(pub[ctx]["clears_floor"]) in s, True)

print()
print("=" * 96)
print("H. published hash reproducibility")
print("=" * 96)
blob_sha = hashlib.sha256(corpus_blob).hexdigest()
disk = open(REPO + "/" + CORPUS, "rb").read()
disk_sha = hashlib.sha256(disk).hexdigest()
pubsha = R["oracle"]["corpus_sha256"]
print("     receipt publishes :", pubsha)
print("     committed blob    :", blob_sha)
print("     worktree file     :", disk_sha)
chk("published sha matches COMMITTED blob", blob_sha == pubsha, True)
chk("  (matches worktree file instead)", disk_sha == pubsha, True)
chk("  content identical modulo EOL",
    hashlib.sha256(disk.replace(b"\r\n", b"\n")).hexdigest() == blob_sha, True)

print()
print("=" * 96)
print("I. parameter-level shape")
print("=" * 96)
tot = sum(len(e["parameters"]) for e in E)
res = sum(1 for e in E for p in e["parameters"] if p.get("live_label_resolved"))
print("     documented parameters total :", tot)
print("     live_label_resolved         :", res,
      "(%.1f%%)" % (100.0 * res / tot if tot else 0))
chk("every parameter carries label", all(p.get("label") for e in E for p in e["parameters"]), True)
chk("live_label_resolved on every parameter",
    all("live_label_resolved" in p for e in E for p in e["parameters"]), True)
notes.append("parameters=%d live_label_resolved=%d" % (tot, res))

print()
print("NOTES")
for n in notes:
    print("  -", n)
print()
if fails:
    print("DISAGREEMENTS: %d" % len(fails))
    for f in fails:
        print("   *", f[0], "got", repr(f[1])[:60], "want", repr(f[2])[:60])
    sys.exit(1)
print("ALL ORACLE CHECKS AGREE.")
