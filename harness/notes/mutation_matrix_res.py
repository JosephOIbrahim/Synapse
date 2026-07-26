"""R34 MUTATION MATRIX for the fake-hou residency leg — the pins' producer.

Law 1: a check that cannot fail is a decoration that will later be cited as
evidence. So each pin is run against a deliberately broken implementation and
must go RED. A pin that survives its own mutation is REPORTED as a decoration,
not quietly repaired.

Every mutation is a byte-exact text substitution applied to a snapshot taken at
start and restored in a `finally` that runs even on KeyboardInterrupt.

THREE THINGS THIS HARNESS LEARNED THE HARD WAY, all from its own bad runs:

  1. **Per-subset controls.** An early version ran controls for two subsets and
     then asserted against three. One mutation's expectations turned out to be
     satisfiable by the UNMUTATED tree — it was "passing" on a defect that was
     still present. Every subset now gets a control run and must be GREEN
     before any mutation of it is believed.

  2. **`--basetemp` needs its parents.** pytest creates only the leaf, so
     tmp_path tests errored for a reason unrelated to any mutation and a
     control went red. A broken instrument reporting on an instrument.

  3. **Verdict vocabulary must distinguish outcomes (Law 3).** "exit != 0" is
     not "the pin failed". A collection-time guard abort exits 4 with NO pin
     having run at all. Reporting that as "PIN FAILED AS REQUIRED" describes
     what was attempted, not what happened. The two are now separate verdicts,
     and each mutation declares which it expects.

Run:  hython3.13 harness/notes/mutation_matrix_res.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONFTEST = "tests/conftest.py"
GUARDS = "tests/test_guards.py"
THEME = "tests/panel/test_theme_source.py"
PIN = "tests/test_hou_reimport_guard.py"
SOLARIS = "tests/solaris/test_live_wiring.py"

BASETEMP = os.environ.get(
    "MUT_BASETEMP", r"C:/Users/User/AppData/Local/Temp/claude/res_bt/mutation"
)

# The proven trigger: theme_source's `_reload_tokens_with`. The identical
# assignment also appears in `_install_hou`, so the anchor carries the
# neighbouring `_TOKENS` line to stay unique — `.replace(old, new, 1)` would
# otherwise mutate the wrong function and the mutation would prove nothing.
THEME_SAFE = (
    '    saved = {k: sys.modules.get(k) for k in ("hou", _TOKENS)}\n'
    '    sys.modules["hou"] = hou_module  # None => deterministic ImportError'
)
THEME_POP = (
    '    saved = {k: sys.modules.get(k) for k in ("hou", _TOKENS)}\n'
    '    sys.modules.pop("hou", None) if hou_module is None '
    'else sys.modules.__setitem__("hou", hou_module)'
)

GUARD_INSTALL = "    sys.meta_path.insert(0, HOU_REIMPORT_GUARD)"
GUARD_UNINSTALL = "    pass  # MUTATED: guard built but not installed"

# Expected verdicts.
PIN_RED = "pin_failed"          # a FAILED line naming the pin
ABORT = "collection_aborted"    # exit 4, guard raised, no pin ran

# (id, description, [(file, old, new)], subset, expectation)
MUTATIONS = [
    (
        "M1",
        "meta_path guard never installed",
        [(CONFTEST, GUARD_INSTALL, GUARD_UNINSTALL)],
        [PIN],
        {"mode": PIN_RED, "failed_contains": ["test_guard_is_installed"]},
    ),
    (
        "M1b",
        "guard not installed, COMPOSED with a real offender — the release-condition "
        "pin itself must go red. M1 alone cannot show this: run in isolation the "
        "pin file is its own first offender, so the headline registry pin runs "
        "before any corruption exists.",
        [(CONFTEST, GUARD_INSTALL, GUARD_UNINSTALL), (THEME, THEME_SAFE, THEME_POP)],
        [THEME, PIN],
        {"mode": PIN_RED, "failed_contains": ["test_swig_parm_registry_is_intact"]},
    ),
    (
        "M2",
        "residency guard reverted to sentinel acceptance",
        [(CONFTEST,
          '    resident = sys.modules.get("hou")\n    if resident is _HOU_AT_IMPORT:\n        return',
          '    resident = sys.modules.get("hou")\n    if getattr(resident, "__synapse_canonical__", False):\n        return')],
        [PIN],
        # Sentinel acceptance makes the collection-finish guard raise under
        # hython (real `hou` carries no sentinel), so pytest ABORTS and no test
        # in the file ever runs. The invariant is defended by a stronger
        # instrument than the pin. Recorded as observed; M2b isolates the pin.
        {"mode": ABORT, "output_contains": ["FAKE_HOU_RESIDENCY_GUARD"]},
    ),
    (
        "M2b",
        "sentinel acceptance ISOLATED — the pin's own assertion, without the "
        "collection abort M2 triggers first. NOTE: this mutates only the wording "
        "of an error message, so it demonstrates the pin is a live SOURCE LINT, "
        "not that it is behavioural. The behavioural claim is carried by "
        "test_no_module_leaves_a_foreign_hou_resident (see M3).",
        [(CONFTEST,
          '        "See the fake-hou residency trap note at the top of tests/conftest.py."\n    )',
          '        "See __synapse_canonical__ note at the top of tests/conftest.py."\n    )')],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_residency_guard_compares_by_object_not_by_sentinel"]},
    ),
    (
        "M3",
        "test_guards.py restore re-gated on the sentinel (Defect A restored)",
        [(GUARDS, '    if _original_hou is not None:\n        sys.modules["hou"] = _original_hou',
          '    if getattr(_original_hou, "__synapse_canonical__", False):\n        sys.modules["hou"] = _original_hou')],
        [GUARDS, PIN],
        {"mode": ABORT, "output_contains": ["FAKE_HOU_RESIDENCY_GUARD"]},
    ),
    (
        "M4",
        "theme_source reverted to pop-eviction (guard still installed) — the "
        "run-level gate must name the offending TEST",
        [(THEME, THEME_SAFE, THEME_POP)],
        [THEME, SOLARIS],
        # The fragment must be one the gate alone can emit. An earlier version
        # asserted on the bare filename, which pytest prints in its own progress
        # line on every run — satisfiable without any mutation at all.
        {"mode": ABORT,
         "output_contains": ["HOU_REIMPORT_GUARD",
                             "during tests/panel/test_theme_source.py::"]},
    ),
    (
        "M5",
        "allowlist widened to the whole tests tree",
        [(CONFTEST, 'SANCTIONED_REIMPORTERS = ("tests/test_hou_reimport_guard.py",)',
          'SANCTIONED_REIMPORTERS = ("tests/",)')],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_gate_rejects_an_unsanctioned_offender"]},
    ),
    (
        "M6",
        "offence filter neutered (always returns clean)",
        [(CONFTEST, "        out.append(rec)", "        pass  # MUTATED")],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_gate_rejects_an_unsanctioned_offender"]},
    ),
    (
        "M7",
        "THE LEG'S ORACLE: guard removed AND theme_source pops -> the original "
        "17-failure defect must return",
        [(CONFTEST, GUARD_INSTALL, GUARD_UNINSTALL), (THEME, THEME_SAFE, THEME_POP)],
        [THEME, SOLARIS],
        {"mode": PIN_RED, "output_contains": ["object has no attribute 'set'"]},
    ),
    (
        "M8",
        "the session-finish gate stops raising — the rescue goes silent (Law 3)",
        [(CONFTEST, "    raise pytest.UsageError(\n        \"HOU_REIMPORT_GUARD:",
          "    return  # MUTATED: rescue is now silent\n    raise pytest.UsageError(\n        \"HOU_REIMPORT_GUARD:")],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_sessionfinish_gate_raises_on_an_unsanctioned_offence"]},
    ),
    (
        "M9",
        "allowlist reverted to matching the INNOCENT field (offender) instead of "
        "the guilty one (during)",
        [(CONFTEST, '        during = (rec.get("during") or "").replace("\\\\", "/")\n'
                    "        if any(ok in during for ok in SANCTIONED_REIMPORTERS):",
          '        during = (rec.get("offender") or "").replace("\\\\", "/")\n'
          "        if any(ok in during for ok in SANCTIONED_REIMPORTERS):")],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_gate_exempts_on_the_guilty_field_not_the_innocent_one"]},
    ),
    (
        "M11",
        "a test reintroduces the eviction idiom — the STATIC ban must catch it "
        "on any interpreter, which is the only version of this law the merge "
        "ratchet (stock python, guard never armed) can run",
        [(GUARDS, "sys.modules[\"hou\"] = hou_mock\ntry:",
          "sys.modules.pop(\"hou\", None)\nsys.modules[\"hou\"] = hou_mock\ntry:")],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_no_test_evicts_hou_from_sys_modules"]},
    ),
    (
        "M12",
        "run-phase residency leak — a swap that collection_finish cannot see "
        "because it happens while tests are RUNNING",
        [(CONFTEST,
          "def pytest_runtest_logfinish(nodeid, location):",
          'def pytest_runtest_logfinish(nodeid, location):\n'
          '    if nodeid.endswith("test_gate_is_clean_for_an_empty_trace"):\n'
          '        sys.modules["hou"] = types.ModuleType("rogue")  # MUTATED\n')],
        [PIN],
        {"mode": ABORT, "output_contains": ["FAKE_HOU_RESIDENCY_GUARD (run phase)"]},
    ),
    (
        "M10",
        "guard narrowed to 'only when hou is absent' — the exact narrowing the "
        "original (wrong) comment invited; the importlib.reload route reopens",
        [(CONFTEST, '        if fullname != "hou":\n            return None',
          '        if fullname != "hou" or "hou" in sys.modules:\n            return None')],
        [PIN],
        {"mode": PIN_RED,
         "failed_contains": ["test_reimport_guard_covers_importlib_reload"]},
    ),
]


def run_pytest(args, tag):
    # pytest creates the basetemp LEAF, not its parents. Without this the
    # tmp_path fixture raises FileNotFoundError and every subset that uses it
    # goes red for a reason that has nothing to do with the mutation.
    bt = pathlib.Path(f"{BASETEMP}/{tag}")
    bt.parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "pytest", *args, "-q", "-p", "no:cacheprovider",
           "--basetemp", str(bt), "-rf"]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
    return proc.returncode, proc.stdout + proc.stderr


def classify(code, out):
    """What actually happened — never what was hoped for."""
    failed = [l for l in out.splitlines() if l.startswith(("FAILED", "ERROR "))]
    named = [l for l in failed if l.startswith("FAILED")]
    if code == 0:
        return "survived_unchanged", failed
    if named or "object has no attribute" in out:
        return PIN_RED, failed
    if code == 4:
        return ABORT, failed
    return "red_unclassified", failed


def evaluate(expect, code, out):
    verdict, failed = classify(code, out)
    reasons = []
    if verdict != expect["mode"]:
        reasons.append(f"expected {expect['mode']}, observed {verdict} (exit {code})")
    failed_blob = "\n".join(failed)
    for frag in expect.get("failed_contains", []):
        if frag not in failed_blob:
            reasons.append(f"expected a FAILED line containing {frag!r}")
    for frag in expect.get("output_contains", []):
        if frag not in out:
            reasons.append(f"expected output containing {frag!r}")
    return verdict, reasons, failed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    args = ap.parse_args()

    targets = sorted({f for _, _, subs, _, _ in MUTATIONS for f, _, _ in subs})
    snapshot = {f: (ROOT / f).read_text(encoding="utf-8") for f in targets}

    results = []
    try:
        # ---- controls: EVERY subset we will mutate must be GREEN unmutated ----
        subsets = []
        for _, _, _, subset, _ in MUTATIONS:
            if subset not in subsets:
                subsets.append(subset)
        control_ok = {}
        for subset in subsets:
            tag = "control_" + "_".join(pathlib.Path(s).stem for s in subset)
            code, out = run_pytest(subset, tag)
            ok = code == 0
            control_ok[tuple(subset)] = ok
            results.append({
                "id": tag, "kind": "control", "subset": subset, "exit": code,
                "verdict": "GREEN" if ok else "RED", "ok": ok,
                "note": "a mutation of a subset whose control is RED proves nothing",
                "failed_lines": [l for l in out.splitlines() if l.startswith("FAILED")][:8],
            })
            print(f"[control] {'/'.join(pathlib.Path(s).stem for s in subset)}: "
                  f"exit={code} {'OK' if ok else '*** BROKEN CONTROL ***'}")

        # ---- mutations ----
        for mid, desc, subs, subset, expect in MUTATIONS:
            for f, old, new in subs:
                text = snapshot[f]
                if old not in text:
                    raise SystemExit(f"{mid}: mutation anchor not found in {f}:\n{old!r}")
                (ROOT / f).write_text(text.replace(old, new, 1), encoding="utf-8")
            try:
                code, out = run_pytest(subset, mid)
            finally:
                for f, _, _ in subs:
                    (ROOT / f).write_text(snapshot[f], encoding="utf-8")

            verdict, reasons, failed = evaluate(expect, code, out)
            if not control_ok.get(tuple(subset), False):
                reasons.append("this subset's control was RED — result not trustworthy")
            results.append({
                "id": mid, "kind": "mutation", "description": desc,
                "files": [f for f, _, _ in subs], "subset": subset,
                "exit": code, "expected": expect["mode"], "observed": verdict,
                "ok": not reasons, "reasons": reasons,
                "failed_lines": failed[:12],
            })
            mark = "PASS" if not reasons else "*** DECORATION / MISMATCH ***"
            print(f"[{mid}] {desc[:88]}\n      exit={code} observed={verdict} {mark}")
            for r in reasons:
                print(f"      ! {r}")
    finally:
        for f in targets:
            (ROOT / f).write_text(snapshot[f], encoding="utf-8")
        print("\n[restore] all mutated files restored from snapshot")

    bad = [r for r in results if not r["ok"]]
    print(f"\n{len(results) - len(bad)}/{len(results)} checks behaved as required")
    if args.json:
        pathlib.Path(args.json).write_text(json.dumps(results, indent=2), encoding="utf-8")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
