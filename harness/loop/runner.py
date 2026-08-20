#!/usr/bin/env python
"""LOOP runner - executes a probe mission against the loop seam, unattended.

Cloned verbatim from harness/autoresearch/runner.py, with ONE structural
adaptation: the hou requirement is gated behind the mission's `needs_hou`
flag (default false). V0.0 is pure-python - the seam is python/synapse/loop/,
no hython, no hou. A later rung (V0.1+, SafetyPort) may set needs_hou: true.

The model authors questions (mission files). Only probes produce answers.
This process runs DETACHED. Never trust the call, trust the artifact.

Contract (every write is atomic - tmp file + os.replace):
    state.json                 heartbeat {mission, phase, question, done, total, pct, ts, pid}
    <artifact_prefix>_<build>.json  evidence, atomically rewritten after every question
    DONE | FAILED              sentinel, written LAST. FAILED carries the traceback.

Usage:
    python runner.py --mission missions/loop_v00_recipe.json --out runs/<stamp>
    python runner.py --mission missions/loop_v00_recipe.json --validate-only
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Sibling imports regardless of launch cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mission_schema import Mission, MissionError, load_mission  # noqa: E402

RUNNER_VERSION = "1.0.0"


# ---------------------------------------------------------------- utilities

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{utc_now()}] {msg}", flush=True)


def atomic_write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_json(path: Path, obj) -> None:
    atomic_write(path, json.dumps(obj, indent=2))


# ---------------------------------------------------------------- run state

class Run:
    """One mission execution: heartbeat + incremental evidence + sentinel."""

    def __init__(self, mission: Mission, out_dir: Path):
        self.mission = mission
        self.out = out_dir
        self.total = mission.total_questions()
        self.done = 0
        self.entries: list = []
        self.evidence_path = None  # named once build is known
        self.meta: dict = {
            "mission": mission.name,
            "mission_version": mission.version,
            "target_build": mission.target_build,
            "needs_hou": mission.needs_hou,
            "build": None,
            "target_build_match": None,
            "runner_version": RUNNER_VERSION,
            "seam_version": None,
            "python": sys.version.split()[0],
            "started": utc_now(),
            "finished": None,
        }

    # -- heartbeat ----------------------------------------------------------
    def heartbeat(self, phase_id: str, question_label: str) -> None:
        pct = 0 if self.total == 0 else round(100 * self.done / self.total)
        atomic_write_json(self.out / "state.json", {
            "mission": self.mission.name,
            "phase": phase_id,
            "question": question_label,
            "done": self.done,
            "total": self.total,
            "pct": pct,
            "ts": utc_now(),
            "pid": os.getpid(),
        })

    # -- evidence -----------------------------------------------------------
    def bind_build(self, build: str, seam_version: str) -> None:
        self.meta["build"] = build
        self.meta["target_build_match"] = (build == self.mission.target_build)
        self.meta["seam_version"] = seam_version
        # Evidence filename follows the mission's artifact_prefix.
        self.meta["artifact_prefix"] = self.mission.artifact_prefix
        self.evidence_path = self.out / f"{self.mission.artifact_prefix}_{build}.json"
        if not self.meta["target_build_match"]:
            log(f"WARNING: probed build {build} != mission target "
                f"{self.mission.target_build} - evidence is true to the probed build")

    def record(self, claim: str, value, probe: str, note: str = "") -> None:
        entry = {
            "claim": claim,
            "value": value,
            "probe": probe,
            "build": self.meta["build"],
            "ts": utc_now(),
        }
        if note:
            entry["note"] = note
        self.entries.append(entry)
        self.done += 1
        self._flush()

    def _flush(self) -> None:
        if self.evidence_path is None:
            return
        atomic_write_json(self.evidence_path,
                          {"meta": self.meta, "entries": self.entries})

    def failures(self) -> int:
        return sum(1 for e in self.entries
                   if isinstance(e["value"], dict) and "error" in e["value"])

    def finish(self) -> None:
        self.meta["finished"] = utc_now()
        self._flush()
        atomic_write_json(self.out / "DONE", {
            "finished": self.meta["finished"],
            "entries": len(self.entries),
            "failures": self.failures(),
            "evidence": self.evidence_path.name if self.evidence_path else None,
        })


# ---------------------------------------------------------------- execution

def question_label(kind: str, q: dict) -> str:
    if kind == "port_contract":
        return f"port_contract:{q['port']}"
    if kind == "mapper_green":
        return f"mapper_green:{q['name']}"
    if kind == "precommit_order":
        return f"precommit_order:{q['turns']}turns"
    if kind == "stageport_cow":
        return f"stageport_cow:{q['stage_identifier']}"
    if kind == "closure_rate":
        return f"closure_rate:{q['turns']}turns"
    return kind


def execute_question(kind: str, q: dict, probes, run: Run) -> None:
    """Dispatch one question to its probe. Probe exceptions become evidence,
    not crashes - a missing seam is an answer, not a failure."""
    note = q.get("note", "")
    try:
        if kind == "port_contract":
            value = probes.probe_port_contract(q["port"], q["methods"])
            run.record(f"port_contract:{q['port']}", value, kind, note)

        elif kind == "mapper_green":
            value = probes.probe_mapper_green(q["name"])
            run.record(f"mapper_green:{q['name']}", value, kind, note)

        elif kind == "precommit_order":
            value = probes.probe_precommit_order(q["turns"])
            run.record(f"precommit_order:{q['turns']}turns", value, kind, note)

        elif kind == "stageport_cow":
            value = probes.probe_stageport_cow(q["stage_identifier"])
            run.record(f"stageport_cow:{q['stage_identifier']}", value, kind, note)

        elif kind == "closure_rate":
            value = probes.probe_closure_rate(q["turns"])
            run.record(f"closure_rate:{q['turns']}turns", value, kind, note)

        else:  # unreachable post-validation; recorded, not raised
            run.record(f"unknown_kind:{kind}", {"error": "unknown question kind"}, kind)

    except Exception:
        run.record(question_label(kind, q),
                   {"error": traceback.format_exc(limit=8)}, kind, note)


def run_mission(mission: Mission, out_dir: Path) -> Run:
    run = Run(mission, out_dir)
    run.heartbeat("boot", "importing probes")

    import probes  # deferred: only the execute path needs the seam
    if mission.needs_hou:
        probes.require_hou()  # V0.0 is pure-python; a needs_hou rung enforces hython

    run.bind_build(probes.get_build(), probes.seam_version())
    log(f"mission '{mission.name}' v{mission.version} | build {run.meta['build']} "
        f"| seam {run.meta['seam_version']} | {run.total} questions")

    for phase in mission.phases:
        log(f"phase {phase.id} ({phase.kind}) - {len(phase.questions)} questions")
        for q in phase.questions:
            label = question_label(phase.kind, q)
            run.heartbeat(phase.id, label)
            execute_question(phase.kind, q, probes, run)
        run.heartbeat(phase.id, "phase complete")

    run.finish()
    log(f"DONE - {len(run.entries)} entries, {run.failures()} probe failures")
    return run


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="LOOP mission runner")
    ap.add_argument("--mission", required=True, help="path to mission JSON")
    ap.add_argument("--out", help="run output directory (required unless --validate-only)")
    ap.add_argument("--validate-only", action="store_true",
                    help="validate mission schema and print the plan; no seam needed")
    args = ap.parse_args(argv)

    try:
        mission = load_mission(Path(args.mission))
    except MissionError as e:
        print(f"MISSION INVALID: {e}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"mission        {mission.name} v{mission.version}")
        print(f"target build   {mission.target_build}")
        print(f"needs_hou      {mission.needs_hou}")
        print(f"questions      {mission.total_questions()}")
        for p in mission.phases:
            print(f"  {p.id:<14} {p.kind:<16} x{len(p.questions)}")
        print("VALID")
        return 0

    if not args.out:
        print("--out is required for execution", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_mission(mission, out_dir)
        return 0
    except Exception:
        tb = traceback.format_exc()
        log("FAILED")
        atomic_write(out_dir / "FAILED", f"{utc_now()}\n\n{tb}")
        print(tb, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
