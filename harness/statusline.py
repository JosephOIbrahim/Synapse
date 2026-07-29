"""Claude Code statusline - the harness state, always on screen.

Wire it once, in .claude/settings.json:

    "statusLine": { "type": "command",
                    "command": "python C:/Users/User/SYNAPSE/harness/statusline.py" }

Stamp the suite figure by PIPING pytest into it - never by typing a number:

    python -m pytest tests/ -q | python harness/statusline.py --stamp

Renders, left to right, omitting anything that is zero:

    feat/repair-heats-01 │ !14 armed  >2 running  !6 attention  5296 ok 12m  4 agents

DESIGN
------
NO CACHE. Every figure is recomputed per render (~90ms) from its live source.
A cached statusline is a statusline that can describe a world that stopped
existing, which is this repo's own central defect: `harness/heats_status.py`
was retired for rendering real receipts into a layout that no longer described
anything, and it never errored and never looked stale.

ZERO SEGMENTS ARE HIDDEN. A bar that prints "0 armed" every day trains the eye
to skip it, and then it is not read on the day it says 14.

NO NUMBER WITHOUT A PRODUCER (Law 2). Each segment names its source:

    branch      git rev-parse --abbrev-ref HEAD
    armed       harness/worktree_guard.py  (git worktree list + resolution)
    running     harness/state/locks/*.lock (written by lock.py / orchestrate.ps1)
    attention   receipt `status` field per harness/legs.json
    suite       harness/state/suite_stamp.json, written ONLY by --stamp from a
                real pytest run. Absent -> the segment does not render. It is
                never inferred from .pytest_cache, whose `lastfailed` survives
                partial runs and read 43 failures on a tree whose full suite had
                just passed with zero.
    agents      live workflow agent transcripts for THIS session

The suite figure carries its age for exactly the reason above - a green tick
from yesterday is not evidence about today, and the age is how you tell.
"""
import json, os, re, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKS = os.path.join(ROOT, "harness", "state", "locks")
# Overridable so a test can stamp without clobbering the real figure - which a
# test did, on a tree where a background full-suite run was writing the same file.
STAMP = os.environ.get("SYNAPSE_SUITE_STAMP") or os.path.join(
    ROOT, "harness", "state", "suite_stamp.json")
MANIFEST = os.path.join(ROOT, "harness", "legs.json")
RDIR = os.path.join(ROOT, "harness", "notes", "receipts")

DIM = "\033[2m"
RED = "\033[31m"
YEL = "\033[33m"
CYA = "\033[36m"
GRN = "\033[32m"
OFF = "\033[0m"

GREEN_WORDS = {"green", "pass", "passed", "ok", "complete", "done"}
AGENT_LIVE_SECONDS = 120


def _git(*a):
    """Only for --stamp, which runs once. NEVER on the render path - see below."""
    try:
        r = subprocess.run(["git", "-C", ROOT] + list(a), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# THE RENDER PATH SPAWNS NO SUBPROCESSES.
#
# The first draft called worktree_guard.verify(), which runs `git rev-parse
# --show-toplevel` inside EVERY orphan directory to prove where writes would
# land. On this tree that is 14 spawns at ~49ms, and the bar took 919ms to
# draw - on every turn.
#
# The authoritative probe belongs in `worktree_guard.py audit`, which is run
# deliberately. The bar needs only the cheap half of the same question, and
# both halves read the same ground truth:
#
#   branch    .git/HEAD
#   registry  .git/worktrees/<name>/gitdir   (git's own record, one file each)
#
# Cost: file reads. No process spawn, no git.
# ---------------------------------------------------------------------------

def _norm(p):
    return os.path.normcase(os.path.normpath(os.path.abspath(p)))


def branch():
    try:
        with open(os.path.join(ROOT, ".git", "HEAD"), encoding="utf-8") as fh:
            head = fh.read().strip()
    except Exception:
        return "?"
    if head.startswith("ref: refs/heads/"):
        return head[len("ref: refs/heads/"):]
    return head[:8] if head else "?"          # detached


def registered_paths():
    """Worktree paths from git's own on-disk record, without invoking git."""
    out = {_norm(ROOT)}
    wt = os.path.join(ROOT, ".git", "worktrees")
    if not os.path.isdir(wt):
        return out
    for name in os.listdir(wt):
        try:
            with open(os.path.join(wt, name, "gitdir"), encoding="utf-8") as fh:
                out.add(_norm(os.path.dirname(fh.read().strip())))
        except Exception:
            pass
    return out


def legs():
    try:
        with open(MANIFEST, encoding="utf-8-sig") as fh:
            return json.load(fh)["legs"]
    except Exception:
        return []


def armed_count(all_legs):
    """Legs whose worktree directory exists but is not a registered worktree.

    The cheap half of worktree_guard's check. It can over-report a directory
    that is a worktree of a DIFFERENT repo (which the guard classifies
    'foreign'), and that is the correct direction to be wrong in: the bar says
    look, the guard says exactly what.
    """
    try:
        reg = registered_paths()
        n = 0
        for l in all_legs:
            w = l.get("worktree")
            if not w:
                continue
            p = w if os.path.isabs(w) else os.path.join(ROOT, w)
            if os.path.isdir(p) and _norm(p) not in reg:
                n += 1
        return n
    except Exception:
        return None  # unknown is not zero - renders as '?'


def running_legs():
    try:
        return [f[:-5] for f in os.listdir(LOCKS) if f.endswith(".lock")]
    except Exception:
        return []


def attention_count(all_legs):
    """Legs whose receipt exists but does not say a green word."""
    n = 0
    for leg in all_legs:
        if leg.get("state") in ("held", "done"):
            continue
        rc = leg.get("receipt")
        if not rc:
            continue
        p = os.path.join(RDIR, rc)
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as fh:
                s = str(json.load(fh).get("status", "")).strip().lower()
        except Exception:
            s = ""
        if s not in GREEN_WORDS:
            n += 1
    return n


def suite():
    try:
        with open(STAMP, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return None
    age = time.time() - d.get("at", 0)
    return {"passed": d.get("passed"), "failed": d.get("failed", 0), "age": age}


def live_agents(payload):
    """Workflow agent transcripts touched recently, for THIS session only."""
    tp = payload.get("transcript_path") or ""
    if not tp:
        return 0
    sess = tp[:-6] if tp.endswith(".jsonl") else tp
    wf = os.path.join(sess, "subagents", "workflows")
    if not os.path.isdir(wf):
        return 0
    now, n = time.time(), 0
    try:
        for run in os.listdir(wf):
            d = os.path.join(wf, run)
            if not os.path.isdir(d):
                continue
            for f in os.listdir(d):
                if f.startswith("agent-") and f.endswith(".jsonl"):
                    try:
                        if now - os.path.getmtime(os.path.join(d, f)) < AGENT_LIVE_SECONDS:
                            n += 1
                    except OSError:
                        pass
    except Exception:
        return 0
    return n


def human_age(sec):
    if sec < 90:
        return "%ds" % int(sec)
    if sec < 5400:
        return "%dm" % int(sec / 60)
    if sec < 172800:
        return "%dh" % int(sec / 3600)
    return "%dd" % int(sec / 86400)


def render(payload):
    L = legs()
    parts = ["%s%s%s" % (DIM, branch(), OFF)]

    a = armed_count(L)
    if a is None:
        parts.append("%s?armed%s" % (YEL, OFF))
    elif a:
        parts.append("%s!%d armed%s" % (RED, a, OFF))

    r = running_legs()
    if r:
        parts.append("%s>%d running%s" % (CYA, len(r), OFF))

    at = attention_count(L)
    if at:
        parts.append("%s!%d attention%s" % (YEL, at, OFF))

    s = suite()
    if s:
        stale = s["age"] > 86400
        col = RED if s["failed"] else (YEL if stale else GRN)
        mark = "%d fail" % s["failed"] if s["failed"] else "ok"
        parts.append("%s%s %s%s %s%s%s"
                     % (col, s["passed"], mark, OFF, DIM, human_age(s["age"]), OFF))

    n = live_agents(payload)
    if n:
        parts.append("%s%d agents%s" % (DIM, n, OFF))

    sep = "%s %s %s" % (DIM, globals().get("SEP_GLYPH", "|"), OFF)
    return parts[0] + (sep + "  ".join(parts[1:]) if len(parts) > 1 else "")


def stamp():
    """Read a real pytest summary off stdin. The number is never typed."""
    text = sys.stdin.read()
    # Anchor to pytest's SUMMARY line, scanning from the end. A plain
    # re.search over the whole stream matches the first '(\d+) skipped'
    # anywhere in it - which on this repo's output is a different number than
    # the summary's, and stamped 2 for a run that skipped 137.
    summary = ""
    for line in reversed(text.splitlines()):
        if re.search(r"\d+ (passed|failed|error)", line):
            summary = line
            break
    m = re.search(r"(\d+) passed", summary)
    if not m:
        print("no pytest summary on stdin - nothing stamped", file=sys.stderr)
        return 1
    if int(m.group(1)) == 0:
        # '0 passed, N errors' is a collection failure, not a green suite.
        # Stamping it would put a confident figure on screen for a tree whose
        # tests never ran.
        print("0 passed - collection failure, not a suite result. Nothing stamped.",
              file=sys.stderr)
        return 1
    failed = re.search(r"(\d+) failed", summary)
    skipped = re.search(r"(\d+) skipped", summary)
    rec = {
        "at": time.time(),
        "passed": int(m.group(1)),
        "failed": int(failed.group(1)) if failed else 0,
        "skipped": int(skipped.group(1)) if skipped else 0,
        "commit": _git("rev-parse", "HEAD")[:12],
        "branch": branch(),
        "producer": "python -m pytest tests/ -q | python harness/statusline.py --stamp",
    }
    os.makedirs(os.path.dirname(STAMP), exist_ok=True)
    tmp = STAMP + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    os.replace(tmp, STAMP)
    print("stamped: %d passed, %d failed, %d skipped @ %s"
          % (rec["passed"], rec["failed"], rec["skipped"], rec["commit"]))
    return 0


def main():
    # Windows consoles default to cp1252, which cannot encode the separator.
    # Reconfigure rather than downgrade the glyph; fall back only if it fails.
    sep_ok = True
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        sep_ok = False
    globals()["SEP_GLYPH"] = "│" if sep_ok else "|"

    if "--stamp" in sys.argv[1:]:
        return stamp()
    payload = {}
    if not sys.stdin.isatty():
        try:
            payload = json.loads(sys.stdin.read() or "{}")
        except Exception:
            payload = {}
    try:
        print(render(payload))
    except Exception as e:
        # A statusline that raises leaves an empty strip and no explanation.
        print("%sstatusline error: %s%s" % (RED, str(e)[:60], OFF))
    return 0


if __name__ == "__main__":
    sys.exit(main())
