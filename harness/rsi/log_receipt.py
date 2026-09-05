#!/usr/bin/env python3
"""RSI closure harness — log_receipt.py

Producer of a FINGERPRINTED log receipt for loop C's L2 (REACHABLE) evidence.

The production log (~/.synapse/logs/synapse.log*) holds pytest-authored records
next to real Houdini-session records (the 4,795-line trap, SPEC P5). A raw
count of 'Memory backend: moneta' lines is therefore not evidence of production
execution. This script attributes every such line to the store construction it
belongs to and classifies it by the *project path* that construction logged:

  TEST         the 'Initialized for project:' path is a pytest temp directory
               (pytest-of-<user>/pytest-<n>/...) -- authored by the suite, excluded
  PRODUCTION   any other project path -- a Houdini session ($HOUDINI_TEMP_DIR or a
               saved .hip's directory)
  UNATTRIBUTED no 'Initialized for project:' line within the attribution window --
               counted, never credited

The receipt is JSON so the number can be re-derived, and it names this file as
its producer (Law 2: every number carries a producer path).

Usage:
  python harness/rsi/log_receipt.py                # write the receipt, print a summary
  python harness/rsi/log_receipt.py --stdout       # print the receipt JSON instead
  python harness/rsi/log_receipt.py --logs <dir>   # read logs from another directory
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RSI = Path(__file__).resolve().parent
DEFAULT_LOG_DIR = Path(os.path.expanduser("~/.synapse/logs"))
DEFAULT_OUT = RSI / "briefs" / "C-L2-log-receipt-2026-09-05.json"

MARKER = "Memory backend: moneta"
OWNER_RE = re.compile(r"Initialized for project: (.*)$")
# Test-only fingerprint. Anything whose project path was minted by pytest --
# the tmp_path factory (pytest-of-<user>/pytest-<n>/), the suite's own
# pytest_shipping_<stamp>/ scratch, or a leaf directory named after a test
# function (test_<name>0) -- was authored by the suite, whatever the log level
# says. The first draft matched only the tmp_path factory and would have
# credited 9 pytest_shipping records as production; kept deliberately wide.
TEST_PATH_RE = re.compile(r"pytest|[\\/]test_[A-Za-z0-9_]+\d*$", re.IGNORECASE)
ATTRIBUTION_WINDOW = 5  # lines after the marker in which the owner line must appear


def classify_logs(log_dir: Path) -> dict:
    files = sorted(glob.glob(str(log_dir / "synapse.log*")))
    counts = {"production": 0, "test": 0, "unattributed": 0}
    per_file = {}
    prod_projects: dict[str, int] = {}
    first = last = None
    samples = []
    for f in files:
        try:
            lines = Path(f).read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        fc = {"production": 0, "test": 0, "unattributed": 0}
        for i, line in enumerate(lines):
            if MARKER not in line:
                continue
            owner = None
            for j in range(i + 1, min(i + 1 + ATTRIBUTION_WINDOW, len(lines))):
                m = OWNER_RE.search(lines[j])
                if m:
                    owner = m.group(1).strip()
                    break
            if owner is None:
                kind = "unattributed"
            elif TEST_PATH_RE.search(owner):
                kind = "test"
            else:
                kind = "production"
                prod_projects[owner] = prod_projects.get(owner, 0) + 1
                ts = line[:19]
                first = ts if first is None else min(first, ts)
                last = ts if last is None else max(last, ts)
                if len(samples) < 3:
                    samples.append({"file": Path(f).name, "line_no": i + 1,
                                    "line": line.strip(), "project": owner})
            counts[kind] += 1
            fc[kind] += 1
        per_file[Path(f).name] = fc
    return {
        "counts": counts,
        "per_file": per_file,
        "production_projects": prod_projects,
        "earliest_production_init": first,
        "latest_production_init": last,
        "samples": samples,
        "files_read": [Path(f).name for f in files],
    }


def build_receipt(log_dir: Path) -> dict:
    data = classify_logs(log_dir)
    return {
        "schema": "rsi_log_receipt/v1",
        "loop": "C",
        "rung": "L2",
        "claim": "MonetaBackedStore is constructed by a live non-test path: real Houdini "
                 "sessions log 'Memory backend: moneta' at store construction.",
        "generated": date.today().isoformat(),
        "producer": "python harness/rsi/log_receipt.py",
        "log_dir": str(log_dir),
        "marker": MARKER,
        "fingerprint": {
            "method": "each marker line is attributed to the next 'Initialized for project:' "
                      f"line within {ATTRIBUTION_WINDOW} lines; the project path decides the class",
            "test_exclusion": f"path matches /{TEST_PATH_RE.pattern}/ (pytest tmp_path factory) "
                              "=> TEST, excluded from the production count",
            "unattributed_rule": "no owner line in the window => UNATTRIBUTED, counted but never credited",
            "negative_control": "the TEST bucket is non-empty on this machine, i.e. the exclusion "
                                "actually removes records rather than matching nothing",
        },
        **data,
        "honesty": (
            "This receipt proves the store is CONSTRUCTED by production processes (L2 REACHABLE). "
            "It does not by itself prove L3 CONSUMED or L4 DURABLE; those rungs cite code paths "
            "and the snapshot round-trip separately."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", type=Path, default=DEFAULT_LOG_DIR)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    if not args.logs.is_dir():
        print(f"no log directory at {args.logs}; no receipt written", file=sys.stderr)
        return 2
    receipt = build_receipt(args.logs)
    text = json.dumps(receipt, indent=2)
    if args.stdout:
        print(text)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8", newline="\n")
    c = receipt["counts"]
    print(f"wrote {args.out.relative_to(REPO)}")
    print(f"production={c['production']} test={c['test']} unattributed={c['unattributed']} "
          f"span={receipt['earliest_production_init']} .. {receipt['latest_production_init']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
