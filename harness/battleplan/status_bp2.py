# status_bp2.py - one-pass BP2 board (clone of status_bp1.py, wave id swap):
# leg branches ahead-count, receipt existence (in-tree + worktree), manifest
# state (held legs shown), bus line count + open claims, orchestrator liveness,
# latest ledger, CRUX flag. Observed, never asserted.
import json
import subprocess
from pathlib import Path

REPO = Path(r"C:\Users\User\SYNAPSE")
AF = REPO / "harness" / "battleplan"
LEGS = ["BP2-METER", "BP2-PANELTRUTH", "BP2-LATENCY", "BP2-STORE", "BP2-PANELDESIGN", "BP2-CRUX"]

def git(*args):
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True)
    return r.stdout.strip()

def main():
    print("== BP2 BATTLEPLAN board ==")
    pid_file = REPO / "harness" / "notes" / "h22" / "orchestrator-bp2.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        alive = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"if (Get-CimInstance Win32_Process -Filter 'ProcessId={pid}') {{'ALIVE'}} else {{'DEAD'}}"],
            capture_output=True, text=True).stdout.strip()
        print(f"orchestrator: pid {pid} {alive}")
    else:
        print("orchestrator: not armed (no pid file)")
    man_path = AF / "waves" / "bp2.live.json"
    states = {}
    if man_path.exists():
        states = {l["id"]: l.get("state", "?") for l in json.loads(man_path.read_text(encoding="utf-8"))["legs"]}
    for leg in LEGS:
        tag = leg.split("-", 1)[1].lower()
        branch = f"bp2/{tag}"
        ahead = git("rev-list", "--count", f"master..{branch}") or "-"
        rec_tree = (REPO / "harness" / "notes" / "receipts" / f"{leg}.json").exists()
        wt = REPO / ".claude" / "worktrees" / leg.lower()
        rec_wt = (wt / "harness" / "notes" / "receipts" / f"{leg}.json").exists()
        print(f"{leg:16s} manifest={states.get(leg, 'unarmed'):8s} branch={branch:16s} ahead={ahead:>3s} "
              f"receipt[tree={'Y' if rec_tree else '-'} wt={'Y' if rec_wt else '-'}]")
    bus = AF / "bus" / "bp2" / "bus.jsonl"
    if bus.exists():
        lines = bus.read_text(encoding="utf-8").splitlines()
        print(f"bus: {len(lines)} lines")
        claims = subprocess.run(["python", str(AF / "bus.py"), "claims", "bp2"],
                                capture_output=True, text=True).stdout.strip()
        print("open claims:\n" + (claims or "  (none)"))
    else:
        print("bus: empty (wave not started)")
    ledgers = sorted((AF / "runs").glob("*/ledger_orch_*.json"))
    if ledgers:
        led = json.loads(ledgers[-1].read_text(encoding="utf-8"))
        print(f"ledger: {ledgers[-1].name} status={led.get('status')} unit={led.get('enforced_unit')} "
              f"turns={led.get('totals', {}).get('turns')}/{led.get('cap', {}).get('turns')} "
              f"tokens_in={led.get('totals', {}).get('tokens_in')} tokens_out={led.get('totals', {}).get('tokens_out')}")
    else:
        print("ledger: none yet")
    flag = REPO / "harness" / "notes" / "h22" / "BP2_CRUX_LANDED.flag"
    print(f"CRUX flag: {'LANDED - ' + flag.read_text().strip() if flag.exists() else 'not yet'}")

if __name__ == "__main__":
    main()
