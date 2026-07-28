"""Context audit of CLAUDE.md - passes 05 and 06 only.

12,074 tokens paid on every turn of every session. E0 measured the panel tool
surface at 15,901-19,711, so this file is ~two-thirds of the entire tool surface
and nothing had ever measured it.

Five sections replaced with pointers, each with evidence:

  6.  Memory Evolution - Pokemon Model   937  memory/evolution.py is DEPRECATED:
                                              'SUPERSEDED by the Moneta backend.
                                              Do not extend it.' (RSI0, verified)
  9.  Implementation Phases              474  a build plan whose phases are done
  13. Key Type Definitions               193  a table of types in shared/types.py
  14. File Structure                     366  a tree that says synapse-agents/ -
                                              not even this repo's name
  15. Revision Manifest                  300  says of ITSELF: 'Historical -
                                              verified on Houdini 21.0.596 /
                                              v5.8.0. Not a current-build claim.'

NOT CUT, deliberately:
  1.  Lossless Execution Bridge        2,559  the /mcp safety anchors. hdefereval
                                              could not be refuted - it needs a
                                              graphical session, so its absence
                                              in hython is by design.
  11. Safety Rules                       986  the card says KEEP irreversible-
                                              action rules. This is those.
  16. Recursive Observability Loop     1,380  claims 'pinned by tests' and that
                                              was not checked. Left standing
                                              rather than cut on suspicion.

Replaced, not deleted: each pointer names the artifact that supersedes it, so a
reader who wanted the section finds the real thing instead of a gap.
"""
import io, re, sys

POINTERS = {
    "6.": ("## 6. Memory evolution",
           "Superseded. `memory/evolution.py` documents itself as **SUPERSEDED by the Moneta\n"
           "backend** and says *\"do not extend it\"* - live only for the legacy jsonl path.\n"
           "The current substrate is Moneta; see `python/synapse/memory/`.\n"),
    "9.": ("## 9. Implementation phases",
           "Historical. The phase plan is complete; `harness/legs.json` and\n"
           "`harness/notes/CTO_RULINGS_01.md` are the live record of what is being built and why.\n"),
    "13.": ("## 13. Key types",
            "`shared/types.py` is the definition. A table here can only go stale against it.\n"),
    "14.": ("## 14. File structure",
            "The file tree is the file tree. The version that was here described `synapse-agents/`,\n"
            "which is not this repository's name.\n"),
    "15.": ("## 15. Revision manifest",
            "Historical - the section said so itself: *verified on Houdini 21.0.596 / v5.8.0, not a\n"
            "current-build claim.* `git log` is the revision record; `CTO_RULINGS_01.md` is the\n"
            "decision record.\n"),
}

raw = open("CLAUDE.md", encoding="utf-8-sig").read()
lines = raw.split("\n")

out, i, cut = [], 0, []
while i < len(lines):
    ln = lines[i]
    m = re.match(r"^## (\d+)\.", ln)
    key = (m.group(1) + ".") if m else None
    if key in POINTERS:
        head, body = POINTERS[key]
        # measure what we are removing
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        removed = len("\n".join(lines[i:j]))
        cut.append((ln.strip(), int(removed / 3.6)))
        out.append(head)
        out.append("")
        out.append(body.rstrip())
        out.append("")
        i = j
        continue
    out.append(ln)
    i += 1

new = "\n".join(out)
with io.open("CLAUDE.md", "w", encoding="utf-8", newline="\n") as f:
    f.write(new)

before = int(len(raw) / 3.6)
after = int(len(new) / 3.6)
print("%-46s %8s" % ("SECTION REPLACED WITH A POINTER", "~TOKENS"))
print("-" * 58)
for name, t in cut:
    print("%-46s %8d" % (name[:46], t))
print("-" * 58)
print("%-46s %8d" % ("before", before))
print("%-46s %8d" % ("after", after))
print("%-46s %8d  (%.0f%%)" % ("saved per turn", before - after,
                               100.0 * (before - after) / max(before, 1)))
