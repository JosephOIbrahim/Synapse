#!/usr/bin/env python3
"""W5-WCRUX probe 1 - combined-state scratch tree verification.

Read-only. Drives git via subprocess (the checks.py idiom) so it runs under the
python-exec permission surface. Verifies, for the harness-provisioned combined
scratch tree (wcrux-scratch @ df8c9ef3 with CATALOG+PARMGATE+MEASURES staged):

  1. FAITHFULNESS  - staged file SET == exact union of the three legs' committed
     files, and each staged file's git BLOB SHA == its leg branch blob (no
     tamper, nothing laundered in, nothing dropped).
  2. MASTER DRIFT  - does master's post-fork drift touch any leg file (a merge to
     *current* master could conflict where this fork-point probe cannot see).
  3. LEDGER R1     - harness/ingest_ledger.json byte-identical base vs combined
     (single-writer: staging the catalog data did NOT write the served ledger).

Emits one JSON blob to stdout. Judgement is the crucible's; this reports facts.
"""
import subprocess, json, hashlib
from pathlib import Path

WT = "C:/Users/User/SYNAPSE/.claude/worktrees"
BASE = f"{WT}/wcrux-base"
SCRATCH = f"{WT}/wcrux-scratch"
SELF = f"{WT}/w5-wcrux"
FORK = "df8c9ef3"
LEGS = {"CATALOG": "wave5/catalog", "PARMGATE": "wave5/parmgate", "MEASURES": "wave5/measures"}
RECEIPTS = {"harness/notes/receipts/W5-CATALOG.json",
            "harness/notes/receipts/W5-PARMGATE.json",
            "harness/notes/receipts/W5-MEASURES.json"}


def git(args, cwd=SELF):
    p = subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return p.returncode, p.stdout or "", p.stderr or ""


def sha256(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


out = {"probe": "combined", "fork": FORK}

# 1. faithfulness -----------------------------------------------------------
leg_files, union, owner = {}, set(), {}
for name, branch in LEGS.items():
    rc, so, se = git(["diff", "--name-only", f"master...{branch}"])
    files = {l.strip() for l in so.splitlines() if l.strip()}
    leg_files[name] = sorted(files)
    union |= files
    for f in files:
        owner.setdefault(f, branch)

rc, so, se = git(["status", "--porcelain"], cwd=SCRATCH)
staged = {line[3:].strip() for line in so.splitlines() if line.strip() and line[:2].strip()}

out["union_count"] = len(union)
out["staged_count"] = len(staged)
out["missing_from_scratch"] = sorted(union - staged)
out["extra_in_scratch"] = sorted(staged - union)
out["set_faithful"] = (union == staged)
out["receipts_staged"] = sorted(RECEIPTS & staged)
out["per_leg_file_counts"] = {k: len(v) for k, v in leg_files.items()}

# content faithfulness: git blob sha (branch) vs hash-object (scratch worktree)
content_mismatch = []
for f, branch in sorted(owner.items()):
    rc1, branch_blob, _ = git(["rev-parse", f"{branch}:{f}"])
    rc2, scratch_blob, _ = git(["hash-object", "--", f], cwd=SCRATCH)
    branch_blob, scratch_blob = branch_blob.strip(), scratch_blob.strip()
    if rc1 != 0 or not branch_blob:
        content_mismatch.append({"file": f, "why": f"missing on {branch}"})
    elif rc2 != 0 or not scratch_blob:
        content_mismatch.append({"file": f, "why": "absent/unhashable in scratch"})
    elif branch_blob != scratch_blob:
        content_mismatch.append({"file": f, "why": f"blob differs {branch_blob[:8]} vs {scratch_blob[:8]}"})
out["content_mismatches"] = content_mismatch
out["content_faithful"] = (len(content_mismatch) == 0)

# 2. master drift over leg files -------------------------------------------
rc, so, se = git(["diff", "--name-only", FORK, "master"])
master_changed = {l.strip() for l in so.splitlines() if l.strip()}
leg_product = union - RECEIPTS
overlap = sorted(master_changed & leg_product)
out["master_drift"] = {
    "master_changed_since_fork": len(master_changed),
    "overlap_with_leg_files": overlap,
    "conflict_risk": len(overlap) > 0,
}

# 3. ingest_ledger R1 byte-check -------------------------------------------
led_base = sha256(f"{BASE}/harness/ingest_ledger.json")
led_scratch = sha256(f"{SCRATCH}/harness/ingest_ledger.json")
out["ingest_ledger"] = {
    "base_sha256": led_base,
    "scratch_sha256": led_scratch,
    "byte_identical": (led_base is not None and led_base == led_scratch),
    "note": "single-writer R1: staging the 3 legs must not touch the served ingest ledger",
}

print(json.dumps(out, indent=2))
