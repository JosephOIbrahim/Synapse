"""Refuse to call a leg done while its branch holds commits master does not.

R139. Four times in two days I reported work as pushed while master was behind.
The pattern never varied: a leg commits to its own branch, I read its receipt,
I rule on its findings, and I never take the branch. The most expensive instance
was INGEST-01 - 1,073,328 insertions, the entire H22 node corpus and both scout
reports, absent from master while the work was reported complete.

Reading a receipt is not merging a branch. Nothing in the harness said so.

This says so. It runs in the release path and it fails loudly, naming the leg,
the branch, and the count.
"""
import json, os, subprocess, sys

MANIFEST = "harness/legs.json"


def git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.stdout.strip(), r.returncode


def branch_exists(ref):
    _, rc = git("rev-parse", "--verify", "--quiet", ref)
    return rc == 0


def receipt_landed(leg):
    """Committed receipt in the main tree, or pinned done in the manifest."""
    if leg.get("state") == "done":
        return True
    rc = leg.get("receipt")
    return bool(rc) and os.path.exists(os.path.join("harness", "notes", "receipts", rc))


def survey():
    legs = json.load(open(MANIFEST, encoding="utf-8-sig"))["legs"]
    stranded, clean, absent, declared = [], [], [], []
    for leg in legs:
        br = leg.get("branch")
        if not br:
            continue
        ref = br if branch_exists(br) else ("origin/" + br)
        if not branch_exists(ref):
            absent.append(leg["id"])
            continue
        out, _ = git("rev-list", "--count", "HEAD.." + ref)
        n = int(out or 0)
        if not n:
            clean.append(leg["id"])
            continue
        # A leg can be unmerged ON PURPOSE - superseded by another leg's
        # composition, or held for review. Without this the check flags them
        # forever, and a check that cries wolf gets ignored (R129).
        ms = leg.get("merge_status")
        if ms in ("superseded", "held"):
            declared.append((leg["id"], ref, n, ms, leg.get("merge_note", "")))
        else:
            stranded.append((leg["id"], ref, n, receipt_landed(leg)))
    return stranded, clean, absent, declared


if __name__ == "__main__":
    stranded, clean, absent, declared = survey()

    print("BRANCH HARVEST")
    print("=" * 72)

    # A leg whose receipt landed but whose branch is unmerged is the defect.
    # A leg still running is expected to be ahead and is NOT a failure.
    hard = [s for s in stranded if s[3]]
    soft = [s for s in stranded if not s[3]]

    if hard:
        print("  STRANDED - receipt landed, branch NOT merged:")
        for lid, ref, n, _ in hard:
            print("    %-6s %-42s %d commit(s)" % (lid, ref, n))
        print()
        print("  Merge each before calling this work shipped:")
        for lid, ref, _, _ in hard:
            print("    git merge %s --no-ff" % ref)
    else:
        print("  no stranded work - every landed leg's branch is merged")

    if soft:
        print()
        print("  ahead but still running (expected, not a failure):")
        for lid, ref, n, _ in soft:
            print("    %-6s %-42s %d commit(s)" % (lid, ref, n))

    if declared:
        print()
        print("  unmerged ON PURPOSE, declared in the manifest:")
        for lid, ref, n, ms, why in declared:
            print("    %-6s %-34s %d commit(s)  [%s]" % (lid, ref, n, ms))
            if why:
                print("           %s" % why[:96])

    print()
    print("  merged clean : %d" % len(clean))
    print("  no branch yet: %d" % len(absent))
    print()
    print("RESULT:", "PASS" if not hard else "FAIL - %d leg(s) stranded" % len(hard))
    sys.exit(0 if not hard else 1)
