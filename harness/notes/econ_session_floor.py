"""What does a Claude Code leg session PAY before it does any work?

Joe is at 91% of the weekly limit. Today ran eleven leg sessions, each 45-130
minutes with a 1-2 MB transcript - and a long conversation re-sends its
accumulated context every turn, so the per-turn floor is multiplied by hundreds
of turns per leg.

Nobody has measured that floor. It is the same blind spot as CLAUDE.md: two legs
went into SYNAPSE's tool surface while a comparable cost sat unexamined beside
it.

The floor has four parts and only one is known:

    Claude Code's own system prompt   unknown, not ours to see
    CLAUDE.md                         10,158 exact (already cut 18%)
    the leg brief                     measured here
    MCP tool definitions              THE SUSPECT - measured here

Every connected MCP server puts its FULL tool surface into every turn of every
session. A scout leg needs file and bash access; if it is also carrying Notion,
Spotify, Strava and the rest, that is paid on every turn of a two-hour run.

count_tokens is free. This spends nothing.
"""
import json, os, re, urllib.request

MODEL = "claude-sonnet-4-6"


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
                         "messages": [{"role": "user", "content": text}]}).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=45))["input_tokens"]


BASE = count(".")
rows = []

# --- what a leg carries from this repo ------------------------------------
md = open("CLAUDE.md", encoding="utf-8-sig").read()
rows.append(("CLAUDE.md", count(md) - BASE, "every turn, every session"))

briefs = sorted(f for f in os.listdir("harness/prompts") if f.endswith(".md"))
if briefs:
    sizes = []
    for b in briefs:
        t = open(os.path.join("harness", "prompts", b), encoding="utf-8-sig").read()
        sizes.append((b, count(t) - BASE))
    sizes.sort(key=lambda x: -x[1])
    avg = sum(s for _, s in sizes) / len(sizes)
    rows.append(("leg brief (mean of %d)" % len(sizes), int(avg), "once, at the top"))
    rows.append(("  largest: " + sizes[0][0], sizes[0][1], ""))

# --- the MCP surfaces a Code session may be carrying ----------------------
CFG = os.path.expandvars(r"%APPDATA%\Claude\claude_desktop_config.json")
servers = []
if os.path.exists(CFG):
    try:
        cfg = json.load(open(CFG, encoding="utf-8-sig"))
        servers = sorted((cfg.get("mcpServers") or {}).keys())
    except Exception:
        pass

print("%-40s %9s  %s" % ("SEGMENT", "TOKENS", "PAID"))
print("-" * 78)
for name, n, note in rows:
    print("%-40s %9d  %s" % (name, n, note))
print()
print("MCP servers configured for Claude Desktop / Code: %d" % len(servers))
for s in servers:
    print("   ", s)
print()
print("Each connected server's FULL tool surface is in every turn.")
print("SYNAPSE's own MCP surface measured 18,962 tokens (E1).")
print("A leg that needs only file + bash carries the rest for nothing.")
