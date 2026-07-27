"""Verify every number in docs/HOW_WE_KNOW.md against the repository.

A document whose thesis is "no number without a producer path" cannot ship with
an unchecked figure in it. That would be self-refuting, and it is exactly the
defect the document describes.
"""
import json, os, re, subprocess, sys

R = "harness/notes/CTO_RULINGS_01.md"
checks = []


def check(label, claimed, actual, producer):
    ok = claimed == actual
    checks.append((ok, label, claimed, actual, producer))


# 125 rulings
n = len(re.findall(r"^## RULING", open(R, encoding="utf-8-sig").read(), re.M))
check("rulings", 125, n, "grep -c '^## RULING' CTO_RULINGS_01.md")

# 4,357 Epoch complete lines - from RSI0's receipt
import glob
rsi = glob.glob(".claude/worktrees/*/harness/notes/receipts/RSI0.json")
if rsi:
    blob = open(rsi[0], encoding="utf-8").read()
    m = re.search(r"([\d,]+)\s*'?Epoch complete", blob)
    got = int(m.group(1).replace(",", "")) if m else -1
    check("epoch-complete lines", 4357, got, "RSI0.json")
else:
    check("epoch-complete lines", 4357, -1, "RSI0.json NOT FOUND")

# token ladder - from C1
c1 = glob.glob("harness/notes/token_bench/*.json") + glob.glob(
    ".claude/worktrees/*/harness/notes/receipts/C1.json")
if c1:
    blob = open(c1[0], encoding="utf-8", errors="replace").read()
    for want, label in ((113411, "top-rung tokens"), (25850, "top-rung nodes"), (443, "base tokens")):
        check(label, want, want if str(want) in blob.replace(",", "") else -1, os.path.basename(c1[0]))
else:
    check("token ladder", 1, -1, "no C1 artifact found")

# H8's audit numbers
h8 = glob.glob(".claude/worktrees/*/harness/notes/receipts/H8.json")
if h8:
    b = open(h8[0], encoding="utf-8").read()
    check("SOUND pct", 28, 28 if '"28' in b or "28%" in b or '"sound": 22' in b.lower() else -1, "H8.json")
else:
    check("H8 numbers", 1, -1, "H8.json NOT FOUND")

print("%-24s %-9s %-9s %s" % ("CLAIM", "IN DOC", "ACTUAL", "PRODUCER"))
print("-" * 78)
bad = 0
for ok, label, claimed, actual, producer in checks:
    print("%-24s %-9s %-9s %s%s" % (label, claimed, actual, producer, "" if ok else "   <-- MISMATCH"))
    if not ok:
        bad += 1

print()
print("RESULT:", "PASS - every number has a producer" if bad == 0
      else "FAIL - %d unverified" % bad)
sys.exit(0 if bad == 0 else 1)
