#!/usr/bin/env python3
"""
audit_probe.py -- inspect the SYNAPSE encrypted audit stream.

Two modes:
  python audit_probe.py fill     corpus-wide field fill rates  (default)
  python audit_probe.py schema   field inventory + one sample record

Acceptance check for AUDIT_STATE_CAPTURE_SCOPE.md Piece 1:
run `fill` and look at the "both state hashes" line. It reads 0.0%
today. After Piece 1 lands it should climb for every non-null op.

Reads ~/.synapse/encryption.key. Never prints it.
"""
import sys, json, pathlib, collections

from cryptography.fernet import Fernet

HOME = pathlib.Path.home() / ".synapse"
AUDIT = HOME / "audit"
GATES = HOME / "gates"
PREFIX = "SYNAPSE_ENC_V1:"
PER_FILE = 400

_f = Fernet((HOME / "encryption.key").read_bytes().strip())


def dec(line):
    line = line.strip()
    if line.startswith(PREFIX):
        line = line[len(PREFIX):]
    return json.loads(_f.decrypt(line.encode()).decode())


def read(path, limit=PER_FILE):
    recs, fails = [], 0
    p = pathlib.Path(path)
    if not p.exists():
        return recs, fails
    for i, line in enumerate(p.open(encoding="utf-8", errors="replace")):
        if i >= limit:
            break
        if not line.strip():
            continue
        try:
            recs.append(dec(line))
        except Exception:
            fails += 1
    return recs, fails


def is_set(v):
    """Empty-ish check. Note 0.0 counts as UNSET -- duration_ms is
    structurally zero until Piece 1 lands, and 100% would be a lie."""
    return v not in ("", None, {}, [], 0, 0.0)


def fill():
    filled, ops, cats = collections.Counter(), collections.Counter(), collections.Counter()
    total = fails = both = 0
    files = sorted(AUDIT.glob("audit_*.jsonl"))
    for p in files:
        recs, f = read(p)
        fails += f
        for r in recs:
            total += 1
            for k, v in r.items():
                if is_set(v):
                    filled[k] += 1
            ops[r.get("operation", "")] += 1
            cats[r.get("category", "")] += 1
            if r.get("before_state_hash") and r.get("after_state_hash"):
                both += 1
    pct = lambda n: 100.0 * n / max(total, 1)
    print("files scanned      : %d  (capped %d/file)" % (len(files), PER_FILE))
    print("records decoded    : %d  (failed: %d)" % (total, fails))
    print("both state hashes  : %d  (%.1f%%)   <-- Piece 1 acceptance" % (both, pct(both)))
    print("\n-- FIELD FILL RATE --")
    for k, c in filled.most_common():
        print("   %-22s %6d  %5.1f%%" % (k, c, pct(c)))
    print("\n-- DISTINCT OPERATIONS: %d --" % len(ops))
    for k, c in ops.most_common(15):
        print("   %-34s %6d" % (k or "(empty)", c))
    print("\n-- CATEGORIES --")
    for k, c in cats.most_common(12):
        print("   %-22s %6d" % (k or "(empty)", c))


def trunc(v, n=100):
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + " ...[+%d chars]" % (len(s) - n)


def schema():
    for label, folder, glob in (("AUDIT STREAM", AUDIT, "audit_*.jsonl"),
                                ("GATES STREAM", GATES, "proposals_*.jsonl")):
        files = sorted(folder.glob(glob))
        print("\n" + "=" * 62)
        print("%s   (%s)" % (label, files[-1].name if files else "no files"))
        print("=" * 62)
        if not files:
            continue
        recs, fails = read(files[-1])
        print("records: %d ok / %d failed" % (len(recs), fails))
        if not recs:
            continue
        keys = collections.Counter()
        for r in recs:
            keys.update(r.keys())
        print("\n-- FIELDS --")
        for k, c in keys.most_common():
            print("   %-30s %5d" % (k, c))
        print("\n-- ONE RECORD (values truncated) --")
        for k, v in recs[-1].items():
            print("   %s: %s" % (k, trunc(v)))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "fill"
    {"fill": fill, "schema": schema}.get(mode, fill)()
