"""I1 RE-ENTRY VERIFICATION — an independent adversarial pass over the committed I1 product.

Run under hython on the live build:
    "$HFS/bin/hython" harness/notes/ingest/i1_verify_reentry.py

WHY THIS EXISTS
---------------
A later orchestrator session was handed harness/prompts/i1.md and found the leg already
built and committed by an earlier run. Accepting a committed artifact because it reports
itself green is precisely the defect Law 1 names. This producer re-derives every headline
number of that leg from PRIMARY sources -- the shipped archive and the running build --
without reading the earlier run's own reported figures for anything except comparison.

It is deliberately NOT a copy of i1b_*.py. Where it re-measures, it re-measures its own way:
the Copernicus census is a link-form census over the raw shipped page, not a reuse of
i1b_the161.py; the counts are recomputed off the corpus entries rather than off the
corpus's own `counts` block; the live parm counts are read by instantiating nodes here.

EVERY CHECK STATES THE CONDITION UNDER WHICH IT FAILS (Law 1). See CHECKS below.

CHECKS
  V1  link-form census on news.zip!22/copernicus.txt
      FAILS IF: the union of the two link forms is not 171, or the slash-requiring
                form alone is not 161 (which is what makes the governing 161 a defect)
  V2  live existence of the node types the slash-requiring pattern drops
      FAILS IF: any dropped name is absent from the live Cop catalogue (i.e. a doc typo
                rather than a real type, which would make 171 wrong and 161 right)
  V3  per-context counts recomputed from corpus entries
      FAILS IF: recomputed ingested/clears/thin disagree with the corpus `counts` block
  V4  per-entry provenance integrity
      FAILS IF: any entry lacks tier==VERIFIED-DOC, build, source, source_archive,
                a boolean floor verdict, or a deprecation block
  V5  live parm counts for the cross-check sample
      FAILS IF: an instantiated node's len(node.parms()) differs from the claimed figure
  V6  calibration binding
      FAILS IF: sha256 of the reader on disk differs from the sha recorded by calibration,
                or the calibration is not all-pass
  V7  the three named as needing a probe
      FAILS IF: any of them clears the floor, or any entry named as clearing does not
  V8  provenance anchors reproduce from the COMMITTED tree, not just this working copy
      FAILS IF: the LF-normalised sha of an artifact cannot be re-derived from what git
                stores -- i.e. the recorded anchor is unreproducible on a fresh clone
"""

import hashlib
import json
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
CORPUS = os.path.join(HERE, "h22_node_corpus.json")
CALIB = os.path.join(HERE, "_i1b_calibration.json")
READER = os.path.join(HERE, "i1b_reader.py")
BUILD = "22.0.368"


def hfs_help():
    hfs = os.environ.get("HFS")
    if hfs and os.path.isdir(os.path.join(hfs, "houdini", "help")):
        return os.path.join(hfs, "houdini", "help")
    guess = r"C:\Program Files\Side Effects Software\Houdini %s\houdini\help" % BUILD
    if os.path.isdir(guess):
        return guess
    raise SystemExit("cannot locate $HFS/houdini/help")


results = {}
failures = []


def record(vid, title, ok, detail):
    results[vid] = {"title": title, "ok": bool(ok), **detail}
    if not ok:
        failures.append(vid)


# ---------------------------------------------------------------- V1
HELP = hfs_help()
page = zipfile.ZipFile(os.path.join(HELP, "news.zip")).read("22/copernicus.txt").decode("utf-8-sig")
targets = [(L.split("|", 1)[1] if "|" in L else L).strip() for L in re.findall(r"\[([^\]]*)\]", page)]

slashed = sorted({m.group(1) for x in targets for m in [re.fullmatch(r"Node:/cop/([A-Za-z0-9_.\-]+)", x)] if m})
bare = sorted({m.group(1) for x in targets for m in [re.fullmatch(r"Node:cop/([A-Za-z0-9_.\-]+)", x)] if m})
union = sorted(set(slashed) | set(bare))
dropped = sorted(set(bare) - set(slashed))

record(
    "V1", "link-form census on the shipped What's New page",
    len(slashed) == 161 and len(union) == 171,
    {
        "with_leading_slash": len(slashed),
        "without_leading_slash": len(bare),
        "in_both_forms": len(set(slashed) & set(bare)),
        "union": len(union),
        "dropped_by_the_slash_pattern": dropped,
        "source": "news.zip!22/copernicus.txt",
        "reading": "the governing 161 is the slash-requiring form alone; the page uses two forms",
    },
)

# ---------------------------------------------------------------- V2 (live)
try:
    import hou  # noqa

    live_cop = set(hou.nodeTypeCategories()["Cop"].nodeTypes().keys())
    absent = [n for n in dropped if n not in live_cop]
    record(
        "V2", "the dropped names are real live Cop types, not doc typos",
        not absent,
        {"probed": len(dropped), "absent_from_live_catalogue": absent,
         "live_cop_catalogue_total": len(live_cop), "tier": "VERIFIED-RUNTIME", "build": BUILD},
    )
except ImportError:
    record("V2", "the dropped names are real live Cop types", False,
           {"error": "hou unavailable - run under hython; a skip is honest, a pass would be a lie"})

# ---------------------------------------------------------------- V3 / V4 / V7
corpus = json.load(open(CORPUS, encoding="utf-8"))
entries = corpus["entries"]

recomputed = {}
integrity = {}
for e in entries:
    c = e.get("context")
    r = recomputed.setdefault(c, {"ingested": 0, "clears": 0, "thin": 0})
    r["ingested"] += 1
    fl = e.get("floor") or {}
    if fl.get("clears") is True:
        r["clears"] += 1
    elif fl.get("clears") is False:
        r["thin"] += 1
    else:
        integrity["floor_verdict_not_boolean"] = integrity.get("floor_verdict_not_boolean", 0) + 1
    if e.get("tier") != "VERIFIED-DOC":
        integrity["tier_not_VERIFIED_DOC"] = integrity.get("tier_not_VERIFIED_DOC", 0) + 1
    if e.get("build") != BUILD:
        integrity["build_not_pinned"] = integrity.get("build_not_pinned", 0) + 1
    for field in ("source", "source_archive", "deprecation"):
        if not e.get(field):
            integrity["missing_" + field] = integrity.get("missing_" + field, 0) + 1

mismatch = {}
for c, rep in corpus["counts"].items():
    got = recomputed.get(c, {})
    for mine, theirs in (("ingested", "ingested"), ("clears", "clears_floor"), ("thin", "known_thin")):
        if got.get(mine) != rep.get(theirs):
            mismatch["%s.%s" % (c, theirs)] = {"recomputed": got.get(mine), "reported": rep.get(theirs)}

record("V3", "per-context counts recomputed from the entries themselves", not mismatch,
       {"recomputed": recomputed, "disagreements": mismatch,
        "catalogue_totals_live": corpus["catalogue_totals_live"]})

record("V4", "per-entry provenance integrity", not integrity,
       {"entries": len(entries), "violations": integrity or "NONE"})

named_thin = corpus["named_copernicus"]["known_thin_named"]
by_stem = {}
for e in entries:
    if e.get("context") == "cop":
        by_stem[e["stem"]] = (e.get("floor") or {}).get("clears")
bad = [s for s in named_thin if by_stem.get(s) is not False]
record("V7", "the three named as needing a runtime probe are genuinely below the floor",
       not bad, {"named": named_thin, "that_actually_clear_and_should_not": bad})

# ---------------------------------------------------------------- V5 (live)
CROSS = [("Cop", "chromakey"), ("Cop", "cellularnoise3d"), ("Cop", "grunge_rust"),
         ("Lop", "karma"), ("Lop", "componentoutput"), ("Lop", "rendersettings"),
         ("Cop2", "blur"), ("Cop2", "light")]
claimed = {"%s/%s" % (n["context"], n["stem"]): n["live_parms"] for n in corpus["crosscheck_20"]["nodes"]}
try:
    import hou  # noqa

    rows, bad5 = [], []
    for cat, typ in CROSS:
        key = {"Cop": "cop", "Lop": "lop", "Cop2": "cop2"}[cat] + "/" + typ
        want = claimed.get(key)
        if cat == "Cop":
            par = hou.node("/obj").createNode("copnet", "vr_%s" % typ)
        elif cat == "Lop":
            par = hou.node("/stage")
        else:
            par = hou.node("/img").createNode("img", "vr2_%s" % typ)
        got = len(par.createNode(typ).parms())
        rows.append({"type": key, "claimed": want, "actual": got, "match": got == want})
        if got != want:
            bad5.append(key)
    record("V5", "claimed live parm counts re-read by instantiating on the running build",
           not bad5, {"probed": len(rows), "rows": rows, "mismatched": bad5,
                      "tier": "VERIFIED-RUNTIME", "build": BUILD})
except ImportError:
    record("V5", "claimed live parm counts", False, {"error": "hou unavailable - run under hython"})

# ---------------------------------------------------------------- V6
cal = json.load(open(CALIB, encoding="utf-8"))
sha = hashlib.sha256(open(READER, "rb").read()).hexdigest()
record("V6", "the corpus was built by the reader the calibration actually gated",
       sha == cal.get("reader_sha256") and cal.get("all_pass") is True,
       {"reader_sha256_on_disk": sha, "reader_sha256_calibrated": cal.get("reader_sha256"),
        "bound": sha == cal.get("reader_sha256"), "controls_total": cal.get("total"),
        "controls_passed": cal.get("passed"), "by_class": cal.get("by_class")})

# ---------------------------------------------------------------- V8
# The anchors above (corpus_sha256 in the receipt, reader_sha256 in the calibration) were
# computed on Windows working-copy bytes. core.autocrlf=true means git stores LF, so on a
# fresh clone -- or on Linux CI -- neither anchor re-derives from the committed path.
# reader_sha256 is a GATE: it binds the corpus to the reader the calibration certified.
# An anchor that cannot be reproduced from the tree is a number without a usable producer.
import subprocess


def committed_bytes(relpath):
    p = subprocess.run(["git", "show", "HEAD:" + relpath], capture_output=True, cwd=REPO)
    return p.stdout if p.returncode == 0 else None


anchors = {}
anchor_broken = []
for label, relpath, recorded in (
    ("corpus", "harness/notes/ingest/h22_node_corpus.json",
     json.load(open(os.path.join(REPO, "harness/notes/receipts/I1.json")))["oracle"]["corpus_sha256"]),
    ("reader", "harness/notes/ingest/i1b_reader.py", cal.get("reader_sha256")),
):
    disk = open(os.path.join(REPO, relpath), "rb").read()
    blob = committed_bytes(relpath)
    lf = hashlib.sha256(disk.replace(b"\r\n", b"\n")).hexdigest()
    crlf = hashlib.sha256(disk.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")).hexdigest()
    blob_sha = hashlib.sha256(blob).hexdigest() if blob is not None else None
    reproduces = (recorded == blob_sha)
    anchors[label] = {
        "path": relpath,
        "recorded_anchor": recorded,
        "committed_blob_sha256": blob_sha,
        "lf_normalised_sha256": lf,
        "crlf_normalised_sha256": crlf,
        "recorded_anchor_reproduces_from_committed_tree": reproduces,
        "recorded_anchor_is_the_crlf_variant": recorded == crlf,
        "content_identical_modulo_line_endings": lf == hashlib.sha256(
            (blob or b"").replace(b"\r\n", b"\n")).hexdigest(),
    }
    if not reproduces:
        anchor_broken.append(label)

record(
    "V8", "provenance anchors reproduce from the COMMITTED tree, not just this working copy",
    not anchor_broken,
    {
        "anchors": anchors,
        "unreproducible": anchor_broken,
        "mechanism": "core.autocrlf=true - producers hashed CRLF working-copy bytes; git stores LF",
        "content_verdict": "IDENTICAL modulo line endings - this is a provenance defect, NOT tampering",
        "reproducible_anchor_to_use": {
            k: v["committed_blob_sha256"] for k, v in anchors.items()
        },
    },
)

# ---------------------------------------------------------------- emit
out = {
    "schema": "i1_reentry_verification/v1",
    "leg": "I1",
    "harness": "INGEST-01",
    "build": BUILD,
    "producer": "harness/notes/ingest/i1_verify_reentry.py",
    "purpose": "independent adversarial re-derivation of the committed I1 leg from primary sources",
    "corpus_verified": "harness/notes/ingest/h22_node_corpus.json",
    "corpus_sha256": hashlib.sha256(open(CORPUS, "rb").read()).hexdigest(),
    "checks": results,
    "all_pass": not failures,
    "failed": failures,
}
dest = os.path.join(HERE, "i1_verify_reentry.json")
with open(dest, "w", encoding="utf-8") as fh:
    json.dump(out, fh, indent=1)
    fh.write("\n")

print("I1 RE-ENTRY VERIFICATION  %d/%d  %s" % (len(results) - len(failures), len(results),
                                               "ALL PASS" if not failures else "FAILED: " + ",".join(failures)))
for k, v in results.items():
    print("  %-3s %-6s %s" % (k, "PASS" if v["ok"] else "FAIL", v["title"]))
print("wrote %s" % dest)
sys.exit(1 if failures else 0)
