"""Run the strict panel audit and ratchet it against a committed baseline.

WHY A RATCHET AND NOT "EXITS 0". The panel spec legs (2026-09-21) each carried the
acceptance line "hython audit_panel.py --strict exits 0". It could not pass on any
branch: audit_panel.py read a token CRIT.md had deleted, so the audit crashed on its
first table and every check below -- including two real FAIL rows -- stopped running.
A gate that cannot pass is a dead gate; it teaches a builder to route around it.

So the gate is a ratchet instead, the shape memory calls "protect green, select red,
fix, prove real, protect green":

  * the audit must RUN TO COMPLETION (a crash is always a failure, never a baseline),
  * no FAIL row may appear that is not in the baseline,
  * a leg that owns a baseline row must clear it and delete the row in the same commit.

The count may only fall. A leg that cannot make its row green leaves the baseline and
says so in its receipt.

    python harness/notes/bp9/audit_ratchet.py             # run and ratchet
    python harness/notes/bp9/audit_ratchet.py --accept    # rewrite the baseline (a human act)

Exit 0 = green or no worse. Exit 1 = a new failure, a rise, or a crash.
Exit 2 = a baseline row is fixed but still listed (tighten the baseline).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:  # a Windows cp1252 console must never kill the gate over a glyph
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - older interpreters
    pass

ROOT = Path(__file__).resolve().parents[3]
BASELINE = Path(__file__).resolve().parent / "audit_baseline.json"
HYTHON = os.environ.get("SYNAPSE_HYTHON") or r"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"

_FAIL = re.compile(r"^\s*(?P<check>.+?)\s*:\s*(?P<detail>.*?)\s*\[FAIL\]\s*$")
_RESULT = re.compile(r"G3 RESULT:\s*(\d+) FAIL")


def run_audit() -> tuple[int, str]:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    env.setdefault("SYNAPSE_LOG_DIR", str(ROOT / ".scratch" / "logs"))
    Path(env["SYNAPSE_LOG_DIR"]).mkdir(parents=True, exist_ok=True)
    r = subprocess.run([HYTHON, "audit_panel.py", "--strict"], cwd=str(ROOT), env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=1800)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def parse(out: str) -> tuple[list[str], int | None, bool]:
    """(failing check names, the audit's own FAIL count, ran_to_completion)."""
    names = [m.group("check").strip() for ln in out.splitlines() if (m := _FAIL.match(ln))]
    m = _RESULT.search(out)
    return names, (int(m.group(1)) if m else None), m is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--accept", action="store_true", help="rewrite the baseline from this run (human act)")
    a = ap.parse_args()

    rc, out = run_audit()
    names, counted, completed = parse(out)

    if not completed:
        tail = "\n".join(out.strip().splitlines()[-12:])
        print("CRASH: the audit did not reach its G3 RESULT line. A crash is never a baseline.\n" + tail)
        return 1

    known = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.exists() else {"failures": []}
    base = {f["check"] for f in known.get("failures", [])}
    now = set(names)

    if a.accept:
        BASELINE.write_text(json.dumps({
            "_why": "Failures the strict panel audit reports at this commit. The ratchet lets these "
                    "stand and refuses anything new. Delete a row in the same commit that fixes it.",
            "failures": [{"check": n, "owner": "unassigned"} for n in sorted(now)],
        }, indent=1) + "\n", encoding="utf-8")
        print(f"baseline rewritten with {len(now)} failure(s): {sorted(now)}")
        return 0

    new = sorted(now - base)
    fixed = sorted(base - now)
    print(f"audit ran to completion; {counted} FAIL reported, {len(base)} in the baseline")
    for n in sorted(now):
        print(f"   {'NEW  ' if n in new else 'known'}  {n}")
    for n in fixed:
        print(f"   FIXED  {n}  <- delete this row from {BASELINE.name}")

    if new:
        print(f"\nRATCHET BROKEN: {len(new)} failure(s) this branch introduced: {new}")
        return 1
    if fixed:
        print(f"\nRATCHET LOOSE: {len(fixed)} baseline row(s) now pass and must be deleted from the baseline.")
        return 2
    print("\nratchet holds: no new failure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
