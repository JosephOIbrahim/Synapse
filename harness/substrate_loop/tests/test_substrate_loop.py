"""Self-tests for the substrate loop. Pure python, no Ollama, no Houdini.

    python -m pytest harness/substrate_loop/tests -q

A fake worker stands in for the model so each rule can be shown to bite:
keep only on strict gain, frozen paths and forbidden additions rejected before
any gate, red gates discarded and reset, Houdini refused at start and paused or
stopped mid-run, and the original checkout never touched.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import houdini_guard
import loop
import metrics
import workers


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def toy(tmp_path, monkeypatch):
    """A tiny substrate: src/toy.py holds a number; the metric is that number."""
    repo = tmp_path / "toy"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "toy.py").write_text("VALUE = 10\n")
    (repo / "tests" / "test_toy.py").write_text("ok\n")
    (repo / "check.py").write_text(
        "import sys; sys.path.insert(0, 'src'); import toy\n"
        "sys.exit(0 if toy.VALUE >= 0 else 1)\n")
    (repo / "measure.py").write_text(
        "import sys; sys.path.insert(0, 'src'); import toy; print(f'METRIC {toy.VALUE}')\n")
    sh(repo, "git", "init", "-q")
    sh(repo, "git", "-c", "user.name=t", "-c", "user.email=t@t", "add", "-A")
    sh(repo, "git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "init")

    runs = tmp_path / "runs"
    monkeypatch.setattr(loop, "RUNS", runs)
    monkeypatch.setattr(loop, "STOP_FILE", runs / "STOP")
    monkeypatch.setattr(loop, "LOCK_FILE", runs / "ACTIVE.lock")
    monkeypatch.setattr(workers, "unload", lambda model: None)
    monkeypatch.setattr(houdini_guard, "_list_process_names", lambda: ["explorer", "hserver"])

    mission = {
        "id": "toy", "target": "toy", "objective": "make VALUE smaller",
        "focus": ["src/**/*.py"], "direction": "min", "min_delta": 1,
        "metric": {"kind": "command", "cmd": [sys.executable, "measure.py"], "regex": r"METRIC (-?\d+)"},
        "budget": {**loop.DEFAULT_BUDGET, "max_iterations": 3, "no_progress": 10, "houdini_poll_s": 0},
        "on_houdini": "pause", "worker_tier": "worker", "max_files": 3,
        "forbid_added": list(loop.DEFAULT_FORBID),
    }
    target = {"repo": str(repo), "frozen": ["tests/**"],
              "gates": [{"name": "check", "cmd": [sys.executable, "check.py"]}]}
    tiers = {"worker": {"backend": "lean", "model": "fake"}}
    return repo, mission, target, tiers


def script(monkeypatch, replies):
    """Feed the run a fixed list of worker proposals, one per iteration."""
    it = iter(replies)

    def fake(tier, ctx):
        r = next(it)
        if isinstance(r, Exception):
            raise r
        return workers.Proposal(edits=r, why="test edit")
    monkeypatch.setattr(workers, "propose", fake)


def edit(old, new, path="src/toy.py"):
    return [(path, f"VALUE = {old}", f"VALUE = {new}")]


def ledger(run):
    rows = run.ledger.read_text().splitlines()[1:]
    return [r.split("\t")[2] for r in rows]


def test_keeps_only_strict_gains_and_never_touches_the_checkout(toy, monkeypatch):
    repo, m, t, tiers = toy
    script(monkeypatch, [edit(10, 7), edit(7, 7), edit(7, 5)])
    run = loop.Run(m, t, tiers, {})
    reason = run.run()
    run.finish(reason, "DONE")
    assert ledger(run) == ["KEEP", "rejected", "KEEP"]  # 7->7 is no change at all
    assert run.best == 5.0 and run.baseline == 10.0
    assert (repo / "src" / "toy.py").read_text() == "VALUE = 10\n"  # original untouched
    log = sh(run.wt, "git", "log", "--format=%s", f"{run.base}..HEAD").splitlines()
    assert len(log) == 2 and all(s.startswith("substrate-loop(toy)") for s in log)
    assert (run.dir / "DONE").exists() and "iteration cap" in (run.dir / "DONE").read_text()
    assert "## Kept commits" in (run.dir / "REVIEW.md").read_text()


def test_tie_is_not_progress(toy, monkeypatch):
    _, m, t, tiers = toy
    m["min_delta"] = 3
    script(monkeypatch, [edit(10, 9), edit(10, 6), edit(6, 6)])
    run = loop.Run(m, t, tiers, {})
    run.run()
    assert ledger(run)[:2] == ["no_gain", "KEEP"]


def test_frozen_path_rejected_before_any_gate(toy, monkeypatch):
    _, m, t, tiers = toy
    m["focus"] = ["src/**/*.py", "tests/**"]  # even if focus allows it, frozen wins
    script(monkeypatch, [[("tests/test_toy.py", "ok", "ok but weaker")]] * 3)
    run = loop.Run(m, t, tiers, {})
    run.run()
    assert set(ledger(run)) == {"rejected"}
    assert (Path(run.wt) / "tests" / "test_toy.py").read_text() == "ok\n"


def test_forbidden_addition_rejected(toy, monkeypatch):
    _, m, t, tiers = toy
    script(monkeypatch, [[("src/toy.py", "VALUE = 10", "VALUE = 1  # noqa")]] * 3)
    run = loop.Run(m, t, tiers, {})
    run.run()
    assert set(ledger(run)) == {"rejected"}
    assert "noqa" in run.last_failure


def test_red_gate_discards_and_resets_worktree(toy, monkeypatch):
    _, m, t, tiers = toy
    script(monkeypatch, [edit(10, -5), edit(10, -5), edit(10, -5)])
    run = loop.Run(m, t, tiers, {})
    run.run()
    assert set(ledger(run)) == {"discard"}
    assert (Path(run.wt) / "src" / "toy.py").read_text() == "VALUE = 10\n"
    assert "gate 'check' failed" in run.last_failure


def test_worker_errors_stop_the_run(toy, monkeypatch):
    _, m, t, tiers = toy
    m["budget"]["worker_errors"] = 2
    script(monkeypatch, [workers.WorkerError("down")] * 3)
    run = loop.Run(m, t, tiers, {})
    assert "worker errors" in run.run()


def test_houdini_mid_run_stop(toy, monkeypatch):
    _, m, t, tiers = toy
    m["on_houdini"] = "stop"
    seq = iter([["explorer"], ["houdinifx.exe"]])
    monkeypatch.setattr(houdini_guard, "_list_process_names",
                        lambda: [n.lower().removesuffix(".exe") for n in next(seq)])
    script(monkeypatch, [edit(10, 7)])
    run = loop.Run(m, t, tiers, {})
    reason = run.run()
    assert "Houdini running (houdinifx)" in reason and ledger(run) == ["KEEP"]


def test_houdini_mid_run_pause_then_resume(toy, monkeypatch):
    _, m, t, tiers = toy
    unloaded = []
    monkeypatch.setattr(workers, "unload", unloaded.append)
    seq = iter([["explorer"], ["houdini"], ["houdini"], ["explorer"], ["explorer"], ["explorer"]])
    monkeypatch.setattr(houdini_guard, "_list_process_names", lambda: next(seq))
    script(monkeypatch, [edit(10, 7), edit(7, 4), edit(4, 1)])
    run = loop.Run(m, t, tiers, {})
    run.run()
    assert ledger(run) == ["KEEP", "KEEP", "KEEP"] and unloaded == ["fake"]


def test_guard_fails_closed():
    def boom():
        raise OSError("no tasklist")
    assert houdini_guard.check(lister=boom)[0] == houdini_guard.UNKNOWN
    assert houdini_guard.check(lister=lambda: ["hserver", "sesinetd"])[0] == houdini_guard.CLEAR
    assert houdini_guard.check(lister=lambda: ["husk"]) == (houdini_guard.RUNNING, ["husk"])


def test_preflight_refuses_when_houdini_is_up(toy, monkeypatch):
    _, m, t, tiers = toy
    monkeypatch.setattr(houdini_guard, "_list_process_names", lambda: ["hython"])
    monkeypatch.setattr(workers, "ollama_models", lambda: ["fake"])
    problems = loop.doctor(m, t, tiers, {}, quiet=True)
    assert any(p.startswith("Houdini check: running hython") for p in problems)


def test_baseline_red_is_refused(toy, monkeypatch):
    _repo, m, t, tiers = toy
    t["gates"] = [{"name": "always-red", "cmd": [sys.executable, "-c", "raise SystemExit(1)"]}]
    run = loop.Run(m, t, tiers, {})
    with pytest.raises(loop.Refused, match="baseline is red"):
        run.setup()


def test_downstream_must_import_the_candidate(toy, monkeypatch, tmp_path):
    _, m, t, tiers = toy
    elsewhere = tmp_path / "site"
    elsewhere.mkdir()
    (elsewhere / "toy.py").write_text("VALUE = 0\n")
    t.update(import_name="toy", downstream_pythonpath=[str(elsewhere)],
             downstream=[{"name": "noop", "cmd": [sys.executable, "-c", "pass"]}])
    run = loop.Run(m, t, tiers, {})
    with pytest.raises(loop.Refused, match="could not see the change"):
        run.setup()
    t["downstream_pythonpath"] = ["{worktree}/src"]
    run2 = loop.Run(m, t, tiers, {})
    run2.setup()  # resolves inside the worktree: allowed


def test_metrics_helpers():
    assert metrics.improved(10, 9, "min", 1) and not metrics.improved(10, 10, "min", 0)
    assert metrics.improved(1, 2, "max", 1) and not metrics.improved(2, 1, "max", 0)


def test_parse_edits():
    text = ("FILE: src/a.py\n<<<<<<< SEARCH\nx = 1\n=======\nx = 2\n>>>>>>> REPLACE\n"
            "WHY: smaller\n")
    edits, why = workers.parse_edits(text)
    assert edits == [("src/a.py", "x = 1", "x = 2")] and why == "smaller"


def test_shipped_missions_and_tiers_are_valid():
    tiers = json.loads((HERE / "tiers.json").read_text())
    targets = json.loads((HERE / "targets.json").read_text())["targets"]
    for f in (HERE / "missions").glob("[!_]*.json"):
        mission = json.loads(f.read_text())
        assert mission["target"] in targets, f.name
        assert mission.get("worker_tier", "worker") in tiers, f.name
        assert mission["metric"]["kind"] in metrics.KINDS, f.name
