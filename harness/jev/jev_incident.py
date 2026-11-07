# jev_incident.py - JEV-INCIDENT: one bounded action choice for an orchestrator anomaly.
# State = observed facts only (code gathers them); Jev picks among actions the harness can take;
# code executes nothing destructive without the operator. Fail closed: 'hold'.
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE))
import jev_client as jc  # noqa: E402
REPO = jc.REPO

ACTIONS = {
    "dismiss_and_wait": "The anomaly is cosmetic or already past; close the dialog, let the orchestrator finish its close gate on its own, touch nothing.",
    "kill_stale_runner": "A leg's runner process outlived its receipt; stop that one process so the close gate can complete. Nothing else changes.",
    "redispatch_leg": "The leg never produced its receipt or its receipt is unusable; flip it back to ready and let the orchestrator dispatch it again.",
    "rearm_wave": "The wave's state is inconsistent (dependents ran before their deps landed); re-arm from scratch.",
    "hold": "Facts are insufficient to choose safely; stop and show the operator the state.",
}

def facts(wave: str, leg: str) -> dict:
    wt = REPO / ".claude" / "worktrees" / leg.lower().replace("-", "-")
    rec = wt / "harness" / "notes" / "receipts" / f"{leg}.json"
    r = json.loads(rec.read_text(encoding="utf-8", errors="replace")) if rec.exists() else None
    log = (REPO / "harness/notes/h22" / f"orchestrator-{wave}.log").read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "leg": leg, "receipt_exists": rec.exists(), "receipt_status": (r or {}).get("status"),
        "receipt_acceptance_verdicts": [a.get("verdict") for a in (r or {}).get("acceptance", [])],
        "board_last": log[-1][-160:], "leg_log_lines": [l[-140:] for l in log if leg in l][-6:],
        "runner_file_exists": (Path(subprocess.run(["powershell", "-NoProfile", "-Command", "$env:TEMP"], capture_output=True, text=True).stdout.strip()) / f"orch_{leg}.ps1").exists(),
    }

def decide(wave: str, leg: str, error_text: str) -> None:
    f = facts(wave, leg)
    state = {"error_as_seen_by_operator": error_text, "facts": f,
             "note": "The launch string in the error carries a trailing space inside the quotes after the .ps1 path."}
    spec = {"action": {"type": "choice", "criteria": ACTIONS, "instructions":
            "Given `facts` (observed by code, trustworthy) and `error_as_seen_by_operator`, which single action should the harness take now? Prefer the least invasive action whose preconditions the facts satisfy."},
            "bug_in_orchestrator": {"type": "noul", "instructions": "Do the facts plus the error string indicate a defect in the orchestrator's own launch/close command construction (as opposed to the leg's work)?"}}
    a = jc.ask(state, spec, wave=wave, guard="incident", leg=leg)
    print(json.dumps(f, indent=1)[:900])
    if a is None:
        print("ACTION hold (fallback)"); return
    c = a["choices"]["action"]; p = {k: round(v, 2) for k, v in c["probabilities"].items()}
    print(f"ACTION {c['choice']}  conf {c['confidence']:.2f}  {p}")
    print(f"orchestrator defect: {a['nouls']['bug_in_orchestrator']['noul']:.2f}")

if __name__ == "__main__":
    decide(sys.argv[1], sys.argv[2], sys.argv[3])
