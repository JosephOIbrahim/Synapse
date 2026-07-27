import re, sys

txt = open('README.md', encoding='utf-8-sig').read()
blocks = re.findall(r"```mermaid\n(.*?)```", txt, re.DOTALL)
print("mermaid blocks:", len(blocks))
print()

bad = 0
for i, b in enumerate(blocks, 1):
    lines = [l.rstrip() for l in b.strip().split("\n")]
    head = lines[0]
    ok_head = re.match(r"^(flowchart|graph|sequenceDiagram|classDiagram|stateDiagram)", head)
    # unbalanced quotes or brackets are the usual GitHub render failure
    unbal_q = any(l.count('"') % 2 for l in lines)
    unbal_b = sum(l.count("[") - l.count("]") for l in lines)
    unbal_p = sum(l.count("(") - l.count(")") for l in lines)
    status = []
    if not ok_head: status.append("BAD HEADER: " + head[:40])
    if unbal_q:     status.append("UNBALANCED QUOTES")
    if unbal_b:     status.append("UNBALANCED [] (%d)" % unbal_b)
    if unbal_p:     status.append("UNBALANCED () (%d)" % unbal_p)
    print("  block %d: %-22s %d lines  %s"
          % (i, head[:22], len(lines), "  ".join(status) if status else "OK"))
    if status:
        bad += 1

print()
print("headings:", txt.count("\n## "))
print("lines    :", txt.count("\n") + 1)
print()
print("RESULT:", "PASS" if bad == 0 else "FAIL - %d block(s) would not render" % bad)
sys.exit(0 if bad == 0 else 1)
