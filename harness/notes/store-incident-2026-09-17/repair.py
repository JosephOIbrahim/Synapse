import sys, os, json, time, shutil, collections
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
from synapse.memory.store import _get_crypto

SRC = r"C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\memory.jsonl"
crypto = _get_crypto()

raw = open(SRC, "r", encoding="utf-8").read().splitlines(keepends=True)

def richness(d):
    """Higher = more metadata survived. Prefer the record that kept its tags."""
    return (len(d.get("tags") or []),
            1 if (d.get("hip_file") or "") else 0,
            0 if (d.get("source") or "") == "auto" else 1,
            1 if d.get("frame") is not None else 0,
            1 if (d.get("hip_version") or 0) else 0)

parsed = []
for n, line in enumerate(raw, 1):
    s = line.strip()
    if not s:
        continue
    try:
        dec = crypto.decrypt_line(s) if crypto else s
        d = json.loads(dec)
        parsed.append((n, d["id"], json.dumps(d, sort_keys=True), d))
    except Exception:
        pass

by_id = collections.defaultdict(list)
for n, mid, canon, d in parsed:
    by_id[mid].append((n, canon, d))

drop = set()
kept_report = []
for mid, rows in by_id.items():
    if len({c for _, c, _ in rows}) <= 1:
        continue                      # identical dupes: loader already tolerates
    best = max(rows, key=lambda r: (richness(r[2]), -r[0]))
    for n, _, d in rows:
        if n != best[0]:
            drop.add(n)
    kept_report.append((mid, best[0], sorted(n for n, _, _ in rows if n != best[0]),
                        len(best[2].get("tags") or [])))

print("conflicting ids      :", len(kept_report))
for mid, keep, dropped, ntags in kept_report:
    print("  %s  KEEP line %-4d (tags=%d)  DROP %s" % (mid, keep, ntags, dropped))
print("lines to drop        :", sorted(drop))

if not drop:
    print("nothing to repair"); raise SystemExit(0)

ts = int(time.time())
backup = SRC + ".pre-repair-%d" % ts
shutil.copy2(SRC, backup)
print("backup               :", backup)

tmp = SRC + ".repaired"
with open(tmp, "w", encoding="utf-8", newline="") as f:
    for n, line in enumerate(raw, 1):
        if n in drop:
            continue
        f.write(line)

# verify the repaired file the way the store's loader does
seen, bad = {}, []
with open(tmp, "r", encoding="utf-8") as f:
    for n, line in enumerate(f, 1):
        s = line.strip()
        if not s:
            continue
        try:
            dec = crypto.decrypt_line(s) if crypto else s
            d = json.loads(dec)
            required = ("id", "created_at", "content", "memory_type")
            if (not isinstance(d, dict)
                    or any(not isinstance(d.get(k), str) for k in required)
                    or not d["id"] or not d["created_at"]):
                raise ValueError("incomplete record identity or content")
            canon = json.dumps(d, sort_keys=True)
            prior = seen.get(d["id"])
            if prior is not None:
                if prior != canon:
                    raise ValueError("conflicting duplicate memory identity")
                continue
            seen[d["id"]] = canon
        except Exception as e:
            bad.append((n, str(e)))

print()
print("VERIFY repaired file")
print("  memories loadable  :", len(seen))
print("  unreadable records :", len(bad), bad[:5])
if bad:
    print("  REFUSING to install the repair - original untouched")
    raise SystemExit(1)

os.replace(tmp, SRC)
print("  installed          :", SRC)
print("  bytes  before/after: %d / %d" % (os.path.getsize(backup), os.path.getsize(SRC)))
