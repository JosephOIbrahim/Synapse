"""Split the H21 references into KEEP (true provenance) and FIX (stale scope).

A find-replace here would be actively harmful. "Part 2/18 of the SideFX MPM H21
Masterclass" is a TRUE citation of real H21 material - rewriting it to 22
falsifies a citation of someone else's work. "Complete OpenCL kernel reference
for Houdini 21 Copernicus" is a claim about what the corpus COVERS, and that one
is stale now the loader reads H22 tables.

The distinction is: does the reference describe WHAT WAS OBSERVED (keep) or WHAT
THIS COVERS (fix)?
"""
import re, subprocess, collections

out = subprocess.run(
    ["git", "grep", "-n", "-i", "-E", r"houdini ?21|h21|21\.0\.6", "--", "rag/"],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
).stdout.splitlines()

# markers of TRUE provenance - a record of what was seen, where, when
KEEP = re.compile(
    r"masterclass|by [A-Z]|verified (live )?(on|against)|tested on|observed on"
    r"|probed on|as of \d{4}|20\d\d-\d\d|recorded|talk|tutorial|series|part \d+/",
    re.I)

keep, fix = [], []
for line in out:
    (keep if KEEP.search(line) else fix).append(line)

print("total H21 references in rag/ :", len(out))
print("  KEEP (true provenance)     :", len(keep))
print("  FIX  (stale scope claim)   :", len(fix))
print()

print("FIX candidates by file:")
c = collections.Counter(l.split(":", 1)[0] for l in fix)
for f, n in c.most_common(12):
    print("  %-58s %d" % (f.replace("rag/", ""), n))
print()
print("sample FIX lines:")
for l in fix[:6]:
    body = l.split(":", 2)[-1].strip()
    print("  -", body[:110])
print()
print("sample KEEP lines (must NOT change):")
for l in keep[:4]:
    body = l.split(":", 2)[-1].strip()
    print("  -", body[:110])
