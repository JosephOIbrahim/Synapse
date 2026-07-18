"""BLACKBOX miner — mine a Claude Code session transcript for crash forensics + in-flight state.

Usage: python scripts/blackbox_mine.py <transcript.jsonl>
Prints: session span, death/resume markers, agent spawns, task ops,
user goals, keyword-matched assistant text, last tool calls in full.
Read-only; safe on live or dead sessions.
"""
import json
import sys
import io

try:
    if (sys.stdout.encoding or "").lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except AttributeError:
    pass

KEYWORDS = ("crash", "died", "death", "killed", "orphan", "resurrect",
            "137", "OOM", "out of memory", "recover")


def clip(s, n=260):
    s = " ".join(str(s).split())
    return s[:n] + ("…" if len(s) > n else "")


def content_items(msg):
    c = msg.get("content")
    if isinstance(c, str):
        yield {"type": "text", "text": c}
    elif isinstance(c, list):
        yield from (i for i in c if isinstance(i, dict))


def main(path):
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    print(f"=== {path}: {len(lines)} lines ===")
    meta, agents, tasks, users, hits, tools = [], [], [], [], [], []
    bad = 0
    for idx, ln in enumerate(lines):
        try:
            o = json.loads(ln)
        except Exception:
            bad += 1
            continue
        t = o.get("type", "?")
        ts = o.get("timestamp", "")
        if t in ("queue-operation", "bridge-session", "summary"):
            meta.append((idx, ts, t, clip(o.get("summary", o.get("operation", "")), 120)))
            continue
        msg = o.get("message") or {}
        for item in content_items(msg):
            it = item.get("type")
            if it == "tool_use":
                name = item.get("name", "?")
                inp = item.get("input", {})
                tools.append((idx, ts, name, inp))
                if name == "Agent":
                    agents.append((idx, ts, clip(inp.get("description", ""), 80),
                                   clip(inp.get("prompt", ""), 200)))
                elif name in ("TaskCreate", "TaskUpdate"):
                    tasks.append((idx, ts, name, clip(json.dumps(inp), 200)))
            elif it == "text":
                txt = item.get("text", "")
                if t == "user" and "command-name" not in txt and "local-command" not in txt and txt.strip():
                    users.append((idx, ts, clip(txt, 300)))
                if t == "assistant" and any(k.lower() in txt.lower() for k in KEYWORDS):
                    hits.append((idx, ts, clip(txt, 400)))

    print(f"\n--- SESSION META (restart/queue markers): {len(meta)}")
    for m in meta[-12:]:
        print(f"  L{m[0]} {m[1]} [{m[2]}] {m[3]}")
    print(f"\n--- USER MESSAGES: {len(users)}")
    shown = users if len(users) <= 12 else users[:6] + [("...", "", "…gap…")] + users[-6:]
    for u in shown:
        print(f"  L{u[0]} {u[1]}: {u[2]}")
    print(f"\n--- AGENT SPAWNS: {len(agents)}")
    for a in agents:
        print(f"  L{a[0]} {a[1]} [{a[2]}] {a[3]}")
    print(f"\n--- TASK OPS: {len(tasks)}")
    for tk in tasks[-10:]:
        print(f"  L{tk[0]} {tk[1]} {tk[2]} {tk[3]}")
    print(f"\n--- KEYWORD HITS (assistant): {len(hits)}")
    for h in hits[-20:]:
        print(f"  L{h[0]} {h[1]}: {h[2]}")
    print("\n--- LAST 4 TOOL CALLS (full input):")
    for tl in tools[-4:]:
        print(f"  L{tl[0]} {tl[1]} {tl[2]}:")
        print("    " + clip(json.dumps(tl[3]), 1500))
    if bad:
        print(f"\n--- UNPARSEABLE LINES: {bad} (truncated write = hard-kill evidence)")


if __name__ == "__main__":
    main(sys.argv[1])
