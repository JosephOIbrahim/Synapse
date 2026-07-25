"""CTO-RELAY-01 status bar. Reads receipts + drift + git; prints current state.

    python harness/relay_status.py

Reads only. Never writes, never commits.
"""
import json, subprocess, glob, os, re, sys

LEGS = [
    ("L0", "ground",      "ledger, hygiene"),
    ("L1", "context",     "lop, cop census"),
    ("L2", "solaris",     "wiring seam"),
    ("L3", "panel truth", "capability map"),
    ("L4", "panel skin",  "cohere pass"),
    ("L5", "ruling",      "one gate"),
]
GLYPH = {"green": "#", "amber": "!", "red": "x", "running": ">", "pending": "."}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(*args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


def main():
    rdir = os.path.join(ROOT, "harness", "notes", "receipts")
    receipts = {}
    for fp in glob.glob(os.path.join(rdir, "L*.json")):
        try:
            r = json.load(open(fp, encoding="utf-8"))
            receipts[r.get("leg", os.path.basename(fp)[:2])] = r
        except Exception:
            pass

    # the running leg is the first without a receipt
    running = next((lid for lid, _, _ in LEGS if lid not in receipts), None)

    print()
    print("  CTO-RELAY-01   " + (sh("git", "rev-parse", "--abbrev-ref", "HEAD") or "?"))
    print("  " + "-" * 66)

    for lid, name, sub in LEGS:
        r = receipts.get(lid)
        if r:
            state = r.get("status", "green")
        elif lid == running:
            state = "running"
        else:
            state = "pending"
        s = r.get("suite", {}) if r else {}
        tail = ""
        if s:
            tail = f"suite {s.get('after','?')} / {s.get('failed','?')} failed"
        nq = len(r.get("for_ruling", [])) if r else 0
        if nq:
            tail += f"   {nq} ruling"
        print(f"  {GLYPH[state]} {lid} {name:<13} {state:<8} {sub:<18} {tail}")

    print("  " + "-" * 66)

    banked = sum(len(r.get("for_ruling", [])) for r in receipts.values())
    finds = sum(len(r.get("findings", [])) for r in receipts.values())
    blockers = sum(1 for r in receipts.values()
                   for f in r.get("findings", []) if f.get("severity") == "blocker")

    drift_fp = os.path.join(ROOT, "harness", "notes", "cto_relay_drift.md")
    drift = 0
    if os.path.exists(drift_fp):
        drift = len(re.findall(r"^## D-R", open(drift_fp, encoding="utf-8",
                                                errors="replace").read(), re.M))

    commits = sh("git", "rev-list", "--count", "master..HEAD") or "?"
    dirty = len([l for l in sh("git", "status", "--porcelain").splitlines() if l])

    print(f"  receipts {len(receipts)}/6    ruling {banked}    findings {finds} "
          f"({blockers} blocker)    drift {drift}")
    print(f"  commits {commits} unpushed    working tree {dirty} changed")
    print()
    print("  gates:  A architecture [check 0.1]   B drop.json [done]   C merge [human]")
    print()


if __name__ == "__main__":
    main()
