#!/usr/bin/env python
"""harness/protected_paths.py - the one parser + matcher for harness/protected_paths.txt.

Upgrade path 1h (harness-review 2026-09-15, finding FENCE-4): the protected set
{VERSION, harness/state/**, harness/verify/*_baseline.json} lives in ONE file and
is consumed by run.ts (post-cycle diff), orchestrate.ps1 (Test-CloseGate) and,
later, the pre-commit hook (1b). This module is the single matcher so the three
consumers cannot drift on glob semantics.

Semantics (pinned by tests/test_protected_paths.py):
  * one glob per line; `#` starts a whole-line comment; blank lines ignored
  * patterns match the WHOLE repo-relative path (anchored both ends)
  * `*` and `?` never cross `/`; `**` matches any depth, `a/**/b` also matches `a/b`
  * paths are normalised before matching: backslashes -> `/`, a leading `./` dropped

CLI (stdlib only, no repo imports - callable from a bare hython/python):
  python harness/protected_paths.py --list
  python harness/protected_paths.py --check PATH [PATH ...]
  git diff --name-only <base>..HEAD | python harness/protected_paths.py --check -
Exit 0 = no protected path among the inputs; 1 = hits (printed one per line on
stdout); 2 = error (message on stderr). `--file` overrides the set file.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FILE = os.path.join(HERE, "protected_paths.txt")

EXIT_CLEAN = 0
EXIT_HIT = 1
EXIT_ERROR = 2


def normalize(path: str) -> str:
    """Repo-relative, forward slashes, no leading `./`, no surrounding whitespace."""
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    return p


def parse(text: str) -> list[str]:
    """Parse the set file's text into a list of globs (order kept, no dedupe)."""
    globs: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        globs.append(normalize(line))
    return globs


def load(path: str = DEFAULT_FILE) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read())


def glob_to_regex(glob: str) -> str:
    """Anchored regex for one glob. `**/` -> zero or more directories, `**` -> any
    run of characters, `*` -> within one segment, `?` -> one non-slash char."""
    out: list[str] = []
    i, n = 0, len(glob)
    while i < n:
        ch = glob[i]
        if ch == "*":
            if glob.startswith("**/", i):
                out.append("(?:.*/)?")
                i += 3
                continue
            if glob.startswith("**", i):
                out.append(".*")
                i += 2
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
        i += 1
    return "^" + "".join(out) + "$"


def compile_globs(globs: list[str]) -> list[re.Pattern[str]]:
    return [re.compile(glob_to_regex(g)) for g in globs]


def is_protected(path: str, globs: list[str]) -> bool:
    p = normalize(path)
    return any(rx.match(p) for rx in compile_globs(globs))


def protected_hits(paths, globs: list[str]) -> list[str]:
    """The protected paths among `paths`, normalised, first-seen order, deduped."""
    rxs = compile_globs(globs)
    seen: set[str] = set()
    hits: list[str] = []
    for raw in paths:
        p = normalize(raw)
        if not p or p in seen:
            continue
        if any(rx.match(p) for rx in rxs):
            seen.add(p)
            hits.append(p)
    return hits


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--file", default=DEFAULT_FILE,
                    help="protected set file (default: harness/protected_paths.txt)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true", help="print the globs, one per line")
    g.add_argument("--check", nargs="+", metavar="PATH",
                   help="paths to test; a single '-' reads one path per line from stdin")
    a = ap.parse_args(argv)
    try:
        globs = load(a.file)
    except OSError as e:
        sys.stderr.write("protected_paths: cannot read %s: %s\n" % (a.file, e))
        return EXIT_ERROR
    if not globs:
        sys.stderr.write("protected_paths: %s declares no globs - refusing to vouch for an empty set\n" % a.file)
        return EXIT_ERROR
    if a.list:
        for gl in globs:
            sys.stdout.write(gl + "\n")
        return EXIT_CLEAN
    paths = a.check
    if paths == ["-"]:
        paths = sys.stdin.read().splitlines()
    hits = protected_hits(paths, globs)
    for h in hits:
        sys.stdout.write(h + "\n")
    return EXIT_HIT if hits else EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
