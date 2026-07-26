#!/usr/bin/env python
"""R34 mutation battery for the Ledger -> Moneta seam pins.

Law 1: every check must be able to fail — PROVE it can. This is the producer
behind the "every new pin fails against its mutation" claim in the LEDGER leg
receipt. It deliberately breaks the implementation, one defect at a time, and
records which pins noticed.

Each mutation is a textual edit applied to a real source file; the file is
restored from its original bytes in a finally-block, so an interrupted run
cannot leave the tree poisoned (verify with `git status` afterwards regardless).

Usage:
    python harness/verify/mutate_ledger_moneta_seam.py [--json <out>]

Exit code 0 iff EVERY mutation was caught by at least one pin. A surviving
mutation means the pins are decoration for that behaviour.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEDGER = os.path.join(REPO, "python", "synapse", "memory", "ledger.py")
RUNTIME = os.path.join(REPO, "python", "synapse", "memory", "moneta_runtime.py")
TESTS = os.path.join("tests", "test_ledger_moneta_seam.py")

# (id, file, description, old, new)  -- `old` must appear EXACTLY once.
MUTATIONS = [
    (
        "stub-returns-none",
        LEDGER,
        "The shipped defect: the seam returns before depositing anything.",
        '    status: Dict = {"deposited": False, "reason": "backend-off",',
        '    return {"deposited": False, "reason": "backend-off", "memory_id": None,\n'
        '            "provenance": None}\n'
        '    status: Dict = {"deposited": False, "reason": "backend-off",',
    ),
    (
        "swallow-errors-report-success",
        LEDGER,
        "Law 3: a failed substrate write reported as a success.",
        '        status["reason"] = f"error: {type(exc).__name__}: {exc}"',
        '        status["deposited"] = True\n'
        '        status["reason"] = "deposited"',
    ),
    (
        "drop-moneta-key-from-result",
        LEDGER,
        "deposit() stops reporting what the substrate leg did.",
        '        "moneta": moneta_result,',
        "",
    ),
    (
        "ignore-backend-flag",
        LEDGER,
        "Gate on availability alone, so `jsonl` still writes to Moneta.",
        '    return os.environ.get("SYNAPSE_MEMORY_BACKEND", "").strip().lower() in MONETA_BACKENDS',
        "    return True",
    ),
    (
        "project-at-conversation-tier",
        LEDGER,
        "Findings lose their protected floor and decay on a sleep pass.",
        "        tier=MemoryTier.SHOW,",
        "        tier=MemoryTier.CONVERSATION,",
    ),
    (
        "drop-record-pointer-and-text",
        LEDGER,
        "The memory lands but carries no recallable content.",
        '    lines.append(f"record: {stem}.json")',
        "    lines = [headline]",
    ),
    (
        "drop-revision-tag",
        LEDGER,
        "The revision is reported but not carried BY the memory.",
        '        tags.append(f"moneta_rev:{revision[:12]}")',
        "        pass",
    ),
    (
        "provenance-only-on-success",
        LEDGER,
        "Provenance is withheld exactly when the deposit fails.",
        '    provenance = mr.moneta_provenance()\n    status["provenance"] = {',
        '    provenance = mr.moneta_provenance()\n    _unused = {',
    ),
    (
        "let-the-substrate-raise",
        LEDGER,
        "A substrate error escapes deposit() and takes the file write with it.",
        "    except Exception as exc:  # noqa: BLE001 -- enrichment never fails the deposit\n"
        '        status["reason"] = f"error: {type(exc).__name__}: {exc}"',
        "    except ZeroDivisionError as exc:\n"
        '        status["reason"] = f"error: {type(exc).__name__}: {exc}"',
    ),
    (
        "revision-always-none",
        RUNTIME,
        "The shipped defect: provenance never resolves a commit.",
        "    git_dir, work_dir = _find_git_dir(root)",
        "    git_dir, work_dir = None, None",
    ),
    (
        "no-packed-refs-fallback",
        RUNTIME,
        "Only loose refs are read; a gc'd repo resolves to nothing.",
        '    packed = _read_text(os.path.join(common_dir, "packed-refs"))',
        "    packed = None",
    ),
    (
        "no-detached-head",
        RUNTIME,
        "HEAD is assumed to always be a symbolic ref.",
        "        if _SHA_RE.match(head):  # detached HEAD",
        "        if False:  # detached HEAD",
    ),
    (
        "gitdir-file-unsupported",
        RUNTIME,
        "Linked worktrees (a `.git` FILE) are not resolved.",
        "        if os.path.isfile(candidate):",
        "        if False:",
    ),
    (
        "ignore-commondir",
        RUNTIME,
        "A linked worktree looks for refs in its own git dir only.",
        '    text = _read_text(os.path.join(git_dir, "commondir"))',
        "    text = None",
    ),
    (
        "no-cache",
        RUNTIME,
        "The git metadata is re-read from disk on every call.",
        "    cached = _REVISION_CACHE.get(root)",
        "    cached = None",
    ),
    (
        "installed-copy-inherits-a-sha",
        RUNTIME,
        "A copy under site-packages inherits an enclosing repo's HEAD.",
        "    if _INSTALLED_MARKERS & parts:\n        return None, None",
        "    if False:\n        return None, None",
    ),
    (
        "unbounded-upward-walk",
        RUNTIME,
        "The walk reaches an unrelated repo far above the package.",
        "    for _ in range(MAX_REVISION_WALK + 1):",
        "    for _ in range(10_000):",
    ),
    (
        "widen-the-walk-bound",
        RUNTIME,
        "MAX_REVISION_WALK back to 3: a vendored copy inherits the host repo's "
        "HEAD (the CRUCIBLE blocker the site-packages guard did not cover).",
        "MAX_REVISION_WALK = 1",
        "MAX_REVISION_WALK = 3",
    ),
    (
        "drop-resolved-at-stamp",
        RUNTIME,
        "The permanent cache stops dating its own read.",
        '        "revision_resolved_at": _utc_now(),',
        '        "revision_resolved_at": None,',
    ),
    (
        "uncached-version-lookup",
        RUNTIME,
        "importlib.metadata.version() runs on every provenance call.",
        "    if _VERSION_CACHE is _VERSION_UNSET:",
        "    if True:",
    ),
    (
        "narrow-the-backend-vocabulary",
        LEDGER,
        "`shadow` silently stops enabling the seam.",
        'MONETA_BACKENDS = ("moneta", "shadow")',
        'MONETA_BACKENDS = ("moneta",)',
    ),
    (
        "claim-durability-on-accept",
        LEDGER,
        "An in-memory accept is reported as durable.",
        '                    "durable": False, "durability": MONETA_DURABILITY}',
        '                    "durable": True, "durability": MONETA_DURABILITY}',
    ),
    (
        "backfill-discards-substrate-status",
        LEDGER,
        "backfill() reports a clean run while every substrate write fails.",
        '        "moneta_deposited": moneta_deposited,\n        "moneta_failures": moneta_failures,',
        '        "moneta_deposited": len(parsed),\n        "moneta_failures": [],',
    ),
    (
        "science-sink-discards-substrate-status",
        os.path.join(REPO, "python", "synapse", "science", "deposit.py"),
        "The only live producer stops reporting substrate outcomes.",
        "            if moneta.get(\"deposited\"):\n                self.moneta_deposited += 1",
        "            if False:\n                self.moneta_deposited += 1",
    ),
    (
        "drop-scope-caveat",
        RUNTIME,
        "The SHA is presented as a full pin of the substrate.",
        '    "committed-only; uncommitted or untracked working-tree edits under "',
        '    "exact pin of the loaded substrate under "',
    ),
]


def run_pins() -> tuple[bool, str]:
    """Run the seam pins. Returns (all_green, tail)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TESTS],
        cwd=REPO, capture_output=True, text=True,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    # The pytest summary line ONLY. pytest's tmpdir cleanup can emit an atexit
    # PermissionError on Windows containing the word "error"; a loose match let
    # that line masquerade as the verdict and made every row unreadable.
    summary = re.compile(r"^=*\s*\d+\s+(passed|failed|error)")
    tail = ""
    for line in out.splitlines():
        stripped = line.strip()
        if summary.match(stripped) or re.search(r"\d+ (passed|failed)", stripped):
            tail = stripped
    return proc.returncode == 0, tail or "(no pytest summary line)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    green, baseline = run_pins()
    if not green:
        print(f"REFUSING: pins are not green before mutation -> {baseline}")
        return 2
    print(f"baseline (unmutated): {baseline}")

    results = []
    for mid, path, why, old, new in MUTATIONS:
        with open(path, "r", encoding="utf-8", newline="") as fh:
            original = fh.read()
        occurrences = original.count(old)
        if occurrences != 1:
            results.append({"id": mid, "caught": False,
                            "error": f"anchor matched {occurrences}x, expected 1"})
            print(f"  [ANCHOR-MISS] {mid}: matched {occurrences}x")
            continue
        try:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(original.replace(old, new, 1))
            still_green, tail = run_pins()
            caught = not still_green
            failed = re.search(r"(\d+) failed", tail)
            results.append({
                "id": mid, "file": os.path.relpath(path, REPO), "mutation": why,
                "caught": caught, "pins_failed": int(failed.group(1)) if failed else 0,
                "pytest": tail,
            })
            print(f"  [{'CAUGHT' if caught else 'SURVIVED'}] {mid}: {tail}")
        finally:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(original)

    survivors = [r for r in results if not r.get("caught")]
    report = {
        "schema": "mutation-battery/v1",
        "target": "ledger -> moneta seam + moneta revision provenance",
        "producer": "harness/verify/mutate_ledger_moneta_seam.py",
        "pins": TESTS.replace(os.sep, "/"),
        "baseline": baseline,
        "mutations": len(MUTATIONS),
        "caught": len(results) - len(survivors),
        "survived": [r["id"] for r in survivors],
        "results": results,
    }
    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    # Post-condition: the tree must be exactly as we found it.
    restored, _ = run_pins()
    print(f"\n{report['caught']}/{len(MUTATIONS)} mutations caught; "
          f"tree restored green: {restored}")
    if survivors:
        print("SURVIVORS (pins are decoration for these): " + ", ".join(report["survived"]))
    return 0 if (not survivors and restored) else 1


if __name__ == "__main__":
    raise SystemExit(main())
