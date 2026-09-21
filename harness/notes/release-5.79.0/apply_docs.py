"""Apply the v5.79.0 release documents, then fix the measured number afterwards.

Two cuts in a row needed their tag re-cut because a product-surface number was typed
BEFORE the commit that changed it. So this script does the edits with the number left as
a placeholder, and a second pass fills it in once the commit exists:

    python harness/notes/release-5.79.0/apply_docs.py --apply
    ... stage, commit ...
    python scripts/product_surface.py --diff v5.78.0 HEAD
    python harness/notes/release-5.79.0/apply_docs.py --fix-diff "33 files, +1931/-0"

It edits README.md, CHANGELOG.md and docs/releases/v5.79.0.md only. It never touches
VERSION (scripts/sync_version.py --write is the only writer) and never runs git.

Every edit asserts its anchor is present exactly once, so a drifted README fails loud
instead of silently writing nothing.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OLD, NEW = "5.78.0", "5.79.0"
PLACEHOLDER = "{{PRODUCT_DIFF}}"
NOT_LANDED = "{{NOT_LANDED}}"


def _sub(path: Path, old: str, new: str, *, count: int = 1) -> None:
    t = path.read_text(encoding="utf-8")
    n = t.count(old)
    if n != count:
        raise SystemExit("%s: expected %d occurrence(s) of %r, found %d"
                         % (path.name, count, old[:70], n))
    path.write_text(t.replace(old, new, count), encoding="utf-8")
    print("  %-14s %s" % (path.name, old[:64].replace("\n", " / ")))


def _section(draft: Path, heading: str, to_end: bool = False) -> str:
    """The body under a '## heading' in a draft.

    Stops at the next '## ' or a '---' rule -- EXCEPT with to_end, which reads to the end
    of the file. The changelog entry needs that: its own body OPENS with a '## v5.79.0'
    heading, so the default terminator fires on the content's first line and silently
    returns an empty string. That bug inserted a blank gap into CHANGELOG.md on the first
    dry run, which is exactly why this script gets dry-run in a throwaway worktree.
    """
    t = draft.read_text(encoding="utf-8")
    m = re.search(r"^## " + re.escape(heading) + r"\s*$", t, re.M)
    if not m:
        raise SystemExit("draft has no section %r" % heading)
    rest = t[m.end():]
    if to_end:
        body = rest
    else:
        end = re.search(r"^(## |---\s*$)", rest, re.M)
        body = rest[:end.start() if end else len(rest)]
    body = body.strip("\n")
    if not body.strip():
        raise SystemExit("section %r extracted EMPTY -- refusing to write nothing" % heading)
    return body


def apply_all(not_landed: str) -> int:
    readme, changelog = ROOT / "README.md", ROOT / "CHANGELOG.md"
    body_draft = HERE / "release-body.draft.md"
    rc_draft = HERE / "readme-changelog.draft.md"

    print("README.md")
    _sub(readme, "v%s · Houdini" % OLD, "v%s · Houdini" % NEW)
    _sub(readme, "tags: v%s is Latest" % OLD, "tags: v%s is Latest" % NEW)
    _sub(readme, "docs/releases/v%s.md" % OLD, "docs/releases/v%s.md" % NEW,
         count=readme.read_text(encoding="utf-8").count("docs/releases/v%s.md" % OLD))

    new_in = _section(rc_draft, 'README "New in" block (replacing 122-128)')
    t = readme.read_text(encoding="utf-8")
    m = re.search(r"^\*\*New in %s\*\*.*?(?=\n## |\n---)" % re.escape(OLD), t, re.M | re.S)
    if not m:
        raise SystemExit("README: no 'New in %s' block to replace" % OLD)
    readme.write_text(t[:m.start()] + new_in.strip() + "\n" + t[m.end():], encoding="utf-8")
    print("  README.md      New-in block replaced")

    print("CHANGELOG.md")
    entry = _section(rc_draft, "CHANGELOG entry (insert above `## v5.78.0`)", to_end=True)
    t = changelog.read_text(encoding="utf-8")
    anchor = "## v%s - " % OLD
    if t.count(anchor) != 1:
        raise SystemExit("CHANGELOG: anchor %r is not unique" % anchor)
    i = t.index(anchor)
    changelog.write_text(t[:i] + entry.strip() + "\n\n" + t[i:], encoding="utf-8")
    print("  CHANGELOG.md   entry inserted above %s" % anchor.strip())

    print("docs/releases/v%s.md" % NEW)
    notes = body_draft.read_text(encoding="utf-8").replace(NOT_LANDED, not_landed.strip())
    out = ROOT / "docs" / "releases" / ("v%s.md" % NEW)
    out.write_text(notes, encoding="utf-8")
    (HERE / "release-body.md").write_text(notes, encoding="utf-8")
    print("  written, and copied to release-body.md for `gh release create --notes-file`")

    left = sum(p.read_text(encoding="utf-8").count(PLACEHOLDER)
               for p in (readme, changelog, out, HERE / "release-body.md"))
    print("\n%d %s placeholder(s) remain -- fill them AFTER the commit." % (left, PLACEHOLDER))
    return 0


def fix_diff(measured: str) -> int:
    targets = [ROOT / "README.md", ROOT / "CHANGELOG.md",
               ROOT / "docs" / "releases" / ("v%s.md" % NEW),
               HERE / "release-body.md", HERE / "commit-msg.txt"]
    total = 0
    for p in targets:
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        n = t.count(PLACEHOLDER)
        if n:
            p.write_text(t.replace(PLACEHOLDER, measured), encoding="utf-8")
            total += n
            print("  %-22s %d filled" % (p.name, n))
    if not total:
        print("no placeholder found -- already filled, or nothing to do")
    body = ROOT / "docs" / "releases" / ("v%s.md" % NEW)
    copy = HERE / "release-body.md"
    if body.exists() and copy.exists():
        same = body.read_text(encoding="utf-8") == copy.read_text(encoding="utf-8")
        print("release-body.md matches docs/releases/v%s.md: %s" % (NEW, same))
        if not same:
            return 1
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--fix-diff", metavar="TEXT")
    ap.add_argument("--not-landed", default="", metavar="MD",
                    help="markdown for the 'Not in this release' slot")
    a = ap.parse_args()
    if a.fix_diff:
        raise SystemExit(fix_diff(a.fix_diff))
    if a.apply:
        raise SystemExit(apply_all(a.not_landed))
    ap.error("pick --apply or --fix-diff")
