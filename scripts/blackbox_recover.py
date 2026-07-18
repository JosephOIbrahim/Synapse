"""BLACKBOX recover — reconstruct everything that was in flight when a Claude Code session died.

Usage:
  python scripts/blackbox_recover.py                    # auto-pick the last dead session for this repo
  python scripts/blackbox_recover.py --session <id>     # explicit session id (prefix ok)
  python scripts/blackbox_recover.py --list             # show candidate sessions, newest first

Options:
  --grace N        seconds; transcripts modified within N are treated as live and skipped (default 90)
  --project DIR    Claude project dir (default: derived from cwd -> ~/.claude/projects/<sanitized-cwd>)
  --out PATH       capsule path (default harness/state/recovery/<sid>-capsule.md)
  --no-git         skip the repo-state section
  --no-forensics   skip the Windows forensics section

Read-only everywhere except the capsule file it writes. Safe to run any time.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    from blackbox_mine import clip, content_items
except ImportError:  # invoked from outside scripts/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from blackbox_mine import clip, content_items


def project_dir_for(cwd):
    base = Path.home() / ".claude" / "projects"

    def sanitize(p):
        return re.sub(r"[:\\/.]", "-", str(p)).rstrip("-")

    # A session started in a repo SUBDIRECTORY maps to the repo root's project
    # dir — walk ancestors and take the first that actually exists.
    p = Path(cwd)
    for cand in (p, *p.parents):
        d = base / sanitize(cand)
        if d.is_dir():
            return d
    return base / sanitize(cwd)


def candidates(proj_dir):
    files = sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def pick_session(proj_dir, grace_s, explicit):
    files = candidates(proj_dir)
    if explicit:
        hits = [f for f in files if f.stem.startswith(explicit)]
        if not hits:
            sys.exit(f"no transcript matching --session {explicit} in {proj_dir}")
        return hits[0]
    now = dt.datetime.now().timestamp()
    for f in files:
        if now - f.stat().st_mtime > grace_s:
            return f
    sys.exit(f"no transcript older than --grace {grace_s}s in {proj_dir} (all look live)")


def parse_transcript(path):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    users, assistant_texts, tools, results = [], [], [], set()
    first_ts = last_ts = ""
    bad = 0
    last_msg_idx = -1
    for idx, ln in enumerate(lines):
        try:
            o = json.loads(ln)
        except Exception:
            bad += 1
            continue
        ts = o.get("timestamp", "")
        if ts:
            first_ts = first_ts or ts
            last_ts = ts
        t = o.get("type", "?")
        msg = o.get("message") or {}
        if msg and t in ("user", "assistant"):
            last_msg_idx = idx
        for item in content_items(msg):
            it = item.get("type")
            if it == "tool_use":
                tools.append({"idx": idx, "ts": ts, "id": item.get("id", ""),
                              "name": item.get("name", "?"), "input": item.get("input", {})})
            elif it == "tool_result":
                results.add(item.get("tool_use_id", ""))
            elif it == "text":
                txt = item.get("text", "")
                if not txt.strip():
                    continue
                if t == "user" and "command-name" not in txt and "local-command" not in txt \
                        and "task-notification" not in txt:
                    users.append((ts, clip(txt, 300)))
                elif t == "assistant":
                    assistant_texts.append((ts, clip(txt, 500)))
    unanswered = [tl for tl in tools if tl["id"] and tl["id"] not in results]
    # A tail-orphan has NO message after it — genuine death evidence. An orphan
    # the session talked past is a routine Esc-interrupt, not a crash.
    tail_orphans = [tl for tl in unanswered if tl["idx"] >= last_msg_idx]
    return {"n_lines": len(lines), "bad": bad, "first_ts": first_ts, "last_ts": last_ts,
            "users": users, "assistant_texts": assistant_texts, "tools": tools,
            "unanswered": unanswered, "tail_orphans": tail_orphans}


def mine_subagents(session_dir):
    out = []
    subdir = session_dir / "subagents"
    if not subdir.is_dir():
        return out
    for meta_path in sorted(subdir.glob("agent-*.meta.json")):
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
        agent = {"id": meta_path.stem.replace(".meta", ""),
                 "type": meta.get("agentType", "?"),
                 "desc": meta.get("description", "?"),
                 "last_ts": "", "last_tool": "", "interrupted": False}
        jsonl = meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl"))
        if jsonl.exists():
            parsed = parse_transcript(jsonl)
            agent["last_ts"] = parsed["last_ts"]
            if parsed["tools"]:
                tl = parsed["tools"][-1]
                agent["last_tool"] = f"{tl['name']}: {clip(json.dumps(tl['input']), 300)}"
            agent["interrupted"] = any("Request interrupted" in u[1] for u in parsed["users"])
        out.append(agent)
    return out


def mine_workflows(session_dir):
    out = []
    for wf_json in sorted((session_dir / "workflows").glob("wf_*.json") if (session_dir / "workflows").is_dir() else []):
        entry = {"id": wf_json.stem, "summary": "", "journal_tail": []}
        try:
            entry["summary"] = clip(json.dumps(json.loads(wf_json.read_text(encoding="utf-8"))), 200)
        except Exception:
            pass
        journal = session_dir / "subagents" / "workflows" / wf_json.stem / "journal.jsonl"
        if journal.exists():
            tail = journal.read_text(encoding="utf-8", errors="replace").splitlines()[-3:]
            entry["journal_tail"] = [clip(ln, 200) for ln in tail]
        out.append(entry)
    return out


def git_state(repo):
    def run(*args):
        try:
            r = subprocess.run(["git", *args], cwd=repo, capture_output=True,
                               text=True, timeout=15)
            return r.stdout.strip() or r.stderr.strip()
        except Exception as e:
            return f"(git unavailable: {e})"
    return (f"status --short:\n{run('status', '--short')}\n\n"
            f"stash list:\n{run('stash', 'list')}\n\n"
            f"log -3:\n{run('log', '--oneline', '-3')}")


def _ps(cmd, timeout=25):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout)
        return (r.stdout.strip() or r.stderr.strip() or "(no output)")
    except Exception as e:
        return f"(query failed: {e})"


def forensics(death_iso):
    # Timestamp comes from the transcript — validate before interpolating into PowerShell.
    death = death_iso if death_iso and re.fullmatch(r"[0-9T:.Z+\-]+", death_iso) else ""
    win = (f"$d=[datetime]::Parse('{death}').ToLocalTime(); "
           if death else "$d=Get-Date; ")
    sections = [
        ("Boot time", "(Get-CimInstance Win32_OperatingSystem).LastBootUpTime"),
        ("App/System errors ±30min of death", win +
         "Get-WinEvent -FilterHashtable @{LogName='Application','System'; Level=1,2; "
         "StartTime=$d.AddMinutes(-30); EndTime=$d.AddMinutes(30)} -MaxEvents 20 -ErrorAction SilentlyContinue "
         "| Select-Object TimeCreated, ProviderName, Id | Format-Table -AutoSize | Out-String"),
        ("Crash dumps <24h old", win +
         "Get-ChildItem \"$env:LOCALAPPDATA\\CrashDumps\" -ErrorAction SilentlyContinue "
         "| Where-Object {$_.LastWriteTime -gt $d.AddHours(-24)} | Select-Object Name, LastWriteTime "
         "| Format-Table -AutoSize | Out-String"),
        ("stderr crash logs", "foreach($f in \"$env:USERPROFILE\\.claude\\stderr-crash.log\","
         "\"$env:USERPROFILE\\claude-stderr.log\"){ if(Test-Path $f){ \"== $f ==\"; Get-Content $f -Tail 15 } }"),
    ]
    return "\n".join(f"### {title}\n```\n{_ps(cmd)}\n```" for title, cmd in sections)


def death_signature(parsed):
    sig = []
    if parsed["bad"]:
        sig.append(f"{parsed['bad']} unparseable line(s) — truncated write (hard kill) or encoding artifact")
    if parsed["tail_orphans"]:
        last = parsed["tail_orphans"][-1]
        sig.append(f"died mid-tool-call: {last['name']} at {last['ts']} never returned")
    return "; ".join(sig) or "tail looks clean (no orphaned tool call — external stop or idle death)"


def build_capsule(sid, path, parsed, agents, workflows, git_txt, forensics_txt):
    mb = round(path.stat().st_size / 1e6, 2)
    L = [f"# BLACKBOX RECOVERY CAPSULE — session {sid}",
         f"Generated: {dt.datetime.now().isoformat(timespec='seconds')} | "
         f"Transcript: {path} ({parsed['n_lines']} lines, {mb} MB)",
         f"Span: {parsed['first_ts']} -> {parsed['last_ts']}",
         f"**Death signature:** {death_signature(parsed)}", "",
         "## WHERE WE ARE (last exchanges)"]
    for ts, txt in parsed["users"][-5:]:
        L.append(f"- USER {ts}: {txt}")
    for ts, txt in parsed["assistant_texts"][-3:]:
        L.append(f"- ASSISTANT {ts}: {txt}")
    tail = parsed["tail_orphans"]
    stale = [tl for tl in parsed["unanswered"] if tl not in tail]
    L += ["", "## IN FLIGHT AT DEATH (resume points)"]
    for tl in tail[-5:]:
        L.append(f"- ORPHANED {tl['name']} ({tl['ts']}): {clip(json.dumps(tl['input']), 600)}")
    if not tail:
        L.append("- (none — no tool call orphaned at the tail)")
    if stale:
        L += ["", "## EARLIER ORPHANED CALLS (session continued after these — likely interrupts, verify before re-running)"]
        for tl in stale[-5:]:
            L.append(f"- {tl['name']} ({tl['ts']}): {clip(json.dumps(tl['input']), 400)}")
    L += ["", "## SUBAGENTS"]
    for a in agents or []:
        flag = "INTERRUPTED/KILLED" if a["interrupted"] else "last seen"
        L.append(f"- [{a['type']}] {a['desc']} — {flag} {a['last_ts']}")
        if a["last_tool"]:
            L.append(f"  last tool: {a['last_tool']}")
    if not agents:
        L.append("- (none)")
    L += ["", "## WORKFLOWS"]
    for w in workflows or []:
        L.append(f"- {w['id']}: {w['summary']}")
        for j in w["journal_tail"]:
            L.append(f"  journal: {j}")
    if not workflows:
        L.append("- (none)")
    if git_txt:
        L += ["", "## REPO STATE", "```", git_txt, "```"]
    if forensics_txt:
        L += ["", "## CRASH FORENSICS (best-effort)", forensics_txt]
    L += ["", "## NEXT ACTION",
          "- Re-run each ORPHANED call above; anything long-running goes DETACHED "
          "(Start-Process -> file in .synapse/), never inline — detached work survives the next death.",
          "- Re-dispatch killed subagents only if their output isn't already in memory/docs; "
          "check first — post-crash sessions re-ask answered questions.",
          "- Read the memory files before resuming: they are the authoritative state, not this capsule."]
    return "\n".join(L) + "\n"


def detect(proj, grace_s=90, window_h=6):
    """SessionStart-hook mode: one line if a recent session died mid-work, else silent.

    Scans ALL non-live transcripts inside the window (a trivial newer session must
    not mask a real crash) and reports the newest with a death signature. Never
    raises — a session-start hook must never hurt the session it runs in.
    """
    try:
        now = dt.datetime.now().timestamp()
        for f in candidates(proj):
            try:
                age = now - f.stat().st_mtime
            except OSError:
                continue
            if age <= grace_s:
                continue  # still being written — the live session
            if age > window_h * 3600:
                break  # sorted newest-first: everything after is older still
            parsed = parse_transcript(f)
            if parsed["tail_orphans"] or parsed["bad"]:
                print(f"[blackbox] Prior session {f.stem} may have died mid-work — "
                      f"{death_signature(parsed)}. "
                      f"Recover with: python scripts/blackbox_recover.py --session {f.stem}")
                break
    except Exception:
        pass
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--session")
    ap.add_argument("--project")
    ap.add_argument("--out")
    ap.add_argument("--grace", type=int, default=90)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--no-forensics", action="store_true")
    args = ap.parse_args(argv)

    proj = Path(args.project) if args.project else project_dir_for(os.getcwd())
    if not proj.is_dir():
        if args.detect:
            return 0  # a hook must never fail the session over a missing dir
        sys.exit(f"project dir not found: {proj}")
    if args.detect:
        return detect(proj, args.grace)
    if args.list:
        for f in candidates(proj)[:12]:
            mt = dt.datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="seconds")
            print(f"{f.stem}  {mt}  {round(f.stat().st_size/1e6, 2)} MB")
        return 0

    path = pick_session(proj, args.grace, args.session)
    sid = path.stem
    print(f"[blackbox] mining {path}")
    parsed = parse_transcript(path)
    session_dir = proj / sid
    agents = mine_subagents(session_dir)
    workflows = mine_workflows(session_dir)
    git_txt = "" if args.no_git else git_state(os.getcwd())
    forensics_txt = "" if args.no_forensics else forensics(parsed["last_ts"])

    capsule = build_capsule(sid, path, parsed, agents, workflows, git_txt, forensics_txt)
    out = Path(args.out) if args.out else Path("harness/state/recovery") / f"{sid}-capsule.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(capsule, encoding="utf-8")
    print(capsule)
    print(f"[blackbox] capsule written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
