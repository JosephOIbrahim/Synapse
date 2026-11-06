"""Houdini guard - substrate work never runs while Houdini is up.

    python harness/substrate_loop/houdini_guard.py          # exit 0 clear, 3 running, 4 unknown

Joe's rule (2026-11-01): Synapse work can't start while Houdini is running.
Houdini and the local model share one GPU, and Synapse's live session holds
locks a substrate change must not race. So the loop checks before it starts
and again between every iteration.

FAIL CLOSED. If the process list cannot be read, the answer is "unknown", and
unknown is treated like "running": refuse to start, pause mid-run. Wrongly
pausing costs minutes; wrongly running beside a live session costs a scene.

License daemons (hserver, sesinetd) stay resident after Houdini exits, so they
are never on the list. The names are configurable in targets.json
(`houdini_processes`) - this file only supplies the default.
"""
from __future__ import annotations

import csv
import io
import os
import subprocess
import sys

DEFAULT_PROCESSES = (
    "houdini", "houdinifx", "houdinicore", "happrentice", "hindie",
    "hython", "hbatch", "husk", "mantra",
)

CLEAR, RUNNING, UNKNOWN = "clear", "running", "unknown"


def _list_process_names() -> list[str]:
    """Lower-cased image names with any .exe stripped. Raises on failure."""
    if os.name == "nt":
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        names = [row[0] for row in csv.reader(io.StringIO(out)) if row]
    else:
        out = subprocess.run(
            ["ps", "-A", "-o", "comm="],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        names = [os.path.basename(line.strip()) for line in out.splitlines() if line.strip()]
    if not names:
        raise RuntimeError("process list came back empty")
    return [n.lower().removesuffix(".exe") for n in names]


def check(watch: tuple[str, ...] | list[str] = DEFAULT_PROCESSES,
          lister=None) -> tuple[str, list[str]]:
    """Return (CLEAR|RUNNING|UNKNOWN, matched names or the error text)."""
    try:
        names = (lister or _list_process_names)()
    except Exception as exc:  # noqa: BLE001 - any failure is UNKNOWN, never CLEAR
        return UNKNOWN, [f"{type(exc).__name__}: {exc}"]
    wanted = {w.lower().removesuffix(".exe") for w in watch}
    hits = sorted({n for n in names if n in wanted})
    return (RUNNING, hits) if hits else (CLEAR, [])


if __name__ == "__main__":
    state, detail = check()
    print(state, " ".join(detail))
    sys.exit({CLEAR: 0, RUNNING: 3, UNKNOWN: 4}[state])
