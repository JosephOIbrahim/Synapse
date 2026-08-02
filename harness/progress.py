#!/usr/bin/env python3
"""The all-harness progress board — every harness bar, plus what is running now.

    python harness/progress.py              # one board, then exit
    python harness/progress.py --watch      # redraw every 300s
    python harness/progress.py --interval 60 --watch
    python harness/progress.py --fast       # skip slow verifiers, structure only
    python harness/progress.py --json       # machine-readable

WHAT THIS IS FOR
----------------
`harness/status.py` renders the leg board from legs.json. `harness/statusline.py`
renders one line into Claude Code. `harness/clear/progress.py` renders the CLEAR
bar. None of them answer the question this file exists for:

    "Several harnesses exist. Which ones are running, and how far along is each?"

DESIGN — three laws, each learned the hard way in this repo
-----------------------------------------------------------
1. DISCOVER, NEVER HARDCODE (R140). `harness/heats_status.py` was retired for
   baking seven legs into its print statements; it went on rendering that board
   for 23 legs and 115 rulings after they stopped existing, reading REAL
   receipts into a layout that no longer described anything. It never errored
   and never looked stale.

   So this file contains no list of harnesses. A harness is *any* directory
   under harness/ holding a verify.py. Add harness/rsi/verify.py and it appears
   here with no edit to this file. Delete one and it stops being rendered.

2. NO NUMBER WITHOUT A PRODUCER (Law 2). Every figure names the command or path
   that produced it, printed under the board. A number you cannot re-derive is
   a number you cannot trust.

3. '?' IS A VALID ANSWER, A GUESS IS NOT. Unreadable file, crashed verifier,
   missing directory -> '?'. This board never infers progress, never narrates,
   and never reports a stalled line as "in progress". A tool that lies quietly
   is worse than one that stops.

NO CACHE. Every figure is recomputed per render from its live source. A cached
board can describe a world that stopped existing.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode box-drawing glyphs.
# Force UTF-8; if the stream refuses, fall back to ASCII so the board always
# renders rather than dying on an encode error.
_UTF_OK = False
try:
    sys.stdout.reconfigure(encoding="utf-8")
    _UTF_OK = True
except Exception:
    try:
        sys.stdout.reconfigure(encoding="ascii")
    except Exception:
        pass

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "harness"
LOCKS = HARNESS / "state" / "locks"
WORKTREE_GUARD = HARNESS / "worktree_guard.py"

# Claude Code keeps live workflow transcripts outside the repo. Absent on a
# clean machine or a non-Claude run -> the section degrades to '?' rather than
# claiming nothing is running.
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects" / "C--Users-User-SYNAPSE"

# A run whose newest file is older than this is treated as finished, not live.
LIVE_WINDOW_S = 15 * 60

VERIFY_TIMEOUT_S = 120

if _UTF_OK:
    GLYPH = {"PASS": "█", "FAIL": "░", "PENDING": "▒", "UNKNOWN": "?"}
    TL, SIDE, BL, DOT = "┌─", "│", "└", "·"
else:
    GLYPH = {"PASS": "#", "FAIL": ".", "PENDING": "-", "UNKNOWN": "?"}
    TL, SIDE, BL, DOT = "+-", "|", "+", "."

WIDTH = 68


# ── primitives ──────────────────────────────────────────────────────────────

def _read(path):
    """Text or None. Never raises, never guesses."""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _run(cmd, timeout=60, cwd=None):
    """(rc, stdout, stderr). Never raises. rc=127 means 'could not run'."""
    try:
        p = subprocess.run(
            cmd, cwd=str(cwd or REPO), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", f"{type(e).__name__}: {e}"


def _newest_mtime(path: Path):
    """Newest mtime anywhere under path, or None. Bounded walk."""
    newest = None
    try:
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    m = (Path(root) / f).stat().st_mtime
                except OSError:
                    continue
                if newest is None or m > newest:
                    newest = m
    except OSError:
        return None
    return newest


def _age(seconds_ago):
    if seconds_ago is None:
        return "?"
    s = int(seconds_ago)
    if s < 90:
        return f"{s}s"
    if s < 90 * 60:
        return f"{s // 60}m"
    if s < 48 * 3600:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


# ── discovery: what harnesses exist ─────────────────────────────────────────

def discover_harnesses():
    """Every harness/<name>/verify.py, sorted. The manifest IS the filesystem.

    Producer: glob harness/*/verify.py
    """
    found = []
    try:
        for child in sorted(HARNESS.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            verify = child / "verify.py"
            if verify.is_file():
                found.append((child.name, child, verify))
    except OSError:
        return []
    return found


def _spec_title(hdir: Path):
    """First markdown H1 of SPEC.md, else '?'. Never invented."""
    spec = _read(hdir / "SPEC.md")
    if not spec:
        return "?"
    for line in spec.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "?"


def _last_log_row(hdir: Path):
    """Last dated table row in LOG.md — the harness's own record of its last
    attempt. Never synthesised from mtimes."""
    log = _read(hdir / "LOG.md")
    if not log:
        return None
    rows = [r for r in log.splitlines() if re.match(r"\|\s*20\d\d-", r)]
    return rows[-1].strip() if rows else None


def probe_harness(name, hdir, verify, fast=False):
    """Run <harness>/verify.py --json. Any failure -> UNKNOWN, never a guess."""
    rec = {
        "name": name,
        "title": _spec_title(hdir),
        "dir": str(hdir.relative_to(REPO)).replace("\\", "/"),
        "predicates": None,
        "pass": None,
        "fail": None,
        "pending": None,
        "note": "",
        "last_log": _last_log_row(hdir),
    }
    if fast:
        rec["note"] = "--fast: verifier not run"
        return rec

    rc, out, err = _run([sys.executable, str(verify), "--json"],
                        timeout=VERIFY_TIMEOUT_S)
    if rc == 127:
        rec["note"] = f"verifier could not run ({err.strip()[:60]})"
        return rec
    try:
        results = json.loads(out)
    except (json.JSONDecodeError, TypeError):
        # A verifier that runs but does not speak --json is still a harness;
        # say so plainly instead of scoring it.
        rec["note"] = "verifier returned no JSON (no --json contract)"
        return rec
    if not isinstance(results, list):
        rec["note"] = "verifier JSON was not a list of predicates"
        return rec

    rec["predicates"] = [
        {"id": str(r.get("id", "?")),
         "label": str(r.get("label", "")),
         "status": str(r.get("status", "UNKNOWN")).upper()}
        for r in results if isinstance(r, dict)
    ]
    rec["pass"] = sum(1 for r in rec["predicates"] if r["status"] == "PASS")
    rec["fail"] = sum(1 for r in rec["predicates"] if r["status"] == "FAIL")
    rec["pending"] = sum(1 for r in rec["predicates"] if r["status"] == "PENDING")
    return rec


# ── discovery: what is running right now ────────────────────────────────────

def discover_locks():
    """harness/state/locks/*.lock — written by lock.py / orchestrate.ps1.

    Producer: ls harness/state/locks/*.lock
    """
    out = []
    try:
        for p in sorted(LOCKS.glob("*.lock")):
            try:
                age = time.time() - p.stat().st_mtime
            except OSError:
                age = None
            body = (_read(p) or "").strip().splitlines()
            out.append({"name": p.stem,
                        "age_s": age,
                        "detail": body[0][:60] if body else ""})
    except OSError:
        return None
    return out


def _journal_results(journal: Path):
    """agentId -> its recorded result, for agents the run has already finished.

    Producer: <run>/journal.jsonl 'result' rows. This is the ONLY authority for
    'done' — an agent file can stop changing because it finished OR because it
    stalled, and those must not render the same.
    """
    out = {}
    if not journal.is_file():
        return out
    for line in _read(journal).splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") != "result" or not rec.get("agentId"):
            continue
        res = rec.get("result")
        out[rec["agentId"]] = res if isinstance(res, dict) else {}
    return out


def _agent_label(agent_jsonl: Path):
    """Best-effort lane name for an IN-FLIGHT agent, mined from its brief.

    Producer: the most frequent lane-shaped token (G1a, RL-3, P3.1 ...) in the
    first 3 KB of the dispatch prompt. Heuristic by construction — returns '?'
    rather than a guess when nothing matches, and is superseded by the
    journal's own `lane` the moment the agent reports.
    """
    try:
        with agent_jsonl.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(3000)
    except OSError:
        return "?"
    toks = re.findall(r"\b[A-Z]{1,3}\d{1,2}(?:[a-z]|\.\d{1,2}|-\d{1,2})?\b", head)
    if not toks:
        return "?"
    return max(set(toks), key=toks.count)


def discover_workflow_runs():
    """Live Claude Code workflow runs and their agent counts.

    Producer: ~/.claude/projects/C--Users-User-SYNAPSE/*/subagents/workflows/wf_*

    A run counts as LIVE when its newest file changed inside LIVE_WINDOW_S.
    Returns None (rendered '?') when the transcript root is absent — that means
    'cannot tell', which is NOT the same as 'nothing is running'.
    """
    if not CLAUDE_PROJECTS.is_dir():
        return None
    runs = []
    try:
        for session in CLAUDE_PROJECTS.iterdir():
            wf_root = session / "subagents" / "workflows"
            if not wf_root.is_dir():
                continue
            for run in wf_root.iterdir():
                if not run.is_dir() or not run.name.startswith("wf_"):
                    continue
                newest = _newest_mtime(run)
                if newest is None:
                    continue
                age = time.time() - newest
                if age > LIVE_WINDOW_S:
                    continue
                agents = sorted(a for a in run.glob("agent-*.jsonl"))
                done = _journal_results(run / "journal.jsonl")
                live_agents = 0
                rows = []
                for a in agents:
                    aid = a.stem[len("agent-"):]
                    try:
                        a_age = time.time() - a.stat().st_mtime
                    except OSError:
                        continue
                    finished = done.get(aid)
                    if finished is None and a_age <= LIVE_WINDOW_S:
                        live_agents += 1
                    rows.append({
                        "id": aid[:8],
                        "label": (finished or {}).get("lane") or _agent_label(a),
                        "state": (finished or {}).get("outcome", "DONE") if finished
                                 else ("running" if a_age <= LIVE_WINDOW_S else "stalled?"),
                        "done": finished is not None,
                        "age_s": a_age,
                    })
                rows.sort(key=lambda r: (r["done"], r["age_s"]))
                runs.append({"run": run.name,
                             "agents_total": len(agents),
                             "agents_recent": live_agents,
                             "agents_done": len(done),
                             "rows": rows,
                             "age_s": age})
    except OSError:
        return None
    runs.sort(key=lambda r: r["age_s"])
    return runs


def discover_worktrees():
    """Armed worktrees — uncommitted work that can be lost.

    Producer: git worktree list --porcelain
    """
    rc, out, _ = _run(["git", "worktree", "list", "--porcelain"], timeout=30)
    if rc != 0:
        return None
    return [ln.split(" ", 1)[1].strip()
            for ln in out.splitlines() if ln.startswith("worktree ")]


def current_branch():
    rc, out, _ = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=20)
    return out.strip() if rc == 0 and out.strip() else "?"


# ── render ──────────────────────────────────────────────────────────────────

def _bar_cells(rec):
    if rec["predicates"] is None:
        return None
    return "".join(GLYPH.get(p["status"], GLYPH["UNKNOWN"]) for p in rec["predicates"])


def _harness_line(rec):
    cells = _bar_cells(rec)
    if cells is None:
        return f"{rec['name']:<10} [{'?':<8}]  ?  {rec['note']}"
    total = len(rec["predicates"])
    tail = f"{rec['pass']}/{total} clear"
    if rec["fail"]:
        tail += f" {DOT} {rec['fail']} open"
    if rec["pending"]:
        tail += f" {DOT} {rec['pending']} wait"
    return f"{rec['name']:<10} [{cells}]  {tail}"


def render(records, locks, runs, worktrees, branch, fast):
    rule = "-" * WIDTH
    ts = time.strftime("%Y-%m-%d %H:%M")
    print(f"\n{TL} HARNESS PROGRESS {DOT} {ts} {DOT} {branch} {rule[:max(0, WIDTH - 34 - len(branch))]}")

    # ── harness bars
    if not records:
        print(f"{SIDE} harnesses  none discovered (no harness/*/verify.py)")
    else:
        print(f"{SIDE}")
        for rec in records:
            print(f"{SIDE} {_harness_line(rec)}")
            if rec["predicates"]:
                for p in rec["predicates"]:
                    if p["status"] != "PASS":
                        mark = "open" if p["status"] == "FAIL" else p["status"].lower()[:4]
                        print(f"{SIDE}   {mark:<5} {p['id']:<6} {p['label'][:44]}")
            if rec["last_log"]:
                print(f"{SIDE}   last  {rec['last_log'][:60]}")

    # ── what is running
    print(f"{SIDE}")
    if runs is None:
        print(f"{SIDE} running    ?  (workflow transcript root not found — cannot tell)")
    elif not runs:
        print(f"{SIDE} running    no live workflow runs in the last {LIVE_WINDOW_S // 60}m")
    else:
        for r in runs:
            done, total = r.get("agents_done", 0), r["agents_total"]
            cells = "".join("█" if row["done"] else ("▓" if row["state"] == "running" else "░")
                            for row in r["rows"])
            print(f"{SIDE} running    {r['run']}  [{cells}]  {done}/{total} reported"
                  f"  {DOT} {r['agents_recent']} live  (last write {_age(r['age_s'])} ago)")
            for row in r["rows"]:
                print(f"{SIDE}   {row['state']:<8} {row['label']:<20} {row['id']}"
                      f"  {_age(row['age_s'])} ago")

    if locks is None:
        print(f"{SIDE} locks      ?  (harness/state/locks unreadable)")
    elif locks:
        for lk in locks:
            print(f"{SIDE} locks      {lk['name']}  held {_age(lk['age_s'])}  {lk['detail']}")
    else:
        print(f"{SIDE} locks      none held")

    if worktrees is None:
        print(f"{SIDE} worktrees  ?  (git worktree list failed)")
    else:
        extra = [w for w in worktrees if Path(w).resolve() != REPO]
        print(f"{SIDE} worktrees  {len(extra)} armed" +
              (f"  {DOT} {', '.join(Path(w).name for w in extra[:4])}" if extra else ""))

    # ── producers (Law 2)
    print(f"{SIDE}")
    print(f"{SIDE} producers  bars: <harness>/verify.py --json" +
          ("  [SKIPPED: --fast]" if fast else ""))
    print(f"{SIDE}            running: ~/.claude/.../subagents/workflows/wf_*")
    print(f"{SIDE}            agent rows: <run>/journal.jsonl results (done) + "
          f"agent-*.jsonl mtime (live); label mined from the brief, '?' if unmatched")
    print(f"{SIDE}            locks: harness/state/locks/*.lock")
    print(f"{SIDE}            worktrees: git worktree list --porcelain")
    print(f"{BL}{rule}")


def collect(fast=False):
    harnesses = discover_harnesses()
    if harnesses:
        # Verifiers are independent and some shell out to pytest; run them
        # concurrently so the board stays usable as harness count grows.
        with ThreadPoolExecutor(max_workers=min(8, len(harnesses))) as pool:
            records = list(pool.map(
                lambda h: probe_harness(h[0], h[1], h[2], fast=fast), harnesses))
    else:
        records = []
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "branch": current_branch(),
        "harnesses": records,
        "locks": discover_locks(),
        "workflow_runs": discover_workflow_runs(),
        "worktrees": discover_worktrees(),
        "fast": fast,
    }


def main():
    ap = argparse.ArgumentParser(description="All-harness progress board.")
    ap.add_argument("--watch", action="store_true", help="redraw on an interval")
    ap.add_argument("--interval", type=int, default=300, help="seconds between redraws")
    ap.add_argument("--fast", action="store_true", help="skip verifiers (structure only)")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    args = ap.parse_args()

    def once():
        data = collect(fast=args.fast)
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            render(data["harnesses"], data["locks"], data["workflow_runs"],
                   data["worktrees"], data["branch"], data["fast"])
        return data

    if not args.watch:
        data = once()
        # Exit code carries the headline: nonzero when any predicate is open,
        # so the board composes into a shell pipeline like the other verifiers.
        open_count = sum(h["fail"] or 0 for h in data["harnesses"])
        sys.exit(1 if open_count else 0)

    try:
        while True:
            once()
            time.sleep(max(5, args.interval))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
