#!/usr/bin/env python3
"""Produce baseline.csv from manifest.json for the v2-baseline run.

WHY THIS FILE EXISTS
--------------------
manifest.json records two "host-script" evidence-export actions -- steps n=8
("...evidence export and closeout", result PARTIAL_BASELINE_PRESERVED, exp-01
only) and n=53 ("Export evidence, finalize ten-task measurements and report",
all ten tasks) -- and both list ``baseline.csv`` in their ``evidence`` array.
The script behind those actions was never checked in.  Only its output was.
That left the CSV-aggregation logic unauditable: you could read the numbers but
not the rule that produced them.

This file is a RECONSTRUCTION of that logic, derived by matching each archived
baseline.csv cell back to its field in ``manifest.json.baseline_tasks[]``.  It
is not the original script and does not claim to be.  What is claimed, and what
``--verify`` re-checks on demand, is that it reproduces the archived
baseline.csv field-for-field for all ten tasks.

COLUMN -> MANIFEST FIELD
------------------------
    task                     <- id
    measurement_kind         <- measurement_kind
    model_round_trips        <- model_round_trips
    input_tokens             <- task_input_tokens
    output_tokens            <- task_output_tokens
    first_call_input_tokens  <- first_call_input_tokens, else first_call_last_prompt
    cache_read               <- cache_read
    cost                     <- (no per-task producer exists; always UNKNOWN)
    wall_ms                  <- wall_ms
    validation               <- independent_observation

HONESTY RULE
------------
An absent field emits the string ``UNKNOWN``, never ``0`` and never an empty
cell -- the same rule ``python/synapse/panel/usage_sink.py`` applies to absent
wire fields.  Three columns are UNKNOWN on every archived row and that is
faithful, not lossy:

* ``cache_read`` -- this run used provider=ollama end to end, and Ollama's wire
  usage chunk carries no cache-token field to map, so the value was never
  producible.  It is written as null at capture time, in the usage snapshots
  themselves, long before any export step runs.
* ``cost`` -- no per-task cost was recorded anywhere in the manifest.
* ``wall_ms`` -- per-task durations were not measured in this run.

KNOWN BYTE-LEVEL DIFFERENCE FROM THE ARCHIVED FILE
--------------------------------------------------
The archived baseline.csv has mixed line endings: every line ends LF except the
last, which ends CRLF (measured: 11 LF, 1 CRLF).  That is an artifact of how the
file was assembled by hand.  This script emits LF throughout, so ``--verify``
compares parsed rows, not raw bytes.

USAGE
-----
    python export_baseline_csv.py                 # rewrite baseline.csv in place
    python export_baseline_csv.py --out /tmp/x.csv
    python export_baseline_csv.py --verify        # compare against the archived CSV
    python export_baseline_csv.py --dir <run>     # read another run's artifacts
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

UNKNOWN = "UNKNOWN"

#: CSV header, in the archived column order.
COLUMNS = [
    "task",
    "measurement_kind",
    "model_round_trips",
    "input_tokens",
    "output_tokens",
    "first_call_input_tokens",
    "cache_read",
    "cost",
    "wall_ms",
    "validation",
]

#: column -> candidate manifest.baseline_tasks[] fields, first hit wins.
#:
#: ``cost`` lists a field that no task carries, which is how it stays honestly
#: UNKNOWN instead of invented.  ``first_call_input_tokens`` needs two
#: candidates: five of the ten archived tasks record only
#: ``first_call_last_prompt``.  Where both fields exist they agree (4 of 4), so
#: the archived column cannot tell the two rules apart; the column's own name is
#: tried first and the context-size field is the fallback.
FIELD_SOURCE = {
    "task": ("id",),
    "measurement_kind": ("measurement_kind",),
    "model_round_trips": ("model_round_trips",),
    "input_tokens": ("task_input_tokens",),
    "output_tokens": ("task_output_tokens",),
    "first_call_input_tokens": ("first_call_input_tokens", "first_call_last_prompt"),
    "cache_read": ("cache_read",),
    "cost": ("cost",),
    "wall_ms": ("wall_ms",),
    "validation": ("independent_observation",),
}


def _cell(task: dict, fields: tuple[str, ...]) -> str:
    """Render one cell, degrading an absent or null field to UNKNOWN."""
    for field in fields:
        value = task.get(field)
        if value is not None:
            return str(value)
    return UNKNOWN


def build_rows(manifest: dict) -> list[list[str]]:
    """Flatten manifest.baseline_tasks[] into CSV rows (header excluded)."""
    tasks = manifest.get("baseline_tasks") or []
    return [[_cell(task, FIELD_SOURCE[col]) for col in COLUMNS] for task in tasks]


def export(artifact_dir: Path, out_path: Path) -> list[list[str]]:
    """Read ``artifact_dir/manifest.json`` and write the CSV to ``out_path``."""
    manifest = json.loads(
        (Path(artifact_dir) / "manifest.json").read_text(encoding="utf-8")
    )
    rows = build_rows(manifest)
    with Path(out_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    return rows


def verify(artifact_dir: Path, csv_path: Path) -> list[str]:
    """Return a list of field-for-field mismatches against an archived CSV."""
    manifest = json.loads(
        (Path(artifact_dir) / "manifest.json").read_text(encoding="utf-8")
    )
    expected = [COLUMNS] + build_rows(manifest)
    with Path(csv_path).open(newline="", encoding="utf-8") as handle:
        archived = list(csv.reader(handle))

    problems: list[str] = []
    if len(expected) != len(archived):
        problems.append(f"row count: rebuilt {len(expected)} vs archived {len(archived)}")
    for index, (want, got) in enumerate(zip(expected, archived)):
        if want != got:
            for col, (a, b) in enumerate(zip(want, got)):
                if a != b:
                    problems.append(f"row {index} col {col}: rebuilt {a!r} vs archived {b!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", default=str(here), help="artifact directory holding manifest.json")
    parser.add_argument("--out", default=None, help="output CSV path (default: <dir>/baseline.csv)")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="compare the rebuild against the archived CSV instead of writing it",
    )
    args = parser.parse_args(argv)

    artifact_dir = Path(args.dir)
    out_path = Path(args.out) if args.out else artifact_dir / "baseline.csv"

    if args.verify:
        problems = verify(artifact_dir, out_path)
        if problems:
            print(f"MISMATCH ({len(problems)}):")
            for problem in problems:
                print("  " + problem)
            return 1
        print(f"MATCH: rebuild reproduces {out_path} field-for-field")
        return 0

    rows = export(artifact_dir, out_path)
    print(f"wrote {out_path} ({len(rows)} task rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
