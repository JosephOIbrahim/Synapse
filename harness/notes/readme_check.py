"""Check the README's mermaid blocks parse before pushing them.

A broken mermaid block renders as a grey error box on the GitHub page - the
first thing a visitor sees, on the file that is meant to establish the project
is careful. Cheap to check, embarrassing to miss.
"""
import re

t = open("README.md", encoding="utf-8").read()
blocks = re.findall(r"```mermaid(.*?)```", t, re.S)
print("  mermaid blocks:", len(blocks))

ok = True
for i, b in enumerate(blocks, 1):
    lines = [l for l in b.strip().split("\n") if l.strip()]
    kind = lines[0].strip() if lines else "?"
    quotes = b.count('"') % 2 == 0
    sq = b.count("[") == b.count("]")
    par = b.count("(") == b.count(")")
    br = b.count("{") == b.count("}")
    good = quotes and sq and par and br
    ok = ok and good
    print("  %d. %-12s %2d lines   quotes=%s square=%s paren=%s brace=%s"
          % (i, kind, len(lines), quotes, sq, par, br))

# The numbers the README asserts, against what the repo actually holds.
import json
import os
print()
print("  ASSERTED vs ACTUAL")
corpus = json.load(open("rag/corpus/h22_nodes.json", encoding="utf-8"))
n = len({e["type"].lower() for e in corpus["entries"]})
print("    h22 node types   README says 603   actual %d   %s" % (n, n == 603))
ver = open("VERSION", encoding="utf-8-sig").read().strip()
print("    VERSION          %s" % ver)
print()
print("RESULT:", "PASS" if ok else "FAIL - a block will render as an error box")
raise SystemExit(0 if ok else 1)
