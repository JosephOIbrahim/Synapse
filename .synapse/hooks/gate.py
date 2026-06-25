#!/usr/bin/env python3
"""SYNAPSE harness Stop hook — the test gate (the reward signal).

Fires when the worker tries to wrap up. Runs the project's test command. Green -> let it
stop. Red -> block the stop and feed the failure back so the worker keeps fixing, up to
max_attempts, after which it records a failure and lets the loop end so the orchestrator
escalates instead of spinning forever. The 'edit -> run -> keep or discard' gate."""
import json
import os
import subprocess
import sys

DEFAULTS = {"gate_cmd": "pytest -q", "max_attempts": "3"}


def load_scalars(path, keys):
    out = dict(DEFAULTS)
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            raw = line.rstrip("\n")
            if not raw.strip() or raw.lstrip().startswith("#") or raw[0].isspace():
                continue
            if ":" in raw:
                k, _, v = raw.partition(":")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k in keys and v:
                    out[k] = v
    return out


def _save(path, obj):
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2)
    except Exception:
        pass


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()

    cfg = load_scalars(os.path.join(cwd, ".synapse", "config.yaml"), {"gate_cmd", "max_attempts"})
    gate_cmd = cfg["gate_cmd"]
    try:
        max_attempts = int(cfg["max_attempts"])
    except ValueError:
        max_attempts = 3

    proc = subprocess.run(gate_cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])

    state_path = os.path.join(cwd, ".synapse", "state.json")
    try:
        with open(state_path, encoding="utf-8") as fh:
            state = json.load(fh)
    except Exception:
        state = {}

    if proc.returncode == 0:
        state["gate_result"] = "passed"
        _save(state_path, state)
        sys.exit(0)

    attempts = int(state.get("gate_attempts", 0)) + 1
    state["gate_attempts"] = attempts
    if attempts >= max_attempts:
        state["gate_result"] = "failed"
        _save(state_path, state)
        print(f"SYNAPSE gate: failed after {attempts} attempts — escalating to human.", file=sys.stderr)
        sys.exit(0)

    state["gate_result"] = "red"
    _save(state_path, state)
    print(json.dumps({
        "decision": "block",
        "reason": (f"Gate failed (`{gate_cmd}`), attempt {attempts}/{max_attempts}. "
                   f"Fix the failures, do not stop until green. Tail:\n{tail}"),
    }))
    sys.exit(2)


if __name__ == "__main__":
    main()
