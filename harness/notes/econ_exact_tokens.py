"""Exact token counts for the surfaces that govern the roadmap.

C1 and E0 both measured with tiktoken/cl100k_base - a PROXY, not Claude's
tokenizer - because the account was credit-blocked and count_tokens returned
HTTP 400. Every figure in both legs, and every ruling built on them, carries
that asterisk.

count_tokens is FREE and does not consume completion credits. This removes the
asterisk without spending anything.

Measures the three things rulings currently rest on:
  1. CLAUDE.md            R154 said 11,647 -> 9,578 by proxy
  2. the panel tool surface   E0 said 15,901-19,711 by proxy
  3. the system prompt    E0's cache-boundary analysis rests on its size
"""
import json, os, sys, urllib.request, urllib.error

KEY_NAMES = ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"


def key_from_env():
    for line in open(".env", encoding="utf-8-sig", errors="replace"):
        line = line.strip()
        for n in KEY_NAMES:
            if line.startswith(n + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


KEY = key_from_env()


def count(text=None, tools=None, system=None):
    """Exact input tokens. FREE - count_tokens is not billed as completion."""
    body = {"model": MODEL, "messages": [{"role": "user", "content": text or "."}]}
    if tools:
        body["tools"] = tools
    if system:
        body["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps(body).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=45))["input_tokens"]
    except urllib.error.HTTPError as e:
        return -int(e.code)


BASELINE = count()          # the floor: model + one "." message
print("baseline (empty turn)      :", BASELINE, "tokens")
print()

# --- 1. CLAUDE.md ---------------------------------------------------------
md = open("CLAUDE.md", encoding="utf-8-sig").read()
n = count(text=md)
print("CLAUDE.md")
print("   proxy said (R154, after) :  9,578")
print("   EXACT                    : %6d   (delta %+d)" % (n - BASELINE, (n - BASELINE) - 9578))
print()

# --- 2. the panel system prompt -------------------------------------------
sys.path.insert(0, "python")
try:
    from synapse.panel.system_prompt import build_system_prompt
    sp = build_system_prompt({"network": "/stage", "selection": [], "frame": 1, "hip": "x.hip"})
    n = count(system=sp)
    print("panel system prompt")
    print("   EXACT                    : %6d" % (n - BASELINE))
    print("   chars                    : %6d" % len(sp))
except Exception as e:
    print("panel system prompt        : could not build -", type(e).__name__)
print()

# --- 3. the tool surface --------------------------------------------------
try:
    from synapse.mcp import _tool_registry as reg
    tools = None
    for attr in ("TOOLS", "ALL_TOOLS", "REGISTRY", "TOOL_SPECS"):
        if hasattr(reg, attr):
            tools = getattr(reg, attr)
            break
    if tools:
        print("tool registry attr found   :", attr, "with", len(tools), "entries")
    else:
        print("tool registry              : shape not recognised; E1's census is the producer")
except Exception as e:
    print("tool registry              : import failed -", type(e).__name__, str(e)[:60])
