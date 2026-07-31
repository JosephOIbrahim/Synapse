#!/usr/bin/env python3
"""CLEAR — progress.py

The 10-minute ADHD-friendly bar. READS shared state; NEVER narrates. If a
file is unreadable or a check can't be made, it prints '?' — never a guess.

  python harness/clear/progress.py --once        # one bar, then exit
  python harness/clear/progress.py               # loop, default 600s
  python harness/clear/progress.py --interval 300

The bar reads:
  - verify.py (subprocess) for the 8 predicates
  - CHAMPION.md for per-line champion state (open/closed/parked)
  - LOG.md tail for the last attempt
Unreadable -> '?'. No fabricated "in progress".
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

# Windows consoles default to cp1252, which can't encode box-drawing. Force UTF-8;
# if the stream can't, fall back to ASCII glyphs so the bar always renders.
_UTF_OK = False
try:
    sys.stdout.reconfigure(encoding="utf-8")
    _UTF_OK = True
except Exception:
    try:
        sys.stdout.reconfigure(encoding="ascii")
    except Exception:
        pass

REPO = Path(__file__).resolve().parents[2]
CLEAR = Path(__file__).resolve().parent
VERIFY = CLEAR / "verify.py"
CHAMPION = CLEAR / "CHAMPION.md"
LOG = CLEAR / "LOG.md"
PLAN = CLEAR / "PLAN.md"

BOX = {"PASS": "█", "FAIL": "░", "PENDING": "▒"}
LABEL = {"PASS": "done", "FAIL": "open ", "PENDING": "wait "}


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _verify_results():
    try:
        p = subprocess.run(
            [sys.executable, str(VERIFY), "--json"],
            cwd=str(REPO), capture_output=True, text=True, timeout=90,
        )
        if p.returncode not in (0, 1):
            return None
        import json
        return json.loads(p.stdout)
    except Exception:
        return None


def _line_modes():
    """Read the SOLO/ORCHESTRATED mode per line from PLAN.md headers."""
    plan = _read(PLAN) or ""
    modes = {}
    cur = "?"
    for line in plan.splitlines():
        m = re.match(r"## (L\d+) · (\S+) · MODE: (\S+)", line)
        if m:
            modes[m.group(1)] = (m.group(2), m.group(3).rstrip(":"))
    return modes


def _last_log():
    log = _read(LOG) or ""
    rows = [r for r in log.splitlines() if r.startswith("| 20") or r.startswith("|202")]
    return rows[-1] if rows else "?"


def _bar(results):
    if results is None:
        return "[ verifier unreachable — run python harness/clear/verify.py ]"
    cells = "".join(BOX.get(r["status"], "?") for r in results)
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    return f"[{cells}]  {n_pass}/8 clear · {n_fail} open"


def render():
    ts = time.strftime("%H:%M")
    results = _verify_results()
    modes = _line_modes()
    if _UTF_OK:
        top, side, bot, mid = "┌─", "│", "└", "·"
    else:
        top, side, bot, mid = "+-", "|", "+", "."
    rule = "-" * 56
    print(f"\n{top} CLEAR {mid} {ts} {rule}")
    print(f"{side} bar   {_bar(results)}")
    if results:
        for r in results:
            tag = LABEL.get(r["status"], "?  ")
            print(f"{side}  {tag} {r['id']}  {r['label']}")
    else:
        print(f"{side}  ?     verify.py did not return a result")
    if modes:
        print(f"{side} lines " + " . ".join(f"{k}:{v[1]}" for k, v in sorted(modes.items())))
    else:
        print(f"{side} lines ?")
    print(f"{side} last  {_last_log()[:96]}")
    print(f"{bot}{rule}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=600)
    args = ap.parse_args()

    if args.once:
        render()
        return

    while True:
        render()
        time.sleep(args.interval)


if __name__ == "__main__":
    main()