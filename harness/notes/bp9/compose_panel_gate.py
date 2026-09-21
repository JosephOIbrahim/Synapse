"""Composed gate for the panel spec legs (PNL-L1..L7).

Isolated green hides composed regressions (memory: solaris-harden). Every leg verified
alone, in its own worktree, against the files IT named. This script does the other half:
merge the leaf branches into one tree and run the gates nothing per-leg can run.

    python harness/notes/bp9/compose_panel_gate.py --plan          # print the merge plan, touch nothing
    python harness/notes/bp9/compose_panel_gate.py --merge         # build the integration worktree
    python harness/notes/bp9/compose_panel_gate.py --gate          # run the gates on it
    python harness/notes/bp9/compose_panel_gate.py --merge --gate  # both

Merging is local only: it creates a worktree and a branch, never touches master, never pushes.
The gates are run ONE AT A TIME (the stock suite and the seat suite both attach a rotating
handler to the same log file; running them together fakes a failure -- see docs/RELEASE_CARD.md
"Traps"). SYNAPSE_LOG_DIR is pointed at the integration worktree for the same reason.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:  # a baseline row can carry a glyph (the U+2318 command key); cp1252 must not kill the gate
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # pragma: no cover - older interpreters
    pass

ROOT = Path(__file__).resolve().parents[3]
INT_DIR = ROOT.parent / "pnl-integration"
INT_BRANCH = "pnl/integration"
HYTHON = r"C:/Program Files/Side Effects Software/Houdini 22.0.400/bin/hython.exe"
RESULTS = Path(__file__).resolve().parent / "panel_results.json"
LOGDIR = Path(__file__).resolve().parent / "gate-logs"

# Leaves of the dependency graph. Each already contains its upstream chain:
#   L3b -> L3a -> L1 ;  L5/L6/L7 -> L4 -> L2 -> L1
# Deepest chain first: the type ramp lands before the palette rows that sit on it.
# Each row is a fallback chain: take the deepest leg that is mergeable, so one refused
# leaf costs its own spec leg, never the verified work underneath it.
LEAF_CHAINS = [
    ["PNL-L5", "PNL-L4", "PNL-L2"],
    ["PNL-L6", "PNL-L4", "PNL-L2"],
    ["PNL-L7", "PNL-L4", "PNL-L2"],
    ["PNL-L3B", "PNL-L3A"],
]

# The two acceptance lines that CANNOT PASS on any branch, master included. Every leg was
# handed one of them, so every verifier set merge_ready=false by the letter while writing in
# its notes that the leg itself was clean and the red was pre-existing. Waiving exactly these
# two predicates is what lets verified work merge; panel_gate.py is what replaces them.
# Anything else a verifier failed still refuses the leaf.
DEAD_GATES = (
    re.compile(r"audit_panel\.py\s+--strict.{0,40}exits?\s*0", re.I | re.S),
    re.compile(r"test_bc_wave\.py.{0,40}exits?\s*0", re.I | re.S),
)

# A leg whose verifier found a REAL failure that was then repaired outside the graph. The
# graph only auto-repairs a BROKEN verdict, so a real finding inside a SOUND-WITH-NITS verdict
# would otherwise silently cost the whole leg. Each entry names the exact predicate it clears,
# the branch carrying the repair, and how the repair was proven -- so the waiver is auditable
# rather than a judgement call. A failure this registry does not name still refuses the leaf.
REPAIRED = {
    "PNL-L3B": {
        "branch": "pnl/l3b-repair",
        "clears": "crucible: the probe is read-only and fails on a dead end",
        "proven": "probe_first_click parked and destroyed a seeded conversation store; after "
                  "pinning session_store._resolve_store_dir at a mkdtemp, live and previous are "
                  "byte-intact. Measured both ways 2026-09-21; pinned by "
                  "tests/test_probe_first_click_is_read_only.py, which reddens without the fix.",
    },
}


def sh(cmd: list[str] | str, cwd: Path = ROOT, env: dict | None = None, timeout: int = 1800):
    e = {**os.environ, **(env or {})}
    return subprocess.run(cmd, cwd=str(cwd), env=e, shell=isinstance(cmd, str),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout)


def load_results(paths: list[str] | None = None) -> dict:
    """Later files win per leg, so a resumed graph's results can be layered over an earlier run's."""
    files = [Path(p) for p in paths] if paths else [RESULTS]
    merged: dict = {}
    for f in files:
        if not f.exists():
            sys.exit(f"no {f}: write the workflow result there first")
        merged.update(json.loads(f.read_text(encoding="utf-8")))
    return merged


def _blocking(v: dict, leg: str = "") -> tuple[list[str], list[str]]:
    """(failures that refuse the leaf, failures waived) from a verifier's own rerun."""
    block, waived = [], []
    fixed = (REPAIRED.get(leg) or {}).get("clears", "")
    for a in v.get("acceptance_rerun", []):
        if a.get("verdict") == "pass":
            continue
        p = " ".join((a.get("predicate") or "").split())
        dead = any(rx.search(p) for rx in DEAD_GATES)
        (waived if (dead or (fixed and fixed in p)) else block).append(p)
    return block, waived


def mergeable(leg: str, res: dict) -> tuple[str, str, str, list[str]] | None:
    """(leg, branch, verdict, waived) if this leg may merge, else None. BROKEN never merges."""
    r = res.get(leg) or {}
    v, rc = r.get("verdict") or {}, r.get("receipt") or {}
    if not rc.get("commit_sha") and not rc.get("branch"):
        return None
    if v.get("verdict") in (None, "BROKEN"):
        return None
    block, waived = _blocking(v, leg)
    if block:
        return None
    branch = (REPAIRED.get(leg) or {}).get("branch") or rc.get("branch") or rc["commit_sha"]
    return (leg, branch, v.get("verdict", "?"), waived)


def plan(res: dict) -> list[tuple[str, str, str]]:
    """[(leg, branch, verdict)] in merge order: the deepest mergeable leg of each chain, deduped."""
    out, seen, dropped, said = [], set(), [], set()
    for chain in LEAF_CHAINS:
        pick = next((m for m in (mergeable(l, res) for l in chain) if m), None)
        if pick is None:
            dropped.append(f"{chain[0]}: nothing in {' -> '.join(chain)} is mergeable")
            continue
        leg, branch, verdict, waived = pick
        if leg != chain[0]:
            dropped.append(f"{chain[0]}: not mergeable; fell back to {leg}")
        if leg not in said:
            said.add(leg)
            for w in waived:
                tag = "repaired on " + REPAIRED[leg]["branch"] if leg in REPAIRED and REPAIRED[leg]["clears"] in w else "dead gate, replaced by panel_gate.py"
                print(f"   WAIVED  {leg}: {tag} -- {w[:88]}")
        if branch in seen:
            continue
        seen.add(branch)
        out.append((leg, branch, verdict))
    for leg in (l for chain in LEAF_CHAINS for l in chain):
        r = res.get(leg) or {}
        block, _ = _blocking((r.get("verdict") or {}), leg)
        for b in block:
            print(f"   REFUSES {leg}: real failure, not a dead gate -- {b[:96]}")
    if dropped:
        print("SPEC LEGS NOT LANDING (say so in the release notes):")
        for d in dropped:
            print("   ", d)
    return out


# The instruments (PNL-L0 audit fix, L0b the gate, L0c the pass-line parser) live on their own
# branch and are merged FIRST, before any leaf. They are an ancestor of every leaf, so this only
# ever adds instrument commits made after the leaves branched -- and it guarantees the gate that
# judges the integration is the current one, not whatever version a leaf happened to inherit.
# pnl/release-prep carries the rulings record, the Jev routing ledgers, the design spec and the
# one test repair the record forced (tests/test_ingest_rulings.py seeds from the REAL
# resolved.json, so ruling on A1 for real reddened it). Merged with the instruments so the
# stock-suite row actually exercises the record + the repair together, rather than meeting
# them for the first time in CI after the tag is cut.
INSTRUMENT_BRANCHES = ["pnl/gate-fix", "pnl/release-prep"]

RATCHET_BASELINES = {"harness/notes/bp9/audit_baseline.json", "harness/notes/bp9/seat_baseline.json"}


def _rows(stage: int, path: str, cwd: Path) -> dict:
    r = sh(["git", "show", f":{stage}:{path}"], cwd=cwd)
    if r.returncode:
        return {}
    d = json.loads(r.stdout)
    return {f["check"]: f for f in d.get("failures", [])}


def resolve_ratchets(conflicts: list[str], cwd: Path) -> list[str] | None:
    """Auto-resolve a baseline both legs edited. Two legs each deleting the row they own IS the
    ratchet working, and the merge of those two deletions is unambiguous: a row survives only if
    BOTH sides kept it. Anything else -- a side ADDING a row, or any other conflicting path --
    returns None and the merge stops for a human. Returns the dropped check names."""
    if any(c not in RATCHET_BASELINES for c in conflicts):
        return None
    dropped = []
    for path in conflicts:
        base, ours, theirs = (_rows(s, path, cwd) for s in (1, 2, 3))
        if (set(ours) | set(theirs)) - set(base):
            return None  # a side recorded a NEW failure; never auto-merge that away
        keep = sorted(set(ours) & set(theirs))
        dropped += [c for c in base if c not in keep]
        why = json.loads(sh(["git", "show", f":1:{path}"], cwd=cwd).stdout).get("_why", "")
        (cwd / path).write_text(
            json.dumps({"_why": why, "failures": [base[c] for c in keep]}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        sh(["git", "add", path], cwd=cwd)
    return dropped


def merge(leaves) -> int:
    if INT_DIR.exists():
        sh(["git", "worktree", "remove", "--force", str(INT_DIR)])
    sh(["git", "branch", "-D", INT_BRANCH])
    r = sh(["git", "worktree", "add", "-b", INT_BRANCH, str(INT_DIR), "master"])
    if r.returncode:
        print(r.stdout, r.stderr)
        return 1
    pre = [("instruments", b, "gate") for b in INSTRUMENT_BRANCHES]
    for leg, branch, verdict in pre + list(leaves):
        m = sh(["git", "merge", "--no-edit", "--no-ff", branch, "-m", f"merge(pnl): {leg} {branch} [{verdict}]"], cwd=INT_DIR)
        if m.returncode:
            conflicts = sh(["git", "diff", "--name-only", "--diff-filter=U"], cwd=INT_DIR).stdout.split()
            dropped = resolve_ratchets(conflicts, INT_DIR)
            if dropped is None:
                print(f"CONFLICT merging {leg} ({branch}):\n  " + "\n  ".join(conflicts))
                print("left in place for a human; resolve in", INT_DIR, "or run --merge again after a fix")
                return 2
            c = sh(["git", "commit", "--no-edit"], cwd=INT_DIR)
            if c.returncode:
                print("could not close the auto-resolved merge:", c.stdout, c.stderr)
                return 2
            print(f"   ratchet baseline auto-resolved; rows both legs fixed: {dropped}")
        print(f"merged {leg:9} {branch}")
    n = sh(["git", "rev-list", "--count", f"master..{INT_BRANCH}"]).stdout.strip()
    print(f"{INT_BRANCH} is {n} commits over master at {INT_DIR}")
    return 0


_SUMMARY = re.compile(r"(\d+) (passed|failed|error)", re.I)


def _verdict(out: str) -> tuple[bool, str]:
    """A pytest run is green only if a summary line exists AND names no failure.
    A run that is entirely skipped is NOT green (hytest skips when PySide is absent)."""
    line = ""
    for ln in out.splitlines():
        if ("passed" in ln or "failed" in ln or "error" in ln) and ("=" in ln or " in " in ln):
            line = ln.strip()
    if not line:
        return False, "no pytest summary line (did it run?)"
    if re.search(r"\d+ (failed|error)", line):
        return False, line
    if not re.search(r"[1-9]\d* passed", line):
        return False, line + "  (no test actually passed)"
    return True, line


def baselines_only_shrank() -> tuple[bool, str]:
    """A ratchet baseline may only LOSE rows. The ratchet itself refuses a failure that is not
    baselined -- but nothing stopped a leg from ADDING its new failure to the baseline and
    passing. Reference is the baseline as authored on the instrument branch, where each row was
    measured on master. Rows may be deleted (the commit that fixes them); a row that appears
    here and not there is a leg widening its own gate."""
    bad, seen = [], []
    for rel in sorted(RATCHET_BASELINES):
        ref = sh(["git", "show", f"{INSTRUMENT_BRANCHES[0]}:{rel}"], cwd=ROOT)
        now = (INT_DIR / rel)
        if ref.returncode or not now.exists():
            bad.append(f"{rel}: missing on {INSTRUMENT_BRANCHES[0]} or in the integration")
            continue
        was = {f["check"] for f in json.loads(ref.stdout).get("failures", [])}
        has = {f["check"] for f in json.loads(now.read_text(encoding="utf-8")).get("failures", [])}
        added = sorted(has - was)
        if added:
            bad.append(f"{rel}: {len(added)} row(s) ADDED: {added}")
        seen.append(f"{Path(rel).stem} {len(was)}->{len(has)}")
    return (not bad), ("; ".join(bad) if bad else "only shrank: " + ", ".join(seen))


def gate() -> int:
    if not INT_DIR.exists():
        sys.exit(f"{INT_DIR} does not exist: run --merge first")
    LOGDIR.mkdir(parents=True, exist_ok=True)
    env = {"SYNAPSE_HYTHON": HYTHON, "QT_QPA_PLATFORM": "offscreen",
           "SYNAPSE_LOG_DIR": str(INT_DIR / ".scratch" / "logs")}
    (INT_DIR / ".scratch" / "logs").mkdir(parents=True, exist_ok=True)

    gates = [
        ("no test deleted", ["git", "diff", "--diff-filter=D", "--name-only", "master", "--", "tests/"], "empty"),
        ("ratchet baselines only shrank", None, "baselines"),
        ("stock suite (alone)", [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider",
                                 "-m", "not needs_houdini", "--deselect", "tests/test_phase0c_doc1_toolcount.py"], "pytest"),
        # NOT "audit exits 0" and NOT "the seat suite is green": both were dead gates that could
        # not pass on master, and both lied from a worktree (HOUDINI_PACKAGE_DIR aims hython at
        # the MAIN tree). panel_gate.py proves which tree it measured, then ratchets each
        # instrument against its committed baseline. Exit 2 means a baseline row now passes and
        # must be deleted -- that is a FAIL here too: the baseline has to shrink in the fixing commit.
        # BP10-SCAFFOLD added harness/jev/tests to pyproject testpaths AND to a CI step of its own.
        # "pytest tests/" above does not collect it, so without this row CI would be the first
        # thing to run it -- after the tag is cut. Both prior releases had to re-cut a tag; not again.
        ("jev suite (CI runs this too)", [sys.executable, "-m", "pytest", "harness/jev/tests", "-q",
                                          "-p", "no:cacheprovider"], "pytest"),
        ("panel gate: audit ratchet", [sys.executable, "harness/notes/bp9/panel_gate.py", "--audit"], "exit0"),
        ("panel gate: seat ratchet", [sys.executable, "harness/notes/bp9/panel_gate.py", "--seat"], "exit0"),
        ("first-click probe", [HYTHON, "python/synapse/panel/scripts/probe_first_click.py"], "exit0"),
        ("measure probe", [HYTHON, "python/synapse/panel/scripts/probe_measure.py"], "exit0"),
        ("host-floor probe", [HYTHON, "python/synapse/panel/scripts/probe_ui_font.py"], "exit0"),
    ]
    rows, bad = [], 0
    for name, cmd, kind in gates:
        print(f"-- {name} ...", flush=True)
        if kind == "baselines":
            ok, ev = baselines_only_shrank()
            (LOGDIR / "ratchet-baselines.log").write_text(ev, encoding="utf-8")
            rows.append((name, ok, ev)); bad += 0 if ok else 1
            print(f"   {'PASS' if ok else 'FAIL'}  {ev}")
            continue
        r = sh(cmd, cwd=INT_DIR, env=env, timeout=3600)
        out = (r.stdout or "") + (r.stderr or "")
        (LOGDIR / (re.sub(r"[^a-z0-9]+", "-", name.lower()) + ".log")).write_text(out, encoding="utf-8")
        if kind == "empty":
            ok, ev = (not out.strip()), (out.strip() or "no test file deleted")
        elif kind == "pytest":
            ok, ev = _verdict(out)
        else:
            ok = r.returncode == 0
            ev = (out.strip().splitlines() or ["(no output)"])[-1][:160]
        rows.append((name, ok, ev))
        bad += 0 if ok else 1
        print(f"   {'PASS' if ok else 'FAIL'}  {ev}")

    print("\n== composed gate ==")
    for name, ok, ev in rows:
        print(f"{'PASS' if ok else 'FAIL'}  {name:34} {ev[:110]}")
    print(f"\n{len(rows) - bad}/{len(rows)} gates green; logs in {LOGDIR}")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--results", nargs="+", metavar="JSON",
                    help="workflow result file(s); later files win per leg (default: panel_results.json)")
    a = ap.parse_args()
    if not (a.plan or a.merge or a.gate):
        ap.error("pick --plan, --merge and/or --gate")
    rc = 0
    if a.plan or a.merge:
        leaves = plan(load_results(a.results))
        print("merge plan:", " -> ".join(f"{l}({b})" for l, b, _ in leaves) or "(nothing merge-ready)")
        if a.merge:
            if not leaves:
                sys.exit("nothing merge-ready; refusing to build an empty integration")
            rc = merge(leaves)
    if a.gate and rc == 0:
        rc = gate()
    sys.exit(rc)
