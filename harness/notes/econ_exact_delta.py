"""The exact saving from the CLAUDE.md audit, and the proxy's error rate.

R154 reported 11,647 -> 9,578, a 2,069 saving, measured with tiktoken as a
proxy. count_tokens now works and the proxy UNDERCOUNTS: CLAUDE.md is 10,158
exact against 9,578 proxy, +6.1%.

So every figure in C1 and E0 is optimistic by roughly that margin, and the
conclusions that sit closest to a threshold are the ones to re-check.
"""
import json, subprocess, urllib.request, urllib.error

MODEL = "claude-sonnet-4-6"


def key_from_env():
    for line in open(".env", encoding="utf-8-sig", errors="replace"):
        line = line.strip()
        for n in ("SYNAPSE_ANTHROPIC_KEY", "ANTHROPIC_API_KEY"):
            if line.startswith(n + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")


KEY = key_from_env()


def count(text):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens",
        data=json.dumps({"model": MODEL,
                         "messages": [{"role": "user", "content": text}]}).encode(),
        headers={"x-api-key": KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=45))["input_tokens"]


BASE = count(".")

# The pre-audit file, from git rather than a backup I deleted.
before_src = subprocess.run(["git", "show", "f02fe89~2:CLAUDE.md"],
                            capture_output=True, text=True,
                            encoding="utf-8", errors="replace").stdout
after_src = open("CLAUDE.md", encoding="utf-8-sig").read()

b_exact = count(before_src) - BASE
a_exact = count(after_src) - BASE
b_proxy = int(len(before_src) / 3.6)
a_proxy = int(len(after_src) / 3.6)

print("%-14s %10s %10s %8s" % ("", "PROXY", "EXACT", "PROXY ERR"))
print("-" * 46)
print("%-14s %10d %10d %+7.1f%%" % ("before", b_proxy, b_exact,
                                    100.0 * (b_proxy - b_exact) / b_exact))
print("%-14s %10d %10d %+7.1f%%" % ("after", a_proxy, a_exact,
                                    100.0 * (a_proxy - a_exact) / a_exact))
print("-" * 46)
print("%-14s %10d %10d" % ("saved/turn", b_proxy - a_proxy, b_exact - a_exact))
print("%-14s %9.0f%% %9.0f%%" % ("of the file",
                                 100.0 * (b_proxy - a_proxy) / b_proxy,
                                 100.0 * (b_exact - a_exact) / b_exact))
print()
print("The proxy UNDERCOUNTS. Every C1 and E0 figure is optimistic by ~6%,")
print("and the conclusions nearest a threshold are the ones to re-check.")
