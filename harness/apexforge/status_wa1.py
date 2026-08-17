# status_wa1.py - one-pass WA1 board: leg branches ahead-count, receipt
# existence (in-tree + worktree), bus line count + open claims, orchestrator
# liveness, ACRUX flag. Observed, never asserted.
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
AF = REPO / "harness" / "apexforge"
LEGS = ["WA1-TRUTH", "WA1-XREF", "WA1-WIRE", "WA1-RECIPE", "WA1-ACRUX"]

def git(*args):
    r = subprocess.run(["git", "-C", str(REPO), *args],
                       capture_output=True, text=True)
    return r.stdout.strip()

def main():
    print("== WA1 APEXFORGE board ==")
    pid_file = REPO / "harness" / "notes" / "h22" / "orchestrator-wa1.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        alive = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"if (Get-CimInstance Win32_Process -Filter 'ProcessId={pid}') {{'ALIVE'}} else {{'DEAD'}}"],
            capture_output=True, text=True).stdout.strip()
        print(f"orchestrator: pid {pid} {alive}")
    else:
        print("orchestrator: not armed (no pid file)")
    for leg in LEGS:
        tag = leg.split("-", 1)[1].lower()
        branch = f"wavea1/{tag}"
        ahead = git("rev-list", "--count", f"master..{branch}") or "-"
        rec_tree = (REPO / "harness" / "notes" / "receipts" / f"{leg}.json").exists()
        wt = REPO / ".claude" / "worktrees" / leg.lower()
        rec_wt = (wt / "harness" / "notes" / "receipts" / f"{leg}.json").exists()
        print(f"{leg:12s} branch={branch:20s} ahead={ahead:>3s} "
              f"receipt[tree={'Y' if rec_tree else '-'} wt={'Y' if rec_wt else '-'}]")
    bus = AF / "bus" / "wavea1" / "bus.jsonl"
    if bus.exists():
        lines = bus.read_text(encoding="utf-8").splitlines()
        print(f"bus: {len(lines)} lines")
        claims = subprocess.run(
            ["python", str(AF / "bus.py"), "claims", "wavea1"],
            capture_output=True, text=True).stdout.strip()
        print("open claims:\n" + (claims or "  (none)"))
    else:
        print("bus: empty (wave not started)")
    flag = REPO / "harness" / "notes" / "h22" / "WA1_ACRUX_LANDED.flag"
    print(f"ACRUX flag: {'LANDED - ' + flag.read_text().strip() if flag.exists() else 'not yet'}")

if __name__ == "__main__":
    main()
