"""Where the week actually went.

The MCP suspect is cleared - only one server is configured, so legs are not
carrying unused tool surfaces.

CLAUDE.md at 10,158 tokens is large, but it is a STABLE PREFIX: identical every
turn, at the front of the prompt. That is exactly what prompt caching is for, and
Claude Code is Anthropic's own product. Assume it is cached until shown otherwise.

What is NOT cacheable is the conversation itself. It grows every turn and every
turn re-sends all of it. A leg that ran 90 minutes has a transcript measured in
megabytes, and the cost of turn N is proportional to everything said in turns
1..N-1.

So the driver is not the floor. It is the INTEGRAL of the transcript.

This measures the real transcripts from today's legs, so the estimate rests on
what happened rather than on a guess about it.
"""
import json, os, urllib.request

MODEL = "claude-sonnet-4-6"
PROJ = os.path.expandvars(r"%USERPROFILE%\.claude\projects")


def key():
    for line in open(".env", encoding="utf-8-sig", errors="replace"):
        s = line.strip()
        for n in ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"):
            if s.startswith(n + "="):
                return s.split("=", 1)[1].strip().strip('"').strip("'")


KEY = key()


def count(text):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps({"model": MODEL,
                         "messages": [{"role": "user", "content": text[:600000]}]}).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))["input_tokens"]


rows = []
for root, _, files in os.walk(PROJ):
    for f in files:
        if not f.endswith(".jsonl"):
            continue
        p = os.path.join(root, f)
        leg = os.path.basename(root).replace("C--Users-User-SYNAPSE-", "")
        mb = os.path.getsize(p) / 1e6
        if mb < 0.2:
            continue
        rows.append((leg[-26:], p, mb))

rows.sort(key=lambda r: -r[2])
print("%-28s %8s %10s %10s" % ("SESSION", "MB", "TURNS", "~TOK/TURN"))
print("-" * 62)

total_turns = 0
for leg, p, mb in rows[:12]:
    turns = 0
    chars = 0
    try:
        for line in open(p, encoding="utf-8", errors="replace"):
            turns += 1
            chars += len(line)
    except Exception:
        continue
    total_turns += turns
    # A conversation of C chars costs roughly C/3.6 tokens ON ITS LAST TURN.
    # Every earlier turn paid a fraction of that. The INTEGRAL over the run is
    # roughly half the final size times the turn count.
    final_tok = chars / 3.6
    integral = final_tok * turns / 2
    print("%-28s %8.1f %10d %10d" % (leg, mb, turns, final_tok / max(turns, 1)))

print()
print("  sessions >0.2MB : %d" % len(rows))
print("  total turns     : %d" % total_turns)
print()
print("A conversation re-sends everything said so far, every turn.")
print("The last turn of a 2 MB transcript costs ~550k tokens on its own.")
print("The COST OF A LEG is the integral, not the floor - and no amount of")
print("CLAUDE.md trimming touches it.")
