import sys, os, json, collections
sys.path.insert(0, r"C:\Users\User\SYNAPSE\python")
from synapse.memory.store import _get_crypto

SRC = r"C:\Users\User\AppData\Local\Temp\houdini_temp\untitled\.synapse\memory.jsonl"
crypto = _get_crypto()
print("crypto engine:", type(crypto).__name__ if crypto else None)

records = []          # (line_no, id, canonical, data)
bad     = []          # (line_no, reason)
with open(SRC, "r", encoding="utf-8") as f:
    for n, raw in enumerate(f, 1):
        line = raw.strip()
        if not line:
            continue
        try:
            if crypto:
                line = crypto.decrypt_line(line)
            data = json.loads(line)
            required = ("id", "created_at", "content", "memory_type")
            if (not isinstance(data, dict)
                    or any(not isinstance(data.get(k), str) for k in required)
                    or not data["id"] or not data["created_at"]):
                raise ValueError("incomplete record identity or content")
            records.append((n, data["id"], json.dumps(data, sort_keys=True), data))
        except Exception as e:
            bad.append((n, "%s: %s" % (type(e).__name__, e)))

print("total lines parsed OK :", len(records))
print("unparseable lines     :", len(bad))
for n, r in bad[:10]:
    print("   line %d -> %s" % (n, r))

by_id = collections.defaultdict(list)
for n, mid, canon, data in records:
    by_id[mid].append((n, canon, data))

conflicts = {k: v for k, v in by_id.items() if len({c for _, c, _ in v}) > 1}
exact_dupes = {k: v for k, v in by_id.items() if len(v) > 1 and len({c for _, c, _ in v}) == 1}

print()
print("distinct ids          :", len(by_id))
print("ids w/ exact dupes    :", len(exact_dupes), "(harmless, loader skips)")
print("ids w/ CONFLICTS      :", len(conflicts), "  <-- these degrade the store")
print()
for mid, rows in conflicts.items():
    print("=" * 70)
    print("id:", mid, " occurrences:", len(rows), " lines:", [n for n, _, _ in rows])
    base = rows[0][2]
    for n, canon, data in rows:
        diffs = []
        for k in sorted(set(base) | set(data)):
            a, b = base.get(k), data.get(k)
            if a != b:
                sa = repr(a)[:70]; sb = repr(b)[:70]
                diffs.append("      %s: %s  ->  %s" % (k, sa, sb))
        print("  line %d  created_at=%r updated_at=%r type=%r len(content)=%d"
              % (n, data.get("created_at"), data.get("updated_at"),
                 data.get("memory_type"), len(data.get("content") or "")))
        if diffs:
            print("    differs from first occurrence in:")
            print("\n".join(diffs))
