#!/usr/bin/env python
"""RSI Line R — L1/L2/L3 closure eval (render-farm learning).

Proves the render-fix learning loop COMPOUNDS across a real process boundary —
the property the audit found every RSI loop lacks. The handler fix
(handlers_render.py: wire get_synapse_memory() into _handle_render_sequence)
is what gives the orchestrator a real store in production; this eval verifies
that GIVEN a real store, the record -> persist -> reload -> apply path closes:

  L1  in-process       record_fix_outcome() -> query_known_fixes() reads it back
  L2  across-restart    a FRESH interpreter reloads the persisted FEEDBACK record
                        (replicated on a SECOND fresh process — restart-aware:
                         one restart is a sample, two is a result)
  L3  behavior-change   after restart, _warmup_from_memory() returns the LEARNED
                        setting (pathtracedsamples=128) while an empty store
                        returns {} — the persisted record alters a later decision

Pure CPython; no Houdini required (hou imports are try/except-guarded).
Run:    python tests/rsi/eval_line_r_closure.py
Exit 0 = every rung PASS. Internal modes: --write <dir> | --read <dir>.
"""
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# Make the synapse package importable regardless of cwd / PYTHONPATH.
_here = Path(__file__).resolve()
for _p in _here.parents:
    if (_p / "python" / "synapse").is_dir():
        sys.path.insert(0, str(_p / "python"))
        break

SCENE_TAGS = ["interior", "karma"]
ISSUE = "saturation"
LEARNED = {"pathtracedsamples": 128.0}   # the learned, persisted value
STATIC_DEFAULT = 64.0                     # a cold ROP's starting samples


def _make_memory(storage_dir):
    from synapse.memory.store import SynapseMemory
    return SynapseMemory(project_path=str(storage_dir))


def do_write(storage_dir):
    """P1: record a learned render-fix, flush, prove L1 in-process."""
    from synapse.server.render_diagnostics import (
        record_fix_outcome, query_known_fixes, ISSUE_REMEDIES,
    )
    mem = _make_memory(storage_dir)
    remedy = ISSUE_REMEDIES[ISSUE][0]  # the pathtracedsamples remedy
    record_fix_outcome(
        mem, ISSUE, remedy, success=True,
        scene_tags=SCENE_TAGS, settings_applied=LEARNED, frame=1001,
    )
    # BLOCKER #1: the store defers writes to a ~2s background flusher; force the
    # write to disk before this process exits, or a real kill would lose it.
    mem.store.flush()

    fixes = query_known_fixes(mem, ISSUE, SCENE_TAGS, limit=3)
    ok = bool(fixes) and "pathtracedsamples = 128" in fixes[0]["content"]
    print(f"WRITE storage_dir={mem.storage_dir}")
    print(f"L1_INPROCESS={'PASS' if ok else 'FAIL'} "
          f"n={len(fixes)} score={fixes[0]['score'] if fixes else 'NA'}")
    return 0 if ok else 1


def do_read(storage_dir):
    """P2/P3 (fresh process): reload across restart (L2) + behavior-change (L3)."""
    from unittest.mock import MagicMock
    from synapse.server.render_diagnostics import query_known_fixes
    from synapse.server.render_farm import RenderFarmOrchestrator

    mem = _make_memory(storage_dir)

    # L2 — the persisted FEEDBACK record reloaded in a brand-new interpreter
    fixes = query_known_fixes(mem, ISSUE, SCENE_TAGS, limit=3)
    reloaded = bool(fixes) and "pathtracedsamples = 128" in fixes[0]["content"]

    # L3 — same warmup call, same scene tags: the store WITH the learned record
    # pre-applies 128; an empty store pre-applies nothing.
    warm_orch = RenderFarmOrchestrator(callbacks=MagicMock(), memory=mem)
    warm_orch._scene_tags = list(SCENE_TAGS)
    warm = warm_orch._warmup_from_memory("/stage/karma1")

    cold_dir = tempfile.mkdtemp(prefix="rsi_cold_")
    try:
        cold_mem = _make_memory(cold_dir)  # empty store, no learned fix
        cold_orch = RenderFarmOrchestrator(callbacks=MagicMock(), memory=cold_mem)
        cold_orch._scene_tags = list(SCENE_TAGS)
        cold = cold_orch._warmup_from_memory("/stage/karma1")
    finally:
        shutil.rmtree(cold_dir, ignore_errors=True)

    learned_applied = warm.get("pathtracedsamples") == 128.0
    behavior_changed = learned_applied and warm != cold

    print(f"READ storage_dir={mem.storage_dir}")
    print(f"L2_RESTART={'PASS' if reloaded else 'FAIL'} "
          f"n={len(fixes)} score={fixes[0]['score'] if fixes else 'NA'}")
    print(f"L3_BEHAVIOR={'PASS' if behavior_changed else 'FAIL'} "
          f"warm={warm} cold={cold} static_default={STATIC_DEFAULT}")
    return 0 if (reloaded and behavior_changed) else 1


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--write":
        return do_write(sys.argv[2])
    if len(sys.argv) >= 3 and sys.argv[1] == "--read":
        return do_read(sys.argv[2])

    work = tempfile.mkdtemp(prefix="rsi_line_r_")
    try:
        print(f"== RSI Line R closure eval ==  workdir={work}")
        p1 = subprocess.run([sys.executable, str(_here), "--write", work],
                            capture_output=True, text=True)
        print(p1.stdout.strip())
        if p1.returncode != 0:
            print("WRITE/L1 process failed:\n" + p1.stderr)
            return 1

        reads = []
        for i in (1, 2):  # two genuinely fresh interpreters = restart-aware
            pr = subprocess.run([sys.executable, str(_here), "--read", work],
                                capture_output=True, text=True)
            print(f"-- restart {i} (fresh process) --")
            print(pr.stdout.strip())
            if pr.returncode != 0 and pr.stderr:
                print(f"restart {i} stderr:\n" + pr.stderr)
            reads.append(pr.returncode == 0)

        l1 = p1.returncode == 0
        l2l3 = all(reads) and len(reads) == 2
        print("\n== VERDICT ==")
        print(f"L1 in-process:          {'PASS' if l1 else 'FAIL'}")
        print(f"L2 across-restart:      {'PASS' if l2l3 else 'FAIL'} "
              f"(restart-aware: {sum(reads)}/2 fresh processes reloaded the record)")
        print(f"L3 behavior-change:     {'PASS' if l2l3 else 'FAIL'} "
              f"(learned 128 pre-applied at warmup vs {{}} on a cold store)")
        overall = l1 and l2l3
        print(f"OVERALL: {'PASS' if overall else 'FAIL'}")
        return 0 if overall else 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
