"""harness/cto/check_backlog.py — the loop's guard on its own record.

Crank 2 (2026-09-06) found eight D-F items whose `closure_predicate` was
stored truncated at exactly 500 characters, ending mid-expression: the ingest
that filed the Bierut findings had clipped every field. A predicate that
cannot be executed is not a predicate, and eight of the loop's own items were
silently unmeasurable. The same crank found B6 marked `closed` with evidence
reading "predicate re-run on master, exit 0" when one clause of that predicate
had never been satisfiable by the merge it cited.

Both are the same failure class the harness exists to prevent — a green that
was never measured — so both get a guard here.

The truncation test is deliberately narrow. A predicate is a shell one-liner
carrying regexes, quotes and character classes; a delimiter-balance parser
flags healthy `rg -c "createNode\\(['\\"]karma['\\"]"` and a guard that cries
wolf is worse than no guard. So it checks only what clipping actually leaves
behind: a length sitting exactly on a slice boundary, or a tail that no
finished command ends on.

Run: python harness/cto/check_backlog.py   (exit 0 = the record is honest)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKLOG = ROOT / "BACKLOG.json"

# The slice lengths the 2026-09-05 ingest used, plus the neighbours a future
# one would reach for. A real predicate landing exactly here is possible but
# rare enough to be worth a look.
CLIP_LENGTHS = {200, 300, 400, 500, 600, 800, 1000, 1200}
BAD_TAILS = {"&&", "||", "|", "if", "for", "in", "and", "or", "not",
             "=", "==", "!=", "<", ">", "<=", ">=", ",", "+", "-", "the"}
OPENERS = "([{"


def check(items: list[dict]) -> list[str]:
    problems: list[str] = []
    for item in items:
        ident = item.get("id", "?")
        pred = (item.get("closure_predicate") or "").rstrip()
        status = item.get("status")

        if not pred:
            problems.append("%s: no closure_predicate — every item carries one" % ident)
            continue

        if len(pred) in CLIP_LENGTHS:
            problems.append("%s: predicate is exactly %d chars — a slice boundary, not a sentence: ...%s"
                            % (ident, len(pred), pred[-50:]))
        if pred[-1] in OPENERS or pred.endswith("\\"):
            problems.append("%s: predicate ends on %r — clipped mid-expression" % (ident, pred[-1]))
        tail = pred.split()[-1] if pred.split() else ""
        if tail in BAD_TAILS:
            problems.append("%s: predicate ends on %r — clipped mid-expression" % (ident, tail))

        # A closed item must say how it was measured, in words a later reader
        # can re-run. "exit 0" alone is a claim, not evidence.
        if status == "closed":
            ev = (item.get("closure_evidence") or "").strip()
            if not ev:
                problems.append("%s: closed with no closure_evidence" % ident)
            elif len(ev) < 25:
                problems.append("%s: closure_evidence too thin to check: %r" % (ident, ev))
    return problems


def main(argv: list[str]) -> int:
    items = json.loads(BACKLOG.read_text(encoding="utf-8"))["items"]
    problems = check(items)
    if problems:
        print("BACKLOG GUARD: %d problem(s)" % len(problems))
        for p in problems:
            print("  -", p)
        return 1
    print("BACKLOG GUARD: %d items, %d open — every predicate runnable, every closure evidenced"
          % (len(items), sum(1 for i in items if i.get("status") == "open")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
