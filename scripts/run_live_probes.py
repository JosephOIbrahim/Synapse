"""Run the SYNAPSE live-probe battery on the pinned Houdini build.

The VERIFY stage of the Solaris hardening harness. Each probe under
``scripts/live_probes/`` drives the real handlers against real Houdini nodes in
an isolated hython process and prints a terminal ``PASS`` / ``FAIL`` (or, for a
negative control, ``PROBE VALID``). This runner executes the whole battery,
reports a table, and enforces the negative-control discipline the hardening work
established: a probe that asserts a fix works should be paired with evidence the
fix is REAL -- either a ``*_fix_is_real.py`` companion, or an inline negative
control (the probe itself reproduces the defect with the fix reverted).

    # run everything on the auto-resolved build
    python scripts/run_live_probes.py

    # fail (not just warn) on any probe missing a negative control
    python scripts/run_live_probes.py --strict-companions

    # point at a specific hython
    python scripts/run_live_probes.py --hython "C:/.../hython.exe"

Exit 0 iff every probe passed (and, under --strict-companions, every probe has a
negative control). This is host-agnostic pure Python -- it shells out to hython,
it does not import hou.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
_PROBE_DIR = _REPO / "scripts" / "live_probes"
_DROP = _REPO / "harness" / "state" / "drop.json"

# A probe declares an inline negative control with any of these markers
# (matched case-insensitively): it reproduces the defect with the fix reverted,
# or otherwise demonstrates the guard actually fires.
_NEG_MARKERS = ("fix_is_real", "probe valid", "negative control", "reproduce",
                "refus", "suppress", "rejected", "clobber")
# Composed / integration probes assert cross-feature composition, not a single
# fix, so they do not need a paired negative control.
_COMPOSED = ("probe_loop_composed", "probe_pr47_fast_follows")


def _resolve_hython(explicit: str | None) -> str | None:
    if explicit:
        return explicit if Path(explicit).exists() else None
    hfs = os.environ.get("HFS")
    if hfs:
        cand = Path(hfs) / "bin" / ("hython.exe" if os.name == "nt" else "hython")
        if cand.exists():
            return str(cand)
    # Pinned build, then any installed build (highest version last).
    pinned = None
    try:
        pinned = json.loads(_DROP.read_text(encoding="utf-8")).get("houdini_build")
    except Exception:
        pinned = None
    roots = [Path("C:/Program Files/Side Effects Software"),
             Path("/opt")]
    found = []
    for root in roots:
        if not root.exists():
            continue
        for d in root.glob("Houdini*"):
            exe = d / "bin" / ("hython.exe" if os.name == "nt" else "hython")
            if exe.exists():
                found.append((d.name, str(exe)))
    if pinned:
        for name, exe in found:
            if pinned in name:
                return exe
    return sorted(found)[-1][1] if found else None


def _has_negative_control(probe: Path) -> bool:
    stem = probe.stem
    if stem in _COMPOSED:
        return True
    # A separate companion is named <shared-prefix>_fix_is_real.py -- e.g.
    # probe_b1_fix_is_real.py pairs with probe_b1_render_tier_ordering.py. Match
    # by prefix: strip the suffix and check it prefixes this probe's stem.
    for comp in probe.parent.glob("*_fix_is_real.py"):
        base = comp.stem[: -len("_fix_is_real")]
        if base and stem.startswith(base):
            return True
    try:
        text = probe.read_text(encoding="utf-8").lower()
    except Exception:
        return False
    return any(m in text for m in _NEG_MARKERS)


def _last_verdict(out: str) -> str:
    for line in reversed(out.strip().splitlines()):
        s = line.strip()
        if s.startswith(("PASS", "FAIL", "PROBE VALID", "PROBE INVALID")):
            return s[:100]
    return "(no verdict line)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hython", default=None)
    ap.add_argument("--strict-companions", action="store_true")
    ap.add_argument("--only", default=None, help="substring filter on probe name")
    args = ap.parse_args()

    hy = _resolve_hython(args.hython)
    if hy is None:
        print("FAIL: no hython found. Set $HFS or pass --hython.", file=sys.stderr)
        return 2

    probes = sorted(p for p in _PROBE_DIR.glob("probe_*.py")
                    if not p.stem.endswith("_fix_is_real")
                    and (args.only is None or args.only in p.stem))
    if not probes:
        print("FAIL: no probes found under %s" % _PROBE_DIR, file=sys.stderr)
        return 2

    print("hython: %s" % hy)
    print("probes: %d\n" % len(probes))

    failed, no_companion = [], []
    for probe in probes:
        r = subprocess.run([hy, str(probe)], capture_output=True, text=True)
        ok = r.returncode == 0
        verdict = _last_verdict(r.stdout + "\n" + r.stderr)
        companion = _has_negative_control(probe)
        mark = "PASS" if ok else "FAIL"
        cflag = "" if companion else "  [no negative control]"
        print("  %-4s  %-38s %s%s" % (mark, probe.stem, verdict, cflag))
        if not ok:
            failed.append(probe.stem)
            # Surface the tail so a failure is diagnosable from the runner alone.
            tail = (r.stdout + r.stderr).strip().splitlines()[-4:]
            for t in tail:
                print("          %s" % t[:110])
        if not companion:
            no_companion.append(probe.stem)

    print()
    print("RESULT: %d/%d passed" % (len(probes) - len(failed), len(probes)))
    if no_companion:
        print("negative control MISSING: %s" % ", ".join(no_companion))
    bad = bool(failed) or (args.strict_companions and bool(no_companion))
    print("VERDICT:", "FAIL" if bad else "PASS")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
