#!/usr/bin/env python
"""AUTORESEARCH runner — executes a probe mission inside hython, unattended.

The model authors questions (mission files). Only probes produce answers.
This process runs DETACHED. Desktop Commander never waits on it — DC fires
the launch via drive_autoresearch.ps1 and returns in milliseconds; Claude
polls the artifacts below with cheap reads. Never trust the call, trust
the artifact.

Contract (every write is atomic — tmp file + os.replace):
    state.json                 heartbeat {mission, phase, question, done, total, pct, ts, pid}
    lop_truth_<build>.json     evidence, atomically rewritten after every question
    DONE | FAILED              sentinel, written LAST. FAILED carries the traceback.

Usage:
    hython  runner.py --mission missions/solaris_basic.json --out runs/<stamp>
    python  runner.py --mission missions/solaris_basic.json --validate-only
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
            "build": None,
            "target_build_match": None,
            "runner_version": RUNNER_VERSION,
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
    def bind_build(self, build: str, canonicalizer: str) -> None:
        self.meta["build"] = build
        self.meta["target_build_match"] = (build == self.mission.target_build)
        self.meta["canonicalizer"] = canonicalizer
        self.evidence_path = self.out / f"lop_truth_{build}.json"
        if not self.meta["target_build_match"]:
            log(f"WARNING: probed build {build} != mission target "
                f"{self.mission.target_build} — evidence is true to the probed build")

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
    if kind == "type_discovery":
        return f"discover:{q['pattern']}"
    if kind == "type_existence":
        return f"exists:{q['name']}"
    if kind == "parm_probe":
        return f"parms:{q['type']}"
    if kind == "chain_hash":
        return f"chain:{q['name']}"
    if kind == "fixture_hash":
        return f"fixture:{q['name']}"
    return kind


def execute_question(kind: str, q: dict, probes, run: Run) -> None:
    """Dispatch one question to its probe. Probe exceptions become evidence,
    not crashes — a dead literal is an answer, not a failure."""
    note = q.get("note", "")
    try:
        if kind == "type_discovery":
            value = probes.probe_type_discovery(q["pattern"])
            run.record(f"lop_type_discovery:{q['pattern']}", value, kind, note)

        elif kind == "type_existence":
            value = probes.probe_type_existence(q["name"])
            run.record(f"lop_type_exists:{q['name']}", value, kind, note)

        elif kind == "parm_probe":
            tname = q["type"]
            if q["skip_if_missing"] and not probes.probe_type_existence(tname)["exists"]:
                run.record(f"lop_type_parms:{tname}",
                           {"skipped": True, "reason": "type does not exist in this build"},
                           kind, note)
                return
            value = probes.probe_parms(tname, q["highlight"])
            run.record(f"lop_type_parms:{tname}", value, kind, note)

        elif kind == "chain_hash":
            value = probes.probe_chain_hash(q["chain"], q["name"], q["repeat"])
            value["candidate"] = q["candidate"]
            run.record(f"chain_stage_hash:{q['name']}", value, kind, note)

        elif kind == "fixture_hash":
            value = probes.probe_fixture_hash(q["path"], q["name"], q["repeat"])
            run.record(f"fixture_stage_hash:{q['name']}", value, kind, note)

        else:  # unreachable post-validation; recorded, not raised
            run.record(f"unknown_kind:{kind}", {"error": "unknown question kind"}, kind)

    except Exception:
        run.record(question_label(kind, q),
                   {"error": traceback.format_exc(limit=8)}, kind, note)


def run_mission(mission: Mission, out_dir: Path) -> Run:
    run = Run(mission, out_dir)
    run.heartbeat("boot", "importing probes")

    import probes  # deferred: only the execute path needs hou
    probes.require_hou()

    run.bind_build(probes.get_build(), probes.CANONICALIZER_VERSION)
    log(f"mission '{mission.name}' v{mission.version} | build {run.meta['build']} "
        f"| {run.total} questions")

    for phase in mission.phases:
        log(f"phase {phase.id} ({phase.kind}) — {len(phase.questions)} questions")
        for q in phase.questions:
            label = question_label(phase.kind, q)
            run.heartbeat(phase.id, label)
            execute_question(phase.kind, q, probes, run)
        run.heartbeat(phase.id, "phase complete")

    run.finish()
    log(f"DONE — {len(run.entries)} entries, {run.failures()} probe failures")
    return run


# ---------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="AUTORESEARCH mission runner")
    ap.add_argument("--mission", required=True, help="path to mission JSON")
    ap.add_argument("--out", help="run output directory (required unless --validate-only)")
    ap.add_argument("--validate-only", action="store_true",
                    help="validate mission schema and print the plan; no hou needed")
    args = ap.parse_args(argv)

    try:
        mission = load_mission(Path(args.mission))
    except MissionError as e:
        print(f"MISSION INVALID: {e}", file=sys.stderr)
        return 2

    if args.validate_only:
        print(f"mission        {mission.name} v{mission.version}")
        print(f"target build   {mission.target_build}")
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
