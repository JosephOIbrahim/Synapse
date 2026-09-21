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
#   python probe_receipt.py run     --leg <id> --cmd-file <path> --timeout <s> --out <path>
#   python probe_receipt.py run     --leg <id> --cmd "<shell cmd>" ...   (tests / POSIX shells only)
#   python probe_receipt.py missing --leg <id> --out <path>      (no probe_cmd -> fail receipt)
#   python probe_receipt.py runner-failed --leg <id> --exit <n> --stderr-file <p> --out <path>
# BP9-NONETIER-FIX: the ps1 passes --cmd-file, never --cmd. Windows PowerShell 5.1 re-tokenises
# embedded double quotes in an argument, so a probe such as python -c "print('ACCEPT: ...')"
# arrived mangled ('unrecognized arguments') and the fallback receipt blamed a missing probe_cmd.
# The file is read as bytes and decoded verbatim - nothing re-tokenises it on the way in.
# Also: a probe that exits 0 but prints ZERO ACCEPT lines is a FAIL. A silent green is not a
# pass; SCREEN treats empty acceptance as a non-verdict, so the receipt says so instead.
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
NO_ACCEPT_FINDING = "probe printed no ACCEPT lines - exit 0 with empty acceptance is a silent green, not a pass"
STDERR_HEAD_LINES = 20
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
    acceptance = parse_accept_lines(stdout)
    if timed_out:
        findings.insert(0, f"probe timed out after {timeout}s - killed; exit code unknown")
    status = "pass" if (exit_code == 0 and not timed_out) else "fail"
    if status == "pass" and not acceptance:
        # a silent green is not a pass: nothing to screen, nothing to board
        status = "fail"
        status_note = status_note or "exit 0 but no ACCEPT lines - silent green refused"
        findings.insert(0, NO_ACCEPT_FINDING)
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
        "acceptance": acceptance,
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


def runner_failed_receipt(leg: str, exit_code: int | None, stderr_text: str, cmd: str = "") -> dict:
    """The ps1's receipt when THIS runner exited non-zero without writing one (a crash, an
    argparse refusal, a missing interpreter). Distinct from missing_receipt: the row DID carry
    a probe_cmd; the finding carries the runner's stderr head so the cause is not misreported."""
    head = [ln.rstrip() for ln in (stderr_text or "").splitlines() if ln.strip()][:STDERR_HEAD_LINES]
    r = build_receipt(leg, cmd, exit_code, "", "", status_note=f"probe runner failed (exit {exit_code}) - no receipt written by the run")
    r["status"] = "fail"
    r["findings"] = [f"probe runner failed with exit {exit_code} before writing a receipt; stderr head: "
                     + (" | ".join(head) if head else "<empty>")]
    r["runner_stderr_head"] = head
    return r


def read_cmd_file(path: Path) -> str:
    """The command exactly as the file holds it: bytes -> UTF-8, no strip, no shell on the way."""
    return Path(path).read_bytes().decode("utf-8")


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
    src = pr.add_mutually_exclusive_group(required=True)
    src.add_argument("--cmd", help="the command as one argument (tests / POSIX shells only)")
    src.add_argument("--cmd-file", help="path holding the command verbatim (what orchestrate.ps1 passes)")
    pr.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    pr.add_argument("--cwd", default=None)
    pr.add_argument("--out", required=True)
    pm = sub.add_parser("missing", help="write the fail receipt for a row with no probe_cmd")
    pm.add_argument("--leg", required=True)
    pm.add_argument("--out", required=True)
    pf = sub.add_parser("runner-failed", help="write the fail receipt for a runner that died without one")
    pf.add_argument("--leg", required=True)
    pf.add_argument("--exit", type=int, default=None)
    pf.add_argument("--stderr-file", default=None)
    pf.add_argument("--cmd-file", default=None)
    pf.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.mode == "missing":
        r = missing_receipt(a.leg)
    elif a.mode == "runner-failed":
        err = Path(a.stderr_file).read_text(encoding="utf-8", errors="replace") if a.stderr_file and Path(a.stderr_file).exists() else ""
        cmd = read_cmd_file(a.cmd_file) if a.cmd_file and Path(a.cmd_file).exists() else ""
        r = runner_failed_receipt(a.leg, a.exit, err, cmd)
    else:
        cmd = read_cmd_file(a.cmd_file) if a.cmd_file else a.cmd
        if not cmd.strip():
            r = missing_receipt(a.leg)
        else:
            code, out, err, to = run_probe(cmd, a.timeout, a.cwd)
            r = build_receipt(a.leg, cmd, code, out, err, timed_out=to, timeout=a.timeout)
            if a.cmd_file:
                r["probe_cmd_file"] = a.cmd_file
    p = write_receipt(r, Path(a.out))
    print(f"{r['status']} {a.leg} acceptance={len(r['acceptance'])} findings={len(r['findings'])} -> {p}")
    return 0 if r["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
