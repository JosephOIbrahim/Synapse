#!/usr/bin/env python
"""rope runner -- deterministic orchestrator (Mode 1).

Methodology after karpathy/autoresearch (fetched 2026-08-03): fresh agent per
task, fixed budget, mechanical verdict, keep-or-discard via git, TSV ledger,
and the loop never pauses to ask. Orchestrator + verifier are plain Python
(zero tokens); the only model spend is one headless `claude -p` per task.

Usage:
  python harness/rope/runner.py status
  python harness/rope/runner.py run --model <id> --confirm-model [--max N] [--task ID] [--allow-dirty]
  python harness/rope/runner.py human <ID> --done "note"
  python harness/rope/runner.py verify <ID> --passed | --failed "why"
  python harness/rope/runner.py gate

Safety: on a failed attempt this runner does `git reset --hard` ONLY. It never
runs `git clean` -- this seat has untracked working files that must survive.
"""
import argparse, json, os, re, shutil, subprocess, sys, time

ROPE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(ROPE))
STATE_P = os.path.join(ROPE, "STATE.json")
RESULTS = os.path.join(ROPE, "results.tsv")
PROMPT_P = os.path.join(ROPE, ".prompt.txt")
RUNLOG = os.path.join(ROPE, "last_run.log")
TIMEOUT = {"trivial": 480, "small": 1200, "medium": 2400}
EXTRA_FLAGS = os.environ.get("SYNAPSE_ROPE_FLAGS", "--permission-mode acceptEdits").split()


def sh(args, timeout=None, stdin=None, stdout=None):
    return subprocess.run(args, cwd=ROOT, timeout=timeout, stdin=stdin,
                          stdout=stdout or subprocess.PIPE,
                          stderr=subprocess.STDOUT, text=(stdout is None))

def git(*a, timeout=120):
    return sh(["git", *a], timeout=timeout)

def claude_cmd(model):
    base = ["claude", "-p", "--model", model] + EXTRA_FLAGS
    return (["cmd", "/c"] + base) if os.name == "nt" else base

def load():
    with open(STATE_P, encoding="utf-8") as f:
        return json.load(f)

def save(st):
    with open(STATE_P, "w", encoding="utf-8") as f:
        json.dump(st, f, indent=1)

def ledger(tid, model, verdict, attempts, dur, note):
    new = not os.path.exists(RESULTS)
    with open(RESULTS, "a", encoding="utf-8") as f:
        if new:
            f.write("ts\ttask\tmodel\tverdict\tattempts\tdur_s\ttokens\tnote\n")
        f.write("%s\t%s\t%s\t%s\t%d\t%.0f\t%s\t%s\n" % (
            time.strftime("%Y-%m-%d %H:%M"), tid, model, verdict, attempts,
            dur, "unavailable", note.replace("\t", " ").replace("\n", " ")[:200]))

def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8", errors="replace") as f:
        return f.read()

def _porcelain():
    return git("status", "--porcelain").stdout.strip().splitlines()

def check(a):
    """Return (passed: bool|None, manual_note). None = manual, not runnable."""
    k = a["kind"]
    try:
        if k == "grep_min":
            return _read(a["path"]).count(a["pattern"]) >= a.get("min", 1), ""
        if k == "grep_absent":
            return _read(a["path"]).count(a["pattern"]) == 0, ""
        if k == "grep_top":
            head = "\n".join(_read(a["path"]).splitlines()[: a.get("lines", 30)])
            return a["pattern"] in head, ""
        if k == "order":
            s = _read(a["path"])
            i, j = s.find(a["first"]), s.find(a["second"])
            return i != -1 and j != -1 and i < j, ""
        if k == "exists":
            return os.path.exists(os.path.join(ROOT, a["path"])), ""
        if k == "desc_len":
            m = re.search(r'description\s*=\s*"(.*?)"', _read(a["path"]), re.S)
            return bool(m) and len(m.group(1)) <= a["max"], ""
    except FileNotFoundError:
        return False, ""
    if k == "pytest":
        r = sh([sys.executable, "-m", "pytest"] + a["args"].split(), timeout=1800)
        return r.returncode == 0, ""
    if k == "clean_after_pytest":
        before = set(_porcelain())
        r = sh([sys.executable, "-m", "pytest", "tests/", "-q"], timeout=5400)
        grew = [ln for ln in _porcelain() if ln not in before]
        return r.returncode == 0 and not grew, "; ".join(grew)[:160]
    if k == "manual":
        return None, a.get("note", "manual check")
    return False, "unknown accept kind: %s" % k

def verdict(task):
    manual, fails = [], []
    for a in task.get("accept", []):
        ok, note = check(a)
        if ok is None:
            manual.append(note)
        elif not ok:
            fails.append(a["kind"] + ":" + a.get("path", a.get("args", "")))
    return (not fails), manual, fails

def eligible(st, only=None):
    done = {"verified", "needs_review"}
    for t in st["tasks"]:
        if only and t["id"] != only:
            continue
        if t["type"] == "agent" and t["status"] == "pending" and \
           all(any(d["id"] == x and d["status"] in done for d in st["tasks"])
               for x in t.get("deps", [])):
            return t
    return None

def build_prompt(task):
    prog = open(os.path.join(ROPE, "program.md"), encoding="utf-8").read()
    return (prog + "\n\n=== YOUR TASK (one task, surgical) ===\n"
            + json.dumps(task, indent=1)
            + "\n\nRules of engagement: edit only the files listed above; honor"
            " every rule in program.md; self-check with the accept spec; print"
            " DONE:%s and a one-line receipt; do NOT commit.\n" % task["id"])

def run_executor(task, model):
    with open(PROMPT_P, "w", encoding="utf-8") as f:
        f.write(build_prompt(task))
    t0 = time.time()
    budget = TIMEOUT.get(task.get("effort", "small"), 1200)
    try:
        with open(PROMPT_P, encoding="utf-8") as fin, open(RUNLOG, "w", encoding="utf-8") as flog:
            subprocess.run(claude_cmd(model), cwd=ROOT, stdin=fin, stdout=flog,
                           stderr=subprocess.STDOUT, timeout=budget)
    except subprocess.TimeoutExpired:
        pass  # verdict decides; karpathy: overrun == failure candidate
    return time.time() - t0

def tail_log(n=3):
    try:
        return " | ".join(open(RUNLOG, encoding="utf-8", errors="replace")
                          .read().splitlines()[-n:])
    except OSError:
        return ""

def preflight(st, args):
    assert os.path.exists(os.path.join(ROOT, "pyproject.toml")), "not the repo root"
    if subprocess.run((["cmd", "/c"] if os.name == "nt" else []) + ["claude", "--version"],
                      capture_output=True).returncode != 0:
        sys.exit("claude CLI not found on PATH -- install Claude Code first")
    if sh([sys.executable, "-m", "pytest", "--version"]).returncode != 0:
        sys.exit("pytest missing for this interpreter")
    if not (args.model and args.confirm_model):
        sys.exit("refusing to run: pass --model <id> --confirm-model "
                 "(model choice is confirmed by the human, by design)")
    if os.name == "nt" and not getattr(args, "live_seat_ok", False):
        tl = sh(["tasklist"]).stdout.lower()
        if any(k in tl for k in ("houdini", "hindie")):
            sys.exit("a Houdini process is running and this loop edits the tree "
                     "Houdini serves; close Houdini or pass --live-seat-ok")
    cur = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if cur != st["branch"]:
        if git("rev-parse", "--verify", st["branch"]).returncode == 0:
            git("checkout", st["branch"])
        else:
            git("checkout", "-b", st["branch"])
    dirty = "\n".join(
        ln for ln in git("status", "--porcelain", "-uno").stdout.splitlines()
        if "harness/rope/" not in ln.replace("\\", "/")
    ).strip()  # the runner's own state/card files never block the runner
    if dirty and not args.allow_dirty:
        sys.exit("tracked files are dirty; commit/stash or pass --allow-dirty:\n" + dirty)
    gi = os.path.join(ROOT, ".gitignore")
    ig = open(gi, encoding="utf-8").read() if os.path.exists(gi) else ""
    for line in ["harness/rope/results.tsv", "harness/rope/.prompt.txt",
                 "harness/rope/last_run.log", "harness/rope/runner_console.log",
                 "harness/rope/runner_console.err.log"]:
        if line not in ig:
            open(gi, "a", encoding="utf-8").write("\n" + line)
    if git("ls-files", "--error-unmatch", "harness/rope/runner.py").returncode != 0:
        git("add", "harness/rope", ".claude/agents/rope-executor.md", ".gitignore")
        git("commit", "-m", "rope: harness scaffolding (GATE A)")
    st["executor_model"] = args.model
    save(st)

def cmd_run(args):
    st = load()
    preflight(st, args)
    done = 0
    while True:
        t = eligible(st, args.task)
        if not t or (args.max and done >= args.max):
            break
        t["status"] = "in_progress"; save(st)
        dur = run_executor(t, args.model)
        ok, manual, fails = verdict(t)
        if ok:
            t["status"] = "needs_review" if manual else "verified"
            save(st)  # state to disk BEFORE the commit, so the commit is truthful
            git("add", "-A")
            git("commit", "-m", "rope:%s %s [%s]" % (t["id"], t["title"], t["law"]))
            ledger(t["id"], args.model, "keep", t["attempts"] + 1, dur,
                   ("manual pending: " + "; ".join(manual)) if manual else "clean")
        else:
            t["attempts"] += 1
            git("reset", "--hard", "HEAD")   # tracked only; NEVER git clean here
            t["status"] = "blocked" if t["attempts"] >= 2 else "pending"
            ledger(t["id"], args.model, "discard", t["attempts"], dur,
                   "fails: " + ", ".join(fails) + " | " + tail_log())
        save(st)
        done += 1
        if args.task:
            break
    cmd_gate(args)

def cmd_status(args):
    st = load()
    for t in st["tasks"]:
        print("%-6s %-13s a=%d  %s" % (t["id"], t["status"], t["attempts"], t["title"]))

def cmd_gate(args):
    st = load()
    tally = {}
    for t in st["tasks"]:
        tally[t["status"]] = tally.get(t["status"], 0) + 1
    open_ = [t["id"] for t in st["tasks"] if t["status"] != "verified"]
    print("GATE A:", "GREEN -- post may go up" if not open_ else
          "HOLDING -- open: " + ", ".join(open_))
    print("tally:", json.dumps(tally))

def cmd_human(args):
    st = load()
    for t in st["tasks"]:
        if t["id"] == args.id:
            ok, manual, fails = verdict(t)
            t["status"] = "verified" if (ok and args.done) else "needs_review"
            ledger(t["id"], "human", "keep" if ok else "partial", t["attempts"],
                   0, args.done or "; ".join(fails))
            save(st)
            return print(t["id"], "->", t["status"])
    sys.exit("no such task")

def cmd_verify(args):
    st = load()
    for t in st["tasks"]:
        if t["id"] == args.id:
            if args.passed:
                t["status"] = "verified"
            else:
                t["status"] = "blocked"
            ledger(t["id"], "human", "keep" if args.passed else "reject",
                   t["attempts"], 0, args.failed or "manual review")
            save(st)
            return print(t["id"], "->", t["status"])
    sys.exit("no such task")

def main():
    ap = argparse.ArgumentParser(prog="rope")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--model"); r.add_argument("--confirm-model", action="store_true")
    r.add_argument("--max", type=int); r.add_argument("--task"); r.add_argument("--allow-dirty", action="store_true")
    r.add_argument("--live-seat-ok", action="store_true")
    sub.add_parser("status"); sub.add_parser("gate")
    h = sub.add_parser("human"); h.add_argument("id"); h.add_argument("--done")
    v = sub.add_parser("verify"); v.add_argument("id")
    v.add_argument("--passed", action="store_true"); v.add_argument("--failed")
    args = ap.parse_args()
    {"run": cmd_run, "status": cmd_status, "gate": cmd_gate,
     "human": cmd_human, "verify": cmd_verify}[args.cmd](args)

if __name__ == "__main__":
    main()
