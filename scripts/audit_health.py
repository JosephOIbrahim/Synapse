#!/usr/bin/env python3
"""
audit_health.py - decrypt and inspect the Synapse audit corpus.

This is the verification harness for AUDIT_STATE_CAPTURE_SCOPE.md.

BASELINE, measured 2026-08-02 (90 files, 22,025 records @ 400/file cap):

    before_state_hash / after_state_hash ....  0.0%
    duration_ms .............................  always 0.0
    tool / user_id ..........................  0%
    agent_id ................................  1.3%
    sequence_id .............................  1.4%
    input_data ..............................  92.5%
    output_data .............................  97.5%
    operation / category / hash chain .......  100%
    distinct operations .....................  71

Re-run after Piece 1. The state-hash fill rate moving off zero is the
pass signal. Nothing else in this output should change.

Usage:
    python audit_health.py              # fill rates across the corpus
    python audit_health.py --schema     # field list + one decoded record
    python audit_health.py --cap 1000   # lines read per file (default 400)
"""
import sys, json, pathlib, collections
from cryptography.fernet import Fernet

HOME = pathlib.Path.home() / ".synapse"
AUDIT = HOME / "audit"
GATES = HOME / "gates"
PREFIX = "SYNAPSE_ENC_V1:"

_fernet = None


def fernet():
    global _fernet
    if _fernet is None:
        _fernet = Fernet((HOME / "encryption.key").read_bytes().strip())
    return _fernet


def dec(line):
    line = line.strip()
    if line.startswith(PREFIX):
        line = line[len(PREFIX):]
    return json.loads(fernet().decrypt(line.encode()).decode())


def is_set(v):
    """A field counts as populated only if it carries real information.

    Numeric zero counts as EMPTY. duration_ms is 0.0 on every historical
    entry; treating that as 'filled' was the bug in the original probe.
    """
    if v in ("", None):
        return False
    if isinstance(v, (dict, list)) and not v:
        return False
    if isinstance(v, bool):
        return True
    if isinstance(v, (int, float)) and v == 0:
        return False
    return True


def read(path, cap):
    recs, fails = [], 0
    for i, line in enumerate(path.open(encoding="utf-8", errors="replace")):
        if i >= cap:
            break
        if not line.strip():
            continue
        try:
            recs.append(dec(line))
        except Exception:
            fails += 1
    return recs, fails


WATCH = ("before_state_hash", "after_state_hash", "duration_ms",
         "tool", "user_id")


def fill_report(cap):
    files = sorted(AUDIT.glob("audit_*.jsonl"))
    filled = collections.Counter()
    ops = collections.Counter()
    cats = collections.Counter()
    total = fails = both = 0

    for p in files:
        recs, f = read(p, cap)
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

    print("files scanned    :", len(files))
    print("records decoded  : %d  (failed: %d)" % (total, fails))
    print("both state hashes: %d  (%.1f%%)   <-- PASS SIGNAL"
          % (both, 100.0 * both / max(total, 1)))
    print("\n-- FIELD FILL RATE --")
    for k in sorted(set(list(filled) + list(WATCH))):
        c = filled.get(k, 0)
        mark = "  <-- watch" if k in WATCH else ""
        print("   %-22s %6d  %5.1f%%%s"
              % (k, c, 100.0 * c / max(total, 1), mark))
    print("\n-- DISTINCT OPERATIONS: %d --" % len(ops))
    for k, c in ops.most_common(15):
        print("   %-34s %6d" % (k or "(empty)", c))
    print("\n-- CATEGORIES --")
    for k, c in cats.most_common(12):
        print("   %-22s %6d" % (k or "(empty)", c))


def trunc(v, n=100):
    s = v if isinstance(v, str) else json.dumps(v, default=str)
    return s if len(s) <= n else s[:n] + " ...[+%d chars]" % (len(s) - n)


def schema_report(cap):
    for label, folder, glob in (("AUDIT STREAM", AUDIT, "audit_*.jsonl"),
                                ("GATES STREAM", GATES, "proposals_*.jsonl")):
        print("\n" + "=" * 62)
        print(label)
        print("=" * 62)
        files = sorted(folder.glob(glob))
        if not files:
            print("  no files found in", folder)
            continue
        recs, fails = read(files[-1], cap)
        print("source :", files[-1].name)
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
    cap = 400
    if "--cap" in sys.argv:
        cap = int(sys.argv[sys.argv.index("--cap") + 1])
    if "--schema" in sys.argv:
        schema_report(cap)
    else:
        fill_report(cap)
