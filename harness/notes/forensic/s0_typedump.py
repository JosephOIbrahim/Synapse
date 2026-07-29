"""S0 · type-surface dump — writes the full registered node-type surface for whichever
Houdini build is running it. Read-only; opens nothing, creates nothing.

Run once per installed build, then diff the two dumps to measure what the native floor
gained between majors. That delta is OBSERVED evidence; a release-note summary of it is
REPORTED evidence. Both are worth having; they are not the same tier.

LAW 1 — the condition under which the delta is INVALID:
  A registered node-type surface includes every HDA the environment happens to load, so a
  raw A-vs-B count is contaminated by third-party packages and is NOT a vendor delta. Each
  type is therefore classified by where its definition lives:
    NATIVE_COMPILED  no HDA definition at all — compiled into the build
    NATIVE_HDA       definition file resolves under $HFS
    THIRD_PARTY      definition file resolves outside $HFS  <-- excluded from any delta claim
  If the THIRD_PARTY bucket is non-empty on either build and the consumer of this dump does
  not filter on it, the resulting delta is void.

Output: harness/notes/forensic/typedump_<version>.json
"""

import json
import os

import hou

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

ver = hou.applicationVersionString()
hfs = (hou.getenv("HFS") or "").replace("\\", "/").rstrip("/")

# $HFS often arrives 8.3-shortened on Windows (PROGRA~1). Resolve it so path
# containment is decided on real paths, not on string luck.
try:
    hfs_real = os.path.realpath(hfs).replace("\\", "/").rstrip("/").lower()
except Exception:
    hfs_real = hfs.lower()


def classify(ntype):
    """-> (bucket, definition_path)"""
    try:
        defn = ntype.definition()
    except Exception as exc:
        return "CLASSIFY_FAILED", repr(exc)
    if defn is None:
        return "NATIVE_COMPILED", ""
    try:
        lib = defn.libraryFilePath() or ""
    except Exception as exc:
        return "CLASSIFY_FAILED", repr(exc)
    try:
        lib_real = os.path.realpath(lib).replace("\\", "/").lower()
    except Exception:
        lib_real = lib.replace("\\", "/").lower()
    if hfs_real and lib_real.startswith(hfs_real):
        return "NATIVE_HDA", lib
    if "/houdini/otls/" in lib_real and hfs_real and hfs_real.split("/")[-1] in lib_real:
        return "NATIVE_HDA", lib
    return "THIRD_PARTY", lib


rows = {}
buckets = {}
cat_labels = {}
third_party_libs = {}

for cat_name, cat in hou.nodeTypeCategories().items():
    try:
        cat_labels[cat_name] = cat.label()
    except Exception as exc:
        cat_labels[cat_name] = "<LABEL FAILED: %r>" % (exc,)
    try:
        types = cat.nodeTypes()
    except Exception:
        continue
    for tname, ntype in types.items():
        try:
            label = ntype.description()
        except Exception:
            label = ""
        bucket, lib = classify(ntype)
        key = "%s/%s" % (cat_name, tname)
        rows[key] = {"label": label, "bucket": bucket}
        buckets[bucket] = buckets.get(bucket, 0) + 1
        if bucket == "THIRD_PARTY":
            third_party_libs[lib] = third_party_libs.get(lib, 0) + 1

payload = {
    "version": ver,
    "python": "%d.%d.%d" % os.sys.version_info[:3],
    "hfs": hfs,
    "hfs_real": hfs_real,
    "category_labels": cat_labels,
    "count_total": len(rows),
    "buckets": buckets,
    "third_party_libraries": dict(
        sorted(third_party_libs.items(), key=lambda kv: -kv[1])
    ),
    "types": rows,
}

path = os.path.join(OUT_DIR, "typedump_%s.json" % ver)
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, indent=0, sort_keys=True)

print("WROTE %s" % path)
print("TOTAL %d   BUCKETS %s" % (len(rows), json.dumps(buckets, sort_keys=True)))
print("THIRD PARTY LIBS: %s" % json.dumps(payload["third_party_libraries"])[:2000])
