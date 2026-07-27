"""Refuse to prune a worktree whose receipt exists ONLY inside it.

2026-07-27, self-inflicted: a housekeeping pass removed the worktrees of H9, C0
and S1. All three had finished and been ruled on. None had COMMITTED its receipt
- read-only legs write to harness/notes/** but the fence denies `git commit`, so
their receipts lived only in the worktree.

The prune destroyed them. The findings survive as rulings with anchors (R95-R98,
R117, R121-R122); the raw evidence does not.

R103 already saw the seam and answered it the other way: "a read-only leg's
product IS its receipt, and R93 is amended to say so." What it did not say is
where that receipt has to END UP. A receipt that only ever exists in a workspace
is one cleanup away from gone.

Run this BEFORE any worktree removal. It names what would be lost.
"""
import json, os, sys

MANIFEST = "harness/legs.json"
MAIN = os.path.join("harness", "notes", "receipts")


def at_risk():
    d = json.load(open(MANIFEST, encoding="utf-8-sig"))
    risk, safe, nowt = [], [], []
    for leg in d["legs"]:
        wt, rc = leg.get("worktree"), leg.get("receipt")
        if not wt or not rc:
            continue
        if not os.path.isdir(wt):
            nowt.append(leg["id"])
            continue
        in_wt = os.path.exists(os.path.join(wt, "harness", "notes", "receipts", rc))
        in_main = os.path.exists(os.path.join(MAIN, rc))
        if in_wt and not in_main:
            risk.append((leg["id"], wt, rc))
        elif in_main:
            safe.append(leg["id"])
    return risk, safe, nowt


if __name__ == "__main__":
    risk, safe, nowt = at_risk()

    print("WORKTREE PRUNE SAFETY")
    print("=" * 68)
    if risk:
        print("  AT RISK - receipt exists ONLY in the worktree:")
        for lid, wt, rc in risk:
            print("    %-6s %s" % (lid, os.path.join(wt, "harness/notes/receipts", rc)))
        print()
        print("  Copy each into %s before pruning." % MAIN)
    else:
        print("  none at risk - every live worktree's receipt is also in the main tree")

    print()
    print("  safe (receipt in main tree) : %d" % len(safe))
    print("  no worktree on disk         : %d" % len(nowt))
    print()
    print("RESULT:", "SAFE TO PRUNE" if not risk else "DO NOT PRUNE - %d receipt(s) would be lost" % len(risk))
    sys.exit(0 if not risk else 1)
