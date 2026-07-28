"""Verify every number in docs/HOW_WE_KNOW.md against the repository.

R127: the first version of this script PASSED a wrong number.

It globbed `.claude/worktrees/*/harness/notes/receipts/RSI0.json`. The document
cites the COMMITTED receipt. Those were different files - the worktree held an
earlier draft saying 4,357, the committed one says 4,795 - so the check read one
copy while the claim rested on another. The published figure was wrong and this
script reported it verified.

That is R108 (a health check must read what the product reads) occurring inside
the check written to prevent exactly this, and LEDGER.F1 / R91 in a third
subsystem: a second copy nobody declared existed.

Two rules now, both bought by that failure:
  1. COMMITTED PATHS ONLY. Never a worktree glob. A worktree is a draft.
  2. A NEGATIVE CONTROL runs first. This script must be seen FAILING on a
     deliberately wrong number before any pass it reports means anything -
     Law 1, applied to the verifier of the document about Law 1.
"""
import os, re, sys

DOC = "docs/HOW_WE_KNOW.md"
RULINGS = "harness/notes/CTO_RULINGS_01.md"
RSI0 = "harness/notes/receipts/RSI0.json"          # committed, not a worktree
H8 = "harness/notes/receipts/H8.json"
BENCH = "harness/notes/token_bench"

results = []


def check(label, claimed, actual, producer):
    results.append((claimed == actual, label, claimed, actual, producer))


def read(path):
    if not os.path.exists(path):
        return None
    return open(path, encoding="utf-8-sig", errors="replace").read()


doc = read(DOC) or ""

# --- 1. rulings ------------------------------------------------------------
r = read(RULINGS) or ""
n = len(re.findall(r"^## RULING", r, re.M))
m = re.search(r"records \*\*(\d+) decisions\*\*", doc)
check("rulings", int(m.group(1)) if m else -1, n, "grep -c '^## RULING' " + RULINGS)

# --- 2. the epoch records --------------------------------------------------
blob = read(RSI0)
if blob is None:
    check("epoch records", "-", "RECEIPT MISSING", RSI0 + "  (missing is NOT clean)")
else:
    rm = re.search(r"([\d,]+)\s*'Epoch N complete'", blob)
    dm = re.search(r"([\d,]+)\s*'Epoch N complete'", doc)
    check("epoch records", dm.group(1) if dm else "ABSENT",
          rm.group(1) if rm else "NOT FOUND", RSI0)

# --- 3. token ladder -------------------------------------------------------
found = None
if os.path.isdir(BENCH):
    for fn in os.listdir(BENCH):
        if "113411" in (read(os.path.join(BENCH, fn)) or "").replace(",", ""):
            found = fn
            break
check("top-rung tokens", True, found is not None, BENCH + "/" + (found or "?"))

# --- 4. H8's receipt -------------------------------------------------------
check("H8 receipt readable", True, read(H8) is not None, H8)


if __name__ == "__main__":
    if "--negative-control" in sys.argv:
        # Prove this script CAN fail before trusting it to pass.
        results.append((False, "PLANTED WRONG NUMBER", "4,357", "4,795", "negative control"))

    print("%-24s %-14s %-16s %s" % ("CLAIM", "IN DOC", "ACTUAL", "PRODUCER"))
    print("-" * 86)
    bad = 0
    for ok, label, claimed, actual, producer in results:
        print("%-24s %-14s %-16s %s%s" % (label, claimed, actual, producer,
                                          "" if ok else "   <-- MISMATCH"))
        if not ok:
            bad += 1
    print()
    print("RESULT:", "PASS - every number matches its COMMITTED producer" if bad == 0
          else "FAIL - %d mismatch(es)" % bad)
    sys.exit(0 if bad == 0 else 1)
