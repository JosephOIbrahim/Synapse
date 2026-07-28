"""Measure CLAUDE.md per section before cutting a word of it.

The context card's six passes are judgement calls. Judgement is cheap to apply
badly to a 463-line file, so this establishes WHERE the mass is first - the same
discipline E1 applied to the tool surface, where it found no Pareto
concentration and changed the plan.

12,074 tokens is paid on every turn of every session. E0 measured the panel
tool surface at 15,901-19,711, so this file is ~two-thirds of the entire tool
surface and has never been measured.
"""
import re, sys

RAW = open("CLAUDE.md", encoding="utf-8-sig").read()
LINES = RAW.split("\n")

# Split on level-2 headings.
sections, cur, buf = [], "(preamble)", []
for ln in LINES:
    if ln.startswith("## "):
        sections.append((cur, buf))
        cur, buf = ln[3:].strip(), []
    else:
        buf.append(ln)
sections.append((cur, buf))

rows = []
for name, body in sections:
    text = "\n".join(body)
    rows.append((name, len(body), len(text), int(len(text) / 3.6)))

total_t = sum(r[3] for r in rows)
rows.sort(key=lambda r: -r[3])

print("CLAUDE.md - %d lines, %d chars, ~%d tokens" % (len(LINES), len(RAW), total_t))
print("=" * 74)
print("%-44s %6s %8s %6s" % ("SECTION", "LINES", "~TOKENS", "% OF FILE"))
print("-" * 74)
run = 0
for name, nl, nc, nt in rows:
    run += nt
    print("%-44s %6d %8d %5.1f%%" % (name[:44], nl, nt, 100.0 * nt / max(total_t, 1)))

print()
# Where does half the file live?
half = None
run = 0
for i, (name, nl, nc, nt) in enumerate(rows, 1):
    run += nt
    if half is None and run >= total_t * 0.5:
        half = i
print("  %d of %d sections carry 50%% of the file" % (half or 0, len(rows)))
print()

# Pass-06 signal: prose describing something that exists as an artifact.
print("PASS 06 CANDIDATES - prose describing what already exists as code")
for name, nl, nc, nt in rows:
    low = name.lower()
    if any(k in low for k in ("file structure", "type definition", "revision",
                              "manifest", "implementation phase", "roster")):
        print("   %-42s ~%d tokens" % (name[:42], nt))
print()
print("PASS 05 CANDIDATE - documents a subsystem RSI0 found DEPRECATED")
for name, nl, nc, nt in rows:
    if "evolution" in name.lower() or "pok" in name.lower():
        print("   %-42s ~%d tokens" % (name[:42], nt))
        print("      memory/evolution.py: 'SUPERSEDED by the Moneta backend...")
        print("      Do not extend it.' - RSI0, verified")
