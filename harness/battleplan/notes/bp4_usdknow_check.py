#!/usr/bin/env python3
"""bp4_usdknow_check.py -- anchor gate for the BP4-USDKNOW USD-composition seed.

Exit 1 if ANY seed row whose tier is VERIFIED-RUNTIME or FIXTURE-VERIFIED carries
an anchor that does not resolve to a real, non-blank, non-BLOCKED line in the
probe stdout AND literally carry both that row's `arc=<arc>` token and its
`verify` token. Exit 0 only when every such row anchors clean. No third-party deps.

The three crucible mutations this must redden (each -> exit 1):
  1. strip an anchor                 -> row anchor has no `stdout.txt:N`      -> FAIL
  2. promote a PROPOSED row to
     VERIFIED-RUNTIME / FIXTURE-VERIFIED -> that row's anchor is a doc ref, not
                                        a `stdout.txt:N` line                 -> FAIL
  3. change the arc on a VERIFIED row -> the anchored stdout line no longer
                                        contains `arc=<new-arc>`              -> FAIL

Also exit 1 if the seed does not parse, if `ratified` is truthy, or if the
stdout cannot be resolved at all (an unverifiable seed is not green -- fail-closed).

stdout resolution order: --stdout PATH -> the literal repo path on disk ->
`git show <ref>:<path>` for ref in (bp4/usdknow, HEAD, master).

Usage:
  python harness/battleplan/notes/bp4_usdknow_check.py
  python harness/battleplan/notes/bp4_usdknow_check.py --seed <json> --stdout <txt>
"""
import argparse
import json
import os
import re
import subprocess
import sys

DEFAULT_SEED = "harness/bench/corpus/usd/usd_composition_worldlabs_22.0.400.json"
STDOUT_REPO_PATH = "harness/notes/h22wl/bp4_usdknow/stdout.txt"
STDOUT_REFS = ("bp4/usdknow", "HEAD", "master")
PROMOTABLE = {"VERIFIED-RUNTIME", "FIXTURE-VERIFIED"}
ANCHOR_RE = re.compile(r"stdout\.txt:(\d+)(?:-(\d+))?")
BANNER_RE = re.compile(r"^=+\s*$")


def resolve_stdout(explicit):
    """Return (lines, source_label) or exit 1 fail-closed."""
    if explicit:
        if os.path.isfile(explicit):
            return open(explicit, encoding="utf-8").read().split("\n"), explicit
        print("[check] --stdout not found: {}".format(explicit), file=sys.stderr)
        return _fail_stdout()
    if os.path.isfile(STDOUT_REPO_PATH):
        return open(STDOUT_REPO_PATH, encoding="utf-8").read().split("\n"), STDOUT_REPO_PATH
    for ref in STDOUT_REFS:
        try:
            out = subprocess.run(
                ["git", "show", "{}:{}".format(ref, STDOUT_REPO_PATH)],
                capture_output=True, text=True, check=True,
            ).stdout
            if out.strip():
                return out.split("\n"), "git:{}:{}".format(ref, STDOUT_REPO_PATH)
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return _fail_stdout()


def _fail_stdout():
    print("[check] FAIL: could not resolve probe stdout.txt "
          "(disk {!r} or git refs {}). An unverifiable seed is not green."
          .format(STDOUT_REPO_PATH, STDOUT_REFS), file=sys.stderr)
    sys.exit(1)


def blocked_lineset(lines):
    """1-indexed line numbers inside a `===`-delimited section that contains a
    'BLOCKED' or 'Traceback' line, plus any line literally containing 'BLOCKED'."""
    # section boundaries: banner lines of '='.
    bounds = [i for i, ln in enumerate(lines) if BANNER_RE.match(ln)]
    blocked = set()
    # walk section spans between consecutive banners
    marks = bounds + [len(lines)]
    for k in range(len(marks) - 1):
        start, end = marks[k], marks[k + 1]
        seg = lines[start:end]
        if any(("BLOCKED" in ln) or ("Traceback" in ln) for ln in seg):
            blocked.update(range(start + 1, end + 1))  # 1-indexed
    for i, ln in enumerate(lines):
        if "BLOCKED" in ln:
            blocked.add(i + 1)
    return blocked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default=DEFAULT_SEED)
    ap.add_argument("--stdout", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.seed):
        print("[check] FAIL: seed not found: {}".format(args.seed), file=sys.stderr)
        sys.exit(1)
    try:
        seed = json.load(open(args.seed, encoding="utf-8"))
    except Exception as e:
        print("[check] FAIL: seed does not parse: {}".format(e), file=sys.stderr)
        sys.exit(1)

    if seed.get("ratified", None) is not False:
        print("[check] FAIL: seed 'ratified' must be exactly false, got {!r} "
              "(ratification is a human+CTO act, rule D-1)."
              .format(seed.get("ratified")), file=sys.stderr)
        sys.exit(1)

    rows = seed.get("rows", [])
    lines, src = resolve_stdout(args.stdout)
    n_lines = len(lines)
    blocked = blocked_lineset(lines)

    tier_counts = {}
    for r in rows:
        tier_counts[r.get("tier", "?")] = tier_counts.get(r.get("tier", "?"), 0) + 1

    checked = 0
    failures = []
    for r in rows:
        tier = str(r.get("tier", "")).strip().strip("*`_ ").upper()
        if tier not in PROMOTABLE:
            continue
        checked += 1
        rid = r.get("id", "?")
        arc = str(r.get("arc", "")).strip()
        verify = str(r.get("verify", "")).strip()
        anchor = str(r.get("anchor", "")).strip()

        m = ANCHOR_RE.search(anchor)
        if not m:
            failures.append((rid, tier, anchor, "no stdout.txt:<line> anchor"))
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start < 1 or end > n_lines or end < start:
            failures.append((rid, tier, anchor,
                             "line {}-{} out of range 1..{}".format(start, end, n_lines)))
            continue
        line = lines[start - 1]
        if not line.strip():
            failures.append((rid, tier, anchor, "stdout.txt:{} is blank".format(start)))
            continue
        if start in blocked:
            failures.append((rid, tier, anchor,
                             "stdout.txt:{} is inside a BLOCKED/Traceback section".format(start)))
            continue
        if not arc:
            failures.append((rid, tier, anchor, "row has no 'arc'"))
            continue
        arc_needle = "arc=" + arc
        if arc_needle not in line:
            failures.append((rid, tier, anchor,
                             "stdout.txt:{} does not carry {!r} (arc mismatch)".format(start, arc_needle)))
            continue
        if not verify:
            failures.append((rid, tier, anchor, "row has no 'verify' token"))
            continue
        if verify not in line:
            failures.append((rid, tier, anchor,
                             "stdout.txt:{} does not carry verify {!r}".format(start, verify)))
            continue
        if not args.quiet:
            print("[check] OK   {:52} {:16} {}  <- {!r}"
                  .format(rid[:52], tier, anchor, line.strip()[:56]))

    print("[check] seed: {}  (ratified={})".format(args.seed, seed.get("ratified")))
    print("[check] stdout source: {}  ({} lines, {} blocked)"
          .format(src, n_lines, len(set(range(1, n_lines + 1)) & blocked)))
    print("[check] tier counts: " + ", ".join(
        "{}={}".format(k, v) for k, v in sorted(tier_counts.items())))
    print("[check] promotable rows checked: {}".format(checked))
    if failures:
        for rid, tier, anchor, why in failures:
            print("[check] FAIL  {!r}  tier={!r}  anchor={!r}  -> {}"
                  .format(rid, tier, anchor, why), file=sys.stderr)
        print("[check] RESULT: FAIL ({} bad row(s))".format(len(failures)), file=sys.stderr)
        sys.exit(1)
    print("[check] RESULT: PASS (all {} promotable rows anchor clean)".format(checked))
    sys.exit(0)


if __name__ == "__main__":
    main()
