"""Pre-trust worktree paths so a dispatched leg never blocks on a trust dialog.

Found 2026-07-26: two legs launched at 09:00, showed 2 CPU-seconds after 13
minutes and wrote nothing. Not stalled, not crashed - waiting at "do you trust
the files in this folder?" with nobody there to answer.

The dispatcher creates a fresh worktree and immediately launches an agent into
it. A brand-new directory is untrusted by default, so the agent blocks before
its first token. Silent, indefinite, and indistinguishable from slow work
unless you check CPU.

Idempotent. Safe to run before every dispatch.
"""
import json, os, sys, subprocess

CFG = os.path.expanduser("~/.claude.json")


def worktree_paths(repo):
    out = subprocess.run(["git", "worktree", "list"], cwd=repo,
                         capture_output=True, text=True, timeout=30).stdout
    paths = []
    for line in out.splitlines():
        p = line.split()[0] if line.strip() else None
        if p:
            paths.append(p.replace("\\", "/"))
    return paths


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\User\SYNAPSE"
    cfg = json.load(open(CFG, encoding="utf-8"))
    projects = cfg.setdefault("projects", {})

    added, already = [], []
    for p in worktree_paths(repo):
        entry = projects.get(p)
        if entry and entry.get("hasTrustDialogAccepted"):
            already.append(p)
            continue
        if entry is None:
            projects[p] = {"hasTrustDialogAccepted": True,
                           "allowedTools": [], "history": []}
        else:
            entry["hasTrustDialogAccepted"] = True
        added.append(p)

    if added:
        # write via temp + replace so a crash mid-write cannot corrupt the config
        tmp = CFG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
        os.replace(tmp, CFG)

    for p in already:
        print(f"  trusted already  {p}")
    for p in added:
        print(f"  TRUSTED NOW      {p}")
    print(f"\n{len(added)} added, {len(already)} already trusted")


if __name__ == "__main__":
    main()
