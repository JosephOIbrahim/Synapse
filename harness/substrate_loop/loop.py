"""Substrate loop - Claude conducts, a local model does the iterations.

    python harness/substrate_loop/loop.py doctor --mission salus_lint
    python harness/substrate_loop/loop.py run    --mission salus_lint
    python harness/substrate_loop/loop.py status
    python harness/substrate_loop/loop.py stop

One mission at a time, against one memory-substrate repo (Moneta, SALUS,
Hanish, Octavius, the shim). Each iteration:

    Houdini check -> worker proposes -> scope check -> gates -> downstream
    SYNAPSE tests -> metric -> keep (commit on the loop's branch) or discard

Claude spends tokens twice: planning the mission and reviewing REVIEW.md at the
end. Everything in between runs on the local model.

Never touched: the substrate's own checkout, its main branch, any remote. The
loop works in a git worktree on `substrate-loop/<mission>/<stamp>`; promotion
is Joe's, per commit.

Exit codes: 0 DONE · 1 error · 2 refused at preflight · 3 Houdini running ·
4 another run is live.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import houdini_guard
import metrics
import workers

SYNAPSE_ROOT = HERE.parents[1]
RUNS = HERE / "runs"
STOP_FILE = RUNS / "STOP"
LOCK_FILE = RUNS / "ACTIVE.lock"

DEFAULT_BUDGET = {"max_iterations": 200, "max_hours": 8.0, "no_progress": 30,
                  "worker_errors": 5, "houdini_poll_s": 60}

# Ways to move a number without improving anything. An added line containing one
# of these rejects the candidate before a single gate runs. Missions may extend it.
DEFAULT_FORBID = ["# noqa", "# type: ignore", "pytest.skip", "pytest.mark.skip",
                  "pytest.mark.xfail", "unittest.skip", "pragma: no cover"]


# ---------------------------------------------------------------- small utils

def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(path: Path, data) -> None:
    write_atomic(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def tail(text: str, n: int = 40) -> str:
    return "\n".join(text.strip().splitlines()[-n:])


def substrate_root() -> str:
    # Siblings of the SYNAPSE checkout by default. No user paths in this repo.
    return os.environ.get("SUBSTRATE_ROOT", str(SYNAPSE_ROOT.parent))


def expand(value, wt: str = ""):
    if isinstance(value, list):
        return [expand(v, wt) for v in value]
    if not isinstance(value, str):
        return value
    return (value.replace("${SUBSTRATE_ROOT}", substrate_root())
                 .replace("${SYNAPSE_ROOT}", str(SYNAPSE_ROOT))
                 .replace("{python}", sys.executable)
                 .replace("{worktree}", wt))


def git(repo: str | Path, *args: str, check: bool = True) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout.strip()


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                             capture_output=True, text=True, check=False).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# ---------------------------------------------------------------- config

def load_config(mission_arg: str) -> tuple[dict, dict, dict, dict]:
    mpath = Path(mission_arg)
    if not mpath.suffix:
        mpath = HERE / "missions" / f"{mission_arg}.json"
    elif not mpath.is_absolute() and not mpath.exists():
        mpath = HERE / mission_arg
    mission = load_json(mpath)
    targets = load_json(HERE / "targets.json")
    tiers = load_json(HERE / "tiers.json")
    for key in ("id", "target", "objective", "focus", "metric"):
        if key not in mission:
            raise SystemExit(f"mission {mpath.name} is missing '{key}'")
    if mission["target"] not in targets["targets"]:
        raise SystemExit(f"unknown target {mission['target']!r}; see targets.json")
    target = dict(targets["targets"][mission["target"]])
    target["repo"] = expand(target["repo"])
    mission["budget"] = {**DEFAULT_BUDGET, **mission.get("budget", {})}
    mission.setdefault("direction", mission["metric"].get("direction", "min"))
    mission.setdefault("min_delta", 1e-9)
    mission.setdefault("on_houdini", "pause")
    mission.setdefault("worker_tier", "worker")
    mission.setdefault("max_files", 3)
    mission["forbid_added"] = DEFAULT_FORBID + mission.get("forbid_added", [])
    if "gates" in mission:  # a fix mission targets a red suite, so it names its own gates
        target["gates"] = mission["gates"]
    mission["metric"] = {k: expand(v) for k, v in mission["metric"].items()}
    if mission["on_houdini"] not in ("pause", "stop"):
        raise SystemExit("on_houdini must be 'pause' or 'stop'")
    return mission, target, tiers, targets


# ---------------------------------------------------------------- scope

def _glob_re(glob: str) -> re.Pattern:
    """Git-style globs: `**/` spans zero or more folders, `*` stays inside one."""
    out, i = "", 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out, i = out + "(?:.*/)?", i + 3
        elif glob.startswith("**", i):
            out, i = out + ".*", i + 2
        elif glob[i] == "*":
            out, i = out + "[^/]*", i + 1
        elif glob[i] == "?":
            out, i = out + "[^/]", i + 1
        else:
            out, i = out + re.escape(glob[i]), i + 1
    return re.compile(out + r"\Z")


def _match(path: str, globs: list[str]) -> bool:
    p = path.replace("\\", "/")
    return any(_glob_re(g).match(p) for g in globs)


def scope_violations(paths: list[str], focus: list[str], frozen: list[str]) -> list[str]:
    bad = []
    for p in paths:
        if _match(p, frozen):
            bad.append(f"{p} is frozen")
        elif not _match(p, focus):
            bad.append(f"{p} is outside the mission's focus")
    return bad


def changed_paths(wt: str) -> list[str]:
    out = git(wt, "status", "--porcelain", "--untracked-files=all")
    paths = []
    for line in out.splitlines():
        entry = line[3:]
        paths.append(entry.split(" -> ")[-1].strip('"'))
    return paths


def focus_files(wt: str, focus: list[str], frozen: list[str]) -> list[str]:
    tracked = git(wt, "ls-files").splitlines()
    return [p for p in tracked if _match(p, focus) and not _match(p, frozen)]


def apply_edits(wt: str, edits, focus, frozen) -> tuple[list[str], str]:
    """Apply SEARCH/REPLACE blocks. Returns (touched paths, error or '')."""
    touched = []
    for path, search, replace in edits:
        rel = path.replace("\\", "/").removeprefix("./")
        bad = scope_violations([rel], focus, frozen)
        if bad:
            return touched, "; ".join(bad)
        full = (Path(wt) / rel).resolve()
        if Path(wt).resolve() not in full.parents:
            return touched, f"{rel} escapes the worktree"
        if not full.exists():
            if search.strip():
                return touched, f"{rel} does not exist"
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(replace + "\n", encoding="utf-8")
        else:
            body = full.read_text(encoding="utf-8")
            count = body.count(search)
            if count != 1:
                return touched, f"SEARCH block matched {count} times in {rel} (must be exactly once)"
            full.write_text(body.replace(search, replace, 1), encoding="utf-8")
        touched.append(rel)
    return touched, ""


def forbidden_additions(wt: str, patterns: list[str]) -> list[str]:
    git(wt, "add", "-A")
    added = [ln[1:] for ln in git(wt, "diff", "--cached", "-U0").splitlines()
             if ln.startswith("+") and not ln.startswith("+++")]
    return sorted({p for p in patterns for ln in added if p in ln})


# ---------------------------------------------------------------- gates

def run_cmd(cmd, cwd, env=None, timeout=900) -> tuple[bool, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                           timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s (budgets are fixed; never raise one to pass)"
    except FileNotFoundError as exc:
        return False, f"command not found: {exc}"
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def downstream_env(target: dict, wt: str) -> dict:
    env = dict(os.environ)
    extra = [expand(p, wt) for p in target.get("downstream_pythonpath", [])]
    env["PYTHONPATH"] = os.pathsep.join(extra + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    return env


def check_import_source(target: dict, wt: str) -> str:
    """Law 1: a downstream check must prove it imported the candidate, not an installed copy."""
    name = target.get("import_name")
    if not name or not target.get("downstream"):
        return ""
    ok, out = run_cmd([sys.executable, "-c", f"import {name}; print({name}.__file__)"],
                      cwd=str(SYNAPSE_ROOT), env=downstream_env(target, wt), timeout=60)
    path = out.strip().splitlines()[-1] if out.strip() else ""
    if not ok or not Path(path).resolve().is_relative_to(Path(wt).resolve()):
        return (f"downstream would import {name} from {path or 'nowhere'}, not the candidate "
                f"worktree - the SYNAPSE check could not see the change")
    return ""


def run_gates(target: dict, wt: str) -> tuple[bool, str, str]:
    """Returns (passed, gate name that failed or '', output tail)."""
    for gate in target.get("gates", []):
        ok, out = run_cmd(expand(gate["cmd"], wt), cwd=wt, timeout=int(gate.get("timeout_s", 900)))
        if not ok:
            return False, gate["name"], tail(out)
    if target.get("downstream"):
        why = check_import_source(target, wt)
        if why:
            return False, "downstream-import", why
        env = downstream_env(target, wt)
        for gate in target["downstream"]:
            ok, out = run_cmd(expand(gate["cmd"], wt), cwd=str(SYNAPSE_ROOT), env=env,
                              timeout=int(gate.get("timeout_s", 900)))
            if not ok:
                return False, f"synapse:{gate['name']}", tail(out)
    return True, "", ""


# ---------------------------------------------------------------- lock

def acquire_lock(mission_id: str) -> None:
    RUNS.mkdir(exist_ok=True)
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            held = load_json(LOCK_FILE)
        except Exception:  # noqa: BLE001
            held = {}
        if pid_alive(int(held.get("pid", 0))):
            print(f"another run is live: {held.get('mission')} (pid {held.get('pid')}). "
                  "One mission at a time.")
            sys.exit(4)
        LOCK_FILE.unlink(missing_ok=True)  # holder is dead: safe to take over
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w") as f:
        json.dump({"pid": os.getpid(), "mission": mission_id, "since": now()}, f)


def release_lock() -> None:
    try:
        if load_json(LOCK_FILE).get("pid") == os.getpid():
            LOCK_FILE.unlink()
    except (OSError, ValueError) as exc:
        print(f"could not release {LOCK_FILE.name}: {exc} - the next run reaps it once this pid is dead")


# ---------------------------------------------------------------- preflight

def doctor(mission, target, tiers, targets, quiet=False) -> list[str]:
    """Everything that would make a long run fail at hour three, checked at minute zero."""
    problems = []
    say = (lambda *_: None) if quiet else print
    watch = targets.get("houdini_processes", houdini_guard.DEFAULT_PROCESSES)
    state, detail = houdini_guard.check(watch)
    if state != houdini_guard.CLEAR:
        problems.append(f"Houdini check: {state} {' '.join(detail)} - close Houdini first")
    repo = target["repo"]
    if not (Path(repo) / ".git").exists():
        problems.append(f"target repo not found at {repo} (set SUBSTRATE_ROOT)")
    tier = tiers.get(mission["worker_tier"])
    if not tier:
        problems.append(f"tier {mission['worker_tier']!r} is not in tiers.json")
    else:
        if tier.get("backend") == "lean" or tier.get("provider", "ollama") == "ollama":
            try:
                have = workers.ollama_models()
                if tier["model"] not in have and f"{tier['model']}:latest" not in have:
                    problems.append(f"model {tier['model']} is not pulled - run `ollama pull {tier['model']}`")
            except workers.WorkerError as exc:
                problems.append(str(exc))
        if tier.get("backend") == "claude-code":
            ok, out = run_cmd([tier.get("claude_bin", "claude"), "--version"], cwd=str(HERE), timeout=60)
            if not ok:
                problems.append("`claude` is not on PATH")
            else:
                say(f"claude: {out.strip()}")
    if mission.get("review_each_keep") and "reviewer" not in tiers:
        problems.append("review_each_keep is on but tiers.json has no 'reviewer'")
    if STOP_FILE.exists():
        problems.append(f"{STOP_FILE.name} file is present - delete it to allow a run")
    for p in problems:
        say("PROBLEM:", p)
    if not problems:
        say(f"ok: {mission['id']} -> {mission['target']} ({repo}) with tier {mission['worker_tier']}")
    return problems


# ---------------------------------------------------------------- the loop

class Run:
    def __init__(self, mission, target, tiers, targets):
        self.m, self.t, self.tiers, self.targets = mission, target, tiers, targets
        self.tier = tiers[mission["worker_tier"]]
        self.dir = RUNS / f"{mission['id']}_{stamp()}"
        n = 1
        while self.dir.exists():  # two runs in one second: never share a folder
            n += 1
            self.dir = RUNS / f"{mission['id']}_{stamp()}-{n}"
        self.dir.mkdir(parents=True)
        self.wt = str(self.dir / "wt")
        self.branch = f"substrate-loop/{mission['id']}/{self.dir.name.split('_', 1)[1]}"
        self.ledger = self.dir / "ledger.tsv"
        self.state = {"mission": mission["id"], "target": mission["target"], "status": "STARTING",
                      "branch": self.branch, "started": now(), "iteration": 0, "kept": 0,
                      "discarded": 0, "worker_errors": 0, "paused_s": 0, "claude_cost_usd": 0.0}
        self.deadends: list[str] = []
        self.last_failure = ""
        self.watch = targets.get("houdini_processes", houdini_guard.DEFAULT_PROCESSES)
        write_atomic(RUNS / "LATEST.txt", self.dir.name + "\n")

    # -- bookkeeping
    def beat(self, **kw):
        self.state.update(kw, heartbeat=now())
        write_json(self.dir / "state.json", self.state)

    def log(self, verdict, metric_val, gate, secs, files, why):
        if not self.ledger.exists():
            self.ledger.write_text("iter\tutc\tverdict\tmetric\tbest\tgate\tseconds\tfiles\twhy\n",
                                   encoding="utf-8")
        row = [self.state["iteration"], now(), verdict, metric_val, self.best, gate,
               f"{secs:.0f}", ",".join(files), why.replace("\t", " ").replace("\n", " ")[:200]]
        with self.ledger.open("a", encoding="utf-8") as f:
            f.write("\t".join(str(c) for c in row) + "\n")

    # -- setup
    def setup(self) -> None:
        self.fresh_bytecode()
        repo = self.t["repo"]
        self.base = git(repo, "rev-parse", "HEAD")
        git(repo, "worktree", "add", "-b", self.branch, self.wt, self.base)
        self.beat(status="BASELINE", base=self.base, worktree=self.wt)
        ok, gate, out = run_gates(self.t, self.wt)
        if not ok:
            raise Refused(f"baseline is red at gate {gate} - fix the substrate first, or write a "
                          f"pytest_failed mission that targets it.\n{out}")
        self.best, self.detail = metrics.measure(self.m["metric"], self.wt)
        self.baseline = self.best
        self.beat(status="RUNNING", baseline=self.best, best=self.best)

    # -- stop rules
    def stop_reason(self, t0: float, no_progress: int) -> str:
        b = self.m["budget"]
        if STOP_FILE.exists():
            return "STOP file"
        if self.state["iteration"] >= b["max_iterations"]:
            return f"iteration cap ({b['max_iterations']})"
        if time.time() - t0 >= b["max_hours"] * 3600:
            return f"wall-clock cap ({b['max_hours']}h)"
        if no_progress >= b["no_progress"]:
            return f"no progress in {no_progress} iterations"
        if self.state["worker_errors"] >= b["worker_errors"]:
            return f"{self.state['worker_errors']} worker errors in a row"
        cap = self.m.get("reviewer_budget_usd")
        if cap is not None and self.state["claude_cost_usd"] >= cap:
            return f"Claude spend cap (${cap})"
        return ""

    def houdini_gate(self) -> str:
        """'' to continue, or a stop reason. Pauses in place when told to."""
        state, detail = houdini_guard.check(self.watch)
        if state == houdini_guard.CLEAR:
            return ""
        if self.m["on_houdini"] == "stop":
            return f"Houdini {state} ({' '.join(detail)}) and on_houdini is 'stop'"
        workers.unload(self.tier["model"])  # hand the GPU back to Houdini
        self.beat(status="PAUSED_HOUDINI", paused_because=" ".join(detail))
        print(f"[{now()}] paused: Houdini {state} ({' '.join(detail)}). Resumes when it closes.")
        t0 = time.time()
        while state != houdini_guard.CLEAR:
            if STOP_FILE.exists():
                return "STOP file (while paused for Houdini)"
            time.sleep(self.m["budget"]["houdini_poll_s"])
            state, detail = houdini_guard.check(self.watch)
        self.state["paused_s"] += int(time.time() - t0)
        self.beat(status="RUNNING", paused_because=None)
        print(f"[{now()}] Houdini closed, resuming.")
        return ""

    # -- one iteration
    def context(self) -> dict:
        files = focus_files(self.wt, self.m["focus"], self.t.get("frozen", []))
        hint = self.detail + "\n" + self.last_failure
        files.sort(key=lambda p: -hint.count(p))  # files the evidence names come first
        if files and not any(p in hint for p in files):
            k = self.state["iteration"] % len(files)  # nothing named: rotate through them
            files = files[k:] + files[:k]
        chosen = files[: self.m["max_files"]]
        budget = int(self.tier.get("num_ctx", 32768)) * 2  # ~chars; leaves room for the reply
        bodies = []
        for p in chosen:
            body = (Path(self.wt) / p).read_text(encoding="utf-8", errors="replace")
            if sum(len(b) for _, b in bodies) + len(body) > budget:
                break
            bodies.append((p, body))
        return {"program": (HERE / "program.md").read_text(encoding="utf-8"),
                "objective": self.m["objective"], "metric_name": self.m["metric"]["kind"],
                "metric_value": self.best, "direction": self.m["direction"],
                "metric_detail": tail(self.detail, 30), "last_failure": self.last_failure,
                "deadends": self.deadends[-8:], "files": bodies, "worktree": self.wt,
                "allowed": focus_files(self.wt, self.m["focus"], self.t.get("frozen", []))}

    def discard(self, reason: str, why: str) -> None:
        git(self.wt, "reset", "--hard", "HEAD")
        git(self.wt, "clean", "-fd")
        self.last_failure = reason
        if why:
            self.deadends.append(f"{why} -> {reason.splitlines()[0][:120]}")
        self.state["discarded"] += 1

    def fresh_bytecode(self) -> None:
        """Give every iteration its own bytecode cache.

        Python trusts a .pyc when the source's mtime (whole seconds) and size
        match. An edit landing in the same second with the same length - 7 to 5
        - would be measured against the OLD code. A fresh cache per iteration
        makes that impossible, and keeps __pycache__ out of the worktree.
        """
        cache = self.dir / "pycache"
        shutil.rmtree(cache, ignore_errors=True)
        os.environ["PYTHONPYCACHEPREFIX"] = str(cache / str(self.state["iteration"]))

    def iterate(self) -> bool:
        """One proposal through the gates. True if kept."""
        self.state["iteration"] += 1
        self.fresh_bytecode()
        self.beat()
        t0 = time.time()
        try:
            prop = workers.propose(self.tier, self.context())
        except workers.WorkerError as exc:
            self.state["worker_errors"] += 1
            self.last_failure = f"worker error: {exc}"
            self.log("worker_error", "", "", time.time() - t0, [], str(exc))
            return False
        self.state["worker_errors"] = 0
        if self.tier.get("provider") == "anthropic":  # local tokens are free; only count real spend
            self.state["claude_cost_usd"] += prop.cost_usd

        if prop.edited_in_place:
            touched = changed_paths(self.wt)
            err = "; ".join(scope_violations(touched, self.m["focus"], self.t.get("frozen", [])))
        else:
            touched, err = apply_edits(self.wt, prop.edits, self.m["focus"], self.t.get("frozen", []))
        if not err and not changed_paths(self.wt):
            err = "no change was made" if prop.edited_in_place or prop.edits else "reply had no edit blocks"
        if not err:
            hits = forbidden_additions(self.wt, self.m["forbid_added"])
            if hits:
                err = f"added {', '.join(hits)} - that moves the number without fixing anything"
        if err:
            self.discard(err, prop.why)
            self.log("rejected", "", "scope", time.time() - t0, touched, f"{err} | {prop.why}")
            return False

        ok, gate, out = run_gates(self.t, self.wt)
        if not ok:
            self.discard(f"gate '{gate}' failed:\n{out}", prop.why)
            self.log("discard", "", gate, time.time() - t0, touched, prop.why)
            return False
        try:
            value, detail = metrics.measure(self.m["metric"], self.wt)
        except metrics.MetricUnreadable as exc:
            self.discard(f"metric unreadable: {exc}", prop.why)
            self.log("discard", "", "metric", time.time() - t0, touched, prop.why)
            return False
        if not metrics.improved(self.best, value, self.m["direction"], self.m["min_delta"]):
            self.discard(f"tests passed but {self.m['metric']['kind']} went {self.best} -> {value}; "
                         "only a strict improvement is kept", prop.why)
            self.log("no_gain", value, "", time.time() - t0, touched, prop.why)
            return False

        if self.m.get("review_each_keep"):
            git(self.wt, "add", "-A")
            diff = git(self.wt, "diff", "--cached")
            try:
                keep, reason, cost = workers.review(self.tiers["reviewer"], self.m["objective"], diff)
                self.state["claude_cost_usd"] += cost
            except workers.WorkerError as exc:
                keep, reason = False, f"review unavailable ({exc}); held back, not kept"
            if not keep:
                self.discard(f"reviewer rejected it: {reason}", prop.why)
                self.log("review_reject", value, "reviewer", time.time() - t0, touched, reason)
                return False

        git(self.wt, "add", "-A")
        msg = (f"substrate-loop({self.m['id']}): it{self.state['iteration']} "
               f"{self.m['metric']['kind']} {self.best} -> {value}\n\n{prop.why or '(no reason given)'}\n\n"
               f"worker: {self.tier.get('backend')}/{self.tier['model']}")
        git(self.wt, "-c", "user.name=substrate-loop", "-c", "user.email=substrate-loop@localhost",
            "commit", "-q", "-m", msg)
        self.log("KEEP", value, "", time.time() - t0, touched, prop.why)
        self.best, self.detail, self.last_failure = value, detail, ""
        self.state["kept"] += 1
        self.beat(best=value)
        return True

    # -- the whole run
    def run(self) -> str:
        self.setup()
        t0, no_progress = time.time(), 0
        while True:
            reason = self.stop_reason(t0, no_progress) or self.houdini_gate()
            if reason:
                return reason
            no_progress = 0 if self.iterate() else no_progress + 1
            self.beat(no_progress=no_progress)

    def finish(self, reason: str, status: str) -> None:
        workers.unload(self.tier["model"])
        kept_log = ""
        if getattr(self, "base", None) and Path(self.wt).exists():
            kept_log = git(self.wt, "log", "--stat", "--format=%n### %s%n%b", f"{self.base}..HEAD",
                           check=False)
        tally: dict[str, int] = {}
        if self.ledger.exists():
            for line in self.ledger.read_text(encoding="utf-8").splitlines()[1:]:
                v = line.split("\t")[2]
                tally[v] = tally.get(v, 0) + 1
        s = self.state
        review = "\n".join([
            f"# Review packet: {self.m['id']}", "",
            f"Stopped because: {reason}.", "",
            (f"Target {self.m['target']} at base `{getattr(self, 'base', '?')}`. "
            f"Branch `{self.branch}`, worktree `{self.wt}`."), "",
            (f"{self.m['metric']['kind']}: {getattr(self, 'baseline', '?')} -> {getattr(self, 'best', '?')} "
            f"({self.m['direction']} is better) over {s['iteration']} iterations, "
            f"{s['kept']} kept, {s['discarded']} discarded, {s['paused_s'] // 60} min paused for Houdini, "
            f"${s['claude_cost_usd']:.2f} Claude spend."), "",
            "Outcomes: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())), "",
            "## For the reviewer", "",
            ("Every commit below passed every gate and moved the metric. That makes it a candidate, "
            "not an improvement. Read each diff for metric gaming (silenced warnings, deleted "
            "behaviour, special-cased inputs) before anything is cherry-picked. Nothing here is merged."),
            "", "## Kept commits", "", kept_log or "(none)", "",
        ])
        write_atomic(self.dir / "REVIEW.md", review)
        self.beat(status=status, stop_reason=reason, finished=now())
        write_atomic(self.dir / status, reason + "\n")  # sentinel written LAST


class Refused(RuntimeError):
    pass


# ---------------------------------------------------------------- cli

def cmd_status() -> int:
    latest = RUNS / "LATEST.txt"
    if not latest.exists():
        print("no runs yet")
        return 0
    d = RUNS / latest.read_text().strip()
    s = load_json(d / "state.json") if (d / "state.json").exists() else {}
    print(f"{d.name}: {s.get('status')} · it {s.get('iteration')} · kept {s.get('kept')} · "
          f"best {s.get('best')} (from {s.get('baseline')}) · heartbeat {s.get('heartbeat')}")
    if s.get("stop_reason"):
        print("stopped:", s["stop_reason"])
    if (d / "ledger.tsv").exists():
        print(tail((d / "ledger.tsv").read_text(encoding="utf-8"), 6))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("command", choices=["doctor", "run", "status", "stop"])
    ap.add_argument("--mission", help="name in missions/ or a path to a mission .json")
    a = ap.parse_args(argv)

    if a.command == "status":
        return cmd_status()
    if a.command == "stop":
        RUNS.mkdir(exist_ok=True)
        STOP_FILE.write_text(now() + "\n")
        print("STOP written; the run ends after its current iteration. Delete it before the next run.")
        return 0
    if not a.mission:
        ap.error("--mission is required")
    mission, target, tiers, targets = load_config(a.mission)

    if a.command == "doctor":
        return 2 if doctor(mission, target, tiers, targets) else 0

    problems = doctor(mission, target, tiers, targets, quiet=True)
    if problems:
        for p in problems:
            print("REFUSED:", p)
        return 3 if any(p.startswith("Houdini") for p in problems) else 2
    acquire_lock(mission["id"])
    run = None
    try:
        run = Run(mission, target, tiers, targets)
        print(f"[{now()}] {mission['id']}: worktree {run.wt}, branch {run.branch}")
        reason = run.run()
        run.finish(reason, "DONE")
        print(f"[{now()}] DONE: {reason}. Review: {run.dir / 'REVIEW.md'}")
        return 0
    except Refused as exc:
        if run:
            run.finish(str(exc).splitlines()[0], "FAILED")
        print("REFUSED:", exc)
        return 2
    except KeyboardInterrupt:
        if run:
            run.finish("interrupted (Ctrl+C)", "DONE")
        return 0
    except Exception as exc:
        if run:
            run.finish(f"{type(exc).__name__}: {exc}", "FAILED")
        raise
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
