"""Board status, read from the manifest rather than a hardcoded layout.

    python harness/status.py

R140. The previous tool, harness/heats_status.py, was written on 2026-07-26 with
the seven REPAIR-HEATS legs baked into its print statements. It went on
rendering that board for 23 legs and 115 rulings after they stopped existing -
reporting 6/7 receipts and "Q2 shipping number decides heat scope" while thirty
legs and E0/E1 were live.

It read real receipts into a layout that no longer described anything. That is
this project's own central finding, in the tool built to report on it.

This reads legs.json. When the manifest changes, so does the board - with no
edit here.
"""
import json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "harness", "legs.json")
RDIR = os.path.join(ROOT, "harness", "notes", "receipts")
LOCKS = os.path.join(ROOT, "harness", "state", "locks")
RULINGS = os.path.join(ROOT, "harness", "notes", "CTO_RULINGS_01.md")


def git(*a):
    r = subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip()


def receipt_for(leg):
    """The COMMITTED receipt first, then the worktree draft (R127)."""
    rc = leg.get("receipt")
    if not rc:
        return None
    main = os.path.join(RDIR, rc)
    if os.path.exists(main):
        return main
    wt = leg.get("worktree")
    if wt:
        p = os.path.join(ROOT, wt, "harness", "notes", "receipts", rc)
        if os.path.exists(p):
            return p
    return None


# R14x. A receipt FILE is not a verdict. Of the 41 receipts on this tree, 17
# carry something other than plain green - amber, red, held_not_started,
# green_with_findings, green-with-collision, and four with no status at all.
# The previous rule was `if receipt_for(leg): return "done"`, so every one of
# them printed as done. H2's receipt says "held_not_started" in as many words
# and the board called it complete.
#
# That is this project's central finding for the third time: heats_status.py
# was retired for rendering real receipts into a layout that no longer
# described anything, and its replacement went on reading presence as success.
# Presence is not status. Read the field.
GREEN = {"green", "pass", "passed", "ok", "complete", "done"}


def verdict_of(path):
    """'green' | 'attention' | 'unreadable' - never inferred from existence."""
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return "unreadable"
    if not isinstance(d, dict):
        return "unreadable"
    s = str(d.get("status", "")).strip().lower()
    if s in GREEN:
        return "green"
    return "attention"


def qualifier(path):
    """The receipt's own word for why it is not plain green."""
    try:
        with open(path, encoding="utf-8") as fh:
            return str(json.load(fh).get("status") or "no status field")[:28]
    except Exception:
        return "unreadable"


def state_of(leg, held):
    if leg.get("state") in ("held", "done"):
        return leg["state"]
    if leg["id"] in held:
        return "running"
    r = receipt_for(leg)
    if r:
        return "done" if verdict_of(r) == "green" else "attention"
    unmet = [d for d in leg.get("deps", []) if d not in DONE]
    return "blocked" if unmet else "ready"


legs = json.load(open(MANIFEST, encoding="utf-8-sig"))["legs"]
held = set()
if os.path.isdir(LOCKS):
    held = {f[:-5] for f in os.listdir(LOCKS) if f.endswith(".lock")}

# A leg only satisfies a downstream dependency when its receipt is actually
# green. A halted leg must not unblock the work that was waiting on it - that
# is how H2's collision would have propagated.
DONE = set()
for l in legs:
    if l.get("state") == "done" or verdict_of(receipt_for(l)) == "green":
        DONE.add(l["id"])

rows = [(l["id"], l.get("name", ""), state_of(l, held), l) for l in legs]
by_state = {}
for r in rows:
    by_state.setdefault(r[2], []).append(r)

print()
print("  SYNAPSE  %s" % git("rev-parse", "--abbrev-ref", "HEAD"))
print("  " + "-" * 74)

for st in ("running", "attention", "ready", "blocked", "held"):
    for lid, name, _, leg in by_state.get(st, []):
        mark = {"running": ">", "attention": "!", "ready": ".",
                "blocked": "-", "held": "#"}[st]
        note = ""
        if st == "blocked":
            note = "waits on " + ",".join(d for d in leg.get("deps", []) if d not in DONE)
        elif st == "running" and lid in held:
            note = "locked"
        elif st == "attention":
            note = "receipt says: " + qualifier(receipt_for(leg))
        print("   %s %-5s %-26s %-9s %s" % (mark, lid, name[:26], st, note))

done = by_state.get("done", [])
if done:
    print("   . %d done: %s" % (len(done), " ".join(d[0] for d in done)))

print("  " + "-" * 74)

nrul = len(re.findall(r"^## RULING", open(RULINGS, encoding="utf-8-sig").read(), re.M)) \
    if os.path.exists(RULINGS) else 0
unpushed = len([x for x in git("log", "--oneline", "origin/master..HEAD").split("\n") if x])
dirty = len([x for x in git("status", "--porcelain").split("\n")
             if x and ".claude" not in x])

print("   rulings %-6d receipts %-5d unpushed %-4d dirty %d"
      % (nrul, len(done), unpushed, dirty))

# The harvest check is the one that has actually caught things (R139) - but it
# only sees COMMITTED work. R146: a leg can hold a finished-looking receipt as
# an uncommitted file in a live worktree, and branch_harvest cannot see that.
# prune_safety covers exactly that case. Neither covers it alone, and nothing
# said to run both - so the status tool runs both.
for name, script in (("branches", "branch_harvest.py"),
                     ("worktrees", "prune_safety.py"),
                     ("isolation", "../worktree_guard.py")):
    path = os.path.normpath(os.path.join(ROOT, "harness", "verify", script))
    args = [sys.executable, path]
    if name == "isolation":
        # A leg whose worktree directory exists but is not a git worktree reads
        # 'ready' here while a dispatch into it would write to the MAIN tree on
        # the live branch. The board must not stay quiet about that.
        args.append("audit")
    h = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if h.returncode == 0:
        print("   %-9s clean" % name)
    elif name == "isolation":
        n = h.stdout.count("ARMED ")
        print("   %-9s %d LEG(S) ARMED - run harness/worktree_guard.py audit"
              % (name, n))
    else:
        print("   %-9s NEEDS ATTENTION - run harness/verify/%s" % (name, script))
print()
