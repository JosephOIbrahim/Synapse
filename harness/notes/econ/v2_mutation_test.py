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
import re
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
    """Returns (outcome, failed, passed, tail).

    ``outcome`` is ``green`` / ``red`` / ``broken``. **A non-zero exit is not
    evidence of a caught mutation** — pytest exits non-zero for a collection
    error, an internal error, or a plugin that raised, and reading any of those
    as "the control noticed" is a check that passes when the instrument is
    broken. The counts are parsed and a mutation only counts as caught when a
    test actually FAILED (pytest exit code 1).
    """
    cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
           "-p", "v2_mutation_plugin", "--tb=no", *targets]
    proc = subprocess.run(cmd, cwd=REPO, env=_env(mutation),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    out = proc.stdout or ""
    tail = [ln for ln in out.splitlines() if " passed" in ln or " failed" in ln]
    summary = tail[-1].strip() if tail else "(no summary)"
    failed = int(re.search(r"(\d+) failed", summary).group(1)) if " failed" in summary else 0
    passed = int(re.search(r"(\d+) passed", summary).group(1)) if " passed" in summary else 0
    if proc.returncode == 0:
        outcome = "green"
    elif proc.returncode == 1 and failed > 0:
        outcome = "red"
    else:
        outcome = "broken"        # exit 2/3/4 or non-zero with zero failures
        summary += "  [exit %d — pytest itself failed, NOT a caught mutation]" % proc.returncode
    return outcome, failed, passed, summary


def main():
    sys.path.insert(0, HERE)
    from v2_mutation_plugin import MUTATIONS

    started = time.time()
    baseline_outcome, _, baseline_passed, baseline_tail = run(SUITE)
    rows = []
    for name in sorted(MUTATIONS):
        _, target = MUTATIONS[name]
        outcome, failed, passed, tail = run((target,), mutation=name)
        verdict = {"red": "PASS",
                   "green": "FAIL — nothing pins this",
                   "broken": "INVALID — pytest itself failed"}[outcome]
        rows.append({
            "mutation": name,
            "control_file": target,
            "outcome": outcome,
            "tests_failed": failed,
            "tests_passed": passed,
            "summary": tail,
            "verdict": verdict,
        })
        print("%-26s %-44s %s" % (name, tail[:44], verdict))

    survivors = [r["mutation"] for r in rows if r["outcome"] == "green"]
    invalid = [r["mutation"] for r in rows if r["outcome"] == "broken"]
    report = {
        "schema": "v2_mutation/v2",
        "producer": "harness/notes/econ/v2_mutation_test.py",
        "interpreter": sys.version.split()[0],
        "baseline": {"outcome": baseline_outcome, "tests_passed": baseline_passed,
                     "summary": baseline_tail,
                     "verdict": "GREEN" if baseline_outcome == "green"
                                else "RED — fix before trusting"},
        "mutations_run": len(rows),
        "survivors": survivors,
        "invalid": invalid,
        "invalid_note": ("a non-zero exit is not evidence of a caught mutation; "
                         "pytest exits non-zero for collection and plugin errors "
                         "too, so a mutation counts as caught ONLY when a test "
                         "actually failed"),
        "verdict": ("PASS — every mutation was caught"
                    if baseline_outcome == "green" and not survivors and not invalid
                    else "FAIL — see survivors / invalid"),
        "rows": rows,
        "duration_s": round(time.time() - started, 1),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print("\nbaseline:", report["baseline"]["verdict"], "|", baseline_tail)
    print("survivors:", survivors or "none", " invalid:", invalid or "none")
    print("->", OUT)
    return 0 if report["verdict"].startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
