"""The one panel gate: prove which tree you measured, then ratchet the audit and the seat suite.

WHY THIS EXISTS. Three gates written for the panel spec legs were dead or lying, and each one
cost a graph:

1. "hython audit_panel.py --strict exits 0" could never pass: audit_panel.py read a token
   CRIT.md had deleted, so the audit crashed on its first table (fixed in PNL-L0).
2. "hython .synapse/hytest.py tests/panel/test_bc_wave.py exits 0" could never pass either:
   master itself is 2 failed / 11 passed there.
3. Worse than dead, both LIED from a worktree. The global HOUDINI_PACKAGE_DIR points Houdini at
   the MAIN tree, so hython imported synapse from C:/Users/User/SYNAPSE no matter what PYTHONPATH
   said: a gate printing green for code the branch did not contain. And tests/panel/test_bc_wave.py
   has one test that needs an Anthropic key, which lives in a gitignored .env the worktree does not
   have, so every worktree saw a third failure that was pure environment.

So this script does three things no per-leg command did: it forces the interpreter onto THIS tree
and prints where it imported from, it supplies the key from the main tree's .env in memory (never
written to the worktree), and it ratchets both instruments against committed baselines instead of
demanding a green that does not exist.

    python harness/notes/bp9/panel_gate.py              # audit + seat suite, ratcheted
    python harness/notes/bp9/panel_gate.py --audit      # audit only
    python harness/notes/bp9/panel_gate.py --seat       # seat suite only
    python harness/notes/bp9/panel_gate.py --accept     # rewrite both baselines (a human act)

Exit 0 = no new failure. Exit 1 = a new failure, a crash, or a suite that did not run.
Exit 2 = a baseline row now passes and must be deleted from the baseline in this same commit.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:  # a cp1252 console must never kill a gate over a glyph in a check name
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AUDIT_BASELINE = HERE / "audit_baseline.json"
SEAT_BASELINE = HERE / "seat_baseline.json"
SEAT_TESTS = "tests/panel"
MAIN_TREE = Path(r"C:/Users/User/SYNAPSE")
HYTHON = os.environ.get("SYNAPSE_HYTHON") or r"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"

_FAIL = re.compile(r"^\s*(?P<check>.+?)\s*:\s*.*?\[FAIL\]\s*$")
# The audit prints TWO result lines: "G3 RESULT: <n> FAIL · <n> WARN" when something failed,
# and "G3 RESULT: pass · <n> WARN" when nothing did (audit_panel.py:540,542). Matching only the
# first made a fully green audit look like a CRASH -- a gate that cannot recognise success is as
# dead as one that cannot pass. Match both; "pass" means zero failures.
_RESULT = re.compile(r"G3 RESULT:\s*(?:(\d+) FAIL|pass)", re.I)
_PYFAIL = re.compile(r"^FAILED\s+(?P<nodeid>\S+)")
_SUMMARY = re.compile(r"^=*\s*(?:\d+ \w+(?:, )?)+ in [\d.]+s")


def env_for_this_tree() -> dict:
    """The env that makes a run measure THIS tree, not the main one."""
    e = {**os.environ}
    e["QT_QPA_PLATFORM"] = "offscreen"
    e["PYTHONPATH"] = str(ROOT / "python")
    e["SYNAPSE_HYTHON"] = HYTHON
    e["SYNAPSE_LOG_DIR"] = str(ROOT / ".scratch" / "logs")
    # THE ONE THAT MATTERS: Houdini prepends $HOUDINI_PACKAGE_DIR's tree in-process and it
    # beats PYTHONPATH. Left at the global value, every hython gate below audits the main tree.
    e["HOUDINI_PACKAGE_DIR"] = str(ROOT / "packages")
    Path(e["SYNAPSE_LOG_DIR"]).mkdir(parents=True, exist_ok=True)
    # One seat test needs an Anthropic key; it lives in the main tree's gitignored .env, which a
    # worktree does not have. Pass it in memory so the worktree never holds a copy on disk.
    if not e.get("ANTHROPIC_API_KEY"):
        for env_file in (ROOT / ".env", MAIN_TREE / ".env"):
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
                    k, _, v = line.partition("=")
                    if k.strip() == "ANTHROPIC_API_KEY" and v.strip():
                        e["ANTHROPIC_API_KEY"] = v.strip().strip('"').strip("'")
                        break
            if e.get("ANTHROPIC_API_KEY"):
                break
    return e


def run(cmd: list[str], e: dict, timeout: int = 2400) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=str(ROOT), env=e, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def prove_tree(e: dict) -> bool:
    """Print the tree hython actually imports from. A gate that cannot say this is not evidence."""
    rc, out = run([HYTHON, "-c", "import synapse; print(synapse.__file__)"], e, timeout=600)
    line = next((l.strip() for l in reversed(out.splitlines()) if l.strip().endswith("__init__.py")), "")
    want = ROOT / "python" / "synapse" / "__init__.py"
    ok = False
    if line:
        try:
            ok = Path(line).resolve() == want.resolve()
        except OSError:
            ok = False
    print(f"tree under test : {ROOT}")
    print(f"hython imports  : {line or '(could not determine)'}   [{'OK' if ok else 'WRONG TREE'}]")
    print(f"anthropic key   : {'present' if e.get('ANTHROPIC_API_KEY') else 'ABSENT (one seat test fails on environment, not code)'}")
    return ok


def load(p: Path) -> set[str]:
    if not p.exists():
        return set()
    return {f["check"] for f in json.loads(p.read_text(encoding="utf-8")).get("failures", [])}


def save(p: Path, names, why: str, owners: dict[str, str] | None = None) -> None:
    owners = owners or {}
    p.write_text(json.dumps({
        "_why": why,
        "failures": [{"check": n, "owner": owners.get(n, "unassigned")} for n in sorted(names)],
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def ratchet(label: str, now: set[str], base: set[str]) -> int:
    new, fixed = sorted(now - base), sorted(base - now)
    print(f"\n{label}: {len(now)} failing, {len(base)} baselined")
    for n in sorted(now):
        print(f"   {'NEW  ' if n in new else 'known'}  {n}")
    for n in fixed:
        print(f"   FIXED  {n}  <- delete this row from the baseline in this commit")
    if new:
        print(f"   RATCHET BROKEN: {label} gained {len(new)} failure(s)")
        return 1
    if fixed:
        print(f"   RATCHET LOOSE: {len(fixed)} baseline row(s) now pass and are still listed")
        return 2
    print("   ratchet holds")
    return 0


def audit(e: dict, accept: bool) -> int:
    rc, out = run([HYTHON, "audit_panel.py", "--strict"], e)
    names = {m.group("check").strip() for ln in out.splitlines() if (m := _FAIL.match(ln))}
    if not _RESULT.search(out):
        print("\naudit: CRASH before its G3 RESULT line. A crash is never a baseline.")
        print("\n".join(out.strip().splitlines()[-10:]))
        return 1
    if accept:
        save(AUDIT_BASELINE, names, "Failures the strict panel audit reports at this commit. The "
             "ratchet lets these stand and refuses anything new. Delete a row in the same commit "
             "that fixes it.")
        print(f"\naudit baseline rewritten with {len(names)} row(s)")
        return 0
    return ratchet("audit", names, load(AUDIT_BASELINE))


def seat(e: dict, accept: bool) -> int:
    rc, out = run([sys.executable, ".synapse/hytest.py", SEAT_TESTS, "-q"], e)
    names = {m.group("nodeid").strip() for ln in out.splitlines() if (m := _PYFAIL.match(ln))}
    summary = next((l.strip() for l in reversed(out.splitlines()) if _SUMMARY.match(l.strip())), "")
    if not summary or " passed" not in summary:
        print(f"\nseat suite: no real run (summary={summary!r}). An all-skipped run is not a pass.")
        print("\n".join(out.strip().splitlines()[-10:]))
        return 1
    print(f"\nseat suite summary: {summary}")
    if accept:
        save(SEAT_BASELINE, names, "Panel seat-suite tests failing at this commit under hython "
             "offscreen, measured on THIS tree with a key present. Refuse anything new; delete a "
             "row in the commit that fixes it.",
             {"tests/panel/test_bc_wave.py::test_chat_face_monochrome_one_accent_plus_state_marks":
              "PNL-L7 (R2-B1 drops the Doctor yellow; the hue-bucket guard goes green with it)"})
        print(f"seat baseline rewritten with {len(names)} row(s)")
        return 0
    return ratchet("seat suite", names, load(SEAT_BASELINE))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--seat", action="store_true")
    ap.add_argument("--accept", action="store_true")
    a = ap.parse_args()
    both = not (a.audit or a.seat)
    e = env_for_this_tree()
    if not prove_tree(e):
        print("\nREFUSING: hython is not importing the tree under test, so nothing measured here "
              "would be evidence about this branch.")
        return 1
    rc = 0
    if a.audit or both:
        rc = max(rc, audit(e, a.accept))
    if a.seat or both:
        rc = max(rc, seat(e, a.accept))
    print(f"\npanel gate: {'GREEN (no new failure)' if rc == 0 else 'rc=' + str(rc)}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
