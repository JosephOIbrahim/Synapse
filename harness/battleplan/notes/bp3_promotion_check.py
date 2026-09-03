#!/usr/bin/env python3
"""bp3_promotion_check.py  --  anchor gate for the BP3-CORPUS promotion proposal.

Exit 1 if ANY promotion row whose *proposed tier* is VERIFIED-RUNTIME or
FIXTURE-VERIFIED carries an anchor that does not resolve to a real, non-blank,
non-BLOCKED line in the probe stdout (`harness/notes/h22wl/bp3_probes/stdout.txt`).
Exit 0 only when every such row's anchor greps clean. No third-party deps.

The three crucible mutations this must redden:
  1. strip an anchor          -> row has no `stdout.txt:N`      -> FAIL
  2. promote a BLOCKED probe  -> anchor line is inside a BLOCKED block -> FAIL
  3. change a tier on a row    -> that row's anchor is not a stdout line -> FAIL
     with no stdout artifact       (e.g. a review/supplementary citation)

stdout resolution order: --stdout PATH  ->  the literal repo path on disk  ->
`git show <ref>:<path>` for ref in (bp3/probe, HEAD, master). Fail-closed: if
stdout cannot be resolved at all, exit 1 (an unverifiable proposal is not green).

Usage:
  python harness/battleplan/notes/bp3_promotion_check.py
  python harness/battleplan/notes/bp3_promotion_check.py --doc <md> --stdout <txt>
"""
import argparse
import os
import re
import subprocess
import sys

DEFAULT_DOC = "docs/reviews/bp3-h22-promotion-proposal.md"
STDOUT_REPO_PATH = "harness/notes/h22wl/bp3_probes/stdout.txt"
STDOUT_REFS = ("bp3/probe", "HEAD", "master")
PROMOTABLE = {"VERIFIED-RUNTIME", "FIXTURE-VERIFIED"}
ANCHOR_RE = re.compile(r"stdout\.txt:(\d+)(?:-(\d+))?")
BLOCK_TITLE_RE = re.compile(r"^(P|B|S)-\d+\b")


def resolve_stdout(explicit):
    """Return (lines, source_label) or exit 1 fail-closed."""
    if explicit:
        if os.path.isfile(explicit):
            return open(explicit, encoding="utf-8").read().split("\n"), explicit
        print(f"[check] --stdout not found: {explicit}", file=sys.stderr)
        return _fail_stdout()
    if os.path.isfile(STDOUT_REPO_PATH):
        return open(STDOUT_REPO_PATH, encoding="utf-8").read().split("\n"), STDOUT_REPO_PATH
    for ref in STDOUT_REFS:
        try:
            out = subprocess.run(
                ["git", "show", f"{ref}:{STDOUT_REPO_PATH}"],
                capture_output=True, text=True, check=True,
            ).stdout
            if out.strip():
                return out.split("\n"), f"git:{ref}:{STDOUT_REPO_PATH}"
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return _fail_stdout()


def _fail_stdout():
    print("[check] FAIL: could not resolve probe stdout.txt "
          f"(disk {STDOUT_REPO_PATH!r} or git refs {STDOUT_REFS}). "
          "An unverifiable proposal is not green.", file=sys.stderr)
    sys.exit(1)


def blocked_lineset(lines):
    """1-indexed line numbers that live inside a BLOCKED probe block, plus any
    line literally containing 'BLOCKED'."""
    # block boundaries: each P-/B-/S- title line starts a block until the next.
    titles = [i for i, ln in enumerate(lines) if BLOCK_TITLE_RE.match(ln)]
    blocked = set()
    for k, start in enumerate(titles):
        end = titles[k + 1] if k + 1 < len(titles) else len(lines)
        if any("BLOCKED" in lines[j] for j in range(start, end)):
            blocked.update(range(start + 1, end + 1))  # 1-indexed
    for i, ln in enumerate(lines):
        if "BLOCKED" in ln:
            blocked.add(i + 1)
    return blocked


def parse_promotion_rows(doc_text):
    """Yield (proposed_tier, anchor_cell, claim_cell, lineno) for every data row
    of every markdown table that has both a 'proposed tier' and an 'anchor'
    column. Table-agnostic: catches Table A, Table B, or any future table."""
    lines = doc_text.split("\n")
    i = 0
    while i < len(lines):
        # a table header row is a '|...|' line whose next line is a '---' sep.
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) \
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header = [c.strip().lower() for c in _cells(lines[i])]
            pt_idx = next((j for j, h in enumerate(header) if "proposed" in h and "tier" in h), None)
            an_idx = next((j for j, h in enumerate(header) if h == "anchor" or h.startswith("anchor")), None)
            id_idx = next((j for j, h in enumerate(header) if "claim" in h or h.startswith("id")), 0)
            i += 2
            if pt_idx is None or an_idx is None:
                # not a promotion table; skip its body
                while i < len(lines) and lines[i].lstrip().startswith("|"):
                    i += 1
                continue
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                cells = _cells(lines[i])
                if len(cells) > max(pt_idx, an_idx):
                    yield (cells[pt_idx].strip(),
                           cells[an_idx].strip(),
                           cells[id_idx].strip() if len(cells) > id_idx else "?",
                           i + 1)
                i += 1
        else:
            i += 1


def _cells(row):
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return s.split("|")


def _tier_norm(cell):
    """The bare tier token if the cell IS exactly a promotable tier (ignoring
    surrounding markdown emphasis/backticks); else the raw cell."""
    t = cell.strip().strip("*`_ ").upper()
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--doc", default=DEFAULT_DOC)
    ap.add_argument("--stdout", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.doc):
        print(f"[check] FAIL: promotion doc not found: {args.doc}", file=sys.stderr)
        sys.exit(1)

    doc_text = open(args.doc, encoding="utf-8").read()
    lines, src = resolve_stdout(args.stdout)
    n_lines = len(lines)
    blocked = blocked_lineset(lines)

    checked = 0
    failures = []
    for tier, anchor, claim, lineno in parse_promotion_rows(doc_text):
        if _tier_norm(tier) not in PROMOTABLE:
            continue
        checked += 1
        m = ANCHOR_RE.search(anchor)
        if not m:
            failures.append((claim, lineno, tier, anchor,
                             "no stdout.txt:<line> anchor"))
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1 or end > n_lines or end < start:
            failures.append((claim, lineno, tier, anchor,
                             f"line {start}-{end} out of range 1..{n_lines}"))
            continue
        if not lines[start - 1].strip():
            failures.append((claim, lineno, tier, anchor,
                             f"stdout.txt:{start} is blank"))
            continue
        if start in blocked:
            failures.append((claim, lineno, tier, anchor,
                             f"stdout.txt:{start} is inside a BLOCKED probe block"))
            continue
        if not args.quiet:
            print(f"[check] OK   {claim:42} {tier:16} {anchor}  "
                  f"<- {lines[start - 1].strip()[:60]!r}")

    print(f"[check] stdout source: {src}  ({n_lines} lines, "
          f"{len(set(range(1, n_lines + 1)) & blocked)} blocked)")
    print(f"[check] promotable rows checked: {checked}")
    if failures:
        for claim, lineno, tier, anchor, why in failures:
            print(f"[check] FAIL doc:{lineno}  {claim!r}  proposed={tier!r}  "
                  f"anchor={anchor!r}  -> {why}", file=sys.stderr)
        print(f"[check] RESULT: FAIL ({len(failures)} bad anchor(s))", file=sys.stderr)
        sys.exit(1)
    print(f"[check] RESULT: PASS (all {checked} promotable rows anchor clean)")
    sys.exit(0)


if __name__ == "__main__":
    main()
