"""Clear the way for `git merge --ff-only pnl/integration`, without losing anything.

THE PROBLEM. Work that started life as an untracked file in the main tree -- the panel spec,
the composed gate, the mission file, this release's own notes -- was later committed on a
branch. Git then refuses the fast-forward:

    error: The following untracked working tree files would be overwritten by merge

THE RULE. An untracked file is removed ONLY when it is byte-identical to the version the
integration branch carries. Anything that differs is reported and the script exits non-zero,
because a difference means the main-tree copy has an edit the branch never received -- and
deleting it would silently drop that edit. That happened once already this session: the
composed gate is edited in the main tree and synced to the instrument branch by hand.

    python harness/notes/release-5.79.0/preflight_ff.py            # report only
    python harness/notes/release-5.79.0/preflight_ff.py --clear    # remove the identical ones

Exit 0 = nothing blocks the fast-forward. Exit 1 = a file differs; sync it to its branch
first. Exit 2 = git said no.
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parents[3]
BRANCH = "pnl/integration"


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clear", action="store_true", help="remove the byte-identical ones")
    ap.add_argument("--branch", default=BRANCH)
    a = ap.parse_args()

    listing = git("ls-tree", "-r", "--name-only", a.branch)
    if listing.returncode:
        print("git ls-tree failed:", listing.stderr.strip())
        return 2
    tracked = set(listing.stdout.split("\n"))

    st = git("status", "--porcelain", "--untracked-files=all")
    if st.returncode:
        print("git status failed:", st.stderr.strip())
        return 2
    untracked = [ln[3:].strip().strip('"') for ln in st.stdout.splitlines()
                 if ln.startswith("?? ")]

    collisions = [p for p in untracked if p in tracked]
    if not collisions:
        print("nothing blocks the fast-forward")
        return 0

    same, differ = [], []
    for rel in sorted(collisions):
        local = (ROOT / rel).read_bytes()
        show = subprocess.run(["git", "show", f"{a.branch}:{rel}"], cwd=str(ROOT),
                              capture_output=True)
        if show.returncode:
            differ.append((rel, "?", "not readable on " + a.branch))
            continue
        # compare with newlines normalised: the repo stores LF, the working copy may hold CRLF
        l, b = local.replace(b"\r\n", b"\n"), show.stdout.replace(b"\r\n", b"\n")
        (same if l == b else differ).append(
            (rel, sha(l), sha(b)) if l != b else rel)

    for rel in same:
        print("  identical  %s" % rel)
    for rel, h1, h2 in differ:
        print("  DIFFERS    %s   local=%s branch=%s" % (rel, h1, h2))

    if differ:
        print("\n%d file(s) differ from %s. Sync each to its branch and commit there before "
              "clearing -- deleting them here would drop those edits." % (len(differ), a.branch))
        return 1

    if not a.clear:
        print("\n%d identical file(s) block the fast-forward. Re-run with --clear." % len(same))
        return 1

    for rel in same:
        (ROOT / rel).unlink()
        print("  removed    %s" % rel)
    for d in sorted({str(Path(r).parent) for r in same}, key=len, reverse=True):
        p = ROOT / d
        try:
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
                print("  rmdir      %s" % d)
        except OSError:
            pass
    print("\ncleared %d file(s); the fast-forward restores every one of them." % len(same))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
