#!/usr/bin/env python
"""Outside-in benchmark runner (T1 / T2 / T5).

Drives each arm on the same prompt text and the same scene, then verifies each arm's
SAVED scene in a THIRD hython that is neither arm's process (verify.py). Records, per run,
the numbers that come from the provider response -- input/output tokens, tool calls,
wall-clock -- plus the verify.py verdict (PASS / FAIL / UNKNOWN) and, for SYNAPSE, its
ledger row count. Over runs it reports MEDIAN and RANGE, never the best (T2).

WHY a not-pass happened is classified AFTER the verdict, here in the runner, by the JEV-BENCH
guard -- so verify.py never reads an arm's text and its verdict stays independent (acceptance 4).

Safety:
  * --scene large refuses without --confirm-spend and prints an estimate from the recorded
    per-turn median (acceptance 5).
  * arms are pinned to distinct ports (SYNAPSE 9999, fxhoudinimcp 8100) and distinct scene
    copies; the runner asserts distinctness (crucible: never share a port/process/scene).
  * an unreachable arm is recorded UNKNOWN with a reason -- never a fabricated token count.

Producer for the plumbing proof (this leg):
    python harness/outside_in/run.py --scene empty --runs 1 --limit 1
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "harness" / "jev"))

OUTDIR = REPO / "harness" / "notes" / "outside_in"
RESULTS = OUTDIR / "results.jsonl"
LEDGER = OUTDIR / "LEDGER.md"
STATS = OUTDIR / "turn_stats.json"
PROMPTS = HERE / "prompts.jsonl"
VERIFY = HERE / "verify.py"

DEFAULT_MODEL = "claude-sonnet-5"   # pinned identically on both arms; recorded in every row
HYTHON = os.environ.get("SYNAPSE_HYTHON",
                        r"C:\Program Files\Side Effects Software\Houdini 22.0.400\bin\hython.exe")

# Scene sources. empty -> the arm makes a fresh hip. demo/large -> a source hip copied per arm.
SCENE_SOURCES = {
    "empty": None,
    "demo": os.environ.get("BENCH_DEMO_SCENE", ""),    # 5,764-node demo (path provided at run time)
    "large": os.environ.get("BENCH_LARGE_SCENE", ""),  # 25,850-node ladder rung
}


# --------------------------------------------------------------------------- #
def load_prompts(limit: int | None) -> list[dict]:
    rows = [json.loads(l) for l in PROMPTS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def median_range(values: list[float]):
    vals = [v for v in values if isinstance(v, (int, float))]
    if not vals:
        return None, None, None
    return statistics.median(vals), min(vals), max(vals)


def read_stats() -> dict:
    if STATS.exists():
        try:
            return json.loads(STATS.read_text(encoding="utf-8"))
        except ValueError:
            pass
    return {"per_turn_tokens": [], "per_turn_wall_s": []}


def record_turn(tokens: int | None, wall_s: float | None):
    st = read_stats()
    if isinstance(tokens, int):
        st["per_turn_tokens"].append(tokens)
    if isinstance(wall_s, (int, float)):
        st["per_turn_wall_s"].append(round(wall_s, 3))
    st["token_median"] = statistics.median(st["per_turn_tokens"]) if st["per_turn_tokens"] else None
    OUTDIR.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(st, indent=2), encoding="utf-8")


def per_turn_token_median() -> float | None:
    st = read_stats()
    return statistics.median(st["per_turn_tokens"]) if st.get("per_turn_tokens") else None


def spend_gate(scene: str, runs: int, n_arms: int, n_prompts: int, confirm: bool) -> int | None:
    """Return an exit code if the run must be refused, else None. Prints an estimate either way."""
    if scene != "large" or confirm:
        return None
    turns = n_prompts * runs * n_arms
    med = per_turn_token_median()
    if med is None:
        print(f"REFUSED: --scene large is real money and needs --confirm-spend.\n"
              f"  estimate: {turns} agent turns (= {n_prompts} prompts x {runs} runs x {n_arms} arms);\n"
              f"  per-turn token median: UNKNOWN (no run recorded in {STATS.name} yet) -- "
              f"run --scene empty first to record one.")
    else:
        print(f"REFUSED: --scene large is real money and needs --confirm-spend.\n"
              f"  estimate: {turns} agent turns x {med:.0f} tok/turn (recorded median) "
              f"= ~{turns * med:,.0f} provider tokens.\n"
              f"  median source: {STATS} (producer: prior --scene empty runs).")
    return 2


def verify_scene(scene_path: str, check: dict) -> dict:
    """Run verify.py in a THIRD hython (neither arm's process). Passes only scene + check."""
    if not Path(scene_path).exists():
        return {"verdict": "UNKNOWN", "reason": f"no saved scene at {scene_path}", "checks": []}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(check, f)
        checkfile = f.name
    try:
        out = subprocess.run([HYTHON, str(VERIFY), "--scene", scene_path, "--check", "@" + checkfile],
                             capture_output=True, text=True, timeout=300)
    except Exception as e:  # noqa: BLE001
        return {"verdict": "UNKNOWN", "reason": f"verify hython failed: {type(e).__name__}: {e}", "checks": []}
    finally:
        try:
            os.unlink(checkfile)
        except OSError:
            pass
    for line in reversed(out.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{") and '"verdict"' in line:
            try:
                return json.loads(line)
            except ValueError:
                continue
    return {"verdict": "UNKNOWN", "reason": "verify.py produced no verdict line",
            "stderr_tail": out.stderr[-300:], "checks": []}


def classify_notpass(prompt: dict, res: dict, verdict: dict, leg: str) -> dict | None:
    """On not-pass only, label WHY via JEV-BENCH. Uses arm text -- but AFTER the independent
    verdict, and never inside verify.py."""
    try:
        import jev_bench
    except Exception as e:  # noqa: BLE001
        return {"kind": "unjudged", "verdict": "FAIL", "reason": f"jev_bench import failed: {e}"}
    summary = "; ".join(f"{c.get('kind')}:{c.get('type', c.get('name'))}={'ok' if c.get('ok') else 'FAIL'}"
                        for c in verdict.get("checks", []))
    return jev_bench.classify_leg(prompt["prompt"], res.get("final_text", ""), res.get("tool_names", []),
                                  summary, wave="bp10", leg=leg)


def run_cell(arm, prompt: dict, *, runs: int, model: str, client, workdir: Path) -> dict:
    """One (arm, prompt) cell over N runs. Returns an aggregated ledger row."""
    per_run = []
    ok, reason = arm.available()
    for r in range(runs):
        leg = f"{arm.name}:{prompt['id']}:run{r}"
        if not ok:
            per_run.append({"run": r, "status": "UNKNOWN", "reason": reason})
            continue
        res = arm.run(client=client, prompt=prompt["prompt"], model=model)
        if res.get("error"):
            per_run.append({"run": r, "status": "UNKNOWN", "reason": res["error"],
                            "input_tokens": res.get("input_tokens"), "output_tokens": res.get("output_tokens"),
                            "tool_calls": res.get("tool_calls"), "wall_s": res.get("wall_s")})
            continue
        saved_ok, saved = arm.save_scene()
        scene_path = str(workdir / f"{arm.name}__{prompt['id']}__run{r}.hip")
        if saved_ok and Path(saved).exists():
            scene_path = saved
        verdict = verify_scene(scene_path, prompt["check"]) if saved_ok else \
            {"verdict": "UNKNOWN", "reason": f"arm could not save scene: {saved}", "checks": []}
        jev = None
        if verdict["verdict"] != "PASS":
            jev = classify_notpass(prompt, res, verdict, leg)
        record_turn(int((res.get("input_tokens") or 0) + (res.get("output_tokens") or 0)) or None,
                    res.get("wall_s"))
        per_run.append({"run": r, "status": verdict["verdict"],
                        "input_tokens": res.get("input_tokens"), "output_tokens": res.get("output_tokens"),
                        "tool_calls": res.get("tool_calls"), "wall_s": res.get("wall_s"),
                        "last_tools": res.get("last_tools"), "jev_kind": (jev or {}).get("kind"),
                        "reason": verdict.get("reason")})
    arm.close()

    def col(key):
        return median_range([r.get(key) for r in per_run if isinstance(r.get(key), (int, float))])
    itok = col("input_tokens"); otok = col("output_tokens"); tc = col("tool_calls"); wall = col("wall_s")
    verdicts = [r["status"] for r in per_run]
    return {"arm": arm.name, "prompt": prompt["id"], "domain": prompt["domain"], "runs": runs,
            "model": model, "input_tokens_median": itok[0], "input_tokens_range": [itok[1], itok[2]],
            "output_tokens_median": otok[0], "output_tokens_range": [otok[1], otok[2]],
            "tool_calls_median": tc[0], "wall_s_median": wall[0], "wall_s_range": [wall[1], wall[2]],
            "verdicts": verdicts, "unknown_count": verdicts.count("UNKNOWN"),
            "ledger_rows": None,  # SYNAPSE ledger row count: wired at live-run via synapse_metrics
            "jev_kinds": [r.get("jev_kind") for r in per_run if r.get("jev_kind")],
            "per_run": per_run}


def append_results(rows: list[dict]):
    OUTDIR.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}, ensure_ascii=False) + "\n")


def build_arms(names: list[str], scene_id: str, workdir: Path, allow_foreign: bool):
    from arms.synapse import SynapseArm
    from arms.fxhoudinimcp import FxArm
    made = []
    scenes = set()
    for n in names:
        scene = str(workdir / f"{n}__{scene_id}.hip")
        assert scene not in scenes, "isolation violation: two arms share a scene file"
        scenes.add(scene)
        if n == "synapse":
            made.append(SynapseArm(scene, allow_foreign=allow_foreign))
        elif n == "fxhoudinimcp":
            made.append(FxArm(scene, venv_dir=str(workdir / "fx_venv"), packages_dir=str(workdir / "fx_pkgs")))
        else:
            raise SystemExit(f"unknown arm {n!r}")
    ports = [a.port for a in made]
    assert len(ports) == len(set(ports)), "isolation violation: two arms share a port"
    return made


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scene", choices=list(SCENE_SOURCES), default="empty")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=None, help="run only the first K prompts")
    ap.add_argument("--arms", default="synapse,fxhoudinimcp")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--allow-foreign", action="store_true",
                    help="let the SYNAPSE arm use a server it did not start (unsafe near a live session)")
    args = ap.parse_args(argv)

    arm_names = [a.strip() for a in args.arms.split(",") if a.strip()]
    prompts = load_prompts(args.limit)

    gate = spend_gate(args.scene, args.runs, len(arm_names), len(prompts), args.confirm_spend)
    if gate is not None:
        return gate

    from arms._agent import anthropic_client
    client, creason = anthropic_client(REPO)
    if client is None:
        print(f"[note] provider client unavailable ({creason}); reachable arms will record UNKNOWN, not fabricate tokens.")

    workdir = Path(tempfile.mkdtemp(prefix="oi_bench_"))
    print(f"[isolation] scene copies + arm venvs under {workdir} (never committed)")
    arms = build_arms(arm_names, args.scene, workdir, args.allow_foreign)

    rows = []
    for prompt in prompts:
        for arm in arms:
            row = run_cell(arm, prompt, runs=args.runs, model=args.model, client=client, workdir=workdir)
            rows.append(row)
            v = row["verdicts"]
            print(f"  {row['arm']:12} {row['prompt']:9} verdict={v} "
                  f"in_tok={row['input_tokens_median']} out_tok={row['output_tokens_median']} "
                  f"tools={row['tool_calls_median']} wall={row['wall_s_median']}")
    append_results(rows)
    write_ledger(args, rows)
    print(f"-- appended {len(rows)} row(s) to {RESULTS.relative_to(REPO)}")
    print(f"-- ledger: {LEDGER.relative_to(REPO)}")
    return 0


def write_ledger(args, rows: list[dict]):
    """Regenerate LEDGER.md from results.jsonl with the producer command beside the table."""
    import ledger_render  # local module keeps this file focused
    ledger_render.render(REPO, OUTDIR, RESULTS, LEDGER, DEFAULT_MODEL)


if __name__ == "__main__":
    sys.exit(main())
