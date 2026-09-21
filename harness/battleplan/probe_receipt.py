# probe_receipt.py - BP9-NONETIER (ruling 2): the receipt for a tier-'none' PROBE leg.
#
# A tier-none leg launches NO model. harness/orchestrate.ps1 runs the row's probe_cmd through
# the shell with a timeout and writes the leg's receipt from what came back. The receipt
# SHAPE is the one the SCREEN guard (harness/jev/jev_screen.py) and the board read:
#   status      pass|fail                (exit code 0 -> pass; anything else, or a timeout -> fail)
#   acceptance  [{predicate, verdict, evidence}]  from stdout lines matching
#               'ACCEPT: <predicate> :: <pass|fail> :: <evidence>'
#   findings    the non-empty stderr lines
#   for_ruling  []  (the board counts it; a probe never asks for a ruling)
# The parser is pure Python so tests can drive it without PowerShell; the ps1 calls the CLI:
#   python probe_receipt.py run     --leg <id> --cmd "<shell cmd>" --timeout <s> --out <path>
#   python probe_receipt.py missing --leg <id> --out <path>      (no probe_cmd -> fail receipt)
# Zero deps, stock library only.
from __future__ import annotations

import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

SCHEMA = "probe-receipt/v1"
DEFAULT_TIMEOUT = 600
ACCEPT_RE = re.compile(r"^ACCEPT:\s*(?P<predicate>.+?)\s*::\s*(?P<verdict>pass|fail)\s*::\s*(?P<evidence>.*?)\s*$",
                       re.IGNORECASE)


def parse_accept_lines(stdout: str) -> list[dict]:
    """Every stdout line of the form 'ACCEPT: <predicate> :: <pass|fail> :: <evidence>' becomes
    one acceptance row, in order. Any other line is ignored (it is the probe's own chatter)."""
    rows = []
    for line in (stdout or "").splitlines():
        m = ACCEPT_RE.match(line.strip())
        if m:
            rows.append({"predicate": m.group("predicate"),
                         "verdict": m.group("verdict").lower(),
                         "evidence": m.group("evidence")})
    return rows


def parse_findings(stderr: str) -> list[str]:
    return [ln.rstrip() for ln in (stderr or "").splitlines() if ln.strip()]


def build_receipt(leg: str, cmd: str, exit_code: int | None, stdout: str, stderr: str, *,
                  timed_out: bool = False, timeout: int = DEFAULT_TIMEOUT, status_note: str = "") -> dict:
    """Pure: (what the shell returned) -> the receipt dict. status is pass ONLY on exit 0 with
    no timeout; a timeout is a fail with exit_code None and a finding that says so."""
    findings = parse_findings(stderr)
    if timed_out:
        findings.insert(0, f"probe timed out after {timeout}s - killed; exit code unknown")
    status = "pass" if (exit_code == 0 and not timed_out) else "fail"
    return {
        "schema": SCHEMA,
        "leg": leg,
        "tier": "none",
        "harness": "BP9-NONETIER probe (orchestrate.ps1 ran probe_cmd; no model launched)",
        "status": status,
        "status_note": status_note or ("exit 0" if status == "pass" else f"exit {exit_code}" if not timed_out else "timeout"),
        "probe_cmd": cmd,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_s": timeout,
        "acceptance": parse_accept_lines(stdout),
        "findings": findings,
        "for_ruling": [],
        "stdout": stdout or "",
        "stderr": stderr or "",
        "date": _dt.datetime.now().isoformat(timespec="seconds"),
    }


def missing_receipt(leg: str) -> dict:
    """The guard's receipt: a tier-none row without a probe_cmd FAILS the leg. Nothing ran."""
    r = build_receipt(leg, "", None, "", "", status_note="no probe_cmd on the row - nothing ran")
    r["findings"] = ["tier 'none' row carries no probe_cmd; the leg fails closed and no model was launched"]
    return r


def run_probe(cmd: str, timeout: int = DEFAULT_TIMEOUT, cwd: str | None = None) -> tuple[int | None, str, str, bool]:
    """Run cmd through the shell. Returns (exit_code, stdout, stderr, timed_out)."""
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout, p.stderr, False
    except subprocess.TimeoutExpired as e:
        out = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return None, out, err, True


def write_receipt(receipt: dict, out: Path) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="tier-none probe runner + receipt writer")
    sub = ap.add_subparsers(dest="mode", required=True)
    pr = sub.add_parser("run", help="run probe_cmd via the shell and write the receipt")
    pr.add_argument("--leg", required=True)
    pr.add_argument("--cmd", required=True)
    pr.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    pr.add_argument("--cwd", default=None)
    pr.add_argument("--out", required=True)
    pm = sub.add_parser("missing", help="write the fail receipt for a row with no probe_cmd")
    pm.add_argument("--leg", required=True)
    pm.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.mode == "missing":
        r = missing_receipt(a.leg)
    else:
        if not a.cmd.strip():
            r = missing_receipt(a.leg)
        else:
            code, out, err, to = run_probe(a.cmd, a.timeout, a.cwd)
            r = build_receipt(a.leg, a.cmd, code, out, err, timed_out=to, timeout=a.timeout)
    p = write_receipt(r, Path(a.out))
    print(f"{r['status']} {a.leg} acceptance={len(r['acceptance'])} findings={len(r['findings'])} -> {p}")
    return 0 if r["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
