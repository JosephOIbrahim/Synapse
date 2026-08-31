#!/usr/bin/env python3
"""BP1-CRUX self-authored mutation set against the recall-honesty path.

Adversarial: the crucible trusts no builder's proved_it_bites. Each mutation is
applied to a fresh checkout of bp1/honesty's ports.py, the honesty goalpost
suite is run, and the mutation is REVERTED via `git checkout -- <file>` (never
stash, per worktree discipline). A mutation that leaves the suite green is a
MUTATION ESCAPE = a hole in the test net (a finding), not a pass. Two mutations
are brief-mandated: restore-empty-list-return and delete-layer-check.

Run:  python BP1-CRUX_mutations.py <honesty_worktree_path>
Emits a JSON ledger to stdout AND to BP1-CRUX_mutations.json beside this file.
"""
import json
import subprocess
import sys
from pathlib import Path

WT = Path(sys.argv[1]).resolve()
PORTS = WT / "python" / "synapse" / "loop" / "ports.py"
TEST = "tests/test_memory_recall_honesty.py"
OUT = Path(__file__).resolve().parent / "BP1-CRUX_mutations.json"

# (id, human name, primary test it must redden, FIND anchor, REPLACE)
MUTATIONS = [
    # ---- brief-mandated ----
    ("MUT-1-restore-empty-list", "restore the old empty-list bare-SUCCESS return",
     "test_empty_list_under_bare_success_is_impossible",
     '''        if clean:
            payload["hit"] = True
            return _require_status(PortResult.ok(payload))

        # Ran, observed the layer, kept nothing: an EXPLICIT no-match, never an
        # empty list smuggled under a bare SUCCESS. quota_pruned when candidates
        # matched the relation-key predicate but PG-DRM dropped them all (the
        # ``dropped`` breakdown says which rule); predicate_nomatch when nothing
        # matched the relation keys in the first place.
        payload["hit"] = False
        payload["reason"] = "quota_pruned" if candidates_seen else "predicate_nomatch"
        return _require_status(PortResult.ok(payload))''',
     '''        return _require_status(PortResult.ok(payload))'''),

    ("MUT-2-delete-layer-check", "delete the layer_uncomposed guard in query_and_filter",
     "test_layer_absent_is_unavailable",
     '''        if not self._layer_observable():
            return self._unobservable(
                "layer_uncomposed",
                "bound store carries no composed memory layer (Moneta "
                "_handle.ecs is absent); recall cannot observe rows to filter",
            )

''',
     ''),

    # ---- crucible's own ----
    ("MUT-3-layer-observable-lies", "_layer_observable always returns True",
     "test_layer_absent_is_unavailable",
     '''        handle = getattr(self._store, "_handle", _MISSING)
        if handle is _MISSING:
            return True
        return getattr(handle, "ecs", None) is not None''',
     '''        return True'''),

    ("MUT-4-reason-swap", "invert the quota_pruned/predicate_nomatch condition",
     "test_nomatch_quota_pruned_when_candidates_are_all_dropped",
     '''        payload["reason"] = "quota_pruned" if candidates_seen else "predicate_nomatch"''',
     '''        payload["reason"] = "predicate_nomatch" if candidates_seen else "quota_pruned"'''),

    ("MUT-5-hit-lies", "hit=False even when clean results survive",
     "test_hit_is_explicit",
     '''            payload["hit"] = True''',
     '''            payload["hit"] = False'''),

    ("MUT-6-env-gate-swap", "invert env_unset/plugin_unregistered classifier",
     "test_moneta_env_gate_classifies_env_vs_plugin",
     '''    return "plugin_unregistered" if env_present else "env_unset"''',
     '''    return "env_unset" if env_present else "plugin_unregistered"'''),

    ("MUT-7-bind-gate-none", "_bind_gate_token never names a gate (returns None)",
     "test_bound_but_moneta_unimportable_names_the_env_gate",
     '''        if detail and "importable" in detail:
            return _moneta_env_gate()
        return None''',
     '''        return None'''),

    ("MUT-8-unobservable-token-drop", "_unobservable drops the gate token from error_message",
     "test_layer_absent_is_unavailable",
     '''            error_message=gate,''',
     '''            error_message="unavailable",'''),
]


def revert():
    subprocess.run(["git", "-C", str(WT), "checkout", "--", "python/synapse/loop/ports.py"],
                   check=True, capture_output=True)


def run_suite():
    p = subprocess.run(
        [sys.executable, "-m", "pytest", TEST, "-q", "--tb=no", "-rfE", "-p", "no:cacheprovider"],
        cwd=str(WT), capture_output=True, text=True)
    failed = []
    for line in (p.stdout + p.stderr).splitlines():
        s = line.strip()
        if s.startswith("FAILED ") or s.startswith("ERROR "):
            failed.append(s.split(" ", 1)[1].split(" ")[0])
    summ = ""
    for line in p.stdout.splitlines():
        if "passed" in line or "failed" in line or "error" in line:
            summ = line.strip()
    return p.returncode, failed, summ


def main():
    revert()  # ensure pristine
    base_rc, base_failed, base_summ = run_suite()
    ledger = {
        "leg": "BP1-CRUX",
        "target": "python/synapse/loop/ports.py recall path (bp1/honesty)",
        "worktree": str(WT),
        "baseline": {"returncode": base_rc, "green": base_rc == 0, "summary": base_summ,
                     "failed": base_failed},
        "mutations": [],
    }
    src0 = PORTS.read_text(encoding="utf-8")
    for mid, name, target, find, repl in MUTATIONS:
        n = src0.count(find)
        entry = {"id": mid, "name": name, "target_test": target, "anchor_hits": n}
        if n != 1:
            entry.update({"applied": False, "reddened": None,
                          "note": f"ANCHOR MATCH COUNT {n} (expected 1) - not applied cleanly"})
            ledger["mutations"].append(entry)
            continue
        PORTS.write_text(src0.replace(find, repl, 1), encoding="utf-8")
        rc, failed, summ = run_suite()
        revert()
        entry.update({
            "applied": True,
            "reddened": rc != 0,
            "returncode": rc,
            "summary": summ,
            "failed_tests": failed,
            "target_in_failed": any(target in f for f in failed),
        })
        ledger["mutations"].append(entry)

    revert()
    final_rc, final_failed, final_summ = run_suite()
    ledger["post_revert"] = {"returncode": final_rc, "green": final_rc == 0,
                             "summary": final_summ, "failed": final_failed}
    applied = [m for m in ledger["mutations"] if m.get("applied")]
    escapes = [m for m in applied if not m.get("reddened")]
    anchor_misses = [m for m in ledger["mutations"] if not m.get("applied")]
    ledger["rollup"] = {
        "total": len(MUTATIONS),
        "applied_cleanly": len(applied),
        "reddened": sum(1 for m in applied if m.get("reddened")),
        "escapes": [m["id"] for m in escapes],
        "anchor_misses": [m["id"] for m in anchor_misses],
        "all_named_targets_hit": all(m.get("target_in_failed") for m in applied),
        "baseline_green_before_and_after": base_rc == 0 and final_rc == 0,
    }
    OUT.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    print(json.dumps(ledger, indent=2))


if __name__ == "__main__":
    main()
