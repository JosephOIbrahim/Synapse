"""V2 · the control suite, mutation-tested (R133).

Runs the V2 suite once clean — it must be GREEN — then once per mutation with a
single piece of enforcement removed from the SHIPPED module. Each mutated run
must be RED. A mutation that leaves the suite green names a guard that nothing
pins: the check exists, it is cited as evidence, and deleting it changes nothing.

    python harness/notes/econ/v2_mutation_test.py
    -> harness/notes/econ/V2_mutation.json

R127/R131: 129 green tests prove nothing on their own. This is the producer that
turns "the suite passes" into "the suite would notice".
"""

import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(HERE, "V2_mutation.json")

SUITE = ("tests/test_v2_verdict_contract.py",
         "tests/test_v2_voice_contract.py",
         "tests/test_v2_invariant8.py")


def _env(mutation=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = HERE + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    if mutation:
        env["SYNAPSE_V2_MUTATION"] = mutation
    else:
        env.pop("SYNAPSE_V2_MUTATION", None)
    return env


def run(targets, mutation=None):
    """Returns (exit_code, tail). Exit 0 = green, non-zero = red."""
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "-p", "v2_mutation_plugin", "--tb=no", *targets]
    proc = subprocess.run(cmd, cwd=REPO, env=_env(mutation),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    tail = [ln for ln in (proc.stdout or "").splitlines() if " passed" in ln or " failed" in ln]
    return proc.returncode, (tail[-1].strip() if tail else "(no summary)")


def main():
    sys.path.insert(0, HERE)
    from v2_mutation_plugin import MUTATIONS

    started = time.time()
    baseline_code, baseline_tail = run(SUITE)
    rows = []
    for name in sorted(MUTATIONS):
        _, target = MUTATIONS[name]
        code, tail = run((target,), mutation=name)
        rows.append({
            "mutation": name,
            "control_file": target,
            "exit_code": code,
            "summary": tail,
            "verdict": "PASS" if code != 0 else "FAIL — nothing pins this",
        })
        print("%-32s %-40s %s" % (name, tail, rows[-1]["verdict"]))

    survivors = [r["mutation"] for r in rows if r["exit_code"] == 0]
    report = {
        "schema": "v2_mutation/v1",
        "producer": "harness/notes/econ/v2_mutation_test.py",
        "interpreter": sys.version.split()[0],
        "baseline": {"exit_code": baseline_code, "summary": baseline_tail,
                     "verdict": "GREEN" if baseline_code == 0 else "RED — fix before trusting"},
        "mutations_run": len(rows),
        "survivors": survivors,
        "verdict": ("PASS — every mutation was caught"
                    if baseline_code == 0 and not survivors
                    else "FAIL — see survivors"),
        "rows": rows,
        "duration_s": round(time.time() - started, 1),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("\nbaseline:", report["baseline"]["verdict"], "|", baseline_tail)
    print("survivors:", survivors or "none")
    print("->", OUT)
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
