"""REPAIR-HEATS-01 status. Reads receipts + git; prints the DAG, not a flat list.

    python harness/heats_status.py

Reads only. Never writes, never commits.

The shape matters: Q1/Q2 BLOCK, H1/H2/H3 run in parallel worktrees, F1/F2 converge.
A flat progress bar would misrepresent it - 3/7 means something different depending
on WHICH three.
"""
import json, subprocess, glob, os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RDIR = os.path.join(ROOT, "harness", "notes", "receipts")

STAGES = {
    "Q1": ("unpoison",    "make the shipping suite runnable"),
    "Q2": ("baseline",    "record the tuple: gate + shipping"),
    "H1": ("schemas",     "wire 5 schemas, zero consumers today"),
    "H2": ("requalify",   "re-probe F1-F11, one was a phantom"),
    "H3": ("cook-cancel", "the real safety gap"),
    "F1": ("integrate",   "merge, housekeep, renormalize"),
    "F2": ("tag call",    "report conditions, do not tag"),
}
GLYPH = {"green": "#", "amber": "!", "red": "x", "running": ">", "blocked": "-", "pending": "."}


def sh(*a):
    try:
        return subprocess.run(a, cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def load():
    out = {}
    for fp in glob.glob(os.path.join(RDIR, "*.json")):
        key = os.path.basename(fp)[:2].upper()
        if key in STAGES:
            try:
                out[key] = json.load(open(fp, encoding="utf-8"))
            except Exception:
                pass
    return out


def state(sid, got):
    if sid in got:
        return got[sid].get("status", "green")
    qualified = "Q1" in got and "Q2" in got
    if sid in ("Q1", "Q2"):
        prior = [s for s in ("Q1", "Q2") if s < sid]
        return "running" if all(p in got for p in prior) else "pending"
    if sid in ("H1", "H2", "H3"):
        return "running" if qualified else "blocked"
    if sid == "F1":
        return "running" if all(h in got for h in ("H1", "H2", "H3")) else "blocked"
    return "blocked" if "F1" not in got else "running"


def line(sid, got, indent=""):
    name, sub = STAGES[sid]
    st = state(sid, got)
    r = got.get(sid)
    tail = ""
    if r:
        s = r.get("suite") or {}
        if s:
            tail = "suite {}/{} failed".format(s.get("after", "?"), s.get("failed", "?"))
        n = len(r.get("for_ruling", []))
        if n:
            tail += "   {} ruling".format(n)
    print("  {}{} {} {:<12} {:<9} {:<34} {}".format(
        indent, GLYPH[st], sid, name, st, sub, tail))


def main():
    got = load()
    qualified = "Q1" in got and "Q2" in got

    print()
    print("  REPAIR-HEATS-01   " + (sh("git", "rev-parse", "--abbrev-ref", "HEAD") or "?"))
    print("  " + "-" * 74)
    print("  QUALIFIER" + ("  [PASSED - heats unblocked]" if qualified else "  [BLOCKING]"))
    line("Q1", got); line("Q2", got)
    print()
    print("  HEATS" + ("  [parallel, own worktrees]" if qualified else "  [held - qualifier not green]"))
    for h in ("H1", "H2", "H3"):
        line(h, got, " ")
    print()
    print("  FINAL")
    line("F1", got); line("F2", got)
    print("  " + "-" * 74)

    banked = sum(len(r.get("for_ruling", [])) for r in got.values())
    blockers = sum(1 for r in got.values() for f in r.get("findings", [])
                   if f.get("severity") == "blocker")
    dfp = os.path.join(ROOT, "harness", "notes", "repair_drift.md")
    drift = 0
    if os.path.exists(dfp):
        drift = len(re.findall(r"^## D-", open(dfp, encoding="utf-8", errors="replace").read(), re.M))

    print("  receipts {}/7    ruling {}    blockers {}    drift {}".format(
        len(got), banked, blockers, drift))
    print("  {} unpushed    {} worktrees".format(
        sh("git", "rev-list", "--count", "@{u}..HEAD") or "?",
        len(sh("git", "worktree", "list").splitlines())))

    if not qualified:
        print()
        print("  gate: nothing is repaired before it can be measured.")
    elif "Q2" in got:
        print()
        print("  Q2 shipping number decides heat scope - see harness section 4.")
    print()


if __name__ == "__main__":
    main()
